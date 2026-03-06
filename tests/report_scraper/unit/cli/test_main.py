"""Tests for report_scraper.cli.main module."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

if TYPE_CHECKING:
    from pathlib import Path

from report_scraper.cli.main import cli
from report_scraper.types import (
    CollectResult,
    ExtractedContent,
    ReportMetadata,
    ReportScraperConfig,
    ScrapedReport,
    SourceConfig,
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


# ---------------------------------------------------------------------------
# Fixtures for list / test-source commands
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_config() -> ReportScraperConfig:
    """Create a sample ReportScraperConfig with multiple sources."""
    return ReportScraperConfig(
        sources=[
            SourceConfig(
                key="advisor_perspectives",
                name="Advisor Perspectives",
                tier="aggregator",
                listing_url="https://www.advisorperspectives.com/articles",
                rendering="static",
                tags=["macro", "equity"],
                max_reports=15,
            ),
            SourceConfig(
                key="blackrock_bii",
                name="BlackRock Investment Institute",
                tier="buy_side",
                listing_url="https://www.blackrock.com/corporate/insights",
                rendering="static",
                tags=["macro", "weekly"],
            ),
            SourceConfig(
                key="schwab",
                name="Charles Schwab",
                tier="sell_side",
                listing_url="https://www.schwab.com/learn/market-commentary",
                rendering="static",
                tags=["macro", "equity", "sector"],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Tests: list command
# ---------------------------------------------------------------------------


class TestListCommand:
    """Tests for the list command."""

    def test_正常系_ヘルプ表示(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["list", "--help"])
        assert result.exit_code == 0
        assert "--tier" in result.output

    @patch("report_scraper.cli.main.load_config")
    def test_正常系_全ソース一覧表示(
        self,
        mock_load_config: MagicMock,
        runner: CliRunner,
        sample_config: ReportScraperConfig,
    ) -> None:
        mock_load_config.return_value = sample_config
        result = runner.invoke(cli, ["list"])
        assert result.exit_code == 0
        # AIDEV-NOTE: Rich Table may truncate long text in narrow terminals.
        # Check for source keys which are short and always visible.
        assert "advisor_perspectives" in result.output
        assert "blackrock_bii" in result.output
        assert "schwab" in result.output

    @patch("report_scraper.cli.main.load_config")
    def test_正常系_tierフィルタでbuy_side(
        self,
        mock_load_config: MagicMock,
        runner: CliRunner,
        sample_config: ReportScraperConfig,
    ) -> None:
        mock_load_config.return_value = sample_config
        result = runner.invoke(cli, ["list", "--tier", "buy_side"])
        assert result.exit_code == 0
        assert "BlackRock" in result.output
        # buy_side 以外は表示されないこと
        assert "Advisor Perspectives" not in result.output
        assert "Schwab" not in result.output

    @patch("report_scraper.cli.main.load_config")
    def test_正常系_tierフィルタでsell_side(
        self,
        mock_load_config: MagicMock,
        runner: CliRunner,
        sample_config: ReportScraperConfig,
    ) -> None:
        mock_load_config.return_value = sample_config
        result = runner.invoke(cli, ["list", "--tier", "sell_side"])
        assert result.exit_code == 0
        assert "Schwab" in result.output
        assert "BlackRock" not in result.output

    @patch("report_scraper.cli.main.load_config")
    def test_正常系_tierフィルタでaggregator(
        self,
        mock_load_config: MagicMock,
        runner: CliRunner,
        sample_config: ReportScraperConfig,
    ) -> None:
        mock_load_config.return_value = sample_config
        result = runner.invoke(cli, ["list", "--tier", "aggregator"])
        assert result.exit_code == 0
        assert "advisor_perspectives" in result.output
        assert "blackrock_bii" not in result.output

    @patch("report_scraper.cli.main.load_config")
    def test_正常系_tierフィルタで該当なし(
        self,
        mock_load_config: MagicMock,
        runner: CliRunner,
    ) -> None:
        config = ReportScraperConfig(
            sources=[
                SourceConfig(
                    key="test",
                    name="Test",
                    tier="sell_side",
                    listing_url="https://example.com",
                    rendering="static",
                ),
            ],
        )
        mock_load_config.return_value = config
        result = runner.invoke(cli, ["list", "--tier", "buy_side"])
        assert result.exit_code == 0
        assert "No sources found" in result.output

    @patch("report_scraper.cli.main.load_config")
    def test_正常系_テーブルにkey列とtier列が含まれる(
        self,
        mock_load_config: MagicMock,
        runner: CliRunner,
        sample_config: ReportScraperConfig,
    ) -> None:
        mock_load_config.return_value = sample_config
        result = runner.invoke(cli, ["list"])
        assert result.exit_code == 0
        # AIDEV-NOTE: Rich may truncate "aggregator" to "aggrega..." in narrow terminal.
        # Check for key (always visible) and partial tier match.
        assert "advisor_perspectives" in result.output
        assert "aggrega" in result.output


# ---------------------------------------------------------------------------
# Tests: test-source command
# ---------------------------------------------------------------------------


class TestTestSourceCommand:
    """Tests for the test-source command."""

    def test_正常系_ヘルプ表示(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["test-source", "--help"])
        assert result.exit_code == 0
        assert "key" in result.output.lower()

    @patch("report_scraper.cli.main.load_config")
    def test_正常系_存在するソースでdry_run(
        self,
        mock_load_config: MagicMock,
        runner: CliRunner,
        sample_config: ReportScraperConfig,
    ) -> None:
        mock_load_config.return_value = sample_config
        result = runner.invoke(cli, ["test-source", "advisor_perspectives"])
        assert result.exit_code == 0
        assert "advisor_perspectives" in result.output

    @patch("report_scraper.cli.main.load_config")
    def test_異常系_存在しないソースキー(
        self,
        mock_load_config: MagicMock,
        runner: CliRunner,
        sample_config: ReportScraperConfig,
    ) -> None:
        mock_load_config.return_value = sample_config
        result = runner.invoke(cli, ["test-source", "nonexistent_source"])
        assert result.exit_code != 0

    @patch("report_scraper.cli.main.load_config")
    def test_正常系_ソース設定詳細が表示される(
        self,
        mock_load_config: MagicMock,
        runner: CliRunner,
        sample_config: ReportScraperConfig,
    ) -> None:
        mock_load_config.return_value = sample_config
        result = runner.invoke(cli, ["test-source", "blackrock_bii"])
        assert result.exit_code == 0
        assert "BlackRock Investment Institute" in result.output
        assert "buy_side" in result.output
        assert "static" in result.output


# ---------------------------------------------------------------------------
# Tests: history command
# ---------------------------------------------------------------------------


class TestHistoryCommand:
    """Tests for the history command."""

    def test_正常系_ヘルプ表示(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["history", "--help"])
        assert result.exit_code == 0
        assert "--days" in result.output

    def test_正常系_履歴なしでメッセージ表示(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        result = runner.invoke(
            cli,
            ["--data-dir", str(tmp_path / "empty"), "history", "--days", "7"],
        )
        assert result.exit_code == 0
        assert "No reports collected" in result.output

    def test_正常系_履歴ありでテーブル表示(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        # Pre-populate index with a recent entry
        from report_scraper.services.dedup_tracker import DedupTracker
        from report_scraper.storage.json_store import JsonReportStore

        data_dir = tmp_path / "history_test"
        store = JsonReportStore(data_dir)
        tracker = DedupTracker(store, dedup_days=30)
        tracker.mark_seen("test_source", "https://example.com/report-1")

        # Update the entry to have a title
        index = store.load_index()
        index["reports"]["https://example.com/report-1"]["title"] = "Test Report Title"
        store.save_index(index)

        result = runner.invoke(
            cli,
            ["--data-dir", str(data_dir), "history", "--days", "7"],
        )
        assert result.exit_code == 0
        assert "1" in result.output  # at least "1 report(s)"
        assert "test_source" in result.output

    def test_正常系_daysオプションのデフォルトは7(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["history", "--help"])
        assert result.exit_code == 0
        assert "7" in result.output
