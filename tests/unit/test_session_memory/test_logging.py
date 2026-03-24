"""_logging.py のユニットテスト."""

from __future__ import annotations


def _is_structlog_logger(obj: object) -> bool:
    """structlog ロガーかどうかを判定する."""
    return hasattr(obj, "info") and hasattr(obj, "bind")


class TestGetLogger:
    """get_logger 関数のテスト."""

    def test_正常系_ロガーインスタンスを返す(self) -> None:
        """get_logger が structlog ロガーを返すことを確認する."""
        from session_memory._logging import get_logger

        logger = get_logger("test_module")
        assert _is_structlog_logger(logger)

    def test_正常系_コンテキストをバインドできる(self) -> None:
        """get_logger にコンテキストを渡せることを確認する."""
        from session_memory._logging import get_logger

        logger = get_logger("test_module", module="cli")
        assert _is_structlog_logger(logger)

    def test_正常系_二重初期化が冪等(self) -> None:
        """get_logger を複数回呼んでもエラーにならないことを確認する."""
        from session_memory._logging import get_logger

        logger1 = get_logger("test1")
        logger2 = get_logger("test2")
        assert _is_structlog_logger(logger1)
        assert _is_structlog_logger(logger2)

    def test_正常系_異なるモジュール名で別インスタンス(self) -> None:
        """異なる name で呼ぶと別のロガーが返ることを確認する."""
        from session_memory._logging import get_logger

        logger_a = get_logger("module_a")
        logger_b = get_logger("module_b")
        assert _is_structlog_logger(logger_a)
        assert _is_structlog_logger(logger_b)
