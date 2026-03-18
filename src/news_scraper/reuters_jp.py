"""Reuters Japan (jp.reuters.com) news collector for the news_scraper package.

This module collects Japanese financial news from Reuters Japan by scraping HTML.
It fetches /markets/ and /business/ pages in parallel using ThreadPoolExecutor.

Both pages are fully server-side rendered (SSR) and can be retrieved with
httpx + lxml only (no Playwright required).

HTML structure is identified by ``data-testid`` attributes to avoid fragile
CSS class names that include unpredictable hash suffixes (e.g. ``__UeoFK``).

Constants
---------
REUTERS_JP_BASE_URL
    Base URL for Reuters Japan.
REUTERS_JP_SECTIONS
    Mapping of section names to their full URLs.
MARKETS_CARDS_XPATH
    XPath selecting HeroCard and BasicCard elements on /markets/.
BUSINESS_CARDS_XPATH
    XPath selecting MediaStoryCard elements on /business/.

Functions
---------
collect_news
    Collect recent news articles from jp.reuters.com.

Examples
--------
>>> from news_scraper.reuters_jp import collect_news
>>> from news_scraper.types import ScraperConfig
>>> config = ScraperConfig()
>>> articles = collect_news(config=config)
>>> len(articles) >= 0
True
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from news_scraper.types import Article, ScraperConfig, deduplicate_by_url

if TYPE_CHECKING:
    import lxml.html

logger = get_logger(__name__, module="reuters_jp")

# ─────────────────────────────────────────────────────────────────────────────
# Constants (verified against reuters-html-analysis.json)
# ─────────────────────────────────────────────────────────────────────────────

REUTERS_JP_BASE_URL: str = "https://jp.reuters.com"

REUTERS_JP_SECTIONS: dict[str, str] = {
    "markets": "https://jp.reuters.com/markets/",
    "business": "https://jp.reuters.com/business/",
}

# /markets/ page XPath constants
# All selectors use data-testid to avoid fragile CSS hash suffixes.
MARKETS_CARDS_XPATH: str = "//*[@data-testid='HeroCard' or @data-testid='BasicCard']"
MARKETS_TITLE_XPATH: str = ".//*[@data-testid='Heading']//text()"
MARKETS_URL_XPATH: str = ".//*[@data-testid='Title']//a/@href"
MARKETS_URL_FALLBACK_XPATH: str = "./@href"
MARKETS_DATE_XPATH: str = ".//time/@dateTime"

# /business/ page XPath constants
BUSINESS_CARDS_XPATH: str = "//*[@data-testid='MediaStoryCard']"
BUSINESS_TITLE_XPATH: str = ".//*[@data-testid='Heading']//text()"
BUSINESS_URL_HERO_XPATH: str = ".//h3[@data-testid='Heading']//a/@href"
BUSINESS_URL_HUB_XPATH: str = ".//a[@data-testid='Heading']/@href"
BUSINESS_DATE_XPATH: str = ".//time/@dateTime"

# Regex to identify canonical article URL paths (not tag/section pages)
# Example: /markets/japan/XMSCJTKCWZL6ZDSSMWAPGSD5YI-2026-03-18/
_ARTICLE_URL_PATTERN: re.Pattern[str] = re.compile(
    r"^/[a-z-]+/[a-z-]+/[A-Z0-9]{20,}-\d{4}-\d{2}-\d{2}/$"
)

# Recommended delay for Reuters Japan (longer than default to avoid 429)
_REUTERS_JP_DEFAULT_DELAY: float = 2.0


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────


def _parse_utc_z_datetime(dt_str: str) -> datetime:
    """Parse an ISO 8601 UTC datetime string with optional Z suffix.

    Reuters Japan uses ``dateTime`` attribute values such as
    ``'2026-03-18T09:14:42.564Z'``.  Python 3.11+ handles the ``Z`` suffix
    natively; for 3.10 compatibility we replace it with ``+00:00``.

    Parameters
    ----------
    dt_str : str
        Datetime string in ISO 8601 format, e.g. ``'2026-03-18T09:14:42.564Z'``.

    Returns
    -------
    datetime
        Timezone-aware UTC datetime.  Falls back to the current UTC time if
        parsing fails.

    Examples
    --------
    >>> from news_scraper.reuters_jp import _parse_utc_z_datetime
    >>> dt = _parse_utc_z_datetime("2026-03-18T09:14:42.564Z")
    >>> dt.hour
    9
    >>> dt.tzinfo.utcoffset(dt).total_seconds()
    0.0
    """
    try:
        normalized = dt_str.strip().replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).astimezone(timezone.utc)
    except (ValueError, AttributeError) as exc:
        logger.warning(
            "Failed to parse Reuters JP datetime",
            dt_str=dt_str,
            error=str(exc),
        )
        return datetime.now(timezone.utc)


def _extract_title_texts(
    card: lxml.html.HtmlElement,
    title_xpath: str,
) -> str:
    """Extract and join all text nodes from an XPath result.

    Parameters
    ----------
    card : lxml.html.HtmlElement
        Card element to query.
    title_xpath : str
        XPath expression returning text nodes.

    Returns
    -------
    str
        Joined and stripped title string, or empty string if not found.
    """
    parts: list[str] = card.xpath(title_xpath)
    return "".join(parts).strip()


def _parse_markets_page(html: str) -> list[Article]:
    """Parse the Reuters Japan /markets/ page and extract articles.

    Extracts HeroCard (1 featured article) and BasicCard (list articles)
    using ``data-testid`` XPath selectors.  Relative URLs are resolved to
    absolute URLs via :func:`~urllib.parse.urljoin`.

    Parameters
    ----------
    html : str
        Raw HTML content of ``https://jp.reuters.com/markets/``.

    Returns
    -------
    list[Article]
        List of parsed :class:`~news_scraper.types.Article` instances.

    Examples
    --------
    >>> # Tested via unit tests with synthetic HTML fixtures
    """
    root = parse_html(html)
    cards: list[lxml.html.HtmlElement] = root.xpath(MARKETS_CARDS_XPATH)
    logger.debug("Markets cards found", count=len(cards))

    articles: list[Article] = []
    for card in cards:
        # ── Title ──────────────────────────────────────────────────────────
        title_parts: list[str] = card.xpath(MARKETS_TITLE_XPATH)
        title = "".join(title_parts).strip()
        if not title:
            logger.debug("Skipping markets card with empty title")
            continue

        # ── URL ────────────────────────────────────────────────────────────
        href_parts: list[str] = card.xpath(MARKETS_URL_XPATH)
        href = href_parts[0].strip() if href_parts else ""
        if not href:
            # Fallback: BasicCard may have href on the container element
            fallback_parts: list[str] = card.xpath(MARKETS_URL_FALLBACK_XPATH)
            href = fallback_parts[0].strip() if fallback_parts else ""
        if not href:
            logger.debug("Skipping markets card with no URL", title=title)
            continue

        url = resolve_relative_url(href, REUTERS_JP_BASE_URL)

        # ── Published datetime ─────────────────────────────────────────────
        date_parts: list[str] = card.xpath(MARKETS_DATE_XPATH)
        if date_parts:
            published = _parse_utc_z_datetime(date_parts[0].strip())
        else:
            logger.debug("No datetime found in markets card", title=title)
            published = datetime.now(timezone.utc)

        articles.append(
            Article(
                title=title,
                url=url,
                published=published,
                source="reuters_jp",
                category="markets",
                metadata={"scraper": "reuters_jp_html", "section": "markets"},
            )
        )

    logger.info("Markets page parsed", article_count=len(articles))
    return articles


def _parse_business_page(html: str) -> list[Article]:
    """Parse the Reuters Japan /business/ page and extract articles.

    Extracts MediaStoryCard elements in both hero and hub variants.
    - **hero variant**: URL is inside ``h3[@data-testid='Heading']//a``.
    - **hub variant**: URL is on ``a[@data-testid='Heading']`` directly.

    Business page URLs are typically absolute (starting with
    ``https://jp.reuters.com``).  Relative URLs are still resolved via
    :func:`~urllib.parse.urljoin` for robustness.

    Parameters
    ----------
    html : str
        Raw HTML content of ``https://jp.reuters.com/business/``.

    Returns
    -------
    list[Article]
        List of parsed :class:`~news_scraper.types.Article` instances.

    Examples
    --------
    >>> # Tested via unit tests with synthetic HTML fixtures
    """
    root = parse_html(html)
    cards: list[lxml.html.HtmlElement] = root.xpath(BUSINESS_CARDS_XPATH)
    logger.debug("Business cards found", count=len(cards))

    articles: list[Article] = []
    for card in cards:
        # ── Title ──────────────────────────────────────────────────────────
        title_parts: list[str] = card.xpath(BUSINESS_TITLE_XPATH)
        title = "".join(title_parts).strip()
        if not title:
            logger.debug("Skipping business card with empty title")
            continue

        # ── URL: try hero XPath first, then hub XPath ──────────────────────
        hero_hrefs: list[str] = card.xpath(BUSINESS_URL_HERO_XPATH)
        hub_hrefs: list[str] = card.xpath(BUSINESS_URL_HUB_XPATH)

        href = ""
        if hero_hrefs:
            href = hero_hrefs[0].strip()
        elif hub_hrefs:
            href = hub_hrefs[0].strip()

        if not href:
            logger.debug("Skipping business card with no URL", title=title)
            continue

        url = resolve_relative_url(href, REUTERS_JP_BASE_URL)

        # ── Published datetime ─────────────────────────────────────────────
        date_parts: list[str] = card.xpath(BUSINESS_DATE_XPATH)
        if date_parts:
            published = _parse_utc_z_datetime(date_parts[0].strip())
        else:
            logger.debug("No datetime found in business card", title=title)
            published = datetime.now(timezone.utc)

        articles.append(
            Article(
                title=title,
                url=url,
                published=published,
                source="reuters_jp",
                category="business",
                metadata={"scraper": "reuters_jp_html", "section": "business"},
            )
        )

    logger.info("Business page parsed", article_count=len(articles))
    return articles


def _fetch_section(
    section_name: str,
    section_url: str,
    config: ScraperConfig,
) -> list[Article]:
    """Fetch and parse a single Reuters Japan section page.

    Parameters
    ----------
    section_name : str
        Section key, either ``'markets'`` or ``'business'``.
    section_url : str
        Full URL of the section page.
    config : ScraperConfig
        Scraper configuration for timeout and delay settings.

    Returns
    -------
    list[Article]
        Parsed articles, or empty list on any HTTP / network error.
    """
    parser_map = {
        "markets": _parse_markets_page,
        "business": _parse_business_page,
    }
    parse_fn = parser_map.get(section_name)
    if parse_fn is None:
        logger.warning("Unknown Reuters JP section", section=section_name)
        return []

    logger.info("Fetching Reuters JP section", section=section_name, url=section_url)

    try:
        with httpx.Client(timeout=config.request_timeout) as client:
            html = fetch_html(section_url, client, headers=JP_DEFAULT_HEADERS)
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "HTTP error fetching Reuters JP section",
            section=section_name,
            url=section_url,
            status_code=exc.response.status_code,
        )
        return []
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        logger.warning(
            "Network error fetching Reuters JP section",
            section=section_name,
            url=section_url,
            error=str(exc),
        )
        return []
    except Exception as exc:
        logger.warning(
            "Unexpected error fetching Reuters JP section",
            section=section_name,
            url=section_url,
            error=str(exc),
        )
        return []

    articles = parse_fn(html)
    max_per_source = config.max_articles_per_source
    return articles[:max_per_source]


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def collect_news(config: ScraperConfig | None = None) -> list[Article]:
    """Collect recent news articles from Reuters Japan.

    Fetches the ``/markets/`` and ``/business/`` pages in parallel using
    :class:`~concurrent.futures.ThreadPoolExecutor` with 2 workers.

    The recommended request delay for Reuters Japan is 2.0 seconds.  If the
    caller provides a config with a shorter delay, the configured value is
    used as-is.

    On HTTP 429 (Too Many Requests) or 403 (Forbidden), the affected section
    returns an empty list (graceful degradation) so the other section's
    results are still usable.

    Parameters
    ----------
    config : ScraperConfig | None, optional
        Scraper configuration.  If ``None``, a default config with
        ``request_delay=2.0`` is used.

    Returns
    -------
    list[Article]
        List of collected articles from both sections, deduplicated by URL.

    Examples
    --------
    >>> from news_scraper.reuters_jp import collect_news
    >>> from news_scraper.types import ScraperConfig
    >>> config = ScraperConfig(max_articles_per_source=10)
    >>> # In tests this is mocked to avoid real HTTP calls
    >>> articles = collect_news(config=config)
    >>> isinstance(articles, list)
    True
    """
    if config is None:
        # Use a longer default delay for Reuters Japan to avoid 429
        config = ScraperConfig(request_delay=_REUTERS_JP_DEFAULT_DELAY)

    sections = list(REUTERS_JP_SECTIONS.items())

    logger.info(
        "Starting Reuters JP news collection",
        sections=[s for s, _ in sections],
        max_articles_per_source=config.max_articles_per_source,
    )

    all_articles: list[Article] = []

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(
                _fetch_section, section_name, section_url, config
            ): section_name
            for section_name, section_url in sections
        }
        for future in as_completed(futures):
            section_name = futures[future]
            try:
                articles = future.result()
                all_articles.extend(articles)
                logger.info(
                    "Reuters JP section complete",
                    section=section_name,
                    count=len(articles),
                )
            except Exception as exc:
                logger.error(
                    "Reuters JP section future raised unexpectedly",
                    section=section_name,
                    error=str(exc),
                    exc_info=True,
                )

    deduplicated = deduplicate_by_url(all_articles)

    logger.info(
        "Reuters JP news collection complete",
        total_articles=len(deduplicated),
    )
    return deduplicated
