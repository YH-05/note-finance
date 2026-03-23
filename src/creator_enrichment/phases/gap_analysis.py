"""creator_enrichment Phase 1: ギャップ分析.

Neo4j の creator-neo4j インスタンスに Q1-Q6 クエリを実行し、
対象ジャンルの低カバレッジ概念と既存サンプルを特定する。

Q1 でジャンルローテーションを行い、Q2-Q6 は
``concurrent.futures.ThreadPoolExecutor`` で並列実行する。

Usage
-----
::

    analyzer = GapAnalyzer(neo4j_client)
    result = analyzer.analyze(prev_genre="career", genre_filter=None)
    # result["genre"]  => "spiritual"
    # result["low_coverage_concepts"]  => ["FOMO活用", "PASONAの法則", ...]
    # result["existing_samples"]  => ["副業で月10万円...", ...]
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Protocol

from creator_enrichment.types import GapAnalysisResult, PhaseError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ダンピング係数
# ---------------------------------------------------------------------------
_SAME_GENRE_DAMPING = 0.7
"""同一ジャンル連続選択時のダンピング係数."""

_MAX_WORKERS = 5
"""Q2-Q6 並列実行時の最大ワーカー数."""

# ---------------------------------------------------------------------------
# Neo4j クライアントプロトコル（ダックタイピング）
# ---------------------------------------------------------------------------


class Neo4jClientProtocol(Protocol):
    """Neo4j クライアントのプロトコル.

    ``execute_query(query, params)`` メソッドを持つ任意のオブジェクト。
    """

    def execute_query(
        self, query: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]: ...


# ---------------------------------------------------------------------------
# Cypher クエリ定義
# ---------------------------------------------------------------------------
_Q1_GENRE_ROTATION = """\
MATCH (g:Genre)
OPTIONAL MATCH (content)-[:IN_GENRE]->(g) WHERE content:Fact OR content:Tip OR content:Story
RETURN g.genre_id AS genre, g.name AS name, count(DISTINCT content) AS content_count
ORDER BY content_count ASC
"""

_Q2_CATEGORY_COVERAGE = """\
MATCH (cc:ConceptCategory)
OPTIONAL MATCH (content)-[:ABOUT]->(concept:Concept)-[:IS_A]->(cc)
WHERE content:Fact OR content:Tip OR content:Story
OPTIONAL MATCH (content)-[:IN_GENRE]->(g:Genre)
WITH cc.name AS category, cc.layer AS layer,
     g.genre_id AS genre, count(DISTINCT content) AS contents
RETURN category, layer, genre, contents
ORDER BY layer, category, genre
"""

_Q3_LOW_COVERAGE_CATEGORIES = """\
MATCH (cc:ConceptCategory)
OPTIONAL MATCH (concept:Concept)-[:IS_A]->(cc)
OPTIONAL MATCH (content)-[:ABOUT]->(concept) WHERE content:Fact OR content:Tip OR content:Story
WITH cc.name AS category, cc.name_ja AS name_ja, cc.layer AS layer,
     count(DISTINCT concept) AS concept_count, count(DISTINCT content) AS content_count
RETURN category, name_ja, layer, concept_count, content_count
ORDER BY content_count ASC
LIMIT 5
"""

_Q4_LOW_COVERAGE_CONCEPTS = """\
MATCH (concept:Concept)-[:IS_A]->(cc:ConceptCategory)
OPTIONAL MATCH (content)-[:ABOUT]->(concept)
WHERE (content:Fact OR content:Tip OR content:Story)
OPTIONAL MATCH (content)-[:IN_GENRE]->(g:Genre {genre_id: $genre_id})
WITH concept.name AS name, cc.name AS category,
     count(DISTINCT content) AS content_count
RETURN name, category, content_count
ORDER BY content_count ASC
LIMIT 10
"""

_Q5_EXISTING_SAMPLES = """\
MATCH (c)
WHERE (c:Fact OR c:Tip OR c:Story) AND c.created_at >= datetime() - duration('P7D')
OPTIONAL MATCH (c)-[:FROM_SOURCE]->(s:Source)
RETURN c.text AS text, s.url AS source_url,
       labels(c)[0] AS content_type
ORDER BY c.created_at DESC
LIMIT 50
"""

_Q6_SERVES_AS_RATE = """\
MATCH (e:Entity)
OPTIONAL MATCH (e)-[:SERVES_AS]->()
WITH e, count(*) > 0 AS has_serves_as
RETURN count(e) AS total,
       sum(CASE WHEN has_serves_as THEN 1 ELSE 0 END) AS with_role,
       sum(CASE WHEN NOT has_serves_as THEN 1 ELSE 0 END) AS without_role
