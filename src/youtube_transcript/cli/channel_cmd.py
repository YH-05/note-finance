"""channel subgroup commands for YouTube Transcript CLI."""

from __future__ import annotations

import click

from youtube_transcript._logging import get_logger
from youtube_transcript.exceptions import (
    ChannelAlreadyExistsError,
    ChannelNotFoundError,
    YouTubeTranscriptError,
)
from youtube_transcript.services.channel_manager import ChannelManager

from ._cli_group import _get_data_dir, cli
from ._helpers import (
    _channel_to_dict,
    _handle_error,
    _output_json,
    _truncate,
    console,
)

logger = get_logger(__name__)


@cli.group()
def channel() -> None:
    """Manage YouTube channels."""
    pass


@channel.command(name="add")
@click.option("--channel-id", required=True, help="YouTube channel ID or URL")
@click.option("--title", required=True, help="Channel title")
@click.option(
    "--language",
    multiple=True,
    default=["ja", "en"],
    show_default=True,
    help="Preferred transcript language (can repeat; e.g. --language ja --language en)",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def channel_add(
    ctx: click.Context,
    channel_id: str,
    title: str,
    language: tuple[str, ...],
    json_output: bool,
) -> None:
    """Register a new YouTube channel."""
    logger.info("Adding channel", channel_id=channel_id, title=title)

    data_dir = _get_data_dir(ctx)
    manager = ChannelManager(data_dir)

    try:
        ch = manager.add(
            url_or_id=channel_id,
            title=title,
            language_priority=list(language),
        )

        if json_output:
            _output_json(_channel_to_dict(ch))
        else:
            console.print("[green]Channel registered successfully[/green]")
            console.print(f"  Channel ID: {ch.channel_id}")
            console.print(f"  Title:      {ch.title}")

        logger.info("Channel added successfully", channel_id=ch.channel_id)

    except ChannelAlreadyExistsError as e:
        _handle_error(e, "Channel already exists", json_output, channel_id=channel_id)

    except YouTubeTranscriptError as e:
        _handle_error(e, "YouTube Transcript error", json_output)


@channel.command(name="list")
@click.option("--enabled-only", is_flag=True, help="Show only enabled channels")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def channel_list(
    ctx: click.Context,
    enabled_only: bool,
    json_output: bool,
) -> None:
    """List registered channels."""
    logger.info("Listing channels", enabled_only=enabled_only)

    data_dir = _get_data_dir(ctx)
    manager = ChannelManager(data_dir)

    channels = manager.list(enabled_only=enabled_only)

    if json_output:
        _output_json([_channel_to_dict(ch) for ch in channels])
        return

    if not channels:
        console.print("[yellow]No channels found[/yellow]")
        return

    from rich.table import Table

    table = Table(title="Registered Channels")
    table.add_column("Channel ID", style="cyan")
    table.add_column("Title", style="green")
    table.add_column("Enabled")
    table.add_column("Videos")
    table.add_column("Last Fetched")

    for ch in channels:
        table.add_row(
            _truncate(ch.channel_id, 24),
            _truncate(ch.title, 30),
            "Yes" if ch.enabled else "No",
            str(ch.video_count),
            ch.last_fetched or "-",
        )

    console.print(table)
    console.print(f"\nTotal: {len(channels)} channels")

    logger.info("Channels listed", count=len(channels))


@channel.command(name="remove")
@click.argument("channel_id")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def channel_remove(
    ctx: click.Context,
    channel_id: str,
    json_output: bool,
) -> None:
    """Remove a channel."""
    logger.info("Removing channel", channel_id=channel_id)

    data_dir = _get_data_dir(ctx)
    manager = ChannelManager(data_dir)

    try:
        manager.remove(channel_id)

        if json_output:
            _output_json({"status": "removed", "channel_id": channel_id})
        else:
            console.print("[green]Channel removed successfully[/green]")
            console.print(f"  Channel ID: {channel_id}")

        logger.info("Channel removed successfully", channel_id=channel_id)

    except ChannelNotFoundError as e:
        _handle_error(e, "Channel not found", json_output, channel_id=channel_id)

    except YouTubeTranscriptError as e:
        _handle_error(e, "YouTube Transcript error", json_output)
