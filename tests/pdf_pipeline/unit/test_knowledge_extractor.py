"""Unit tests for pdf_pipeline.core.knowledge_extractor module.

Tests cover:
- Successful extraction from chunks (Entity/Fact/Claim)
- Graceful degradation on LLM failure (empty result fallback)
- Invalid JSON parsing fallback
- Empty chunk handling
- DocumentExtractionResult aggregation
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from pdf_pipeline.core.knowledge_extractor import KnowledgeExtractor
from pdf_pipeline.exceptions import LLMProviderError
from pdf_pipeline.schemas.extraction import (
    ChunkExtractionResult,
    DocumentExtractionResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(
    chunk_index: int = 0,
    content: str = "Apple reported revenue of $100B in Q4 2025.",
    section_title: str | None = "Financial Summary",
) -> dict[str, Any]:
    """Create a mock chunk dict."""
    return {
        "chunk_index": chunk_index,
        "content": content,
        "section_title": section_title,
        "source_hash": "testhash",
        "tables": [],
    }


def _make_valid_extraction_json(chunk_index: int = 0) -> str:
    """Create a valid extraction JSON response."""
    return json.dumps(
        {
            "chunk_index": chunk_index,
            "section_title": "Financial Summary",
            "entities": [
                {
                    "name": "Apple",
                    "entity_type": "company",
                    "ticker": "AAPL",
                    "aliases": ["Apple Inc."],
                }
            ],
            "facts": [
                {
                    "content": "Revenue was $100B in Q4 2025",
                    "fact_type": "statistic",
                    "as_of_date": "2025-Q4",
                    "confidence": 0.9,
                    "about_entities": ["Apple"],
                }
            ],
            "claims": [
                {
                    "content": "We expect further growth",
                    "claim_type": "prediction",
                    "sentiment": "bullish",
                    "confidence": 0.7,
                    "about_entities": ["Apple"],
                }
            ],
        }
    )


# ---------------------------------------------------------------------------
# KnowledgeExtractor initialization
# ---------------------------------------------------------------------------


class TestKnowledgeExtractorInit:
    """Tests for KnowledgeExtractor initialization."""

    def test_正常系_provider_chainで初期化できる(self) -> None:
        chain = MagicMock()
        extractor = KnowledgeExtractor(provider_chain=chain)
        assert extractor.provider_chain is chain


# ---------------------------------------------------------------------------
# KnowledgeExtractor._extract_single
# ---------------------------------------------------------------------------


class TestKnowledgeExtractorExtractSingle:
    """Tests for single chunk extraction."""

    def test_正常系_チャンクからEntity_Fact_Claim抽出(self) -> None:
        chain = MagicMock()
        chain.extract_knowledge.return_value = _make_valid_extraction_json()

        extractor = KnowledgeExtractor(provider_chain=chain)
        chunk = _make_chunk()
        result = extractor._extract_single(chunk, chunk_index=0)

        assert isinstance(result, ChunkExtractionResult)
        assert len(result.entities) == 1
        assert result.entities[0].name == "Apple"
        assert result.entities[0].entity_type == "company"
        assert len(result.facts) == 1
        assert result.facts[0].fact_type == "statistic"
        assert len(result.claims) == 1
        assert result.claims[0].sentiment == "bullish"

    def test_異常系_LLM失敗で空結果フォールバック(self) -> None:
        chain = MagicMock()
        chain.extract_knowledge.side_effect = LLMProviderError("API error")

        extractor = KnowledgeExtractor(provider_chain=chain)
        chunk = _make_chunk()
        result = extractor._extract_single(chunk, chunk_index=0)

        assert isinstance(result, ChunkExtractionResult)
        assert result.chunk_index == 0
        assert result.entities == []
        assert result.facts == []
        assert result.claims == []

    def test_異常系_不正JSON解析で空結果フォールバック(self) -> None:
        chain = MagicMock()
        chain.extract_knowledge.return_value = "not valid json {{"

        extractor = KnowledgeExtractor(provider_chain=chain)
        chunk = _make_chunk()
        result = extractor._extract_single(chunk, chunk_index=0)

        assert isinstance(result, ChunkExtractionResult)
        assert result.entities == []

    def test_エッジケース_空チャンクで空結果(self) -> None:
        chain = MagicMock()
        extractor = KnowledgeExtractor(provider_chain=chain)
        chunk = _make_chunk(content="")
        result = extractor._extract_single(chunk, chunk_index=0)

        assert isinstance(result, ChunkExtractionResult)
        assert result.entities == []
        # LLM should not be called for empty content
        chain.extract_knowledge.assert_not_called()

    def test_エッジケース_空白のみチャンクでスキップ(self) -> None:
        chain = MagicMock()
        extractor = KnowledgeExtractor(provider_chain=chain)
        chunk = _make_chunk(content="   \n  \t  ")
        result = extractor._extract_single(chunk, chunk_index=0)

        assert result.entities == []
        chain.extract_knowledge.assert_not_called()


# ---------------------------------------------------------------------------
# KnowledgeExtractor.extract_from_chunks
# ---------------------------------------------------------------------------


class TestKnowledgeExtractorExtractFromChunks:
    """Tests for document-level extraction."""

    def test_正常系_複数チャンクからDocument結果を集約(self) -> None:
        chain = MagicMock()
        chain.extract_knowledge.return_value = _make_valid_extraction_json()

        extractor = KnowledgeExtractor(provider_chain=chain)
        chunks = [_make_chunk(chunk_index=0), _make_chunk(chunk_index=1)]

        result = extractor.extract_from_chunks(
            chunks=chunks,
            source_hash="abc123",
        )

        assert isinstance(result, DocumentExtractionResult)
        assert result.source_hash == "abc123"
        assert len(result.chunks) == 2

    def test_正常系_一部チャンク失敗でも他は成功(self) -> None:
        chain = MagicMock()
        # First call succeeds, second fails
        chain.extract_knowledge.side_effect = [
            _make_valid_extraction_json(0),
            LLMProviderError("API error"),
        ]

        extractor = KnowledgeExtractor(provider_chain=chain)
        chunks = [_make_chunk(chunk_index=0), _make_chunk(chunk_index=1)]

        result = extractor.extract_from_chunks(
            chunks=chunks,
            source_hash="abc123",
        )

        assert len(result.chunks) == 2
        # First chunk has data
        assert len(result.chunks[0].entities) == 1
        # Second chunk is empty (fallback)
        assert result.chunks[1].entities == []

    def test_正常系_空のチャンクリストで空のDocument結果(self) -> None:
        chain = MagicMock()
        extractor = KnowledgeExtractor(provider_chain=chain)

        result = extractor.extract_from_chunks(
            chunks=[],
            source_hash="abc123",
        )

        assert isinstance(result, DocumentExtractionResult)
        assert result.chunks == []
        chain.extract_knowledge.assert_not_called()
