"""graph-queue JSON → Neo4j 直接投入.

neo4j Python ドライバーを使って graph-queue JSON のノードとリレーションを
MERGE ベースで冪等に投入する。

research-neo4j (7688): ingest_to_neo4j() — save-to-research-graph スキルの Python 版
creator-neo4j (7689): ingest_to_creator_neo4j() — CreatorGraphWriter アダプター
"""

from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING, Any

from neo4j import GraphDatabase

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_URI = "bolt://localhost:7688"
_DEFAULT_USER = "neo4j"
_DEFAULT_PASSWORD = "gomasuke"  # nosec B105 - ローカル開発用デフォルト

# ノードラベルとキープロパティのマッピング
_NODE_KEY_MAP = {
    "sources": ("Source", "source_id"),
    "facts": ("Fact", "fact_id"),
    "claims": ("Claim", "claim_id"),
    "entities": (
        "Entity",
        "entity_key",
    ),  # AIDEV-NOTE: entity_key (UNIQUE制約キー) で MERGE。entity_id は ON CREATE のみ設定
    "topics": (
        "Topic",
        "topic_key",
    ),  # AIDEV-NOTE: topic_key (UNIQUE制約キー) で MERGE。topic_id は ON CREATE のみ設定
    "chunks": ("Chunk", "chunk_id"),
    "financial_datapoints": ("FinancialDataPoint", "datapoint_id"),
    "fiscal_periods": ("FiscalPeriod", "period_id"),
    "authors": ("Author", "author_id"),
    "classification_nodes": None,  # 別処理
}

# AIDEV-NOTE: entity/topic は business key でMERGEするため id は ON CREATE のみ保存する
_NODE_ID_ON_CREATE: dict[str, str] = {
    "Entity": "entity_id",
    "Topic": "topic_id",
}

# リレーションの from/to キー名
# AIDEV-NOTE: entity/topic 参照は entity_key/topic_key で MATCH する（entity_id/topic_id はパイプライン間で異なる場合あり）
_REL_ENDPOINTS = {
    "source_fact": ("source_id", "Source", "fact_id", "Fact", "STATES_FACT"),
    "source_claim": ("source_id", "Source", "claim_id", "Claim", "MAKES_CLAIM"),
    # AIDEV-NOTE: extracted_from の宛先は chunks 有無で動的に切替（_resolve_rel_endpoints）
    "extracted_from_fact": ("fact_id", "Fact", "source_id", "Source", "EXTRACTED_FROM"),
    "extracted_from_claim": (
        "claim_id",
        "Claim",
        "source_id",
        "Source",
        "EXTRACTED_FROM",
    ),
    "fact_entity": ("fact_id", "Fact", "entity_key", "Entity", "RELATES_TO"),
    "claim_entity": ("claim_id", "Claim", "entity_key", "Entity", "ABOUT"),
    "tagged": ("source_id", "Source", "topic_key", "Topic", "TAGGED"),
    "tagged_fact": ("fact_id", "Fact", "topic_key", "Topic", "TAGGED"),
    "contains_chunk": ("source_id", "Source", "chunk_id", "Chunk", "CONTAINS_CHUNK"),
    "has_datapoint": (
        "entity_key",
        "Entity",
        "datapoint_id",
        "FinancialDataPoint",
        "HAS_DATAPOINT",
    ),
    "for_period": (
        "datapoint_id",
        "FinancialDataPoint",
        "period_id",
        "FiscalPeriod",
        "FOR_PERIOD",
    ),
    "datapoint_entity": (
        "datapoint_id",
        "FinancialDataPoint",
        "entity_key",
        "Entity",
        "ABOUT",
    ),
    "authored_by": ("source_id", "Source", "author_id", "Author", "AUTHORED_BY"),
}


