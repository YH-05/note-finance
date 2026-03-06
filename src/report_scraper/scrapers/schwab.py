"""Charles Schwab market commentary scraper implementation.

Scrapes market perspectives and sector outlooks from Charles Schwab's
market commentary pages.

Classes
-------
SchwabScraper
    Concrete HTML scraper for Charles Schwab market commentary.

Examples
--------
>>> scraper = SchwabScraper()
>>> scraper.source_key
'schwab'
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

        return get_logger(__name__, module="schwab_scraper")
    except ImportError:
        import logging

        return logging.getLogger(__name__)


logger: Any = _get_logger()


# ---------------------------------------------------------------------------
# SchwabScraper
# ---------------------------------------------------------------------------


class SchwabScraper(HtmlReportScraper):
    """Scraper for Charles Schwab market commentary.

    Fetches the Schwab market commentary page and extracts report
    metadata for market perspectives and sector analysis articles.

    Attributes
    ----------
    listing_url : str
        URL of the Schwab market commentary page.
    article_selector : str
        CSS selector for article list items.

    Examples
    --------
    >>> scraper = SchwabScraper()
    >>> scraper.source_key
    'schwab'
    >>> config = scraper.source_config
    >>> config.tier
    'sell_side'
    """

    listing_url: ClassVar[str] = "https://www.schwab.com/learn/market-commentary"
    article_selector: ClassVar[str] = (
        "div.article-listing a, div.content-card a.card-link"
    )

    @property
    def source_key(self) -> str:
        """Unique identifier for Charles Schwab.

        Returns
        -------
        str
            ``"schwab"``.
        """
        return "schwab"

    @property
    def source_config(self) -> SourceConfig:
        """Configuration for Charles Schwab source.

        Returns
        -------
        SourceConfig
            Source configuration with static rendering.
        """
        return SourceConfig(
            key="schwab",
            name="Charles Schwab",
            tier="sell_side",
            listing_url=self.listing_url,
            rendering="static",
            tags=["macro", "equity", "sector"],
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
            "Parsed Schwab listing item",
            title=title,
            url=url,
        )

        return ReportMetadata(
            url=url,
            title=title.strip(),
            published=datetime.now(timezone.utc),
            source_key=self.source_key,
            tags=("macro", "equity", "sector"),
        )

    async def extract_report(self, meta: ReportMetadata) -> ScrapedReport | None:
        """Extract report content from Charles Schwab.

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
