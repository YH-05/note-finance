"""Unit tests for youtube_transcript._logging module."""

import structlog

from youtube_transcript._logging import get_logger


class TestGetLogger:
    def test_正常系_get_loggerがロガーを返す(self) -> None:
        logger = get_logger(__name__)
        # BoundLoggerLazyProxy or BoundLogger are both valid structlog loggers
        assert hasattr(logger, "info")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "error")

    def test_正常系_異なる名前で呼び出せる(self) -> None:
        logger1 = get_logger("youtube_transcript.test1")
        logger2 = get_logger("youtube_transcript.test2")
        assert hasattr(logger1, "info")
        assert hasattr(logger2, "info")

    def test_正常系_コンテキストを付与できる(self) -> None:
        logger = get_logger(__name__, channel_id="UC_test", video_id="abc123")
        # When context is bound, we get a BoundLogger
        assert isinstance(logger, structlog.stdlib.BoundLogger)

    def test_正常系_コンテキストなしで呼び出せる(self) -> None:
        logger = get_logger("youtube_transcript")
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")

    def test_正常系_同一名で複数回呼び出せる(self) -> None:
        logger_a = get_logger("youtube_transcript.repeat")
        logger_b = get_logger("youtube_transcript.repeat")
        assert hasattr(logger_a, "info")
        assert hasattr(logger_b, "info")

    def test_正常系_bindでBoundLoggerを取得できる(self) -> None:
        logger = get_logger(__name__)
        bound = logger.bind(video_id="abc")
        assert isinstance(bound, structlog.stdlib.BoundLogger)
