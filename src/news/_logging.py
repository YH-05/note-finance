"""Logging configuration for news package."""

import logging
import os
import sys

import structlog
from structlog import BoundLogger

_initialized = False


def _ensure_basic_config() -> None:
    """get_logger 呼び出し前に最小限のロギング設定を確保する."""
    global _initialized  # noqa: PLW0603
    if _initialized:
        return
    _initialized = True

    level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
    level_value = getattr(logging, level_str, logging.INFO)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    console_formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(colors=True),
        ],
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(level_value)
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )


def get_logger(name: str, **context) -> BoundLogger:
    """構造化ロガーインスタンスを取得する."""
    _ensure_basic_config()
    logger: BoundLogger = structlog.get_logger(name)
    if context:
        logger = logger.bind(**context)
    return logger


def setup_logging(
    level: str = "INFO",
    format: str = "console",
    log_file: str | None = None,
    force: bool = False,
) -> None:
    """ロギングを設定する。

    Parameters
    ----------
    level : str, default="INFO"
        ログレベル（DEBUG/INFO/WARNING/ERROR/CRITICAL）。
    format : str, default="console"
        出力フォーマット（console/json/plain）。
    log_file : str | None, optional
        ログファイルのパス。None の場合は stdout のみ出力。
    force : bool, default=False
        True の場合、既に初期化済みでも再設定する。
    """
    global _initialized  # noqa: PLW0603
    if _initialized and not force:
        return
    _initialized = True

    level_value = getattr(logging, level.upper(), logging.INFO)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=(format == "console"))

    console_formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(level_value)
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    if log_file is not None:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(console_formatter)
        root_logger.addHandler(file_handler)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
