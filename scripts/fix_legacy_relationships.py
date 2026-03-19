#!/usr/bin/env python3
"""レガシーリレーションタイプをスキーマ準拠にリネームするスクリプト。

Neo4j はリレーションタイプの直接リネームが不可のため、
CREATE new → COPY properties → DELETE old パターンで処理する。

neo4j-write-rules.md の修復作業例外に該当。
--dry-run（デフォルト）で件数確認、--execute で明示的に実行。

Usage
-----
::

    # dry-run（デフォルト）
    python scripts/fix_legacy_relationships.py --dry-run

    # 実行
    python scripts/fix_legacy_relationships.py --execute
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any

from neo4j_utils import create_driver

try:
    from quants.utils.logging_config import get_logger

    logger = get_logger(__name__)
except ImportError:
    import logging

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

LEGACY_MAPPING: dict[str, str] = {
    "RELATED_TO": "RELATES_TO",
    "HAS_FACT": "STATES_FACT",
    "TAGGED_WITH": "TAGGED",
}
"""レガシー → 新リレーションタイプのマッピング。"""

BATCH_SIZE = 100
"""トランザクションタイムアウト防止のバッチサイズ。"""


# ---------------------------------------------------------------------------
# DataClass
# ---------------------------------------------------------------------------


@dataclass
class LegacyRelInfo:
    """レガシーリレーションの集計情報。"""

    old_type: str
    new_type: str
    count: int


# ---------------------------------------------------------------------------
# 検索・修正
# ---------------------------------------------------------------------------


def find_legacy_relationships(session: Any) -> list[LegacyRelInfo]:
    """レガシーリレーションの件数を集計する。

    Parameters
    ----------
    session
        Neo4j セッション。

    Returns
    -------
    list[LegacyRelInfo]
        レガシーリレーションの集計リスト。
    """
    results: list[LegacyRelInfo] = []

    for old_type, new_type in LEGACY_MAPPING.items():
        query = f"""
        MATCH (a)-[r:{old_type}]->(b)
        WHERE NOT 'Memory' IN labels(a) AND NOT 'Memory' IN labels(b)
        RETURN count(r) AS cnt
        """
        result = session.run(query)
        count: int = result.single()["cnt"]
        if count > 0:
            results.append(LegacyRelInfo(old_type=old_type, new_type=new_type, count=count))
            logger.info("Found %d %s relationships (→ %s)", count, old_type, new_type)

    total = sum(r.count for r in results)
    logger.info("Total legacy relationships: %d", total)
    return results


def fix_legacy_relationships(
    session: Any,
    legacy_rels: list[LegacyRelInfo],
    *,
    dry_run: bool = True,
    batch_size: int = BATCH_SIZE,
) -> int:
    """レガシーリレーションをリネームする。

    Neo4j はリレーションタイプの直接変更不可のため、
    新タイプで CREATE → プロパティコピー → 旧リレーション DELETE のパターン。

    Parameters
    ----------
    session
        Neo4j セッション。
    legacy_rels : list[LegacyRelInfo]
        修正対象のレガシーリレーション情報。
    dry_run : bool
        True の場合は実際の書き込みを行わない。
    batch_size : int
        バッチサイズ。

    Returns
    -------
    int
        修正した件数。
    """
    if not legacy_rels:
        logger.info("No legacy relationships to fix")
        return 0

    if dry_run:
        logger.info("[DRY-RUN] Would fix the following relationships:")
        for rel in legacy_rels:
            logger.info("  %s → %s: %d件", rel.old_type, rel.new_type, rel.count)
        return 0

    total_fixed = 0

    for rel in legacy_rels:
        remaining = rel.count
        while remaining > 0:
            # AIDEV-NOTE: old_type/new_type は LEGACY_MAPPING 由来の信頼済み定数
            # Cypher インジェクションのリスクはない
            query = f"""
            MATCH (a)-[r:{rel.old_type}]->(b)
            WHERE NOT 'Memory' IN labels(a) AND NOT 'Memory' IN labels(b)
            WITH a, r, b LIMIT $batch_size
            CREATE (a)-[r2:{rel.new_type}]->(b)
            SET r2 = properties(r)
            DELETE r
            RETURN count(r2) AS migrated
            """
            result = session.run(query, batch_size=batch_size)
            migrated: int = result.single()["migrated"]
            total_fixed += migrated
            remaining -= migrated
            logger.info(
                "Migrated %d %s → %s (remaining: ~%d)",
                migrated,
                rel.old_type,
                rel.new_type,
                max(remaining, 0),
            )
            if migrated == 0:
                break

    logger.info("Total migrated: %d relationships", total_fixed)
    return total_fixed


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """コマンドライン引数を解析する。"""
    parser = argparse.ArgumentParser(
        description="レガシーリレーションタイプをスキーマ準拠にリネーム",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="実際に修正を実行（デフォルトは dry-run）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="dry-run モード（デフォルト）",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help=f"バッチサイズ（デフォルト: {BATCH_SIZE}）",
    )
    parser.add_argument(
        "--neo4j-uri",
        default="bolt://localhost:7688",
        help="Neo4j 接続 URI",
    )
    parser.add_argument(
        "--neo4j-password",
        default=None,
        help="Neo4j パスワード",
    )
    args = parser.parse_args(argv)
    if args.execute:
        args.dry_run = False
    return args


def main() -> None:
    """エントリーポイント。"""
    args = parse_args()
    mode = "DRY-RUN" if args.dry_run else "EXECUTE"
    logger.info("fix_legacy_relationships: mode=%s", mode)

    driver = create_driver(uri=args.neo4j_uri, password=args.neo4j_password)
    try:
        with driver.session() as session:
            legacy_rels = find_legacy_relationships(session)
            if not legacy_rels:
                logger.info("No legacy relationships found. Nothing to do.")
                return
            fixed = fix_legacy_relationships(
                session,
                legacy_rels,
                dry_run=args.dry_run,
                batch_size=args.batch_size,
            )
            if not args.dry_run:
                logger.info("Successfully migrated %d relationships", fixed)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
