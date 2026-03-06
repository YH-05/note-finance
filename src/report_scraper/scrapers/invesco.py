"""Invesco scraper implementation.

Scrapes market insights and research from Invesco.

Classes
-------
InvescoScraper
    Concrete HTML scraper for Invesco publications.

Examples
--------
>>> scraper = InvescoScraper()
>>> scraper.source_key
'invesco'
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, ClassVar

from report_scraper._logging import get_logger
from report_scraper.scrapers._html_scraper import HtmlReportScraper
from report_scraper.types import ReportMetadata, ScrapedReport, SourceConfig

logger = get_logger(__name__, module="invesco_scraper")


# ---------------------------------------------------------------------------
# InvescoScraper
# ---------------------------------------------------------------------------


class InvescoScraper(HtmlReportScraper):
    """Scraper for Invesco publications.

    Fetches the Invesco insights page and extracts report metadata
    for market commentary and investment outlooks.

    Attributes
    ----------
    listing_url : str
        URL of the Invesco insights page.
    article_selector : str
        CSS selector for article list items.

    Examples
    --------
    >>> scraper = InvescoScraper()
    >>> scraper.source_key
    'invesco'
    >>> config = scraper.source_config
    >>> config.tier
    'buy_side'
    """

    listing_url: ClassVar[str] = "https://www.invesco.com/us/en/insights.html"
    article_selector: ClassVar[str] = (
        "div.insights-list a, div.article-card a, a.insight-link"
    )

    # AIDEV-NOTE: pdf_selector for downloadable research PDFs
    _pdf_selector: ClassVar[str] = "a[href$='.pdf']"

    @property
    def source_key(self) -> str:
        """Unique identifier for Invesco.

        Returns
        -------
        str
            ``"invesco"``.
        """
        return "invesco"

    @property
    def source_config(self) -> SourceConfig:
        """Configuration for Invesco source.

        Returns
        -------
        SourceConfig
            Source configuration with static rendering and PDF selector.
        """
        return SourceConfig(
            key="invesco",
            name="Invesco",
            tier="buy_side",
            listing_url=self.listing_url,
            rendering="static",
            tags=["macro", "etf", "outlook"],
            pdf_selector=self._pdf_selector,
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
            Parsed metadata with optional PDF URL, or ``None`` if the
            element lacks required fields.
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

        # Detect PDF links within this element
        pdf_url: str | None = None
        try:
            pdf_elements = element.css(self._pdf_selector)
            pdf_links = self.find_pdf_links(pdf_elements, base_url)
            if pdf_links:
                pdf_url = pdf_links[0]
        except Exception:
            pass

        if pdf_url is None and self.is_pdf_url(url):
            pdf_url = url

        logger.debug(
            "Parsed Invesco listing item",
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
            tags=("macro", "etf", "outlook"),
        )

    async def extract_report(self, meta: ReportMetadata) -> ScrapedReport | None:
        """Extract report content from Invesco.

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
