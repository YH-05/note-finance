"""JETRO news collector for the news_scraper package.

This module collects financial and trade news from JETRO
(Japan External Trade Organization) via RSS feeds and HTML scraping.

JETRO provides a Business Brief (ビジネス短信) RSS 2.0 feed, as well as
categorised news pages covering world regions, themes, and industries.

Functions
---------
_parse_jetro_date
    Parse a JETRO date string (RFC 2822 or Japanese format) to UTC datetime.
_fetch_rss_entries
    Fetch and parse RSS entries from the JETRO Business Brief feed.
_fetch_article_detail
    Fetch HTML content from a JETRO article page.
_extract_article_body
    Extract article body text using trafilatura with lxml fallback.
_extract_tags_from_page
    Extract country/theme/industry tags from a JETRO article page.
_entry_to_article
    Convert a feedparser entry to an Article model.
_to_article
    Build an Article from RSS entry data and optional scraped detail.
collect_news
    Collect recent news articles from JETRO feeds and pages.

Notes
-----
JETRO date strings can appear in two formats:
- RFC 2822 from the RSS feed: ``"Mon, 18 Mar 2026 09:00:00 +0900"``
- Japanese display format from HTML pages: ``"2026年03月18日"``

Examples
--------
>>> from news_scraper.jetro import _parse_jetro_date
>>> dt = _parse_jetro_date("Mon, 18 Mar 2026 09:00:00 +0900")
>>> dt.year
2026
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import httpx
import trafilatura
from lxml import html as lxml_html

from news_scraper._jetro_config import (
    ARTICLE_SELECTORS,
    JETRO_RSS_BIZNEWS,
)
from news_scraper._logging import get_logger
from news_scraper.types import Article, ScraperConfig, deduplicate_by_url, get_delay

logger = get_logger(__name__, module="jetro")


def _run_async(coro: Any) -> Any:
    """Run an async coroutine from sync context, handling nested event loops.

    Parameters
    ----------
    coro : Coroutine
        The coroutine to run.

    Returns
    -------
    Any
        The result of the coroutine.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


# Regex for Japanese date format: 2026年03月18日
_JP_DATE_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")

# Default HTTP headers for JETRO requests
_DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}


def _parse_jetro_date(date_str: str | None) -> datetime:
    """Parse a JETRO date string to a UTC datetime.

    Handles two formats commonly found on JETRO:
    1. RFC 2822 (from RSS feeds): ``"Mon, 18 Mar 2026 09:00:00 +0900"``
    2. Japanese date format (from HTML pages): ``"2026年03月18日"``

    Parameters
    ----------
    date_str : str | None
        Date string from JETRO RSS feed or HTML page, or None.

    Returns
    -------
    datetime
        Parsed datetime in UTC, or current UTC time if parsing fails.

    Examples
    --------
    >>> dt = _parse_jetro_date("Mon, 18 Mar 2026 09:00:00 +0900")
    >>> dt.year
    2026
    >>> dt.tzinfo == timezone.utc
    True

    >>> dt = _parse_jetro_date("2026年03月18日")
    >>> dt.year
    2026
    >>> dt.month
    3
    >>> dt.day
    18

    >>> dt = _parse_jetro_date(None)
    >>> dt.tzinfo is not None
    True
    """
    if not date_str:
        return datetime.now(timezone.utc)

    # Try RFC 2822 first (RSS feed format)
    try:
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    # Try Japanese date format: YYYY年MM月DD日
    match = _JP_DATE_RE.search(date_str)
    if match:
        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            return datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            pass

    logger.warning("Failed to parse JETRO date", date_str=date_str)
    return datetime.now(timezone.utc)


