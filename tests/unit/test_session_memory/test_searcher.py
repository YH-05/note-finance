"""searcher モジュールのユニットテスト.

受け入れ条件:
- RRFスコアが正しく計算されること
- SearchMode別の時間減衰が正しく動作すること
- make check-all が成功すること
"""

import math
from datetime import datetime, timezone

import pytest

from session_memory.searcher import (
    SearchMode,
    SearchResult,
    compute_rrf_score,
    compute_time_decay,
    merge_rrf,
)

# ---------------------------------------------------------------------------
# RRFスコア計算テスト
# ---------------------------------------------------------------------------


class TestComputeRrfScore:
    """compute_rrf_score のユニットテスト."""

    def test_正常系_rank0で最大スコア(self) -> None:
        """rank=0 のとき最大スコアを返す."""
        score = compute_rrf_score(rank=0, k=60)
        assert score == pytest.approx(1.0 / 60.0)

    def test_正常系_rank1で正しいスコア(self) -> None:
        """rank=1 のとき 1/(k+1) を返す."""
        score = compute_rrf_score(rank=1, k=60)
        assert score == pytest.approx(1.0 / 61.0)

    def test_正常系_デフォルトk値は60(self) -> None:
        """k のデフォルト値が 60 であること."""
        score = compute_rrf_score(rank=5)
        assert score == pytest.approx(1.0 / 65.0)

    def test_正常系_大きなrankで小さなスコア(self) -> None:
        """rank が大きいほどスコアが小さくなる."""
        score_r0 = compute_rrf_score(rank=0)
        score_r10 = compute_rrf_score(rank=10)
        score_r100 = compute_rrf_score(rank=100)
        assert score_r0 > score_r10 > score_r100

    def test_正常系_スコアは常に正の値(self) -> None:
        """任意の非負 rank でスコアが正."""
        for rank in [0, 1, 10, 100, 1000]:
            assert compute_rrf_score(rank=rank) > 0.0

    def test_異常系_負のrankでValueError(self) -> None:
        """rank が負の場合 ValueError."""
        with pytest.raises(ValueError, match="rank must be non-negative"):
            compute_rrf_score(rank=-1)

    def test_異常系_kが0以下でValueError(self) -> None:
        """k が 0 以下の場合 ValueError."""
        with pytest.raises(ValueError, match="k must be positive"):
            compute_rrf_score(rank=0, k=0)
        with pytest.raises(ValueError, match="k must be positive"):
            compute_rrf_score(rank=0, k=-10)


# ---------------------------------------------------------------------------
# 時間減衰テスト
# ---------------------------------------------------------------------------


