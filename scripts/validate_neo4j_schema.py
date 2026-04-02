#!/usr/bin/env python3
"""Neo4j スキーマ検証スクリプト。

ontology_loader 経由で ontology.yaml の namespaces 定義と Neo4j DB 上の
実際のラベルを照合し、逸脱を検出・レポートする。

Usage
-----
::

    # 検証のみ（デフォルト）
    python scripts/validate_neo4j_schema.py

    # JSON レポート出力
    python scripts/validate_neo4j_schema.py --output data/processed/schema_validation.json

    # 接続先を指定
    python scripts/validate_neo4j_schema.py --neo4j-uri bolt://localhost:7687
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from ontology_loader import (
    load_consolidation_mapping as _ol_load_consolidation_mapping,
)
from ontology_loader import (
    load_constraints as _ol_load_constraints,
)
from ontology_loader import (
    load_indices as _ol_load_indices,
)
from ontology_loader import (
    load_multilabel_types as _ol_load_multilabel_types,
)
from ontology_loader import (
    load_namespaces as _ol_load_namespaces,
)
from ontology_loader import (
    load_source_type_normalization as _ol_load_source_type_normalization,
)

try:
    from neo4j import Driver, GraphDatabase
except ImportError:
    print("neo4j driver not installed. Run: uv add neo4j")
    sys.exit(1)

try:
    from utils_core.logging.config import get_logger

    logger = get_logger(__name__)
except ImportError:
    import logging

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger = logging.getLogger(__name__)

ALLOWED_URI_SCHEMES = {"bolt", "bolt+s", "bolt+ssc", "neo4j", "neo4j+s", "neo4j+ssc"}

# ---------------------------------------------------------------------------
# Schema loading
# ---------------------------------------------------------------------------


def load_namespaces(schema_path: Path | None = None) -> dict[str, Any]:
    """ontology_loader 経由で namespaces 定義を読み込む。

    Parameters
    ----------
    schema_path : Path | None
        後方互換のため残すが使用しない。ontology_loader のデフォルトを使用。

    Returns
    -------
    dict[str, Any]
        名前空間定義。
    """
    return _ol_load_namespaces()


def load_v30_sections(schema_path: Path | None = None) -> dict[str, Any]:
    """ontology_loader 経由で v3.0 セクション相当のデータを構築する。

    ontology_loader の各関数から取得したデータを旧形式互換の dict に組み立てて返す。

    Parameters
    ----------
    schema_path : Path | None
        後方互換のため残すが使用しない。ontology_loader のデフォルトを使用。

    Returns
    -------
    dict[str, Any]
        v3.0 新規セクション互換の辞書。
    """
    multilabel_types = _ol_load_multilabel_types()
    source_norm = _ol_load_source_type_normalization()
    consolidation = _ol_load_consolidation_mapping()

    return {
        "multilabel_types": {"entity_labels": {"labels": multilabel_types}},
        "consolidation_rules": {"entity_type": {"mapping": consolidation}},
        "enum_validations": {
            "entity_type": {"values": multilabel_types},
            "source_type": {"values": list({v for v in source_norm.values()})},
        },
        "source_type_normalization": {"mapping": source_norm},
    }


def build_allowed_labels(namespaces: dict[str, Any]) -> dict[str, str]:
    """名前空間定義から許可ラベル → 名前空間のマッピングを構築する。

    Parameters
    ----------
    namespaces : dict[str, Any]
        YAML の namespaces セクション。

    Returns
    -------
    dict[str, str]
        ラベル名 → 名前空間名のマッピング。
    """
    label_to_ns: dict[str, str] = {}

    for ns_name, ns_def in namespaces.items():
        if "labels" in ns_def:
            for label in ns_def["labels"]:
                label_to_ns[label] = ns_name
        if "root_label" in ns_def:
            label_to_ns[ns_def["root_label"]] = ns_name
        if "sub_labels" in ns_def:
            for label in ns_def["sub_labels"]:
                label_to_ns[label] = ns_name

    return label_to_ns


# ---------------------------------------------------------------------------
# Validation checks
# ---------------------------------------------------------------------------


def check_pascal_case_violations(db_labels: list[str]) -> list[dict[str, str]]:
    """小文字で始まるラベル（PascalCase 違反）を検出する。

    Parameters
    ----------
    db_labels : list[str]
        DB 上の全ラベル。

    Returns
    -------
    list[dict[str, str]]
        違反ラベルのリスト。
    """
    return [
        {"label": label, "issue": "starts with lowercase"}
        for label in db_labels
        if label and label[0].islower()
    ]


def check_cross_contamination(
    session: Any,
    allowed: dict[str, str],
) -> list[dict[str, Any]]:
    """Memory ノードが KG v2 ラベルを持つケースを検出する。

    Parameters
    ----------
    session
        Neo4j セッション。
    allowed : dict[str, str]
        許可ラベルマッピング（kg_v2 ラベルを動的に取得するため）。

    Returns
    -------
    list[dict[str, Any]]
        クロスコンタミネーションの一覧。
    """
    kg_v2_labels = [label for label, ns in allowed.items() if ns == "kg_v2"]
    query = """
    MATCH (n:Memory)
    WHERE any(l IN labels(n) WHERE l IN $kg_labels)
    RETURN labels(n) AS labels, n.name AS name
    """
    result = session.run(query, kg_labels=kg_v2_labels)
    return [dict(r) for r in result]


def check_multilabel_entity(session: Any) -> dict[str, Any]:
    """シングルラベル Entity ノードを検出する（WARNING 対象）。

    v3.0 では全 Entity に対してマルチラベル（e.g. Entity + Company）が付与される。
    シングルラベル（``Entity`` のみ）のノードが残っている場合は Migration が
    未完了であることを示す。

    Parameters
    ----------
    session
        Neo4j セッション。

    Returns
    -------
    dict[str, Any]
        - ``single_label_count`` (int): シングルラベル Entity の件数。
        - ``pass`` (bool): 件数が 0 の場合 True。
        - ``warning`` (bool): 件数 > 0 の場合 True（WARNING レベル）。
    """
    # AIDEV-NOTE: Wave7 (Issue #312) — Entity ラベルは廃止済み。
    # 個別ラベル(Company等)のみを持つノード（サブラベルがないもの）を検出する。
    # Node KEY制約により name で一意識別される。
    result = session.run(
        "MATCH (e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product) "
        "WHERE size(labels(e)) = 1 RETURN count(e) AS cnt"
    )
    record = result.single()
    count = record["cnt"] if record else 0
    return {
        "single_label_count": count,
        "pass": count == 0,
        "warning": count > 0,
    }


def check_enum_source_type(
    session: Any,
    allowed_values: list[str],
) -> dict[str, Any]:
    """Source.source_type の不正値を検出する（ERROR 対象）。

    Parameters
    ----------
    session
        Neo4j セッション。
    allowed_values : list[str]
        YAML の ``enum_validations.source_type.values`` から取得した有効値リスト。

    Returns
    -------
    dict[str, Any]
        - ``db_values`` (list[str]): DB 上の全 source_type 値。
        - ``invalid_values`` (list[str]): 許可されていない値。
        - ``pass`` (bool): 不正値が 0 件の場合 True。
    """
    result = session.run(
        "MATCH (s:Source) "
        "WHERE s.source_type IS NOT NULL "
        "RETURN DISTINCT s.source_type AS source_type "
        "ORDER BY source_type"
    )
    db_values = [r["source_type"] for r in result]
    allowed_set = set(allowed_values)
    invalid_values = [v for v in db_values if v not in allowed_set]
    return {
        "db_values": db_values,
        "invalid_values": invalid_values,
        "pass": len(invalid_values) == 0,
    }


def check_entity_type_convergence(
    session: Any,
    allowed_values: list[str],
) -> dict[str, Any]:
    """Entity.entity_type が 14 種の正規型に収束しているか確認する。

    Parameters
    ----------
    session
        Neo4j セッション。
    allowed_values : list[str]
        YAML の ``enum_validations.entity_type.values`` から取得した有効値リスト（14種）。

    Returns
    -------
    dict[str, Any]
        - ``db_values`` (list[str]): DB 上の全 entity_type 値。
        - ``invalid_values`` (list[str]): 14種以外の値（未マイグレーション等）。
        - ``type_count`` (int): DB 上のユニーク entity_type 数。
        - ``pass`` (bool): 不正値が 0 件かつ type_count <= len(allowed_values) の場合 True。
    """
    # AIDEV-NOTE: Wave7 (Issue #312) — :Entity → 個別ラベル union に更新
    max_allowed = len(allowed_values)
    result = session.run(
        "MATCH (e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product) "
        "WHERE e.entity_type IS NOT NULL "
        "RETURN DISTINCT e.entity_type AS entity_type "
        "ORDER BY entity_type"
    )
    db_values = [r["entity_type"] for r in result]
    allowed_set = set(allowed_values)
    invalid_values = [v for v in db_values if v not in allowed_set]
    return {
        "db_values": db_values,
        "invalid_values": invalid_values,
        "type_count": len(db_values),
        "max_allowed": max_allowed,
        "pass": len(invalid_values) == 0 and len(db_values) <= max_allowed,
    }


def check_constraints_and_indices(
    session: Any,
    schema_constraints: list[dict[str, str]],
    schema_indices: list[dict[str, str]],
) -> dict[str, Any]:
    """YAML 定義の constraints/indices と DB の実際の制約・インデックスを照合する。

    Parameters
    ----------
    session
        Neo4j セッション。
    schema_constraints : list[dict[str, str]]
        YAML の ``constraints`` セクション（``label``, ``property``, ``type`` キー）。
    schema_indices : list[dict[str, str]]
        YAML の ``indices`` セクション（``label``, ``property`` キー）。

    Returns
    -------
    dict[str, Any]
        - ``missing_constraints`` (list): YAML にあるが DB にない制約。
        - ``missing_indices`` (list): YAML にあるが DB にないインデックス。
        - ``pass`` (bool): 欠落が 0 件の場合 True。
    """
    # DB の制約を取得（UNIQUE のみ対象）
    try:
        constraint_result = session.run(
            "SHOW CONSTRAINTS YIELD labelsOrTypes, properties, type"
        )
        db_constraints: set[tuple[str, str]] = set()
        for r in constraint_result:
            labels = r["labelsOrTypes"]
            props = r["properties"]
            ctype = r["type"]
            if (
                labels
                and props
                and ctype in ("UNIQUENESS", "NODE_UNIQUENESS", "UNIQUE")
            ):
                label = labels[0] if isinstance(labels, list) else labels
                prop = props[0] if isinstance(props, list) else props
                db_constraints.add((label, prop))
    except Exception:
        # SHOW CONSTRAINTS が利用できない場合はスキップ
        db_constraints = set()

    # DB のインデックスを取得（BTREE / RANGE など通常インデックス）
    try:
        index_result = session.run(
            "SHOW INDEXES YIELD labelsOrTypes, properties, type "
            "WHERE type IN ['BTREE', 'RANGE', 'LOOKUP', 'TEXT'] OR type IS NOT NULL"
        )
        db_indices: set[tuple[str, str]] = set()
        for r in index_result:
            labels = r["labelsOrTypes"]
            props = r["properties"]
            if labels and props:
                label = labels[0] if isinstance(labels, list) else labels
                prop = props[0] if isinstance(props, list) else props
                db_indices.add((label, prop))
    except Exception:
        db_indices = set()

    # YAML 定義との照合
    missing_constraints = [
        c
        for c in schema_constraints
        if (c["label"], c["property"]) not in db_constraints
    ]
    missing_indices = [
        i for i in schema_indices if (i["label"], i["property"]) not in db_indices
    ]

    return {
        "missing_constraints": missing_constraints,
        "missing_indices": missing_indices,
        "db_constraint_count": len(db_constraints),
        "db_index_count": len(db_indices),
        "pass": len(missing_constraints) == 0 and len(missing_indices) == 0,
    }


def classify_db_labels(
    db_labels: list[str],
    allowed: dict[str, str],
) -> dict[str, list[str]]:
    """DB ラベルを名前空間ごとに分類する。

    Parameters
    ----------
    db_labels : list[str]
        DB 上の全ラベル。
    allowed : dict[str, str]
        許可ラベルマッピング。

    Returns
    -------
    dict[str, list[str]]
        名前空間名 → ラベルリスト。
    """
    classified: dict[str, list[str]] = {}
    for label in db_labels:
        ns = allowed.get(label, "UNKNOWN")
        classified.setdefault(ns, []).append(label)
    return classified


# ---------------------------------------------------------------------------
# Report building & formatting
# ---------------------------------------------------------------------------


def build_report(
    *,
    schema_path: str,
    db_labels: list[str],
    allowed: dict[str, str],
    unknown_labels: list[dict[str, str]],
    pascal_violations: list[dict[str, str]],
    contamination: list[dict[str, Any]],
    classified: dict[str, list[str]],
    now: datetime | None = None,
    multilabel_check: dict[str, Any] | None = None,
    source_type_check: dict[str, Any] | None = None,
    entity_type_check: dict[str, Any] | None = None,
    constraints_check: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """検証結果からレポート辞書を構築する。

    Parameters
    ----------
    schema_path : str
        YAML スキーマファイルのパス文字列。
    db_labels : list[str]
        DB 上の全ラベル。
    allowed : dict[str, str]
        許可ラベルマッピング。
    unknown_labels : list[dict[str, str]]
        不明ラベルのリスト。
    pascal_violations : list[dict[str, str]]
        PascalCase 違反ラベルのリスト。
    contamination : list[dict[str, Any]]
        クロスコンタミネーションのリスト。
    classified : dict[str, list[str]]
        名前空間ごとに分類したラベル辞書。
    now : datetime | None
        検証日時（テスト用）。
    multilabel_check : dict[str, Any] | None
        :func:`check_multilabel_entity` の結果（v3.0）。
    source_type_check : dict[str, Any] | None
        :func:`check_enum_source_type` の結果（v3.0）。
    entity_type_check : dict[str, Any] | None
        :func:`check_entity_type_convergence` の結果（v3.0）。
    constraints_check : dict[str, Any] | None
        :func:`check_constraints_and_indices` の結果（v3.0）。
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # v3.0 チェックが提供されている場合は overall_pass に反映
    # multilabel は WARNING のみ（overall_pass には影響しない）
    # source_type の不正値は ERROR → overall_pass を False にする
    # entity_type の収束は ERROR → overall_pass を False にする
    # constraints/indices の欠落は WARNING のみ（overall_pass には影響しない）
    v30_errors_pass = all(
        [
            source_type_check is None or source_type_check.get("pass", True),
            entity_type_check is None or entity_type_check.get("pass", True),
        ]
    )

    return {
        "validation_date": now.isoformat(),
        "schema_path": schema_path,
        "db_label_count": len(db_labels),
        "allowed_label_count": len(allowed),
        "namespace_classification": classified,
        "checks": {
            "unknown_labels": {
                "count": len(unknown_labels),
                "pass": len(unknown_labels) == 0,
                "details": unknown_labels,
            },
            "pascal_case_violations": {
                "count": len(pascal_violations),
                "pass": len(pascal_violations) == 0,
                "details": pascal_violations,
            },
            "cross_contamination": {
                "count": len(contamination),
                "pass": len(contamination) == 0,
                "details": contamination,
            },
            "multilabel_entity": multilabel_check,
            "source_type_enum": source_type_check,
            "entity_type_convergence": entity_type_check,
            "constraints_and_indices": constraints_check,
        },
        "overall_pass": (
            len(unknown_labels) == 0
            and len(pascal_violations) == 0
            and len(contamination) == 0
            and v30_errors_pass
        ),
    }


