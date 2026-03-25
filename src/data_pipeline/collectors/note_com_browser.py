"""Playwright async wrapper for reading note.com articles.

Provides ``NoteComBrowser``, an async context manager that wraps
Playwright to scrape public note.com articles. Handles article listing
via "load more" pagination, paywall detection, JSON-LD metadata
extraction, and body text parsing.

Examples
--------
>>> from data_pipeline.collectors.note_com_browser import NoteComBrowser
>>>
>>> async with NoteComBrowser(headless=True) as browser:
...     urls = await browser.list_article_urls("username", max_pages=5)
...     for url in urls:
...         article = await browser.scrape_article(url)
...         if article:
...             print(article.title)
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy Playwright import
# ---------------------------------------------------------------------------


def _async_playwright() -> Any:
    """Import and return ``async_playwright`` from the playwright package.

    Returns
    -------
    Any
        The ``async_playwright`` context manager object.

    Raises
    ------
    ImportError
        If the ``playwright`` package is not installed.
    """
    try:
        from playwright.async_api import (  # type: ignore[import-not-found]
            async_playwright,
        )

        return async_playwright()
    except ImportError as exc:
        raise ImportError(
            "playwright is not installed. "
            "Install with: uv add playwright && playwright install chromium"
        ) from exc


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class NoteArticle:
    """Scraped note.com article data.

    Attributes
    ----------
    url : str
        Article URL.
    title : str
        Article title.
    body_text : str
        Full body text (paragraphs joined with double newlines).
    author : str | None
        Author name, if available.
    published_at : datetime | None
        Publication datetime, if available.
    hashtags : list[str]
        Hashtags attached to the article.
    like_count : int | None
        Number of likes, if available.
    """

    url: str
    title: str
    body_text: str
    author: str | None = None
    published_at: datetime | None = None
    hashtags: list[str] = field(default_factory=list)
    like_count: int | None = None


# ---------------------------------------------------------------------------
# NoteComBrowser
# ---------------------------------------------------------------------------


class NoteComBrowser:
    """note.com article scraper powered by Playwright.

    Use as an async context manager to ensure proper resource cleanup:

        async with NoteComBrowser(headless=True) as browser:
            urls = await browser.list_article_urls("username")
            for url in urls:
                article = await browser.scrape_article(url)

    Parameters
    ----------
    headless : bool
        Whether to run the browser in headless mode.
    request_delay : float
        Base delay in seconds between requests (anti-detection).

    Attributes
    ----------
    _headless : bool
        Headless mode flag.
    _request_delay : float
        Base delay between operations.
    _playwright : Any | None
        Playwright instance (set on ``__aenter__``).
    _browser : Any | None
        Browser instance.
    _page : Any | None
        Active page used for scraping.
    """

    _SELECTORS: ClassVar[dict[str, str]] = {
        "article_links": 'a[href*="/n/"]',
        "load_more": 'button:has-text("もっとみる")',
        "article_body": ".note-common-styles__textnote-body",
        "paywall_price": 'button:text-matches("¥")',
        "paywall_purchase": 'button:has-text("購入手続きへ")',
        "json_ld": 'script[type="application/ld+json"]',
        "hashtags": 'a[href*="/hashtag/"]',
    }

    _TIMEOUT_MS: int = 30_000

    def __init__(
        self,
        *,
        headless: bool = True,
        request_delay: float = 2.0,
    ) -> None:
        self._headless = headless
        self._request_delay = request_delay
        self._playwright: Any | None = None
        self._browser: Any | None = None
        self._page: Any | None = None

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> NoteComBrowser:
        """Start Playwright, launch browser, and create a page.

        Uses ``channel="chrome"`` to reduce bot-detection risk.

        Returns
        -------
        NoteComBrowser
            Self, ready for scraping operations.
        """
        logger.debug("note_com_browser_starting headless=%s", self._headless)

        pw = await _async_playwright().start()
        self._playwright = pw

        # AIDEV-NOTE: Use channel="chrome" to launch the user's installed
        # Chrome browser instead of Playwright's bundled Chromium.  This
        # reduces the risk of bot detection.
        try:
            browser = await pw.chromium.launch(
                headless=self._headless,
                channel="chrome",
            )
        except Exception:
            logger.warning(
                "chrome_channel_launch_failed_falling_back_to_chromium",
            )
            browser = await pw.chromium.launch(headless=self._headless)

        self._browser = browser
        self._page = await browser.new_page()

        logger.info("note_com_browser_started")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Shut down browser resources.

        Parameters
        ----------
        exc_type : type[BaseException] | None
            Exception type, if any.
        exc_val : BaseException | None
            Exception value, if any.
        exc_tb : Any
            Traceback, if any.
        """
        await self.close()

    async def close(self) -> None:
        """Release all Playwright resources.

        Safe to call multiple times -- subsequent calls are no-ops.
        """
        if self._page is not None:
            await self._page.close()
            self._page = None

        if self._browser is not None:
            await self._browser.close()
            self._browser = None

        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

        logger.debug("note_com_browser_closed")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def list_article_urls(
        self,
        username: str,
        *,
        max_pages: int = 10,
    ) -> list[str]:
        """List article URLs from a note.com user's profile page.

        Navigates to ``https://note.com/{username}`` and clicks the
        "load more" button up to ``max_pages`` times to discover articles.

        Parameters
        ----------
        username : str
            note.com username (without ``@``).
        max_pages : int
            Maximum number of "load more" clicks.

        Returns
        -------
        list[str]
            Deduplicated list of article URLs.
        """
        assert self._page is not None

        profile_url = f"https://note.com/{username}"
        logger.info(
            "listing_article_urls username=%s profile_url=%s max_pages=%d",
            username,
            profile_url,
            max_pages,
        )

        try:
            await self._page.goto(
                profile_url,
                timeout=self._TIMEOUT_MS,
                wait_until="load",
            )
            # Wait for article links to render in the DOM
            try:
                await self._page.wait_for_selector(
                    self._SELECTORS["article_links"],
                    timeout=15_000,
                )
            except Exception:
                logger.debug("no_article_links_found_after_wait username=%s", username)
        except Exception:
            logger.error(
                "profile_page_navigation_failed username=%s",
                username,
                exc_info=True,
            )
            return []

        # Click "load more" button up to max_pages times
        for page_idx in range(max_pages):
            try:
                load_more_btn = self._page.locator(
                    self._SELECTORS["load_more"],
                )
                if await load_more_btn.count() == 0:
                    logger.debug(
                        "load_more_button_not_found pages_loaded=%d",
                        page_idx,
                    )
                    break

                if not await load_more_btn.first.is_enabled():
                    logger.debug(
                        "load_more_button_disabled pages_loaded=%d",
                        page_idx,
                    )
                    break

                await load_more_btn.first.click()
                logger.debug("load_more_clicked page_index=%d", page_idx)
                await self._delay()
            except Exception:
                logger.debug(
                    "load_more_click_failed page_index=%d",
                    page_idx,
                    exc_info=True,
                )
                break

        # Extract all article URLs
        link_elements = await self._page.query_selector_all(
            self._SELECTORS["article_links"],
        )

        seen: set[str] = set()
        urls: list[str] = []

        for link_el in link_elements:
            href = await link_el.get_attribute("href")
            if href is None:
                continue

            # Normalize to absolute URL
            if href.startswith("/"):
                href = f"https://note.com{href}"

            # Filter: only article URLs (pattern: /n/xxxxx)
            if "/n/" not in href:
                continue

            if href not in seen:
                seen.add(href)
                urls.append(href)

        logger.info(
            "article_urls_listed username=%s total_urls=%d",
            username,
            len(urls),
        )
        return urls

    async def scrape_article(self, url: str) -> NoteArticle | None:
        """Scrape a single note.com article.

        Navigates to the article URL, checks for paywall, and extracts
        the article content if it is free.

        Parameters
        ----------
        url : str
            Full URL of the note.com article.

        Returns
        -------
        NoteArticle | None
            Parsed article data, or ``None`` if the article is paid
            or an error occurred.
        """
        assert self._page is not None

        logger.info("scraping_article url=%s", url)

        try:
            await self._page.goto(
                url,
                timeout=self._TIMEOUT_MS,
                wait_until="load",
            )
            await self._delay()
        except Exception:
            logger.error(
                "article_navigation_failed url=%s",
                url,
                exc_info=True,
            )
            return None

        try:
            # Check paywall
            if await self.is_paid():
                logger.info("article_is_paid_skipping url=%s", url)
                return None

            # Extract data
            body_text = await self.extract_body_text()
            json_ld = await self.extract_json_ld()
            hashtags = await self._extract_hashtags()

            # Parse JSON-LD metadata
            title = json_ld.get("headline", "")
            if not title:
                # Fallback: use page title
                title = await self._page.title() or ""

            author = None
            author_data = json_ld.get("author")
            if isinstance(author_data, dict):
                author = author_data.get("name")

            published_at = self._parse_datetime(
                json_ld.get("datePublished"),
            )

            like_count = None
            interaction_stats = json_ld.get("interactionStatistic")
            if isinstance(interaction_stats, list):
                for stat in interaction_stats:
                    if isinstance(stat, dict) and stat.get(
                        "interactionType",
                    ) == {"@type": "LikeAction"}:
                        with contextlib.suppress(ValueError, TypeError):
                            like_count = int(
                                stat.get("userInteractionCount", 0),
                            )
            elif isinstance(interaction_stats, dict):
                with contextlib.suppress(ValueError, TypeError):
                    like_count = int(
                        interaction_stats.get("userInteractionCount", 0),
                    )

            article = NoteArticle(
                url=url,
                title=title,
                body_text=body_text,
                author=author,
                published_at=published_at,
                hashtags=hashtags,
                like_count=like_count,
            )

            logger.info(
                "article_scraped url=%s title=%s body_length=%d hashtag_count=%d",
                url,
                title,
                len(body_text),
                len(hashtags),
            )
            return article

        except Exception:
            logger.error(
                "article_scrape_failed url=%s",
                url,
                exc_info=True,
            )
            return None

    async def is_paid(self) -> bool:
        """Check whether the current page is a paid article.

        Looks for price buttons (containing "yen") or purchase buttons.

        Returns
        -------
        bool
            ``True`` if the article appears to be behind a paywall.
        """
        assert self._page is not None

        try:
            # Check for price button with yen symbol
            price_locator = self._page.locator(
                self._SELECTORS["paywall_price"],
            )
            if await price_locator.count() > 0:
                return True

            # Check for purchase button
            purchase_locator = self._page.locator(
                self._SELECTORS["paywall_purchase"],
            )
            if await purchase_locator.count() > 0:
                return True
        except Exception:
            logger.debug("paywall_check_failed", exc_info=True)

        return False

    async def extract_json_ld(self) -> dict[str, Any]:
        """Extract JSON-LD metadata from the current page.

        Looks for ``<script type="application/ld+json">`` elements and
        returns the ``BlogPosting`` entry from ``@graph`` if present.

        Returns
        -------
        dict[str, Any]
            Parsed JSON-LD ``BlogPosting`` data, or empty dict on failure.
        """
        assert self._page is not None

        try:
            script_elements = await self._page.query_selector_all(
                self._SELECTORS["json_ld"],
            )

            for script_el in script_elements:
                raw_text = await script_el.inner_text()
                if not raw_text.strip():
                    continue

                try:
                    data = json.loads(raw_text)
                except json.JSONDecodeError:
                    continue

                # Handle @graph structure
                if isinstance(data, dict) and "@graph" in data:
                    graph = data["@graph"]
                    if isinstance(graph, list):
                        for item in graph:
                            if (
                                isinstance(item, dict)
                                and item.get("@type") == "BlogPosting"
                            ):
                                return item

                # Handle direct BlogPosting
                if isinstance(data, dict) and data.get("@type") == "BlogPosting":
                    return data

                # Handle list of items
                if isinstance(data, list):
                    for item in data:
                        if (
                            isinstance(item, dict)
                            and item.get("@type") == "BlogPosting"
                        ):
                            return item

        except Exception:
            logger.debug("json_ld_extraction_failed", exc_info=True)

        return {}

    async def extract_body_text(self) -> str:
        """Extract article body text from the current page.

        Collects all ``<p>`` elements within the article body container
        and joins their text content with double newlines.

        Returns
        -------
        str
            Article body text with paragraphs separated by ``\\n\\n``.
        """
        assert self._page is not None

        try:
            body_selector = self._SELECTORS["article_body"]

            # Wait for the body container to appear
            await self._page.wait_for_selector(
                body_selector,
                timeout=self._TIMEOUT_MS,
            )

            paragraphs = await self._page.eval_on_selector_all(
                f"{body_selector} p",
                "elements => elements.map(el => el.textContent || '')",
            )

            # Filter out empty paragraphs and join
            text_parts = [p.strip() for p in paragraphs if p.strip()]
            return "\n\n".join(text_parts)

        except Exception:
            logger.debug("body_text_extraction_failed", exc_info=True)
            return ""

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _extract_hashtags(self) -> list[str]:
        """Extract hashtag texts from the current page.

        Returns
        -------
        list[str]
            List of hashtag strings (without ``#`` prefix).
        """
        assert self._page is not None

        try:
            hashtag_elements = await self._page.query_selector_all(
                self._SELECTORS["hashtags"],
            )

            hashtags: list[str] = []
            for el in hashtag_elements:
                text = await el.inner_text()
                tag = text.strip().lstrip("#").strip()
                if tag and tag not in hashtags:
                    hashtags.append(tag)

            return hashtags
        except Exception:
            logger.debug("hashtag_extraction_failed", exc_info=True)
            return []

    async def _delay(self) -> None:
        """Sleep for ``request_delay`` plus random jitter.

        Adds a uniform random component of 0 to 0.5 seconds on top of
        the base ``request_delay``.
        """
        delay = self._request_delay + random.uniform(0, 0.5)
        await asyncio.sleep(delay)

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        """Parse an ISO 8601 datetime string.

        Parameters
        ----------
        value : str | None
            ISO 8601 datetime string, or ``None``.

        Returns
        -------
        datetime | None
            Parsed datetime, or ``None`` if parsing fails.
        """
        if not value:
            return None

        try:
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            logger.debug("datetime_parse_failed value=%s", value)
            return None


__all__ = ["NoteArticle", "NoteComBrowser"]
