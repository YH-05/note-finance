"""File lock management for youtube_transcript data.

This module provides thread-safe and process-safe file locking mechanisms
for managing concurrent access to youtube_transcript data files.
Three lock tiers are supported:
  - channels.lock   (global channel registry)
  - {channel_id}/videos.lock  (per-channel video list)
  - {channel_id}/{video_id}/transcript.lock  (per-video transcript)
"""

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock, Timeout

from youtube_transcript._logging import get_logger
from youtube_transcript.exceptions import FileLockError

logger = get_logger(__name__)


class LockManager:
    """Manage file locks for youtube_transcript data files.

    This class provides context managers for acquiring and releasing locks
    on channels.json, videos.json, and transcript.json files, ensuring safe
    concurrent access from multiple processes or threads.

    Parameters
    ----------
    data_dir : Path
        Root directory where youtube_transcript data is stored

    Attributes
    ----------
    data_dir : Path
        Root directory for youtube_transcript data
    default_timeout : float
        Default timeout in seconds for lock acquisition (default: 10.0)

    Examples
    --------
    >>> from pathlib import Path
    >>> manager = LockManager(Path("data/raw/youtube_transcript"))
    >>> with manager.lock_channels():
    ...     # Safely read/write channels.json
    ...     pass

    >>> with manager.lock_videos("UC_123"):
    ...     # Safely read/write UC_123/videos.json
    ...     pass

    >>> with manager.lock_transcript("UC_123", "abc1234567a"):
    ...     # Safely read/write UC_123/abc1234567a/transcript.json
    ...     pass
    """

    def __init__(self, data_dir: Path, *, default_timeout: float = 10.0) -> None:
        """Initialize LockManager.

        Parameters
        ----------
        data_dir : Path
            Root directory where youtube_transcript data is stored
        default_timeout : float, default=10.0
            Default timeout in seconds for lock acquisition

        Raises
        ------
        ValueError
            If default_timeout is not positive
        """
        if default_timeout <= 0:
            logger.error(
                "Invalid timeout value",
                timeout=default_timeout,
                error="timeout must be positive",
            )
            raise ValueError(f"timeout must be positive, got {default_timeout}")

        self.data_dir = data_dir
        self.default_timeout = default_timeout
        logger.debug(
            "LockManager initialized",
            data_dir=str(data_dir),
            default_timeout=default_timeout,
        )

    @contextmanager
    def lock_channels(
        self, *, timeout: float | None = None
    ) -> Generator[None, None, None]:
        """Acquire lock for channels.json file.

        This context manager ensures exclusive access to channels.json,
        preventing concurrent modifications from multiple processes or threads.

        Parameters
        ----------
        timeout : float, optional
            Timeout in seconds for lock acquisition.
            If None, uses default_timeout.

        Yields
        ------
        None
            Context where channels.json is locked

        Raises
        ------
        FileLockError
            If lock cannot be acquired within timeout period

        Examples
        --------
        >>> manager = LockManager(Path("data/raw/youtube_transcript"))
        >>> with manager.lock_channels():
        ...     # Read or write channels.json safely
        ...     pass
        """
        lock_timeout = timeout if timeout is not None else self.default_timeout
        lock_file = self.data_dir / "channels.lock"

        logger.debug(
            "Attempting to acquire channels lock",
            lock_file=str(lock_file),
            timeout=lock_timeout,
        )

        lock = FileLock(lock_file, timeout=lock_timeout)

        try:
            with lock:
                logger.debug(
                    "Channels lock acquired",
                    lock_file=str(lock_file),
                )
                yield
                logger.debug(
                    "Releasing channels lock",
                    lock_file=str(lock_file),
                )
        except Timeout as e:
            logger.error(
                "Failed to acquire channels lock",
                lock_file=str(lock_file),
                timeout=lock_timeout,
                error=str(e),
            )
            raise FileLockError(
                f"Failed to acquire lock for {lock_file} after {lock_timeout} seconds"
            ) from e

    @contextmanager
    def lock_videos(
        self, channel_id: str, *, timeout: float | None = None
    ) -> Generator[None, None, None]:
        """Acquire lock for videos.json file of a specific channel.

        This context manager ensures exclusive access to a channel's videos.json,
        preventing concurrent modifications from multiple processes or threads.

        Parameters
        ----------
        channel_id : str
            YouTube channel ID whose videos.json should be locked
        timeout : float, optional
            Timeout in seconds for lock acquisition.
            If None, uses default_timeout.

        Yields
        ------
        None
            Context where videos.json is locked

        Raises
        ------
        FileLockError
            If lock cannot be acquired within timeout period
        ValueError
            If channel_id is empty

        Examples
        --------
        >>> manager = LockManager(Path("data/raw/youtube_transcript"))
        >>> with manager.lock_videos("UC_123"):
        ...     # Read or write UC_123/videos.json safely
        ...     pass
        """
        if not channel_id:
            logger.error(
                "Invalid channel_id",
                channel_id=channel_id,
                error="channel_id cannot be empty",
            )
            raise ValueError("channel_id cannot be empty")

        lock_timeout = timeout if timeout is not None else self.default_timeout
        lock_file = self.data_dir / channel_id / "videos.lock"

        logger.debug(
            "Attempting to acquire videos lock",
            channel_id=channel_id,
            lock_file=str(lock_file),
            timeout=lock_timeout,
        )

        # Ensure channel directory exists
        lock_file.parent.mkdir(parents=True, exist_ok=True)

        lock = FileLock(lock_file, timeout=lock_timeout)

        try:
            with lock:
                logger.debug(
                    "Videos lock acquired",
                    channel_id=channel_id,
                    lock_file=str(lock_file),
                )
                yield
                logger.debug(
                    "Releasing videos lock",
                    channel_id=channel_id,
                    lock_file=str(lock_file),
                )
        except Timeout as e:
            logger.error(
                "Failed to acquire videos lock",
                channel_id=channel_id,
                lock_file=str(lock_file),
                timeout=lock_timeout,
                error=str(e),
            )
            raise FileLockError(
                f"Failed to acquire lock for {lock_file} after {lock_timeout} seconds"
            ) from e

    @contextmanager
    def lock_transcript(
        self, channel_id: str, video_id: str, *, timeout: float | None = None
    ) -> Generator[None, None, None]:
        """Acquire lock for transcript.json file of a specific video.

        This context manager ensures exclusive access to a video's transcript.json,
        preventing concurrent modifications from multiple processes or threads.

        Parameters
        ----------
        channel_id : str
            YouTube channel ID
        video_id : str
            YouTube video ID (11-character string)
        timeout : float, optional
            Timeout in seconds for lock acquisition.
            If None, uses default_timeout.

        Yields
        ------
        None
            Context where transcript.json is locked

        Raises
        ------
        FileLockError
            If lock cannot be acquired within timeout period
        ValueError
            If channel_id or video_id is empty

        Examples
        --------
        >>> manager = LockManager(Path("data/raw/youtube_transcript"))
        >>> with manager.lock_transcript("UC_123", "abc1234567a"):
        ...     # Read or write UC_123/abc1234567a/transcript.json safely
        ...     pass
        """
        if not channel_id:
            logger.error(
                "Invalid channel_id",
                channel_id=channel_id,
                error="channel_id cannot be empty",
            )
            raise ValueError("channel_id cannot be empty")

        if not video_id:
            logger.error(
                "Invalid video_id",
                video_id=video_id,
                error="video_id cannot be empty",
            )
            raise ValueError("video_id cannot be empty")

        lock_timeout = timeout if timeout is not None else self.default_timeout
        lock_file = self.data_dir / channel_id / video_id / "transcript.lock"

        logger.debug(
            "Attempting to acquire transcript lock",
            channel_id=channel_id,
            video_id=video_id,
            lock_file=str(lock_file),
            timeout=lock_timeout,
        )

        # Ensure transcript directory exists
        lock_file.parent.mkdir(parents=True, exist_ok=True)

        lock = FileLock(lock_file, timeout=lock_timeout)

        try:
            with lock:
                logger.debug(
                    "Transcript lock acquired",
                    channel_id=channel_id,
                    video_id=video_id,
                    lock_file=str(lock_file),
                )
                yield
                logger.debug(
                    "Releasing transcript lock",
                    channel_id=channel_id,
                    video_id=video_id,
                    lock_file=str(lock_file),
                )
        except Timeout as e:
            logger.error(
                "Failed to acquire transcript lock",
                channel_id=channel_id,
                video_id=video_id,
                lock_file=str(lock_file),
                timeout=lock_timeout,
                error=str(e),
            )
            raise FileLockError(
                f"Failed to acquire lock for {lock_file} after {lock_timeout} seconds"
            ) from e
