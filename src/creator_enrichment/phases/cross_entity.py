"""creator_enrichment Phase 4.5: CrossEntityEnricher.

3サイクルに1回実行され、共起候補クエリで Entity ペアを抽出し、
claude_agent_sdk 経由で最大 25 ペアを一括判定して SKIP 以外の
リレーションを MERGE する。

Usage
-----
::

    enricher = CrossEntityEnricher(neo4j_driver, llm_client=SdkLLMClient())
    added = enricher.run(cycle_count=3)
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from creator_enrichment.utils import strip_json_codeblock

if TYPE_CHECKING:
    from creator_enrichment.llm_client import LLMClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------
_MAX_PAIRS = 25
"""LLM に送信するペアの上限数."""

_ALLOWED_REL_DETAILS = frozenset(
    {
        "ENABLES",
        "USES",
        "COMPETES_WITH",
        "PART_OF",
        "MEASURES",
        "PRODUCES",
        "RELATED",
    }
)
"""LLM 判定で許可される rel_detail 値."""

# ---------------------------------------------------------------------------
# Cypher クエリ
# ---------------------------------------------------------------------------
_CO_OCCURRENCE_QUERY = """\
MATCH (e1:Entity)<-[:MENTIONS]-(c)-[:MENTIONS]->(e2:Entity)
WHERE e1.entity_key < e2.entity_key
  AND NOT (e1)-[:RELATES_TO]-(e2)
WITH e1, e2, count(DISTINCT c) AS co_occurrence
WHERE co_occurrence >= 2
RETURN e1.name AS from_name, e1.entity_type AS from_type, e1.entity_id AS from_id,
       e2.name AS to_name, e2.entity_type AS to_type, e2.entity_id AS to_id,
       co_occurrence
ORDER BY co_occurrence DESC
LIMIT 15
"""

_SAME_TYPE_QUERY = """\
MATCH (e1:Entity), (e2:Entity)
WHERE e1.entity_type = e2.entity_type
  AND e1.entity_type IN ['platform', 'technique', 'service']
  AND e1.entity_key < e2.entity_key
  AND NOT (e1)-[:RELATES_TO]-(e2)
WITH e1, e2
OPTIONAL MATCH (c1)-[:MENTIONS]->(e1) WHERE c1:Fact OR c1:Tip OR c1:Story
OPTIONAL MATCH (c2)-[:MENTIONS]->(e2) WHERE c2:Fact OR c2:Tip OR c2:Story
RETURN e1.name AS from_name, e1.entity_type AS from_type, e1.entity_id AS from_id,
       e2.name AS to_name, e2.entity_type AS to_type, e2.entity_id AS to_id,
       head(collect(DISTINCT c1.text)[..1]) AS from_context,
       head(collect(DISTINCT c2.text)[..1]) AS to_context
LIMIT 10
"""

_MERGE_QUERY = """\
UNWIND $rels AS row
MATCH (e1:Entity {entity_id: row.from_id})
MATCH (e2:Entity {entity_id: row.to_id})
MERGE (e1)-[r:RELATES_TO]->(e2)
SET r.rel_detail = row.rel_detail,
    r.source = 'cross-entity-enrichment',
    r.created_at = datetime()
"""

# ---------------------------------------------------------------------------
# LLM 判定プロンプト
# ---------------------------------------------------------------------------
_JUDGMENT_PROMPT = """\
以下の Entity ペアについて、意味的な関係があるか判定してください。
関係がある場合のみ、rel_detail を選択してください。

許可される rel_detail:
- ENABLES: AがBを可能にする
- USES: AがBを使用する
- COMPETES_WITH: AとBが競合する
- PART_OF: AがBの一部である
- MEASURES: AがBを測定する
- PRODUCES: AがBを生み出す
- RELATED: 上記に該当しないが関連がある

判定基準:
- 明確な関係がない場合は "SKIP" とする
- 無理にリレーションを作らない

## Entity ペア一覧

{pairs_text}

