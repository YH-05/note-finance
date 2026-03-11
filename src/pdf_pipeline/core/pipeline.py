"""Phase 1-4 orchestration pipeline for the pdf_pipeline package.

Orchestrates the full PDF processing pipeline in sequence:
  Phase 1 (Scan)   → :class:`~pdf_pipeline.core.pdf_scanner.PdfScanner`
  Phase 2 (Filter) → :class:`~pdf_pipeline.core.noise_filter.NoiseFilter`
  Phase 3 (Convert)→ :class:`~pdf_pipeline.core.markdown_converter.MarkdownConverter`
  Phase 4 (Tables) → :class:`~pdf_pipeline.core.table_detector.TableDetector`
               and → :class:`~pdf_pipeline.core.table_reconstructor.TableReconstructor`
  Chunk            → :class:`~pdf_pipeline.core.chunker.MarkdownChunker`

Output is written to ``{output_dir}/{source_hash}/chunks.json``.
Processing state is tracked via :class:`~pdf_pipeline.services.state_manager.StateManager`
to provide idempotency across pipeline runs.

Classes
-------
PdfPipeline
    Composition-based Phase 1-4 pipeline orchestrator.

Examples
--------
>>> from unittest.mock import MagicMock
>>> from pdf_pipeline.types import PipelineConfig
>>> from pathlib import Path
>>> config = PipelineConfig(input_dirs=[Path("data/raw/pdfs")])
>>> pipeline = PdfPipeline(
...     config=config,
...     scanner=MagicMock(),
...     noise_filter=MagicMock(),
...     markdown_converter=MagicMock(),
...     table_detector=MagicMock(),
...     table_reconstructor=MagicMock(),
...     chunker=MagicMock(),
...     state_manager=MagicMock(),
... )
>>> isinstance(pipeline, PdfPipeline)
True
"""

from __future__ import annotations

import contextlib
import json
from typing import TYPE_CHECKING, Any

from pdf_pipeline._logging import get_logger

if TYPE_CHECKING:
    from pathlib import Path

    from pdf_pipeline.core.chunker import MarkdownChunker
    from pdf_pipeline.core.markdown_converter import MarkdownConverter
    from pdf_pipeline.core.noise_filter import NoiseFilter
    from pdf_pipeline.core.pdf_scanner import PdfScanner
    from pdf_pipeline.core.table_detector import TableDetector
    from pdf_pipeline.core.table_reconstructor import TableReconstructor
    from pdf_pipeline.services.state_manager import StateManager
    from pdf_pipeline.types import PipelineConfig

logger = get_logger(__name__, module="pipeline")

# ---------------------------------------------------------------------------
# PdfPipeline
# ---------------------------------------------------------------------------


