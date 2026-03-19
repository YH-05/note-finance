"""JSON storage for youtube_transcript data.

This module provides JSON-based persistence for the 3-tier hierarchy:
  - channels.json  (global channel registry)
  - {channel_id}/videos.json  (per-channel video list)
  - {channel_id}/{video_id}/transcript.json  (per-video transcript)
  - quota_usage.json  (API quota tracking)

All operations use file locking to ensure safe concurrent access.
"""

import json
from dataclasses import asdict
from pathlib import Path

from youtube_transcript._errors import log_and_reraise
from youtube_transcript._logging import get_logger
from youtube_transcript.exceptions import StorageError
from youtube_transcript.storage.lock_manager import LockManager
from youtube_transcript.types import (
    Channel,
    QuotaUsage,
    TranscriptEntry,
    TranscriptResult,
    TranscriptStatus,
    Video,
)

logger = get_logger(__name__)


class JSONStorage:
    """JSON storage for youtube_transcript data.

    This class provides CRUD operations for all 3 tiers of the data hierarchy
    plus quota tracking, using JSON files with file locking for safe concurrent
    access.

    Parameters
    ----------
    data_dir : Path
        Root directory for youtube_transcript data (e.g., data/raw/youtube_transcript/)

    Attributes
    ----------
    data_dir : Path
        Root directory for youtube_transcript data
    lock_manager : LockManager
        File lock manager for concurrent access control

    Examples
    --------
    >>> from pathlib import Path
    >>> storage = JSONStorage(Path("data/raw/youtube_transcript"))
    >>> channels = storage.load_channels()
    >>> len(channels)
    0
    """

    def __init__(self, data_dir: Path) -> None:
        """Initialize JSONStorage.

        Parameters
        ----------
        data_dir : Path
            Root directory for youtube_transcript data

        Raises
        ------
        ValueError
            If data_dir is not a Path object
        """
        if not isinstance(data_dir, Path):  # type: ignore[reportUnnecessaryIsInstance]
            logger.error(
                "Invalid data_dir type",
                data_dir=str(data_dir),
                expected_type="Path",
                actual_type=type(data_dir).__name__,
            )
            raise ValueError(f"data_dir must be a Path object, got {type(data_dir)}")

        self.data_dir = data_dir
        self.lock_manager = LockManager(data_dir)
        logger.debug("JSONStorage initialized", data_dir=str(data_dir))

    # ------------------------------------------------------------------
    # Channels CRUD
    # ------------------------------------------------------------------

    def save_channels(self, channels: list[Channel]) -> None:
        """Save channel registry to channels.json.

        Parameters
        ----------
        channels : list[Channel]
            List of channels to persist

        Raises
        ------
        StorageError
            If JSON serialization or file write fails

        Examples
        --------
        >>> from pathlib import Path
        >>> storage = JSONStorage(Path("data/raw/youtube_transcript"))
        >>> storage.save_channels([])
        """
        channels_file = self.data_dir / "channels.json"

        logger.debug(
            "Saving channels",
            channels_file=str(channels_file),
            channels_count=len(channels),
        )

        self.data_dir.mkdir(parents=True, exist_ok=True)

        with (
            log_and_reraise(
                logger,
                f"save channels to {channels_file}",
                context={"channels_file": str(channels_file)},
                reraise_as=StorageError,
            ),
            self.lock_manager.lock_channels(),
        ):
            data = [asdict(ch) for ch in channels]
            channels_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        logger.info(
            "Channels saved successfully",
            channels_file=str(channels_file),
            channels_count=len(channels),
        )

    def load_channels(self) -> list[Channel]:
        """Load channel registry from channels.json.

        Returns
        -------
        list[Channel]
            Loaded channels, or empty list if file does not exist

        Raises
        ------
        StorageError
            If JSON deserialization fails

        Examples
        --------
        >>> from pathlib import Path
        >>> storage = JSONStorage(Path("data/raw/youtube_transcript"))
        >>> channels = storage.load_channels()
        >>> len(channels)
        0
        """
        channels_file = self.data_dir / "channels.json"

        logger.debug("Loading channels", channels_file=str(channels_file))

        if not channels_file.exists():
            logger.info(
                "Channels file not found, returning empty list",
                channels_file=str(channels_file),
            )
            return []

        with (
            log_and_reraise(
                logger,
                f"load channels from {channels_file}",
                context={"channels_file": str(channels_file)},
                reraise_as=StorageError,
            ),
            self.lock_manager.lock_channels(),
        ):
            content = channels_file.read_text(encoding="utf-8")
            data = json.loads(content)
            channels = [Channel(**ch) for ch in data]

        logger.info(
            "Channels loaded successfully",
            channels_file=str(channels_file),
            channels_count=len(channels),
        )

        return channels

    # ------------------------------------------------------------------
    # Videos CRUD
    # ------------------------------------------------------------------

    def save_videos(self, channel_id: str, videos: list[Video]) -> None:
        """Save video list for a channel to {channel_id}/videos.json.

        Parameters
        ----------
        channel_id : str
            YouTube channel ID
        videos : list[Video]
            List of videos to persist

        Raises
        ------
        ValueError
            If channel_id is empty
        StorageError
            If JSON serialization or file write fails

        Examples
        --------
        >>> from pathlib import Path
        >>> storage = JSONStorage(Path("data/raw/youtube_transcript"))
        >>> storage.save_videos("UC_123", [])
        """
        if not channel_id:
            logger.error("Invalid channel_id", channel_id=channel_id)
            raise ValueError("channel_id cannot be empty")

        channel_dir = self.data_dir / channel_id
        videos_file = channel_dir / "videos.json"

        logger.debug(
            "Saving videos",
            channel_id=channel_id,
            videos_file=str(videos_file),
            videos_count=len(videos),
        )

        channel_dir.mkdir(parents=True, exist_ok=True)

        with (
            log_and_reraise(
                logger,
                f"save videos for channel {channel_id}",
                context={"channel_id": channel_id, "videos_file": str(videos_file)},
                reraise_as=StorageError,
            ),
            self.lock_manager.lock_videos(channel_id),
        ):
            data = []
            for v in videos:
                v_dict = asdict(v)
                # Serialize TranscriptStatus enum to string
                if "transcript_status" in v_dict:
                    v_dict["transcript_status"] = v_dict["transcript_status"]
                data.append(v_dict)
            videos_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        logger.info(
            "Videos saved successfully",
            channel_id=channel_id,
            videos_file=str(videos_file),
            videos_count=len(videos),
        )

    def load_videos(self, channel_id: str) -> list[Video]:
        """Load video list for a channel from {channel_id}/videos.json.

        Parameters
        ----------
        channel_id : str
            YouTube channel ID

        Returns
        -------
        list[Video]
            Loaded videos, or empty list if file does not exist

        Raises
        ------
        ValueError
            If channel_id is empty
        StorageError
            If JSON deserialization fails

        Examples
        --------
        >>> from pathlib import Path
        >>> storage = JSONStorage(Path("data/raw/youtube_transcript"))
        >>> videos = storage.load_videos("UC_123")
        >>> len(videos)
        0
        """
        if not channel_id:
            logger.error("Invalid channel_id", channel_id=channel_id)
            raise ValueError("channel_id cannot be empty")

        videos_file = self.data_dir / channel_id / "videos.json"

        logger.debug(
            "Loading videos",
            channel_id=channel_id,
            videos_file=str(videos_file),
        )

        if not videos_file.exists():
            logger.info(
                "Videos file not found, returning empty list",
                channel_id=channel_id,
                videos_file=str(videos_file),
            )
            return []

        with (
            log_and_reraise(
                logger,
                f"load videos for channel {channel_id}",
                context={"channel_id": channel_id, "videos_file": str(videos_file)},
                reraise_as=StorageError,
            ),
            self.lock_manager.lock_videos(channel_id),
        ):
            content = videos_file.read_text(encoding="utf-8")
            data = json.loads(content)
            videos = []
            for v_dict in data:
                if "transcript_status" in v_dict:
                    v_dict["transcript_status"] = TranscriptStatus(
                        v_dict["transcript_status"]
                    )
                videos.append(Video(**v_dict))

        logger.info(
            "Videos loaded successfully",
            channel_id=channel_id,
            videos_file=str(videos_file),
            videos_count=len(videos),
        )

        return videos

    # ------------------------------------------------------------------
    # Transcripts CRUD
    # ------------------------------------------------------------------

    def save_transcript(self, channel_id: str, result: TranscriptResult) -> None:
        """Save transcript to {channel_id}/{video_id}/transcript.json.

        Parameters
        ----------
        channel_id : str
            YouTube channel ID
        result : TranscriptResult
            Transcript result to persist

        Raises
        ------
        ValueError
            If channel_id is empty
        StorageError
            If JSON serialization or file write fails

        Examples
        --------
        >>> from pathlib import Path
        >>> storage = JSONStorage(Path("data/raw/youtube_transcript"))
        >>> from youtube_transcript.types import TranscriptResult, TranscriptEntry
        >>> entry = TranscriptEntry(start=0.0, duration=3.0, text="Hello")
        >>> result = TranscriptResult(
        ...     video_id="abc1234567a",
        ...     language="en",
        ...     entries=[entry],
        ...     fetched_at="2026-03-18T00:00:00+00:00",
        ... )
        >>> storage.save_transcript("UC_123", result)
        """
        if not channel_id:
            logger.error("Invalid channel_id", channel_id=channel_id)
            raise ValueError("channel_id cannot be empty")

        video_dir = self.data_dir / channel_id / result.video_id
        transcript_file = video_dir / "transcript.json"

        logger.debug(
            "Saving transcript",
            channel_id=channel_id,
            video_id=result.video_id,
            transcript_file=str(transcript_file),
            entries_count=len(result.entries),
        )

        video_dir.mkdir(parents=True, exist_ok=True)

        with (
            log_and_reraise(
                logger,
                f"save transcript for video {result.video_id}",
                context={
                    "channel_id": channel_id,
                    "video_id": result.video_id,
                    "transcript_file": str(transcript_file),
                },
                reraise_as=StorageError,
            ),
            self.lock_manager.lock_transcript(channel_id, result.video_id),
        ):
            data = asdict(result)
            transcript_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        logger.info(
            "Transcript saved successfully",
            channel_id=channel_id,
            video_id=result.video_id,
            transcript_file=str(transcript_file),
        )

    def load_transcript(
        self, channel_id: str, video_id: str
    ) -> TranscriptResult | None:
        """Load transcript from {channel_id}/{video_id}/transcript.json.

        Parameters
        ----------
        channel_id : str
            YouTube channel ID
        video_id : str
            YouTube video ID

        Returns
        -------
        TranscriptResult | None
            Loaded transcript, or None if file does not exist

        Raises
        ------
        ValueError
            If channel_id or video_id is empty
        StorageError
            If JSON deserialization fails

        Examples
        --------
        >>> from pathlib import Path
        >>> storage = JSONStorage(Path("data/raw/youtube_transcript"))
        >>> result = storage.load_transcript("UC_123", "abc1234567a")
        >>> result is None
        True
        """
        if not channel_id:
            logger.error("Invalid channel_id", channel_id=channel_id)
            raise ValueError("channel_id cannot be empty")

        if not video_id:
            logger.error("Invalid video_id", video_id=video_id)
            raise ValueError("video_id cannot be empty")

        transcript_file = self.data_dir / channel_id / video_id / "transcript.json"

        logger.debug(
            "Loading transcript",
            channel_id=channel_id,
            video_id=video_id,
            transcript_file=str(transcript_file),
        )

        if not transcript_file.exists():
            logger.info(
                "Transcript file not found, returning None",
                channel_id=channel_id,
                video_id=video_id,
                transcript_file=str(transcript_file),
            )
            return None

        with (
            log_and_reraise(
                logger,
                f"load transcript for video {video_id}",
                context={
                    "channel_id": channel_id,
                    "video_id": video_id,
                    "transcript_file": str(transcript_file),
                },
                reraise_as=StorageError,
            ),
            self.lock_manager.lock_transcript(channel_id, video_id),
        ):
            content = transcript_file.read_text(encoding="utf-8")
            data = json.loads(content)
            entries = [TranscriptEntry(**e) for e in data.get("entries", [])]
            result = TranscriptResult(
                video_id=data["video_id"],
                language=data["language"],
                entries=entries,
                fetched_at=data["fetched_at"],
            )

        logger.info(
            "Transcript loaded successfully",
            channel_id=channel_id,
            video_id=video_id,
            transcript_file=str(transcript_file),
        )

        return result

    # ------------------------------------------------------------------
    # Quota Usage CRUD
    # ------------------------------------------------------------------

    def save_quota_usage(self, quota: QuotaUsage) -> None:
        """Save quota usage to quota_usage.json.

        Parameters
        ----------
        quota : QuotaUsage
            Quota usage data to persist

        Raises
        ------
        StorageError
            If JSON serialization or file write fails

        Examples
        --------
        >>> from pathlib import Path
        >>> storage = JSONStorage(Path("data/raw/youtube_transcript"))
        >>> from youtube_transcript.types import QuotaUsage
        >>> quota = QuotaUsage(date="2026-03-18", units_used=100, budget=10000)
        >>> storage.save_quota_usage(quota)
        """
        quota_file = self.data_dir / "quota_usage.json"

        logger.debug(
            "Saving quota usage",
            quota_file=str(quota_file),
            date=quota.date,
            units_used=quota.units_used,
        )

        self.data_dir.mkdir(parents=True, exist_ok=True)

        with (
            log_and_reraise(
                logger,
                f"save quota usage to {quota_file}",
                context={"quota_file": str(quota_file)},
                reraise_as=StorageError,
            ),
            self.lock_manager.lock_channels(),
        ):
            data = asdict(quota)
            quota_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        logger.info(
            "Quota usage saved successfully",
            quota_file=str(quota_file),
            date=quota.date,
        )

    def load_quota_usage(self) -> QuotaUsage | None:
        """Load quota usage from quota_usage.json.

        Returns
        -------
        QuotaUsage | None
            Loaded quota usage, or None if file does not exist

        Raises
        ------
        StorageError
            If JSON deserialization fails

        Examples
        --------
        >>> from pathlib import Path
        >>> storage = JSONStorage(Path("data/raw/youtube_transcript"))
        >>> quota = storage.load_quota_usage()
        >>> quota is None
        True
        """
        quota_file = self.data_dir / "quota_usage.json"

        logger.debug("Loading quota usage", quota_file=str(quota_file))

        if not quota_file.exists():
            logger.info(
                "Quota usage file not found, returning None",
                quota_file=str(quota_file),
            )
            return None

        with (
            log_and_reraise(
                logger,
                f"load quota usage from {quota_file}",
                context={"quota_file": str(quota_file)},
                reraise_as=StorageError,
            ),
            self.lock_manager.lock_channels(),
        ):
            content = quota_file.read_text(encoding="utf-8")
            data = json.loads(content)
            quota = QuotaUsage(**data)

        logger.info(
            "Quota usage loaded successfully",
            quota_file=str(quota_file),
            date=quota.date,
        )

        return quota
