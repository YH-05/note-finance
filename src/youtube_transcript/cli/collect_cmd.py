"""collect command for YouTube Transcript CLI."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

import click

from youtube_transcript._logging import get_logger
from youtube_transcript.storage.quota_tracker import QuotaTracker

from ._cli_group import _get_data_dir, cli
from ._helpers import _collect_result_to_dict, _output_json, console

if TYPE_CHECKING:
    from pathlib import Path

    from youtube_transcript.types import CollectResult

logger = get_logger(__name__)


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
    import os

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

    from rich.table import Table

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
