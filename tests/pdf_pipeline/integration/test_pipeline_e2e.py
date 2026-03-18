"""End-to-end integration tests for the PDF processing pipeline.

Tests cover:
- E2E pipeline execution with mock LLM (PDF input → chunks.json output)
- Idempotency: same PDF processed twice produces identical output
- CLI command integration via Click's test runner
- Ground truth validation against data/sample_report/ground_truth.json

All external LLM calls are mocked to avoid network dependencies.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from pdf_pipeline.cli.main import cli
from pdf_pipeline.core.chunker import MarkdownChunker
from pdf_pipeline.core.noise_filter import NoiseFilter
from pdf_pipeline.core.pipeline import PdfPipeline
from pdf_pipeline.schemas.tables import ExtractedTables, RawTable, TableCell
from pdf_pipeline.services.state_manager import StateManager
from pdf_pipeline.types import PipelineConfig

# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

_SAMPLE_PDF_CONTENT = b"%PDF-1.4 1 0 obj <</Type /Catalog>> endobj"
"""Minimal fake PDF bytes for hashing and pipeline testing."""

_SAMPLE_MARKDOWN = """\
# Executive Summary

This is the executive summary section of the HSBC ISAT 3Q25 report.
Revenue grew 5% year-over-year to $15.8 billion.

## Financial Highlights

Net interest income increased by 3% to $8.2 billion.
Fee income was stable at $4.1 billion.

## Capital Position

CET1 ratio stands at 15.2%, well above regulatory minimums.
Return on Tangible Equity (RoTE) was 14.5%.

## Outlook