def format_report(report: dict[str, Any]) -> str:
    """レポートをテキスト形式にフォーマットする。"""
    lines: list[str] = []
    lines.append("\n=== Neo4j Schema Validation Report ===\n")
    lines.append(f"DB Labels: {report['db_label_count']}")
    lines.append(f"Allowed Labels: {report['allowed_label_count']}")
    lines.append("")

    lines.append("Namespace Classification:")
    for ns, labels in sorted(report["namespace_classification"].items()):
        lines.append(f"  {ns}: {', '.join(sorted(labels))}")
    lines.append("")

    unknown = report["checks"]["unknown_labels"]
    if unknown["count"] > 0:
        lines.append(f"UNKNOWN labels ({unknown['count']}):")
        for u in unknown["details"]:
            lines.append(f"  - {u['label']}")
    else:
        lines.append("UNKNOWN labels: 0 (PASS)")

    violations = report["checks"]["pascal_case_violations"]
    if violations["count"] > 0:
        lines.append(f"\nPascalCase violations ({violations['count']}):")
        for v in violations["details"]:
            lines.append(f"  - {v['label']}: {v['issue']}")
    else:
        lines.append("PascalCase violations: 0 (PASS)")

    contamination = report["checks"]["cross_contamination"]
    if contamination["count"] > 0:
        lines.append(f"\nCross-contamination ({contamination['count']}):")
        for c in contamination["details"]:
            lines.append(f"  - {c['name']}: {c['labels']}")
    else:
        lines.append("Cross-contamination: 0 (PASS)")

    # --- v3.0 チェック ---
    multilabel = report["checks"].get("multilabel_entity")
    if multilabel is not None:
        count = multilabel.get("single_label_count", 0)
        if count > 0:
            lines.append(
                f"\nWARNING: Single-label Entity nodes: {count} "
                "(v3.0 migration may be incomplete)"
            )
        else:
            lines.append("\nMulti-label Entity check: 0 single-label nodes (PASS)")

    source_type = report["checks"].get("source_type_enum")
    if source_type is not None:
        invalid = source_type.get("invalid_values", [])
        if invalid:
            lines.append(f"\nERROR: Invalid source_type values ({len(invalid)}):")
            for v in invalid:
                lines.append(f"  - {v!r}")
        else:
            lines.append("\nSource.source_type enum: all valid (PASS)")

    entity_type = report["checks"].get("entity_type_convergence")
    if entity_type is not None:
        invalid = entity_type.get("invalid_values", [])
        type_count = entity_type.get("type_count", 0)
        max_allowed = entity_type.get("max_allowed", 14)
        if invalid:
            lines.append(
                f"\nERROR: Entity.entity_type out-of-range values ({len(invalid)}):"
            )
            for v in invalid:
                lines.append(f"  - {v!r}")
        else:
            lines.append(
                f"\nEntity.entity_type convergence: {type_count}/{max_allowed} types (PASS)"
            )

    constraints = report["checks"].get("constraints_and_indices")
    if constraints is not None:
        missing_c = constraints.get("missing_constraints", [])
        missing_i = constraints.get("missing_indices", [])
        if missing_c:
            lines.append(f"\nWARNING: Missing constraints ({len(missing_c)}):")
            for c in missing_c:
                lines.append(
                    f"  - {c['label']}.{c['property']} ({c.get('type', 'UNIQUE')})"
                )
        else:
            lines.append(
                f"\nConstraints: {constraints.get('db_constraint_count', 0)} in DB (PASS)"
            )
        if missing_i:
            lines.append(f"\nWARNING: Missing indices ({len(missing_i)}):")
            for i in missing_i:
                lines.append(f"  - {i['label']}.{i['property']}")
        else:
            lines.append(
                f"\nIndices: {constraints.get('db_index_count', 0)} in DB (PASS)"
            )

    lines.append(f"\nOverall: {'PASS' if report['overall_pass'] else 'FAIL'}")
    return "\n".join(lines)


