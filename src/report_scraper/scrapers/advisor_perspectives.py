"""Advisor Perspectives scraper implementation.

Scrapes investment commentaries from Advisor Perspectives via their
RSS feed at ``https://www.advisorperspectives.com/commentaries.rss``.

Classes
-------
AdvisorPerspectivesScraper
    Concrete RSS scraper for Advisor Perspectives commentaries.

Examples
--------
>>> scraper = AdvisorPerspectivesScraper()
>>> scraper.source_key
'advisor_perspectives'
>>> scraper.feed_url
'https://www.advisorperspectives.com/commentaries.rss'
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from report_scraper.scrapers._rss_scraper import RssReportScraper
from report_scraper.types import ScrapedReport, SourceConfig

if TYPE_CHECKING:
    from report_scraper.types import ReportMetadata


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------


def _get_logger() -> Any:
    """Get logger with lazy initialization to avoid circular imports."""
    try:
        from report_scraper._logging import get_logger

        return get_logger(__name__, module="advisor_perspectives_scraper")
    except ImportError:
        import logging

        return logging.getLogger(__name__)


logger: Any = _get_logger()


# ---------------------------------------------------------------------------
# AdvisorPerspectivesScraper
# ---------------------------------------------------------------------------


class AdvisorPerspectivesScraper(RssReportScraper):
    """Scraper for Advisor Perspectives investment commentaries.

    Uses the Advisor Perspectives RSS feed to discover new commentaries.
    This is a minimal implementation that returns ``ScrapedReport`` with
    metadata only (no content extraction).

    Attributes
    ----------
    feed_url : str
        RSS feed URL for Advisor Perspectives commentaries.

    Examples
    --------
    >>> scraper = AdvisorPerspectivesScraper()
    >>> scraper.source_key
    'advisor_perspectives'
    >>> config = scraper.source_config
    >>> config.rendering
    'rss'
    """

    feed_url = "https://www.advisorperspectives.com/commentaries.rss"

    @property
    def source_key(self) -> str:
        """Unique identifier for Advisor Perspectives.

        Returns
        -------
        str
            ``"advisor_perspectives"``.
        """
        return "advisor_perspectives"

    @property
    def source_config(self) -> SourceConfig:
        """Configuration for Advisor Perspectives source.

        Returns
        -------
        SourceConfig
            Source configuration with RSS rendering type.
        """
        return SourceConfig(
            key="advisor_perspectives",
            name="Advisor Perspectives",
            tier="aggregator",
            listing_url=self.feed_url,
            rendering="rss",
            tags=["macro", "equity", "fixed_income"],
        )

    async def extract_report(self, meta: ReportMetadata) -> ScrapedReport | None:
        """Extract report content from Advisor Perspectives.

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
