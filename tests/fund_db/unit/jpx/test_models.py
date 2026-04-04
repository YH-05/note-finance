"""Unit tests for fund_db.jpx.models module.

Tests Pydantic validation, is_etf/is_reit properties, and field defaults.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fund_db.jpx.models import JpxListedStock


class TestJpxListedStockCreation:
    """Tests for JpxListedStock model creation and field defaults."""

    def test_正常系_必須フィールドのみで生成できる(self) -> None:
        stock = JpxListedStock(
            ticker_code="7203",
            name="トヨタ自動車",
        )
        assert stock.ticker_code == "7203"
        assert stock.name == "トヨタ自動車"

    def test_正常系_全フィールドを指定して生成できる(self) -> None:
        stock = JpxListedStock(
            ticker_code="7203",
            name="トヨタ自動車",
            market_segment="プライム（内国株式）",
            sector_code_33="3700",
            sector_name_33="輸送用機器",
            sector_code_17="8",
            sector_name_17="自動車・輸送機",
            size_code="1",
            size_category="TOPIX Large70",
        )
        assert stock.market_segment == "プライム（内国株式）"
        assert stock.sector_code_33 == "3700"
        assert stock.sector_name_33 == "輸送用機器"
        assert stock.sector_code_17 == "8"
        assert stock.sector_name_17 == "自動車・輸送機"
        assert stock.size_code == "1"
        assert stock.size_category == "TOPIX Large70"

    def test_正常系_オプショナルフィールドがNoneのデフォルト(self) -> None:
        stock = JpxListedStock(
            ticker_code="7203",
            name="トヨタ自動車",
        )
        assert stock.market_segment is None
        assert stock.sector_code_33 is None
        assert stock.sector_name_33 is None
        assert stock.sector_code_17 is None
        assert stock.sector_name_17 is None
        assert stock.size_code is None
        assert stock.size_category is None

    def test_異常系_ticker_code欠落でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            JpxListedStock(  # type: ignore[call-arg]
                name="トヨタ自動車",
            )

    def test_異常系_name欠落でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            JpxListedStock(  # type: ignore[call-arg]
                ticker_code="7203",
            )

    def test_正常系_明示的にNoneを指定できる(self) -> None:
        stock = JpxListedStock(
            ticker_code="7203",
            name="トヨタ自動車",
            market_segment=None,
            sector_code_33=None,
        )
        assert stock.market_segment is None
        assert stock.sector_code_33 is None

    def test_正常系_model_dumpで辞書に変換できる(self) -> None:
        stock = JpxListedStock(
            ticker_code="7203",
            name="トヨタ自動車",
            market_segment="プライム（内国株式）",
        )
        data = stock.model_dump()
        assert isinstance(data, dict)
        assert data["ticker_code"] == "7203"
        assert data["market_segment"] == "プライム（内国株式）"
        assert data["sector_code_33"] is None

    def test_正常系_model_json_schemaでスキーマ取得できる(self) -> None:
        schema = JpxListedStock.model_json_schema()
        assert "ticker_code" in schema["properties"]
        assert "name" in schema["properties"]
        required = schema.get("required", [])
        assert "ticker_code" in required
        assert "name" in required


class TestJpxListedStockIsEtf:
    """Tests for the is_etf property."""

    def test_正常系_ETF_ETNセグメントでis_etf_True(self) -> None:
        stock = JpxListedStock(
            ticker_code="1306",
            name="NEXT FUNDS TOPIX連動型上場投信",
            market_segment="ETF・ETN",
        )
        assert stock.is_etf is True

    def test_正常系_内国株式セグメントでis_etf_False(self) -> None:
        stock = JpxListedStock(
            ticker_code="7203",
            name="トヨタ自動車",
            market_segment="プライム（内国株式）",
        )
        assert stock.is_etf is False

    def test_正常系_market_segmentがNoneでis_etf_False(self) -> None:
        stock = JpxListedStock(
            ticker_code="7203",
            name="トヨタ自動車",
            market_segment=None,
        )
        assert stock.is_etf is False

    def test_正常系_ETFを含む文字列でis_etf_True(self) -> None:
        stock = JpxListedStock(
            ticker_code="1234",
            name="テストETF",
            market_segment="Some ETF Category",
        )
        assert stock.is_etf is True


class TestJpxListedStockIsReit:
    """Tests for the is_reit property."""

    def test_正常系_REITセグメントでis_reit_True(self) -> None:
        stock = JpxListedStock(
            ticker_code="8951",
            name="日本ビルファンド投資法人",
            market_segment="REIT・ベンチャーファンド・カントリーファンド・インフラファンド",
        )
        assert stock.is_reit is True

    def test_正常系_内国株式セグメントでis_reit_False(self) -> None:
        stock = JpxListedStock(
            ticker_code="7203",
            name="トヨタ自動車",
            market_segment="プライム（内国株式）",
        )
        assert stock.is_reit is False

    def test_正常系_market_segmentがNoneでis_reit_False(self) -> None:
        stock = JpxListedStock(
            ticker_code="7203",
            name="トヨタ自動車",
            market_segment=None,
        )
        assert stock.is_reit is False

    def test_正常系_ETFセグメントでis_reit_False(self) -> None:
        stock = JpxListedStock(
            ticker_code="1306",
            name="NEXT FUNDS TOPIX連動型上場投信",
            market_segment="ETF・ETN",
        )
        assert stock.is_reit is False


class TestJpxListedStockEquality:
    """Tests for model equality."""

    def test_正常系_同一フィールド値で等価判定できる(self) -> None:
        a = JpxListedStock(ticker_code="7203", name="トヨタ自動車")
        b = JpxListedStock(ticker_code="7203", name="トヨタ自動車")
        assert a == b

    def test_正常系_異なるフィールド値で非等価判定できる(self) -> None:
        a = JpxListedStock(ticker_code="7203", name="トヨタ自動車")
        b = JpxListedStock(ticker_code="6758", name="ソニーグループ")
        assert a != b
