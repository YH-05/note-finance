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
from datetime import datetime, timezone
from string import Template
from typing import TYPE_CHECKING, Any

from pdf_pipeline._logging import get_logger

if TYPE_CHECKING:
    from pathlib import Path

    from pdf_pipeline.core.chunker import MarkdownChunker
    from pdf_pipeline.core.knowledge_extractor import KnowledgeExtractor
    from pdf_pipeline.core.markdown_converter import MarkdownConverter
    from pdf_pipeline.core.noise_filter import NoiseFilter
    from pdf_pipeline.core.pdf_scanner import PdfScanner
    from pdf_pipeline.core.table_detector import TableDetector
    from pdf_pipeline.core.table_reconstructor import TableReconstructor
    from pdf_pipeline.core.text_extractor import TextExtractor
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
    table_detector : TableDetector | None
        Phase 4a component for table region detection.
        ``None`` when ``text_only=True``.
    table_reconstructor : TableReconstructor | None
        Phase 4b component for table structure reconstruction.
        ``None`` when ``text_only=True``.
    chunker : MarkdownChunker
        Phase 5 component for Markdown section chunking.
    state_manager : StateManager
        State persistence component for idempotency tracking.
    text_extractor : TextExtractor | None
        Component for raw text extraction from PDFs (DIP boundary).
        When ``None`` (default), a :class:`~pdf_pipeline.core.text_extractor.FitzTextExtractor`
        is created automatically.

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
        table_detector: TableDetector | None = None,
        table_reconstructor: TableReconstructor | None = None,
        chunker: MarkdownChunker,
        state_manager: StateManager,
        text_extractor: TextExtractor | None = None,
        knowledge_extractor: KnowledgeExtractor | None = None,
    ) -> None:
        self.config = config
        self.scanner = scanner
        self.noise_filter = noise_filter
        self.markdown_converter = markdown_converter
        self.table_detector = table_detector
        self.table_reconstructor = table_reconstructor
        self.chunker = chunker
        self.state_manager = state_manager
        self.knowledge_extractor = knowledge_extractor

        if text_extractor is None:
            from pdf_pipeline.core.text_extractor import (
                FitzTextExtractor,
            )

            self.text_extractor: TextExtractor = FitzTextExtractor()
        else:
            self.text_extractor = text_extractor

        # Ensure the output directory exists
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        logger.debug(
            "PdfPipeline initialized",
            output_dir=str(self.config.output_dir),
            text_only=self.config.text_only,
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

        # Record start — store filename immediately for provenance even on failure
        self.state_manager.record_status(
            source_hash, "processing", filename=pdf_path.name,
        )

        try:
            # -- Phase 2: Extract raw text + noise filter --------------------
            # Use extract_with_doc when available to avoid opening the PDF
            # twice (once for text extraction, once for table detection).
            from pdf_pipeline.core.text_extractor import (
                FitzTextExtractor,
            )

            fitz_doc = None
            if isinstance(self.text_extractor, FitzTextExtractor):
                raw_text, fitz_doc = self.text_extractor.extract_with_doc(pdf_path)
            else:
                raw_text = self.text_extractor.extract(pdf_path)

            filtered_text = self.noise_filter.filter_text(raw_text)

            # -- Phase 3: PDF → Markdown conversion --------------------------
            markdown = self.markdown_converter.convert(
                pdf_path=pdf_path,
                filtered_text=filtered_text,
            )

            # -- Phase 4: Table detection/reconstruction (skip in text_only) --
            reconstructed_tables = self._run_table_phase(
                pdf_path=pdf_path, fitz_doc=fitz_doc,
            )
            fitz_doc = None  # ownership transferred to _run_table_phase

            # -- Chunk -------------------------------------------------------
            chunks = self.chunker.chunk(
                markdown=markdown,
                source_hash=source_hash,
                raw_tables=reconstructed_tables,
            )

            # -- Save output -------------------------------------------------
            self._save_chunks(source_hash=source_hash, chunks=chunks, pdf_path=pdf_path)

            # -- Phase 5: Knowledge extraction (optional) --------------------
            if self.knowledge_extractor is not None:
                try:
                    extraction = self.knowledge_extractor.extract_from_chunks(
                        chunks=chunks,
                        source_hash=source_hash,
                    )
                    self._save_extraction(
                        source_hash=source_hash,
                        extraction=extraction,
                    )
                except Exception as ke_exc:
                    logger.warning(
                        "Knowledge extraction failed, chunks still saved",
                        error=str(ke_exc),
                        source_hash=source_hash,
                    )

            # -- Record completed state --------------------------------------
            self.state_manager.record_status(
                source_hash,
                "completed",
                filename=pdf_path.name,
                processed_at=datetime.now(tz=timezone.utc).isoformat(),
            )
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

            # Ensure any open fitz.Document is closed on error
            if fitz_doc is not None:  # type: ignore[possibly-undefined]
                with contextlib.suppress(Exception):
                    fitz_doc.close()

            self.state_manager.record_status(
                source_hash, "failed", filename=pdf_path.name,
            )
            with contextlib.suppress(Exception):
                self.state_manager.save()

            return {
                "status": "failed",
                "source_hash": source_hash,
                "error": error_msg,
            }

    # -- Internal helpers ----------------------------------------------------

    def _run_table_phase(
        self, *, pdf_path: Path, fitz_doc: Any,
    ) -> list[Any]:
        """Run Phase 4 (table detection + reconstruction) or skip in text_only mode.

        Parameters
        ----------
        pdf_path : Path
            Path to the PDF file.
        fitz_doc : Any
            Open fitz.Document (or None). Closed by this method.

        Returns
        -------
        list[Any]
            Reconstructed tables (empty list when text_only or no tables).
        """
        if not self.config.text_only and self.table_detector is not None:
            raw_tables = self.table_detector.detect(str(pdf_path), doc=fitz_doc)
            if fitz_doc is not None:
                with contextlib.suppress(Exception):
                    fitz_doc.close()

            if raw_tables and self.table_reconstructor is not None:
                try:
                    extracted = self.table_reconstructor.reconstruct(
                        pdf_path=str(pdf_path), raw_tables=raw_tables,
                    )
                    return extracted.raw_tables
                except Exception as table_exc:
                    logger.warning(
                        "Table reconstruction failed, continuing with raw tables",
                        error=str(table_exc),
                        pdf_path=str(pdf_path),
                        table_count=len(raw_tables),
                    )
                    return raw_tables
            return raw_tables if raw_tables else []

        if fitz_doc is not None:
            with contextlib.suppress(Exception):
                fitz_doc.close()
        return []

    def _render_markdown(
        self,
        *,
        metadata: dict[str, Any],
        chunks: list[dict[str, Any]],
    ) -> str:
        """Render chunks to Markdown using the template at ``config.chunk_template``.

        The template uses ``$placeholder`` syntax (``string.Template``).
        Available variables: all keys from ``metadata`` plus ``chunks_content``
        (chunk ``content`` fields joined by ``\\n\\n``).

        Falls back to a minimal inline template if the template file is missing.

        Parameters
        ----------
        metadata : dict[str, Any]
            Provenance metadata dict (source_hash, issuer, report_date, …).
        chunks : list[dict[str, Any]]
            Serialized chunk dicts; each must have a ``content`` key.

        Returns
        -------
        str
            Rendered Markdown string ready to write to ``report.md``.
        """
        chunks_content = "\n\n".join(c.get("content", "") for c in chunks)
        context = {**metadata, "chunks_content": chunks_content}
        # None → empty string so $placeholder renders cleanly
        context = {k: ("" if v is None else v) for k, v in context.items()}

        template_path = self.config.chunk_template
        try:
            template_text = template_path.read_text(encoding="utf-8")
        except OSError:
            logger.warning(
                "chunk_template not found, using inline fallback",
                template_path=str(template_path),
            )
            template_text = (
                "---\n"
                "source_hash: $source_hash\n"
                "original_filename: $original_filename\n"
                "report_date: $report_date\n"
                "issuer: $issuer\n"
                "processed_at: $processed_at\n"
                "chunk_count: $chunk_count\n"
                "---\n\n"
                "$chunks_content\n"
            )

        return Template(template_text).safe_substitute(context)

    def _extract_report_metadata(
        self,
        *,
        pdf_path: Path,
        chunks: list[dict[str, Any]],
    ) -> dict[str, str | None]:
        """Extract report_date and issuer from the PDF.

        ``report_date`` is read from the PDF ``creationDate`` metadata field via
        PyMuPDF (format ``D:YYYYMMDDHHmmSS…`` → ``YYYY-MM-DD``).

        ``issuer`` is resolved through a two-step LLM pipeline:

        1. **PDF Vision** (primary): calls
           :meth:`~pdf_pipeline.services.gemini_provider.GeminiCLIProvider.extract_issuer`
           on the underlying LLM provider if it supports the method.  Gemini reads
           the PDF cover page directly and returns the publishing organisation name.
        2. **Report body text** (fallback): if the Vision call returns ``None``
           (Gemini replied ``"unknown"`` or failed), the first chunk's content is
           sent to
           :meth:`~pdf_pipeline.services.gemini_provider.GeminiCLIProvider.extract_issuer_from_text`.
           This covers PDFs where the cover page is ambiguous but the header/body
           clearly identifies the issuer.

        No filename-based heuristics are used.

        Parameters
        ----------
        pdf_path : Path
            Path to the PDF file.
        chunks : list[dict[str, Any]]
            Chunks already produced by the pipeline (used as fallback text
            source).

        Returns
        -------
        dict[str, str | None]
            Dict with keys ``report_date`` (ISO date string or ``None``) and
            ``issuer`` (organisation name or ``None``).
        """
        # -- report_date: PyMuPDF creationDate field --------------------------
        report_date: str | None = None
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(str(pdf_path))
            raw_date = (doc.metadata.get("creationDate") or "").strip()
            doc.close()
            if raw_date.startswith("D:") and len(raw_date) >= 10:
                d = raw_date[2:]
                report_date = f"{d[0:4]}-{d[4:6]}-{d[6:8]}"
        except Exception:
            pass

        # -- issuer: LLM-based extraction -------------------------------------
        issuer: str | None = None

        # Collect provider instances that expose extract_issuer / extract_issuer_from_text
        llm_providers: list[Any] = []
        try:
            provider = self.markdown_converter.provider
            candidates = (
                provider.providers
                if isinstance(getattr(provider, "providers", None), list)
                else [provider]
            )
            llm_providers = [
                p
                for p in candidates
                if callable(getattr(p, "extract_issuer", None))
                and callable(getattr(p, "is_available", None))
                and p.is_available()
            ]
        except Exception:
            pass

        # Step 1: Vision — ask the LLM to read the PDF directly
        for p in llm_providers:
            try:
                result = p.extract_issuer(str(pdf_path))
                issuer = result if isinstance(result, str) and result else None
            except Exception:
                issuer = None
            if issuer:
                logger.info(
                    "Issuer resolved via PDF Vision",
                    issuer=issuer,
                    pdf_path=str(pdf_path),
                )
                break

        # Step 2: Text fallback — scan the first chunk's content
        if not issuer and chunks:
            first_text = (chunks[0].get("content") or "")[:2000]
            for p in llm_providers:
                if not callable(getattr(p, "extract_issuer_from_text", None)):
                    continue
                try:
                    result = p.extract_issuer_from_text(first_text)
                    issuer = result if isinstance(result, str) and result else None
                except Exception:
                    issuer = None
                if issuer:
                    logger.info(
                        "Issuer resolved via report body text",
                        issuer=issuer,
                        pdf_path=str(pdf_path),
                    )
                    break

        if not issuer:
            logger.warning(
                "Could not determine issuer",
                pdf_path=str(pdf_path),
            )

        return {"report_date": report_date, "issuer": issuer}

    def _save_chunks(
        self,
        *,
        source_hash: str,
        chunks: list[dict[str, Any]],
        pdf_path: Path,
    ) -> None:
        """Save chunks and provenance metadata to ``{output_dir}/{source_hash}/``.

        Writes two files:

        - ``chunks.json`` — list of section chunks (Markdown + tables).
        - ``metadata.json`` — provenance record linking the hash back to the
          original PDF filename, processing timestamp, report date, and issuer.
          ``original_path`` is intentionally omitted: the SHA-256 ``source_hash``
          is the stable content-based identifier regardless of file location.

        Parameters
        ----------
        source_hash : str
            SHA-256 hex digest used as the subdirectory name.
        chunks : list[dict[str, Any]]
            Chunk dicts to serialize.  ``RawTable`` objects in the
            ``tables`` key are excluded from serialization (not JSON
            serializable) and replaced with their cell text representation.
        pdf_path : Path
            Original PDF path; filename is stored in ``metadata.json``.
        """
        output_dir = self.config.output_dir / source_hash
        output_dir.mkdir(parents=True, exist_ok=True)

        report_meta = self._extract_report_metadata(pdf_path=pdf_path, chunks=chunks)

        # -- metadata.json: provenance record --------------------------------
        metadata: dict[str, Any] = {
            "source_hash": source_hash,
            "original_filename": pdf_path.name,
            "report_date": report_meta["report_date"],
            "issuer": report_meta["issuer"],
            "processed_at": datetime.now(tz=timezone.utc).isoformat(),
            "chunk_count": len(chunks),
        }
        (output_dir / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # -- chunks.json (machine-readable) ----------------------------------
        serializable_chunks = [self._serialize_chunk(chunk) for chunk in chunks]
        output_file = output_dir / "chunks.json"
        output_file.write_text(
            json.dumps(serializable_chunks, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # -- report.md (human-readable, rendered from template) --------------
        report_md = self._render_markdown(metadata=metadata, chunks=serializable_chunks)
        (output_dir / "report.md").write_text(report_md, encoding="utf-8")

        logger.debug(
            "Chunks, metadata and report.md saved",
            output_dir=str(output_dir),
            chunk_count=len(chunks),
            original_filename=pdf_path.name,
        )

    def _save_extraction(
        self,
        *,
        source_hash: str,
        extraction: Any,
    ) -> None:
        """Save extraction result to ``{output_dir}/{source_hash}/extraction.json``.

        Parameters
        ----------
        source_hash : str
            SHA-256 hex digest used as the subdirectory name.
        extraction : DocumentExtractionResult
            Knowledge extraction result to serialize.
        """
        output_dir = self.config.output_dir / source_hash
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "extraction.json"

        output_file.write_text(
            extraction.model_dump_json(indent=2),
            encoding="utf-8",
        )

        logger.debug(
            "Extraction saved",
            output_file=str(output_file),
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
