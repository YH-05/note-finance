"""E2E integration tests for the report collection pipeline.

Verifies the complete flow: collect -> dedup -> save using a mock HTTP
server (pytest-httpserver) so no real network access is required.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest

from report_scraper.core.base_scraper import BaseReportScraper
from report_scraper.core.scraper_engine import ScraperEngine
from report_scraper.core.scraper_registry import ScraperRegistry
from report_scraper.services.content_extractor import ContentExtractor
from report_scraper.services.dedup_tracker import DedupTracker
from report_scraper.services.pdf_downloader import PdfDownloader
from report_scraper.storage.json_store import JsonReportStore
from report_scraper.storage.pdf_store import PdfStore
from report_scraper.types import (
    ReportMetadata,
    ScrapedReport,
    SourceConfig,
)

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_httpserver import HTTPServer

# ---------------------------------------------------------------------------
# Test scraper that fetches from mock HTTP server
# ---------------------------------------------------------------------------


class _MockScraper(BaseReportScraper):
    """Scraper that fetches a listing page from a mock HTTP server.

    Parses a simple JSON listing response and creates reports with
    extracted content from a second endpoint.
    """

    def __init__(self, server_url: str, config: SourceConfig) -> None:
        self._server_url = server_url
        self._config = config

    @property
    def source_key(self) -> str:
        return self._config.key

    @property
    def source_config(self) -> SourceConfig:
        return self._config

    async def fetch_listing(self) -> list[ReportMetadata]:
        """Fetch listing from mock server's /listing.json endpoint."""
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self._server_url}/listing.json")
            resp.raise_for_status()
            data = resp.json()

        results: list[ReportMetadata] = []
        for item in data["articles"]:
            results.append(
                ReportMetadata(
                    url=item["url"],
                    title=item["title"],
                    published=datetime.fromisoformat(item["published"]),
                    source_key=self.source_key,
                    author=item.get("author"),
                )
            )
        return results

    async def extract_report(self, meta: ReportMetadata) -> ScrapedReport | None:
        """Fetch article HTML from mock server and extract content."""
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.get(meta.url)
            resp.raise_for_status()
            html = resp.text

        extractor = ContentExtractor()
        content = extractor.extract_from_html(html, url=meta.url)
        return ScrapedReport(metadata=meta, content=content)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# AIDEV-NOTE: pytest-httpserver provides the ``httpserver`` fixture
# automatically when installed; we build on top of it.

ARTICLE_HTML = """<!DOCTYPE html>
<html>
<head><title>Test Article</title></head>
<body>
<article>
<h1>Test Article Title</h1>
<p>{content}</p>
</article>
</body>
</html>"""

LONG_PARAGRAPH = (
    "This is a detailed investment analysis covering market trends, "
    "economic indicators, and portfolio strategies for the upcoming quarter. "
) * 5  # > 100 chars to pass MIN_CONTENT_LENGTH


