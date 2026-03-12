"""Unit tests for pdf-extraction mapper in emit_graph_queue.py.

Tests cover:
- graph-queue JSON format validation
- Entity/Fact/Claim node generation
- Relation generation (source→fact, source→claim, fact→entity, claim→entity)
- ID determinism
- Entity deduplication
"""

from __future__ import annotations

# Import from scripts path
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from emit_graph_queue import (
    generate_claim_id,
    generate_entity_id,
    generate_source_id,
    map_pdf_extraction,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_extraction_data(
    source_hash: str = "abc123def456",
) -> dict[str, Any]:
    """Create a valid DocumentExtractionResult-like dict."""
    return {
        "source_hash": source_hash,
        "session_id": "test-session",
        "chunks": [
            {
                "chunk_index": 0,
                "section_title": "Financial Summary",
                "entities": [
                    {
                        "name": "Apple",
                        "entity_type": "company",
                        "ticker": "AAPL",
                        "aliases": [],
                    },
                    {
                        "name": "S&P 500",
                        "entity_type": "index",
                        "ticker": None,
                        "aliases": [],
                    },
                ],
                "facts": [
                    {
                        "content": "Revenue was $100B in Q4",
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
        ],
    }


# ---------------------------------------------------------------------------
# map_pdf_extraction
# ---------------------------------------------------------------------------


class TestMapPdfExtraction:
    """Tests for map_pdf_extraction mapper function."""

    def test_正常系_graph_queue形式の結果を生成できる(self) -> None:
        data = _make_extraction_data()
        result = map_pdf_extraction(data)

        assert "sources" in result
        assert "entities" in result
        assert "claims" in result
        assert "relations" in result
        assert result["batch_label"] == "pdf-extraction"

    def test_正常系_Sourceノードが生成される(self) -> None:
        data = _make_extraction_data(source_hash="abc123")
        result = map_pdf_extraction(data)

        assert len(result["sources"]) == 1
        source = result["sources"][0]
        assert source["source_type"] == "pdf"
        assert source["source_id"] == generate_source_id("pdf:abc123")

    def test_正常系_Entityノードが生成される(self) -> None:
        data = _make_extraction_data()
        result = map_pdf_extraction(data)

        assert len(result["entities"]) == 2
        entity_names = {e["name"] for e in result["entities"]}
        assert "Apple" in entity_names
        assert "S&P 500" in entity_names

    def test_正常系_EntityのIDが決定論的である(self) -> None:
        data = _make_extraction_data()
        result1 = map_pdf_extraction(data)
        result2 = map_pdf_extraction(data)

        ids1 = {e["entity_id"] for e in result1["entities"]}
        ids2 = {e["entity_id"] for e in result2["entities"]}
        assert ids1 == ids2

    def test_正常系_Fact_Claimがclaimsに含まれる(self) -> None:
        data = _make_extraction_data()
        result = map_pdf_extraction(data)

        # 1 fact + 1 claim = 2 claims in graph-queue
        assert len(result["claims"]) == 2
        categories = {c["category"] for c in result["claims"]}
        assert "pdf-fact" in categories
        assert "pdf-claim" in categories

    def test_正常系_リレーションが生成される(self) -> None:
        data = _make_extraction_data()
        result = map_pdf_extraction(data)

        relations = result["relations"]
        assert len(relations["source_fact"]) == 1
        assert relations["source_fact"][0]["type"] == "STATES_FACT"
        assert len(relations["source_claim"]) == 1
        assert relations["source_claim"][0]["type"] == "MAKES_CLAIM"

    def test_正常系_fact_entityリレーションが生成される(self) -> None:
        data = _make_extraction_data()
        result = map_pdf_extraction(data)

        relations = result["relations"]
        assert len(relations["fact_entity"]) == 1
        assert relations["fact_entity"][0]["type"] == "RELATES_TO"

    def test_正常系_claim_entityリレーションが生成される(self) -> None:
        data = _make_extraction_data()
        result = map_pdf_extraction(data)

        relations = result["relations"]
        assert len(relations["claim_entity"]) == 1
        assert relations["claim_entity"][0]["type"] == "ABOUT"

    def test_正常系_Entityが重複排除される(self) -> None:
        """Same entity in multiple chunks should appear only once."""
        data = {
            "source_hash": "hash1",
            "session_id": "",
            "chunks": [
                {
                    "chunk_index": 0,
                    "entities": [
                        {"name": "Apple", "entity_type": "company"},
                    ],
                    "facts": [],
                    "claims": [],
                },
                {
                    "chunk_index": 1,
                    "entities": [
                        {"name": "Apple", "entity_type": "company"},
                    ],
                    "facts": [],
                    "claims": [],
                },
            ],
        }
        result = map_pdf_extraction(data)
        assert len(result["entities"]) == 1

    def test_正常系_空のチャンクリストで空の結果(self) -> None:
        data = {"source_hash": "hash1", "session_id": "", "chunks": []}
        result = map_pdf_extraction(data)

        assert len(result["sources"]) == 1  # source always created
        assert result["entities"] == []
        assert result["claims"] == []

    def test_正常系_IDの決定論性(self) -> None:
        """Same input should produce same IDs every time."""
        data = _make_extraction_data(source_hash="test-hash")
        result1 = map_pdf_extraction(data)
        result2 = map_pdf_extraction(data)

        assert result1["sources"][0]["source_id"] == result2["sources"][0]["source_id"]
        assert result1["claims"][0]["claim_id"] == result2["claims"][0]["claim_id"]
