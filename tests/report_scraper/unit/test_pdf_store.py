"""Tests for PdfStore.

Tests cover:
- Directory creation and source directory management
- list_pdfs, has_pdf
- Path traversal protection
- cleanup_source and get_total_size
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from report_scraper.storage.pdf_store import PdfStore


class TestPdfStoreInit:
    """Tests for PdfStore initialization."""

    def test_正常系_初期化でベースディレクトリが作成される(
        self, tmp_path: Path
    ) -> None:
        base = tmp_path / "pdfs"
        store = PdfStore(base)
        assert base.exists()
        assert store.base_dir == base


class TestPdfStoreGetSourceDir:
    """Tests for PdfStore.get_source_dir."""

    def test_正常系_ソースディレクトリが作成される(self, tmp_path: Path) -> None:
        store = PdfStore(tmp_path / "pdfs")
        source_dir = store.get_source_dir("blackrock")
        assert source_dir.exists()
        assert source_dir.name == "blackrock"

    def test_異常系_パストラバーサルでValueError(self, tmp_path: Path) -> None:
        store = PdfStore(tmp_path / "pdfs")
        with pytest.raises(ValueError, match="Invalid source_key"):
            store.get_source_dir("../../../etc")

    def test_異常系_不正文字を含むsource_keyでValueError(self, tmp_path: Path) -> None:
        store = PdfStore(tmp_path / "pdfs")
        with pytest.raises(ValueError, match="must be alphanumeric"):
            store.get_source_dir("bad-key")

    def test_異常系_空のsource_keyでValueError(self, tmp_path: Path) -> None:
        store = PdfStore(tmp_path / "pdfs")
        with pytest.raises(ValueError, match="must be alphanumeric"):
            store.get_source_dir("")


class TestPdfStoreListPdfs:
    """Tests for PdfStore.list_pdfs."""

    def test_正常系_PDFファイルが一覧される(self, tmp_path: Path) -> None:
        store = PdfStore(tmp_path / "pdfs")
        source_dir = store.get_source_dir("test_source")
        (source_dir / "report1.pdf").write_bytes(b"%PDF-1.4 test1")
        (source_dir / "report2.pdf").write_bytes(b"%PDF-1.4 test2")
        (source_dir / "notes.txt").write_text("not a pdf")

        pdfs = store.list_pdfs("test_source")
        assert len(pdfs) == 2
        assert all(p.suffix == ".pdf" for p in pdfs)

    def test_エッジケース_存在しないソースで空リスト(self, tmp_path: Path) -> None:
        store = PdfStore(tmp_path / "pdfs")
        pdfs = store.list_pdfs("nonexistent")
        assert pdfs == []


class TestPdfStoreHasPdf:
    """Tests for PdfStore.has_pdf."""

    def test_正常系_存在するPDFでTrueを返す(self, tmp_path: Path) -> None:
        store = PdfStore(tmp_path / "pdfs")
        source_dir = store.get_source_dir("test_source")
        (source_dir / "report.pdf").write_bytes(b"%PDF-1.4 test")

        assert store.has_pdf("test_source", "report.pdf") is True

    def test_正常系_存在しないPDFでFalseを返す(self, tmp_path: Path) -> None:
        store = PdfStore(tmp_path / "pdfs")
        assert store.has_pdf("test_source", "missing.pdf") is False


class TestPdfStoreGetTotalSize:
    """Tests for PdfStore.get_total_size."""

    def test_正常系_合計サイズが正しく算出される(self, tmp_path: Path) -> None:
        store = PdfStore(tmp_path / "pdfs")
        source_dir = store.get_source_dir("test_source")
        (source_dir / "a.pdf").write_bytes(b"x" * 100)
        (source_dir / "b.pdf").write_bytes(b"y" * 200)

        total = store.get_total_size("test_source")
        assert total == 300


class TestPdfStoreCleanup:
    """Tests for PdfStore.cleanup_source."""

    def test_正常系_ソースのPDFが全て削除される(self, tmp_path: Path) -> None:
        store = PdfStore(tmp_path / "pdfs")
        source_dir = store.get_source_dir("cleanup_test")
        (source_dir / "a.pdf").write_bytes(b"test1")
        (source_dir / "b.pdf").write_bytes(b"test2")

        removed = store.cleanup_source("cleanup_test")
        assert removed == 2
        assert store.list_pdfs("cleanup_test") == []