def save_report(report: dict[str, Any], output_path: Path) -> None:
    """レポートを JSON ファイルに保存する。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    logger.info("Report saved: %s", output_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _validate_uri_scheme(uri: str) -> None:
    """URI スキームが許可されたものか検証する。"""
    parsed = urlparse(uri)
    if parsed.scheme not in ALLOWED_URI_SCHEMES:
        msg = (
            f"Unsupported URI scheme: {parsed.scheme}. "
            f"Allowed: {', '.join(sorted(ALLOWED_URI_SCHEMES))}"
        )
        raise ValueError(msg)


def _validate_output_path(output: str) -> Path:
    """出力パスがプロジェクト内であることを検証する。"""
    output_path = Path(output).resolve()
    project_root = Path.cwd().resolve()
    if not str(output_path).startswith(str(project_root)):
        msg = f"Output path must be under project root: {project_root}"
        raise ValueError(msg)
    return output_path


def main() -> None:
    """スキーマ検証のエントリーポイント。"""
    parser = argparse.ArgumentParser(
        description="Validate Neo4j schema against ontology.yaml (via ontology_loader)",
    )
    parser.add_argument(
        "--schema",
        default=None,
        help="Path to ontology.yaml (default: auto-detect via ontology_loader)",
    )
    parser.add_argument("--output", help="Output JSON report path")
    parser.add_argument(
        "--neo4j-uri",
        default=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        help="Neo4j connection URI",
    )
    parser.add_argument(
        "--neo4j-user",
        default=os.environ.get("NEO4J_USER", "neo4j"),
        help="Neo4j username",
    )
    parser.add_argument(
        "--neo4j-password",
        default=os.environ.get("NEO4J_PASSWORD"),
        help="Neo4j password (required: set NEO4J_PASSWORD env var)",
    )
    args = parser.parse_args()

    if not args.neo4j_password:
        parser.error(
            "Neo4j password is required. "
            "Set NEO4J_PASSWORD environment variable or use --neo4j-password."
        )

    try:
        _validate_uri_scheme(args.neo4j_uri)
    except ValueError as e:
        parser.error(str(e))

    logger.info("Loading schema via ontology_loader")
    try:
        namespaces = load_namespaces()
    except (ValueError, FileNotFoundError) as e:
        logger.error("%s", e)
        sys.exit(1)

    allowed = build_allowed_labels(namespaces)
    logger.info("Allowed labels loaded: %d", len(allowed))

    # Load v3.0 sections for additional validation
    v30 = load_v30_sections()

    parsed_uri = urlparse(args.neo4j_uri)
    logger.info("Connecting to Neo4j: %s:%s", parsed_uri.hostname, parsed_uri.port)
    driver: Driver = GraphDatabase.driver(
        args.neo4j_uri,
        auth=(args.neo4j_user, args.neo4j_password),
    )

    try:
        with driver.session() as session:
            result = session.run(
                "CALL db.labels() YIELD label RETURN label ORDER BY label"
            )
            db_labels = [r["label"] for r in result]
            logger.info("DB labels fetched: %d", len(db_labels))

            # classify first, then derive unknown from it (single scan)
            classified = classify_db_labels(db_labels, allowed)
            unknown_labels = [
                {"label": label, "namespace": "UNKNOWN"}
                for label in classified.get("UNKNOWN", [])
            ]
            pascal_violations = check_pascal_case_violations(db_labels)
            contamination = check_cross_contamination(session, allowed)

            # --- v3.0 checks ---
            logger.info("Running v3.0 multilabel Entity check...")
            multilabel_check = check_multilabel_entity(session)
            if multilabel_check["warning"]:
                logger.warning(
                    "Single-label Entity nodes detected: %d "
                    "(v3.0 migration may be incomplete)",
                    multilabel_check["single_label_count"],
                )

            source_type_check: dict[str, Any] | None = None
            entity_type_check: dict[str, Any] | None = None
            if v30.get("enum_validations"):
                enum_vals = v30["enum_validations"]

                source_type_vals = (
                    enum_vals.get("source_type", {}).get("values", [])
                    if isinstance(enum_vals, dict)
                    else []
                )
                if source_type_vals:
                    logger.info("Running v3.0 source_type enum check...")
                    source_type_check = check_enum_source_type(
                        session, source_type_vals
                    )
                    if not source_type_check["pass"]:
                        logger.error(
                            "Invalid source_type values detected: %s",
                            source_type_check["invalid_values"],
                        )

                entity_type_vals = (
                    enum_vals.get("entity_type", {}).get("values", [])
                    if isinstance(enum_vals, dict)
                    else []
                )
                if entity_type_vals:
                    logger.info("Running v3.0 entity_type convergence check...")
                    entity_type_check = check_entity_type_convergence(
                        session, entity_type_vals
                    )
                    if not entity_type_check["pass"]:
                        logger.error(
                            "Entity.entity_type convergence failed: "
                            "%d/%d types, invalid: %s",
                            entity_type_check["type_count"],
                            entity_type_check["max_allowed"],
                            entity_type_check["invalid_values"],
                        )

            constraints_check: dict[str, Any] | None = None
            try:
                schema_constraints = _ol_load_constraints()
                schema_indices = _ol_load_indices()
                if schema_constraints or schema_indices:
                    logger.info("Running v3.0 constraints/indices check...")
                    constraints_check = check_constraints_and_indices(
                        session, schema_constraints, schema_indices
                    )
                    if not constraints_check["pass"]:
                        logger.warning(
                            "Missing constraints: %d, missing indices: %d",
                            len(constraints_check["missing_constraints"]),
                            len(constraints_check["missing_indices"]),
                        )
            except Exception as e:
                logger.warning("Could not load constraints/indices: %s", e)

        report = build_report(
            schema_path=args.schema or "ontology.yaml (via ontology_loader)",
            db_labels=db_labels,
            allowed=allowed,
            unknown_labels=unknown_labels,
            pascal_violations=pascal_violations,
            contamination=contamination,
            classified=classified,
            multilabel_check=multilabel_check,
            source_type_check=source_type_check,
            entity_type_check=entity_type_check,
            constraints_check=constraints_check,
        )

        print(format_report(report))

        if args.output:
            try:
                validated_path = _validate_output_path(args.output)
            except ValueError as e:
                logger.error("%s", e)
                sys.exit(1)
            save_report(report, validated_path)

        if not report["overall_pass"]:
            sys.exit(1)

    finally:
        driver.close()


if __name__ == "__main__":
    main()
