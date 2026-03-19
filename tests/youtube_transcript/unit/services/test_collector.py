"""Unit tests for Collector.

TDD Red phase: tests covering acceptance criteria from Issue #166.

Acceptance criteria:
- Collector.collect() が5ステップフローを実行する
- collect_all() で全有効チャンネル順次処理
- quota 超過時に適切にハンドルする
- `test_collector.py` の全テストが通過する
"""

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from youtube_transcript.exceptions import (
    ChannelNotFoundError,
    QuotaExceededError,
)
from youtube_transcript.services.channel_manager import ChannelManager
from youtube_transcript.services.collector import Collector
from youtube_transcript.types import (
    Channel,
    CollectResult,
    TranscriptResult,
    TranscriptStatus,
    Video,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_data_dir(tmp_path: Path) -> Path:
    """Temporary data directory for tests."""
    return tmp_path / "youtube_transcript"


def make_channel(
    channel_id: str = "UCabc123",
    title: str = "Test Channel",
    uploads_playlist_id: str = "UUabc123",
    enabled: bool = True,
) -> Channel:
    """Helper to create a Channel instance for testing."""
    return Channel(
        channel_id=channel_id,
        title=title,
        uploads_playlist_id=uploads_playlist_id,
        language_priority=["ja", "en"],
        enabled=enabled,
        created_at="2026-03-18T00:00:00+00:00",
        last_fetched=None,
        video_count=0,
    )


def make_video(
    video_id: str,
    channel_id: str = "UCabc123",
    transcript_status: TranscriptStatus = TranscriptStatus.PENDING,
) -> Video:
    """Helper to create a Video instance for testing."""
    return Video(
        video_id=video_id,
        channel_id=channel_id,
        title=f"Video {video_id}",
        published="2026-03-18T00:00:00+00:00",
        description="",
        transcript_status=transcript_status,
        transcript_language=None,
        fetched_at=None,
    )


def make_transcript_result(video_id: str = "vid1234567a") -> TranscriptResult:
    """Helper to create a TranscriptResult for testing."""
    from youtube_transcript.types import TranscriptEntry

    return TranscriptResult(
        video_id=video_id,
        language="ja",
        entries=[TranscriptEntry(start=0.0, duration=3.0, text="テスト")],
        fetched_at="2026-03-18T00:00:00+00:00",
    )


@pytest.fixture()
def mock_channel_fetcher() -> MagicMock:
    """Mock for ChannelFetcher."""
    fetcher = MagicMock()
    fetcher.list_all_videos.return_value = [
        make_video("vid1234567a"),
        make_video("vid2345678b"),
    ]
    return fetcher


@pytest.fixture()
def mock_transcript_fetcher() -> MagicMock:
    """Mock for TranscriptFetcher."""
    fetcher = MagicMock()
    fetcher.fetch.return_value = make_transcript_result("vid1234567a")
    return fetcher


@pytest.fixture()
def mock_quota_tracker() -> MagicMock:
    """Mock for QuotaTracker."""
    tracker = MagicMock()
    tracker.remaining.return_value = 9000
    return tracker


@pytest.fixture()
def collector(
    tmp_data_dir: Path,
    mock_channel_fetcher: MagicMock,
    mock_transcript_fetcher: MagicMock,
    mock_quota_tracker: MagicMock,
) -> Collector:
    """Collector with mocked dependencies."""
    return Collector(
        data_dir=tmp_data_dir,
        channel_fetcher=mock_channel_fetcher,
        transcript_fetcher=mock_transcript_fetcher,
        quota_tracker=mock_quota_tracker,
    )


# ---------------------------------------------------------------------------
# Collector Initialization
# ---------------------------------------------------------------------------


class TestCollectorInit:
    """Tests for Collector initialization."""

    def test_正常系_依存性注入で初期化できる(
        self,
        tmp_data_dir: Path,
        mock_channel_fetcher: MagicMock,
        mock_transcript_fetcher: MagicMock,
        mock_quota_tracker: MagicMock,
    ) -> None:
        """Collector can be initialized with injected dependencies."""
        c = Collector(
            data_dir=tmp_data_dir,
            channel_fetcher=mock_channel_fetcher,
            transcript_fetcher=mock_transcript_fetcher,
            quota_tracker=mock_quota_tracker,
        )
        assert c is not None

    def test_異常系_非Pathで初期化するとValueError(
        self,
        mock_channel_fetcher: MagicMock,
        mock_transcript_fetcher: MagicMock,
        mock_quota_tracker: MagicMock,
    ) -> None:
        """Collector raises ValueError when given a non-Path data_dir."""
        with pytest.raises(ValueError, match="data_dir must be a Path object"):
            Collector(
                data_dir="not_a_path",  # type: ignore[arg-type]
                channel_fetcher=mock_channel_fetcher,
                transcript_fetcher=mock_transcript_fetcher,
                quota_tracker=mock_quota_tracker,
            )


# ---------------------------------------------------------------------------
# collect() tests
# ---------------------------------------------------------------------------


class TestCollect:
    """Tests for Collector.collect() - 5-step flow."""

    def test_正常系_5ステップフローが実行される(
        self,
        collector: Collector,
        tmp_data_dir: Path,
        mock_channel_fetcher: MagicMock,
        mock_transcript_fetcher: MagicMock,
    ) -> None:
        """collect() executes all 5 steps: fetch videos, diff, transcripts, save, result."""
        # Prepare: add channel to storage
        from youtube_transcript.storage.json_storage import JSONStorage

        storage = JSONStorage(tmp_data_dir)
        channel = make_channel(channel_id="UCabc123")
        storage.save_channels([channel])

        # Transcripts: first returns result, second returns None (unavailable)
        mock_transcript_fetcher.fetch.side_effect = [
            make_transcript_result("vid1234567a"),
            None,
        ]

        result = collector.collect("UCabc123")

        assert isinstance(result, CollectResult)
        # Step 1: channel_fetcher.list_all_videos was called
        mock_channel_fetcher.list_all_videos.assert_called_once_with(
            "UCabc123", "UUabc123"
        )
        # Step 3: transcript_fetcher.fetch was called for each new video
        assert mock_transcript_fetcher.fetch.call_count == 2
        # Step 5: result has counts
        assert result.total == 2
        assert result.success == 1
        assert result.unavailable == 1
        assert result.failed == 0
        assert result.skipped == 0

    def test_正常系_差分検出で既存動画はスキップされる(
        self,
        collector: Collector,
        tmp_data_dir: Path,
        mock_channel_fetcher: MagicMock,
        mock_transcript_fetcher: MagicMock,
    ) -> None:
        """collect() skips videos that already have SUCCESS transcript status."""
        from youtube_transcript.storage.json_storage import JSONStorage

        storage = JSONStorage(tmp_data_dir)
        channel = make_channel(channel_id="UCabc123")
        storage.save_channels([channel])

        # Set up: vid1234567a already collected (SUCCESS), vid2345678b is new
        existing_videos = [
            make_video(
                "vid1234567a",
                transcript_status=TranscriptStatus.SUCCESS,
            )
        ]
        storage.save_videos("UCabc123", existing_videos)

        # fetched: both videos (vid1234567a already exists, vid2345678b is new)
        mock_channel_fetcher.list_all_videos.return_value = [
            make_video("vid1234567a"),
            make_video("vid2345678b"),
        ]
        mock_transcript_fetcher.fetch.return_value = make_transcript_result(
            "vid2345678b"
        )

        result = collector.collect("UCabc123")

        # Only new video should have transcript fetched
        assert mock_transcript_fetcher.fetch.call_count == 1
        assert result.total == 1  # Only new videos counted
        assert result.success == 1
        assert result.skipped == 0

    def test_正常系_トランスクリプト取得後に保存される(
        self,
        collector: Collector,
        tmp_data_dir: Path,
        mock_channel_fetcher: MagicMock,
        mock_transcript_fetcher: MagicMock,
    ) -> None:
        """collect() saves transcript to storage after successful fetch."""
        from youtube_transcript.storage.json_storage import JSONStorage

        storage = JSONStorage(tmp_data_dir)
        channel = make_channel(channel_id="UCabc123")
        storage.save_channels([channel])

        mock_channel_fetcher.list_all_videos.return_value = [make_video("vid1234567a")]
        mock_transcript_fetcher.fetch.return_value = make_transcript_result(
            "vid1234567a"
        )

        collector.collect("UCabc123")

        # Transcript should be saved in storage
        saved = storage.load_transcript("UCabc123", "vid1234567a")
        assert saved is not None
        assert saved.video_id == "vid1234567a"
        assert saved.language == "ja"

    def test_正常系_動画ステータスがSUCCESSに更新される(
        self,
        collector: Collector,
        tmp_data_dir: Path,
        mock_channel_fetcher: MagicMock,
        mock_transcript_fetcher: MagicMock,
    ) -> None:
        """collect() updates video.transcript_status to SUCCESS after fetch."""
        from youtube_transcript.storage.json_storage import JSONStorage

        storage = JSONStorage(tmp_data_dir)
        channel = make_channel(channel_id="UCabc123")
        storage.save_channels([channel])

        mock_channel_fetcher.list_all_videos.return_value = [make_video("vid1234567a")]
        mock_transcript_fetcher.fetch.return_value = make_transcript_result(
            "vid1234567a"
        )

        collector.collect("UCabc123")

        videos = storage.load_videos("UCabc123")
        video = next(v for v in videos if v.video_id == "vid1234567a")
        assert video.transcript_status == TranscriptStatus.SUCCESS
        assert video.transcript_language == "ja"
        assert video.fetched_at is not None

    def test_正常系_トランスクリプトなし動画はUNAVAILABLEに更新される(
        self,
        collector: Collector,
        tmp_data_dir: Path,
        mock_channel_fetcher: MagicMock,
        mock_transcript_fetcher: MagicMock,
    ) -> None:
        """collect() sets video.transcript_status to UNAVAILABLE when transcript is None."""
        from youtube_transcript.storage.json_storage import JSONStorage

        storage = JSONStorage(tmp_data_dir)
        channel = make_channel(channel_id="UCabc123")
        storage.save_channels([channel])

        mock_channel_fetcher.list_all_videos.return_value = [make_video("vid1234567a")]
        mock_transcript_fetcher.fetch.return_value = None  # No transcript available

        result = collector.collect("UCabc123")

        assert result.unavailable == 1
        videos = storage.load_videos("UCabc123")
        video = next(v for v in videos if v.video_id == "vid1234567a")
        assert video.transcript_status == TranscriptStatus.UNAVAILABLE

    def test_異常系_ChannelNotFoundErrorで例外を発生させる(
        self, collector: Collector
    ) -> None:
        """collect() raises ChannelNotFoundError for non-existent channel."""
        with pytest.raises(ChannelNotFoundError):
            collector.collect("UCnonexistent")

    def test_異常系_quota超過時はスキップされる(
        self,
        collector: Collector,
        tmp_data_dir: Path,
        mock_channel_fetcher: MagicMock,
        mock_transcript_fetcher: MagicMock,
        mock_quota_tracker: MagicMock,
    ) -> None:
        """collect() skips channel when quota is exceeded during video list fetch."""
        from youtube_transcript.storage.json_storage import JSONStorage

        storage = JSONStorage(tmp_data_dir)
        channel = make_channel(channel_id="UCabc123")
        storage.save_channels([channel])

        # Quota exceeded when fetching video list
        mock_channel_fetcher.list_all_videos.side_effect = QuotaExceededError(
            "Quota exceeded"
        )

        result = collector.collect("UCabc123")

        # Should return a result with skipped count
        assert result.skipped == 1
        assert result.total == 0
        assert result.success == 0


# ---------------------------------------------------------------------------
# collect_all() tests
# ---------------------------------------------------------------------------


class TestCollectAll:
    """Tests for Collector.collect_all()."""

    def test_正常系_全有効チャンネルを順次処理する(
        self,
        collector: Collector,
        tmp_data_dir: Path,
        mock_channel_fetcher: MagicMock,
        mock_transcript_fetcher: MagicMock,
    ) -> None:
        """collect_all() processes all enabled channels sequentially."""
        from youtube_transcript.storage.json_storage import JSONStorage

        storage = JSONStorage(tmp_data_dir)
        channels = [
            make_channel("UCabc123", "Channel 1", "UUabc123"),
            make_channel("UCdef456", "Channel 2", "UUdef456"),
        ]
        storage.save_channels(channels)

        # Each channel has 1 video
        mock_channel_fetcher.list_all_videos.side_effect = [
            [make_video("vid1234567a", "UCabc123")],
            [make_video("vid2345678b", "UCdef456")],
        ]
        mock_transcript_fetcher.fetch.side_effect = [
            make_transcript_result("vid1234567a"),
            make_transcript_result("vid2345678b"),
        ]

        results = collector.collect_all()

        assert len(results) == 2
        assert mock_channel_fetcher.list_all_videos.call_count == 2

    def test_正常系_無効チャンネルはスキップされる(
        self,
        collector: Collector,
        tmp_data_dir: Path,
        mock_channel_fetcher: MagicMock,
    ) -> None:
        """collect_all() skips disabled channels."""
        from youtube_transcript.storage.json_storage import JSONStorage

        storage = JSONStorage(tmp_data_dir)
        channels = [
            make_channel("UCabc123", "Enabled Channel", "UUabc123", enabled=True),
            make_channel("UCdef456", "Disabled Channel", "UUdef456", enabled=False),
        ]
        storage.save_channels(channels)

        mock_channel_fetcher.list_all_videos.return_value = []

        results = collector.collect_all()

        # Only 1 enabled channel should be processed
        assert mock_channel_fetcher.list_all_videos.call_count == 1
        assert len(results) == 1

    def test_正常系_チャンネルなしで空リストを返す(self, collector: Collector) -> None:
        """collect_all() returns empty list when there are no channels."""
        results = collector.collect_all()
        assert results == []

    def test_正常系_quota超過時は残りのチャンネルをスキップする(
        self,
        collector: Collector,
        tmp_data_dir: Path,
        mock_channel_fetcher: MagicMock,
        mock_quota_tracker: MagicMock,
    ) -> None:
        """collect_all() stops processing when quota is exceeded."""
        from youtube_transcript.storage.json_storage import JSONStorage

        storage = JSONStorage(tmp_data_dir)
        channels = [
            make_channel("UCabc123", "Channel 1", "UUabc123"),
            make_channel("UCdef456", "Channel 2", "UUdef456"),
        ]
        storage.save_channels(channels)

        # First channel: quota exceeded; second channel should not be processed
        mock_channel_fetcher.list_all_videos.side_effect = QuotaExceededError(
            "Quota exceeded"
        )

        results = collector.collect_all()

        # Both channels attempted but quota exceeded on each
        assert len(results) == 2
        # Both should have skipped=1 due to quota
        for result in results:
            assert result.skipped == 1
