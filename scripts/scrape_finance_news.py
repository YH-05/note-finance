#!/usr/bin/env python3
"""Finance news scraping script for automated collection.

Collects financial news from multiple sources (CNBC, NASDAQ, Kabutan,
Reuters JP, Minkabu, JETRO), saves articles as JSON to NAS (or local
fallback), and optionally cleans up old data.

This script is intended to be run by macOS launchd on a schedule
(every 6 hours), but can also be run manually.

Usage
-----
Basic (default settings):

    $ uv run python scripts/scrape_finance_news.py

Specify output directory and sources:

    $ uv run python scripts/scrape_finance_news.py \\
        --output-dir /Volumes/personal_folder/finance-news \\
        --sources cnbc nasdaq \\
        --include-content

Clean up old data (30+ days):

    $ uv run python scripts/scrape_finance_news.py --cleanup-days 30

Notes
-----
- Output file: ``{output_dir}/{YYYY-MM-DD}/news_{HHMMSS}.json``
- NAS fallback: ``data/scraped/`` when NAS is not mounted
- Structured logging via structlog
"""

from __future__ import annotations

import sys
from pathlib import Path

# AIDEV-NOTE: パッケージ衝突の保険として src/ を確実に Python パスに含める
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import argparse
import asyncio
import json
import os
import shutil
from datetime import datetime, timezone

import structlog

from data_paths import get_path
from news_scraper import ScraperConfig, collect_financial_news
from news_scraper._logging import get_logger

logger = get_logger(__name__, module="scrape_finance_news")

# Default paths (overridable via environment variables)
# FINANCE_NEWS_NAS_DIR  : NAS マウントパス（優先）
# FINANCE_NEWS_LOCAL_DIR: NAS 未マウント時のローカルフォールバック
DEFAULT_NAS_OUTPUT = Path(
    os.environ.get("FINANCE_NEWS_NAS_DIR", "/Volumes/personal_folder/finance-news")
)
_local_dir_env = os.environ.get("FINANCE_NEWS_LOCAL_DIR")
DEFAULT_LOCAL_FALLBACK = Path(_local_dir_env) if _local_dir_env else get_path("scraped")
DEFAULT_SOURCES = ["cnbc"]
DEFAULT_CLEANUP_DAYS = 30


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


def _parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns
    -------
    argparse.Namespace
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Collect financial news from multiple sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python scripts/scrape_finance_news.py
  uv run python scripts/scrape_finance_news.py --output-dir /Volumes/NAS/finance-news
  uv run python scripts/scrape_finance_news.py --sources cnbc --include-content
  uv run python scripts/scrape_finance_news.py --cleanup-days 30
        """,
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
        "--sources",
        nargs="+",
        choices=["cnbc", "nasdaq", "kabutan", "reuters_jp", "minkabu", "jetro"],
        default=DEFAULT_SOURCES,
        help="News sources to collect from (default: cnbc)",
    )
    parser.add_argument(
        "--include-content",
        action="store_true",
        default=False,
        help="Fetch full article content (slower, more requests)",
    )
    parser.add_argument(
        "--cleanup-days",
        type=_positive_int,
        default=None,
        metavar="DAYS",
        help=f"Delete output directories older than DAYS days (default: {DEFAULT_CLEANUP_DAYS})",
    )
    parser.add_argument(
        "--max-articles",
        type=_positive_int,
        default=50,
        metavar="N",
        help="Maximum articles per source (default: 50)",
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
    # Use user-provided path if specified
    if requested is not None:
        logger.info("Using requested output directory", path=str(requested))
        return requested

    # Try NAS mount
    if DEFAULT_NAS_OUTPUT.exists():
        logger.info("NAS is mounted, using NAS output", path=str(DEFAULT_NAS_OUTPUT))
        return DEFAULT_NAS_OUTPUT

    # Fall back to local directory
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
    articles_json: list[dict], output_dir: Path, timestamp: datetime
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

    Examples
    --------
    >>> # Tested via unit tests with mock filesystem
    """
    if not base_dir.exists():
        logger.debug("Cleanup: base directory does not exist", path=str(base_dir))
        return 0

    now = datetime.now(timezone.utc)
    deleted_count = 0

    for subdir in sorted(base_dir.iterdir()):
        if not subdir.is_dir():
            continue

        # Only process YYYY-MM-DD formatted directories
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


def main() -> int:
    """Run the finance news scraping script.

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
        "Finance news scraper starting",
        sources=args.sources,
        include_content=args.include_content,
        max_articles=args.max_articles,
    )

    # Resolve output directory
    output_dir = _resolve_output_dir(args.output_dir)

    # Setup scraper config
    config = ScraperConfig(
        include_content=args.include_content,
        max_articles_per_source=args.max_articles,
    )

    # Collect news
    now = datetime.now(timezone.utc)
    logger.info("Starting news collection", sources=args.sources)

    try:
        df = asyncio.run(collect_financial_news(sources=args.sources, config=config))
    except Exception as e:
        logger.error("News collection failed", error=str(e), exc_info=True)
        return 1

    logger.info("Collection complete", article_count=len(df))

    if df.empty:
        logger.warning("No articles collected, skipping save")
        return 0

    # Create dated subdirectory
    try:
        dated_dir = _create_dated_output_dir(output_dir, now)
    except OSError as e:
        logger.error("Failed to create output directory", error=str(e), exc_info=True)
        return 1

    # Save to JSON
    try:
        articles_json = df.to_json()
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
        "Scraper finished successfully",
        output_file=str(output_path),
        total_articles=len(df),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
