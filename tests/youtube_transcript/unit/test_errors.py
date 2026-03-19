"""Unit tests for youtube_transcript._errors module."""

import pytest

from youtube_transcript._errors import log_and_reraise
from youtube_transcript._logging import get_logger
from youtube_transcript.exceptions import StorageError

_logger = get_logger(__name__)


class TestLogAndReraise:
    def test_正常系_例外が発生しない場合はそのまま通過する(self) -> None:
        result = []
        with log_and_reraise(_logger, "test operation"):
            result.append("ok")
        assert result == ["ok"]

    def test_正常系_例外が発生した場合にそのまま再raiseされる(self) -> None:
        with (
            pytest.raises(ValueError, match="original error"),
            log_and_reraise(_logger, "test operation"),
        ):
            raise ValueError("original error")

    def test_正常系_reraise_asで例外型を変換できる(self) -> None:
        with (
            pytest.raises(StorageError),
            log_and_reraise(_logger, "write operation", reraise_as=StorageError),
        ):
            raise OSError("disk full")

    def test_正常系_reraise_asで変換した例外にメッセージが含まれる(self) -> None:
        with (
            pytest.raises(StorageError, match="write operation failed"),
            log_and_reraise(_logger, "write operation", reraise_as=StorageError),
        ):
            raise OSError("disk full")

    def test_正常系_contextがある場合もログが記録される(self) -> None:
        with (
            pytest.raises(ValueError),
            log_and_reraise(
                _logger,
                "fetch transcript",
                context={"video_id": "abc123", "language": "ja"},
            ),
        ):
            raise ValueError("network error")

    def test_正常系_reraise_asで既に同じ型の例外はラップされない(self) -> None:
        original = StorageError("already storage error")
        with (
            pytest.raises(StorageError) as exc_info,
            log_and_reraise(_logger, "storage op", reraise_as=StorageError),
        ):
            raise original
        # 元の例外がそのまま再raiseされる
        assert exc_info.value is original

    def test_エッジケース_空のcontextで呼び出せる(self) -> None:
        with pytest.raises(RuntimeError), log_and_reraise(_logger, "task", context={}):
            raise RuntimeError("runtime error")

    def test_エッジケース_reraise_asがNoneの場合は元の例外をraise(self) -> None:
        with (
            pytest.raises(KeyError),
            log_and_reraise(_logger, "lookup", reraise_as=None),
        ):
            raise KeyError("key not found")
