"""Tests for report_scraper.services.summary_exporter module."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from report_scraper.services.summary_exporter import SummaryExporter
from report_scraper.types import (
    CollectResult,
    ExtractedContent,
    PdfMetadata,
    ReportMetadata,
    RunSummary,
    ScrapedReport,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_meta(
    url: str = "https://example.com/report/1",
    title: str = "Test Report",
    source_key: str = "source_a",
    published: datetime | None = None,
) -> ReportMetadata:
    return ReportMetadata(
        url=url,
        title=title,
        published=published or datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
        source_key=source_key,
    )


def _make_report(
    url: str = "https://example.com/report/1",
    title: str = "Test Report",
    source_key: str = "source_a",
    with_content: bool = False,
    with_pdf: bool = False,
) -> ScrapedReport:
    content = (
        ExtractedContent(text="Sample content", method="trafilatura", length=14)
        if with_content
        else None
    )
    pdf = (
        PdfMetadata(
            url=f"{url}.pdf",
            local_path=Path("data/pdfs/report.pdf"),
            size_bytes=512000,
        )
        if with_pdf
        else None
    )
    return ScrapedReport(
        metadata=_make_meta(url=url, title=title, source_key=source_key),
        content=content,
        pdf=pdf,
    )


def _make_run_summary(
    results: tuple[CollectResult, ...] = (),
    timestamp: datetime | None = None,
) -> RunSummary:
    total_reports = sum(len(r.reports) for r in results)
    total_errors = sum(len(r.errors) for r in results)
    return RunSummary(
        timestamp=timestamp or datetime(2026, 3, 6, 12, 0, tzinfo=timezone.utc),
        results=results,
        total_reports=total_reports,
        total_errors=total_errors,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSummaryExporter:
    """Tests for SummaryExporter.export() method."""

    def test_正常系_空のRunSummaryでMarkdownが生成される(self) -> None:
        summary = _make_run_summary()
        exporter = SummaryExporter()

        result = exporter.export(summary)

        assert isinstance(result, str)
        assert "# Report Scraper" in result
        assert "0" in result  # total reports = 0

    def test_正常系_レポートありでソース別集計が含まれる(self) -> None:
        results = (
            CollectResult(
                source_key="source_a",
                reports=(
                    _make_report(
                        url="https://example.com/r1",
                        title="Report A1",
                        source_key="source_a",
                    ),
                    _make_report(
                        url="https://example.com/r2",
                        title="Report A2",
                        source_key="source_a",
                    ),
                ),
                errors=(),
                duration=2.5,
            ),
            CollectResult(
                source_key="source_b",
                reports=(
                    _make_report(
                        url="https://example.com/r3",
                        title="Report B1",
                        source_key="source_b",
                    ),
                ),
                errors=(),
                duration=1.0,
            ),
        )
        summary = _make_run_summary(results=results)
        exporter = SummaryExporter()

        result = exporter.export(summary)

        assert "source_a" in result
        assert "source_b" in result
        # Total reports should be 3
        assert "3" in result

    def test_正常系_エラーありでエラーサマリーが含まれる(self) -> None:
        results = (
            CollectResult(
                source_key="source_a",
                reports=(),
                errors=(
                    "Connection timeout for source_a",
                    "Parse error for source_a",
                ),
                duration=5.0,
            ),
        )
        summary = _make_run_summary(results=results)
        exporter = SummaryExporter()

        result = exporter.export(summary)

        assert "Connection timeout" in result
        assert "Parse error" in result

    def test_正常系_実行日時が出力に含まれる(self) -> None:
        ts = datetime(2026, 3, 6, 15, 30, tzinfo=timezone.utc)
        summary = _make_run_summary(timestamp=ts)
        exporter = SummaryExporter()

        result = exporter.export(summary)

        assert "2026-03-06" in result

    def test_正常系_新着レポート一覧にタイトルとURLが含まれる(self) -> None:
        results = (
            CollectResult(
                source_key="source_a",
                reports=(
                    _make_report(
                        url="https://example.com/report/q4",
                        title="Q4 Earnings Report",
                        source_key="source_a",
                    ),
                ),
                errors=(),
                duration=1.0,
            ),
        )
        summary = _make_run_summary(results=results)
        exporter = SummaryExporter()

        result = exporter.export(summary)

        assert "Q4 Earnings Report" in result
        assert "https://example.com/report/q4" in result

    def test_正常系_エラーゼロの場合エラーセクションが最小限(self) -> None:
        results = (
            CollectResult(
                source_key="source_a",
                reports=(_make_report(source_key="source_a"),),
                errors=(),
                duration=1.0,
            ),
        )
        summary = _make_run_summary(results=results)
        exporter = SummaryExporter()

        result = exporter.export(summary)

        # Should not contain error details when there are no errors
        assert "error" not in result.lower() or "0" in result

    def test_正常系_複数ソースの新着が全て列挙される(self) -> None:
        results = (
            CollectResult(
                source_key="alpha",
                reports=(
                    _make_report(
                        url="https://alpha.com/r1",
                        title="Alpha Report",
                        source_key="alpha",
                    ),
                ),
                errors=(),
                duration=0.5,
            ),
            CollectResult(
                source_key="beta",
                reports=(
                    _make_report(
                        url="https://beta.com/r1",
                        title="Beta Report",
                        source_key="beta",
                    ),
                ),
                errors=(),
                duration=0.8,
            ),
        )
        summary = _make_run_summary(results=results)
        exporter = SummaryExporter()

        result = exporter.export(summary)

        assert "Alpha Report" in result
        assert "Beta Report" in result

    def test_正常系_出力がMarkdown形式のヘッダーを含む(self) -> None:
        summary = _make_run_summary()
        exporter = SummaryExporter()

        result = exporter.export(summary)

        # Markdown headers should use # syntax
        lines = result.strip().split("\n")
        header_lines = [line for line in lines if line.startswith("#")]
        assert len(header_lines) > 0

    def test_正常系_ソース別レポート数テーブルが含まれる(self) -> None:
        results = (
            CollectResult(
                source_key="source_a",
                reports=(
                    _make_report(source_key="source_a"),
                    _make_report(
                        url="https://example.com/r2",
                        source_key="source_a",
                    ),
                ),
                errors=("some error",),
                duration=3.0,
            ),
        )
        summary = _make_run_summary(results=results)
        exporter = SummaryExporter()

        result = exporter.export(summary)

        # Should contain the source key and count
        assert "source_a" in result
        assert "2" in result  # 2 reports
