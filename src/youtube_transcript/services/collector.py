"""Transcript collection orchestrator for YouTube channels.

This module provides the Collector class, which orchestrates the 5-step
transcript collection flow:

  1. Fetch video list from YouTube (ChannelFetcher.list_all_videos)
  2. Detect diff (DiffDetector.detect_new)
  3. Fetch transcripts (TranscriptFetcher.fetch)
  4. Save results (JSONStorage)
  5. Return CollectResult

References
----------
- Modelled after src/rss/services/feed_fetcher.py
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from youtube_transcript._logging import get_logger
from youtube_transcript.core.diff_detector import DiffDetector
from youtube_transcript.exceptions import (
    ChannelNotFoundError,
    QuotaExceededError,
)
from youtube_transcript.storage.json_storage import JSONStorage
from youtube_transcript.types import (
    Channel,
    CollectResult,
    TranscriptStatus,
    Video,
)

logger = get_logger(__name__)


class Collector:
    """Orchestrator for YouTube transcript collection.

    Coordinates ChannelFetcher, DiffDetector, TranscriptFetcher, and
    JSONStorage to execute the 5-step collection flow for one or all
    channels.

    Parameters
    ----------
    data_dir : Path
        Root directory for youtube_transcript data.
    channel_fetcher : Any
        :class:`~youtube_transcript.core.channel_fetcher.ChannelFetcher`
        instance (or compatible mock).  Must implement
        ``list_all_videos(channel_id, uploads_playlist_id) -> list[Video]``.
    transcript_fetcher : Any
        :class:`~youtube_transcript.core.transcript_fetcher.TranscriptFetcher`
        instance (or compatible mock).  Must implement
        ``fetch(video_id, languages) -> TranscriptResult | None``.
    quota_tracker : Any
        :class:`~youtube_transcript.storage.quota_tracker.QuotaTracker`
        instance (or compatible mock).  Must implement
        ``remaining() -> int``.

    Examples
    --------
    >>> from pathlib import Path
    >>> from youtube_transcript.core.channel_fetcher import ChannelFetcher
    >>> from youtube_transcript.core.transcript_fetcher import TranscriptFetcher
    >>> from youtube_transcript.storage.quota_tracker import QuotaTracker
    >>> data_dir = Path("data/raw/youtube_transcript")
    >>> tracker = QuotaTracker(data_dir)
    >>> collector = Collector(
    ...     data_dir=data_dir,
    ...     channel_fetcher=ChannelFetcher(api_key="key", quota_tracker=tracker),
    ...     transcript_fetcher=TranscriptFetcher(),
    ...     quota_tracker=tracker,
    ... )
    >>> result = collector.collect("UCabc123")
    >>> print(result.success)
    """

    def __init__(
        self,
        data_dir: Path,
        channel_fetcher: Any,
        transcript_fetcher: Any,
        quota_tracker: Any,
    ) -> None:
        """Initialise Collector.

        Parameters
        ----------
        data_dir : Path
            Root directory for youtube_transcript data.
        channel_fetcher : Any
            ChannelFetcher-compatible object.
        transcript_fetcher : Any
            TranscriptFetcher-compatible object.
        quota_tracker : Any
            QuotaTracker-compatible object.

        Raises
        ------
        ValueError
            If data_dir is not a Path object.
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
        self._storage = JSONStorage(data_dir)
        self._channel_fetcher = channel_fetcher
        self._transcript_fetcher = transcript_fetcher
        self._quota_tracker = quota_tracker
        self._diff_detector = DiffDetector()

        logger.debug("Collector initialized", data_dir=str(data_dir))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def collect(self, channel_id: str) -> CollectResult:
        """Execute the 5-step transcript collection flow for one channel.

        Step 1: Fetch all videos from YouTube via ChannelFetcher.
        Step 2: Detect new videos (diff against stored list).
        Step 3: Fetch transcripts for new videos.
        Step 4: Save transcripts and update video statuses.
        Step 5: Return aggregated CollectResult.

        Parameters
        ----------
        channel_id : str
            YouTube channel ID (e.g., ``"UCabc123"``).

        Returns
        -------
        CollectResult
            Aggregated result of the collection run.

        Raises
        ------
        ChannelNotFoundError
            If no channel with the given ID is registered in storage.

        Examples
        --------
        >>> result = collector.collect("UCabc123")
        >>> print(f"Success: {result.success}, Unavailable: {result.unavailable}")
        """
        logger.info("Starting collection", channel_id=channel_id)

        # Load channel from storage (raises ChannelNotFoundError if missing)
        channel = self._load_channel(channel_id)

        # Step 1: Fetch video list
        try:
            fetched_videos = self._channel_fetcher.list_all_videos(
                channel.channel_id, channel.uploads_playlist_id
            )
        except QuotaExceededError:
            logger.warning(
                "Quota exceeded while fetching video list; skipping channel",
                channel_id=channel_id,
            )
            return CollectResult(
                total=0,
                success=0,
                unavailable=0,
                failed=0,
                skipped=1,
            )

        # Step 2: Detect new videos
        existing_videos = self._storage.load_videos(channel_id)
        new_videos = self._diff_detector.detect_new(
            existing=existing_videos, fetched=fetched_videos
        )

        logger.info(
            "Diff detection complete",
            channel_id=channel_id,
            fetched_count=len(fetched_videos),
            existing_count=len(existing_videos),
            new_count=len(new_videos),
        )

        if not new_videos:
            return CollectResult(
                total=0,
                success=0,
                unavailable=0,
                failed=0,
                skipped=0,
            )

        # Steps 3 & 4: Fetch transcripts and save
        result = self._collect_transcripts(channel, new_videos, existing_videos)

        logger.info(
            "Collection complete",
            channel_id=channel_id,
            total=result.total,
            success=result.success,
            unavailable=result.unavailable,
            failed=result.failed,
            skipped=result.skipped,
        )

        return result

    def collect_all(self) -> list[CollectResult]:
        """Execute transcript collection for all enabled channels.

        Processes channels sequentially.  If quota is exceeded during any
        individual channel's collection, that channel is recorded as skipped
        but the loop continues for remaining channels.

        Returns
        -------
        list[CollectResult]
            One CollectResult per enabled channel.

        Examples
        --------
        >>> results = collector.collect_all()
        >>> total_success = sum(r.success for r in results)
        """
        channels = self._storage.load_channels()
        enabled = [ch for ch in channels if ch.enabled]

        logger.info(
            "Starting collect_all",
            total_channels=len(channels),
            enabled_channels=len(enabled),
        )

        results: list[CollectResult] = []

        for channel in enabled:
            logger.info(
                "Processing channel",
                channel_id=channel.channel_id,
                title=channel.title,
            )
            result = self.collect(channel.channel_id)
            results.append(result)

        logger.info(
            "collect_all complete",
            channels_processed=len(results),
        )

        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_channel(self, channel_id: str) -> Channel:
        """Load channel from storage or raise ChannelNotFoundError.

        Parameters
        ----------
        channel_id : str
            YouTube channel ID.

        Returns
        -------
        Channel
            The channel from storage.

        Raises
        ------
        ChannelNotFoundError
            If the channel does not exist in storage.
        """
        channels = self._storage.load_channels()
        for ch in channels:
            if ch.channel_id == channel_id:
                return ch
        raise ChannelNotFoundError(f"Channel '{channel_id}' not found")

    def _collect_transcripts(
        self,
        channel: Channel,
        new_videos: list[Video],
        existing_videos: list[Video],
    ) -> CollectResult:
        """Fetch transcripts for new_videos and persist results.

        Parameters
        ----------
        channel : Channel
            The channel being processed.
        new_videos : list[Video]
            Videos detected as new (not in existing_videos).
        existing_videos : list[Video]
            Videos already in storage.

        Returns
        -------
        CollectResult
            Aggregated result for this batch.
        """
        total = len(new_videos)
        success = 0
        unavailable = 0
        failed = 0
        skipped = 0

        # Build a mutable dict of all videos by ID for efficient update
        video_map: dict[str, Video] = {v.video_id: v for v in existing_videos}
        # Add new videos to the map
        for v in new_videos:
            video_map[v.video_id] = v

        now_str = datetime.now(UTC).isoformat()

        for video in new_videos:
            try:
                result = self._transcript_fetcher.fetch(
                    video.video_id,
                    languages=channel.language_priority,
                )
            except Exception:
                logger.exception(
                    "Unexpected error fetching transcript",
                    channel_id=channel.channel_id,
                    video_id=video.video_id,
                )
                failed += 1
                video.transcript_status = TranscriptStatus.FAILED
                video_map[video.video_id] = video
                continue

            if result is not None:
                # Step 4: Save transcript
                self._storage.save_transcript(channel.channel_id, result)

                # Update video status
                video.transcript_status = TranscriptStatus.SUCCESS
                video.transcript_language = result.language
                video.fetched_at = result.fetched_at
                success += 1

                logger.debug(
                    "Transcript saved",
                    channel_id=channel.channel_id,
                    video_id=video.video_id,
                    language=result.language,
                )
            else:
                video.transcript_status = TranscriptStatus.UNAVAILABLE
                unavailable += 1

                logger.debug(
                    "Transcript unavailable",
                    channel_id=channel.channel_id,
                    video_id=video.video_id,
                )

            video_map[video.video_id] = video

        # Step 4 (continued): Save updated video list
        all_videos = list(video_map.values())
        self._storage.save_videos(channel.channel_id, all_videos)

        # Update channel.video_count and last_fetched
        channels = self._storage.load_channels()
        for i, ch in enumerate(channels):
            if ch.channel_id == channel.channel_id:
                ch.video_count = len(all_videos)
                ch.last_fetched = now_str
                channels[i] = ch
                break
        self._storage.save_channels(channels)

        return CollectResult(
            total=total,
            success=success,
            unavailable=unavailable,
            failed=failed,
            skipped=skipped,
        )
