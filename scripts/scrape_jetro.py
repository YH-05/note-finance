#!/usr/bin/env python3
"""JETRO news scraping script for automated collection.

Collects trade and business news from JETRO (Japan External Trade
Organization) via RSS feeds and optional Playwright-based category page
crawling, saves articles as JSON to NAS (or local fallback), and
optionally cleans up old data.

This script is intended to be run by macOS launchd on a schedule or
manually from the command line.

Usage
-----
Basic (RSS-only, no Playwright):

    $ uv run python scripts/scrape_jetro.py --no-playwright

Specify categories and regions with full content:

    $ uv run python scripts/scrape_jetro.py \
        --categories world --regions us cn --include-content

Clean up old data (30+ days):

    $ uv run python scripts/scrape_jetro.py --cleanup-days 30

Notes
-----
- Output file: ``{output_dir}/{YYYY-MM-DD}/news_{HHMMSS}.json``
- NAS fallback: ``data/scraped/jetro/`` when NAS is not mounted
- Structured logging via structlog
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import structlog

from data_paths import get_path
from news_scraper._logging import get_logger
from news_scraper.jetro import collect_news
from news_scraper.types import ScraperConfig

logger = get_logger(__name__, module="scrape_jetro")

# Default paths (overridable via environment variables)
# JETRO_NEWS_NAS_DIR  : NAS mount path (preferred)
# JETRO_NEWS_LOCAL_DIR: local fallback when NAS is not mounted
DEFAULT_NAS_OUTPUT = Path(
    os.environ.get("JETRO_NEWS_NAS_DIR", "/Volumes/personal_folder/jetro-news")
)
_local_dir_env = os.environ.get("JETRO_NEWS_LOCAL_DIR")
DEFAULT_LOCAL_FALLBACK = (
    Path(_local_dir_env) if _local_dir_env else get_path("scraped/jetro")
)
DEFAULT_CATEGORIES = ["world", "theme", "industry"]
DEFAULT_CLEANUP_DAYS = 30
DEFAULT_MAX_ARTICLES = 100
DEFAULT_REQUEST_DELAY = 2.0


def _positive_int(value: str) -> int:
    """Validate that a CLI argument is a positive integer.

    Parameters
    ----------
    value : str
        String value from the command line.

    Returns
    -------
    int
        Parsed positive integer.

    Raises
    ------
    argparse.ArgumentTypeError
        If the value is not a positive integer.
    """
    try:
        ivalue = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{value!r} は整数で指定してください") from exc
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(f"{value} は 1 以上の整数を指定してください")
    return ivalue


def _positive_float(value: str) -> float:
    """Validate that a CLI argument is a positive float.

    Parameters
    ----------
    value : str
        String value from the command line.

    Returns
    -------
    float
        Parsed positive float.

    Raises
    ------
    argparse.ArgumentTypeError
        If the value is not a positive float.
    """
    try:
        fvalue = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{value!r} は数値で指定してください") from exc
    if fvalue <= 0:
        raise argparse.ArgumentTypeError(
            f"{value} は 0 より大きい数値を指定してください"
        )
    return fvalue


def _parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns
    -------
    argparse.Namespace
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Collect trade and business news from JETRO",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python scripts/scrape_jetro.py --no-playwright --max-articles 5 --log-level DEBUG
  uv run python scripts/scrape_jetro.py --categories world --regions us --include-content
  uv run python scripts/scrape_jetro.py --cleanup-days 30
        """,
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        choices=["world", "theme", "industry"],
        default=None,
        help="JETRO category groups to fetch (default: all)",
    )
    parser.add_argument(
        "--regions",
        nargs="+",
        default=None,
        metavar="CODE",
        help="Country/region codes to filter (e.g. cn us vn)",
    )
    parser.add_argument(
        "--include-content",
        action="store_true",
        default=False,
        help="Fetch full article content (slower, more requests)",
    )
    parser.add_argument(
        "--no-playwright",
        action="store_true",
        default=False,
        help="RSS-only mode: skip Playwright-based category page crawling",
    )
    parser.add_argument(
        "--max-articles",
        type=_positive_int,
        default=DEFAULT_MAX_ARTICLES,
        metavar="N",
        help=f"Maximum articles to fetch (default: {DEFAULT_MAX_ARTICLES})",
    )
    parser.add_argument(
        "--request-delay",
        type=_positive_float,
        default=DEFAULT_REQUEST_DELAY,
        metavar="SECONDS",
        help=f"Delay between requests in seconds (default: {DEFAULT_REQUEST_DELAY})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            f"Output directory for JSON files (default: {DEFAULT_NAS_OUTPUT}, "
            f"fallback: {DEFAULT_LOCAL_FALLBACK})"
        ),
    )
    parser.add_argument(
        "--cleanup-days",
        type=_positive_int,
        default=None,
        metavar="DAYS",
        help=(
            f"Delete output directories older than DAYS days "
            f"(default: {DEFAULT_CLEANUP_DAYS})"
        ),
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Log level (default: INFO)",
    )
    return parser.parse_args()