@pytest.fixture
def mock_source_config() -> SourceConfig:
    """Source config pointing at the mock server."""
    return SourceConfig(
        key="mock_source",
        name="Mock Research",
        tier="sell_side",
        listing_url="http://placeholder",  # replaced at runtime
        rendering="static",
        tags=["macro"],
    )


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Temporary data directory for JSON/PDF storage."""
    d = tmp_path / "reports"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCollectFlowE2E:
    """End-to-end tests for the collect pipeline."""

    def test_正常系_完全パイプラインで収集から保存まで成功(
        self,
        httpserver: HTTPServer,
        mock_source_config: SourceConfig,
        data_dir: Path,
    ) -> None:
        """Collect -> extract -> dedup -> save in one pass."""
        import asyncio

        # -- Set up mock HTTP endpoints --
        base_url = httpserver.url_for("")

        article_url_1 = f"{base_url}/articles/report-1"
        article_url_2 = f"{base_url}/articles/report-2"

        listing = {
            "articles": [
                {
                    "url": article_url_1,
                    "title": "Q4 Market Outlook",
                    "published": "2026-03-01T10:00:00+00:00",
                    "author": "Analyst A",
                },
                {
                    "url": article_url_2,
                    "title": "Sector Rotation Strategy",
                    "published": "2026-03-02T08:00:00+00:00",
                    "author": "Analyst B",
                },
            ]
        }

        httpserver.expect_request("/listing.json").respond_with_json(listing)
        httpserver.expect_request("/articles/report-1").respond_with_data(
            ARTICLE_HTML.format(content=LONG_PARAGRAPH),
            content_type="text/html",
        )
        httpserver.expect_request("/articles/report-2").respond_with_data(
            ARTICLE_HTML.format(content=LONG_PARAGRAPH),
            content_type="text/html",
        )

        # -- Build pipeline components --
        json_store = JsonReportStore(data_dir)
        pdf_store = PdfStore(data_dir / "pdfs")
        dedup_tracker = DedupTracker(json_store, dedup_days=30)
        content_extractor = ContentExtractor()
        pdf_downloader = PdfDownloader()

        # -- Register mock scraper --
        scraper = _MockScraper(
            server_url=base_url.rstrip("/"),
            config=mock_source_config,
        )
        registry = ScraperRegistry()
        registry.register(scraper)

        # -- Run engine --
        engine = ScraperEngine(
            content_extractor=content_extractor,
            pdf_downloader=pdf_downloader,
            dedup_tracker=dedup_tracker,
            json_store=json_store,
            pdf_store=pdf_store,
            concurrency=2,
        )

        summary = asyncio.run(
            engine.collect(
                sources=["mock_source"],
                registry=registry,
            )
        )

        # -- Assertions on RunSummary --
        assert summary.total_reports == 2
        assert summary.total_errors == 0
        assert len(summary.results) == 1

        result = summary.results[0]
        assert result.source_key == "mock_source"
        assert len(result.reports) == 2

        # -- Save results and verify persistence --
        json_store.save_run(result)
        json_store.update_index(result)
        for report in result.reports:
            json_store.save_text(report)

        # Verify index contains both URLs
        index = json_store.load_index()
        assert article_url_1 in index["reports"]
        assert article_url_2 in index["reports"]

        # Verify run file was saved
        runs_dir = data_dir / "runs"
        run_files = list(runs_dir.glob("*.json"))
        assert len(run_files) >= 1

        # Verify text files were saved
        text_dir = data_dir / "text" / "mock_source"
        text_files = list(text_dir.glob("*.txt"))
        assert len(text_files) == 2

    def test_正常系_重複排除で既存URLをスキップ(
        self,
        httpserver: HTTPServer,
        mock_source_config: SourceConfig,
        data_dir: Path,
    ) -> None:
        """URLs already in the index should be detected by DedupTracker."""
        base_url = httpserver.url_for("")
        existing_url = f"{base_url}/articles/old-report"

        # -- Pre-populate the index with an existing URL --
        json_store = JsonReportStore(data_dir)
        dedup_tracker = DedupTracker(json_store, dedup_days=30)
        dedup_tracker.mark_seen("mock_source", existing_url)

        # -- Verify dedup detects existing URL --
        assert dedup_tracker.is_seen("mock_source", existing_url) is True

        # New URL should not be seen
        new_url = f"{base_url}/articles/new-report"
        assert dedup_tracker.is_seen("mock_source", new_url) is False

    def test_正常系_空のリスティングで0件収集(
        self,
        httpserver: HTTPServer,
        mock_source_config: SourceConfig,
        data_dir: Path,
    ) -> None:
        """Engine handles empty source listing gracefully."""
        import asyncio

        base_url = httpserver.url_for("")

        httpserver.expect_request("/listing.json").respond_with_json({"articles": []})

        json_store = JsonReportStore(data_dir)
        pdf_store = PdfStore(data_dir / "pdfs")
        dedup_tracker = DedupTracker(json_store, dedup_days=30)
        content_extractor = ContentExtractor()
        pdf_downloader = PdfDownloader()

        scraper = _MockScraper(
            server_url=base_url.rstrip("/"),
            config=mock_source_config,
        )
        registry = ScraperRegistry()
        registry.register(scraper)

        engine = ScraperEngine(
            content_extractor=content_extractor,
            pdf_downloader=pdf_downloader,
            dedup_tracker=dedup_tracker,
            json_store=json_store,
            pdf_store=pdf_store,
        )

        summary = asyncio.run(
            engine.collect(sources=["mock_source"], registry=registry)
        )

        assert summary.total_reports == 0
        assert summary.total_errors == 0

    def test_正常系_保存後のインデックスに全メタデータが含まれる(
        self,
        httpserver: HTTPServer,
        mock_source_config: SourceConfig,
        data_dir: Path,
    ) -> None:
        """Index entries contain expected metadata fields after save."""
        import asyncio

        base_url = httpserver.url_for("")
        article_url = f"{base_url}/articles/metadata-check"

        listing = {
            "articles": [
                {
                    "url": article_url,
                    "title": "Metadata Test Report",
                    "published": "2026-03-05T14:00:00+00:00",
                    "author": "Test Author",
                },
            ]
        }

        httpserver.expect_request("/listing.json").respond_with_json(listing)
        httpserver.expect_request("/articles/metadata-check").respond_with_data(
            ARTICLE_HTML.format(content=LONG_PARAGRAPH),
            content_type="text/html",
        )

        json_store = JsonReportStore(data_dir)
        pdf_store = PdfStore(data_dir / "pdfs")
        dedup_tracker = DedupTracker(json_store, dedup_days=30)
        content_extractor = ContentExtractor()
        pdf_downloader = PdfDownloader()

        scraper = _MockScraper(
            server_url=base_url.rstrip("/"),
            config=mock_source_config,
        )
        registry = ScraperRegistry()
        registry.register(scraper)

        engine = ScraperEngine(
            content_extractor=content_extractor,
            pdf_downloader=pdf_downloader,
            dedup_tracker=dedup_tracker,
            json_store=json_store,
            pdf_store=pdf_store,
        )

        summary = asyncio.run(
            engine.collect(sources=["mock_source"], registry=registry)
        )

        assert summary.total_reports == 1
        result = summary.results[0]

        # Save and check index metadata
        json_store.update_index(result)
        index = json_store.load_index()

        entry = index["reports"][article_url]
        assert entry["title"] == "Metadata Test Report"
        assert entry["source_key"] == "mock_source"
        assert "collected_at" in entry
        assert entry["has_content"] is True

    def test_正常系_履歴取得で期間内のエントリを返す(
        self,
        data_dir: Path,
    ) -> None:
        """DedupTracker.get_history returns entries within the window."""
        json_store = JsonReportStore(data_dir)
        tracker = DedupTracker(json_store, dedup_days=7)

        # Mark two URLs
        tracker.mark_seen("source_a", "https://example.com/report-1")
        tracker.mark_seen("source_b", "https://example.com/report-2")

        history = tracker.get_history(days=7)
        assert len(history) == 2

        urls = {h["url"] for h in history}
        assert "https://example.com/report-1" in urls
        assert "https://example.com/report-2" in urls
