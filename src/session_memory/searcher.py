"""FTS5 + sqlite-vec RRF 統合検索エンジン.

Reciprocal Rank Fusion (RRF) により全文検索とベクトル検索を統合し、
SearchMode 別の時間減衰を適用する。

RRF 統合スコア:
    ``score = w_fts/(k+rank_fts) + w_vec/(k+rank_vec)``

SearchMode 別の時間減衰:
    - RELEVANCE: 減衰なし (1.0)
    - RECENT: 半減期30日, weight=0.3
    - HYBRID: 半減期30日, weight=0.1
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from session_memory._logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

_DEFAULT_K = 60
"""RRF の定数 k（デフォルト: 60）."""

_DEFAULT_W_FTS = 0.4
"""FTS スコアの重み（デフォルト: 0.4）."""

_DEFAULT_W_VEC = 0.6
"""ベクトルスコアの重み（デフォルト: 0.6）."""

_HALF_LIFE_DAYS = 30.0
"""時間減衰の半減期（日数）."""


# ---------------------------------------------------------------------------
# Enum
# ---------------------------------------------------------------------------


class SearchMode(Enum):
    """検索モード.

    Attributes
    ----------
    RELEVANCE : str
        関連度優先（時間減衰なし）
    RECENT : str
        新しさ優先（半減期30日, weight=0.3）
    HYBRID : str
        関連度+新しさのハイブリッド（半減期30日, weight=0.1）
    """

    RELEVANCE = "relevance"
    RECENT = "recent"
    HYBRID = "hybrid"


# ---------------------------------------------------------------------------
# データクラス
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SearchResult:
    """検索結果の1件を表す不変データクラス.

    Parameters
    ----------
    chunk_key : str
        チャンクの一意識別子
    score : float
        RRF統合スコア（時間減衰適用後）
    content : str | None
        チャンク本文（オプション）
    session_id : str | None
        所属セッションID（オプション）
    created_at : str | None
        作成日時（ISO 8601 形式、オプション）
    """

    chunk_key: str
    score: float
    content: str | None = None
    session_id: str | None = None
    created_at: str | None = None


# ---------------------------------------------------------------------------
# 時間減衰パラメータ
# ---------------------------------------------------------------------------

_DECAY_PARAMS: dict[SearchMode, float] = {
    SearchMode.RELEVANCE: 0.0,
    SearchMode.RECENT: 0.3,
    SearchMode.HYBRID: 0.1,
}
"""SearchMode ごとの時間減衰 weight.

decay = 1 - weight + weight * 2^(-days / half_life)
weight=0 のとき decay=1（減衰なし）。
"""


# ---------------------------------------------------------------------------
# 公開関数
# ---------------------------------------------------------------------------


def compute_rrf_score(*, rank: int, k: int = _DEFAULT_K) -> float:
    """RRF スコアを計算する.

    Parameters
    ----------
    rank : int
        検索結果内でのランク（0始まり）
    k : int
        RRF定数（デフォルト: 60）

    Returns
    -------
    float
        RRF スコア = 1 / (k + rank)

    Raises
    ------
    ValueError
        rank が負、または k が 0 以下の場合
    """
    if rank < 0:
        raise ValueError(f"rank must be non-negative, got {rank}")
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    return 1.0 / (k + rank)


def compute_time_decay(
    *,
    created_at: str,
    now: datetime,
    mode: SearchMode,
) -> float:
    """SearchMode に基づく時間減衰係数を計算する.

    減衰式:
        ``decay = 1 - weight + weight * 2^(-days / half_life)``

    - RELEVANCE (weight=0): 常に 1.0
    - RECENT (weight=0.3): 半減期30日
    - HYBRID (weight=0.1): 半減期30日

    Parameters
    ----------
    created_at : str
        チャンク作成日時（ISO 8601 形式）
    now : datetime
        現在時刻（timezone-aware）
    mode : SearchMode
        検索モード

    Returns
    -------
    float
        時間減衰係数（0 < decay <= 1）
    """
    weight = _DECAY_PARAMS[mode]
    if weight == 0.0:
        return 1.0

    try:
        created = datetime.fromisoformat(created_at)
    except (ValueError, TypeError):
        logger.warning(
            "Failed to parse created_at, falling back to decay=1.0",
            created_at=created_at,
        )
        return 1.0

    # timezone-naive な場合は UTC として扱う
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)

    delta_days = max((now - created).total_seconds() / 86400.0, 0.0)

    # decay = 1 - weight + weight * 2^(-days / half_life)
    decay = 1.0 - weight + weight * math.pow(2.0, -delta_days / _HALF_LIFE_DAYS)
    return decay


def merge_rrf(
    *,
    fts_ranked: list[tuple[str, int]],
    vec_ranked: list[tuple[str, int]],
    w_fts: float = _DEFAULT_W_FTS,
    w_vec: float = _DEFAULT_W_VEC,
    k: int = _DEFAULT_K,
) -> list[SearchResult]:
    """FTS と VEC のランキングを RRF で統合する.

    Parameters
    ----------
    fts_ranked : list[tuple[str, int]]
        FTS 検索結果のリスト。各要素は (chunk_key, rank)。
    vec_ranked : list[tuple[str, int]]
        ベクトル検索結果のリスト。各要素は (chunk_key, rank)。
    w_fts : float
        FTS の重み（デフォルト: 0.4）
    w_vec : float
        ベクトルの重み（デフォルト: 0.6）
    k : int
        RRF 定数（デフォルト: 60）

    Returns
    -------
    list[SearchResult]
        統合スコア降順でソートされた検索結果リスト
    """
    scores: dict[str, float] = {}

    for chunk_key, rank in fts_ranked:
        rrf = compute_rrf_score(rank=rank, k=k)
        scores[chunk_key] = scores.get(chunk_key, 0.0) + w_fts * rrf

    for chunk_key, rank in vec_ranked:
        rrf = compute_rrf_score(rank=rank, k=k)
        scores[chunk_key] = scores.get(chunk_key, 0.0) + w_vec * rrf

    results = [
        SearchResult(chunk_key=key, score=score) for key, score in scores.items()
    ]

    # スコア降順でソート
    results.sort(key=lambda r: r.score, reverse=True)

    logger.debug(
        "merge_rrf completed",
        fts_count=len(fts_ranked),
        vec_count=len(vec_ranked),
        merged_count=len(results),
    )
    return results


__all__ = [
    "SearchMode",
    "SearchResult",
    "compute_rrf_score",
    "compute_time_decay",
    "merge_rrf",
]
