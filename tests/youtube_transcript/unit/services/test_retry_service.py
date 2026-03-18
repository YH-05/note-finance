"""Unit tests for RetryService.

TDD Red phase: tests covering acceptance criteria from Issue #169.

Acceptance criteria:
- FAILED ステータスの動画のみが再取得の対象になる
- SUCCESS / UNAVAILABLE は再取得しない
- quota 超過時はスキップ
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from youtube_transcript.exceptions import (
    ChannelNotFoundError,
    QuotaExceededError,
)
from youtube_transcript.services.retry_service import RetryService
from youtube_transcript.storage.json_storage import JSONStorage
from youtube_transcript.types import (
    Channel,
    CollectResult,
    TranscriptResult,
    TranscriptStatus,
    Video,
)

# ---------------------------------------------------------------------------
# Helpers / Fixtures
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
def retry_service(
    tmp_data_dir: Path,
    mock_transcript_fetcher: MagicMock,
    mock_quota_tracker: MagicMock,
) -> RetryService:
    """RetryService with mocked dependencies."""
    return RetryService(
        data_dir=tmp_data_dir,
        transcript_fetcher=mock_transcript_fetcher,
        quota_tracker=mock_quota_tracker,
    )


# ---------------------------------------------------------------------------
# RetryService Initialization
# ---------------------------------------------------------------------------


class TestRetryServiceInit:
    """Tests for RetryService initialization."""

    def test_正常系_依存性注入で初期化できる(
        self,
        tmp_data_dir: Path,
        mock_transcript_fetcher: MagicMock,
        mock_quota_tracker: MagicMock,
    ) -> None:
        """RetryService can be initialized with injected dependencies."""
        service = RetryService(
            data_dir=tmp_data_dir,
            transcript_fetcher=mock_transcript_fetcher,
            quota_tracker=mock_quota_tracker,
        )
        assert service is not None

    def test_異常系_非Pathで初期化するとValueError(
        self,
        mock_transcript_fetcher: MagicMock,
        mock_quota_tracker: MagicMock,
    ) -> None:
        """RetryService raises ValueError when given a non-Path data_dir."""
        with pytest.raises(ValueError, match="data_dir must be a Path object"):
            RetryService(
                data_dir="not_a_path",  # type: ignore[arg-type]
                transcript_fetcher=mock_transcript_fetcher,
                quota_tracker=mock_quota_tracker,
            )


# ---------------------------------------------------------------------------
# retry_failed(channel_id) tests
# ---------------------------------------------------------------------------


class TestRetryFailed:
    """Tests for RetryService.retry_failed()."""

    def test_正常系_FAILEDのみが再取得される(
        self,
        retry_service: RetryService,
        tmp_data_dir: Path,
        mock_transcript_fetcher: MagicMock,
    ) -> None:
        """retry_failed() only re-fetches videos with FAILED status."""
        storage = JSONStorage(tmp_data_dir)
        channel = make_channel(channel_id="UCabc123")
        storage.save_channels([channel])

        # 3 videos: FAILED, SUCCESS, UNAVAILABLE
        videos = [
            make_video("vid_failed1", transcript_status=TranscriptStatus.FAILED),
            make_video("vid_success1", transcript_status=TranscriptStatus.SUCCESS),
            make_video("vid_unavail1", transcript_status=TranscriptStatus.UNAVAILABLE),
        ]
        storage.save_videos("UCabc123", videos)

        mock_transcript_fetcher.fetch.return_value = make_transcript_result(
            "vid_failed1"
        )

        result = retry_service.retry_failed("UCabc123")

        # Only FAILED video should be retried
        assert mock_transcript_fetcher.fetch.call_count == 1
        # CollectResult reflects only the retried video
        assert isinstance(result, CollectResult)
        assert result.total == 1

    def test_正常系_SUCCESSは再取得されない(
        self,
        retry_service: RetryService,
        tmp_data_dir: Path,
        mock_transcript_fetcher: MagicMock,
    ) -> None:
        """retry_failed() does not retry videos with SUCCESS status."""
        storage = JSONStorage(tmp_data_dir)
        channel = make_channel(channel_id="UCabc123")
        storage.save_channels([channel])

        videos = [
            make_video("vid_success1", transcript_status=TranscriptStatus.SUCCESS),
        ]
        storage.save_videos("UCabc123", videos)

        result = retry_service.retry_failed("UCabc123")

        # No fetches should be made
        mock_transcript_fetcher.fetch.assert_not_called()
        assert result.total == 0
        assert result.success == 0

    def test_正常系_UNAVAILABLEは再取得されない(
        self,
        retry_service: RetryService,
        tmp_data_dir: Path,
        mock_transcript_fetcher: MagicMock,
    ) -> None:
        """retry_failed() does not retry videos with UNAVAILABLE status."""
        storage = JSONStorage(tmp_data_dir)
        channel = make_channel(channel_id="UCabc123")
        storage.save_channels([channel])

        videos = [
            make_video("vid_unavail1", transcript_status=TranscriptStatus.UNAVAILABLE),
        ]
        storage.save_videos("UCabc123", videos)

        result = retry_service.retry_failed("UCabc123")

        # No fetches should be made
        mock_transcript_fetcher.fetch.assert_not_called()
        assert result.total == 0

    def test_正常系_FAILED動画が再取得に成功するとSUCCESSになる(
        self,
        retry_service: RetryService,
        tmp_data_dir: Path,
        mock_transcript_fetcher: MagicMock,
    ) -> None:
        """retry_failed() updates video status to SUCCESS after successful re-fetch."""
        storage = JSONStorage(tmp_data_dir)
        channel = make_channel(channel_id="UCabc123")
        storage.save_channels([channel])

        videos = [
            make_video("vid_failed1", transcript_status=TranscriptStatus.FAILED),
        ]
        storage.save_videos("UCabc123", videos)

        mock_transcript_fetcher.fetch.return_value = make_transcript_result(
            "vid_failed1"
        )

        result = retry_service.retry_failed("UCabc123")

        assert result.success == 1
        # Verify storage updated
        updated_videos = storage.load_videos("UCabc123")
        video = next(v for v in updated_videos if v.video_id == "vid_failed1")
        assert video.transcript_status == TranscriptStatus.SUCCESS
        assert video.transcript_language == "ja"
        assert video.fetched_at is not None

    def test_正常系_FAILED動画の再取得がNoneならUNAVAILABLEになる(
        self,
        retry_service: RetryService,
        tmp_data_dir: Path,
        mock_transcript_fetcher: MagicMock,
    ) -> None:
        """retry_failed() sets status to UNAVAILABLE when re-fetch returns None."""
        storage = JSONStorage(tmp_data_dir)
        channel = make_channel(channel_id="UCabc123")
        storage.save_channels([channel])

        videos = [
            make_video("vid_failed1", transcript_status=TranscriptStatus.FAILED),
        ]
        storage.save_videos("UCabc123", videos)

        mock_transcript_fetcher.fetch.return_value = None  # Unavailable

        result = retry_service.retry_failed("UCabc123")

        assert result.unavailable == 1
        updated_videos = storage.load_videos("UCabc123")
        video = next(v for v in updated_videos if v.video_id == "vid_failed1")
        assert video.transcript_status == TranscriptStatus.UNAVAILABLE

    def test_正常系_FAILEDがなければ何もしない(
        self,
        retry_service: RetryService,
        tmp_data_dir: Path,
        mock_transcript_fetcher: MagicMock,
    ) -> None:
        """retry_failed() returns empty CollectResult when no FAILED videos."""
        storage = JSONStorage(tmp_data_dir)
        channel = make_channel(channel_id="UCabc123")
        storage.save_channels([channel])

        videos = [
            make_video("vid_pending1", transcript_status=TranscriptStatus.PENDING),
        ]
        storage.save_videos("UCabc123", videos)

        result = retry_service.retry_failed("UCabc123")

        mock_transcript_fetcher.fetch.assert_not_called()
        assert result.total == 0

    def test_正常系_transcript取得保存済みになる(
        self,
        retry_service: RetryService,
        tmp_data_dir: Path,
        mock_transcript_fetcher: MagicMock,
    ) -> None:
        """retry_failed() saves the transcript to storage after successful re-fetch."""
        storage = JSONStorage(tmp_data_dir)
        channel = make_channel(channel_id="UCabc123")
        storage.save_channels([channel])

        videos = [
            make_video("vid_failed1", transcript_status=TranscriptStatus.FAILED),
        ]
        storage.save_videos("UCabc123", videos)

        mock_transcript_fetcher.fetch.return_value = make_transcript_result(
            "vid_failed1"
        )

        retry_service.retry_failed("UCabc123")

        saved = storage.load_transcript("UCabc123", "vid_failed1")
        assert saved is not None
        assert saved.video_id == "vid_failed1"

    def test_異常系_存在しないチャンネルはChannelNotFoundError(
        self,
        retry_service: RetryService,
    ) -> None:
        """retry_failed() raises ChannelNotFoundError for non-existent channel."""
        with pytest.raises(ChannelNotFoundError):
            retry_service.retry_failed("UCnonexistent")

    def test_正常系_quota超過時はスキップされる(
        self,
        retry_service: RetryService,
        tmp_data_dir: Path,
        mock_transcript_fetcher: MagicMock,
        mock_quota_tracker: MagicMock,
    ) -> None:
        """retry_failed() skips re-fetch when quota is exceeded."""
        storage = JSONStorage(tmp_data_dir)
        channel = make_channel(channel_id="UCabc123")
        storage.save_channels([channel])

        videos = [
            make_video("vid_failed1", transcript_status=TranscriptStatus.FAILED),
            make_video("vid_failed2", transcript_status=TranscriptStatus.FAILED),
        ]
        storage.save_videos("UCabc123", videos)

        # Quota exceeded on first fetch attempt
        mock_transcript_fetcher.fetch.side_effect = QuotaExceededError("Quota exceeded")

        result = retry_service.retry_failed("UCabc123")

        # Should skip remaining after quota exceeded
        assert result.skipped >= 1

    def test_正常系_取得エラー時はFAILEDのまま(
        self,
        retry_service: RetryService,
        tmp_data_dir: Path,
        mock_transcript_fetcher: MagicMock,
    ) -> None:
        """retry_failed() keeps FAILED status when re-fetch raises an unexpected error."""
        storage = JSONStorage(tmp_data_dir)
        channel = make_channel(channel_id="UCabc123")
        storage.save_channels([channel])

        videos = [
            make_video("vid_failed1", transcript_status=TranscriptStatus.FAILED),
        ]
        storage.save_videos("UCabc123", videos)

        # Unexpected error
        mock_transcript_fetcher.fetch.side_effect = RuntimeError("Unexpected error")

        result = retry_service.retry_failed("UCabc123")

        assert result.failed == 1
        updated_videos = storage.load_videos("UCabc123")
        video = next(v for v in updated_videos if v.video_id == "vid_failed1")
        assert video.transcript_status == TranscriptStatus.FAILED


# ---------------------------------------------------------------------------
# retry_all_failed() tests
# ---------------------------------------------------------------------------


class TestRetryAllFailed:
    """Tests for RetryService.retry_all_failed()."""

    def test_正常系_全チャンネルのFAILEDを再取得する(
        self,
        retry_service: RetryService,
        tmp_data_dir: Path,
        mock_transcript_fetcher: MagicMock,
    ) -> None:
        """retry_all_failed() processes all channels and retries their FAILED videos."""
        storage = JSONStorage(tmp_data_dir)
        channels = [
            make_channel("UCabc123", "Channel 1", "UUabc123"),
            make_channel("UCdef456", "Channel 2", "UUdef456"),
        ]
        storage.save_channels(channels)

        storage.save_videos(
            "UCabc123",
            [make_video("vid_fail_a", "UCabc123", TranscriptStatus.FAILED)],
        )
        storage.save_videos(
            "UCdef456",
            [make_video("vid_fail_b", "UCdef456", TranscriptStatus.FAILED)],
        )

        mock_transcript_fetcher.fetch.side_effect = [
            make_transcript_result("vid_fail_a"),
            make_transcript_result("vid_fail_b"),
        ]

        results = retry_service.retry_all_failed()

        assert len(results) == 2
        assert mock_transcript_fetcher.fetch.call_count == 2

    def test_正常系_チャンネルなしで空リストを返す(
        self,
        retry_service: RetryService,
    ) -> None:
        """retry_all_failed() returns empty list when there are no channels."""
        results = retry_service.retry_all_failed()
        assert results == []

    def test_正常系_無効チャンネルもスキップされる(
        self,
        retry_service: RetryService,
        tmp_data_dir: Path,
        mock_transcript_fetcher: MagicMock,
    ) -> None:
        """retry_all_failed() skips disabled channels."""
        storage = JSONStorage(tmp_data_dir)
        channels = [
            make_channel("UCabc123", "Enabled", "UUabc123", enabled=True),
            make_channel("UCdef456", "Disabled", "UUdef456", enabled=False),
        ]
        storage.save_channels(channels)

        storage.save_videos(
            "UCabc123",
            [make_video("vid_fail_a", "UCabc123", TranscriptStatus.FAILED)],
        )
        storage.save_videos(
            "UCdef456",
            [make_video("vid_fail_b", "UCdef456", TranscriptStatus.FAILED)],
        )

        mock_transcript_fetcher.fetch.return_value = make_transcript_result(
            "vid_fail_a"
        )

        results = retry_service.retry_all_failed()

        # Only enabled channel should be processed
        assert len(results) == 1
        assert mock_transcript_fetcher.fetch.call_count == 1
