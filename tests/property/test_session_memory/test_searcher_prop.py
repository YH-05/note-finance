"""searcher モジュールのプロパティベーステスト.

受け入れ条件:
- Hypothesis でRRFスコア単調減少を検証
- Hypothesis で時間減衰 in (0,1] を検証
"""

from datetime import datetime, timedelta, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from session_memory.searcher import (
    SearchMode,
    SearchResult,
    compute_rrf_score,
    compute_time_decay,
    merge_rrf,
)

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_rank_strategy = st.integers(min_value=0, max_value=10_000)
_k_strategy = st.integers(min_value=1, max_value=1_000)
_weight_strategy = st.floats(min_value=0.01, max_value=1.0, allow_nan=False)
_mode_strategy = st.sampled_from(list(SearchMode))


@st.composite
def _datetime_pair(draw: st.DrawFn) -> tuple[datetime, datetime]:
    """(created_at, now) のペアを生成する。now >= created_at.

    Parameters
    ----------
    draw : st.DrawFn
        Hypothesis の draw 関数

    Returns
    -------
    tuple[datetime, datetime]
        (created_at, now) の日時ペア
    """
    days_ago = draw(st.integers(min_value=0, max_value=3650))
    now = datetime(2026, 3, 24, tzinfo=timezone.utc)
    created_at = now - timedelta(days=days_ago)
    return created_at, now


@st.composite
def _ranked_list(draw: st.DrawFn) -> list[tuple[str, int]]:
    """(chunk_key, rank) のリストを生成する。chunk_key はユニーク.

    Parameters
    ----------
    draw : st.DrawFn
        Hypothesis の draw 関数

    Returns
    -------
    list[tuple[str, int]]
        (chunk_key, rank) のリスト
    """
    n = draw(st.integers(min_value=0, max_value=20))
    keys = [f"chunk-{i}" for i in range(n)]
    return [(k, i) for i, k in enumerate(keys)]


# ---------------------------------------------------------------------------
# プロパティテスト: compute_rrf_score
# ---------------------------------------------------------------------------


class TestRrfScoreProperty:
    """compute_rrf_score のプロパティテスト."""

    @given(rank=_rank_strategy, k=_k_strategy)
    @settings(max_examples=200)
    def test_プロパティ_スコアは常に正の値(self, rank: int, k: int) -> None:
        """任意の非負 rank, 正の k でスコアが正."""
        score = compute_rrf_score(rank=rank, k=k)
        assert score > 0.0

    @given(rank=_rank_strategy, k=_k_strategy)
    @settings(max_examples=200)
    def test_プロパティ_スコアは1_k以下(self, rank: int, k: int) -> None:
        """スコアの最大値は 1/k."""
        score = compute_rrf_score(rank=rank, k=k)
        assert score <= 1.0 / k + 1e-10  # 浮動小数点誤差

    @given(k=_k_strategy)
    @settings(max_examples=100)
    def test_プロパティ_RRFスコア単調減少(self, k: int) -> None:
        """rank が増加するとスコアは単調減少する."""
        scores = [compute_rrf_score(rank=r, k=k) for r in range(50)]
        for i in range(len(scores) - 1):
            assert scores[i] > scores[i + 1], (
                f"Non-monotonic at rank {i}: {scores[i]} <= {scores[i + 1]}"
            )


# ---------------------------------------------------------------------------
# プロパティテスト: compute_time_decay
# ---------------------------------------------------------------------------


