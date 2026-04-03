"""Unit tests for fund_db.cli.main module.

Uses Click CliRunner to verify each CLI command's exit code and
basic output. All network I/O is mocked.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from fund_db.cli.main import cli

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def tmp_store(tmp_path: Path) -> Path:
    """Provide a temporary data directory path."""
    return tmp_path / "fund_db"


# ---------------------------------------------------------------------------
# Root CLI
# ---------------------------------------------------------------------------


class TestCli:
    """Tests for the root CLI group."""

    def test_正常系_ヘルプが全サブグループを表示する(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "nisa" in result.output
        assert "jpx" in result.output
        assert "stats" in result.output
        assert "etf" in result.output
        assert "sync-all" in result.output
        assert "status" in result.output

    def test_正常系_datadirオプションが受け付けられる(
        self, runner: CliRunner, tmp_store: Path
    ) -> None:
        result = runner.invoke(cli, ["--data-dir", str(tmp_store), "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# nisa group
# ---------------------------------------------------------------------------


class TestNisaGroup:
    """Tests for the nisa subgroup commands."""

    def test_正常系_nisaヘルプが全コマンドを表示する(
        self, runner: CliRunner, tmp_store: Path
    ) -> None:
        result = runner.invoke(cli, ["--data-dir", str(tmp_store), "nisa", "--help"])
        assert result.exit_code == 0
        assert "download" in result.output
        assert "parse" in result.output
        assert "sync" in result.output
        assert "list" in result.output

    @patch("fund_db.nisa.downloader.NisaDownloader.download_all")
    def test_正常系_nisaダウンロードが成功する(
        self, mock_download: MagicMock, runner: CliRunner, tmp_store: Path
    ) -> None:
        from fund_db.types import DownloadResult

        mock_download.return_value = [
            DownloadResult(
                path=Path("/tmp/test.xlsx"),
                url="https://example.com/test.xlsx",
                size_bytes=1024,
                downloaded_at=datetime.now(timezone.utc),
            ),
        ]
        result = runner.invoke(cli, ["--data-dir", str(tmp_store), "nisa", "download"])
        assert result.exit_code == 0
        assert "Downloaded" in result.output

    @patch("fund_db.nisa.downloader.NisaDownloader.download_all")
    def test_異常系_nisaダウンロードエラーで終了コード1(
        self, mock_download: MagicMock, runner: CliRunner, tmp_store: Path
    ) -> None:
        mock_download.side_effect = RuntimeError("Network error")
        result = runner.invoke(cli, ["--data-dir", str(tmp_store), "nisa", "download"])
        assert result.exit_code == 1
        assert "Error" in result.output

    def test_正常系_nisaパースでデータなし警告(
        self, runner: CliRunner, tmp_store: Path
    ) -> None:
        result = runner.invoke(cli, ["--data-dir", str(tmp_store), "nisa", "parse"])
        assert result.exit_code == 0
        assert "No NISA" in result.output or "Total:" in result.output

    def test_正常系_nisaリストでデータなし警告(
        self, runner: CliRunner, tmp_store: Path
    ) -> None:
        result = runner.invoke(cli, ["--data-dir", str(tmp_store), "nisa", "list"])
        assert result.exit_code == 0
        assert "No NISA" in result.output


# ---------------------------------------------------------------------------
# jpx group
# ---------------------------------------------------------------------------


class TestJpxGroup:
    """Tests for the jpx subgroup commands."""

    def test_正常系_jpxヘルプが全コマンドを表示する(
        self, runner: CliRunner, tmp_store: Path
    ) -> None:
        result = runner.invoke(cli, ["--data-dir", str(tmp_store), "jpx", "--help"])
        assert result.exit_code == 0
        assert "download" in result.output
        assert "parse" in result.output
        assert "sync" in result.output
        assert "list-etfs" in result.output

    @patch("fund_db.jpx.downloader.JpxDownloader.download")
    def test_正常系_jpxダウンロードが成功する(
        self, mock_download: MagicMock, runner: CliRunner, tmp_store: Path
    ) -> None:
        from fund_db.types import DownloadResult

        mock_download.return_value = DownloadResult(
            path=Path("/tmp/data_j.xls"),
            url="https://example.com/data_j.xls",
            size_bytes=2048,
            downloaded_at=datetime.now(timezone.utc),
        )
        result = runner.invoke(cli, ["--data-dir", str(tmp_store), "jpx", "download"])
        assert result.exit_code == 0
        assert "Downloaded" in result.output

    @patch("fund_db.jpx.downloader.JpxDownloader.download")
    def test_異常系_jpxダウンロードエラーで終了コード1(
        self, mock_download: MagicMock, runner: CliRunner, tmp_store: Path
    ) -> None:
        mock_download.side_effect = RuntimeError("Network error")
        result = runner.invoke(cli, ["--data-dir", str(tmp_store), "jpx", "download"])
        assert result.exit_code == 1

    def test_正常系_jpxパースでデータなし警告(
        self, runner: CliRunner, tmp_store: Path
    ) -> None:
        result = runner.invoke(cli, ["--data-dir", str(tmp_store), "jpx", "parse"])
        assert result.exit_code == 0
        assert "No JPX" in result.output or "Total:" in result.output

    def test_正常系_jpxリストETFでデータなし警告(
        self, runner: CliRunner, tmp_store: Path
    ) -> None:
        result = runner.invoke(cli, ["--data-dir", str(tmp_store), "jpx", "list-etfs"])
        assert result.exit_code == 0
        assert "No JPX" in result.output


# ---------------------------------------------------------------------------
# stats group
# ---------------------------------------------------------------------------


class TestStatsGroup:
    """Tests for the stats subgroup commands."""

    def test_正常系_statsヘルプが全コマンドを表示する(
        self, runner: CliRunner, tmp_store: Path
    ) -> None:
        result = runner.invoke(cli, ["--data-dir", str(tmp_store), "stats", "--help"])
        assert result.exit_code == 0
        assert "download" in result.output
        assert "parse" in result.output
        assert "sync" in result.output
        assert "summary" in result.output

    @patch("fund_db.toushin_stats.downloader.ToushinStatsDownloader.download_all")
    def test_正常系_statsダウンロードが成功する(
        self, mock_download: MagicMock, runner: CliRunner, tmp_store: Path
    ) -> None:
        from fund_db.types import DownloadResult

        mock_download.return_value = [
            DownloadResult(
                path=Path("/tmp/stats_b1.xlsx"),
                url="https://example.com/b1.xlsx",
                size_bytes=512,
                downloaded_at=datetime.now(timezone.utc),
            ),
        ]
        result = runner.invoke(cli, ["--data-dir", str(tmp_store), "stats", "download"])
        assert result.exit_code == 0
        assert "Downloaded" in result.output

    @patch("fund_db.toushin_stats.downloader.ToushinStatsDownloader.download_all")
    def test_異常系_statsダウンロードエラーで終了コード1(
        self, mock_download: MagicMock, runner: CliRunner, tmp_store: Path
    ) -> None:
        mock_download.side_effect = RuntimeError("Network error")
        result = runner.invoke(cli, ["--data-dir", str(tmp_store), "stats", "download"])
        assert result.exit_code == 1

    def test_正常系_statsSummaryでデータなし表示(
        self, runner: CliRunner, tmp_store: Path
    ) -> None:
        result = runner.invoke(cli, ["--data-dir", str(tmp_store), "stats", "summary"])
        assert result.exit_code == 0
        # Should display the table even with no data
        assert "Statistics Summary" in result.output or "No data" in result.output


# ---------------------------------------------------------------------------
# etf group
# ---------------------------------------------------------------------------


class TestEtfGroup:
    """Tests for the etf subgroup commands."""

    def test_正常系_etfヘルプが全コマンドを表示する(
        self, runner: CliRunner, tmp_store: Path
    ) -> None:
        result = runner.invoke(cli, ["--data-dir", str(tmp_store), "etf", "--help"])
        assert result.exit_code == 0
        assert "fetch" in result.output
        assert "performance" in result.output

    @patch("fund_db.etf_prices.fetcher.EtfPriceFetcher.fetch")
    def test_正常系_etfフェッチが成功する(
        self, mock_fetch: MagicMock, runner: CliRunner, tmp_store: Path
    ) -> None:
        from fund_db.etf_prices.models import EtfPriceRecord

        mock_fetch.return_value = [
            EtfPriceRecord(
                ticker="1306.T",
                date=date(2026, 4, 1),
                open=2500.0,
                high=2550.0,
                low=2480.0,
                close=2520.0,
                volume=100000,
            ),
        ]
        result = runner.invoke(
            cli,
            [
                "--data-dir",
                str(tmp_store),
                "etf",
                "fetch",
                "--tickers",
                "1306",
                "--start",
                "2026-01-01",
            ],
        )
        assert result.exit_code == 0
        assert "1306.T" in result.output

    @patch("fund_db.etf_prices.fetcher.EtfPriceFetcher.fetch")
    def test_正常系_etfフェッチでデータなし(
        self, mock_fetch: MagicMock, runner: CliRunner, tmp_store: Path
    ) -> None:
        mock_fetch.return_value = []
        result = runner.invoke(
            cli,
            [
                "--data-dir",
                str(tmp_store),
                "etf",
                "fetch",
                "--tickers",
                "9999",
                "--start",
                "2026-01-01",
            ],
        )
        assert result.exit_code == 0
        assert "No price data" in result.output

    def test_異常系_etfフェッチでtickersなしエラー(
        self, runner: CliRunner, tmp_store: Path
    ) -> None:
        result = runner.invoke(
            cli,
            ["--data-dir", str(tmp_store), "etf", "fetch", "--start", "2026-01-01"],
        )
        assert result.exit_code != 0

    @patch("fund_db.etf_prices.fetcher.EtfPriceFetcher.get_performance")
    def test_正常系_etfパフォーマンスが成功する(
        self, mock_perf: MagicMock, runner: CliRunner, tmp_store: Path
    ) -> None:
        from fund_db.etf_prices.models import EtfPerformanceSummary

        mock_perf.return_value = [
            EtfPerformanceSummary(
                ticker="1306.T",
                period_start=date(2023, 4, 1),
                period_end=date(2026, 4, 1),
                total_return=0.45,
                annualized_volatility=0.18,
                max_drawdown=-0.12,
            ),
        ]
        result = runner.invoke(
            cli,
            [
                "--data-dir",
                str(tmp_store),
                "etf",
                "performance",
                "--tickers",
                "1306",
                "--years",
                "3",
            ],
        )
        assert result.exit_code == 0
        assert "1306.T" in result.output
        assert "+45.0%" in result.output

    @patch("fund_db.etf_prices.fetcher.EtfPriceFetcher.get_performance")
    def test_正常系_etfパフォーマンスでデータなし(
        self, mock_perf: MagicMock, runner: CliRunner, tmp_store: Path
    ) -> None:
        mock_perf.return_value = []
        result = runner.invoke(
            cli,
            [
                "--data-dir",
                str(tmp_store),
                "etf",
                "performance",
                "--tickers",
                "9999",
            ],
        )
        assert result.exit_code == 0
        assert "No performance data" in result.output


# ---------------------------------------------------------------------------
# sync-all command
# ---------------------------------------------------------------------------


class TestSyncAll:
    """Tests for the sync-all command."""

    @patch("fund_db.toushin_stats.downloader.ToushinStatsDownloader.download_all")
    @patch("fund_db.jpx.downloader.JpxDownloader.download")
    @patch("fund_db.nisa.downloader.NisaDownloader.download_all")
    def test_正常系_syncallが全グループを順次実行する(
        self,
        mock_nisa_dl: MagicMock,
        mock_jpx_dl: MagicMock,
        mock_stats_dl: MagicMock,
        runner: CliRunner,
        tmp_store: Path,
    ) -> None:
        from fund_db.types import DownloadResult

        dl_result = DownloadResult(
            path=Path("/tmp/test.xlsx"),
            url="https://example.com/test.xlsx",
            size_bytes=512,
            downloaded_at=datetime.now(timezone.utc),
        )
        mock_nisa_dl.return_value = [dl_result]
        mock_jpx_dl.return_value = dl_result
        mock_stats_dl.return_value = [dl_result]

        result = runner.invoke(cli, ["--data-dir", str(tmp_store), "sync-all"])
        # sync-all should not fail even if parse finds no raw files
        assert "sync-all complete" in result.output

    @patch("fund_db.nisa.downloader.NisaDownloader.download_all")
    def test_正常系_syncallで一部失敗しても継続する(
        self,
        mock_nisa_dl: MagicMock,
        runner: CliRunner,
        tmp_store: Path,
    ) -> None:
        mock_nisa_dl.side_effect = RuntimeError("NISA download failed")

        result = runner.invoke(cli, ["--data-dir", str(tmp_store), "sync-all"])
        # Should continue despite NISA failure
        assert "sync-all complete" in result.output


# ---------------------------------------------------------------------------
# status command
# ---------------------------------------------------------------------------


class TestStatus:
    """Tests for the status command."""

    def test_正常系_statusが全カテゴリを表示する(
        self, runner: CliRunner, tmp_store: Path
    ) -> None:
        result = runner.invoke(cli, ["--data-dir", str(tmp_store), "status"])
        assert result.exit_code == 0
        assert "Data Status" in result.output

    def test_正常系_statusでデータあり時にパーティション表示(
        self, runner: CliRunner, tmp_store: Path
    ) -> None:
        from fund_db.storage import FundDbStore

        store = FundDbStore(data_dir=tmp_store)
        store.save_records(
            [{"fund_name": "Test Fund", "association_code": "00001"}],
            "nisa_unlisted",
            date(2026, 4, 1),
        )

        result = runner.invoke(cli, ["--data-dir", str(tmp_store), "status"])
        assert result.exit_code == 0
        assert "2026-04-01" in result.output