def _fetch_rss_entries(
    feed_url: str = JETRO_RSS_BIZNEWS,
) -> list[Any]:
    """Fetch and parse RSS entries from a JETRO feed URL.

    Parameters
    ----------
    feed_url : str
        URL of the RSS feed to fetch. Defaults to the JETRO Business Brief feed.

    Returns
    -------
    list[Any]
        List of feedparser entry objects. Empty list on error.

    Examples
    --------
    >>> # In tests, feedparser.parse is mocked
    """
    logger.debug("Fetching JETRO RSS feed", url=feed_url)
    try:
        feed = feedparser.parse(feed_url)
        if feed.bozo and not feed.entries:
            logger.warning(
                "JETRO RSS feed parse error",
                url=feed_url,
                error=str(feed.bozo_exception)
                if hasattr(feed, "bozo_exception")
                else "unknown",
            )
            return []
        logger.info("JETRO RSS feed fetched", entry_count=len(feed.entries))
        return list(feed.entries)
    except Exception as e:
        logger.error(
            "Failed to fetch JETRO RSS feed",
            url=feed_url,
            error=str(e),
            exc_info=True,
        )
        return []


def _fetch_article_detail(
    url: str,
    client: httpx.Client,
) -> str | None:
    """Fetch HTML content from a JETRO article page.

    Parameters
    ----------
    url : str
        Full URL of the JETRO article page.
    client : httpx.Client
        HTTP client to use for the request.

    Returns
    -------
    str | None
        Raw HTML string, or None on failure.

    Examples
    --------
    >>> # In tests, httpx.Client is mocked
    """
    logger.debug("Fetching JETRO article detail", url=url)
    try:
        response = client.get(url)
        response.raise_for_status()
        return response.text
    except httpx.HTTPStatusError as e:
        logger.warning(
            "JETRO article HTTP error",
            url=url,
            status_code=e.response.status_code,
        )
    except httpx.RequestError as e:
        logger.warning(
            "JETRO article request failed",
            url=url,
            error=str(e),
        )
    except Exception as e:
        logger.error(
            "Unexpected error fetching JETRO article",
            url=url,
            error=str(e),
            exc_info=True,
        )
    return None


def _extract_article_body(html_content: str) -> str | None:
    """Extract article body text from JETRO HTML content.

    Uses trafilatura for primary extraction with lxml CSS selector fallback.

    Parameters
    ----------
    html_content : str
        Raw HTML string of the JETRO article page.

    Returns
    -------
    str | None
        Extracted article text, or None if extraction fails.

    Examples
    --------
    >>> html = "<html><body><p>Test content</p></body></html>"
    >>> # Result depends on trafilatura's ability to extract
    """
    # Primary: trafilatura extraction
    try:
        text = trafilatura.extract(html_content)
        if text and len(text.strip()) > 50:
            logger.debug("Article body extracted via trafilatura", length=len(text))
            return text.strip()
    except Exception as e:
        logger.debug("Trafilatura extraction failed", error=str(e))

    # Fallback: lxml CSS selector extraction
    try:
        tree = lxml_html.fromstring(html_content)
        for selector in ARTICLE_SELECTORS["body"]:
            elements = tree.cssselect(selector)
            if elements:
                paragraphs = [
                    text for el in elements if (text := el.text_content().strip())
                ]
                if paragraphs:
                    body = "\n\n".join(paragraphs)
                    logger.debug(
                        "Article body extracted via lxml fallback",
                        selector=selector,
                        length=len(body),
                    )
                    return body
    except Exception as e:
        logger.warning("lxml fallback extraction failed", error=str(e))

    logger.warning("Failed to extract article body")
    return None


def _extract_tags_from_page(html_content: str) -> list[str]:
    """Extract tags (country, theme, industry) from a JETRO article page.

    Parameters
    ----------
    html_content : str
        Raw HTML string of the JETRO article page.

    Returns
    -------
    list[str]
        List of tag strings. Empty list if no tags found.

    Examples
    --------
    >>> # Tags are extracted from `.elem_tag a` elements
    """
    tags: list[str] = []
    try:
        tree = lxml_html.fromstring(html_content)
        for selector in ARTICLE_SELECTORS["tags"]:
            elements = tree.cssselect(selector)
            if elements:
                for el in elements:
                    text = el.text_content().strip()
                    if text:
                        tags.append(text)
                if tags:
                    logger.debug("Tags extracted", selector=selector, count=len(tags))
                    return tags
    except Exception as e:
        logger.debug("Tag extraction failed", error=str(e))
    return tags


