"""Unit tests for MarkdownChunker.

Tests cover:
- Initialization
- Section-based Markdown chunking
- Table chunk association to parent sections
- chunk_index ordering
- Edge cases: empty markdown, no headings, tables only
- Output structure (source_hash, chunk_index, section_title, content)
"""

from __future__ import annotations

import pytest

from pdf_pipeline.core.chunker import MarkdownChunker
from pdf_pipeline.schemas.tables import RawTable, TableCell

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_raw_table(page_number: int = 1) -> RawTable:
    """Create a minimal RawTable for testing."""
    cell = TableCell(row=0, col=0, value="Revenue")
    return RawTable(
        page_number=page_number, bbox=[0.0, 0.0, 200.0, 100.0], cells=[cell]
    )


# ---------------------------------------------------------------------------
# MarkdownChunker initialization
# ---------------------------------------------------------------------------


class TestMarkdownChunkerInit:
    """Tests for MarkdownChunker initialization."""

    def test_正常系_デフォルト設定で初期化できる(self) -> None:
        chunker = MarkdownChunker()
        assert chunker is not None

    def test_正常系_インスタンスが作成される(self) -> None:
        chunker = MarkdownChunker()
        assert isinstance(chunker, MarkdownChunker)


# ---------------------------------------------------------------------------
# MarkdownChunker.chunk: basic section splitting
# ---------------------------------------------------------------------------


class TestMarkdownChunkerBasic:
    """Tests for basic Markdown section chunking."""

    def test_正常系_単一見出しでチャンクが1つ生成される(self) -> None:
        chunker = MarkdownChunker()
        md = "# Introduction\n\nThis is the intro text."
        chunks = chunker.chunk(markdown=md, source_hash="abc123")
        assert len(chunks) == 1

    def test_正常系_複数見出しで複数チャンクが生成される(self) -> None:
        chunker = MarkdownChunker()
        md = "# Section 1\n\nContent 1.\n\n## Section 2\n\nContent 2."
        chunks = chunker.chunk(markdown=md, source_hash="abc123")
        assert len(chunks) == 2

    def test_正常系_見出しなしのMarkdownで1チャンク生成される(self) -> None:
        chunker = MarkdownChunker()
        md = "Just plain text without any headings."
        chunks = chunker.chunk(markdown=md, source_hash="abc123")
        assert len(chunks) == 1

    def test_正常系_空のMarkdownで空リストが返される(self) -> None:
        chunker = MarkdownChunker()
        chunks = chunker.chunk(markdown="", source_hash="abc123")
        assert chunks == []

    def test_正常系_空白のみのMarkdownで空リストが返される(self) -> None:
        chunker = MarkdownChunker()
        chunks = chunker.chunk(markdown="   \n\n   ", source_hash="abc123")
        assert chunks == []


# ---------------------------------------------------------------------------
# chunk_index ordering
# ---------------------------------------------------------------------------


class TestChunkIndex:
    """Tests for chunk_index ordering."""

    def test_正常系_chunk_indexが0から始まる(self) -> None:
        chunker = MarkdownChunker()
        md = "# First\n\nContent."
        chunks = chunker.chunk(markdown=md, source_hash="abc123")
        assert chunks[0]["chunk_index"] == 0

    def test_正常系_chunk_indexが順序通り付与される(self) -> None:
        chunker = MarkdownChunker()
        md = "# First\n\nContent 1.\n\n## Second\n\nContent 2.\n\n### Third\n\nContent 3."
        chunks = chunker.chunk(markdown=md, source_hash="abc123")
        indices = [c["chunk_index"] for c in chunks]
        assert indices == list(range(len(chunks)))


# ---------------------------------------------------------------------------
# source_hash field
# ---------------------------------------------------------------------------


class TestSourceHash:
    """Tests for source_hash field in chunks."""

    def test_正常系_source_hashが各チャンクに付与される(self) -> None:
        chunker = MarkdownChunker()
        md = "# Section\n\nText."
        chunks = chunker.chunk(markdown=md, source_hash="deadbeef")
        assert chunks[0]["source_hash"] == "deadbeef"

    def test_正常系_複数チャンクにsource_hashが付与される(self) -> None:
        chunker = MarkdownChunker()
        md = "# A\n\nContent A.\n\n## B\n\nContent B."
        chunks = chunker.chunk(markdown=md, source_hash="myhash")
        assert all(c["source_hash"] == "myhash" for c in chunks)


# ---------------------------------------------------------------------------
# section_title field
# ---------------------------------------------------------------------------