Management expects full-year 2025 RoTE of approximately 14-15%.
"""

_SAMPLE_GROUND_TRUTH_PATH = Path("data/sample_report/ground_truth.json")


def _make_pipeline_config(tmp_path: Path) -> PipelineConfig:
    """Create a minimal PipelineConfig for testing.

    Parameters
    ----------
    tmp_path : Path
        Pytest temporary directory.

    Returns
    -------
    PipelineConfig
        Configured pipeline settings pointing to tmp_path.
    """
    return PipelineConfig(
        input_dirs=[tmp_path / "pdfs"],
        output_dir=tmp_path / "output",
    )


def _make_mock_pipeline(
    tmp_path: Path,
    *,
    markdown: str = _SAMPLE_MARKDOWN,
    fail_on_convert: bool = False,
) -> tuple[PdfPipeline, dict[str, MagicMock]]:
    """Create a PdfPipeline with all external components mocked.

    Parameters
    ----------
    tmp_path : Path
        Pytest temporary directory.
    markdown : str
        Markdown string the mock converter should return.
    fail_on_convert : bool
        If True, the mock markdown converter raises RuntimeError.

    Returns
    -------
    tuple[PdfPipeline, dict[str, MagicMock]]
        Pipeline instance and dict of mock components keyed by name.
    """
    config = _make_pipeline_config(tmp_path)
    config.input_dirs[0].mkdir(parents=True, exist_ok=True)
    config.output_dir.mkdir(parents=True, exist_ok=True)

    scanner = MagicMock()
    noise_filter = MagicMock()
    noise_filter.filter_text.return_value = "filtered text content"

    markdown_converter = MagicMock()
    if fail_on_convert:
        markdown_converter.convert.side_effect = RuntimeError("LLM unavailable")
    else:
        markdown_converter.convert.return_value = markdown

    table_detector = MagicMock()
    table_detector.detect.return_value = []

    table_reconstructor = MagicMock()
    # AIDEV-NOTE: ExtractedTables requires raw_tables to be non-empty (Tier 1 guarantee)
    _sample_cell = TableCell(row=0, col=0, value="Revenue")
    _sample_raw_table = RawTable(
        page_number=1, bbox=[0.0, 0.0, 200.0, 100.0], cells=[_sample_cell]
    )
    table_reconstructor.reconstruct.return_value = ExtractedTables(
        pdf_path=str(tmp_path / "report.pdf"),
        raw_tables=[_sample_raw_table],
    )

    # Use real MarkdownChunker for accurate chunk behaviour
    chunker = MarkdownChunker()

    # Use real StateManager backed by a temp file
    state_manager = StateManager(config.output_dir / "state.json")

    pipeline = PdfPipeline(
        config=config,
        scanner=scanner,
        noise_filter=noise_filter,
        markdown_converter=markdown_converter,
        table_detector=table_detector,
        table_reconstructor=table_reconstructor,
        chunker=chunker,
        state_manager=state_manager,
    )

    mocks = {
        "scanner": scanner,
        "noise_filter": noise_filter,
        "markdown_converter": markdown_converter,
        "table_detector": table_detector,
        "table_reconstructor": table_reconstructor,
    }

    return pipeline, mocks


def _create_sample_pdf(directory: Path, name: str = "sample.pdf") -> Path:
    """Write a minimal fake PDF to a directory.

    Parameters
    ----------
    directory : Path
        Directory in which to create the file.
    name : str
        Filename for the PDF.

    Returns
    -------
    Path
        Path to the newly created file.
    """
    directory.mkdir(parents=True, exist_ok=True)
    pdf_path = directory / name
    pdf_path.write_bytes(_SAMPLE_PDF_CONTENT)
    return pdf_path


# ---------------------------------------------------------------------------
# E2E Pipeline Tests (PDF input → chunks.json output)
# ---------------------------------------------------------------------------


class TestPipelineE2E:
    """End-to-end pipeline tests using mock LLM components."""

    def test_正常系_PDFからchunksJsonが生成される(self, tmp_path: Path) -> None:
        """E2E: A PDF input produces a chunks.json output file."""
        pipeline, _ = _make_mock_pipeline(tmp_path)
        pdf_path = _create_sample_pdf(tmp_path / "pdfs")
        source_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()

        result = pipeline.process_pdf(pdf_path=pdf_path, source_hash=source_hash)

        assert result["status"] == "completed"
        output_file = tmp_path / "output" / source_hash / "chunks.json"
        assert output_file.exists(), f"chunks.json not found at {output_file}"

    def test_正常系_chunksJsonに正しい構造がある(self, tmp_path: Path) -> None:
        """E2E: chunks.json contains well-formed chunk dicts."""
        pipeline, _ = _make_mock_pipeline(tmp_path)
        pdf_path = _create_sample_pdf(tmp_path / "pdfs")
        source_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()

        pipeline.process_pdf(pdf_path=pdf_path, source_hash=source_hash)

        output_file = tmp_path / "output" / source_hash / "chunks.json"
        chunks: list[dict[str, Any]] = json.loads(
            output_file.read_text(encoding="utf-8")
        )

        assert isinstance(chunks, list)
        assert len(chunks) > 0, "At least one chunk should be produced"

        for chunk in chunks:
            assert "source_hash" in chunk
            assert "chunk_index" in chunk
            assert "content" in chunk
            assert "tables" in chunk
            assert chunk["source_hash"] == source_hash

    def test_正常系_chunksのsource_hashが正しい(self, tmp_path: Path) -> None:
        """E2E: All chunks carry the expected source_hash."""
        pipeline, _ = _make_mock_pipeline(tmp_path)
        pdf_path = _create_sample_pdf(tmp_path / "pdfs")
        source_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()

        pipeline.process_pdf(pdf_path=pdf_path, source_hash=source_hash)

        output_file = tmp_path / "output" / source_hash / "chunks.json"
        chunks = json.loads(output_file.read_text(encoding="utf-8"))

        for i, chunk in enumerate(chunks):
            assert chunk["source_hash"] == source_hash, (
                f"Chunk {i} has wrong source_hash: {chunk['source_hash']}"
            )

    def test_正常系_複数セクションが正しくチャンク化される(
        self, tmp_path: Path
    ) -> None:
        """E2E: Multi-section Markdown produces multiple ordered chunks."""
        pipeline, _ = _make_mock_pipeline(tmp_path, markdown=_SAMPLE_MARKDOWN)
        pdf_path = _create_sample_pdf(tmp_path / "pdfs")
        source_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()

        pipeline.process_pdf(pdf_path=pdf_path, source_hash=source_hash)

        output_file = tmp_path / "output" / source_hash / "chunks.json"
        chunks = json.loads(output_file.read_text(encoding="utf-8"))

        assert len(chunks) >= 3, f"Expected at least 3 chunks, got {len(chunks)}"

        # Verify chunk ordering
        indices = [c["chunk_index"] for c in chunks]
        assert indices == list(range(len(chunks))), "Chunks must be in order"

    def test_異常系_LLM変換失敗でfailedステータスになる(self, tmp_path: Path) -> None:
        """E2E: LLM conversion failure results in 'failed' status."""
        pipeline, _ = _make_mock_pipeline(tmp_path, fail_on_convert=True)
        pdf_path = _create_sample_pdf(tmp_path / "pdfs")
        source_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()

        result = pipeline.process_pdf(pdf_path=pdf_path, source_hash=source_hash)

        assert result["status"] == "failed"
        assert "error" in result


# ---------------------------------------------------------------------------
# Idempotency Tests
# ---------------------------------------------------------------------------


class TestPipelineIdempotency:
    """Tests for pipeline idempotency: same PDF processed twice = same output."""

    def test_正常系_同一PDFを2回処理すると2回目はスキップされる(
        self, tmp_path: Path
    ) -> None:
        """Idempotency: Second processing of same PDF is skipped."""
        pipeline, mocks = _make_mock_pipeline(tmp_path)
        pdf_path = _create_sample_pdf(tmp_path / "pdfs")
        source_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()

        result1 = pipeline.process_pdf(pdf_path=pdf_path, source_hash=source_hash)
        assert result1["status"] == "completed"

        result2 = pipeline.process_pdf(pdf_path=pdf_path, source_hash=source_hash)
        assert result2["status"] == "skipped"

        # LLM conversion should only be called once
        assert mocks["markdown_converter"].convert.call_count == 1

    def test_正常系_2回処理後のchunksJsonが同一内容になる(self, tmp_path: Path) -> None:
        """Idempotency: chunks.json content is unchanged after second processing attempt."""
        pipeline, _ = _make_mock_pipeline(tmp_path)
        pdf_path = _create_sample_pdf(tmp_path / "pdfs")
        source_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()

        pipeline.process_pdf(pdf_path=pdf_path, source_hash=source_hash)

        output_file = tmp_path / "output" / source_hash / "chunks.json"
        content_after_first = output_file.read_text(encoding="utf-8")
        mtime_after_first = output_file.stat().st_mtime

        # Second run should skip and not modify the file
        pipeline.process_pdf(pdf_path=pdf_path, source_hash=source_hash)

        content_after_second = output_file.read_text(encoding="utf-8")
        mtime_after_second = output_file.stat().st_mtime

        assert content_after_first == content_after_second
        assert mtime_after_first == mtime_after_second

    def test_正常系_異なるPDFは独立して処理される(self, tmp_path: Path) -> None:
        """Idempotency: Different PDFs are processed independently."""
        pipeline, _mocks = _make_mock_pipeline(tmp_path)

        pdf_path_a = _create_sample_pdf(tmp_path / "pdfs", name="report_a.pdf")
        pdf_path_b = tmp_path / "pdfs" / "report_b.pdf"
        pdf_path_b.write_bytes(b"%PDF-1.4 different content for b")

        hash_a = hashlib.sha256(pdf_path_a.read_bytes()).hexdigest()
        hash_b = hashlib.sha256(pdf_path_b.read_bytes()).hexdigest()

        assert hash_a != hash_b, "Test requires different hashes"

        result_a = pipeline.process_pdf(pdf_path=pdf_path_a, source_hash=hash_a)
        result_b = pipeline.process_pdf(pdf_path=pdf_path_b, source_hash=hash_b)

        assert result_a["status"] == "completed"
        assert result_b["status"] == "completed"

        # Both output files should exist
        assert (tmp_path / "output" / hash_a / "chunks.json").exists()
        assert (tmp_path / "output" / hash_b / "chunks.json").exists()


# ---------------------------------------------------------------------------
# CLI Command Tests
# ---------------------------------------------------------------------------


class TestCliProcess:
    """Tests for the 'pdf-pipeline process' CLI command."""

    def test_正常系_processコマンドがPDFを処理できる(self, tmp_path: Path) -> None:
        """CLI: 'process' command exits 0 for a valid PDF."""
        pdf_path = _create_sample_pdf(tmp_path / "pdfs")
        output_dir = tmp_path / "output"

        runner = CliRunner()
        with (
            runner.isolated_filesystem(temp_dir=tmp_path),
            patch("pdf_pipeline.cli.main.load_config") as mock_load_config,
            patch("pdf_pipeline.cli.main._build_pipeline_for_dir") as mock_build,
        ):
            mock_config = MagicMock()
            mock_load_config.return_value = mock_config

            mock_pipeline = MagicMock()
            source_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
            mock_pipeline.process_pdf.return_value = {
                "status": "completed",
                "source_hash": source_hash,
                "chunk_count": 4,
            }
            mock_build.return_value = mock_pipeline

            result = runner.invoke(
                cli,
                [
                    "--output-dir",
                    str(output_dir),
                    "--config",
                    str(tmp_path / "config.yaml"),
                    "process",
                    str(pdf_path),
                ],
            )

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert "Completed" in result.output or "completed" in result.output.lower()

    def test_異常系_存在しないPDFでエラー終了する(self, tmp_path: Path) -> None:
        """CLI: 'process' command exits non-zero for non-existent PDF."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--output-dir",
                str(tmp_path / "output"),
                "--config",
                str(tmp_path / "config.yaml"),
                "process",
                str(tmp_path / "nonexistent.pdf"),
            ],
        )
        assert result.exit_code != 0


