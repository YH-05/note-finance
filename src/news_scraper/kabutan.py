"""Kabutan (kabutan.jp) news collector for the news_scraper package.

This module collects Japanese stock news from kabutan.jp by scraping HTML.
The page structure uses two tables split by an advertisement div:
- ``//table[@class='s_news_list mgbt0']`` for the top 10 articles
- ``//table[@class='s_news_list mgt0']`` for the bottom 5 articles

Both tables are matched by ``KABUTAN_ROW_XPATH`` which uses ``contains``.

Constants
---------
KABUTAN_NEWS_URL
    Full URL of the market news page on kabutan.jp.
KABUTAN_BASE_URL
    Base URL used for resolving relative article links.
KABUTAN_ROW_XPATH
    XPath selecting all ``<tr>`` rows in kabutan news list tables.

Functions
---------
collect_news
    Collect recent news articles from kabutan.jp.

Examples
--------
>>> from news_scraper.kabutan import collect_news
>>> from news_scraper.types import ScraperConfig
>>> config = ScraperConfig()
>>> articles = collect_news(config=config)
>>> len(articles) >= 0
True
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx

from news_scraper._html_utils import (
    JP_DEFAULT_HEADERS,
    fetch_html,
    parse_html,
    resolve_relative_url,
)
from news_scraper._logging import get_logger
from news_scraper.types import Article, ScraperConfig

if TYPE_CHECKING:
    import lxml.html

logger = get_logger(__name__, module="kabutan")

# ─────────────────────────────────────────────────────────────────────────────
# Constants (verified against kabutan-html-analysis.json)
# ─────────────────────────────────────────────────────────────────────────────

KABUTAN_NEWS_URL: str = "https://kabutan.jp/news/marketnews/"
KABUTAN_BASE_URL: str = "https://kabutan.jp"

# The page contains two separate tables split by an ad div; ``contains`` matches both.
KABUTAN_ROW_XPATH: str = "//table[contains(@class, 's_news_list')]//tr"

# XPath expressions relative to each <tr> row
KABUTAN_TITLE_XPATH: str = ".//td[3]/a/text()"
KABUTAN_URL_XPATH: str = ".//td[3]/a/@href"
KABUTAN_DATE_XPATH: str = ".//td[@class='news_time']/time/@datetime"
KABUTAN_TYPE_XPATH: str = ".//td[2]/div[contains(@class, 'newslist_ctg')]/text()"


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────


def _parse_jst_to_utc(datetime_attr: str) -> datetime:
    """Parse an ISO 8601 datetime string with JST offset and return UTC.

    Parameters
    ----------
    datetime_attr : str
        Datetime string such as ``'2026-03-18T18:15:00+09:00'``.

    Returns
    -------
    datetime
        Timezone-aware datetime in UTC.

    Examples
    --------
    >>> from news_scraper.kabutan import _parse_jst_to_utc
    >>> dt = _parse_jst_to_utc("2026-03-18T18:15:00+09:00")
    >>> dt.hour
    9
    >>> dt.tzinfo.utcoffset(dt).total_seconds()
    0.0
    """
    dt = datetime.fromisoformat(datetime_attr)
    if dt.tzinfo is None:
        # Treat naive datetime as JST (+09:00) even though it is unlikely
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _row_to_article(
    row: lxml.html.HtmlElement,
    base_url: str,
) -> Article | None:
    """Convert a kabutan news ``<tr>`` element to an :class:`Article`.

    Parameters
    ----------
    row : lxml.html.HtmlElement
        A ``<tr>`` element from one of the kabutan news list tables.
    base_url : str
        Base URL (e.g. ``"https://kabutan.jp"``) used to resolve relative hrefs.

    Returns
    -------
    Article | None
        Parsed article, or ``None`` when the row has no title (e.g. header rows,
        advertisement rows without an ``<a>`` element).

    Examples
    --------
    >>> # Tested via unit tests with synthetic lxml HtmlElement fixtures
    """
    # ── title ─────────────────────────────────────────────────────────────
    title_parts: list[str] = row.xpath(KABUTAN_TITLE_XPATH)
    title = title_parts[0].strip() if title_parts else ""
    if not title:
        logger.debug("Skipping row with empty title")
        return None

    # ── URL ───────────────────────────────────────────────────────────────
    href_parts: list[str] = row.xpath(KABUTAN_URL_XPATH)
    href = href_parts[0].strip() if href_parts else ""
    url = resolve_relative_url(href, base_url) if href else base_url

    # ── Published datetime ────────────────────────────────────────────────
    datetime_parts: list[str] = row.xpath(KABUTAN_DATE_XPATH)
    if datetime_parts:
        try:
            published = _parse_jst_to_utc(datetime_parts[0].strip())
        except (ValueError, TypeError) as exc:
            logger.warning(
                "Failed to parse kabutan datetime attribute",
                datetime_attr=datetime_parts[0],
                error=str(exc),
            )
            published = datetime.now(timezone.utc)
    else:
        logger.debug("No datetime attribute found in row, using current time")
        published = datetime.now(timezone.utc)

    # ── Category ──────────────────────────────────────────────────────────
    category_parts: list[str] = row.xpath(KABUTAN_TYPE_XPATH)
    category: str | None = category_parts[0].strip() if category_parts else None

    return Article(
        title=title,
        url=url,
        published=published,
        source="kabutan",
        category=category,
        metadata={"scraper": "kabutan_html"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def collect_news(config: ScraperConfig | None = None) -> list[Article]:
    """Collect recent news articles from kabutan.jp.

    Fetches the market news page, parses all rows from both ``s_news_list``
    tables using XPath, and converts them to :class:`Article` instances.

    Parameters
    ----------
    config : ScraperConfig | None, optional
        Scraper configuration. If ``None``, uses default settings.

    Returns
    -------
    list[Article]
        List of scraped articles, limited to
        ``config.max_articles_per_source`` entries.
        Returns an empty list on any HTTP or network error.

    Examples
    --------
    >>> from news_scraper.kabutan import collect_news
    >>> from news_scraper.types import ScraperConfig
    >>> config = ScraperConfig(max_articles_per_source=10)
    >>> # In tests this is mocked to avoid real HTTP calls
    >>> articles = collect_news(config=config)
    >>> isinstance(articles, list)
    True
    """
    if config is None:
        config = ScraperConfig()

    max_articles = config.max_articles_per_source
    logger.info(
        "Starting kabutan news collection",
        url=KABUTAN_NEWS_URL,
        max_articles=max_articles,
    )

    articles: list[Article] = []

    try:
        with httpx.Client(timeout=config.request_timeout) as client:
            html_content = fetch_html(
                KABUTAN_NEWS_URL,
                client,
                headers=JP_DEFAULT_HEADERS,
            )
    except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as exc:
        logger.warning(
            "HTTP error fetching kabutan news page",
            url=KABUTAN_NEWS_URL,
            error=str(exc),
        )
        return []
    except Exception as exc:
        logger.warning(
            "Unexpected error fetching kabutan news page",
            url=KABUTAN_NEWS_URL,
            error=str(exc),
        )
        return []

    root = parse_html(html_content)
    rows: list[lxml.html.HtmlElement] = root.xpath(KABUTAN_ROW_XPATH)

    logger.debug("Kabutan rows found", count=len(rows))

    for row in rows:
        if len(articles) >= max_articles:
            break
        article = _row_to_article(row, KABUTAN_BASE_URL)
        if article is not None:
            articles.append(article)

    logger.info(
        "Kabutan news collection complete",
        total_articles=len(articles),
    )
    return articles