def _resolve_output_dir(requested: Path | None) -> Path:
    """Resolve the output directory, falling back to local if NAS is unavailable.

    Parameters
    ----------
    requested : Path | None
        User-requested output directory. If None, tries NAS first.

    Returns
    -------
    Path
        Resolved output directory (NAS or local fallback).
    """
    if requested is not None:
        logger.info("Using requested output directory", path=str(requested))
        return requested

    if DEFAULT_NAS_OUTPUT.exists():
        logger.info("NAS is mounted, using NAS output", path=str(DEFAULT_NAS_OUTPUT))
        return DEFAULT_NAS_OUTPUT

    logger.warning(
        "NAS is not mounted, falling back to local storage",
        nas_path=str(DEFAULT_NAS_OUTPUT),
        fallback_path=str(DEFAULT_LOCAL_FALLBACK),
    )
    return DEFAULT_LOCAL_FALLBACK


def _create_dated_output_dir(base_dir: Path, date: datetime) -> Path:
    """Create and return a dated subdirectory for output.

    Creates a directory at ``{base_dir}/{YYYY-MM-DD}/`` if it does not exist.

    Parameters
    ----------
    base_dir : Path
        Base output directory.
    date : datetime
        Date to use for the subdirectory name.

    Returns
    -------
    Path
        Dated subdirectory path.

    Raises
    ------
    OSError
        If the directory cannot be created.
    """
    dated_dir = base_dir / date.strftime("%Y-%m-%d")
    dated_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Output directory ready", path=str(dated_dir))
    return dated_dir