def _resolve_rel_endpoints(queue_data: dict[str, Any]) -> dict[str, tuple]:
    """queue_data の chunks 有無で extracted_from の宛先を動的に決定する.

    chunks が存在する場合、extracted_from_fact/claim は Chunk を宛先にする。
    存在しない場合（web-research 等）は Source を宛先にする（デフォルト）。
    """
    endpoints = dict(_REL_ENDPOINTS)
    if queue_data.get("chunks"):
        endpoints["extracted_from_fact"] = (
            "fact_id",
            "Fact",
            "chunk_id",
            "Chunk",
            "EXTRACTED_FROM",
        )
        endpoints["extracted_from_claim"] = (
            "claim_id",
            "Claim",
            "chunk_id",
            "Chunk",
            "EXTRACTED_FROM",
        )
    return endpoints


def _get_driver():
    """Neo4j ドライバーを取得する."""
    uri = os.environ.get("NEO4J_RESEARCH_URI", _DEFAULT_URI)
    user = os.environ.get("NEO4J_RESEARCH_USER", _DEFAULT_USER)
    password = os.environ.get("NEO4J_RESEARCH_PASSWORD", _DEFAULT_PASSWORD)
    return GraphDatabase.driver(uri, auth=(user, password))


def _merge_node(tx, label: str, key_prop: str, props: dict[str, Any]) -> None:
    """MERGE ベースでノードを投入する.

    entity_key / topic_key でMERGEする場合、元の entity_id / topic_id は
    ON CREATE SET でのみ設定し、既存ノードの id を上書きしない。
    """
    key_val = props.get(key_prop)
    if not key_val:
        return
    # ON CREATE のみ保存すべき id フィールド（entity_id, topic_id）
    on_create_field = _NODE_ID_ON_CREATE.get(label)
    skip_keys = {key_prop, on_create_field}
    set_props = {k: v for k, v in props.items() if k not in skip_keys}
    set_clause = (
        ", ".join(f"n.{k} = ${k}" for k in set_props)
        if set_props
        else "n.updated = true"
    )
    on_create_clause = (
        f"ON CREATE SET n.{on_create_field} = ${on_create_field} "
        if on_create_field and on_create_field in props
        else ""
    )
    query = (
        f"MERGE (n:{label} {{{key_prop}: ${key_prop}}}) "
        f"{on_create_clause}"
        f"SET {set_clause}"
    )
    tx.run(query, **props)


def _merge_relation(
    tx,
    from_key: str,
    from_label: str,
    to_key: str,
    to_label: str,
    rel_type: str,
    rel: dict[str, Any],
    id_to_key: dict[str, str] | None = None,
) -> int:
    """MERGE ベースでリレーションを投入する.

    graph-queue v3.0 の from_id/to_id 形式と旧形式（ドメイン固有キー名）の両方に対応する。
    id_to_key が指定された場合、entity_id / topic_id を entity_key / topic_key に解決する。

    Returns
    -------
    int
        新規作成されたリレーション数（0 or 1）。MATCH 失敗時も 0。
    """
    # v3.0: from_id/to_id 形式を優先、フォールバックでドメイン固有キー名
    from_val = rel.get("from_id") or rel.get(from_key)
    to_val = rel.get("to_id") or rel.get(to_key)
    # entity_id / topic_id → entity_key / topic_key に解決
    if id_to_key:
        from_val = id_to_key.get(from_val, from_val) if from_val else from_val
        to_val = id_to_key.get(to_val, to_val) if to_val else to_val
    if not from_val or not to_val:
        return 0
    query = (
        f"MATCH (a:{from_label} {{{from_key}: $from_val}}) "
        f"MATCH (b:{to_label} {{{to_key}: $to_val}}) "
        f"MERGE (a)-[:{rel_type}]->(b)"
    )
    result = tx.run(query, from_val=from_val, to_val=to_val)
    summary = result.consume()
    return summary.counters.relationships_created


def load_graph_queue(queue_path: Path) -> dict[str, Any]:
    """graph-queue JSON を読み込む."""
    with queue_path.open(encoding="utf-8") as f:
        return json.load(f)


