"""HTML-based intermediate base class for report scrapers.

Provides ``HtmlReportScraper``, which implements ``fetch_listing()`` using
Scrapling's StealthyFetcher for TLS fingerprint spoofing and adaptive element
tracking. Concrete subclasses define CSS/XPath selectors and implement
``extract_report()``.

Scrapling is an **optional** dependency. If not installed, a warning is logged
and the scraper raises ``ImportError`` only when ``fetch_listing()`` is called.

Classes
-------
HtmlReportScraper
    Intermediate ABC using Scrapling StealthyFetcher for static HTML sources.

Examples
--------
>>> class MyScraper(HtmlReportScraper):
...     listing_url = "https://example.com/research"
...     article_selector = "div.article-list a"
...     @property
...     def source_key(self) -> str:
...         return "example"
...     @property
...     def source_config(self):
...         ...
...     def parse_listing_item(self, element, base_url):
...         return None
...     async def extract_report(self, meta):
...         return None
"""

from __future__ import annotations

import re
import warnings
from abc import abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import urljoin, urlparse

from report_scraper.core.base_scraper import BaseReportScraper
from report_scraper.exceptions import FetchError

if TYPE_CHECKING:
    from report_scraper.types import ReportMetadata, ScrapedReport, SourceConfig

# ---------------------------------------------------------------------------
# Optional Scrapling import
# ---------------------------------------------------------------------------

_scrapling_available = False

try:
    from scrapling import StealthyFetcher  # type: ignore[import-untyped]

    _scrapling_available = True
except ImportError:
    StealthyFetcher = None  # type: ignore[assignment, misc]
    warnings.warn(
        "scrapling is not installed. HtmlReportScraper will not function. "
        "Install with: uv add scrapling",
        ImportWarning,
        stacklevel=2,
    )

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------


def _get_logger() -> Any:
    """Get logger with lazy initialization to avoid circular imports."""
    try:
        from report_scraper._logging import get_logger

        return get_logger(__name__, module="html_scraper")
    except ImportError:
        import logging

        return logging.getLogger(__name__)


logger: Any = _get_logger()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PDF_URL_PATTERN = re.compile(r"\.pdf(\?.*)?$", re.IGNORECASE)
"""Regex pattern matching URLs that end with ``.pdf``."""


# ---------------------------------------------------------------------------
# HtmlReportScraper
# ---------------------------------------------------------------------------


