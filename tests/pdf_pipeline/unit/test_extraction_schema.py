"""Unit tests for pdf_pipeline.schemas.extraction module.

Tests cover:
- ExtractedEntity validation (entity_type Literal constraint, ticker optional)
- ExtractedFact validation (confidence range, fact_type constraint)
- ExtractedClaim validation (sentiment Literal constraint, claim_type)
- ChunkExtractionResult defaults and validation
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
        assert entity.aliases == []

    def test_正常系_全フィールドで生成できる(self) -> None:
        entity = ExtractedEntity(
            name="Apple",
            entity_type="company",
            ticker="AAPL",
            aliases=["Apple Inc.", "AAPL"],
        )
        assert entity.ticker == "AAPL"
        assert len(entity.aliases) == 2

    def test_正常系_全entity_typeが有効(self) -> None:
        valid_types = [
            "company",
            "index",
            "sector",
            "indicator",
            "currency",
            "commodity",
            "person",
            "organization",
        ]
        for etype in valid_types:
            entity = ExtractedEntity(name="Test", entity_type=etype)
            assert entity.entity_type == etype

    def test_異常系_不正なentity_typeでValidationError(self) -> None:
        with pytest.raises(ValidationError):
            ExtractedEntity(name="Test", entity_type="invalid_type")

    def test_異常系_空のnameでValidationError(self) -> None:
        with pytest.raises(ValidationError):
            ExtractedEntity(name="", entity_type="company")


# ---------------------------------------------------------------------------
# ExtractedFact
# ---------------------------------------------------------------------------


class TestExtractedFact:
    """Tests for ExtractedFact Pydantic model."""

    def test_正常系_必須フィールドで生成できる(self) -> None:
        fact = ExtractedFact(content="Revenue was $100B", fact_type="statistic")
        assert fact.content == "Revenue was $100B"
        assert fact.fact_type == "statistic"
        assert fact.confidence == 0.8
        assert fact.as_of_date is None
        assert fact.about_entities == []

    def test_正常系_全フィールドで生成できる(self) -> None:
        fact = ExtractedFact(
            content="GDP grew 2.5%",
            fact_type="data_point",
            as_of_date="2025-Q4",
            confidence=0.95,
            about_entities=["US Economy"],
        )
        assert fact.as_of_date == "2025-Q4"
        assert fact.confidence == 0.95

    def test_正常系_全fact_typeが有効(self) -> None:
        for ftype in ["statistic", "event", "data_point", "quote"]:
            fact = ExtractedFact(content="Test", fact_type=ftype)
            assert fact.fact_type == ftype

    def test_異常系_confidenceが範囲外でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            ExtractedFact(content="Test", fact_type="statistic", confidence=1.5)

    def test_異常系_confidenceが負でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            ExtractedFact(content="Test", fact_type="statistic", confidence=-0.1)

    def test_異常系_不正なfact_typeでValidationError(self) -> None:
        with pytest.raises(ValidationError):
            ExtractedFact(content="Test", fact_type="invalid")

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
        assert claim.confidence == 0.8

    def test_正常系_全フィールドで生成できる(self) -> None:
        claim = ExtractedClaim(
            content="We recommend buying",
            claim_type="recommendation",
            sentiment="bullish",
            confidence=0.9,
            about_entities=["Apple"],
        )
        assert claim.sentiment == "bullish"
        assert claim.confidence == 0.9

    def test_正常系_全claim_typeが有効(self) -> None:
        for ctype in ["opinion", "prediction", "recommendation", "analysis"]:
            claim = ExtractedClaim(content="Test", claim_type=ctype)
            assert claim.claim_type == ctype

    def test_正常系_全sentimentが有効(self) -> None:
        for sentiment in ["bullish", "bearish", "neutral"]:
            claim = ExtractedClaim(
                content="Test",
                claim_type="opinion",
                sentiment=sentiment,
            )
            assert claim.sentiment == sentiment

    def test_異常系_不正なsentimentでValidationError(self) -> None:
        with pytest.raises(ValidationError):
            ExtractedClaim(
                content="Test",
                claim_type="opinion",
                sentiment="invalid",
            )

    def test_異常系_confidenceが範囲外でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            ExtractedClaim(
                content="Test",
                claim_type="opinion",
                confidence=2.0,
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

    def test_正常系_全フィールドで生成できる(self) -> None:
        entity = ExtractedEntity(name="Apple", entity_type="company")
        fact = ExtractedFact(content="Revenue grew", fact_type="statistic")
        claim = ExtractedClaim(content="Buy rating", claim_type="recommendation")

        result = ChunkExtractionResult(
            chunk_index=1,
            section_title="Financial Summary",
            entities=[entity],
            facts=[fact],
            claims=[claim],
        )
        assert result.section_title == "Financial Summary"
        assert len(result.entities) == 1
        assert len(result.facts) == 1
        assert len(result.claims) == 1

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
        entity = ExtractedEntity(name="Apple", entity_type="company")
        fact = ExtractedFact(content="Revenue $100B", fact_type="statistic")
        chunk = ChunkExtractionResult(
            chunk_index=0,
            entities=[entity],
            facts=[fact],
        )
        doc = DocumentExtractionResult(source_hash="hash123", chunks=[chunk])

        json_str = doc.model_dump_json()
        restored = DocumentExtractionResult.model_validate_json(json_str)

        assert restored.source_hash == "hash123"
        assert len(restored.chunks) == 1
        assert restored.chunks[0].entities[0].name == "Apple"
