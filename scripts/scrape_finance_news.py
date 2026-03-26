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

Specify sources:

    $ uv run python scripts/scrape_finance_news.py \\
        --sources cnbc nasdaq \\
        --include-content

Clean up old data (30+ days):

    $ uv run python scripts/scrape_finance_news.py --cleanup-days 30

Notes
-----
- Output file: ``{NAS}/{source}/{YYYY-MM-DD}/news_{HHMMSS}.json``
  e.g. ``/Volumes/personal_folder/scraped/cnbc/2026-03-19/news_031218.json``
- NAS fallback: ``data/scraped/{source}/`` when NAS is not mounted
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
from typing import Any

import structlog

from data_paths import get_path
from news_scraper import ScraperConfig, collect_financial_news
from news_scraper._logging import get_logger

logger = get_logger(__name__, module="scrape_finance_news")

# Default paths
# AIDEV-NOTE: 全NASパスは環境変数で上書き可能。Mac Mini等の別マシンから実行する場合は
# launchd plist の EnvironmentVariables に適切なマウントパスを設定すること。
NAS_SCRAPED_BASE = Path(os.environ.get("NAS_SCRAPED_BASE", "/Volumes/personal_folder/scraped"))
NAS_GRAPH_QUEUE_BASE = Path(os.environ.get("GRAPH_QUEUE_DIR", "/Volumes/personal_folder/graph-queue"))
DEFAULT_SOURCES = ["cnbc"]
DEFAULT_CLEANUP_DAYS = 30


