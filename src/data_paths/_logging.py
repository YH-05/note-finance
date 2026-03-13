"""Logging configuration for data_paths package.

AIDEV-NOTE: ライブラリパッケージとして root logger を操作しない設計。
NullHandler パターンに従い、ログ設定はアプリケーション側に委ねる。
"""

import logging
import os
import sys

import structlog
from structlog import BoundLogger

_initialized = False


def _ensure_basic_config() -> None:
    """get_logger 呼び出し前に最小限のロギング設定を確保する.

    AIDEV-NOTE: root logger のハンドラは操作しない（PEP 推奨のライブラリ作法）。
    data_paths パッケージ専用ロガーに NullHandler を設定する。
    root logger の設定はアプリケーション側の責務とする。
    """
    global _initialized  # noqa: PLW0603
    if _initialized:
        return
    _initialized = True

    level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
    _valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if level_str not in _valid_levels:
        print(
            f"[data_paths] Invalid LOG_LEVEL '{os.environ.get('LOG_LEVEL')}', "
            "defaulting to INFO",
            file=sys.stderr,
        )
        level_str = "INFO"
    level_value = getattr(logging, level_str)

    # ライブラリ専用ロガーに NullHandler を追加し、LOG_LEVEL を反映（PEP 推奨）
    pkg_logger = logging.getLogger("data_paths")
    pkg_logger.setLevel(level_value)
    pkg_logger.addHandler(logging.NullHandler())

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str, **context: object) -> BoundLogger:
    """構造化ロガーインスタンスを取得する.

    Parameters
    ----------
    name : str
        ロガー名（通常は ``__name__`` を渡す）。
    **context : object
        ロガーにバインドする追加コンテキスト。

    Returns
    -------
    BoundLogger
        コンテキストをバインドした structlog BoundLogger インスタンス。
    """
    _ensure_basic_config()
    logger: BoundLogger = structlog.get_logger(name)
    if context:
        logger = logger.bind(**context)
    return logger
