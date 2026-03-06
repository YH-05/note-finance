"""Fidelity Investments scraper implementation.

Scrapes market insights and research from Fidelity Investments.

Classes
-------
FidelityScraper
    Concrete HTML scraper for Fidelity publications.

Examples
--------
>>> scraper = FidelityScraper()
>>> scraper.source_key
'fidelity'
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, ClassVar

from report_scraper.scrapers._html_scraper import HtmlReportScraper
from report_scraper.types import ReportMetadata, ScrapedReport, SourceConfig

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------


def _get_logger() -> Any:
    """Get logger with lazy initialization to avoid circular imports."""
    try:
        from report_scraper._logging import get_logger

        return get_logger(__name__, module="fidelity_scraper")
    except ImportError:
        import logging

        return logging.getLogger(__name__)


logger: Any = _get_logger()


# ---------------------------------------------------------------------------
# FidelityScraper
# ---------------------------------------------------------------------------


class FidelityScraper(HtmlReportScraper):
    """Scraper for Fidelity Investments publications.

    Fetches the Fidelity viewpoints page and extracts report metadata
    for market commentary and investment research.

    Attributes
    ----------
    listing_url : str
        URL of the Fidelity viewpoints page.
    article_selector : str
        CSS selector for article list items.

    Examples
    --------
    >>> scraper = FidelityScraper()
    >>> scraper.source_key
    'fidelity'
    >>> config = scraper.source_config
    >>> config.tier
    'buy_side'
    """

    listing_url: ClassVar[str] = (
        "https://www.fidelity.com/learning-center/trading-investing/overview"
    )
    article_selector: ClassVar[str] = (
        "div.article-listing a, div.content-card a, a.article-link"
    )

    @property
    def source_key(self) -> str:
        """Unique identifier for Fidelity.

        Returns
        -------
        str
            ``"fidelity"``.
        """
        return "fidelity"

    @property
    def source_config(self) -> SourceConfig:
        """Configuration for Fidelity source.

        Returns
        -------
        SourceConfig
            Source configuration with static rendering.
        """
        return SourceConfig(
            key="fidelity",
            name="Fidelity Investments",
            tier="buy_side",
            listing_url=self.listing_url,
            rendering="static",
            tags=["macro", "equity", "retirement"],
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
            "Parsed Fidelity listing item",
            title=title,
            url=url,
        )

        return ReportMetadata(
            url=url,
            title=title.strip(),
            published=datetime.now(timezone.utc),
            source_key=self.source_key,
            tags=("macro", "equity", "retirement"),
        )

    async def extract_report(self, meta: ReportMetadata) -> ScrapedReport | None:
        """Extract report content from Fidelity.

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
