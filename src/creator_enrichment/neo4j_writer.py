"""creator_enrichment Neo4j グラフ書き込みモジュール.

guide-v2.md の MERGE Cypher パターンを Python に移植した CreatorGraphWriter を提供する。
10 ノード + 11 リレーションを依存関係順（ノード先行 -> リレーション後）で
UNWIND バッチ MERGE する。

Usage
-----
::

    from creator_enrichment.neo4j_writer import CreatorGraphWriter

    writer = CreatorGraphWriter(driver)
    result = writer.ingest(queue_doc, cycle_id="cycle-20260323-140000")
    validation = writer.validate("cycle-20260323-140000")
"""

from __future__ import annotations

import logging
from typing import Any

from .types import IngestResult

logger = logging.getLogger(__name__)


class CreatorGraphWriter:
    """creator-neo4j への UNWIND バッチ MERGE を実行するライター.

    10 ノード種を依存関係順で MERGE した後、11 リレーション種を MERGE する。
    ドライバはダックタイプで ``driver.session()`` がコンテキストマネージャを返し、
    セッションに ``run(query, **params)`` メソッドがあればよい。

    Parameters
    ----------
    driver : Any
        neo4j.Driver 互換のドライバオブジェクト（ダックタイプ）

    Attributes
    ----------
    _driver : Any
        保持するドライバインスタンス
    """

    # ------------------------------------------------------------------
    # ノード定義: (label, key_field, has_cycle_id)
    # 依存関係順に並べる
    # ------------------------------------------------------------------
    _NODE_ORDER: list[tuple[str, str, bool]] = [
        ("Genre", "genre_id", False),
        ("ConceptCategory", "name", False),
        ("Concept", "concept_id", False),
        ("Entity", "entity_key", False),
        ("Source", "source_id", False),
        ("Domain", "name", False),
        ("Fact", "fact_id", True),
        ("Tip", "tip_id", True),
        ("Story", "story_id", True),
        ("Alias", "value", False),
    ]

    # ------------------------------------------------------------------
    # queue_doc キーとノード定義のマッピング
    # ------------------------------------------------------------------
    _NODE_KEY_MAP: dict[str, str] = {
        "Genre": "genres",
        "ConceptCategory": "concept_categories",
        "Concept": "concepts",
        "Entity": "entities",
        "Source": "sources",
        "Domain": "domains",
        "Fact": "facts",
        "Tip": "tips",
        "Story": "stories",
        "Alias": "aliases",
    }

    # ------------------------------------------------------------------
    # リレーション定義:
    # (rel_type, from_label, to_label, from_key, to_key, queue_key)
    # ------------------------------------------------------------------
    _REL_ORDER: list[tuple[str, str, str, str, str, str]] = [
        ("IS_A", "Concept", "ConceptCategory", "concept_id", "name", "is_a"),
        ("SERVES_AS", "Entity", "Concept", "entity_key", "concept_id", "serves_as"),
        ("ABOUT", "Fact", "Concept", "fact_id", "concept_id", "about_fact"),
        ("ABOUT", "Tip", "Concept", "tip_id", "concept_id", "about_tip"),
        ("ABOUT", "Story", "Concept", "story_id", "concept_id", "about_story"),
        ("MENTIONS", "Fact", "Entity", "fact_id", "entity_id", "mentions_fact"),
        ("MENTIONS", "Tip", "Entity", "tip_id", "entity_id", "mentions_tip"),
        ("MENTIONS", "Story", "Entity", "story_id", "entity_id", "mentions_story"),
        ("IN_GENRE", "Fact", "Genre", "fact_id", "genre_id", "in_genre_fact"),
        ("IN_GENRE", "Tip", "Genre", "tip_id", "genre_id", "in_genre_tip"),
        ("IN_GENRE", "Story", "Genre", "story_id", "genre_id", "in_genre_story"),
        ("FROM_SOURCE", "Fact", "Source", "fact_id", "source_id", "from_source_fact"),
        ("FROM_SOURCE", "Tip", "Source", "tip_id", "source_id", "from_source_tip"),
        ("FROM_SOURCE", "Story", "Source", "story_id", "source_id", "from_source_story"),
        ("FROM_DOMAIN", "Source", "Domain", "source_id", "name", "from_domain"),
        ("ALIAS_OF", "Alias", "Entity", "value", "entity_id", "alias_of"),
    ]

    def __init__(self, driver: Any) -> None:
        self._driver = driver
        logger.info("CreatorGraphWriter initialized")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def ingest(self, queue_doc: dict[str, Any], *, cycle_id: str) -> IngestResult:
        """queue_doc のノードとリレーションを Neo4j に MERGE する.

        ノードを依存関係順で先に MERGE し、その後リレーションを MERGE する。
        Fact / Tip / Story には cycle_id を SET する。

        Parameters
        ----------
        queue_doc : dict[str, Any]
            creator-2.0 形式の queue document
        cycle_id : str
            サイクル識別子（Fact/Tip/Story に SET）

        Returns
        -------
        IngestResult
            作成されたノード数とリレーション数
        """
        total_nodes = 0
        total_relations = 0

        # 全ノード種が空かチェック
        has_data = False
        for label, key_field, has_cycle_id in self._NODE_ORDER:
            queue_key = self._NODE_KEY_MAP[label]
            items = queue_doc.get(queue_key, [])
            if items:
                has_data = True
                break

        if not has_data:
            logger.info("Empty queue_doc, skipping ingest")
            return IngestResult(nodes_created=0, relations_created=0)

        with self._driver.session() as session:
            # Phase 1: ノード MERGE（依存関係順）
            logger.info(
                "Starting node MERGE phase: cycle_id=%s",
                cycle_id,
            )
            for label, key_field, has_cycle_id in self._NODE_ORDER:
                queue_key = self._NODE_KEY_MAP[label]
                items = queue_doc.get(queue_key, [])
                cid = cycle_id if has_cycle_id else None
                created = self._merge_nodes(
                    session, label, items, key_field, cycle_id=cid,
                )
                total_nodes += created
                if items:
                    logger.debug(
                        "Merged %s: %d items, %d created",
                        label,
                        len(items),
                        created,
                    )

            # Phase 2: リレーション MERGE（ノード MERGE 完了後）
            logger.info("Starting relationship MERGE phase")
            relations = queue_doc.get("relations", {})
            for rel_type, from_label, to_label, from_key, to_key, queue_key in self._REL_ORDER:
                items = relations.get(queue_key, [])
                created = self._merge_relations(
                    session,
                    rel_type=rel_type,
                    from_label=from_label,
                    to_label=to_label,
                    from_key=from_key,
                    to_key=to_key,
                    items=items,
                )
                total_relations += created
                if items:
                    logger.debug(
                        "Merged %s (%s->%s): %d items, %d created",
                        rel_type,
                        from_label,
                        to_label,
                        len(items),
                        created,
                    )

        logger.info(
            "Ingest completed: nodes_created=%d, relations_created=%d",
            total_nodes,
            total_relations,
        )
        return IngestResult(
            nodes_created=total_nodes,
            relations_created=total_relations,
        )

    def validate(self, cycle_id: str) -> dict[str, int]:
        """cycle_id でタグ付けされたノードのラベル別カウントを返す.

        Parameters
        ----------
        cycle_id : str
            検証対象のサイクル識別子

        Returns
        -------
        dict[str, int]
            ラベル名をキー、ノード数を値とする辞書
        """
        query = """
        MATCH (n) WHERE n.cycle_id = $cycle_id
        RETURN labels(n)[0] AS label, count(n) AS count
        """
        logger.info("Validating ingest: cycle_id=%s", cycle_id)

        with self._driver.session() as session:
            records = session.run(query, cycle_id=cycle_id)
            result: dict[str, int] = {}
            for record in records:
                result[record["label"]] = record["count"]

        logger.info("Validation result: %s", result)
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _merge_nodes(
        self,
        session: Any,
        label: str,
        items: list[dict[str, Any]],
        key_field: str,
        *,
        cycle_id: str | None = None,
    ) -> int:
        """UNWIND バッチでノードを MERGE する.

        Parameters
        ----------
        session : Any
            neo4j セッション
        label : str
            ノードラベル (e.g. "Genre", "Fact")
        items : list[dict[str, Any]]
            MERGE 対象のノードデータリスト
        key_field : str
            MERGE キーとなるフィールド名
        cycle_id : str | None
            cycle_id を SET する場合に指定

        Returns
        -------
        int
            作成されたノード数
        """
        if not items:
            return 0

        query = f"""
        UNWIND $items AS row
        MERGE (n:{label} {{{key_field}: row.{key_field}}})
        SET n += row
        """
        if cycle_id:
            query += ", n.cycle_id = $cycle_id"

        result = session.run(query, items=items, cycle_id=cycle_id)
        counters = result.consume().counters
        return counters.nodes_created

    def _merge_relations(
        self,
        session: Any,
        *,
        rel_type: str,
        from_label: str,
        to_label: str,
        from_key: str,
        to_key: str,
        items: list[dict[str, Any]],
    ) -> int:
        """UNWIND バッチでリレーションを MERGE する.

        Parameters
        ----------
        session : Any
            neo4j セッション
        rel_type : str
            リレーションタイプ (e.g. "IS_A", "ABOUT")
        from_label : str
            起点ノードラベル
        to_label : str
            終点ノードラベル
        from_key : str
            起点ノードの MATCH キーフィールド
        to_key : str
            終点ノードの MATCH キーフィールド
        items : list[dict[str, Any]]
            MERGE 対象のリレーションデータリスト

        Returns
        -------
        int
            作成されたリレーション数
        """
        if not items:
            return 0

        # ALIAS_OF は特殊なキー構造 (alias_value, target_id)
        if rel_type == "ALIAS_OF":
            query = f"""
            UNWIND $rels AS row
            MATCH (a:{from_label} {{{from_key}: row.alias_value}})
            MATCH (b:{to_label} {{{to_key}: row.target_id}})
            MERGE (a)-[:{rel_type}]->(b)
            """
        else:
            query = f"""
            UNWIND $rels AS row
            MATCH (a:{from_label} {{{from_key}: row.from_id}})
            MATCH (b:{to_label} {{{to_key}: row.to_id}})
            MERGE (a)-[:{rel_type}]->(b)
            """

        result = session.run(query, rels=items)
        counters = result.consume().counters
        return counters.relationships_created
