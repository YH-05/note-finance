"""SPA-based intermediate base class for report scrapers.

Provides ``SpaReportScraper``, which implements ``fetch_listing()`` using
Scrapling's DynamicFetcher for JavaScript rendering via Playwright. Handles
Cloudflare Turnstile automatically and waits for JS-rendered content.

Scrapling and Playwright are **optional** dependencies. If not installed,
a warning is logged and the scraper raises ``ImportError`` only when
``fetch_listing()`` is called.

Classes
-------
SpaReportScraper
    Intermediate ABC using Scrapling DynamicFetcher for SPA sources.

Examples
--------
>>> class MyScraper(SpaReportScraper):
...     listing_url = "https://example.com/spa-research"
...     article_selector = "div.article-list a"
...     @property
...     def source_key(self) -> str:
...         return "example_spa"
...     @property
...     def source_config(self):
...         ...
...     def parse_listing_item(self, element, base_url):
...         return None
...     async def extract_report(self, meta):
...         return None
"""

from __future__ import annotations

import warnings
from abc import abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import urlparse

from report_scraper._logging import get_logger
from report_scraper.core.base_scraper import BaseReportScraper
from report_scraper.exceptions import FetchError
from report_scraper.scrapers._scraper_utils import (
    extract_links_by_css as _extract_links_by_css,
)
from report_scraper.scrapers._scraper_utils import (
    find_pdf_links as _find_pdf_links,
)
from report_scraper.scrapers._scraper_utils import (
    is_pdf_url as _is_pdf_url,
)
from report_scraper.scrapers._scraper_utils import (
    resolve_url as _resolve_url,
)

if TYPE_CHECKING:
    from report_scraper.types import ReportMetadata, ScrapedReport, SourceConfig

# ---------------------------------------------------------------------------
# Optional Scrapling DynamicFetcher import
# ---------------------------------------------------------------------------

_dynamic_fetcher_available = False

try:
    from scrapling import DynamicFetcher  # type: ignore[import-untyped]

    _dynamic_fetcher_available = True
except ImportError:
    DynamicFetcher = None  # type: ignore[assignment, misc]
    warnings.warn(
        "scrapling DynamicFetcher is not installed. SpaReportScraper will not "
        "function. Install with: uv add scrapling && playwright install",
        ImportWarning,
        stacklevel=2,
    )

logger = get_logger(__name__, module="spa_scraper")

# ---------------------------------------------------------------------------
# SpaReportScraper
# ---------------------------------------------------------------------------


