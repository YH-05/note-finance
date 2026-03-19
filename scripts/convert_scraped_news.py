#!/usr/bin/env python3
"""Convert scraped news JSON files to news_from_project.json compatible format.

Reads output JSON files from ``scrape_finance_news.py`` and converts them
into the format expected by ``wr-news-aggregator`` and the weekly report
pipeline, including category mapping, deduplication by URL, date range
filtering, and summary generation.

Usage
-----
Single file:

    $ uv run python scripts/convert_scraped_news.py \\
        --input /Volumes/personal_folder/scraped/cnbc/2026-03-01/news_120000.json \\
        --output articles/market_report/2026-03-01/data \\
        --start 2026-02-22 \\
        --end 2026-03-01

Directory (merge CNBC + NASDAQ):

    $ uv run python scripts/convert_scraped_news.py \\
        --input-dir /Volumes/personal_folder/scraped/cnbc/ \\
        --output articles/market_report/2026-03-01/data \\
        --start 2026-02-22 \\
        --end 2026-03-01

Notes
-----
- The output file is always named ``news_from_project.json`` in ``--output``.
- When ``--input-dir`` is used, all ``*.json`` files under the directory
  are merged and deduplicated by URL before filtering.
- Category mapping falls back to keyword detection when no category is
  present or the category key is not found in CATEGORY_MAP.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import structlog

from news_scraper._logging import get_logger

logger = get_logger(__name__, module="convert_scraped_news")

# ---------------------------------------------------------------------------
# Category mapping
# ---------------------------------------------------------------------------

# AIDEV-NOTE: Keys match the ``category`` field in scraped article JSON.
# Values are the standard categories used by the weekly report pipeline.
# Split by source to avoid key collisions (e.g. "Technology" vs "technology").
CNBC_CATEGORY_MAP: dict[str, str] = {
    "economy": "macro",
    "finance": "finance",
    "investing": "indices",
    "earnings": "mag7",
    "bonds": "macro",
    "commodities": "sectors",
    "technology": "tech",
    "energy": "sectors",
    "health_care": "sectors",
    "real_estate": "sectors",
    "autos": "sectors",
    "top_news": "indices",
    "business": "finance",
    "markets": "indices",
}

NASDAQ_CATEGORY_MAP: dict[str, str] = {
    "Markets": "indices",
    "Earnings": "mag7",
    "Economy": "macro",
    "Commodities": "sectors",
    "Currencies": "macro",
    "Technology": "tech",
    "Stocks": "mag7",
    "ETFs": "sectors",
}

# Keyword-based fallback mapping (applied to title + summary, case-insensitive)
KEYWORD_MAP: list[tuple[str, str]] = [
    # indices
    (r"S&P\s*500|Nasdaq|Dow Jones|Russell\s+\d+|stock market", "indices"),
    # mag7 (individual stocks and MAG7)
    (
        r"Apple|Microsoft|Google|Alphabet|Amazon|Meta|Nvidia|Tesla"
        r"|AAPL|MSFT|GOOGL|GOOG|AMZN|META|NVDA|TSLA",
        "mag7",
    ),
    # macro
    (
        r"Fed(?:eral Reserve)?|interest rate|inflation|GDP"
        r"|employment|unemployment|treasury|bond yield|CPI|PCE|FOMC",
        "macro",
    ),
    # sectors
    (
        r"sector|industry|energy|healthcare|financials|real estate|utility|materials",
        "sectors",
    ),
    # tech / AI
    (r"AI|artificial intelligence|machine learning|semiconductor|chip|GPU", "tech"),
    # finance (catch-all for financial topics)
    (r"bank|fund|ETF|hedge|portfolio|dividend|IPO|merger|acquisition|M&A", "finance"),
]

# Pre-compiled keyword patterns for performance (avoid re-compiling on every call)
_COMPILED_KEYWORD_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(pattern, re.IGNORECASE), cat) for pattern, cat in KEYWORD_MAP
]

# Valid output categories
VALID_CATEGORIES = {"indices", "mag7", "sectors", "macro", "tech", "finance", "other"}

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _map_category(category: str | None, title: str, summary: str | None) -> str:
    """Map a scraped article category to a weekly-report category.

    First attempts a direct lookup in ``CATEGORY_MAP``.  If the category is
    missing or unmapped, falls back to keyword detection on the article title
    and summary text.  Returns ``"other"`` when no match is found.

    Parameters
    ----------
    category : str | None
        Raw category string from the scraped JSON (may be ``None``).
    title : str
        Article title used for keyword fallback.
    summary : str | None
        Article summary used for keyword fallback (may be ``None``).

    Returns
    -------
    str
        One of: ``"indices"``, ``"mag7"``, ``"sectors"``, ``"macro"``,
        ``"tech"``, ``"finance"``, ``"other"``.

    Examples
    --------
    >>> _map_category("economy", "Fed raises rates", None)
    'macro'
    >>> _map_category(None, "S&P 500 reaches new record", None)
    'indices'
    >>> _map_category("unknown_key", "Random article", None)
    'other'
    """
    # Direct map lookup (CNBC first, then NASDAQ)
    if category is not None:
        mapped = CNBC_CATEGORY_MAP.get(category) or NASDAQ_CATEGORY_MAP.get(category)
        if mapped is not None:
            logger.debug(
                "Category mapped via CATEGORY_MAP", raw=category, mapped=mapped
            )
            return mapped

    # Keyword fallback on title + summary (pre-compiled patterns)
    text = title + " " + (summary or "")
    for pattern, cat in _COMPILED_KEYWORD_MAP:
        if pattern.search(text):
            logger.debug(
                "Category mapped via keywords", pattern=str(pattern.pattern), mapped=cat
            )
            return cat

    logger.debug("Category unmapped, defaulting to 'other'", raw=category, title=title)
    return "other"


def _parse_published(published_str: str | None) -> datetime | None:
    """Parse a published date string to a timezone-aware datetime object.

    Accepts ISO 8601 strings with or without timezone information.
    Returns ``None`` when the input is ``None`` or unparseable.

    Parameters
    ----------
    published_str : str | None
        ISO 8601 date/time string, or ``None``.

    Returns
    -------
    datetime | None
        Parsed UTC datetime, or ``None`` on failure.

    Examples
    --------
    >>> from datetime import datetime, timezone
    >>> _parse_published("2026-03-01T12:00:00+00:00")
    datetime.datetime(2026, 3, 1, 12, 0, tzinfo=datetime.timezone.utc)
    >>> _parse_published(None) is None
    True
    """
    if published_str is None:
        return None

    try:
        dt = datetime.fromisoformat(published_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError) as exc:
        logger.warning(
            "Failed to parse published date", raw=published_str, error=str(exc)
        )
        return None


def _is_in_period(dt: datetime | None, start: date, end: date) -> bool:
    """Return True when *dt* falls within [start, end] (inclusive).

    Parameters
    ----------
    dt : datetime | None
        Article publication datetime.  Articles without a date are excluded.
    start : date
        Period start (inclusive).
    end : date
        Period end (inclusive).

    Returns
    -------
    bool
        ``True`` if the article is within the period.
    """
    if dt is None:
        return False
    article_date = dt.date()
    return start <= article_date <= end


def _build_summary(article: dict) -> str:
    """Build a summary string for the output article.

    Uses the ``summary`` field when available and non-empty.
    Falls back to the first 200 characters of ``content``.
    Returns an empty string when both are absent.

    Parameters
    ----------
    article : dict
        Raw article dict from scraped JSON.

    Returns
    -------
    str
        Summary text (may be empty).
    """
    summary = article.get("summary") or ""
    if summary:
        return summary

    content = article.get("content") or ""
    if content:
        return content[:200]

    return ""


def _read_scraped_file(path: Path) -> list[dict]:
    """Read a single scraped JSON file and return its ``news`` list.

    Parameters
    ----------
    path : Path
        Path to the scraped JSON file.

    Returns
    -------
    list[dict]
        List of raw article dicts, or ``[]`` on error.

    Raises
    ------
    Does not raise; errors are logged and an empty list is returned.
    """
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Failed to read scraped file", path=str(path), error=str(exc))
        return []

    news = data.get("news", [])
    if not isinstance(news, list):
        logger.warning(
            "Unexpected 'news' type in file", path=str(path), type=type(news).__name__
        )
        return []

    logger.info("Read scraped file", path=str(path), article_count=len(news))
    return news


def _collect_raw_articles(
    input_file: Path | None,
    input_dir: Path | None,
) -> list[dict]:
    """Load raw articles from file(s), deduplicating by URL.

    Parameters
    ----------
    input_file : Path | None
        Single input JSON file path (mutually exclusive with *input_dir*).
    input_dir : Path | None
        Directory to search recursively for ``*.json`` files.

    Returns
    -------
    list[dict]
        Deduplicated list of raw article dicts.

    Raises
    ------
    ValueError
        If neither *input_file* nor *input_dir* is provided.
    """
    if input_file is None and input_dir is None:
        raise ValueError("Either --input or --input-dir must be provided")

    raw_articles: list[dict] = []

    if input_file is not None:
        raw_articles.extend(_read_scraped_file(input_file))
    else:
        assert input_dir is not None  # guaranteed by caller
        json_files = sorted(input_dir.rglob("*.json"))
        if not json_files:
            logger.warning("No JSON files found in directory", path=str(input_dir))
        for json_file in json_files:
            raw_articles.extend(_read_scraped_file(json_file))

    # Deduplicate by URL (preserve insertion order)
    seen_urls: set[str] = set()
    unique_articles: list[dict] = []
    for article in raw_articles:
        url = article.get("url", "")
        if not url:
            continue  # skip articles without URL
        if url not in seen_urls:
            seen_urls.add(url)
            unique_articles.append(article)

    logger.info(
        "Deduplication complete",
        raw_count=len(raw_articles),
        unique_count=len(unique_articles),
    )
    return unique_articles


def _convert_article(article: dict, issue_number: int) -> dict:
    """Convert a raw scraped article dict to the news_from_project.json format.

    Parameters
    ----------
    article : dict
        Raw article dict from the scraped JSON file.
    issue_number : int
        Sequential issue number to assign to the article.

    Returns
    -------
    dict
        Article dict in ``news_from_project.json`` format.
    """
    title = article.get("title", "")
    url = article.get("url", "")
    source = article.get("source", "")
    raw_category = article.get("category")
    summary = _build_summary(article)
    published_str = article.get("published")
    published_dt = _parse_published(published_str)
    created_at = published_dt.isoformat() if published_dt else (published_str or "")
    category = _map_category(raw_category, title, summary)

    return {
        "issue_number": issue_number,
        "title": title,
        "category": category,
        "url": url,
        "original_url": url,
        "created_at": created_at,
        "summary": summary,
        "source": source,
    }


def _build_by_category(news: list[dict]) -> dict[str, list[dict]]:
    """Group news articles by category.

    Parameters
    ----------
    news : list[dict]
        Converted article dicts with a ``"category"`` key.

    Returns
    -------
    dict[str, list[dict]]
        Mapping of category name to list of articles.  All valid categories
        are present as keys (even if empty).
    """
    by_category: dict[str, list[dict]] = {cat: [] for cat in VALID_CATEGORIES}
    for article in news:
        cat = article.get("category", "other")
        if cat not in by_category:
            cat = "other"
        by_category[cat].append(article)
    return by_category


def _build_statistics(by_category: dict[str, list[dict]]) -> dict[str, int]:
    """Build statistics dict from by_category mapping.

    Parameters
    ----------
    by_category : dict[str, list[dict]]
        Mapping of category to articles.

    Returns
    -------
    dict[str, int]
        Mapping of category to article count.
    """
    return {cat: len(articles) for cat, articles in by_category.items()}


def convert(
    *,
    input_file: Path | None,
    input_dir: Path | None,
    output_dir: Path,
    start: date,
    end: date,
) -> Path:
    """Convert scraped news files to news_from_project.json format.

    Parameters
    ----------
    input_file : Path | None
        Single input JSON file.
    input_dir : Path | None
        Directory containing multiple JSON files to merge.
    output_dir : Path
        Directory where ``news_from_project.json`` will be written.
    start : date
        Inclusive start date for filtering articles.
    end : date
        Inclusive end date for filtering articles.

    Returns
    -------
    Path
        Path to the created ``news_from_project.json`` file.

    Raises
    ------
    ValueError
        If neither *input_file* nor *input_dir* is provided.
    OSError
        If the output file cannot be written.
    """
    logger.info(
        "Starting conversion",
        input_file=str(input_file) if input_file else None,
        input_dir=str(input_dir) if input_dir else None,
        output_dir=str(output_dir),
        start=str(start),
        end=str(end),
    )

    # Load and deduplicate raw articles
    raw_articles = _collect_raw_articles(input_file, input_dir)
    logger.info("Collected raw articles", count=len(raw_articles))

    # Filter by date range
    filtered: list[dict] = []
    for article in raw_articles:
        published_str = article.get("published")
        dt = _parse_published(published_str)
        if _is_in_period(dt, start, end):
            filtered.append(article)

    logger.info(
        "Filtered by date range",
        before=len(raw_articles),
        after=len(filtered),
        start=str(start),
        end=str(end),
    )

    # Convert articles and assign sequential issue numbers
    news: list[dict] = []
    for idx, article in enumerate(filtered, start=1):
        converted = _convert_article(article, issue_number=idx)
        news.append(converted)
        logger.debug(
            "Converted article",
            issue_number=idx,
            title=converted["title"],
            category=converted["category"],
        )

    # Build by_category and statistics
    by_category = _build_by_category(news)
    statistics = _build_statistics(by_category)

    # Build output payload
    output_payload: dict = {
        "period": {
            "start": str(start),
            "end": str(end),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_count": len(news),
        "news": news,
        "by_category": by_category,
        "statistics": statistics,
    }

    # Write output
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "news_from_project.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output_payload, f, ensure_ascii=False, indent=2)

    logger.info(
        "Conversion complete",
        output_path=str(output_path),
        total_articles=len(news),
        by_category={cat: len(items) for cat, items in by_category.items()},
    )

    return output_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _validate_input_paths(args: argparse.Namespace) -> str | None:
    """Validate that the input file or directory exists.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments.

    Returns
    -------
    str | None
        Human-readable error message if validation fails, else ``None``.
    """
    if args.input is not None and not args.input.exists():
        return f"入力ファイルが見つかりません: {args.input}"
    if args.input_dir is not None and not args.input_dir.exists():
        return f"入力ディレクトリが見つかりません: {args.input_dir}"
    return None


def _parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns
    -------
    argparse.Namespace
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Convert scraped news JSON to news_from_project.json format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python scripts/convert_scraped_news.py \\
      --input /Volumes/personal_folder/scraped/cnbc/2026-03-01/news_120000.json \\
      --output articles/market_report/2026-03-01/data \\
      --start 2026-02-22 \\
      --end 2026-03-01

  uv run python scripts/convert_scraped_news.py \\
      --input-dir /Volumes/personal_folder/scraped/cnbc/ \\
      --output articles/market_report/2026-03-01/data \\
      --start 2026-02-22 \\
      --end 2026-03-01
        """,
    )

    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--input",
        type=Path,
        metavar="FILE",
        help="Path to a single scraped JSON file",
    )
    source_group.add_argument(
        "--input-dir",
        type=Path,
        metavar="DIR",
        help="Directory containing scraped JSON files (searched recursively)",
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        metavar="DIR",
        help="Output directory for news_from_project.json",
    )
    parser.add_argument(
        "--start",
        required=True,
        metavar="YYYY-MM-DD",
        help="Start date (inclusive) for filtering articles",
    )
    parser.add_argument(
        "--end",
        required=True,
        metavar="YYYY-MM-DD",
        help="End date (inclusive) for filtering articles",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Log level (default: INFO)",
    )

    return parser.parse_args()


