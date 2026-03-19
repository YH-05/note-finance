"""CLI group definition for YouTube Transcript CLI."""

from __future__ import annotations

from pathlib import Path

import click

from data_paths import get_path
from youtube_transcript._logging import get_logger

logger = get_logger(__name__)

# Default data directory: NAS preferred, local fallback via data_paths
_NAS_YT_DIR = Path("/Volumes/personal_folder/scraped/youtube_transcript")
DEFAULT_DATA_DIR = _NAS_YT_DIR if _NAS_YT_DIR.parent.exists() else get_path("raw/youtube_transcript")


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
