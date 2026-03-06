"""Morgan Stanley Investment Management scraper implementation.

Scrapes investment insights from Morgan Stanley's IM portal. Supports
a hybrid approach: HTML scraping for the listing page and JSON API
parsing for structured data from their internal API endpoint.

Classes
-------
MorganStanleyScraper
    Concrete HTML scraper with JSON API support for Morgan Stanley insights.

Examples
--------
>>> scraper = MorganStanleyScraper()
>>> scraper.source_key
'morgan_stanley'
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, ClassVar

from report_scraper._logging import get_logger
from report_scraper.scrapers._html_scraper import HtmlReportScraper
from report_scraper.types import ReportMetadata, ScrapedReport, SourceConfig

logger = get_logger(__name__, module="morgan_stanley_scraper")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# AIDEV-NOTE: Morgan Stanley provides a JSON API endpoint for insights data.
# This can be used as an alternative or supplement to HTML scraping.
_JSON_API_URL = "https://www.morganstanley.com/im/json/imwebdata/data"
_BASE_URL = "https://www.morganstanley.com"


# ---------------------------------------------------------------------------
# MorganStanleyScraper
# ---------------------------------------------------------------------------


class MorganStanleyScraper(HtmlReportScraper):
    """Scraper for Morgan Stanley Investment Management insights.

    Supports two modes of data acquisition:

    1. **HTML scraping** (default): Fetches the insights listing page
       and extracts article links via CSS selectors.
    2. **JSON API**: Parses structured data from Morgan Stanley's
       internal JSON API endpoint at ``/im/json/imwebdata/data``.

    The ``parse_json_response()`` method handles JSON API data and can
    be used standalone or to supplement HTML scraping results.

    Attributes
    ----------
    listing_url : str
        URL of the Morgan Stanley insights listing page.
    article_selector : str
        CSS selector for article list items.

    Examples
    --------
    >>> scraper = MorganStanleyScraper()
    >>> scraper.source_key
    'morgan_stanley'
    >>> config = scraper.source_config
    >>> config.tier
    'sell_side'
    """

    listing_url: ClassVar[str] = (
        "https://www.morganstanley.com/im/en-us/"
        "institutional-investor/insights/all-insights.html"
    )
    article_selector: ClassVar[str] = (
        "div.insights-list a.insight-card, div.article-list a, a.insight-link"
    )

    @property
    def source_key(self) -> str:
        """Unique identifier for Morgan Stanley.

        Returns
        -------
        str
            ``"morgan_stanley"``.
        """
        return "morgan_stanley"

    @property
    def source_config(self) -> SourceConfig:
        """Configuration for Morgan Stanley source.

        Returns
        -------
        SourceConfig
            Source configuration with static rendering.
        """
        return SourceConfig(
            key="morgan_stanley",
            name="Morgan Stanley Investment Management",
            tier="sell_side",
            listing_url=self.listing_url,
            rendering="static",
            tags=["macro", "equity", "fixed_income"],
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
            "Parsed Morgan Stanley listing item",
            title=title,
            url=url,
        )

        return ReportMetadata(
            url=url,
            title=title.strip(),
            published=datetime.now(timezone.utc),
            source_key=self.source_key,
            tags=("macro", "equity", "fixed_income"),
        )

    def parse_json_response(
        self,
        json_data: list[dict[str, Any]],
    ) -> list[ReportMetadata]:
        """Parse Morgan Stanley JSON API response into ReportMetadata list.

        Parameters
        ----------
        json_data : list[dict[str, Any]]
            List of article objects from the JSON API. Each object should
            contain at minimum ``title``, ``url``, and ``date`` fields.

        Returns
        -------
        list[ReportMetadata]
            Parsed report metadata. Items with missing required fields
            are skipped.

        Examples
        --------
        >>> scraper = MorganStanleyScraper()
        >>> data = [{"title": "GIC Weekly", "url": "/im/insights/gic", "date": "2026-03-01"}]
        >>> results = scraper.parse_json_response(data)
        >>> len(results)
        1
        """
        results: list[ReportMetadata] = []

        for item in json_data:
            title = item.get("title", "")
            url_path = item.get("url", "")
            date_str = item.get("date", "")
            author = item.get("authors") or item.get("author")

            if not title or not url_path:
                logger.debug(
                    "Skipping JSON item with missing title or url",
                    title=title,
                    url=url_path,
                )
                continue

            # Resolve relative URL against Morgan Stanley base
            url = self.resolve_url(url_path, _BASE_URL)

            # Parse date string
            published: datetime
            if date_str:
                try:
                    published = datetime.strptime(date_str, "%Y-%m-%d").replace(
                        tzinfo=timezone.utc
                    )
                except ValueError:
                    logger.debug(
                        "Failed to parse date, using current time",
                        date_str=date_str,
                    )
                    published = datetime.now(timezone.utc)
            else:
                published = datetime.now(timezone.utc)

            logger.debug(
                "Parsed Morgan Stanley JSON item",
                title=title,
                url=url,
                date=date_str,
            )

            results.append(
                ReportMetadata(
                    url=url,
                    title=title.strip(),
                    published=published,
                    source_key=self.source_key,
                    author=author,
                    tags=("macro", "equity", "fixed_income"),
                )
            )

        logger.info(
            "Parsed JSON API response",
            total_items=len(json_data),
            parsed=len(results),
        )

        return results

    async def extract_report(self, meta: ReportMetadata) -> ScrapedReport | None:
        """Extract report content from Morgan Stanley.

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