class TestTimeDecayProperty:
    """compute_time_decay のプロパティテスト."""

    @given(dt_pair=_datetime_pair(), mode=_mode_strategy)
    @settings(max_examples=200)
    def test_プロパティ_時間減衰は0より大きく1以下(
        self, dt_pair: tuple[datetime, datetime], mode: SearchMode
    ) -> None:
        """任意の日時ペア・モードで decay in (0, 1]."""
        created_at, now = dt_pair
        decay = compute_time_decay(
            created_at=created_at.isoformat(),
            now=now,
            mode=mode,
        )
        assert 0.0 < decay <= 1.0, f"mode={mode}, decay={decay}"

    @given(dt_pair=_datetime_pair())
    @settings(max_examples=100)
    def test_プロパティ_RELEVANCEモードは常に1(
        self, dt_pair: tuple[datetime, datetime]
    ) -> None:
        """RELEVANCE モードでは常に 1.0."""
        created_at, now = dt_pair
        decay = compute_time_decay(
            created_at=created_at.isoformat(),
            now=now,
            mode=SearchMode.RELEVANCE,
        )
        assert decay == 1.0

    @given(mode=st.sampled_from([SearchMode.RECENT, SearchMode.HYBRID]))
    @settings(max_examples=50)
    def test_プロパティ_同時刻なら減衰なし(self, mode: SearchMode) -> None:
        """created_at == now なら decay == 1.0."""
        now = datetime(2026, 3, 24, tzinfo=timezone.utc)
        decay = compute_time_decay(
            created_at=now.isoformat(),
            now=now,
            mode=mode,
        )
        assert decay == 1.0

    @given(
        days_recent=st.integers(min_value=0, max_value=100),
        days_old=st.integers(min_value=101, max_value=3650),
    )
    @settings(max_examples=100)
    def test_プロパティ_RECENTモードで古いほど減衰が大きい(
        self, days_recent: int, days_old: int
    ) -> None:
        """RECENT モードで days_recent < days_old なら decay_recent >= decay_old."""
        now = datetime(2026, 3, 24, tzinfo=timezone.utc)
        recent = (now - timedelta(days=days_recent)).isoformat()
        old = (now - timedelta(days=days_old)).isoformat()
        decay_recent = compute_time_decay(
            created_at=recent, now=now, mode=SearchMode.RECENT
        )
        decay_old = compute_time_decay(created_at=old, now=now, mode=SearchMode.RECENT)
        assert decay_recent >= decay_old


# ---------------------------------------------------------------------------
# プロパティテスト: merge_rrf
# ---------------------------------------------------------------------------


class TestMergeRrfProperty:
    """merge_rrf のプロパティテスト."""

    @given(fts=_ranked_list(), vec=_ranked_list())
    @settings(max_examples=100)
    def test_プロパティ_結果はスコア降順(
        self,
        fts: list[tuple[str, int]],
        vec: list[tuple[str, int]],
    ) -> None:
        """merge_rrf の結果は常にスコア降順."""
        merged = merge_rrf(fts_ranked=fts, vec_ranked=vec)
        scores = [r.score for r in merged]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]

    @given(fts=_ranked_list(), vec=_ranked_list())
    @settings(max_examples=100)
    def test_プロパティ_結果のchunk_keyはユニーク(
        self,
        fts: list[tuple[str, int]],
        vec: list[tuple[str, int]],
    ) -> None:
        """merge_rrf の結果の chunk_key は全てユニーク."""
        merged = merge_rrf(fts_ranked=fts, vec_ranked=vec)
        keys = [r.chunk_key for r in merged]
        assert len(keys) == len(set(keys))

    @given(fts=_ranked_list(), vec=_ranked_list())
    @settings(max_examples=100)
    def test_プロパティ_結果数はFTSとVECのユニオン以下(
        self,
        fts: list[tuple[str, int]],
        vec: list[tuple[str, int]],
    ) -> None:
        """結果数は FTS と VEC の chunk_key ユニオンサイズ以下."""
        merged = merge_rrf(fts_ranked=fts, vec_ranked=vec)
        fts_keys = {k for k, _ in fts}
        vec_keys = {k for k, _ in vec}
        union_size = len(fts_keys | vec_keys)
        assert len(merged) <= union_size

    @given(fts=_ranked_list(), vec=_ranked_list())
    @settings(max_examples=100)
    def test_プロパティ_全スコアは正の値(
        self,
        fts: list[tuple[str, int]],
        vec: list[tuple[str, int]],
    ) -> None:
        """全ての SearchResult.score は正."""
        merged = merge_rrf(fts_ranked=fts, vec_ranked=vec)
        for r in merged:
            assert r.score > 0.0
