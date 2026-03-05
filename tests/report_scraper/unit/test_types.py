"""Unit tests for report_scraper.types module.

Tests cover:
- Frozen dataclass immutability
- Pydantic validation (required fields, type constraints)
- Default values and optional fields
- Exception hierarchy inheritance
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from report_scraper.exceptions import (
    ConfigError,
    ExtractionError,
    FetchError,
    ReportScraperError,
)
from report_scraper.types import (
    CollectResult,
    ExtractedContent,
    GlobalConfig,
    PdfMetadata,
    ReportMetadata,
    RunSummary,
    ScrapedReport,
    SourceConfig,
    TimeoutConfig,
)

# ---------------------------------------------------------------------------
# SourceConfig (Pydantic)
# ---------------------------------------------------------------------------


class TestSourceConfig:
    """Tests for SourceConfig Pydantic model."""

    def test_正常系_必須フィールドで生成できる(self) -> None:
        config = SourceConfig(
            key="test",
            name="Test Source",
            tier="sell_side",
            listing_url="https://example.com",
            rendering="static",
        )
        assert config.key == "test"
        assert config.name == "Test Source"
        assert config.tier == "sell_side"
        assert config.rendering == "static"

    def test_正常系_オプションフィールドのデフォルト値(self) -> None:
        config = SourceConfig(
            key="test",
            name="Test",
            tier="buy_side",
            listing_url="https://example.com",
            rendering="rss",
        )
        assert config.tags == []
        assert config.pdf_selector is None
        assert config.article_selector is None
        assert config.max_reports is None

    def test_正常系_全フィールドを指定できる(self) -> None:
        config = SourceConfig(
            key="full",
            name="Full Config",
            tier="aggregator",
            listing_url="https://example.com/reports",
            rendering="playwright",
            tags=["macro", "equity"],
            pdf_selector="a.pdf-link",
            article_selector="div.report-item",
            max_reports=10,
        )
        assert config.tags == ["macro", "equity"]
        assert config.pdf_selector == "a.pdf-link"
        assert config.max_reports == 10

    def test_異常系_必須フィールド欠落でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            SourceConfig(  # type: ignore[call-arg]
                key="test",
                name="Test",
                # tier missing
                listing_url="https://example.com",
                rendering="static",
            )

    def test_異常系_空文字列のkeyでValidationError(self) -> None:
        with pytest.raises(ValidationError):
            SourceConfig(
                key="",
                name="Test",
                tier="sell_side",
                listing_url="https://example.com",
                rendering="static",
            )

    def test_異常系_不正なtierでValidationError(self) -> None:
        with pytest.raises(ValidationError):
            SourceConfig(
                key="test",
                name="Test",
                tier="invalid_tier",  # type: ignore[arg-type]
                listing_url="https://example.com",
                rendering="static",
            )

    def test_異常系_不正なrenderingでValidationError(self) -> None:
        with pytest.raises(ValidationError):
            SourceConfig(
                key="test",
                name="Test",
                tier="sell_side",
                listing_url="https://example.com",
                rendering="invalid",  # type: ignore[arg-type]
            )

    def test_異常系_max_reportsが0以下でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            SourceConfig(
                key="test",
                name="Test",
                tier="sell_side",
                listing_url="https://example.com",
                rendering="static",
                max_reports=0,
            )


# ---------------------------------------------------------------------------
# GlobalConfig (Pydantic)
# ---------------------------------------------------------------------------


class TestGlobalConfig:
    """Tests for GlobalConfig Pydantic model."""

    def test_正常系_デフォルト値で生成できる(self) -> None:
        config = GlobalConfig()
        assert config.output_dir == Path("data/scraped/reports")
        assert config.pdf_dir == Path("data/scraped/pdfs")
        assert config.max_reports_per_source == 20
        assert config.dedup_days == 30

    def test_正常系_カスタム値で生成できる(self) -> None:
        config = GlobalConfig(
            output_dir=Path("/tmp/reports"),
            pdf_dir=Path("/tmp/pdfs"),
            max_reports_per_source=50,
            dedup_days=60,
        )
        assert config.output_dir == Path("/tmp/reports")
        assert config.max_reports_per_source == 50
        assert config.dedup_days == 60

    def test_正常系_TimeoutConfigのデフォルト値(self) -> None:
        config = GlobalConfig()
        assert config.timeouts.connect == 10
        assert config.timeouts.read == 30

    def test_異常系_max_reports_per_sourceが0以下でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            GlobalConfig(max_reports_per_source=0)

    def test_異常系_dedup_daysが0以下でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            GlobalConfig(dedup_days=0)

    def test_異常系_dedup_daysが365超でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            GlobalConfig(dedup_days=400)


class TestTimeoutConfig:
    """Tests for TimeoutConfig Pydantic model."""

    def test_正常系_デフォルト値(self) -> None:
        t = TimeoutConfig()
        assert t.connect == 10
        assert t.read == 30

    def test_異常系_connectが0でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            TimeoutConfig(connect=0)


# ---------------------------------------------------------------------------
# ReportMetadata (frozen dataclass)
# ---------------------------------------------------------------------------


class TestReportMetadata:
    """Tests for ReportMetadata frozen dataclass."""

    def test_正常系_必須フィールドで生成できる(self) -> None:
        meta = ReportMetadata(
            url="https://example.com/report",
            title="Test Report",
            published=datetime(2026, 1, 1, tzinfo=timezone.utc),
            source_key="test",
        )
        assert meta.url == "https://example.com/report"
        assert meta.title == "Test Report"
        assert meta.source_key == "test"

    def test_正常系_オプションフィールドのデフォルト値(self) -> None:
        meta = ReportMetadata(
            url="https://example.com",
            title="Test",
            published=datetime(2026, 1, 1, tzinfo=timezone.utc),
            source_key="test",
        )
        assert meta.pdf_url is None
        assert meta.author is None
        assert meta.tags == ()

    def test_正常系_不変性_フィールド変更でFrozenInstanceError(self) -> None:
        meta = ReportMetadata(
            url="https://example.com",
            title="Test",
            published=datetime(2026, 1, 1, tzinfo=timezone.utc),
            source_key="test",
        )
        with pytest.raises(FrozenInstanceError):
            meta.title = "Changed"  # type: ignore[misc]

    def test_正常系_フィクスチャから生成できる(
        self, sample_report_metadata: ReportMetadata
    ) -> None:
        assert sample_report_metadata.url == "https://example.com/report/q4-2025"
        assert sample_report_metadata.author == "Test Author"
        assert sample_report_metadata.tags == ("macro", "outlook")


# ---------------------------------------------------------------------------
# ExtractedContent (frozen dataclass)
# ---------------------------------------------------------------------------


class TestExtractedContent:
    """Tests for ExtractedContent frozen dataclass."""

    def test_正常系_全フィールドで生成できる(self) -> None:
        content = ExtractedContent(
            text="Report content here.",
            method="trafilatura",
            length=20,
        )
        assert content.text == "Report content here."
        assert content.method == "trafilatura"
        assert content.length == 20

    def test_正常系_不変性_フィールド変更でFrozenInstanceError(self) -> None:
        content = ExtractedContent(text="test", method="lxml", length=4)
        with pytest.raises(FrozenInstanceError):
            content.text = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# PdfMetadata (frozen dataclass)
# ---------------------------------------------------------------------------


class TestPdfMetadata:
    """Tests for PdfMetadata frozen dataclass."""

    def test_正常系_全フィールドで生成できる(self) -> None:
        pdf = PdfMetadata(
            url="https://example.com/report.pdf",
            local_path=Path("data/pdfs/report.pdf"),
            size_bytes=512000,
        )
        assert pdf.url == "https://example.com/report.pdf"
        assert pdf.local_path == Path("data/pdfs/report.pdf")
        assert pdf.size_bytes == 512000

    def test_正常系_不変性_フィールド変更でFrozenInstanceError(self) -> None:
        pdf = PdfMetadata(
            url="https://example.com/report.pdf",
            local_path=Path("data/pdfs/report.pdf"),
            size_bytes=512000,
        )
        with pytest.raises(FrozenInstanceError):
            pdf.size_bytes = 0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ScrapedReport (frozen dataclass)
# ---------------------------------------------------------------------------


class TestScrapedReport:
    """Tests for ScrapedReport frozen dataclass."""

    def test_正常系_メタデータのみで生成できる(self) -> None:
        meta = ReportMetadata(
            url="https://example.com",
            title="Test",
            published=datetime(2026, 1, 1, tzinfo=timezone.utc),
            source_key="test",
        )
        report = ScrapedReport(metadata=meta)
        assert report.metadata == meta
        assert report.content is None
        assert report.pdf is None

    def test_正常系_全フィールドで生成できる(
        self, sample_scraped_report: ScrapedReport
    ) -> None:
        assert sample_scraped_report.metadata is not None
        assert sample_scraped_report.content is not None
        assert sample_scraped_report.pdf is not None

    def test_正常系_不変性_フィールド変更でFrozenInstanceError(
        self, sample_scraped_report: ScrapedReport
    ) -> None:
        with pytest.raises(FrozenInstanceError):
            sample_scraped_report.content = None  # type: ignore[misc]


# ---------------------------------------------------------------------------
# CollectResult (frozen dataclass)
# ---------------------------------------------------------------------------


class TestCollectResult:
    """Tests for CollectResult frozen dataclass."""

    def test_正常系_デフォルト値で生成できる(self) -> None:
        result = CollectResult(source_key="test")
        assert result.source_key == "test"
        assert result.reports == ()
        assert result.errors == ()
        assert result.duration == 0.0

    def test_正常系_不変性_フィールド変更でFrozenInstanceError(self) -> None:
        result = CollectResult(source_key="test")
        with pytest.raises(FrozenInstanceError):
            result.source_key = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# RunSummary (frozen dataclass)
# ---------------------------------------------------------------------------


class TestRunSummary:
    """Tests for RunSummary frozen dataclass."""

    def test_正常系_必須フィールドで生成できる(self) -> None:
        summary = RunSummary(
            timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        assert summary.results == ()
        assert summary.total_reports == 0
        assert summary.total_errors == 0

    def test_正常系_結果を含む生成(self, sample_collect_result: CollectResult) -> None:
        summary = RunSummary(
            timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
            results=(sample_collect_result,),
            total_reports=1,
            total_errors=0,
        )
        assert len(summary.results) == 1
        assert summary.total_reports == 1

    def test_正常系_不変性_フィールド変更でFrozenInstanceError(self) -> None:
        summary = RunSummary(
            timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        with pytest.raises(FrozenInstanceError):
            summary.total_reports = 10  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class TestExceptionHierarchy:
    """Tests for the exception hierarchy."""

    def test_正常系_FetchErrorはReportScraperErrorを継承(self) -> None:
        assert issubclass(FetchError, ReportScraperError)

    def test_正常系_ExtractionErrorはReportScraperErrorを継承(self) -> None:
        assert issubclass(ExtractionError, ReportScraperError)

    def test_正常系_ConfigErrorはReportScraperErrorを継承(self) -> None:
        assert issubclass(ConfigError, ReportScraperError)

    def test_正常系_ReportScraperErrorはExceptionを継承(self) -> None:
        assert issubclass(ReportScraperError, Exception)

    def test_正常系_FetchErrorの属性(self) -> None:
        err = FetchError("timeout", url="https://example.com", status_code=408)
        assert str(err) == "timeout"
        assert err.url == "https://example.com"
        assert err.status_code == 408

    def test_正常系_ExtractionErrorの属性(self) -> None:
        err = ExtractionError(
            "parse failed", url="https://example.com", method="trafilatura"
        )
        assert err.url == "https://example.com"
        assert err.method == "trafilatura"

    def test_正常系_ConfigErrorの属性(self) -> None:
        err = ConfigError("missing field", field="listing_url")
        assert err.field == "listing_url"

    def test_正常系_基底クラスで全例外をキャッチできる(self) -> None:
        exceptions: list[ReportScraperError] = [
            FetchError("fetch", url="https://example.com"),
            ExtractionError("extract", url="https://example.com"),
            ConfigError("config"),
        ]
        for exc in exceptions:
            with pytest.raises(ReportScraperError):
                raise exc

    def test_正常系_FetchErrorのstatus_codeデフォルト値(self) -> None:
        err = FetchError("timeout", url="https://example.com")
        assert err.status_code is None

    def test_正常系_ExtractionErrorのmethodデフォルト値(self) -> None:
        err = ExtractionError("failed", url="https://example.com")
        assert err.method is None

    def test_正常系_ConfigErrorのfieldデフォルト値(self) -> None:
        err = ConfigError("invalid config")
        assert err.field is None
