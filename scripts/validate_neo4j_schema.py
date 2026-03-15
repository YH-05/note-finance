#!/usr/bin/env python3
"""Neo4j スキーマ検証スクリプト。

knowledge-graph-schema.yaml の namespaces セクションと Neo4j DB 上の
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

import yaml

try:
    from neo4j import GraphDatabase
except ImportError:
    print("neo4j driver not installed. Run: uv add neo4j")
    sys.exit(1)

import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema loading
# ---------------------------------------------------------------------------

def load_namespaces(schema_path: Path) -> dict:
    """knowledge-graph-schema.yaml から namespaces セクションを読み込む。

    Parameters
    ----------
    schema_path : Path
        YAML スキーマファイルのパス。

    Returns
    -------
    dict
        名前空間定義。
    """
    with open(schema_path, encoding="utf-8") as f:
        schema = yaml.safe_load(f)

    namespaces = schema.get("namespaces")
    if namespaces is None:
        logger.error("namespaces section not found in schema: %s", schema_path)
        sys.exit(1)

    return namespaces


def build_allowed_labels(namespaces: dict) -> dict[str, str]:
    """名前空間定義から許可ラベル → 名前空間のマッピングを構築する。

    Parameters
    ----------
    namespaces : dict
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

def check_unknown_labels(
    db_labels: list[str],
    allowed: dict[str, str],
) -> list[dict]:
    """許可リストにないラベルを検出する。

    Parameters
    ----------
    db_labels : list[str]
        DB 上の全ラベル。
    allowed : dict[str, str]
        許可ラベルマッピング。

    Returns
    -------
    list[dict]
        UNKNOWN ラベルのリスト。
    """
    unknown = []
    for label in db_labels:
        if label not in allowed:
            unknown.append({"label": label, "namespace": "UNKNOWN"})
    return unknown


def check_pascal_case_violations(db_labels: list[str]) -> list[dict]:
    """小文字で始まるラベル（PascalCase 違反）を検出する。

    Parameters
    ----------
    db_labels : list[str]
        DB 上の全ラベル。

    Returns
    -------
    list[dict]
        違反ラベルのリスト。
    """
    violations = []
    for label in db_labels:
        if label[0].islower():
            violations.append({"label": label, "issue": "starts with lowercase"})
    return violations


def check_cross_contamination(driver) -> list[dict]:
    """Memory ノードが KG v2 ラベルを持つケースを検出する。

    Parameters
    ----------
    driver
        Neo4j ドライバー。

    Returns
    -------
    list[dict]
        クロスコンタミネーションの一覧。
    """
    kg_v2_labels = [
        "Source", "Author", "Chunk", "Fact", "Claim", "Entity",
        "FinancialDataPoint", "FiscalPeriod", "Topic", "Insight",
    ]
    query = """
    MATCH (n:Memory)
    WHERE any(l IN labels(n) WHERE l IN $kg_labels)
    RETURN labels(n) AS labels, n.name AS name
    """
    with driver.session() as session:
        result = session.run(query, kg_labels=kg_v2_labels)
        return [dict(r) for r in result]


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
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate Neo4j schema against knowledge-graph-schema.yaml",
    )
    parser.add_argument(
        "--schema",
        default="data/config/knowledge-graph-schema.yaml",
        help="Path to knowledge-graph-schema.yaml",
    )
    parser.add_argument(
        "--output",
        help="Output JSON report path",
    )
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
        default=os.environ.get("NEO4J_PASSWORD", "password"),
        help="Neo4j password",
    )
    args = parser.parse_args()

    logger.info("Loading schema: %s", args.schema)
    namespaces = load_namespaces(Path(args.schema))
    allowed = build_allowed_labels(namespaces)
    logger.info("Allowed labels loaded: %d", len(allowed))

    logger.info("Connecting to Neo4j: %s", args.neo4j_uri)
    driver = GraphDatabase.driver(
        args.neo4j_uri,
        auth=(args.neo4j_user, args.neo4j_password),
    )

    try:
        with driver.session() as session:
            result = session.run("CALL db.labels() YIELD label RETURN label ORDER BY label")
            db_labels = [r["label"] for r in result]

        logger.info("DB labels fetched: %d", len(db_labels))

        # Run checks
        unknown = check_unknown_labels(db_labels, allowed)
        pascal_violations = check_pascal_case_violations(db_labels)
        contamination = check_cross_contamination(driver)
        classified = classify_db_labels(db_labels, allowed)

        # Build report
        report = {
            "validation_date": datetime.now(timezone.utc).isoformat(),
            "schema_path": args.schema,
            "db_label_count": len(db_labels),
            "allowed_label_count": len(allowed),
            "namespace_classification": classified,
            "checks": {
                "unknown_labels": {
                    "count": len(unknown),
                    "pass": len(unknown) == 0,
                    "details": unknown,
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
            },
            "overall_pass": (
                len(unknown) == 0
                and len(pascal_violations) == 0
                and len(contamination) == 0
            ),
        }

        # Print results
        print("\n=== Neo4j Schema Validation Report ===\n")
        print(f"DB Labels: {len(db_labels)}")
        print(f"Allowed Labels: {len(allowed)}")
        print()

        print("Namespace Classification:")
        for ns, labels in sorted(classified.items()):
            print(f"  {ns}: {', '.join(sorted(labels))}")
        print()

        if unknown:
            print(f"UNKNOWN labels ({len(unknown)}):")
            for u in unknown:
                print(f"  - {u['label']}")
        else:
            print("UNKNOWN labels: 0 (PASS)")

        if pascal_violations:
            print(f"\nPascalCase violations ({len(pascal_violations)}):")
            for v in pascal_violations:
                print(f"  - {v['label']}: {v['issue']}")
        else:
            print("PascalCase violations: 0 (PASS)")

        if contamination:
            print(f"\nCross-contamination ({len(contamination)}):")
            for c in contamination:
                print(f"  - {c['name']}: {c['labels']}")
        else:
            print("Cross-contamination: 0 (PASS)")

        print(f"\nOverall: {'PASS' if report['overall_pass'] else 'FAIL'}")

        # Save JSON report
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            logger.info("Report saved: %s", output_path)

        if not report["overall_pass"]:
            sys.exit(1)

    finally:
        driver.close()


if __name__ == "__main__":
    main()