出力形式（JSON配列）:
[
  {{"from_id": "...", "to_id": "...", "rel_detail": "COMPETES_WITH"}},
  {{"from_id": "...", "to_id": "...", "rel_detail": "SKIP"}}
]
"""


# ---------------------------------------------------------------------------
# CrossEntityEnricher
# ---------------------------------------------------------------------------
class CrossEntityEnricher:
    """Entity ペアの意味的関係を LLM で判定し RELATES_TO を MERGE する.

    Neo4j の共起候補クエリと同一タイプクエリで Entity ペアを抽出し、
    claude_agent_sdk 経由で最大 25 ペアを一括判定する。
    SKIP 以外のリレーションのみ MERGE する。

    Parameters
    ----------
    neo4j_driver : Any
        neo4j.Driver 互換のドライバオブジェクト（ダックタイプ）
    llm_client : LLMClient
        ``query(prompt)`` メソッドを持つ LLM クライアント
    """

    def __init__(self, neo4j_driver: Any, llm_client: LLMClient) -> None:
        self._driver = neo4j_driver
        self._client = llm_client
        logger.info("CrossEntityEnricher initialized")

    def run(self, cycle_count: int) -> int:
        """Entity ペアを抽出・判定し、リレーションを MERGE する.

        Parameters
        ----------
        cycle_count : int
            現在のサイクル番号（ログ用）

        Returns
        -------
        int
            追加されたリレーション数
        """
        logger.info(
            "CrossEntityEnricher started: cycle_count=%d",
            cycle_count,
        )

        # Step 1 + 2: 共起候補 + 同一タイプ未接続ペアを同一セッションで取得
        with self._driver.session() as session:
            co_occurrence_candidates = [
                dict(record) for record in session.run(_CO_OCCURRENCE_QUERY)
            ]
            logger.info(
                "Co-occurrence candidates: %d pairs",
                len(co_occurrence_candidates),
            )

            same_type_candidates = [
                dict(record) for record in session.run(_SAME_TYPE_QUERY)
            ]
            logger.info(
                "Same-type candidates: %d pairs",
                len(same_type_candidates),
            )

        # Step 3: 候補の結合とトランケーション
        all_candidates = co_occurrence_candidates + same_type_candidates

        if not all_candidates:
            logger.info("No candidates found, skipping LLM judgment")
            return 0

        all_candidates = all_candidates[:_MAX_PAIRS]

        logger.info(
            "Combined candidates: %d pairs (max %d)",
            len(all_candidates),
            _MAX_PAIRS,
        )

        # ペア情報をテキストに変換
        pairs_text = self._format_pairs(all_candidates)

        # LLM 判定
        prompt = _JUDGMENT_PROMPT.format(pairs_text=pairs_text)

        logger.debug("Calling LLM for judgment: %d pairs", len(all_candidates))

        response_text = self._client.query(prompt)
        cleaned = strip_json_codeblock(response_text)

        try:
            judgments: list[dict[str, str]] = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response: %s", str(e))
            return 0

        # Step 4: SKIP をフィルタし、許可リスト外の rel_detail も除外して MERGE
        non_skip_rels = [
            j for j in judgments if j.get("rel_detail") in _ALLOWED_REL_DETAILS
        ]

        if not non_skip_rels:
            logger.info("All pairs judged as SKIP, no relations to MERGE")
            return 0

        logger.info(
            "MERGE targets: %d relations (filtered from %d judgments)",
            len(non_skip_rels),
            len(judgments),
        )

        with self._driver.session() as session:
            session.run(_MERGE_QUERY, rels=non_skip_rels)

        logger.info(
            "CrossEntityEnricher completed: %d relations added",
            len(non_skip_rels),
        )

        return len(non_skip_rels)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _format_pairs(candidates: list[dict[str, Any]]) -> str:
        """候補ペアを LLM プロンプト用のテキストに変換する.

        Parameters
        ----------
        candidates : list[dict[str, Any]]
            共起クエリ / 同一タイプクエリの結果レコード

        Returns
        -------
        str
            フォーマット済みのペアテキスト
        """
        lines: list[str] = []
        for i, c in enumerate(candidates, 1):
            co_occ = c.get("co_occurrence")
            from_ctx = c.get("from_context")
            to_ctx = c.get("to_context")

            line = (
                f"{i}. {c['from_name']} ({c['from_type']}, id={c['from_id']}) "
                f"↔ {c['to_name']} ({c['to_type']}, id={c['to_id']})"
            )

            if co_occ is not None:
                line += f" [共起: {co_occ}回]"
            if from_ctx:
                line += f"\n   from コンテキスト: {from_ctx}"
            if to_ctx:
                line += f"\n   to コンテキスト: {to_ctx}"

            lines.append(line)

        return "\n".join(lines)