class PdfPipeline:
    """Composition-based Phase 1-4 PDF processing pipeline.

    Orchestrates the following phases for each PDF:

    1. **Scan** (``PdfScanner.scan_with_hashes``): enumerate PDFs with SHA-256.
    2. **Filter** (``NoiseFilter.filter_text``): remove boilerplate from raw text.
    3. **Convert** (``MarkdownConverter.convert``): PDF → structured Markdown.
    4. **Tables** (``TableDetector.detect`` + ``TableReconstructor.reconstruct``):
       extract and classify table structures.
    5. **Chunk** (``MarkdownChunker.chunk``): split Markdown into section chunks.
    6. **Save**: write ``{output_dir}/{source_hash}/chunks.json``.

    State tracking via ``StateManager`` ensures idempotency: a PDF whose
    hash is already in ``completed`` state is skipped on subsequent runs.

    Parameters
    ----------
    config : PipelineConfig
        Top-level pipeline configuration.
    scanner : PdfScanner
        Phase 1 component for scanning PDF directories.
    noise_filter : NoiseFilter
        Phase 2 component for text noise removal.
    markdown_converter : MarkdownConverter
        Phase 3 component for PDF → Markdown conversion.
    table_detector : TableDetector
        Phase 4a component for table region detection.
    table_reconstructor : TableReconstructor
        Phase 4b component for table structure reconstruction.
    chunker : MarkdownChunker
        Phase 5 component for Markdown section chunking.
    state_manager : StateManager
        State persistence component for idempotency tracking.

    Examples
    --------
    >>> from unittest.mock import MagicMock
    >>> from pdf_pipeline.types import PipelineConfig
    >>> from pathlib import Path
    >>> config = PipelineConfig(input_dirs=[Path("data/raw/pdfs")])
    >>> pipeline = PdfPipeline(
    ...     config=config,
    ...     scanner=MagicMock(),
    ...     noise_filter=MagicMock(),
    ...     markdown_converter=MagicMock(),
    ...     table_detector=MagicMock(),
    ...     table_reconstructor=MagicMock(),
    ...     chunker=MagicMock(),
    ...     state_manager=MagicMock(),
    ... )
    >>> pipeline.config is config
    True
    """

    def __init__(
        self,
        *,
        config: PipelineConfig,
        scanner: PdfScanner,
        noise_filter: NoiseFilter,
        markdown_converter: MarkdownConverter,
        table_detector: TableDetector,
        table_reconstructor: TableReconstructor,
        chunker: MarkdownChunker,
        state_manager: StateManager,
    ) -> None:
        self.config = config
        self.scanner = scanner
        self.noise_filter = noise_filter
        self.markdown_converter = markdown_converter
        self.table_detector = table_detector
        self.table_reconstructor = table_reconstructor
        self.chunker = chunker
        self.state_manager = state_manager

        # Ensure the output directory exists
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        logger.debug(
            "PdfPipeline initialized",
            output_dir=str(self.config.output_dir),
        )

    # -- Public API ----------------------------------------------------------

    def run(self) -> dict[str, Any]:
        """Run the pipeline for all PDFs found by the scanner.

        Scans the configured input directories, processes each PDF in
        sequence, and returns a summary dict.

        Returns
        -------
        dict[str, Any]
            Summary with keys: ``total``, ``completed``, ``failed``,
            ``skipped``.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from pdf_pipeline.types import PipelineConfig
        >>> from pathlib import Path
        >>> config = PipelineConfig(input_dirs=[Path("data/raw/pdfs")])
        >>> pipeline = PdfPipeline(
        ...     config=config,
        ...     scanner=MagicMock(scan_with_hashes=MagicMock(return_value=[])),
        ...     noise_filter=MagicMock(),
        ...     markdown_converter=MagicMock(),
        ...     table_detector=MagicMock(),
        ...     table_reconstructor=MagicMock(),
        ...     chunker=MagicMock(),
        ...     state_manager=MagicMock(),
        ... )
        >>> summary = pipeline.run()
        >>> summary["total"]
        0
        """
        pdf_entries = self.scanner.scan_with_hashes()

        logger.info(
            "Pipeline run started",
            pdf_count=len(pdf_entries),
            output_dir=str(self.config.output_dir),
        )

        completed = 0
        failed = 0
        skipped = 0

        for pdf_path, source_hash in pdf_entries:
            result = self.process_pdf(pdf_path=pdf_path, source_hash=source_hash)
            status = result["status"]
            if status == "completed":
                completed += 1
            elif status == "failed":
                failed += 1
            elif status == "skipped":
                skipped += 1

        total = len(pdf_entries)
        summary: dict[str, Any] = {
            "total": total,
            "completed": completed,
            "failed": failed,
            "skipped": skipped,
        }

        logger.info(
            "Pipeline run completed",
            **summary,
        )

        return summary

    def process_pdf(
        self,
        *,
        pdf_path: Path,
        source_hash: str,
    ) -> dict[str, Any]:
        """Process a single PDF through all pipeline phases.

        Phases executed in order:
        1. Idempotency check via StateManager.
        2. Extract raw text from the PDF (using PyMuPDF).
        3. Apply NoiseFilter to the raw text.
        4. Convert PDF → Markdown via MarkdownConverter (Phase 3).
        5. Detect and reconstruct tables (Phase 4).
        6. Chunk the Markdown into section-level pieces.
        7. Save chunks to ``{output_dir}/{source_hash}/chunks.json``.

        Parameters
        ----------
        pdf_path : Path
            Path to the PDF file.
        source_hash : str
            SHA-256 hex digest of the PDF (used as output directory name).

        Returns
        -------
        dict[str, Any]
            Processing result with key ``status``:
            ``"completed"``, ``"skipped"``, or ``"failed"``.
            On failure, an ``"error"`` key contains the error message.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from pdf_pipeline.types import PipelineConfig
        >>> from pathlib import Path, tmp_path
        """
        # -- Idempotency check -----------------------------------------------
        if self.state_manager.is_processed(source_hash):
            logger.info(
                "PDF already processed, skipping",
                source_hash=source_hash,
                pdf_path=str(pdf_path),
            )
            return {"status": "skipped", "source_hash": source_hash}

        logger.info(
            "Processing PDF",
            source_hash=source_hash,
            pdf_path=str(pdf_path),
        )

        # Record start
        self.state_manager.record_status(source_hash, "processing")

        try:
            # -- Phase 2: Extract raw text + noise filter --------------------
            raw_text = self._extract_raw_text(pdf_path)
            filtered_text = self.noise_filter.filter_text(raw_text)

            # -- Phase 3: PDF → Markdown conversion --------------------------
            markdown = self.markdown_converter.convert(
                pdf_path=pdf_path,
                filtered_text=filtered_text,
            )

            # -- Phase 4a: Table detection -----------------------------------
            raw_tables = self.table_detector.detect(str(pdf_path))

            # -- Phase 4b: Table reconstruction (only if tables found) -------
            if raw_tables:
                extracted = self.table_reconstructor.reconstruct(
                    pdf_path=str(pdf_path),
                    raw_tables=raw_tables,
                )
                reconstructed_tables = extracted.raw_tables
            else:
                reconstructed_tables = []

            # -- Chunk -------------------------------------------------------
            chunks = self.chunker.chunk(
                markdown=markdown,
                source_hash=source_hash,
                raw_tables=reconstructed_tables,
            )

            # -- Save output -------------------------------------------------
            self._save_chunks(source_hash=source_hash, chunks=chunks)

            # -- Record completed state --------------------------------------
            self.state_manager.record_status(source_hash, "completed")
            self.state_manager.save()

            logger.info(
                "PDF processing completed",
                source_hash=source_hash,
                chunk_count=len(chunks),
            )

            return {
                "status": "completed",
                "source_hash": source_hash,
                "chunk_count": len(chunks),
            }

        except Exception as exc:
            error_msg = str(exc)
            logger.error(
                "PDF processing failed",
                source_hash=source_hash,
                pdf_path=str(pdf_path),
                error=error_msg,
                exc_info=True,
            )

            self.state_manager.record_status(source_hash, "failed")
            with contextlib.suppress(Exception):
                self.state_manager.save()

            return {
                "status": "failed",
                "source_hash": source_hash,
                "error": error_msg,
            }

    # -- Internal helpers ----------------------------------------------------

    def _extract_raw_text(self, pdf_path: Path) -> str:
        """Extract raw text from a PDF file using PyMuPDF.

        Parameters
        ----------
        pdf_path : Path
            Path to the PDF file.

        Returns
        -------
        str
            All text extracted from the PDF, pages joined by newlines.
        """
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(str(pdf_path))
            texts: list[str] = []
            for page in doc:
                texts.append(str(page.get_text()))
            doc.close()
            result = "\n".join(texts)
            logger.debug(
                "Raw text extracted",
                pdf_path=str(pdf_path),
                char_count=len(result),
            )
            return result
        except ImportError:
            logger.warning(
                "PyMuPDF not available, using empty text",
                pdf_path=str(pdf_path),
            )
            return ""
        except Exception as exc:
            logger.warning(
                "Failed to extract raw text",
                pdf_path=str(pdf_path),
                error=str(exc),
            )
            return ""

    def _save_chunks(self, *, source_hash: str, chunks: list[dict[str, Any]]) -> None:
        """Save chunks to ``{output_dir}/{source_hash}/chunks.json``.

        Parameters
        ----------
        source_hash : str
            SHA-256 hex digest used as the subdirectory name.
        chunks : list[dict[str, Any]]
            Chunk dicts to serialize.  ``RawTable`` objects in the
            ``tables`` key are excluded from serialization (not JSON
            serializable) and replaced with their cell text representation.
        """
        output_dir = self.config.output_dir / source_hash
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "chunks.json"

        # Serialize chunks: RawTable objects need custom handling
        serializable_chunks = [self._serialize_chunk(chunk) for chunk in chunks]

        output_file.write_text(
            json.dumps(serializable_chunks, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        logger.debug(
            "Chunks saved",
            output_file=str(output_file),
            chunk_count=len(chunks),
        )

    def _serialize_chunk(self, chunk: dict[str, Any]) -> dict[str, Any]:
        """Convert a chunk dict to a JSON-serializable form.

        Parameters
        ----------
        chunk : dict[str, Any]
            Chunk dict possibly containing ``RawTable`` objects.

        Returns
        -------
        dict[str, Any]
            Chunk with ``tables`` replaced by their serializable representation.
        """
        from pdf_pipeline.schemas.tables import RawTable

        serializable = dict(chunk)
        tables = serializable.get("tables", [])
        serialized_tables = []
        for table in tables:
            if isinstance(table, RawTable):
                serialized_tables.append(table.model_dump())
            else:
                serialized_tables.append(table)
        serializable["tables"] = serialized_tables
        return serializable
