"""Unit tests for pdf_pipeline.services.id_generator module.

Tests cover:
- Deterministic behavior (same inputs → same outputs)
- Format correctness (UUID5, SHA-256 hex)
- Distinct outputs for distinct inputs
"""

from __future__ import annotations

import pytest

from pdf_pipeline.services.id_generator import (
    generate_author_id,
    generate_chunk_id,
    generate_datapoint_id,
    generate_entity_id,
    generate_period_id,
    generate_question_id,
    generate_source_id,
    generate_stance_id,
)

# ---------------------------------------------------------------------------
# generate_source_id
# ---------------------------------------------------------------------------


class TestGenerateSourceId:
    """Tests for generate_source_id."""

    def test_正常系_URLから決定論的にIDを生成できる(self) -> None:
        url = "https://example.com/report.pdf"
        result = generate_source_id(url)
        assert isinstance(result, str)
        assert len(result) == 36  # UUID5 format

    def test_正常系_同じURLで同じIDを生成する(self) -> None:
        url = "https://example.com/report.pdf"
        assert generate_source_id(url) == generate_source_id(url)

    def test_正常系_異なるURLで異なるIDを生成する(self) -> None:
        url1 = "https://example.com/report1.pdf"
        url2 = "https://example.com/report2.pdf"
        assert generate_source_id(url1) != generate_source_id(url2)

    def test_正常系_UUID形式である(self) -> None:
        import uuid

        url = "https://example.com/report.pdf"
        result = generate_source_id(url)
        # Should parse as a valid UUID without error
        parsed = uuid.UUID(result)
        assert str(parsed) == result


# ---------------------------------------------------------------------------
# generate_chunk_id
# ---------------------------------------------------------------------------


class TestGenerateChunkId:
    """Tests for generate_chunk_id."""

    def test_正常系_source_idとchunk_indexからIDを生成できる(self) -> None:
        result = generate_chunk_id(source_id="abc-123", chunk_index=0)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_正常系_同じ入力で同じIDを生成する(self) -> None:
        assert generate_chunk_id(source_id="abc", chunk_index=1) == generate_chunk_id(
            source_id="abc", chunk_index=1
        )

    def test_正常系_異なるchunk_indexで異なるIDを生成する(self) -> None:
        id0 = generate_chunk_id(source_id="abc", chunk_index=0)
        id1 = generate_chunk_id(source_id="abc", chunk_index=1)
        assert id0 != id1

    def test_正常系_異なるsource_idで異なるIDを生成する(self) -> None:
        id_a = generate_chunk_id(source_id="source-a", chunk_index=0)
        id_b = generate_chunk_id(source_id="source-b", chunk_index=0)
        assert id_a != id_b

    def test_正常系_UUID形式である(self) -> None:
        import uuid

        result = generate_chunk_id(source_id="test", chunk_index=5)
        parsed = uuid.UUID(result)
        assert str(parsed) == result


# ---------------------------------------------------------------------------
# generate_datapoint_id
# ---------------------------------------------------------------------------


class TestGenerateDatapointId:
    """Tests for generate_datapoint_id."""

    def test_正常系_contentからSHA256ベースIDを生成できる(self) -> None:
        content = "GDP growth rate was 2.5% in Q4 2025"
        result = generate_datapoint_id(content)
        assert isinstance(result, str)
        assert len(result) == 32  # first 32 hex chars of SHA-256 (128-bit)

    def test_正常系_同じcontentで同じIDを生成する(self) -> None:
        content = "same content"
        assert generate_datapoint_id(content) == generate_datapoint_id(content)

    def test_正常系_異なるcontentで異なるIDを生成する(self) -> None:
        id1 = generate_datapoint_id("content A")
        id2 = generate_datapoint_id("content B")
        assert id1 != id2

    def test_正常系_32文字の16進数文字列である(self) -> None:
        result = generate_datapoint_id("test content")
        assert all(c in "0123456789abcdef" for c in result)
        assert len(result) == 32


# ---------------------------------------------------------------------------
# generate_entity_id
# ---------------------------------------------------------------------------


