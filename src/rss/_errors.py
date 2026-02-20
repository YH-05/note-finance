"""Error utilities for rss package."""
import logging
from typing import Any

logger = logging.getLogger(__name__)


def log_and_reraise(
    exc: Exception,
    message: str,
    *,
    extra: dict[str, Any] | None = None,
) -> None:
    """例外をログに記録して再 raise する."""
    if extra:
        logger.error(message, exc_info=exc, **extra)
    else:
        logger.error(message, exc_info=exc)
    raise exc
