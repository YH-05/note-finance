"""session_memory Neo4j グラフ書き込みモジュール.

creator_enrichment.neo4j_writer の CreatorGraphWriter パターンを踏襲した
SessionGraphWriter を提供する。Session / SessionChunk ノードと
5 種リレーション（BELONGS_TO / NEXT / MENTIONS / DISCUSSES / DECIDED）を
UNWIND バッチ MERGE で冪等に投入する。

Usage
-----
::

    from session_memory.graph import SessionGraphWriter

    writer = SessionGraphWriter(driver)
    result = writer.ingest(queue_doc, session_id="sess-001")
    validation = writer.validate("sess-001")
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar, TypedDict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 戻り値の型
# ---------------------------------------------------------------------------


class IngestResult(TypedDict):
    """ingest() の戻り値型.

    Parameters
    ----------
    nodes_created : int
        作成されたノード数
    relations_created : int
        作成されたリレーション数
    """

    nodes_created: int
    relations_created: int


# ---------------------------------------------------------------------------
# SessionGraphWriter
# ---------------------------------------------------------------------------


class SessionGraphWriter:
    """note-neo4j への UNWIND バッチ MERGE を実行するライター.

    5 ノード種を依存関係順で MERGE した後、5 リレーション種を MERGE する。
    ドライバはダックタイプで ``driver.session()`` がコンテキストマネージャを返し、
    セッションに ``run(query, **params)`` メソッドがあればよい。

    ノード順序:
    1. Session（親ノード）
    2. SessionChunk（チャンクノード）
    3. Entity（言及されるエンティティ）
    4. Topic（議論されるトピック）
    5. Decision（決定事項）

    リレーション順序:
    1. BELONGS_TO: SessionChunk → Session
    2. NEXT: SessionChunk → SessionChunk
    3. MENTIONS: SessionChunk → Entity
    4. DISCUSSES: SessionChunk → Topic
    5. DECIDED: SessionChunk → Decision

    Parameters
    ----------
    driver : Any
        neo4j.Driver 互換のドライバオブジェクト（ダックタイプ）
    """

    # ------------------------------------------------------------------
    # ノード定義: (label, key_field, queue_key, has_session_id)
    # 依存関係順に並べる
    # ------------------------------------------------------------------
    _NODE_ORDER: ClassVar[list[tuple[str, str, str, bool]]] = [
        ("Session", "session_id", "sessions", True),
        ("SessionChunk", "chunk_key", "session_chunks", True),
        ("Entity", "entity_key", "entities", False),
        ("Topic", "name", "topics", False),
        ("Decision", "decision_id", "decisions", False),
    ]

    # ------------------------------------------------------------------
    # リレーション定義:
    # (rel_type, from_label, to_label, from_key, to_key, queue_key)
    # ------------------------------------------------------------------
    _REL_ORDER: ClassVar[list[tuple[str, str, str, str, str, str]]] = [
        (
            "BELONGS_TO",
            "SessionChunk",
            "Session",
            "chunk_key",
            "session_id",
            "belongs_to",
        ),
        (
            "NEXT",
            "SessionChunk",
            "SessionChunk",
            "chunk_key",
            "chunk_key",
            "next",
        ),
        (
            "MENTIONS",
            "SessionChunk",
            "Entity",
            "chunk_key",
            "entity_key",
            "mentions",
        ),
        (
            "DISCUSSES",
            "SessionChunk",
            "Topic",
            "chunk_key",
            "name",
            "discusses",
        ),
        (
            "DECIDED",
            "SessionChunk",
            "Decision",
            "chunk_key",
            "decision_id",
            "decided",
        ),
    ]

    # 許可リスト（Cypher インジェクション防止）
    _ALLOWED_LABELS: ClassVar[frozenset[str]] = frozenset(
        label
        for label, _, _, _ in _NODE_ORDER  # type: ignore[misc]
    )

    def __init__(self, driver: Any) -> None:
        self._driver = driver
        logger.info("SessionGraphWriter initialized")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest(
        self,
        queue_doc: dict[str, Any],
        *,
        session_id: str,
    ) -> IngestResult:
        """queue_doc のノードとリレーションを Neo4j に MERGE する.

        ノードを依存関係順で先に MERGE し、その後リレーションを MERGE する。
        Session / SessionChunk には session_id を SET する。

        Parameters
        ----------
        queue_doc : dict[str, Any]
            セッショングラフ形式の queue document
        session_id : str
            セッション識別子（Session/SessionChunk に SET）

        Returns
        -------
        IngestResult
            作成されたノード数とリレーション数
        """
        total_nodes = 0
        total_relations = 0

        # 全ノード種が空かチェック
        has_data = False
        for _label, _key_field, queue_key, _has_sid in self._NODE_ORDER:
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
                "Starting node MERGE phase: session_id=%s",
                session_id,
            )
            for label, key_field, queue_key, has_session_id in self._NODE_ORDER:
                items = queue_doc.get(queue_key, [])
                sid = session_id if has_session_id else None
                created = self._merge_nodes(
                    session,
                    label,
                    items,
                    key_field,
                    session_id=sid,
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
            for (
                rel_type,
                from_label,
                to_label,
                from_key,
                to_key,
                queue_key,
            ) in self._REL_ORDER:
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

    def validate(self, session_id: str) -> dict[str, int]:
        """session_id でタグ付けされたノードのラベル別カウントを返す.

        Parameters
        ----------
        session_id : str
            検証対象のセッション識別子

        Returns
        -------
        dict[str, int]
            ラベル名をキー、ノード数を値とする辞書
        """
        query = """
        MATCH (n) WHERE n.session_id = $session_id
        RETURN labels(n)[0] AS label, count(n) AS count
        """
        logger.info("Validating ingest: session_id=%s", session_id)

        with self._driver.session() as session:
            records = session.run(query, session_id=session_id)
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
        session_id: str | None = None,
    ) -> int:
        """UNWIND バッチでノードを MERGE する.

        Parameters
        ----------
        session : Any
            neo4j セッション
        label : str
            ノードラベル (e.g. "Session", "SessionChunk")
        items : list[dict[str, Any]]
            MERGE 対象のノードデータリスト
        key_field : str
            MERGE キーとなるフィールド名
        session_id : str | None
            session_id を SET する場合に指定

        Returns
        -------
        int
            作成されたノード数
        """
        if not items:
            return 0

        if label not in self._ALLOWED_LABELS:
            msg = f"Disallowed label: {label!r}"
            raise ValueError(msg)

        query = f"""
        UNWIND $items AS row
        MERGE (n:{label} {{{key_field}: row.{key_field}}})
        SET n += row
        """
        if session_id:
            query += ", n.session_id = $session_id"

        result = session.run(query, items=items, session_id=session_id)
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
            リレーションタイプ (e.g. "BELONGS_TO", "NEXT")
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

        query = f"""
        UNWIND $rels AS row
        MATCH (a:{from_label} {{{from_key}: row.from_id}})
        MATCH (b:{to_label} {{{to_key}: row.to_id}})
        MERGE (a)-[:{rel_type}]->(b)
        """

        result = session.run(query, rels=items)
        counters = result.consume().counters
        return counters.relationships_created


__all__ = [
    "IngestResult",
    "SessionGraphWriter",
]
