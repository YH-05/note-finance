"""JP Morgan Markets & Economy scraper implementation.

Scrapes market insights from JP Morgan's dynamically loaded pages.
Uses DynamicFetcher (Playwright) for JavaScript rendering as the site
uses dynamic loading with scroll/button-based content pagination.

Classes
-------
JPMorganScraper
    Concrete SPA scraper for JP Morgan Markets & Economy publications.

Examples
--------
>>> scraper = JPMorganScraper()
>>> scraper.source_key
'jpmorgan'
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

        return get_logger(__name__, module="jpmorgan_scraper")
    except ImportError:
        import logging

        return logging.getLogger(__name__)


logger: Any = _get_logger()


# ---------------------------------------------------------------------------
# JPMorganScraper
# ---------------------------------------------------------------------------


class JPMorganScraper(SpaReportScraper):
    """Scraper for JP Morgan Markets & Economy publications.

    Fetches the JP Morgan insights page using DynamicFetcher for full
    JavaScript rendering. The site uses dynamic loading with scroll
    and button-based pagination for content display.

    Attributes
    ----------
    listing_url : str
        URL of the JP Morgan Markets & Economy insights page.
    article_selector : str
        CSS selector for article items on the insights page.
    wait_selector : str
        CSS selector to wait for dynamic content to load.

    Examples
    --------
    >>> scraper = JPMorganScraper()
    >>> scraper.source_key
    'jpmorgan'
    >>> config = scraper.source_config
    >>> config.tier
    'sell_side'
    """

    listing_url: ClassVar[str] = "https://www.jpmorgan.com/insights/markets-and-economy"
    article_selector: ClassVar[str] = (
        "div.article-item a, div.card-item a, a.insight-link, "
        "div.content-card a.card-link"
    )
    wait_selector: str | None = "div.article-item, div.card-item, div.content-card"

    @property
    def source_key(self) -> str:
        """Unique identifier for JP Morgan.

        Returns
        -------
        str
            ``"jpmorgan"``.
        """
        return "jpmorgan"

    @property
    def source_config(self) -> SourceConfig:
        """Configuration for JP Morgan source.

        Returns
        -------
        SourceConfig
            Source configuration with playwright rendering.
        """
        return SourceConfig(
            key="jpmorgan",
            name="JP Morgan Markets & Economy",
            tier="sell_side",
            listing_url=self.listing_url,
            rendering="playwright",
            tags=["macro", "markets", "economy"],
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

        # AIDEV-NOTE: JP Morgan pages may link to PDF research reports
        pdf_url: str | None = None
        if self.is_pdf_url(url):
            pdf_url = url

        logger.debug(
            "Parsed JP Morgan listing item",
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
            tags=("macro", "markets", "economy"),
        )

    async def extract_report(self, meta: ReportMetadata) -> ScrapedReport | None:
        """Extract report content from JP Morgan.

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
