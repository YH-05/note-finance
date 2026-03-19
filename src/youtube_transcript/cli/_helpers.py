"""Shared helper utilities for YouTube Transcript CLI."""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING, Any

import click
from rich.console import Console

from youtube_transcript._logging import get_logger

if TYPE_CHECKING:
    from youtube_transcript.exceptions import YouTubeTranscriptError
    from youtube_transcript.types import (
        Channel,
        CollectResult,
        TranscriptResult,
        Video,
    )

logger = get_logger(__name__)

# Shared console instance
console = Console()


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
