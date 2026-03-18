"""RSS CLI main module.

This module provides the command-line interface for RSS feed management.
Implements 9 subcommands: add, list, update, remove, fetch, items, search, info, stats.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from data_paths import get_path

from .. import __version__
from ..exceptions import (
    FeedAlreadyExistsError,
    FeedFetchError,
    FeedNotFoundError,
    FeedParseError,
    InvalidURLError,
    RSSError,
)
from ..services.feed_fetcher import FeedFetcher
from ..services.feed_manager import FeedManager
from ..services.feed_reader import FeedReader
from ..types import Feed, FeedItem, FetchInterval, FetchResult


def _get_logger() -> Any:
    """Get logger with lazy initialization to avoid circular imports."""
    try:
        from rss._logging import get_logger

        return get_logger(__name__, module="cli")
    except ImportError:
        return logging.getLogger(__name__)


logger: Any = _get_logger()

# Default data directory (resolved via data_paths)
DEFAULT_DATA_DIR = get_path("raw/rss")

# Console for rich output
console = Console()


def _get_data_dir(ctx: click.Context) -> Path:
    """Get data directory from context.

    Parameters
    ----------
    ctx : click.Context
        Click context

    Returns
    -------
    Path
        Data directory path
    """
    return ctx.obj.get("data_dir", DEFAULT_DATA_DIR)


def _output_json(data: dict[str, Any] | list[dict[str, Any]]) -> None:
    """Output data as JSON.

    Parameters
    ----------
    data : dict[str, Any] | list[dict[str, Any]]
        Data to output
    """
    click.echo(json.dumps(data, ensure_ascii=False, indent=2))


def _feed_to_dict(feed: Feed) -> dict[str, Any]:
    """Convert Feed to dictionary.

    Parameters
    ----------
    feed : Feed
        Feed object

    Returns
    -------
    dict[str, Any]
        Dictionary representation
    """
    return {
        "feed_id": feed.feed_id,
        "url": feed.url,
        "title": feed.title,
        "category": feed.category,
        "fetch_interval": feed.fetch_interval.value,
        "created_at": feed.created_at,
        "updated_at": feed.updated_at,
        "last_fetched": feed.last_fetched,
        "last_status": feed.last_status.value,
        "enabled": feed.enabled,
    }


def _item_to_dict(item: FeedItem) -> dict[str, Any]:
    """Convert FeedItem to dictionary.

    Parameters
    ----------
    item : FeedItem
        FeedItem object

    Returns
    -------
    dict[str, Any]
        Dictionary representation
    """
    return {
        "item_id": item.item_id,
        "title": item.title,
        "link": item.link,
        "published": item.published,
        "summary": item.summary,
        "content": item.content,
        "author": item.author,
        "fetched_at": item.fetched_at,
    }


def _result_to_dict(result: FetchResult) -> dict[str, Any]:
    """Convert FetchResult to dictionary.

    Parameters
    ----------
    result : FetchResult
        FetchResult object

    Returns
    -------
    dict[str, Any]
        Dictionary representation
    """
    return {
        "feed_id": result.feed_id,
        "success": result.success,
        "items_count": result.items_count,
        "new_items": result.new_items,
        "error_message": result.error_message,
    }


def _truncate(text: str | None, max_length: int = 50) -> str:
    """Truncate text to max length.

    Parameters
    ----------
    text : str | None
        Text to truncate
    max_length : int, default=50
        Maximum length

    Returns
    -------
    str
        Truncated text
    """
    if text is None:
        return ""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def _handle_error(
    error: RSSError,
    error_type: str,
    json_output: bool,
    **log_context: Any,
) -> None:
    """Handle RSS error with consistent logging and output.

    Parameters
    ----------
    error : RSSError
        The error to handle
    error_type : str
        Error type description for logging
    json_output : bool
        Whether to output as JSON
    **log_context : Any
        Additional context for logging
    """
    logger.error(error_type, error=str(error), **log_context)
    if json_output:
        _output_json({"error": str(error)})
    else:
        console.print(f"[red]Error: {error}[/red]")
    sys.exit(1)


def _configure_log_level(quiet: bool, verbose: bool) -> None:
    """Configure log level based on CLI flags.

    Parameters
    ----------
    quiet : bool
        Suppress log output
    verbose : bool
        Enable DEBUG log level
    """
    if quiet:
        logging.getLogger("rss").setLevel(logging.CRITICAL)
    elif verbose:
        logging.getLogger("rss").setLevel(logging.DEBUG)


@click.group()
@click.version_option(version=__version__, prog_name="rss-cli")
@click.option(
    "--data-dir",
    type=click.Path(path_type=Path),
    default=DEFAULT_DATA_DIR,
    help="Data directory path (default: data/raw/rss)",
)
@click.option("--quiet", "-q", is_flag=True, help="Suppress log output")
@click.option("--verbose", "-v", is_flag=True, help="Enable DEBUG log output")
@click.pass_context
def cli(ctx: click.Context, data_dir: Path, quiet: bool, verbose: bool) -> None:
    """RSS Feed Management CLI.

    Manage RSS feeds: add, list, update, remove, fetch, view items, and search.
    """
    ctx.ensure_object(dict)
    ctx.obj["data_dir"] = data_dir
    ctx.obj["quiet"] = quiet
    _configure_log_level(quiet, verbose)
    logger.debug("CLI started", data_dir=str(data_dir))


@cli.command()
@click.option("--url", required=True, help="Feed URL (HTTP/HTTPS)")
@click.option("--title", required=True, help="Feed title")
@click.option("--category", required=True, help="Feed category")
@click.option(
    "--interval",
    type=click.Choice(["daily", "weekly", "manual"]),
    default="daily",
    help="Fetch interval (default: daily)",
)
@click.option(
    "--validate/--no-validate",
    default=False,
    help="Validate URL reachability",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def add(
    ctx: click.Context,
    url: str,
    title: str,
    category: str,
    interval: str,
    validate: bool,
    json_output: bool,
) -> None:
    """Register a new feed."""
    logger.info("Adding feed", url=url, title=title, category=category)

    data_dir = _get_data_dir(ctx)
    manager = FeedManager(data_dir)

    interval_enum = FetchInterval(interval)

    try:
        feed = manager.add_feed(
            url=url,
            title=title,
            category=category,
            fetch_interval=interval_enum,
            validate_url=validate,
        )

        if json_output:
            _output_json(_feed_to_dict(feed))
        else:
            console.print("[green]Feed registered successfully[/green]")
            console.print(f"  Feed ID: {feed.feed_id}")
            console.print(f"  Title: {feed.title}")
            console.print(f"  URL: {feed.url}")

        logger.info("Feed added successfully", feed_id=feed.feed_id)

    except FeedAlreadyExistsError as e:
        _handle_error(e, "Feed already exists", json_output, url=url)

    except InvalidURLError as e:
        _handle_error(e, "Invalid URL", json_output, url=url)

    except FeedFetchError as e:
        _handle_error(e, "URL validation failed", json_output, url=url)

    except RSSError as e:
        _handle_error(e, "RSS error", json_output)


@cli.command(name="list")
@click.option("--category", default=None, help="Filter by category")
@click.option("--enabled-only", is_flag=True, help="Show only enabled feeds")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def list_feeds(
    ctx: click.Context,
    category: str | None,
    enabled_only: bool,
    json_output: bool,
) -> None:
    """List registered feeds."""
    logger.info("Listing feeds", category=category, enabled_only=enabled_only)

    data_dir = _get_data_dir(ctx)
    manager = FeedManager(data_dir)

    feeds = manager.list_feeds(category=category, enabled_only=enabled_only)

    if json_output:
        _output_json([_feed_to_dict(f) for f in feeds])
    else:
        if not feeds:
            console.print("[yellow]No feeds found[/yellow]")
            return

        table = Table(title="Registered Feeds")
        table.add_column("ID", style="cyan", max_width=8)
        table.add_column("Title", style="green")
        table.add_column("Category")
        table.add_column("Interval")
        table.add_column("Status")
        table.add_column("Enabled")

        for feed in feeds:
            status_style = "green" if feed.last_status.value == "success" else "red"
            enabled_text = "Yes" if feed.enabled else "No"
            table.add_row(
                feed.feed_id[:8],
                _truncate(feed.title, 30),
                feed.category,
                feed.fetch_interval.value,
                f"[{status_style}]{feed.last_status.value}[/{status_style}]",
                enabled_text,
            )

        console.print(table)
        console.print(f"\nTotal: {len(feeds)} feeds")

    logger.info("Feeds listed", count=len(feeds))


@cli.command()
@click.argument("feed_id")
@click.option("--title", default=None, help="New title")
@click.option("--category", default=None, help="New category")
@click.option(
    "--interval",
    type=click.Choice(["daily", "weekly", "manual"]),
    default=None,
    help="New fetch interval",
)
@click.option("--enabled/--disabled", default=None, help="Enable/disable feed")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def update(
    ctx: click.Context,
    feed_id: str,
    title: str | None,
    category: str | None,
    interval: str | None,
    enabled: bool | None,
    json_output: bool,
) -> None:
    """Update feed information."""
    logger.info("Updating feed", feed_id=feed_id)

    data_dir = _get_data_dir(ctx)
    manager = FeedManager(data_dir)

    interval_enum = FetchInterval(interval) if interval else None

    try:
        feed = manager.update_feed(
            feed_id,
            title=title,
            category=category,
            fetch_interval=interval_enum,
            enabled=enabled,
        )

        if json_output:
            _output_json(_feed_to_dict(feed))
        else:
            console.print("[green]Feed updated successfully[/green]")
            console.print(f"  Feed ID: {feed.feed_id}")
            console.print(f"  Title: {feed.title}")
            console.print(f"  Category: {feed.category}")

        logger.info("Feed updated successfully", feed_id=feed_id)

    except FeedNotFoundError as e:
        _handle_error(e, "Feed not found", json_output, feed_id=feed_id)

    except RSSError as e:
        _handle_error(e, "RSS error", json_output)


@cli.command()
@click.argument("feed_id")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def remove(
    ctx: click.Context,
    feed_id: str,
    json_output: bool,
) -> None:
    """Remove a feed."""
    logger.info("Removing feed", feed_id=feed_id)

    data_dir = _get_data_dir(ctx)
    manager = FeedManager(data_dir)

    try:
        manager.remove_feed(feed_id)

        if json_output:
            _output_json({"status": "removed", "feed_id": feed_id})
        else:
            console.print("[green]Feed removed successfully[/green]")
            console.print(f"  Feed ID: {feed_id}")

        logger.info("Feed removed successfully", feed_id=feed_id)

    except FeedNotFoundError as e:
        _handle_error(e, "Feed not found", json_output, feed_id=feed_id)

    except RSSError as e:
        _handle_error(e, "RSS error", json_output)


@cli.command()
@click.argument("feed_id", required=False)
@click.option("--all", "fetch_all", is_flag=True, help="Fetch all feeds")
@click.option("--category", default=None, help="Filter by category (with --all)")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def fetch(  # noqa: PLR0912, PLR0915
    ctx: click.Context,
    feed_id: str | None,
    fetch_all: bool,
    category: str | None,
    json_output: bool,
) -> None:
    """Fetch feed content."""
    if not feed_id and not fetch_all:
        if json_output:
            _output_json({"error": "Specify feed_id or --all"})
        else:
            console.print("[red]Error: Specify feed_id or --all[/red]")
        sys.exit(1)

    data_dir = _get_data_dir(ctx)
    fetcher = FeedFetcher(data_dir)

    try:
        if fetch_all:
            logger.info("Fetching all feeds", category=category)
            results = fetcher.fetch_all(category=category)

            if json_output:
                _output_json([_result_to_dict(r) for r in results])
            else:
                if not results:
                    console.print("[yellow]No feeds to fetch[/yellow]")
                    return

                table = Table(title="Fetch Results")
                table.add_column("Feed ID", style="cyan", max_width=8)
                table.add_column("Status")
                table.add_column("Items")
                table.add_column("New")
                table.add_column("Error")

                for result in results:
                    status_text = (
                        "[green]OK[/green]" if result.success else "[red]FAIL[/red]"
                    )
                    error_text = _truncate(result.error_message, 30) or ""
                    table.add_row(
                        result.feed_id[:8],
                        status_text,
                        str(result.items_count),
                        str(result.new_items),
                        error_text,
                    )

                console.print(table)
                success = sum(1 for r in results if r.success)
                console.print(f"\nSuccess: {success}/{len(results)}")

            logger.info("Fetch all completed", total=len(results))

        else:
            logger.info("Fetching feed", feed_id=feed_id)
            result = asyncio.run(fetcher.fetch_feed(feed_id))  # type: ignore[arg-type]

            if json_output:
                _output_json(_result_to_dict(result))
            elif result.success:
                console.print("[green]Feed fetched successfully[/green]")
                console.print(f"  Feed ID: {result.feed_id}")
                console.print(f"  Total items: {result.items_count}")
                console.print(f"  New items: {result.new_items}")
            else:
                console.print("[red]Feed fetch failed[/red]")
                console.print(f"  Feed ID: {result.feed_id}")
                console.print(f"  Error: {result.error_message}")
                sys.exit(1)

            logger.info("Fetch completed", feed_id=feed_id, success=result.success)

    except FeedFetchError as e:
        _handle_error(e, "Fetch error", json_output)

    except FeedParseError as e:
        _handle_error(e, "Parse error", json_output)

    except RSSError as e:
        _handle_error(e, "RSS error", json_output)


@cli.command()
@click.argument("feed_id", required=False)
@click.option("--limit", type=int, default=10, help="Number of items to show")
@click.option("--offset", type=int, default=0, help="Number of items to skip")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def items(
    ctx: click.Context,
    feed_id: str | None,
    limit: int,
    offset: int,
    json_output: bool,
) -> None:
    """List feed items."""
    logger.info("Listing items", feed_id=feed_id, limit=limit, offset=offset)

    data_dir = _get_data_dir(ctx)
    reader = FeedReader(data_dir)

    item_list = reader.get_items(feed_id=feed_id, limit=limit, offset=offset)

    if json_output:
        _output_json([_item_to_dict(item) for item in item_list])
    else:
        if not item_list:
            console.print("[yellow]No items found[/yellow]")
            return

        table = Table(title="Feed Items")
        table.add_column("ID", style="cyan", max_width=8)
        table.add_column("Title", style="green")
        table.add_column("Published")
        table.add_column("Author")

        for item in item_list:
            pub_date = _truncate(item.published, 16) if item.published else "-"
            table.add_row(
                item.item_id[:8],
                _truncate(item.title, 40),
                pub_date,
                _truncate(item.author, 15) or "-",
            )

        console.print(table)
        console.print(f"\nShowing {len(item_list)} items")

    logger.info("Items listed", count=len(item_list))


@cli.command()
@click.option("--query", "-q", required=True, help="Search query")
@click.option("--category", default=None, help="Filter by category")
@click.option(
    "--fields",
    default="title,summary,content",
    help="Fields to search (comma-separated)",
)
@click.option("--limit", type=int, default=50, help="Maximum results")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def search(
    ctx: click.Context,
    query: str,
    category: str | None,
    fields: str,
    limit: int,
    json_output: bool,
) -> None:
    """Search feed items."""
    logger.info("Searching items", query=query, category=category, fields=fields)

    data_dir = _get_data_dir(ctx)
    reader = FeedReader(data_dir)

    field_list = [f.strip() for f in fields.split(",")]

    item_list = reader.search_items(
        query=query,
        category=category,
        fields=field_list,
        limit=limit,
    )

    if json_output:
        _output_json([_item_to_dict(item) for item in item_list])
    else:
        if not item_list:
            console.print(f"[yellow]No items found for '{query}'[/yellow]")
            return

        table = Table(title=f"Search Results for '{query}'")
        table.add_column("ID", style="cyan", max_width=8)
        table.add_column("Title", style="green")
        table.add_column("Published")
        table.add_column("Link")

        for item in item_list:
            pub_date = _truncate(item.published, 16) if item.published else "-"
            table.add_row(
                item.item_id[:8],
                _truncate(item.title, 35),
                pub_date,
                _truncate(item.link, 30),
            )

        console.print(table)
        console.print(f"\nFound {len(item_list)} items")

    logger.info("Search completed", query=query, count=len(item_list))


@cli.group()
def preset() -> None:
    """Manage preset feeds."""
    pass


@preset.command()
@click.option(
    "--file",
    "-f",
    "presets_file",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Presets file path (default: {DATA_ROOT}/config/rss-presets.json)",
)
@click.option(
    "--validate/--no-validate",
    default=False,
    help="Validate URL reachability",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def apply(
    ctx: click.Context,
    presets_file: Path | None,
    validate: bool,
    json_output: bool,
) -> None:
    """Apply preset feeds from a configuration file."""
    if presets_file is None:
        presets_file = get_path("config/rss-presets.json")
    logger.info("Applying presets", presets_file=str(presets_file), validate=validate)

    data_dir = _get_data_dir(ctx)
    manager = FeedManager(data_dir)

    try:
        result = manager.apply_presets(presets_file, validate_urls=validate)

        if json_output:
            _output_json(
                {
                    "total": result.total,
                    "added": result.added,
                    "skipped": result.skipped,
                    "failed": result.failed,
                    "errors": result.errors,
                }
            )
        else:
            console.print("[green]Presets applied successfully[/green]")
            console.print(f"  Total: {result.total}")
            console.print(f"  Added: {result.added}")
            console.print(f"  Skipped: {result.skipped}")
            console.print(f"  Failed: {result.failed}")

            if result.errors:
                console.print("\n[yellow]Errors:[/yellow]")
                for error in result.errors:
                    console.print(f"  - {error}")

        logger.info(
            "Presets applied",
            total=result.total,
            added=result.added,
            skipped=result.skipped,
            failed=result.failed,
        )

    except FileNotFoundError as e:
        _handle_error(
            RSSError(str(e)),
            "Presets file not found",
            json_output,
            presets_file=str(presets_file),
        )

    except ValueError as e:
        _handle_error(
            RSSError(str(e)),
            "Invalid presets file",
            json_output,
            presets_file=str(presets_file),
        )

    except RSSError as e:
        _handle_error(e, "RSS error", json_output)


@cli.command()
@click.argument("feed_id")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def info(
    ctx: click.Context,
    feed_id: str,
    json_output: bool,
) -> None:
    """Show detailed information for a single feed."""
    logger.info("Showing feed info", feed_id=feed_id)

    data_dir = _get_data_dir(ctx)
    manager = FeedManager(data_dir)
    reader = FeedReader(data_dir)

    try:
        feed = manager.get_feed(feed_id)

        item_count = len(reader.get_items(feed_id=feed_id))

        if json_output:
            data = _feed_to_dict(feed)
            data["item_count"] = item_count
            _output_json(data)
        else:
            console.print(f"[bold]Feed: {feed.title}[/bold]")
            console.print(f"  ID:        {feed.feed_id}")
            console.print(f"  URL:       {feed.url}")
            console.print(f"  Category:  {feed.category}")
            console.print(f"  Interval:  {feed.fetch_interval.value}")
            console.print(f"  Enabled:   {'Yes' if feed.enabled else 'No'}")
            console.print(f"  Status:    {feed.last_status.value}")
            console.print(f"  Created:   {feed.created_at or '-'}")
            console.print(f"  Updated:   {feed.updated_at or '-'}")
            console.print(f"  Fetched:   {feed.last_fetched or '-'}")
            console.print(f"  Items:     {item_count}")

        logger.info("Feed info displayed", feed_id=feed_id)

    except FeedNotFoundError as e:
        _handle_error(e, "Feed not found", json_output, feed_id=feed_id)

    except RSSError as e:
        _handle_error(e, "RSS error", json_output)


@cli.command()
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def stats(
    ctx: click.Context,
    json_output: bool,
) -> None:
    """Show feed statistics summary."""
    logger.info("Showing stats")

    data_dir = _get_data_dir(ctx)
    manager = FeedManager(data_dir)

    feeds = manager.list_feeds()

    category_counts: Counter[str] = Counter(f.category for f in feeds)
    enabled_count = sum(1 for f in feeds if f.enabled)
    disabled_count = len(feeds) - enabled_count

    last_fetched_dates = [f.last_fetched for f in feeds if f.last_fetched]
    latest_fetch = max(last_fetched_dates) if last_fetched_dates else None

    if json_output:
        _output_json(
            {
                "total_feeds": len(feeds),
                "enabled": enabled_count,
                "disabled": disabled_count,
                "categories": dict(category_counts),
                "latest_fetch": latest_fetch,
            }
        )
    else:
        console.print("[bold]RSS Feed Statistics[/bold]")
        console.print(f"  Total feeds: {len(feeds)}")
        console.print(f"  Enabled:     {enabled_count}")
        console.print(f"  Disabled:    {disabled_count}")
        console.print(f"  Latest fetch: {latest_fetch or '-'}")

        if category_counts:
            console.print("\n[bold]Categories:[/bold]")
            for cat, count in sorted(category_counts.items()):
                console.print(f"  {cat}: {count}")

    logger.info("Stats displayed", total=len(feeds))


if __name__ == "__main__":
    cli()
