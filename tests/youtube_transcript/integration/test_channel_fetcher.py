"""Integration tests for ChannelFetcher.

実際の YouTube Data API v3 を使用してチャンネル情報と動画一覧を取得する。

Notes
-----
- CI では ``@pytest.mark.integration`` により自動スキップされる。
- ``YT_API_KEY`` 環境変数が未設定の場合は ``pytest.skip()`` でスキップする。
- チャンネル ID: "UC295-Dw4tzbADK2UKBbKBXg" (YouTube 公式チャンネル)
"""

import os
from pathlib import Path

import pytest

from youtube_transcript.core.channel_fetcher import ChannelFetcher
from youtube_transcript.exceptions import APIError, ChannelNotFoundError
from youtube_transcript.types import Channel, Video

# テストで使用する実際の YouTube チャンネル
# YouTube 公式チャンネル
_TEST_CHANNEL_ID = "UC295-Dw4tzbADK2UKBbKBXg"
_TEST_CHANNEL_URL = f"https://www.youtube.com/channel/{_TEST_CHANNEL_ID}"

# 存在しない（無効な）チャンネル ID
_NONEXISTENT_CHANNEL_ID = "UCxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"


def _get_api_key() -> str:
    """環境変数から API キーを取得する。未設定ならスキップ。"""
    api_key = os.environ.get("YT_API_KEY", "")
    if not api_key:
        pytest.skip("YT_API_KEY not set")
    return api_key


class _DummyQuotaTracker:
    """テスト用のダミー QuotaTracker.

    QuotaTracker の ``consume(units)`` インターフェースを実装する。
    常に quota 消費を許可する。
    """

    def consume(self, units: int) -> None:
        """quota 消費を記録せずに通過させる."""


class TestChannelFetcherIntegration:
    """ChannelFetcher の統合テスト（実際の YouTube Data API v3 を呼ぶ）."""

    @pytest.mark.integration
    def test_正常系_実際のチャンネルからチャンネル情報を取得できる(
        self,
        tmp_path: Path,
    ) -> None:
        """実際のチャンネル ID からチャンネル情報を取得できることを確認する."""
        api_key = _get_api_key()
        tracker = _DummyQuotaTracker()
        fetcher = ChannelFetcher(api_key=api_key, quota_tracker=tracker)

        channel = fetcher.get_channel_info(_TEST_CHANNEL_ID)

        assert isinstance(channel, Channel)
        assert channel.channel_id == _TEST_CHANNEL_ID
        assert len(channel.title) > 0
        # uploads_playlist_id は通常 "UU" + channel_id[2:] の形式
        assert channel.uploads_playlist_id.startswith("UU")

    @pytest.mark.integration
    def test_正常系_チャンネルURLからチャンネル情報を取得できる(
        self,
        tmp_path: Path,
    ) -> None:
        """URL 形式のチャンネル指定からチャンネル情報を取得できることを確認する."""
        api_key = _get_api_key()
        tracker = _DummyQuotaTracker()
        fetcher = ChannelFetcher(api_key=api_key, quota_tracker=tracker)

        channel = fetcher.get_channel_info(_TEST_CHANNEL_URL)

        assert isinstance(channel, Channel)
        assert channel.channel_id == _TEST_CHANNEL_ID
        assert channel.uploads_playlist_id != ""

    @pytest.mark.integration
    def test_正常系_uploads_playlist_idが取得できる(
        self,
        tmp_path: Path,
    ) -> None:
        """チャンネルの uploads_playlist_id が正常に取得できることを確認する."""
        api_key = _get_api_key()
        tracker = _DummyQuotaTracker()
        fetcher = ChannelFetcher(api_key=api_key, quota_tracker=tracker)

        channel = fetcher.get_channel_info(_TEST_CHANNEL_ID)

        # uploads_playlist_id は空でない文字列
        assert isinstance(channel.uploads_playlist_id, str)
        assert len(channel.uploads_playlist_id) > 0

    @pytest.mark.integration
    def test_正常系_動画リストを取得できる(
        self,
        tmp_path: Path,
    ) -> None:
        """uploads_playlist_id からチャンネルの動画一覧を取得できることを確認する.

        YouTube 公式チャンネルは多数の動画を持つが、テストでは 1 件以上あれば OK。
        """
        api_key = _get_api_key()
        tracker = _DummyQuotaTracker()
        fetcher = ChannelFetcher(api_key=api_key, quota_tracker=tracker)

        channel = fetcher.get_channel_info(_TEST_CHANNEL_ID)
        videos = fetcher.list_all_videos(
            channel_id=channel.channel_id,
            uploads_playlist_id=channel.uploads_playlist_id,
        )

        assert isinstance(videos, list)
        assert len(videos) > 0

        # 各 Video オブジェクトの構造を確認
        first_video = videos[0]
        assert isinstance(first_video, Video)
        assert first_video.channel_id == _TEST_CHANNEL_ID
        assert len(first_video.video_id) == 11  # YouTube 動画 ID は 11 文字
        assert isinstance(first_video.title, str)

    @pytest.mark.integration
    def test_異常系_無効なチャンネルIDでChannelNotFoundError(
        self,
        tmp_path: Path,
    ) -> None:
        """存在しないチャンネル ID に対して ChannelNotFoundError が発生することを確認する."""
        api_key = _get_api_key()
        tracker = _DummyQuotaTracker()
        fetcher = ChannelFetcher(api_key=api_key, quota_tracker=tracker)

        with pytest.raises(ChannelNotFoundError):
            fetcher.get_channel_info(_NONEXISTENT_CHANNEL_ID)

    @pytest.mark.integration
    def test_異常系_無効なAPIキーでAPIError(
        self,
        tmp_path: Path,
    ) -> None:
        """無効な API キーに対して APIError が発生することを確認する."""
        # YT_API_KEY のセットは確認済みだが、意図的に無効なキーを使用
        _ = _get_api_key()  # スキップ条件チェックのみ
        tracker = _DummyQuotaTracker()
        fetcher = ChannelFetcher(
            api_key="INVALID_API_KEY_FOR_TEST", quota_tracker=tracker
        )

        with pytest.raises(APIError):
            fetcher.get_channel_info(_TEST_CHANNEL_ID)
