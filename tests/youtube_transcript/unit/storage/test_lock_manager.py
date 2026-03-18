"""Unit tests for youtube_transcript LockManager class."""

from pathlib import Path

import pytest

from youtube_transcript.exceptions import FileLockError
from youtube_transcript.storage.lock_manager import LockManager


class TestLockManagerInit:
    def test_正常系_初期化成功(self, tmp_path: Path) -> None:
        manager = LockManager(tmp_path)
        assert manager.data_dir == tmp_path
        assert manager.default_timeout == 10.0

    def test_正常系_カスタムタイムアウトで初期化(self, tmp_path: Path) -> None:
        manager = LockManager(tmp_path, default_timeout=5.0)
        assert manager.default_timeout == 5.0

    def test_異常系_タイムアウトが0以下でValueError(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="timeout must be positive"):
            LockManager(tmp_path, default_timeout=0)

    def test_異常系_タイムアウトが負でValueError(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="timeout must be positive"):
            LockManager(tmp_path, default_timeout=-1.0)


class TestLockChannels:
    def test_正常系_チャンネルロックを取得して解放(self, tmp_path: Path) -> None:
        manager = LockManager(tmp_path)
        with manager.lock_channels():
            pass  # No exception should be raised

    def test_正常系_カスタムタイムアウトでロック(self, tmp_path: Path) -> None:
        manager = LockManager(tmp_path)
        with manager.lock_channels(timeout=5.0):
            pass

    def test_正常系_ロックファイルのパスはchannels_lock(self, tmp_path: Path) -> None:
        manager = LockManager(tmp_path)
        with manager.lock_channels():
            lock_file = tmp_path / "channels.lock"
            # Lock file exists while held
            assert lock_file.exists()


class TestLockVideos:
    def test_正常系_動画ロックを取得して解放(self, tmp_path: Path) -> None:
        manager = LockManager(tmp_path)
        with manager.lock_videos("UC_abc123"):
            pass

    def test_正常系_ロックファイルのパスはvideos_lock(self, tmp_path: Path) -> None:
        manager = LockManager(tmp_path)
        with manager.lock_videos("UC_abc123"):
            lock_file = tmp_path / "UC_abc123" / "videos.lock"
            assert lock_file.exists()

    def test_異常系_空channel_idでValueError(self, tmp_path: Path) -> None:
        manager = LockManager(tmp_path)
        with (
            pytest.raises(ValueError, match="channel_id cannot be empty"),
            manager.lock_videos(""),
        ):
            pass

    def test_正常系_ディレクトリが存在しなくても作成(self, tmp_path: Path) -> None:
        manager = LockManager(tmp_path)
        with manager.lock_videos("UC_new_channel"):
            channel_dir = tmp_path / "UC_new_channel"
            assert channel_dir.exists()


class TestLockTranscript:
    def test_正常系_トランスクリプトロックを取得して解放(self, tmp_path: Path) -> None:
        manager = LockManager(tmp_path)
        with manager.lock_transcript("UC_abc123", "abc1234567a"):
            pass

    def test_正常系_ロックファイルのパスはtranscript_lock(self, tmp_path: Path) -> None:
        manager = LockManager(tmp_path)
        with manager.lock_transcript("UC_abc123", "abc1234567a"):
            lock_file = tmp_path / "UC_abc123" / "abc1234567a" / "transcript.lock"
            assert lock_file.exists()

    def test_異常系_空channel_idでValueError(self, tmp_path: Path) -> None:
        manager = LockManager(tmp_path)
        with (
            pytest.raises(ValueError, match="channel_id cannot be empty"),
            manager.lock_transcript("", "abc1234567a"),
        ):
            pass

    def test_異常系_空video_idでValueError(self, tmp_path: Path) -> None:
        manager = LockManager(tmp_path)
        with (
            pytest.raises(ValueError, match="video_id cannot be empty"),
            manager.lock_transcript("UC_abc123", ""),
        ):
            pass

    def test_正常系_ディレクトリが存在しなくても作成(self, tmp_path: Path) -> None:
        manager = LockManager(tmp_path)
        with manager.lock_transcript("UC_new", "new_video_1"):
            video_dir = tmp_path / "UC_new" / "new_video_1"
            assert video_dir.exists()
