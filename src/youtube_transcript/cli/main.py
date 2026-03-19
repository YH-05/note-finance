"""YouTube Transcript CLI main module.

This module provides the command-line interface for the YouTube Transcript
collector (yt-transcript command).

Implements the following commands:
- yt-transcript channel add/list/remove
- yt-transcript collect [--channel-id | --all]
- yt-transcript videos <channel_id>
- yt-transcript transcript <video_id> [--json | --plain]
- yt-transcript stats
- yt-transcript nlm add <notebook_id>
- yt-transcript kg export

References
----------
- Modelled after src/rss/cli/main.py

Implementation
--------------
Commands are split across submodules for maintainability:
- channel_cmd.py  : channel subgroup (add/list/remove)
- collect_cmd.py  : collect command
- media_cmd.py    : videos, transcript, stats, search
- nlm_cmd.py      : nlm subgroup
- kg_cmd.py       : kg subgroup
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Re-exports for test patching compatibility
# (tests patch "youtube_transcript.cli.main.X" where X is used in submodules)
# ---------------------------------------------------------------------------
from youtube_transcript.core.search_engine import SearchEngine
from youtube_transcript.services.channel_manager import ChannelManager
from youtube_transcript.storage.json_storage import JSONStorage
from youtube_transcript.storage.quota_tracker import QuotaTracker

# ---------------------------------------------------------------------------
# Register all subgroups and commands by importing their modules.
# The @cli.group() / @cli.command() decorators run on import and register
# each command on the shared `cli` group object from _cli_group.py.
# ---------------------------------------------------------------------------
from . import channel_cmd, collect_cmd, kg_cmd, media_cmd, nlm_cmd
from ._cli_group import DEFAULT_DATA_DIR, _get_data_dir, cli

# Import builder functions so tests can patch "youtube_transcript.cli.main._build_*"
from .collect_cmd import _build_collector, _build_retry_service
from .kg_cmd import _build_kg_exporter
from .nlm_cmd import _build_nlm_pipeline

if __name__ == "__main__":
    cli()