def _entry_to_article(entry: Any, category: str | None = None) -> Article | None:
    """Convert a feedparser entry to an Article model.

    Parameters
    ----------
    entry : Any
        Feedparser entry dict-like object.
    category : str | None
        Category name for the article.

    Returns
    -------
    Article | None
        Parsed Article, or None if the entry is invalid (missing title or URL).

    Examples
    --------
    >>> # Tested via unit tests with mock feedparser entries
    """
    title = entry.get("title")
    url = entry.get("link")

    if not title or not isinstance(title, str):
        logger.debug("Skipping entry with missing title", category=category)
        return None
    if not url or not isinstance(url, str):
        logger.debug("Skipping entry with missing URL", category=category)
        return None

    # Parse publication date
    pub_date_str = entry.get("published") or entry.get("updated")
    published = _parse_jetro_date(pub_date_str)

    # Extract summary from RSS description
    summary_raw = entry.get("summary") or entry.get("description")
    summary = (
        summary_raw.strip() if summary_raw and isinstance(summary_raw, str) else None
    )

    # Extract RSS-level category/tags
    tags: list[str] = []
    entry_tags = entry.get("tags", [])
    if isinstance(entry_tags, list):
        for tag in entry_tags:
            if isinstance(tag, dict):
                term = tag.get("term")
                if term and isinstance(term, str):
                    tags.append(term)
            elif isinstance(tag, str):
                tags.append(tag)

    # Determine category from RSS feed category field
    rss_category = None
    entry_category = entry.get("category")
    if entry_category and isinstance(entry_category, str):
        rss_category = entry_category

    return Article(
        title=title.strip(),
        url=url.strip(),
        published=published,
        source="jetro",
        category=category or rss_category,
        summary=summary,
        tags=tags,
        metadata={
            "feed_source": "jetro_rss",
            "content_type": rss_category,
        },
    )


def _to_article(
    entry: Any,
    category: str | None,
    content: str | None,
    page_tags: list[str],
) -> Article | None:
    """Build an Article from RSS entry data and optional scraped detail.

    Combines the RSS entry data with scraped article body and page tags.

    Parameters
    ----------
    entry : Any
        Feedparser entry dict-like object.
    category : str | None
        Category name for the article.
    content : str | None
        Full article content extracted from the detail page, or None.
    page_tags : list[str]
        Tags extracted from the detail page.

    Returns
    -------
    Article | None
        Complete Article with content and enriched tags, or None if invalid.
    """
    article = _entry_to_article(entry, category)
    if article is None:
        return None

    # Collect all updates and apply in a single model_copy
    updates: dict[str, Any] = {}
    if content:
        updates["content"] = content
    if page_tags:
        merged_tags = list(article.tags)
        seen = set(merged_tags)
        for tag in page_tags:
            if tag not in seen:
                merged_tags.append(tag)
                seen.add(tag)
        updates["tags"] = merged_tags
    if updates:
        article = article.model_copy(update=updates)

    return article


def _crawled_entry_to_article(entry: Any) -> Article | None:
    """Convert a CrawledEntry from the category crawler to an Article.

    Parameters
    ----------
    entry : Any
        A ``CrawledEntry`` dataclass instance from ``_jetro_crawler``.

    Returns
    -------
    Article | None
        Converted Article, or None if the entry is invalid.
    """
    if not entry.title or not entry.url:
        return None

    published = _parse_jetro_date(entry.published)

    return Article(
        title=entry.title.strip(),
        url=entry.url.strip(),
        published=published,
        source="jetro",
        category=entry.category,
        summary=None,
        tags=[entry.content_type] if entry.content_type else [],
        metadata={
            "feed_source": "jetro_category",
            "content_type": entry.content_type,
            "subcategory": entry.subcategory,
        },
    )


