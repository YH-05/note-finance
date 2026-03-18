"""YouTube Transcript collector package.

Public API
----------
Types:
    Channel
    CollectResult
    QuotaUsage
    TranscriptEntry
    TranscriptResult
    TranscriptStatus
    Video

Exceptions:
    APIError
    ChannelAlreadyExistsError
    ChannelNotFoundError
    FileLockError
    QuotaExceededError
    StorageError
    TranscriptUnavailableError
    YouTubeTranscriptError

Services:
    ChannelManager
    Collector

Core:
    ChannelFetcher
    DiffDetector
    SearchEngine
    TranscriptFetcher
    YtDlpFetcher

Storage:
    JSONStorage
    LockManager
    QuotaTracker
"""

from youtube_transcript.core.channel_fetcher import ChannelFetcher
from youtube_transcript.core.diff_detector import DiffDetector
from youtube_transcript.core.search_engine import SearchEngine, SearchResult
from youtube_transcript.core.transcript_fetcher import TranscriptFetcher
from youtube_transcript.core.yt_dlp_fetcher import YtDlpFetcher
from youtube_transcript.exceptions import (
    APIError,
    ChannelAlreadyExistsError,
    ChannelNotFoundError,
    FileLockError,
    QuotaExceededError,
    StorageError,
    TranscriptUnavailableError,
    YouTubeTranscriptError,
)
from youtube_transcript.services.channel_manager import ChannelManager
from youtube_transcript.services.collector import Collector
from youtube_transcript.storage.json_storage import JSONStorage
from youtube_transcript.storage.lock_manager import LockManager
from youtube_transcript.storage.quota_tracker import QuotaTracker
from youtube_transcript.types import (
    Channel,
    CollectResult,
    QuotaUsage,
    TranscriptEntry,
    TranscriptResult,
    TranscriptStatus,
    Video,
)

__all__ = [
    "APIError",
    "Channel",
    "ChannelAlreadyExistsError",
    "ChannelFetcher",
    "ChannelManager",
    "ChannelNotFoundError",
    "CollectResult",
    "Collector",
    "DiffDetector",
    "FileLockError",
    "JSONStorage",
    "LockManager",
    "QuotaExceededError",
    "QuotaTracker",
    "QuotaUsage",
    "SearchEngine",
    "SearchResult",
    "StorageError",
    "TranscriptEntry",
    "TranscriptFetcher",
    "TranscriptResult",
    "TranscriptStatus",
    "TranscriptUnavailableError",
    "Video",
    "YouTubeTranscriptError",
    "YtDlpFetcher",
]
