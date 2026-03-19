"""Unit tests for ChannelManager.

TDD Red phase: tests covering acceptance criteria from Issue #166.

Acceptance criteria:
- ChannelManager CRUD が機能する
- add() / list() / get() / remove() / update() が正常に動作する
- URL正規化 + 重複チェック + JSONStorage 保存
- `test_channel_manager.py` の全テストが通過する
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from youtube_transcript.exceptions import (
    ChannelAlreadyExistsError,
    ChannelNotFoundError,
)
from youtube_transcript.services.channel_manager import ChannelManager
from youtube_transcript.types import Channel

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_data_dir(tmp_path: Path) -> Path:
    """Temporary data directory for tests."""
    return tmp_path / "youtube_transcript"


@pytest.fixture()
def manager(tmp_data_dir: Path) -> ChannelManager:
    """ChannelManager with a temporary data directory."""
    return ChannelManager(tmp_data_dir)


def make_channel(
    channel_id: str = "UCabc123",
    title: str = "Test Channel",
    uploads_playlist_id: str = "UUabc123",
    language_priority: list[str] | None = None,
    enabled: bool = True,
) -> Channel:
    """Helper to create a Channel instance for testing."""
    if language_priority is None:
        language_priority = ["ja", "en"]
    return Channel(
        channel_id=channel_id,
        title=title,
        uploads_playlist_id=uploads_playlist_id,
        language_priority=language_priority,
        enabled=enabled,
        created_at="2026-03-18T00:00:00+00:00",
        last_fetched=None,
        video_count=0,
    )


# ---------------------------------------------------------------------------
# ChannelManager Initialization
# ---------------------------------------------------------------------------


class TestChannelManagerInit:
    """Tests for ChannelManager initialization."""

    def test_正常系_Pathで初期化できる(self, tmp_data_dir: Path) -> None:
        """ChannelManager can be initialized with a Path object."""
        manager = ChannelManager(tmp_data_dir)
        assert manager.data_dir == tmp_data_dir

    def test_異常系_非Pathで初期化するとValueError(self, tmp_path: Path) -> None:
        """ChannelManager raises ValueError when given a non-Path data_dir."""
        with pytest.raises(ValueError, match="data_dir must be a Path object"):
            ChannelManager("not_a_path")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# add() tests
# ---------------------------------------------------------------------------


class TestAdd:
    """Tests for ChannelManager.add()."""

    def test_正常系_チャンネルIDで追加できる(self, manager: ChannelManager) -> None:
        """add() succeeds with a raw channel ID."""
        channel = manager.add(
            url_or_id="UCabc123",
            title="Test Channel",
            language_priority=["ja", "en"],
        )
        assert channel.channel_id == "UCabc123"
        assert channel.title == "Test Channel"
        assert channel.language_priority == ["ja", "en"]
        assert channel.enabled is True

    def test_正常系_handleURLで追加できる(self, manager: ChannelManager) -> None:
        """add() succeeds with an @handle URL."""
        channel = manager.add(
            url_or_id="https://www.youtube.com/@TestChannel",
            title="Handle Channel",
        )
        assert channel.title == "Handle Channel"
        assert channel.enabled is True

    def test_正常系_デフォルト言語優先度が設定される(
        self, manager: ChannelManager
    ) -> None:
        """add() uses ['ja', 'en'] as default language_priority."""
        channel = manager.add(url_or_id="UCabc123", title="Test Channel")
        assert channel.language_priority == ["ja", "en"]

    def test_正常系_enabled_Falseで追加できる(self, manager: ChannelManager) -> None:
        """add() supports enabled=False."""
        channel = manager.add(
            url_or_id="UCabc123",
            title="Test Channel",
            enabled=False,
        )
        assert channel.enabled is False

    def test_正常系_追加後にJSONStorageに保存される(
        self, manager: ChannelManager
    ) -> None:
        """add() persists channel to JSON storage."""
        manager.add(url_or_id="UCabc123", title="Test Channel")
        channels = manager.list()
        assert len(channels) == 1
        assert channels[0].channel_id == "UCabc123"

    def test_正常系_created_atが設定される(self, manager: ChannelManager) -> None:
        """add() sets created_at timestamp."""
        channel = manager.add(url_or_id="UCabc123", title="Test Channel")
        assert channel.created_at != ""
        assert channel.last_fetched is None
        assert channel.video_count == 0

    def test_異常系_重複チャンネルIDでChannelAlreadyExistsError(
        self, manager: ChannelManager
    ) -> None:
        """add() raises ChannelAlreadyExistsError for duplicate channel_id."""
        manager.add(url_or_id="UCabc123", title="First Channel")
        with pytest.raises(ChannelAlreadyExistsError):
            manager.add(url_or_id="UCabc123", title="Second Channel")

    def test_異常系_重複URLでChannelAlreadyExistsError(
        self, manager: ChannelManager
    ) -> None:
        """add() with same channel URL but different URL format raises error."""
        manager.add(
            url_or_id="https://www.youtube.com/channel/UCabc123",
            title="First Channel",
        )
        with pytest.raises(ChannelAlreadyExistsError):
            manager.add(
                url_or_id="UCabc123",
                title="Second Channel",
            )


# ---------------------------------------------------------------------------
# list() tests
# ---------------------------------------------------------------------------


class TestList:
    """Tests for ChannelManager.list()."""

    def test_正常系_空リストを返す(self, manager: ChannelManager) -> None:
        """list() returns empty list when no channels exist."""
        channels = manager.list()
        assert channels == []

    def test_正常系_全チャンネルを返す(self, manager: ChannelManager) -> None:
        """list() returns all channels."""
        manager.add(url_or_id="UCabc123", title="Channel 1")
        manager.add(url_or_id="UCdef456", title="Channel 2")
        channels = manager.list()
        assert len(channels) == 2

    def test_正常系_enabled_onlyフィルタが機能する(
        self, manager: ChannelManager
    ) -> None:
        """list(enabled_only=True) returns only enabled channels."""
        manager.add(url_or_id="UCabc123", title="Enabled", enabled=True)
        manager.add(url_or_id="UCdef456", title="Disabled", enabled=False)
        channels = manager.list(enabled_only=True)
        assert len(channels) == 1
        assert channels[0].channel_id == "UCabc123"

    def test_正常系_enabled_only_Falseで全件返す(self, manager: ChannelManager) -> None:
        """list(enabled_only=False) returns all channels including disabled."""
        manager.add(url_or_id="UCabc123", title="Enabled", enabled=True)
        manager.add(url_or_id="UCdef456", title="Disabled", enabled=False)
        channels = manager.list(enabled_only=False)
        assert len(channels) == 2


# ---------------------------------------------------------------------------
# get() tests
# ---------------------------------------------------------------------------


class TestGet:
    """Tests for ChannelManager.get()."""

    def test_正常系_チャンネルIDで取得できる(self, manager: ChannelManager) -> None:
        """get() returns channel by channel_id."""
        manager.add(url_or_id="UCabc123", title="Test Channel")
        channel = manager.get("UCabc123")
        assert channel.channel_id == "UCabc123"
        assert channel.title == "Test Channel"

    def test_異常系_存在しないIDでChannelNotFoundError(
        self, manager: ChannelManager
    ) -> None:
        """get() raises ChannelNotFoundError for non-existent channel_id."""
        with pytest.raises(ChannelNotFoundError):
            manager.get("UCnonexistent")


# ---------------------------------------------------------------------------
# remove() tests
# ---------------------------------------------------------------------------


class TestRemove:
    """Tests for ChannelManager.remove()."""

    def test_正常系_チャンネルを削除できる(self, manager: ChannelManager) -> None:
        """remove() deletes the channel from storage."""
        manager.add(url_or_id="UCabc123", title="Test Channel")
        manager.remove("UCabc123")
        channels = manager.list()
        assert len(channels) == 0

    def test_正常系_削除後に他のチャンネルが残る(self, manager: ChannelManager) -> None:
        """remove() only deletes the specified channel."""
        manager.add(url_or_id="UCabc123", title="Channel 1")
        manager.add(url_or_id="UCdef456", title="Channel 2")
        manager.remove("UCabc123")
        channels = manager.list()
        assert len(channels) == 1
        assert channels[0].channel_id == "UCdef456"

    def test_異常系_存在しないIDでChannelNotFoundError(
        self, manager: ChannelManager
    ) -> None:
        """remove() raises ChannelNotFoundError for non-existent channel_id."""
        with pytest.raises(ChannelNotFoundError):
            manager.remove("UCnonexistent")


# ---------------------------------------------------------------------------
# update() tests
# ---------------------------------------------------------------------------


class TestUpdate:
    """Tests for ChannelManager.update()."""

    def test_正常系_titleを更新できる(self, manager: ChannelManager) -> None:
        """update() can change the title."""
        manager.add(url_or_id="UCabc123", title="Old Title")
        updated = manager.update("UCabc123", title="New Title")
        assert updated.title == "New Title"

    def test_正常系_language_priorityを更新できる(
        self, manager: ChannelManager
    ) -> None:
        """update() can change language_priority."""
        manager.add(url_or_id="UCabc123", title="Test Channel")
        updated = manager.update("UCabc123", language_priority=["en", "ja"])
        assert updated.language_priority == ["en", "ja"]

    def test_正常系_enabledを更新できる(self, manager: ChannelManager) -> None:
        """update() can change enabled status."""
        manager.add(url_or_id="UCabc123", title="Test Channel", enabled=True)
        updated = manager.update("UCabc123", enabled=False)
        assert updated.enabled is False

    def test_正常系_更新がJSONStorageに保存される(
        self, manager: ChannelManager
    ) -> None:
        """update() persists changes to JSON storage."""
        manager.add(url_or_id="UCabc123", title="Old Title")
        manager.update("UCabc123", title="New Title")
        channel = manager.get("UCabc123")
        assert channel.title == "New Title"

    def test_正常系_Noneフィールドは変更されない(self, manager: ChannelManager) -> None:
        """update() does not change fields passed as None."""
        manager.add(
            url_or_id="UCabc123",
            title="Original Title",
            language_priority=["ja"],
        )
        updated = manager.update("UCabc123", enabled=False)
        assert updated.title == "Original Title"
        assert updated.language_priority == ["ja"]

    def test_異常系_存在しないIDでChannelNotFoundError(
        self, manager: ChannelManager
    ) -> None:
        """update() raises ChannelNotFoundError for non-existent channel_id."""
        with pytest.raises(ChannelNotFoundError):
            manager.update("UCnonexistent", title="New Title")
