"""Structured logging configuration using structlog.

quants テンプレート由来のロギングユーティリティ。
``get_logger(__name__)`` で structlog の BoundLogger を取得し、
キーワード引数で構造化ログを出力できる。

Examples
--------
>>> from quants.utils.logging_config import get_logger
>>> logger = get_logger(__name__)
>>> logger.info("processing_started", item_count=100)
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from collections.abc import Iterator

import structlog
from structlog import BoundLogger
from structlog.contextvars import bind_contextvars, unbind_contextvars

type LogFormat = Literal["json", "console", "plain"]
type LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def add_timestamp(
    _: Any,
    __: Any,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add ISO timestamp to log entries."""
    event_dict["timestamp"] = datetime.now(UTC).isoformat()
    return event_dict


def add_log_level_upper(
    _: Any,
    __: Any,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Convert log level to uppercase for consistency."""
    if "level" in event_dict:
        event_dict["level"] = event_dict["level"].upper()
    return event_dict


def setup_logging(
    *,
    level: LogLevel | str = "INFO",
    format: LogFormat = "console",
    log_file: str | Path | None = None,
    include_timestamp: bool = True,
    force: bool = False,
) -> None:
    """Setup structured logging configuration.

    Parameters
    ----------
    level : LogLevel | str
        Logging level. Can also be set via ``LOG_LEVEL`` env var.
    format : LogFormat
        Output format: "json", "console", or "plain".
    log_file : str | Path | None
        Optional file path to write logs to.
    include_timestamp : bool
        Whether to add ISO timestamps.
    force : bool
        Force reconfiguration even if already configured.
    """
    env_level = os.environ.get("LOG_LEVEL", "").upper()
    if env_level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        level = env_level

    env_format = os.environ.get("LOG_FORMAT", "").lower()
    if env_format in ("json", "console", "plain"):
        format = env_format  # type: ignore[assignment]

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        add_log_level_upper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if include_timestamp:
        processors.insert(3, add_timestamp)

    if format == "json":
        processors.append(structlog.processors.JSONRenderer())
    elif format == "console":
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        processors.append(structlog.processors.KeyValueRenderer())

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
        force=force,
    )

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        logging.root.addHandler(file_handler)

    if level != "DEBUG":
        for logger_name in ("urllib3", "asyncio", "filelock"):
            logging.getLogger(logger_name).setLevel(logging.WARNING)


def get_logger(name: str, **context: Any) -> BoundLogger:
    """Get a structured logger instance with optional context.

    Parameters
    ----------
    name : str
        Name of the logger (typically ``__name__``).
    **context : Any
        Initial context to bind to the logger.

    Returns
    -------
    BoundLogger
        Configured structlog logger instance.

    Examples
    --------
    >>> logger = get_logger(__name__)
    >>> logger.info("processing_started", items_count=100)
    """
    logger: BoundLogger = structlog.get_logger(name)
    if context:
        logger = logger.bind(**context)
    return logger


@contextmanager
def log_context(**kwargs: Any) -> Iterator[None]:
    """Context manager to temporarily bind context variables.

    Parameters
    ----------
    **kwargs : Any
        Context variables to bind.
    """
    bind_contextvars(**kwargs)
    try:
        yield
    finally:
        unbind_contextvars(*kwargs.keys())
