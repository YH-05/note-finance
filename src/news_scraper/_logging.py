"""Logging configuration for news_scraper package.

This module provides structured logging using structlog,
consistent with the rest of the note-finance project.

Functions
---------
get_logger
    Get a structured logger instance.

Examples
--------
>>> from news_scraper._logging import get_logger
>>> logger = get_logger(__name__)
>>> logger  # doctest: +ELLIPSIS
<...>
"""

from __future__ import annotations

import logging
import os
import sys

import structlog
from structlog import BoundLogger

_initialized = False


def _ensure_basic_config() -> None:
    """Ensure basic logging configuration is set up before first use."""
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
    if not root_logger.handlers:
        root_logger.setLevel(level_value)
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


def get_logger(name: str, **context: object) -> BoundLogger:
    """Get a structured logger instance.

    Parameters
    ----------
    name : str
        Logger name (typically ``__name__``).
    **context : object
        Additional context key-value pairs to bind to the logger.

    Returns
    -------
    BoundLogger
        Configured structlog logger.

    Examples
    --------
    >>> logger = get_logger(__name__, module="example")
    >>> logger  # doctest: +ELLIPSIS
    <...>
    """
    _ensure_basic_config()
    logger: BoundLogger = structlog.get_logger(name)
    if context:
        logger = logger.bind(**context)
    return logger