class TestGenerateEntityId:
    """Tests for generate_entity_id."""

    def test_正常系_nameとentity_typeからIDを生成できる(self) -> None:
        result = generate_entity_id(name="Apple", entity_type="company")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_正常系_同じ入力で同じIDを生成する(self) -> None:
        assert generate_entity_id(
            name="Apple", entity_type="company"
        ) == generate_entity_id(name="Apple", entity_type="company")

    def test_正常系_異なる入力で異なるIDを生成する(self) -> None:
        id1 = generate_entity_id(name="Apple", entity_type="company")
        id2 = generate_entity_id(name="Google", entity_type="company")
        assert id1 != id2

    def test_正常系_異なるentity_typeで異なるIDを生成する(self) -> None:
        id1 = generate_entity_id(name="Apple", entity_type="company")
        id2 = generate_entity_id(name="Apple", entity_type="brand")
        assert id1 != id2

    def test_正常系_UUID形式の文字列を返す(self) -> None:
        import uuid

        result = generate_entity_id(name="S&P 500", entity_type="index")
        parsed = uuid.UUID(result)
        assert str(parsed) == result


# ---------------------------------------------------------------------------
# generate_period_id
# ---------------------------------------------------------------------------


class TestGeneratePeriodId:
    """Tests for generate_period_id."""

    def test_正常系_period文字列からIDを生成できる(self) -> None:
        result = generate_period_id("2025-Q4")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_正常系_同じperiodで同じIDを生成する(self) -> None:
        assert generate_period_id("2025-Q4") == generate_period_id("2025-Q4")

    def test_正常系_異なるperiodで異なるIDを生成する(self) -> None:
        id1 = generate_period_id("2025-Q3")
        id2 = generate_period_id("2025-Q4")
        assert id1 != id2

    def test_正常系_UUID形式である(self) -> None:
        import uuid

        result = generate_period_id("2026-01")
        parsed = uuid.UUID(result)
        assert str(parsed) == result

    def test_正常系_年月日形式でも動作する(self) -> None:
        result = generate_period_id("2025-12-31")
        assert isinstance(result, str)
        assert len(result) == 36


# ---------------------------------------------------------------------------
# generate_stance_id
# ---------------------------------------------------------------------------


class TestGenerateStanceId:
    """Tests for generate_stance_id."""

    def test_正常系_決定論的IDを返す(self) -> None:
        id1 = generate_stance_id("Goldman Sachs", "Apple", "2026-03-15")
        id2 = generate_stance_id("Goldman Sachs", "Apple", "2026-03-15")
        assert id1 == id2

    def test_正常系_異なる入力で異なるIDを返す(self) -> None:
        id1 = generate_stance_id("Goldman Sachs", "Apple", "2026-03-15")
        id2 = generate_stance_id("Morgan Stanley", "Apple", "2026-03-15")
        assert id1 != id2

    def test_正常系_UUID形式である(self) -> None:
        import uuid

        result = generate_stance_id("Goldman Sachs", "Apple", "2026-03-15")
        parsed = uuid.UUID(result)
        assert str(parsed) == result


# ---------------------------------------------------------------------------
# generate_author_id
# ---------------------------------------------------------------------------


class TestGenerateAuthorId:
    """Tests for generate_author_id."""

    def test_正常系_決定論的IDを返す(self) -> None:
        id1 = generate_author_id("Goldman Sachs", "sell_side")
        id2 = generate_author_id("Goldman Sachs", "sell_side")
        assert id1 == id2

    def test_正常系_異なる入力で異なるIDを返す(self) -> None:
        id1 = generate_author_id("Goldman Sachs", "sell_side")
        id2 = generate_author_id("Morgan Stanley", "sell_side")
        assert id1 != id2

    def test_正常系_UUID形式である(self) -> None:
        import uuid

        result = generate_author_id("Goldman Sachs", "sell_side")
        parsed = uuid.UUID(result)
        assert str(parsed) == result


# ---------------------------------------------------------------------------
# generate_question_id
# ---------------------------------------------------------------------------


class TestGenerateQuestionId:
    """Tests for generate_question_id."""

    def test_正常系_決定論的IDを返す(self) -> None:
        content = "What is the revenue breakdown by segment?"
        id1 = generate_question_id(content)
        id2 = generate_question_id(content)
        assert id1 == id2

    def test_正常系_異なる入力で異なるIDを返す(self) -> None:
        id1 = generate_question_id("What drives margin compression?")
        id2 = generate_question_id("What is the capex plan for FY2026?")
        assert id1 != id2

    def test_正常系_SHA256ベースの32文字IDである(self) -> None:
        result = generate_question_id("What is the revenue breakdown by segment?")
        assert len(result) == 32
        assert all(c in "0123456789abcdef" for c in result)
