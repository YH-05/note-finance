"""スレッドセーフなレートリミッター.

quants プロジェクトの edgar.rate_limiter から移植。
外部依存なしのスタンドアロン実装。
"""

from __future__ import annotations

import threading
import time

import structlog

logger = structlog.get_logger(__name__)

DEFAULT_RATE_LIMIT_PER_SECOND = 10


class RateLimiter:
    """Thread-safe rate limiter.

    Parameters
    ----------
    max_requests_per_second : int
        Maximum number of requests allowed per second.
    """

    def __init__(
        self,
        max_requests_per_second: int = DEFAULT_RATE_LIMIT_PER_SECOND,
    ) -> None:
        if max_requests_per_second <= 0:
            msg = (
                f"max_requests_per_second must be positive, "
                f"got {max_requests_per_second}"
            )
            raise ValueError(msg)

        self.max_requests_per_second = max_requests_per_second
        self._min_interval = 1.0 / max_requests_per_second
        self._last_request_time = 0.0
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Acquire permission to make a request, blocking if necessary."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            wait_time = self._min_interval - elapsed

            if wait_time > 0:
                time.sleep(wait_time)

            self._last_request_time = time.monotonic()

    def __repr__(self) -> str:
        return f"RateLimiter(max_requests_per_second={self.max_requests_per_second})"


__all__ = ["RateLimiter"]
