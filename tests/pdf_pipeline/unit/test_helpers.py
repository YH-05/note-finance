"""Unit tests for pdf_pipeline.cli.helpers module.

Tests cover:
- compute_hash: SHA-256 hash calculation via compute_sha256_standalone
- check_idempotency: StateManager-based duplicate detection
- get_page_count: PyMuPDF-based page counting
- compute_output_dir: Mirror-path output directory computation
- chunk_and_save: MarkdownChunker-based chunking and JSON persistence
- save_metadata: Metadata JSON file creation
- record_completed: StateManager status recording
- CLI entry point: sys.argv dispatch
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
    check_idempotency,
    chunk_and_save,
    compute_hash,
    compute_output_dir,
    get_page_count,
    record_completed,
    save_metadata,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_pdf(tmp_path: Path) -> Path:
    """Create a temporary fake PDF file."""
    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF-1.4 test content for helpers")
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
# compute_hash
# ---------------------------------------------------------------------------


class TestComputeHash:
    """Tests for compute_hash function."""

    def test_正常系_SHA256ハッシュを計算できる(self, tmp_pdf: Path) -> None:
        result = compute_hash(str(tmp_pdf))

        expected = hashlib.sha256(b"%PDF-1.4 test content for helpers").hexdigest()
        assert result == expected

    def test_正常系_ハッシュは64文字の16進数(self, tmp_pdf: Path) -> None:
        result = compute_hash(str(tmp_pdf))

        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_異常系_存在しないファイルでScanError(self, tmp_path: Path) -> None:
        from pdf_pipeline.exceptions import ScanError

        with pytest.raises(ScanError, match="not found"):
            compute_hash(str(tmp_path / "nonexistent.pdf"))


# ---------------------------------------------------------------------------
# check_idempotency
# ---------------------------------------------------------------------------


class TestCheckIdempotency:
    """Tests for check_idempotency function."""

    def test_正常系_未処理のハッシュでfalseを返す(self, state_file: Path) -> None:
        result = check_idempotency("abcd1234" * 8, str(state_file))

        assert result == "false"

    def test_正常系_処理済みのハッシュでtrueを返す(self, state_file: Path) -> None:
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

        result = check_idempotency(sha256, str(state_file))

        assert result == "true"

    def test_正常系_状態ファイルが存在しない場合falseを返す(
        self, tmp_path: Path
    ) -> None:
        new_state = tmp_path / "new_dir" / "state.json"
        result = check_idempotency("abcd1234" * 8, str(new_state))

        assert result == "false"


# ---------------------------------------------------------------------------
# get_page_count
# ---------------------------------------------------------------------------


class TestGetPageCount:
    """Tests for get_page_count function."""

    def test_正常系_ページ数を返す(self, tmp_pdf: Path) -> None:
        mock_doc = MagicMock()
        mock_doc.page_count = 42
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        with patch("pdf_pipeline.cli.helpers.fitz") as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            result = get_page_count(str(tmp_pdf))

        assert result == "42"

    def test_正常系_1ページのPDFで1を返す(self, tmp_pdf: Path) -> None:
        mock_doc = MagicMock()
        mock_doc.page_count = 1
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        with patch("pdf_pipeline.cli.helpers.fitz") as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            result = get_page_count(str(tmp_pdf))

        assert result == "1"

    def test_正常系_結果は文字列で返る(self, tmp_pdf: Path) -> None:
        mock_doc = MagicMock()
        mock_doc.page_count = 10
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        with patch("pdf_pipeline.cli.helpers.fitz") as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            result = get_page_count(str(tmp_pdf))

        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# compute_output_dir
# ---------------------------------------------------------------------------


class TestComputeOutputDir:
    """Tests for compute_output_dir function."""

    def test_正常系_出力ディレクトリパスを返す(self, tmp_path: Path) -> None:
        pdf_path = str(tmp_path / "raw" / "pdfs" / "report.pdf")
        sha256 = "abcdef0123456789" * 4

        with patch("pdf_pipeline.cli.helpers.get_path") as mock_get_path:
            mock_get_path.return_value = tmp_path / "processed"
            result = compute_output_dir(pdf_path, sha256)

        # Should contain stem and hash8
        assert "report" in result
        assert "abcdef01" in result

    def test_正常系_hash8は先頭8文字(self, tmp_path: Path) -> None:
        pdf_path = str(tmp_path / "report.pdf")
        sha256 = "deadbeef" + "0" * 56

        with patch("pdf_pipeline.cli.helpers.get_path") as mock_get_path:
            mock_get_path.return_value = tmp_path / "processed"
            result = compute_output_dir(pdf_path, sha256)

        assert "deadbeef" in result

    def test_正常系_結果は文字列で返る(self, tmp_path: Path) -> None:
        pdf_path = str(tmp_path / "report.pdf")
        sha256 = "a" * 64

        with patch("pdf_pipeline.cli.helpers.get_path") as mock_get_path:
            mock_get_path.return_value = tmp_path / "processed"
            result = compute_output_dir(pdf_path, sha256)

        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# chunk_and_save
# ---------------------------------------------------------------------------


class TestChunkAndSave:
    """Tests for chunk_and_save function."""

    def test_正常系_チャンク数を返す(
        self, sample_markdown: Path, tmp_path: Path
    ) -> None:
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        sha256 = "abcd1234" * 8

        result = chunk_and_save(str(sample_markdown), sha256, str(output_dir))

        # Markdown with 2 headings should produce 2 chunks
        assert int(result) == 2

    def test_正常系_チャンクファイルが保存される(
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

    def test_正常系_空マークダウンで0チャンク(self, tmp_path: Path) -> None:
        empty_md = tmp_path / "empty.md"
        empty_md.write_text("", encoding="utf-8")
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        sha256 = "abcd1234" * 8

        result = chunk_and_save(str(empty_md), sha256, str(output_dir))

        assert result == "0"

    def test_正常系_結果は文字列で返る(
        self, sample_markdown: Path, tmp_path: Path
    ) -> None:
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        sha256 = "abcd1234" * 8

        result = chunk_and_save(str(sample_markdown), sha256, str(output_dir))

        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# save_metadata
# ---------------------------------------------------------------------------


class TestSaveMetadata:
    """Tests for save_metadata function."""

    def test_正常系_メタデータファイルが保存される(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        sha256 = "abcd1234" * 8
        pdf_path = "/path/to/report.pdf"
        pages = "30"
        chunks = "5"

        result = save_metadata(str(output_dir), sha256, pdf_path, pages, chunks)

        assert result == "ok"

    def test_正常系_メタデータにフィールドが含まれる(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        sha256 = "abcd1234" * 8
        pdf_path = "/path/to/report.pdf"

        save_metadata(str(output_dir), sha256, pdf_path, "30", "5")

        meta_file = output_dir / "metadata.json"
        assert meta_file.exists()

        data = json.loads(meta_file.read_text(encoding="utf-8"))
        assert data["sha256"] == sha256
        assert data["pdf_path"] == pdf_path
        assert data["pages"] == 30
        assert data["chunks"] == 5

    def test_正常系_出力ディレクトリが自動作成される(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "new_dir" / "sub"
        sha256 = "abcd1234" * 8

        result = save_metadata(
            str(output_dir), sha256, "/path/to/report.pdf", "10", "3"
        )

        assert result == "ok"
        assert output_dir.exists()


# ---------------------------------------------------------------------------
# record_completed
# ---------------------------------------------------------------------------


class TestRecordCompleted:
    """Tests for record_completed function."""

    def test_正常系_状態を記録してokを返す(self, state_file: Path) -> None:
        sha256 = "abcd1234" * 8

        result = record_completed(sha256, str(state_file), "report.pdf")

        assert result == "ok"

    def test_正常系_状態ファイルにcompletedが記録される(self, state_file: Path) -> None:
        sha256 = "abcd1234" * 8

        record_completed(sha256, str(state_file), "report.pdf")

        assert state_file.exists()
        data = json.loads(state_file.read_text(encoding="utf-8"))
        entry = data["sha256_to_status"][sha256]
        assert entry["status"] == "completed"
        assert entry["filename"] == "report.pdf"

    def test_正常系_状態ファイルが存在しない場合も記録できる(
        self, tmp_path: Path
    ) -> None:
        new_state = tmp_path / "new_dir" / "state.json"
        sha256 = "abcd1234" * 8

        result = record_completed(sha256, str(new_state), "doc.pdf")

        assert result == "ok"
        assert new_state.exists()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


class TestCLIEntryPoint:
    """Tests for the __main__ CLI dispatcher."""

    def test_正常系_compute_hashが呼び出せる(
        self, tmp_pdf: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with patch(
            "sys.argv",
            ["helpers", "compute_hash", str(tmp_pdf)],
        ):
            import pdf_pipeline.cli.helpers as mod

            mod._cli_main()

        captured = capsys.readouterr()
        output = captured.out.strip()
        assert len(output) == 64
        assert all(c in "0123456789abcdef" for c in output)

    def test_正常系_check_idempotencyが呼び出せる(
        self, state_file: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        sha256 = "abcd1234" * 8
        with patch(
            "sys.argv",
            ["helpers", "check_idempotency", sha256, str(state_file)],
        ):
            import pdf_pipeline.cli.helpers as mod

            mod._cli_main()

        captured = capsys.readouterr()
        assert captured.out.strip() == "false"

    def test_異常系_不正な関数名でSystemExit(self) -> None:
        with (
            patch("sys.argv", ["helpers", "nonexistent_func"]),
            pytest.raises(SystemExit),
        ):
            import pdf_pipeline.cli.helpers as mod

            mod._cli_main()
