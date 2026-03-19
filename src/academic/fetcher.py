"""PaperFetcher オーケストレータ.

cache -> S2 -> arXiv の3段フォールバックで論文メタデータを取得する。
"""

from __future__ import annotations

from typing import Any, Protocol

import structlog

from .arxiv_client import ArxivClient
from .cache import SQLiteCache, get_academic_cache, make_cache_key
from .errors import AcademicError, PaperNotFoundError, RetryableError
from .s2_client import S2Client
from .types import (
    AcademicConfig,
    AuthorInfo,
    CitationInfo,
    PaperMetadata,
)

logger = structlog.get_logger(__name__)


class S2ClientProtocol(Protocol):
    def fetch_paper(self, arxiv_id: str) -> dict[str, Any]: ...
    def fetch_papers_batch(self, arxiv_ids: list[str]) -> list[dict[str, Any]]: ...
    def close(self) -> None: ...


class ArxivClientProtocol(Protocol):
    def fetch_paper(self, arxiv_id: str) -> PaperMetadata: ...
    def close(self) -> None: ...


class CacheProtocol(Protocol):
    def get(self, key: str) -> dict[str, Any] | None: ...
    def set(self, key: str, value: dict[str, Any]) -> None: ...


class PaperFetcher:
    """S2Client + ArxivClient + SQLiteCache を統合するオーケストレータ."""

    def __init__(
        self,
        s2_client: S2ClientProtocol | None = None,
        arxiv_client: ArxivClientProtocol | None = None,
        cache: CacheProtocol | None = None,
        config: AcademicConfig | None = None,
    ) -> None:
        if config is None:
            config = AcademicConfig()

        self._s2_client = s2_client or S2Client(config=config)
        self._arxiv_client = arxiv_client or ArxivClient(config=config)
        self._cache = cache or get_academic_cache(config=config)

        logger.info("PaperFetcher initialized")

    def fetch_paper(self, arxiv_id: str) -> PaperMetadata:
        """単一論文のメタデータを取得する（3段フォールバック）."""
        cache_key = make_cache_key(arxiv_id)
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.info("Cache hit", arxiv_id=arxiv_id)
            return _dict_to_paper_metadata(cached)

        try:
            raw = self._s2_client.fetch_paper(arxiv_id)
            paper = self._parse_s2_response(raw, arxiv_id)
            self._save_to_cache(cache_key, paper)
            return paper
        except (PaperNotFoundError, RetryableError) as exc:
            logger.warning(
                "S2 fetch failed, falling back to arXiv",
                arxiv_id=arxiv_id,
                error=str(exc),
            )

        paper = self._arxiv_client.fetch_paper(arxiv_id)
        self._save_to_cache(cache_key, paper)
        return paper

    def fetch_papers_batch(self, arxiv_ids: list[str]) -> list[PaperMetadata]:
        """複数論文のメタデータをバッチ取得する."""
        if not arxiv_ids:
            return []

        results: dict[str, PaperMetadata] = {}

        uncached_ids: list[str] = []
        for arxiv_id in arxiv_ids:
            cache_key = make_cache_key(arxiv_id)
            cached = self._cache.get(cache_key)
            if cached is not None:
                results[arxiv_id] = _dict_to_paper_metadata(cached)
            else:
                uncached_ids.append(arxiv_id)

        if not uncached_ids:
            return [results[aid] for aid in arxiv_ids]

        s2_failed_ids: list[str] = []
        try:
            s2_results = self._s2_client.fetch_papers_batch(uncached_ids)
            for idx, arxiv_id in enumerate(uncached_ids):
                if idx >= len(s2_results):
                    s2_failed_ids.append(arxiv_id)
                    continue
                raw: dict[str, Any] | None = s2_results[idx]
                if raw is None:
                    s2_failed_ids.append(arxiv_id)
                    continue
                paper = self._parse_s2_response(raw, arxiv_id)
                results[arxiv_id] = paper
                self._save_to_cache(make_cache_key(arxiv_id), paper)

        except (RetryableError, AcademicError) as exc:
            logger.warning(
                "S2 batch fetch failed, falling back to arXiv",
                error=str(exc),
            )
            s2_failed_ids = uncached_ids

        for arxiv_id in s2_failed_ids:
            try:
                paper = self._arxiv_client.fetch_paper(arxiv_id)
                results[arxiv_id] = paper
                self._save_to_cache(make_cache_key(arxiv_id), paper)
            except AcademicError as exc:
                logger.error(
                    "arXiv fallback also failed",
                    arxiv_id=arxiv_id,
                    error=str(exc),
                )

        return [results[aid] for aid in arxiv_ids if aid in results]

    def _parse_s2_response(self, raw: dict[str, Any], arxiv_id: str) -> PaperMetadata:
        authors = tuple(
            AuthorInfo(
                name=a.get("name", "Unknown"),
                s2_author_id=a.get("authorId"),
            )
            for a in (raw.get("authors") or [])
        )

        references = tuple(
            CitationInfo(
                title=r.get("title", ""),
                arxiv_id=(r.get("externalIds") or {}).get("ArXiv"),
                s2_paper_id=r.get("paperId"),
            )
            for r in (raw.get("references") or [])
        )

        citations = tuple(
            CitationInfo(
                title=c.get("title", ""),
                arxiv_id=(c.get("externalIds") or {}).get("ArXiv"),
                s2_paper_id=c.get("paperId"),
            )
            for c in (raw.get("citations") or [])
        )

        return PaperMetadata(
            arxiv_id=arxiv_id,
            title=raw.get("title", ""),
            authors=authors,
            references=references,
            citations=citations,
            abstract=raw.get("abstract"),
            s2_paper_id=raw.get("paperId"),
            published=raw.get("publicationDate"),
        )

    def _save_to_cache(self, cache_key: str, paper: PaperMetadata) -> None:
        data = _paper_metadata_to_dict(paper)
        try:
            self._cache.set(cache_key, data)
        except Exception as exc:
            logger.warning("Cache save failed", cache_key=cache_key, error=str(exc))

    def close(self) -> None:
        if hasattr(self._s2_client, "close"):
            self._s2_client.close()
        if hasattr(self._arxiv_client, "close"):
            self._arxiv_client.close()

    def __enter__(self) -> PaperFetcher:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def _paper_metadata_to_dict(paper: PaperMetadata) -> dict[str, Any]:
    return {
        "arxiv_id": paper.arxiv_id,
        "title": paper.title,
        "authors": [
            {
                "name": a.name,
                "s2_author_id": a.s2_author_id,
                "organization": a.organization,
            }
            for a in paper.authors
        ],
        "references": [
            {
                "title": r.title,
                "arxiv_id": r.arxiv_id,
                "s2_paper_id": r.s2_paper_id,
            }
            for r in paper.references
        ],
        "citations": [
            {
                "title": c.title,
                "arxiv_id": c.arxiv_id,
                "s2_paper_id": c.s2_paper_id,
            }
            for c in paper.citations
        ],
        "abstract": paper.abstract,
        "s2_paper_id": paper.s2_paper_id,
        "published": paper.published,
        "updated": paper.updated,
    }


