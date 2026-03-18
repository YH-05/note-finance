"""JETRO category-page crawler using Playwright.

This module provides a ``JetroCategoryCrawler`` that uses Playwright to
render JETRO category pages (which rely on AJAX for article loading) and
extract article entries from the resulting DOM.

Classes
-------
CrawledEntry
    Immutable dataclass for a single crawled article entry.
JetroCategoryCrawler
    Playwright-based crawler for JETRO category pages.

Notes
-----
JETRO category pages (e.g. ``/biznewstop/asia/cn.html``) load article
lists via AJAX, so a headless browser is required.  The crawler attempts
``networkidle`` first, then falls back to ``domcontentloaded`` on timeout.

Examples
--------
>>> from news_scraper._jetro_crawler import JetroCategoryCrawler
>>> crawler = JetroCategoryCrawler()
>>> entries = crawler.crawl_all(
...     categories=["world"],
...     regions={"asia": ["cn"]},
... )
>>> isinstance(entries, list)
True
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from dataclasses import dataclass
from typing import Any

from lxml import html as lxml_html

from news_scraper._jetro_config import (
    JETRO_BASE_URL,
    JETRO_CATEGORY_URLS,
)
from news_scraper._logging import get_logger

logger = get_logger(__name__, module="jetro_crawler")

# ---------------------------------------------------------------------------
# Section mapping: section_id -> content_type label
# ---------------------------------------------------------------------------

_SECTION_MAP: dict[str, str] = {
    "cty_biznews": "ビジネス短信",
    "cty_special": "特集",
    "cty_areareports": "地域・分析レポート",
    "cty_reports": "調査レポート",
}
"""Mapping of HTML section ``id`` to JETRO content-type label.

