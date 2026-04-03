"""Unit tests for fund_db.toushin_stats.parser module.

Tests parse_b1() using synthetic openpyxl workbooks.
B-2/B-3/A-2 tests are skipped as those parsers are not yet implemented.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import openpyxl
import pytest

if TYPE_CHECKING:
    from pathlib import Path

from fund_db.exceptions import ParseError
from fund_db.toushin_stats.parser import ToushinStatsParser, _to_float, _to_year_month

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def parser() -> ToushinStatsParser:
    """Create a ToushinStatsParser instance."""
    return ToushinStatsParser()


@pytest.fixture
def b1_workbook(tmp_path: Path) -> Path:
    """Create a synthetic B-1 Excel workbook for testing.

    Mimics the structure of toushin_B1_shisan_zougen.xlsx:
    - Title rows at top
    - Header row with column names
    - Data rows with year_month and numeric values
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "資産増減状況"

    # Title rows
    ws.cell(row=1, column=1, value="投資信託の資産増減状況")
    ws.cell(row=2, column=1, value="（単位：百万円）")

    # Header row
    ws.cell(row=3, column=1, value="年月")
    ws.cell(row=3, column=2, value="純資産総額")
    ws.cell(row=3, column=3, value="設定額")
    ws.cell(row=3, column=4, value="解約額")
    ws.cell(row=3, column=5, value="純増減額")

    # Data rows
    ws.cell(row=4, column=1, value="2024/1")
    ws.cell(row=4, column=2, value=1500000.0)
    ws.cell(row=4, column=3, value=50000.0)
    ws.cell(row=4, column=4, value=30000.0)
    ws.cell(row=4, column=5, value=20000.0)

    ws.cell(row=5, column=1, value="2024/2")
    ws.cell(row=5, column=2, value=1520000.0)
    ws.cell(row=5, column=3, value=55000.0)
    ws.cell(row=5, column=4, value=35000.0)
    ws.cell(row=5, column=5, value=20000.0)

    ws.cell(row=6, column=1, value="2024/3")
    ws.cell(row=6, column=2, value=1550000.0)
    ws.cell(row=6, column=3, value=60000.0)
    ws.cell(row=6, column=4, value=32000.0)
    ws.cell(row=6, column=5, value=28000.0)

    path = tmp_path / "test_b1.xlsx"
    wb.save(path)
    wb.close()
    return path


@pytest.fixture
def b1_workbook_with_none_cells(tmp_path: Path) -> Path:
    """Create a B-1 workbook with None/empty cells."""
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "資産増減状況"

    # Header row
    ws.cell(row=1, column=1, value="年月")
    ws.cell(row=1, column=2, value="純資産総額")
    ws.cell(row=1, column=3, value="設定額")
    ws.cell(row=1, column=4, value="解約額")
    ws.cell(row=1, column=5, value="純増減額")

    # Data row with some None values
    ws.cell(row=2, column=1, value="2024/1")
    ws.cell(row=2, column=2, value=1500000.0)
    ws.cell(row=2, column=3, value=None)
    ws.cell(row=2, column=4, value=None)
    ws.cell(row=2, column=5, value=20000.0)

    # Empty row (should be skipped)
    ws.cell(row=3, column=1, value=None)
    ws.cell(row=3, column=2, value=None)

    # Another valid row
    ws.cell(row=4, column=1, value="2024/2")
    ws.cell(row=4, column=2, value=1520000.0)
    ws.cell(row=4, column=3, value=55000.0)
    ws.cell(row=4, column=4, value=35000.0)
    ws.cell(row=4, column=5, value=20000.0)

    path = tmp_path / "test_b1_none.xlsx"
    wb.save(path)
    wb.close()
    return path


@pytest.fixture
def b1_workbook_datetime_format(tmp_path: Path) -> Path:
    """Create a B-1 workbook with datetime year_month values."""
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None

    ws.cell(row=1, column=1, value="年月")
    ws.cell(row=1, column=2, value="純資産総額")
    ws.cell(row=1, column=3, value="設定額")

    # Use datetime objects for year_month
    ws.cell(row=2, column=1, value=datetime(2024, 1, 1))
    ws.cell(row=2, column=2, value=1500000.0)
    ws.cell(row=2, column=3, value=50000.0)

    ws.cell(row=3, column=1, value=datetime(2024, 6, 15))
    ws.cell(row=3, column=2, value=1600000.0)
    ws.cell(row=3, column=3, value=60000.0)

    path = tmp_path / "test_b1_datetime.xlsx"
    wb.save(path)
    wb.close()
    return path


