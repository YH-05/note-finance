"""academic 用リトライデコレータ・エラー分類ユーティリティ."""

from typing import Any

import structlog
import tenacity

from .errors import (
    AcademicError,
    PaperNotFoundError,
    PermanentError,
    RateLimitError,
    RetryableError,
)

logger = structlog.get_logger(__name__)


def create_retry_decorator(
    max_attempts: int = 3,
    base_wait: float = 1.0,
    max_wait: float = 60.0,
) -> Any:
    """academic 用リトライデコレータを生成する."""
    return tenacity.retry(
        retry=tenacity.retry_if_exception_type(RetryableError),
        stop=tenacity.stop_after_attempt(max_attempts),
        wait=tenacity.wait_exponential(multiplier=base_wait, max=max_wait)
        + tenacity.wait_random(0, 1),
        before_sleep=_log_retry,
        reraise=True,
    )


def classify_http_error(status_code: int, response: Any) -> AcademicError:
    """HTTP ステータスコードからエラーを分類する."""
    if status_code == 429:
        retry_after_f = _parse_retry_after(response)
        retry_after: int | None = (
            int(retry_after_f) if retry_after_f is not None else None
        )
        return RateLimitError(
            f"Rate limited ({status_code})",
            status_code=429,
            retry_after=retry_after,
        )
    elif status_code == 404:
        return PaperNotFoundError(
            f"Paper not found ({status_code})",
            status_code=404,
        )
    elif status_code >= 500:
        return RetryableError(
            f"Server error ({status_code})",
            status_code=status_code,
        )
    else:
        return PermanentError(
            f"HTTP {status_code} client error",
            status_code=status_code,
        )


def _parse_retry_after(response: Any) -> float | None:
    """Retry-After ヘッダをパースして秒数を返す."""
    if response is None or not hasattr(response, "headers"):
        return None

    retry_after_value = response.headers.get("Retry-After")
    if retry_after_value is None:
        return None

    try:
        return float(retry_after_value)
    except (ValueError, TypeError):
        return None


def _log_retry(retry_state: tenacity.RetryCallState) -> None:
    """リトライ前のログ出力."""
    exception = retry_state.outcome.exception()  # type: ignore[union-attr]
    logger.warning(
        "リトライ実行",
        attempt_number=retry_state.attempt_number,
        exception=str(exception),
    )