class TestComputeTimeDecay:
    """compute_time_decay のユニットテスト."""

    def test_正常系_RELEVANCE_モードで減衰なし(self) -> None:
        """RELEVANCE モードでは常に 1.0 を返す."""
        now = datetime(2026, 3, 24, tzinfo=timezone.utc)
        old = datetime(2025, 1, 1, tzinfo=timezone.utc)
        decay = compute_time_decay(
            created_at=old.isoformat(),
            now=now,
            mode=SearchMode.RELEVANCE,
        )
        assert decay == 1.0

    def test_正常系_RECENT_モードで半減期30日(self) -> None:
        """RECENT モードでは半減期30日の指数減衰."""
        now = datetime(2026, 3, 24, tzinfo=timezone.utc)
        # 30日前 -> 減衰係数 ~= 0.3 * exp(-ln2) + (1 - 0.3) = 0.7 + 0.3 * 0.5 = 0.85
        # RECENT: weight=0.3, half_life=30
        # decay = 1 - weight + weight * 2^(-days/half_life)
        # at 30 days: 1 - 0.3 + 0.3 * 0.5 = 0.85
        thirty_days_ago = datetime(2026, 2, 22, tzinfo=timezone.utc)
        decay = compute_time_decay(
            created_at=thirty_days_ago.isoformat(),
            now=now,
            mode=SearchMode.RECENT,
        )
        assert decay == pytest.approx(0.85, abs=0.01)

    def test_正常系_RECENT_モードで作成日が今日なら約1(self) -> None:
        """RECENT モードで経過日数0なら 1.0 に近い."""
        now = datetime(2026, 3, 24, tzinfo=timezone.utc)
        decay = compute_time_decay(
            created_at=now.isoformat(),
            now=now,
            mode=SearchMode.RECENT,
        )
        assert decay == pytest.approx(1.0, abs=0.001)

    def test_正常系_HYBRID_モードで弱い減衰(self) -> None:
        """HYBRID モードでは weight=0.1 の弱い減衰."""
        now = datetime(2026, 3, 24, tzinfo=timezone.utc)
        # 30 days: 1 - 0.1 + 0.1 * 0.5 = 0.95
        thirty_days_ago = datetime(2026, 2, 22, tzinfo=timezone.utc)
        decay = compute_time_decay(
            created_at=thirty_days_ago.isoformat(),
            now=now,
            mode=SearchMode.HYBRID,
        )
        assert decay == pytest.approx(0.95, abs=0.01)

    def test_正常系_時間減衰は0より大きく1以下(self) -> None:
        """減衰値は (0, 1] の範囲."""
        now = datetime(2026, 3, 24, tzinfo=timezone.utc)
        # 1年前
        old = datetime(2025, 3, 24, tzinfo=timezone.utc)
        for mode in SearchMode:
            decay = compute_time_decay(
                created_at=old.isoformat(),
                now=now,
                mode=mode,
            )
            assert 0.0 < decay <= 1.0, f"mode={mode}, decay={decay}"

    def test_正常系_古いほど減衰が大きい(self) -> None:
        """RECENT モードで古いほど減衰が大きい."""
        now = datetime(2026, 3, 24, tzinfo=timezone.utc)
        recent = datetime(2026, 3, 23, tzinfo=timezone.utc)
        old = datetime(2025, 3, 24, tzinfo=timezone.utc)
        decay_recent = compute_time_decay(
            created_at=recent.isoformat(), now=now, mode=SearchMode.RECENT
        )
        decay_old = compute_time_decay(
            created_at=old.isoformat(), now=now, mode=SearchMode.RECENT
        )
        assert decay_recent > decay_old

    def test_正常系_RECENTはHYBRIDより強い減衰(self) -> None:
        """同じ経過日数でも RECENT の方が HYBRID より減衰が大きい."""
        now = datetime(2026, 3, 24, tzinfo=timezone.utc)
        old = datetime(2025, 12, 24, tzinfo=timezone.utc)
        decay_recent = compute_time_decay(
            created_at=old.isoformat(), now=now, mode=SearchMode.RECENT
        )
        decay_hybrid = compute_time_decay(
            created_at=old.isoformat(), now=now, mode=SearchMode.HYBRID
        )
        assert decay_recent < decay_hybrid

    def test_正常系_不正なISO文字列で減衰1を返す(self) -> None:
        """パースできない created_at では安全にフォールバック."""
        now = datetime(2026, 3, 24, tzinfo=timezone.utc)
        decay = compute_time_decay(
            created_at="not-a-date",
            now=now,
            mode=SearchMode.RECENT,
        )
        assert decay == 1.0


# ---------------------------------------------------------------------------
# RRF統合 (merge_rrf) テスト
# ---------------------------------------------------------------------------


