#!/usr/bin/env python3
"""entity_id が NULL の Entity ノードを UUID5 で補完するスクリプト。

neo4j-write-rules.md の修復作業例外に該当。
--dry-run（デフォルト）で件数確認、--execute で明示的に実行。

Usage
-----
::

    # dry-run（デフォルト）
    python scripts/fix_entity_id_null.py --dry-run

    # 実行
    python scripts/fix_entity_id_null.py --execute
"""

from __future__ import annotations

import argparse
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
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
# ID 生成（pdf_pipeline/services/id_generator.py と同じロジック）
# ---------------------------------------------------------------------------


def generate_entity_id(name: str, entity_type: str) -> str:
    """Deterministic entity ID from name and type via UUID5.

    Parameters
    ----------
    name : str
        Entity name.
    entity_type : str
        Entity type.

    Returns
    -------
    str
        UUID5 string.
    """
    key = f"entity:{name}:{entity_type}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


# ---------------------------------------------------------------------------
# DataClass
# ---------------------------------------------------------------------------


@dataclass
class NullEntityRecord:
    """entity_id が NULL の Entity 情報。"""

    element_id: str
    name: str
    entity_type: str | None


# ---------------------------------------------------------------------------
# 検索・修正
# ---------------------------------------------------------------------------


def find_null_entity_ids(session: Any) -> list[NullEntityRecord]:
    """entity_id が NULL の Entity ノードを検索する。

    Parameters
    ----------
    session
        Neo4j セッション。

    Returns
    -------
    list[NullEntityRecord]
        該当ノードのリスト。
    """
    query = """
    MATCH (n:Entity)
    WHERE NOT 'Memory' IN labels(n)
    AND n.entity_id IS NULL
    RETURN elementId(n) AS eid, n.name AS name, n.entity_type AS entity_type
    """
    result = session.run(query)
    records = [
        NullEntityRecord(
            element_id=r["eid"],
            name=r["name"] or "",
            entity_type=r["entity_type"],
        )
        for r in result.data()
    ]
    logger.info("Found %d Entity nodes with NULL entity_id", len(records))
    return records


def fix_entity_ids(
    session: Any,
    entities: list[NullEntityRecord],
    *,
    dry_run: bool = True,
) -> int:
    """entity_id を UUID5 で補完する。

    Parameters
    ----------
    session
        Neo4j セッション。
    entities : list[NullEntityRecord]
        修正対象のエンティティリスト。
    dry_run : bool
        True の場合は実際の書き込みを行わない。

    Returns
    -------
    int
        修正した件数。
    """
    if not entities:
        logger.info("No entities to fix")
        return 0

    if dry_run:
        logger.info("[DRY-RUN] Would fix %d entities:", len(entities))
        for e in entities[:10]:
            et = e.entity_type or "unknown"
            eid = generate_entity_id(e.name, et)
            ekey = f"{e.name}::{et}"
            logger.info(
                "  %s -> entity_id=%s, entity_key=%s",
                e.name,
                eid[:12] + "...",
                ekey,
            )
        if len(entities) > 10:
            logger.info("  ... and %d more", len(entities) - 10)
        return 0

    fixed_count = 0
    skipped_count = 0
    batch_size = 100
    for i in range(0, len(entities), batch_size):
        batch = entities[i : i + batch_size]
        for entity in batch:
            et = entity.entity_type or "unknown"
            new_id = generate_entity_id(entity.name, et)
            new_key = f"{entity.name}::{et}"

            # entity_key のユニーク制約違反を回避:
            # 同じ entity_key を持つ別ノードが既に存在する場合はスキップ
            check_query = """
            MATCH (existing:Entity {entity_key: $entity_key})
            WHERE elementId(existing) <> $element_id
            RETURN count(existing) AS cnt
            """
            check_result = session.run(
                check_query,
                entity_key=new_key,
                element_id=entity.element_id,
            )
            if check_result.single()["cnt"] > 0:
                logger.warning(
                    "Skipped %s: entity_key '%s' already exists on another node",
                    entity.name,
                    new_key,
                )
                skipped_count += 1
                continue

            update_query = """
            MATCH (n:Entity)
            WHERE elementId(n) = $element_id
            SET n.entity_id = $entity_id,
                n.entity_key = $entity_key
            """
            session.run(
                update_query,
                element_id=entity.element_id,
                entity_id=new_id,
                entity_key=new_key,
            )
            fixed_count += 1

        logger.info("Fixed batch %d-%d (%d total)", i, i + len(batch), fixed_count)

    logger.info(
        "Fixed %d entities total (skipped %d due to duplicate entity_key)",
        fixed_count,
        skipped_count,
    )
    return fixed_count


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """コマンドライン引数を解析する。"""
    parser = argparse.ArgumentParser(
        description="entity_id が NULL の Entity ノードを UUID5 で補完",
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
    logger.info("fix_entity_id_null: mode=%s", mode)

    driver = create_driver(uri=args.neo4j_uri, password=args.neo4j_password)
    try:
        with driver.session() as session:
            entities = find_null_entity_ids(session)
            if not entities:
                logger.info("No entities with NULL entity_id found. Nothing to do.")
                return
            fixed = fix_entity_ids(session, entities, dry_run=args.dry_run)
            if not args.dry_run:
                logger.info("Successfully fixed %d entities", fixed)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