def _dict_to_paper_metadata(data: dict[str, Any]) -> PaperMetadata:
    authors = tuple(
        AuthorInfo(
            name=a.get("name", "Unknown"),
            s2_author_id=a.get("s2_author_id"),
            organization=a.get("organization"),
        )
        for a in (data.get("authors") or [])
    )

    references = tuple(
        CitationInfo(
            title=r.get("title", ""),
            arxiv_id=r.get("arxiv_id"),
            s2_paper_id=r.get("s2_paper_id"),
        )
        for r in (data.get("references") or [])
    )

    citations = tuple(
        CitationInfo(
            title=c.get("title", ""),
            arxiv_id=c.get("arxiv_id"),
            s2_paper_id=c.get("s2_paper_id"),
        )
        for c in (data.get("citations") or [])
    )

    return PaperMetadata(
        arxiv_id=data["arxiv_id"],
        title=data.get("title", ""),
        authors=authors,
        references=references,
        citations=citations,
        abstract=data.get("abstract"),
        s2_paper_id=data.get("s2_paper_id"),
        published=data.get("published"),
        updated=data.get("updated"),
    )


def paper_metadata_to_dict(paper: PaperMetadata) -> dict[str, Any]:
    """PaperMetadata を JSON シリアライズ可能な dict に変換する."""
    return _paper_metadata_to_dict(paper)


__all__ = ["PaperFetcher", "paper_metadata_to_dict"]