def main() -> int:
    """Run the conversion script.

    Returns
    -------
    int
        Exit code: 0 for success, 1 for failure.
    """
    args = _parse_args()

    # Configure logging
    import logging

    logging.basicConfig(level=getattr(logging, args.log_level, logging.INFO))
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, args.log_level, logging.INFO)
        ),
    )

    # Parse dates
    try:
        start = date.fromisoformat(args.start)
        end = date.fromisoformat(args.end)
    except ValueError as exc:
        logger.error("Invalid date format", error=str(exc))
        print(
            f"エラー: 日付は YYYY-MM-DD 形式で指定してください ({exc})", file=sys.stderr
        )
        return 1

    if start > end:
        print(
            f"エラー: --start ({args.start}) は --end ({args.end}) 以前の日付にしてください",
            file=sys.stderr,
        )
        return 1

    # Validate input paths
    path_error = _validate_input_paths(args)
    if path_error is not None:
        print(f"エラー: {path_error}", file=sys.stderr)
        return 1

    try:
        output_path = convert(
            input_file=args.input,
            input_dir=args.input_dir,
            output_dir=args.output,
            start=start,
            end=end,
        )
    except ValueError as exc:
        logger.error("Conversion validation error", error=str(exc))
        print(f"エラー: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        logger.error("Conversion IO error", error=str(exc))
        print(f"エラー: ファイル書き込みに失敗しました: {exc}", file=sys.stderr)
        return 1

    # Print human-readable summary to stdout
    data = json.loads(output_path.read_text(encoding="utf-8"))
    stat_parts = ", ".join(
        f"{cat}={count}" for cat, count in data["statistics"].items() if count > 0
    )
    print(f"変換完了: {data['total_count']} 件 → {output_path}")
    print(f"カテゴリ別: {stat_parts or '(なし)'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