"""


# ---------------------------------------------------------------------------
# GapAnalyzer
# ---------------------------------------------------------------------------
class GapAnalyzer:
    """Neo4j ギャップ分析を実行する.

    Parameters
    ----------
    neo4j_client
        ``execute_query(query, params)`` メソッドを持つ Neo4j クライアント。
        ダックタイピングでモック注入可能。
    """

    def __init__(self, neo4j_client: Neo4jClientProtocol) -> None:
        self._client = neo4j_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def analyze(
        self,
        prev_genre: str | None,
        genre_filter: str | None,
    ) -> GapAnalysisResult:
        """ギャップ分析を実行し、対象ジャンルと低カバレッジ概念を返す.

        Parameters
        ----------
        prev_genre : str | None
            直前サイクルのジャンル（ダンピング適用対象）。
            None の場合はダンピングなし。
        genre_filter : str | None
            指定されている場合はローテーションをスキップし、
            このジャンルを強制的に使用する。

        Returns
        -------
        GapAnalysisResult
            genre, low_coverage_concepts, existing_samples を含む辞書。

        Raises
        ------
        PhaseError
            Neo4j 接続エラーが発生した場合。
        """
        try:
            return self._execute_analysis(prev_genre, genre_filter)
        except (ConnectionError, OSError) as e:
            logger.error("Neo4j connection error: %s", e)
            raise PhaseError(f"Neo4j connection error: {e}") from e

    # ------------------------------------------------------------------
    # Private: 分析実行
    # ------------------------------------------------------------------
    def _execute_analysis(
        self,
        prev_genre: str | None,
        genre_filter: str | None,
    ) -> GapAnalysisResult:
        """分析のメインロジック.

        genre_filter が指定されていれば Q1 をスキップ。
        ジャンル確定後、Q2-Q6 を ThreadPoolExecutor で並列実行する。
        """
        # --- Phase 1a: ジャンル決定 ---
        if genre_filter is not None:
            genre = genre_filter
            logger.info("Genre forced by filter: %s", genre)
        else:
            genre = self._select_genre(prev_genre)
            logger.info("Genre selected by rotation: %s (prev=%s)", genre, prev_genre)

        # --- Phase 1b: Q2-Q6 並列実行 ---
        q2_result, q3_result, q4_result, q5_result, q6_result = (
            self._run_parallel_queries(genre)
        )

        logger.debug(
            "Parallel query results: Q2=%d, Q3=%d, Q4=%d, Q5=%d, Q6=%d rows",
            len(q2_result),
            len(q3_result),
            len(q4_result),
            len(q5_result),
            len(q6_result),
        )

        # --- 結果構築 ---
        low_coverage_concepts = [row["name"] for row in q4_result if "name" in row]
        existing_samples = [row["text"] for row in q5_result if "text" in row]

        result = GapAnalysisResult(
            genre=genre,
            low_coverage_concepts=low_coverage_concepts,
            existing_samples=existing_samples,
        )
        logger.info(
            "Gap analysis complete: genre=%s, concepts=%d, samples=%d",
            result["genre"],
            len(result["low_coverage_concepts"]),
            len(result["existing_samples"]),
        )
        return result

    # ------------------------------------------------------------------
    # Private: ジャンルローテーション (Q1)
    # ------------------------------------------------------------------
    def _select_genre(self, prev_genre: str | None) -> str:
        """Q1 結果に基づきジャンルを選択する.

        priority_score = 1.0 / (content_count + 1)
        prev_genre と同じジャンルには _SAME_GENRE_DAMPING を乗算。
        最高スコアのジャンルを返す。

        Parameters
        ----------
        prev_genre : str | None
            直前サイクルのジャンル

        Returns
        -------
        str
            選択されたジャンル ID
        """
        q1_data = self._client.execute_query(_Q1_GENRE_ROTATION)
        logger.debug("Q1 genre data: %s", q1_data)

        if not q1_data:
            logger.warning("Q1 returned empty results, defaulting to 'career'")
            return "career"

        best_genre = q1_data[0].get("genre", "career")
        best_score = 0.0

        for row in q1_data:
            genre_id = row.get("genre", "")
            content_count = row.get("content_count", 0)
            score = 1.0 / (content_count + 1)

            if genre_id == prev_genre:
                score *= _SAME_GENRE_DAMPING

            logger.debug(
                "Genre %s: content_count=%d, score=%.4f (damped=%s)",
                genre_id,
                content_count,
                score,
                genre_id == prev_genre,
            )

            if score > best_score:
                best_score = score
                best_genre = genre_id

        return best_genre

    # ------------------------------------------------------------------
    # Private: Q2-Q6 並列実行
    # ------------------------------------------------------------------
    def _run_parallel_queries(
        self, genre: str
    ) -> tuple[
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
    ]:
        """Q2-Q6 を ThreadPoolExecutor で並列実行する.

        Parameters
        ----------
        genre : str
            選択されたジャンル ID（Q4 のパラメータに使用）

        Returns
        -------
        tuple
            (q2_result, q3_result, q4_result, q5_result, q6_result)
        """
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
            f_q2 = executor.submit(self._client.execute_query, _Q2_CATEGORY_COVERAGE)
            f_q3 = executor.submit(
                self._client.execute_query, _Q3_LOW_COVERAGE_CATEGORIES
            )
            f_q4 = executor.submit(
                self._client.execute_query,
                _Q4_LOW_COVERAGE_CONCEPTS,
                {"genre_id": genre},
            )
            f_q5 = executor.submit(self._client.execute_query, _Q5_EXISTING_SAMPLES)
            f_q6 = executor.submit(self._client.execute_query, _Q6_SERVES_AS_RATE)

            return (
                f_q2.result(),
                f_q3.result(),
                f_q4.result(),
                f_q5.result(),
                f_q6.result(),
            )
