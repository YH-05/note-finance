"""Unit tests for NoiseFilter.

Tests cover:
- Initialization from NoiseFilterConfig
- Pattern-based chunk filtering
- Minimum character length filtering
- Multiple pattern matching (header, footer, page_number, footnote, disclaimer)
- Edge cases: empty text, no patterns configured
"""

from __future__ import annotations

import pytest

from pdf_pipeline.core.noise_filter import NoiseFilter
from pdf_pipeline.types import NoiseFilterConfig

# ---------------------------------------------------------------------------
# NoiseFilter initialization
# ---------------------------------------------------------------------------


class TestNoiseFilterInit:
    """Tests for NoiseFilter initialization."""

    def test_正常系_デフォルト設定で初期化できる(self) -> None:
        config = NoiseFilterConfig()
        nf = NoiseFilter(config)
        assert nf is not None

    def test_正常系_カスタム設定で初期化できる(self) -> None:
        config = NoiseFilterConfig(
            min_chunk_chars=100,
            skip_patterns=["^\\s*$", "^\\d+\\s*$"],
        )
        nf = NoiseFilter(config)
        assert nf is not None

    def test_正常系_設定が保持される(self) -> None:
        config = NoiseFilterConfig(min_chunk_chars=80, skip_patterns=["foo"])
        nf = NoiseFilter(config)
        assert nf.config.min_chunk_chars == 80
        assert nf.config.skip_patterns == ["foo"]


# ---------------------------------------------------------------------------
# NoiseFilter.filter_text
# ---------------------------------------------------------------------------


class TestNoiseFilterFilterText:
    """Tests for NoiseFilter.filter_text() — single text string."""

    def test_正常系_ノイズなしのテキストはそのまま返す(self) -> None:
        config = NoiseFilterConfig(min_chunk_chars=10, skip_patterns=[])
        nf = NoiseFilter(config)
        text = "This is a valid paragraph with enough content."
        assert nf.filter_text(text) == text

    def test_正常系_min_chunk_chars未満のテキストは空文字を返す(self) -> None:
        config = NoiseFilterConfig(min_chunk_chars=50, skip_patterns=[])
        nf = NoiseFilter(config)
        short_text = "Too short"
        result = nf.filter_text(short_text)
        assert result == ""

    def test_正常系_skip_patternにマッチするテキストは空文字を返す(self) -> None:
        config = NoiseFilterConfig(
            min_chunk_chars=1,
            skip_patterns=["This report must be read with the disclosures"],
        )
        nf = NoiseFilter(config)
        disclaimer = "This report must be read with the disclosures in full."
        result = nf.filter_text(disclaimer)
        assert result == ""

    def test_正常系_正規表現パターンが正しく機能する(self) -> None:
        config = NoiseFilterConfig(
            min_chunk_chars=1,
            skip_patterns=["^\\s*$"],
        )
        nf = NoiseFilter(config)
        blank = "   \n  "
        result = nf.filter_text(blank)
        assert result == ""

    def test_正常系_ページ番号のみのテキストを除去できる(self) -> None:
        config = NoiseFilterConfig(
            min_chunk_chars=1,
            skip_patterns=["^\\d+\\s*$"],
        )
        nf = NoiseFilter(config)
        page_num = "42"
        result = nf.filter_text(page_num)
        assert result == ""

    def test_正常系_複数パターンのいずれかにマッチしても除去できる(self) -> None:
        config = NoiseFilterConfig(
            min_chunk_chars=1,
            skip_patterns=["^\\s*$", "^\\d+\\s*$", "FOOTER"],
        )
        nf = NoiseFilter(config)
        assert nf.filter_text("") == ""
        assert nf.filter_text("123") == ""
        assert nf.filter_text("FOOTER TEXT") == ""

    def test_正常系_空テキストはmin_chunk_chars判定で除去される(self) -> None:
        config = NoiseFilterConfig(min_chunk_chars=1, skip_patterns=[])
        nf = NoiseFilter(config)
        result = nf.filter_text("")
        assert result == ""

    def test_エッジケース_min_chunk_charsちょうどのテキストは保持される(self) -> None:
        config = NoiseFilterConfig(min_chunk_chars=5, skip_patterns=[])
        nf = NoiseFilter(config)
        text = "12345"
        result = nf.filter_text(text)
        assert result == text

    def test_エッジケース_patternなし_min_charも通過するテキストは保持(self) -> None:
        config = NoiseFilterConfig(min_chunk_chars=1, skip_patterns=[])
        nf = NoiseFilter(config)
        text = "Hello"
        assert nf.filter_text(text) == text


# ---------------------------------------------------------------------------
# NoiseFilter.filter_chunks
# ---------------------------------------------------------------------------


