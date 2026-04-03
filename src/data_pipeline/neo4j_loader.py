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
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from neo4j import Driver, GraphDatabase

# Ensure scripts/ is on the import path for ontology_loader
_SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent.parent / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from ontology_loader import ENTITY_TYPE_TO_LABEL as _ENTITY_TYPE_TO_LABEL  # noqa: E402
from ontology_loader import load_constraints as _ol_load_constraints  # noqa: E402
from ontology_loader import load_indices as _ol_load_indices  # noqa: E402

logger = logging.getLogger(__name__)

# SEC-005: Cypher ラベル/プロパティ名インジェクション対策
# ラベルおよびキープロパティ名は英数字とアンダースコアのみ許可する
_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def _is_safe_identifier(name: str) -> bool:
    """Cypher ラベル/プロパティ名として安全な識別子かどうかを検証する.

    Returns True if name consists only of ASCII letters, digits, and underscores,
    and starts with a letter (preventing Cypher injection via classification_nodes).
    """
    return bool(_SAFE_IDENTIFIER_RE.match(name))


_DEFAULT_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
_DEFAULT_USER = "neo4j"
_DEFAULT_PASSWORD = "gomasuke"  # nosec B105 - ローカル開発用デフォルト（本番環境では NEO4J_RESEARCH_PASSWORD/NEO4J_CREATOR_PASSWORD を必ず設定すること）

# Enterprise multi-database: database名で分離
_RESEARCH_DB = os.environ.get("NEO4J_RESEARCH_DB", "research")
_CREATOR_DB = os.environ.get("NEO4J_CREATOR_DB", "creator")

