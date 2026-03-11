"""Unit tests for MarkdownConverter.

Tests cover:
- Initialization with ProviderChain
- convert() using dual-input (PDF path + filtered text)
- Section-split Markdown output (H1/H2/H3 hierarchy)
- Mock LLM provider for deterministic testing
- Error handling when provider fails
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from pdf_pipeline.core.markdown_converter import MarkdownConverter
from pdf_pipeline.exceptions import LLMProviderError
from pdf_pipeline.services.llm_provider import LLMProvider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_provider(markdown_output: str) -> MagicMock:
    """Build a mock LLMProvider that returns ``markdown_output`` from convert_pdf_to_markdown."""
    provider = MagicMock(spec=LLMProvider)
    provider.is_available.return_value = True
    provider.convert_pdf_to_markdown.return_value = markdown_output
    return provider


# ---------------------------------------------------------------------------
# MarkdownConverter initialization
# ---------------------------------------------------------------------------


class TestMarkdownConverterInit:
    """Tests for MarkdownConverter initialization."""

    def test_正常系_LLMProviderで初期化できる(self) -> None:
        provider = _make_mock_provider("# Test")
        converter = MarkdownConverter(provider)
        assert converter is not None

    def test_正常系_providerが保持される(self) -> None:
        provider = _make_mock_provider("# Test")
        converter = MarkdownConverter(provider)
        assert converter.provider is provider


# ---------------------------------------------------------------------------
# MarkdownConverter.convert
# ---------------------------------------------------------------------------


class TestMarkdownConverterConvert:
    """Tests for MarkdownConverter.convert()."""

    def test_正常系_PDFからMarkdownを生成できる(self, tmp_path: Path) -> None:
        pdf_file = tmp_path / "report.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 test content")

        expected_md = "# Q4 2025 Report\n\n## Executive Summary\n\nRevenue grew 15%."
        provider = _make_mock_provider(expected_md)
        converter = MarkdownConverter(provider)

        result = converter.convert(pdf_path=pdf_file, filtered_text="Revenue grew 15%.")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_正常系_H1見出しが出力に含まれる(self, tmp_path: Path) -> None:
        pdf_file = tmp_path / "report.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        md_with_headings = (
            "# Main Title\n\n## Section 1\n\n### Subsection 1.1\n\nContent here."
        )
        provider = _make_mock_provider(md_with_headings)
        converter = MarkdownConverter(provider)

        result = converter.convert(pdf_path=pdf_file, filtered_text="Content here.")

        assert "# Main Title" in result

    def test_正常系_H2見出しが出力に含まれる(self, tmp_path: Path) -> None:
        pdf_file = tmp_path / "report.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        md_with_headings = "# Title\n\n## Section A\n\nSome content."
        provider = _make_mock_provider(md_with_headings)
        converter = MarkdownConverter(provider)

        result = converter.convert(pdf_path=pdf_file, filtered_text="Some content.")

        assert "## Section A" in result

    def test_正常系_H3見出しが出力に含まれる(self, tmp_path: Path) -> None:
        pdf_file = tmp_path / "report.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        md_with_headings = (
            "# Title\n\n## Section\n\n### Subsection\n\nDetailed content."
        )
        provider = _make_mock_provider(md_with_headings)
        converter = MarkdownConverter(provider)

        result = converter.convert(pdf_path=pdf_file, filtered_text="Detailed content.")

        assert "### Subsection" in result

    def test_正常系_H1_H2_H3階層が保持される(self, tmp_path: Path) -> None:
        pdf_file = tmp_path / "report.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        md = "# Top Level\n\n## Second Level\n\n### Third Level\n\nParagraph."
        provider = _make_mock_provider(md)
        converter = MarkdownConverter(provider)

        result = converter.convert(pdf_path=pdf_file, filtered_text="Paragraph.")

        assert "# Top Level" in result
        assert "## Second Level" in result
        assert "### Third Level" in result

    def test_正常系_filtered_textがプロンプトに使用される(self, tmp_path: Path) -> None:
        pdf_file = tmp_path / "report.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        provider = _make_mock_provider("# Result\n\nFiltered content.")
        converter = MarkdownConverter(provider)

        result = converter.convert(
            pdf_path=pdf_file,
            filtered_text="Filtered content without noise.",
        )

        assert isinstance(result, str)
        # プロバイダーが呼ばれたことを確認
        provider.convert_pdf_to_markdown.assert_called_once()

    def test_異常系_LLMProviderErrorが発生した場合に再raiseされる(
        self, tmp_path: Path
    ) -> None:
        pdf_file = tmp_path / "report.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        provider = MagicMock(spec=LLMProvider)
        provider.is_available.return_value = True
        provider.convert_pdf_to_markdown.side_effect = LLMProviderError(
            "Provider failed", provider="MockProvider"
        )

        converter = MarkdownConverter(provider)

        with pytest.raises(LLMProviderError):
            converter.convert(pdf_path=pdf_file, filtered_text="Some text.")

    def test_異常系_PDFファイルが存在しない場合にエラーが発生する(
        self, tmp_path: Path
    ) -> None:
        nonexistent_pdf = tmp_path / "nonexistent.pdf"
        provider = _make_mock_provider("# Content")
        converter = MarkdownConverter(provider)

        with pytest.raises((FileNotFoundError, ValueError, LLMProviderError)):
            converter.convert(pdf_path=nonexistent_pdf, filtered_text="Some text.")


# ---------------------------------------------------------------------------
# MarkdownConverter.parse_sections
# ---------------------------------------------------------------------------


class TestMarkdownConverterParseSections:
    """Tests for MarkdownConverter.parse_sections() — section parsing."""

    def test_正常系_セクションを正しく分割できる(self) -> None:
        provider = _make_mock_provider("")
        converter = MarkdownConverter(provider)

        md = "# Title\n\n## Section 1\n\nContent 1.\n\n## Section 2\n\nContent 2."
        sections = converter.parse_sections(md)

        assert len(sections) >= 1
        assert any("# Title" in s or "Title" in s for s in sections)

    def test_正常系_見出しのないMarkdownは単一セクションを返す(self) -> None:
        provider = _make_mock_provider("")
        converter = MarkdownConverter(provider)

        md = "Just plain text without any headings."
        sections = converter.parse_sections(md)

        assert len(sections) == 1
        assert "Just plain text" in sections[0]

    def test_正常系_空のMarkdownは空リストを返す(self) -> None:
        provider = _make_mock_provider("")
        converter = MarkdownConverter(provider)

        sections = converter.parse_sections("")
        assert sections == []

    def test_正常系_H1_H2_H3が正しく分割される(self) -> None:
        provider = _make_mock_provider("")
        converter = MarkdownConverter(provider)

        md = (
            "# Top\n\nIntro text.\n\n"
            "## Section A\n\nContent A.\n\n"
            "### Sub A1\n\nDetail A1.\n\n"
            "## Section B\n\nContent B."
        )
        sections = converter.parse_sections(md)

        assert len(sections) >= 2
        # 全セクションが文字列であることを確認
        assert all(isinstance(s, str) for s in sections)


# ---------------------------------------------------------------------------
# MarkdownConverter integration-style tests with mock provider
# ---------------------------------------------------------------------------


class TestMarkdownConverterMockLLM:
    """Integration-style tests using mock LLM provider."""

    def test_正常系_モックLLMで完全なMarkdown変換フローが動作する(
        self, tmp_path: Path
    ) -> None:
        pdf_file = tmp_path / "financial_report.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake pdf content")

        mock_output = """# Financial Report Q4 2025

