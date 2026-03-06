"""Tests for report_scraper.cli.main module."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from report_scraper.cli.main import cli
from report_scraper.types import (
    CollectResult,
    ExtractedContent,
    ReportMetadata,
    ScrapedReport,
)


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def sample_collect_result() -> CollectResult:
    """Create a sample CollectResult for testing."""
    meta = ReportMetadata(
        url="https://example.com/report/1",
        title="Test Report",
        published=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
        source_key="advisor_perspectives",
    )
    content = ExtractedContent(
        text="Full report content. " * 10,
        method="trafilatura",
        length=210,
    )
    report = ScrapedReport(metadata=meta, content=content)
    return CollectResult(
        source_key="advisor_perspectives",
        reports=(report,),
        errors=(),
        duration=2.5,
    )


class TestCli:
    """Tests for CLI group."""

    def test_正常系_ヘルプ表示(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Report Scraper CLI" in result.output

    def test_正常系_data_dirオプション(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["--data-dir", "/tmp/test", "--help"])
        assert result.exit_code == 0


class TestCollectCommand:
    """Tests for the collect command."""

    def test_正常系_ヘルプ表示(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["collect", "--help"])
        assert result.exit_code == 0
        assert "--source" in result.output

    @patch("report_scraper.cli.main._get_scraper")
    def test_正常系_source指定で収集(
        self,
        mock_get_scraper: MagicMock,
        runner: CliRunner,
        sample_collect_result: CollectResult,
    ) -> None:
        mock_scraper = MagicMock()
        mock_scraper.collect_latest = AsyncMock(return_value=sample_collect_result)
        mock_get_scraper.return_value = mock_scraper

        with patch("report_scraper.cli.main._save_results"):
            result = runner.invoke(cli, ["collect", "--source", "advisor_perspectives"])

        assert result.exit_code == 0
        assert "advisor_perspectives" in result.output or "Report" in result.output

    @patch("report_scraper.cli.main._get_scraper")
    def test_異常系_不明なsource(
        self,
        mock_get_scraper: MagicMock,
        runner: CliRunner,
    ) -> None:
        mock_get_scraper.return_value = None
        result = runner.invoke(cli, ["collect", "--source", "unknown_source"])
        assert result.exit_code != 0

    def test_異常系_sourceオプション未指定(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["collect"])
        assert result.exit_code != 0