def _collect_rss_articles(
    entries: list[Any],
    config: ScraperConfig,
    delay: float,
) -> list[Article]:
    """Phase 1: Collect articles from RSS entries.

    Parameters
    ----------
    entries : list[Any]
        Feedparser entry objects.
    config : ScraperConfig
        Scraper configuration.
    delay : float
        Delay between requests in seconds.

    Returns
    -------
    list[Article]
        Articles collected from RSS entries.
    """
    articles: list[Article] = []
    if not entries:
        return articles

    if not config.include_content:
        for entry in entries:
            article = _entry_to_article(entry)
            if article is not None:
                articles.append(article)
    else:
        with httpx.Client(
            timeout=config.request_timeout,
            headers=_DEFAULT_HEADERS,
            follow_redirects=True,
        ) as client:
            for i, entry in enumerate(entries):
                url = entry.get("link")
                content: str | None = None
                page_tags: list[str] = []

                if url and isinstance(url, str):
                    html_content = _fetch_article_detail(url, client)
                    if html_content:
                        content = _extract_article_body(html_content)
                        page_tags = _extract_tags_from_page(html_content)

                article = _to_article(entry, None, content, page_tags)
                if article is not None:
                    articles.append(article)

                if i < len(entries) - 1:
                    time.sleep(delay)

    return articles


def _collect_category_articles(
    categories: list[str],
    regions: dict[str, list[str]] | None,
) -> list[Article]:
    """Phase 2: Crawl JETRO category pages via Playwright.

    Parameters
    ----------
    categories : list[str]
        Category groups to crawl.
    regions : dict[str, list[str]] | None
        Region-to-country mapping.

    Returns
    -------
    list[Article]
        Articles collected from category pages.
    """
    articles: list[Article] = []
    logger.info(
        "Starting JETRO category page crawling",
        categories=categories,
        regions=regions,
    )
    try:
        from news_scraper._jetro_crawler import JetroCategoryCrawler

        crawler = JetroCategoryCrawler()
        crawled_entries = crawler.crawl_all(
            categories=categories,
            regions=regions,
        )
        logger.info("Category crawl complete", crawled_entries=len(crawled_entries))
        for crawled in crawled_entries:
            article = _crawled_entry_to_article(crawled)
            if article is not None:
                articles.append(article)
    except ImportError:
        logger.warning(
            "Playwright not installed, skipping category crawl. "
            "Install with: uv add playwright && playwright install chromium"
        )
    except Exception as e:
        logger.error("Category crawl failed", error=str(e), exc_info=True)
    return articles


def _collect_archive_articles(
    archive_pages: int,
    regions: dict[str, list[str]],
) -> list[Article]:
    """Phase 3: Crawl paginated archive pages for historical articles.

    Parameters
    ----------
    archive_pages : int
        Number of archive pages to crawl per country per content type.
    regions : dict[str, list[str]]
        Region-to-country mapping.

    Returns
    -------
    list[Article]
        Articles collected from archive pages.
    """
    articles: list[Article] = []
    logger.info(
        "Starting JETRO archive page crawling",
        archive_pages=archive_pages,
        regions=regions,
    )

    archive_types = {
        "ビジネス短信": "biznewstop/{region}/{code}/biznews/",
        "地域・分析レポート": "areareportstop/{region}/{code}/areareports/",
        "調査レポート": "reportstop/{region}/{code}/reports/",
    }

    # Validate region keys and country codes (same pattern as _build_page_urls)
    _safe_key_re = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")

    try:
        from news_scraper._jetro_crawler import JetroCategoryCrawler

        crawler = JetroCategoryCrawler()

        async def _crawl_archives() -> list[Any]:
            """Crawl all archive URLs concurrently with Semaphore throttling."""
            sem = asyncio.Semaphore(3)

            async def _crawl_one(
                archive_url: str, code: str, content_type: str
            ) -> list[Any]:
                async with sem:
                    return await crawler.crawl_archive_pages(
                        url=archive_url,
                        category="world",
                        subcategory=code,
                        content_type=content_type,
                        max_pages=archive_pages,
                    )

            tasks: list[asyncio.Task[list[Any]]] = []
            for region_key, country_codes in regions.items():
                if not _safe_key_re.match(region_key):
                    logger.warning(
                        "Invalid region_key, skipping", region_key=region_key
                    )
                    continue
                for code in country_codes:
                    if not _safe_key_re.match(code):
                        logger.warning("Invalid country code, skipping", code=code)
                        continue
                    for content_type, url_pattern in archive_types.items():
                        archive_url = (
                            f"https://www.jetro.go.jp/"
                            f"{url_pattern.format(region=region_key, code=code)}"
                        )
                        tasks.append(
                            asyncio.create_task(
                                _crawl_one(archive_url, code, content_type)
                            )
                        )

            results = await asyncio.gather(*tasks, return_exceptions=True)
            all_crawled: list[Any] = []
            for result in results:
                if isinstance(result, BaseException):
                    logger.warning("Archive crawl failed", error=str(result))
                else:
                    all_crawled.extend(result)
            return all_crawled

        archive_entries = _run_async(_crawl_archives())

        logger.info("Archive crawl complete", archive_entries=len(archive_entries))
        for crawled in archive_entries:
            article = _crawled_entry_to_article(crawled)
            if article is not None:
                articles.append(article)

    except ImportError:
        logger.warning("Playwright not installed, skipping archive crawl")
    except Exception as e:
        logger.error("Archive crawl failed", error=str(e), exc_info=True)

    return articles


