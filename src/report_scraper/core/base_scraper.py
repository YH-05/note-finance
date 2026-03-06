"""Abstract base class for all report scrapers.

Provides a common interface that concrete scrapers (RSS, static HTML,
Playwright/SPA) must implement. The ``collect_latest`` method provides
a default orchestration flow using ``fetch_listing`` and ``extract_report``.

Classes
-------
BaseReportScraper
    ABC with abstract ``fetch_listing`` and ``extract_report`` methods.

Examples
--------
>>> class MyScraper(BaseReportScraper):
...     @property
...     def source_key(self) -> str:
...         return "my_source"
...     @property
...     def source_config(self) -> SourceConfig:
...         return SourceConfig(...)
...     async def fetch_listing(self) -> list[ReportMetadata]:
...         return [...]
...     async def extract_report(self, meta: ReportMetadata) -> ScrapedReport | None:
...         return ScrapedReport(metadata=meta)
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from report_scraper.types import (
        CollectResult,
        ReportMetadata,
        ScrapedReport,
        SourceConfig,
    )


from report_scraper._logging import get_logger

logger = get_logger(__name__, module="base_report_scraper")


# ---------------------------------------------------------------------------
# BaseReportScraper
# ---------------------------------------------------------------------------


class BaseReportScraper(ABC):
    """Abstract base class for all report scrapers.

    Concrete subclasses must implement ``source_key``, ``source_config``,
    ``fetch_listing``, and ``extract_report``. The ``collect_latest``
    method provides a default orchestration flow.

    Examples
    --------
    >>> class ExampleScraper(BaseReportScraper):
    ...     @property
    ...     def source_key(self) -> str:
    ...         return "example"
    ...     @property
    ...     def source_config(self) -> SourceConfig:
    ...         return SourceConfig(
    ...             key="example", name="Example", tier="sell_side",
    ...             listing_url="https://example.com", rendering="static",
    ...         )
    ...     async def fetch_listing(self):
    ...         return []
    ...     async def extract_report(self, meta):
    ...         return None
    """

    # -- Abstract properties -------------------------------------------------

    @property
    @abstractmethod
    def source_key(self) -> str:
        """Unique identifier for this source.

        Returns
        -------
        str
            Source key matching ``SourceConfig.key``.
        """
        ...

    @property
    @abstractmethod
    def source_config(self) -> SourceConfig:
        """Configuration for this source.

        Returns
        -------
        SourceConfig
            The source configuration.
        """
        ...

    # -- Abstract methods ----------------------------------------------------

    @abstractmethod
    async def fetch_listing(self) -> list[ReportMetadata]:
        """Fetch the list of available reports from the source.

        Returns
        -------
        list[ReportMetadata]
            Metadata for each discovered report.
        """
        ...

    @abstractmethod
    async def extract_report(self, meta: ReportMetadata) -> ScrapedReport | None:
        """Extract full content from a single report.

        Parameters
        ----------
        meta : ReportMetadata
            Metadata of the report to extract.

        Returns
        -------
        ScrapedReport | None
            Extracted report, or ``None`` if extraction fails.
        """
        ...

    # -- Default implementation ----------------------------------------------

    async def collect_latest(self, max_reports: int = 20) -> CollectResult:
        """Collect the latest reports from this source.

        Default orchestration flow:

        1. Call ``fetch_listing()`` to discover reports.
        2. Truncate to ``max_reports``.
        3. Call ``extract_report()`` for each report.
        4. Return ``CollectResult`` with successes and errors.

        Parameters
        ----------
        max_reports : int
            Maximum number of reports to collect.

        Returns
        -------
        CollectResult
            Collection result with scraped reports and any errors.
        """
        from report_scraper.types import CollectResult

        logger.info(
            "Starting collection",
            source_key=self.source_key,
            max_reports=max_reports,
        )

        start_time = time.monotonic()
        reports: list[ScrapedReport] = []
        errors: list[str] = []

        try:
            listing = await self.fetch_listing()
        except Exception as exc:
            msg = f"Failed to fetch listing: {exc}"
            logger.error(msg, source_key=self.source_key, exc_info=True)
            elapsed = time.monotonic() - start_time
            return CollectResult(
                source_key=self.source_key,
                reports=(),
                errors=(msg,),
                duration=elapsed,
            )

        candidates = listing[:max_reports]
        logger.debug(
            "Processing candidates",
            source_key=self.source_key,
            total_listed=len(listing),
            candidates=len(candidates),
        )

        for meta in candidates:
            try:
                report = await self.extract_report(meta)
                if report is not None:
                    reports.append(report)
                    logger.debug(
                        "Report extracted",
                        source_key=self.source_key,
                        title=meta.title,
                    )
                else:
                    logger.debug(
                        "Report extraction returned None",
                        source_key=self.source_key,
                        title=meta.title,
                    )
            except Exception as exc:
                msg = f"Failed to extract report '{meta.title}': {exc}"
                logger.warning(msg, source_key=self.source_key, exc_info=True)
                errors.append(msg)

        elapsed = time.monotonic() - start_time

        logger.info(
            "Collection completed",
            source_key=self.source_key,
            reports_collected=len(reports),
            errors_count=len(errors),
            duration_seconds=round(elapsed, 2),
        )

        return CollectResult(
            source_key=self.source_key,
            reports=tuple(reports),
            errors=tuple(errors),
            duration=elapsed,
        )
