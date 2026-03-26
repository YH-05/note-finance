"""creator_enrichment.phases.gap_analysis のテスト.

GapAnalyzer によるギャップ分析ロジックを検証する。
- ジャンルローテーション
- genre_filter による固定ジャンル選択
- 低カバレッジ Concept 抽出
- Neo4j 接続エラーの PhaseError 変換
- Q2-Q6 の並列実行
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from creator_enrichment.phases.gap_analysis import GapAnalyzer
from creator_enrichment.types import PhaseError

# ---------------------------------------------------------------------------
# クエリディスパッチ用ヘルパー
# ---------------------------------------------------------------------------
# 各テストで繰り返し定義される side_effect を共通化する。
# query_map は {検索キーワード: 返却データ} の辞書。
# 複数のキーワードにマッチする場合は最初にマッチしたものを返す。

# Q1-Q6 を識別するためのキーワード
_Q1_KEY = "g.genre_id AS genre, g.name AS name"
_Q2_KEY = "cc.name AS category, cc.layer AS layer"
_Q3_KEY = "concept_count, content_count"
_Q4_KEY = "$genre_id"
_Q5_KEY = "duration('P7D')"
_Q6_KEY = "SERVES_AS"

_QUERY_KEYS = [_Q1_KEY, _Q2_KEY, _Q3_KEY, _Q4_KEY, _Q5_KEY, _Q6_KEY]


def _make_side_effect(
    query_map: dict[str, list[dict[str, Any]]],
) -> Any:
    """クエリキーワードに基づくディスパッチ関数を生成する.

    Parameters
    ----------
    query_map
        {キーワード文字列: 返却リスト} のマッピング

    Returns
    -------
    Callable
        execute_query の side_effect として使用する関数
    """

    def side_effect(
        query: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        for key in _QUERY_KEYS:
            if key in query and key in query_map:
                return query_map[key]
        return []

    return side_effect


def _make_tracking_side_effect(
    query_map: dict[str, list[dict[str, Any]]],
    tracker: list[str],
) -> Any:
    """クエリキーワードに基づくディスパッチ + クエリ追跡関数を生成する."""

    def side_effect(
        query: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        tracker.append(query)
        for key in _QUERY_KEYS:
            if key in query and key in query_map:
                return query_map[key]
        return []

    return side_effect


# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_neo4j_client() -> MagicMock:
    """execute_query メソッドを持つ Neo4j クライアントモック.

    Returns
    -------
    MagicMock
        execute_query メソッドを持つモック
    """
    client = MagicMock()
    client.execute_query = MagicMock(return_value=[])
    return client


@pytest.fixture
def q1_genre_data() -> list[dict[str, str | int]]:
    """Q1 ジャンル別コンテンツ数のモックデータ.

    career が最多(10)、beauty-romance が中間(5)、spiritual が最少(2)。
    """
    return [
        {"genre": "spiritual", "name": "占い・スピリチュアル", "content_count": 2},
        {"genre": "beauty-romance", "name": "美容・恋愛", "content_count": 5},
        {"genre": "career", "name": "転職・副業", "content_count": 10},
    ]


@pytest.fixture
def q3_low_coverage_data() -> list[dict[str, str | int]]:
    """Q3 低カバレッジ ConceptCategory のモックデータ."""
    return [
        {
            "category": "EmotionalHook",
            "name_ja": "感情フック",
            "layer": "How",
            "concept_count": 3,
            "content_count": 0,
        },
        {
            "category": "Objection",
            "name_ja": "反論処理",
            "layer": "How",
            "concept_count": 5,
            "content_count": 1,
        },
        {
            "category": "CopyFramework",
            "name_ja": "コピーフレームワーク",
            "layer": "How",
            "concept_count": 4,
            "content_count": 1,
        },
        {
            "category": "Monetization",
            "name_ja": "収益化",
            "layer": "What",
            "concept_count": 8,
            "content_count": 2,
        },
        {
            "category": "PersuasionTechnique",
            "name_ja": "説得技法",
            "layer": "How",
            "concept_count": 6,
            "content_count": 3,
        },
    ]


@pytest.fixture
def q4_low_coverage_concepts() -> list[dict[str, str | int]]:
    """Q4 低カバレッジ Concept のモックデータ."""
    return [
        {"name": "FOMO活用", "category": "EmotionalHook", "content_count": 0},
        {
            "name": "損失回避フレーミング",
            "category": "EmotionalHook",
            "content_count": 0,
        },
        {"name": "PASONAの法則", "category": "CopyFramework", "content_count": 0},
        {
            "name": "価格アンカリング",
            "category": "PersuasionTechnique",
            "content_count": 1,
        },
        {"name": "返金保証訴求", "category": "Objection", "content_count": 1},
    ]


@pytest.fixture
def q5_existing_samples() -> list[dict[str, str | None]]:
    """Q5 既存コンテンツサンプルのモックデータ."""
    return [
        {
            "text": "副業で月10万円を稼ぐための3つのステップ",
            "source_url": "https://example.com/article-1",
            "content_type": "Tip",
        },
        {
            "text": "転職成功率は2026年で前年比15%増加",
            "source_url": "https://example.com/article-2",
            "content_type": "Fact",
        },
    ]


@pytest.fixture
def q6_serves_as_data() -> list[dict[str, int]]:
    """Q6 SERVES_AS 接続率のモックデータ."""
    return [{"total": 50, "with_role": 30, "without_role": 20}]


@pytest.fixture
def all_query_map(
    q1_genre_data: list[dict],
    q3_low_coverage_data: list[dict],
    q4_low_coverage_concepts: list[dict],
    q5_existing_samples: list[dict],
    q6_serves_as_data: list[dict],
) -> dict[str, list[dict]]:
    """全クエリキーワードに対応するディスパッチマップ."""
    return {
        _Q1_KEY: q1_genre_data,
        _Q2_KEY: [],
        _Q3_KEY: q3_low_coverage_data,
        _Q4_KEY: q4_low_coverage_concepts,
        _Q5_KEY: q5_existing_samples,
        _Q6_KEY: q6_serves_as_data,
    }


@pytest.fixture
def q2_to_q6_map(
    q3_low_coverage_data: list[dict],
    q4_low_coverage_concepts: list[dict],
    q5_existing_samples: list[dict],
    q6_serves_as_data: list[dict],
) -> dict[str, list[dict]]:
    """Q2-Q6 のみのディスパッチマップ（genre_filter 使用時は Q1 不要）."""
    return {
        _Q2_KEY: [],
        _Q3_KEY: q3_low_coverage_data,
        _Q4_KEY: q4_low_coverage_concepts,
        _Q5_KEY: q5_existing_samples,
        _Q6_KEY: q6_serves_as_data,
    }


# ---------------------------------------------------------------------------
# ジャンルローテーション
# ---------------------------------------------------------------------------
class TestGenreRotation:
    """Q1 ジャンルローテーションのテスト."""

    def test_正常系_prev_genreがcareerの場合spiritualを選択(
        self,
        mock_neo4j_client: MagicMock,
        all_query_map: dict[str, list[dict]],
    ) -> None:
        """prev_genre=career のとき、career 以外で最高スコアのジャンルを選択する."""
        mock_neo4j_client.execute_query.side_effect = _make_side_effect(all_query_map)

        analyzer = GapAnalyzer(mock_neo4j_client)
        result = analyzer.analyze(prev_genre="career", genre_filter=None)

        # career にはダンピング0.7が適用されるため、spiritual(最少コンテンツ)が選ばれる
        assert result["genre"] == "spiritual"

    def test_正常系_prev_genreがNoneの場合最少コンテンツジャンルを選択(
        self,
        mock_neo4j_client: MagicMock,
        all_query_map: dict[str, list[dict]],
    ) -> None:
        """prev_genre=None のとき、ダンピングなしで最少コンテンツジャンルを選択する."""
        mock_neo4j_client.execute_query.side_effect = _make_side_effect(all_query_map)

        analyzer = GapAnalyzer(mock_neo4j_client)
        result = analyzer.analyze(prev_genre=None, genre_filter=None)

        # spiritual(content_count=2) -> score = 1/(2+1) = 0.333 (最高)
        assert result["genre"] == "spiritual"

    def test_正常系_prev_genreがspiritualの場合ダンピング適用でbeauty_romance選択(
        self,
        mock_neo4j_client: MagicMock,
        q3_low_coverage_data: list[dict],
        q4_low_coverage_concepts: list[dict],
        q5_existing_samples: list[dict],
        q6_serves_as_data: list[dict],
    ) -> None:
        """prev_genre=spiritual でコンテンツ数接近時にダンピングで逆転する.

        spiritual: 1/(3+1) * 0.7 = 0.175
        beauty-romance: 1/(4+1) = 0.200
        career: 1/(10+1) = 0.091
        """
        close_genre_data = [
            {"genre": "spiritual", "name": "占い・スピリチュアル", "content_count": 3},
            {"genre": "beauty-romance", "name": "美容・恋愛", "content_count": 4},
            {"genre": "career", "name": "転職・副業", "content_count": 10},
        ]
        query_map = {
            _Q1_KEY: close_genre_data,
            _Q2_KEY: [],
            _Q3_KEY: q3_low_coverage_data,
            _Q4_KEY: q4_low_coverage_concepts,
            _Q5_KEY: q5_existing_samples,
            _Q6_KEY: q6_serves_as_data,
        }
        mock_neo4j_client.execute_query.side_effect = _make_side_effect(query_map)

        analyzer = GapAnalyzer(mock_neo4j_client)
        result = analyzer.analyze(prev_genre="spiritual", genre_filter=None)

        assert result["genre"] == "beauty-romance"


# ---------------------------------------------------------------------------
# genre_filter
# ---------------------------------------------------------------------------
class TestGenreFilter:
    """genre_filter 指定時のテスト."""

    def test_正常系_genre_filterで指定ジャンルが強制される(
        self,
        mock_neo4j_client: MagicMock,
        q2_to_q6_map: dict[str, list[dict]],
    ) -> None:
        """genre_filter を指定すると Q1 をスキップし、そのジャンルが使われる."""
        mock_neo4j_client.execute_query.side_effect = _make_side_effect(q2_to_q6_map)

        analyzer = GapAnalyzer(mock_neo4j_client)
        result = analyzer.analyze(prev_genre="career", genre_filter="career")

        assert result["genre"] == "career"

    def test_正常系_genre_filter指定時Q1が呼ばれない(
        self,
        mock_neo4j_client: MagicMock,
        q2_to_q6_map: dict[str, list[dict]],
    ) -> None:
        """genre_filter 指定時は Q1(ジャンルローテーション)クエリが実行されない."""
        mock_neo4j_client.execute_query.side_effect = _make_side_effect(q2_to_q6_map)

        analyzer = GapAnalyzer(mock_neo4j_client)
        analyzer.analyze(prev_genre=None, genre_filter="beauty-romance")

        # 全ての呼び出しを確認し、Q1 に相当するクエリが含まれないことを検証
        for c in mock_neo4j_client.execute_query.call_args_list:
            query_arg = c[0][0] if c[0] else c[1].get("query", "")
            assert _Q1_KEY not in query_arg


# ---------------------------------------------------------------------------
# 低カバレッジ Concept 抽出
# ---------------------------------------------------------------------------
class TestLowCoverageConcepts:
    """低カバレッジ Concept 抽出のテスト."""

    def test_正常系_Q4の結果からconceptリストが構築される(
        self,
        mock_neo4j_client: MagicMock,
        all_query_map: dict[str, list[dict]],
    ) -> None:
        """Q4 のレスポンスから low_coverage_concepts が構築される."""
        mock_neo4j_client.execute_query.side_effect = _make_side_effect(all_query_map)

        analyzer = GapAnalyzer(mock_neo4j_client)
        result = analyzer.analyze(prev_genre=None, genre_filter=None)

        assert isinstance(result["low_coverage_concepts"], list)
        assert len(result["low_coverage_concepts"]) > 0
        concept_names = result["low_coverage_concepts"]
        assert "FOMO活用" in concept_names
        assert "PASONAの法則" in concept_names

    def test_正常系_Q4が空の場合low_coverage_conceptsは空リスト(
        self,
        mock_neo4j_client: MagicMock,
        all_query_map: dict[str, list[dict]],
    ) -> None:
        """Q4 が空レスポンスの場合は空リストになる."""
        empty_q4_map = {**all_query_map, _Q4_KEY: []}
        mock_neo4j_client.execute_query.side_effect = _make_side_effect(empty_q4_map)

        analyzer = GapAnalyzer(mock_neo4j_client)
        result = analyzer.analyze(prev_genre=None, genre_filter=None)

        assert result["low_coverage_concepts"] == []

    def test_正常系_Q4がgenre_idパラメータつきで呼ばれる(
        self,
        mock_neo4j_client: MagicMock,
        q2_to_q6_map: dict[str, list[dict]],
    ) -> None:
        """Bug 1 回帰テスト: Q4 は選択ジャンルの genre_id パラメータを受け取る.

        修正前は $genre_id が WHERE 句に含まれていなかったため、
        Q4 がジャンル非依存の全体カバレッジを返していた（beauty-romance 選択時に
        career 系 Concept が返る原因となった）。
        """
        captured_params: list[dict[str, Any] | None] = []

        def capturing_side_effect(
            query: str, params: dict[str, Any] | None = None
        ) -> list[dict[str, Any]]:
            if _Q4_KEY in query:
                captured_params.append(params)
            for key in _QUERY_KEYS:
                if key in query and key in q2_to_q6_map:
                    return q2_to_q6_map[key]
            return []

        mock_neo4j_client.execute_query.side_effect = capturing_side_effect

        analyzer = GapAnalyzer(mock_neo4j_client)
        analyzer.analyze(prev_genre=None, genre_filter="beauty-romance")

        # Q4 が1回呼ばれ、正しい genre_id が渡されていること
        assert len(captured_params) == 1
        assert captured_params[0] is not None
        assert captured_params[0].get("genre_id") == "beauty-romance"


# ---------------------------------------------------------------------------
# 既存サンプル抽出
# ---------------------------------------------------------------------------
class TestExistingSamples:
    """Q5 既存コンテンツサンプルのテスト."""

    def test_正常系_Q5の結果からexisting_samplesが構築される(
        self,
        mock_neo4j_client: MagicMock,
        all_query_map: dict[str, list[dict]],
    ) -> None:
        """Q5 のレスポンスから existing_samples が構築される."""
        mock_neo4j_client.execute_query.side_effect = _make_side_effect(all_query_map)

        analyzer = GapAnalyzer(mock_neo4j_client)
        result = analyzer.analyze(prev_genre=None, genre_filter=None)

        assert isinstance(result["existing_samples"], list)
        assert len(result["existing_samples"]) == 2
        assert "副業で月10万円を稼ぐための3つのステップ" in result["existing_samples"]


# ---------------------------------------------------------------------------
# Neo4j 接続エラーの PhaseError 変換
# ---------------------------------------------------------------------------
class TestNeo4jErrorHandling:
    """Neo4j 接続エラー時の PhaseError 変換テスト."""

    def test_異常系_Neo4j接続エラーがPhaseErrorに変換される(
        self,
        mock_neo4j_client: MagicMock,
    ) -> None:
        """Neo4j への接続エラーが PhaseError にラップされる."""
        mock_neo4j_client.execute_query.side_effect = ConnectionError(
            "Failed to connect to Neo4j"
        )

        analyzer = GapAnalyzer(mock_neo4j_client)

        with pytest.raises(PhaseError) as exc_info:
            analyzer.analyze(prev_genre=None, genre_filter=None)

        assert isinstance(exc_info.value.__cause__, ConnectionError)
        assert "Failed to connect to Neo4j" in str(exc_info.value)

    def test_異常系_OSErrorもPhaseErrorに変換される(
        self,
        mock_neo4j_client: MagicMock,
    ) -> None:
        """OSError(ネットワーク系)も PhaseError にラップされる."""
        mock_neo4j_client.execute_query.side_effect = OSError("Network unreachable")

        analyzer = GapAnalyzer(mock_neo4j_client)

        with pytest.raises(PhaseError) as exc_info:
            analyzer.analyze(prev_genre=None, genre_filter=None)

        assert isinstance(exc_info.value.__cause__, OSError)


# ---------------------------------------------------------------------------
# エッジケース: Q1 空リスト
# ---------------------------------------------------------------------------
class TestQ1EmptyFallback:
    """Q1 が空を返した場合のフォールバックテスト."""

    def test_エッジケース_Q1空リストでcareerにフォールバック(
        self,
        mock_neo4j_client: MagicMock,
    ) -> None:
        """Q1 が空リストを返した場合、デフォルトで 'career' が選択される."""
        mock_neo4j_client.execute_query.return_value = []

        analyzer = GapAnalyzer(mock_neo4j_client)
        result = analyzer.analyze(prev_genre=None, genre_filter=None)

        assert result["genre"] == "career"


# ---------------------------------------------------------------------------
# 並列実行
# ---------------------------------------------------------------------------
class TestParallelExecution:
    """Q2-Q6 並列実行のテスト."""

    def test_正常系_Q2からQ6まで全て呼ばれる(
        self,
        mock_neo4j_client: MagicMock,
        all_query_map: dict[str, list[dict]],
    ) -> None:
        """ジャンル確定後に Q2-Q6 が全て実行される."""
        queries_called: list[str] = []
        mock_neo4j_client.execute_query.side_effect = _make_tracking_side_effect(
            all_query_map, queries_called
        )

        analyzer = GapAnalyzer(mock_neo4j_client)
        analyzer.analyze(prev_genre=None, genre_filter=None)

        # 全6クエリが実行されたことを確認
        all_queries = " ".join(queries_called)
        assert _Q1_KEY in all_queries  # Q1
        assert _Q2_KEY in all_queries  # Q2
        assert _Q4_KEY in all_queries  # Q4
        assert _Q5_KEY in all_queries  # Q5
        assert _Q6_KEY in all_queries  # Q6

    @patch("creator_enrichment.phases.gap_analysis.ThreadPoolExecutor")
    def test_正常系_ThreadPoolExecutorが使用される(
        self,
        mock_executor_cls: MagicMock,
        mock_neo4j_client: MagicMock,
        q1_genre_data: list[dict],
        q3_low_coverage_data: list[dict],
        q4_low_coverage_concepts: list[dict],
        q5_existing_samples: list[dict],
        q6_serves_as_data: list[dict],
    ) -> None:
        """Q2-Q6 は ThreadPoolExecutor で並列実行される."""
        # ThreadPoolExecutor のモックをセットアップ
        mock_executor = MagicMock()
        mock_executor_cls.return_value.__enter__ = MagicMock(return_value=mock_executor)
        mock_executor_cls.return_value.__exit__ = MagicMock(return_value=False)

        # submit が返す Future のモック
        def make_future(result: list) -> MagicMock:
            future = MagicMock()
            future.result.return_value = result
            return future

        mock_executor.submit.side_effect = [
            make_future([]),  # Q2
            make_future(q3_low_coverage_data),  # Q3
            make_future(q4_low_coverage_concepts),  # Q4
            make_future(q5_existing_samples),  # Q5
            make_future(q6_serves_as_data),  # Q6
        ]

        # Q1 はシーケンシャルに実行される
        q1_map = {_Q1_KEY: q1_genre_data}
        mock_neo4j_client.execute_query.side_effect = _make_side_effect(q1_map)

        analyzer = GapAnalyzer(mock_neo4j_client)
        analyzer.analyze(prev_genre=None, genre_filter=None)

        # ThreadPoolExecutor(max_workers=5) で呼ばれたことを確認
        mock_executor_cls.assert_called_once_with(max_workers=5)
        # submit が5回呼ばれたことを確認（Q2-Q6）
        assert mock_executor.submit.call_count == 5


# ---------------------------------------------------------------------------
# GapAnalysisResult の型チェック
# ---------------------------------------------------------------------------
class TestGapAnalysisResultType:
    """返却型 GapAnalysisResult の構造テスト."""

    def test_正常系_返却値がGapAnalysisResultの構造を持つ(
        self,
        mock_neo4j_client: MagicMock,
        all_query_map: dict[str, list[dict]],
    ) -> None:
        """analyze() の返却値は genre, low_coverage_concepts, existing_samples を持つ."""
        mock_neo4j_client.execute_query.side_effect = _make_side_effect(all_query_map)

        analyzer = GapAnalyzer(mock_neo4j_client)
        result = analyzer.analyze(prev_genre=None, genre_filter=None)

        assert "genre" in result
        assert "low_coverage_concepts" in result
        assert "existing_samples" in result
        assert isinstance(result["genre"], str)
        assert isinstance(result["low_coverage_concepts"], list)
        assert isinstance(result["existing_samples"], list)