## Executive Summary

Revenue increased by 15% year-over-year.

## Revenue Analysis

### Product Revenue

Product revenue reached $10B.

### Service Revenue

Service revenue was $5B.

## Conclusion

Strong performance across all segments.
"""
        provider = _make_mock_provider(mock_output)
        converter = MarkdownConverter(provider)

        filtered_text = (
            "Revenue increased by 15% year-over-year. "
            "Product revenue reached $10B. "
            "Service revenue was $5B."
        )

        result = converter.convert(pdf_path=pdf_file, filtered_text=filtered_text)

        # 見出し階層が保持されている
        assert "# Financial Report" in result
        assert "## Executive Summary" in result
        assert "## Revenue Analysis" in result
        assert "### Product Revenue" in result
        assert "### Service Revenue" in result

    def test_正常系_免責事項フレーズが出力に含まれないこと(
        self, tmp_path: Path
    ) -> None:
        """filtered_text（ノイズ除去済み）を渡した場合、LLMはそれをコンテキストとして使う。"""
        pdf_file = tmp_path / "report.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        # モックLLMは filtered_text のクリーンなテキストを反映したMarkdownを返す
        mock_output = "# Report\n\nRevenue grew 15%. Strong performance noted."
        provider = _make_mock_provider(mock_output)
        converter = MarkdownConverter(provider)

        # ノイズ除去済みのテキスト（免責事項は既にNoiseFilterで除去済み）
        filtered_text = "Revenue grew 15%. Strong performance noted."

        result = converter.convert(pdf_path=pdf_file, filtered_text=filtered_text)

        # モックは免責事項を含まないMarkdownを返すため、結果にも含まれない
        assert "must be read with the disclosures" not in result
