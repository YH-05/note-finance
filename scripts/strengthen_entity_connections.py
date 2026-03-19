#!/usr/bin/env python3
"""Entity 孤立ノード接続強化スクリプト (Phase 4-B).

Phase 4-A の計測結果に基づき、Entity-Entity 間の接続を強化する。
3 つの手法を組み合わせて孤立 Entity ノードの接続率を向上させる。

手法:
    1. CO_MENTIONED_WITH 閾値緩和 (shared >= 1)
    2. SHARES_TOPIC 拡充 (共有 Topic 数 >= 2)
    3. 全手法の組み合わせ (デフォルト)

Usage
-----
::

    # ドライラン（推奨：まず変更内容を確認）
    python scripts/strengthen_entity_connections.py --dry-run

    # 全手法で実行
    python scripts/strengthen_entity_connections.py

    # CO_MENTIONED_WITH 閾値緩和のみ
    python scripts/strengthen_entity_connections.py --method co_mention

    # Topic 媒介のみ
    python scripts/strengthen_entity_connections.py --method topic

    # 件数制限付き
    python scripts/strengthen_entity_connections.py --method co_mention --limit 50

    # 接続先を指定
    python scripts/strengthen_entity_connections.py --neo4j-uri bolt://remote:7688
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Any

from neo4j_utils import create_driver

try:
    from quants.utils.logging_config import get_logger

    logger = get_logger(__name__)
except ImportError:
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

ENTITY_RELATIONSHIP_TYPES: list[str] = [
    "CO_MENTIONED_WITH",
    "SHARES_TOPIC",
    "COMPETES_WITH",
    "PARTNERS_WITH",
    "SUBSIDIARY_OF",
    "CUSTOMER_OF",
    "INVESTED_IN",
    "LED_BY",
    "OPERATES_IN",
    "INFLUENCES",
    "SUPPLIER_OF",
]
"""Entity-Entity 間の直接リレーションタイプ一覧。

