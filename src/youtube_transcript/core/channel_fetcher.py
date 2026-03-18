"""ChannelFetcher: YouTube Data API v3 ラッパー + URL 正規化.

全4形式の YouTube チャンネル URL を正規化し、チャンネル情報取得と
全動画一覧取得を quota 効率的に提供するモジュール。

URL 正規化対応形式:
  - @handle               → channels.list(forHandle=...)
  - https://.../@handle   → channels.list(forHandle=...)
  - UCxxx (raw ID)        → channels.list(id=...)
  - /channel/UCxxx        → channels.list(id=...)
  - /c/name               → channels.list(forUsername=...) (フォールバック)
  - /user/name            → channels.list(forUsername=...)

quota 消費:
  - channels.list: 1 unit/call
  - playlistItems.list: 1 unit/call  (search.list は使用しない)
"""

import re
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from youtube_transcript._logging import get_logger
from youtube_transcript.exceptions import APIError, ChannelNotFoundError
from youtube_transcript.types import Channel, TranscriptStatus, Video

logger = get_logger(__name__)

# quota cost per API call (units)
_CHANNELS_LIST_COST = 1
_PLAYLIST_ITEMS_LIST_COST = 1

# Maximum results per page for playlistItems.list (API max: 50)
_PAGE_SIZE = 50


