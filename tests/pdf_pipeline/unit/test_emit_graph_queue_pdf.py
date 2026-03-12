"""Unit tests for pdf-extraction mapper in emit_graph_queue.py.

Tests cover:
- graph-queue JSON format validation
- Entity/Fact/Claim node generation
- Chunk/FinancialDataPoint/FiscalPeriod node generation (v2)
- Relation generation (10 types including 6 new v2 relations)
- ID determinism
- Entity deduplication
- _infer_period_type helper
- SCHEMA_VERSION == '2.0'
"""

from __future__ import annotations

# Import from scripts path
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from emit_graph_queue import (
    SCHEMA_VERSION,
    _infer_period_type,
    generate_chunk_id,
    generate_claim_id,
    generate_datapoint_id,
    generate_entity_id,
    generate_fact_id,
    generate_source_id,
    map_pdf_extraction,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_extraction_data(
    source_hash: str = "abc123def456",
    *,
    include_datapoints: bool = False,
) -> dict[str, Any]:
    """Create a valid DocumentExtractionResult-like dict.

    Parameters
    ----------
    source_hash : str
        SHA-256 hash of the source document.
    include_datapoints : bool
        If True, include financial_datapoints in the chunk data.
    """
    chunk: dict[str, Any] = {
        "chunk_index": 0,
        "section_title": "Financial Summary",
        "content": "Apple reported revenue of $100B in Q4...",
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
                "about_entities": ["Apple"],
            }
        ],
        "claims": [
            {
                "content": "We expect further growth",
                "claim_type": "prediction",
                "sentiment": "bullish",
                "about_entities": ["Apple"],
            }
        ],
    }

    if include_datapoints:
        chunk["financial_datapoints"] = [
            {
                "metric_name": "Revenue",
                "value": 100000.0,
                "unit": "USD mn",
                "is_estimate": False,
                "currency": "USD",
                "period_label": "FY2025",
                "about_entities": ["Apple"],
            },
            {
                "metric_name": "EBITDA",
                "value": 35000.0,
                "unit": "USD mn",
                "is_estimate": True,
                "currency": "USD",
                "period_label": "4Q25",
                "about_entities": ["Apple"],
            },
        ]

    return {
        "source_hash": source_hash,
        "session_id": "test-session",
        "chunks": [chunk],
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
        assert "facts" in result
        assert "claims" in result
        assert "chunks" in result
        assert "financial_datapoints" in result
        assert "fiscal_periods" in result
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

    def test_正常系_FactとClaimが分離される(self) -> None:
        data = _make_extraction_data()
        result = map_pdf_extraction(data)

        # facts[] and claims[] are separate lists
        assert len(result["facts"]) == 1
        assert len(result["claims"]) == 1

        # facts[] uses fact_id, not claim_id
        assert "fact_id" in result["facts"][0]
        assert "claim_id" not in result["facts"][0]

        # claims[] uses claim_id
        assert "claim_id" in result["claims"][0]
        assert result["claims"][0]["category"] == "pdf-claim"

    def test_正常系_factsにcategoryが含まれない(self) -> None:
        data = _make_extraction_data()
        result = map_pdf_extraction(data)

        for fact in result["facts"]:
            assert "category" not in fact

    def test_正常系_confidenceフィールドが存在しない(self) -> None:
        data = _make_extraction_data()
        result = map_pdf_extraction(data)

        for fact in result["facts"]:
            assert "confidence" not in fact
        for claim in result["claims"]:
            assert "confidence" not in claim

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
        assert result["facts"] == []
        assert result["claims"] == []
        assert result["chunks"] == []
        assert result["financial_datapoints"] == []
        assert result["fiscal_periods"] == []

    def test_正常系_IDの決定論性(self) -> None:
        """Same input should produce same IDs every time."""
        data = _make_extraction_data(source_hash="test-hash")
        result1 = map_pdf_extraction(data)
        result2 = map_pdf_extraction(data)

        assert result1["sources"][0]["source_id"] == result2["sources"][0]["source_id"]
        assert result1["facts"][0]["fact_id"] == result2["facts"][0]["fact_id"]
        assert result1["claims"][0]["claim_id"] == result2["claims"][0]["claim_id"]


# ---------------------------------------------------------------------------
# SCHEMA_VERSION
# ---------------------------------------------------------------------------


class TestSchemaVersion:
    """Tests for SCHEMA_VERSION constant."""

    def test_正常系_SCHEMA_VERSIONが2_0である(self) -> None:
        assert SCHEMA_VERSION == "2.0"


# ---------------------------------------------------------------------------
# Chunk node generation
# ---------------------------------------------------------------------------


class TestChunkNodes:
    """Tests for Chunk node generation in map_pdf_extraction."""

    def test_正常系_Chunkノードが生成される(self) -> None:
        data = _make_extraction_data(source_hash="hash1")
        result = map_pdf_extraction(data)

        assert len(result["chunks"]) == 1
        chunk = result["chunks"][0]
        assert chunk["chunk_id"] == "hash1_chunk_0"
        assert chunk["chunk_index"] == 0
        assert chunk["section_title"] == "Financial Summary"

    def test_正常系_chunk_idフォーマットが正しい(self) -> None:
        assert generate_chunk_id("abc123", 0) == "abc123_chunk_0"
        assert generate_chunk_id("abc123", 5) == "abc123_chunk_5"
        assert generate_chunk_id("xyz", 99) == "xyz_chunk_99"

    def test_正常系_複数チャンクのIDが異なる(self) -> None:
        data = {
            "source_hash": "hash1",
            "session_id": "",
            "chunks": [
                {
                    "chunk_index": 0,
                    "section_title": "Intro",
                    "entities": [],
                    "facts": [],
                    "claims": [],
                },
                {
                    "chunk_index": 1,
                    "section_title": "Details",
                    "entities": [],
                    "facts": [],
                    "claims": [],
                },
            ],
        }
        result = map_pdf_extraction(data)
        assert len(result["chunks"]) == 2
        assert result["chunks"][0]["chunk_id"] == "hash1_chunk_0"
        assert result["chunks"][1]["chunk_id"] == "hash1_chunk_1"

    def test_正常系_contains_chunkリレーションが生成される(self) -> None:
        data = _make_extraction_data(source_hash="hash1")
        result = map_pdf_extraction(data)

        rels = result["relations"]["contains_chunk"]
        assert len(rels) == 1
        assert rels[0]["type"] == "CONTAINS_CHUNK"
        assert rels[0]["to_id"] == "hash1_chunk_0"


# ---------------------------------------------------------------------------
# FinancialDataPoint node generation
# ---------------------------------------------------------------------------


class TestFinancialDataPointNodes:
    """Tests for FinancialDataPoint node generation."""

    def test_正常系_FinancialDataPointが生成される(self) -> None:
        data = _make_extraction_data(source_hash="hash1", include_datapoints=True)
        result = map_pdf_extraction(data)

        assert len(result["financial_datapoints"]) == 2
        dp = result["financial_datapoints"][0]
        assert dp["datapoint_id"] == "hash1_Revenue_FY2025"
        assert dp["metric_name"] == "Revenue"
        assert dp["value"] == 100000.0
        assert dp["unit"] == "USD mn"
        assert dp["is_estimate"] is False

    def test_正常系_datapoint_idフォーマットが正しい(self) -> None:
        dp_id = generate_datapoint_id("hash1", "Revenue", "FY2025")
        assert dp_id == "hash1_Revenue_FY2025"

    def test_正常系_has_datapointリレーションが生成される(self) -> None:
        data = _make_extraction_data(source_hash="hash1", include_datapoints=True)
        result = map_pdf_extraction(data)

        rels = result["relations"]["has_datapoint"]
        assert len(rels) == 2
        assert all(r["type"] == "HAS_DATAPOINT" for r in rels)

    def test_正常系_datapoint_entityリレーションが生成される(self) -> None:
        data = _make_extraction_data(source_hash="hash1", include_datapoints=True)
        result = map_pdf_extraction(data)

        rels = result["relations"]["datapoint_entity"]
        assert len(rels) == 2
        assert all(r["type"] == "RELATES_TO" for r in rels)

    def test_正常系_datapointsなしで空リスト(self) -> None:
        data = _make_extraction_data(source_hash="hash1", include_datapoints=False)
        result = map_pdf_extraction(data)

        assert result["financial_datapoints"] == []
        assert result["relations"]["has_datapoint"] == []
        assert result["relations"]["datapoint_entity"] == []


# ---------------------------------------------------------------------------
# FiscalPeriod node generation
# ---------------------------------------------------------------------------


class TestFiscalPeriodNodes:
    """Tests for FiscalPeriod node generation from period_label."""

    def test_正常系_FiscalPeriodが派生生成される(self) -> None:
        data = _make_extraction_data(source_hash="hash1", include_datapoints=True)
        result = map_pdf_extraction(data)

        assert len(result["fiscal_periods"]) == 2
        period_ids = {p["period_id"] for p in result["fiscal_periods"]}
        assert "AAPL_FY2025" in period_ids
        assert "AAPL_4Q25" in period_ids

    def test_正常系_FiscalPeriodが重複排除される(self) -> None:
        """Same period from multiple datapoints should appear once."""
        data = {
            "source_hash": "hash1",
            "session_id": "",
            "chunks": [
                {
                    "chunk_index": 0,
                    "entities": [
                        {"name": "Apple", "entity_type": "company", "ticker": "AAPL"},
                    ],
                    "facts": [],
                    "claims": [],
                    "financial_datapoints": [
                        {
                            "metric_name": "Revenue",
                            "value": 100.0,
                            "unit": "USD mn",
                            "period_label": "FY2025",
                            "about_entities": ["Apple"],
                        },
                        {
                            "metric_name": "EBITDA",
                            "value": 50.0,
                            "unit": "USD mn",
                            "period_label": "FY2025",
                            "about_entities": ["Apple"],
                        },
                    ],
                }
            ],
        }
        result = map_pdf_extraction(data)
        assert len(result["fiscal_periods"]) == 1
        assert result["fiscal_periods"][0]["period_id"] == "AAPL_FY2025"

    def test_正常系_for_periodリレーションが生成される(self) -> None:
        data = _make_extraction_data(source_hash="hash1", include_datapoints=True)
        result = map_pdf_extraction(data)

        rels = result["relations"]["for_period"]
        assert len(rels) == 2
        assert all(r["type"] == "FOR_PERIOD" for r in rels)

    def test_正常系_period_labelなしでFiscalPeriodスキップ(self) -> None:
        data = {
            "source_hash": "hash1",
            "session_id": "",
            "chunks": [
                {
                    "chunk_index": 0,
                    "entities": [],
                    "facts": [],
                    "claims": [],
                    "financial_datapoints": [
                        {
                            "metric_name": "Revenue",
                            "value": 100.0,
                            "unit": "USD mn",
                            "period_label": "",
                            "about_entities": [],
                        }
                    ],
                }
            ],
        }
        result = map_pdf_extraction(data)
        assert result["fiscal_periods"] == []
        assert result["relations"]["for_period"] == []


# ---------------------------------------------------------------------------
# _infer_period_type
# ---------------------------------------------------------------------------


class TestInferPeriodType:
    """Tests for _infer_period_type helper function."""

    def test_正常系_FYでannualを推論(self) -> None:
        assert _infer_period_type("FY2025") == "annual"
        assert _infer_period_type("FY26") == "annual"

    def test_正常系_Qでquarterlyを推論(self) -> None:
        assert _infer_period_type("4Q25") == "quarterly"
        assert _infer_period_type("Q4 2025") == "quarterly"
        assert _infer_period_type("1Q26") == "quarterly"

    def test_正常系_Hでhalf_yearを推論(self) -> None:
        assert _infer_period_type("1H26") == "half_year"
        assert _infer_period_type("2H25") == "half_year"
        assert _infer_period_type("H1 2026") == "half_year"

    def test_正常系_不明なラベルでannualフォールバック(self) -> None:
        assert _infer_period_type("2025") == "annual"
        assert _infer_period_type("unknown") == "annual"

    def test_正常系_大文字小文字を区別しない(self) -> None:
        assert _infer_period_type("fy2025") == "annual"
        assert _infer_period_type("q4") == "quarterly"
        assert _infer_period_type("1h26") == "half_year"


# ---------------------------------------------------------------------------
# New relation types (v2: 6 new relations)
# ---------------------------------------------------------------------------


class TestNewRelations:
    """Tests for the 6 new v2 relation types."""

    def test_正常系_全10種のリレーションキーが存在する(self) -> None:
        data = _make_extraction_data(source_hash="hash1", include_datapoints=True)
        result = map_pdf_extraction(data)

        expected_keys = {
            "source_fact",
            "source_claim",
            "fact_entity",
            "claim_entity",
            "contains_chunk",
            "extracted_from_fact",
            "extracted_from_claim",
            "has_datapoint",
            "for_period",
            "datapoint_entity",
        }
        assert set(result["relations"].keys()) == expected_keys

    def test_正常系_extracted_from_factリレーションが生成される(self) -> None:
        data = _make_extraction_data(source_hash="hash1")
        result = map_pdf_extraction(data)

        rels = result["relations"]["extracted_from_fact"]
        assert len(rels) == 1
        assert rels[0]["type"] == "EXTRACTED_FROM"
        assert rels[0]["to_id"] == "hash1_chunk_0"

    def test_正常系_extracted_from_claimリレーションが生成される(self) -> None:
        data = _make_extraction_data(source_hash="hash1")
        result = map_pdf_extraction(data)

        rels = result["relations"]["extracted_from_claim"]
        assert len(rels) == 1
        assert rels[0]["type"] == "EXTRACTED_FROM"
        assert rels[0]["to_id"] == "hash1_chunk_0"