def _save_articles_json(
    articles_json: list[dict],
    output_dir: Path,
    timestamp: datetime,
) -> Path:
    """Save articles to a JSON file in the output directory.

    Parameters
    ----------
    articles_json : list[dict]
        Articles as JSON-serializable dictionaries.
    output_dir : Path
        Directory to save the file.
    timestamp : datetime
        Timestamp for the file name.

    Returns
    -------
    Path
        Path to the created JSON file.

    Raises
    ------
    OSError
        If the file cannot be written.
    """
    filename = f"news_{timestamp.strftime('%H%M%S')}.json"
    output_path = output_dir / filename

    payload = {
        "collected_at": timestamp.isoformat(),
        "total_count": len(articles_json),
        "news": articles_json,
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    logger.info(
        "Articles saved to JSON",
        path=str(output_path),
        total_count=len(articles_json),
    )
    return output_path


def _cleanup_old_data(base_dir: Path, max_age_days: int) -> int:
    """Delete dated subdirectories older than max_age_days.

    Removes directories of the form ``{YYYY-MM-DD}`` that are more than
    ``max_age_days`` days old.

    Parameters
    ----------
    base_dir : Path
        Base output directory to scan.
    max_age_days : int
        Maximum age in days. Directories older than this are deleted.

    Returns
    -------
    int
        Number of directories deleted.
    """
    if not base_dir.exists():
        logger.debug("Cleanup: base directory does not exist", path=str(base_dir))
        return 0

    now = datetime.now(timezone.utc)
    deleted_count = 0

    for subdir in sorted(base_dir.iterdir()):
        if not subdir.is_dir():
            continue

        try:
            dir_date = datetime.strptime(subdir.name, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            logger.debug("Skipping non-dated directory", name=subdir.name)
            continue

        age_days = (now - dir_date).days
        if age_days > max_age_days:
            shutil.rmtree(subdir)
            deleted_count += 1
            logger.info(
                "Deleted old data directory",
                path=str(subdir),
                age_days=age_days,
                max_age_days=max_age_days,
            )

    logger.info(
        "Cleanup complete",
        deleted_directories=deleted_count,
        max_age_days=max_age_days,
    )
    return deleted_count


def _articles_to_json(articles: list) -> list[dict]:
    """Convert Article models to JSON-serializable dicts.

    Parameters
    ----------
    articles : list
        List of Article pydantic models.

    Returns
    -------
    list[dict]
        JSON-serializable list of article dictionaries.
    """
    result: list[dict] = []
    for article in articles:
        record: dict = {
            "title": article.title,
            "url": article.url,
            "published": article.published.isoformat(),
            "source": article.source,
            "category": article.category,
            "summary": article.summary,
            "content": article.content,
            "author": article.author,
            "tags": article.tags,
            "fetched_at": article.fetched_at.isoformat(),
            "metadata": article.metadata,
        }
        result.append(record)
    return result


def main() -> int:
    """Run the JETRO news scraping script.

    Returns
    -------
    int
        Exit code: 0 for success, 1 for failure.
    """
    args = _parse_args()

    # Setup logging level
    import logging

    logging.basicConfig(level=getattr(logging, args.log_level, logging.INFO))
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, args.log_level, logging.INFO)
        ),
    )

    logger.info(
        "JETRO news scraper starting",
        categories=args.categories,
        regions=args.regions,
        include_content=args.include_content,
        no_playwright=args.no_playwright,
        max_articles=args.max_articles,
        request_delay=args.request_delay,
    )

    # Resolve output directory
    output_dir = _resolve_output_dir(args.output_dir)

    # Setup scraper config
    config = ScraperConfig(
        include_content=args.include_content,
        max_articles_per_source=args.max_articles,
        request_delay=args.request_delay,
        use_playwright=not args.no_playwright,
    )

    # Collect news
    now = datetime.now(timezone.utc)
    logger.info(
        "Starting JETRO news collection",
        categories=args.categories,
        regions=args.regions,
    )

    try:
        articles = collect_news(
            config=config,
            categories=args.categories,
            regions=args.regions,
        )
    except Exception as e:
        logger.error("JETRO news collection failed", error=str(e), exc_info=True)
        return 1

    logger.info("Collection complete", article_count=len(articles))

    if not articles:
        logger.warning("No articles collected, skipping save")
        # Still run cleanup if requested
        if args.cleanup_days is not None:
            logger.info("Running cleanup", max_age_days=args.cleanup_days)
            deleted = _cleanup_old_data(output_dir, args.cleanup_days)
            logger.info("Cleanup finished", deleted_directories=deleted)
        return 0

    # Create dated subdirectory
    try:
        dated_dir = _create_dated_output_dir(output_dir, now)
    except OSError as e:
        logger.error("Failed to create output directory", error=str(e), exc_info=True)
        return 1

    # Convert articles to JSON and save
    try:
        articles_json = _articles_to_json(articles)
        output_path = _save_articles_json(articles_json, dated_dir, now)
        logger.info("Save complete", output_file=str(output_path))
    except OSError as e:
        logger.error("Failed to save articles", error=str(e), exc_info=True)
        return 1

    # Optional cleanup
    if args.cleanup_days is not None:
        logger.info("Running cleanup", max_age_days=args.cleanup_days)
        deleted = _cleanup_old_data(output_dir, args.cleanup_days)
        logger.info("Cleanup finished", deleted_directories=deleted)

    logger.info(
        "JETRO scraper finished successfully",
        output_file=str(output_path),
        total_articles=len(articles),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
