"""Goldman Sachs Research scraper implementation.

Scrapes research insights from Goldman Sachs' React SPA research page.
Uses DynamicFetcher (Playwright) for JavaScript rendering as the site
is built with React and requires full browser execution.

Classes
-------
GoldmanSachsScraper
    Concrete SPA scraper for Goldman Sachs Research publications.

Examples
--------
>>> scraper = GoldmanSachsScraper()
>>> scraper.source_key
'goldman_sachs'
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, ClassVar

from report_scraper._logging import get_logger
from report_scraper.scrapers._spa_scraper import SpaReportScraper
from report_scraper.types import ReportMetadata, ScrapedReport, SourceConfig

logger = get_logger(__name__, module="goldman_sachs_scraper")


# ---------------------------------------------------------------------------
# GoldmanSachsScraper
# ---------------------------------------------------------------------------


class GoldmanSachsScraper(SpaReportScraper):
    """Scraper for Goldman Sachs Research publications.

    Fetches the Goldman Sachs Research insights page (React SPA) using
    DynamicFetcher for full JavaScript rendering. Extracts report metadata
    from the rendered article cards.

    Attributes
    ----------
    listing_url : str
        URL of the Goldman Sachs Research insights page.
    article_selector : str
        CSS selector for article cards on the research page.
    wait_selector : str
        CSS selector to wait for React content to render.

    Examples
    --------
    >>> scraper = GoldmanSachsScraper()
    >>> scraper.source_key
    'goldman_sachs'
    >>> config = scraper.source_config
    >>> config.tier
    'sell_side'
    """

    listing_url: ClassVar[str] = (
        "https://www.goldmansachs.com/insights/goldman-sachs-research"
    )
    article_selector: ClassVar[str] = (
        "div.article-card a, div.insight-card a, a.research-link"
    )
    wait_selector: str | None = "div.article-card, div.insight-card"

    @property
    def source_key(self) -> str:
        """Unique identifier for Goldman Sachs Research.

        Returns
        -------
        str
            ``"goldman_sachs"``.
        """
        return "goldman_sachs"

    @property
    def source_config(self) -> SourceConfig:
        """Configuration for Goldman Sachs Research source.

        Returns
        -------
        SourceConfig
            Source configuration with playwright rendering.
        """
        return SourceConfig(
            key="goldman_sachs",
            name="Goldman Sachs Research",
            tier="sell_side",
            listing_url=self.listing_url,
            rendering="playwright",
            tags=["macro", "equity", "research"],
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

        # AIDEV-NOTE: Goldman Sachs React SPA article cards may contain
        # PDF links for downloadable research reports.
        pdf_url: str | None = None
        if self.is_pdf_url(url):
            pdf_url = url

        logger.debug(
            "Parsed Goldman Sachs listing item",
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
            tags=("macro", "equity", "research"),
        )

    async def extract_report(self, meta: ReportMetadata) -> ScrapedReport | None:
        """Extract report content from Goldman Sachs Research.

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