def ingest_to_neo4j(  # noqa: PLR0912, PLR0915
    queue_data: dict[str, Any],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """graph-queue データを Neo4j に投入する.

    Parameters
    ----------
    queue_data : dict
        graph-queue JSON のパース済みデータ。
    dry_run : bool
        True の場合は投入せずカウントのみ返す。

    Returns
    -------
    dict[str, Any]
        投入結果 {"nodes": int, "relations": int, "rel_verification": dict}。
    """
    node_count = 0
    rel_count = 0
    # chunks 有無で extracted_from の宛先を動的に決定
    rel_endpoints = _resolve_rel_endpoints(queue_data)

    driver = None if dry_run else _get_driver()
    try:
        # ノード投入
        for section, config in _NODE_KEY_MAP.items():
            if config is None:
                continue
            label, key_prop = config
            items = queue_data.get(section, [])
            if not items:
                continue
            logger.info("Ingesting %d %s nodes", len(items), label)
            if driver:
                with driver.session() as session:
                    for item in items:
                        session.execute_write(_merge_node, label, key_prop, item)
            node_count += len(items)

        # classification_nodes 投入（動的ラベル）
        for cnode in queue_data.get("classification_nodes", []):
            label = cnode.get("label")
            key_prop = cnode.get(
                "key_property", f"{label.lower()}_id" if label else "id"
            )
            if label and driver:
                with driver.session() as session:
                    session.execute_write(
                        _merge_node, label, key_prop, cnode.get("properties", cnode)
                    )
            node_count += 1

        # entity_id/topic_id → entity_key/topic_key の解決マップを構築
        # AIDEV-NOTE: graph-queue v3.0 では relations の to_id が entity_id (UUID) を指すが、
        # Neo4j では entity_key でMERGEするため、投入前に解決する。
        id_to_key: dict[str, str] = {}
        for entity in queue_data.get("entities", []):
            if entity.get("entity_id") and entity.get("entity_key"):
                id_to_key[entity["entity_id"]] = entity["entity_key"]
        for topic in queue_data.get("topics", []):
            if topic.get("topic_id") and topic.get("topic_key"):
                id_to_key[topic["topic_id"]] = topic["topic_key"]

        # リレーション投入
        rel_verification: dict[
            str, tuple[int, int]
        ] = {}  # {section: (expected, created)}
        relations = queue_data.get("relations", {})
        for rel_section, endpoints in rel_endpoints.items():
            rels = relations.get(rel_section, [])
            if not rels:
                continue
            from_key, from_label, to_key, to_label, rel_type = endpoints
            logger.info("Ingesting %d %s relations", len(rels), rel_section)
            section_created = 0
            if driver:
                with driver.session() as session:
                    for rel in rels:
                        section_created += session.execute_write(
                            _merge_relation,
                            from_key,
                            from_label,
                            to_key,
                            to_label,
                            rel_type,
                            rel,
                            id_to_key,
                        )
            expected = len(rels)
            rel_verification[rel_section] = (expected, section_created)
            if driver and section_created < expected:
                matched = expected - section_created
                logger.warning(
                    "Relation %s: attempted %d, created %d new, matched %d existing",
                    rel_section,
                    expected,
                    section_created,
                    matched,
                )
            rel_count += expected

        # classification_rels 投入
        # AIDEV-NOTE: classification_nodes の key_property/key_value マップを使って
        # to_label/to_key を正確に解決する。from_id は source_id として扱う。
        cn_keymap: dict[str, tuple[str, str]] = {}  # key_value → (label, key_property)
        for cnode in queue_data.get("classification_nodes", []):
            cn_label = cnode.get("label", "")
            cn_key_prop = cnode.get(
                "key_property", f"{cn_label.lower()}_id" if cn_label else "id"
            )
            cn_key_val = cnode.get("key_value", "")
            if cn_key_val and cn_label:
                cn_keymap[cn_key_val] = (cn_label, cn_key_prop)
        source_id_set = {s.get("source_id") for s in queue_data.get("sources", [])}

        for crel in queue_data.get("classification_rels", []):
            rel_type = crel.get("type", "CLASSIFIED_AS")
            from_id = crel.get("from_id")
            to_id = crel.get("to_id")
            # from_label/key: source_id ならば Source として扱う
            if from_id in source_id_set:
                from_label = "Source"
                from_key = "source_id"
            else:
                from_label = crel.get("from_label", "Entity")
                from_key = f"{from_label.lower()}_id"
            # to_label/key: classification_nodes のマップで解決
            if to_id in cn_keymap:
                to_label, to_key = cn_keymap[to_id]
            else:
                to_label = crel.get("to_label", "Classification")
                to_key = f"{to_label.lower()}_id"
            if from_id and to_id and driver:
                with driver.session() as session:
                    session.execute_write(
                        _merge_relation,
                        from_key,
                        from_label,
                        to_key,
                        to_label,
                        rel_type,
                        {from_key: from_id, to_key: to_id},
                    )
            rel_count += 1
    finally:
        if driver:
            driver.close()

    logger.info("Ingestion complete: %d nodes, %d relations", node_count, rel_count)
    return {
        "nodes": node_count,
        "relations": rel_count,
        "rel_verification": rel_verification,
    }


# ---------------------------------------------------------------------------
# creator-neo4j 投入
# ---------------------------------------------------------------------------

_CREATOR_DEFAULT_URI = "bolt://localhost:7689"

# creator-2.0 のノードセクション名一覧（dry-run カウント用）
_CREATOR_NODE_SECTIONS = [
    "genres",
    "concept_categories",
    "concepts",
    "entities",
    "sources",
    "domains",
    "facts",
    "tips",
    "stories",
    "aliases",
]

_CREATOR_REL_SECTIONS = [
    "is_a",
    "serves_as",
    "about_fact",
    "about_tip",
    "about_story",
    "from_source_fact",
    "from_source_tip",
    "from_source_story",
    "from_domain",
    "mentions_fact",
    "mentions_tip",
    "mentions_story",
    "in_genre_fact",
    "in_genre_tip",
    "in_genre_story",
    "concept_relations",
]


def _get_creator_driver():
    """creator-neo4j ドライバーを取得する."""
    uri = os.environ.get("NEO4J_CREATOR_URI", _CREATOR_DEFAULT_URI)
    user = os.environ.get("NEO4J_CREATOR_USER", _DEFAULT_USER)
    password = os.environ.get("NEO4J_CREATOR_PASSWORD", _DEFAULT_PASSWORD)
    return GraphDatabase.driver(uri, auth=(user, password))


def _count_creator_nodes_rels(queue_data: dict[str, Any]) -> dict[str, int]:
    """creator queue_data のノード/リレーション数をカウントする（dry-run用）."""
    node_count = sum(
        len(queue_data.get(section, [])) for section in _CREATOR_NODE_SECTIONS
    )
    relations = queue_data.get("relations", {})
    rel_count = sum(
        len(relations.get(section, [])) for section in _CREATOR_REL_SECTIONS
    )
    return {"nodes": node_count, "relations": rel_count}


def ingest_to_creator_neo4j(
    queue_data: dict[str, Any],
    *,
    dry_run: bool = False,
    cycle_id: str = "",
) -> dict[str, int]:
    """creator graph-queue データを creator-neo4j に投入する.

    CreatorGraphWriter（creator_enrichment/neo4j_writer.py）をアダプター経由で再利用。

    Parameters
    ----------
    queue_data : dict
        creator graph-queue JSON のパース済みデータ。
    dry_run : bool
        True の場合は投入せずカウントのみ返す。
    cycle_id : str
        サイクルID（検証用）。

    Returns
    -------
    dict[str, int]
        {"nodes": N, "relations": N}
    """
    if dry_run:
        counts = _count_creator_nodes_rels(queue_data)
        logger.info(
            "Creator dry-run: would ingest %d nodes, %d relations",
            counts["nodes"],
            counts["relations"],
        )
        return counts

    driver = _get_creator_driver()
    try:
        from creator_enrichment.neo4j_writer import CreatorGraphWriter

        writer = CreatorGraphWriter(driver)
        result = writer.ingest(queue_data, cycle_id=cycle_id)
        nodes = result["nodes_created"]
        rels = result["relations_created"]
        logger.info("Creator ingestion complete: %d nodes, %d relations", nodes, rels)
        return {"nodes": nodes, "relations": rels}
    finally:
        driver.close()
