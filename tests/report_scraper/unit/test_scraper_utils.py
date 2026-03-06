"""Tests for shared scraper utility functions.

Tests cover:
- resolve_url: relative and absolute URL resolution
- is_pdf_url: PDF URL detection
- find_pdf_links: PDF link extraction from elements
"""

from __future__ import annotations

from unittest.mock import MagicMock

from report_scraper.scrapers._scraper_utils import (
    find_pdf_links,
    is_pdf_url,
    resolve_url,
)


class TestResolveUrl:
    """Tests for resolve_url."""

    def test_正常系_絶対URLはそのまま返される(self) -> None:
        assert (
            resolve_url("https://cdn.example.com/file.pdf", "https://example.com")
            == "https://cdn.example.com/file.pdf"
        )

    def test_正常系_相対URLがベースURLで解決される(self) -> None:
        result = resolve_url("/reports/q4.pdf", "https://example.com/page")
        assert result == "https://example.com/reports/q4.pdf"

    def test_正常系_相対パスがベースURLのディレクトリで解決される(self) -> None:
        result = resolve_url("q4.pdf", "https://example.com/reports/index.html")
        assert result == "https://example.com/reports/q4.pdf"


class TestIsPdfUrl:
    """Tests for is_pdf_url."""

    def test_正常系_PDFURLでTrueを返す(self) -> None:
        assert is_pdf_url("https://example.com/report.pdf") is True

    def test_正常系_大文字PDFでもTrueを返す(self) -> None:
        assert is_pdf_url("https://example.com/report.PDF") is True

    def test_正常系_クエリパラメータ付きPDFでTrueを返す(self) -> None:
        assert is_pdf_url("https://example.com/report.pdf?token=abc") is True

    def test_正常系_非PDFでFalseを返す(self) -> None:
        assert is_pdf_url("https://example.com/page.html") is False

    def test_エッジケース_空文字列でFalseを返す(self) -> None:
        assert is_pdf_url("") is False


class TestFindPdfLinks:
    """Tests for find_pdf_links."""

    def test_正常系_PDF要素からリンクを抽出(self) -> None:
        el1 = MagicMock()
        el1.attrib = {"href": "/docs/report.pdf"}
        el2 = MagicMock()
        el2.attrib = {"href": "/docs/page.html"}

        result = find_pdf_links([el1, el2], "https://example.com")
        assert len(result) == 1
        assert result[0] == "https://example.com/docs/report.pdf"

    def test_エッジケース_空リストで空結果(self) -> None:
        assert find_pdf_links([], "https://example.com") == []

    def test_エッジケース_hrefなし要素はスキップ(self) -> None:
        el = MagicMock()
        el.attrib = {"href": ""}
        assert find_pdf_links([el], "https://example.com") == []
