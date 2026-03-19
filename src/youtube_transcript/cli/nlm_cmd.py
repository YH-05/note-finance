"""nlm subgroup commands for YouTube Transcript CLI."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

import click

from youtube_transcript._logging import get_logger
from youtube_transcript.storage.json_storage import JSONStorage

from ._cli_group import _get_data_dir, cli
from ._helpers import _output_json, console

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__)


def _build_nlm_pipeline(data_dir: Path) -> Any:
    """Build a NlmPipeline instance.

    Extracted for easy mocking in tests.

    Parameters
    ----------
    data_dir : Path
        Root directory for youtube_transcript data.

    Returns
    -------
    NlmPipeline
        Configured NlmPipeline instance.
    """
    # AIDEV-NOTE: Import here to avoid circular imports and allow test mocking.
    from youtube_transcript.services.nlm_pipeline import NlmPipeline

    return NlmPipeline(data_dir=data_dir)


def _find_transcript_by_video_id(
    storage: Any,
    video_id: str,
) -> tuple[str, Any]:
    """Look up a transcript by video_id across all channels.

    Parameters
    ----------
    storage : JSONStorage
        Storage instance to query.
    video_id : str
        YouTube video ID to search for.

    Returns
    -------
    tuple[str, TranscriptResult | None]
        (title, transcript) where transcript is None if not found.
    """
    channels = storage.load_channels()
    title = video_id
    channel_id_found: str | None = None

    for ch in channels:
        vids = storage.load_videos(ch.channel_id)
        for v in vids:
            if v.video_id == video_id:
                title = v.title
                channel_id_found = ch.channel_id
                break
        if channel_id_found:
            break

    if channel_id_found:
        return title, storage.load_transcript(channel_id_found, video_id)

    return title, None


def _nlm_add_bulk(
    pipeline: Any,
    notebook_id: str,
    channel_id: str,
    json_output: bool,
) -> None:
    """Execute bulk NLM add for all channel videos.

    Parameters
    ----------
    pipeline : NlmPipeline
        Configured NlmPipeline instance.
    notebook_id : str
        Target NotebookLM notebook ID.
    channel_id : str
        YouTube channel ID to process.
    json_output : bool
        Whether to output as JSON.
    """
    import asyncio

    results = asyncio.run(
        pipeline.bulk_add_channel(
            notebook_id=notebook_id,
            channel_id=channel_id,
        )
    )
    if json_output:
        _output_json(
            {
                "notebook_id": notebook_id,
                "channel_id": channel_id,
                "added": len(results),
            }
        )
    else:
        console.print(f"[green]Added {len(results)} sources to notebook[/green]")
        console.print(f"  Notebook ID:  {notebook_id}")
        console.print(f"  Channel ID:   {channel_id}")

    logger.info(
        "nlm add completed (bulk)",
        notebook_id=notebook_id,
        channel_id=channel_id,
        added=len(results),
    )


def _nlm_add_single(
    pipeline: Any,
    notebook_id: str,
    video_id: str,
    data_dir: Path,
    json_output: bool,
) -> None:
    """Execute single-video NLM add.

    Parameters
    ----------
    pipeline : NlmPipeline
        Configured NlmPipeline instance.
    notebook_id : str
        Target NotebookLM notebook ID.
    video_id : str
        YouTube video ID to add.
    data_dir : Path
        Root directory for youtube_transcript data.
    json_output : bool
        Whether to output as JSON.
    """
    import asyncio

    storage = JSONStorage(data_dir)
    title, transcript = _find_transcript_by_video_id(storage, video_id)

    if transcript is None:
        msg = f"Transcript not found for video '{video_id}'"
        logger.error("Transcript not found", video_id=video_id)
        if json_output:
            _output_json({"error": msg})
        else:
            console.print(f"[red]Error: {msg}[/red]")
        sys.exit(1)

    result = asyncio.run(
        pipeline.add_to_notebook(
            notebook_id=notebook_id,
            transcript=transcript,
            title=title,
        )
    )

    source_id = getattr(result, "source_id", None)

    if json_output:
        _output_json(
            {
                "notebook_id": notebook_id,
                "video_id": video_id,
                "source_id": source_id,
            }
        )
    else:
        console.print("[green]Transcript added to notebook[/green]")
        console.print(f"  Notebook ID: {notebook_id}")
        console.print(f"  Video ID:    {video_id}")
        if source_id:
            console.print(f"  Source ID:   {source_id}")

    logger.info(
        "nlm add completed (single)",
        notebook_id=notebook_id,
        video_id=video_id,
        source_id=source_id,
    )


@cli.group()
def nlm() -> None:
    """NotebookLM pipeline commands."""
    pass


@nlm.command(name="add")
@click.argument("notebook_id")
@click.option("--channel-id", default=None, help="Add all videos from this channel")
@click.option("--video-id", default=None, help="Add a single video")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def nlm_add(
    ctx: click.Context,
    notebook_id: str,
    channel_id: str | None,
    video_id: str | None,
    json_output: bool,
) -> None:
    """Add YouTube transcripts to a NotebookLM notebook.

    Specify either --channel-id (bulk) or --video-id (single).
    """
    if not channel_id and not video_id:
        msg = "Specify --channel-id <id> or --video-id <id>"
        if json_output:
            _output_json({"error": msg})
        else:
            console.print(f"[red]Error: {msg}[/red]")
        sys.exit(1)

    data_dir = _get_data_dir(ctx)
    pipeline = _build_nlm_pipeline(data_dir)

    logger.info(
        "nlm add started",
        notebook_id=notebook_id,
        channel_id=channel_id,
        video_id=video_id,
    )

    if channel_id and not video_id:
        _nlm_add_bulk(pipeline, notebook_id, channel_id, json_output)
    else:
        assert video_id is not None
        _nlm_add_single(pipeline, notebook_id, video_id, data_dir, json_output)
