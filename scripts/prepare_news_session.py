#!/usr/bin/env python3
"""Finance News Session Preparation Script.

Performs deterministic preprocessing for the finance news workflow,
reducing AI agent context load by handling:
- Existing Issue retrieval and URL extraction
- RSS feed fetching by theme
- Date filtering
- Duplicate checking

Usage:
    uv run python scripts/prepare_news_session.py --days 7 --themes all

Output:
    Session JSON file in .tmp/ directory
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pydantic import BaseModel, Field

from data_paths import get_path

from _script_utils import FINANCE_NEWS_THEMES_CONFIG
from rss.services.feed_reader import FeedReader
from rss.utils.url_normalizer import normalize_url
from session_utils import (
    ArticleData,
    BlockedArticle,
    SessionStats,
    configure_logging,
    filter_by_date,
    get_logger as _get_logger,
    load_json_config,
    select_top_n,
    write_session_file,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_DAYS = 7
"""Default number of days to look back for articles."""

DEFAULT_THEMES = "all"
"""Default theme filter (all themes)."""

DEFAULT_TOP_N = 10
"""Default number of top articles per theme (sorted by published date, newest first)."""

DEFAULT_DATA_DIR = get_path("raw/rss")
"""Default RSS data directory."""

THEME_CONFIG_PATH = FINANCE_NEWS_THEMES_CONFIG
"""Path to theme configuration file."""

TMP_DIR = Path(".tmp")
"""Temporary directory for session files."""

REPO = "YH-05/finance"
"""GitHub repository."""

URL_PATTERN = re.compile(r"https?://[^\s<>\"\)]+")
"""Regex pattern for extracting URLs from text."""


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

logger = _get_logger(__name__)


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------


class SessionConfig(BaseModel):
    """GitHub Project configuration for the session.

    Attributes
    ----------
    project_id : str
        GitHub Project ID (PVT_...).
    project_number : int
        GitHub Project number.
    project_owner : str
        GitHub Project owner username.
    status_field_id : str
        Status field ID in the Project.
    published_date_field_id : str
        Published date field ID in the Project.
    """

    project_id: str
    project_number: int
    project_owner: str
    status_field_id: str
    published_date_field_id: str


class ThemeConfig(BaseModel):
    """Theme-specific configuration.

    Attributes
    ----------
    name_ja : str
        Japanese name of the theme.
    github_status_id : str
        GitHub Project Status option ID.
    """

    name_ja: str
    github_status_id: str


# AIDEV-NOTE: ArticleData, BlockedArticle are imported from session_utils


class ThemeData(BaseModel):
    """Data for a single theme.

    Attributes
    ----------
    articles : list[ArticleData]
        List of accessible articles.
    blocked : list[BlockedArticle]
        List of blocked articles.
    theme_config : ThemeConfig
        Theme-specific configuration.
    """

    articles: list[ArticleData] = Field(default_factory=list)
    blocked: list[BlockedArticle] = Field(default_factory=list)
    theme_config: ThemeConfig


# AIDEV-NOTE: SessionStats is imported from session_utils


class NewsSession(BaseModel):
    """Complete news session data.

    Attributes
    ----------
    session_id : str
        Unique session identifier (news-{YYYYMMDD}-{HHMMSS}).
    timestamp : str
        Session creation timestamp in ISO 8601 format.
    config : SessionConfig
        GitHub Project configuration.
    themes : dict[str, ThemeData]
        Theme data keyed by theme key.
    stats : SessionStats
        Session statistics.
    """

    session_id: str
    timestamp: str
    config: SessionConfig
    themes: dict[str, ThemeData]
    stats: SessionStats


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
        description="Prepare finance news session for AI workflow.",
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


def load_theme_config(config_path: Path = THEME_CONFIG_PATH) -> dict[str, Any]:
    """Load theme configuration from JSON file.

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
    return load_json_config(config_path)


# ---------------------------------------------------------------------------
# Existing Issues Retrieval
# ---------------------------------------------------------------------------