class ChannelFetcher:
    """YouTube Data API v3 ラッパー.

    チャンネル URL / ID を正規化して ``Channel`` を取得し、
    ``playlistItems.list`` を使って全動画一覧をページネーションで取得する。
    ``search.list`` は使用しないため quota 効率が高い。

    Parameters
    ----------
    api_key : str
        YouTube Data API v3 の API キー。
    quota_tracker : Any
        :class:`~youtube_transcript.storage.quota_tracker.QuotaTracker` 互換
        オブジェクト。``consume(units: int)`` メソッドを持つ必要がある。
    _service : Any | None, optional
        テスト用の依存性注入。``None`` のとき ``build()`` でサービスを構築する。

    Examples
    --------
    >>> from pathlib import Path
    >>> from youtube_transcript.storage.quota_tracker import QuotaTracker
    >>> tracker = QuotaTracker(Path("data/raw/youtube_transcript"))
    >>> fetcher = ChannelFetcher(api_key="YOUR_API_KEY", quota_tracker=tracker)
    >>> channel = fetcher.get_channel_info("https://www.youtube.com/@SomeChannel")
    >>> videos = fetcher.list_all_videos(channel.channel_id, channel.uploads_playlist_id)
    """

    def __init__(
        self,
        api_key: str,
        quota_tracker: Any,
        *,
        _service: Any | None = None,
    ) -> None:
        """Initialise ChannelFetcher.

        Parameters
        ----------
        api_key : str
            YouTube Data API v3 の API キー。
        quota_tracker : Any
            QuotaTracker 互換オブジェクト。
        _service : Any | None, optional
            テスト用依存性注入。
        """
        self._api_key = api_key
        self._quota_tracker = quota_tracker
        self._service = _service

        logger.debug(
            "ChannelFetcher initialized",
            has_injected_service=_service is not None,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_channel_info(self, url_or_id: str) -> Channel:
        """チャンネル URL または ID からチャンネル情報を取得する.

        全4形式の URL と生の channel_id に対応する。

        Parameters
        ----------
        url_or_id : str
            YouTube チャンネルの URL、@handle、または channel_id。

        Returns
        -------
        Channel
            チャンネル情報。

        Raises
        ------
        ChannelNotFoundError
            チャンネルが存在しない場合。
        QuotaExceededError
            quota が枯渇している場合。
        APIError
            API 呼び出しが失敗した場合。

        Examples
        --------
        >>> channel = fetcher.get_channel_info("https://www.youtube.com/@SomeChannel")
        >>> print(channel.channel_id)
        """
        logger.info(
            "Fetching channel info",
            url_or_id=url_or_id,
        )

        lookup_type, lookup_value = _parse_url_or_id(url_or_id)

        service = self._get_service()
        request_kwargs = _build_channels_list_kwargs(lookup_type, lookup_value)

        logger.debug(
            "channels.list request",
            lookup_type=lookup_type,
            lookup_value=lookup_value,
        )

        # consume quota before calling (raises QuotaExceededError if exhausted)
        self._quota_tracker.consume(_CHANNELS_LIST_COST)

        try:
            response = (
                service.channels()
                .list(**request_kwargs, part="snippet,contentDetails")
                .execute()
            )
        except HttpError as exc:
            logger.error(
                "channels.list failed",
                status=exc.resp.status,
                reason=exc.resp.reason,
                url_or_id=url_or_id,
            )
            raise APIError(
                f"YouTube API error {exc.resp.status}: {exc.resp.reason}"
            ) from exc

        items = response.get("items", [])
        if not items:
            logger.warning(
                "Channel not found",
                url_or_id=url_or_id,
                lookup_type=lookup_type,
            )
            raise ChannelNotFoundError(f"Channel not found for '{url_or_id}'")

        item = items[0]
        channel_id = item["id"]
        title = item["snippet"]["title"]
        uploads_playlist_id = item["contentDetails"]["relatedPlaylists"]["uploads"]

        channel = Channel(
            channel_id=channel_id,
            title=title,
            uploads_playlist_id=uploads_playlist_id,
            language_priority=["ja", "en"],
            enabled=True,
            created_at="",
            last_fetched=None,
            video_count=0,
        )

        logger.info(
            "Channel info retrieved",
            channel_id=channel_id,
            title=title,
            uploads_playlist_id=uploads_playlist_id,
        )

        return channel

    def list_all_videos(self, channel_id: str, uploads_playlist_id: str) -> list[Video]:
        """uploads_playlist_id からチャンネルの全動画一覧を取得する.

        ``playlistItems.list`` を使用してページネーションで全件取得する。
        ``search.list`` は使用しない。

        Parameters
        ----------
        channel_id : str
            YouTube チャンネル ID。
        uploads_playlist_id : str
            チャンネルのアップロードプレイリスト ID。

        Returns
        -------
        list[Video]
            動画一覧（PENDING ステータス）。

        Raises
        ------
        QuotaExceededError
            quota が枯渇している場合。
        APIError
            API 呼び出しが失敗した場合。

        Examples
        --------
        >>> videos = fetcher.list_all_videos(channel.channel_id, channel.uploads_playlist_id)
        >>> print(len(videos))
        """
        logger.info(
            "Fetching all videos",
            channel_id=channel_id,
            uploads_playlist_id=uploads_playlist_id,
        )

        service = self._get_service()
        videos: list[Video] = []

        # Initial request
        self._quota_tracker.consume(_PLAYLIST_ITEMS_LIST_COST)

        try:
            request = service.playlistItems().list(
                playlistId=uploads_playlist_id,
                part="snippet,contentDetails",
                maxResults=_PAGE_SIZE,
            )
            response = request.execute()
        except HttpError as exc:
            logger.error(
                "playlistItems.list failed",
                status=exc.resp.status,
                reason=exc.resp.reason,
                channel_id=channel_id,
            )
            raise APIError(
                f"YouTube API error {exc.resp.status}: {exc.resp.reason}"
            ) from exc

        videos.extend(_parse_playlist_items(response, channel_id))

        # Pagination
        while True:
            next_request = service.playlistItems().list_next(request, response)
            if next_request is None:
                break

            self._quota_tracker.consume(_PLAYLIST_ITEMS_LIST_COST)

            try:
                response = next_request.execute()
            except HttpError as exc:
                logger.error(
                    "playlistItems.list_next failed",
                    status=exc.resp.status,
                    reason=exc.resp.reason,
                    channel_id=channel_id,
                )
                raise APIError(
                    f"YouTube API error {exc.resp.status}: {exc.resp.reason}"
                ) from exc

            request = next_request
            videos.extend(_parse_playlist_items(response, channel_id))

        logger.info(
            "All videos fetched",
            channel_id=channel_id,
            total_videos=len(videos),
        )

        return videos

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_service(self) -> Any:
        """Return the YouTube service resource, building it if necessary.

        Returns
        -------
        Any
            googleapiclient Resource for the YouTube Data API v3.
        """
        if self._service is None:
            self._service = build("youtube", "v3", developerKey=self._api_key)
            logger.debug("YouTube service built", api_version="v3")
        return self._service


# ---------------------------------------------------------------------------
# Module-level helpers (pure functions)
# ---------------------------------------------------------------------------


def _parse_url_or_id(url_or_id: str) -> tuple[str, str]:
    """Parse a URL or ID and return (lookup_type, lookup_value).

    Parameters
    ----------
    url_or_id : str
        One of:
        - Raw channel ID (starts with "UC")
        - @handle (with or without https://... prefix)
        - https://www.youtube.com/channel/UCxxx
        - https://www.youtube.com/c/name
        - https://www.youtube.com/user/name

    Returns
    -------
    tuple[str, str]
        (lookup_type, lookup_value) where lookup_type is one of:
        "id", "forHandle", "forUsername"

    Examples
    --------
    >>> _parse_url_or_id("UCabc123")
    ('id', 'UCabc123')
    >>> _parse_url_or_id("@TestChannel")
    ('forHandle', '@TestChannel')
    >>> _parse_url_or_id("https://www.youtube.com/@TestChannel")
    ('forHandle', '@TestChannel')
    >>> _parse_url_or_id("https://www.youtube.com/channel/UCabc123")
    ('id', 'UCabc123')
    >>> _parse_url_or_id("https://www.youtube.com/user/TestChannel")
    ('forUsername', 'TestChannel')
    >>> _parse_url_or_id("https://www.youtube.com/c/TestChannel")
    ('forUsername', 'TestChannel')
    """
    stripped = url_or_id.strip()

    # Ordered list of (regex_pattern, lookup_type, group_transform)
    # Each tuple: (pattern, lookup_type, value_fn)
    _patterns: list[tuple[str, str, Any]] = [
        (r"/channel/(UC[\w-]+)", "id", lambda m: m.group(1)),
        (r"/@([\w.-]+)", "forHandle", lambda m: f"@{m.group(1)}"),
        (r"/user/([\w.-]+)", "forUsername", lambda m: m.group(1)),
        (r"/c/([\w.-]+)", "forUsername", lambda m: m.group(1)),
    ]

    for pattern, lookup_type, value_fn in _patterns:
        m = re.search(pattern, stripped)
        if m:
            return (lookup_type, value_fn(m))

    # standalone @handle (no URL)
    if stripped.startswith("@"):
        return ("forHandle", stripped)

    # Raw channel ID
    if re.match(r"^UC[\w-]+$", stripped):
        return ("id", stripped)

    # Fallback: treat as forUsername
    logger.warning(
        "URL format not recognized, treating as forUsername",
        url_or_id=url_or_id,
    )
    return ("forUsername", stripped)


def _build_channels_list_kwargs(lookup_type: str, lookup_value: str) -> dict[str, str]:
    """Build keyword args for channels().list() based on lookup type.

    Parameters
    ----------
    lookup_type : str
        One of "id", "forHandle", "forUsername".
    lookup_value : str
        The value to pass to the corresponding parameter.

    Returns
    -------
    dict[str, str]
        Keyword arguments for channels().list().
    """
    return {lookup_type: lookup_value}


def _parse_playlist_items(response: dict, channel_id: str) -> list[Video]:
    """Parse playlistItems.list response into Video objects.

    Parameters
    ----------
    response : dict
        Raw API response from playlistItems.list.
    channel_id : str
        Channel ID to associate with the videos.

    Returns
    -------
    list[Video]
        Parsed Video objects with PENDING status.
    """
    videos: list[Video] = []
    for item in response.get("items", []):
        video_id = item["contentDetails"]["videoId"]
        snippet = item.get("snippet", {})
        title = snippet.get("title", "")
        published = snippet.get("publishedAt", "")
        description = snippet.get("description", "")

        video = Video(
            video_id=video_id,
            channel_id=channel_id,
            title=title,
            published=published,
            description=description,
            transcript_status=TranscriptStatus.PENDING,
            transcript_language=None,
            fetched_at=None,
        )
        videos.append(video)

    return videos
