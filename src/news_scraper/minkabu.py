"""Minkabu (minkabu.jp/news) news collector for the news_scraper package.

This module collects Japanese stock news from minkabu.jp using Playwright
for JavaScript rendering.

JavaScript rendering is required because minkabu.jp uses a React/Vue SPA
that does not serve article links in the initial server-side HTML.

Graceful Degradation
--------------------
When ``ScraperConfig.use_playwright`` is ``False`` (the default), this module
immediately returns an empty list without launching the browser.  This keeps
the default ``collect_financial_news()`` behaviour unchanged for callers that
do not have Playwright installed.

Constants
---------
MINKABU_NEWS_URL
    Full URL of the news listing page on minkabu.jp.
MINKABU_BASE_URL
    Base URL used for resolving relative article links.

Functions
---------
_entry_to_article
    Convert a single news list item element to an Article.
collect_news
    Collect recent news articles from minkabu.jp.

Examples
--------
>>> import asyncio
>>> from news_scraper.minkabu import collect_news
>>> from news_scraper.types import ScraperConfig
>>> config = ScraperConfig()
>>> articles = asyncio.run(collect_news(config=config))
>>> articles  # empty list when use_playwright=False
[]
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from news_scraper._html_utils import parse_html, resolve_relative_url
from news_scraper._logging import get_logger
from news_scraper.types import Article, ScraperConfig

if TYPE_CHECKING:
    import lxml.html

# Lazily imported at module level so unit tests can patch it.
# ``from playwright.async_api import async_playwright`` is deferred to avoid
# import errors when playwright is not installed.
try:
    from playwright.async_api import async_playwright
except ImportError:  # pragma: no cover
    async_playwright = None  # type: ignore[assignment]

logger = get_logger(__name__, module="minkabu")

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

MINKABU_NEWS_URL: str = "https://minkabu.jp/news"
MINKABU_BASE_URL: str = "https://minkabu.jp"

# XPath for news article list item elements.
# Minkabu renders news items as <li> elements inside a container.
# Each item contains an <a> tag whose href points to /news/<numeric-id>.
MINKABU_ITEM_XPATH: str = (
    "//li[.//a[re:match(@href, '^/news/[0-9]+$')]]"
    "|//li[.//a[starts-with(@href, '/news/')]]"
)

# Simpler XPath that looks for <a> tags linking to individual articles
# (numeric ID pattern like /news/4469066)
MINKABU_LINK_XPATH: str = "//a[re:match(@href, '^/news/[0-9]+$')]"

# Fallback XPath when regex namespace is unavailable
MINKABU_LINK_XPATH_FALLBACK: str = "//a[starts-with(@href, '/news/')]"

# lxml supports EXSLT regex; we use this namespace
_LXML_REGEXP_NS = "http://exslt.org/regular-expressions"

# Regex to identify canonical article URLs (numeric ID only, not /news/search etc.)
_ARTICLE_HREF_RE: re.Pattern[str] = re.compile(r"^/news/[0-9]+$")

# Scroll settings for infinite scroll control
_DEFAULT_SCROLL_WAIT_MS: int = 1500  # 1.5 seconds between scrolls


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────


def _is_article_href(href: str) -> bool:
    """Return True if href points to a canonical Minkabu article.

    Accepts both relative paths (``/news/4469066``) and absolute URLs
    (``https://minkabu.jp/news/4469066``).  Excludes non-article URLs such
    as ``/news/search``, ``/news/topics``, etc.

    Parameters
    ----------
    href : str
        URL or path to check.

    Returns
    -------
    bool
        True when the href is a canonical article link.

    Examples
    --------
    >>> _is_article_href("/news/4469066")
    True
    >>> _is_article_href("https://minkabu.jp/news/4469066")
    True
    >>> _is_article_href("/news/search")
    False
    """
    if not href:
        return False
    # Normalize: strip domain for absolute URLs
    path = href
    if href.startswith("http"):
        from urllib.parse import urlparse

        path = urlparse(href).path
    return bool(_ARTICLE_HREF_RE.match(path))


def _parse_minkabu_datetime(dt_str: str) -> datetime:
    """Parse a Minkabu datetime string and return UTC datetime.

    Minkabu uses ISO 8601 with JST offset (e.g. ``'2026-03-18T10:00:00+09:00'``)
    in ``datetime`` attributes, or plain text like ``'今日 19:30'`` / ``'03/18 19:30'``
    in visible text nodes.

    Parameters
    ----------
    dt_str : str
        Datetime string from a ``<time>`` element's ``datetime`` attribute or
        visible text.

    Returns
    -------
    datetime
        Timezone-aware UTC datetime.  Falls back to current UTC time on failure.

    Examples
    --------
    >>> from news_scraper.minkabu import _parse_minkabu_datetime
    >>> dt = _parse_minkabu_datetime("2026-03-18T10:00:00+09:00")
    >>> dt.hour
    1
    >>> dt.tzinfo.utcoffset(dt).total_seconds()
    0.0
    """
    dt_str = dt_str.strip()

    # Try ISO 8601 with timezone offset (preferred format from datetime attribute)
    try:
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            # Treat naive datetime as JST (+09:00)
            from datetime import timedelta

            jst = timezone(timedelta(hours=9))
            dt = dt.replace(tzinfo=jst)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        pass

    # Fall back to current UTC time if all parsing attempts fail
    logger.debug(
        "Failed to parse Minkabu datetime, using current UTC time",
        dt_str=dt_str,
    )
    return datetime.now(timezone.utc)


def _entry_to_article(element: lxml.html.HtmlElement) -> Article | None:
    """Convert a news list item element to an Article.

    Extracts title, URL, and published datetime from a ``<li>`` element
    (or other container element) that wraps a Minkabu news article link.

    Parameters
    ----------
    element : lxml.html.HtmlElement
        An element containing a Minkabu news article link.

    Returns
    -------
    Article | None
        Parsed article, or ``None`` when the element has no usable title
        (e.g. header rows or navigation elements).

    Examples
    --------
    >>> # Tested via unit tests with synthetic lxml HtmlElement fixtures
    """
    # ── Find the article anchor ────────────────────────────────────────────
    # Look for an <a> tag pointing to an article (numeric ID pattern).
    # Handles both relative (/news/4469066) and absolute URLs.
    anchors: list[lxml.html.HtmlElement] = element.xpath(
        ".//a[starts-with(@href, '/news/') or contains(@href, 'minkabu.jp/news/')]"
    )
    # Filter to canonical article links only (exclude /news/search, /news/topics, etc.)
    article_anchors = [a for a in anchors if _is_article_href(a.get("href", ""))]

    if not article_anchors:
        # Fall back: if element itself is an anchor
        href = element.get("href", "")
        if not _is_article_href(href):
            logger.debug("No article anchor found in element")
            return None
        anchor = element
    else:
        anchor = article_anchors[0]

    # ── URL ───────────────────────────────────────────────────────────────
    href = anchor.get("href", "").strip()
    # resolve_relative_url (urljoin) handles both relative and absolute hrefs correctly
    url = resolve_relative_url(href, MINKABU_BASE_URL) if href else MINKABU_BASE_URL

    # ── Title ─────────────────────────────────────────────────────────────
    # Try <h3>, <h2>, or <h1> heading elements first (most reliable)
    title_parts: list[str] = anchor.xpath(
        ".//h3[not(ancestor::time)]//text()"
        " | .//h2[not(ancestor::time)]//text()"
        " | .//h1[not(ancestor::time)]//text()"
    )
    title = "".join(title_parts).strip()

    if not title:
        # Fall back: use direct text nodes of the anchor (not nested elements).
        # Exclude text from <time>, <span class=...> category badges, etc.
        direct_texts: list[str] = anchor.xpath(
            "text() | .//p[not(ancestor::time)]//text()"
        )
        title = " ".join(t.strip() for t in direct_texts if t.strip()).strip()

    if not title:
        logger.debug("Skipping element with empty title", href=href)
        return None

    # ── Published datetime ────────────────────────────────────────────────
    time_elements: list[lxml.html.HtmlElement] = element.xpath(".//time")
    if not time_elements:
        time_elements = anchor.xpath(".//time")

    published = datetime.now(timezone.utc)
    if time_elements:
        datetime_attr = time_elements[0].get("datetime", "").strip()
        if datetime_attr:
            published = _parse_minkabu_datetime(datetime_attr)
        else:
            # Try visible text of <time> element
            time_text = time_elements[0].text_content().strip()
            if time_text:
                published = _parse_minkabu_datetime(time_text)

    return Article(
        title=title,
        url=url,
        published=published,
        source="minkabu",
        metadata={"scraper": "minkabu_playwright"},
    )


def _extract_articles_from_html(
    html: str,
    max_articles: int,
) -> list[Article]:
    """Parse HTML and extract Article objects.

    Parameters
    ----------
    html : str
        Raw HTML content from Playwright page.content().
    max_articles : int
        Maximum number of articles to return.

    Returns
    -------
    list[Article]
        List of parsed articles.
    """
    root = parse_html(html)

    # Strategy 1: Find <li> elements containing article links
    # Minkabu renders each article as an <li> in the news list
    li_elements: list[lxml.html.HtmlElement] = root.xpath(
        "//li[.//a[starts-with(@href, '/news/') "
        "or contains(@href, 'minkabu.jp/news/')]]"
    )

    # Filter to items that actually contain canonical article links
    article_li_elements = [
        li
        for li in li_elements
        if any(
            _is_article_href(a.get("href", ""))
            for a in li.xpath(
                ".//a[starts-with(@href, '/news/') "
                "or contains(@href, 'minkabu.jp/news/')]"
            )
        )
    ]

    articles: list[Article] = []
    seen_urls: set[str] = set()

    if article_li_elements:
        logger.debug("Found article li elements", count=len(article_li_elements))
        for li in article_li_elements:
            if len(articles) >= max_articles:
                break
            article = _entry_to_article(li)
            if article is not None and article.url not in seen_urls:
                seen_urls.add(article.url)
                articles.append(article)
    else:
        # Strategy 2: Fall back to finding article <a> tags directly
        # This handles cases where the page structure differs
        logger.debug("No article li elements found, trying direct anchor search")
        anchors: list[lxml.html.HtmlElement] = root.xpath(
            "//a[starts-with(@href, '/news/') or contains(@href, 'minkabu.jp/news/')]"
        )
        article_anchors = [a for a in anchors if _is_article_href(a.get("href", ""))]

        logger.debug("Found article anchors", count=len(article_anchors))
        for anchor in article_anchors:
            if len(articles) >= max_articles:
                break
            article = _entry_to_article(anchor)
            if article is not None and article.url not in seen_urls:
                seen_urls.add(article.url)
                articles.append(article)

    logger.debug("Articles extracted from HTML", count=len(articles))
    return articles


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


async def collect_news(config: ScraperConfig | None = None) -> list[Article]:
    """Collect recent news articles from minkabu.jp.

    Requires ``config.use_playwright=True`` to actually fetch articles.
    When ``use_playwright=False`` (the default), returns an empty list
    immediately without launching Playwright.

    Uses :func:`playwright.async_api.async_playwright` to launch a headless
    Chromium browser, navigate to the news listing page, and scroll to load
    more articles until ``max_articles_per_source`` is reached.

    Parameters
    ----------
    config : ScraperConfig | None, optional
        Scraper configuration.  If ``None`` or ``use_playwright=False``,
        returns an empty list (graceful degradation).

    Returns
    -------
    list[Article]
        List of scraped articles, limited to
        ``config.max_articles_per_source`` entries.
        Returns an empty list when ``use_playwright=False`` or on any
        Playwright error.

    Examples
    --------
    >>> from news_scraper.minkabu import collect_news
    >>> from news_scraper.types import ScraperConfig
    >>> import asyncio
    >>> config = ScraperConfig()
    >>> asyncio.run(collect_news(config=config))
    []
    >>> config_pw = ScraperConfig(use_playwright=True, max_articles_per_source=5)
    >>> # articles = asyncio.run(collect_news(config=config_pw))  # requires Playwright
    """
    # ── Graceful degradation: skip when use_playwright=False ──────────────
    if config is None or not config.use_playwright:
        logger.info(
            "use_playwright=False: skipping minkabu collection",
            use_playwright=config.use_playwright if config is not None else False,
        )
        return []

    max_articles = config.max_articles_per_source

    logger.info(
        "Starting minkabu news collection",
        url=MINKABU_NEWS_URL,
        max_articles=max_articles,
    )

    try:
        if async_playwright is None:
            logger.warning(
                "Playwright is not installed; skipping minkabu collection. "
                "Install with: uv add playwright && playwright install chromium"
            )
            return []
        articles = await _collect_with_async_playwright(async_playwright, max_articles)
    except Exception as exc:
        logger.warning(
            "Playwright error during minkabu collection",
            error=str(exc),
        )
        return []

    logger.info(
        "Minkabu news collection complete",
        total_articles=len(articles),
    )
    return articles


async def _collect_with_async_playwright(
    async_playwright_fn: Any,
    max_articles: int,
) -> list[Article]:
    """Fetch minkabu news using async Playwright and return Article list.

    Separated from collect_news to enable unit testing with a mocked
    async_playwright callable.

    Parameters
    ----------
    async_playwright_fn : callable
        The ``playwright.async_api.async_playwright`` function (or a mock).
    max_articles : int
        Maximum number of articles to collect.

    Returns
    -------
    list[Article]
        Parsed articles up to ``max_articles``.

    Raises
    ------
    Exception
        Propagates any Playwright error to the caller (collect_news handles it).
    """
    # Calculate number of scrolls needed (10 items per scroll, +3 safety margin)
    max_scrolls = (max_articles // 10) + 3

    articles: list[Article] = []
    seen_urls: set[str] = set()

    async with async_playwright_fn() as playwright:
        browser = await playwright.chromium.launch()
        try:
            page = await browser.new_page()
            await page.goto(MINKABU_NEWS_URL)

            for _ in range(max_scrolls):
                if len(articles) >= max_articles:
                    break

                # Get current HTML and extract articles
                html = await page.content()
                new_articles = _extract_articles_from_html(html, max_articles)

                for article in new_articles:
                    if article.url not in seen_urls and len(articles) < max_articles:
                        seen_urls.add(article.url)
                        articles.append(article)

                if len(articles) >= max_articles:
                    break

                # Scroll down to load more articles
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await page.wait_for_timeout(_DEFAULT_SCROLL_WAIT_MS)
        finally:
            await browser.close()

    return articles
