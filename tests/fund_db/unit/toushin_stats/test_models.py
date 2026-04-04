"""Unit tests for fund_db.toushin_stats.models module.

Tests Pydantic validation, None-tolerant fields, and required field enforcement
for all four statistics models: AssetFlowRecord, ProductClassRecord,
ManagementCompanyRecord, and OverallStatusRecord.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fund_db.toushin_stats.models import (
    AssetFlowRecord,
    ManagementCompanyRecord,
    OverallStatusRecord,
    ProductClassRecord,
)


class TestAssetFlowRecord:
    """Tests for the AssetFlowRecord (B-1) Pydantic model."""

    def test_正常系_必須フィールドのみで生成できる(self) -> None:
        record = AssetFlowRecord(year_month="2024-01")
        assert record.year_month == "2024-01"

    def test_正常系_全フィールドを指定して生成できる(self) -> None:
        record = AssetFlowRecord(
            year_month="2024-01",
            net_assets=1500000.0,
            inflow=50000.0,
            outflow=30000.0,
            net_flow=20000.0,
        )
        assert record.year_month == "2024-01"
        assert record.net_assets == 1500000.0
        assert record.inflow == 50000.0
        assert record.outflow == 30000.0
        assert record.net_flow == 20000.0

    def test_正常系_オプショナルフィールドがNoneのデフォルト(self) -> None:
        record = AssetFlowRecord(year_month="2024-06")
        assert record.net_assets is None
        assert record.inflow is None
        assert record.outflow is None
        assert record.net_flow is None

    def test_異常系_year_month欠落でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            AssetFlowRecord()  # type: ignore[call-arg]

    def test_正常系_明示的にNoneを指定できる(self) -> None:
        record = AssetFlowRecord(
            year_month="2024-03",
            net_assets=None,
            inflow=None,
        )
        assert record.net_assets is None
        assert record.inflow is None

    def test_正常系_model_dumpで辞書に変換できる(self) -> None:
        record = AssetFlowRecord(
            year_month="2024-01",
            net_assets=1500000.0,
            inflow=50000.0,
        )
        data = record.model_dump()
        assert isinstance(data, dict)
        assert data["year_month"] == "2024-01"
        assert data["net_assets"] == 1500000.0
        assert data["inflow"] == 50000.0
        assert data["outflow"] is None

    def test_正常系_model_json_schemaでスキーマ取得できる(self) -> None:
        schema = AssetFlowRecord.model_json_schema()
        assert "year_month" in schema["properties"]
        assert "net_assets" in schema["properties"]
        required = schema.get("required", [])
        assert "year_month" in required
        assert "net_assets" not in required

    def test_正常系_同一フィールド値で等価判定できる(self) -> None:
        a = AssetFlowRecord(year_month="2024-01", net_assets=100.0)
        b = AssetFlowRecord(year_month="2024-01", net_assets=100.0)
        assert a == b

    def test_正常系_異なるフィールド値で非等価判定できる(self) -> None:
        a = AssetFlowRecord(year_month="2024-01", net_assets=100.0)
        b = AssetFlowRecord(year_month="2024-02", net_assets=100.0)
        assert a != b


class TestProductClassRecord:
    """Tests for the ProductClassRecord (B-2) Pydantic model."""

    def test_正常系_必須フィールドのみで生成できる(self) -> None:
        record = ProductClassRecord(
            product_class="株式投信",
            year_month="2024-01",
        )
        assert record.product_class == "株式投信"
        assert record.year_month == "2024-01"

    def test_正常系_全フィールドを指定して生成できる(self) -> None:
        record = ProductClassRecord(
            product_class="株式投信",
            year_month="2024-01",
            net_assets=500000.0,
            fund_count=1200,
        )
        assert record.net_assets == 500000.0
        assert record.fund_count == 1200

    def test_正常系_オプショナルフィールドがNoneのデフォルト(self) -> None:
        record = ProductClassRecord(
            product_class="公社債投信",
            year_month="2024-06",
        )
        assert record.net_assets is None
        assert record.fund_count is None

    def test_異常系_product_class欠落でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            ProductClassRecord(  # type: ignore[call-arg]
                year_month="2024-01",
            )

    def test_異常系_year_month欠落でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            ProductClassRecord(  # type: ignore[call-arg]
                product_class="株式投信",
            )

    def test_正常系_model_dumpで辞書に変換できる(self) -> None:
        record = ProductClassRecord(
            product_class="株式投信",
            year_month="2024-01",
            net_assets=500000.0,
        )
        data = record.model_dump()
        assert data["product_class"] == "株式投信"
        assert data["net_assets"] == 500000.0
        assert data["fund_count"] is None


class TestManagementCompanyRecord:
    """Tests for the ManagementCompanyRecord (B-3) Pydantic model."""

    def test_正常系_必須フィールドのみで生成できる(self) -> None:
        record = ManagementCompanyRecord(
            company_name="三菱UFJアセットマネジメント",
            year_month="2024-01",
        )
        assert record.company_name == "三菱UFJアセットマネジメント"
        assert record.year_month == "2024-01"

    def test_正常系_全フィールドを指定して生成できる(self) -> None:
        record = ManagementCompanyRecord(
            company_name="三菱UFJアセットマネジメント",
            year_month="2024-01",
            net_assets=300000.0,
            fund_count=250,
        )
        assert record.net_assets == 300000.0
        assert record.fund_count == 250

    def test_正常系_オプショナルフィールドがNoneのデフォルト(self) -> None:
        record = ManagementCompanyRecord(
            company_name="テスト運用会社",
            year_month="2024-06",
        )
        assert record.net_assets is None
        assert record.fund_count is None

    def test_異常系_company_name欠落でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            ManagementCompanyRecord(  # type: ignore[call-arg]
                year_month="2024-01",
            )

    def test_異常系_year_month欠落でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            ManagementCompanyRecord(  # type: ignore[call-arg]
                company_name="テスト運用会社",
            )

    def test_正常系_model_dumpで辞書に変換できる(self) -> None:
        record = ManagementCompanyRecord(
            company_name="テスト運用会社",
            year_month="2024-01",
            fund_count=100,
        )
        data = record.model_dump()
        assert data["company_name"] == "テスト運用会社"
        assert data["fund_count"] == 100
        assert data["net_assets"] is None


class TestOverallStatusRecord:
    """Tests for the OverallStatusRecord (A-2) Pydantic model."""

    def test_正常系_必須フィールドのみで生成できる(self) -> None:
        record = OverallStatusRecord(year_month="2024-01")
        assert record.year_month == "2024-01"

    def test_正常系_全フィールドを指定して生成できる(self) -> None:
        record = OverallStatusRecord(
            year_month="2024-01",
            total_net_assets=5000000.0,
            total_fund_count=6000,
            total_inflow=200000.0,
            total_outflow=150000.0,
        )
        assert record.total_net_assets == 5000000.0
        assert record.total_fund_count == 6000
        assert record.total_inflow == 200000.0
        assert record.total_outflow == 150000.0

    def test_正常系_オプショナルフィールドがNoneのデフォルト(self) -> None:
        record = OverallStatusRecord(year_month="2024-06")
        assert record.total_net_assets is None
        assert record.total_fund_count is None
        assert record.total_inflow is None
        assert record.total_outflow is None

    def test_異常系_year_month欠落でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            OverallStatusRecord()  # type: ignore[call-arg]

    def test_正常系_明示的にNoneを指定できる(self) -> None:
        record = OverallStatusRecord(
            year_month="2024-03",
            total_net_assets=None,
            total_fund_count=None,
        )
        assert record.total_net_assets is None
        assert record.total_fund_count is None

    def test_正常系_model_dumpで辞書に変換できる(self) -> None:
        record = OverallStatusRecord(
            year_month="2024-01",
            total_net_assets=5000000.0,
        )
        data = record.model_dump()
        assert data["year_month"] == "2024-01"
        assert data["total_net_assets"] == 5000000.0
        assert data["total_fund_count"] is None

    def test_正常系_model_json_schemaでスキーマ取得できる(self) -> None:
        schema = OverallStatusRecord.model_json_schema()
        assert "year_month" in schema["properties"]
        assert "total_net_assets" in schema["properties"]
        required = schema.get("required", [])
        assert "year_month" in required
        assert "total_net_assets" not in required
