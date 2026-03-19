"""Semantic Scholar API クライアント.

論文の著者・引用情報を Semantic Scholar Graph API から取得する。
"""

from __future__ import annotations

import os
from typing import Any

import httpx
import structlog

from .errors import PaperNotFoundError, RateLimitError, RetryableError
from .rate_limiter import RateLimiter
from .retry import classify_http_error, create_retry_decorator
from .types import AcademicConfig

logger = structlog.get_logger(__name__)

_BASE_URL = "https://api.semanticscholar.org/graph/v1"

_PAPER_FIELDS = (
    "title,authors,externalIds,references,citations,"
    "abstract,publicationDate,fieldsOfStudy"
)

_BATCH_MAX_SIZE = 500


class S2Client:
    """Semantic Scholar API クライアント."""

    def __init__(self, config: AcademicConfig | None = None) -> None:
        if config is None:
            config = AcademicConfig()

        self._api_key = config.s2_api_key or os.environ.get("S2_API_KEY")

        headers: dict[str, str] = {"Accept": "application/json"}
        if self._api_key is not None:
            headers["x-api-key"] = self._api_key

        self._http_client = httpx.Client(
            base_url=_BASE_URL,
            headers=headers,
            timeout=config.timeout,
        )

        max_rps = (
            max(1, int(1.0 / config.s2_rate_limit)) if config.s2_rate_limit > 0 else 1
        )
        self._rate_limiter = RateLimiter(max_requests_per_second=max_rps)

        self._retry = create_retry_decorator(
            max_attempts=config.max_retries,
            base_wait=0.5,
            max_wait=30.0,
        )

        logger.info(
            "S2Client initialized",
            has_api_key=self._api_key is not None,
            rate_limit_rps=max_rps,
        )

    def fetch_paper(self, arxiv_id: str) -> dict[str, Any]:
        """単一論文のメタデータを取得する."""

        @self._retry
        def _do_fetch() -> dict[str, Any]:
            self._rate_limiter.acquire()
            url = f"/paper/arXiv:{arxiv_id}"
            response = self._http_client.get(url, params={"fields": _PAPER_FIELDS})
            if response.status_code != 200:
                raise classify_http_error(response.status_code, response)
            data: dict[str, Any] = response.json()
            logger.info("Paper fetched", arxiv_id=arxiv_id, title=data.get("title"))
            return data

        return _do_fetch()

    def fetch_papers_batch(self, arxiv_ids: list[str]) -> list[dict[str, Any]]:
        """複数論文のメタデータをバッチ取得する."""
        if not arxiv_ids:
            return []

        results: list[dict[str, Any]] = []
        chunks = [
            arxiv_ids[i : i + _BATCH_MAX_SIZE]
            for i in range(0, len(arxiv_ids), _BATCH_MAX_SIZE)
        ]

        logger.info(
            "Batch fetch started",
            total_ids=len(arxiv_ids),
            num_chunks=len(chunks),
        )

        for chunk_idx, chunk in enumerate(chunks):
            chunk_results = self._fetch_batch_chunk(chunk, chunk_idx)
            results.extend(chunk_results)

        return results

    def _fetch_batch_chunk(
        self, arxiv_ids: list[str], chunk_idx: int
    ) -> list[dict[str, Any]]:
        @self._retry
        def _do_fetch() -> list[dict[str, Any]]:
            self._rate_limiter.acquire()
            ids_payload = [f"arXiv:{aid}" for aid in arxiv_ids]
            response = self._http_client.post(
                "/paper/batch",
                params={"fields": _PAPER_FIELDS},
                json={"ids": ids_payload},
            )
            if response.status_code != 200:
                raise classify_http_error(response.status_code, response)
            data: list[dict[str, Any]] = response.json()
            logger.info(
                "Batch chunk fetched",
                chunk_idx=chunk_idx,
                results_count=len(data),
            )
            return data

        return _do_fetch()

    def close(self) -> None:
        self._http_client.close()

    def __enter__(self) -> S2Client:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


__all__ = ["S2Client"]
