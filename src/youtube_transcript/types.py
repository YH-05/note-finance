"""Common type definitions for the youtube_transcript package."""

from dataclasses import dataclass, field
from enum import Enum


class TranscriptStatus(str, Enum):
    """Transcript collection status.

    Attributes
    ----------
    PENDING : str
        Transcript collection has not been attempted yet.
    SUCCESS : str
        Transcript was successfully collected.
    UNAVAILABLE : str
        Transcript is not available for this video.
    FAILED : str
        Transcript collection failed due to an error.
    """

    PENDING = "pending"
    SUCCESS = "success"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


@dataclass
class Channel:
    """YouTube channel model.

    Attributes
    ----------
    channel_id : str
        YouTube channel ID (e.g., "UC_xxxxxxxxxxxxxxxxxxxx")
    title : str
        Channel title
    uploads_playlist_id : str
        ID of the channel's uploads playlist (e.g., "UU_xxxxxxxxxxxxxxxxxxxx")
    language_priority : list[str]
        Preferred transcript language codes in priority order (e.g., ["ja", "en"])
    enabled : bool
        Whether the channel is enabled for transcript collection
    created_at : str
        Creation timestamp (ISO 8601 format)
    last_fetched : str | None
        Last fetch timestamp (ISO 8601 format), None if never fetched
    video_count : int
        Number of videos tracked for this channel
    """

    channel_id: str
    title: str
    uploads_playlist_id: str
    language_priority: list[str]
    enabled: bool
    created_at: str
    last_fetched: str | None
    video_count: int


@dataclass
class Video:
    """YouTube video model.

    Attributes
    ----------
    video_id : str
        YouTube video ID (11-character string)
    channel_id : str
        YouTube channel ID
    title : str
        Video title
    published : str
        Publication timestamp (ISO 8601 format)
    description : str
        Video description
    transcript_status : TranscriptStatus
        Current transcript collection status
    transcript_language : str | None
        Language code of the collected transcript, None if not collected
    fetched_at : str | None
        Transcript fetch timestamp (ISO 8601 format), None if not fetched
    """

    video_id: str
    channel_id: str
    title: str
    published: str
    description: str
    transcript_status: TranscriptStatus
    transcript_language: str | None
    fetched_at: str | None


@dataclass
class TranscriptEntry:
    """Single transcript entry (a timed text segment).

    Attributes
    ----------
    start : float
        Start time in seconds
    duration : float
        Duration in seconds
    text : str
        Transcript text for this segment
    """

    start: float
    duration: float
    text: str


@dataclass
class TranscriptResult:
    """Complete transcript result for a video.

    Attributes
    ----------
    video_id : str
        YouTube video ID
    language : str
        Language code of the transcript (e.g., "ja", "en")
    entries : list[TranscriptEntry]
        List of timed transcript entries
    fetched_at : str
        Fetch timestamp (ISO 8601 format)
    """

    video_id: str
    language: str
    entries: list[TranscriptEntry]
    fetched_at: str

    def to_plain_text(self) -> str:
        """Convert transcript entries to a plain text string.

        Returns
        -------
        str
            All transcript entry texts joined with newlines.
            Returns an empty string if entries is empty.

        Examples
        --------
        >>> entry1 = TranscriptEntry(start=0.0, duration=3.0, text="Hello")
        >>> entry2 = TranscriptEntry(start=3.0, duration=2.0, text="world")
        >>> result = TranscriptResult(
        ...     video_id="abc",
        ...     language="en",
        ...     entries=[entry1, entry2],
        ...     fetched_at="2026-03-18T00:00:00+00:00",
        ... )
        >>> result.to_plain_text()
        'Hello\\nworld'
        """
        if not self.entries:
            return ""
        return "\n".join(entry.text for entry in self.entries)


@dataclass
class CollectResult:
    """Aggregated result of a transcript collection run.

    Attributes
    ----------
    total : int
        Total number of videos processed
    success : int
        Number of videos where transcript was successfully collected
    unavailable : int
        Number of videos where transcript was unavailable
    failed : int
        Number of videos where collection failed due to an error
    skipped : int
        Number of videos skipped (e.g., already collected, disabled)
    """

    total: int
    success: int
    unavailable: int
    failed: int
    skipped: int


@dataclass
class QuotaUsage:
    """YouTube Data API quota usage tracking.

    Attributes
    ----------
    date : str
        Date in ISO 8601 format (e.g., "2026-03-18")
    units_used : int
        Number of API quota units consumed on this date
    budget : int
        Daily quota budget (maximum units allowed)
    """

    date: str
    units_used: int
    budget: int
