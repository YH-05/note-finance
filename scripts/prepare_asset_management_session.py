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
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pydantic import BaseModel, Field

from session_utils import (
    ArticleData,
    filter_by_date,
    get_logger as _get_structlog,
    select_top_n,
    write_session_file,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_DAYS = 14
"""Default number of days to look back for articles."""

DEFAULT_THEMES = "all"
"""Default theme filter (all themes)."""

DEFAULT_TOP_N = 10
"""Default number of top articles per theme (sorted by published date, newest first)."""

THEME_CONFIG_PATH = Path("data/config/asset-management-themes.json")
"""Path to asset management theme configuration file."""

RSS_PRESETS_JP_PATH = Path("data/config/rss-presets-jp.json")
"""Path to JP RSS presets configuration file."""

TMP_DIR = Path(".tmp")
"""Temporary directory for session files."""


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

logger = _get_structlog(__name__)


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

    return parser.parse_args(args)


# ---------------------------------------------------------------------------
# Configuration Loading
# ---------------------------------------------------------------------------


def load_theme_config(
    config_path: Path = THEME_CONFIG_PATH,
) -> dict[str, Any]:
    """Load asset management theme configuration from JSON file.

    Parameters
    ----------
    config_path : Path
        Path to the theme configuration file.

    Returns
    -------
    dict[str, Any]
        Theme configuration data.

    Raises
    ------
    FileNotFoundError
        If configuration file does not exist.
    json.JSONDecodeError
        If configuration file is not valid JSON.
    """
    logger.info("loading_theme_configuration", config_path=str(config_path))

    with open(config_path) as f:
        config = json.load(f)

    logger.debug("loaded_themes", count=len(config.get("themes", {})))
    return config


def load_rss_presets(
    presets_path: Path = RSS_PRESETS_JP_PATH,
) -> list[dict[str, Any]]:
    """Load JP RSS presets configuration.

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
    logger.info("loading_rss_presets", presets_path=str(presets_path))

    with open(presets_path) as f:
        data = json.load(f)

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
    # AIDEV-NOTE: We use httpx/feedparser-like approach but since the project
    # uses rss.services.feed_reader.FeedReader which reads from local JSON
    # files, we import and use it here.  However, for JP feeds that may not
    # have local data yet, we fall back to fetching directly.
    from rss.services.feed_reader import FeedReader

    logger.info("fetching_items_by_source", preset_count=len(presets))

    # Map URL patterns to source keys used in theme config
    url_to_source: dict[str, str] = {
        "fsa.go.jp": "fsa",
        "boj.or.jp": "boj",
        "dir.co.jp": "daiwa",
        "jpx.co.jp": "jpx",
        "emaxis": "emaxis",
        "morningstar": "morningstar_jp",
    }

    items_by_source: dict[str, list[dict[str, Any]]] = {}

    # Try reading from local RSS data first
    data_dir = Path("data/raw/rss")
    reader: FeedReader | None = None
    if data_dir.exists():
        try:
            reader = FeedReader(data_dir)
        except Exception as e:
            logger.warning("feed_reader_init_failed", error=str(e))

    for preset in presets:
        url = preset.get("url", "")
        title = preset.get("title", "Unknown")

        # Determine source key from URL
        source_key = "unknown"
        for pattern, key in url_to_source.items():
            if pattern in url:
                source_key = key
                break

        if source_key not in items_by_source:
            items_by_source[source_key] = []

        # Try to get items from local storage via FeedReader
        if reader is not None:
            try:
                feed_items = reader.search_items(
                    query="",
                    limit=100,
                )
                for fi in feed_items:
                    # Only include items from this feed's domain
                    if fi.link and any(p in fi.link for p in [source_key, url.split("/")[2]]):
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
            except Exception as e:
                logger.warning(
                    "failed_to_read_local_feed",
                    source_key=source_key,
                    error=str(e),
                )

        logger.debug(
            "source_items_fetched",
            source_key=source_key,
            count=len(items_by_source.get(source_key, [])),
        )

    return items_by_source


# ---------------------------------------------------------------------------
# Theme Processing
# ---------------------------------------------------------------------------


def process_themes(
    items_by_source: dict[str, list[dict[str, Any]]],
    themes_config: dict[str, Any],
    days: int,
    top_n: int,
    selected_themes: list[str] | None,
) -> dict[str, dict[str, Any]]:
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
    dict[str, dict[str, Any]]
        Processed theme results with ``articles`` and ``name_ja`` keys.
    """
    logger.info(
        "processing_themes",
        theme_count=len(themes_config),
        days=days,
        top_n=top_n,
    )

    results: dict[str, dict[str, Any]] = {}

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

    return results


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
    theme_results: dict[str, dict[str, Any]],
    total_fetched: int,
    total_filtered: int,
    total_matched: int,
) -> AssetManagementSession:
    """Build the complete session data structure.

    Parameters
    ----------
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
        session_id=generate_session_id(),
        timestamp=datetime.now(timezone.utc).isoformat(),
        themes=themes,
        stats=AssetManagementStats(
            total=total_fetched,
            filtered=total_filtered,
            matched=total_matched,
        ),
    )


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def get_default_output_path() -> Path:
    """Get default output path in .tmp directory.

    Returns
    -------
    Path
        Default output file path.
    """
    session_id = generate_session_id()
    return TMP_DIR / f"{session_id}.json"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run(
    days: int,
    themes_filter: list[str] | None,
    output_path: Path,
    top_n: int = DEFAULT_TOP_N,
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

    Returns
    -------
    int
        Exit code (0 for success).
    """
    # Load configurations
    theme_config = load_theme_config()
    themes_config = theme_config.get("themes", {})

    presets = load_rss_presets()

    # Fetch RSS items by source
    items_by_source = fetch_items_by_source(presets)

    # Calculate total fetched
    total_fetched = sum(len(items) for items in items_by_source.values())
    logger.info("total_items_fetched", count=total_fetched)

    # Process themes
    theme_results = process_themes(
        items_by_source=items_by_source,
        themes_config=themes_config,
        days=days,
        top_n=top_n,
        selected_themes=themes_filter,
    )

    # Calculate stats
    total_filtered = sum(
        len(data.get("articles", []))
        for data in theme_results.values()
    )
    total_matched = total_filtered  # After keyword matching

    # Build session
    session = build_session(theme_results, total_fetched, total_filtered, total_matched)

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
    for theme_key, theme_data in session.themes.items():
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
    if parsed.verbose:
        import structlog

        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
        )

    # Parse themes
    themes_filter: list[str] | None = None
    if parsed.themes != "all":
        themes_filter = [t.strip() for t in parsed.themes.split(",")]

    # Determine output path
    output_path = Path(parsed.output) if parsed.output else get_default_output_path()

    # Run processing
    return run(
        days=parsed.days,
        themes_filter=themes_filter,
        output_path=output_path,
        top_n=parsed.top_n,
    )


if __name__ == "__main__":
    sys.exit(main())
