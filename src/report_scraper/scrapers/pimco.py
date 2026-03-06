"""PIMCO Insights scraper implementation.

Scrapes investment insights from PIMCO's Coveo-powered search page.
Uses DynamicFetcher (Playwright) for JavaScript rendering as the site
relies on the Coveo JavaScript search engine for content rendering.

Classes
-------
PimcoScraper
    Concrete SPA scraper for PIMCO Insights publications.

Examples
--------
>>> scraper = PimcoScraper()
>>> scraper.source_key
'pimco'
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, ClassVar

from report_scraper.scrapers._spa_scraper import SpaReportScraper
from report_scraper.types import ReportMetadata, ScrapedReport, SourceConfig

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------


def _get_logger() -> Any:
    """Get logger with lazy initialization to avoid circular imports."""
    try:
        from report_scraper._logging import get_logger

        return get_logger(__name__, module="pimco_scraper")
    except ImportError:
        import logging

        return logging.getLogger(__name__)


logger: Any = _get_logger()


# ---------------------------------------------------------------------------
# PimcoScraper
# ---------------------------------------------------------------------------


class PimcoScraper(SpaReportScraper):
    """Scraper for PIMCO Insights publications.

    Fetches the PIMCO insights page using DynamicFetcher for full
    JavaScript rendering. The site uses Coveo JavaScript search engine
    to dynamically render investment insights and outlooks.

    Attributes
    ----------
    listing_url : str
        URL of the PIMCO insights page.
    article_selector : str
        CSS selector for article results rendered by Coveo search.
    wait_selector : str
        CSS selector to wait for Coveo search results to render.

    Examples
    --------
    >>> scraper = PimcoScraper()
    >>> scraper.source_key
    'pimco'
    >>> config = scraper.source_config
    >>> config.tier
    'buy_side'
    """

    listing_url: ClassVar[str] = "https://www.pimco.com/gbl/en/insights"
    article_selector: ClassVar[str] = (
        "div.coveo-result-cell a, div.CoveoResult a, "
        "a.coveo-result-link, div.insight-card a"
    )
    # AIDEV-NOTE: Coveo search engine renders results asynchronously.
    # Wait for CoveoResult containers to appear before extracting.
    wait_selector: str | None = (
        "div.coveo-result-cell, div.CoveoResult, div.insight-card"
    )

    @property
    def source_key(self) -> str:
        """Unique identifier for PIMCO.

        Returns
        -------
        str
            ``"pimco"``.
        """
        return "pimco"

    @property
    def source_config(self) -> SourceConfig:
        """Configuration for PIMCO source.

        Returns
        -------
        SourceConfig
            Source configuration with playwright rendering.
        """
        return SourceConfig(
            key="pimco",
            name="PIMCO Insights",
            tier="buy_side",
            listing_url=self.listing_url,
            rendering="playwright",
            tags=["fixed_income", "macro", "outlook"],
            article_selector=self.article_selector,
        )

    def parse_listing_item(
        self,
        element: Any,
        base_url: str,
    ) -> ReportMetadata | None:
        """Parse a single listing element into ReportMetadata.

        Parameters
        ----------
        element : Any
            A Scrapling element matched by ``article_selector``.
        base_url : str
            Base URL for resolving relative links.

        Returns
        -------
        ReportMetadata | None
            Parsed metadata, or ``None`` if the element lacks required fields.
        """
        href = element.attrib.get("href", "")
        title = element.text or ""

        if not href or not title:
            logger.debug(
                "Skipping element with missing href or title",
                href=href,
                title=title,
            )
            return None

        url = self.resolve_url(href, base_url)

        # AIDEV-NOTE: PIMCO may provide PDF versions of investment outlooks
        pdf_url: str | None = None
        if self.is_pdf_url(url):
            pdf_url = url

        logger.debug(
            "Parsed PIMCO listing item",
            title=title,
            url=url,
            pdf_url=pdf_url,
        )

        return ReportMetadata(
            url=url,
            title=title.strip(),
            published=datetime.now(timezone.utc),
            source_key=self.source_key,
            pdf_url=pdf_url,
            tags=("fixed_income", "macro", "outlook"),
        )

    async def extract_report(self, meta: ReportMetadata) -> ScrapedReport | None:
        """Extract report content from PIMCO.

        Currently returns a ``ScrapedReport`` wrapping the metadata
        without content extraction. Full extraction will be added
        in a future wave.

        Parameters
        ----------
        meta : ReportMetadata
            Report metadata to extract.

        Returns
        -------
        ScrapedReport | None
            Scraped report with metadata (content is ``None``).
        """
        logger.debug(
            "Extracting report",
            source_key=self.source_key,
            title=meta.title,
            url=meta.url,
        )
        return ScrapedReport(metadata=meta)