def collect_news(
    config: ScraperConfig | None = None,
    categories: list[str] | None = None,
    regions: dict[str, list[str]] | None = None,
    archive_pages: int = 0,
) -> list[Article]:
    """Collect recent news articles from JETRO RSS feeds and category pages.

    Fetches articles from JETRO's Business Brief RSS feed. When
    ``categories`` is provided, also crawls JETRO category pages
    (world/theme/industry) using Playwright to collect additional articles.
    When ``archive_pages`` > 0, crawls the paginated archive pages for
    each country to collect historical articles (30 articles per page).

    Parameters
    ----------
    config : ScraperConfig | None, optional
        Scraper configuration. If None, uses default settings.
    categories : list[str] | None, optional
        List of JETRO category groups to crawl via Playwright.
        Valid values: ``"world"``, ``"theme"``, ``"industry"``.
        When None, only the RSS feed is fetched.
    regions : dict[str, list[str]] | None, optional
        Mapping of JETRO region key to country codes for the ``"world"``
        category. E.g. ``{"asia": ["cn", "kr"]}``.
    archive_pages : int, optional
        Number of archive pages to crawl per country per content type
        (default 0 = disabled). Each page has ~30 articles.
        E.g. ``archive_pages=3`` fetches up to 90 articles per content type.

    Returns
    -------
    list[Article]
        List of collected articles, deduplicated by URL.

    Examples
    --------
    >>> from news_scraper.jetro import collect_news
    >>> from news_scraper.types import ScraperConfig
    >>> config = ScraperConfig(max_articles_per_source=10)
    >>> # In tests, feedparser and httpx are mocked
    >>> articles = collect_news(config=config)
    >>> isinstance(articles, list)
    True
    """
    if config is None:
        config = ScraperConfig()

    max_per_source = config.max_articles_per_source
    delay = get_delay(config)

    logger.info(
        "Starting JETRO news collection",
        max_articles_per_source=max_per_source,
        include_content=config.include_content,
        categories=categories,
    )

    # Phase 1: RSS
    entries = _fetch_rss_entries()
    articles = _collect_rss_articles(entries, config, delay)
    logger.info("RSS phase complete", rss_articles=len(articles))

    # Phase 2: Category page crawling
    if categories:
        articles.extend(_collect_category_articles(categories, regions))

    # Phase 3: Archive page crawling
    if archive_pages > 0 and regions:
        articles.extend(_collect_archive_articles(archive_pages, regions))

    deduplicated = deduplicate_by_url(articles)

    # Apply max_per_source limit after deduplication
    if len(deduplicated) > max_per_source:
        logger.info(
            "Limiting articles to max_per_source",
            before=len(deduplicated),
            after=max_per_source,
        )
        deduplicated = deduplicated[:max_per_source]

    logger.info(
        "JETRO news collection complete",
        total_articles=len(deduplicated),
        rss_count=len(entries) if entries else 0,
        category_crawl=categories is not None,
        archive_crawl=archive_pages > 0,
    )
    return deduplicated
