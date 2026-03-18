"""Unit tests for ChannelFetcher.

TDD Red phase: tests covering acceptance criteria from Issue #165.

Acceptance criteria:
- 全4形式 URL を正規化できる
- list_all_videos() がページネーションで全動画を返す
- search.list を使わず quota 効率を実現
- QuotaTracker.consume() が呼ばれる
- `test_channel_fetcher.py` の全テストが通過する
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from youtube_transcript.core.channel_fetcher import ChannelFetcher
from youtube_transcript.exceptions import (
    APIError,
    ChannelNotFoundError,
    QuotaExceededError,
)
from youtube_transcript.types import Channel, Video

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_channels_list_response(
    channel_id: str = "UCabc123",
    title: str = "Test Channel",
    uploads_playlist_id: str = "UUabc123",
) -> dict:
    """Return a mock channels.list API response."""
    return {
        "items": [
            {
                "id": channel_id,
                "snippet": {"title": title},
                "contentDetails": {
                    "relatedPlaylists": {"uploads": uploads_playlist_id}
                },
            }
        ]
    }


def make_empty_channels_response() -> dict:
    """Return a channels.list response with no items."""
    return {"items": []}


def make_playlist_items_response(
    video_ids: list[str],
    next_page_token: str | None = None,
) -> dict:
    """Return a mock playlistItems.list API response."""
    items = []
    for vid in video_ids:
        items.append(
            {
                "contentDetails": {"videoId": vid},
                "snippet": {
                    "title": f"Video {vid}",
                    "publishedAt": "2026-03-18T10:00:00Z",
                    "description": f"Description for {vid}",
                },
            }
        )
    response: dict = {"items": items}
    if next_page_token:
        response["nextPageToken"] = next_page_token
    return response


def make_mock_youtube_service(
    channels_response: dict | None = None,
    playlist_items_responses: list[dict] | None = None,
) -> MagicMock:
    """Return a mock YouTube Data API service resource."""
    service = MagicMock()

    # channels().list().execute()
    if channels_response is not None:
        channels_execute = MagicMock(return_value=channels_response)
        channels_list = MagicMock()
        channels_list.execute = channels_execute
        service.channels.return_value.list.return_value = channels_list

    # playlistItems().list().execute() — supports multiple pages
    if playlist_items_responses is not None:
        responses_iter = iter(playlist_items_responses)
        playlist_items_list = MagicMock()
        playlist_items_list.execute.side_effect = lambda: next(responses_iter)
        service.playlistItems.return_value.list.return_value = playlist_items_list
        service.playlistItems.return_value.list_next = MagicMock(
            side_effect=_make_list_next(playlist_items_responses)
        )

    return service


def _make_list_next(responses: list[dict]):
    """Return a side_effect function for list_next that drives pagination."""
    call_count = [0]

    def _list_next(prev_request, prev_response):
        call_count[0] += 1
        if call_count[0] < len(responses):
            # Return a next request object (truthy), whose execute() will be
            # called to get the next response
            next_request = MagicMock()
            next_request.execute.return_value = responses[call_count[0]]
            return next_request
        return None  # No more pages

    return _list_next


def make_quota_tracker(data_dir: Path | None = None) -> MagicMock:
    """Return a mock QuotaTracker."""
    tracker = MagicMock()
    tracker.consume = MagicMock()
    tracker.remaining = MagicMock(return_value=9000)
    return tracker


# ---------------------------------------------------------------------------
# Phase 0: Initialisation
# ---------------------------------------------------------------------------


class TestChannelFetcherInit:
    """Tests for ChannelFetcher initialization."""

    def test_正常系_APIキーで初期化できる(self, tmp_path: Path) -> None:
        """ChannelFetcher can be initialized with an API key."""
        tracker = make_quota_tracker(tmp_path)
        fetcher = ChannelFetcher(api_key="test-api-key", quota_tracker=tracker)
        assert fetcher is not None

    def test_正常系_注入サービスで初期化できる(self, tmp_path: Path) -> None:
        """ChannelFetcher can be initialized with an injected service."""
        tracker = make_quota_tracker(tmp_path)
        mock_service = MagicMock()
        fetcher = ChannelFetcher(
            api_key="test-api-key", quota_tracker=tracker, _service=mock_service
        )
        assert fetcher is not None


# ---------------------------------------------------------------------------
# Phase 1: URL 正規化 (全4形式)
# ---------------------------------------------------------------------------


class TestGetChannelInfoUrlNormalization:
    """Tests for URL normalization in get_channel_info()."""

    def _make_fetcher(
        self,
        channels_response: dict | None = None,
        playlist_items_responses: list[dict] | None = None,
    ) -> tuple[ChannelFetcher, MagicMock]:
        tracker = make_quota_tracker()
        if channels_response is None:
            channels_response = make_channels_list_response()
        service = make_mock_youtube_service(
            channels_response=channels_response,
            playlist_items_responses=playlist_items_responses or [],
        )
        fetcher = ChannelFetcher(
            api_key="test-api-key", quota_tracker=tracker, _service=service
        )
        return fetcher, service

    # --- @handle 形式 ---

    def test_正常系_handle形式URLを正規化できる(self) -> None:
        """@handle format URL is normalized to channel_id."""
        fetcher, service = self._make_fetcher()
        channel = fetcher.get_channel_info("https://www.youtube.com/@TestChannel")
        assert isinstance(channel, Channel)
        assert channel.channel_id == "UCabc123"
        # channels().list() must use forHandle, not id/forUsername
        _, kwargs = service.channels.return_value.list.call_args
        assert "forHandle" in kwargs

    def test_正常系_handle形式のatプレフィックスを正規化できる(self) -> None:
        """@handle without URL prefix is also accepted."""
        fetcher, service = self._make_fetcher()
        channel = fetcher.get_channel_info("@TestChannel")
        assert isinstance(channel, Channel)
        _, kwargs = service.channels.return_value.list.call_args
        assert "forHandle" in kwargs

    # --- /channel/UCxxx 形式 ---

    def test_正常系_channel_id形式URLを正規化できる(self) -> None:
        """/channel/UCxxx format URL resolves to channel_id."""
        fetcher, service = self._make_fetcher()
        channel = fetcher.get_channel_info("https://www.youtube.com/channel/UCabc123")
        assert isinstance(channel, Channel)
        assert channel.channel_id == "UCabc123"
        _, kwargs = service.channels.return_value.list.call_args
        assert "id" in kwargs

    def test_正常系_raw_channel_idを直接受け入れられる(self) -> None:
        """Raw channel ID (UCxxx) is accepted directly."""
        fetcher, service = self._make_fetcher()
        channel = fetcher.get_channel_info("UCabc123")
        assert isinstance(channel, Channel)
        assert channel.channel_id == "UCabc123"
        _, kwargs = service.channels.return_value.list.call_args
        assert "id" in kwargs

    # --- /c/name 形式 ---

    def test_正常系_c_name形式URLを正規化できる(self) -> None:
        """/c/name format URL is resolved via forUsername or id lookup."""
        fetcher, _service = self._make_fetcher()
        channel = fetcher.get_channel_info("https://www.youtube.com/c/TestChannel")
        assert isinstance(channel, Channel)

    # --- /user/name 形式 ---

    def test_正常系_user_name形式URLを正規化できる(self) -> None:
        """/user/name format URL is resolved via forUsername."""
        fetcher, service = self._make_fetcher()
        channel = fetcher.get_channel_info("https://www.youtube.com/user/TestChannel")
        assert isinstance(channel, Channel)
        _, kwargs = service.channels.return_value.list.call_args
        assert "forUsername" in kwargs or "id" in kwargs

    # --- レスポンス内容の検証 ---

    def test_正常系_チャンネル情報が正しく返される(self) -> None:
        """Returned Channel has correct title and uploads_playlist_id."""
        fetcher, _ = self._make_fetcher()
        channel = fetcher.get_channel_info("UCabc123")
        assert channel.title == "Test Channel"
        assert channel.uploads_playlist_id == "UUabc123"
        assert channel.channel_id == "UCabc123"

    def test_異常系_チャンネルが見つからない場合はChannelNotFoundError(self) -> None:
        """ChannelNotFoundError is raised when channel does not exist."""
        fetcher, _ = self._make_fetcher(
            channels_response=make_empty_channels_response()
        )
        with pytest.raises(ChannelNotFoundError):
            fetcher.get_channel_info("@NonExistentChannel")


# ---------------------------------------------------------------------------
# Phase 2: list_all_videos() — ページネーション
# ---------------------------------------------------------------------------


class TestListAllVideos:
    """Tests for list_all_videos() with pagination."""

    def _make_fetcher(
        self,
        playlist_items_responses: list[dict],
        channels_response: dict | None = None,
    ) -> ChannelFetcher:
        tracker = make_quota_tracker()
        if channels_response is None:
            channels_response = make_channels_list_response()
        service = make_mock_youtube_service(
            channels_response=channels_response,
            playlist_items_responses=playlist_items_responses,
        )
        return ChannelFetcher(
            api_key="test-api-key", quota_tracker=tracker, _service=service
        )

    def test_正常系_1ページで全動画を返す(self) -> None:
        """All videos are returned when results fit in one page."""
        fetcher = self._make_fetcher(
            [make_playlist_items_response(["vid001", "vid002", "vid003"])]
        )
        videos = fetcher.list_all_videos("UCabc123", "UUabc123")
        assert len(videos) == 3
        ids = [v.video_id for v in videos]
        assert "vid001" in ids
        assert "vid002" in ids
        assert "vid003" in ids

    def test_正常系_2ページにわたる動画を全件返す(self) -> None:
        """All videos across two pages are returned."""
        page1 = make_playlist_items_response(
            ["vid001", "vid002"], next_page_token="page2token"
        )
        page2 = make_playlist_items_response(["vid003", "vid004"])
        fetcher = self._make_fetcher([page1, page2])
        videos = fetcher.list_all_videos("UCabc123", "UUabc123")
        assert len(videos) == 4

    def test_正常系_3ページにわたる動画を全件返す(self) -> None:
        """All videos across three pages are returned."""
        page1 = make_playlist_items_response(
            ["vid001", "vid002"], next_page_token="page2"
        )
        page2 = make_playlist_items_response(
            ["vid003", "vid004"], next_page_token="page3"
        )
        page3 = make_playlist_items_response(["vid005"])
        fetcher = self._make_fetcher([page1, page2, page3])
        videos = fetcher.list_all_videos("UCabc123", "UUabc123")
        assert len(videos) == 5

    def test_正常系_動画なしの場合は空リストを返す(self) -> None:
        """Empty list is returned when the channel has no videos."""
        fetcher = self._make_fetcher([make_playlist_items_response([])])
        videos = fetcher.list_all_videos("UCabc123", "UUabc123")
        assert videos == []

    def test_正常系_Videoオブジェクトが正しいフィールドを持つ(self) -> None:
        """Returned Video objects have correct fields."""
        fetcher = self._make_fetcher([make_playlist_items_response(["vid001"])])
        videos = fetcher.list_all_videos("UCabc123", "UUabc123")
        assert len(videos) == 1
        video = videos[0]
        assert isinstance(video, Video)
        assert video.video_id == "vid001"
        assert video.channel_id == "UCabc123"
        assert video.title == "Video vid001"


# ---------------------------------------------------------------------------
# Phase 3: search.list 不使用 / quota 効率
# ---------------------------------------------------------------------------


class TestQuotaEfficiency:
    """Tests verifying that search.list is never used."""

    def test_正常系_searchlistを呼ばない_get_channel_info(self) -> None:
        """get_channel_info() does NOT call search.list."""
        tracker = make_quota_tracker()
        service = make_mock_youtube_service(
            channels_response=make_channels_list_response()
        )
        fetcher = ChannelFetcher(
            api_key="test-api-key", quota_tracker=tracker, _service=service
        )
        fetcher.get_channel_info("UCabc123")
        service.search.assert_not_called()

    def test_正常系_searchlistを呼ばない_list_all_videos(self) -> None:
        """list_all_videos() does NOT call search.list."""
        tracker = make_quota_tracker()
        service = make_mock_youtube_service(
            channels_response=make_channels_list_response(),
            playlist_items_responses=[make_playlist_items_response(["vid001"])],
        )
        fetcher = ChannelFetcher(
            api_key="test-api-key", quota_tracker=tracker, _service=service
        )
        fetcher.list_all_videos("UCabc123", "UUabc123")
        service.search.assert_not_called()

    def test_正常系_playlistItems_listを使用する(self) -> None:
        """list_all_videos() uses playlistItems.list (not search.list)."""
        tracker = make_quota_tracker()
        service = make_mock_youtube_service(
            channels_response=make_channels_list_response(),
            playlist_items_responses=[make_playlist_items_response(["vid001"])],
        )
        fetcher = ChannelFetcher(
            api_key="test-api-key", quota_tracker=tracker, _service=service
        )
        fetcher.list_all_videos("UCabc123", "UUabc123")
        service.playlistItems.assert_called()


# ---------------------------------------------------------------------------
# Phase 4: QuotaTracker.consume() の呼び出し確認
# ---------------------------------------------------------------------------


class TestQuotaTrackerIntegration:
    """Tests verifying QuotaTracker.consume() is called."""

    def test_正常系_get_channel_infoでconsumeが呼ばれる(self) -> None:
        """QuotaTracker.consume() is called once in get_channel_info()."""
        tracker = make_quota_tracker()
        service = make_mock_youtube_service(
            channels_response=make_channels_list_response()
        )
        fetcher = ChannelFetcher(
            api_key="test-api-key", quota_tracker=tracker, _service=service
        )
        fetcher.get_channel_info("UCabc123")
        tracker.consume.assert_called()
        # channels.list costs 1 unit
        args, _ = tracker.consume.call_args
        assert args[0] >= 1

    def test_正常系_list_all_videosでconsumeが呼ばれる(self) -> None:
        """QuotaTracker.consume() is called once per page in list_all_videos()."""
        tracker = make_quota_tracker()
        service = make_mock_youtube_service(
            channels_response=make_channels_list_response(),
            playlist_items_responses=[
                make_playlist_items_response(
                    ["vid001", "vid002"], next_page_token="page2"
                ),
                make_playlist_items_response(["vid003"]),
            ],
        )
        fetcher = ChannelFetcher(
            api_key="test-api-key", quota_tracker=tracker, _service=service
        )
        fetcher.list_all_videos("UCabc123", "UUabc123")
        # playlistItems.list costs 1 unit per page call
        assert tracker.consume.call_count >= 2

    def test_異常系_QuotaExceededErrorが伝播する(self) -> None:
        """QuotaExceededError from tracker propagates out of get_channel_info()."""
        tracker = make_quota_tracker()
        tracker.consume.side_effect = QuotaExceededError(
            "Daily quota exceeded: 9000/9000"
        )
        service = make_mock_youtube_service(
            channels_response=make_channels_list_response()
        )
        fetcher = ChannelFetcher(
            api_key="test-api-key", quota_tracker=tracker, _service=service
        )
        with pytest.raises(QuotaExceededError):
            fetcher.get_channel_info("UCabc123")


# ---------------------------------------------------------------------------
# Phase 5: エラーハンドリング
# ---------------------------------------------------------------------------


class TestChannelFetcherErrorHandling:
    """Tests for error handling in ChannelFetcher."""

    def test_異常系_APIエラーはAPIErrorに変換される(self) -> None:
        """HTTP errors from the API are converted to APIError."""
        from googleapiclient.errors import HttpError

        tracker = make_quota_tracker()
        service = MagicMock()
        http_error = HttpError(
            resp=MagicMock(status=403, reason="Forbidden"),
            content=b"Forbidden",
        )
        service.channels.return_value.list.return_value.execute.side_effect = http_error
        fetcher = ChannelFetcher(
            api_key="test-api-key", quota_tracker=tracker, _service=service
        )
        with pytest.raises(APIError):
            fetcher.get_channel_info("UCabc123")

    def test_異常系_list_all_videosでAPIErrorが発生する(self) -> None:
        """HTTP errors in list_all_videos() are converted to APIError."""
        from googleapiclient.errors import HttpError

        tracker = make_quota_tracker()
        service = MagicMock()
        http_error = HttpError(
            resp=MagicMock(status=500, reason="Internal Server Error"),
            content=b"Error",
        )
        service.playlistItems.return_value.list.return_value.execute.side_effect = (
            http_error
        )
        fetcher = ChannelFetcher(
            api_key="test-api-key", quota_tracker=tracker, _service=service
        )
        with pytest.raises(APIError):
            fetcher.list_all_videos("UCabc123", "UUabc123")
