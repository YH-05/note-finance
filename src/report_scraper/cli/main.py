"""Report Scraper CLI with Click.

Provides the ``report-scraper`` command-line interface with a ``collect``
subcommand for collecting investment reports from configured sources.

Functions
---------
cli
    Click group (entry point).
collect
    Collect reports from a specified source.

Examples
--------
CLI usage::

    $ report-scraper collect --source advisor_perspectives
    $ report-scraper --data-dir /tmp/reports collect --source advisor_perspectives
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
from rich.console import Console
from rich.table import Table

from report_scraper._logging import get_logger

if TYPE_CHECKING:
    from report_scraper.types import CollectResult

logger = get_logger(__name__, module="cli")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_DATA_DIR = Path("data/scraped/reports")
"""Default data directory for report storage."""

# AIDEV-NOTE: Known scrapers are registered here. When new scrapers are added,
# update this registry.
KNOWN_SCRAPERS: dict[str, str] = {
    "advisor_perspectives": "report_scraper.scrapers.advisor_perspectives.AdvisorPerspectivesScraper",
}
"""Registry of known scraper source keys to class paths."""

console = Console()


# ---------------------------------------------------------------------------
# Scraper factory
# ---------------------------------------------------------------------------


def _get_scraper(source_key: str) -> Any | None:
    """Get a scraper instance for the given source key.

    Parameters
    ----------
    source_key : str
        Source identifier (e.g., ``"advisor_perspectives"``).

    Returns
    -------
    BaseReportScraper | None
        Scraper instance, or ``None`` if the source is unknown.
    """
    if source_key not in KNOWN_SCRAPERS:
        logger.warning("Unknown source key", source_key=source_key)
        return None

    class_path = KNOWN_SCRAPERS[source_key]
    module_path, class_name = class_path.rsplit(".", 1)

    try:
        import importlib

        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        return cls()
    except (ImportError, AttributeError) as exc:
        logger.error(
            "Failed to load scraper class",
            source_key=source_key,
            class_path=class_path,
            error=str(exc),
        )
        return None


# ---------------------------------------------------------------------------
# Result saving helper
# ---------------------------------------------------------------------------


def _save_results(result: CollectResult, data_dir: Path) -> None:
    """Save collection results to storage.

    Parameters
    ----------
    result : CollectResult
        Collection result to save.
    data_dir : Path
        Root directory for report storage.
    """
    from report_scraper.storage.json_store import JsonReportStore

    store = JsonReportStore(data_dir)
    store.save_run(result)
    store.update_index(result)

    for report in result.reports:
        store.save_text(report)

    logger.info(
        "Results saved",
        source_key=result.source_key,
        data_dir=str(data_dir),
    )


# ---------------------------------------------------------------------------
# CLI definition
# ---------------------------------------------------------------------------


@click.group()
@click.option(
    "--data-dir",
    type=click.Path(path_type=Path),
    default=DEFAULT_DATA_DIR,
    help="Data directory path (default: data/scraped/reports)",
)
@click.pass_context
def cli(ctx: click.Context, data_dir: Path) -> None:
    """Report Scraper CLI.

    Collect investment reports from various sources.
    """
    ctx.ensure_object(dict)
    ctx.obj["data_dir"] = data_dir
    logger.debug("CLI started", data_dir=str(data_dir))


@cli.command()
@click.option(
    "--source",
    required=True,
    help="Source key to collect from (e.g., advisor_perspectives)",
)
@click.option(
    "--max-reports",
    type=int,
    default=20,
    help="Maximum number of reports to collect (default: 20)",
)
@click.pass_context
def collect(ctx: click.Context, source: str, max_reports: int) -> None:
    """Collect reports from a specified source.

    Fetches the latest reports from the specified source, extracts
    content, and saves results to the data directory.
    """
    data_dir: Path = ctx.obj.get("data_dir", DEFAULT_DATA_DIR)
    logger.info(
        "Starting collection",
        source_key=source,
        max_reports=max_reports,
        data_dir=str(data_dir),
    )

    scraper = _get_scraper(source)
    if scraper is None:
        console.print(f"[red]Error: Unknown source '{source}'[/red]")
        console.print(f"Available sources: {', '.join(sorted(KNOWN_SCRAPERS))}")
        sys.exit(1)

    try:
        result: CollectResult = asyncio.run(scraper.collect_latest(max_reports))
    except Exception as exc:
        console.print(f"[red]Error: Collection failed: {exc}[/red]")
        logger.error(
            "Collection failed",
            source_key=source,
            error=str(exc),
            exc_info=True,
        )
        sys.exit(1)

    # Save results
    try:
        _save_results(result, data_dir)
    except Exception as exc:
        console.print(f"[yellow]Warning: Failed to save results: {exc}[/yellow]")
        logger.warning(
            "Failed to save results",
            source_key=source,
            error=str(exc),
        )

    # Display results
    if result.reports:
        table = Table(title=f"Collected Reports ({source})")
        table.add_column("Title", style="green", max_width=50)
        table.add_column("Published")
        table.add_column("Content")

        for report in result.reports:
            meta = report.metadata
            pub_date = meta.published.strftime("%Y-%m-%d") if meta.published else "-"
            content_info = (
                f"{report.content.length} chars ({report.content.method})"
                if report.content
                else "[dim]none[/dim]"
            )
            title_display = (
                meta.title[:47] + "..." if len(meta.title) > 50 else meta.title
            )
            table.add_row(title_display, pub_date, content_info)

        console.print(table)

    # Summary
    console.print(
        f"\n[bold]Summary:[/bold] {len(result.reports)} reports collected, "
        f"{len(result.errors)} errors, {result.duration:.1f}s"
    )

    if result.errors:
        console.print("\n[yellow]Errors:[/yellow]")
        for error in result.errors:
            console.print(f"  - {error}")

    logger.info(
        "Collection completed",
        source_key=source,
        reports=len(result.reports),
        errors=len(result.errors),
        duration=round(result.duration, 2),
    )


if __name__ == "__main__":
    cli()
