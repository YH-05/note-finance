#!/usr/bin/env python3
"""Dedup and stage scraped RSS JSON files for Neo4j ingestion.

Reads raw scraped JSON files from NAS, deduplicates articles by URL across
all sources and runs, filters out already-ingested URLs via a JSONL registry,
then writes a deduplicated batch to .tmp/ for downstream emit_research_queue.py.

Stages
------
1. For each source: load unprocessed JSON files (skip processed/ subdirs)
2. Dedup by URL within source (keep oldest entry by fetched_at)
3. Cross-source dedup via JSONL registry (skip already-ingested URLs)
4. Move all scanned files to {source}/processed/{date}/ (even if 0 new articles)
5. Append new URL entries to registry JSONL
6. Write .tmp/deduped-all-{ts}.json in finance-news-workflow format

Usage
-----
::

    # Run dedup (dry-run to preview without moving files)
    uv run python scripts/dedup_scraped.py --dry-run

    # Run dedup and emit/ingest (full pipeline Stage 2-4)
    uv run python scripts/dedup_scraped.py

    # Override NAS base directory
    uv run python scripts/dedup_scraped.py --scraped-base /path/to/scraped

Notes
-----
- Registry: ``{scraped_base}/_registry/processed_urls.jsonl``
- Processed: ``{scraped_base}/{source}/processed/{date}/``
- Output: ``.tmp/deduped-all-{ts}.json``
- ``NAS_SCRAPED_BASE`` env var overrides default NAS path
"""

from __future__ import annotations

import sys
from pathlib import Path

# AIDEV-NOTE: src/ を Python パスに追加（パッケージ衝突の保険）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import argparse
import json
import os
import secrets
import shutil
from datetime import datetime, timezone
from typing import Any

from news_scraper._logging import get_logger

logger = get_logger(__name__, module="dedup_scraped")

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

NAS_SCRAPED_BASE = Path(
    os.environ.get("NAS_SCRAPED_BASE", "/Volumes/personal_folder/scraped")
)
REGISTRY_SUBDIR = "_registry"
REGISTRY_FILENAME = "processed_urls.jsonl"
PROCESSED_SUBDIR = "processed"
TMP_DIR = Path(".tmp")

# 対象ソース（scrape_finance_news.py の全11ソース）
SOURCES: list[str] = [
    "ars_technica",
    "cnbc",
    "developing_telecoms",
    "federal_reserve",
    "hacker_news",
    "jetro",
    "kabutan",
    "reuters_jp",
    "techcrunch",
    "the_verge",
    "zero_hedge",
]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def _load_registry(registry_path: Path) -> set[str]:
    """Load already-ingested URLs from JSONL registry.

    Parameters
    ----------
    registry_path : Path
        Path to the processed_urls.jsonl file.

    Returns
    -------
    set[str]
        Set of already-ingested URLs.
    """
    if not registry_path.exists():
        logger.debug("Registry does not exist yet", path=str(registry_path))
        return set()

    urls: set[str] = set()
    with registry_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                url = entry.get("url")
                if url:
                    urls.add(url)
            except json.JSONDecodeError:
                logger.warning("Skipping malformed registry line", line=line[:80])
    logger.info("Registry loaded", url_count=len(urls), path=str(registry_path))
    return urls


