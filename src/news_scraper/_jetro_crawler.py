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
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from lxml import html as lxml_html

from news_scraper._jetro_config import (
    JETRO_BASE_URL,
    JETRO_CATEGORY_URLS,
)
from news_scraper._logging import get_logger

_JETRO_HOST = urlparse(JETRO_BASE_URL).netloc
_SAFE_CODE_RE = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")

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

    def _extract_section_entries_from_tree(
        self,
        tree: Any,
        section_id: str,
        content_type: str,
        category: str,
        subcategory: str,
    ) -> list[CrawledEntry]:
        """Extract article entries from a single section of a parsed HTML tree.

        Parameters
        ----------
        tree : Any
            Pre-parsed lxml HTML element tree.
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

            # Convert relative URL to absolute with domain validation
            parsed_href = urlparse(href)
            if parsed_href.scheme and parsed_href.scheme not in ("http", "https"):
                continue  # Skip javascript:, data:, etc.
            if href.startswith("/"):
                url = f"{JETRO_BASE_URL}{href}"
            elif href.startswith("http"):
                if parsed_href.netloc != _JETRO_HOST:
                    logger.debug("Skipping off-domain URL", href=href)
                    continue
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

    @staticmethod
    def _resolve_href(href: str) -> str | None:
        """Resolve an href to an absolute JETRO URL, or None if invalid.

        Parameters
        ----------
        href : str
            The href attribute value from an ``<a>`` element.

        Returns
        -------
        str | None
            Absolute URL, or ``None`` if the href should be skipped.
        """
        parsed = urlparse(href)
        if parsed.scheme and parsed.scheme not in ("http", "https"):
            return None
        if href.startswith("/"):
            return f"{JETRO_BASE_URL}{href}"
        if href.startswith("http"):
            return href if parsed.netloc == _JETRO_HOST else None
        return f"{JETRO_BASE_URL}/{href}"

    def _extract_dd_entries(
        self,
        container: Any,
        category: str,
        subcategory: str,
        content_type: str,
    ) -> list[CrawledEntry]:
        """Extract entries from ``<dd><a>`` + ``<dt>`` pairs in a container.

        Parameters
        ----------
        container : Any
            lxml element containing ``<dl>`` with ``<dt>``/``<dd>`` pairs.
        category, subcategory, content_type : str
            Metadata for the created entries.

        Returns
        -------
        list[CrawledEntry]
            Extracted entries.
        """
        entries: list[CrawledEntry] = []
        dd_links = container.cssselect("dd a")
        dt_elements = container.cssselect("dt")
        dates = [dt.text_content().strip() for dt in dt_elements]

        for i, dd_link in enumerate(dd_links):
            title = dd_link.text_content().strip()
            href = dd_link.get("href", "")
            if not title or not href or title == "もっと見る":
                continue
            url = self._resolve_href(href)
            if url is None:
                continue
            published = dates[i] if i < len(dates) else None
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
        return entries

    def _extract_li_entries(
        self,
        container: Any,
        category: str,
        subcategory: str,
        content_type: str,
    ) -> list[CrawledEntry]:
        """Fallback extraction from ``<li><a>`` elements (e.g. 特集 section).

        Parameters
        ----------
        container : Any
            lxml element containing ``<ul><li><a>`` links.
        category, subcategory, content_type : str
            Metadata for the created entries.

        Returns
        -------
        list[CrawledEntry]
            Extracted entries.
        """
        entries: list[CrawledEntry] = []
        for link_el in container.cssselect("li a"):
            title = link_el.text_content().strip()
            href = link_el.get("href", "")
            if not title or not href or title == "もっと見る":
                continue
            url = self._resolve_href(href)
            if url is None:
                continue
            entries.append(
                CrawledEntry(
                    title=title,
                    url=url,
                    category=category,
                    subcategory=subcategory,
                    content_type=content_type,
                    published=None,
                )
            )
        return entries

    def _extract_entries_by_heading(
        self,
        tree: Any,
        category: str,
        subcategory: str,
    ) -> list[CrawledEntry]:
        """Extract article entries by finding h2 headings and their next sibling.

        The current JETRO country pages use a structure where ``<h2>`` is
        wrapped in ``div.elem_heading_lv2``, and articles appear in the
        next sibling ``<div>`` as ``<dt>`` (date) + ``<dd>`` (link) pairs.

        Parameters
        ----------
        tree : Any
            Pre-parsed lxml HTML element tree.
        category : str
            Top-level category key.
        subcategory : str
            Sub-category key.

        Returns
        -------
        list[CrawledEntry]
            Extracted entries from all recognized sections.
        """
        entries: list[CrawledEntry] = []

        heading_map: dict[str, str] = {
            "ビジネス短信": "ビジネス短信",
            "地域・分析レポート": "地域・分析レポート",
            "調査レポート": "調査レポート",
            "特集": "特集",
        }

        for h2 in tree.cssselect("h2"):
            heading_text = h2.text_content().strip()
            content_type = heading_map.get(heading_text)
            if not content_type:
                continue

            heading_div = h2.getparent()
            if heading_div is None:
                continue
            article_container = heading_div.getnext()
            if article_container is None:
                continue

            section_entries = self._extract_dd_entries(
                article_container,
                category,
                subcategory,
                content_type,
            )
            if not section_entries:
                section_entries = self._extract_li_entries(
                    article_container,
                    category,
                    subcategory,
                    content_type,
                )

            entries.extend(section_entries)
            logger.debug(
                "Heading-based entries extracted",
                heading=heading_text,
                content_type=content_type,
                count=len(section_entries),
            )

        logger.info(
            "Heading-based extraction complete",
            category=category,
            subcategory=subcategory,
            total_entries=len(entries),
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
            except Exception as exc:
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
                except Exception as exc2:
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
        browser: Any = None,
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
        browser : Any, optional
            Playwright browser instance.  When ``None`` a temporary browser
            is launched and closed within this call.

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

        own_browser = browser is None
        pw_ctx = None
        try:
            if own_browser:
                pw_ctx = async_playwright()
                pw = await pw_ctx.__aenter__()
                browser = await pw.chromium.launch(headless=self._headless)

            html_content = await self._load_page_html(url, browser)
        finally:
            if own_browser:
                if browser is not None:
                    await browser.close()
                if pw_ctx is not None:
                    await pw_ctx.__aexit__(None, None, None)

        if not html_content:
            logger.warning("No HTML content retrieved", url=url)
            return []

        # Parse HTML once, then extract entries from each section
        try:
            tree = lxml_html.fromstring(html_content)
        except Exception as exc:
            logger.warning("Failed to parse HTML", url=url, error=str(exc))
            return []

        all_entries: list[CrawledEntry] = []

        # Strategy 1: Legacy section-id based extraction
        for section_id, content_type in _SECTION_MAP.items():
            section_entries = self._extract_section_entries_from_tree(
                tree=tree,
                section_id=section_id,
                content_type=content_type,
                category=category,
                subcategory=subcategory,
            )
            all_entries.extend(section_entries)

        # Strategy 2: h2 heading-based extraction (current page structure)
        if not all_entries:
            all_entries = self._extract_entries_by_heading(
                tree=tree,
                category=category,
                subcategory=subcategory,
            )

        logger.info(
            "Category page crawl complete",
            url=url,
            total_entries=len(all_entries),
        )
        return all_entries

    # ------------------------------------------------------------------
    # Archive page crawling (paginated list pages)
    # ------------------------------------------------------------------

    def _extract_archive_entries(
        self,
        tree: Any,
        category: str,
        subcategory: str,
        content_type: str,
    ) -> list[CrawledEntry]:
        """Extract article entries from an archive list page.

        Archive pages use ``<li>`` elements containing a date ``<span>``
        and an ``<a>`` link.

        Parameters
        ----------
        tree : Any
            Pre-parsed lxml HTML element tree.
        category : str
            Top-level category key.
        subcategory : str
            Sub-category key.
        content_type : str
            JETRO content-type label.

        Returns
        -------
        list[CrawledEntry]
            Extracted entries.
        """
        entries: list[CrawledEntry] = []

        # Archive pages: <li> contains <div class="date"> + <div class="title">
        # where <div class="title"> > <span> > <a> holds the article link.
        for li in tree.cssselect("li"):
            title_div = li.cssselect("div.title")
            if not title_div:
                continue

            links = title_div[0].cssselect("a")
            if not links:
                continue

            link_el = links[0]
            href = link_el.get("href", "")
            if not href or not href.startswith("/"):
                continue

            title = link_el.text_content().strip()
            if not title:
                continue

            url = f"{JETRO_BASE_URL}{href}"

            # Extract date from <div class="date">
            date_div = li.cssselect("div.date")
            published = date_div[0].text_content().strip() if date_div else None

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

        return entries

    async def crawl_archive_pages(
        self,
        url: str,
        category: str,
        subcategory: str,
        content_type: str,
        max_pages: int = 3,
        browser: Any = None,
    ) -> list[CrawledEntry]:
        """Crawl a paginated archive page with JavaScript pagination.

        Navigates to the archive URL, extracts entries from the first page,
        then clicks the "次へ" button to load subsequent pages.

        Parameters
        ----------
        url : str
            Full URL of the archive page.
        category : str
            Top-level category key.
        subcategory : str
            Sub-category key.
        content_type : str
            JETRO content-type label (e.g. ``"ビジネス短信"``).
        max_pages : int
            Maximum number of pages to crawl (default 3).
        browser : Any, optional
            Playwright browser instance.

        Returns
        -------
        list[CrawledEntry]
            All extracted entries across pages.
        """
        logger.info(
            "Crawling JETRO archive pages",
            url=url,
            content_type=content_type,
            max_pages=max_pages,
        )

        own_browser = browser is None
        pw_ctx = None
        all_entries: list[CrawledEntry] = []

        try:
            if own_browser:
                pw_ctx = async_playwright()
                pw = await pw_ctx.__aenter__()
                browser = await pw.chromium.launch(headless=self._headless)

            page = await browser.new_page()
            try:
                await page.goto(
                    url,
                    timeout=self._timeout_ms,
                    wait_until="networkidle",
                )

                for page_num in range(max_pages):
                    html_content = await page.content()
                    try:
                        tree = lxml_html.fromstring(html_content)
                    except Exception as exc:
                        logger.warning(
                            "Failed to parse archive HTML",
                            page=page_num + 1,
                            error=str(exc),
                        )
                        break

                    entries = self._extract_archive_entries(
                        tree,
                        category,
                        subcategory,
                        content_type,
                    )
                    if not entries:
                        logger.debug(
                            "No entries on archive page, stopping",
                            page=page_num + 1,
                        )
                        break

                    all_entries.extend(entries)
                    logger.info(
                        "Archive page extracted",
                        page=page_num + 1,
                        entries=len(entries),
                        total=len(all_entries),
                    )

                    # Click "次へ" for next page (skip on last page)
                    if page_num < max_pages - 1:
                        next_button = page.locator("a", has_text="次へ")
                        if await next_button.count() == 0:
                            logger.debug("No next button found, stopping")
                            break
                        await next_button.click()
                        # Wait for content to update
                        await page.wait_for_load_state("networkidle")
                        await page.wait_for_timeout(1000)

            finally:
                await page.close()

        finally:
            if own_browser:
                if browser is not None:
                    await browser.close()
                if pw_ctx is not None:
                    await pw_ctx.__aexit__(None, None, None)

        logger.info(
            "Archive crawl complete",
            url=url,
            total_entries=len(all_entries),
            pages_crawled=min(max_pages, len(all_entries) // 30 + 1),
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
                        if not _SAFE_CODE_RE.match(country_code):
                            logger.warning(
                                "Invalid country code, skipping",
                                code=country_code,
                            )
                            continue
                        page_url = f"{base_url.rstrip('/')}/{country_code}/"
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

        Launches a single browser instance and crawls pages concurrently
        with a semaphore to limit simultaneous requests.

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

        sem = asyncio.Semaphore(3)

        async def _crawl_with_sem(
            url: str, cat_group: str, subcat: str, browser: Any
        ) -> list[CrawledEntry]:
            async with sem:
                return await self.crawl_category_page(
                    url=url,
                    category=cat_group,
                    subcategory=subcat,
                    browser=browser,
                )

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self._headless)
            try:
                tasks = [
                    _crawl_with_sem(url, cat, sub, browser) for url, cat, sub in targets
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
            finally:
                await browser.close()

        all_entries: list[CrawledEntry] = []
        for result in results:
            if isinstance(result, BaseException):
                logger.warning("Page crawl failed", error=str(result))
            else:
                all_entries.extend(result)

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