Phase 1-3 で定義された 10 種 + Phase 4-B で追加検討の SUPPLIER_OF。
孤立 Entity の判定および既存リレーション重複チェックに使用する。
"""


# ---------------------------------------------------------------------------
# DataClasses
# ---------------------------------------------------------------------------


@dataclass
class MethodStats:
    """手法ごとの実行統計。

    Attributes
    ----------
    method : str
        手法名（"co_mention", "topic"）。
    candidates_found : int
        検出された候補ペア数。
    relationships_created : int
        作成されたリレーション数。
    dry_run : bool
        ドライランモードかどうか。
    """

    method: str
    candidates_found: int
    relationships_created: int
    dry_run: bool


@dataclass
class ConnectionResult:
    """接続強化の全体結果。

    Attributes
    ----------
    method : str
        使用した手法名。
    relationships_added : int
        追加されたリレーション数。
    before_isolated : int
        処理前の孤立 Entity 数。
    after_isolated : int
        処理後の孤立 Entity 数。
    """

    method: str
    relationships_added: int
    before_isolated: int
    after_isolated: int


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """コマンドライン引数をパースする。

    Parameters
    ----------
    argv : list[str] | None
        引数リスト。``None`` の場合は ``sys.argv[1:]`` を使用する。

    Returns
    -------
    argparse.Namespace
        パース結果。
    """
    parser = argparse.ArgumentParser(
        description="Entity 孤立ノード接続強化 (Phase 4-B)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="変更を適用せず候補のみ表示する",
    )
    parser.add_argument(
        "--method",
        choices=["co_mention", "topic", "all"],
        default="all",
        help="使用する接続強化手法 (デフォルト: all)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="処理する候補ペアの上限数",
    )
    parser.add_argument(
        "--neo4j-uri",
        default="bolt://localhost:7688",
        help="Neo4j 接続 URI (デフォルト: bolt://localhost:7688)",
    )
    parser.add_argument(
        "--neo4j-password",
        default=None,
        help="Neo4j パスワード（環境変数 NEO4J_PASSWORD から取得）",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# 計測関数
# ---------------------------------------------------------------------------


def count_isolated_entities(session: Any) -> int:
    """Entity-Entity 間リレーションを持たない孤立 Entity 数をカウントする。

    Memory ノードを除外してカウントする。
    Entity 同士の直接リレーション（CO_MENTIONED_WITH, SHARES_TOPIC,
    COMPETES_WITH 等）を持たない Entity を孤立とみなす。

    Parameters
    ----------
    session
        Neo4j セッション。

    Returns
    -------
    int
        孤立 Entity 数。
    """
    # AIDEV-NOTE: type(r) IN [...] は ENTITY_RELATIONSHIP_TYPES 定数と同期すること
    query = """
    MATCH (e:Entity)
    WHERE NOT 'Memory' IN labels(e)
      AND NOT EXISTS {
        MATCH (e)-[r]-(other:Entity)
        WHERE NOT 'Memory' IN labels(other)
          AND type(r) IN [
            'CO_MENTIONED_WITH', 'SHARES_TOPIC',
            'COMPETES_WITH', 'PARTNERS_WITH', 'SUBSIDIARY_OF',
            'CUSTOMER_OF', 'INVESTED_IN', 'LED_BY',
            'OPERATES_IN', 'INFLUENCES', 'SUPPLIER_OF'
          ]
      }
    RETURN count(e) AS count
    """
    result = session.run(query)
    count: int = result.single()["count"]
    return count


# ---------------------------------------------------------------------------
# 接続強化手法
# ---------------------------------------------------------------------------

_MERGE_BATCH_SIZE = 500
"""UNWIND MERGE のバッチサイズ。"""


def _execute_strengthen_method(
    session: Any,
    find_query: str,
    merge_query: str,
    method_name: str,
    count_key: str,
    *,
    dry_run: bool = False,
    limit: int | None = None,
) -> MethodStats:
    """接続強化メソッドの共通実行フローを処理する。

    候補取得 -> limit 適用 -> dry_run 分岐 -> UNWIND バッチ MERGE -> 統計返却
    のパターンを共通化する。

    Parameters
    ----------
    session
        Neo4j セッション。
    find_query : str
        候補ペア検索用 Cypher クエリ。
    merge_query : str
        UNWIND バッチ MERGE 用 Cypher クエリ。
    method_name : str
        手法名（"co_mention", "topic"）。
    count_key : str
        候補レコード内のカウント値キー（"shared", "shared_topics"）。
    dry_run : bool
        True の場合はリレーション作成を行わない。
    limit : int | None
        処理する候補ペアの上限。None の場合は全件処理。

    Returns
    -------
    MethodStats
        実行統計。
    """
    candidates_result = session.run(find_query)
    candidates = list(candidates_result)

    if limit is not None:
        candidates = candidates[:limit]

    candidates_found = len(candidates)
    relationships_created = 0

    if dry_run:
        for c in candidates:
            logger.info(
                "  [DRY-RUN] %s: %s <-> %s (%s=%d)",
                method_name,
                c["e1_key"],
                c["e2_key"],
                count_key,
                c[count_key],
            )
        logger.info(
            "%s: %d 候補ペア検出 (dry-run)",
            method_name,
            candidates_found,
        )
    else:
        # HIGH-002: UNWIND バッチ MERGE（バッチサイズ 500 件ずつ）
        for i in range(0, len(candidates), _MERGE_BATCH_SIZE):
            batch = [
                {
                    "e1_key": c["e1_key"],
                    "e2_key": c["e2_key"],
                    "count_val": c[count_key],
                }
                for c in candidates[i : i + _MERGE_BATCH_SIZE]
            ]
            result = session.run(
                merge_query,
                batch=batch,
                method_label=method_name,
            )
            record = result.single()
            relationships_created += record["created"] if record else 0

        logger.info(
            "%s: %d 候補 → %d リレーション作成",
            method_name,
            candidates_found,
            relationships_created,
        )

    return MethodStats(
        method=method_name,
        candidates_found=candidates_found,
        relationships_created=relationships_created,
        dry_run=dry_run,
    )


def lower_co_mention_threshold(
    session: Any,
    *,
    dry_run: bool = False,
    limit: int | None = None,
) -> MethodStats:
    """CO_MENTIONED_WITH 閾値を緩和して新規リレーションを追加する。

    既存の CO_MENTIONED_WITH は shared >= 2 で作成済み。
    shared == 1 のペアを追加することで接続を拡充する。
    既に何らかの Entity-Entity リレーションを持つペアはスキップする。

    Parameters
    ----------
    session
        Neo4j セッション。
    dry_run : bool
        True の場合はリレーション作成を行わない。
    limit : int | None
        処理する候補ペアの上限。None の場合は全件処理。

    Returns
    -------
    MethodStats
        実行統計。
    """
    # AIDEV-NOTE: type(existing) IN [...] は ENTITY_RELATIONSHIP_TYPES 定数と同期すること
    find_query = """
    MATCH (e1:Entity)<-[:ABOUT]-(c:Claim)-[:ABOUT]->(e2:Entity)
    WHERE NOT 'Memory' IN labels(e1)
      AND NOT 'Memory' IN labels(e2)
      AND id(e1) < id(e2)
      AND NOT EXISTS {
        MATCH (e1)-[existing]-(e2)
        WHERE type(existing) IN [
          'CO_MENTIONED_WITH', 'SHARES_TOPIC',
          'COMPETES_WITH', 'PARTNERS_WITH', 'SUBSIDIARY_OF',
          'CUSTOMER_OF', 'INVESTED_IN', 'LED_BY',
          'OPERATES_IN', 'INFLUENCES', 'SUPPLIER_OF'
        ]
      }
    WITH e1, e2, count(DISTINCT c) AS shared
    WHERE shared >= 1
    RETURN e1.entity_key AS e1_key, e2.entity_key AS e2_key, shared
    ORDER BY shared DESC
    """

    # AIDEV-NOTE: rel_type は定数文字列なので f-string 埋め込みは安全
    merge_query = """
    UNWIND $batch AS c
    MATCH (e1:Entity {entity_key: c.e1_key})
    MATCH (e2:Entity {entity_key: c.e2_key})
    WHERE NOT 'Memory' IN labels(e1)
      AND NOT 'Memory' IN labels(e2)
    MERGE (e1)-[r:CO_MENTIONED_WITH]-(e2)
    ON CREATE SET r.shared_claims = c.count_val,
                  r.method = $method_label,
                  r.created_at = datetime()
    RETURN count(r) AS created
    """

    return _execute_strengthen_method(
        session,
        find_query,
        merge_query,
        method_name="co_mention",
        count_key="shared",
        dry_run=dry_run,
        limit=limit,
    )


def strengthen_topic_links(
    session: Any,
    *,
    dry_run: bool = False,
    limit: int | None = None,
) -> MethodStats:
    """Topic 媒介で Entity 間の SHARES_TOPIC リレーションを拡充する。

    同じ Topic に TAGGED されている Entity ペアで、まだ SHARES_TOPIC
    リレーションを持たないものを検出して追加する。
    共有 Topic 数 >= 2 の既存閾値を >= 1 に緩和する。

    Parameters
    ----------
    session
        Neo4j セッション。
    dry_run : bool
        True の場合はリレーション作成を行わない。
    limit : int | None
        処理する候補ペアの上限。None の場合は全件処理。

    Returns
    -------
    MethodStats
        実行統計。
    """
    find_query = """
    MATCH (e1:Entity)-[:TAGGED]->(t:Topic)<-[:TAGGED]-(e2:Entity)
    WHERE NOT 'Memory' IN labels(e1)
      AND NOT 'Memory' IN labels(e2)
      AND id(e1) < id(e2)
      AND NOT EXISTS {
        MATCH (e1)-[existing:SHARES_TOPIC]-(e2)
      }
    WITH e1, e2, count(DISTINCT t) AS shared_topics
    WHERE shared_topics >= 1
    RETURN e1.entity_key AS e1_key, e2.entity_key AS e2_key, shared_topics
    ORDER BY shared_topics DESC
    """

    merge_query = """
    UNWIND $batch AS c
    MATCH (e1:Entity {entity_key: c.e1_key})
    MATCH (e2:Entity {entity_key: c.e2_key})
    WHERE NOT 'Memory' IN labels(e1)
      AND NOT 'Memory' IN labels(e2)
    MERGE (e1)-[r:SHARES_TOPIC]-(e2)
    ON CREATE SET r.shared_count = c.count_val,
                  r.method = $method_label,
                  r.created_at = datetime()
    RETURN count(r) AS created
    """

    return _execute_strengthen_method(
        session,
        find_query,
        merge_query,
        method_name="topic",
        count_key="shared_topics",
        dry_run=dry_run,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------


def run(args: argparse.Namespace) -> ConnectionResult:
    """接続強化メイン処理を実行する。

    Parameters
    ----------
    args : argparse.Namespace
        CLI 引数。

    Returns
    -------
    ConnectionResult
        接続強化の全体結果。
    """
    driver = create_driver(
        uri=args.neo4j_uri,
        password=args.neo4j_password,
    )

    try:
        total_added = 0
        all_stats: list[MethodStats] = []

        with driver.session() as session:
            # 処理前の孤立 Entity 数
            before_count = count_isolated_entities(session)
            logger.info("処理前 孤立Entity数: %d", before_count)

            # 手法実行
            if args.method in ("co_mention", "all"):
                stats = lower_co_mention_threshold(
                    session,
                    dry_run=args.dry_run,
                    limit=args.limit,
                )
                all_stats.append(stats)
                total_added += stats.relationships_created

            if args.method in ("topic", "all"):
                stats = strengthen_topic_links(
                    session,
                    dry_run=args.dry_run,
                    limit=args.limit,
                )
                all_stats.append(stats)
                total_added += stats.relationships_created

            # 処理後の孤立 Entity 数
            after_count = count_isolated_entities(session)
            logger.info("処理後 孤立Entity数: %d", after_count)

        # サマリー出力
        logger.info("=" * 60)
        logger.info("=== 接続強化サマリー ===")
        logger.info("=" * 60)
        for s in all_stats:
            mode = " (dry-run)" if s.dry_run else ""
            logger.info(
                "  [%s] 候補: %d, 作成: %d%s",
                s.method,
                s.candidates_found,
                s.relationships_created,
                mode,
            )
        logger.info("  追加リレーション合計: %d", total_added)
        logger.info(
            "  孤立Entity: %d → %d (-%d)",
            before_count,
            after_count,
            before_count - after_count,
        )
        if before_count > 0:
            reduction_pct = (before_count - after_count) / before_count * 100
            logger.info("  削減率: %.1f%%", reduction_pct)
        logger.info("=" * 60)

        return ConnectionResult(
            method=args.method,
            relationships_added=total_added,
            before_isolated=before_count,
            after_isolated=after_count,
        )

    finally:
        driver.close()


def main() -> None:
    """エントリポイント。"""
    args = parse_args()
    run(args)


if __name__ == "__main__":
    main()
