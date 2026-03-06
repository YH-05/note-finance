"""Vanguard Market Perspectives scraper implementation.

Scrapes market perspectives articles from Vanguard's advisors portal.

Classes
-------
VanguardScraper
    Concrete HTML scraper for Vanguard market perspectives.

Examples
--------
>>> scraper = VanguardScraper()
>>> scraper.source_key
'vanguard'
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

        return get_logger(__name__, module="vanguard_scraper")
    except ImportError:
        import logging

        return logging.getLogger(__name__)


logger: Any = _get_logger()


# ---------------------------------------------------------------------------
# VanguardScraper
# ---------------------------------------------------------------------------


class VanguardScraper(HtmlReportScraper):
    """Scraper for Vanguard market perspectives.

    Fetches the Vanguard advisors portal and extracts metadata
    for market perspectives articles and research publications.

    Attributes
    ----------
    listing_url : str
        URL of the Vanguard market perspectives series page.
    article_selector : str
        CSS selector for article list items.

    Examples
    --------
    >>> scraper = VanguardScraper()
    >>> scraper.source_key
    'vanguard'
    >>> config = scraper.source_config
    >>> config.tier
    'buy_side'
    """

    listing_url: ClassVar[str] = (
        "https://advisors.vanguard.com/insights/article/series/market-perspectives"
    )
    article_selector: ClassVar[str] = (
        "div.article-list a, div.card-list a.card-link, a.article-link"
    )

    @property
    def source_key(self) -> str:
        """Unique identifier for Vanguard.

        Returns
        -------
        str
            ``"vanguard"``.
        """
        return "vanguard"

    @property
    def source_config(self) -> SourceConfig:
        """Configuration for Vanguard source.

        Returns
        -------
        SourceConfig
            Source configuration with static rendering.
        """
        return SourceConfig(
            key="vanguard",
            name="Vanguard",
            tier="buy_side",
            listing_url=self.listing_url,
            rendering="static",
            tags=["macro", "market_perspectives"],
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
            "Parsed Vanguard listing item",
            title=title,
            url=url,
        )

        return ReportMetadata(
            url=url,
            title=title.strip(),
            published=datetime.now(timezone.utc),
            source_key=self.source_key,
            tags=("macro", "market_perspectives"),
        )

    async def extract_report(self, meta: ReportMetadata) -> ScrapedReport | None:
        """Extract report content from Vanguard.

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
