"""Unit tests for note_publisher.config module.

Tests cover:
- ``load_config()`` returns default ``NotePublisherConfig``.
- Environment variable overrides for each field.
- Invalid environment variable values are handled gracefully.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from note_publisher.config import load_config
from note_publisher.types import NotePublisherConfig

if TYPE_CHECKING:
    import pytest


class TestLoadConfig:
    """Tests for the ``load_config`` function."""

    # -----------------------------------------------------------------
    # Default values
    # -----------------------------------------------------------------

    def test_正常系_デフォルト値でNotePublisherConfigを返す(self) -> None:
        """環境変数未設定時にデフォルト値のConfigが返されることを確認。"""
        config = load_config()

        assert isinstance(config, NotePublisherConfig)
        assert config.headless is True
        assert config.timeout_ms == 30000
        assert config.typing_delay_ms == 50
        assert config.storage_state_path == Path("data/config/note-storage-state.json")

    # -----------------------------------------------------------------
    # Environment variable overrides
    # -----------------------------------------------------------------

    def test_正常系_NOTE_HEADLESSでheadlessをオーバーライドできる(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """NOTE_HEADLESS=false でheadlessがFalseになることを確認。"""
        monkeypatch.setenv("NOTE_HEADLESS", "false")
        config = load_config()

        assert config.headless is False

    def test_正常系_NOTE_HEADLESS_trueでheadlessがTrueになる(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """NOTE_HEADLESS=true でheadlessがTrueになることを確認。"""
        monkeypatch.setenv("NOTE_HEADLESS", "true")
        config = load_config()

        assert config.headless is True

    def test_正常系_NOTE_HEADLESS_0でheadlessがFalseになる(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """NOTE_HEADLESS=0 でheadlessがFalseになることを確認。"""
        monkeypatch.setenv("NOTE_HEADLESS", "0")
        config = load_config()

        assert config.headless is False

    def test_正常系_NOTE_HEADLESS_1でheadlessがTrueになる(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """NOTE_HEADLESS=1 でheadlessがTrueになることを確認。"""
        monkeypatch.setenv("NOTE_HEADLESS", "1")
        config = load_config()

        assert config.headless is True

    def test_正常系_NOTE_TIMEOUT_MSでtimeout_msをオーバーライドできる(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """NOTE_TIMEOUT_MS=60000 でtimeout_msが60000になることを確認。"""
        monkeypatch.setenv("NOTE_TIMEOUT_MS", "60000")
        config = load_config()

        assert config.timeout_ms == 60000

    def test_正常系_NOTE_TYPING_DELAY_MSでtyping_delay_msをオーバーライドできる(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """NOTE_TYPING_DELAY_MS=100 でtyping_delay_msが100になることを確認。"""
        monkeypatch.setenv("NOTE_TYPING_DELAY_MS", "100")
        config = load_config()

        assert config.typing_delay_ms == 100

    def test_正常系_NOTE_SESSION_PATHでstorage_state_pathをオーバーライドできる(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """NOTE_SESSION_PATH でstorage_state_pathが変更されることを確認。"""
        monkeypatch.setenv("NOTE_SESSION_PATH", "/custom/path/state.json")
        config = load_config()

        assert config.storage_state_path == Path("/custom/path/state.json")

    def test_正常系_複数の環境変数を同時にオーバーライドできる(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """複数の環境変数を同時に設定した場合に全てオーバーライドされることを確認。"""
        monkeypatch.setenv("NOTE_HEADLESS", "false")
        monkeypatch.setenv("NOTE_TIMEOUT_MS", "10000")
        monkeypatch.setenv("NOTE_TYPING_DELAY_MS", "200")
        monkeypatch.setenv("NOTE_SESSION_PATH", "/tmp/state.json")

        config = load_config()

        assert config.headless is False
        assert config.timeout_ms == 10000
        assert config.typing_delay_ms == 200
        assert config.storage_state_path == Path("/tmp/state.json")

    # -----------------------------------------------------------------
    # Invalid environment variable values
    # -----------------------------------------------------------------

    def test_異常系_NOTE_TIMEOUT_MSが数値でない場合デフォルト値を使用する(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """NOTE_TIMEOUT_MS に非数値が設定された場合デフォルト値が使われることを確認。"""
        monkeypatch.setenv("NOTE_TIMEOUT_MS", "not_a_number")
        config = load_config()

        assert config.timeout_ms == 30000

    def test_異常系_NOTE_TYPING_DELAY_MSが数値でない場合デフォルト値を使用する(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """NOTE_TYPING_DELAY_MS に非数値が設定された場合デフォルト値が使われることを確認。"""
        monkeypatch.setenv("NOTE_TYPING_DELAY_MS", "invalid")
        config = load_config()

        assert config.typing_delay_ms == 50

    def test_異常系_NOTE_TIMEOUT_MSがバリデーション範囲外の場合デフォルト値を使用する(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """NOTE_TIMEOUT_MS が1000未満の場合デフォルト値が使われることを確認。"""
        monkeypatch.setenv("NOTE_TIMEOUT_MS", "500")
        config = load_config()

        assert config.timeout_ms == 30000

    def test_異常系_NOTE_TYPING_DELAY_MSが負の値の場合デフォルト値を使用する(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """NOTE_TYPING_DELAY_MS が負の値の場合デフォルト値が使われることを確認。"""
        monkeypatch.setenv("NOTE_TYPING_DELAY_MS", "-10")
        config = load_config()

        assert config.typing_delay_ms == 50

    # -----------------------------------------------------------------
    # Edge cases
    # -----------------------------------------------------------------

    def test_エッジケース_NOTE_HEADLESS_空文字列でデフォルト値を使用する(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """NOTE_HEADLESS が空文字列の場合デフォルト値が使われることを確認。"""
        monkeypatch.setenv("NOTE_HEADLESS", "")
        config = load_config()

        assert config.headless is True

    def test_エッジケース_NOTE_SESSION_PATH_空文字列でデフォルト値を使用する(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """NOTE_SESSION_PATH が空文字列の場合デフォルト値が使われることを確認。"""
        monkeypatch.setenv("NOTE_SESSION_PATH", "")
        config = load_config()

        assert config.storage_state_path == Path("data/config/note-storage-state.json")

    def test_エッジケース_環境変数未設定時にデフォルト値が保持される(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """環境変数が明示的に削除された場合でもデフォルト値が返ることを確認。"""
        monkeypatch.delenv("NOTE_HEADLESS", raising=False)
        monkeypatch.delenv("NOTE_TIMEOUT_MS", raising=False)
        monkeypatch.delenv("NOTE_TYPING_DELAY_MS", raising=False)
        monkeypatch.delenv("NOTE_SESSION_PATH", raising=False)

        config = load_config()

        assert config.headless is True
        assert config.timeout_ms == 30000
        assert config.typing_delay_ms == 50
        assert config.storage_state_path == Path("data/config/note-storage-state.json")
