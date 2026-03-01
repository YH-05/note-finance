"""CNBC news collector for the news_scraper package.

This module collects financial news from CNBC's RSS feeds.
CNBC provides RSS feeds for various financial categories including
markets, investing, economy, and more.

Functions
---------
collect_news
    Collect recent news articles from CNBC RSS feeds.

Examples
--------
>>> from news_scraper.cnbc import collect_news
>>> from news_scraper.types import ScraperConfig
>>> config = ScraperConfig()
>>> articles = collect_news(config=config)
>>> len(articles) >= 0
True
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser

from news_scraper._logging import get_logger
from news_scraper.types import Article, ScraperConfig, deduplicate_by_url

logger = get_logger(__name__, module="cnbc")

# CNBC RSS feed URLs for financial news
CNBC_FEEDS: dict[str, str] = {
    "top_news": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "markets": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069",
    "economy": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
    "finance": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
    "earnings": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839135",
    "investing": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069",
}


def _parse_cnbc_date(date_str: str | None) -> datetime:
    """Parse a CNBC RSS date string to a UTC datetime.

    Parameters
    ----------
    date_str : str | None
        RFC 2822 date string from RSS feed, or None.

    Returns
    -------
    datetime
        Parsed datetime in UTC, or current UTC time if parsing fails.

    Examples
    --------
    >>> from news_scraper.cnbc import _parse_cnbc_date
    >>> dt = _parse_cnbc_date("Mon, 01 Mar 2026 12:00:00 GMT")
    >>> dt.year
    2026
    """
    if not date_str:
        return datetime.now(timezone.utc)
    try:
        dt = parsedate_to_datetime(date_str)
        # Ensure timezone-aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        logger.warning("Failed to parse CNBC date", date_str=date_str)
        return datetime.now(timezone.utc)


def _get_entry_field(entry: Any, *keys: str) -> str | None:
    """Extract a string field from a feedparser entry.

    Tries each key in order, returning the first non-empty string value found.

    Parameters
    ----------
    entry : Any
        Feedparser entry dict-like object.
    *keys : str
        Attribute/key names to try in order.

    Returns
    -------
    str | None
        First non-empty string value found, or None.
    """
    for key in keys:
        value = entry.get(key)
        if value and isinstance(value, str):
            return value
    return None


def _extract_tags(entry: Any) -> list[str]:
    """Extract tags/keywords from a feedparser entry.

    Parameters
    ----------
    entry : Any
        Feedparser entry dict-like object.

    Returns
    -------
    list[str]
        List of tag strings.
    """
    tags: list[str] = []
    tags_raw = entry.get("tags", [])
    if not isinstance(tags_raw, list):
        return tags
    for tag in tags_raw:
        if isinstance(tag, dict):
            term = tag.get("term")
            if term and isinstance(term, str):
                tags.append(term)
        elif isinstance(tag, str):
            tags.append(tag)
    return tags


def _extract_author(entry: Any) -> str | None:
    """Extract author name from a feedparser entry.

    Parameters
    ----------
    entry : Any
        Feedparser entry dict-like object.

    Returns
    -------
    str | None
        Author name, or None if not found.
    """
    author_detail = entry.get("author_detail")
    if isinstance(author_detail, dict):
        name = author_detail.get("name")
        if name and isinstance(name, str):
            return name.strip()
    author = entry.get("author")
    if author and isinstance(author, str):
        return author.strip()
    return None


def _entry_to_article(entry: Any, category: str) -> Article | None:
    """Convert a feedparser entry to an Article model.

    Parameters
    ----------
    entry : Any
        Feedparser entry dict-like object (feedparser.FeedParserDict).
    category : str
        Category name for the feed.

    Returns
    -------
    Article | None
        Parsed Article, or None if the entry is invalid.

    Examples
    --------
    >>> # Tested via integration with feedparser
    """
    title = _get_entry_field(entry, "title")
    url = _get_entry_field(entry, "link")

    if not title or not url:
        logger.debug("Skipping entry with missing title or URL", category=category)
        return None

    # Parse publication date
    pub_date_str = _get_entry_field(entry, "published", "updated")
    published = _parse_cnbc_date(pub_date_str)

    # Extract optional fields
    summary = _get_entry_field(entry, "summary", "description")
    author = _extract_author(entry)
    tags = _extract_tags(entry)

    return Article(
        title=title.strip(),
        url=url.strip(),
        published=published,
        source="cnbc",
        category=category,
        summary=summary.strip() if summary else None,
        author=author,
        tags=tags,
        metadata={"feed_category": category, "feed_source": "cnbc_rss"},
    )


def collect_news(
    config: ScraperConfig | None = None,
    categories: list[str] | None = None,
) -> list[Article]:
    """Collect recent news articles from CNBC RSS feeds.

    Fetches articles from CNBC's RSS feeds for the specified categories.
    If no categories are specified, fetches from all available feeds.

    Parameters
    ----------
    config : ScraperConfig | None, optional
        Scraper configuration. If None, uses default settings.
    categories : list[str] | None, optional
        List of CNBC categories to fetch. If None, fetches all.
        Valid values: "top_news", "markets", "economy", "finance",
        "earnings", "investing".

    Returns
    -------
    list[Article]
        List of collected articles, deduplicated by URL.

    Examples
    --------
    >>> from news_scraper.cnbc import collect_news
    >>> from news_scraper.types import ScraperConfig
    >>> config = ScraperConfig(max_articles_per_source=10)
    >>> # In tests, this is mocked to return empty list
    >>> articles = collect_news(config=config, categories=["markets"])
    >>> isinstance(articles, list)
    True
    """
    if config is None:
        config = ScraperConfig()

    feeds_to_fetch = categories if categories else list(CNBC_FEEDS.keys())
    max_per_source = config.max_articles_per_source

    logger.info(
        "Starting CNBC news collection",
        feeds=feeds_to_fetch,
        max_articles_per_source=max_per_source,
    )

    def _task(category: str) -> list[Article]:
        feed_url = CNBC_FEEDS.get(category)
        if not feed_url:
            logger.warning("Unknown CNBC category, skipping", category=category)
            return []
        logger.debug("Fetching CNBC feed", category=category, url=feed_url)
        try:
            feed = feedparser.parse(feed_url)
            if feed.bozo and not feed.entries:
                logger.warning(
                    "CNBC feed parse error",
                    category=category,
                    error=str(feed.bozo_exception)
                    if hasattr(feed, "bozo_exception")
                    else "unknown",
                )
                return []
            articles: list[Article] = []
            for entry in feed.entries:
                if len(articles) >= max_per_source:
                    break
                article = _entry_to_article(entry, category)
                if article is not None:
                    articles.append(article)
            logger.info("CNBC feed fetched", category=category, count=len(articles))
            return articles
        except Exception as e:
            logger.error(
                "Failed to fetch CNBC feed",
                category=category,
                error=str(e),
                exc_info=True,
            )
            return []

    all_articles: list[Article] = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        for result in executor.map(_task, feeds_to_fetch):
            all_articles.extend(result)

    deduplicated = deduplicate_by_url(all_articles)
    logger.info(
        "CNBC news collection complete",
        total_articles=len(deduplicated),
    )
    return deduplicated
