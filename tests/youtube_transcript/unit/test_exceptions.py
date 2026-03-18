"""Unit tests for youtube_transcript.exceptions module."""

import pytest

from youtube_transcript.exceptions import (
    APIError,
    ChannelAlreadyExistsError,
    ChannelNotFoundError,
    QuotaExceededError,
    StorageError,
    TranscriptUnavailableError,
    YouTubeTranscriptError,
)


class TestYouTubeTranscriptError:
    def test_正常系_基底例外が発生できる(self) -> None:
        with pytest.raises(YouTubeTranscriptError, match="base error"):
            raise YouTubeTranscriptError("base error")

    def test_正常系_Exceptionのサブクラスである(self) -> None:
        err = YouTubeTranscriptError("test")
        assert isinstance(err, Exception)


class TestChannelNotFoundError:
    def test_正常系_ChannelNotFoundErrorが発生できる(self) -> None:
        with pytest.raises(ChannelNotFoundError):
            raise ChannelNotFoundError("Channel 'UC_123' not found")

    def test_正常系_YouTubeTranscriptErrorのサブクラスである(self) -> None:
        err = ChannelNotFoundError("not found")
        assert isinstance(err, YouTubeTranscriptError)

    def test_正常系_catcherでキャッチできる(self) -> None:
        with pytest.raises(YouTubeTranscriptError):
            raise ChannelNotFoundError("channel missing")


class TestChannelAlreadyExistsError:
    def test_正常系_ChannelAlreadyExistsErrorが発生できる(self) -> None:
        with pytest.raises(ChannelAlreadyExistsError):
            raise ChannelAlreadyExistsError("Channel already exists")

    def test_正常系_YouTubeTranscriptErrorのサブクラスである(self) -> None:
        err = ChannelAlreadyExistsError("already exists")
        assert isinstance(err, YouTubeTranscriptError)


class TestQuotaExceededError:
    def test_正常系_QuotaExceededErrorが発生できる(self) -> None:
        with pytest.raises(QuotaExceededError):
            raise QuotaExceededError("Quota exceeded: 10000 units used")

    def test_正常系_YouTubeTranscriptErrorのサブクラスである(self) -> None:
        err = QuotaExceededError("quota exceeded")
        assert isinstance(err, YouTubeTranscriptError)


class TestTranscriptUnavailableError:
    def test_正常系_TranscriptUnavailableErrorが発生できる(self) -> None:
        with pytest.raises(TranscriptUnavailableError):
            raise TranscriptUnavailableError(
                "Transcript unavailable for video 'abc123'"
            )

    def test_正常系_YouTubeTranscriptErrorのサブクラスである(self) -> None:
        err = TranscriptUnavailableError("unavailable")
        assert isinstance(err, YouTubeTranscriptError)


class TestAPIError:
    def test_正常系_APIErrorが発生できる(self) -> None:
        with pytest.raises(APIError):
            raise APIError("YouTube API error: 403 Forbidden")

    def test_正常系_YouTubeTranscriptErrorのサブクラスである(self) -> None:
        err = APIError("api error")
        assert isinstance(err, YouTubeTranscriptError)


class TestStorageError:
    def test_正常系_StorageErrorが発生できる(self) -> None:
        with pytest.raises(StorageError):
            raise StorageError("Failed to write to storage")

    def test_正常系_YouTubeTranscriptErrorのサブクラスである(self) -> None:
        err = StorageError("storage error")
        assert isinstance(err, YouTubeTranscriptError)


class TestExceptionHierarchy:
    def test_正常系_全サブクラスがYouTubeTranscriptErrorを継承(self) -> None:
        subclasses = [
            ChannelNotFoundError,
            ChannelAlreadyExistsError,
            QuotaExceededError,
            TranscriptUnavailableError,
            APIError,
            StorageError,
        ]
        for cls in subclasses:
            instance = cls("test")
            assert isinstance(instance, YouTubeTranscriptError), (
                f"{cls.__name__} should be a subclass of YouTubeTranscriptError"
            )

    def test_正常系_サブクラスが6つ存在する(self) -> None:
        subclasses = YouTubeTranscriptError.__subclasses__()
        assert len(subclasses) == 6
