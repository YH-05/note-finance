"""Unit tests for pdf_pipeline.schemas.extraction module.

Tests cover:
- ExtractedEntity validation (entity_type Literal constraint, ticker/isin optional)
- ExtractedFact validation (fact_type constraint, no confidence field)
- ExtractedClaim validation (sentiment Literal constraint, claim_type, new fields)
- ExtractedFinancialDataPoint validation (metric_name, value, unit, is_estimate)
- ChunkExtractionResult defaults and validation (including financial_datapoints)
- DocumentExtractionResult envelope
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pdf_pipeline.schemas.extraction import (
    ChunkExtractionResult,
    DocumentExtractionResult,
    ExtractedClaim,
    ExtractedEntity,
    ExtractedFact,
    ExtractedFinancialDataPoint,
)

# ---------------------------------------------------------------------------
# ExtractedEntity
# ---------------------------------------------------------------------------


class TestExtractedEntity:
    """Tests for ExtractedEntity Pydantic model."""

    def test_正常系_必須フィールドで生成できる(self) -> None:
        entity = ExtractedEntity(name="Apple", entity_type="company")
        assert entity.name == "Apple"
        assert entity.entity_type == "company"
        assert entity.ticker is None
        assert entity.isin is None
        assert entity.aliases == []

    def test_正常系_全フィールドで生成できる(self) -> None:
        entity = ExtractedEntity(
            name="Apple",
            entity_type="company",
            ticker="AAPL",
            isin="US0378331005",
            aliases=["Apple Inc.", "AAPL"],
        )
        assert entity.ticker == "AAPL"
        assert entity.isin == "US0378331005"
        assert len(entity.aliases) == 2

    def test_正常系_全entity_typeが有効_10種(self) -> None:
        valid_types = [
            "company",
            "index",
            "sector",
            "indicator",
            "currency",
            "commodity",
            "person",
            "organization",
            "country",
            "instrument",
        ]
        assert len(valid_types) == 10
        for etype in valid_types:
            entity = ExtractedEntity(name="Test", entity_type=etype)  # type: ignore[arg-type]
            assert entity.entity_type == etype

    def test_異常系_不正なentity_typeでValidationError(self) -> None:
        with pytest.raises(ValidationError):
            ExtractedEntity(name="Test", entity_type="invalid_type")  # type: ignore[arg-type]

    def test_異常系_空のnameでValidationError(self) -> None:
        with pytest.raises(ValidationError):
            ExtractedEntity(name="", entity_type="company")

    def test_正常系_isinがNoneでも生成できる(self) -> None:
        entity = ExtractedEntity(name="S&P 500", entity_type="index")
        assert entity.isin is None


# ---------------------------------------------------------------------------
# ExtractedFact
# ---------------------------------------------------------------------------


class TestExtractedFact:
    """Tests for ExtractedFact Pydantic model."""

    def test_正常系_必須フィールドで生成できる(self) -> None:
        fact = ExtractedFact(content="Revenue was $100B", fact_type="statistic")
        assert fact.content == "Revenue was $100B"
        assert fact.fact_type == "statistic"
        assert fact.as_of_date is None
        assert fact.about_entities == []

    def test_正常系_confidenceフィールドが存在しない(self) -> None:
        fact = ExtractedFact(content="Revenue was $100B", fact_type="statistic")
        assert not hasattr(fact, "confidence")

    def test_正常系_全フィールドで生成できる(self) -> None:
        fact = ExtractedFact(
            content="GDP grew 2.5%",
            fact_type="economic_indicator",
            as_of_date="2025-Q4",
            about_entities=["US Economy"],
        )
        assert fact.as_of_date == "2025-Q4"
        assert fact.fact_type == "economic_indicator"

    def test_正常系_全fact_typeが有効_8種(self) -> None:
        valid_types = [
            "statistic",
            "event",
            "data_point",
            "quote",
            "policy_action",
            "economic_indicator",
            "regulatory",
            "corporate_action",
        ]
        assert len(valid_types) == 8
        for ftype in valid_types:
            fact = ExtractedFact(content="Test", fact_type=ftype)  # type: ignore[arg-type]
            assert fact.fact_type == ftype

    def test_異常系_不正なfact_typeでValidationError(self) -> None:
        with pytest.raises(ValidationError):
            ExtractedFact(content="Test", fact_type="invalid")  # type: ignore[arg-type]

    def test_異常系_空のcontentでValidationError(self) -> None:
        with pytest.raises(ValidationError):
            ExtractedFact(content="", fact_type="statistic")


# ---------------------------------------------------------------------------
# ExtractedClaim
# ---------------------------------------------------------------------------


class TestExtractedClaim:
    """Tests for ExtractedClaim Pydantic model."""

    def test_正常系_必須フィールドで生成できる(self) -> None:
        claim = ExtractedClaim(content="Stock will rise", claim_type="prediction")
        assert claim.content == "Stock will rise"
        assert claim.claim_type == "prediction"
        assert claim.sentiment is None
        assert claim.magnitude is None
        assert claim.target_price is None
        assert claim.rating is None
        assert claim.time_horizon is None

    def test_正常系_confidenceフィールドが存在しない(self) -> None:
        claim = ExtractedClaim(content="Stock will rise", claim_type="prediction")
        assert not hasattr(claim, "confidence")

    def test_正常系_全フィールドで生成できる(self) -> None:
        claim = ExtractedClaim(
            content="We recommend buying",
            claim_type="recommendation",
            sentiment="bullish",
            magnitude="strong",
            target_price=150.0,
            rating="Buy",
            time_horizon="12M",
            about_entities=["Apple"],
        )
        assert claim.sentiment == "bullish"
        assert claim.magnitude == "strong"
        assert claim.target_price == 150.0
        assert claim.rating == "Buy"
        assert claim.time_horizon == "12M"

    def test_正常系_全claim_typeが有効_10種(self) -> None:
        valid_types = [
            "opinion",
            "prediction",
            "recommendation",
            "analysis",
            "assumption",
            "guidance",
            "risk_assessment",
            "policy_stance",
            "sector_view",
            "forecast",
        ]
        assert len(valid_types) == 10
        for ctype in valid_types:
            claim = ExtractedClaim(content="Test", claim_type=ctype)  # type: ignore[arg-type]
            assert claim.claim_type == ctype

    def test_正常系_全sentimentが有効_4種(self) -> None:
        valid_sentiments = ["bullish", "bearish", "neutral", "mixed"]
        assert len(valid_sentiments) == 4
        for sentiment in valid_sentiments:
            claim = ExtractedClaim(
                content="Test",
                claim_type="opinion",
                sentiment=sentiment,  # type: ignore[arg-type]
            )
            assert claim.sentiment == sentiment

    def test_正常系_全magnitudeが有効(self) -> None:
        for mag in ["strong", "moderate", "slight"]:
            claim = ExtractedClaim(
                content="Test",
                claim_type="opinion",
                magnitude=mag,  # type: ignore[arg-type]
            )
            assert claim.magnitude == mag

    def test_異常系_不正なsentimentでValidationError(self) -> None:
        with pytest.raises(ValidationError):
            ExtractedClaim(
                content="Test",
                claim_type="opinion",
                sentiment="invalid",  # type: ignore[arg-type]
            )

    def test_異常系_不正なmagnitudeでValidationError(self) -> None:
        with pytest.raises(ValidationError):
            ExtractedClaim(
                content="Test",
                claim_type="opinion",
                magnitude="invalid",  # type: ignore[arg-type]
            )

    def test_異常系_不正なclaim_typeでValidationError(self) -> None:
        with pytest.raises(ValidationError):
            ExtractedClaim(content="Test", claim_type="invalid")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# ExtractedFinancialDataPoint
# ---------------------------------------------------------------------------


class TestExtractedFinancialDataPoint:
    """Tests for ExtractedFinancialDataPoint Pydantic model."""

    def test_正常系_必須フィールドで生成できる(self) -> None:
        dp = ExtractedFinancialDataPoint(
            metric_name="Revenue",
            value=1000.0,
            unit="USD mn",
        )
        assert dp.metric_name == "Revenue"
        assert dp.value == 1000.0
        assert dp.unit == "USD mn"
        assert dp.is_estimate is False
        assert dp.currency is None
        assert dp.period_label is None
        assert dp.about_entities == []

    def test_正常系_全フィールドで生成できる(self) -> None:
        dp = ExtractedFinancialDataPoint(
            metric_name="EBITDA",
            value=500.5,
            unit="IDR bn",
            is_estimate=True,
            currency="IDR",
            period_label="FY2025",
            about_entities=["Indosat"],
        )
        assert dp.is_estimate is True
        assert dp.currency == "IDR"
        assert dp.period_label == "FY2025"
        assert dp.about_entities == ["Indosat"]

    def test_異常系_空のmetric_nameでValidationError(self) -> None:
        with pytest.raises(ValidationError):
            ExtractedFinancialDataPoint(
                metric_name="",
                value=100.0,
                unit="USD",
            )

    def test_異常系_空のunitでValidationError(self) -> None:
        with pytest.raises(ValidationError):
            ExtractedFinancialDataPoint(
                metric_name="Revenue",
                value=100.0,
                unit="",
            )


# ---------------------------------------------------------------------------
# ChunkExtractionResult
# ---------------------------------------------------------------------------


class TestChunkExtractionResult:
    """Tests for ChunkExtractionResult Pydantic model."""

    def test_正常系_空の結果を生成できる(self) -> None:
        result = ChunkExtractionResult(chunk_index=0)
        assert result.chunk_index == 0
        assert result.section_title is None
        assert result.entities == []
        assert result.facts == []
        assert result.claims == []
        assert result.financial_datapoints == []

    def test_正常系_全フィールドで生成できる(self) -> None:
        entity = ExtractedEntity(name="Apple", entity_type="company")
        fact = ExtractedFact(content="Revenue grew", fact_type="statistic")
        claim = ExtractedClaim(content="Buy rating", claim_type="recommendation")
        dp = ExtractedFinancialDataPoint(
            metric_name="Revenue",
            value=100.0,
            unit="USD bn",
        )

        result = ChunkExtractionResult(
            chunk_index=1,
            section_title="Financial Summary",
            entities=[entity],
            facts=[fact],
            claims=[claim],
            financial_datapoints=[dp],
        )
        assert result.section_title == "Financial Summary"
        assert len(result.entities) == 1
        assert len(result.facts) == 1
        assert len(result.claims) == 1
        assert len(result.financial_datapoints) == 1

    def test_異常系_chunk_indexが負でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            ChunkExtractionResult(chunk_index=-1)


# ---------------------------------------------------------------------------
# DocumentExtractionResult
# ---------------------------------------------------------------------------


class TestDocumentExtractionResult:
    """Tests for DocumentExtractionResult Pydantic model."""

    def test_正常系_空のチャンクリストで生成できる(self) -> None:
        result = DocumentExtractionResult(source_hash="abc123def456")
        assert result.source_hash == "abc123def456"
        assert result.chunks == []

    def test_正常系_チャンク結果を含めて生成できる(self) -> None:
        chunk = ChunkExtractionResult(chunk_index=0)
        result = DocumentExtractionResult(
            source_hash="abc123def456",
            chunks=[chunk],
        )
        assert len(result.chunks) == 1

    def test_異常系_空のsource_hashでValidationError(self) -> None:
        with pytest.raises(ValidationError):
            DocumentExtractionResult(source_hash="")

    def test_正常系_JSONシリアライズとデシリアライズ(self) -> None:
        entity = ExtractedEntity(
            name="Apple", entity_type="company", isin="US0378331005"
        )
        fact = ExtractedFact(content="Revenue $100B", fact_type="statistic")
        claim = ExtractedClaim(
            content="Buy recommendation",
            claim_type="recommendation",
            sentiment="bullish",
            magnitude="strong",
            target_price=200.0,
            rating="Buy",
            time_horizon="12M",
        )
        dp = ExtractedFinancialDataPoint(
            metric_name="Revenue",
            value=100.0,
            unit="USD bn",
            is_estimate=False,
            currency="USD",
            period_label="FY2025",
        )
        chunk = ChunkExtractionResult(
            chunk_index=0,
            entities=[entity],
            facts=[fact],
            claims=[claim],
            financial_datapoints=[dp],
        )
        doc = DocumentExtractionResult(source_hash="hash123", chunks=[chunk])

        json_str = doc.model_dump_json()
        restored = DocumentExtractionResult.model_validate_json(json_str)

        assert restored.source_hash == "hash123"
        assert len(restored.chunks) == 1
        assert restored.chunks[0].entities[0].name == "Apple"
        assert restored.chunks[0].entities[0].isin == "US0378331005"
        assert restored.chunks[0].claims[0].target_price == 200.0
        assert restored.chunks[0].financial_datapoints[0].metric_name == "Revenue"
