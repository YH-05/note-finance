"""Common RSS fetcher and parser for the news_scraper package.

Shared utilities for fetching and parsing RSS feeds used by all Wave 2+
source modules (CNBC, Ars Technica, ZeroHedge, The Verge, etc.).

Examples
--------
>>> import asyncio
>>> from news_scraper._rss_fetcher import fetch_rss_feeds
>>> from news_scraper.types import ScraperConfig
>>> feeds = {"markets": "https://example.com/rss"}
>>> config = ScraperConfig()
>>> articles = asyncio.run(fetch_rss_feeds(feeds, config, "test_source"))
>>> isinstance(articles, list)
True
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
from lxml import html as lxml_html

from news_scraper._logging import get_logger
from news_scraper.types import Article, ScraperConfig, deduplicate_by_url

logger = get_logger(__name__, module="rss_fetcher")

# Minimum content length (chars) to accept entry.content[0].value
_MIN_CONTENT_LEN = 100


def _parse_rss_date(date_str: str | None) -> datetime:
    """Parse an RSS date string (RFC 2822 or ISO 8601) to a UTC datetime.

    Parameters
    ----------
    date_str : str | None
        Date string from an RSS entry, or None.

    Returns
    -------
    datetime
        Parsed datetime in UTC, or current UTC time on failure.

    Examples
    --------
    >>> dt = _parse_rss_date("Mon, 01 Mar 2026 12:00:00 GMT")
    >>> dt.year
    2026
    """
    if not date_str:
        return datetime.now(timezone.utc)
    for parser in (parsedate_to_datetime, datetime.fromisoformat):
        try:
            dt = parser(date_str)  # type: ignore[operator]
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue
    logger.warning("Failed to parse RSS date", date_str=date_str)
    return datetime.now(timezone.utc)


def _get_entry_field(entry: Any, *keys: str) -> str | None:
    """Return the first non-empty string from the given feedparser entry keys."""
    for key in keys:
        value = entry.get(key)
        if value and isinstance(value, str):
            return value
    return None


def _extract_tags(entry: Any) -> list[str]:
    """Extract tags/keywords from a feedparser entry."""
    tags_raw = entry.get("tags", [])
    if not isinstance(tags_raw, list):
        return []
    result: list[str] = []
    for tag in tags_raw:
        if isinstance(tag, dict):
            term = tag.get("term")
            if term and isinstance(term, str):
                result.append(term)
        elif isinstance(tag, str):
            result.append(tag)
    return result


def _extract_author(entry: Any) -> str | None:
    """Extract author name from a feedparser entry (prefers author_detail.name)."""
    author_detail = entry.get("author_detail")
    if isinstance(author_detail, dict):
        name = author_detail.get("name")
        if name and isinstance(name, str):
            return name.strip()
    author = entry.get("author")
    if author and isinstance(author, str):
        return author.strip()
    return None


def _html_to_text(html_str: str) -> str:
    """Convert an HTML string to plain text using lxml.

    Parameters
    ----------
    html_str : str
        Raw HTML string.

    Returns
    -------
    str
        Plain text with normalised whitespace, or empty string on failure.

    Examples
    --------
    >>> result = _html_to_text("<p>Hello <b>world</b>!</p>")
    >>> "Hello" in result and "<b>" not in result
    True
    """
    if not html_str:
        return ""
    try:
        tree = lxml_html.fromstring(html_str)
    except Exception:
        logger.debug("Failed to parse HTML with lxml")
        return ""
    for el in tree.xpath("//script | //style | //noscript"):
        parent = el.getparent()
        if parent is not None:
            parent.remove(el)
    lines = tree.text_content().splitlines()
    return "\n".join(line.strip() for line in lines if line.strip())


def _extract_content(
    entry: Any,
    content_field: str,
    *,
    content_is_html: bool,
) -> str | None:
    """Extract article content from a feedparser entry.

    Parameters
    ----------
    entry : Any
        Feedparser entry dict-like object.
    content_field : str
        One of ``"entry.summary"`` or ``"entry.content[0].value"``.
    content_is_html : bool
        When True, strip HTML tags from the extracted value.

    Returns
    -------
    str | None
        Extracted text, or None if not available / too short.

    Examples
    --------
    >>> from unittest.mock import MagicMock
    >>> entry = MagicMock()
    >>> entry.get = {"summary": "Short summary"}.get
    >>> _extract_content(entry, "entry.summary", content_is_html=False)
    'Short summary'
    """
    raw = _get_raw_field(entry, content_field)
    if raw is None:
        return None
    return _html_to_text(raw) or None if content_is_html else raw


def _get_raw_field(entry: Any, content_field: str) -> str | None:
    """Return the raw string for the given content_field selector, or None."""
    if content_field == "entry.summary":
        raw = entry.get("summary")
        return raw if raw and isinstance(raw, str) else None

    if content_field != "entry.content[0].value":
        logger.warning("Unknown content_field value", content_field=content_field)
        return None

    # entry.content[0].value branch
    content_list = entry.get("content")
    first = content_list[0] if isinstance(content_list, list) and content_list else None
    raw = first.get("value") if isinstance(first, dict) else None
    if not raw or not isinstance(raw, str):
        return None
    if len(raw) < _MIN_CONTENT_LEN:
        logger.debug(
            "entry.content[0].value too short",
            length=len(raw),
            threshold=_MIN_CONTENT_LEN,
        )
        return None
    return raw


def _entry_to_article(
    entry: Any,
    *,
    category: str,
    source_name: str,
    content_field: str,
    content_is_html: bool,
) -> Article | None:
    """Convert a feedparser entry to an Article, returning None for invalid entries."""
    title = _get_entry_field(entry, "title")
    url = _get_entry_field(entry, "link")
    if not title or not url:
        logger.debug("Skipping entry: missing title or URL", source=source_name)
        return None
    pub_date_str = _get_entry_field(entry, "published", "updated")
    return Article(
        title=title.strip(),
        url=url.strip(),
        published=_parse_rss_date(pub_date_str),
        source=source_name,
        category=category,
        summary=(
            s.strip()
            if (s := _get_entry_field(entry, "summary", "description"))
            else None
        ),
        content=_extract_content(entry, content_field, content_is_html=content_is_html),
        author=_extract_author(entry),
        tags=_extract_tags(entry),
        metadata={"feed_category": category, "feed_source": f"{source_name}_rss"},
    )


async def fetch_rss_feeds(
    feeds: dict[str, str],
    config: ScraperConfig,
    source_name: str,
    content_field: str = "entry.summary",
    content_is_html: bool = False,
) -> list[Article]:
    """Fetch and parse multiple RSS feeds in parallel.

    Uses ``asyncio.to_thread`` to run :func:`feedparser.parse` concurrently.
    Applies ``max_articles_per_source`` per feed. When
    ``config.include_content`` is True, calls
    ``ArticleExtractor.extract_batch`` to populate full article text.

    Parameters
    ----------
    feeds : dict[str, str]
        Mapping of category name → feed URL.
    config : ScraperConfig
        Scraper configuration.
    source_name : str
        Source identifier stored in each :class:`Article`.
    content_field : str, optional
        RSS entry field used as article content — ``"entry.summary"``
        (default) or ``"entry.content[0].value"``.
    content_is_html : bool, optional
        Whether *content_field* contains HTML to strip. Default False.

    Returns
    -------
    list[Article]
        Collected articles, deduplicated by URL.
    """
    max_per = config.max_articles_per_source
    logger.info(
        "Starting RSS feed collection",
        source=source_name,
        feeds=list(feeds.keys()),
        max_articles_per_source=max_per,
    )

    async def _fetch_one(category: str, url: str) -> list[Article]:
        logger.debug(
            "Fetching RSS feed", source=source_name, category=category, url=url
        )
        try:
            feed = await asyncio.wait_for(
                asyncio.to_thread(feedparser.parse, url),
                timeout=config.request_timeout,
            )
        except TimeoutError:
            logger.error(
                "RSS feed fetch timed out",
                source=source_name,
                category=category,
                url=url,
                timeout=config.request_timeout,
            )
            return []
        except Exception as exc:
            logger.error(
                "Failed to fetch RSS feed",
                source=source_name,
                category=category,
                error=str(exc),
                exc_info=True,
            )
            return []
        if feed.bozo and not feed.entries:
            logger.warning(
                "RSS feed parse error (bozo)",
                source=source_name,
                category=category,
            )
            return []
        articles: list[Article] = []
        for entry in feed.entries:
            if len(articles) >= max_per:
                break
            article = _entry_to_article(
                entry,
                category=category,
                source_name=source_name,
                content_field=content_field,
                content_is_html=content_is_html,
            )
            if article is not None:
                articles.append(article)
        logger.info(
            "RSS feed fetched",
            source=source_name,
            category=category,
            count=len(articles),
        )
        return articles

    results: list[list[Article]] = await asyncio.gather(
        *[_fetch_one(cat, url) for cat, url in feeds.items()]
    )
    all_articles: list[Article] = [a for batch in results for a in batch]

    if config.include_content and all_articles:
        from rss.services import ArticleExtractor

        extractor = ArticleExtractor(timeout=config.request_timeout)
        logger.info(
            "Fetching full article content", source=source_name, count=len(all_articles)
        )
        extracted = await extractor.extract_batch([a.url for a in all_articles])
        content_map: dict[str, str | None] = {r.url: r.text for r in extracted}
        all_articles = [
            a.model_copy(update={"content": content_map.get(a.url)})
            for a in all_articles
        ]

    deduplicated = deduplicate_by_url(all_articles)
    logger.info("RSS collection complete", source=source_name, total=len(deduplicated))
    return deduplicated
