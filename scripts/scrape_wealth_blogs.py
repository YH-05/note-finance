#!/usr/bin/env python3
"""Wealth Finance Blog RSS Scraping CLI.

2モード（incremental/backfill）対応のメインCLIスクリプト。
15サイトからのRSS収集+バックフィルスクレイピングを実行する
オーケストレータースクリプト。

Usage
-----
    # Incremental mode (RSS fetch)
    uv run python scripts/scrape_wealth_blogs.py --mode incremental --days 7

    # Backfill mode (sitemap scraping)
    uv run python scripts/scrape_wealth_blogs.py --mode backfill --limit 100

    # Dry run
    uv run python scripts/scrape_wealth_blogs.py --mode incremental --dry-run

    # Single domain
    uv run python scripts/scrape_wealth_blogs.py --domain awealthofcommonsense.com

Output
------
    Session JSON file in ``.tmp/`` directory (incremental mode).
    Markdown files in ``data/scraped/wealth/{domain}/{slug}.md``.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pydantic import BaseModel, Field
from session_utils import (
    configure_logging,
    filter_by_date,
    load_json_config,
    select_top_n,
    write_session_file,
)

from rss._logging import get_logger
from rss.config.wealth_scraping_config import (
    BACKFILL_TIER,
    WEALTH_DOMAIN_RATE_LIMITS,
    WEALTH_SITEMAP_URLS,
    WEALTH_URL_TO_SOURCE_KEY,
)
from rss.services.article_extractor import ArticleExtractor, ExtractionStatus
from rss.services.company_scrapers.scraping_policy import ScrapingPolicy
from rss.storage.scrape_state_db import ScrapeStateDB
from rss.utils.robots_checker import RobotsChecker
from rss.utils.sitemap_parser import SitemapParser

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_DAYS = 14
"""Default number of days to look back for articles."""

DEFAULT_TOP_N = 10
"""Default number of top articles per theme."""

DEFAULT_LIMIT = 200
"""Default maximum articles to scrape in backfill mode."""

DEFAULT_PER_DOMAIN = 0
"""Default per-domain limit (0 = auto-calculate from limit / number of domains)."""

DEFAULT_CONCURRENCY = 4
"""Default number of domains to scrape concurrently in backfill mode."""

MAX_DAYS = 365
"""Maximum allowed value for --days argument."""

MAX_TOP_N = 100
"""Maximum allowed value for --top-n argument."""

WEALTH_SESSION_PREFIX = "wealth-scrape"
"""Session ID prefix for wealth scraping sessions."""

WEALTH_SCRAPE_DB_PATH = Path(".tmp/wealth_scrape_state.db")
"""Default path for the SQLite scraping state database."""

THEME_CONFIG_PATH = Path("data/config/wealth-management-themes.json")
"""Path to wealth management theme configuration file."""

RSS_PRESETS_WEALTH_PATH = Path("data/config/rss-presets-wealth.json")
"""Path to wealth RSS presets configuration file."""

SITEMAP_CONFIG_PATH = Path("data/config/wealth-sitemap-config.json")
"""Path to wealth sitemap configuration file."""

TMP_DIR = Path(".tmp")
"""Temporary directory for session files."""

_NAS_SCRAPED_WEALTH = Path("/Volumes/personal_folder/scraped/wealth")
SCRAPED_OUTPUT_DIR = _NAS_SCRAPED_WEALTH if _NAS_SCRAPED_WEALTH.parent.exists() else Path("data/scraped/wealth")
"""Base directory for scraped Markdown article files (NAS preferred, local fallback)."""

FEED_READ_LIMIT = 200
"""Maximum number of items to fetch from FeedReader per search call."""


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------


class WealthArticleData(BaseModel):
    """Article data for a wealth finance blog article.

    Attributes
    ----------
    url : str
        Article URL.
    title : str
        Article title.
    summary : str
        Article summary from RSS feed or scraped content.
    feed_source : str
        Name of the RSS feed source.
    published : str
        Publication timestamp in ISO 8601 format.
    source_key : str
        Canonical source key (e.g., "awealthofcommonsense").
    domain : str
        Domain of the article URL.
    """

    url: str
    title: str
    summary: str
    feed_source: str
    published: str
    source_key: str = ""
    domain: str = ""


class WealthThemeData(BaseModel):
    """Data for a single wealth management theme.

    Attributes
    ----------
    name_en : str
        English name of the theme.
    articles : list[WealthArticleData]
        List of matched articles for this theme.
    keywords_used : list[str]
        Keywords used for matching.
    """

    name_en: str
    articles: list[WealthArticleData] = Field(default_factory=list)
    keywords_used: list[str] = Field(default_factory=list)


class WealthScrapeStats(BaseModel):
    """Session statistics for wealth scraping workflow.

    Attributes
    ----------
    total : int
        Total number of articles fetched.
    filtered : int
        Number of articles after date filtering.
    matched : int
        Number of articles matched by keywords.
    scraped : int
        Number of articles successfully scraped/saved.
    skipped : int
        Number of articles skipped (paywall, duplicate, etc.).
    """

    total: int
    filtered: int
    matched: int
    scraped: int
    skipped: int = 0


class WealthScrapeSession(BaseModel):
    """Complete wealth scraping session data.

    Attributes
    ----------
    session_id : str
        Unique session identifier.
    timestamp : str
        Session creation timestamp in ISO 8601 format.
    mode : str
        Operation mode ("incremental" or "backfill").
    themes : dict[str, WealthThemeData]
        Theme data keyed by theme key.
    stats : WealthScrapeStats
        Session statistics.
    """

    session_id: str
    timestamp: str
    mode: str
    themes: dict[str, WealthThemeData] = Field(default_factory=dict)
    stats: WealthScrapeStats


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
        description="Wealth Finance Blog RSS scraping orchestrator (incremental/backfill).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["incremental", "backfill"],
        default="incremental",
        help="Operation mode: incremental (RSS) or backfill (sitemap). (default: incremental)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        help=f"Days to look back for incremental mode. (default: {DEFAULT_DAYS})",
    )
    parser.add_argument(
        "--tier",
        type=int,
        default=None,
        help="Filter by RSS tier (1 or 2) for incremental mode.",
    )
    parser.add_argument(
        "--backfill-tier",
        type=str,
        choices=["A", "B", "C", "D"],
        default=None,
        dest="backfill_tier",
        help="Process only this backfill tier (A/B/C/D).",
    )
    parser.add_argument(
        "--domain",
        type=str,
        default=None,
        help="Process only this domain (e.g., awealthofcommonsense.com).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Maximum articles to scrape in backfill mode. (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--per-domain",
        type=int,
        default=DEFAULT_PER_DOMAIN,
        dest="per_domain",
        help="Max articles per domain (0 = auto: limit / number of domains).",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=DEFAULT_TOP_N,
        dest="top_n",
        help=f"Max articles per theme in incremental mode. (default: {DEFAULT_TOP_N})",
    )
    parser.add_argument(
        "--check-robots",
        action="store_true",
        dest="check_robots",
        help="Enable robots.txt compliance checking.",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        dest="retry_failed",
        help="Retry previously failed articles.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Show what would be processed without actually scraping.",
    )
    parser.add_argument(
        "--concurrency",
        "-j",
        type=int,
        default=DEFAULT_CONCURRENCY,
        dest="concurrency",
        help=f"Number of domains to scrape concurrently in backfill mode. (default: {DEFAULT_CONCURRENCY})",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging.",
    )

    parsed = parser.parse_args(args)

    # Validate ranges
    if parsed.days <= 0 or parsed.days > MAX_DAYS:
        parser.error(f"--days must be between 1 and {MAX_DAYS}")
    if parsed.top_n < 0 or parsed.top_n > MAX_TOP_N:
        parser.error(f"--top-n must be between 0 and {MAX_TOP_N}")

    return parsed


# ---------------------------------------------------------------------------
# Session ID
# ---------------------------------------------------------------------------


def generate_session_id() -> str:
    """Generate a unique wealth scrape session ID.

    Returns
    -------
    str
        Session ID in format ``wealth-scrape-{YYYYMMDD}-{HHMMSS}-{microseconds}``.
        Microseconds ensure uniqueness even within the same second.
    """
    now = datetime.now(timezone.utc)
    return (
        f"{WEALTH_SESSION_PREFIX}-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"
        f"-{now.microsecond:06d}"
    )


# ---------------------------------------------------------------------------
# Source Key Resolution
# ---------------------------------------------------------------------------


def resolve_source_key_wealth(domain: str) -> str:
    """Resolve a canonical source key from a domain string.

    Uses WEALTH_URL_TO_SOURCE_KEY mapping from wealth_scraping_config.

    Parameters
    ----------
    domain : str
        Domain string (e.g., "awealthofcommonsense.com" or
        "www.mrmoneymustache.com").

    Returns
    -------
    str
        Canonical source key, or "unknown" if no mapping found.
    """
    if not domain:
        return "unknown"
    return WEALTH_URL_TO_SOURCE_KEY.get(domain, "unknown")


def _extract_domain_from_url(url: str) -> str:
    """Extract netloc domain from a URL.

    Parameters
    ----------
    url : str
        Full URL string.

    Returns
    -------
    str
        Domain (netloc), or empty string on parse failure.
    """
    try:
        return urlparse(url).netloc
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Keyword Matching
# ---------------------------------------------------------------------------


def match_keywords_en(
    item: dict[str, Any],
    keywords: list[str],
) -> bool:
    """Check if an RSS item matches any English keyword.

    Performs case-insensitive partial matching on ``title`` and ``summary``.

    Parameters
    ----------
    item : dict[str, Any]
        RSS item dict with ``title`` and ``summary`` keys.
    keywords : list[str]
        List of English keywords to match.

    Returns
    -------
    bool
        True if any keyword found in title or summary.
    """
    if not keywords:
        return False

    title = (item.get("title") or "").lower()
    summary = (item.get("summary") or "").lower()
    text = f"{title} {summary}"

    for keyword in keywords:
        if keyword.lower() in text:
            logger.debug(
                "keyword_matched", keyword=keyword, title=item.get("title", "")
            )
            return True

    return False


# ---------------------------------------------------------------------------
# RSS Feed Loading
# ---------------------------------------------------------------------------


def _load_wealth_presets(
    presets_path: Path = RSS_PRESETS_WEALTH_PATH,
    tier_filter: int | None = None,
    domain_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Load enabled wealth RSS presets with optional filtering.

    Parameters
    ----------
    presets_path : Path
        Path to rss-presets-wealth.json.
    tier_filter : int | None
        If set, only return presets matching this tier.
    domain_filter : str | None
        If set, only return presets whose URL domain matches.

    Returns
    -------
    list[dict[str, Any]]
        Enabled preset entries after filtering.
    """
    data = load_json_config(presets_path)
    presets = data.get("presets", [])
    enabled = [p for p in presets if p.get("enabled", True)]

    if tier_filter is not None:
        enabled = [p for p in enabled if p.get("tier") == tier_filter]

    if domain_filter:
        enabled = [p for p in enabled if domain_filter in p.get("url", "")]

    logger.debug(
        "wealth_presets_loaded",
        total=len(presets),
        enabled=len(enabled),
        tier_filter=tier_filter,
        domain_filter=domain_filter,
    )
    return enabled


