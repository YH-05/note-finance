"""Unit tests for fund_db.jpx.parser module.

Tests JpxParser using in-memory pandas DataFrames as mock data.
Real-file tests (using .tmp/jpx_listed_stocks.xls) are skipped if
the file does not exist.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pandas as pd
import pytest

from fund_db.exceptions import ParseError
from fund_db.jpx.models import JpxListedStock
from fund_db.jpx.parser import JpxParser, _normalize_value

# ---------------------------------------------------------------------------
# Path to optional real XLS file for integration-style tests
# ---------------------------------------------------------------------------

_REAL_XLS_PATH = Path(".tmp/jpx_listed_stocks.xls")
_has_real_xls = _REAL_XLS_PATH.exists()


# ---------------------------------------------------------------------------
# Tests: _normalize_value
# ---------------------------------------------------------------------------


class TestNormalizeValue:
    """Tests for the _normalize_value helper function."""

    def test_正常系_文字列を返す(self) -> None:
        assert _normalize_value("トヨタ自動車") == "トヨタ自動車"

    def test_正常系_前後空白を除去する(self) -> None:
        assert _normalize_value("  トヨタ自動車  ") == "トヨタ自動車"

    def test_正常系_Noneを返す_None入力(self) -> None:
        assert _normalize_value(None) is None

    def test_正常系_Noneを返す_NaN入力(self) -> None:
        assert _normalize_value(float("nan")) is None

    def test_正常系_Noneを返す_空文字列(self) -> None:
        assert _normalize_value("") is None

    def test_正常系_Noneを返す_None文字列(self) -> None:
        assert _normalize_value("None") is None

    def test_正常系_Noneを返す_nan文字列(self) -> None:
        assert _normalize_value("nan") is None

    def test_正常系_数値を文字列に変換する(self) -> None:
        assert _normalize_value(7203) == "7203"

    def test_正常系_浮動小数点を文字列に変換する(self) -> None:
        assert _normalize_value(3700.0) == "3700.0"


# ---------------------------------------------------------------------------
# Tests: JpxParser.parse() with mocked DataFrame
# ---------------------------------------------------------------------------


def _make_mock_dataframe(rows: list[dict[str, str | None]]) -> pd.DataFrame:
    """Create a mock DataFrame with JPX column names in Japanese."""
    jp_columns = [
        "日付",  # extra column that should be ignored
        "コード",
        "銘柄名",
        "市場・商品区分",
        "33業種コード",
        "33業種区分",
        "17業種コード",
        "17業種区分",
        "規模コード",
        "規模区分",
    ]
    data: list[dict[str, str | None]] = []
    for row in rows:
        data.append(
            {
                "日付": row.get("日付", "2026-04-01"),
                "コード": row.get("コード"),
                "銘柄名": row.get("銘柄名"),
                "市場・商品区分": row.get("市場・商品区分"),
                "33業種コード": row.get("33業種コード"),
                "33業種区分": row.get("33業種区分"),
                "17業種コード": row.get("17業種コード"),
                "17業種区分": row.get("17業種区分"),
                "規模コード": row.get("規模コード"),
                "規模区分": row.get("規模区分"),
            }
        )
    return pd.DataFrame(data, columns=jp_columns)


class TestJpxParserParse:
    """Tests for JpxParser.parse() using mocked DataFrames."""

    def test_正常系_正常なデータをパースできる(self, tmp_path: Path) -> None:
        df = _make_mock_dataframe(
            [
                {
                    "コード": "7203",
                    "銘柄名": "トヨタ自動車",
                    "市場・商品区分": "プライム（内国株式）",
                    "33業種コード": "3700",
                    "33業種区分": "輸送用機器",
                    "17業種コード": "8",
                    "17業種区分": "自動車・輸送機",
                    "規模コード": "1",
                    "規模区分": "TOPIX Large70",
                },
                {
                    "コード": "6758",
                    "銘柄名": "ソニーグループ",
                    "市場・商品区分": "プライム（内国株式）",
                    "33業種コード": "3650",
                    "33業種区分": "電気機器",
                    "17業種コード": "7",
                    "17業種区分": "電機・精密",
                    "規模コード": "1",
                    "規模区分": "TOPIX Large70",
                },
            ]
        )

        parser = JpxParser()
        dummy_path = tmp_path / "test.xls"
        with patch("fund_db.jpx.parser.pd.read_excel", return_value=df):
            result = parser.parse(dummy_path)

        assert len(result) == 2
        assert result[0].ticker_code == "7203"
        assert result[0].name == "トヨタ自動車"
        assert result[0].market_segment == "プライム（内国株式）"
        assert result[0].sector_code_33 == "3700"
        assert result[1].ticker_code == "6758"
        assert result[1].name == "ソニーグループ"

    def test_正常系_NaN値がNoneに変換される(self, tmp_path: Path) -> None:
        df = _make_mock_dataframe(
            [
                {
                    "コード": "1306",
                    "銘柄名": "NEXT FUNDS TOPIX連動型上場投信",
                    "市場・商品区分": "ETF・ETN",
                    "33業種コード": None,
                    "33業種区分": None,
                    "17業種コード": None,
                    "17業種区分": None,
                    "規模コード": None,
                    "規模区分": None,
                },
            ]
        )

        parser = JpxParser()
        dummy_path = tmp_path / "test.xls"
        with patch("fund_db.jpx.parser.pd.read_excel", return_value=df):
            result = parser.parse(dummy_path)

        assert len(result) == 1
        assert result[0].ticker_code == "1306"
        assert result[0].market_segment == "ETF・ETN"
        assert result[0].sector_code_33 is None
        assert result[0].sector_name_33 is None

    def test_正常系_必須フィールド欠落行をスキップする(self, tmp_path: Path) -> None:
        df = _make_mock_dataframe(
            [
                {
                    "コード": "7203",
                    "銘柄名": "トヨタ自動車",
                    "市場・商品区分": "プライム（内国株式）",
                },
                {
                    "コード": None,  # Missing ticker_code
                    "銘柄名": "不明な銘柄",
                    "市場・商品区分": "プライム（内国株式）",
                },
                {
                    "コード": "6758",
                    "銘柄名": None,  # Missing name
                    "市場・商品区分": "プライム（内国株式）",
                },
            ]
        )

        parser = JpxParser()
        dummy_path = tmp_path / "test.xls"
        with patch("fund_db.jpx.parser.pd.read_excel", return_value=df):
            result = parser.parse(dummy_path)

        assert len(result) == 1
        assert result[0].ticker_code == "7203"

    def test_正常系_空のDataFrameで空リストを返す(self, tmp_path: Path) -> None:
        df = _make_mock_dataframe([])

        parser = JpxParser()
        dummy_path = tmp_path / "test.xls"
        with patch("fund_db.jpx.parser.pd.read_excel", return_value=df):
            result = parser.parse(dummy_path)

        assert result == []

    def test_異常系_ファイル読み込み失敗でParseError(self, tmp_path: Path) -> None:
        parser = JpxParser()
        nonexistent = tmp_path / "nonexistent.xls"

        with pytest.raises(ParseError) as exc_info:
            parser.parse(nonexistent)
        assert exc_info.value.source == str(nonexistent)

    def test_正常系_ETFとREITのis_etf_is_reitが正しい(self, tmp_path: Path) -> None:
        df = _make_mock_dataframe(
            [
                {
                    "コード": "1306",
                    "銘柄名": "NEXT FUNDS TOPIX連動型上場投信",
                    "市場・商品区分": "ETF・ETN",
                },
                {
                    "コード": "8951",
                    "銘柄名": "日本ビルファンド投資法人",
                    "市場・商品区分": "REIT・ベンチャーファンド・カントリーファンド・インフラファンド",
                },
                {
                    "コード": "7203",
                    "銘柄名": "トヨタ自動車",
                    "市場・商品区分": "プライム（内国株式）",
                },
            ]
        )

        parser = JpxParser()
        dummy_path = tmp_path / "test.xls"
        with patch("fund_db.jpx.parser.pd.read_excel", return_value=df):
            result = parser.parse(dummy_path)

        assert len(result) == 3
        # ETF
        assert result[0].is_etf is True
        assert result[0].is_reit is False
        # REIT
        assert result[1].is_etf is False
        assert result[1].is_reit is True
        # Regular stock
        assert result[2].is_etf is False
        assert result[2].is_reit is False


class TestJpxParserParseEtfsOnly:
    """Tests for JpxParser.parse_etfs_only()."""

    def test_正常系_ETFのみをフィルタして返す(self, tmp_path: Path) -> None:
        df = _make_mock_dataframe(
            [
                {
                    "コード": "1306",
                    "銘柄名": "NEXT FUNDS TOPIX連動型上場投信",
                    "市場・商品区分": "ETF・ETN",
                },
                {
                    "コード": "7203",
                    "銘柄名": "トヨタ自動車",
                    "市場・商品区分": "プライム（内国株式）",
                },
                {
                    "コード": "1321",
                    "銘柄名": "NEXT FUNDS 日経225連動型上場投信",
                    "市場・商品区分": "ETF・ETN",
                },
                {
                    "コード": "8951",
                    "銘柄名": "日本ビルファンド投資法人",
                    "市場・商品区分": "REIT・ベンチャーファンド・カントリーファンド・インフラファンド",
                },
            ]
        )

        parser = JpxParser()
        dummy_path = tmp_path / "test.xls"
        with patch("fund_db.jpx.parser.pd.read_excel", return_value=df):
            result = parser.parse_etfs_only(dummy_path)

        assert len(result) == 2
        assert all(stock.is_etf for stock in result)
        assert result[0].ticker_code == "1306"
        assert result[1].ticker_code == "1321"

    def test_正常系_ETFが無い場合は空リスト(self, tmp_path: Path) -> None:
        df = _make_mock_dataframe(
            [
                {
                    "コード": "7203",
                    "銘柄名": "トヨタ自動車",
                    "市場・商品区分": "プライム（内国株式）",
                },
            ]
        )

        parser = JpxParser()
        dummy_path = tmp_path / "test.xls"
        with patch("fund_db.jpx.parser.pd.read_excel", return_value=df):
            result = parser.parse_etfs_only(dummy_path)

        assert result == []


# ---------------------------------------------------------------------------
# Real file tests (skipped if .tmp/jpx_listed_stocks.xls does not exist)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _has_real_xls,
    reason=".tmp/jpx_listed_stocks.xls not found",
)
class TestJpxParserRealFile:
    """Integration-style tests using the real JPX XLS file."""

    def test_正常系_実ファイルから4000件以上パースできる(self) -> None:
        parser = JpxParser()
        result = parser.parse(_REAL_XLS_PATH)
        assert len(result) >= 4000

    def test_正常系_実ファイルからETFを抽出できる(self) -> None:
        parser = JpxParser()
        etfs = parser.parse_etfs_only(_REAL_XLS_PATH)
        assert len(etfs) > 0
        assert all(stock.is_etf for stock in etfs)

    def test_正常系_パース結果がJpxListedStock型(self) -> None:
        parser = JpxParser()
        result = parser.parse(_REAL_XLS_PATH)
        assert all(isinstance(stock, JpxListedStock) for stock in result)

    def test_正常系_ticker_codeが全て非空(self) -> None:
        parser = JpxParser()
        result = parser.parse(_REAL_XLS_PATH)
        assert all(stock.ticker_code for stock in result)
