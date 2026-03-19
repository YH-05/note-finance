"""academic パッケージの型定義.

学術論文メタデータの構造化に使用する frozen dataclass を提供する。
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AuthorInfo:
    """論文著者の情報."""

    name: str
    s2_author_id: str | None = None
    organization: str | None = None


@dataclass(frozen=True)
class CitationInfo:
    """引用論文の情報."""

    title: str
    arxiv_id: str | None = None
    s2_paper_id: str | None = None


@dataclass(frozen=True)
class PaperMetadata:
    """論文メタデータの全体構造."""

    arxiv_id: str
    title: str
    authors: tuple[AuthorInfo, ...] = field(default_factory=tuple)
    references: tuple[CitationInfo, ...] = field(default_factory=tuple)
    citations: tuple[CitationInfo, ...] = field(default_factory=tuple)
    abstract: str | None = None
    s2_paper_id: str | None = None
    published: str | None = None
    updated: str | None = None


@dataclass(frozen=True)
class AcademicConfig:
    """API 設定."""

    s2_api_key: str | None = None
    s2_rate_limit: float = 1.0
    arxiv_rate_limit: float = 3.0
    cache_ttl: int = 604800
    max_retries: int = 3
    timeout: float = 30.0


__all__ = [
    "AcademicConfig",
    "AuthorInfo",
    "CitationInfo",
    "PaperMetadata",
]
