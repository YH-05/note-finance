"""Channel management service for YouTube transcript collection.

This module provides the ChannelManager class for managing YouTube channel
registration, listing, retrieval, updating, and deletion.

References
----------
- Modelled after src/rss/services/feed_manager.py
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from youtube_transcript._errors import log_and_reraise
from youtube_transcript._logging import get_logger
from youtube_transcript.core.channel_fetcher import _parse_url_or_id
from youtube_transcript.exceptions import (
    ChannelAlreadyExistsError,
    ChannelNotFoundError,
    StorageError,
)
from youtube_transcript.storage.json_storage import JSONStorage
from youtube_transcript.types import Channel

logger = get_logger(__name__)


class ChannelManager:
    """Service for managing YouTube channels.

    This class provides methods for channel registration (CRUD), URL
    normalisation, duplicate checking, and JSON storage persistence.

    Parameters
    ----------
    data_dir : Path
        Root directory for youtube_transcript data
        (e.g., data/raw/youtube_transcript/).

    Attributes
    ----------
    data_dir : Path
        Root directory for youtube_transcript data.
    storage : JSONStorage
        JSON storage for persistence.

    Examples
    --------
    >>> from pathlib import Path
    >>> manager = ChannelManager(Path("data/raw/youtube_transcript"))
    >>> channel = manager.add(
    ...     url_or_id="UCabc123",
    ...     title="My Channel",
    ... )
    >>> print(channel.channel_id)
    UCabc123
    """

    def __init__(self, data_dir: Path) -> None:
        """Initialise ChannelManager.

        Parameters
        ----------
        data_dir : Path
            Root directory for youtube_transcript data.

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
        self.storage = JSONStorage(data_dir)
        logger.debug("ChannelManager initialized", data_dir=str(data_dir))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(
        self,
        url_or_id: str,
        title: str,
        *,
        language_priority: list[str] | None = None,
        enabled: bool = True,
    ) -> Channel:
        """Register a new YouTube channel.

        Normalises the given URL or channel ID, checks for duplicates,
        and persists the new channel to JSON storage.

        Parameters
        ----------
        url_or_id : str
            YouTube channel URL (@handle, /channel/UCxxx, raw UCxxx ID, etc.)
            or raw channel ID.
        title : str
            Human-readable channel title.
        language_priority : list[str] | None, default=None
            Ordered list of preferred transcript language codes.
            Defaults to ``["ja", "en"]`` when *None*.
        enabled : bool, default=True
            Whether the channel is enabled for transcript collection.

        Returns
        -------
        Channel
            The newly registered channel.

        Raises
        ------
        ChannelAlreadyExistsError
            If a channel with the same normalised channel_id already exists.

        Examples
        --------
        >>> manager = ChannelManager(Path("data/raw/youtube_transcript"))
        >>> channel = manager.add("UCabc123", "My Channel")
        >>> print(channel.channel_id)
        UCabc123
        """
        if language_priority is None:
            language_priority = ["ja", "en"]

        # Normalise: extract channel_id if a full URL is given
        channel_id = _normalise_to_channel_id(url_or_id)

        logger.debug(
            "Adding channel",
            url_or_id=url_or_id,
            resolved_channel_id=channel_id,
            title=title,
            language_priority=language_priority,
            enabled=enabled,
        )

        # Duplicate check
        channels = self.storage.load_channels()
        for existing in channels:
            if existing.channel_id == channel_id:
                logger.warning(
                    "Duplicate channel_id detected",
                    channel_id=channel_id,
                    title=existing.title,
                )
                raise ChannelAlreadyExistsError(
                    f"Channel '{channel_id}' already exists"
                )

        now = datetime.now(UTC).isoformat()
        channel = Channel(
            channel_id=channel_id,
            title=title,
            uploads_playlist_id=_derive_uploads_playlist_id(channel_id),
            language_priority=language_priority,
            enabled=enabled,
            created_at=now,
            last_fetched=None,
            video_count=0,
        )

        channels.append(channel)
        self.storage.save_channels(channels)

        logger.info(
            "Channel registered successfully",
            channel_id=channel_id,
            title=title,
        )

        return channel

    def list(self, *, enabled_only: bool = False) -> list[Channel]:
        """Return all registered channels, with optional enabled filter.

        Parameters
        ----------
        enabled_only : bool, default=False
            When *True*, only enabled channels are returned.

        Returns
        -------
        list[Channel]
            Channels matching the filter criteria.

        Examples
        --------
        >>> manager = ChannelManager(Path("data/raw/youtube_transcript"))
        >>> all_channels = manager.list()
        >>> active = manager.list(enabled_only=True)
        """
        logger.debug("Listing channels", enabled_only=enabled_only)

        channels = self.storage.load_channels()

        if enabled_only:
            channels = [ch for ch in channels if ch.enabled]

        logger.info(
            "Channels listed",
            total_count=len(channels),
            enabled_only=enabled_only,
        )

        return channels

    def get(self, channel_id: str) -> Channel:
        """Return a channel by its ID.

        Parameters
        ----------
        channel_id : str
            YouTube channel ID (e.g., ``"UCabc123"``).

        Returns
        -------
        Channel
            The matching channel.

        Raises
        ------
        ChannelNotFoundError
            If no channel with the given ID exists.

        Examples
        --------
        >>> manager = ChannelManager(Path("data/raw/youtube_transcript"))
        >>> channel = manager.get("UCabc123")
        """
        logger.debug("Getting channel", channel_id=channel_id)

        channels = self.storage.load_channels()
        for channel in channels:
            if channel.channel_id == channel_id:
                logger.debug("Channel found", channel_id=channel_id)
                return channel

        logger.error("Channel not found", channel_id=channel_id)
        raise ChannelNotFoundError(f"Channel '{channel_id}' not found")

    def remove(self, channel_id: str) -> None:
        """Remove a channel and its associated data from storage.

        Parameters
        ----------
        channel_id : str
            YouTube channel ID to remove.

        Raises
        ------
        ChannelNotFoundError
            If no channel with the given ID exists.

        Examples
        --------
        >>> manager = ChannelManager(Path("data/raw/youtube_transcript"))
        >>> manager.remove("UCabc123")
        """
        logger.debug("Removing channel", channel_id=channel_id)

        channels = self.storage.load_channels()

        idx = next(
            (i for i, ch in enumerate(channels) if ch.channel_id == channel_id),
            None,
        )

        if idx is None:
            logger.error("Channel not found for removal", channel_id=channel_id)
            raise ChannelNotFoundError(f"Channel '{channel_id}' not found")

        removed = channels.pop(idx)
        self.storage.save_channels(channels)

        logger.info(
            "Channel removed successfully",
            channel_id=channel_id,
            title=removed.title,
        )

    def update(
        self,
        channel_id: str,
        *,
        title: str | None = None,
        language_priority: list[str] | None = None,
        enabled: bool | None = None,
    ) -> Channel:
        """Update channel metadata.

        Parameters
        ----------
        channel_id : str
            YouTube channel ID to update.
        title : str | None, default=None
            New channel title; unchanged if *None*.
        language_priority : list[str] | None, default=None
            New language priority list; unchanged if *None*.
        enabled : bool | None, default=None
            New enabled status; unchanged if *None*.

        Returns
        -------
        Channel
            The updated channel.

        Raises
        ------
        ChannelNotFoundError
            If no channel with the given ID exists.

        Examples
        --------
        >>> manager = ChannelManager(Path("data/raw/youtube_transcript"))
        >>> updated = manager.update("UCabc123", title="New Title", enabled=False)
        """
        logger.debug(
            "Updating channel",
            channel_id=channel_id,
            title=title,
            language_priority=language_priority,
            enabled=enabled,
        )

        channels = self.storage.load_channels()

        idx = next(
            (i for i, ch in enumerate(channels) if ch.channel_id == channel_id),
            None,
        )

        if idx is None:
            logger.error("Channel not found for update", channel_id=channel_id)
            raise ChannelNotFoundError(f"Channel '{channel_id}' not found")

        channel = channels[idx]

        if title is not None:
            channel.title = title
        if language_priority is not None:
            channel.language_priority = language_priority
        if enabled is not None:
            channel.enabled = enabled

        channels[idx] = channel
        self.storage.save_channels(channels)

        logger.info(
            "Channel updated successfully",
            channel_id=channel_id,
            updated_fields={
                k: v
                for k, v in {
                    "title": title,
                    "language_priority": language_priority,
                    "enabled": enabled,
                }.items()
                if v is not None
            },
        )

        return channel


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _normalise_to_channel_id(url_or_id: str) -> str:
    """Normalise a URL or ID string to a bare YouTube channel ID.

    For raw ``UCxxx`` IDs the value is returned unchanged.  For URLs the
    path is parsed to extract the channel ID component.  If the URL uses
    a @handle or username form the raw string is returned as-is because
    the actual ``UCxxx`` ID is not resolvable without an API call.

    Parameters
    ----------
    url_or_id : str
        YouTube channel URL or ID.

    Returns
    -------
    str
        Normalised channel identifier.

    Examples
    --------
    >>> _normalise_to_channel_id("UCabc123")
    'UCabc123'
    >>> _normalise_to_channel_id("https://www.youtube.com/channel/UCabc123")
    'UCabc123'
    >>> _normalise_to_channel_id("https://www.youtube.com/@TestChannel")
    '@TestChannel'
    """
    lookup_type, lookup_value = _parse_url_or_id(url_or_id)

    if lookup_type == "id":
        # Raw UCxxx ID or /channel/UCxxx URL
        return lookup_value

    # For @handle and forUsername forms we use the lookup_value as the key.
    # The actual UCxxx ID is only resolvable via the API (ChannelFetcher).
    return lookup_value


def _derive_uploads_playlist_id(channel_id: str) -> str:
    """Derive the uploads playlist ID from a channel ID.

    YouTube's convention: replace the second character ``C`` with ``U``.
    E.g., ``UCabc123`` → ``UUabc123``.  Only applicable to raw UCxxx IDs.
    For @handle / username forms an empty string is returned; the real ID
    should be populated later by ChannelFetcher.get_channel_info().

    Parameters
    ----------
    channel_id : str
        YouTube channel ID.

    Returns
    -------
    str
        Derived uploads playlist ID, or empty string if not a UCxxx ID.

    Examples
    --------
    >>> _derive_uploads_playlist_id("UCabc123")
    'UUabc123'
    >>> _derive_uploads_playlist_id("@TestChannel")
    ''
    """
    if channel_id.startswith("UC"):
        return "UU" + channel_id[2:]
    return ""
