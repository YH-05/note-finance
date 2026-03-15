"""Method B helper functions for the ``/convert-pdf`` skill.

Provides standalone CLI-callable helper functions for PDF processing
operations: SHA-256 hashing, idempotency checks, page counting,
output directory computation, Markdown chunking, metadata persistence,
and state recording.

Each function prints its result to stdout for consumption by the
orchestrating skill via ``uv run python -m pdf_pipeline.cli.helpers <func> <args>``.

Functions
---------
compute_hash
    Compute SHA-256 hex digest of a PDF file.
check_idempotency
    Check whether a SHA-256 hash has already been processed.
get_page_count
    Count pages in a PDF using PyMuPDF.
compute_output_dir
    Compute the mirror-path output directory for a PDF.
chunk_and_save
    Chunk a Markdown report and save as ``chunks.json``.
save_metadata
    Save processing metadata as ``metadata.json``.
record_completed
    Record a PDF as completed in the state file.

Examples
--------
CLI usage::

    $ uv run python -m pdf_pipeline.cli.helpers compute_hash /path/to/report.pdf
    a1b2c3d4e5f6...

    $ uv run python -m pdf_pipeline.cli.helpers check_idempotency <sha256> state.json
    false
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import fitz  # type: ignore[import-untyped]

from data_paths import get_path
from pdf_pipeline._logging import get_logger
from pdf_pipeline.core.chunker import MarkdownChunker
from pdf_pipeline.core.pdf_scanner import compute_sha256_standalone
from pdf_pipeline.services.state_manager import StateManager

logger = get_logger(__name__, module="cli.helpers")

# ---------------------------------------------------------------------------
# Dispatch table for CLI entry point
# ---------------------------------------------------------------------------

_DISPATCH: dict[str, object] = {}

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def compute_hash(pdf_path: str) -> str:
    """Compute the SHA-256 hex digest of a PDF file.

    Parameters
    ----------
    pdf_path : str
        Path to the PDF file.

    Returns
    -------
    str
        Lowercase 64-character SHA-256 hex digest.

    Raises
    ------
    ScanError
        If the file does not exist or cannot be read.

    Examples
    --------
    >>> result = compute_hash("/data/raw/pdfs/report.pdf")  # doctest: +SKIP
    >>> len(result)
    64
    """
    logger.debug("compute_hash called", pdf_path=pdf_path)
    digest = compute_sha256_standalone(pdf_path)
    logger.info("Hash computed", pdf_path=pdf_path, sha256=digest[:16] + "...")
    return digest


def check_idempotency(sha256: str, state_file: str) -> str:
    """Check whether a SHA-256 hash has already been processed.

    Parameters
    ----------
    sha256 : str
        SHA-256 hex digest to check.
    state_file : str
        Path to the JSON state file.

    Returns
    -------
    str
        ``"true"`` if the hash is already processed (status == completed),
        ``"false"`` otherwise.

    Examples
    --------
    >>> check_idempotency("abc...", "state.json")  # doctest: +SKIP
    'false'
    """
    logger.debug(
        "check_idempotency called",
        sha256=sha256[:16] + "...",
        state_file=state_file,
    )
    manager = StateManager(Path(state_file))
    is_processed = manager.is_processed(sha256)
    result = "true" if is_processed else "false"
    logger.info(
        "Idempotency check completed",
        sha256=sha256[:16] + "...",
        is_processed=is_processed,
    )
    return result


def get_page_count(pdf_path: str) -> str:
    """Count pages in a PDF file using PyMuPDF.

    Parameters
    ----------
    pdf_path : str
        Path to the PDF file.

    Returns
    -------
    str
        Number of pages as a string.

    Raises
    ------
    RuntimeError
        If the PDF cannot be opened.

    Examples
    --------
    >>> get_page_count("/data/raw/pdfs/report.pdf")  # doctest: +SKIP
    '30'
    """
    logger.debug("get_page_count called", pdf_path=pdf_path)
    with fitz.open(pdf_path) as doc:
        count = doc.page_count
    logger.info("Page count retrieved", pdf_path=pdf_path, page_count=count)
    return str(count)


def compute_output_dir(pdf_path: str, sha256: str) -> str:
    """Compute the mirror-path output directory for a PDF.

    The output directory follows the pattern::

        {DATA_ROOT}/processed/{mirror_subpath}/{stem}_{hash8}/

    Parameters
    ----------
    pdf_path : str
        Path to the source PDF file.
    sha256 : str
        SHA-256 hex digest of the PDF.

    Returns
    -------
    str
        Computed output directory path.

    Examples
    --------
    >>> compute_output_dir("/data/raw/pdfs/report.pdf", "abcdef01...")  # doctest: +SKIP
    '/data/processed/report_abcdef01'
    """
    logger.debug(
        "compute_output_dir called",
        pdf_path=pdf_path,
        sha256=sha256[:16] + "...",
    )

    pdf = Path(pdf_path)
    stem = pdf.stem
    hash8 = sha256[:8]

    processed_dir = get_path("processed")

    # Attempt to mirror subpath if PDF is under raw/pdfs/
    mirror_subpath = _compute_mirror_subpath(pdf)

    if mirror_subpath:
        output = processed_dir / mirror_subpath / f"{stem}_{hash8}"
    else:
        output = processed_dir / f"{stem}_{hash8}"

    result = str(output)
    logger.info("Output directory computed", output_dir=result)
    return result


def _compute_mirror_subpath(pdf: Path) -> str | None:
    """Compute the mirror subpath for a PDF relative to ``raw/pdfs/``.

    Parameters
    ----------
    pdf : Path
        Source PDF path.

    Returns
    -------
    str | None
        Relative subpath between ``raw/pdfs/`` and the PDF's parent,
        or ``None`` if the PDF is not under ``raw/pdfs/``.
    """
    parts = pdf.parts
    # Find "raw" then "pdfs" in the path parts
    for i, part in enumerate(parts):
        if part == "raw" and i + 1 < len(parts) and parts[i + 1] == "pdfs":
            # Subpath is everything between raw/pdfs/ and the filename
            subpath_parts = parts[i + 2 : -1]  # exclude filename
            if subpath_parts:
                return str(Path(*subpath_parts))
            return None
    return None


def chunk_and_save(report_md: str, sha256: str, output_dir: str) -> str:
    """Chunk a Markdown report and save as ``chunks.json``.

    Parameters
    ----------
    report_md : str
        Path to the Markdown report file.
    sha256 : str
        SHA-256 hex digest of the source PDF.
    output_dir : str
        Directory to save ``chunks.json``.

    Returns
    -------
    str
        Number of chunks as a string.

    Examples
    --------
    >>> chunk_and_save("report.md", "abc...", "/output")  # doctest: +SKIP
    '5'
    """
    logger.debug(
        "chunk_and_save called",
        report_md=report_md,
        sha256=sha256[:16] + "...",
        output_dir=output_dir,
    )

    markdown = Path(report_md).read_text(encoding="utf-8")

    chunker = MarkdownChunker()
    chunks = chunker.chunk(markdown=markdown, source_hash=sha256)

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    chunks_file = out_path / "chunks.json"
    chunks_file.write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    count = len(chunks)
    logger.info(
        "Chunks saved",
        chunk_count=count,
        output_file=str(chunks_file),
    )
    return str(count)


def save_metadata(
    output_dir: str,
    sha256: str,
    pdf_path: str,
    pages: str,
    chunks: str,
) -> str:
    """Save processing metadata as ``metadata.json``.

    Parameters
    ----------
    output_dir : str
        Directory to save ``metadata.json``.
    sha256 : str
        SHA-256 hex digest of the source PDF.
    pdf_path : str
        Path to the original PDF file.
    pages : str
        Number of pages (as string from CLI args).
    chunks : str
        Number of chunks (as string from CLI args).

    Returns
    -------
    str
        ``"ok"`` on success.

    Examples
    --------
    >>> save_metadata("/output", "abc...", "report.pdf", "30", "5")  # doctest: +SKIP
    'ok'
    """
    logger.debug(
        "save_metadata called",
        output_dir=output_dir,
        sha256=sha256[:16] + "...",
        pdf_path=pdf_path,
    )

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    metadata = {
        "sha256": sha256,
        "pdf_path": pdf_path,
        "pages": int(pages),
        "chunks": int(chunks),
        "converter": "method_b",
        "processed_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    meta_file = out_path / "metadata.json"
    meta_file.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info("Metadata saved", output_file=str(meta_file))
    return "ok"


def record_completed(sha256: str, state_file: str, filename: str) -> str:
    """Record a PDF as completed in the state file.

    Parameters
    ----------
    sha256 : str
        SHA-256 hex digest of the processed PDF.
    state_file : str
        Path to the JSON state file.
    filename : str
        Original PDF filename for provenance tracking.

    Returns
    -------
    str
        ``"ok"`` on success.

    Examples
    --------
    >>> record_completed("abc...", "state.json", "report.pdf")  # doctest: +SKIP
    'ok'
    """
    logger.debug(
        "record_completed called",
        sha256=sha256[:16] + "...",
        state_file=state_file,
        filename=filename,
    )

    manager = StateManager(Path(state_file))
    manager.record_status(
        sha256,
        "completed",
        filename=filename,
        processed_at=datetime.now(tz=timezone.utc).isoformat(),
    )
    manager.save()

    logger.info(
        "Completion recorded",
        sha256=sha256[:16] + "...",
        filename=filename,
    )
    return "ok"


# ---------------------------------------------------------------------------
# CLI dispatch table
# ---------------------------------------------------------------------------

_DISPATCH = {
    "compute_hash": compute_hash,
    "check_idempotency": check_idempotency,
    "get_page_count": get_page_count,
    "compute_output_dir": compute_output_dir,
    "chunk_and_save": chunk_and_save,
    "save_metadata": save_metadata,
    "record_completed": record_completed,
}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _cli_main() -> None:
    """Dispatch CLI calls to the appropriate helper function.

    Reads ``sys.argv`` to determine which function to call and
    prints the result to stdout.

    Raises
    ------
    SystemExit
        If the function name is unknown.
    """
    if len(sys.argv) < 2:
        print(
            "Usage: python -m pdf_pipeline.cli.helpers <func> [args...]",
            file=sys.stderr,
        )
        sys.exit(1)

    func_name = sys.argv[1]
    args = sys.argv[2:]

    if func_name not in _DISPATCH:
        print(f"Unknown function: {func_name}", file=sys.stderr)
        print(f"Available: {', '.join(sorted(_DISPATCH.keys()))}", file=sys.stderr)
        sys.exit(1)

    func = _DISPATCH[func_name]
    result = func(*args)  # type: ignore[operator]
    print(result)


if __name__ == "__main__":
    _cli_main()
