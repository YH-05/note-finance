"""Tests for report_scraper.core.scraper_engine module."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from report_scraper.core.base_scraper import BaseReportScraper
from report_scraper.core.scraper_engine import ScraperEngine
from report_scraper.core.scraper_registry import ScraperRegistry
from report_scraper.services.content_extractor import ContentExtractor
from report_scraper.services.dedup_tracker import DedupTracker
from report_scraper.services.pdf_downloader import PdfDownloader
from report_scraper.storage.json_store import JsonReportStore
from report_scraper.storage.pdf_store import PdfStore
from report_scraper.types import (
    CollectResult,
    ReportMetadata,
    RunSummary,
    ScrapedReport,
    SourceConfig,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_meta(
    url: str = "https://example.com/report/1",
    title: str = "Test Report",
    source_key: str = "test_source",
) -> ReportMetadata:
    return ReportMetadata(
        url=url,
        title=title,
        published=datetime(2026, 3, 1, tzinfo=timezone.utc),
        source_key=source_key,
    )


def _make_collect_result(
    source_key: str = "test_source",
    reports: tuple[ScrapedReport, ...] = (),
    errors: tuple[str, ...] = (),
    duration: float = 1.0,
) -> CollectResult:
    return CollectResult(
        source_key=source_key,
        reports=reports,
        errors=errors,
        duration=duration,
    )


class _SuccessScraper(BaseReportScraper):
    """Scraper that returns a fixed set of reports."""

    def __init__(self, key: str, reports: list[ScrapedReport] | None = None) -> None:
        self._key = key
        self._reports = reports or []

    @property
    def source_key(self) -> str:
        return self._key

    @property
    def source_config(self) -> SourceConfig:
        return SourceConfig(
            key=self._key,
            name=f"Source {self._key}",
            tier="sell_side",
            listing_url=f"https://{self._key}.example.com",
            rendering="static",
        )

    async def fetch_listing(self) -> list[ReportMetadata]:
        return [r.metadata for r in self._reports]

    async def extract_report(self, meta: ReportMetadata) -> ScrapedReport | None:
        for r in self._reports:
            if r.metadata.url == meta.url:
                return r
        return None


class _FailingScraper(BaseReportScraper):
    """Scraper that always raises an error."""

    def __init__(self, key: str) -> None:
        self._key = key

    @property
    def source_key(self) -> str:
        return self._key

    @property
    def source_config(self) -> SourceConfig:
        return SourceConfig(
            key=self._key,
            name=f"Failing {self._key}",
            tier="sell_side",
            listing_url=f"https://{self._key}.example.com",
            rendering="static",
        )

    async def fetch_listing(self) -> list[ReportMetadata]:
        msg = f"Simulated failure for {self._key}"
        raise RuntimeError(msg)

    async def extract_report(self, meta: ReportMetadata) -> ScrapedReport | None:
        return None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_dirs(tmp_path: Path) -> dict[str, Path]:
    """Create temporary directories for stores."""
    json_dir = tmp_path / "reports"
    pdf_dir = tmp_path / "pdfs"
    return {"json_dir": json_dir, "pdf_dir": pdf_dir}


@pytest.fixture
def json_store(tmp_dirs: dict[str, Path]) -> JsonReportStore:
    """Create a JsonReportStore instance."""
    return JsonReportStore(tmp_dirs["json_dir"])


@pytest.fixture
def pdf_store(tmp_dirs: dict[str, Path]) -> PdfStore:
    """Create a PdfStore instance."""
    return PdfStore(tmp_dirs["pdf_dir"])


@pytest.fixture
def engine(json_store: JsonReportStore, pdf_store: PdfStore) -> ScraperEngine:
    """Create a ScraperEngine instance with real stores and mock services."""
    content_extractor = ContentExtractor()
    pdf_downloader = PdfDownloader()
    dedup_tracker = DedupTracker(json_store, dedup_days=30)

    return ScraperEngine(
        content_extractor=content_extractor,
        pdf_downloader=pdf_downloader,
        dedup_tracker=dedup_tracker,
        json_store=json_store,
        pdf_store=pdf_store,
        concurrency=3,
    )


# ---------------------------------------------------------------------------
# Tests: Initialization
# ---------------------------------------------------------------------------


class TestScraperEngineInit:
    """Tests for ScraperEngine initialization."""

    def test_正常系_デフォルト並行数で初期化(
        self, json_store: JsonReportStore, pdf_store: PdfStore
    ) -> None:
        engine = ScraperEngine(
            content_extractor=ContentExtractor(),
            pdf_downloader=PdfDownloader(),
            dedup_tracker=DedupTracker(json_store),
            json_store=json_store,
            pdf_store=pdf_store,
        )
        assert engine.concurrency == 5

    def test_正常系_カスタム並行数で初期化(
        self, json_store: JsonReportStore, pdf_store: PdfStore
    ) -> None:
        engine = ScraperEngine(
            content_extractor=ContentExtractor(),
            pdf_downloader=PdfDownloader(),
            dedup_tracker=DedupTracker(json_store),
            json_store=json_store,
            pdf_store=pdf_store,
            concurrency=10,
        )
        assert engine.concurrency == 10


# ---------------------------------------------------------------------------
# Tests: collect
# ---------------------------------------------------------------------------


class TestScraperEngineCollect:
    """Tests for ScraperEngine.collect method."""

    @pytest.mark.asyncio
    async def test_正常系_複数ソースを並行収集(self, engine: ScraperEngine) -> None:
        meta_a = _make_meta(
            url="https://a.example.com/1", title="Report A", source_key="source_a"
        )
        meta_b = _make_meta(
            url="https://b.example.com/1", title="Report B", source_key="source_b"
        )
        report_a = ScrapedReport(metadata=meta_a)
        report_b = ScrapedReport(metadata=meta_b)

        scraper_a = _SuccessScraper("source_a", [report_a])
        scraper_b = _SuccessScraper("source_b", [report_b])

        registry = ScraperRegistry()
        registry.register(scraper_a)
        registry.register(scraper_b)

        summary = await engine.collect(
            sources=["source_a", "source_b"],
            registry=registry,
        )

        assert isinstance(summary, RunSummary)
        assert summary.total_reports == 2
        assert summary.total_errors == 0
        assert len(summary.results) == 2

    @pytest.mark.asyncio
    async def test_正常系_1ソース失敗でも他ソースは継続(
        self, engine: ScraperEngine
    ) -> None:
        meta = _make_meta(
            url="https://good.example.com/1",
            title="Good Report",
            source_key="good_source",
        )
        report = ScrapedReport(metadata=meta)

        good_scraper = _SuccessScraper("good_source", [report])
        bad_scraper = _FailingScraper("bad_source")

        registry = ScraperRegistry()
        registry.register(good_scraper)
        registry.register(bad_scraper)

        summary = await engine.collect(
            sources=["good_source", "bad_source"],
            registry=registry,
        )

        assert isinstance(summary, RunSummary)
        # Good source should have 1 report
        assert summary.total_reports == 1
        # Bad source should have errors
        assert summary.total_errors > 0
        assert len(summary.results) == 2

    @pytest.mark.asyncio
    async def test_正常系_空のソースリストで空のサマリー(
        self, engine: ScraperEngine
    ) -> None:
        registry = ScraperRegistry()

        summary = await engine.collect(sources=[], registry=registry)

        assert isinstance(summary, RunSummary)
        assert summary.total_reports == 0
        assert summary.total_errors == 0
        assert len(summary.results) == 0

    @pytest.mark.asyncio
    async def test_正常系_全ソース失敗でもRunSummaryを返す(
        self, engine: ScraperEngine
    ) -> None:
        bad_a = _FailingScraper("bad_a")
        bad_b = _FailingScraper("bad_b")

        registry = ScraperRegistry()
        registry.register(bad_a)
        registry.register(bad_b)

        summary = await engine.collect(
            sources=["bad_a", "bad_b"],
            registry=registry,
        )

        assert isinstance(summary, RunSummary)
        assert summary.total_reports == 0
        assert summary.total_errors > 0
        assert len(summary.results) == 2

    @pytest.mark.asyncio
    async def test_正常系_未登録ソースキーでエラー結果(
        self, engine: ScraperEngine
    ) -> None:
        registry = ScraperRegistry()

        summary = await engine.collect(
            sources=["nonexistent_source"],
            registry=registry,
        )

        assert isinstance(summary, RunSummary)
        assert summary.total_reports == 0
        assert summary.total_errors > 0

    @pytest.mark.asyncio
    async def test_正常系_並行数制限が適用される(
        self,
        json_store: JsonReportStore,
        pdf_store: PdfStore,
    ) -> None:
        """Verify concurrency semaphore limits parallel execution."""
        engine = ScraperEngine(
            content_extractor=ContentExtractor(),
            pdf_downloader=PdfDownloader(),
            dedup_tracker=DedupTracker(json_store),
            json_store=json_store,
            pdf_store=pdf_store,
            concurrency=2,
        )

        # Track concurrent execution count inside the semaphore
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def _tracked_collect_source(
            source_key: str,
            registry: ScraperRegistry,
            semaphore: asyncio.Semaphore,
        ) -> CollectResult:
            nonlocal max_concurrent, current_concurrent
            # The semaphore is passed from collect() -- acquire it here
            # to track concurrency within the semaphore-controlled region
            async with semaphore:
                async with lock:
                    current_concurrent += 1
                    max_concurrent = max(max_concurrent, current_concurrent)
                try:
                    await asyncio.sleep(0.05)  # Small delay to allow overlap
                    # Call original without semaphore (we already acquired it)
                    # Just return a simple result to avoid double-acquire
                    return CollectResult(
                        source_key=source_key,
                        reports=(),
                        errors=(),
                        duration=0.0,
                    )
                finally:
                    async with lock:
                        current_concurrent -= 1

        registry = ScraperRegistry()
        for i in range(5):
            registry.register(_SuccessScraper(f"source_{i}"))

        with patch.object(engine, "_collect_source", _tracked_collect_source):
            await engine.collect(
                sources=[f"source_{i}" for i in range(5)],
                registry=registry,
            )

        # With concurrency=2, max_concurrent should not exceed 2
        assert max_concurrent <= 2