class SpaReportScraper(BaseReportScraper):
    """Intermediate base class for SPA (Single Page Application) report scrapers.

    Uses Scrapling's ``DynamicFetcher`` which wraps Playwright for full
    JavaScript rendering. Automatically handles Cloudflare Turnstile
    challenges and waits for JS-rendered content to appear.

    Subclasses define CSS selectors for listing pages and implement
    ``parse_listing_item()`` and ``extract_report()``.

    Attributes
    ----------
    listing_url : str
        URL of the page listing available reports.
    article_selector : str
        CSS selector to find article/report items on the listing page.
    wait_selector : str | None
        Optional CSS selector to wait for before extracting content.
        If set, DynamicFetcher waits until this element appears in the DOM.

    Examples
    --------
    >>> class ExampleSpaScraper(SpaReportScraper):
    ...     listing_url = "https://example.com/spa-research"
    ...     article_selector = "div.articles a.report-link"
    ...     wait_selector = "div.content-loaded"
    ...     @property
    ...     def source_key(self) -> str:
    ...         return "example_spa"
    ...     @property
    ...     def source_config(self):
    ...         return SourceConfig(
    ...             key="example_spa", name="Example SPA", tier="sell_side",
    ...             listing_url="https://example.com/spa-research",
    ...             rendering="playwright",
    ...         )
    ...     def parse_listing_item(self, element, base_url):
    ...         return None
    ...     async def extract_report(self, meta):
    ...         return None
    """

    listing_url: ClassVar[str]
    article_selector: ClassVar[str]
    wait_selector: str | None = None

    # -- Abstract interface --------------------------------------------------

    @property
    @abstractmethod
    def source_key(self) -> str:
        """Unique identifier for this source."""
        ...

    @property
    @abstractmethod
    def source_config(self) -> SourceConfig:
        """Configuration for this source."""
        ...

    @abstractmethod
    def parse_listing_item(
        self,
        element: Any,
        base_url: str,
    ) -> ReportMetadata | None:
        """Parse a single listing element into ReportMetadata.

        Parameters
        ----------
        element : Any
            A Scrapling ``Adaptor`` element matched by ``article_selector``.
        base_url : str
            Base URL for resolving relative links.

        Returns
        -------
        ReportMetadata | None
            Parsed metadata, or ``None`` if the element should be skipped.
        """
        ...

    @abstractmethod
    async def extract_report(self, meta: ReportMetadata) -> ScrapedReport | None:
        """Extract full content from a single report."""
        ...

    # -- Fetch listing implementation ----------------------------------------

    async def fetch_listing(self) -> list[ReportMetadata]:
        """Fetch the listing page using DynamicFetcher and extract report metadata.

        Uses DynamicFetcher (Playwright) to render JavaScript content, then
        applies ``article_selector`` to find report items. Each matched element
        is passed to ``parse_listing_item()`` for conversion.

        Returns
        -------
        list[ReportMetadata]
            Parsed report metadata from the listing page.

        Raises
        ------
        ImportError
            If scrapling DynamicFetcher or Playwright is not installed.
        FetchError
            If the HTTP request or JS rendering fails.
        """
        if not _dynamic_fetcher_available:
            msg = (
                "scrapling DynamicFetcher is required for SpaReportScraper. "
                "Install with: uv add scrapling && playwright install"
            )
            raise ImportError(msg)

        # SSRF protection: validate listing_url scheme
        parsed_listing = urlparse(self.listing_url)
        if parsed_listing.scheme not in {"https", "http"}:
            raise FetchError(
                f"Invalid listing_url scheme: {parsed_listing.scheme}",
                url=self.listing_url,
            )

        logger.info(
            "Fetching SPA listing page with DynamicFetcher",
            source_key=self.source_key,
            url=self.listing_url,
            wait_selector=self.wait_selector,
        )

        try:
            if DynamicFetcher is None:
                raise ImportError(
                    "Scrapling DynamicFetcher is not installed. "
                    "Install with: uv add 'scrapling[fetchers]'"
                )
            fetcher = DynamicFetcher()
            # AIDEV-NOTE: DynamicFetcher.fetch() renders JS via Playwright
            # and handles Cloudflare Turnstile automatically.
            response = fetcher.fetch(self.listing_url)
        except ImportError as exc:
            # Playwright not installed - provide helpful message
            logger.error(
                "Playwright is not installed",
                source_key=self.source_key,
                error=str(exc),
            )
            raise ImportError(
                "Playwright is required for SpaReportScraper. "
                "Install with: playwright install"
            ) from exc
        except Exception as exc:
            logger.error(
                "Failed to fetch SPA listing page",
                source_key=self.source_key,
                url=self.listing_url,
                error=str(exc),
                exc_info=True,
            )
            raise FetchError(
                f"Failed to fetch listing: {exc}",
                url=self.listing_url,
            ) from exc

        if response.status != 200:
            logger.warning(
                "Non-200 status from SPA listing page",
                source_key=self.source_key,
                url=self.listing_url,
                status=response.status,
            )
            raise FetchError(
                f"HTTP {response.status} from {self.listing_url}",
                url=self.listing_url,
                status_code=response.status,
            )

        base_url = self.listing_url
        elements = response.css(self.article_selector)

        logger.debug(
            "Elements found on SPA listing page",
            source_key=self.source_key,
            selector=self.article_selector,
            count=len(elements),
        )

        results: list[ReportMetadata] = []
        for element in elements:
            try:
                meta = self.parse_listing_item(element, base_url)
                if meta is not None:
                    results.append(meta)
            except Exception as exc:
                logger.warning(
                    "Failed to parse SPA listing item, skipping",
                    source_key=self.source_key,
                    error=str(exc),
                )
                continue

        logger.info(
            "SPA listing page parsed",
            source_key=self.source_key,
            total_elements=len(elements),
            converted=len(results),
        )
        return results

    # -- Helper methods (delegated to _scraper_utils) -------------------------

    @staticmethod
    def resolve_url(relative_url: str, base_url: str) -> str:
        """Resolve a potentially relative URL against a base URL.

        See Also
        --------
        report_scraper.scrapers._scraper_utils.resolve_url
        """
        return _resolve_url(relative_url, base_url)

    @staticmethod
    def is_pdf_url(url: str) -> bool:
        """Check if a URL points to a PDF file.

        See Also
        --------
        report_scraper.scrapers._scraper_utils.is_pdf_url
        """
        return _is_pdf_url(url)

    @staticmethod
    def find_pdf_links(elements: Any, base_url: str) -> list[str]:
        """Extract PDF links from a collection of anchor elements.

        See Also
        --------
        report_scraper.scrapers._scraper_utils.find_pdf_links
        """
        return _find_pdf_links(elements, base_url)

    def extract_links_by_css(
        self,
        response: Any,
        selector: str,
        base_url: str,
    ) -> list[str]:
        """Extract all href links matching a CSS selector.

        See Also
        --------
        report_scraper.scrapers._scraper_utils.extract_links_by_css
        """
        return _extract_links_by_css(response, selector, base_url)