class TestMergeRrf:
    """merge_rrf のユニットテスト."""

    def test_正常系_FTSのみの結果をマージ(self) -> None:
        """FTS結果のみの場合、FTS重みだけでスコア計算."""
        fts_results = [
            ("chunk-a", 0),  # (chunk_key, rank)
            ("chunk-b", 1),
        ]
        merged = merge_rrf(
            fts_ranked=fts_results,
            vec_ranked=[],
            w_fts=0.4,
            w_vec=0.6,
        )
        assert len(merged) == 2
        # chunk-a は rank 0 -> score = 0.4/(60+0) = 0.4/60
        assert merged[0].chunk_key == "chunk-a"
        assert merged[0].score == pytest.approx(0.4 / 60.0)

    def test_正常系_VECのみの結果をマージ(self) -> None:
        """VEC結果のみの場合、VEC重みだけでスコア計算."""
        vec_results = [
            ("chunk-x", 0),
            ("chunk-y", 1),
        ]
        merged = merge_rrf(
            fts_ranked=[],
            vec_ranked=vec_results,
            w_fts=0.4,
            w_vec=0.6,
        )
        assert len(merged) == 2
        assert merged[0].chunk_key == "chunk-x"
        assert merged[0].score == pytest.approx(0.6 / 60.0)

    def test_正常系_両方の結果を統合(self) -> None:
        """FTS + VEC の両方に出現するキーのスコアが合算される."""
        fts_ranked = [("chunk-a", 0), ("chunk-b", 1)]
        vec_ranked = [("chunk-a", 0), ("chunk-c", 1)]
        merged = merge_rrf(
            fts_ranked=fts_ranked,
            vec_ranked=vec_ranked,
            w_fts=0.4,
            w_vec=0.6,
        )
        # chunk-a: FTS rank 0 + VEC rank 0
        # = 0.4/60 + 0.6/60 = 1.0/60
        chunk_a = next(r for r in merged if r.chunk_key == "chunk-a")
        expected = 0.4 / 60.0 + 0.6 / 60.0
        assert chunk_a.score == pytest.approx(expected)

    def test_正常系_スコア降順でソートされる(self) -> None:
        """結果はスコアの降順でソートされる."""
        fts_ranked = [("chunk-a", 0), ("chunk-b", 5)]
        vec_ranked = [("chunk-a", 0), ("chunk-b", 10)]
        merged = merge_rrf(
            fts_ranked=fts_ranked,
            vec_ranked=vec_ranked,
        )
        scores = [r.score for r in merged]
        assert scores == sorted(scores, reverse=True)

    def test_正常系_空の入力で空リスト(self) -> None:
        """FTS/VEC ともに空なら空リスト."""
        merged = merge_rrf(fts_ranked=[], vec_ranked=[])
        assert merged == []

    def test_正常系_デフォルト重みは04と06(self) -> None:
        """デフォルト重みが w_fts=0.4, w_vec=0.6 であること."""
        fts_ranked = [("chunk-a", 0)]
        vec_ranked = [("chunk-a", 0)]
        merged = merge_rrf(fts_ranked=fts_ranked, vec_ranked=vec_ranked)
        chunk_a = merged[0]
        expected = 0.4 / 60.0 + 0.6 / 60.0
        assert chunk_a.score == pytest.approx(expected)


# ---------------------------------------------------------------------------
# SearchResult データクラステスト
# ---------------------------------------------------------------------------


class TestSearchResult:
    """SearchResult のテスト."""

    def test_正常系_基本フィールド(self) -> None:
        """SearchResult のフィールドが正しく設定される."""
        result = SearchResult(
            chunk_key="session-001::0",
            score=0.5,
        )
        assert result.chunk_key == "session-001::0"
        assert result.score == 0.5
        assert result.content is None
        assert result.session_id is None
        assert result.created_at is None

    def test_正常系_全フィールド指定(self) -> None:
        """全フィールドを指定して SearchResult を作成できる."""
        result = SearchResult(
            chunk_key="session-001::0",
            score=0.85,
            content="test content",
            session_id="session-001",
            created_at="2026-03-24T00:00:00+00:00",
        )
        assert result.content == "test content"
        assert result.session_id == "session-001"
        assert result.created_at == "2026-03-24T00:00:00+00:00"


# ---------------------------------------------------------------------------
# SearchMode enumテスト
# ---------------------------------------------------------------------------


class TestSearchMode:
    """SearchMode のテスト."""

    def test_正常系_3つのモードが存在(self) -> None:
        """RELEVANCE, RECENT, HYBRID の3モードが存在する."""
        assert hasattr(SearchMode, "RELEVANCE")
        assert hasattr(SearchMode, "RECENT")
        assert hasattr(SearchMode, "HYBRID")

    def test_正常系_全モードの列挙(self) -> None:
        """SearchMode の全値を列挙できる."""
        modes = list(SearchMode)
        assert len(modes) == 3
