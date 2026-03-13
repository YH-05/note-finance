#!/usr/bin/env python3
"""Asset Management Session Preparation Script.

JP RSSフィードから資産形成関連ニュースを収集し、テーマ別キーワード
マッチングを行い、セッションJSONを出力するスクリプト。

GitHub Issue連携は含まない（ローカル処理のみ）。

Usage
-----
    uv run python scripts/prepare_asset_management_session.py --days 14 --themes all

Output
------
    Session JSON file in ``.tmp/`` directory.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pydantic import BaseModel, Field
from session_utils import (
    ArticleData,
    configure_logging,
    filter_by_date,
    load_json_config,
    select_top_n,
    write_session_file,
)
from session_utils import (
    get_logger as _get_logger,
)

from rss.config.wealth_scraping_config import WEALTH_URL_TO_SOURCE_KEY

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_DAYS = 14
"""Default number of days to look back for articles."""

DEFAULT_THEMES = "all"
"""Default theme filter (all themes)."""

DEFAULT_TOP_N = 10
"""Default number of top articles per theme (sorted by published date, newest first)."""

DEFAULT_PRESETS = "jp"
"""Default preset key for RSS feed configuration."""

THEME_CONFIG_PATH = Path("data/config/asset-management-themes.json")
"""Path to asset management theme configuration file."""

RSS_PRESETS_JP_PATH = Path("data/config/rss-presets-jp.json")
"""Path to JP RSS presets configuration file."""

RSS_PRESETS_WEALTH_PATH = Path("data/config/rss-presets-wealth.json")
"""Path to Wealth RSS presets configuration file."""

# Mapping from preset key to file path
PRESET_KEY_TO_PATH: dict[str, Path] = {
    "jp": RSS_PRESETS_JP_PATH,
    "wealth": RSS_PRESETS_WEALTH_PATH,
}
"""Mapping from preset key to configuration file path."""

TMP_DIR = Path(".tmp")
"""Temporary directory for session files."""

FEED_READ_LIMIT = 100
"""Maximum number of items to fetch from FeedReader per search call."""

MAX_DAYS = 365
"""Maximum allowed value for --days argument."""

MAX_TOP_N = 100
"""Maximum allowed value for --top-n argument."""


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

logger = _get_logger(__name__)


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------


class AssetManagementThemeData(BaseModel):
    """Data for a single asset management theme.

    Attributes
    ----------
    name_ja : str
        Japanese name of the theme.
    articles : list[ArticleData]
        List of matched articles for this theme.
    keywords_used : list[str]
        Keywords used for matching.
    """

    name_ja: str
    articles: list[ArticleData] = Field(default_factory=list)
    keywords_used: list[str] = Field(default_factory=list)


class AssetManagementStats(BaseModel):
    """Session statistics for asset management workflow.

    Attributes
    ----------
    total : int
        Total number of articles fetched from RSS.
    filtered : int
        Number of articles after date filtering.
    matched : int
        Number of articles matched by keywords.
    """

    total: int
    filtered: int
    matched: int


class AssetManagementSession(BaseModel):
    """Complete asset management session data.

    Attributes
    ----------
    session_id : str
        Unique session identifier (asset-mgmt-{YYYYMMDD}-{HHMMSS}).
    timestamp : str
        Session creation timestamp in ISO 8601 format.
    themes : dict[str, AssetManagementThemeData]
        Theme data keyed by theme key.
    stats : AssetManagementStats
        Session statistics.
    """

    session_id: str
    timestamp: str
    themes: dict[str, AssetManagementThemeData] = Field(default_factory=dict)
    stats: AssetManagementStats


# ---------------------------------------------------------------------------
# CLI Argument Parsing
# ---------------------------------------------------------------------------


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Parameters
    ----------
    args : list[str] | None
        Command-line arguments. If None, uses sys.argv.

    Returns
    -------
    argparse.Namespace
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Prepare asset management session for AI workflow.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--presets",
        type=str,
        default=DEFAULT_PRESETS,
        help=(
            f"RSS preset key ('jp', 'wealth') or path to a preset JSON file "
            f"(default: {DEFAULT_PRESETS})"
        ),
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        help=f"Number of days to look back (default: {DEFAULT_DAYS})",
    )
    parser.add_argument(
        "--themes",
        type=str,
        default=DEFAULT_THEMES,
        help="Comma-separated theme keys or 'all' (default: all)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=DEFAULT_TOP_N,
        help=f"Max articles per theme, newest first (default: {DEFAULT_TOP_N})",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path (default: auto-generated in .tmp/)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    parsed = parser.parse_args(args)

    # Validate ranges
    if parsed.days <= 0 or parsed.days > MAX_DAYS:
        parser.error(f"--days must be between 1 and {MAX_DAYS}")
    if parsed.top_n < 0 or parsed.top_n > MAX_TOP_N:
        parser.error(f"--top-n must be between 0 and {MAX_TOP_N}")

    # Validate output path
    if parsed.output:
        output_path = Path(parsed.output).resolve()
        allowed_base = Path(".tmp").resolve()
        if not str(output_path).startswith(str(allowed_base)):
            parser.error(f"Output path must be within .tmp/: {parsed.output}")

    return parsed


# ---------------------------------------------------------------------------
# Configuration Loading
# ---------------------------------------------------------------------------


def resolve_presets_path(presets_key: str) -> Path:
    """Resolve a preset key or file path to a Path object.

    Parameters
    ----------
    presets_key : str
        A preset key ('jp', 'wealth') or a path to a JSON file.

    Returns
    -------
    Path
        Resolved Path to the presets configuration file.
    """
    if presets_key in PRESET_KEY_TO_PATH:
        return PRESET_KEY_TO_PATH[presets_key]
    return Path(presets_key)


def load_rss_presets(
    presets_path: Path = RSS_PRESETS_JP_PATH,
) -> list[dict[str, Any]]:
    """Load RSS presets configuration from the given file path.

    Parameters
    ----------
    presets_path : Path
        Path to the RSS presets configuration file.

    Returns
    -------
    list[dict[str, Any]]
        List of RSS preset entries (enabled only).

    Raises
    ------
    FileNotFoundError
        If configuration file does not exist.
    json.JSONDecodeError
        If configuration file is not valid JSON.
    """
    data = load_json_config(presets_path)
    presets = data.get("presets", [])
    enabled = [p for p in presets if p.get("enabled", True)]

    logger.debug("loaded_rss_presets", total=len(presets), enabled=len(enabled))
    return enabled


# ---------------------------------------------------------------------------
# Keyword Matching
# ---------------------------------------------------------------------------


def match_keywords(
    item: dict[str, Any],
    keywords: list[str],
) -> bool:
    """Check if an RSS item matches any of the given keywords.

    Performs case-insensitive partial matching on the ``title`` and
    ``summary`` fields of the item.

    Parameters
    ----------
    item : dict[str, Any]
        RSS item dictionary containing ``title`` and ``summary`` keys.
    keywords : list[str]
        List of keywords to match against.

    Returns
    -------
    bool
        True if any keyword is found in the item's title or summary.
    """
    if not keywords:
        return False

    title = (item.get("title") or "").lower()
    summary = (item.get("summary") or "").lower()
    text = f"{title} {summary}"

    for keyword in keywords:
        if keyword.lower() in text:
            logger.debug(
                "keyword_matched",
                keyword=keyword,
                title=item.get("title", ""),
            )
            return True

    return False


# ---------------------------------------------------------------------------
# RSS Feed Fetching by Source
# ---------------------------------------------------------------------------

# Map URL patterns to source keys used in theme config
URL_TO_SOURCE_KEY: dict[str, str] = {
    "fsa.go.jp": "fsa",
    "boj.or.jp": "boj",
    "dir.co.jp": "daiwa",
    "jpx.co.jp": "jpx",
    "emaxis": "emaxis",
    "morningstar": "morningstar_jp",
}
"""Mapping from URL domain patterns to source keys."""


def resolve_source_key(url: str) -> str:
    """Resolve a source key from a URL using domain pattern matching.

    Parameters
    ----------
    url : str
        RSS feed URL.

    Returns
    -------
    str
        Resolved source key, or ``"unknown"`` if no pattern matched.
    """
    for pattern, key in URL_TO_SOURCE_KEY.items():
        if pattern in url:
            return key
    return "unknown"


def _extract_domain(url: str) -> str:
    """Extract domain from a URL.

    Parameters
    ----------
    url : str
        URL string.

    Returns
    -------
    str
        Domain part of the URL, or empty string on failure.
    """
    try:
        return url.split("/")[2]
    except (IndexError, AttributeError):
        return ""


def fetch_items_by_source(
    presets: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Fetch RSS items grouped by source key.

    Source keys are derived from the ``target_sources`` values in the theme
    config (e.g. ``fsa``, ``morningstar_jp``).  The mapping from preset
    ``title`` to source key uses a simple heuristic based on the URL domain.

    Parameters
    ----------
    presets : list[dict[str, Any]]
        Enabled RSS preset entries from ``rss-presets-jp.json``.

    Returns
    -------
    dict[str, list[dict[str, Any]]]
        RSS items keyed by source key.
    """
    # AIDEV-NOTE: We use rss.services.feed_reader.FeedReader which reads
    # from local JSON files. For JP feeds that may not have local data yet,
    # items will simply be empty.
    from rss.services.feed_reader import FeedReader

    logger.info("fetching_items_by_source", preset_count=len(presets))

    items_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)

    # Build a set of (source_key, domain) pairs from presets
    preset_mapping: list[tuple[str, str, str]] = []
    for preset in presets:
        url = preset.get("url", "")
        title = preset.get("title", "Unknown")
        source_key = resolve_source_key(url)
        domain = _extract_domain(url)
        preset_mapping.append((source_key, domain, title))

    # Try reading from local RSS data - fetch all items once (N+1 fix)
    data_dir = Path("data/raw/rss")
    if data_dir.exists():
        try:
            reader = FeedReader(data_dir)
            all_items = reader.search_items(query="", limit=FEED_READ_LIMIT)

            # Index items by domain
            items_by_domain: dict[str, list[Any]] = defaultdict(list)
            for fi in all_items:
                if fi.link:
                    item_domain = _extract_domain(fi.link)
                    items_by_domain[item_domain].append(fi)

            # Assign items to source keys based on domain matching
            for source_key, domain, title in preset_mapping:
                for fi in items_by_domain.get(domain, []):
                    items_by_source[source_key].append(
                        {
                            "item_id": fi.item_id,
                            "title": fi.title,
                            "link": fi.link,
                            "published": fi.published,
                            "summary": fi.summary or "",
                            "content": fi.content,
                            "author": fi.author,
                            "fetched_at": fi.fetched_at,
                            "feed_source": title,
                        }
                    )

        except (OSError, ValueError) as e:
            logger.warning("feed_reader_failed", error=str(e))

    for source_key, _, _ in preset_mapping:
        logger.debug(
            "source_items_fetched",
            source_key=source_key,
            count=len(items_by_source.get(source_key, [])),
        )

    return dict(items_by_source)


