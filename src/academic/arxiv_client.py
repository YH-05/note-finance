"""arXiv API クライアント（Semantic Scholar のフォールバック用）.

feedparser で Atom XML をパースし、PaperMetadata に変換する。
arXiv API は引用情報を提供しないため、references/citations は常に空。
"""

from __future__ import annotations

import xml.etree.ElementTree as ET  # nosec B405 - ET.ParseError type only

import defusedxml.ElementTree as DefusedET
import feedparser
import httpx
import structlog
from typing import Any

from .errors import PaperNotFoundError, ParseError
from .rate_limiter import RateLimiter
from .retry import classify_http_error, create_retry_decorator
from .types import AcademicConfig, AuthorInfo, PaperMetadata

logger = structlog.get_logger(__name__)

_BASE_URL = "https://export.arxiv.org/api"


class ArxivClient:
    """arXiv API クライアント."""

    def __init__(self, config: AcademicConfig | None = None) -> None:
        if config is None:
            config = AcademicConfig()

        self._http_client = httpx.Client(
            base_url=_BASE_URL,
            timeout=config.timeout,
        )

        max_rps = max(1, int(config.arxiv_rate_limit))
        self._rate_limiter = RateLimiter(max_requests_per_second=max_rps)

        self._retry = create_retry_decorator(
            max_attempts=config.max_retries,
            base_wait=1.0,
            max_wait=30.0,
        )

        logger.info(
            "ArxivClient initialized",
            rate_limit_rps=max_rps,
            max_retries=config.max_retries,
        )

    def fetch_paper(self, arxiv_id: str) -> PaperMetadata:
        """単一論文のメタデータを arXiv API から取得する."""

        @self._retry
        def _do_fetch() -> PaperMetadata:
            self._rate_limiter.acquire()
            response = self._http_client.get(
                "/query", params={"id_list": arxiv_id}
            )
            if response.status_code != 200:
                raise classify_http_error(response.status_code, response)
            return _parse_atom_response(response.text, arxiv_id)

        return _do_fetch()

    def close(self) -> None:
        self._http_client.close()

    def __enter__(self) -> ArxivClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def _parse_atom_response(text: str, arxiv_id: str) -> PaperMetadata:
    """arXiv Atom XML レスポンスをパースして PaperMetadata に変換する."""
    try:
        root = DefusedET.fromstring(text)
    except ET.ParseError as exc:
        raise ParseError(f"arXiv Atom フィードのパースに失敗しました: {exc}") from exc

    try:
        feed = feedparser.parse(text)
    except Exception as exc:
        raise ParseError(f"arXiv Atom フィードのパースに失敗しました: {exc}") from exc

    if feed.bozo and not feed.entries:
        bozo_exception = feed.get("bozo_exception", "Unknown parse error")
        raise ParseError(f"arXiv Atom フィードのパースに失敗しました: {bozo_exception}")

    if not feed.entries:
        raise PaperNotFoundError(
            f"論文が見つかりません: {arxiv_id}", status_code=404
        )

    entry = feed.entries[0]
    authors = _extract_authors_from_root(root)
    return _entry_to_paper_metadata(entry, arxiv_id, authors)


def _entry_to_paper_metadata(
    entry: Any, arxiv_id: str, authors: list[AuthorInfo]
) -> PaperMetadata:
    title = entry.get("title", "").replace("\n", " ").strip()
    abstract = entry.get("summary", "").strip() or None
    published = entry.get("published")
    updated = entry.get("updated")

    return PaperMetadata(
        arxiv_id=arxiv_id,
        title=title,
        authors=tuple(authors),
        references=(),
        citations=(),
        abstract=abstract,
        s2_paper_id=None,
        published=published,
        updated=updated,
    )


def _extract_authors_from_root(root: ET.Element) -> list[AuthorInfo]:
    """パース済み XML ルートから著者情報を抽出する."""
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }

    authors: list[AuthorInfo] = []
    for entry_elem in root.findall("atom:entry", ns):
        for author_elem in entry_elem.findall("atom:author", ns):
            name_elem = author_elem.find("atom:name", ns)
            if name_elem is None or not (name_elem.text or "").strip():
                continue

            name = (name_elem.text or "").strip()
            affiliation_elem = author_elem.find("arxiv:affiliation", ns)
            organization = None
            if affiliation_elem is not None and affiliation_elem.text:
                organization = affiliation_elem.text.strip() or None

            authors.append(
                AuthorInfo(name=name, s2_author_id=None, organization=organization)
            )

    return authors


__all__ = ["ArxivClient"]
