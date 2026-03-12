"""Unit tests for pdf_pipeline.core.pdf_scanner module.

Tests cover:
- PDF file detection in input directories
- SHA-256 hash calculation
- Unprocessed file detection
- Path traversal prevention
- Edge cases (empty directory, non-PDF files, nested directories)
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from pdf_pipeline.core.pdf_scanner import PdfScanner
from pdf_pipeline.exceptions import PathTraversalError, ScanError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_pdf_dir(tmp_path: Path) -> Path:
    """Create a temporary directory with sample PDF files."""
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    return pdf_dir


def _create_pdf(
    directory: Path, name: str, content: bytes = b"%PDF-1.4 sample"
) -> Path:
    """Helper to create a fake PDF file."""
    path = directory / name
    path.write_bytes(content)
    return path


# ---------------------------------------------------------------------------
# PdfScanner.__init__
# ---------------------------------------------------------------------------


class TestPdfScannerInit:
    """Tests for PdfScanner initialization."""

    def test_正常系_有効なディレクトリで初期化できる(self, tmp_pdf_dir: Path) -> None:
        scanner = PdfScanner(tmp_pdf_dir)
        assert scanner.input_dir == tmp_pdf_dir

    def test_異常系_存在しないディレクトリでScanError(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "nonexistent"
        with pytest.raises(ScanError, match="does not exist"):
            PdfScanner(nonexistent)

    def test_異常系_ファイルパスを指定した場合ScanError(self, tmp_path: Path) -> None:
        file_path = tmp_path / "file.txt"
        file_path.write_text("not a directory")
        with pytest.raises(ScanError, match="not a directory"):
            PdfScanner(file_path)


# ---------------------------------------------------------------------------
# PdfScanner.scan
# ---------------------------------------------------------------------------


class TestPdfScannerScan:
    """Tests for PdfScanner.scan method."""

    def test_正常系_PDFファイルを検出できる(self, tmp_pdf_dir: Path) -> None:
        _create_pdf(tmp_pdf_dir, "report.pdf")
        _create_pdf(tmp_pdf_dir, "annual.pdf")

        scanner = PdfScanner(tmp_pdf_dir)
        results = scanner.scan()

        assert len(results) == 2
        names = {r.name for r in results}
        assert "report.pdf" in names
        assert "annual.pdf" in names

    def test_正常系_空ディレクトリで空リストを返す(self, tmp_pdf_dir: Path) -> None:
        scanner = PdfScanner(tmp_pdf_dir)
        results = scanner.scan()
        assert results == []

    def test_正常系_PDFでないファイルを除外する(self, tmp_pdf_dir: Path) -> None:
        _create_pdf(tmp_pdf_dir, "report.pdf")
        (tmp_pdf_dir / "readme.txt").write_text("not a pdf")
        (tmp_pdf_dir / "data.csv").write_text("a,b,c")

        scanner = PdfScanner(tmp_pdf_dir)
        results = scanner.scan()

        assert len(results) == 1
        assert results[0].name == "report.pdf"

    def test_正常系_結果がソートされている(self, tmp_pdf_dir: Path) -> None:
        _create_pdf(tmp_pdf_dir, "c_report.pdf")
        _create_pdf(tmp_pdf_dir, "a_report.pdf")
        _create_pdf(tmp_pdf_dir, "b_report.pdf")

        scanner = PdfScanner(tmp_pdf_dir)
        results = scanner.scan()

        names = [r.name for r in results]
        assert names == sorted(names)

    def test_正常系_サブディレクトリのPDFは検出しない(self, tmp_pdf_dir: Path) -> None:
        sub = tmp_pdf_dir / "subdir"
        sub.mkdir()
        _create_pdf(tmp_pdf_dir, "root.pdf")
        _create_pdf(sub, "nested.pdf")

        scanner = PdfScanner(tmp_pdf_dir)
        results = scanner.scan()

        assert len(results) == 1
        assert results[0].name == "root.pdf"


# ---------------------------------------------------------------------------
# PdfScanner.compute_sha256
# ---------------------------------------------------------------------------


class TestPdfScannerComputeSha256:
    """Tests for PdfScanner.compute_sha256 method."""

    def test_正常系_SHA256ハッシュを計算できる(self, tmp_pdf_dir: Path) -> None:
        content = b"%PDF-1.4 test content for hashing"
        pdf_path = _create_pdf(tmp_pdf_dir, "test.pdf", content)

        scanner = PdfScanner(tmp_pdf_dir)
        result = scanner.compute_sha256(pdf_path)

        expected = hashlib.sha256(content).hexdigest()
        assert result == expected

    def test_正常系_同じファイルで同じハッシュを返す(self, tmp_pdf_dir: Path) -> None:
        pdf_path = _create_pdf(tmp_pdf_dir, "test.pdf", b"%PDF-1.4 deterministic")

        scanner = PdfScanner(tmp_pdf_dir)
        hash1 = scanner.compute_sha256(pdf_path)
        hash2 = scanner.compute_sha256(pdf_path)

        assert hash1 == hash2

    def test_正常系_異なるファイルで異なるハッシュを返す(
        self, tmp_pdf_dir: Path
    ) -> None:
        pdf1 = _create_pdf(tmp_pdf_dir, "a.pdf", b"content A")
        pdf2 = _create_pdf(tmp_pdf_dir, "b.pdf", b"content B")

        scanner = PdfScanner(tmp_pdf_dir)
        hash1 = scanner.compute_sha256(pdf1)
        hash2 = scanner.compute_sha256(pdf2)

        assert hash1 != hash2

    def test_正常系_ハッシュは64文字の16進数(self, tmp_pdf_dir: Path) -> None:
        pdf_path = _create_pdf(tmp_pdf_dir, "test.pdf")

        scanner = PdfScanner(tmp_pdf_dir)
        result = scanner.compute_sha256(pdf_path)

        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_異常系_存在しないファイルでScanError(self, tmp_pdf_dir: Path) -> None:
        scanner = PdfScanner(tmp_pdf_dir)
        nonexistent = tmp_pdf_dir / "missing.pdf"

        with pytest.raises(ScanError, match="not found"):
            scanner.compute_sha256(nonexistent)

    def test_異常系_パストラバーサルを検出してPathTraversalError(
        self, tmp_pdf_dir: Path
    ) -> None:
        scanner = PdfScanner(tmp_pdf_dir)
        traversal_path = tmp_pdf_dir / ".." / ".." / "etc" / "passwd"

        with pytest.raises(PathTraversalError):
            scanner.compute_sha256(traversal_path)


# ---------------------------------------------------------------------------
# PdfScanner.scan_with_hashes
# ---------------------------------------------------------------------------


class TestPdfScannerScanWithHashes:
    """Tests for PdfScanner.scan_with_hashes method."""

    def test_正常系_ファイルパスとハッシュのペアを返す(self, tmp_pdf_dir: Path) -> None:
        content = b"%PDF-1.4 sample content"
        pdf_path = _create_pdf(tmp_pdf_dir, "report.pdf", content)

        scanner = PdfScanner(tmp_pdf_dir)
        results = scanner.scan_with_hashes()

        assert len(results) == 1
        path, sha256 = results[0]
        assert path == pdf_path
        assert sha256 == hashlib.sha256(content).hexdigest()

    def test_正常系_複数ファイルのハッシュを一括取得できる(
        self, tmp_pdf_dir: Path
    ) -> None:
        content_a = b"content A"
        content_b = b"content B"
        _create_pdf(tmp_pdf_dir, "a.pdf", content_a)
        _create_pdf(tmp_pdf_dir, "b.pdf", content_b)

        scanner = PdfScanner(tmp_pdf_dir)
        results = scanner.scan_with_hashes()

        assert len(results) == 2
        hashes = {sha256 for _, sha256 in results}
        assert hashlib.sha256(content_a).hexdigest() in hashes
        assert hashlib.sha256(content_b).hexdigest() in hashes

    def test_正常系_空ディレクトリで空リストを返す(self, tmp_pdf_dir: Path) -> None:
        scanner = PdfScanner(tmp_pdf_dir)
        results = scanner.scan_with_hashes()
        assert results == []

    def test_正常系_結果がパスでソートされている(self, tmp_pdf_dir: Path) -> None:
        _create_pdf(tmp_pdf_dir, "c.pdf")
        _create_pdf(tmp_pdf_dir, "a.pdf")
        _create_pdf(tmp_pdf_dir, "b.pdf")

        scanner = PdfScanner(tmp_pdf_dir)
        results = scanner.scan_with_hashes()

        paths = [p for p, _ in results]
        assert paths == sorted(paths)


# ---------------------------------------------------------------------------
# PdfScanner.find_unprocessed
# ---------------------------------------------------------------------------


class TestPdfScannerFindUnprocessed:
    """Tests for PdfScanner.find_unprocessed method."""

    def test_正常系_処理済みハッシュがない場合全ファイルを返す(
        self, tmp_pdf_dir: Path
    ) -> None:
        _create_pdf(tmp_pdf_dir, "a.pdf", b"content A")
        _create_pdf(tmp_pdf_dir, "b.pdf", b"content B")

        scanner = PdfScanner(tmp_pdf_dir)
        results = scanner.find_unprocessed(processed_hashes=set())

        assert len(results) == 2

    def test_正常系_処理済みファイルを除外する(self, tmp_pdf_dir: Path) -> None:
        content_a = b"content A"
        content_b = b"content B"
        _create_pdf(tmp_pdf_dir, "a.pdf", content_a)
        _create_pdf(tmp_pdf_dir, "b.pdf", content_b)

        processed = {hashlib.sha256(content_a).hexdigest()}

        scanner = PdfScanner(tmp_pdf_dir)
        results = scanner.find_unprocessed(processed_hashes=processed)

        assert len(results) == 1
        path, sha256 = results[0]
        assert path.name == "b.pdf"
        assert sha256 == hashlib.sha256(content_b).hexdigest()

    def test_正常系_全ファイルが処理済みの場合空リストを返す(
        self, tmp_pdf_dir: Path
    ) -> None:
        content = b"processed content"
        _create_pdf(tmp_pdf_dir, "done.pdf", content)
        processed = {hashlib.sha256(content).hexdigest()}

        scanner = PdfScanner(tmp_pdf_dir)
        results = scanner.find_unprocessed(processed_hashes=processed)

        assert results == []

    def test_正常系_空ディレクトリで空リストを返す(self, tmp_pdf_dir: Path) -> None:
        scanner = PdfScanner(tmp_pdf_dir)
        results = scanner.find_unprocessed(processed_hashes={"some_hash"})
        assert results == []
