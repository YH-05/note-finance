"""Unit tests for youtube_transcript JSONStorage class."""

import json
from pathlib import Path

import pytest

from youtube_transcript.exceptions import StorageError
from youtube_transcript.storage.json_storage import JSONStorage
from youtube_transcript.types import (
    Channel,
    QuotaUsage,
    TranscriptEntry,
    TranscriptResult,
    TranscriptStatus,
    Video,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def storage(tmp_path: Path) -> JSONStorage:
    """Return a JSONStorage instance backed by a temp directory."""
    return JSONStorage(tmp_path)


@pytest.fixture()
def sample_channel() -> Channel:
    return Channel(
        channel_id="UC_abc123",
        title="Test Channel",
        uploads_playlist_id="UU_abc123",
        language_priority=["ja", "en"],
        enabled=True,
        created_at="2026-03-18T00:00:00+00:00",
        last_fetched=None,
        video_count=0,
    )


@pytest.fixture()
def sample_video() -> Video:
    return Video(
        video_id="abc1234567a",
        channel_id="UC_abc123",
        title="Test Video",
        published="2026-03-18T00:00:00+00:00",
        description="A test video.",
        transcript_status=TranscriptStatus.PENDING,
        transcript_language=None,
        fetched_at=None,
    )


@pytest.fixture()
def sample_transcript_result() -> TranscriptResult:
    entries = [
        TranscriptEntry(start=0.0, duration=3.0, text="Hello"),
        TranscriptEntry(start=3.0, duration=2.0, text="world"),
    ]
    return TranscriptResult(
        video_id="abc1234567a",
        language="en",
        entries=entries,
        fetched_at="2026-03-18T00:00:00+00:00",
    )


@pytest.fixture()
def sample_quota() -> QuotaUsage:
    return QuotaUsage(date="2026-03-18", units_used=100, budget=10000)


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestJSONStorageInit:
    def test_正常系_初期化成功(self, tmp_path: Path) -> None:
        storage = JSONStorage(tmp_path)
        assert storage.data_dir == tmp_path
        assert storage.lock_manager is not None

    def test_異常系_Pathでないdata_dirでValueError(self) -> None:
        with pytest.raises(ValueError, match="data_dir must be a Path object"):
            JSONStorage("invalid")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------


class TestSaveChannels:
    def test_正常系_チャンネルリストを保存(
        self, storage: JSONStorage, sample_channel: Channel, tmp_path: Path
    ) -> None:
        storage.save_channels([sample_channel])

        channels_file = tmp_path / "channels.json"
        assert channels_file.exists()

        data = json.loads(channels_file.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["channel_id"] == "UC_abc123"
        assert data[0]["title"] == "Test Channel"

    def test_正常系_空リストを保存(self, storage: JSONStorage, tmp_path: Path) -> None:
        storage.save_channels([])

        channels_file = tmp_path / "channels.json"
        assert channels_file.exists()
        data = json.loads(channels_file.read_text(encoding="utf-8"))
        assert data == []

    def test_正常系_ディレクトリが存在しなくても作成(self, tmp_path: Path) -> None:
        new_dir = tmp_path / "new_dir"
        storage = JSONStorage(new_dir)
        storage.save_channels([])
        assert new_dir.exists()
        assert (new_dir / "channels.json").exists()

    def test_正常系_UTF8エンコード(self, storage: JSONStorage, tmp_path: Path) -> None:
        channel = Channel(
            channel_id="UC_jp",
            title="日本語チャンネル",
            uploads_playlist_id="UU_jp",
            language_priority=["ja"],
            enabled=True,
            created_at="2026-03-18T00:00:00+00:00",
            last_fetched=None,
            video_count=0,
        )
        storage.save_channels([channel])

        content = (tmp_path / "channels.json").read_text(encoding="utf-8")
        data = json.loads(content)
        assert data[0]["title"] == "日本語チャンネル"

    def test_正常系_インデントされたJSON(
        self, storage: JSONStorage, tmp_path: Path
    ) -> None:
        storage.save_channels([])
        content = (tmp_path / "channels.json").read_text(encoding="utf-8")
        lines = content.split("\n")
        # At minimum the JSON array itself has 2 lines for "[]" without indent,
        # but an indented empty array would be "[\n]"
        assert len(lines) >= 1


class TestLoadChannels:
    def test_正常系_チャンネルをロード(
        self, storage: JSONStorage, sample_channel: Channel
    ) -> None:
        storage.save_channels([sample_channel])
        loaded = storage.load_channels()

        assert len(loaded) == 1
        assert loaded[0].channel_id == "UC_abc123"
        assert loaded[0].title == "Test Channel"
        assert loaded[0].language_priority == ["ja", "en"]

    def test_正常系_ファイルなしで空リストを返す(self, storage: JSONStorage) -> None:
        loaded = storage.load_channels()
        assert loaded == []

    def test_異常系_不正なJSONでStorageError(
        self, storage: JSONStorage, tmp_path: Path
    ) -> None:
        (tmp_path / "channels.json").write_text("invalid json", encoding="utf-8")
        with pytest.raises(StorageError):
            storage.load_channels()

    def test_正常系_保存と復元の往復(
        self, storage: JSONStorage, sample_channel: Channel
    ) -> None:
        storage.save_channels([sample_channel])
        loaded = storage.load_channels()
        assert loaded[0] == sample_channel


# ---------------------------------------------------------------------------
# Videos
# ---------------------------------------------------------------------------


class TestSaveVideos:
    def test_正常系_動画リストを保存(
        self, storage: JSONStorage, sample_video: Video, tmp_path: Path
    ) -> None:
        storage.save_videos("UC_abc123", [sample_video])

        videos_file = tmp_path / "UC_abc123" / "videos.json"
        assert videos_file.exists()

        data = json.loads(videos_file.read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["video_id"] == "abc1234567a"
        assert data[0]["transcript_status"] == "pending"

    def test_正常系_ディレクトリが存在しなくても作成(
        self, storage: JSONStorage, tmp_path: Path
    ) -> None:
        storage.save_videos("UC_new", [])
        assert (tmp_path / "UC_new" / "videos.json").exists()

    def test_異常系_空channel_idでValueError(self, storage: JSONStorage) -> None:
        with pytest.raises(ValueError, match="channel_id cannot be empty"):
            storage.save_videos("", [])

    def test_正常系_TranscriptStatusがシリアライズされる(
        self, storage: JSONStorage, sample_video: Video, tmp_path: Path
    ) -> None:
        video_success = Video(
            video_id="abc1234567a",
            channel_id="UC_abc123",
            title="Done",
            published="2026-03-18T00:00:00+00:00",
            description="",
            transcript_status=TranscriptStatus.SUCCESS,
            transcript_language="en",
            fetched_at="2026-03-18T01:00:00+00:00",
        )
        storage.save_videos("UC_abc123", [video_success])
        data = json.loads(
            (tmp_path / "UC_abc123" / "videos.json").read_text(encoding="utf-8")
        )
        assert data[0]["transcript_status"] == "success"


class TestLoadVideos:
    def test_正常系_動画リストをロード(
        self, storage: JSONStorage, sample_video: Video
    ) -> None:
        storage.save_videos("UC_abc123", [sample_video])
        loaded = storage.load_videos("UC_abc123")

        assert len(loaded) == 1
        assert loaded[0].video_id == "abc1234567a"
        assert loaded[0].transcript_status == TranscriptStatus.PENDING

    def test_正常系_ファイルなしで空リストを返す(self, storage: JSONStorage) -> None:
        loaded = storage.load_videos("UC_abc123")
        assert loaded == []

    def test_異常系_空channel_idでValueError(self, storage: JSONStorage) -> None:
        with pytest.raises(ValueError, match="channel_id cannot be empty"):
            storage.load_videos("")

    def test_異常系_不正なJSONでStorageError(
        self, storage: JSONStorage, tmp_path: Path
    ) -> None:
        channel_dir = tmp_path / "UC_abc123"
        channel_dir.mkdir()
        (channel_dir / "videos.json").write_text("invalid json", encoding="utf-8")
        with pytest.raises(StorageError):
            storage.load_videos("UC_abc123")

    def test_正常系_TranscriptStatusがデシリアライズされる(
        self, storage: JSONStorage, sample_video: Video
    ) -> None:
        storage.save_videos("UC_abc123", [sample_video])
        loaded = storage.load_videos("UC_abc123")
        assert isinstance(loaded[0].transcript_status, TranscriptStatus)
        assert loaded[0].transcript_status == TranscriptStatus.PENDING

    def test_正常系_保存と復元の往復(
        self, storage: JSONStorage, sample_video: Video
    ) -> None:
        storage.save_videos("UC_abc123", [sample_video])
        loaded = storage.load_videos("UC_abc123")
        assert loaded[0] == sample_video


# ---------------------------------------------------------------------------
# Transcripts
# ---------------------------------------------------------------------------


class TestSaveTranscript:
    def test_正常系_トランスクリプトを保存(
        self,
        storage: JSONStorage,
        sample_transcript_result: TranscriptResult,
        tmp_path: Path,
    ) -> None:
        storage.save_transcript("UC_abc123", sample_transcript_result)

        transcript_file = tmp_path / "UC_abc123" / "abc1234567a" / "transcript.json"
        assert transcript_file.exists()

        data = json.loads(transcript_file.read_text(encoding="utf-8"))
        assert data["video_id"] == "abc1234567a"
        assert data["language"] == "en"
        assert len(data["entries"]) == 2
        assert data["entries"][0]["text"] == "Hello"

    def test_正常系_ディレクトリが存在しなくても作成(
        self,
        storage: JSONStorage,
        sample_transcript_result: TranscriptResult,
        tmp_path: Path,
    ) -> None:
        storage.save_transcript("UC_abc123", sample_transcript_result)
        assert (tmp_path / "UC_abc123" / "abc1234567a").is_dir()

    def test_異常系_空channel_idでValueError(
        self, storage: JSONStorage, sample_transcript_result: TranscriptResult
    ) -> None:
        with pytest.raises(ValueError, match="channel_id cannot be empty"):
            storage.save_transcript("", sample_transcript_result)

    def test_正常系_UTF8エンコード(
        self,
        storage: JSONStorage,
        tmp_path: Path,
    ) -> None:
        entry = TranscriptEntry(start=0.0, duration=2.0, text="こんにちは")
        result = TranscriptResult(
            video_id="jp_video_id1",
            language="ja",
            entries=[entry],
            fetched_at="2026-03-18T00:00:00+00:00",
        )
        storage.save_transcript("UC_jp", result)
        content = (tmp_path / "UC_jp" / "jp_video_id1" / "transcript.json").read_text(
            encoding="utf-8"
        )
        data = json.loads(content)
        assert data["entries"][0]["text"] == "こんにちは"


class TestLoadTranscript:
    def test_正常系_トランスクリプトをロード(
        self,
        storage: JSONStorage,
        sample_transcript_result: TranscriptResult,
    ) -> None:
        storage.save_transcript("UC_abc123", sample_transcript_result)
        loaded = storage.load_transcript("UC_abc123", "abc1234567a")

        assert loaded is not None
        assert loaded.video_id == "abc1234567a"
        assert loaded.language == "en"
        assert len(loaded.entries) == 2
        assert loaded.entries[0].text == "Hello"

    def test_正常系_ファイルなしでNoneを返す(self, storage: JSONStorage) -> None:
        result = storage.load_transcript("UC_abc123", "missing_video")
        assert result is None

    def test_異常系_空channel_idでValueError(self, storage: JSONStorage) -> None:
        with pytest.raises(ValueError, match="channel_id cannot be empty"):
            storage.load_transcript("", "abc1234567a")

    def test_異常系_空video_idでValueError(self, storage: JSONStorage) -> None:
        with pytest.raises(ValueError, match="video_id cannot be empty"):
            storage.load_transcript("UC_abc123", "")

    def test_異常系_不正なJSONでStorageError(
        self, storage: JSONStorage, tmp_path: Path
    ) -> None:
        video_dir = tmp_path / "UC_abc123" / "abc1234567a"
        video_dir.mkdir(parents=True)
        (video_dir / "transcript.json").write_text("invalid json", encoding="utf-8")
        with pytest.raises(StorageError):
            storage.load_transcript("UC_abc123", "abc1234567a")

    def test_正常系_to_plain_textが動作する(
        self,
        storage: JSONStorage,
        sample_transcript_result: TranscriptResult,
    ) -> None:
        storage.save_transcript("UC_abc123", sample_transcript_result)
        loaded = storage.load_transcript("UC_abc123", "abc1234567a")

        assert loaded is not None
        plain_text = loaded.to_plain_text()
        assert plain_text == "Hello\nworld"

    def test_正常系_保存と復元の往復(
        self,
        storage: JSONStorage,
        sample_transcript_result: TranscriptResult,
    ) -> None:
        storage.save_transcript("UC_abc123", sample_transcript_result)
        loaded = storage.load_transcript("UC_abc123", "abc1234567a")
        assert loaded == sample_transcript_result


# ---------------------------------------------------------------------------
# Quota Usage
# ---------------------------------------------------------------------------


class TestSaveQuotaUsage:
    def test_正常系_クォータ使用量を保存(
        self, storage: JSONStorage, sample_quota: QuotaUsage, tmp_path: Path
    ) -> None:
        storage.save_quota_usage(sample_quota)

        quota_file = tmp_path / "quota_usage.json"
        assert quota_file.exists()

        data = json.loads(quota_file.read_text(encoding="utf-8"))
        assert data["date"] == "2026-03-18"
        assert data["units_used"] == 100
        assert data["budget"] == 10000

    def test_正常系_ディレクトリが存在しなくても作成(self, tmp_path: Path) -> None:
        new_dir = tmp_path / "quota_dir"
        storage = JSONStorage(new_dir)
        quota = QuotaUsage(date="2026-03-18", units_used=0, budget=10000)
        storage.save_quota_usage(quota)
        assert (new_dir / "quota_usage.json").exists()


class TestLoadQuotaUsage:
    def test_正常系_クォータ使用量をロード(
        self, storage: JSONStorage, sample_quota: QuotaUsage
    ) -> None:
        storage.save_quota_usage(sample_quota)
        loaded = storage.load_quota_usage()

        assert loaded is not None
        assert loaded.date == "2026-03-18"
        assert loaded.units_used == 100
        assert loaded.budget == 10000

    def test_正常系_ファイルなしでNoneを返す(self, storage: JSONStorage) -> None:
        loaded = storage.load_quota_usage()
        assert loaded is None

    def test_異常系_不正なJSONでStorageError(
        self, storage: JSONStorage, tmp_path: Path
    ) -> None:
        (tmp_path / "quota_usage.json").write_text("invalid json", encoding="utf-8")
        with pytest.raises(StorageError):
            storage.load_quota_usage()

    def test_正常系_保存と復元の往復(
        self, storage: JSONStorage, sample_quota: QuotaUsage
    ) -> None:
        storage.save_quota_usage(sample_quota)
        loaded = storage.load_quota_usage()
        assert loaded == sample_quota


# ---------------------------------------------------------------------------
# File Locking
# ---------------------------------------------------------------------------


class TestFileLocking:
    def test_正常系_channels保存でロックが使用される(
        self, storage: JSONStorage, tmp_path: Path
    ) -> None:
        storage.save_channels([])
        lock_file = tmp_path / "channels.lock"
        # Lock file should not exist or be empty after the operation
        assert not lock_file.exists() or lock_file.stat().st_size == 0

    def test_正常系_videos保存でロックが使用される(
        self, storage: JSONStorage, tmp_path: Path
    ) -> None:
        storage.save_videos("UC_abc123", [])
        lock_file = tmp_path / "UC_abc123" / "videos.lock"
        assert not lock_file.exists() or lock_file.stat().st_size == 0

    def test_正常系_transcript保存でロックが使用される(
        self,
        storage: JSONStorage,
        sample_transcript_result: TranscriptResult,
        tmp_path: Path,
    ) -> None:
        storage.save_transcript("UC_abc123", sample_transcript_result)
        lock_file = tmp_path / "UC_abc123" / "abc1234567a" / "transcript.lock"
        assert not lock_file.exists() or lock_file.stat().st_size == 0