def fetch_rss_items_by_source(
    presets: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Fetch RSS items from local storage grouped by source key.

    Reads from local ``data/raw/rss/`` JSON files via FeedReader.
    Maps items to wealth source keys using WEALTH_URL_TO_SOURCE_KEY.

    Parameters
    ----------
    presets : list[dict[str, Any]]
        Enabled RSS preset entries from rss-presets-wealth.json.

    Returns
    -------
    dict[str, list[dict[str, Any]]]
        RSS items keyed by source key.
    """
    from rss.services.feed_reader import FeedReader

    logger.info("fetching_rss_items_by_source", preset_count=len(presets))

    items_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)

    # Build preset mapping: (source_key, preset_domain, title)
    preset_mapping: list[tuple[str, str, str]] = []
    for preset in presets:
        url = preset.get("url", "")
        title = preset.get("title", "Unknown")
        domain = _extract_domain_from_url(url)
        source_key = resolve_source_key_wealth(domain)
        preset_mapping.append((source_key, domain, title))

    # Read from RSS data directory (NAS preferred, local fallback)
    _nas_rss = Path("/Volumes/personal_folder/scraped/rss")
    data_dir = _nas_rss if _nas_rss.exists() else Path("data/raw/rss")
    if data_dir.exists():
        try:
            reader = FeedReader(data_dir)
            all_items = reader.search_items(query="", limit=FEED_READ_LIMIT)

            # Index items by domain
            items_by_domain: dict[str, list[Any]] = defaultdict(list)
            for fi in all_items:
                if fi.link:
                    item_domain = _extract_domain_from_url(fi.link)
                    items_by_domain[item_domain].append(fi)

            # Assign items to source keys by domain matching
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
                            "source_key": source_key,
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


def _process_themes_incremental(
    items_by_source: dict[str, list[dict[str, Any]]],
    themes_config: dict[str, Any],
    days: int,
    top_n: int,
) -> tuple[dict[str, dict[str, Any]], int, int]:
    """Process RSS items for each theme (incremental mode).

    Parameters
    ----------
    items_by_source : dict[str, list[dict[str, Any]]]
        RSS items keyed by source key.
    themes_config : dict[str, Any]
        Theme configuration from wealth-management-themes.json.
    days : int
        Number of days to look back.
    top_n : int
        Maximum articles per theme.

    Returns
    -------
    tuple[dict[str, dict[str, Any]], int, int]
        Tuple of (theme_results, total_date_filtered, total_keyword_matched).
    """
    results: dict[str, dict[str, Any]] = {}
    total_date_filtered = 0
    total_keyword_matched = 0

    for theme_key, theme_data in themes_config.items():
        name_en = theme_data.get("name_en", theme_key)
        keywords = theme_data.get("keywords_en", [])
        target_sources = theme_data.get("target_sources", [])

        logger.info(
            "processing_theme",
            theme=theme_key,
            name_en=name_en,
            keyword_count=len(keywords),
            source_count=len(target_sources),
        )

        # Collect from target sources
        theme_items: list[dict[str, Any]] = []
        for source_key in target_sources:
            source_items = items_by_source.get(source_key, [])
            theme_items.extend(source_items)

        # Date filter
        date_filtered = filter_by_date(theme_items, days)
        total_date_filtered += len(date_filtered)

        # Keyword match
        keyword_matched = [
            item for item in date_filtered if match_keywords_en(item, keywords)
        ]
        total_keyword_matched += len(keyword_matched)

        # Top N selection
        selected = select_top_n(keyword_matched, top_n)

        results[theme_key] = {
            "articles": selected,
            "name_en": name_en,
            "keywords_used": keywords,
        }

        logger.info(
            "theme_processing_complete",
            theme=theme_key,
            article_count=len(selected),
        )

    return results, total_date_filtered, total_keyword_matched


# ---------------------------------------------------------------------------
# Session Construction
# ---------------------------------------------------------------------------


def build_session(
    session_id: str,
    mode: str,
    theme_results: dict[str, dict[str, Any]],
    total_fetched: int,
    total_filtered: int,
    total_matched: int,
    total_scraped: int = 0,
    total_skipped: int = 0,
) -> WealthScrapeSession:
    """Build the complete WealthScrapeSession data structure.

    Parameters
    ----------
    session_id : str
        Pre-generated session ID.
    mode : str
        Operation mode ("incremental" or "backfill").
    theme_results : dict[str, dict[str, Any]]
        Processed theme results from _process_themes_incremental.
    total_fetched : int
        Total articles fetched from RSS.
    total_filtered : int
        Articles after date filtering.
    total_matched : int
        Articles matched by keywords.
    total_scraped : int
        Articles successfully scraped (backfill mode).
    total_skipped : int
        Articles skipped.

    Returns
    -------
    WealthScrapeSession
        Complete session data.
    """
    themes: dict[str, WealthThemeData] = {}

    for theme_key, data in theme_results.items():
        articles = [
            WealthArticleData(
                url=item.get("link", ""),
                title=item.get("title", ""),
                summary=item.get("summary", ""),
                feed_source=item.get("feed_source", "Unknown"),
                published=item.get("published", ""),
                source_key=item.get("source_key", ""),
                domain=_extract_domain_from_url(item.get("link", "")),
            )
            for item in data.get("articles", [])
        ]

        themes[theme_key] = WealthThemeData(
            name_en=data.get("name_en", theme_key),
            articles=articles,
            keywords_used=data.get("keywords_used", []),
        )

    return WealthScrapeSession(
        session_id=session_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        mode=mode,
        themes=themes,
        stats=WealthScrapeStats(
            total=total_fetched,
            filtered=total_filtered,
            matched=total_matched,
            scraped=total_scraped,
            skipped=total_skipped,
        ),
    )


# ---------------------------------------------------------------------------
# Markdown Output Helper
# ---------------------------------------------------------------------------


def _slugify(title: str) -> str:
    """Convert a title to a URL-safe slug.

    Parameters
    ----------
    title : str
        Article title.

    Returns
    -------
    str
        Lowercase hyphenated slug (max 80 chars).
    """
    import re

    slug = title.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug[:80]


def _save_article_markdown(
    url: str,
    title: str | None,
    text: str,
    date: str | None,
    author: str | None,
    domain: str,
    output_base: Path = SCRAPED_OUTPUT_DIR,
) -> Path:
    """Save an extracted article as Markdown with YAML frontmatter.

    Parameters
    ----------
    url : str
        Article URL.
    title : str | None
        Article title.
    text : str
        Extracted article text.
    date : str | None
        Publication date.
    author : str | None
        Author name.
    domain : str
        Article domain (used as subdirectory).
    output_base : Path
        Base output directory.

    Returns
    -------
    Path
        Written file path.
    """
    slug = _slugify(title or "untitled")
    domain_clean = domain.replace("www.", "")

    # SEC-003: Path traversal guard — resolve and verify output stays under output_base
    output_dir = (output_base / domain_clean).resolve()
    output_base_resolved = output_base.resolve()
    if not str(output_dir).startswith(str(output_base_resolved)):
        raise ValueError(
            f"Path traversal detected: {output_dir} is outside {output_base_resolved}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{slug}.md"

    # INFRA-003: Sanitize external field values before embedding in YAML frontmatter.
    # Newlines and YAML delimiter "---" in external data would break the frontmatter block.
    def _sanitize_fm(value: str | None) -> str:
        if not value:
            return ""
        return value.replace("\r", "").replace("\n", " ").replace("---", "- - -")

    # QUAL-005: Single-quote all YAML scalar values to prevent injection from
    # special YAML characters (`:`, `[`, `{`, `#`) in titles, authors, etc.
    # Single-quoted YAML scalars are literal except `'` which must be doubled.
    title_val = (_sanitize_fm(title) or "untitled").replace("'", "''")
    date_val = _sanitize_fm(date).replace("'", "''")
    author_val = _sanitize_fm(author).replace("'", "''")
    domain_val = domain.replace("'", "''")
    # URLs must not contain single quotes; sanitize anyway for safety.
    url_val = url.replace("'", "%27")
    frontmatter_lines = [
        "---",
        f"url: '{url_val}'",
        f"title: '{title_val}'",
        f"date: '{date_val}'",
        f"author: '{author_val}'",
        f"domain: '{domain_val}'",
        "---",
        "",
    ]
    content = "\n".join(frontmatter_lines) + text

    output_path.write_text(content, encoding="utf-8")
    logger.debug("article_saved", path=str(output_path), url=url)
    return output_path


# ---------------------------------------------------------------------------
# Playwright Tier 3 Helper (guarded import)
# ---------------------------------------------------------------------------


def _scrape_with_playwright(url: str) -> str | None:
    """Attempt Playwright-based scraping for Tier 3 (Kiplinger).

    Returns None and logs a WARNING if playwright is not installed.

    Parameters
    ----------
    url : str
        URL to scrape.

    Returns
    -------
    str | None
        Extracted text content, or None on failure/unavailability.
    """
    try:
        from playwright.sync_api import (
            sync_playwright,  # type: ignore[import-not-found]
        )
    except ImportError:
        logger.warning(
            "playwright_not_installed",
            message="Tier 3 (Kiplinger) skipped — install playwright: uv add playwright",
            url=url,
        )
        return None

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)
            text = page.inner_text("body") or ""
            browser.close()
            return text
    except Exception as e:
        logger.warning("playwright_scrape_failed", url=url, error=str(e))
        return None


# ---------------------------------------------------------------------------
# Incremental Mode
# ---------------------------------------------------------------------------


def run_incremental(
    days: int,
    top_n: int,
    output_path: Path,
    dry_run: bool = False,
    domain_filter: str | None = None,
    tier_filter: int | None = None,
    check_robots: bool = False,
    retry_failed: bool = False,
) -> int:
    """Run incremental mode: RSS fetch → filter → theme match → session JSON.

    Parameters
    ----------
    days : int
        Number of days to look back.
    top_n : int
        Maximum articles per theme.
    output_path : Path
        Session JSON output path.
    dry_run : bool
        If True, only display feed list without scraping.
    domain_filter : str | None
        If set, only process this domain.
    tier_filter : int | None
        If set, only process this RSS tier.
    check_robots : bool
        If True, enable robots.txt checking (currently informational).
    retry_failed : bool
        If True, include previously failed articles.

    Returns
    -------
    int
        Exit code (0 for success).
    """
    session_id = generate_session_id()

    # Load presets
    presets = _load_wealth_presets(
        tier_filter=tier_filter,
        domain_filter=domain_filter,
    )

    if dry_run:
        print("\n" + "=" * 60)
        print("Dry Run — Incremental Mode Feed List")
        print("=" * 60)
        for p in presets:
            print(
                f"  [{p.get('tier', '?')}] {p.get('title', '?')}: {p.get('url', '?')}"
            )
        print(f"\nTotal feeds: {len(presets)}")
        print("=" * 60)
        logger.info("dry_run_incremental_complete", feed_count=len(presets))
        return 0

    # Load theme config
    theme_config = load_json_config(THEME_CONFIG_PATH)
    themes_config = theme_config.get("themes", {})

    # Fetch RSS items
    items_by_source = fetch_rss_items_by_source(presets)
    total_fetched = sum(len(items) for items in items_by_source.values())
    logger.info("total_rss_items_fetched", count=total_fetched)

    # Process themes
    theme_results, total_filtered, total_matched = _process_themes_incremental(
        items_by_source=items_by_source,
        themes_config=themes_config,
        days=days,
        top_n=top_n,
    )

    # Build session
    session = build_session(
        session_id=session_id,
        mode="incremental",
        theme_results=theme_results,
        total_fetched=total_fetched,
        total_filtered=total_filtered,
        total_matched=total_matched,
    )

    # Write output
    write_session_file(session, output_path)

    # Print summary
    print("\n" + "=" * 60)
    print("Wealth Blog Incremental Scraping Complete")
    print("=" * 60)
    print(f"Session ID: {session.session_id}")
    print(f"Output: {output_path}")
    print("\nStatistics:")
    print(f"  Total fetched: {session.stats.total}")
    print(f"  Date filtered: {session.stats.filtered}")
    print(f"  Keyword matched: {session.stats.matched}")
    print("\nTheme breakdown:")
    for _theme_key, theme_data in session.themes.items():
        print(f"  {theme_data.name_en}: {len(theme_data.articles)} articles")
    print("=" * 60)

    return 0


# ---------------------------------------------------------------------------
# Backfill Mode
# ---------------------------------------------------------------------------


class _BackfillState:
    """Shared mutable state for concurrent backfill coroutines.

    Attributes
    ----------
    total_scraped : int
        Total articles scraped across all domains.
    total_skipped : int
        Total articles skipped across all domains.
    limit : int
        Global maximum articles to scrape.
    """

    def __init__(self, limit: int) -> None:
        self.total_scraped = 0
        self.total_skipped = 0
        self.limit = limit

    @property
    def limit_reached(self) -> bool:
        """Check if the global scrape limit has been reached."""
        return self.total_scraped >= self.limit


async def _scrape_site_backfill(
    site: dict[str, Any],
    tier: str,
    state: _BackfillState,
    effective_per_domain: int,
    db: ScrapeStateDB,
    policy: ScrapingPolicy,
    extractor: ArticleExtractor,
    parser: SitemapParser,
    robots_checker: RobotsChecker | None,
    retry_failed: bool,
    dry_run: bool,
    semaphore: asyncio.Semaphore,
) -> None:
    """Scrape a single site in backfill mode.

    Acquires a semaphore slot to limit concurrency across domains.

    Parameters
    ----------
    site : dict[str, Any]
        Site configuration from wealth-sitemap-config.json.
    tier : str
        Backfill tier (A/B/C/D).
    state : _BackfillState
        Shared mutable state for tracking progress.
    effective_per_domain : int
        Maximum articles per domain.
    db : ScrapeStateDB
        Scraping state database.
    policy : ScrapingPolicy
        Rate limiting policy.
    extractor : ArticleExtractor
        Article content extractor.
    parser : SitemapParser
        Sitemap parser.
    robots_checker : RobotsChecker | None
        Optional robots.txt checker.
    retry_failed : bool
        Include previously failed URLs for retry.
    dry_run : bool
        If True, only display URL list.
    semaphore : asyncio.Semaphore
        Concurrency limiter.
    """
    async with semaphore:
        if state.limit_reached:
            return

        domain = site.get("domain", "")
        domain_scraped = 0
        sitemap_url = WEALTH_SITEMAP_URLS.get(domain)
        if not sitemap_url:
            logger.warning("no_sitemap_url", domain=domain)
            return

        # Parse sitemap
        logger.info("parsing_sitemap", domain=domain, url=sitemap_url)
        entries = await parser.parse(sitemap_url)
        post_entries = parser.filter_post_urls(entries)
        all_urls = [e.url for e in post_entries]

        # Filter new / retry failed
        if retry_failed:
            pending_urls = db.get_pending_urls()
            new_urls = db.filter_new_urls(all_urls)
            urls_to_scrape = list({*pending_urls, *new_urls})
        else:
            urls_to_scrape = db.filter_new_urls(all_urls)

        # Apply domain URL pattern filter from sitemap config
        url_patterns = site.get("url_patterns", [])
        exclude_patterns = site.get("exclude_patterns", [])
        if url_patterns:
            urls_to_scrape = [
                u
                for u in urls_to_scrape
                if any(p in u for p in url_patterns)
                and not any(ep in u for ep in exclude_patterns)
            ]

        # Update sitemap state
        if all_urls:
            db.update_sitemap_state(
                sitemap_url=sitemap_url,
                last_processed_url=all_urls[-1],
                processed_count=len(all_urls),
            )

        if dry_run:
            capped = min(len(urls_to_scrape), effective_per_domain)
            print(
                f"\n[{tier}] {domain}: {len(urls_to_scrape)} new URLs"
                f" (cap: {effective_per_domain})"
            )
            for url in urls_to_scrape[:5]:
                print(f"  {url}")
            if len(urls_to_scrape) > 5:
                print(f"  ... and {len(urls_to_scrape) - 5} more")
            print(f"  → will process: {capped}")
            return

        # Scrape URLs
        for url in urls_to_scrape:
            if state.limit_reached:
                break
            if domain_scraped >= effective_per_domain:
                logger.info(
                    "per_domain_limit_reached",
                    domain=domain,
                    domain_scraped=domain_scraped,
                    per_domain=effective_per_domain,
                )
                break

            # robots.txt check
            if robots_checker:
                try:
                    robots_result = await robots_checker.check(url)
                    if not robots_result.allowed:
                        logger.info("robots_disallowed", url=url)
                        state.total_skipped += 1
                        continue
                except Exception as e:
                    logger.warning("robots_check_failed", url=url, error=str(e))

            # Rate limiting
            await policy.wait_for_domain(domain)

            # Tier D: Playwright scraping
            if tier == "D":
                text = _scrape_with_playwright(url)
                if text is None:
                    state.total_skipped += 1
                    continue
                extracted_title = url.split("/")[-1].replace("-", " ").title()
                _save_article_markdown(
                    url=url,
                    title=extracted_title,
                    text=text,
                    date=None,
                    author=None,
                    domain=domain,
                )
                db.mark_scraped(url, success=True)
                state.total_scraped += 1
                domain_scraped += 1
                logger.info(
                    "article_scraped_playwright",
                    url=url,
                    total=state.total_scraped,
                    domain_scraped=domain_scraped,
                )
                continue

            # Standard HTTP extraction
            result = await extractor.extract(url)

            if result.status == ExtractionStatus.SUCCESS and result.text:
                _save_article_markdown(
                    url=url,
                    title=result.title or url.split("/")[-1],
                    text=result.text,
                    date=result.date,
                    author=result.author,
                    domain=domain,
                )
                db.mark_scraped(url, success=True)
                state.total_scraped += 1
                domain_scraped += 1
                logger.info(
                    "article_scraped",
                    url=url,
                    total=state.total_scraped,
                    domain_scraped=domain_scraped,
                    method=result.extraction_method,
                )
            else:
                db.mark_scraped(url, success=False)
                state.total_skipped += 1
                logger.debug(
                    "article_skipped",
                    url=url,
                    status=result.status.value,
                )


async def _run_backfill_async(
    limit: int,
    dry_run: bool,
    domain_filter: str | None,
    backfill_tier: str | None,
    check_robots: bool,
    retry_failed: bool,
    db_path: Path,
    per_domain: int = DEFAULT_PER_DOMAIN,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> int:
    """Run backfill mode asynchronously with concurrent domain processing.

    Domains within each tier are processed concurrently (up to ``concurrency``
    domains at a time). Rate limiting is per-domain, so concurrent processing
    of different domains does not violate crawl-delay constraints.

    Phase order: A → B → C → D (Tier A is highest priority).
    D-tier uses Playwright with try/except guard.

    Parameters
    ----------
    limit : int
        Maximum total URLs to scrape.
    dry_run : bool
        If True, only display URL list without scraping.
    domain_filter : str | None
        If set, only process this domain.
    backfill_tier : str | None
        If set, only process this backfill tier.
    check_robots : bool
        Enable robots.txt compliance checking.
    retry_failed : bool
        Include previously failed URLs for retry.
    db_path : Path
        SQLite state database path.
    per_domain : int
        Maximum articles per domain. 0 means auto-calculate
        as ``limit // number_of_target_domains``.
    concurrency : int
        Maximum number of domains to scrape concurrently.

    Returns
    -------
    int
        Exit code (0 for success).
    """
    # Load sitemap config
    sitemap_config_data = load_json_config(SITEMAP_CONFIG_PATH)
    sites = sitemap_config_data.get("sites", [])

    # Filter by domain
    if domain_filter:
        sites = [s for s in sites if domain_filter in s.get("domain", "")]

    # Determine tier order
    tier_order = ["A", "B", "C", "D"]
    if backfill_tier:
        tier_order = [backfill_tier]

    # Resolve per-domain cap
    if per_domain > 0:
        effective_per_domain = per_domain
    else:
        num_sites = max(len(sites), 1)
        effective_per_domain = max(limit // num_sites, 1)
    logger.info(
        "per_domain_limit_resolved",
        per_domain=effective_per_domain,
        global_limit=limit,
        site_count=len(sites),
        concurrency=concurrency,
    )

    policy = ScrapingPolicy(domain_rate_limits=WEALTH_DOMAIN_RATE_LIMITS)
    extractor = ArticleExtractor()
    parser = SitemapParser()
    robots_checker = RobotsChecker() if check_robots else None
    semaphore = asyncio.Semaphore(concurrency)

    state = _BackfillState(limit=limit)

    with ScrapeStateDB(db_path) as db:
        for tier in tier_order:
            tier_sites = [s for s in sites if s.get("backfill_tier") == tier]
            if not tier_sites:
                continue

            logger.info(
                "processing_backfill_tier",
                tier=tier,
                site_count=len(tier_sites),
                concurrency=concurrency,
            )

            if state.limit_reached:
                logger.info("backfill_limit_reached", limit=limit)
                break

            # Process all sites in this tier concurrently
            tasks = [
                _scrape_site_backfill(
                    site=site,
                    tier=tier,
                    state=state,
                    effective_per_domain=effective_per_domain,
                    db=db,
                    policy=policy,
                    extractor=extractor,
                    parser=parser,
                    robots_checker=robots_checker,
                    retry_failed=retry_failed,
                    dry_run=dry_run,
                    semaphore=semaphore,
                )
                for site in tier_sites
            ]
            await asyncio.gather(*tasks)

        # QUAL-006: Collect stats inside the `with` block so db._conn is still open.
        stats = db.get_stats() if not dry_run else {}

    # Print summary
    print("\n" + "=" * 60)
    print("Wealth Blog Backfill Scraping Complete")
    print("=" * 60)
    print(f"  Scraped: {state.total_scraped}")
    print(f"  Skipped: {state.total_skipped}")
    print(f"  Per-domain cap: {effective_per_domain}")
    print(f"  Concurrency: {concurrency}")
    if stats:
        print("\nDomain breakdown:")
        for domain_key, counts in sorted(stats.items()):
            print(
                f"  {domain_key}: success={counts['success']}, failure={counts['failure']}"
            )
    print("=" * 60)

    return 0


def run_backfill(
    limit: int,
    dry_run: bool = False,
    domain_filter: str | None = None,
    backfill_tier: str | None = None,
    check_robots: bool = False,
    retry_failed: bool = False,
    db_path: Path = WEALTH_SCRAPE_DB_PATH,
    per_domain: int = DEFAULT_PER_DOMAIN,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> int:
    """Run backfill mode: sitemap parsing → URL collection → scraping.

    Parameters
    ----------
    limit : int
        Maximum total URLs to scrape.
    dry_run : bool
        If True, only display URL list.
    domain_filter : str | None
        If set, only process this domain.
    backfill_tier : str | None
        If set, only process this backfill tier (A/B/C/D).
    check_robots : bool
        Enable robots.txt checking.
    retry_failed : bool
        Include previously failed URLs.
    db_path : Path
        SQLite state database path.
    per_domain : int
        Maximum articles per domain. 0 means auto-calculate.
    concurrency : int
        Maximum number of domains to scrape concurrently.

    Returns
    -------
    int
        Exit code (0 for success).
    """
    return asyncio.run(
        _run_backfill_async(
            limit=limit,
            dry_run=dry_run,
            domain_filter=domain_filter,
            backfill_tier=backfill_tier,
            check_robots=check_robots,
            retry_failed=retry_failed,
            db_path=db_path,
            per_domain=per_domain,
            concurrency=concurrency,
        )
    )


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------


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

    logger.info(
        "scrape_wealth_blogs_start",
        mode=parsed.mode,
        days=parsed.days,
        dry_run=parsed.dry_run,
    )

    if parsed.mode == "incremental":
        output_path = TMP_DIR / f"{generate_session_id()}.json"
        return run_incremental(
            days=parsed.days,
            top_n=parsed.top_n,
            output_path=output_path,
            dry_run=parsed.dry_run,
            domain_filter=parsed.domain,
            tier_filter=parsed.tier,
            check_robots=parsed.check_robots,
            retry_failed=parsed.retry_failed,
        )
    else:
        # backfill mode
        return run_backfill(
            limit=parsed.limit,
            dry_run=parsed.dry_run,
            domain_filter=parsed.domain,
            backfill_tier=parsed.backfill_tier,
            check_robots=parsed.check_robots,
            retry_failed=parsed.retry_failed,
            per_domain=parsed.per_domain,
            concurrency=parsed.concurrency,
        )


if __name__ == "__main__":
    sys.exit(main())