def extract_urls_from_issues(issues: list[dict[str, Any]]) -> set[str]:
    """Extract article URLs from issue bodies.

    Parameters
    ----------
    issues : list[dict[str, Any]]
        List of GitHub issues.

    Returns
    -------
    set[str]
        Set of normalized article URLs found in issue bodies.
    """
    urls: set[str] = set()

    for issue in issues:
        body = issue.get("body", "") or ""

        # Find all URLs in the body
        found_urls = URL_PATTERN.findall(body)

        for url in found_urls:
            # Skip GitHub URLs
            if "github.com" in url:
                continue

            # Normalize and add
            normalized = normalize_url(url)
            if normalized:
                urls.add(normalized)

    logger.debug("extracted_urls", unique_count=len(urls), issue_count=len(issues))
    return urls


def get_existing_issues_with_urls(
    project_number: int,
    owner: str,
    days_back: int = 30,
) -> tuple[list[dict[str, Any]], set[str]]:
    """Fetch existing issues from GitHub Project and extract URLs.

    Parameters
    ----------
    project_number : int
        GitHub Project number.
    owner : str
        GitHub Project owner.
    days_back : int
        Number of days to look back for issues.

    Returns
    -------
    tuple[list[dict[str, Any]], set[str]]
        Tuple of (issues list, extracted URLs set).
    """
    logger.info(
        "fetching_existing_issues",
        project_number=project_number,
        days_back=days_back,
    )

    try:
        # Use gh CLI to get project items
        result = subprocess.run(
            [
                "gh",
                "project",
                "item-list",
                str(project_number),
                "--owner",
                owner,
                "--limit",
                "500",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        data = json.loads(result.stdout)
        items = data.get("items", [])

        # Extract issue data
        issues: list[dict[str, Any]] = []
        for item in items:
            content = item.get("content", {})
            if content.get("type") == "Issue":
                issues.append(
                    {
                        "number": content.get("number"),
                        "title": content.get("title"),
                        "body": content.get("body", ""),
                        "url": content.get("url"),
                    }
                )

        logger.info("found_existing_issues", count=len(issues))

        # Extract URLs
        urls = extract_urls_from_issues(issues)
        logger.info("extracted_unique_article_urls", count=len(urls))

        return issues, urls

    except subprocess.CalledProcessError as e:
        logger.warning("failed_to_fetch_project_items", error=e.stderr)
        return [], set()
    except json.JSONDecodeError as e:
        logger.warning("failed_to_parse_project_items", error=str(e))
        return [], set()


# ---------------------------------------------------------------------------
# RSS Feed Fetching
# ---------------------------------------------------------------------------


def fetch_rss_items_by_theme(
    theme_config: dict[str, Any],
    data_dir: Path,
    selected_themes: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Fetch RSS items grouped by theme.

    Parameters
    ----------
    theme_config : dict[str, Any]
        Theme configuration with feed mappings.
    data_dir : Path
        RSS data directory.
    selected_themes : list[str] | None
        List of theme keys to fetch. If None, fetches all.

    Returns
    -------
    dict[str, list[dict[str, Any]]]
        RSS items keyed by theme key.
    """
    logger.info("fetching_rss_items_by_theme", data_dir=str(data_dir))

    reader = FeedReader(data_dir)
    items_by_theme: dict[str, list[dict[str, Any]]] = {}

    themes = theme_config.get("themes", {})

    for theme_key, theme_data in themes.items():
        # Skip if not in selected themes
        if selected_themes and theme_key not in selected_themes:
            continue

        theme_items: list[dict[str, Any]] = []
        feeds = theme_data.get("feeds", [])

        for feed_info in feeds:
            feed_id = feed_info.get("feed_id")
            feed_title = feed_info.get("title", "Unknown")

            try:
                items = reader.get_items(feed_id=feed_id)
                for item in items:
                    theme_items.append(
                        {
                            "item_id": item.item_id,
                            "title": item.title,
                            "link": item.link,
                            "published": item.published,
                            "summary": item.summary or "",
                            "content": item.content,
                            "author": item.author,
                            "fetched_at": item.fetched_at,
                            "feed_source": feed_title,
                        }
                    )
            except Exception as e:
                logger.warning("failed_to_fetch_feed_items", feed_id=feed_id, error=str(e))

        items_by_theme[theme_key] = theme_items
        logger.debug("fetched_theme_items", theme=theme_key, count=len(theme_items))

    return items_by_theme


# AIDEV-NOTE: filter_by_date is imported from session_utils


# AIDEV-NOTE: select_top_n is imported from session_utils


# ---------------------------------------------------------------------------
# Duplicate Checking
# ---------------------------------------------------------------------------


def check_duplicates(
    items: list[dict[str, Any]],
    existing_urls: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Check for duplicate URLs against existing issues.

    Parameters
    ----------
    items : list[dict[str, Any]]
        List of RSS items.
    existing_urls : set[str]
        Set of normalized URLs from existing issues.

    Returns
    -------
    tuple[list[dict[str, Any]], list[dict[str, Any]]]
        Tuple of (unique items, duplicate items).
    """
    unique: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []

    for item in items:
        link = item.get("link", "")
        normalized = normalize_url(link)

        if normalized and normalized in existing_urls:
            duplicates.append(item)
        else:
            unique.append(item)
            # Add to existing URLs to catch duplicates within the batch
            if normalized:
                existing_urls.add(normalized)

    logger.debug(
        "duplicate_check_completed",
        unique_count=len(unique),
        duplicate_count=len(duplicates),
    )

    return unique, duplicates


# ---------------------------------------------------------------------------
# Session Generation
# ---------------------------------------------------------------------------


def generate_session_id() -> str:
    """Generate a unique session ID.

    Returns
    -------
    str
        Session ID in format news-{YYYYMMDD}-{HHMMSS}.
    """
    now = datetime.now(timezone.utc)
    return f"news-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"


def calculate_stats(
    theme_results: dict[str, dict[str, list[Any]]],
    total_fetched: int,
    duplicates_count: int,
) -> dict[str, int]:
    """Calculate session statistics.

    Parameters
    ----------
    theme_results : dict[str, dict[str, list[Any]]]
        Theme results with articles and blocked lists.
    total_fetched : int
        Total number of articles fetched from RSS.
    duplicates_count : int
        Number of duplicate articles filtered.

    Returns
    -------
    dict[str, int]
        Statistics dictionary.
    """
    accessible = sum(len(data.get("articles", [])) for data in theme_results.values())

    return {
        "total": total_fetched,
        "duplicates": duplicates_count,
        "accessible": accessible,
    }


def generate_session(
    theme_results: dict[str, dict[str, Any]],
    theme_config: dict[str, Any],
    stats: dict[str, int],
) -> NewsSession:
    """Generate the complete session data structure.

    Parameters
    ----------
    theme_results : dict[str, dict[str, Any]]
        Theme results with articles and blocked lists.
    theme_config : dict[str, Any]
        Full theme configuration.
    stats : dict[str, int]
        Session statistics.

    Returns
    -------
    NewsSession
        Complete session data.
    """
    project_config = theme_config.get("project", {})
    themes_config = theme_config.get("themes", {})

    # Build theme data
    themes: dict[str, ThemeData] = {}

    for theme_key, results in theme_results.items():
        theme_info = themes_config.get(theme_key, {})

        # Build articles
        articles = [
            ArticleData(
                url=item.get("link", ""),
                title=item.get("title", ""),
                summary=item.get("summary", ""),
                feed_source=item.get("feed_source", "Unknown"),
                published=item.get("published", ""),
            )
            for item in results.get("articles", [])
        ]

        # Build blocked
        blocked = [
            BlockedArticle(
                url=item.get("link", ""),
                title=item.get("title", ""),
                summary=item.get("summary", ""),
                reason=item.get("reason", "Unknown"),
            )
            for item in results.get("blocked", [])
        ]

        themes[theme_key] = ThemeData(
            articles=articles,
            blocked=blocked,
            theme_config=ThemeConfig(
                name_ja=theme_info.get("name_ja", theme_key),
                github_status_id=theme_info.get("github_status_id", ""),
            ),
        )

    return NewsSession(
        session_id=generate_session_id(),
        timestamp=datetime.now(timezone.utc).isoformat(),
        config=SessionConfig(
            project_id=project_config.get("project_id", ""),
            project_number=project_config.get("number", 0),
            project_owner=project_config.get("owner", ""),
            status_field_id=project_config.get("status_field_id", ""),
            published_date_field_id=project_config.get("published_date_field_id", ""),
        ),
        themes=themes,
        stats=SessionStats(**stats),
    )


# ---------------------------------------------------------------------------
# Output File
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


# AIDEV-NOTE: write_session_file is imported from session_utils


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def run_async(
    days: int,
    themes_filter: list[str] | None,
    output_path: Path,
    top_n: int = DEFAULT_TOP_N,
) -> int:
    """Run the main async processing.

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
    # Load configuration
    theme_config = load_theme_config()
    project_config = theme_config.get("project", {})

    # Get existing issues and URLs
    _, existing_urls = get_existing_issues_with_urls(
        project_number=project_config.get("number", 15),
        owner=project_config.get("owner", "YH-05"),
        days_back=30,
    )

    # Fetch RSS items by theme
    items_by_theme = fetch_rss_items_by_theme(
        theme_config=theme_config,
        data_dir=DEFAULT_DATA_DIR,
        selected_themes=themes_filter,
    )

    # Process each theme
    theme_results: dict[str, dict[str, Any]] = {}
    total_fetched = 0
    total_duplicates = 0

    for theme_key, items in items_by_theme.items():
        logger.info("processing_theme", theme=theme_key, item_count=len(items))
        total_fetched += len(items)

        # Filter by date
        date_filtered = filter_by_date(items, days)
        logger.debug(
            "after_date_filter",
            input_count=len(items),
            output_count=len(date_filtered),
        )

        # Check duplicates
        unique, duplicates = check_duplicates(date_filtered, existing_urls)
        total_duplicates += len(duplicates)

        # Select top N articles (newest first)
        selected = select_top_n(unique, top_n)

        theme_results[theme_key] = {
            "articles": selected,
            "blocked": [],
        }

        logger.info(
            "theme_processing_complete",
            theme=theme_key,
            article_count=len(selected),
            duplicate_count=len(duplicates),
            top_n=top_n,
            unique_count=len(unique),
        )

    # Calculate stats
    stats = calculate_stats(theme_results, total_fetched, total_duplicates)

    # Generate session
    session = generate_session(theme_results, theme_config, stats)

    # Write output
    write_session_file(session, output_path)

    # Print summary
    print("\n" + "=" * 60)
    print("Finance News Session Preparation Complete")
    print("=" * 60)
    print(f"Session ID: {session.session_id}")
    print(f"Output: {output_path}")
    print("\nStatistics:")
    print(f"  Total fetched: {stats['total']}")
    print(f"  Duplicates: {stats['duplicates']}")
    print(f"  Accessible: {stats['accessible']}")
    print("\nTheme breakdown:")
    for theme_key, data in theme_results.items():
        print(f"  {theme_key}: {len(data['articles'])} articles")
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

    # Parse themes
    themes_filter: list[str] | None = None
    if parsed.themes != "all":
        themes_filter = [t.strip() for t in parsed.themes.split(",")]

    # Determine output path
    output_path = Path(parsed.output) if parsed.output else get_default_output_path()

    # Run async processing
    return asyncio.run(
        run_async(
            days=parsed.days,
            themes_filter=themes_filter,
            output_path=output_path,
            top_n=parsed.top_n,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