Only sections that contain article links are included.  ``cty_events``
and other non-article sections are intentionally excluded.
"""


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CrawledEntry:
    """Immutable record for a single article entry extracted from a category page.

    Attributes
    ----------
    title : str
        Article title text.
    url : str
        Absolute URL of the article page.
    category : str
        Top-level category (``"world"``, ``"theme"``, ``"industry"``).
    subcategory : str
        Sub-category key (e.g. ``"cn"``, ``"asia"``, ``"export"``).
    content_type : str | None
        JETRO content type (e.g. ``"ビジネス短信"``), or ``None``.
    published : str | None
        Published-date string as shown on the page, or ``None``.

    Examples
    --------
    >>> entry = CrawledEntry(
    ...     title="テスト記事",
    ...     url="https://www.jetro.go.jp/biznews/2026/03/test.html",
    ...     category="world",
    ...     subcategory="cn",
    ...     content_type="ビジネス短信",
    ...     published="2026年03月18日",
    ... )
    >>> entry.title
    'テスト記事'
    """

    title: str
    url: str
    category: str
    subcategory: str
    content_type: str | None = None
    published: str | None = None


# ---------------------------------------------------------------------------
# Playwright import helper
# ---------------------------------------------------------------------------


def async_playwright() -> Any:
    """Import and return ``async_playwright`` from playwright.

    Returns
    -------
    Any
        The ``async_playwright`` context manager.

    Raises
    ------
    ImportError
        If playwright is not installed.
    """
    try:
        from playwright.async_api import (  # type: ignore[import-not-found]
            async_playwright as _async_playwright,
        )

        return _async_playwright()
    except ImportError as e:
        raise ImportError(
            "playwright is not installed. "
            "Install with: uv add playwright && playwright install chromium"
        ) from e


# ---------------------------------------------------------------------------
# Crawler class
# ---------------------------------------------------------------------------


class JetroCategoryCrawler:
    """Playwright-based crawler for JETRO category pages.

    Category pages load article lists via AJAX, so a headless browser is
    required to render the content before DOM extraction.

    Parameters
    ----------
    timeout_ms : int
        Playwright page-load timeout in milliseconds (default 30 000).
    headless : bool
        Whether to run the browser in headless mode (default ``True``).

    Examples
    --------
    >>> crawler = JetroCategoryCrawler(timeout_ms=60000)
    >>> entries = crawler.crawl_all(
    ...     categories=["world"],
    ...     regions={"asia": ["cn"]},
    ... )
    """

    def __init__(
        self,
        timeout_ms: int = 30_000,
        headless: bool = True,
    ) -> None:
        self._timeout_ms = timeout_ms
        self._headless = headless

    # ------------------------------------------------------------------
    # Static HTML extraction (testable without Playwright)
    # ------------------------------------------------------------------

    def _extract_section_entries_from_html(
        self,
        html_content: str,
        section_id: str,
        content_type: str,
        category: str,
        subcategory: str,
    ) -> list[CrawledEntry]:
        """Extract article entries from a single section of the rendered HTML.

        Parameters
        ----------
        html_content : str
            Full page HTML (already rendered by Playwright).
        section_id : str
            The ``id`` attribute of the section ``<div>``
            (e.g. ``"cty_biznews"``).
        content_type : str
            JETRO content-type label (e.g. ``"ビジネス短信"``).
        category : str
            Top-level category key.
        subcategory : str
            Sub-category key.

        Returns
        -------
        list[CrawledEntry]
            Extracted entries.  Empty list if the section is missing or empty.
        """
        entries: list[CrawledEntry] = []
        try:
            tree = lxml_html.fromstring(html_content)
        except Exception as exc:
            logger.warning(
                "Failed to parse HTML for section extraction",
                section_id=section_id,
                error=str(exc),
            )
            return entries

        # Locate the section container by its id
        section_elements = tree.cssselect(f"#{section_id}")
        if not section_elements:
            logger.debug(
                "Section not found in HTML",
                section_id=section_id,
            )
            return entries

        section = section_elements[0]

        # Find all <li> inside the section's article list
        list_items = section.cssselect(".elem_list_news li")
        if not list_items:
            # Fallback: try direct <li> children
            list_items = section.cssselect("ul li")

        for li in list_items:
            link_elements = li.cssselect("a")
            if not link_elements:
                continue

            link_el = link_elements[0]
            title = link_el.text_content().strip()
            href = link_el.get("href", "")

            if not title or not href:
                continue

            # Convert relative URL to absolute
            if href.startswith("/"):
                url = f"{JETRO_BASE_URL}{href}"
            elif href.startswith("http"):
                url = href
            else:
                url = f"{JETRO_BASE_URL}/{href}"

            # Extract date from <span class="date"> if present
            date_elements = li.cssselect("span.date")
            published = (
                date_elements[0].text_content().strip() if date_elements else None
            )

            entries.append(
                CrawledEntry(
                    title=title,
                    url=url,
                    category=category,
                    subcategory=subcategory,
                    content_type=content_type,
                    published=published,
                )
            )

        logger.debug(
            "Section entries extracted",
            section_id=section_id,
            content_type=content_type,
            count=len(entries),
        )
        return entries

    # ------------------------------------------------------------------
    # Playwright-based page loading
    # ------------------------------------------------------------------

    async def _load_page_html(
        self,
        url: str,
        browser: Any,
    ) -> str | None:
        """Load a page with Playwright and return rendered HTML.

        Attempts ``networkidle`` first; on timeout falls back to
        ``domcontentloaded``.

        Parameters
        ----------
        url : str
            URL to navigate to.
        browser : Any
            Playwright browser instance.

        Returns
        -------
        str | None
            Rendered HTML, or ``None`` on failure.
        """
        page = await browser.new_page()
        try:
            # Attempt 1: networkidle (waits for all AJAX to complete)
            try:
                await page.goto(
                    url,
                    timeout=self._timeout_ms,
                    wait_until="networkidle",
                )
                logger.debug("Page loaded with networkidle", url=url)
            except (TimeoutError, Exception) as exc:
                logger.warning(
                    "networkidle timeout, falling back to domcontentloaded",
                    url=url,
                    error=str(exc),
                )
                # Attempt 2: domcontentloaded (faster, may miss late AJAX)
                try:
                    await page.goto(
                        url,
                        timeout=self._timeout_ms,
                        wait_until="domcontentloaded",
                    )
                    logger.debug("Page loaded with domcontentloaded fallback", url=url)
                except (TimeoutError, Exception) as exc2:
                    logger.error(
                        "Both networkidle and domcontentloaded failed",
                        url=url,
                        error=str(exc2),
                    )
                    return None

            html_content: str = await page.content()
            return html_content

        finally:
            await page.close()

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def crawl_category_page(
        self,
        url: str,
        category: str,
        subcategory: str,
    ) -> list[CrawledEntry]:
        """Crawl a single JETRO category page and extract article entries.

        Parameters
        ----------
        url : str
            Full URL of the category page.
        category : str
            Top-level category key (``"world"``, ``"theme"``, ``"industry"``).
        subcategory : str
            Sub-category key (e.g. ``"cn"``, ``"asia"``).

        Returns
        -------
        list[CrawledEntry]
            All article entries found across all known sections on the page.
        """
        logger.info(
            "Crawling JETRO category page",
            url=url,
            category=category,
            subcategory=subcategory,
        )

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self._headless)
            try:
                html_content = await self._load_page_html(url, browser)
            finally:
                await browser.close()

        if not html_content:
            logger.warning("No HTML content retrieved", url=url)
            return []

        # Extract entries from each known section
        all_entries: list[CrawledEntry] = []
        for section_id, content_type in _SECTION_MAP.items():
            section_entries = self._extract_section_entries_from_html(
                html_content=html_content,
                section_id=section_id,
                content_type=content_type,
                category=category,
                subcategory=subcategory,
            )
            all_entries.extend(section_entries)

        logger.info(
            "Category page crawl complete",
            url=url,
            total_entries=len(all_entries),
        )
        return all_entries

    # ------------------------------------------------------------------
    # Private: build page URLs from categories + regions
    # ------------------------------------------------------------------

    @staticmethod
    def _build_page_urls(
        categories: list[str] | None,
        regions: dict[str, list[str]] | None,
    ) -> list[tuple[str, str, str]]:
        """Build a list of (url, category, subcategory) tuples to crawl.

        Parameters
        ----------
        categories : list[str] | None
            Category groups to crawl (``"world"``, ``"theme"``, ``"industry"``).
            When ``regions`` is also provided, only ``"world"`` entries from
            ``categories`` are expanded using ``regions``.
        regions : dict[str, list[str]] | None
            Mapping of JETRO region key to list of country codes.
            E.g. ``{"asia": ["cn", "kr"]}``.
            Only used for ``"world"`` category.

        Returns
        -------
        list[tuple[str, str, str]]
            Each tuple is ``(url, category_group, subcategory_key)``.
        """
        targets: list[tuple[str, str, str]] = []

        if not categories:
            return targets

        for cat_group in categories:
            group_urls = JETRO_CATEGORY_URLS.get(cat_group, {})
            if not group_urls:
                logger.warning(
                    "Unknown category group, skipping",
                    category=cat_group,
                )
                continue

            if cat_group == "world" and regions:
                # Build country-specific URLs from regions
                for region_key, country_codes in regions.items():
                    base_url = group_urls.get(region_key)
                    if not base_url:
                        logger.warning(
                            "Unknown region key, skipping",
                            category=cat_group,
                            region=region_key,
                        )
                        continue
                    for country_code in country_codes:
                        page_url = f"{base_url.rstrip('/')}/{country_code}.html"
                        targets.append((page_url, cat_group, country_code))
            else:
                # Use the region/subcategory URLs directly
                for subcat_key, url in group_urls.items():
                    targets.append((url, cat_group, subcat_key))

        return targets

    # ------------------------------------------------------------------
    # Private async orchestrator
    # ------------------------------------------------------------------

    async def _crawl_all_async(
        self,
        categories: list[str] | None,
        regions: dict[str, list[str]] | None,
    ) -> list[CrawledEntry]:
        """Crawl multiple category pages (async implementation).

        Parameters
        ----------
        categories : list[str] | None
            Category groups to crawl.
        regions : dict[str, list[str]] | None
            Region-to-country mapping for world category.

        Returns
        -------
        list[CrawledEntry]
            Combined entries from all crawled pages.
        """
        targets = self._build_page_urls(categories, regions)
        if not targets:
            return []

        all_entries: list[CrawledEntry] = []
        for url, cat_group, subcat in targets:
            entries = await self.crawl_category_page(
                url=url,
                category=cat_group,
                subcategory=subcat,
            )
            all_entries.extend(entries)

        return all_entries

    # ------------------------------------------------------------------
    # Public sync wrapper
    # ------------------------------------------------------------------

    def crawl_all(
        self,
        categories: list[str] | None = None,
        regions: dict[str, list[str]] | None = None,
    ) -> list[CrawledEntry]:
        """Crawl multiple JETRO category pages (synchronous wrapper).

        This method wraps the async implementation with ``asyncio.run()``
        so it can be called from synchronous code such as ``collect_news()``.

        Parameters
        ----------
        categories : list[str] | None
            Category groups to crawl (``"world"``, ``"theme"``, ``"industry"``).
        regions : dict[str, list[str]] | None
            Mapping of JETRO region key to list of country codes.
            E.g. ``{"asia": ["cn", "kr"]}``.  Only relevant when
            ``"world"`` is in ``categories``.

        Returns
        -------
        list[CrawledEntry]
            Combined entries from all crawled pages.

        Examples
        --------
        >>> crawler = JetroCategoryCrawler()
        >>> entries = crawler.crawl_all(
        ...     categories=["world"],
        ...     regions={"asia": ["cn"]},
        ... )
        >>> isinstance(entries, list)
        True
        """
        if not categories:
            return []

        logger.info(
            "Starting JETRO category crawl",
            categories=categories,
            regions=regions,
        )

        try:
            # Use asyncio.run() for sync wrapper
            # If already in an event loop, use the loop directly
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None and loop.is_running():
                # Already in an async context: run in a thread
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = pool.submit(
                        asyncio.run,
                        self._crawl_all_async(categories, regions),
                    ).result()
                return result  # type: ignore[return-value]
            else:
                return asyncio.run(self._crawl_all_async(categories, regions))

        except Exception as exc:
            logger.error(
                "JETRO category crawl failed",
                error=str(exc),
                exc_info=True,
            )
            return []


__all__ = ["CrawledEntry", "JetroCategoryCrawler"]