class TestCliStatus:
    """Tests for the 'pdf-pipeline status' CLI command."""

    def test_正常系_statusコマンドが状態を表示できる(self, tmp_path: Path) -> None:
        """CLI: 'status' command exits 0 and displays tracking info."""
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True)

        # Pre-populate state
        state_manager = StateManager(output_dir / "state.json")
        state_manager.record_status("abc123def456" * 4, "completed")
        state_manager.save()

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--output-dir",
                str(output_dir),
                "--config",
                str(tmp_path / "config.yaml"),
                "status",
            ],
        )

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert "completed" in result.output.lower() or "Completed" in result.output

    def test_正常系_状態が空の場合にメッセージが表示される(
        self, tmp_path: Path
    ) -> None:
        """CLI: 'status' command shows empty message when no PDFs tracked."""
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True)

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--output-dir",
                str(output_dir),
                "--config",
                str(tmp_path / "config.yaml"),
                "status",
            ],
        )

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert "No PDFs" in result.output or "no" in result.output.lower()


class TestCliReprocess:
    """Tests for the 'pdf-pipeline reprocess' CLI command."""

    def test_正常系_reprocessコマンドが指定ハッシュを再処理できる(
        self, tmp_path: Path
    ) -> None:
        """CLI: 'reprocess' resets status and re-runs the pipeline for a hash."""
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True)
        pdf_dir = tmp_path / "pdfs"
        pdf_path = _create_sample_pdf(pdf_dir)
        source_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()

        # Pre-set state to "failed"
        state_manager = StateManager(output_dir / "state.json")
        state_manager.record_status(source_hash, "failed")
        state_manager.save()

        runner = CliRunner()
        with (
            patch("pdf_pipeline.cli.main.load_config") as mock_load_config,
            patch("pdf_pipeline.cli.main._build_pipeline_for_dir") as mock_build,
        ):
            mock_config = MagicMock()
            mock_config.input_dirs = [pdf_dir]
            mock_load_config.return_value = mock_config

            mock_pipeline = MagicMock()
            mock_pipeline.process_pdf.return_value = {
                "status": "completed",
                "source_hash": source_hash,
                "chunk_count": 3,
            }
            mock_build.return_value = mock_pipeline

            # Also mock the scanner used in reprocess
            with patch("pdf_pipeline.cli.main.PdfScanner") as mock_scanner_class:
                mock_scanner = MagicMock()
                mock_scanner.scan_with_hashes.return_value = [(pdf_path, source_hash)]
                mock_scanner_class.return_value = mock_scanner

                result = runner.invoke(
                    cli,
                    [
                        "--output-dir",
                        str(output_dir),
                        "--config",
                        str(tmp_path / "config.yaml"),
                        "reprocess",
                        "--hash",
                        source_hash,
                    ],
                )

        assert result.exit_code == 0, f"CLI failed: {result.output}"

    def test_異常系_存在しないハッシュでエラー終了する(self, tmp_path: Path) -> None:
        """CLI: 'reprocess' exits non-zero for an unknown hash."""
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True)

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--output-dir",
                str(output_dir),
                "--config",
                str(tmp_path / "config.yaml"),
                "reprocess",
                "--hash",
                "unknown_hash_that_does_not_exist",
            ],
        )

        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Ground Truth Tests