def _append_to_registry(
    registry_path: Path,
    new_articles: list[dict[str, Any]],
    dry_run: bool,
) -> None:
    """Append new article URLs to the JSONL registry.

    Parameters
    ----------
    registry_path : Path
        Path to the processed_urls.jsonl file.
    new_articles : list[dict[str, Any]]
        New articles to register (must have ``url`` and ``source`` keys).
    dry_run : bool
        If True, skip writing.
    """
    if not new_articles or dry_run:
        return

    registry_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()

    with registry_path.open("a", encoding="utf-8") as f:
        for article in new_articles:
            entry = {
                "url": article["url"],
                "ingested_at": now,
                "source": article.get("source", ""),
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    logger.info("Registry updated", added=len(new_articles))


# ---------------------------------------------------------------------------
# File operations
# ---------------------------------------------------------------------------

def _find_unprocessed_files(source_dir: Path) -> list[Path]:
    """Find unprocessed scraped JSON files for a source.

    Scans all date subdirectories under ``source_dir``, skipping any
    ``processed/`` subdirectory.

    Parameters
    ----------
    source_dir : Path
        Source directory, e.g. ``scraped/cnbc/``.

    Returns
    -------
    list[Path]
        Sorted list of unprocessed JSON file paths.
    """
    files: list[Path] = []
    if not source_dir.exists():
        return files

    for date_dir in sorted(source_dir.iterdir()):
        if not date_dir.is_dir():
            continue
        if date_dir.name == PROCESSED_SUBDIR or date_dir.name.startswith("_"):
            continue
        # Validate YYYY-MM-DD format
        try:
            datetime.strptime(date_dir.name, "%Y-%m-%d")
        except ValueError:
            logger.debug("Skipping non-dated directory", name=date_dir.name)
            continue

        for json_file in sorted(date_dir.glob("*.json")):
            files.append(json_file)

    return files


def _load_articles(files: list[Path]) -> list[dict[str, Any]]:
    """Load articles from a list of scraped JSON files.

    Parameters
    ----------
    files : list[Path]
        List of scraped JSON file paths.

    Returns
    -------
    list[dict[str, Any]]
        Flat list of article dicts with ``_source_file`` metadata added.
    """
    articles: list[dict[str, Any]] = []
    for file_path in files:
        try:
            with file_path.open(encoding="utf-8") as f:
                data = json.load(f)
            news = data.get("news", [])
            for article in news:
                article["_source_file"] = str(file_path)
            articles.extend(news)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load file", path=str(file_path), error=str(e))
    return articles


def _dedup_by_url(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate articles by URL, keeping the oldest entry (by fetched_at).

    Parameters
    ----------
    articles : list[dict[str, Any]]
        Raw articles from one or more scraped JSON files.

    Returns
    -------
    list[dict[str, Any]]
        Deduplicated articles, one per URL.
    """
    seen: dict[str, dict[str, Any]] = {}
    for article in articles:
        url = article.get("url")
        if not url:
            continue
        if url not in seen:
            seen[url] = article
        else:
            # Keep oldest (smallest fetched_at)
            existing_ts = seen[url].get("fetched_at", "")
            new_ts = article.get("fetched_at", "")
            if new_ts and new_ts < existing_ts:
                seen[url] = article
    return list(seen.values())


def _move_to_processed(
    files: list[Path],
    source_dir: Path,
    dry_run: bool,
) -> None:
    """Move scanned files to processed/ subdirectory.

    Preserves the date subdirectory structure:
    ``{source}/processed/{date}/news_*.json``

    Parameters
    ----------
    files : list[Path]
        Files to move.
    source_dir : Path
        Source root directory (e.g. ``scraped/cnbc/``).
    dry_run : bool
        If True, log but do not move.
    """
    for file_path in files:
        # file_path: scraped/{source}/{date}/news_*.json
        date_name = file_path.parent.name
        dest_dir = source_dir / PROCESSED_SUBDIR / date_name
        dest = dest_dir / file_path.name

        if dry_run:
            logger.info("[DRY-RUN] Would move", src=str(file_path), dest=str(dest))
            continue

        dest_dir.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(file_path), str(dest))
            logger.debug("Moved to processed", src=str(file_path), dest=str(dest))
        except OSError as e:
            logger.error("Failed to move file", src=str(file_path), error=str(e))


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _to_finance_news_format(article: dict[str, Any]) -> dict[str, Any]:
    """Convert scraped article dict to finance-news-workflow article format.

    Parameters
    ----------
    article : dict[str, Any]
        Raw scraped article.

    Returns
    -------
    dict[str, Any]
        Article in finance-news-workflow format.
    """
    return {
        "url": article.get("url", ""),
        "title": article.get("title", ""),
        "summary": article.get("summary") or "",
        "feed_source": article.get("source", ""),
        "published": article.get("published", ""),
    }


def _write_output(articles: list[dict[str, Any]], dry_run: bool) -> Path | None:
    """Write deduplicated articles to .tmp/deduped-all-{ts}.json.

    Parameters
    ----------
    articles : list[dict[str, Any]]
        New articles to write.
    dry_run : bool
        If True, log but do not write.

    Returns
    -------
    Path | None
        Path to the written file, or None if dry-run or empty.
    """
    if not articles:
        logger.info("No new articles, skipping output")
        return None

    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    suffix = secrets.token_hex(4)
    output_path = TMP_DIR / f"deduped-all-{ts}-{suffix}.json"

    payload = {
        "articles": [_to_finance_news_format(a) for a in articles],
        "session_id": f"dedup-{ts}-{suffix}",
        "batch_label": "rss-scrape",
    }

    if dry_run:
        logger.info(
            "[DRY-RUN] Would write output",
            path=str(output_path),
            article_count=len(articles),
        )
        return None

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    logger.info("Output written", path=str(output_path), article_count=len(articles))
    return output_path


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def run_dedup(
    scraped_base: Path,
    sources: list[str],
    dry_run: bool,
) -> Path | None:
    """Run the full dedup pipeline.

    Parameters
    ----------
    scraped_base : Path
        NAS scraped base directory.
    sources : list[str]
        Source names to process.
    dry_run : bool
        If True, do not move files, update registry, or write output.

    Returns
    -------
    Path | None
        Path to the output .tmp file, or None if no new articles.
    """
    registry_path = scraped_base / REGISTRY_SUBDIR / REGISTRY_FILENAME
    ingested_urls = _load_registry(registry_path)

    all_new_articles: list[dict[str, Any]] = []

    for source in sources:
        source_dir = scraped_base / source
        unprocessed = _find_unprocessed_files(source_dir)

        if not unprocessed:
            logger.debug("No unprocessed files", source=source)
            continue

        logger.info(
            "Processing source",
            source=source,
            file_count=len(unprocessed),
        )

        # Load + dedup within source
        raw_articles = _load_articles(unprocessed)
        deduped = _dedup_by_url(raw_articles)

        # Filter already-ingested URLs
        new_articles = [a for a in deduped if a.get("url") not in ingested_urls]

        logger.info(
            "Source dedup complete",
            source=source,
            raw=len(raw_articles),
            after_url_dedup=len(deduped),
            new=len(new_articles),
        )

        # Move all files to processed/ (even if 0 new articles)
        _move_to_processed(unprocessed, source_dir, dry_run)

        # Register new URLs in memory (for cross-source dedup within this run)
        for a in new_articles:
            if a.get("url"):
                ingested_urls.add(a["url"])

        all_new_articles.extend(new_articles)

    logger.info("All sources processed", total_new=len(all_new_articles))

    # Persist new URLs to registry
    _append_to_registry(registry_path, all_new_articles, dry_run)

    # Write output
    return _write_output(all_new_articles, dry_run)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dedup scraped RSS JSONs and stage for Neo4j ingestion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python scripts/dedup_scraped.py --dry-run
  uv run python scripts/dedup_scraped.py
  uv run python scripts/dedup_scraped.py --sources cnbc jetro --dry-run
        """,
    )
    parser.add_argument(
        "--scraped-base",
        type=Path,
        default=NAS_SCRAPED_BASE,
        help=f"NAS scraped base directory (default: {NAS_SCRAPED_BASE})",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        default=SOURCES,
        metavar="SOURCE",
        help="Sources to process (default: all 11 sources)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview without moving files, updating registry, or writing output",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Log level (default: INFO)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    import logging
    logging.getLogger().setLevel(getattr(logging, args.log_level, logging.INFO))

    logger.info(
        "dedup_scraped starting",
        scraped_base=str(args.scraped_base),
        sources=args.sources,
        dry_run=args.dry_run,
    )

    output_path = run_dedup(
        scraped_base=args.scraped_base,
        sources=args.sources,
        dry_run=args.dry_run,
    )

    if output_path:
        logger.info("Done. Next step: emit_research_queue.py", output=str(output_path))
        print(str(output_path))  # stdout で後続スクリプトがパスを受け取れるように
    elif args.dry_run:
        logger.info("Done. (dry-run: no files written)")
    else:
        logger.info("Done. No new articles to ingest.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