# ---------------------------------------------------------------------------
# Theme Processing
# ---------------------------------------------------------------------------


def process_themes(
    items_by_source: dict[str, list[dict[str, Any]]],
    themes_config: dict[str, Any],
    days: int,
    top_n: int,
    selected_themes: list[str] | None,
) -> tuple[dict[str, dict[str, Any]], int, int]:
    """Process RSS items for each theme with date filtering and keyword matching.

    Parameters
    ----------
    items_by_source : dict[str, list[dict[str, Any]]]
        RSS items keyed by source key.
    themes_config : dict[str, Any]
        Theme configuration from ``asset-management-themes.json``.
    days : int
        Number of days to look back for date filtering.
    top_n : int
        Maximum number of articles per theme.
    selected_themes : list[str] | None
        List of theme keys to process. If None, processes all.

    Returns
    -------
    tuple[dict[str, dict[str, Any]], int, int]
        Tuple of (theme results, total date-filtered count, total
        keyword-matched count).
    """
    logger.info(
        "processing_themes",
        theme_count=len(themes_config),
        days=days,
        top_n=top_n,
    )

    results: dict[str, dict[str, Any]] = {}
    total_date_filtered = 0
    total_keyword_matched = 0

    for theme_key, theme_data in themes_config.items():
        # Skip if not in selected themes
        if selected_themes and theme_key not in selected_themes:
            continue

        name_ja = theme_data.get("name_ja", theme_key)
        keywords = theme_data.get("keywords_ja", [])
        target_sources = theme_data.get("target_sources", [])

        logger.info(
            "processing_theme",
            theme=theme_key,
            name_ja=name_ja,
            keyword_count=len(keywords),
            source_count=len(target_sources),
        )

        # Collect items from target sources
        theme_items: list[dict[str, Any]] = []
        for source_key in target_sources:
            source_items = items_by_source.get(source_key, [])
            theme_items.extend(source_items)

        logger.debug(
            "collected_source_items",
            theme=theme_key,
            item_count=len(theme_items),
        )

        # Filter by date
        date_filtered = filter_by_date(theme_items, days)
        total_date_filtered += len(date_filtered)
        logger.debug(
            "after_date_filter",
            theme=theme_key,
            input_count=len(theme_items),
            output_count=len(date_filtered),
        )

        # Filter by keywords
        keyword_matched = [
            item for item in date_filtered if match_keywords(item, keywords)
        ]
        total_keyword_matched += len(keyword_matched)
        logger.debug(
            "after_keyword_filter",
            theme=theme_key,
            input_count=len(date_filtered),
            output_count=len(keyword_matched),
        )

        # Select top N (newest first)
        selected = select_top_n(keyword_matched, top_n)

        results[theme_key] = {
            "articles": selected,
            "name_ja": name_ja,
            "keywords_used": keywords,
        }

        logger.info(
            "theme_processing_complete",
            theme=theme_key,
            article_count=len(selected),
        )

    return results, total_date_filtered, total_keyword_matched


