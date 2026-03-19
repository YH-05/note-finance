"""kg subgroup commands for YouTube Transcript CLI."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

import click

from youtube_transcript._logging import get_logger

from ._cli_group import _get_data_dir, cli
from ._helpers import _output_json, console

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__)


def _build_kg_exporter(data_dir: Path) -> Any:
    """Build a KgExporter instance.

    Extracted for easy mocking in tests.

    Parameters
    ----------
    data_dir : Path
        Root directory for youtube_transcript data.

    Returns
    -------
    KgExporter
        Configured KgExporter instance.
    """
    # AIDEV-NOTE: Import here to avoid circular imports and allow test mocking.
    from youtube_transcript.services.kg_exporter import KgExporter

    return KgExporter(data_dir=data_dir)


@cli.group()
def kg() -> None:
    """Knowledge graph export commands."""
    pass


@kg.command(name="export")
@click.option("--channel-id", default=None, help="Export all videos from this channel")
@click.option(
    "--video-id",
    default=None,
    help="Export a single video (requires --channel-id)",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def kg_export(
    ctx: click.Context,
    channel_id: str | None,
    video_id: str | None,
    json_output: bool,
) -> None:
    """Export YouTube transcripts to graph-queue JSON for Neo4j ingestion.

    Generates graph-queue JSON files in .tmp/graph-queue/youtube_transcript/.
    Use the /save-to-graph skill to ingest the generated files into Neo4j.
    """
    if not channel_id:
        msg = "Specify --channel-id <id>"
        if json_output:
            _output_json({"error": msg})
        else:
            console.print(f"[red]Error: {msg}[/red]")
        sys.exit(1)

    data_dir = _get_data_dir(ctx)
    exporter = _build_kg_exporter(data_dir)

    logger.info(
        "kg export started",
        channel_id=channel_id,
        video_id=video_id,
    )

    output_paths = exporter.export_channel(
        channel_id=channel_id,
        video_id=video_id,
    )

    if json_output:
        _output_json(
            {
                "channel_id": channel_id,
                "video_id": video_id,
                "exported": len(output_paths),
                "files": [str(p) for p in output_paths],
            }
        )
    else:
        console.print(
            f"[green]Exported {len(output_paths)} graph-queue file(s)[/green]"
        )
        console.print(f"  Channel ID: {channel_id}")
        if video_id:
            console.print(f"  Video ID:   {video_id}")
        for p in output_paths:
            console.print(f"  -> {p}")

    logger.info(
        "kg export completed",
        channel_id=channel_id,
        video_id=video_id,
        exported=len(output_paths),
    )
