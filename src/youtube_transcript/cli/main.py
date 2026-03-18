"""YouTube Transcript CLI main module.

This module provides the command-line interface for the YouTube Transcript
collector (yt-transcript command).

Implements the following commands:
- yt-transcript channel add/list/remove
- yt-transcript collect [--channel-id | --all]
- yt-transcript videos <channel_id>
- yt-transcript transcript <video_id> [--json | --plain]
- yt-transcript stats

References
----------
- Modelled after src/rss/cli/main.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
from rich.console import Console
from rich.table import Table

from data_paths import get_path
from youtube_transcript._logging import get_logger
from youtube_transcript.core.search_engine import SearchEngine
from youtube_transcript.exceptions import (
    ChannelAlreadyExistsError,
    ChannelNotFoundError,
    YouTubeTranscriptError,
)
from youtube_transcript.services.channel_manager import ChannelManager
from youtube_transcript.storage.json_storage import JSONStorage
from youtube_transcript.storage.quota_tracker import QuotaTracker

if TYPE_CHECKING:
    from youtube_transcript.core.search_engine import SearchResult
    from youtube_transcript.types import (
        Channel,
        CollectResult,
        TranscriptResult,
        Video,
    )

logger = get_logger(__name__)

# Default data directory (resolved via data_paths)
DEFAULT_DATA_DIR = get_path("raw/youtube_transcript")

# Console for rich output
console = Console()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _output_json(data: dict[str, Any] | list[dict[str, Any]]) -> None:
    """Output data as JSON.

    Parameters
    ----------
    data : dict[str, Any] | list[dict[str, Any]]
        Data to output as JSON string.
    """
    click.echo(json.dumps(data, ensure_ascii=False, indent=2))


def _channel_to_dict(channel: Channel) -> dict[str, Any]:
    """Convert Channel to dictionary.

    Parameters
    ----------
    channel : Channel
        Channel object to convert.

    Returns
    -------
    dict[str, Any]
        Dictionary representation of the channel.
    """
    return {
        "channel_id": channel.channel_id,
        "title": channel.title,
        "uploads_playlist_id": channel.uploads_playlist_id,
        "language_priority": channel.language_priority,
        "enabled": channel.enabled,
        "created_at": channel.created_at,
        "last_fetched": channel.last_fetched,
        "video_count": channel.video_count,
    }


def _video_to_dict(video: Video) -> dict[str, Any]:
    """Convert Video to dictionary.

    Parameters
    ----------
    video : Video
        Video object to convert.

    Returns
    -------
    dict[str, Any]
        Dictionary representation of the video.
    """
    return {
        "video_id": video.video_id,
        "channel_id": video.channel_id,
        "title": video.title,
        "published": video.published,
        "description": video.description,
        "transcript_status": video.transcript_status.value,
        "transcript_language": video.transcript_language,
        "fetched_at": video.fetched_at,
    }


def _transcript_to_dict(transcript: TranscriptResult) -> dict[str, Any]:
    """Convert TranscriptResult to dictionary.

    Parameters
    ----------
    transcript : TranscriptResult
        TranscriptResult object to convert.

    Returns
    -------
    dict[str, Any]
        Dictionary representation of the transcript.
    """
    return {
        "video_id": transcript.video_id,
        "language": transcript.language,
        "entries": [
            {
                "start": e.start,
                "duration": e.duration,
                "text": e.text,
            }
            for e in transcript.entries
        ],
        "fetched_at": transcript.fetched_at,
    }


def _collect_result_to_dict(result: CollectResult) -> dict[str, Any]:
    """Convert CollectResult to dictionary.

    Parameters
    ----------
    result : CollectResult
        CollectResult object to convert.

    Returns
    -------
    dict[str, Any]
        Dictionary representation of the collect result.
    """
    return {
        "total": result.total,
        "success": result.success,
        "unavailable": result.unavailable,
        "failed": result.failed,
        "skipped": result.skipped,
    }


def _truncate(text: str | None, max_length: int = 50) -> str:
    """Truncate text to max length.

    Parameters
    ----------
    text : str | None
        Text to truncate.
    max_length : int, default=50
        Maximum text length.

    Returns
    -------
    str
        Truncated text with ellipsis if needed.
    """
    if text is None:
        return ""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def _handle_error(
    error: YouTubeTranscriptError,
    error_type: str,
    json_output: bool,
    **log_context: Any,
) -> None:
    """Handle YouTube Transcript error with consistent logging and output.

    Parameters
    ----------
    error : YouTubeTranscriptError
        The error to handle.
    error_type : str
        Error type description for logging.
    json_output : bool
        Whether to output as JSON.
    **log_context : Any
        Additional context for logging.
    """
    logger.error(error_type, error=str(error), **log_context)
    if json_output:
        _output_json({"error": str(error)})
    else:
        console.print(f"[red]Error: {error}[/red]")
    sys.exit(1)


def _build_collector(data_dir: Path) -> Any:
    """Build a Collector instance with default dependencies.

    This function is extracted to allow easy mocking in tests.

    Parameters
    ----------
    data_dir : Path
        Root directory for youtube_transcript data.

    Returns
    -------
    Collector
        Configured collector instance.
    """
    # AIDEV-NOTE: Import here to avoid circular imports and allow test mocking.
    from youtube_transcript.core.channel_fetcher import ChannelFetcher
    from youtube_transcript.core.transcript_fetcher import TranscriptFetcher
    from youtube_transcript.services.collector import Collector

    api_key = os.environ.get("YOUTUBE_API_KEY", "")
    quota_tracker = QuotaTracker(data_dir)
    channel_fetcher = ChannelFetcher(api_key=api_key, quota_tracker=quota_tracker)
    transcript_fetcher = TranscriptFetcher()
    return Collector(
        data_dir=data_dir,
        channel_fetcher=channel_fetcher,
        transcript_fetcher=transcript_fetcher,
        quota_tracker=quota_tracker,
    )


def _build_retry_service(data_dir: Path) -> Any:
    """Build a RetryService instance with default dependencies.

    This function is extracted to allow easy mocking in tests.

    Parameters
    ----------
    data_dir : Path
        Root directory for youtube_transcript data.

    Returns
    -------
    RetryService
        Configured retry service instance.
    """
    # AIDEV-NOTE: Import here to avoid circular imports and allow test mocking.
    from youtube_transcript.core.transcript_fetcher import TranscriptFetcher
    from youtube_transcript.services.retry_service import RetryService

    quota_tracker = QuotaTracker(data_dir)
    transcript_fetcher = TranscriptFetcher()
    return RetryService(
        data_dir=data_dir,
        transcript_fetcher=transcript_fetcher,
        quota_tracker=quota_tracker,
    )


# ---------------------------------------------------------------------------
# CLI Group
# ---------------------------------------------------------------------------


@click.group()
@click.option(
    "--data-dir",
    type=click.Path(path_type=Path),
    default=DEFAULT_DATA_DIR,
    help="Data directory path (default: data/raw/youtube_transcript)",
)
@click.option("--quiet", "-q", is_flag=True, help="Suppress log output")
@click.option("--verbose", "-v", is_flag=True, help="Enable DEBUG log output")
@click.pass_context
def cli(ctx: click.Context, data_dir: Path, quiet: bool, verbose: bool) -> None:
    """YouTube Transcript Collector CLI.

    Manage YouTube channels and collect transcripts.
    """
    import logging

    ctx.ensure_object(dict)
    ctx.obj["data_dir"] = data_dir
    ctx.obj["quiet"] = quiet
    if quiet:
        logging.getLogger("youtube_transcript").setLevel(logging.CRITICAL)
    elif verbose:
        logging.getLogger("youtube_transcript").setLevel(logging.DEBUG)
    logger.debug("CLI started", data_dir=str(data_dir))


def _get_data_dir(ctx: click.Context) -> Path:
    """Get data directory from context.

    Parameters
    ----------
    ctx : click.Context
        Click context.

    Returns
    -------
    Path
        Data directory path.
    """
    return ctx.obj.get("data_dir", DEFAULT_DATA_DIR)


# ---------------------------------------------------------------------------
# channel subgroup
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# collect helpers
# ---------------------------------------------------------------------------


def _print_collect_result(result: CollectResult, title: str = "Collection") -> None:
    """Print a single CollectResult in human-readable form.

    Parameters
    ----------
    result : CollectResult
        Result to display.
    title : str, default="Collection"
        Label prefix for the output line.
    """
    console.print(f"[green]{title} complete[/green]")
    console.print(f"  Total:       {result.total}")
    console.print(f"  Success:     {result.success}")
    console.print(f"  Unavailable: {result.unavailable}")
    console.print(f"  Failed:      {result.failed}")
    console.print(f"  Skipped:     {result.skipped}")


def _print_collect_results_table(
    results: list[CollectResult], title: str = "Collection Results"
) -> None:
    """Print a list of CollectResult objects as a Rich table.

    Parameters
    ----------
    results : list[CollectResult]
        Results to display.
    title : str, default="Collection Results"
        Table title.
    """
    if not results:
        console.print("[yellow]No enabled channels found[/yellow]")
        return

    table = Table(title=title)
    table.add_column("Total")
    table.add_column("Success")
    table.add_column("Unavailable")
    table.add_column("Failed")
    table.add_column("Skipped")

    for r in results:
        table.add_row(
            str(r.total),
            str(r.success),
            str(r.unavailable),
            str(r.failed),
            str(r.skipped),
        )

    console.print(table)
    total_success = sum(r.success for r in results)
    console.print(
        f"\nChannels processed: {len(results)}, Total success: {total_success}"
    )


# ---------------------------------------------------------------------------
# collect
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--channel-id", default=None, help="Collect for a specific channel")
@click.option("--all", "collect_all", is_flag=True, help="Collect for all channels")
@click.option(
    "--retry-failed",
    "retry_failed",
    is_flag=True,
    help="Re-fetch FAILED transcripts instead of new collection",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def collect(
    ctx: click.Context,
    channel_id: str | None,
    collect_all: bool,
    retry_failed: bool,
    json_output: bool,
) -> None:
    """Collect transcripts for one or all channels."""
    if not channel_id and not collect_all:
        msg = "Specify --channel-id <id> or --all"
        if json_output:
            _output_json({"error": msg})
        else:
            console.print(f"[red]Error: {msg}[/red]")
        sys.exit(1)

    data_dir = _get_data_dir(ctx)

    if retry_failed:
        _run_retry_failed(data_dir, channel_id, collect_all, json_output)
    else:
        _run_collect(data_dir, channel_id, collect_all, json_output)


def _run_retry_failed(
    data_dir: Path,
    channel_id: str | None,
    collect_all: bool,
    json_output: bool,
) -> None:
    """Execute the --retry-failed branch of the collect command.

    Parameters
    ----------
    data_dir : Path
        Data directory.
    channel_id : str | None
        Target channel ID (used when collect_all is False).
    collect_all : bool
        Whether to retry all channels.
    json_output : bool
        Whether to output JSON.
    """
    service = _build_retry_service(data_dir)

    if collect_all:
        logger.info("Retrying FAILED transcripts for all channels")
        results = service.retry_all_failed()
        if json_output:
            _output_json([_collect_result_to_dict(r) for r in results])
        else:
            _print_collect_results_table(results, title="Retry-Failed Results")
        logger.info("Retry-failed all completed", channels=len(results))
    else:
        logger.info("Retrying FAILED transcripts for channel", channel_id=channel_id)
        result = service.retry_failed(channel_id)  # type: ignore[arg-type]
        if json_output:
            _output_json(_collect_result_to_dict(result))
        else:
            _print_collect_result(result, title="Retry-failed")
        logger.info(
            "Retry-failed completed",
            channel_id=channel_id,
            total=result.total,
            success=result.success,
        )


def _run_collect(
    data_dir: Path,
    channel_id: str | None,
    collect_all: bool,
    json_output: bool,
) -> None:
    """Execute the normal collect branch of the collect command.

    Parameters
    ----------
    data_dir : Path
        Data directory.
    channel_id : str | None
        Target channel ID (used when collect_all is False).
    collect_all : bool
        Whether to collect all channels.
    json_output : bool
        Whether to output JSON.
    """
    collector = _build_collector(data_dir)

    if collect_all:
        logger.info("Collecting all channels")
        results = collector.collect_all()
        if json_output:
            _output_json([_collect_result_to_dict(r) for r in results])
        else:
            _print_collect_results_table(results, title="Collection Results")
        logger.info("Collect all completed", channels=len(results))
    else:
        logger.info("Collecting channel", channel_id=channel_id)
        result = collector.collect(channel_id)  # type: ignore[arg-type]
        if json_output:
            _output_json(_collect_result_to_dict(result))
        else:
            _print_collect_result(result, title="Collection")
        logger.info(
            "Collect completed",
            channel_id=channel_id,
            total=result.total,
            success=result.success,
        )


# ---------------------------------------------------------------------------
# videos
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# transcript
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


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


if __name__ == "__main__":
    cli()
