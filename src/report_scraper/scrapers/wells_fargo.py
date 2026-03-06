"""Wells Fargo Investment Strategy scraper implementation.

Scrapes weekly investment strategy reports from Wells Fargo Advisors.

Classes
-------
WellsFargoScraper
    Concrete HTML scraper for Wells Fargo investment strategy reports.

Examples
--------
>>> scraper = WellsFargoScraper()
>>> scraper.source_key
'wells_fargo'
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, ClassVar

from report_scraper._logging import get_logger
from report_scraper.scrapers._html_scraper import HtmlReportScraper
from report_scraper.types import ReportMetadata, ScrapedReport, SourceConfig

logger = get_logger(__name__, module="wells_fargo_scraper")


# ---------------------------------------------------------------------------
# WellsFargoScraper
# ---------------------------------------------------------------------------


class WellsFargoScraper(HtmlReportScraper):
    """Scraper for Wells Fargo investment strategy weekly reports.

    Fetches the Wells Fargo Advisors research page and extracts
    metadata for weekly investment strategy publications.

    Attributes
    ----------
    listing_url : str
        URL of the Wells Fargo strategy weekly page.
    article_selector : str
        CSS selector for article list items.

    Examples
    --------
    >>> scraper = WellsFargoScraper()
    >>> scraper.source_key
    'wells_fargo'
    >>> config = scraper.source_config
    >>> config.tier
    'sell_side'
    """

    listing_url: ClassVar[str] = (
        "https://www.wellsfargoadvisors.com/research-analysis/strategy/weekly.htm"
    )
    article_selector: ClassVar[str] = (
        "div.article-list a, div.research-item a, a.report-link"
    )

    @property
    def source_key(self) -> str:
        """Unique identifier for Wells Fargo.

        Returns
        -------
        str
            ``"wells_fargo"``.
        """
        return "wells_fargo"

    @property
    def source_config(self) -> SourceConfig:
        """Configuration for Wells Fargo source.

        Returns
        -------
        SourceConfig
            Source configuration with static rendering.
        """
        return SourceConfig(
            key="wells_fargo",
            name="Wells Fargo Investment Institute",
            tier="sell_side",
            listing_url=self.listing_url,
            rendering="static",
            tags=["macro", "strategy", "weekly"],
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

        logger.debug(
            "Parsed Wells Fargo listing item",
            title=title,
            url=url,
        )

        return ReportMetadata(
            url=url,
            title=title.strip(),
            published=datetime.now(timezone.utc),
            source_key=self.source_key,
            tags=("macro", "strategy", "weekly"),
        )

    async def extract_report(self, meta: ReportMetadata) -> ScrapedReport | None:
        """Extract report content from Wells Fargo.

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
