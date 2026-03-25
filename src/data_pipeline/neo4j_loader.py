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
_DEFAULT_PASSWORD = "gomasuke"

# ノードラベルとキープロパティのマッピング
_NODE_KEY_MAP = {
    "sources": ("Source", "source_id"),
    "facts": ("Fact", "fact_id"),
    "claims": ("Claim", "claim_id"),
    "entities": ("Entity", "entity_id"),
    "topics": ("Topic", "topic_id"),
    "chunks": ("Chunk", "chunk_id"),
    "financial_datapoints": ("FinancialDataPoint", "datapoint_id"),
    "fiscal_periods": ("FiscalPeriod", "period_id"),
    "authors": ("Author", "author_id"),
    "classification_nodes": None,  # 別処理
}

# リレーションの from/to キー名
_REL_ENDPOINTS = {
    "source_fact": ("source_id", "Source", "fact_id", "Fact", "PROVIDES"),
    "source_claim": ("source_id", "Source", "claim_id", "Claim", "PROVIDES"),
    "extracted_from_fact": ("fact_id", "Fact", "source_id", "Source", "EXTRACTED_FROM"),
    "extracted_from_claim": (
        "claim_id",
        "Claim",
        "source_id",
        "Source",
        "EXTRACTED_FROM",
    ),
    "fact_entity": ("fact_id", "Fact", "entity_id", "Entity", "RELATES_TO"),
    "claim_entity": ("claim_id", "Claim", "entity_id", "Entity", "ABOUT"),
    "tagged": ("source_id", "Source", "topic_id", "Topic", "TAGGED"),
    "contains_chunk": ("source_id", "Source", "chunk_id", "Chunk", "CONTAINS_CHUNK"),
    "has_datapoint": (
        "entity_id",
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
        "entity_id",
        "Entity",
        "ABOUT",
    ),
    "authored_by": ("source_id", "Source", "author_id", "Author", "AUTHORED_BY"),
}


def _get_driver():
    """Neo4j ドライバーを取得する."""
    uri = os.environ.get("NEO4J_RESEARCH_URI", _DEFAULT_URI)
    user = os.environ.get("NEO4J_RESEARCH_USER", _DEFAULT_USER)
    password = os.environ.get("NEO4J_RESEARCH_PASSWORD", _DEFAULT_PASSWORD)
    return GraphDatabase.driver(uri, auth=(user, password))


def _merge_node(tx, label: str, key_prop: str, props: dict[str, Any]) -> None:
    """MERGE ベースでノードを投入する."""
    key_val = props.get(key_prop)
    if not key_val:
        return
    set_clause = ", ".join(f"n.{k} = ${k}" for k in props if k != key_prop)
    query = f"MERGE (n:{label} {{{key_prop}: ${key_prop}}}) SET {set_clause}"
    tx.run(query, **props)


def _merge_relation(
    tx,
    from_key: str,
    from_label: str,
    to_key: str,
    to_label: str,
    rel_type: str,
    rel: dict[str, Any],
) -> None:
    """MERGE ベースでリレーションを投入する."""
    from_val = rel.get(from_key)
    to_val = rel.get(to_key)
    if not from_val or not to_val:
        return
    query = (
        f"MATCH (a:{from_label} {{{from_key}: $from_val}}) "
        f"MATCH (b:{to_label} {{{to_key}: $to_val}}) "
        f"MERGE (a)-[:{rel_type}]->(b)"
    )
    tx.run(query, from_val=from_val, to_val=to_val)


def load_graph_queue(queue_path: Path) -> dict[str, Any]:
    """graph-queue JSON を読み込む."""
    with queue_path.open(encoding="utf-8") as f:
        return json.load(f)


def ingest_to_neo4j(  # noqa: PLR0912
    queue_data: dict[str, Any],
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    """graph-queue データを Neo4j に投入する.

    Parameters
    ----------
    queue_data : dict
        graph-queue JSON のパース済みデータ。
    dry_run : bool
        True の場合は投入せずカウントのみ返す。

    Returns
    -------
    dict[str, int]
        投入結果 {"nodes": N, "relations": N}。
    """
    node_count = 0
    rel_count = 0

    # ノード投入
    for section, config in _NODE_KEY_MAP.items():
        if config is None:
            continue
        label, key_prop = config
        items = queue_data.get(section, [])
        if not items:
            continue
        logger.info("Ingesting %d %s nodes", len(items), label)
        if not dry_run:
            driver = _get_driver()
            with driver.session() as session:
                for item in items:
                    session.execute_write(_merge_node, label, key_prop, item)
            driver.close()
        node_count += len(items)

    # classification_nodes 投入（動的ラベル）
    for cnode in queue_data.get("classification_nodes", []):
        label = cnode.get("label")
        key_prop = cnode.get("key_property", f"{label.lower()}_id" if label else "id")
        if label and not dry_run:
            driver = _get_driver()
            with driver.session() as session:
                session.execute_write(
                    _merge_node, label, key_prop, cnode.get("properties", cnode)
                )
            driver.close()
        node_count += 1

    # リレーション投入
    relations = queue_data.get("relations", {})
    for rel_section, endpoints in _REL_ENDPOINTS.items():
        rels = relations.get(rel_section, [])
        if not rels:
            continue
        from_key, from_label, to_key, to_label, rel_type = endpoints
        logger.info("Ingesting %d %s relations", len(rels), rel_section)
        if not dry_run:
            driver = _get_driver()
            with driver.session() as session:
                for rel in rels:
                    session.execute_write(
                        _merge_relation,
                        from_key,
                        from_label,
                        to_key,
                        to_label,
                        rel_type,
                        rel,
                    )
            driver.close()
        rel_count += len(rels)

    # classification_rels 投入
    for crel in queue_data.get("classification_rels", []):
        rel_type = crel.get("type", "CLASSIFIED_AS")
        from_id = crel.get("from_id")
        to_id = crel.get("to_id")
        from_label = crel.get("from_label", "Entity")
        to_label = crel.get("to_label", "Classification")
        if from_id and to_id and not dry_run:
            driver = _get_driver()
            with driver.session() as session:
                session.execute_write(
                    _merge_relation,
                    f"{from_label.lower()}_id",
                    from_label,
                    f"{to_label.lower()}_id",
                    to_label,
                    rel_type,
                    {
                        f"{from_label.lower()}_id": from_id,
                        f"{to_label.lower()}_id": to_id,
                    },
                )
            driver.close()
        rel_count += 1

    logger.info("Ingestion complete: %d nodes, %d relations", node_count, rel_count)
    return {"nodes": node_count, "relations": rel_count}


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