class TestNoiseFilterFilterChunks:
    """Tests for NoiseFilter.filter_chunks() — list of text chunks."""

    def test_正常系_ノイズなしのチャンクリストはそのまま返す(self) -> None:
        config = NoiseFilterConfig(min_chunk_chars=10, skip_patterns=[])
        nf = NoiseFilter(config)
        chunks = [
            "This is a valid paragraph.",
            "Another valid paragraph with enough content.",
        ]
        result = nf.filter_chunks(chunks)
        assert result == chunks

    def test_正常系_ノイズチャンクが除去される(self) -> None:
        config = NoiseFilterConfig(
            min_chunk_chars=20,
            skip_patterns=["disclaimer"],
        )
        nf = NoiseFilter(config)
        chunks = [
            "This is a valid paragraph with content.",
            "Too short",
            "See disclaimer text here",
            "Another valid paragraph with enough text.",
        ]
        result = nf.filter_chunks(chunks)
        assert "Too short" not in result
        assert "See disclaimer text here" not in result
        assert "This is a valid paragraph with content." in result
        assert "Another valid paragraph with enough text." in result

    def test_正常系_空のチャンクリストは空リストを返す(self) -> None:
        config = NoiseFilterConfig()
        nf = NoiseFilter(config)
        result = nf.filter_chunks([])
        assert result == []

    def test_正常系_全チャンクがノイズの場合は空リストを返す(self) -> None:
        config = NoiseFilterConfig(min_chunk_chars=100, skip_patterns=[])
        nf = NoiseFilter(config)
        chunks = ["short", "also short", "tiny"]
        result = nf.filter_chunks(chunks)
        assert result == []

    def test_正常系_免責事項のフレーズを含むチャンクを除去できる(self) -> None:
        config = NoiseFilterConfig(
            min_chunk_chars=1,
            skip_patterns=[
                "This report must be read with the disclosures",
                "Important disclosures can be found",
            ],
        )
        nf = NoiseFilter(config)
        chunks = [
            "# Q4 2025 Market Report",
            "This report must be read with the disclosures in section 5.",
            "Important disclosures can be found at the end of the document.",
            "Revenue grew 15% year over year.",
        ]
        result = nf.filter_chunks(chunks)
        assert "# Q4 2025 Market Report" in result
        assert "Revenue grew 15% year over year." in result
        assert len([c for c in result if "disclosures" in c]) == 0

    def test_正常系_ヘッダーフッターパターンで除去できる(self) -> None:
        config = NoiseFilterConfig(
            min_chunk_chars=1,
            skip_patterns=[
                "^\\s*Page \\d+ of \\d+\\s*$",
                "^\\s*CONFIDENTIAL\\s*$",
            ],
        )
        nf = NoiseFilter(config)
        chunks = [
            "Page 1 of 10",
            "CONFIDENTIAL",
            "This is the main content of the report.",
        ]
        result = nf.filter_chunks(chunks)
        assert result == ["This is the main content of the report."]

    def test_正常系_フィルター後のチャンク順序が保持される(self) -> None:
        config = NoiseFilterConfig(
            min_chunk_chars=1,
            skip_patterns=["REMOVE"],
        )
        nf = NoiseFilter(config)
        chunks = ["First", "REMOVE THIS", "Second", "Third"]
        result = nf.filter_chunks(chunks)
        assert result == ["First", "Second", "Third"]


# ---------------------------------------------------------------------------
# NoiseFilter.is_noise
# ---------------------------------------------------------------------------


class TestNoiseFilterIsNoise:
    """Tests for NoiseFilter.is_noise() — single text noise check."""

    def test_正常系_有効なテキストはFalseを返す(self) -> None:
        config = NoiseFilterConfig(min_chunk_chars=10, skip_patterns=[])
        nf = NoiseFilter(config)
        assert nf.is_noise("This is valid content.") is False

    def test_正常系_短すぎるテキストはTrueを返す(self) -> None:
        config = NoiseFilterConfig(min_chunk_chars=50, skip_patterns=[])
        nf = NoiseFilter(config)
        assert nf.is_noise("Short") is True

    def test_正常系_パターンマッチするテキストはTrueを返す(self) -> None:
        config = NoiseFilterConfig(
            min_chunk_chars=1,
            skip_patterns=["^\\d+\\s*$"],
        )
        nf = NoiseFilter(config)
        assert nf.is_noise("123") is True

    def test_正常系_空文字はTrueを返す(self) -> None:
        config = NoiseFilterConfig(min_chunk_chars=1, skip_patterns=[])
        nf = NoiseFilter(config)
        assert nf.is_noise("") is True
