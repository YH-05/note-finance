"""BlackRock Investment Institute scraper implementation.

Scrapes weekly investment commentaries and research from BlackRock's
Investment Institute archives. Supports PDF detection for downloadable
reports.

Classes
-------
BlackRockScraper
    Concrete HTML scraper for BlackRock BII publications.

Examples
--------
>>> scraper = BlackRockScraper()
>>> scraper.source_key
'blackrock_bii'
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, ClassVar

from report_scraper._logging import get_logger
from report_scraper.scrapers._html_scraper import HtmlReportScraper
from report_scraper.types import ReportMetadata, ScrapedReport, SourceConfig

logger = get_logger(__name__, module="blackrock_scraper")


# ---------------------------------------------------------------------------
# BlackRockScraper
# ---------------------------------------------------------------------------


class BlackRockScraper(HtmlReportScraper):
    """Scraper for BlackRock Investment Institute publications.

    Fetches the BII archives page and extracts report metadata including
    PDF links for downloadable weekly commentaries.

    Attributes
    ----------
    listing_url : str
        URL of the BII archives page.
    article_selector : str
        CSS selector for article list items on the archives page.

    Examples
    --------
    >>> scraper = BlackRockScraper()
    >>> scraper.source_key
    'blackrock_bii'
    >>> config = scraper.source_config
    >>> config.tier
    'buy_side'
    """

    listing_url: ClassVar[str] = (
        "https://www.blackrock.com/corporate/insights/"
        "blackrock-investment-institute/archives"
    )
    article_selector: ClassVar[str] = "div.archive-item a, article a.archive-link"

    # AIDEV-NOTE: pdf_selector is used to find PDF links within each article element
    _pdf_selector: ClassVar[str] = "a[href$='.pdf']"

    @property
    def source_key(self) -> str:
        """Unique identifier for BlackRock BII.

        Returns
        -------
        str
            ``"blackrock_bii"``.
        """
        return "blackrock_bii"

    @property
    def source_config(self) -> SourceConfig:
        """Configuration for BlackRock BII source.

        Returns
        -------
        SourceConfig
            Source configuration with static rendering and PDF selector.
        """
        return SourceConfig(
            key="blackrock_bii",
            name="BlackRock Investment Institute",
            tier="buy_side",
            listing_url=self.listing_url,
            rendering="static",
            tags=["macro", "weekly"],
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
            # If CSS selection fails on the element, skip PDF detection
            pass

        # Also check if the main link itself is a PDF
        if pdf_url is None and self.is_pdf_url(url):
            pdf_url = url

        logger.debug(
            "Parsed BlackRock listing item",
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
            tags=("macro", "weekly"),
        )

    async def extract_report(self, meta: ReportMetadata) -> ScrapedReport | None:
        """Extract report content from BlackRock BII.

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
