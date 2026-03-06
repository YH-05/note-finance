"""Report Scraper CLI with Click.

Provides the ``report-scraper`` command-line interface with subcommands
for collecting, listing, and testing report sources.

Functions
---------
cli
    Click group (entry point).
collect
    Collect reports from a specified source.
list_sources
    List configured report sources with optional tier filter.
test_source
    Dry-run a single source to verify configuration.

Examples
--------
CLI usage::

    $ report-scraper collect --source advisor_perspectives
    $ report-scraper list
    $ report-scraper list --tier buy_side
    $ report-scraper test-source advisor_perspectives
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
from report_scraper.config.loader import load_config

if TYPE_CHECKING:
    from report_scraper.types import CollectResult, ReportScraperConfig, SourceConfig

logger = get_logger(__name__, module="cli")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_DATA_DIR = Path("data/scraped/reports")
"""Default data directory for report storage."""

DEFAULT_CONFIG_PATH = Path("data/config/report-scraper-config.yaml")
"""Default path to the YAML configuration file."""

# AIDEV-NOTE: Known scrapers are registered here. When new scrapers are added,
# update this registry.
KNOWN_SCRAPERS: dict[str, str] = {
    "advisor_perspectives": "report_scraper.scrapers.advisor_perspectives.AdvisorPerspectivesScraper",
    "bank_of_america": "report_scraper.scrapers.bank_of_america.BankOfAmericaScraper",
    "blackrock_bii": "report_scraper.scrapers.blackrock.BlackRockScraper",
    "deutsche_bank": "report_scraper.scrapers.deutsche_bank.DeutscheBankScraper",
    "fidelity": "report_scraper.scrapers.fidelity.FidelityScraper",
    "goldman_sachs": "report_scraper.scrapers.goldman_sachs.GoldmanSachsScraper",
    "invesco": "report_scraper.scrapers.invesco.InvescoScraper",
    "jpmorgan": "report_scraper.scrapers.jpmorgan.JPMorganScraper",
    "morgan_stanley": "report_scraper.scrapers.morgan_stanley.MorganStanleyScraper",
    "pimco": "report_scraper.scrapers.pimco.PimcoScraper",
    "schroders": "report_scraper.scrapers.schroders.SchrodersScraper",
    "schwab": "report_scraper.scrapers.schwab.SchwabScraper",
    "state_street": "report_scraper.scrapers.state_street.StateStreetScraper",
    "t_rowe_price": "report_scraper.scrapers.t_rowe_price.TRowePriceScraper",
    "vanguard": "report_scraper.scrapers.vanguard.VanguardScraper",
    "wells_fargo": "report_scraper.scrapers.wells_fargo.WellsFargoScraper",
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


# ---------------------------------------------------------------------------
# Helper: load config with error handling
# ---------------------------------------------------------------------------


def _load_config_or_exit(config_path: Path | None = None) -> ReportScraperConfig:
    """Load configuration file or exit with an error message.

    Parameters
    ----------
    config_path : Path | None
        Path to the config file. Defaults to ``DEFAULT_CONFIG_PATH``.

    Returns
    -------
    ReportScraperConfig
        Validated configuration object.
    """
    path = config_path or DEFAULT_CONFIG_PATH
    try:
        return load_config(path)
    except Exception as exc:
        console.print(f"[red]Error: Failed to load config: {exc}[/red]")
        logger.error("Failed to load config", path=str(path), error=str(exc))
        sys.exit(1)


def _filter_sources_by_tier(
    sources: list[SourceConfig],
    tier: str | None,
) -> list[SourceConfig]:
    """Filter sources by tier if specified.

    Parameters
    ----------
    sources : list[SourceConfig]
        All configured sources.
    tier : str | None
        Tier to filter by, or ``None`` for no filtering.

    Returns
    -------
    list[SourceConfig]
        Filtered list of sources.
    """
    if tier is None:
        return sources
    return [s for s in sources if s.tier == tier]


# ---------------------------------------------------------------------------
# list command
# ---------------------------------------------------------------------------


@cli.command("list")
@click.option(
    "--tier",
    type=click.Choice(["buy_side", "sell_side", "aggregator"]),
    default=None,
    help="Filter sources by tier (buy_side, sell_side, aggregator)",
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to config file (default: data/config/report-scraper-config.yaml)",
)
def list_sources(tier: str | None, config_path: Path | None) -> None:
    """List configured report sources.

    Displays a table of all configured sources with key, name, tier,
    rendering method, and tags. Supports filtering by tier.
    """
    logger.debug("Listing sources", tier=tier)

    config = _load_config_or_exit(config_path)
    filtered = _filter_sources_by_tier(config.sources, tier)

    if not filtered:
        tier_msg = f" for tier '{tier}'" if tier else ""
        console.print(f"[yellow]No sources found{tier_msg}.[/yellow]")
        return

    table = Table(title="Configured Report Sources")
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Name", style="green")
    table.add_column("Tier", style="magenta")
    table.add_column("Rendering")
    table.add_column("Tags")
    table.add_column("Max Reports", justify="right")

    for source in filtered:
        max_rpt = str(source.max_reports) if source.max_reports else "-"
        tags_str = ", ".join(source.tags) if source.tags else "-"
        table.add_row(
            source.key,
            source.name,
            source.tier,
            source.rendering,
            tags_str,
            max_rpt,
        )

    console.print(table)
    console.print(f"\n[bold]{len(filtered)}[/bold] source(s) listed.")

    logger.info(
        "Sources listed",
        total=len(filtered),
        tier_filter=tier,
    )


# ---------------------------------------------------------------------------
# test-source command
# ---------------------------------------------------------------------------


@cli.command("test-source")
@click.argument("key")
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to config file (default: data/config/report-scraper-config.yaml)",
)
def test_source(key: str, config_path: Path | None) -> None:
    """Dry-run a single source to verify its configuration.

    Looks up the source KEY in the configuration and displays its
    settings without actually fetching any reports.
    """
    logger.debug("Testing source", source_key=key)

    config = _load_config_or_exit(config_path)

    # Find the source by key
    source: SourceConfig | None = None
    for s in config.sources:
        if s.key == key:
            source = s
            break

    if source is None:
        available_keys = [s.key for s in config.sources]
        console.print(f"[red]Error: Source '{key}' not found in config.[/red]")
        console.print(f"Available sources: {', '.join(sorted(available_keys))}")
        logger.warning(
            "Source not found for test",
            source_key=key,
            available=available_keys,
        )
        sys.exit(1)

    # Display source configuration details
    console.print(f"\n[bold]Source Configuration: {key}[/bold]\n")

    detail_table = Table(show_header=False, box=None, padding=(0, 2))
    detail_table.add_column("Field", style="bold cyan")
    detail_table.add_column("Value")

    detail_table.add_row("Key", source.key)
    detail_table.add_row("Name", source.name)
    detail_table.add_row("Tier", source.tier)
    detail_table.add_row("Listing URL", source.listing_url)
    detail_table.add_row("Rendering", source.rendering)
    detail_table.add_row("Tags", ", ".join(source.tags) if source.tags else "-")
    detail_table.add_row(
        "Max Reports",
        str(source.max_reports)
        if source.max_reports
        else f"(global: {config.global_config.max_reports_per_source})",
    )
    detail_table.add_row(
        "Article Selector",
        source.article_selector or "-",
    )
    detail_table.add_row(
        "PDF Selector",
        source.pdf_selector or "-",
    )

    console.print(detail_table)
    console.print("\n[green]Configuration is valid.[/green]")

    logger.info(
        "Source test completed",
        source_key=key,
        tier=source.tier,
        rendering=source.rendering,
    )


# ---------------------------------------------------------------------------
# history command
# ---------------------------------------------------------------------------


@cli.command("history")
@click.option(
    "--days",
    type=int,
    default=7,
    help="Number of days to look back (default: 7)",
)
@click.pass_context
def history(ctx: click.Context, days: int) -> None:
    """Show collection history for the specified period.

    Displays a Rich table of reports collected within the last ``--days``
    days, reading from the JSON index maintained by ``JsonReportStore``.
    """
    data_dir: Path = ctx.obj.get("data_dir", DEFAULT_DATA_DIR)
    logger.debug("Showing history", days=days, data_dir=str(data_dir))

    from report_scraper.services.dedup_tracker import DedupTracker
    from report_scraper.storage.json_store import JsonReportStore

    store = JsonReportStore(data_dir)
    tracker = DedupTracker(store, dedup_days=days)
    entries = tracker.get_history(days=days)

    if not entries:
        console.print(
            f"[yellow]No reports collected in the last {days} day(s).[/yellow]"
        )
        logger.info("No history entries found", days=days)
        return

    # Sort by collected_at descending
    entries.sort(key=lambda e: e.get("collected_at", ""), reverse=True)

    table = Table(title=f"Collection History (last {days} day(s))")
    table.add_column("Collected At", style="cyan", no_wrap=True)
    table.add_column("Source", style="magenta")
    table.add_column("Title", style="green", max_width=50)
    table.add_column("URL", style="dim", max_width=60)

    for entry in entries:
        collected_at = entry.get("collected_at", "-")
        # Truncate ISO timestamp to date + time (no microseconds / tz)
        if len(collected_at) > 19:
            collected_at = collected_at[:19]

        title = entry.get("title", "")
        title_display = title[:47] + "..." if len(title) > 50 else title

        url = entry.get("url", "")
        url_display = url[:57] + "..." if len(url) > 60 else url

        table.add_row(
            collected_at,
            entry.get("source_key", "-"),
            title_display,
            url_display,
        )

    console.print(table)
    console.print(f"\n[bold]{len(entries)}[/bold] report(s) in the last {days} day(s).")

    logger.info(
        "History displayed",
        days=days,
        entries=len(entries),
    )


if __name__ == "__main__":
    cli()