class HtmlReportScraper(BaseReportScraper):
    """Intermediate base class for static HTML report scrapers.

    Uses Scrapling's ``StealthyFetcher`` for TLS fingerprint spoofing and
    adaptive element tracking. Subclasses define CSS selectors for listing
    pages and implement ``parse_listing_item()`` and ``extract_report()``.

    Attributes
    ----------
    listing_url : str
        URL of the page listing available reports.
    article_selector : str
        CSS selector to find article/report items on the listing page.

    Examples
    --------
    >>> class ExampleHtmlScraper(HtmlReportScraper):
    ...     listing_url = "https://example.com/research"
    ...     article_selector = "div.articles a.report-link"
    ...     @property
    ...     def source_key(self) -> str:
    ...         return "example"
    ...     @property
    ...     def source_config(self):
    ...         return SourceConfig(
    ...             key="example", name="Example", tier="sell_side",
    ...             listing_url="https://example.com/research",
    ...             rendering="static",
    ...         )
    ...     def parse_listing_item(self, element, base_url):
    ...         return None
    ...     async def extract_report(self, meta):
    ...         return None
    """

    listing_url: ClassVar[str]
    article_selector: ClassVar[str]

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
        """Fetch the listing page and extract report metadata.

        Uses StealthyFetcher to download the listing page, then applies
        ``article_selector`` to find report items. Each matched element
        is passed to ``parse_listing_item()`` for conversion.

        Returns
        -------
        list[ReportMetadata]
            Parsed report metadata from the listing page.

        Raises
        ------
        ImportError
            If scrapling is not installed.
        FetchError
            If the HTTP request fails.
        """
        if not _scrapling_available:
            msg = (
                "scrapling is required for HtmlReportScraper. "
                "Install with: uv add scrapling"
            )
            raise ImportError(msg)

        logger.info(
            "Fetching listing page",
            source_key=self.source_key,
            url=self.listing_url,
        )

        try:
            if StealthyFetcher is None:  # noqa: E711
                raise FetchError(
                    "Scrapling is not installed. Install with: uv add 'scrapling[fetchers]'",
                    url=self.listing_url,
                )
            fetcher = StealthyFetcher()
            response = fetcher.fetch(self.listing_url)
        except Exception as exc:
            logger.error(
                "Failed to fetch listing page",
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
                "Non-200 status from listing page",
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
            "Elements found on listing page",
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
                    "Failed to parse listing item, skipping",
                    source_key=self.source_key,
                    error=str(exc),
                )
                continue

        logger.info(
            "Listing page parsed",
            source_key=self.source_key,
            total_elements=len(elements),
            converted=len(results),
        )
        return results

    # -- Helper methods ------------------------------------------------------

    @staticmethod
    def resolve_url(relative_url: str, base_url: str) -> str:
        """Resolve a potentially relative URL against a base URL.

        Parameters
        ----------
        relative_url : str
            URL that may be relative.
        base_url : str
            Base URL for resolution.

        Returns
        -------
        str
            Absolute URL.

        Examples
        --------
        >>> HtmlReportScraper.resolve_url("/reports/q4.pdf", "https://example.com/page")
        'https://example.com/reports/q4.pdf'
        >>> HtmlReportScraper.resolve_url("https://cdn.example.com/q4.pdf", "https://example.com")
        'https://cdn.example.com/q4.pdf'
        """
        parsed = urlparse(relative_url)
        if parsed.scheme:
            return relative_url
        return urljoin(base_url, relative_url)

    @staticmethod
    def is_pdf_url(url: str) -> bool:
        """Check if a URL points to a PDF file.

        Parameters
        ----------
        url : str
            URL to check.

        Returns
        -------
        bool
            ``True`` if the URL ends with ``.pdf`` (case-insensitive).

        Examples
        --------
        >>> HtmlReportScraper.is_pdf_url("https://example.com/report.pdf")
        True
        >>> HtmlReportScraper.is_pdf_url("https://example.com/report.pdf?token=abc")
        True
        >>> HtmlReportScraper.is_pdf_url("https://example.com/report.html")
        False
        """
        parsed = urlparse(url)
        return bool(
            PDF_URL_PATTERN.search(
                parsed.path + ("?" + parsed.query if parsed.query else "")
            )
        )

    @staticmethod
    def find_pdf_links(elements: Any, base_url: str) -> list[str]:
        """Extract PDF links from a collection of anchor elements.

        Parameters
        ----------
        elements : Any
            Iterable of Scrapling elements (or any objects with
            ``attrib`` dict containing ``"href"``).
        base_url : str
            Base URL for resolving relative links.

        Returns
        -------
        list[str]
            List of absolute PDF URLs found.
        """
        pdf_links: list[str] = []
        for el in elements:
            href = el.attrib.get("href", "")
            if not href:
                continue
            absolute = HtmlReportScraper.resolve_url(href, base_url)
            if HtmlReportScraper.is_pdf_url(absolute):
                pdf_links.append(absolute)
        return pdf_links

    def extract_links_by_css(
        self,
        response: Any,
        selector: str,
        base_url: str,
    ) -> list[str]:
        """Extract all href links matching a CSS selector.

        Parameters
        ----------
        response : Any
            Scrapling response object.
        selector : str
            CSS selector to find anchor elements.
        base_url : str
            Base URL for resolving relative links.

        Returns
        -------
        list[str]
            List of absolute URLs.
        """
        elements = response.css(selector)
        links: list[str] = []
        for el in elements:
            href = el.attrib.get("href", "")
            if href:
                links.append(self.resolve_url(href, base_url))
        return links
