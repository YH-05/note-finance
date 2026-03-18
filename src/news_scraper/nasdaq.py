"""NASDAQ news collector for the news_scraper package.

This module collects financial news from NASDAQ's API.
NASDAQ provides a JSON API for fetching news articles by category.

Functions
---------
collect_news
    Collect recent news articles from the NASDAQ API.

Notes
-----
The NASDAQ API endpoint used in this module is:
    https://api.nasdaq.com/api/news/category?category={category}&limit={limit}

More advanced functionality (pagination, historical data, Playwright scraping)
is implemented in subsequent waves (Issues #3687-#3691).

Examples
--------
>>> from news_scraper.nasdaq import collect_news
>>> from news_scraper.types import ScraperConfig
>>> config = ScraperConfig()
>>> articles = collect_news(config=config)
>>> isinstance(articles, list)
True
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx

from news_scraper._logging import get_logger
from news_scraper.types import Article, ScraperConfig, deduplicate_by_url

logger = get_logger(__name__, module="nasdaq")

# NASDAQ API base URL
NASDAQ_API_BASE = "https://api.nasdaq.com/api/news"

# NASDAQ news categories available via API
NASDAQ_API_CATEGORIES: list[str] = [
    "Markets",
    "Earnings",
    "Economy",
    "Commodities",
    "Currencies",
    "Technology",
    "Stocks",
    "ETFs",
]

# Frozenset for O(1) whitelist check in _fetch_category
NASDAQ_API_CATEGORIES_SET: frozenset[str] = frozenset(NASDAQ_API_CATEGORIES)

# Default HTTP headers to mimic a browser request
DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nasdaq.com/",
    "Origin": "https://www.nasdaq.com",
}


def _parse_nasdaq_date(date_str: str | None) -> datetime:
    """Parse a NASDAQ API date string to a UTC datetime.

    Parameters
    ----------
    date_str : str | None
        Date string from the NASDAQ API (ISO 8601 or similar format).

    Returns
    -------
    datetime
        Parsed datetime in UTC, or current UTC time if parsing fails.

    Examples
    --------
    >>> dt = _parse_nasdaq_date("2026-03-01T12:00:00.000Z")
    >>> dt.year
    2026
    >>> dt.tzinfo is not None
    True
    """
    if not date_str:
        return datetime.now(timezone.utc)
    # Normalize milliseconds suffix
    normalized = date_str.rstrip("Z").split(".")[0]
    for fmt in [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%m/%d/%Y",
    ]:
        try:
            dt = datetime.strptime(normalized, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    logger.warning("Failed to parse NASDAQ date", date_str=date_str)
    return datetime.now(timezone.utc)


def _row_to_article(row: dict, category: str) -> Article | None:
    """Convert a NASDAQ API response row to an Article model.

    Parameters
    ----------
    row : dict
        A single news row from the NASDAQ API response.
    category : str
        Category name for the article.

    Returns
    -------
    Article | None
        Parsed Article, or None if the row is invalid.

    Examples
    --------
    >>> # Tested via unit tests with mock data
    """
    title = row.get("title") or row.get("headline")
    url = row.get("url") or row.get("link")

    if not title or not url:
        logger.debug("Skipping NASDAQ row with missing title or URL", category=category)
        return None

    # Ensure absolute URL
    if url.startswith("/"):
        url = f"https://www.nasdaq.com{url}"

    # Parse date
    date_str = row.get("date") or row.get("publishedAt") or row.get("created")
    published = _parse_nasdaq_date(date_str)

    # Extract summary
    summary = row.get("summary") or row.get("description") or row.get("body")
    if summary and len(summary) > 500:
        summary = summary[:497] + "..."

    return Article(
        title=title.strip(),
        url=url.strip(),
        published=published,
        source="nasdaq",
        category=category,
        summary=summary.strip() if summary else None,
        tags=[],
        metadata={
            "feed_category": category,
            "feed_source": "nasdaq_api",
        },
    )


def _extract_rows_from_response(data: dict) -> list[dict]:
    """Extract article rows from a NASDAQ API response payload.

    Handles multiple response shapes: data.data.rows, data.data, data.rows,
    and data.news.

    Parameters
    ----------
    data : dict
        Parsed JSON response from the NASDAQ API.

    Returns
    -------
    list[dict]
        List of raw article rows (may be empty).

    Examples
    --------
    >>> _extract_rows_from_response({"data": {"rows": [{"title": "T"}]}})
    [{'title': 'T'}]
    """
    api_data = data.get("data", {})
    if isinstance(api_data, dict):
        rows_raw = api_data.get("rows", api_data.get("data", []))
        if isinstance(rows_raw, list):
            return rows_raw
    if isinstance(api_data, list):
        return api_data
    # Fall back to top-level keys
    top_rows = data.get("rows", data.get("news", []))
    if isinstance(top_rows, list):
        return top_rows
    return []


async def _fetch_category_async(
    client: httpx.AsyncClient,
    category: str,
    max_per_source: int,
) -> list[Article]:
    """Fetch articles for a single NASDAQ category asynchronously.

    Parameters
    ----------
    client : httpx.AsyncClient
        Async HTTP client to use for requests.
    category : str
        NASDAQ category name.
    max_per_source : int
        Maximum number of articles to return.

    Returns
    -------
    list[Article]
        List of articles for the category (may be empty on error).
    """
    if category not in NASDAQ_API_CATEGORIES_SET:
        logger.warning("Invalid NASDAQ category, skipping", category=category)
        return []

    params = {"category": category, "limit": max_per_source}
    url = f"{NASDAQ_API_BASE}/category"
    logger.debug("Fetching NASDAQ category (async)", category=category, url=url)

    try:
        response = await client.get(url, params=params)
        response.raise_for_status()
        rows = _extract_rows_from_response(response.json())
        articles = []
        for row in rows:
            if len(articles) >= max_per_source:
                break
            if not isinstance(row, dict):
                continue
            article = _row_to_article(row, category)
            if article is not None:
                articles.append(article)
        logger.info("NASDAQ category fetched", category=category, count=len(articles))
        return articles

    except httpx.HTTPStatusError as e:
        logger.error(
            "NASDAQ API HTTP error",
            category=category,
            status_code=e.response.status_code,
            error=str(e),
        )
    except httpx.RequestError as e:
        logger.error(
            "NASDAQ API request failed",
            category=category,
            error=str(e),
            exc_info=True,
        )
    except Exception as e:
        logger.error(
            "Unexpected error fetching NASDAQ news",
            category=category,
            error=str(e),
            exc_info=True,
        )
    return []


async def collect_news(
    config: ScraperConfig | None = None,
    categories: list[str] | None = None,
) -> list[Article]:
    """Collect recent news articles from the NASDAQ API.

    Fetches articles from NASDAQ's JSON API for the specified categories
    in parallel using ``asyncio.gather``.
    If no categories are specified, fetches from all available API categories.

    Parameters
    ----------
    config : ScraperConfig | None, optional
        Scraper configuration. If None, uses default settings.
    categories : list[str] | None, optional
        List of NASDAQ categories to fetch. If None, fetches all.
        Valid values: "Markets", "Earnings", "Economy", "Commodities",
        "Currencies", "Technology", "Stocks", "ETFs".

    Returns
    -------
    list[Article]
        List of collected articles, deduplicated by URL.

    Examples
    --------
    >>> from news_scraper.nasdaq import collect_news
    >>> from news_scraper.types import ScraperConfig
    >>> import asyncio
    >>> config = ScraperConfig(max_articles_per_source=5)
    >>> # In tests, HTTP calls are mocked
    >>> articles = asyncio.run(collect_news(config=config))
    >>> isinstance(articles, list)
    True
    """
    if config is None:
        config = ScraperConfig()

    categories_to_fetch = categories if categories else NASDAQ_API_CATEGORIES
    max_per_source = config.max_articles_per_source

    logger.info(
        "Starting NASDAQ news collection (async)",
        categories=categories_to_fetch,
        max_articles_per_source=max_per_source,
    )

    all_articles: list[Article] = []

    async with httpx.AsyncClient(
        timeout=config.request_timeout,
        headers=DEFAULT_HEADERS,
        follow_redirects=True,
    ) as client:
        tasks = [
            _fetch_category_async(client, cat, max_per_source)
            for cat in categories_to_fetch
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.error("NASDAQ category task failed", error=str(result))
            elif isinstance(result, list):
                all_articles.extend(result)

    deduplicated = deduplicate_by_url(all_articles)
    logger.info(
        "NASDAQ news collection complete",
        total_articles=len(deduplicated),
    )
    return deduplicated
