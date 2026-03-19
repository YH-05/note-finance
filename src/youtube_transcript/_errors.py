"""Error utilities for youtube_transcript package."""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from youtube_transcript._logging import get_logger

_default_logger = get_logger(__name__)


@contextmanager
def log_and_reraise(
    logger: Any,
    message: str,
    *,
    context: dict[str, Any] | None = None,
    reraise_as: type[Exception] | None = None,
) -> Generator[None, None, None]:
    """例外をログに記録して再 raise するコンテキストマネージャ。

    Parameters
    ----------
    logger : Any
        structlog ロガーインスタンス。
    message : str
        エラーメッセージのベース文字列。
    context : dict[str, Any] | None, optional
        ログに追加するコンテキスト情報。
    reraise_as : type[Exception] | None, optional
        指定した場合、発生した例外をこの型でラップして再 raise する。
        既に同じ型の例外の場合はラップしない。

    Examples
    --------
    >>> with log_and_reraise(logger, "save transcript", reraise_as=StorageError):
    ...     save_to_file()
    """
    try:
        yield
    except Exception as exc:
        log_kwargs: dict[str, Any] = {}
        if context:
            log_kwargs.update(context)
        log_kwargs["error"] = str(exc)
        logger.error(f"{message} failed", **log_kwargs)
        if reraise_as is not None and not isinstance(exc, reraise_as):
            raise reraise_as(f"{message} failed: {exc}") from exc
        raise