# ノードラベルとキープロパティのマッピング
# AIDEV-NOTE: v4.0 (Issue #310) — Entity ラベル廃止。entities セクションは neo4j_label ごとに動的処理
_NODE_KEY_MAP = {
    "sources": ("Source", "source_id"),
    "facts": ("Fact", "fact_id"),
    "claims": ("Claim", "claim_id"),
    "entities": None,  # v4.0: 個別ラベル動的処理 (_ingest_entity_nodes)
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

# AIDEV-NOTE: topic は business key でMERGEするため id は ON CREATE のみ保存する
# Entity は v4.0 で個別ラベルに分解済み (entity_id → ON CREATE も廃止)
_NODE_ID_ON_CREATE: dict[str, str] = {
    "Topic": "topic_id",
}

# リレーションの from/to キー名
# AIDEV-NOTE: v4.0 — entity 参照は name+label で MATCH する（entity_key 廃止）
# fact_entity / claim_entity / has_datapoint / datapoint_entity は _ingest_entity_rels で処理
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
    # fact_entity / claim_entity は entity_key 廃止により _ingest_entity_rels で処理
    # "fact_entity": 廃止 (entity_key 参照のため)
    # "claim_entity": 廃止 (entity_key 参照のため)
    "tagged": ("source_id", "Source", "topic_key", "Topic", "TAGGED"),
    "tagged_fact": ("fact_id", "Fact", "topic_key", "Topic", "TAGGED"),
    "contains_chunk": ("source_id", "Source", "chunk_id", "Chunk", "CONTAINS_CHUNK"),
    # has_datapoint / datapoint_entity は _ingest_entity_rels で処理
    "for_period": (
        "datapoint_id",
        "FinancialDataPoint",
        "period_id",
        "FiscalPeriod",
        "FOR_PERIOD",
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


def _get_driver() -> Driver:
    """research database 用ドライバーを取得する."""
    uri = os.environ.get("NEO4J_RESEARCH_URI", _DEFAULT_URI)
    user = os.environ.get("NEO4J_RESEARCH_USER", _DEFAULT_USER)
    password = os.environ.get("NEO4J_RESEARCH_PASSWORD", _DEFAULT_PASSWORD)
    return GraphDatabase.driver(uri, auth=(user, password))


def _check_apoc_available(driver) -> bool:
    """APOC が利用可能かどうかを確認する.

    Returns
    -------
    bool
        APOC apoc.merge.node が利用可能なら True。
    """
    try:
        with driver.session(database=_RESEARCH_DB) as session:
            result = session.run(
                "CALL apoc.help('merge.node') YIELD name RETURN name LIMIT 1"
            )
            return result.single() is not None
    except Exception:
        logger.debug("APOC not available, using fallback multi-label strategy")
        return False


def _merge_node(
    tx,
    label: str,
    key_prop: str,
    props: dict[str, Any],
    extra_labels: list[str] | None = None,
) -> None:
    """MERGE ベースでノードを投入する.

    entity_key / topic_key でMERGEする場合、元の entity_id / topic_id は
    ON CREATE SET でのみ設定し、既存ノードの id を上書きしない。

    Parameters
    ----------
    tx : neo4j.Transaction
        Neo4j トランザクション。
    label : str
        ノードのプライマリラベル。
    key_prop : str
        MERGE に使用するキープロパティ名。
    props : dict
        ノードプロパティ。
    extra_labels : list[str] | None
        追加するマルチラベル（例: ["Company"]）。None または [] の場合は追加なし。
        AIDEV-NOTE: extra_labels が渡された場合はここで SET n:ExtraLabel を実行する。
        APOC を使った一発投入は _ingest_multilabel が担当する。
    """
    key_val = props.get(key_prop)
    if not key_val:
        return
    # ON CREATE のみ保存すべき id フィールド（entity_id, topic_id）
    on_create_field = _NODE_ID_ON_CREATE.get(label)
    skip_keys = {key_prop, on_create_field}
    set_props = {
        k: v for k, v in props.items() if k not in skip_keys and k != "extra_labels"
    }
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
    filtered_props = {k: v for k, v in props.items() if k != "extra_labels"}
    tx.run(query, **filtered_props)

    # extra_labels が直接渡された場合のフォールバック処理（SET n:ExtraLabel）
    if extra_labels:
        for extra_label in extra_labels:
            label_query = (
                f"MATCH (n:{label} {{{key_prop}: ${key_prop}}}) SET n:{extra_label}"
            )
            tx.run(label_query, **{key_prop: key_val})


def _ingest_multilabel(
    session,
    label: str,
    key_prop: str,
    key_val: str,
    extra_labels: list[str],
    *,
    apoc_available: bool = True,
) -> None:
    """マルチラベルを投入するサブ関数.

    APOC が利用可能な場合は `apoc.merge.node` を使用して一発投入する。
    APOC 不在の場合は `MATCH (n:Label) SET n:ExtraLabel` の2クエリ分割でフォールバック。

    Parameters
    ----------
    session : neo4j.Session
        Neo4j セッション。
    label : str
        ノードのプライマリラベル。
    key_prop : str
        ノードの UNIQUE キープロパティ名。
    key_val : str
        キープロパティの値。
    extra_labels : list[str]
        追加するラベル一覧（例: ["Company", "Technology"]）。
    apoc_available : bool
        APOC が利用可能かどうか。
    """
    if not extra_labels:
        return

    if apoc_available:
        # APOC: apoc.merge.node([label, *extra_labels], {key: val}, {}) YIELD node
        all_labels = [label, *extra_labels]
        query = (
            f"CALL apoc.merge.node({all_labels!r}, {{{key_prop}: $key_val}}, {{}}) "
            f"YIELD node RETURN node"
        )
        session.run(query, key_val=key_val)
    else:
        # フォールバック: MATCH でノードを取得し SET でラベルを付与
        for extra_label in extra_labels:
            query = f"MATCH (n:{label} {{{key_prop}: $key_val}}) SET n:{extra_label}"
            session.run(query, key_val=key_val)


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


def _get_entity_neo4j_label(entity: dict[str, Any]) -> str:
    """entity dict から Neo4j 個別ラベルを取得する.

    v4.0: Entity 汎用ラベル廃止。neo4j_label フィールドまたは entity_type から決定。
    SSoT: ontology_loader.ENTITY_TYPE_TO_LABEL

    Parameters
    ----------
    entity : dict[str, Any]
        エンティティ dict（neo4j_label または entity_type フィールドを含む）。

    Returns
    -------
    str
        Neo4j 個別ラベル (e.g. "Company", "MarketIndex")。
    """
    # 明示的な neo4j_label フィールドを優先
    neo4j_label = entity.get("neo4j_label")
    if neo4j_label and _is_safe_identifier(neo4j_label):
        return neo4j_label

    # entity_type から ENTITY_TYPE_TO_LABEL でマッピング
    entity_type: str = str(entity.get("entity_type", "concept")).lower().strip()
    # 統合マッピング（fine-grained → canonical）
    from ontology_loader import load_consolidation_mapping as _load_cm

    consolidation = _load_cm()
    canonical_type: str = consolidation.get(entity_type, entity_type)
    label = _ENTITY_TYPE_TO_LABEL.get(canonical_type, "Concept")
    return label


def _build_id_to_key(queue_data: dict[str, Any]) -> dict[str, str]:
    """topic_id → topic_key の解決マップを構築する.

    v4.0 変更: entity_key 廃止のため Entity の解決マップは除去。
    Topic の topic_id → topic_key の解決のみ行う。

    AIDEV-NOTE: graph-queue の relations の to_id が topic_id (UUID) を指す場合、
    Neo4j では topic_key で MERGE するため、投入前に解決する。
    """
    id_to_key: dict[str, str] = {}
    # v4.0: Entity の entity_id → entity_key マッピングは廃止
    for topic in queue_data.get("topics", []):
        if topic.get("topic_id") and topic.get("topic_key"):
            id_to_key[topic["topic_id"]] = topic["topic_key"]
    return id_to_key


def _ingest_entity_nodes(
    queue_data: dict[str, Any],
    driver,
) -> int:
    """entities セクションを個別ラベルで MERGE 投入するサブ関数.

    v4.0: Entity 汎用ラベル廃止。neo4j_label または entity_type から個別ラベルを決定し、
    ラベルごとに UNWIND バッチで MERGE (n:Label {name: $name}) を実行する。

    Parameters
    ----------
    queue_data : dict
        graph-queue JSON のパース済みデータ。
    driver : neo4j.Driver | None
        Neo4j ドライバー。None の場合は dry_run（カウントのみ）。

    Returns
    -------
    int
        投入したエンティティ数。
    """
    entities = queue_data.get("entities", [])
    if not entities:
        return 0

    # ラベルごとにグループ化
    label_to_items: dict[str, list[dict[str, Any]]] = {}
    for entity in entities:
        neo4j_label = _get_entity_neo4j_label(entity)
        label_to_items.setdefault(neo4j_label, []).append(entity)

    count = 0
    for neo4j_label, items in label_to_items.items():
        if not _is_safe_identifier(neo4j_label):
            logger.warning("Skipping unsafe entity label: %r", neo4j_label)
            continue
        logger.info("Ingesting %d %s nodes", len(items), neo4j_label)

        # UNWIND バッチ: name を NODE KEY として MERGE
        rows = []
        for item in items:
            name = item.get("name", "")
            if not name:
                continue
            # name と updated_at/enriched_at のみ保存（entity_key/entity_id は廃止）
            props = {
                k: v
                for k, v in item.items()
                if k
                not in {
                    "entity_id",
                    "entity_key",
                    "entity_type",
                    "neo4j_label",
                    "extra_labels",
                }
                and v is not None
            }
            rows.append({"name": name, "props": props})

        if not rows:
            continue

        if driver:
            query = (
                f"UNWIND $rows AS row "
                f"MERGE (n:{neo4j_label} {{name: row.name}}) "
                f"SET n += row.props"
            )
            with driver.session(database=_RESEARCH_DB) as session:
                session.execute_write(lambda tx, q=query, r=rows: tx.run(q, rows=r))

        count += len(rows)

    return count


def _ingest_entity_rel_single(
    driver,
    from_label: str,
    from_id_key: str,
    from_id: str,
    neo4j_label: str,
    entity_name: str,
) -> None:
    """単一の entity リレーション (from_node)-[:RELATES_TO]->(entity) を投入するサブ関数.

    Parameters
    ----------
    driver : neo4j.Driver
        Neo4j ドライバー。
    from_label : str
        始点ノードのラベル (例: "Fact", "Claim")。
    from_id_key : str
        始点ノードのキープロパティ名 (例: "fact_id", "claim_id")。
    from_id : str
        始点ノードのキー値。
    neo4j_label : str
        終点エンティティのラベル。
    entity_name : str
        終点エンティティの name プロパティ値。
    """
    query = (
        f"MATCH (f:{from_label} {{{from_id_key}: $from_id}}) "
        f"MATCH (e:{neo4j_label} {{name: $entity_name}}) "
        f"MERGE (f)-[:RELATES_TO]->(e)"
    )
    with driver.session(database=_RESEARCH_DB) as session:
        session.execute_write(
            lambda tx, q=query, fid=from_id, en=entity_name: tx.run(
                q, from_id=fid, entity_name=en
            )
        )


def _ingest_entity_rels_for_type(
    driver,
    rels: list[dict[str, Any]],
    from_label: str,
    from_id_rel_key: str,
    entity_id_to_info: dict[str, dict[str, str]],
) -> int:
    """単一リレーション種別 (fact_entity / claim_entity) のループ処理サブ関数.

    AIDEV-NOTE: N+1クエリ → UNWIND バッチに変換。
    neo4j_label ごとにグループ化し、1ラベル = 1トランザクションで実行する。

    Parameters
    ----------
    driver : neo4j.Driver | None
        Neo4j ドライバー。None の場合はカウントのみ。
    rels : list[dict]
        当該リレーション種別のリスト。
    from_label : str
        始点ノードのラベル (例: "Fact", "Claim")。
    from_id_rel_key : str
        始点ノードのキープロパティ名 (例: "fact_id", "claim_id")。
    entity_id_to_info : dict
        entity_id → {name, neo4j_label} の解決マップ。

    Returns
    -------
    int
        投入したリレーション数。
    """
    # neo4j_label → [{from_id, entity_name}] でグループ化
    label_to_rows: dict[str, list[dict[str, str]]] = {}
    for rel in rels:
        from_id = rel.get("from_id") or rel.get(from_id_rel_key)
        to_val = rel.get("to_id") or rel.get("entity_key") or rel.get("entity_name")
        if not from_id or not to_val:
            continue
        entity_info = entity_id_to_info.get(to_val)
        if entity_info is None:
            continue
        neo4j_label = entity_info["neo4j_label"]
        entity_name = entity_info["name"]
        if not entity_name or not _is_safe_identifier(neo4j_label):
            continue
        label_to_rows.setdefault(neo4j_label, []).append(
            {"from_id": from_id, "entity_name": entity_name}
        )

    count = 0
    for neo4j_label, rows in label_to_rows.items():
        count += len(rows)
        if driver:
            # 1ラベルにつき1クエリ（N+1 → O(unique_labels) に削減）
            query = (
                f"UNWIND $rows AS row "
                f"MATCH (f:{from_label} {{{from_id_rel_key}: row.from_id}}) "
                f"MATCH (e:{neo4j_label} {{name: row.entity_name}}) "
                f"MERGE (f)-[:RELATES_TO]->(e)"
            )
            with driver.session(database=_RESEARCH_DB) as session:
                session.execute_write(lambda tx, q=query, r=rows: tx.run(q, rows=r))
    return count


def _ingest_entity_rels(
    queue_data: dict[str, Any],
    driver,
) -> int:
    """entity 関連リレーション (fact_entity / claim_entity 等) を投入するサブ関数.

    v4.0: entity_key 廃止のため、name+label で MATCH する Cypher に変更。
    relations セクションの fact_entity / claim_entity / has_datapoint /
    datapoint_entity を処理する。

    Parameters
    ----------
    queue_data : dict
        graph-queue JSON のパース済みデータ。
    driver : neo4j.Driver | None
        Neo4j ドライバー。None の場合は dry_run（カウントのみ）。

    Returns
    -------
    int
        投入したリレーション数。
    """
    entities = queue_data.get("entities", [])
    if not entities:
        return 0

    # entity_id → (name, neo4j_label) の解決マップ
    # AIDEV-NOTE: relations の from_id/to_id が entity_id を指す場合に name+label で解決
    entity_id_to_info: dict[str, dict[str, str]] = {}
    for e in entities:
        eid = e.get("entity_id", "")
        if eid:
            entity_id_to_info[eid] = {
                "name": e.get("name", ""),
                "neo4j_label": _get_entity_neo4j_label(e),
            }

    relations = queue_data.get("relations", {})
    count = _ingest_entity_rels_for_type(
        driver,
        relations.get("fact_entity", []),
        "Fact",
        "fact_id",
        entity_id_to_info,
    )
    count += _ingest_entity_rels_for_type(
        driver,
        relations.get("claim_entity", []),
        "Claim",
        "claim_id",
        entity_id_to_info,
    )
    return count


def _batch_merge_nodes_tx(
    tx,
    label: str,
    key_prop: str,
    items: list[dict[str, Any]],
    on_create_field: str | None = None,
) -> None:
    """UNWIND バッチでノードをMERGEする (N+1クエリ → 1クエリ).

    Parameters
    ----------
    tx : neo4j.Transaction
        Neo4j トランザクション。
    label : str
        ノードのプライマリラベル。
    key_prop : str
        MERGE に使用するキープロパティ名。
    items : list[dict]
        投入するノードプロパティ一覧。
    on_create_field : str | None
        ON CREATE のみ設定するフィールド名（entity_id / topic_id 等）。
    """
    rows = []
    for item in items:
        key_val = item.get(key_prop)
        if not key_val:
            continue
        skip = {"extra_labels", key_prop}
        if on_create_field:
            skip.add(on_create_field)
        props = {k: v for k, v in item.items() if k not in skip}
        row: dict[str, Any] = {key_prop: key_val, "props": props}
        if on_create_field and on_create_field in item:
            row["on_create_val"] = item[on_create_field]
        rows.append(row)

    if not rows:
        return

    if on_create_field:
        query = (
            f"UNWIND $rows AS row "
            f"MERGE (n:{label} {{{key_prop}: row.{key_prop}}}) "
            f"ON CREATE SET n.{on_create_field} = row.on_create_val "
            f"SET n += row.props"
        )
    else:
        query = (
            f"UNWIND $rows AS row "
            f"MERGE (n:{label} {{{key_prop}: row.{key_prop}}}) "
            f"SET n += row.props"
        )
    tx.run(query, rows=rows)


def _batch_set_extra_labels(
    session,
    label: str,
    key_prop: str,
    items_with_extra: list[tuple[str, list[str]]],
) -> None:
    """UNWIND バッチで extra_labels を設定する (N+1クエリ → unique_label数クエリ).

    Parameters
    ----------
    session : neo4j.Session
        Neo4j セッション。
    label : str
        ノードのプライマリラベル。
    key_prop : str
        ノードの UNIQUE キープロパティ名。
    items_with_extra : list[tuple[str, list[str]]]
        (key_val, extra_labels) のペア一覧。
    """
    label_to_keys: dict[str, list[str]] = {}
    for key_val, extra_labels in items_with_extra:
        for extra_label in extra_labels:
            label_to_keys.setdefault(extra_label, []).append(key_val)

    for extra_label, keys in label_to_keys.items():
        if not _is_safe_identifier(extra_label):
            logger.warning("Skipping unsafe extra_label: %r", extra_label)
            continue
        query = (
            f"UNWIND $keys AS key "
            f"MATCH (n:{label} {{{key_prop}: key}}) "
            f"SET n:{extra_label}"
        )
        session.run(query, keys=keys)


def _batch_merge_rels_tx(
    tx,
    from_key: str,
    from_label: str,
    to_key: str,
    to_label: str,
    rel_type: str,
    rels: list[dict[str, Any]],
    id_to_key: dict[str, str] | None = None,
) -> int:
    """UNWIND バッチでリレーションをMERGEする (N+1クエリ → 1クエリ).

    Parameters
    ----------
    tx : neo4j.Transaction
        Neo4j トランザクション。
    from_key, from_label, to_key, to_label, rel_type : str
        エンドポイント情報。
    rels : list[dict]
        リレーションデータ一覧。
    id_to_key : dict | None
        entity_id / topic_id → entity_key / topic_key の解決マップ。

    Returns
    -------
    int
        新規作成されたリレーション数。
    """
    rows = []
    for rel in rels:
        from_val = rel.get("from_id") or rel.get(from_key)
        to_val = rel.get("to_id") or rel.get(to_key)
        if id_to_key:
            from_val = id_to_key.get(from_val, from_val) if from_val else from_val
            to_val = id_to_key.get(to_val, to_val) if to_val else to_val
        if from_val and to_val:
            rows.append({"from_val": from_val, "to_val": to_val})

    if not rows:
        return 0

    query = (
        f"UNWIND $rows AS row "
        f"MATCH (a:{from_label} {{{from_key}: row.from_val}}) "
        f"MATCH (b:{to_label} {{{to_key}: row.to_val}}) "
        f"MERGE (a)-[:{rel_type}]->(b)"
    )
    result = tx.run(query, rows=rows)
    summary = result.consume()
    return summary.counters.relationships_created


def _ingest_nodes(
    queue_data: dict[str, Any],
    driver,
) -> dict[str, int]:
    """ノードを投入するサブ関数.

    _NODE_KEY_MAP に定義された全セクションのノードを投入する。
    entities セクションは v4.0 スキーマで個別ラベル動的処理 (_ingest_entity_nodes)。
    classification_nodes は動的ラベルとして別処理する。

    Parameters
    ----------
    queue_data : dict
        graph-queue JSON のパース済みデータ。
    driver : neo4j.Driver | None
        Neo4j ドライバー。None の場合は dry_run（カウントのみ）。

    Returns
    -------
    dict[str, int]
        {"node_count": N}
    """
    node_count = 0

    # v4.0: entities セクションは個別ラベル動的処理
    entity_count = _ingest_entity_nodes(queue_data, driver)
    node_count += entity_count

    # 通常ノード投入（UNWIND バッチ: N+1 → 1クエリ/section）
    for section, config in _NODE_KEY_MAP.items():
        if config is None:
            continue  # entities と classification_nodes は別処理
        label, key_prop = config
        items = queue_data.get(section, [])
        if not items:
            continue
        logger.info("Ingesting %d %s nodes", len(items), label)
        on_create_field = _NODE_ID_ON_CREATE.get(label)
        if driver:
            with driver.session(database=_RESEARCH_DB) as session:
                session.execute_write(
                    _batch_merge_nodes_tx, label, key_prop, items, on_create_field
                )
                # extra_labels は v4.0 では entities に使用しないが、他のノード型に残す
                items_with_extra = [
                    (item[key_prop], item["extra_labels"])
                    for item in items
                    if item.get("extra_labels") and item.get(key_prop)
                ]
                if items_with_extra:
                    _batch_set_extra_labels(session, label, key_prop, items_with_extra)
        node_count += len(items)

    # classification_nodes 投入（動的ラベル）
    # SEC-005: label と key_property をホワイトリスト検証してから使用する
    for cnode in queue_data.get("classification_nodes", []):
        label = cnode.get("label")
        key_prop = cnode.get("key_property", f"{label.lower()}_id" if label else "id")
        if (
            not label
            or not _is_safe_identifier(label)
            or not _is_safe_identifier(key_prop)
        ):
            logger.warning(
                "Skipping classification_node with unsafe label/key_property: %r/%r",
                label,
                key_prop,
            )
            continue
        if driver:
            with driver.session(database=_RESEARCH_DB) as session:
                session.execute_write(
                    _merge_node, label, key_prop, cnode.get("properties", cnode)
                )
        node_count += 1

    return {"node_count": node_count}


def _ingest_classification_rels(
    queue_data: dict[str, Any],
    driver,
) -> int:
    """classification_rels を投入するサブ関数.

    AIDEV-NOTE: classification_nodes の key_property/key_value マップを使って
    to_label/to_key を正確に解決する。from_id は source_id として扱う。

    Returns
    -------
    int
        投入したリレーション数。
    """
    cn_keymap: dict[str, tuple[str, str]] = {}  # key_value → (label, key_property)
    for cnode in queue_data.get("classification_nodes", []):
        cn_label = cnode.get("label", "")
        cn_key_prop = cnode.get(
            "key_property", f"{cn_label.lower()}_id" if cn_label else "id"
        )
        cn_key_val = cnode.get("key_value", "")
        # SEC-005: 安全な識別子のみ使用する
        if (
            cn_key_val
            and cn_label
            and _is_safe_identifier(cn_label)
            and _is_safe_identifier(cn_key_prop)
        ):
            cn_keymap[cn_key_val] = (cn_label, cn_key_prop)

    source_id_set = {s.get("source_id") for s in queue_data.get("sources", [])}
    count = 0

    for crel in queue_data.get("classification_rels", []):
        rel_type = crel.get("type", "CLASSIFIED_AS")
        if not _is_safe_identifier(rel_type):
            logger.warning(
                "Skipping unsafe rel_type in classification_rels: %r", rel_type
            )
            continue
        from_id = crel.get("from_id")
        to_id = crel.get("to_id")
        # from_label/key: source_id ならば Source として扱う
        if from_id in source_id_set:
            from_label = "Source"
            from_key = "source_id"
        else:
            from_label = crel.get("from_label", "Entity")
            if not _is_safe_identifier(from_label):
                logger.warning(
                    "Skipping unsafe from_label in classification_rels: %r", from_label
                )
                continue
            from_key = f"{from_label.lower()}_id"
        # to_label/key: classification_nodes のマップで解決
        if to_id in cn_keymap:
            to_label, to_key = cn_keymap[to_id]
        else:
            to_label = crel.get("to_label", "Classification")
            to_key = f"{to_label.lower()}_id"
        if from_id and to_id and driver:
            with driver.session(database=_RESEARCH_DB) as session:
                session.execute_write(
                    _merge_relation,
                    from_key,
                    from_label,
                    to_key,
                    to_label,
                    rel_type,
                    {from_key: from_id, to_key: to_id},
                )
        count += 1

    return count


def _ingest_rels(
    queue_data: dict[str, Any],
    driver,
    id_to_key: dict[str, str],
) -> dict[str, Any]:
    """リレーションを投入するサブ関数.

    relations セクションと classification_rels セクションを処理する。

    Parameters
    ----------
    queue_data : dict
        graph-queue JSON のパース済みデータ。
    driver : neo4j.Driver | None
        Neo4j ドライバー。None の場合は dry_run（カウントのみ）。
    id_to_key : dict[str, str]
        entity_id / topic_id → entity_key / topic_key の解決マップ。

    Returns
    -------
    dict[str, Any]
        {"rel_count": N, "rel_verification": {section: (expected, created)}}
    """
    rel_count = 0
    rel_verification: dict[str, tuple[int, int]] = {}
    rel_endpoints = _resolve_rel_endpoints(queue_data)

    # v4.0: entity 関連リレーション (fact_entity / claim_entity 等) を個別処理
    entity_rel_count = _ingest_entity_rels(queue_data, driver)
    rel_count += entity_rel_count

    # ファイル内リレーション投入（entity 関連を除く）
    relations = queue_data.get("relations", {})
    for rel_section, endpoints in rel_endpoints.items():
        rels = relations.get(rel_section, [])
        if not rels:
            continue
        from_key, from_label, to_key, to_label, rel_type = endpoints
        logger.info("Ingesting %d %s relations", len(rels), rel_section)
        section_created = 0
        if driver:
            with driver.session(database=_RESEARCH_DB) as session:
                # UNWIND バッチ: N+1 → 1クエリ/section
                section_created = session.execute_write(
                    _batch_merge_rels_tx,
                    from_key,
                    from_label,
                    to_key,
                    to_label,
                    rel_type,
                    rels,
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
    rel_count += _ingest_classification_rels(queue_data, driver)

    return {"rel_count": rel_count, "rel_verification": rel_verification}


def load_graph_queue(queue_path: Path) -> dict[str, Any]:
    """graph-queue JSON を読み込む."""
    with queue_path.open(encoding="utf-8") as f:
        return json.load(f)


def apply_constraints_from_yaml(
    driver,
    schema_path: Path | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    """ontology_loader 経由で Neo4j の制約/インデックスを適用する.

    ontology_loader の ``load_constraints()`` / ``load_indices()`` から定義を取得し
    Cypher を生成・実行する。

    Parameters
    ----------
    driver : neo4j.Driver
        Neo4j ドライバー。
    schema_path : Path | None
        後方互換のため残すが使用しない。ontology_loader のデフォルトを使用。
    dry_run : bool
        True の場合は Cypher を生成するがドライバーは呼ばない。

    Returns
    -------
    dict[str, int]
        {"constraints_applied": N, "indices_applied": N}
    """
    constraints = _ol_load_constraints()
    indices = _ol_load_indices()

    if dry_run:
        constraints_applied = len(constraints)
        indices_applied = len(indices)
        logger.info(
            "dry_run: would apply %d constraints, %d indices",
            constraints_applied,
            indices_applied,
        )
        return {
            "constraints_applied": constraints_applied,
            "indices_applied": indices_applied,
        }

    constraints_applied = 0
    indices_applied = 0
    with driver.session(database=_RESEARCH_DB) as session:
        for constraint in constraints:
            label = constraint["label"]
            prop = constraint["property"]
            if not _is_safe_identifier(label) or not _is_safe_identifier(prop):
                logger.warning(
                    "Skipping unsafe constraint label/prop: %r/%r", label, prop
                )
                continue
            ctype = constraint.get("type", "UNIQUE")
            if ctype == "UNIQUE":
                cypher = (
                    f"CREATE CONSTRAINT IF NOT EXISTS "
                    f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
                )
            elif ctype == "NODE_KEY":
                # Neo4j Enterprise Edition のみ対応
                cypher = (
                    f"CREATE CONSTRAINT IF NOT EXISTS "
                    f"FOR (n:{label}) REQUIRE (n.{prop}) IS NODE KEY"
                )
            else:
                logger.warning("Unsupported constraint type: %s, skipping", ctype)
                continue
            try:
                session.run(cypher)
                constraints_applied += 1
                logger.debug("Applied constraint: %s.%s (%s)", label, prop, ctype)
            except Exception as e:
                logger.warning("Failed to apply constraint %s.%s: %s", label, prop, e)

        for index in indices:
            label = index["label"]
            prop = index["property"]
            if not _is_safe_identifier(label) or not _is_safe_identifier(prop):
                logger.warning("Skipping unsafe index label/prop: %r/%r", label, prop)
                continue
            cypher = f"CREATE INDEX IF NOT EXISTS FOR (n:{label}) ON (n.{prop})"
            try:
                session.run(cypher)
                indices_applied += 1
                logger.debug("Applied index: %s.%s", label, prop)
            except Exception as e:
                logger.warning("Failed to apply index %s.%s: %s", label, prop, e)

    logger.info(
        "Schema applied: %d constraints, %d indices",
        constraints_applied,
        indices_applied,
    )
    return {
        "constraints_applied": constraints_applied,
        "indices_applied": indices_applied,
    }


def _apply_constraints_if_requested(
    driver,
    schema_path: Path | None,
    dry_run: bool,
) -> None:
    """apply_constraints フラグが True の場合に制約/インデックスを適用する."""
    try:
        result = apply_constraints_from_yaml(driver, schema_path, dry_run=dry_run)
        logger.info(
            "Constraints applied: %d constraints, %d indices",
            result["constraints_applied"],
            result["indices_applied"],
        )
    except Exception:
        logger.warning("Failed to apply constraints, skipping", exc_info=True)


def ingest_to_neo4j(
    queue_data: dict[str, Any],
    *,
    dry_run: bool = False,
    apply_constraints: bool = False,
    skip_schema_check: bool = False,
    schema_path: Path | None = None,
) -> dict[str, Any]:
    """graph-queue データを Neo4j に投入する.

    Parameters
    ----------
    queue_data : dict
        graph-queue JSON のパース済みデータ。
    dry_run : bool
        True の場合は投入せずカウントのみ返す。
    apply_constraints : bool
        True の場合、YAML スキーマの制約/インデックスを適用してから投入する。
        False（デフォルト）の場合は制約/インデックス適用をスキップする。
    skip_schema_check : bool
        True の場合、スキーマチェック全体をスキップする。
    schema_path : Path | None
        ontology.yaml へのパス (ontology_loader 経由)。None の場合はデフォルトパスを使用。

    Returns
    -------
    dict[str, Any]
        投入結果 {"nodes": int, "relations": int, "rel_verification": dict}。
    """
    driver = None if dry_run else _get_driver()

    try:
        # YAML 制約/インデックス自動適用
        if apply_constraints and not skip_schema_check:
            _apply_constraints_if_requested(driver, schema_path, dry_run)

        # ノード投入
        node_result = _ingest_nodes(queue_data, driver)
        node_count = node_result["node_count"]

        # entity_id/topic_id → entity_key/topic_key 解決マップの構築
        id_to_key = _build_id_to_key(queue_data)

        # リレーション投入
        rel_result = _ingest_rels(queue_data, driver, id_to_key)
        rel_count = rel_result["rel_count"]
        rel_verification = rel_result["rel_verification"]

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

_CREATOR_DEFAULT_URI = _DEFAULT_URI  # Enterprise: 同一ポート、database名で分離

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


def _get_creator_driver() -> Driver:
    """creator database 用ドライバーを取得する."""
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
