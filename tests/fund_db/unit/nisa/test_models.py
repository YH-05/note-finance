"""Unit tests for fund_db.nisa.models module.

Tests Pydantic validation, None-tolerant fields, and required field enforcement.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fund_db.nisa.models import NisaListedEtf, NisaUnlistedFund


class TestNisaUnlistedFund:
    """Tests for the NisaUnlistedFund Pydantic model."""

    def test_正常系_必須フィールドのみで生成できる(self) -> None:
        fund = NisaUnlistedFund(
            association_code="01311046",
            fund_name="eMAXIS Slim 全世界株式",
            management_company="三菱UFJアセットマネジメント",
        )
        assert fund.association_code == "01311046"
        assert fund.fund_name == "eMAXIS Slim 全世界株式"
        assert fund.management_company == "三菱UFJアセットマネジメント"

    def test_正常系_全フィールドを指定して生成できる(self) -> None:
        fund = NisaUnlistedFund(
            association_code="01311046",
            fund_name="eMAXIS Slim 全世界株式",
            management_company="三菱UFJアセットマネジメント",
            asset_class="株式",
            investment_region="内外",
            fund_type="インデックス型",
            benchmark_index="MSCI ACWI",
            expense_ratio="0.05775%以内",
            tsumitate_eligible="○",
            growth_eligible="○",
        )
        assert fund.asset_class == "株式"
        assert fund.investment_region == "内外"
        assert fund.fund_type == "インデックス型"
        assert fund.benchmark_index == "MSCI ACWI"
        assert fund.expense_ratio == "0.05775%以内"
        assert fund.tsumitate_eligible == "○"
        assert fund.growth_eligible == "○"

    def test_正常系_オプショナルフィールドがNoneのデフォルト(self) -> None:
        fund = NisaUnlistedFund(
            association_code="01311046",
            fund_name="テストファンド",
            management_company="テスト運用会社",
        )
        assert fund.asset_class is None
        assert fund.investment_region is None
        assert fund.fund_type is None
        assert fund.benchmark_index is None
        assert fund.expense_ratio is None
        assert fund.tsumitate_eligible is None
        assert fund.growth_eligible is None

    def test_異常系_必須フィールド欠落でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            NisaUnlistedFund(  # type: ignore[call-arg]
                fund_name="テストファンド",
                management_company="テスト運用会社",
            )

    def test_異常系_fund_name欠落でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            NisaUnlistedFund(  # type: ignore[call-arg]
                association_code="01311046",
                management_company="テスト運用会社",
            )

    def test_異常系_management_company欠落でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            NisaUnlistedFund(  # type: ignore[call-arg]
                association_code="01311046",
                fund_name="テストファンド",
            )

    def test_正常系_明示的にNoneを指定できる(self) -> None:
        fund = NisaUnlistedFund(
            association_code="01311046",
            fund_name="テストファンド",
            management_company="テスト運用会社",
            asset_class=None,
            benchmark_index=None,
        )
        assert fund.asset_class is None
        assert fund.benchmark_index is None

    def test_正常系_model_dumpで辞書に変換できる(self) -> None:
        fund = NisaUnlistedFund(
            association_code="01311046",
            fund_name="テストファンド",
            management_company="テスト運用会社",
            asset_class="株式",
        )
        data = fund.model_dump()
        assert isinstance(data, dict)
        assert data["association_code"] == "01311046"
        assert data["asset_class"] == "株式"
        assert data["investment_region"] is None

    def test_正常系_model_json_schemaでスキーマ取得できる(self) -> None:
        schema = NisaUnlistedFund.model_json_schema()
        assert "association_code" in schema["properties"]
        assert "fund_name" in schema["properties"]
        assert "management_company" in schema["properties"]
        required = schema.get("required", [])
        assert "association_code" in required
        assert "fund_name" in required
        assert "management_company" in required


class TestNisaListedEtf:
    """Tests for the NisaListedEtf Pydantic model."""

    def test_正常系_必須フィールドのみで生成できる(self) -> None:
        etf = NisaListedEtf(
            ticker_code="1306",
            fund_name="TOPIX連動型上場投資信託",
        )
        assert etf.ticker_code == "1306"
        assert etf.fund_name == "TOPIX連動型上場投資信託"

    def test_正常系_全フィールドを指定して生成できる(self) -> None:
        etf = NisaListedEtf(
            ticker_code="1306",
            fund_name="TOPIX連動型上場投資信託",
            management_company="野村アセットマネジメント",
            benchmark_index="TOPIX",
            expense_ratio="0.0968%以内",
            trading_unit="10口",
        )
        assert etf.management_company == "野村アセットマネジメント"
        assert etf.benchmark_index == "TOPIX"
        assert etf.expense_ratio == "0.0968%以内"
        assert etf.trading_unit == "10口"

    def test_正常系_オプショナルフィールドがNoneのデフォルト(self) -> None:
        etf = NisaListedEtf(
            ticker_code="1306",
            fund_name="テストETF",
        )
        assert etf.management_company is None
        assert etf.benchmark_index is None
        assert etf.expense_ratio is None
        assert etf.trading_unit is None

    def test_異常系_ticker_code欠落でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            NisaListedEtf(  # type: ignore[call-arg]
                fund_name="テストETF",
            )

    def test_異常系_fund_name欠落でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            NisaListedEtf(  # type: ignore[call-arg]
                ticker_code="1306",
            )

    def test_正常系_明示的にNoneを指定できる(self) -> None:
        etf = NisaListedEtf(
            ticker_code="1306",
            fund_name="テストETF",
            management_company=None,
            trading_unit=None,
        )
        assert etf.management_company is None
        assert etf.trading_unit is None

    def test_正常系_model_dumpで辞書に変換できる(self) -> None:
        etf = NisaListedEtf(
            ticker_code="1306",
            fund_name="テストETF",
            benchmark_index="TOPIX",
        )
        data = etf.model_dump()
        assert isinstance(data, dict)
        assert data["ticker_code"] == "1306"
        assert data["benchmark_index"] == "TOPIX"
        assert data["management_company"] is None


class TestModelEquality:
    """Tests for model equality and immutability patterns."""

    def test_正常系_同一フィールド値で等価判定できる(self) -> None:
        a = NisaUnlistedFund(
            association_code="01311046",
            fund_name="テストファンド",
            management_company="テスト運用会社",
        )
        b = NisaUnlistedFund(
            association_code="01311046",
            fund_name="テストファンド",
            management_company="テスト運用会社",
        )
        assert a == b

    def test_正常系_異なるフィールド値で非等価判定できる(self) -> None:
        a = NisaUnlistedFund(
            association_code="01311046",
            fund_name="ファンドA",
            management_company="テスト運用会社",
        )
        b = NisaUnlistedFund(
            association_code="01311046",
            fund_name="ファンドB",
            management_company="テスト運用会社",
        )
        assert a != b

    def test_正常系_ETF同一フィールド値で等価判定できる(self) -> None:
        a = NisaListedEtf(ticker_code="1306", fund_name="テストETF")
        b = NisaListedEtf(ticker_code="1306", fund_name="テストETF")
        assert a == b
