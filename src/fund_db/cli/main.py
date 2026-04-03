"""Fund DB CLI with Click.

Provides the ``fund-db`` command-line interface with subcommands
for downloading, parsing, and managing fund data from NISA, JPX,
investment trust statistics, and ETF price sources.

Functions
---------
cli
    Click group (entry point).
nisa_group
    NISA fund data commands.
jpx_group
    JPX listed securities commands.
stats_group
    Investment trust statistics commands.
etf_group
    ETF price data commands.
sync_all
    Execute all sync workflows sequentially.
status
    Display data freshness for each category.

Examples
--------
CLI usage::

    $ fund-db --help
    $ fund-db nisa download
    $ fund-db jpx sync
    $ fund-db stats summary
    $ fund-db etf fetch --tickers 1306 1321 --start 2026-01-01
    $ fund-db sync-all
    $ fund-db status
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from fund_db._logging import get_logger

logger = get_logger(__name__, module="cli")
console = Console()

# ---------------------------------------------------------------------------
# Data categories used across the CLI
# ---------------------------------------------------------------------------

_DATA_CATEGORIES: list[tuple[str, str]] = [
    ("nisa_unlisted", "NISA (非上場ファンド)"),
    ("nisa_listed", "NISA (上場ETF)"),
    ("jpx_listed", "JPX 上場銘柄"),
    ("toushin_stats_b1", "投信統計 B-1 (資産増減)"),
    ("toushin_stats_b2", "投信統計 B-2 (商品分類)"),
    ("toushin_stats_b3", "投信統計 B-3 (運用会社)"),
    ("toushin_stats_a2", "投信統計 A-2 (全体像)"),
]
"""Categories and their display labels for the status command."""


# ---------------------------------------------------------------------------
# CLI root group
# ---------------------------------------------------------------------------


@click.group()
@click.option(
    "--data-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Data directory path (default: data/fund_db)",
)
@click.pass_context
def cli(ctx: click.Context, data_dir: str | None) -> None:
    """Fund DB CLI -- download, parse, and manage fund data."""
    from fund_db.storage import FundDbStore

    ctx.ensure_object(dict)
    ctx.obj["store"] = FundDbStore(Path(data_dir) if data_dir else None)
    logger.debug("CLI started", data_dir=str(data_dir))


# ===================================================================
# nisa group
# ===================================================================


@cli.group("nisa")
def nisa_group() -> None:
    """NISA growth investment target fund commands."""


@nisa_group.command("download")
@click.pass_context
def nisa_download(ctx: click.Context) -> None:
    """Download NISA Excel files from IMAJ."""
    from fund_db.nisa import NisaDownloader

    store = ctx.obj["store"]
    try:
        downloader = NisaDownloader(store=store)
        results = downloader.download_all()
        console.print(
            f"[green]Downloaded {len(results)} file(s), "
            f"total {sum(r.size_bytes for r in results):,} bytes[/green]"
        )
        logger.info("NISA download complete", file_count=len(results))
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        logger.error("NISA download failed", error=str(exc), exc_info=True)
        sys.exit(1)


@nisa_group.command("parse")
@click.pass_context
def nisa_parse(ctx: click.Context) -> None:
    """Parse downloaded NISA Excel files."""
    from fund_db.nisa import NisaParser

    store = ctx.obj["store"]
    parser = NisaParser()

    # Find latest raw files
    unlisted_partitions = store.list_partitions("nisa_unlisted")
    listed_partitions = store.list_partitions("nisa_listed")

    total_records = 0

    if unlisted_partitions:
        latest_date = max(unlisted_partitions)
        raw_path = store.data_dir / "nisa_unlisted" / latest_date.isoformat() / "raw"
        xlsx_files = list(raw_path.glob("*.xlsx")) if raw_path.exists() else []
        for xlsx_file in xlsx_files:
            try:
                funds = parser.parse_unlisted(xlsx_file)
                records = [f.model_dump() for f in funds]
                store.save_records(records, "nisa_unlisted", latest_date)
                total_records += len(records)
                console.print(f"  Parsed {len(records)} unlisted funds")
            except Exception as exc:
                console.print(f"[red]Error parsing {xlsx_file.name}: {exc}[/red]")
    else:
        console.print(
            "[yellow]No NISA unlisted data found. Run download first.[/yellow]"
        )

    if listed_partitions:
        latest_date = max(listed_partitions)
        raw_path = store.data_dir / "nisa_listed" / latest_date.isoformat() / "raw"
        xlsx_files = list(raw_path.glob("*.xlsx")) if raw_path.exists() else []
        for xlsx_file in xlsx_files:
            try:
                etfs = parser.parse_listed(xlsx_file)
                records = [e.model_dump() for e in etfs]
                store.save_records(records, "nisa_listed", latest_date)
                total_records += len(records)
                console.print(f"  Parsed {len(records)} listed ETFs")
            except Exception as exc:
                console.print(f"[red]Error parsing {xlsx_file.name}: {exc}[/red]")
    else:
        console.print("[yellow]No NISA listed data found. Run download first.[/yellow]")

    console.print(f"[green]Total: {total_records} records parsed[/green]")
    logger.info("NISA parse complete", total_records=total_records)


@nisa_group.command("sync")
@click.pass_context
def nisa_sync(ctx: click.Context) -> None:
    """Download and parse NISA data (download + parse)."""
    ctx.invoke(nisa_download)
    ctx.invoke(nisa_parse)
    console.print("[green]NISA sync complete[/green]")


@nisa_group.command("list")
@click.pass_context
def nisa_list(ctx: click.Context) -> None:
    """List latest NISA unlisted fund data."""
    store = ctx.obj["store"]
    records = store.load_latest("nisa_unlisted")
    if records is None:
        console.print("[yellow]No NISA unlisted data available.[/yellow]")
        return

    table = Table(title="NISA Unlisted Funds (Latest)")
    table.add_column("Code", style="cyan", no_wrap=True)
    table.add_column("Fund Name", style="green", max_width=50)
    table.add_column("Management Company")
    table.add_column("Asset Class")
    table.add_column("Expense Ratio", justify="right")

    for rec in records[:50]:  # Show first 50
        table.add_row(
            rec.get("association_code", "-"),
            _truncate(rec.get("fund_name", "-"), 50),
            _truncate(rec.get("management_company", "-"), 30),
            rec.get("asset_class", "-") or "-",
            rec.get("expense_ratio", "-") or "-",
        )

    console.print(table)
    console.print(f"\n[bold]{len(records)}[/bold] total fund(s)")
    if len(records) > 50:
        console.print(f"  (showing first 50 of {len(records)})")


# ===================================================================
# jpx group
# ===================================================================


@cli.group("jpx")
def jpx_group() -> None:
    """JPX listed securities commands."""


@jpx_group.command("download")
@click.pass_context
def jpx_download(ctx: click.Context) -> None:
    """Download JPX listed securities XLS file."""
    from fund_db.jpx import JpxDownloader

    store = ctx.obj["store"]
    try:
        downloader = JpxDownloader(store=store)
        result = downloader.download()
        console.print(
            f"[green]Downloaded {result.path.name}, {result.size_bytes:,} bytes[/green]"
        )
        logger.info("JPX download complete", size_bytes=result.size_bytes)
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        logger.error("JPX download failed", error=str(exc), exc_info=True)
        sys.exit(1)


@jpx_group.command("parse")
@click.pass_context
def jpx_parse(ctx: click.Context) -> None:
    """Parse downloaded JPX XLS file."""
    from fund_db.jpx import JpxParser

    store = ctx.obj["store"]
    parser = JpxParser()
    partitions = store.list_partitions("jpx_listed")

    if not partitions:
        console.print("[yellow]No JPX data found. Run download first.[/yellow]")
        return

    latest_date = max(partitions)
    raw_path = store.data_dir / "jpx_listed" / latest_date.isoformat() / "raw"
    xls_files = list(raw_path.glob("*.xls")) if raw_path.exists() else []

    total_records = 0
    for xls_file in xls_files:
        try:
            stocks = parser.parse(xls_file)
            records = [s.model_dump() for s in stocks]
            store.save_records(records, "jpx_listed", latest_date)
            total_records += len(records)
            console.print(f"  Parsed {len(records)} listed securities")
        except Exception as exc:
            console.print(f"[red]Error parsing {xls_file.name}: {exc}[/red]")

    console.print(f"[green]Total: {total_records} records parsed[/green]")
    logger.info("JPX parse complete", total_records=total_records)


@jpx_group.command("sync")
@click.pass_context
def jpx_sync(ctx: click.Context) -> None:
    """Download and parse JPX data (download + parse)."""
    ctx.invoke(jpx_download)
    ctx.invoke(jpx_parse)
    console.print("[green]JPX sync complete[/green]")


@jpx_group.command("list-etfs")
@click.pass_context
def jpx_list_etfs(ctx: click.Context) -> None:
    """List ETF/ETN securities from latest JPX data."""
    from fund_db.jpx import JpxParser

    store = ctx.obj["store"]
    partitions = store.list_partitions("jpx_listed")

    if not partitions:
        console.print("[yellow]No JPX data found. Run download first.[/yellow]")
        return

    latest_date = max(partitions)
    raw_path = store.data_dir / "jpx_listed" / latest_date.isoformat() / "raw"
    xls_files = list(raw_path.glob("*.xls")) if raw_path.exists() else []

    if not xls_files:
        console.print("[yellow]No raw XLS files found.[/yellow]")
        return

    parser = JpxParser()
    etfs = parser.parse_etfs_only(xls_files[0])

    table = Table(title="JPX Listed ETFs/ETNs (Latest)")
    table.add_column("Ticker", style="cyan", no_wrap=True)
    table.add_column("Name", style="green", max_width=50)
    table.add_column("Market Segment")
    table.add_column("Sector (33)")

    for etf in etfs[:50]:
        table.add_row(
            etf.ticker_code,
            _truncate(etf.name, 50),
            etf.market_segment or "-",
            etf.sector_name_33 or "-",
        )

    console.print(table)
    console.print(f"\n[bold]{len(etfs)}[/bold] ETF/ETN(s)")
    if len(etfs) > 50:
        console.print(f"  (showing first 50 of {len(etfs)})")


# ===================================================================
# stats group
# ===================================================================


@cli.group("stats")
def stats_group() -> None:
    """Investment trust statistics commands."""


@stats_group.command("download")
@click.pass_context
def stats_download(ctx: click.Context) -> None:
    """Download all statistics Excel files from IMAJ."""
    from fund_db.toushin_stats import ToushinStatsDownloader

    store = ctx.obj["store"]
    try:
        downloader = ToushinStatsDownloader(store=store)
        results = downloader.download_all()
        console.print(
            f"[green]Downloaded {len(results)} file(s), "
            f"total {sum(r.size_bytes for r in results):,} bytes[/green]"
        )
        logger.info("Stats download complete", file_count=len(results))
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        logger.error("Stats download failed", error=str(exc), exc_info=True)
        sys.exit(1)


@stats_group.command("parse")
@click.pass_context
def stats_parse(ctx: click.Context) -> None:
    """Parse downloaded statistics Excel files."""
    from fund_db.toushin_stats import ToushinStatsParser

    store = ctx.obj["store"]
    parser = ToushinStatsParser()
    total_records = 0

    report_configs = [
        ("toushin_stats_b1", "parse_b1", "B-1 (Asset Flow)"),
        ("toushin_stats_b2", "parse_b2", "B-2 (Product Class)"),
        ("toushin_stats_b3", "parse_b3", "B-3 (Management Company)"),
        ("toushin_stats_a2", "parse_a2", "A-2 (Overall Status)"),
    ]

    for category, method_name, label in report_configs:
        partitions = store.list_partitions(category)
        if not partitions:
            console.print(f"[yellow]No {label} data found.[/yellow]")
            continue

        latest_date = max(partitions)
        raw_path = store.data_dir / category / latest_date.isoformat() / "raw"
        xlsx_files = list(raw_path.glob("*.xlsx")) if raw_path.exists() else []

        for xlsx_file in xlsx_files:
            try:
                parse_method = getattr(parser, method_name)
                parsed = parse_method(xlsx_file)
                records = [r.model_dump() for r in parsed]
                store.save_records(records, category, latest_date)
                total_records += len(records)
                console.print(f"  Parsed {len(records)} {label} records")
            except Exception as exc:
                console.print(
                    f"[red]Error parsing {label} ({xlsx_file.name}): {exc}[/red]"
                )

    console.print(f"[green]Total: {total_records} records parsed[/green]")
    logger.info("Stats parse complete", total_records=total_records)


@stats_group.command("sync")
@click.pass_context
def stats_sync(ctx: click.Context) -> None:
    """Download and parse statistics data (download + parse)."""
    ctx.invoke(stats_download)
    ctx.invoke(stats_parse)
    console.print("[green]Stats sync complete[/green]")


@stats_group.command("summary")
@click.pass_context
def stats_summary(ctx: click.Context) -> None:
    """Display latest statistics summary."""
    store = ctx.obj["store"]

    table = Table(title="Investment Trust Statistics Summary")
    table.add_column("Report", style="cyan")
    table.add_column("Records", justify="right")
    table.add_column("Sample Data")

    stat_categories = [
        ("toushin_stats_b1", "B-1 (Asset Flow)"),
        ("toushin_stats_b2", "B-2 (Product Class)"),
        ("toushin_stats_b3", "B-3 (Management Company)"),
        ("toushin_stats_a2", "A-2 (Overall Status)"),
    ]

    for category, label in stat_categories:
        records = store.load_latest(category)
        if records is None:
            table.add_row(label, "-", "[dim]No data[/dim]")
            continue

        sample = ""
        if records:
            first = records[0]
            if "year_month" in first:
                sample = f"Latest: {first['year_month']}"
            elif "company_name" in first:
                sample = f"e.g., {first['company_name']}"

        table.add_row(label, str(len(records)), sample)

    console.print(table)


# ===================================================================
# etf group
# ===================================================================


@cli.group("etf")
def etf_group() -> None:
    """ETF price data commands."""


@etf_group.command("fetch")
@click.option(
    "--tickers",
    required=True,
    multiple=True,
    help="ETF ticker codes (e.g., --tickers 1306 --tickers 1321)",
)
@click.option(
    "--start",
    required=True,
    help="Start date in YYYY-MM-DD format",
)
@click.option(
    "--end",
    default=None,
    help="End date in YYYY-MM-DD format (default: today)",
)
def etf_fetch(tickers: tuple[str, ...], start: str, end: str | None) -> None:
    """Fetch ETF price data from Yahoo Finance."""
    from fund_db.etf_prices import EtfPriceFetcher

    fetcher = EtfPriceFetcher()
    try:
        records = fetcher.fetch(list(tickers), start=start, end=end)
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        logger.error("ETF fetch failed", error=str(exc), exc_info=True)
        sys.exit(1)

    if not records:
        console.print("[yellow]No price data returned.[/yellow]")
        return

    table = Table(title=f"ETF Prices ({start} to {end or 'today'})")
    table.add_column("Ticker", style="cyan", no_wrap=True)
    table.add_column("Date")
    table.add_column("Open", justify="right")
    table.add_column("High", justify="right")
    table.add_column("Low", justify="right")
    table.add_column("Close", justify="right")
    table.add_column("Volume", justify="right")

    for rec in records[:50]:
        table.add_row(
            rec.ticker,
            str(rec.date),
            f"{rec.open:,.1f}" if rec.open is not None else "-",
            f"{rec.high:,.1f}" if rec.high is not None else "-",
            f"{rec.low:,.1f}" if rec.low is not None else "-",
            f"{rec.close:,.1f}",
            f"{rec.volume:,}" if rec.volume is not None else "-",
        )

    console.print(table)
    console.print(f"\n[bold]{len(records)}[/bold] record(s)")
    if len(records) > 50:
        console.print(f"  (showing first 50 of {len(records)})")


@etf_group.command("performance")
@click.option(
    "--tickers",
    required=True,
    multiple=True,
    help="ETF ticker codes (e.g., --tickers 1306 --tickers 1321)",
)
@click.option(
    "--years",
    type=int,
    default=3,
    help="Number of years to look back (default: 3)",
)
def etf_performance(tickers: tuple[str, ...], years: int) -> None:
    """Display ETF performance metrics."""
    from fund_db.etf_prices import EtfPriceFetcher

    fetcher = EtfPriceFetcher()
    try:
        summaries = fetcher.get_performance(list(tickers), years=years)
    except Exception as exc:
        console.print(f"[red]Error: {exc}[/red]")
        logger.error("ETF performance failed", error=str(exc), exc_info=True)
        sys.exit(1)

    if not summaries:
        console.print("[yellow]No performance data available.[/yellow]")
        return

    table = Table(title=f"ETF Performance ({years}-year)")
    table.add_column("Ticker", style="cyan", no_wrap=True)
    table.add_column("Period")
    table.add_column("Total Return", justify="right")
    table.add_column("Annualized Vol", justify="right")
    table.add_column("Max Drawdown", justify="right")

    for s in summaries:
        table.add_row(
            s.ticker,
            f"{s.period_start} - {s.period_end}",
            f"{s.total_return:+.1%}",
            f"{s.annualized_volatility:.1%}",
            f"{s.max_drawdown:+.1%}",
        )

    console.print(table)


# ===================================================================
# sync-all command
# ===================================================================


@cli.command("sync-all")
@click.pass_context
def sync_all(ctx: click.Context) -> None:
    """Execute all sync workflows sequentially (nisa + jpx + stats)."""
    console.print("[bold]Starting sync-all...[/bold]\n")

    console.print("[bold cyan]--- NISA ---[/bold cyan]")
    try:
        ctx.invoke(nisa_sync)
    except SystemExit:
        console.print("[red]NISA sync failed, continuing...[/red]")

    console.print("\n[bold cyan]--- JPX ---[/bold cyan]")
    try:
        ctx.invoke(jpx_sync)
    except SystemExit:
        console.print("[red]JPX sync failed, continuing...[/red]")

    console.print("\n[bold cyan]--- Stats ---[/bold cyan]")
    try:
        ctx.invoke(stats_sync)
    except SystemExit:
        console.print("[red]Stats sync failed, continuing...[/red]")

    console.print("\n[bold green]sync-all complete[/bold green]")
    logger.info("sync-all complete")


# ===================================================================
# status command
# ===================================================================


@cli.command("status")
@click.pass_context
def status(ctx: click.Context) -> None:
    """Display data freshness for each category."""
    store = ctx.obj["store"]

    table = Table(title="Fund DB Data Status")
    table.add_column("Category", style="cyan")
    table.add_column("Latest Partition")
    table.add_column("Records", justify="right")
    table.add_column("Partitions", justify="right")

    for category, label in _DATA_CATEGORIES:
        partitions = store.list_partitions(category)
        if not partitions:
            table.add_row(label, "[dim]No data[/dim]", "-", "0")
            continue

        latest_date = max(partitions)
        records = store.load_latest(category)
        record_count = str(len(records)) if records else "-"
        table.add_row(
            label,
            latest_date.isoformat(),
            record_count,
            str(len(partitions)),
        )

    console.print(table)
    logger.info("Status displayed")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _truncate(text: str, max_length: int) -> str:
    """Truncate text with ellipsis if exceeding max_length.

    Parameters
    ----------
    text : str
        Text to truncate.
    max_length : int
        Maximum length before truncation.

    Returns
    -------
    str
        Truncated text.
    """
    if len(text) > max_length:
        return text[: max_length - 3] + "..."
    return text


if __name__ == "__main__":
    cli()
