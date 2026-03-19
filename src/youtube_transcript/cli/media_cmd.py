"""videos, transcript, stats, search commands for YouTube Transcript CLI."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

import click

from youtube_transcript._logging import get_logger
from youtube_transcript.core.search_engine import SearchEngine
from youtube_transcript.services.channel_manager import ChannelManager
from youtube_transcript.storage.json_storage import JSONStorage
from youtube_transcript.storage.quota_tracker import QuotaTracker

from ._cli_group import _get_data_dir, cli
from ._helpers import (
    _output_json,
    _transcript_to_dict,
    _truncate,
    _video_to_dict,
    console,
)

if TYPE_CHECKING:
    from youtube_transcript.core.search_engine import SearchResult

logger = get_logger(__name__)


def _search_result_to_dict(result: SearchResult) -> dict[str, Any]:
    """Convert SearchResult to dictionary.

    Parameters
    ----------
    result : SearchResult
        SearchResult object to convert.

    Returns
    -------
    dict[str, Any]
        Dictionary representation of the search result.
    """
    return {
        "video_id": result.video_id,
        "channel_id": result.channel_id,
        "matched_text": result.matched_text,
        "timestamp": result.timestamp,
    }


@cli.command()
@click.argument("channel_id")
@click.option("--limit", type=int, default=20, help="Number of videos to show")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def videos(
    ctx: click.Context,
    channel_id: str,
    limit: int,
    json_output: bool,
) -> None:
    """List videos for a channel."""
    logger.info("Listing videos", channel_id=channel_id, limit=limit)

    data_dir = _get_data_dir(ctx)
    storage = JSONStorage(data_dir)

    video_list = storage.load_videos(channel_id)
    # Sort by published descending and apply limit
    video_list.sort(key=lambda v: v.published or "", reverse=True)
    video_list = video_list[:limit]

    if json_output:
        _output_json([_video_to_dict(v) for v in video_list])
        return

    if not video_list:
        console.print("[yellow]No videos found[/yellow]")
        return

    from rich.table import Table

    table = Table(title=f"Videos for {channel_id}")
    table.add_column("Video ID", style="cyan")
    table.add_column("Title", style="green")
    table.add_column("Published")
    table.add_column("Transcript")

    for v in video_list:
        table.add_row(
            v.video_id,
            _truncate(v.title, 40),
            _truncate(v.published, 16) if v.published else "-",
            v.transcript_status.value,
        )

    console.print(table)
    console.print(f"\nShowing {len(video_list)} videos")

    logger.info("Videos listed", channel_id=channel_id, count=len(video_list))


@cli.command()
@click.argument("video_id")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--plain", "plain_output", is_flag=True, help="Output as plain text")
@click.pass_context
def transcript(
    ctx: click.Context,
    video_id: str,
    json_output: bool,
    plain_output: bool,
) -> None:
    """Show transcript for a video."""
    logger.info("Loading transcript", video_id=video_id)

    data_dir = _get_data_dir(ctx)
    storage = JSONStorage(data_dir)

    # Find which channel owns this video_id
    channels = storage.load_channels()
    channel_id_found: str | None = None
    for ch in channels:
        vids = storage.load_videos(ch.channel_id)
        for v in vids:
            if v.video_id == video_id:
                channel_id_found = ch.channel_id
                break
        if channel_id_found:
            break

    if channel_id_found is None:
        # Still try a direct load with empty channel_id fallback (None check)
        result = None
    else:
        result = storage.load_transcript(channel_id_found, video_id)

    if result is None:
        msg = f"Transcript not found for video '{video_id}'"
        logger.error("Transcript not found", video_id=video_id)
        if json_output:
            _output_json({"error": msg})
        else:
            console.print(f"[red]Error: {msg}[/red]")
        sys.exit(1)

    if json_output:
        _output_json(_transcript_to_dict(result))
    elif plain_output:
        click.echo(result.to_plain_text())
    else:
        console.print(f"[bold]Transcript: {video_id}[/bold]")
        console.print(f"  Language: {result.language}")
        console.print(f"  Entries:  {len(result.entries)}")
        console.print(f"  Fetched:  {result.fetched_at}")
        console.print()
        click.echo(result.to_plain_text())

    logger.info("Transcript displayed", video_id=video_id)


@cli.command()
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def stats(
    ctx: click.Context,
    json_output: bool,
) -> None:
    """Show statistics including quota usage."""
    logger.info("Showing stats")

    data_dir = _get_data_dir(ctx)
    manager = ChannelManager(data_dir)
    quota_tracker = QuotaTracker(data_dir)

    channels = manager.list()
    enabled_count = sum(1 for ch in channels if ch.enabled)
    disabled_count = len(channels) - enabled_count
    total_videos = sum(ch.video_count for ch in channels)

    units_used = quota_tracker.today_usage()
    budget = quota_tracker.budget
    remaining = quota_tracker.remaining()

    if json_output:
        _output_json(
            {
                "total_channels": len(channels),
                "enabled": enabled_count,
                "disabled": disabled_count,
                "total_videos": total_videos,
                "quota": {
                    "units_used": units_used,
                    "budget": budget,
                    "remaining": remaining,
                },
            }
        )
    else:
        console.print("[bold]YouTube Transcript Statistics[/bold]")
        console.print(f"  Total channels: {len(channels)}")
        console.print(f"  Enabled:        {enabled_count}")
        console.print(f"  Disabled:       {disabled_count}")
        console.print(f"  Total videos:   {total_videos}")
        console.print()
        console.print("[bold]Quota Usage (Today)[/bold]")
        console.print(f"  Used:      {units_used}")
        console.print(f"  Budget:    {budget}")
        console.print(f"  Remaining: {remaining}")

    logger.info(
        "Stats displayed",
        total_channels=len(channels),
        quota_used=units_used,
    )


@cli.command()
@click.argument("query")
@click.option("--channel-id", default=None, help="Limit search to a specific channel")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def search(
    ctx: click.Context,
    query: str,
    channel_id: str | None,
    json_output: bool,
) -> None:
    """Search transcripts by keyword.

    QUERY is the keyword to search for in all stored transcripts.
    """
    logger.info("Searching transcripts", query=query, channel_id=channel_id)

    data_dir = _get_data_dir(ctx)
    engine = SearchEngine(data_dir)

    channel_ids: list[str] | None = [channel_id] if channel_id else None
    results = engine.search(query, channel_ids=channel_ids)

    if json_output:
        _output_json([_search_result_to_dict(r) for r in results])
        return

    if not results:
        console.print("[yellow]No results found[/yellow]")
        logger.info("Search completed", query=query, result_count=0)
        return

    from rich.table import Table

    table = Table(title=f'Search results for "{query}"')
    table.add_column("Video ID", style="cyan")
    table.add_column("Channel ID", style="green")
    table.add_column("Timestamp")
    table.add_column("Matched Text")

    for r in results:
        table.add_row(
            r.video_id,
            r.channel_id,
            f"{r.timestamp:.1f}s",
            _truncate(r.matched_text, 60),
        )

    console.print(table)
    console.print(f"\nTotal: {len(results)} results")

    logger.info("Search completed", query=query, result_count=len(results))
