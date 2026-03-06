"""Pipeline engine for concurrent report scraping across multiple sources.

ScraperEngine orchestrates the collection of reports from multiple sources
using ``asyncio.Semaphore`` for concurrency control. Each source is
processed independently -- a failure in one source does not affect others.

Classes
-------
ScraperEngine
    Composition-based pipeline engine for concurrent report scraping.

Examples
--------
>>> from report_scraper.core.scraper_engine import ScraperEngine
>>> from report_scraper.core.scraper_registry import ScraperRegistry
>>> # engine = ScraperEngine(...)
>>> # summary = await engine.collect(sources=["source_a"], registry=registry)
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from report_scraper.core.scraper_registry import ScraperRegistry
    from report_scraper.services.content_extractor import ContentExtractor
    from report_scraper.services.dedup_tracker import DedupTracker
    from report_scraper.services.pdf_downloader import PdfDownloader
    from report_scraper.storage.json_store import JsonReportStore
    from report_scraper.storage.pdf_store import PdfStore
    from report_scraper.types import CollectResult, RunSummary


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------


def _get_logger() -> Any:
    """Get logger with lazy initialization to avoid circular imports."""
    try:
        from report_scraper._logging import get_logger

        return get_logger(__name__, module="scraper_engine")
    except ImportError:
        import logging

        return logging.getLogger(__name__)


logger: Any = _get_logger()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_CONCURRENCY = 5
"""Default number of concurrent source collections."""


# ---------------------------------------------------------------------------
# ScraperEngine
# ---------------------------------------------------------------------------


class ScraperEngine:
    """Composition-based pipeline engine for concurrent report scraping.

    Orchestrates the collection of reports from multiple sources,
    using ``asyncio.Semaphore`` for concurrency control. Each source
    is collected independently: a failure in one source does not
    prevent other sources from completing.

    Parameters
    ----------
    content_extractor : ContentExtractor
        Service for extracting text content from HTML.
    pdf_downloader : PdfDownloader
        Service for downloading PDF files.
    dedup_tracker : DedupTracker
        URL-based deduplication tracker.
    json_store : JsonReportStore
        JSON storage for scraped report data.
    pdf_store : PdfStore
        PDF file storage manager.
    concurrency : int
        Maximum number of concurrent source collections.
        Defaults to 5.

    Examples
    --------
    >>> # engine = ScraperEngine(
    >>> #     content_extractor=extractor,
    >>> #     pdf_downloader=downloader,
    >>> #     dedup_tracker=tracker,
    >>> #     json_store=json_store,
    >>> #     pdf_store=pdf_store,
    >>> #     concurrency=5,
    >>> # )
    """

    def __init__(
        self,
        *,
        content_extractor: ContentExtractor,
        pdf_downloader: PdfDownloader,
        dedup_tracker: DedupTracker,
        json_store: JsonReportStore,
        pdf_store: PdfStore,
        concurrency: int = DEFAULT_CONCURRENCY,
    ) -> None:
        self.content_extractor = content_extractor
        self.pdf_downloader = pdf_downloader
        self.dedup_tracker = dedup_tracker
        self.json_store = json_store
        self.pdf_store = pdf_store
        self.concurrency = concurrency

        logger.debug(
            "ScraperEngine initialized",
            concurrency=concurrency,
        )

    # -- Public API ----------------------------------------------------------

    async def collect(
        self,
        sources: list[str],
        registry: ScraperRegistry,
    ) -> RunSummary:
        """Collect reports from multiple sources concurrently.

        Uses ``asyncio.Semaphore`` to limit the number of concurrent
        source collections. Each source is processed independently:
        if one source fails, the others continue.

        Parameters
        ----------
        sources : list[str]
            List of source keys to collect from. Each key must be
            registered in the registry.
        registry : ScraperRegistry
            Registry mapping source keys to scraper instances.

        Returns
        -------
        RunSummary
            Summary of the complete scraping run with per-source results.

        Examples
        --------
        >>> # summary = await engine.collect(
        >>> #     sources=["source_a", "source_b"],
        >>> #     registry=registry,
        >>> # )
        """
        from report_scraper.types import RunSummary

        logger.info(
            "Starting collection run",
            source_count=len(sources),
            concurrency=self.concurrency,
        )

        start_time = time.monotonic()
        timestamp = datetime.now(timezone.utc)

        if not sources:
            logger.info("No sources to collect")
            return RunSummary(
                timestamp=timestamp,
                results=(),
                total_reports=0,
                total_errors=0,
            )

        semaphore = asyncio.Semaphore(self.concurrency)
        tasks = [
            self._collect_source(source_key, registry, semaphore)
            for source_key in sources
        ]

        results = await asyncio.gather(*tasks)

        total_reports = sum(len(r.reports) for r in results)
        total_errors = sum(len(r.errors) for r in results)
        elapsed = time.monotonic() - start_time

        logger.info(
            "Collection run completed",
            source_count=len(sources),
            total_reports=total_reports,
            total_errors=total_errors,
            duration_seconds=round(elapsed, 2),
        )

        return RunSummary(
            timestamp=timestamp,
            results=tuple(results),
            total_reports=total_reports,
            total_errors=total_errors,
        )

    # -- Internal: per-source collection -------------------------------------

    async def _collect_source(
        self,
        source_key: str,
        registry: ScraperRegistry,
        semaphore: asyncio.Semaphore,
    ) -> CollectResult:
        """Collect reports from a single source with semaphore control.

        Parameters
        ----------
        source_key : str
            Source key to collect from.
        registry : ScraperRegistry
            Registry to look up the scraper.
        semaphore : asyncio.Semaphore
            Concurrency limiter.

        Returns
        -------
        CollectResult
            Collection result for this source.
        """
        from report_scraper.types import CollectResult

        async with semaphore:
            logger.debug(
                "Collecting source",
                source_key=source_key,
            )

            start_time = time.monotonic()

            try:
                scraper = registry.get_scraper(source_key)
            except KeyError as exc:
                elapsed = time.monotonic() - start_time
                error_msg = f"Scraper not found for source '{source_key}': {exc}"
                logger.error(error_msg, source_key=source_key)
                return CollectResult(
                    source_key=source_key,
                    reports=(),
                    errors=(error_msg,),
                    duration=elapsed,
                )

            try:
                result = await scraper.collect_latest()
            except Exception as exc:
                elapsed = time.monotonic() - start_time
                error_msg = f"Collection failed for source '{source_key}': {exc}"
                logger.error(
                    error_msg,
                    source_key=source_key,
                    exc_info=True,
                )
                return CollectResult(
                    source_key=source_key,
                    reports=(),
                    errors=(error_msg,),
                    duration=elapsed,
                )

            logger.info(
                "Source collection completed",
                source_key=source_key,
                reports=len(result.reports),
                errors=len(result.errors),
                duration_seconds=round(result.duration, 2),
            )

            return result
