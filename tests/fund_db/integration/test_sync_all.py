"""Integration tests for fund_db sync-all workflow.

Tests the parse + save portion of the sync-all workflow using
pre-saved raw files in a temporary FundDbStore. Does not perform
actual HTTP downloads.

All tests are marked with @pytest.mark.integration.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from fund_db.cli.main import cli
from fund_db.storage import FundDbStore

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def store_with_records(tmp_path: Path) -> tuple[FundDbStore, Path]:
    """Create a FundDbStore with pre-saved test records.

    Simulates the state after download + parse has completed successfully.
    Returns the store and the data directory path.
    """
    data_dir = tmp_path / "fund_db"
    store = FundDbStore(data_dir=data_dir)

    partition_date = date(2026, 4, 1)

    # Save sample NISA unlisted records
    nisa_unlisted_records = [
        {
            "association_code": "01311046",
            "fund_name": "eMAXIS Slim 全世界株式（オール・カントリー）",
            "management_company": "三菱UFJアセットマネジメント",
            "asset_class": "株式",
            "investment_region": "内外",
            "fund_type": "インデックス型",
            "benchmark_index": "MSCI ACWI",
            "expense_ratio": "0.05775%",
            "tsumitate_eligible": "○",
            "growth_eligible": "○",
        },
        {
            "association_code": "01319228",
            "fund_name": "たわらノーロード 先進国株式",
            "management_company": "アセットマネジメントOne",
            "asset_class": "株式",
            "investment_region": "海外",
            "fund_type": "インデックス型",
            "benchmark_index": "MSCI Kokusai",
            "expense_ratio": "0.09889%",
            "tsumitate_eligible": "○",
            "growth_eligible": "○",
        },
    ]
    store.save_records(nisa_unlisted_records, "nisa_unlisted", partition_date)

    # Save sample NISA listed records
    nisa_listed_records = [
        {
            "ticker_code": "1306",
            "fund_name": "NEXT FUNDS TOPIX連動型上場投信",
            "management_company": "野村アセットマネジメント",
            "benchmark_index": "TOPIX",
            "expense_ratio": "0.0616%",
            "trading_unit": "10口",
        },
    ]
    store.save_records(nisa_listed_records, "nisa_listed", partition_date)

    # Save sample JPX listed records
    jpx_listed_records = [
        {
            "ticker_code": "7203",
            "name": "トヨタ自動車",
            "market_segment": "プライム（内国株式）",
            "sector_code_33": "3700",
            "sector_name_33": "輸送用機器",
        },
        {
            "ticker_code": "1306",
            "name": "NEXT FUNDS TOPIX連動型上場投信",
            "market_segment": "ETF・ETN",
        },
    ]
    store.save_records(jpx_listed_records, "jpx_listed", partition_date)

    # Save sample toushin stats B-1 records
    stats_b1_records = [
        {
            "year_month": "2026-01",
            "net_assets": 220000000.0,
            "inflow": 5000000.0,
            "outflow": 3000000.0,
            "net_flow": 2000000.0,
        },
        {
            "year_month": "2026-02",
            "net_assets": 225000000.0,
            "inflow": 5500000.0,
            "outflow": 3200000.0,
            "net_flow": 2300000.0,
        },
    ]
    store.save_records(stats_b1_records, "toushin_stats_b1", partition_date)

    return store, data_dir


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestStatusWithData:
    """Integration tests for the status command with pre-existing data."""

    def test_正常系_statusコマンドが全カテゴリのデータ鮮度を表示する(
        self,
        runner: CliRunner,
        store_with_records: tuple[FundDbStore, Path],
    ) -> None:
        _, data_dir = store_with_records
        result = runner.invoke(cli, ["--data-dir", str(data_dir), "status"])

        assert result.exit_code == 0
        assert "2026-04-01" in result.output
        assert "Data Status" in result.output

    def test_正常系_statusコマンドがレコード件数を表示する(
        self,
        runner: CliRunner,
        store_with_records: tuple[FundDbStore, Path],
    ) -> None:
        _, data_dir = store_with_records
        result = runner.invoke(cli, ["--data-dir", str(data_dir), "status"])

        assert result.exit_code == 0
        # nisa_unlisted has 2 records
        assert "2" in result.output


@pytest.mark.integration
class TestNisaListWithData:
    """Integration tests for nisa list with pre-existing data."""

    def test_正常系_nisaリストが保存済みレコードを表示する(
        self,
        runner: CliRunner,
        store_with_records: tuple[FundDbStore, Path],
    ) -> None:
        _, data_dir = store_with_records
        result = runner.invoke(cli, ["--data-dir", str(data_dir), "nisa", "list"])

        assert result.exit_code == 0
        assert "01311046" in result.output
        assert "eMAXIS" in result.output


@pytest.mark.integration
class TestStatsSummaryWithData:
    """Integration tests for stats summary with pre-existing data."""

    def test_正常系_statsSummaryが保存済みレコード件数を表示する(
        self,
        runner: CliRunner,
        store_with_records: tuple[FundDbStore, Path],
    ) -> None:
        _, data_dir = store_with_records
        result = runner.invoke(cli, ["--data-dir", str(data_dir), "stats", "summary"])

        assert result.exit_code == 0
        # B-1 has 2 records
        assert "2" in result.output


@pytest.mark.integration
class TestLoadLatestWorkflow:
    """Integration tests verifying save + load_latest round-trip."""

    def test_正常系_save後にload_latestで取得できる(
        self,
        store_with_records: tuple[FundDbStore, Path],
    ) -> None:
        store, _ = store_with_records

        records = store.load_latest("nisa_unlisted")
        assert records is not None
        assert len(records) == 2
        assert records[0]["association_code"] == "01311046"
        assert records[1]["fund_name"] == "たわらノーロード 先進国株式"

    def test_正常系_複数カテゴリのload_latestが独立動作する(
        self,
        store_with_records: tuple[FundDbStore, Path],
    ) -> None:
        store, _ = store_with_records

        nisa = store.load_latest("nisa_unlisted")
        jpx = store.load_latest("jpx_listed")
        stats = store.load_latest("toushin_stats_b1")

        assert nisa is not None and len(nisa) == 2
        assert jpx is not None and len(jpx) == 2
        assert stats is not None and len(stats) == 2

    def test_正常系_存在しないカテゴリでNone(
        self,
        store_with_records: tuple[FundDbStore, Path],
    ) -> None:
        store, _ = store_with_records
        assert store.load_latest("nonexistent_category") is None