class TestSectionTitle:
    """Tests for section_title extraction from Markdown headings."""

    def test_正常系_H1見出しのタイトルが抽出される(self) -> None:
        chunker = MarkdownChunker()
        md = "# Financial Summary\n\nRevenue was $100M."
        chunks = chunker.chunk(markdown=md, source_hash="abc")
        assert chunks[0]["section_title"] == "Financial Summary"

    def test_正常系_H2見出しのタイトルが抽出される(self) -> None:
        chunker = MarkdownChunker()
        md = "## Revenue Analysis\n\nQ1 revenue was strong."
        chunks = chunker.chunk(markdown=md, source_hash="abc")
        assert chunks[0]["section_title"] == "Revenue Analysis"

    def test_正常系_見出しなしのチャンクでsection_titleがNone(self) -> None:
        chunker = MarkdownChunker()
        md = "Just plain text without heading."
        chunks = chunker.chunk(markdown=md, source_hash="abc")
        assert chunks[0]["section_title"] is None


# ---------------------------------------------------------------------------
# content field
# ---------------------------------------------------------------------------


class TestContentField:
    """Tests for content field in chunks."""

    def test_正常系_コンテンツが保持される(self) -> None:
        chunker = MarkdownChunker()
        md = "# Section\n\nThis is important content."
        chunks = chunker.chunk(markdown=md, source_hash="abc")
        assert "important content" in chunks[0]["content"]

    def test_正常系_見出しテキストがcontentに含まれる(self) -> None:
        chunker = MarkdownChunker()
        md = "# My Heading\n\nBody text here."
        chunks = chunker.chunk(markdown=md, source_hash="abc")
        # The full section text (including heading) should be in content
        assert "My Heading" in chunks[0]["content"]


# ---------------------------------------------------------------------------
# Table association
# ---------------------------------------------------------------------------


class TestTableAssociation:
    """Tests for table chunk association with parent sections."""

    def test_正常系_テーブルなしでtables_フィールドが空(self) -> None:
        chunker = MarkdownChunker()
        md = "# Section\n\nContent."
        chunks = chunker.chunk(markdown=md, source_hash="abc", raw_tables=[])
        assert chunks[0]["tables"] == []

    def test_正常系_raw_tablesを渡さなくてもtablesフィールドが空(self) -> None:
        chunker = MarkdownChunker()
        md = "# Section\n\nContent."
        chunks = chunker.chunk(markdown=md, source_hash="abc")
        assert chunks[0]["tables"] == []

    def test_正常系_テーブルリストがNoneでもtablesフィールドが空(self) -> None:
        chunker = MarkdownChunker()
        md = "# Section\n\nContent."
        chunks = chunker.chunk(markdown=md, source_hash="abc", raw_tables=None)
        assert chunks[0]["tables"] == []

    def test_正常系_raw_tablesが渡されチャンクに付与される(self) -> None:
        chunker = MarkdownChunker()
        md = "# Section\n\nContent."
        raw_table = _make_raw_table(page_number=1)
        chunks = chunker.chunk(markdown=md, source_hash="abc", raw_tables=[raw_table])
        # All tables should be associated to the single chunk
        assert len(chunks[0]["tables"]) == 1

    def test_正常系_複数テーブルが全て付与される(self) -> None:
        chunker = MarkdownChunker()
        md = "# Section\n\nContent."
        tables = [_make_raw_table(1), _make_raw_table(2)]
        chunks = chunker.chunk(markdown=md, source_hash="abc", raw_tables=tables)
        assert len(chunks[0]["tables"]) == 2


# ---------------------------------------------------------------------------
# Output structure (dict keys)
# ---------------------------------------------------------------------------


class TestOutputStructure:
    """Tests for the output dict structure of each chunk."""

    def test_正常系_チャンクに必須キーが全て含まれる(self) -> None:
        chunker = MarkdownChunker()
        md = "# Section\n\nContent."
        chunks = chunker.chunk(markdown=md, source_hash="abc123")
        chunk = chunks[0]
        required_keys = {
            "source_hash",
            "chunk_index",
            "section_title",
            "content",
            "tables",
        }
        assert required_keys.issubset(chunk.keys())


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    """Tests for idempotent behavior (same input → same output)."""

    def test_正常系_同じ入力で同じ出力が得られる(self) -> None:
        chunker = MarkdownChunker()
        md = "# Section\n\nContent.\n\n## Other\n\nMore."
        chunks1 = chunker.chunk(markdown=md, source_hash="hash1")
        chunks2 = chunker.chunk(markdown=md, source_hash="hash1")
        assert len(chunks1) == len(chunks2)
        for c1, c2 in zip(chunks1, chunks2, strict=True):
            assert c1["chunk_index"] == c2["chunk_index"]
            assert c1["section_title"] == c2["section_title"]
            assert c1["content"] == c2["content"]

    def test_正常系_異なるsource_hashで異なるハッシュ値(self) -> None:
        chunker = MarkdownChunker()
        md = "# Section\n\nContent."
        chunks1 = chunker.chunk(markdown=md, source_hash="hash1")
        chunks2 = chunker.chunk(markdown=md, source_hash="hash2")
        assert chunks1[0]["source_hash"] != chunks2[0]["source_hash"]
