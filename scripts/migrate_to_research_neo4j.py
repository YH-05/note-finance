#!/usr/bin/env python3
"""既存 Neo4j から Research Neo4j へ KG v2 データを移行するスクリプト.

移行対象ノード:
  Source, Claim, Chunk, Entity, FinancialDataPoint, Topic, Fact, FiscalPeriod, Insight

移行対象リレーション:
  MAKES_CLAIM, ABOUT, TAGGED, CONTAINS_CHUNK, RELATES_TO,
  FOR_PERIOD, HAS_DATAPOINT, STATES_FACT, COVERS, CITES, BASED_ON

Usage:
  python scripts/migrate_to_research_neo4j.py [--dry-run] [--batch-size 500]

環境変数:
  NEO4J_PASSWORD - Neo4j パスワード (全DB共通、デフォルト: gomasuke)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from neo4j import GraphDatabase
from neo4j.exceptions import ConstraintError

# --- 設定 ---

SOURCE_URI = "bolt://localhost:7687"
SOURCE_USER = "neo4j"

TARGET_URI = "bolt://localhost:7688"
TARGET_USER = "neo4j"

# 移行対象ラベル
MIGRATE_LABELS = [
    "Source",
    "Chunk",
    "Entity",
    "Topic",
    "Fact",
    "Claim",
    "FinancialDataPoint",
    "FiscalPeriod",
    "Insight",
]

# 移行対象リレーションシップタイプ
MIGRATE_RELS = [
    "MAKES_CLAIM",
    "ABOUT",
    "TAGGED",
    "CONTAINS_CHUNK",
    "RELATES_TO",
    "FOR_PERIOD",
    "HAS_DATAPOINT",
    "STATES_FACT",
    "COVERS",
    "CITES",
    "BASED_ON",
]


def get_logger():
    """簡易ロガー."""
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger("migrate")


logger = get_logger()


def export_nodes(
    source_driver, label: str, batch_size: int
) -> list[dict]:
    """ソースDBから指定ラベルのノードをエクスポート."""
    nodes = []
    with source_driver.session() as session:
        # Memory ラベルを持つノードは除外
        result = session.run(
            f"MATCH (n:{label}) "
            "WHERE NOT 'Memory' IN labels(n) AND NOT 'Archived' IN labels(n) "
            "RETURN n, labels(n) AS labels, elementId(n) AS eid"
        )
        for record in result:
            node = dict(record["n"])
            nodes.append(
                {
                    "labels": record["labels"],
                    "properties": node,
                    "element_id": record["eid"],
                }
            )
    logger.info(f"  {label}: {len(nodes)} ノードをエクスポート")
    return nodes


def export_relationships(
    source_driver, rel_type: str
) -> list[dict]:
    """ソースDBから指定タイプのリレーションシップをエクスポート."""
    rels = []
    with source_driver.session() as session:
        result = session.run(
            f"MATCH (a)-[r:{rel_type}]->(b) "
            "WHERE NOT 'Memory' IN labels(a) AND NOT 'Memory' IN labels(b) "
            "AND NOT 'Archived' IN labels(a) AND NOT 'Archived' IN labels(b) "
            "RETURN labels(a) AS a_labels, properties(a) AS a_props, "
            f"type(r) AS rel_type, properties(r) AS rel_props, "
            "labels(b) AS b_labels, properties(b) AS b_props"
        )
        for record in result:
            rels.append(
                {
                    "start_labels": record["a_labels"],
                    "start_props": dict(record["a_props"]),
                    "rel_type": record["rel_type"],
                    "rel_props": dict(record["rel_props"]) if record["rel_props"] else {},
                    "end_labels": record["b_labels"],
                    "end_props": dict(record["b_props"]),
                }
            )
    logger.info(f"  {rel_type}: {len(rels)} リレーションをエクスポート")
    return rels


def get_unique_key(label: str) -> str | None:
    """ラベルに対応するユニークキーを返す."""
    key_map = {
        "Source": "source_id",
        "Chunk": "chunk_id",
        "Entity": "entity_id",
        "Topic": "topic_id",
        "Fact": "fact_id",
        "Claim": "claim_id",
        "FinancialDataPoint": "datapoint_id",
        "FiscalPeriod": "period_id",
        "Insight": "insight_id",
    }
    return key_map.get(label)


def import_nodes(
    target_driver, label: str, nodes: list[dict], dry_run: bool = False
) -> int:
    """ターゲットDBにノードをインポート（MERGE ベース）."""
    if not nodes:
        return 0

    unique_key = get_unique_key(label)
    if not unique_key:
        logger.warning(f"  {label}: ユニークキーが不明、スキップ")
        return 0

    imported = 0
    skipped = 0
    with target_driver.session() as session:
        for node in nodes:
            props = node["properties"]
            if unique_key not in props:
                logger.warning(
                    f"  {label}: ユニークキー {unique_key} が見つかりません、スキップ"
                )
                continue

            if dry_run:
                imported += 1
                continue

            # datetime を文字列に変換（Neo4j ドライバの型互換性）
            clean_props = {}
            for k, v in props.items():
                if hasattr(v, "isoformat"):
                    clean_props[k] = v.isoformat()
                elif isinstance(v, list):
                    clean_props[k] = [
                        item.isoformat() if hasattr(item, "isoformat") else item
                        for item in v
                    ]
                else:
                    clean_props[k] = v

            query = (
                f"MERGE (n:{label} {{{unique_key}: $key_value}}) "
                "SET n += $props"
            )
            try:
                session.run(
                    query,
                    key_value=clean_props[unique_key],
                    props=clean_props,
                )
                imported += 1
            except ConstraintError as e:
                skipped += 1
                if skipped <= 3:
                    logger.warning(f"  {label}: 制約エラーでスキップ: {e}")

    if skipped:
        logger.warning(f"  {label}: {skipped} ノードを制約エラーでスキップ")
    logger.info(f"  {label}: {imported} ノードをインポート{'（dry-run）' if dry_run else ''}")
    return imported


def import_relationships(
    target_driver, rel_type: str, rels: list[dict], dry_run: bool = False
) -> int:
    """ターゲットDBにリレーションシップをインポート."""
    if not rels:
        return 0

    imported = 0
    skipped = 0
    with target_driver.session() as session:
        for rel in rels:
            # 開始・終了ノードのラベルとキーを特定
            start_label = _find_kg_label(rel["start_labels"])
            end_label = _find_kg_label(rel["end_labels"])

            if not start_label or not end_label:
                skipped += 1
                continue

            start_key = get_unique_key(start_label)
            end_key = get_unique_key(end_label)

            if not start_key or not end_key:
                skipped += 1
                continue

            start_key_val = rel["start_props"].get(start_key)
            end_key_val = rel["end_props"].get(end_key)

            if not start_key_val or not end_key_val:
                skipped += 1
                continue

            if dry_run:
                imported += 1
                continue

            # リレーションプロパティの datetime 変換
            rel_props = {}
            for k, v in rel["rel_props"].items():
                if hasattr(v, "isoformat"):
                    rel_props[k] = v.isoformat()
                else:
                    rel_props[k] = v

            query = (
                f"MATCH (a:{start_label} {{{start_key}: $start_val}}) "
                f"MATCH (b:{end_label} {{{end_key}: $end_val}}) "
                f"MERGE (a)-[r:{rel_type}]->(b) "
                "SET r += $rel_props"
            )
            session.run(
                query,
                start_val=start_key_val,
                end_val=end_key_val,
                rel_props=rel_props,
            )
            imported += 1

    if skipped:
        logger.info(f"  {rel_type}: {skipped} リレーションをスキップ（非KGノード）")
    logger.info(
        f"  {rel_type}: {imported} リレーションをインポート{'（dry-run）' if dry_run else ''}"
    )
    return imported


def _find_kg_label(labels: list[str]) -> str | None:
    """ラベルリストからKG v2ラベルを見つける."""
    for label in labels:
        if label in MIGRATE_LABELS:
            return label
    return None


def verify_migration(source_driver, target_driver) -> dict:
    """移行後の検証: ノード数を比較."""
    results = {}
    for label in MIGRATE_LABELS:
        with source_driver.session() as session:
            source_count = session.run(
                f"MATCH (n:{label}) "
                "WHERE NOT 'Memory' IN labels(n) AND NOT 'Archived' IN labels(n) "
                "RETURN count(n) AS c"
            ).single()["c"]

        with target_driver.session() as session:
            target_count = session.run(
                f"MATCH (n:{label}) RETURN count(n) AS c"
            ).single()["c"]

        status = "OK" if source_count == target_count else "MISMATCH"
        results[label] = {
            "source": source_count,
            "target": target_count,
            "status": status,
        }

    return results


def main():
    """メイン処理."""
    parser = argparse.ArgumentParser(description="Research Neo4j へのデータ移行")
    parser.add_argument("--dry-run", action="store_true", help="実際の書き込みを行わない")
    parser.add_argument("--batch-size", type=int, default=500, help="バッチサイズ")
    parser.add_argument(
        "--source-password",
        default=None,
        help="ソースDB パスワード (env: NEO4J_PASSWORD)",
    )
    parser.add_argument(
        "--target-password",
        default=None,
        help="ターゲットDB パスワード (env: NEO4J_PASSWORD)",
    )
    parser.add_argument("--verify-only", action="store_true", help="検証のみ実行")
    parser.add_argument(
        "--export-json",
        type=str,
        default=None,
        help="エクスポートデータをJSONファイルに保存",
    )
    args = parser.parse_args()

    import os

    source_password = args.source_password or os.environ.get("NEO4J_PASSWORD", "")
    target_password = args.target_password or os.environ.get(
        "NEO4J_PASSWORD", "gomasuke"
    )

    if not source_password:
        logger.error("NEO4J_PASSWORD が設定されていません")
        sys.exit(1)

    # ドライバ接続
    logger.info("=== Research Neo4j 移行ツール ===")
    logger.info(f"ソース: {SOURCE_URI}")
    logger.info(f"ターゲット: {TARGET_URI}")
    logger.info(f"モード: {'dry-run' if args.dry_run else 'LIVE'}")

    source_driver = GraphDatabase.driver(
        SOURCE_URI, auth=(SOURCE_USER, source_password)
    )
    target_driver = GraphDatabase.driver(
        TARGET_URI, auth=(TARGET_USER, target_password)
    )

    # 接続テスト
    try:
        with source_driver.session() as s:
            s.run("RETURN 1")
        logger.info("ソースDB: 接続OK")
    except Exception as e:
        logger.error(f"ソースDB接続失敗: {e}")
        sys.exit(1)

    try:
        with target_driver.session() as s:
            s.run("RETURN 1")
        logger.info("ターゲットDB: 接続OK")
    except Exception as e:
        logger.error(f"ターゲットDB接続失敗: {e}")
        sys.exit(1)

    if args.verify_only:
        logger.info("\n--- 検証 ---")
        results = verify_migration(source_driver, target_driver)
        for label, info in results.items():
            logger.info(
                f"  {label}: source={info['source']}, target={info['target']} [{info['status']}]"
            )
        source_driver.close()
        target_driver.close()
        return

    # Phase 1: ノードエクスポート
    logger.info("\n=== Phase 1: ノードエクスポート ===")
    all_nodes: dict[str, list[dict]] = {}
    for label in MIGRATE_LABELS:
        all_nodes[label] = export_nodes(source_driver, label, args.batch_size)

    # Phase 2: リレーションエクスポート
    logger.info("\n=== Phase 2: リレーションエクスポート ===")
    all_rels: dict[str, list[dict]] = {}
    for rel_type in MIGRATE_RELS:
        all_rels[rel_type] = export_relationships(source_driver, rel_type)

    # JSON エクスポート（オプション）
    if args.export_json:
        export_data = {
            "exported_at": datetime.now().isoformat(),
            "source": SOURCE_URI,
            "nodes": {
                label: [
                    {
                        "labels": n["labels"],
                        "properties": {
                            k: v.isoformat() if hasattr(v, "isoformat") else v
                            for k, v in n["properties"].items()
                        },
                    }
                    for n in nodes
                ]
                for label, nodes in all_nodes.items()
            },
            "relationships": {
                rel_type: [
                    {
                        "start_labels": r["start_labels"],
                        "start_props": {
                            k: v.isoformat() if hasattr(v, "isoformat") else v
                            for k, v in r["start_props"].items()
                        },
                        "rel_type": r["rel_type"],
                        "rel_props": {
                            k: v.isoformat() if hasattr(v, "isoformat") else v
                            for k, v in r["rel_props"].items()
                        },
                        "end_labels": r["end_labels"],
                        "end_props": {
                            k: v.isoformat() if hasattr(v, "isoformat") else v
                            for k, v in r["end_props"].items()
                        },
                    }
                    for r in rels
                ]
                for rel_type, rels in all_rels.items()
            },
        }
        export_path = Path(args.export_json)
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with open(export_path, "w") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        logger.info(f"\nエクスポートデータを保存: {export_path}")

    # Phase 3: ノードインポート
    logger.info("\n=== Phase 3: ノードインポート ===")
    total_nodes = 0
    for label in MIGRATE_LABELS:
        total_nodes += import_nodes(
            target_driver, label, all_nodes[label], dry_run=args.dry_run
        )

    # Phase 4: リレーションインポート
    logger.info("\n=== Phase 4: リレーションインポート ===")
    total_rels = 0
    for rel_type in MIGRATE_RELS:
        total_rels += import_relationships(
            target_driver, rel_type, all_rels[rel_type], dry_run=args.dry_run
        )

    # Phase 5: 検証
    if not args.dry_run:
        logger.info("\n=== Phase 5: 移行検証 ===")
        results = verify_migration(source_driver, target_driver)
        all_ok = True
        for label, info in results.items():
            status_mark = "✓" if info["status"] == "OK" else "✗"
            logger.info(
                f"  {status_mark} {label}: source={info['source']}, target={info['target']}"
            )
            if info["status"] != "OK":
                all_ok = False

        if all_ok:
            logger.info("\n移行完了: 全データが正常に移行されました")
        else:
            logger.warning("\n移行完了: 一部データに不一致があります")

    # サマリー
    logger.info(f"\n=== サマリー ===")
    logger.info(f"  ノード: {total_nodes}")
    logger.info(f"  リレーション: {total_rels}")

    source_driver.close()
    target_driver.close()


if __name__ == "__main__":
    main()