@pytest.fixture
def empty_workbook(tmp_path: Path) -> Path:
    """Create an empty workbook with no data."""
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Empty"

    path = tmp_path / "test_empty.xlsx"
    wb.save(path)
    wb.close()
    return path


# ---------------------------------------------------------------------------
# Tests: _to_float helper
# ---------------------------------------------------------------------------


class TestToFloat:
    """Tests for the _to_float helper function."""

    def test_正常系_整数を変換できる(self) -> None:
        assert _to_float(42) == 42.0

    def test_正常系_浮動小数点を変換できる(self) -> None:
        assert _to_float(3.14) == 3.14

    def test_正常系_文字列数値を変換できる(self) -> None:
        assert _to_float("1500000") == 1500000.0

    def test_正常系_カンマ区切り文字列を変換できる(self) -> None:
        assert _to_float("1,500,000") == 1500000.0

    def test_正常系_NoneをNoneに変換する(self) -> None:
        assert _to_float(None) is None

    def test_正常系_空文字列をNoneに変換する(self) -> None:
        assert _to_float("") is None

    def test_正常系_ハイフンをNoneに変換する(self) -> None:
        assert _to_float("-") is None

    def test_正常系_NAをNoneに変換する(self) -> None:
        assert _to_float("N/A") is None

    def test_正常系_NaN浮動小数点をNoneに変換する(self) -> None:
        assert _to_float(float("nan")) is None

    def test_正常系_Inf浮動小数点をNoneに変換する(self) -> None:
        assert _to_float(float("inf")) is None

    def test_正常系_非数値文字列をNoneに変換する(self) -> None:
        assert _to_float("abc") is None


# ---------------------------------------------------------------------------
# Tests: _to_year_month helper
# ---------------------------------------------------------------------------


class TestToYearMonth:
    """Tests for the _to_year_month helper function."""

    def test_正常系_YYYY_MM形式を変換できる(self) -> None:
        assert _to_year_month("2024-01") == "2024-01"

    def test_正常系_YYYYスラッシュM形式を変換できる(self) -> None:
        assert _to_year_month("2024/1") == "2024-01"

    def test_正常系_YYYYスラッシュMM形式を変換できる(self) -> None:
        assert _to_year_month("2024/01") == "2024-01"

    def test_正常系_YYYY年M月形式を変換できる(self) -> None:
        assert _to_year_month("2024年1月") == "2024-01"

    def test_正常系_YYYY年MM月形式を変換できる(self) -> None:
        assert _to_year_month("2024年12月") == "2024-12"

    def test_正常系_datetimeオブジェクトを変換できる(self) -> None:
        dt = datetime(2024, 6, 15, 10, 30)
        assert _to_year_month(dt) == "2024-06"

    def test_正常系_NoneをNoneに変換する(self) -> None:
        assert _to_year_month(None) is None

    def test_正常系_空文字列をNoneに変換する(self) -> None:
        assert _to_year_month("") is None

    def test_正常系_不正な文字列をNoneに変換する(self) -> None:
        assert _to_year_month("abc") is None

    def test_正常系_ハイフンをNoneに変換する(self) -> None:
        assert _to_year_month("-") is None


# ---------------------------------------------------------------------------
# Tests: ToushinStatsParser.parse_b1
# ---------------------------------------------------------------------------


