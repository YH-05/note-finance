"""PDF Pipeline CLI with Click.

Provides the ``pdf-pipeline`` command-line interface with subcommands
for processing, status checking, and reprocessing PDF files.

Functions
---------
cli
    Click group (entry point).
process
    Process a PDF file through the pipeline.
status
    Display processing status of all PDFs.
reprocess
    Reprocess a PDF by its SHA-256 hash.

Examples
--------
CLI usage::

    $ pdf-pipeline process data/raw/pdfs/report.pdf
    $ pdf-pipeline status
    $ pdf-pipeline reprocess --hash abc123def456...

"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
from rich.console import Console
from rich.table import Table

from data_paths import get_path
from pdf_pipeline._logging import get_logger
from pdf_pipeline.config.loader import load_config
from pdf_pipeline.core.pdf_scanner import PdfScanner

if TYPE_CHECKING:
    from pdf_pipeline.core.pipeline import PdfPipeline
    from pdf_pipeline.services.state_manager import StateManager
    from pdf_pipeline.types import ProcessingStatus

logger = get_logger(__name__, module="cli")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT_DIR = get_path("processed")
"""Default output directory for processed PDFs."""

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

DEFAULT_CONFIG_PATH = get_path("config/pdf-pipeline-config.yaml")
"""Default path to the YAML configuration file."""

console = Console()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_pipeline_for_dir(
    input_dir: Path,
    output_dir: Path,
    config_path: Path,
) -> "PdfPipeline":
    """Build a fully wired PdfPipeline instance for a given input directory.

    Constructs all pipeline components using the loaded configuration,
    wiring together LLM providers via a ProviderChain with fallback.

    Parameters
    ----------
    input_dir : Path
        Directory to scan for PDF files.
    output_dir : Path
        Directory where processed outputs are written.
    config_path : Path
        Path to the YAML configuration file.

    Returns
    -------
    PdfPipeline
        Wired pipeline instance ready to run.

    Raises
    ------
    SystemExit
        If configuration loading fails.
    """
    from pdf_pipeline.core.chunker import MarkdownChunker
    from pdf_pipeline.core.markdown_converter import MarkdownConverter
    from pdf_pipeline.core.noise_filter import NoiseFilter
    from pdf_pipeline.core.pipeline import PdfPipeline
    from pdf_pipeline.core.table_detector import TableDetector
    from pdf_pipeline.core.table_reconstructor import TableReconstructor
    from pdf_pipeline.services.claude_provider import ClaudeCodeProvider
    from pdf_pipeline.services.gemini_provider import GeminiCLIProvider
    from pdf_pipeline.services.provider_chain import ProviderChain
    from pdf_pipeline.services.state_manager import StateManager

    try:
        config = load_config(config_path)
    except Exception as exc:
        console.print(f"[red]Error: Failed to load config: {exc}[/red]")
        logger.error("Config loading failed", error=str(exc), exc_info=True)
        sys.exit(1)

    config = config.model_copy(
        update={
            "output_dir": output_dir,
            "input_dirs": [input_dir],
        }
    )

    state_manager = StateManager(output_dir / "state.json")

    # Build provider chain with fallback: Gemini → Claude
    provider_chain = ProviderChain([GeminiCLIProvider(), ClaudeCodeProvider()])

    return PdfPipeline(
        config=config,
        scanner=PdfScanner(input_dir=input_dir),
        noise_filter=NoiseFilter(config=config.noise_filter),
        markdown_converter=MarkdownConverter(provider=provider_chain),
        table_detector=TableDetector(),
        table_reconstructor=TableReconstructor(provider_chain=provider_chain),
        chunker=MarkdownChunker(),
        state_manager=state_manager,
    )


def _get_state_manager(output_dir: Path) -> "StateManager":
    """Get a StateManager instance for the given output directory.

    Parameters
    ----------
    output_dir : Path
        Directory containing the state.json file.

    Returns
    -------
    StateManager
        State manager loaded with existing state.
    """
    from pdf_pipeline.services.state_manager import StateManager

    state_file = output_dir / "state.json"
    return StateManager(state_file)


def _display_process_result(result: dict[str, Any], *, pdf_path: Path) -> None:
    """Display the result of a single PDF processing run.

    Parameters
    ----------
    result : dict[str, Any]
        Result dict from ``PdfPipeline.process_pdf``.
    pdf_path : Path
        Path to the processed PDF.
    """
    proc_status = result.get("status", "unknown")

    if proc_status == "completed":
        chunk_count = result.get("chunk_count", 0)
        console.print(f"[bold green]Completed:[/bold green] {pdf_path.name}")
        console.print(f"  Chunks extracted: {chunk_count}")
        console.print(f"  Hash: {result.get('source_hash', 'N/A')}")
    elif proc_status == "skipped":
        console.print(
            f"[bold yellow]Skipped:[/bold yellow] {pdf_path.name} (already processed)"
        )
        console.print(f"  Hash: {result.get('source_hash', 'N/A')}")
    else:
        error = result.get("error", "Unknown error")
        console.print(f"[bold red]Failed:[/bold red] {pdf_path.name}")
        console.print(f"  Error: {error}")
        sys.exit(1)


def _format_status(proc_status: str) -> str:
    """Format a processing status for Rich console output.

    Parameters
    ----------
    proc_status : str
        Raw status string (e.g., 'completed', 'failed').

    Returns
    -------
    str
        Rich-formatted status string.
    """
    color_map = {
        "completed": "green",
        "failed": "red",
        "processing": "yellow",
        "pending": "dim",
    }
    color = color_map.get(proc_status, "white")
    return f"[{color}]{proc_status}[/{color}]"


# ---------------------------------------------------------------------------
# CLI Group
# ---------------------------------------------------------------------------


@click.group()
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=DEFAULT_OUTPUT_DIR,
    show_default=True,
    help="Output directory for processed PDFs.",
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path),
    default=DEFAULT_CONFIG_PATH,
    show_default=True,
    help="Path to the YAML configuration file.",
)
@click.pass_context
def cli(ctx: click.Context, output_dir: Path, config_path: Path) -> None:
    """PDF Pipeline CLI — process financial PDF reports.

    Use one of the subcommands to process PDFs, check status,
    or reprocess previously failed items.
    """
    ctx.ensure_object(dict)
    ctx.obj["output_dir"] = output_dir
    ctx.obj["config_path"] = config_path

    logger.debug(
        "CLI initialized",
        output_dir=str(output_dir),
        config_path=str(config_path),
    )


# ---------------------------------------------------------------------------
# process subcommand
# ---------------------------------------------------------------------------


@cli.command()
@click.argument(
    "pdf_path",
    type=click.Path(path_type=Path, exists=True, readable=True),
)
@click.pass_context
def process(ctx: click.Context, pdf_path: Path) -> None:
    """Process a PDF file through the pipeline.

    PDF_PATH is the path to the PDF file to process.

    The pipeline performs:
    - Phase 1: PDF scanning and SHA-256 hashing
    - Phase 2: Noise filtering
    - Phase 3: Markdown conversion via LLM
    - Phase 4: Table detection and reconstruction
    - Phase 5: Markdown chunking

    Output is written to ``<output-dir>/<sha256>/chunks.json``.

    Examples
    --------
        $ pdf-pipeline process data/raw/pdfs/hsbc_isat_3q25.pdf
    """
    output_dir: Path = ctx.obj["output_dir"]
    config_path: Path = ctx.obj["config_path"]

    logger.info(
        "Starting PDF processing",
        pdf_path=str(pdf_path),
        output_dir=str(output_dir),
    )

    console.print(f"[bold blue]Processing PDF:[/bold blue] {pdf_path}")

    # Compute SHA-256 hash via PdfScanner (uses 64 KiB chunked reads)
    source_hash = PdfScanner(input_dir=pdf_path.parent).compute_sha256(pdf_path)
    console.print(f"[dim]SHA-256:[/dim] {source_hash}")

    # Build pipeline with the PDF's parent directory as input
    pipeline = _build_pipeline_for_dir(
        input_dir=pdf_path.parent,
        output_dir=output_dir,
        config_path=config_path,
    )

    result = pipeline.process_pdf(pdf_path=pdf_path, source_hash=source_hash)
    _display_process_result(result, pdf_path=pdf_path)


# ---------------------------------------------------------------------------
# status subcommand
# ---------------------------------------------------------------------------


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Display processing status of all PDFs.

    Shows a table with SHA-256 hash and processing status
    for all tracked PDFs in the output directory.

    Examples
    --------
        $ pdf-pipeline status
        $ pdf-pipeline --output-dir /tmp/processed status
    """
    output_dir: Path = ctx.obj["output_dir"]

    logger.info("Querying processing status", output_dir=str(output_dir))

    state_manager = _get_state_manager(output_dir)

    all_statuses: dict[str, ProcessingStatus] = state_manager.get_all_statuses()

    if not all_statuses:
        console.print("[yellow]No PDFs have been tracked yet.[/yellow]")
        console.print(f"  State file: {output_dir / 'state.json'}")
        return

    table = Table(
        title="PDF Pipeline Status",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("SHA-256 (truncated)", style="dim", width=20)
    table.add_column("Status", width=12)
    table.add_column("Output Exists", width=14)

    for sha256, proc_status in sorted(all_statuses.items(), key=lambda x: x[1]):
        short_hash = sha256[:16] + "..."
        output_path = output_dir / sha256
        output_exists = (
            "[green]yes[/green]" if output_path.exists() else "[dim]no[/dim]"
        )
        table.add_row(short_hash, _format_status(proc_status), output_exists)

    console.print(table)

    from collections import Counter

    counts = Counter(all_statuses.values())
    total = len(all_statuses)
    completed = counts["completed"]
    failed = counts["failed"]
    processing = counts["processing"]
    pending = counts["pending"]

    console.print(
        f"\n[bold]Total:[/bold] {total}  "
        f"[green]Completed: {completed}[/green]  "
        f"[red]Failed: {failed}[/red]  "
        f"[yellow]Processing: {processing}[/yellow]  "
        f"[dim]Pending: {pending}[/dim]"
    )

    logger.info(
        "Status query completed",
        total=total,
        completed=completed,
        failed=failed,
    )


# ---------------------------------------------------------------------------
# reprocess subcommand
# ---------------------------------------------------------------------------


@cli.command()
@click.option(
    "--hash",
    "source_hash",
    required=True,
    help="SHA-256 hash of the PDF to reprocess.",
)
@click.pass_context
def reprocess(ctx: click.Context, source_hash: str) -> None:
    """Reprocess a PDF by its SHA-256 hash.

    Clears the existing state for the given hash and re-runs the
    pipeline from the beginning.

    Examples
    --------
        $ pdf-pipeline reprocess --hash abc123def456...
    """
    output_dir: Path = ctx.obj["output_dir"]
    config_path: Path = ctx.obj["config_path"]

    if not _SHA256_RE.fullmatch(source_hash):
        console.print(
            "[red]Error: --hash must be a 64-character lowercase hex string (SHA-256)[/red]"
        )
        sys.exit(1)

    logger.info(
        "Starting reprocessing",
        source_hash=source_hash,
        output_dir=str(output_dir),
    )

    console.print(f"[bold blue]Reprocessing hash:[/bold blue] {source_hash[:16]}...")

    # Load state and verify the hash exists
    state_manager = _get_state_manager(output_dir)
    current_status = state_manager.get_status(source_hash)

    if current_status is None:
        console.print(
            f"[red]Error: Hash not found in state: {source_hash[:16]}...[/red]"
        )
        console.print("Use 'pdf-pipeline status' to list tracked PDFs.")
        sys.exit(1)

    console.print(f"  Current status: {current_status}")
    console.print("  Resetting state to 'pending'...")

    # Reset to pending so the pipeline will re-process
    state_manager.record_status(source_hash, "pending")
    state_manager.save()

    # Load config to find the original PDF
    try:
        config = load_config(config_path)
    except Exception as exc:
        console.print(f"[red]Error: Failed to load config: {exc}[/red]")
        logger.error("Config loading failed", error=str(exc), exc_info=True)
        sys.exit(1)

    # Scan all configured input directories to find the PDF
    matching_pdf: Path | None = None
    for input_dir in config.input_dirs:
        if not input_dir.exists():
            continue
        try:
            scanner = PdfScanner(input_dir=input_dir)
        except Exception:
            continue
        for pdf_path, pdf_hash in scanner.scan_with_hashes():
            if pdf_hash == source_hash:
                matching_pdf = pdf_path
                break
        if matching_pdf is not None:
            break

    if matching_pdf is None:
        console.print(f"[red]Error: No PDF found with hash {source_hash[:16]}...[/red]")
        console.print("The PDF may have been moved or deleted.")
        sys.exit(1)

    console.print(f"  Found PDF: {matching_pdf.name}")

    # Build full pipeline and reprocess
    pipeline = _build_pipeline_for_dir(
        input_dir=matching_pdf.parent,
        output_dir=output_dir,
        config_path=config_path,
    )

    result = pipeline.process_pdf(pdf_path=matching_pdf, source_hash=source_hash)
    _display_process_result(result, pdf_path=matching_pdf)

    chunks_file = output_dir / source_hash / "chunks.json"
    if chunks_file.exists():
        console.print(f"  Output: {chunks_file}")
