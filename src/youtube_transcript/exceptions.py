"""Custom exceptions for the youtube_transcript package."""


class YouTubeTranscriptError(Exception):
    """Base exception for all youtube_transcript package errors.

    This is the base class for all custom exceptions raised by the
    youtube_transcript package. All package-specific exceptions should
    inherit from this class.

    Examples
    --------
    >>> try:
    ...     raise YouTubeTranscriptError("An error occurred")
    ... except YouTubeTranscriptError as e:
    ...     print(f"Caught error: {e}")
    Caught error: An error occurred
    """

    pass


class ChannelNotFoundError(YouTubeTranscriptError):
    """Exception raised when a channel is not found.

    This exception is raised when attempting to access a channel that
    doesn't exist in the channel registry.

    Parameters
    ----------
    message : str
        Description of the error, typically including the channel ID.

    Examples
    --------
    >>> raise ChannelNotFoundError("Channel 'UC_123' not found")
    Traceback (most recent call last):
        ...
    ChannelNotFoundError: Channel 'UC_123' not found
    """

    pass


class ChannelAlreadyExistsError(YouTubeTranscriptError):
    """Exception raised when attempting to add a channel that already exists.

    This exception is raised when trying to register a channel with an ID
    that is already present in the channel registry.

    Parameters
    ----------
    message : str
        Description of the error, typically including the channel ID.

    Examples
    --------
    >>> raise ChannelAlreadyExistsError("Channel 'UC_123' already exists")
    Traceback (most recent call last):
        ...
    ChannelAlreadyExistsError: Channel 'UC_123' already exists
    """

    pass


class QuotaExceededError(YouTubeTranscriptError):
    """Exception raised when the YouTube Data API quota is exceeded.

    This exception is raised when the daily API quota budget has been
    consumed and further requests cannot be made.

    Parameters
    ----------
    message : str
        Description of the error, typically including quota details.

    Examples
    --------
    >>> raise QuotaExceededError("Daily quota exceeded: 10000/10000 units used")
    Traceback (most recent call last):
        ...
    QuotaExceededError: Daily quota exceeded: 10000/10000 units used
    """

    pass


class TranscriptUnavailableError(YouTubeTranscriptError):
    """Exception raised when a transcript is not available for a video.

    This exception is raised when a video does not have captions or
    transcripts available (e.g., auto-generated captions disabled,
    no captions in the requested language).

    Parameters
    ----------
    message : str
        Description of the error, typically including the video ID.

    Examples
    --------
    >>> raise TranscriptUnavailableError("Transcript unavailable for 'abc123'")
    Traceback (most recent call last):
        ...
    TranscriptUnavailableError: Transcript unavailable for 'abc123'
    """

    pass


class APIError(YouTubeTranscriptError):
    """Exception raised when a YouTube API call fails.

    This exception is raised when an API request to the YouTube Data API
    fails due to HTTP errors (4xx, 5xx), network issues, or invalid responses.

    Parameters
    ----------
    message : str
        Description of the error, typically including HTTP status code and reason.

    Examples
    --------
    >>> raise APIError("YouTube API error: 403 Forbidden")
    Traceback (most recent call last):
        ...
    APIError: YouTube API error: 403 Forbidden
    """

    pass


class StorageError(YouTubeTranscriptError):
    """Exception raised when a storage operation fails.

    This exception is raised when reading from or writing to the storage
    backend fails (e.g., file I/O errors, serialization failures).

    Parameters
    ----------
    message : str
        Description of the error.

    Examples
    --------
    >>> raise StorageError("Failed to write transcript to storage")
    Traceback (most recent call last):
        ...
    StorageError: Failed to write transcript to storage
    """

    pass


class FileLockError(YouTubeTranscriptError):
    """Exception raised when a file lock cannot be acquired.

    This exception is raised when the file lock acquisition times out,
    indicating that another process holds the lock longer than expected.

    Parameters
    ----------
    message : str
        Description of the error, typically including the lock file path
        and timeout duration.

    Examples
    --------
    >>> raise FileLockError("Failed to acquire lock for channels.lock after 10.0 seconds")
    Traceback (most recent call last):
        ...
    FileLockError: Failed to acquire lock for channels.lock after 10.0 seconds
    """

    pass