# ---------------------------------------------------------------------------
# Session Generation
# ---------------------------------------------------------------------------


def generate_session_id() -> str:
    """Generate a unique session ID.

    Returns
    -------
    str
        Session ID in format ``asset-mgmt-{YYYYMMDD}-{HHMMSS}``.
    """
    now = datetime.now(timezone.utc)
    return f"asset-mgmt-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"


def build_session(
    session_id: str,
    theme_results: dict[str, dict[str, Any]],
    total_fetched: int,
    total_filtered: int,
    total_matched: int,
) -> AssetManagementSession:
    """Build the complete session data structure.

    Parameters
    ----------
    session_id : str
        Pre-generated session ID.
    theme_results : dict[str, dict[str, Any]]
        Processed theme results.
    total_fetched : int
        Total number of articles fetched from RSS.
    total_filtered : int
        Number of articles after date filtering.
    total_matched : int
        Number of articles matched by keywords.

    Returns
    -------
    AssetManagementSession
        Complete session data.
    """
    themes: dict[str, AssetManagementThemeData] = {}

    for theme_key, data in theme_results.items():
        articles = [
            ArticleData(
                url=item.get("link", ""),
                title=item.get("title", ""),
                summary=item.get("summary", ""),
                feed_source=item.get("feed_source", "Unknown"),
                published=item.get("published", ""),
            )
            for item in data.get("articles", [])
        ]

        themes[theme_key] = AssetManagementThemeData(
            name_ja=data.get("name_ja", theme_key),
            articles=articles,
            keywords_used=data.get("keywords_used", []),
        )

    return AssetManagementSession(
        session_id=session_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        themes=themes,
        stats=AssetManagementStats(
            total=total_fetched,
            filtered=total_filtered,
            matched=total_matched,
        ),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run(
    days: int,
    themes_filter: list[str] | None,
    output_path: Path,
    top_n: int = DEFAULT_TOP_N,
    presets_path: Path = RSS_PRESETS_JP_PATH,
) -> int:
    """Run the main processing.

    Parameters
    ----------
    days : int
        Number of days to look back.
    themes_filter : list[str] | None
        List of theme keys to process.
    output_path : Path
        Output file path.
    top_n : int
        Maximum number of articles per theme (newest first).
    presets_path : Path
        Path to the RSS presets configuration file.

    Returns
    -------
    int
        Exit code (0 for success).
    """
    # Generate session ID once for consistency
    session_id = generate_session_id()

    # Load configurations
    theme_config = load_json_config(THEME_CONFIG_PATH)
    themes_config = theme_config.get("themes", {})

    presets = load_rss_presets(presets_path)

    # Fetch RSS items by source
    items_by_source = fetch_items_by_source(presets)

    # Calculate total fetched
    total_fetched = sum(len(items) for items in items_by_source.values())
    logger.info("total_items_fetched", count=total_fetched)

    # Process themes (returns separate date-filtered and keyword-matched counts)
    theme_results, total_filtered, total_matched = process_themes(
        items_by_source=items_by_source,
        themes_config=themes_config,
        days=days,
        top_n=top_n,
        selected_themes=themes_filter,
    )

    # Build session with pre-generated ID
    session = build_session(
        session_id, theme_results, total_fetched, total_filtered, total_matched,
    )

    # Write output
    write_session_file(session, output_path)

    # Print summary
    print("\n" + "=" * 60)
    print("Asset Management Session Preparation Complete")
    print("=" * 60)
    print(f"Session ID: {session.session_id}")
    print(f"Output: {output_path}")
    print("\nStatistics:")
    print(f"  Total fetched: {session.stats.total}")
    print(f"  Date filtered: {session.stats.filtered}")
    print(f"  Keyword matched: {session.stats.matched}")
    print("\nTheme breakdown:")
    for _theme_key, theme_data in session.themes.items():
        print(f"  {theme_data.name_ja}: {len(theme_data.articles)} articles")
    print("=" * 60)

    return 0


def main(args: list[str] | None = None) -> int:
    """Main entry point.

    Parameters
    ----------
    args : list[str] | None
        Command-line arguments.

    Returns
    -------
    int
        Exit code (0 for success).
    """
    parsed = parse_args(args)

    # Configure logging
    configure_logging(parsed.verbose)

    # Resolve presets path from key or file path
    presets_path = resolve_presets_path(parsed.presets)

    # Parse themes
    themes_filter: list[str] | None = None
    if parsed.themes != "all":
        themes_filter = [t.strip() for t in parsed.themes.split(",")]

    # Determine output path (use session_id-based default)
    output_path = Path(parsed.output) if parsed.output else TMP_DIR / f"{generate_session_id()}.json"

    # Run processing
    return run(
        days=parsed.days,
        themes_filter=themes_filter,
        output_path=output_path,
        top_n=parsed.top_n,
        presets_path=presets_path,
    )


if __name__ == "__main__":
    sys.exit(main())