class TestParseB1:
    """Tests for ToushinStatsParser.parse_b1()."""

    def test_正常系_合成ワークブックからレコードを読み込める(
        self,
        parser: ToushinStatsParser,
        b1_workbook: Path,
    ) -> None:
        records = parser.parse_b1(b1_workbook)
        assert len(records) == 3

    def test_正常系_最初のレコードのフィールド値が正しい(
        self,
        parser: ToushinStatsParser,
        b1_workbook: Path,
    ) -> None:
        records = parser.parse_b1(b1_workbook)
        first = records[0]
        assert first.year_month == "2024-01"
        assert first.net_assets == 1500000.0
        assert first.inflow == 50000.0
        assert first.outflow == 30000.0
        assert first.net_flow == 20000.0

    def test_正常系_3レコード目のフィールド値が正しい(
        self,
        parser: ToushinStatsParser,
        b1_workbook: Path,
    ) -> None:
        records = parser.parse_b1(b1_workbook)
        third = records[2]
        assert third.year_month == "2024-03"
        assert third.net_assets == 1550000.0
        assert third.inflow == 60000.0
        assert third.outflow == 32000.0
        assert third.net_flow == 28000.0

    def test_正常系_Noneセルを含むレコードを正しく変換できる(
        self,
        parser: ToushinStatsParser,
        b1_workbook_with_none_cells: Path,
    ) -> None:
        records = parser.parse_b1(b1_workbook_with_none_cells)
        # Should have 2 records (empty row skipped)
        assert len(records) == 2
        first = records[0]
        assert first.year_month == "2024-01"
        assert first.net_assets == 1500000.0
        assert first.inflow is None
        assert first.outflow is None
        assert first.net_flow == 20000.0

    def test_正常系_datetime形式のyear_monthを正しく変換できる(
        self,
        parser: ToushinStatsParser,
        b1_workbook_datetime_format: Path,
    ) -> None:
        records = parser.parse_b1(b1_workbook_datetime_format)
        assert len(records) == 2
        assert records[0].year_month == "2024-01"
        assert records[1].year_month == "2024-06"

    def test_異常系_存在しないファイルでParseError(
        self,
        parser: ToushinStatsParser,
        tmp_path: Path,
    ) -> None:
        with pytest.raises(ParseError):
            parser.parse_b1(tmp_path / "nonexistent.xlsx")

    def test_異常系_ヘッダー行なしでParseError(
        self,
        parser: ToushinStatsParser,
        empty_workbook: Path,
    ) -> None:
        with pytest.raises(ParseError):
            parser.parse_b1(empty_workbook)

    def test_正常系_空データ行のみの場合は空リスト(
        self,
        parser: ToushinStatsParser,
        tmp_path: Path,
    ) -> None:
        """Workbook with header but no data rows returns empty list."""
        wb = openpyxl.Workbook()
        ws = wb.active
        assert ws is not None
        ws.cell(row=1, column=1, value="年月")
        ws.cell(row=1, column=2, value="純資産総額")
        ws.cell(row=1, column=3, value="設定額")
        path = tmp_path / "test_header_only.xlsx"
        wb.save(path)
        wb.close()

        records = parser.parse_b1(path)
        assert records == []

    def test_正常系_レコードがAssetFlowRecord型である(
        self,
        parser: ToushinStatsParser,
        b1_workbook: Path,
    ) -> None:
        from fund_db.toushin_stats.models import AssetFlowRecord

        records = parser.parse_b1(b1_workbook)
        for record in records:
            assert isinstance(record, AssetFlowRecord)

    def test_正常系_レコードをmodel_dumpで辞書に変換できる(
        self,
        parser: ToushinStatsParser,
        b1_workbook: Path,
    ) -> None:
        records = parser.parse_b1(b1_workbook)
        data = records[0].model_dump()
        assert isinstance(data, dict)
        assert "year_month" in data
        assert "net_assets" in data


# ---------------------------------------------------------------------------
# Tests: parse_b2, parse_b3, parse_a2 (skipped - not implemented)
# ---------------------------------------------------------------------------


class TestParseB2:
    """Tests for ToushinStatsParser.parse_b2() (not yet implemented)."""

    @pytest.mark.skip(reason="B-2 parser not yet implemented")
    def test_正常系_B2をパースできる(
        self,
        parser: ToushinStatsParser,
        tmp_path: Path,
    ) -> None:
        records = parser.parse_b2(tmp_path / "dummy.xlsx")
        assert isinstance(records, list)

    def test_異常系_NotImplementedErrorが発生する(
        self,
        parser: ToushinStatsParser,
        tmp_path: Path,
    ) -> None:
        with pytest.raises(NotImplementedError, match="B-2"):
            parser.parse_b2(tmp_path / "dummy.xlsx")


class TestParseB3:
    """Tests for ToushinStatsParser.parse_b3() (not yet implemented)."""

    @pytest.mark.skip(reason="B-3 parser not yet implemented")
    def test_正常系_B3をパースできる(
        self,
        parser: ToushinStatsParser,
        tmp_path: Path,
    ) -> None:
        records = parser.parse_b3(tmp_path / "dummy.xlsx")
        assert isinstance(records, list)

    def test_異常系_NotImplementedErrorが発生する(
        self,
        parser: ToushinStatsParser,
        tmp_path: Path,
    ) -> None:
        with pytest.raises(NotImplementedError, match="B-3"):
            parser.parse_b3(tmp_path / "dummy.xlsx")


class TestParseA2:
    """Tests for ToushinStatsParser.parse_a2() (not yet implemented)."""

    @pytest.mark.skip(reason="A-2 parser not yet implemented")
    def test_正常系_A2をパースできる(
        self,
        parser: ToushinStatsParser,
        tmp_path: Path,
    ) -> None:
        records = parser.parse_a2(tmp_path / "dummy.xlsx")
        assert isinstance(records, list)

    def test_異常系_NotImplementedErrorが発生する(
        self,
        parser: ToushinStatsParser,
        tmp_path: Path,
    ) -> None:
        with pytest.raises(NotImplementedError, match="A-2"):
            parser.parse_a2(tmp_path / "dummy.xlsx")
