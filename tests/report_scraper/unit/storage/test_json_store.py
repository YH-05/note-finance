"""Tests for report_scraper.storage.json_store module."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path  # noqa: TC003

import pytest

from report_scraper.storage.json_store import JsonReportStore
from report_scraper.types import (
    CollectResult,
    ExtractedContent,
    ReportMetadata,
    ScrapedReport,
)


@pytest.fixture
def store_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for the store."""
    return tmp_path / "reports"


@pytest.fixture
def store(store_dir: Path) -> JsonReportStore:
    """Create a JsonReportStore instance."""
    return JsonReportStore(store_dir)


@pytest.fixture
def sample_metadata() -> ReportMetadata:
    """Create sample report metadata."""
    return ReportMetadata(
        url="https://example.com/report/1",
        title="Test Report",
        published=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
        source_key="test_source",
        author="Test Author",
    )


@pytest.fixture
def sample_content() -> ExtractedContent:
    """Create sample extracted content."""
    return ExtractedContent(
        text="This is the full content of the test report. " * 10,
        method="trafilatura",
        length=460,
    )


@pytest.fixture
def sample_report(
    sample_metadata: ReportMetadata,
    sample_content: ExtractedContent,
) -> ScrapedReport:
    """Create a sample scraped report."""
    return ScrapedReport(metadata=sample_metadata, content=sample_content)


@pytest.fixture
def sample_collect_result(sample_report: ScrapedReport) -> CollectResult:
    """Create a sample collect result."""
    return CollectResult(
        source_key="test_source",
        reports=(sample_report,),
        errors=(),
        duration=1.5,
    )


class TestJsonReportStore:
    """Tests for JsonReportStore class."""

    def test_正常系_初期化でディレクトリ作成(
        self, store: JsonReportStore, store_dir: Path
    ) -> None:
        assert store_dir.exists()
        assert (store_dir / "runs").exists()
        assert (store_dir / "text").exists()

    def test_正常系_空のインデックス読み込み(self, store: JsonReportStore) -> None:
        index = store.load_index()
        assert index == {"reports": {}}

    def test_正常系_インデックス保存と読み込み(self, store: JsonReportStore) -> None:
        index = {
            "reports": {
                "https://example.com/report/1": {
                    "title": "Test Report",
                    "source_key": "test_source",
                    "published": "2026-03-01T12:00:00+00:00",
                    "collected_at": "2026-03-06T10:00:00+00:00",
                }
            }
        }
        store.save_index(index)
        loaded = store.load_index()
        assert loaded == index

    def test_正常系_実行結果保存(
        self,
        store: JsonReportStore,
        sample_collect_result: CollectResult,
    ) -> None:
        run_path = store.save_run(sample_collect_result, timestamp="2026-03-06T100000")
        assert run_path.exists()
        with run_path.open() as f:
            data = json.load(f)
        assert data["source_key"] == "test_source"
        assert len(data["reports"]) == 1

    def test_正常系_テキスト保存(
        self,
        store: JsonReportStore,
        sample_report: ScrapedReport,
    ) -> None:
        store.save_text(sample_report)
        text_dir = store.data_dir / "text" / "test_source"
        assert text_dir.exists()
        files = list(text_dir.glob("*.txt"))
        assert len(files) == 1

    def test_正常系_コンテンツなしレポートのテキスト保存スキップ(
        self,
        store: JsonReportStore,
        sample_metadata: ReportMetadata,
    ) -> None:
        report = ScrapedReport(metadata=sample_metadata, content=None)
        store.save_text(report)
        text_dir = store.data_dir / "text" / "test_source"
        # Text dir may or may not exist, but should have no files
        if text_dir.exists():
            files = list(text_dir.glob("*.txt"))
            assert len(files) == 0

    def test_正常系_インデックス更新(
        self,
        store: JsonReportStore,
        sample_collect_result: CollectResult,
    ) -> None:
        store.update_index(sample_collect_result)
        index = store.load_index()
        assert "https://example.com/report/1" in index["reports"]
        entry = index["reports"]["https://example.com/report/1"]
        assert entry["title"] == "Test Report"
        assert entry["source_key"] == "test_source"

    def test_正常系_重複URL更新時に上書き(
        self,
        store: JsonReportStore,
        sample_collect_result: CollectResult,
    ) -> None:
        store.update_index(sample_collect_result)
        store.update_index(sample_collect_result)
        index = store.load_index()
        # Only one entry per URL
        assert len(index["reports"]) == 1

    def test_正常系_既知URL判定(
        self,
        store: JsonReportStore,
        sample_collect_result: CollectResult,
    ) -> None:
        assert not store.is_known_url("https://example.com/report/1")
        store.update_index(sample_collect_result)
        assert store.is_known_url("https://example.com/report/1")
        assert not store.is_known_url("https://example.com/report/2")

    def test_異常系_不正なJSON読み込みで空インデックス(
        self,
        store: JsonReportStore,
    ) -> None:
        index_path = store.data_dir / "index.json"
        index_path.write_text("not valid json", encoding="utf-8")
        index = store.load_index()
        assert index == {"reports": {}}
