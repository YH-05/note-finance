"""Diff detector for YouTube video lists."""

from typing import Any

from ..types import Video


def _get_logger() -> Any:
    """Lazy-initialize logger to avoid circular imports."""
    try:
        from youtube_transcript._logging import get_logger

        return get_logger(__name__, module="diff_detector")
    except ImportError:
        import logging

        return logging.getLogger(__name__)


logger: Any = _get_logger()


class DiffDetector:
    """Detect new videos by comparing existing and fetched video lists.

    Identifies new :class:`~youtube_transcript.types.Video` objects by
    comparing ``video_id`` fields using an O(n) set-difference approach.

    Examples
    --------
    >>> from youtube_transcript.types import TranscriptStatus, Video
    >>> detector = DiffDetector()
    >>> existing = [
    ...     Video(
    ...         video_id="aaa1111",
    ...         channel_id="UC_test",
    ...         title="Old Video",
    ...         published="2026-01-01T00:00:00+00:00",
    ...         description="",
    ...         transcript_status=TranscriptStatus.PENDING,
    ...         transcript_language=None,
    ...         fetched_at=None,
    ...     )
    ... ]
    >>> fetched = existing + [
    ...     Video(
    ...         video_id="bbb2222",
    ...         channel_id="UC_test",
    ...         title="New Video",
    ...         published="2026-03-18T00:00:00+00:00",
    ...         description="",
    ...         transcript_status=TranscriptStatus.PENDING,
    ...         transcript_language=None,
    ...         fetched_at=None,
    ...     )
    ... ]
    >>> new_videos = detector.detect_new(existing=existing, fetched=fetched)
    >>> len(new_videos)
    1
    >>> new_videos[0].video_id
    'bbb2222'
    """

    def __init__(self) -> None:
        """Initialize DiffDetector."""
        logger.debug("DiffDetector initialized")

    def detect_new(
        self,
        existing: list[Video],
        fetched: list[Video],
    ) -> list[Video]:
        """Return videos in *fetched* whose ``video_id`` is not in *existing*.

        Uses an O(n) set-difference: builds a set of ``video_id`` values from
        *existing* then filters *fetched* in a single pass.  The order of the
        returned list matches the order of *fetched*.

        Parameters
        ----------
        existing : list[Video]
            Videos already stored / known.
        fetched : list[Video]
            Videos retrieved from the latest API/RSS poll.

        Returns
        -------
        list[Video]
            Newly discovered videos (subset of *fetched*), preserving order.

        Examples
        --------
        >>> detector = DiffDetector()
        >>> new = detector.detect_new(existing=[], fetched=[])
        >>> new
        []
        """
        logger.debug(
            "差分検出開始",
            existing_count=len(existing),
            fetched_count=len(fetched),
        )

        existing_ids: set[str] = {video.video_id for video in existing}
        new_videos = [video for video in fetched if video.video_id not in existing_ids]

        logger.info(
            "差分検出完了",
            existing_count=len(existing),
            fetched_count=len(fetched),
            new_count=len(new_videos),
        )

        return new_videos
