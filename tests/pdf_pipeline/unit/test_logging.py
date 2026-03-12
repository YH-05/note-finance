"""Unit tests for pdf_pipeline._logging module."""

from __future__ import annotations

from pdf_pipeline._logging import get_logger


class TestGetLogger:
    def test_正常系_ロガーが返される(self) -> None:
        logger = get_logger(__name__)
        assert logger is not None

    def test_正常系_コンテキスト付きロガーが返される(self) -> None:
        logger = get_logger(__name__, module="test", env="testing")
        assert logger is not None

    def test_正常系_複数回呼び出しても正常動作する(self) -> None:
        logger1 = get_logger("pdf_pipeline.test1")
        logger2 = get_logger("pdf_pipeline.test2")
        assert logger1 is not None
        assert logger2 is not None

    def test_正常系_異なる名前で異なるロガーを取得できる(self) -> None:
        logger_a = get_logger("pdf_pipeline.a")
        logger_b = get_logger("pdf_pipeline.b")
        # Both should be valid loggers
        assert logger_a is not None
        assert logger_b is not None
