#!/usr/bin/env python3
"""Metric マスターノードを research-neo4j に投入し、既存 FinancialDataPoint と MEASURES リレーションで紐づける.

Usage:
  uv run python scripts/apply_metric_master.py [--dry-run]

処理フロー:
  1. metric_master.json を読み込み
  2. Metric ノードを MERGE で作成
  3. 既存 FinancialDataPoint.metric_name を aliases でファジーマッチ
  4. マッチしたペアに (FinancialDataPoint)-[:MEASURES]->(Metric) を作成
  5. マッチしなかった metric_name を未分類として報告
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from neo4j import GraphDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("metric-master")

URI = "bolt://localhost:7688"
USER = "neo4j"

MASTER_PATH = Path("data/config/metric_master.json")


def load_master() -> list[dict]:
    """metric_master.json を読み込む."""
    with open(MASTER_PATH) as f:
        data = json.load(f)
    return data["metrics"]


def build_alias_index(metrics: list[dict]) -> dict[str, str]:
    """alias テキスト → metric_id のルックアップテーブルを構築.

    完全一致 + 小文字正規化で検索する。
    """
    index: dict[str, str] = {}
    for m in metrics:
        for alias in m["aliases"]:
            key = alias.strip().lower()
            if key in index:
                logger.warning(
                    f"エイリアス衝突: '{alias}' → {index[key]} と {m['metric_id']}"
                )
            index[key] = m["metric_id"]
    return index


def main() -> None:
    """メイン処理."""
    parser = argparse.ArgumentParser(description="Metric マスター投入")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--password", default=None)
    args = parser.parse_args()

    password = args.password or os.environ.get("NEO4J_PASSWORD", "gomasuke")
    metrics = load_master()
    alias_index = build_alias_index(metrics)

    logger.info(f"Metric マスター: {len(metrics)} 指標, {len(alias_index)} エイリアス")

    driver = GraphDatabase.driver(URI, auth=(USER, password))

    # 接続テスト
    with driver.session() as s:
        s.run("RETURN 1")
    logger.info("research-neo4j 接続OK")

    # Phase 1: Metric 制約・インデックス作成
    logger.info("\n=== Phase 1: 制約・インデックス ===")
    with driver.session() as s:
        s.run(
            "CREATE CONSTRAINT metric_id IF NOT EXISTS "
            "FOR (m:Metric) REQUIRE m.metric_id IS UNIQUE"
        )
        s.run(
            "CREATE CONSTRAINT metric_canonical IF NOT EXISTS "
            "FOR (m:Metric) REQUIRE m.canonical_name IS UNIQUE"
        )
        s.run(
            "CREATE INDEX metric_category IF NOT EXISTS "
            "FOR (m:Metric) ON (m.category)"
        )
    logger.info("  制約・インデックス作成完了")

    # Phase 2: Metric ノード MERGE
    logger.info("\n=== Phase 2: Metric ノード作成 ===")
    created = 0
    with driver.session() as s:
        for m in metrics:
            if args.dry_run:
                created += 1
                continue
            s.run(
                "MERGE (met:Metric {metric_id: $mid}) "
                "SET met.canonical_name = $cname, "
                "    met.display_name = $dname, "
                "    met.category = $cat, "
                "    met.unit_standard = $unit, "
                "    met.comparable_across = $comp, "
                "    met.aliases = $aliases",
                mid=m["metric_id"],
                cname=m["canonical_name"],
                dname=m["display_name"],
                cat=m["category"],
                unit=m["unit_standard"],
                comp=m["comparable_across"],
                aliases=m["aliases"],
            )
            created += 1
    logger.info(f"  {created} Metric ノード作成{'（dry-run）' if args.dry_run else ''}")

    # Phase 3: 既存 FinancialDataPoint → Metric マッチング
    logger.info("\n=== Phase 3: FinancialDataPoint → Metric マッチング ===")
    with driver.session() as s:
        result = s.run(
            "MATCH (dp:FinancialDataPoint) "
            "RETURN DISTINCT dp.metric_name AS metric_name, count(dp) AS cnt "
            "ORDER BY cnt DESC"
        )
        all_metrics = [(r["metric_name"], r["cnt"]) for r in result]

    matched = 0
    unmatched = []
    matched_pairs: list[tuple[str, str]] = []  # (metric_name, metric_id)

    for metric_name, cnt in all_metrics:
        if not metric_name:
            unmatched.append((metric_name, cnt))
            continue
        key = metric_name.strip().lower()
        if key in alias_index:
            matched += cnt
            matched_pairs.append((metric_name, alias_index[key]))
        else:
            unmatched.append((metric_name, cnt))

    logger.info(f"  マッチ: {matched} データポイント ({len(matched_pairs)} 指標名)")
    if unmatched:
        logger.info(f"  未マッチ: {sum(c for _, c in unmatched)} データポイント ({len(unmatched)} 指標名)")
        for name, cnt in unmatched:
            logger.info(f"    - '{name}' ({cnt}件)")

    # Phase 4: MEASURES リレーション作成
    logger.info("\n=== Phase 4: MEASURES リレーション作成 ===")
    rel_count = 0
    with driver.session() as s:
        for metric_name, metric_id in matched_pairs:
            if args.dry_run:
                result = s.run(
                    "MATCH (dp:FinancialDataPoint {metric_name: $mname}) "
                    "RETURN count(dp) AS cnt",
                    mname=metric_name,
                )
                rel_count += result.single()["cnt"]
                continue
            result = s.run(
                "MATCH (dp:FinancialDataPoint {metric_name: $mname}) "
                "MATCH (met:Metric {metric_id: $mid}) "
                "MERGE (dp)-[:MEASURES]->(met) "
                "RETURN count(dp) AS cnt",
                mname=metric_name,
                mid=metric_id,
            )
            rel_count += result.single()["cnt"]
    logger.info(f"  {rel_count} MEASURES リレーション作成{'（dry-run）' if args.dry_run else ''}")

    # Phase 5: 検証
    if not args.dry_run:
        logger.info("\n=== Phase 5: 検証 ===")
        with driver.session() as s:
            total_dp = s.run(
                "MATCH (dp:FinancialDataPoint) RETURN count(dp) AS c"
            ).single()["c"]
            linked_dp = s.run(
                "MATCH (dp:FinancialDataPoint)-[:MEASURES]->(:Metric) "
                "RETURN count(DISTINCT dp) AS c"
            ).single()["c"]
            metric_count = s.run(
                "MATCH (m:Metric) RETURN count(m) AS c"
            ).single()["c"]
            used_metrics = s.run(
                "MATCH (:FinancialDataPoint)-[:MEASURES]->(m:Metric) "
                "RETURN count(DISTINCT m) AS c"
            ).single()["c"]

        coverage = (linked_dp / total_dp * 100) if total_dp > 0 else 0
        logger.info(f"  Metric ノード: {metric_count}")
        logger.info(f"  使用中 Metric: {used_metrics}")
        logger.info(f"  FinancialDataPoint 総数: {total_dp}")
        logger.info(f"  MEASURES リンク済み: {linked_dp} ({coverage:.1f}%)")
        logger.info(f"  未リンク: {total_dp - linked_dp}")

    # サマリー
    logger.info("\n=== サマリー ===")
    logger.info(f"  Metric ノード: {created}")
    logger.info(f"  MEASURES リレーション: {rel_count}")
    if unmatched:
        logger.info(f"  未分類指標（要確認）: {len(unmatched)} 件")

    driver.close()


if __name__ == "__main__":
    main()