def _resolve_source_output_dir(source: str) -> Path:
    """Resolve per-source output directory (NAS preferred, local fallback).

    Parameters
    ----------
    source : str
        Source name (e.g. "cnbc", "nasdaq").

    Returns
    -------
    Path
        Resolved output directory for the source.
    """
    nas_dir = NAS_SCRAPED_BASE / source
    if NAS_SCRAPED_BASE.exists():
        logger.info("NAS is mounted, using NAS output", source=source, path=str(nas_dir))
        return nas_dir

    local_dir = get_path(f"scraped/{source}")
    logger.warning(
        "NAS is not mounted, falling back to local storage",
        source=source,
        nas_path=str(nas_dir),
        fallback_path=str(local_dir),
    )
    return local_dir


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
  uv run python scripts/scrape_finance_news.py --sources cnbc --include-content
  uv run python scripts/scrape_finance_news.py --cleanup-days 30
        """,
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=["cnbc", "nasdaq", "kabutan", "reuters_jp", "minkabu", "jetro"],
        default=DEFAULT_SOURCES,
        help="News sources to collect from (default: cnbc)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override output directory (ignores per-source NAS resolution)",
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
    # JETRO-specific options
    parser.add_argument(
        "--jetro-categories",
        nargs="+",
        default=None,
        metavar="CAT",
        help="JETRO category groups to crawl (e.g. world theme industry)",
    )
    parser.add_argument(
        "--jetro-regions",
        type=str,
        default=None,
        metavar="JSON",
        help='JETRO regions as JSON (e.g. \'{"asia": ["cn", "kr"]}\')',
    )
    parser.add_argument(
        "--jetro-archive-pages",
        type=int,
        default=0,
        metavar="N",
        help="Number of JETRO archive pages to crawl per country (default: 0)",
    )
    parser.add_argument(
        "--use-playwright",
        action="store_true",
        default=False,
        help="Use Playwright for JavaScript-rendered pages",
    )
    parser.add_argument(
        "--skip-neo4j",
        action="store_true",
        default=False,
        help="Skip research-neo4j ingestion (default: ingest automatically)",
    )
    return parser.parse_args()


def _resolve_output_dir(requested: Path | None, source: str) -> Path:
    """Resolve the output directory for a specific source.

    Parameters
    ----------
    requested : Path | None
        User-requested output directory override.
    source : str
        Source name (e.g. "cnbc", "nasdaq").

    Returns
    -------
    Path
        Resolved output directory.
    """
    if requested is not None:
        # When user overrides, use a source subdirectory under the requested path
        out = requested / source
        logger.info("Using requested output directory", source=source, path=str(out))
        return out

    return _resolve_source_output_dir(source)


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


def _neo4j_article(article: dict) -> dict:
    """スクレイピング済み記事dict を finance-news-workflow 入力形式に変換する.

    Parameters
    ----------
    article : dict
        ``NewsDataFrame.to_json()`` が返すdict（Article モデルの直列化）。

    Returns
    -------
    dict
        ``map_finance_news`` が期待する article dict。
    """
    metadata = article.get("metadata") or {}
    return {
        "url": article.get("url", ""),
        "title": article.get("title", ""),
        "published": article.get("published", ""),
        "feed_source": article.get("source", "") or metadata.get("feed_source", ""),
        "summary": article.get("summary") or "",
    }


def _ingest_source_to_neo4j(
    source_articles_json: list[dict],
    source: str,
    now: datetime,
    *,
    skip_ingest: bool = False,
) -> None:
    """スクレイピング済み記事を graph-queue 化し、必要に応じて Neo4j に投入する.

    Phase 1: graph-queue ドキュメント生成（常に実行）
    Phase 2: NAS へ queue ファイル保存（常に実行 → メインマシンから後で投入可能）
    Phase 3: Neo4j 投入（skip_ingest=True の場合はスキップ）

    Parameters
    ----------
    source_articles_json : list[dict]
        当該ソースの記事dict リスト（NewsDataFrame.to_json() 形式）。
    source : str
        ソース名（"cnbc" 等）。
    now : datetime
        実行時刻（session_id 生成に使用）。
    skip_ingest : bool
        True の場合は Phase 3（Neo4j 投入）をスキップし queue ファイルのみ保存。
    """
    # AIDEV-NOTE: emit_research_queue は scripts/ 配下のスクリプトなので
    #   lazy import で取り込む。neo4j が起動していない場合でもスクレイパーを
    #   クラッシュさせないため、全体を try/except で包む。
    try:
        from emit_research_queue import (  # type: ignore[import]
            _build_queue_doc,
            _write_output,
            DEFAULT_OUTPUT_BASE,
            map_finance_news,
        )
        from data_pipeline.neo4j_loader import ingest_to_neo4j
    except ImportError as exc:
        logger.warning(
            "Neo4j pipeline modules not available, skipping ingestion",
            source=source,
            error=str(exc),
        )
        return

    mapped_articles = [_neo4j_article(a) for a in source_articles_json]
    data = {
        "articles": mapped_articles,
        "session_id": f"scrape-{source}-{now.strftime('%Y%m%d%H%M%S')}",
        "batch_label": source,
    }

    # Phase 1: graph-queue ドキュメント生成（失敗時は投入もスキップ）
    try:
        mapped = map_finance_news(data)
        queue_doc = _build_queue_doc("finance-news-workflow", mapped)
    except Exception as exc:
        logger.warning(
            "Graph-queue build failed, skipping neo4j ingestion",
            source=source,
            error=str(exc),
            exc_info=True,
        )
        return

    # Phase 2: queue ファイル保存（監査ログ目的。失敗しても neo4j 投入は継続）
    # AIDEV-NOTE: NAS_GRAPH_QUEUE_BASE は NAS マウント優先。NAS 未マウント時は
    # DEFAULT_OUTPUT_BASE（.tmp/graph-queue）にフォールバック。
    queue_base = NAS_GRAPH_QUEUE_BASE if NAS_GRAPH_QUEUE_BASE.parent.exists() else DEFAULT_OUTPUT_BASE
    queue_file: Path | None = None
    try:
        queue_file = _write_output(queue_doc, "finance-news-workflow", queue_base)
    except Exception as exc:
        logger.warning(
            "Queue file write failed (non-blocking, neo4j ingestion continues)",
            source=source,
            error=str(exc),
        )

    # Phase 3: neo4j 投入（skip_ingest=True の場合はスキップ）
    if skip_ingest:
        logger.info(
            "Neo4j ingestion skipped (--skip-neo4j). Queue file saved for later ingestion.",
            source=source,
            queue_file=str(queue_file) if queue_file else "not saved",
        )
        return

    try:
        result = ingest_to_neo4j(queue_doc)
        logger.info(
            "Neo4j ingestion complete",
            source=source,
            nodes=result.get("nodes", 0),
            relations=result.get("relations", 0),
            queue_file=str(queue_file) if queue_file else "not saved",
        )
    except Exception as exc:
        logger.warning(
            "Neo4j ingestion failed (non-blocking)",
            source=source,
            error=str(exc),
            exc_info=True,
        )


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

    Saves articles to per-source directories (cnbc/, nasdaq/).

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

    # Build per-source options from CLI arguments
    source_options: dict[str, dict[str, Any]] = {}
    if args.jetro_categories or args.jetro_regions or args.jetro_archive_pages:
        jetro_opts: dict[str, Any] = {}
        if args.jetro_categories:
            jetro_opts["categories"] = args.jetro_categories
        if args.jetro_regions:
            try:
                raw_regions = json.loads(args.jetro_regions)
            except json.JSONDecodeError:
                logger.error(
                    "Invalid JSON for --jetro-regions", raw=args.jetro_regions
                )
                return 1
            if not isinstance(raw_regions, dict) or not all(
                isinstance(k, str)
                and isinstance(v, list)
                and all(isinstance(c, str) for c in v)
                for k, v in raw_regions.items()
            ):
                logger.error(
                    "--jetro-regions must be dict[str, list[str]]",
                    raw=args.jetro_regions,
                )
                return 1
            jetro_opts["regions"] = raw_regions
        if args.jetro_archive_pages > 0:
            jetro_opts["archive_pages"] = args.jetro_archive_pages
        source_options["jetro"] = jetro_opts


    # Setup scraper config
    config = ScraperConfig(
        include_content=args.include_content,
        max_articles_per_source=args.max_articles,
        use_playwright=args.use_playwright,
        source_options=source_options,
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

    # Save per source
    saved_files: list[str] = []
    all_articles = df.to_json()
    for source in args.sources:
        source_articles_json = [a for a in all_articles if a.get("source") == source]

        if not source_articles_json:
            logger.info("No articles for source, skipping", source=source)
            continue

        # Resolve per-source output directory
        source_output_dir = _resolve_output_dir(args.output_dir, source)

        try:
            dated_dir = _create_dated_output_dir(source_output_dir, now)
        except OSError as e:
            logger.error(
                "Failed to create output directory",
                source=source,
                error=str(e),
                exc_info=True,
            )
            return 1

        try:
            output_path = _save_articles_json(source_articles_json, dated_dir, now)
            saved_files.append(str(output_path))
            logger.info(
                "Save complete",
                source=source,
                output_file=str(output_path),
                count=len(source_articles_json),
            )
        except OSError as e:
            logger.error(
                "Failed to save articles",
                source=source,
                error=str(e),
                exc_info=True,
            )
            return 1

        # graph-queue 生成 + NAS 保存（常に実行）、Neo4j 投入は --skip-neo4j で制御
        _ingest_source_to_neo4j(
            source_articles_json, source, now, skip_ingest=args.skip_neo4j
        )

        # Optional cleanup (per-source directory)
        if args.cleanup_days is not None:
            logger.info("Running cleanup", source=source, max_age_days=args.cleanup_days)
            deleted = _cleanup_old_data(source_output_dir, args.cleanup_days)
            logger.info("Cleanup finished", source=source, deleted_directories=deleted)

    logger.info(
        "Scraper finished successfully",
        saved_files=saved_files,
        total_articles=len(df),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
