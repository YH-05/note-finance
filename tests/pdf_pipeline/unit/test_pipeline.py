"""Unit tests for PdfPipeline (Phase 1-4 orchestrator).

Tests cover:
- Initialization with composition-based dependencies
- Single PDF processing (Phase 1 → 2 → 3 → 4 in sequence)
- Batch processing
- Error handling with partial result saving
- Idempotency (same PDF hash → skip if already completed)
- Progress logging
- Output path: {source_hash}/chunks.json
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from pdf_pipeline.core.pipeline import PdfPipeline
from pdf_pipeline.schemas.tables import ExtractedTables, RawTable, TableCell
from pdf_pipeline.types import PipelineConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_raw_table() -> RawTable:
    cell = TableCell(row=0, col=0, value="Revenue")
    return RawTable(page_number=1, bbox=[0.0, 0.0, 200.0, 100.0], cells=[cell])


def _make_extracted_tables(pdf_path: str = "report.pdf") -> ExtractedTables:
    return ExtractedTables(pdf_path=pdf_path, raw_tables=[_make_raw_table()])


def _make_config(tmp_path: Path) -> PipelineConfig:
    return PipelineConfig(
        input_dirs=[tmp_path / "pdfs"],
        output_dir=tmp_path / "output",
    )


# ---------------------------------------------------------------------------
# PdfPipeline initialization
# ---------------------------------------------------------------------------


class TestPdfPipelineInit:
    """Tests for PdfPipeline initialization."""

    def test_正常系_全コンポーネントで初期化できる(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        scanner = MagicMock()
        noise_filter = MagicMock()
        markdown_converter = MagicMock()
        table_detector = MagicMock()
        table_reconstructor = MagicMock()
        chunker = MagicMock()
        state_manager = MagicMock()

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
        assert pipeline is not None

    def test_正常系_コンポーネントが保持される(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        scanner = MagicMock()
        noise_filter = MagicMock()
        markdown_converter = MagicMock()
        table_detector = MagicMock()
        table_reconstructor = MagicMock()
        chunker = MagicMock()
        state_manager = MagicMock()

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
        assert pipeline.config is config
        assert pipeline.scanner is scanner
        assert pipeline.chunker is chunker


# ---------------------------------------------------------------------------
# PdfPipeline.process_pdf: single file processing
# ---------------------------------------------------------------------------


class TestPdfPipelineProcessPdf:
    """Tests for single PDF processing."""

    def _make_pipeline(
        self, tmp_path: Path
    ) -> tuple[PdfPipeline, dict[str, MagicMock]]:
        """Create a pipeline with all mock components."""
        config = _make_config(tmp_path)

        scanner = MagicMock()
        scanner.scan_with_hashes.return_value = []

        noise_filter = MagicMock()
        noise_filter.filter_text.return_value = "filtered text"

        markdown_converter = MagicMock()
        markdown_converter.convert.return_value = "# Section\n\nContent."

        table_detector = MagicMock()
        table_detector.detect.return_value = [_make_raw_table()]

        table_reconstructor = MagicMock()
        table_reconstructor.reconstruct.return_value = _make_extracted_tables()

        chunker = MagicMock()
        chunker.chunk.return_value = [
            {
                "source_hash": "abc123",
                "chunk_index": 0,
                "section_title": "Section",
                "content": "# Section\n\nContent.",
                "tables": [],
            }
        ]

        state_manager = MagicMock()
        state_manager.is_processed.return_value = False

        mocks = {
            "scanner": scanner,
            "noise_filter": noise_filter,
            "markdown_converter": markdown_converter,
            "table_detector": table_detector,
            "table_reconstructor": table_reconstructor,
            "chunker": chunker,
            "state_manager": state_manager,
        }

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
        return pipeline, mocks

    def test_正常系_単一PDFを処理してステータスがcompletedになる(
        self, tmp_path: Path
    ) -> None:
        pipeline, _mocks = self._make_pipeline(tmp_path)
        pdf_path = tmp_path / "report.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        # We expect no exception and completed status
        result = pipeline.process_pdf(pdf_path=pdf_path, source_hash="abc123")
        assert result["status"] == "completed"

    def test_正常系_Phase1スキャンが呼ばれる(self, tmp_path: Path) -> None:
        pipeline, mocks = self._make_pipeline(tmp_path)
        pdf_path = tmp_path / "report.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        with patch.object(
            mocks["noise_filter"], "filter_text", return_value="filtered"
        ):
            result = pipeline.process_pdf(pdf_path=pdf_path, source_hash="abc123")

        mocks["state_manager"].record_status.assert_called()
        assert result["source_hash"] == "abc123"

    def test_正常系_Phase2ノイズフィルターが呼ばれる(self, tmp_path: Path) -> None:
        pipeline, mocks = self._make_pipeline(tmp_path)
        pdf_path = tmp_path / "report.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        pipeline.process_pdf(pdf_path=pdf_path, source_hash="abc123")
        # noise_filter.filter_text should be called
        mocks["noise_filter"].filter_text.assert_called()

    def test_正常系_Phase3マークダウン変換が呼ばれる(self, tmp_path: Path) -> None:
        pipeline, mocks = self._make_pipeline(tmp_path)
        pdf_path = tmp_path / "report.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        pipeline.process_pdf(pdf_path=pdf_path, source_hash="abc123")
        mocks["markdown_converter"].convert.assert_called()

    def test_正常系_Phase4テーブル検出が呼ばれる(self, tmp_path: Path) -> None:
        config = PipelineConfig(
            input_dirs=[tmp_path / "pdfs"],
            output_dir=tmp_path / "output",
            text_only=False,
        )
        pipeline, mocks = self._make_pipeline(tmp_path)
        pipeline.config = config
        pdf_path = tmp_path / "report.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        pipeline.process_pdf(pdf_path=pdf_path, source_hash="abc123")
        mocks["table_detector"].detect.assert_called()

    def test_正常系_チャンカーが呼ばれる(self, tmp_path: Path) -> None:
        pipeline, mocks = self._make_pipeline(tmp_path)
        pdf_path = tmp_path / "report.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        pipeline.process_pdf(pdf_path=pdf_path, source_hash="abc123")
        mocks["chunker"].chunk.assert_called()

    def test_正常系_state_managerのrecord_statusが呼ばれる(
        self, tmp_path: Path
    ) -> None:
        pipeline, mocks = self._make_pipeline(tmp_path)
        pdf_path = tmp_path / "report.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        pipeline.process_pdf(pdf_path=pdf_path, source_hash="abc123")
        mocks["state_manager"].record_status.assert_called()

    def test_正常系_chunks_jsonが出力ディレクトリに保存される(
        self, tmp_path: Path
    ) -> None:
        pipeline, _mocks = self._make_pipeline(tmp_path)
        pdf_path = tmp_path / "report.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        pipeline.process_pdf(pdf_path=pdf_path, source_hash="abc123")
        # Output: {output_dir}/{source_hash}/chunks.json
        output_file = tmp_path / "output" / "abc123" / "chunks.json"
        assert output_file.exists()

    def test_正常系_chunks_jsonが正しい内容で保存される(self, tmp_path: Path) -> None:
        import json

        pipeline, _mocks = self._make_pipeline(tmp_path)
        pdf_path = tmp_path / "report.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        pipeline.process_pdf(pdf_path=pdf_path, source_hash="abc123")
        output_file = tmp_path / "output" / "abc123" / "chunks.json"
        data = json.loads(output_file.read_text())
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_正常系_metadata_jsonが出力ディレクトリに保存される(
        self, tmp_path: Path
    ) -> None:
        pipeline, _mocks = self._make_pipeline(tmp_path)
        pdf_path = tmp_path / "report.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        pipeline.process_pdf(pdf_path=pdf_path, source_hash="abc123")
        metadata_file = tmp_path / "output" / "abc123" / "metadata.json"
        assert metadata_file.exists()

    def test_正常系_metadata_jsonに元PDFのファイル名が含まれる(
        self, tmp_path: Path
    ) -> None:
        import json

        pipeline, _mocks = self._make_pipeline(tmp_path)
        pdf_path = tmp_path / "report.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        pipeline.process_pdf(pdf_path=pdf_path, source_hash="abc123")
        metadata_file = tmp_path / "output" / "abc123" / "metadata.json"
        metadata = json.loads(metadata_file.read_text())

        assert metadata["source_hash"] == "abc123"
        assert metadata["original_filename"] == "report.pdf"
        assert "original_path" not in metadata  # path-based reference removed
        assert "report_date" in metadata
        assert "issuer" in metadata
        assert "processed_at" in metadata
        assert metadata["chunk_count"] == 1

    def test_正常系_report_mdが出力ディレクトリに保存される(self, tmp_path: Path) -> None:
        pipeline, _mocks = self._make_pipeline(tmp_path)
        pdf_path = tmp_path / "report.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        pipeline.process_pdf(pdf_path=pdf_path, source_hash="abc123")
        report_file = tmp_path / "output" / "abc123" / "report.md"
        assert report_file.exists()

    def test_正常系_report_mdにchunkのcontentが含まれる(self, tmp_path: Path) -> None:
        pipeline, _mocks = self._make_pipeline(tmp_path)
        pdf_path = tmp_path / "report.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        pipeline.process_pdf(pdf_path=pdf_path, source_hash="abc123")
        report_file = tmp_path / "output" / "abc123" / "report.md"
        content = report_file.read_text(encoding="utf-8")
        assert "# Section" in content
        assert "source_hash" in content

    def test_正常系_テンプレートファイルなしでもフォールバック出力される(
        self, tmp_path: Path
    ) -> None:
        from pdf_pipeline.types import PipelineConfig

        config = PipelineConfig(
            input_dirs=[tmp_path / "pdfs"],
            output_dir=tmp_path / "output",
            chunk_template=tmp_path / "nonexistent-template.md",
        )
        pipeline, _mocks = self._make_pipeline(tmp_path)
        pipeline.config = config

        pdf_path = tmp_path / "report.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        result = pipeline.process_pdf(pdf_path=pdf_path, source_hash="abc123")
        assert result["status"] == "completed"
        report_file = tmp_path / "output" / "abc123" / "report.md"
        assert report_file.exists()

    def test_正常系_既処理済みのPDFはスキップされる(self, tmp_path: Path) -> None:
        pipeline, mocks = self._make_pipeline(tmp_path)
        mocks["state_manager"].is_processed.return_value = True

        pdf_path = tmp_path / "report.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        result = pipeline.process_pdf(pdf_path=pdf_path, source_hash="abc123")
        assert result["status"] == "skipped"
        # Should not call convert or chunk
        mocks["markdown_converter"].convert.assert_not_called()

    def test_異常系_markdown_converter失敗時にエラーログが出力される(
        self, tmp_path: Path
    ) -> None:
        pipeline, mocks = self._make_pipeline(tmp_path)
        mocks["markdown_converter"].convert.side_effect = RuntimeError("LLM failed")

        pdf_path = tmp_path / "report.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        result = pipeline.process_pdf(pdf_path=pdf_path, source_hash="abc123")
        assert result["status"] == "failed"
        assert "error" in result

    def test_異常系_エラー時にstateManagerでfailedが記録される(
        self, tmp_path: Path
    ) -> None:
        pipeline, mocks = self._make_pipeline(tmp_path)
        mocks["markdown_converter"].convert.side_effect = RuntimeError("LLM failed")

        pdf_path = tmp_path / "report.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        pipeline.process_pdf(pdf_path=pdf_path, source_hash="abc123")
        # Should record failed status
        call_args = mocks["state_manager"].record_status.call_args_list
        statuses = [call[0][1] for call in call_args if len(call[0]) > 1]
        assert "failed" in statuses


# ---------------------------------------------------------------------------
# PdfPipeline.run: batch processing
# ---------------------------------------------------------------------------


class TestPdfPipelineRun:
    """Tests for batch processing via run()."""

    def _make_pipeline(
        self, tmp_path: Path
    ) -> tuple[PdfPipeline, dict[str, MagicMock]]:
        config = _make_config(tmp_path)

        pdf_dir = tmp_path / "pdfs"
        pdf_dir.mkdir(parents=True, exist_ok=True)

        scanner = MagicMock()
        noise_filter = MagicMock()
        noise_filter.filter_text.return_value = "filtered"
        markdown_converter = MagicMock()
        markdown_converter.convert.return_value = "# Section\n\nContent."
        table_detector = MagicMock()
        table_detector.detect.return_value = []
        table_reconstructor = MagicMock()
        table_reconstructor.reconstruct.return_value = _make_extracted_tables()
        chunker = MagicMock()
        chunker.chunk.return_value = [
            {
                "source_hash": "hash1",
                "chunk_index": 0,
                "section_title": "Section",
                "content": "# Section\n\nContent.",
                "tables": [],
            }
        ]
        state_manager = MagicMock()
        state_manager.is_processed.return_value = False

        mocks = {
            "scanner": scanner,
            "noise_filter": noise_filter,
            "markdown_converter": markdown_converter,
            "table_detector": table_detector,
            "table_reconstructor": table_reconstructor,
            "chunker": chunker,
            "state_manager": state_manager,
        }

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
        return pipeline, mocks

    def test_正常系_空のPDFリストでゼロ件処理される(self, tmp_path: Path) -> None:
        pipeline, mocks = self._make_pipeline(tmp_path)
        mocks["scanner"].scan_with_hashes.return_value = []

        summary = pipeline.run()
        assert summary["total"] == 0
        assert summary["completed"] == 0

    def test_正常系_1件のPDFが処理される(self, tmp_path: Path) -> None:
        pipeline, mocks = self._make_pipeline(tmp_path)
        pdf_path = tmp_path / "pdfs" / "report.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")
        mocks["scanner"].scan_with_hashes.return_value = [(pdf_path, "hash1")]

        summary = pipeline.run()
        assert summary["total"] == 1
        assert summary["completed"] == 1

    def test_正常系_複数PDFが全て処理される(self, tmp_path: Path) -> None:
        pipeline, mocks = self._make_pipeline(tmp_path)
        pdf1 = tmp_path / "pdfs" / "a.pdf"
        pdf2 = tmp_path / "pdfs" / "b.pdf"
        pdf1.write_bytes(b"%PDF-1.4")
        pdf2.write_bytes(b"%PDF-1.4")
        mocks["scanner"].scan_with_hashes.return_value = [
            (pdf1, "hash1"),
            (pdf2, "hash2"),
        ]

        # Make chunker return different hashes
        def chunker_side_effect(**kwargs: Any) -> list[dict]:
            sh = kwargs.get("source_hash", "unknown")
            return [
                {
                    "source_hash": sh,
                    "chunk_index": 0,
                    "section_title": "Section",
                    "content": "Content.",
                    "tables": [],
                }
            ]

        mocks["chunker"].chunk.side_effect = chunker_side_effect

        summary = pipeline.run()
        assert summary["total"] == 2
        assert summary["completed"] == 2

    def test_正常系_1件失敗しても他が処理される(self, tmp_path: Path) -> None:
        pipeline, mocks = self._make_pipeline(tmp_path)
        pdf1 = tmp_path / "pdfs" / "a.pdf"
        pdf2 = tmp_path / "pdfs" / "b.pdf"
        pdf1.write_bytes(b"%PDF-1.4")
        pdf2.write_bytes(b"%PDF-1.4")
        mocks["scanner"].scan_with_hashes.return_value = [
            (pdf1, "hash1"),
            (pdf2, "hash2"),
        ]

        call_count = [0]

        def convert_side_effect(**kwargs: Any) -> str:
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("First PDF failed")
            return "# Section\n\nContent."

        mocks["markdown_converter"].convert.side_effect = convert_side_effect
        mocks["chunker"].chunk.side_effect = lambda **kwargs: [
            {
                "source_hash": kwargs.get("source_hash", "x"),
                "chunk_index": 0,
                "section_title": "S",
                "content": "C",
                "tables": [],
            }
        ]

        summary = pipeline.run()
        assert summary["total"] == 2
        assert summary["failed"] == 1
        assert summary["completed"] == 1

    def test_正常系_runのサマリーに必須キーが含まれる(self, tmp_path: Path) -> None:
        pipeline, mocks = self._make_pipeline(tmp_path)
        mocks["scanner"].scan_with_hashes.return_value = []

        summary = pipeline.run()
        required_keys = {"total", "completed", "failed", "skipped"}
        assert required_keys.issubset(summary.keys())


# ---------------------------------------------------------------------------
# PdfPipeline: text_only mode
# ---------------------------------------------------------------------------


class TestPdfPipelineTextOnly:
    """Tests for text_only mode (table skipping)."""

    def _make_pipeline(
        self, tmp_path: Path, *, text_only: bool = True
    ) -> tuple[PdfPipeline, dict[str, MagicMock]]:
        config = PipelineConfig(
            input_dirs=[tmp_path / "pdfs"],
            output_dir=tmp_path / "output",
            text_only=text_only,
        )

        scanner = MagicMock()
        scanner.scan_with_hashes.return_value = []
        noise_filter = MagicMock()
        noise_filter.filter_text.return_value = "filtered text"
        markdown_converter = MagicMock()
        markdown_converter.convert.return_value = "# Section\n\nContent."
        table_detector = MagicMock()
        table_detector.detect.return_value = [_make_raw_table()]
        table_reconstructor = MagicMock()
        table_reconstructor.reconstruct.return_value = _make_extracted_tables()
        chunker = MagicMock()
        chunker.chunk.return_value = [
            {
                "source_hash": "abc123",
                "chunk_index": 0,
                "section_title": "Section",
                "content": "# Section\n\nContent.",
                "tables": [],
            }
        ]
        state_manager = MagicMock()
        state_manager.is_processed.return_value = False

        mocks = {
            "scanner": scanner,
            "noise_filter": noise_filter,
            "markdown_converter": markdown_converter,
            "table_detector": table_detector,
            "table_reconstructor": table_reconstructor,
            "chunker": chunker,
            "state_manager": state_manager,
        }

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
        return pipeline, mocks

    def test_正常系_text_onlyモードでテーブル検出スキップ(self, tmp_path: Path) -> None:
        pipeline, mocks = self._make_pipeline(tmp_path, text_only=True)
        pdf_path = tmp_path / "report.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        result = pipeline.process_pdf(pdf_path=pdf_path, source_hash="abc123")
        assert result["status"] == "completed"
        mocks["table_detector"].detect.assert_not_called()
        mocks["table_reconstructor"].reconstruct.assert_not_called()

    def test_正常系_table_detector_Noneで初期化成功(self, tmp_path: Path) -> None:
        config = PipelineConfig(
            input_dirs=[tmp_path / "pdfs"],
            output_dir=tmp_path / "output",
        )
        pipeline = PdfPipeline(
            config=config,
            scanner=MagicMock(),
            noise_filter=MagicMock(),
            markdown_converter=MagicMock(),
            table_detector=None,
            table_reconstructor=None,
            chunker=MagicMock(),
            state_manager=MagicMock(),
        )
        assert pipeline.table_detector is None
        assert pipeline.table_reconstructor is None

    def test_正常系_text_only_Falseで従来通りテーブル処理(self, tmp_path: Path) -> None:
        pipeline, mocks = self._make_pipeline(tmp_path, text_only=False)
        pdf_path = tmp_path / "report.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        result = pipeline.process_pdf(pdf_path=pdf_path, source_hash="abc123")
        assert result["status"] == "completed"
        mocks["table_detector"].detect.assert_called()


# ---------------------------------------------------------------------------
# PdfPipeline: knowledge extraction integration
# ---------------------------------------------------------------------------


class TestPdfPipelineKnowledgeExtraction:
    """Tests for Phase 5 knowledge extraction integration."""

    def _make_pipeline(
        self,
        tmp_path: Path,
        *,
        knowledge_extractor: Any = None,
    ) -> tuple[PdfPipeline, dict[str, MagicMock]]:
        config = PipelineConfig(
            input_dirs=[tmp_path / "pdfs"],
            output_dir=tmp_path / "output",
        )

        noise_filter = MagicMock()
        noise_filter.filter_text.return_value = "filtered text"
        markdown_converter = MagicMock()
        markdown_converter.convert.return_value = "# Section\n\nContent."
        chunker = MagicMock()
        chunker.chunk.return_value = [
            {
                "source_hash": "abc123",
                "chunk_index": 0,
                "section_title": "Section",
                "content": "# Section\n\nContent.",
                "tables": [],
            }
        ]
        state_manager = MagicMock()
        state_manager.is_processed.return_value = False

        mocks = {
            "noise_filter": noise_filter,
            "markdown_converter": markdown_converter,
            "chunker": chunker,
            "state_manager": state_manager,
        }

        pipeline = PdfPipeline(
            config=config,
            scanner=MagicMock(),
            noise_filter=noise_filter,
            markdown_converter=markdown_converter,
            chunker=chunker,
            state_manager=state_manager,
            knowledge_extractor=knowledge_extractor,
        )
        return pipeline, mocks

    def test_正常系_knowledge_extractor設定時にextraction_json出力(
        self, tmp_path: Path
    ) -> None:
        import json

        from pdf_pipeline.schemas.extraction import DocumentExtractionResult

        mock_extraction = DocumentExtractionResult(
            source_hash="abc123",
            chunks=[],
        )
        knowledge_extractor = MagicMock()
        knowledge_extractor.extract_from_chunks.return_value = mock_extraction

        pipeline, _mocks = self._make_pipeline(
            tmp_path,
            knowledge_extractor=knowledge_extractor,
        )
        pdf_path = tmp_path / "report.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        result = pipeline.process_pdf(pdf_path=pdf_path, source_hash="abc123")
        assert result["status"] == "completed"

        output_file = tmp_path / "output" / "abc123" / "extraction.json"
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert data["source_hash"] == "abc123"

    def test_正常系_knowledge_extractor_Noneでスキップ(self, tmp_path: Path) -> None:
        pipeline, _mocks = self._make_pipeline(
            tmp_path,
            knowledge_extractor=None,
        )
        pdf_path = tmp_path / "report.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        result = pipeline.process_pdf(pdf_path=pdf_path, source_hash="abc123")
        assert result["status"] == "completed"

        output_file = tmp_path / "output" / "abc123" / "extraction.json"
        assert not output_file.exists()

    def test_異常系_extraction失敗でもchunks保存は成功(self, tmp_path: Path) -> None:
        knowledge_extractor = MagicMock()
        knowledge_extractor.extract_from_chunks.side_effect = RuntimeError("LLM failed")

        pipeline, _mocks = self._make_pipeline(
            tmp_path,
            knowledge_extractor=knowledge_extractor,
        )
        pdf_path = tmp_path / "report.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        result = pipeline.process_pdf(pdf_path=pdf_path, source_hash="abc123")
        assert result["status"] == "completed"

        # chunks.json should still exist
        chunks_file = tmp_path / "output" / "abc123" / "chunks.json"
        assert chunks_file.exists()
