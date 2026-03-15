"""Unit tests for pdf_pipeline.cli.helpers module.

Tests cover:
- compute_sha256_standalone: SHA-256 hash calculation consistency
- compute_hash: SHA-256 hash output via CLI helper
- check_idempotency: StateManager-based duplicate detection
- get_page_count: PyMuPDF-based page counting (mocked)
- compute_output_dir: Mirror-path output directory computation
- chunk_and_save: MarkdownChunker-based chunking and JSON persistence
- save_metadata: Metadata JSON file creation with method_b converter
- record_completed: StateManager status recording
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from pdf_pipeline.cli.helpers import (
    _cli_main,
    check_idempotency,
    chunk_and_save,
    compute_hash,
    compute_output_dir,
    get_page_count,
    record_completed,
    save_metadata,
)
from pdf_pipeline.core.pdf_scanner import PdfScanner, compute_sha256_standalone
from pdf_pipeline.exceptions import ScanError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_pdf(tmp_path: Path) -> Path:
    """Create a temporary fake PDF file."""
    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF-1.4 test content for cli helpers")
    return pdf


@pytest.fixture
def state_file(tmp_path: Path) -> Path:
    """Return a temporary state file path."""
    return tmp_path / ".tmp" / "state.json"


@pytest.fixture
def sample_markdown(tmp_path: Path) -> Path:
    """Create a sample Markdown report file."""
    md = tmp_path / "report.md"
    md.write_text(
        "# Section 1\n\nContent for section 1.\n\n"
        "## Section 2\n\nContent for section 2.\n",
        encoding="utf-8",
    )
    return md


# ---------------------------------------------------------------------------
# compute_sha256_standalone
# ---------------------------------------------------------------------------


class TestComputeSha256Standalone:
    """Tests for compute_sha256_standalone function."""

    def test_正常系_SHA256ハッシュを計算できる(self, tmp_pdf: Path) -> None:
        result = compute_sha256_standalone(str(tmp_pdf))

        expected = hashlib.sha256(b"%PDF-1.4 test content for cli helpers").hexdigest()
        assert result == expected
        assert len(result) == 64

    def test_正常系_PdfScannerと同じハッシュを返す(self, tmp_path: Path) -> None:
        # Create a PDF inside a directory so PdfScanner can use it
        pdf_dir = tmp_path / "pdfs"
        pdf_dir.mkdir()
        pdf = pdf_dir / "test.pdf"
        content = b"%PDF-1.4 consistency test content"
        pdf.write_bytes(content)

        # Compute via standalone function
        standalone_hash = compute_sha256_standalone(str(pdf))

        # Compute via PdfScanner instance method
        scanner = PdfScanner(pdf_dir)
        scanner_hash = scanner.compute_sha256(pdf)

        assert standalone_hash == scanner_hash

    def test_異常系_存在しないファイルでScanError(self, tmp_path: Path) -> None:
        with pytest.raises(ScanError, match="not found"):
            compute_sha256_standalone(str(tmp_path / "nonexistent.pdf"))


# ---------------------------------------------------------------------------
# compute_hash
# ---------------------------------------------------------------------------


class TestComputeHash:
    """Tests for compute_hash function."""

    def test_正常系_SHA256をstdoutに出力する(
        self, tmp_pdf: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with patch(
            "sys.argv",
            ["helpers", "compute_hash", str(tmp_pdf)],
        ):
            _cli_main()

        captured = capsys.readouterr()
        output = captured.out.strip()
        expected = hashlib.sha256(b"%PDF-1.4 test content for cli helpers").hexdigest()
        assert output == expected

    def test_異常系_存在しないファイルでエラー(self, tmp_path: Path) -> None:
        with pytest.raises(ScanError, match="not found"):
            compute_hash(str(tmp_path / "nonexistent.pdf"))


# ---------------------------------------------------------------------------
# check_idempotency
# ---------------------------------------------------------------------------


class TestCheckIdempotency:
    """Tests for check_idempotency function."""

    def test_正常系_未処理でfalseを出力する(
        self, state_file: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        sha256 = "abcd1234" * 8
        with patch(
            "sys.argv",
            ["helpers", "check_idempotency", sha256, str(state_file)],
        ):
            _cli_main()

        captured = capsys.readouterr()
        assert captured.out.strip() == "false"

    def test_正常系_処理済みでtrueを出力する(
        self, state_file: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Pre-populate state file with a completed entry
        state_file.parent.mkdir(parents=True, exist_ok=True)
        sha256 = "abcd1234" * 8
        state_data = {
            "version": 2,
            "sha256_to_status": {
                sha256: {
                    "status": "completed",
                    "filename": None,
                    "processed_at": None,
                }
            },
            "batches": {},
        }
        state_file.write_text(
            json.dumps(state_data, ensure_ascii=False), encoding="utf-8"
        )

        with patch(
            "sys.argv",
            ["helpers", "check_idempotency", sha256, str(state_file)],
        ):
            _cli_main()

        captured = capsys.readouterr()
        assert captured.out.strip() == "true"


# ---------------------------------------------------------------------------
# get_page_count
# ---------------------------------------------------------------------------


class TestGetPageCount:
    """Tests for get_page_count function."""

    def test_正常系_ページ数をstdoutに出力する(
        self, tmp_pdf: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_doc = MagicMock()
        mock_doc.page_count = 42
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        with (
            patch("pdf_pipeline.cli.helpers.fitz") as mock_fitz,
            patch(
                "sys.argv",
                ["helpers", "get_page_count", str(tmp_pdf)],
            ),
        ):
            mock_fitz.open.return_value = mock_doc
            _cli_main()

        captured = capsys.readouterr()
        assert captured.out.strip() == "42"


# ---------------------------------------------------------------------------
# compute_output_dir
# ---------------------------------------------------------------------------


class TestComputeOutputDir:
    """Tests for compute_output_dir function."""

    def test_正常系_ミラーパスを出力する(self, tmp_path: Path) -> None:
        pdf_path = str(tmp_path / "raw" / "pdfs" / "subdir" / "report.pdf")
        sha256 = "abcdef0123456789" * 4

        with patch("pdf_pipeline.cli.helpers.get_path") as mock_get_path:
            mock_get_path.return_value = tmp_path / "processed"
            result = compute_output_dir(pdf_path, sha256)

        # Mirror subpath should include "subdir"
        assert "subdir" in result
        assert "report_abcdef01" in result

    def test_正常系_rawpdfs外のPDFでフォールバック(self, tmp_path: Path) -> None:
        # PDF is NOT under raw/pdfs/, so no mirror subpath
        pdf_path = str(tmp_path / "other" / "location" / "report.pdf")
        sha256 = "deadbeef" + "0" * 56

        with patch("pdf_pipeline.cli.helpers.get_path") as mock_get_path:
            mock_get_path.return_value = tmp_path / "processed"
            result = compute_output_dir(pdf_path, sha256)

        # Should fallback to processed/{stem}_{hash8} without mirror subpath
        expected_suffix = "report_deadbeef"
        assert result.endswith(expected_suffix)
        # Should NOT contain any subdirectory between "processed" and the stem
        processed_str = str(tmp_path / "processed")
        relative = result[len(processed_str) :]
        # Only one path separator (the leading /) plus the stem_hash8
        assert relative in {"/report_deadbeef", "\\report_deadbeef"}

    def test_正常系_stem_hash8形式(self, tmp_path: Path) -> None:
        pdf_path = str(tmp_path / "raw" / "pdfs" / "annual_report.pdf")
        sha256 = "1a2b3c4d" + "e" * 56

        with patch("pdf_pipeline.cli.helpers.get_path") as mock_get_path:
            mock_get_path.return_value = tmp_path / "processed"
            result = compute_output_dir(pdf_path, sha256)

        # Format: {stem}_{first 8 chars of sha256}
        assert "annual_report_1a2b3c4d" in result


# ---------------------------------------------------------------------------
# chunk_and_save
# ---------------------------------------------------------------------------


class TestChunkAndSave:
    """Tests for chunk_and_save function."""

    def test_正常系_reportmdをチャンク化してchunksjsonを保存する(
        self, sample_markdown: Path, tmp_path: Path
    ) -> None:
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        sha256 = "abcd1234" * 8

        chunk_and_save(str(sample_markdown), sha256, str(output_dir))

        chunks_file = output_dir / "chunks.json"
        assert chunks_file.exists()

        data = json.loads(chunks_file.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) == 2

    def test_正常系_チャンク数をstdoutに出力する(
        self, sample_markdown: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        output_dir = tmp_path / "output"
        sha256 = "abcd1234" * 8

        with patch(
            "sys.argv",
            [
                "helpers",
                "chunk_and_save",
                str(sample_markdown),
                sha256,
                str(output_dir),
            ],
        ):
            _cli_main()

        captured = capsys.readouterr()
        assert captured.out.strip() == "2"

    def test_正常系_空のmarkdownで0を出力する(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        empty_md = tmp_path / "empty.md"
        empty_md.write_text("", encoding="utf-8")
        output_dir = tmp_path / "output"
        sha256 = "abcd1234" * 8

        with patch(
            "sys.argv",
            [
                "helpers",
                "chunk_and_save",
                str(empty_md),
                sha256,
                str(output_dir),
            ],
        ):
            _cli_main()

        captured = capsys.readouterr()
        assert captured.out.strip() == "0"


# ---------------------------------------------------------------------------
# save_metadata
# ---------------------------------------------------------------------------


class TestSaveMetadata:
    """Tests for save_metadata function."""

    def test_正常系_metadatajsonを書き込む(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        sha256 = "abcd1234" * 8
        pdf_path = "/path/to/report.pdf"
        pages = "30"
        chunks = "5"

        result = save_metadata(str(output_dir), sha256, pdf_path, pages, chunks)

        assert result == "ok"

        meta_file = output_dir / "metadata.json"
        assert meta_file.exists()

        data = json.loads(meta_file.read_text(encoding="utf-8"))
        assert data["sha256"] == sha256
        assert data["pdf_path"] == pdf_path
        assert data["pages"] == 30
        assert data["chunks"] == 5
        assert "processed_at" in data

    def test_正常系_converter名がmethod_bである(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        sha256 = "abcd1234" * 8

        save_metadata(str(output_dir), sha256, "/path/to/doc.pdf", "10", "3")

        meta_file = output_dir / "metadata.json"
        data = json.loads(meta_file.read_text(encoding="utf-8"))
        assert data["converter"] == "method_b"


# ---------------------------------------------------------------------------
# record_completed
# ---------------------------------------------------------------------------


class TestRecordCompleted:
    """Tests for record_completed function."""

    def test_正常系_StateManagerにcompletedを記録する(self, state_file: Path) -> None:
        sha256 = "abcd1234" * 8

        result = record_completed(sha256, str(state_file), "report.pdf")

        assert result == "ok"
        assert state_file.exists()

        data = json.loads(state_file.read_text(encoding="utf-8"))
        entry = data["sha256_to_status"][sha256]
        assert entry["status"] == "completed"
        assert entry["filename"] == "report.pdf"