# ---------------------------------------------------------------------------


class TestGroundTruth:
    """Tests validating the ground_truth.json data structure."""

    @pytest.fixture()
    def ground_truth(self) -> dict[str, Any]:
        """Load and return the ground truth JSON document.

        Returns
        -------
        dict[str, Any]
            Parsed ground truth document.

        Raises
        ------
        pytest.skip.Exception
            If the ground truth file does not exist.
        """
        if not _SAMPLE_GROUND_TRUTH_PATH.exists():
            pytest.skip(f"Ground truth file not found: {_SAMPLE_GROUND_TRUTH_PATH}")
        return json.loads(_SAMPLE_GROUND_TRUTH_PATH.read_text(encoding="utf-8"))

    def test_正常系_groundTruthファイルが存在する(self) -> None:
        """Ground truth: file exists at expected path."""
        if not _SAMPLE_GROUND_TRUTH_PATH.exists():
            pytest.skip(f"Ground truth file not found: {_SAMPLE_GROUND_TRUTH_PATH}")
        assert _SAMPLE_GROUND_TRUTH_PATH.exists()

    def test_正常系_groundTruthにdocument_idがある(
        self, ground_truth: dict[str, Any]
    ) -> None:
        """Ground truth: document_id field is present and non-empty."""
        assert "document_id" in ground_truth
        assert ground_truth["document_id"]

    def test_正常系_groundTruthにkey_metricsがある(
        self, ground_truth: dict[str, Any]
    ) -> None:
        """Ground truth: key_metrics contains 5+ entries with required fields."""
        assert "key_metrics" in ground_truth
        metrics = ground_truth["key_metrics"]
        assert isinstance(metrics, list)
        assert len(metrics) >= 5, f"Expected at least 5 metrics, got {len(metrics)}"

        required_fields = {"metric_name", "value", "unit", "period"}
        for i, metric in enumerate(metrics):
            missing = required_fields - set(metric.keys())
            assert not missing, f"Metric {i} missing fields: {missing}"

    def test_正常系_groundTruthにsectionsがある(
        self, ground_truth: dict[str, Any]
    ) -> None:
        """Ground truth: sections list contains entries with required fields."""
        assert "sections" in ground_truth
        sections = ground_truth["sections"]
        assert isinstance(sections, list)
        assert len(sections) >= 1

        required_fields = {"section_id", "title", "page_start", "page_end"}
        for i, section in enumerate(sections):
            missing = required_fields - set(section.keys())
            assert not missing, f"Section {i} missing fields: {missing}"

    def test_正常系_groundTruthにnoise_phrasesがある(
        self, ground_truth: dict[str, Any]
    ) -> None:
        """Ground truth: noise_phrases is a non-empty list of strings."""
        assert "noise_phrases" in ground_truth
        phrases = ground_truth["noise_phrases"]
        assert isinstance(phrases, list)
        assert len(phrases) >= 1
        for phrase in phrases:
            assert isinstance(phrase, str)

    def test_正常系_groundTruthのschema_versionが正しい(
        self, ground_truth: dict[str, Any]
    ) -> None:
        """Ground truth: schema_version is present."""
        assert "schema_version" in ground_truth

    def test_正常系_groundTruthにHSBCデータが含まれる(
        self, ground_truth: dict[str, Any]
    ) -> None:
        """Ground truth: document relates to HSBC ISAT 3Q25 source data."""
        doc_id = ground_truth.get("document_id", "")
        title = ground_truth.get("title", "")
        publisher = ground_truth.get("publisher", "")

        # At least one identifier should reference HSBC
        assert any("hsbc" in field.lower() for field in [doc_id, title, publisher]), (
            "Ground truth should reference HSBC data"
        )
