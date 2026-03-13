"""Unit tests for data_paths._logging module."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
import structlog

if TYPE_CHECKING:
    from collections.abc import Iterator

import data_paths._logging as logging_mod
from data_paths._logging import _ensure_basic_config, get_logger


@pytest.fixture(autouse=True)
def _reset_logging_state() -> Iterator[None]:
    """各テストの前後でロギング初期化状態をリセットする。"""
    original = logging_mod._initialized
    logging_mod._initialized = False
    yield
    logging_mod._initialized = original


class TestEnsureBasicConfig:
    """_ensure_basic_config のテスト。"""

    def test_正常系_初回呼び出しで初期化される(self) -> None:
        """初回呼び出しで _initialized が True になることを確認。"""
        assert logging_mod._initialized is False
        _ensure_basic_config()
        assert logging_mod._initialized is True

    def test_正常系_二回目以降は再初期化されない(self) -> None:
        """_initialized が True の場合は再初期化をスキップすることを確認。"""
        _ensure_basic_config()
        assert logging_mod._initialized is True

        # 二回目の呼び出しでもエラーにならない
        _ensure_basic_config()
        assert logging_mod._initialized is True

    def test_正常系_NullHandlerがdata_pathsロガーに追加される(self) -> None:
        """data_paths ロガーに NullHandler が追加されることを確認。"""
        _ensure_basic_config()
        pkg_logger = logging.getLogger("data_paths")
        handler_types = [type(h) for h in pkg_logger.handlers]
        assert logging.NullHandler in handler_types

    def test_正常系_有効なLOG_LEVELが反映される(self) -> None:
        """有効な LOG_LEVEL 環境変数が正しく反映されることを確認。"""
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            logging_mod._initialized = False
            _ensure_basic_config()
            # エラーにならずに初期化が完了する
            assert logging_mod._initialized is True

    def test_異常系_無効なLOG_LEVELでデフォルトINFOを使用(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """無効な LOG_LEVEL の場合、INFO にフォールバックしてstderrに警告を出す。"""
        with patch.dict(os.environ, {"LOG_LEVEL": "INVALID_LEVEL"}):
            logging_mod._initialized = False
            _ensure_basic_config()
            captured = capsys.readouterr()
            assert "Invalid LOG_LEVEL" in captured.err
            assert "INVALID_LEVEL" in captured.err


class TestGetLogger:
    """get_logger のテスト。"""

    def test_正常系_BoundLoggerを返す(self) -> None:
        """get_logger がログ可能なオブジェクトを返すことを確認。"""
        logger = get_logger("test_module")
        # structlog は cache_logger_on_first_use=True の場合
        # BoundLoggerLazyProxy を返す
        assert hasattr(logger, "info")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")

    def test_正常系_コンテキストをバインドできる(self) -> None:
        """追加コンテキストをバインドしてロガーを取得できることを確認。"""
        logger = get_logger("test_module", component="test")
        assert isinstance(logger, structlog.stdlib.BoundLogger)

    def test_正常系_初期化を自動で行う(self) -> None:
        """get_logger が _ensure_basic_config を自動呼び出しすることを確認。"""
        assert logging_mod._initialized is False
        get_logger("test_auto_init")
        assert logging_mod._initialized is True
