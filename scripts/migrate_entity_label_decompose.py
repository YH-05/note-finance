#!/usr/bin/env python3
"""Entity ラベル分解・entity_key 廃止・NODE KEY 制約導入スクリプト。

Wave 4 移行スクリプト。以下のフェーズを順次実行する:

1. **Entity:Sector テーマ的ノード → Topic 変換**: テーマ的な Sector ノード（~69件）に
   Topic ラベルを追加し Sector ラベルを削除する。
2. **NODE KEY 制約作成**: 13 個別ラベル全てに NODE KEY 制約を作成する。
3. **entity_key プロパティ削除**: 個別ラベル付きノードから entity_key プロパティを削除する。
4. **EntityType ノード削除**: EntityType ノード(~1,597件) と IS_TYPE リレーションを削除する。
5. **InstrumentClass ノード削除**: InstrumentClass ノード(~106件) と
   IS_INSTRUMENT_CLASS リレーションを削除する。
6. **Entity ラベル削除**: 個別ラベル付きノードから Entity ラベルを削除する（最終ステップ）。

Usage
-----
::

    # 対象件数確認（DB への書き込みなし）
    uv run python scripts/migrate_entity_label_decompose.py --dry-run

    # 本番実行（全フェーズ）
    uv run python scripts/migrate_entity_label_decompose.py

    # 特定フェーズのみ実行
    uv run python scripts/migrate_entity_label_decompose.py --phase sector_to_topic
    uv run python scripts/migrate_entity_label_decompose.py --phase node_key
    uv run python scripts/migrate_entity_label_decompose.py --phase remove_entity_key
    uv run python scripts/migrate_entity_label_decompose.py --phase delete_entity_type
    uv run python scripts/migrate_entity_label_decompose.py --phase delete_instrument_class
    uv run python scripts/migrate_entity_label_decompose.py --phase remove_entity_label

    # 接続先を指定
    uv run python scripts/migrate_entity_label_decompose.py --neo4j-uri bolt://localhost:7688

設計方針
--------
- 冪等実行可能: 制約作成は IF NOT EXISTS、プロパティ削除は IS NOT NULL チェック
- --dry-run フラグで書き込みをスキップして件数のみ確認
- フェーズ 6 (Entity ラベル削除) は明示的に --run-final-phase フラグを指定しないと実行しない
- neo4j-write-rules.md 例外適用: 本スクリプトは移行専用（ユーザー明示承認済み）
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from typing import Any

try:
    from neo4j import GraphDatabase
except ImportError:
    print("neo4j driver not installed. Run: uv add neo4j")
    sys.exit(1)

try:
    from utils_core.logging.config import get_logger

    logger = get_logger(__name__)
except ImportError:
    import logging

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_NEO4J_URI = "bolt://localhost:7687"
_DEFAULT_NEO4J_USER = "neo4j"

# 13 種の個別ラベル（Wave 2 で Entity に付与済み）
# AIDEV-NOTE: migrate_entity_multilabel.py の CANONICAL_TO_LABEL と同期すること。
# index は "MarketIndex" という特殊マッピング（ontology.yaml に準拠）。
INDIVIDUAL_LABELS: list[str] = [
    "Company",
    "Technology",
    "Organization",
    "Person",
    "MarketIndex",
    "Indicator",
    "Instrument",
    "Commodity",
    "Country",
    "Concept",
    "Regulation",
    "Broker",
    "Product",
]
"""13 種の個別 PascalCase ラベル。Sector は Topic に変換されるため除外。"""

# NODE KEY 制約の各ラベルとプロパティの対応
# AIDEV-NOTE: entity_key は廃止されるため、name プロパティを NODE KEY とする。
# ただし MarketIndex/Indicator 等は ticker + name の複合 KEY とすることも検討できるが、
# Wave 4 では簡潔に name 単体で統一する。
_NODE_KEY_PROPERTY = "name"

# NODE KEY 制約名のプレフィックス
_CONSTRAINT_NAME_PREFIX = "node_key"


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass
class DecompositionStats:
    """Wave 4 分解移行の統計情報。"""

    sector_converted: int = 0
    """テーマ的 Sector → Topic 変換件数。"""

    constraints_created: int = 0
    """NODE KEY 制約作成件数。"""

    entity_key_removed: int = 0
    """entity_key プロパティ削除件数。"""

    entity_type_nodes_deleted: int = 0
    """EntityType ノード削除件数。"""

    instrument_class_nodes_deleted: int = 0
    """InstrumentClass ノード削除件数。"""

    entity_label_removed: int = 0
    """Entity ラベル削除件数。"""

    failed: int = 0
    """失敗件数。"""


# ---------------------------------------------------------------------------
# Phase 1: Entity:Sector テーマ的ノード → Topic 変換
# ---------------------------------------------------------------------------


def fetch_thematic_sector_entities(session: Any) -> list[dict[str, Any]]:
    """テーマ的な Entity:Sector ノードを取得する。

    GICS セクターではなく、テーマ・概念的な Sector ノードを対象とする。
    Wave 3 で Sector ノードに正規化されなかった Entity:Sector が対象。

    Parameters
    ----------
    session : Any
        Neo4j セッション。

    Returns
    -------
    list[dict[str, Any]]
        テーマ的 Sector ノードのリスト。各要素に ``entity_key`` と ``name`` を含む。
    """
    # AIDEV-NOTE: Entity:Sector のうち、IN_SECTOR リレーションがないもの（孤立 Sector）が
    # テーマ的ノードと見なせる。ただし全件変換するシンプルな方針も許容される。
    cypher = "MATCH (e:Entity:Sector) RETURN e.entity_key AS entity_key, e.name AS name"
    result = session.run(cypher)
    records = [
        {"entity_key": record["entity_key"], "name": record["name"]}
        for record in result
    ]
    logger.info("Found %d Entity:Sector nodes to convert to Topic", len(records))
    return records


def convert_sector_to_topic(
    session: Any,
    entities: list[dict[str, Any]],
    dry_run: bool = False,
) -> int:
    """Entity:Sector テーマ的ノードを Topic ラベルに変換する。

    各ノードに Topic ラベルを追加し、Sector ラベルを削除する。
    entity_key で対象ノードを特定する。

    Parameters
    ----------
    session : Any
        Neo4j セッション。
    entities : list[dict[str, Any]]
        変換対象ノードのリスト（fetch_thematic_sector_entities の戻り値）。
    dry_run : bool
        True の場合、実際の書き込みをスキップして 0 を返す。

    Returns
    -------
    int
        変換件数（dry_run=True の場合は 0）。
    """
    if not entities:
        return 0

    if dry_run:
        logger.debug(
            "[dry-run] Would convert %d Entity:Sector nodes to Topic", len(entities)
        )
        return 0

    applied = 0
    for entity in entities:
        entity_key = entity["entity_key"]
        # AIDEV-NOTE: SET e:Topic でTopicラベルを追加し、REMOVE e:Sector でSectorラベルを削除。
        # Entity ラベルはこのフェーズでは保持する（Phase 6 で一括削除）。
        cypher = (
            "MATCH (e:Entity:Sector {entity_key: $entity_key}) "
            "SET e:Topic "
            "REMOVE e:Sector"
        )
        try:
            session.run(cypher, entity_key=entity_key)
            applied += 1
            logger.debug("Converted Sector to Topic: entity_key=%s", entity_key)
        except Exception:
            logger.exception(
                "Failed to convert Sector to Topic: entity_key=%s", entity_key
            )

    logger.info("Converted %d Entity:Sector nodes to Topic", applied)
    return applied


# ---------------------------------------------------------------------------
# Phase 2: NODE KEY 制約作成
# ---------------------------------------------------------------------------


def create_node_key_constraints(
    session: Any,
    dry_run: bool = False,
) -> int:
    """13 個別ラベル全てに NODE KEY 制約を作成する。

    制約名は ``node_key_{lowercase_label}`` 形式。
    既存の制約がある場合は ``IF NOT EXISTS`` により冪等実行される。

    Parameters
    ----------
    session : Any
        Neo4j セッション。
    dry_run : bool
        True の場合、制約を作成せずに 0 を返す。

    Returns
    -------
    int
        作成した制約件数（既存除く）。dry_run=True の場合は 0。
    """
    if dry_run:
        logger.debug(
            "[dry-run] Would create %d NODE KEY constraints", len(INDIVIDUAL_LABELS)
        )
        return 0

    created = 0
    for label in INDIVIDUAL_LABELS:
        constraint_name = f"{_CONSTRAINT_NAME_PREFIX}_{label.lower()}"
        # AIDEV-NOTE: Neo4j 5.x の NODE KEY 制約構文。
        # IF NOT EXISTS により冪等実行を保証する。
        cypher = (
            f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS "
            f"FOR (n:{label}) "
            f"REQUIRE n.{_NODE_KEY_PROPERTY} IS NODE KEY"
        )
        try:
            session.run(cypher)
            created += 1
            logger.debug("Created NODE KEY constraint: %s", constraint_name)
        except Exception:
            logger.exception(
                "Failed to create NODE KEY constraint: %s (may already exist with different definition)",
                constraint_name,
            )

    logger.info(
        "NODE KEY constraint creation: %d/%d succeeded",
        created,
        len(INDIVIDUAL_LABELS),
    )
    return created


# ---------------------------------------------------------------------------
# Phase 3: entity_key プロパティ削除
# ---------------------------------------------------------------------------


def remove_entity_key_property(
    session: Any,
    dry_run: bool = False,
) -> int:
    """個別ラベル付きノードから entity_key プロパティを削除する。

    全 13 個別ラベルに対して一括削除クエリを実行する。
    IS NOT NULL チェックにより冪等実行を保証する。

    Parameters
    ----------
    session : Any
        Neo4j セッション。
    dry_run : bool
        True の場合、削除せずに 0 を返す。

    Returns
    -------
    int
        削除件数（dry_run=True の場合は 0）。
    """
    if dry_run:
        logger.debug(
            "[dry-run] Would remove entity_key property from individual label nodes"
        )
        return 0

    # 全個別ラベルのノードから entity_key を一括削除
    # AIDEV-NOTE: INDIVIDUAL_LABELS 内のラベルは全て許可リストから取得した固定値のため安全。
    label_match = " OR ".join([f"n:{label}" for label in INDIVIDUAL_LABELS])
    cypher = (
        f"MATCH (n) WHERE ({label_match}) AND n.entity_key IS NOT NULL "
        "REMOVE n.entity_key "
        "RETURN count(n) AS removed_count"
    )
    result = session.run(cypher)
    record = result.single()
    count: int = record["removed_count"] if record else 0
    logger.info("Removed entity_key property from %d nodes", count)
    return count


# ---------------------------------------------------------------------------
# Phase 4: EntityType ノード削除
# ---------------------------------------------------------------------------


def delete_entity_type_nodes(
    session: Any,
    dry_run: bool = False,
) -> int:
    """EntityType ノード(~1,597件) と IS_TYPE リレーションを削除する。

    DETACH DELETE を使用し、接続する全リレーション（IS_TYPE）を含めて削除する。

    Parameters
    ----------
    session : Any
        Neo4j セッション。
    dry_run : bool
        True の場合、削除せずに 0 を返す。

    Returns
    -------
    int
        削除した EntityType ノード件数（dry_run=True の場合は 0）。
    """
    if dry_run:
        logger.debug(
            "[dry-run] Would delete EntityType nodes and IS_TYPE relationships"
        )
        return 0

    cypher = "MATCH (et:EntityType) DETACH DELETE et RETURN count(et) AS deleted_count"
    result = session.run(cypher)
    record = result.single()
    count: int = record["deleted_count"] if record else 0
    logger.info("Deleted %d EntityType nodes (with IS_TYPE relationships)", count)
    return count


# ---------------------------------------------------------------------------
# Phase 5: InstrumentClass ノード削除
# ---------------------------------------------------------------------------


def delete_instrument_class_nodes(
    session: Any,
    dry_run: bool = False,
) -> int:
    """InstrumentClass ノード(~106件) と IS_INSTRUMENT_CLASS リレーションを削除する。

    DETACH DELETE を使用し、接続する全リレーション（IS_INSTRUMENT_CLASS）を含めて削除する。

    Parameters
    ----------
    session : Any
        Neo4j セッション。
    dry_run : bool
        True の場合、削除せずに 0 を返す。

    Returns
    -------
    int
        削除した InstrumentClass ノード件数（dry_run=True の場合は 0）。
    """
    if dry_run:
        logger.debug(
            "[dry-run] Would delete InstrumentClass nodes and IS_INSTRUMENT_CLASS relationships"
        )
        return 0

    cypher = (
        "MATCH (ic:InstrumentClass) DETACH DELETE ic RETURN count(ic) AS deleted_count"
    )
    result = session.run(cypher)
    record = result.single()
    count: int = record["deleted_count"] if record else 0
    logger.info(
        "Deleted %d InstrumentClass nodes (with IS_INSTRUMENT_CLASS relationships)",
        count,
    )
    return count


# ---------------------------------------------------------------------------
# Phase 6: Entity ラベル削除（最終ステップ）
# ---------------------------------------------------------------------------


def remove_entity_label(
    session: Any,
    dry_run: bool = False,
) -> int:
    """個別ラベル付きノードから Entity ラベルを削除する（最終ステップ）。

    全 13 個別ラベルを持つノードから Entity ラベルを一括削除する。

    Parameters
    ----------
    session : Any
        Neo4j セッション。
    dry_run : bool
        True の場合、削除せずに 0 を返す。

    Returns
    -------
    int
        Entity ラベルを削除したノード件数（dry_run=True の場合は 0）。
    """
    if dry_run:
        logger.debug(
            "[dry-run] Would remove Entity label from all individual label nodes"
        )
        return 0

    label_match = " OR ".join([f"n:{label}" for label in INDIVIDUAL_LABELS])
    # AIDEV-NOTE: Topic に変換された旧 Sector ノードも Entity ラベルを持つため対象に含める。
    cypher = (
        f"MATCH (n:Entity) WHERE ({label_match}) OR n:Topic "
        "REMOVE n:Entity "
        "RETURN count(n) AS removed_count"
    )
    result = session.run(cypher)
    record = result.single()
    count: int = record["removed_count"] if record else 0
    logger.info("Removed Entity label from %d nodes", count)
    return count


# ---------------------------------------------------------------------------
# Dry-run サマリー
# ---------------------------------------------------------------------------


def run_dry_run_summary(session: Any) -> None:
    """dry-run 時のサマリーを出力する。"""
    # Phase 1: テーマ的 Sector
    thematic_sectors = fetch_thematic_sector_entities(session)

    # Phase 2: NODE KEY 制約対象
    constraint_count = len(INDIVIDUAL_LABELS)

    # Phase 3: entity_key 削除対象
    label_match = " OR ".join([f"n:{label}" for label in INDIVIDUAL_LABELS])
    ek_result = session.run(
        f"MATCH (n) WHERE ({label_match}) AND n.entity_key IS NOT NULL "
        "RETURN count(n) AS cnt"
    )
    ek_record = ek_result.single()
    ek_count = ek_record["cnt"] if ek_record else 0

    # Phase 4: EntityType ノード件数
    et_result = session.run("MATCH (et:EntityType) RETURN count(et) AS cnt")
    et_record = et_result.single()
    et_count = et_record["cnt"] if et_record else 0

    # Phase 5: InstrumentClass ノード件数
    ic_result = session.run("MATCH (ic:InstrumentClass) RETURN count(ic) AS cnt")
    ic_record = ic_result.single()
    ic_count = ic_record["cnt"] if ic_record else 0

    # Phase 6: Entity ラベル削除対象
    el_result = session.run(
        f"MATCH (n:Entity) WHERE ({label_match}) OR n:Topic RETURN count(n) AS cnt"
    )
    el_record = el_result.single()
    el_count = el_record["cnt"] if el_record else 0

    print("\n=== Wave 4 dry-run サマリー ===")
    print(f"  Phase 1: Entity:Sector → Topic 変換対象 : {len(thematic_sectors):,} 件")
    print(f"  Phase 2: NODE KEY 制約作成対象          : {constraint_count:,} ラベル")
    print(f"  Phase 3: entity_key プロパティ削除対象   : {ek_count:,} 件")
    print(f"  Phase 4: EntityType ノード削除対象       : {et_count:,} 件")
    print(f"  Phase 5: InstrumentClass ノード削除対象  : {ic_count:,} 件")
    print(f"  Phase 6: Entity ラベル削除対象           : {el_count:,} 件")
    print("  ※ --dry-run のため DB への書き込みは行いません")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Wave 4 Entity ラベル分解移行スクリプトのエントリーポイント。"""
    parser = argparse.ArgumentParser(
        description=(
            "Wave 4: Entity ラベル分解・entity_key 廃止・NODE KEY 制約導入の移行スクリプト"
        ),
    )
    parser.add_argument(
        "--neo4j-uri",
        default=os.environ.get("NEO4J_URI", _DEFAULT_NEO4J_URI),
        help=f"Neo4j 接続 URI (デフォルト: {_DEFAULT_NEO4J_URI})",
    )
    parser.add_argument(
        "--neo4j-user",
        default=os.environ.get("NEO4J_USER", _DEFAULT_NEO4J_USER),
        help="Neo4j ユーザー名 (デフォルト: neo4j)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="変更対象件数のみ表示し、DB への書き込みは行わない",
    )
    parser.add_argument(
        "--phase",
        choices=[
            "sector_to_topic",
            "node_key",
            "remove_entity_key",
            "delete_entity_type",
            "delete_instrument_class",
            "remove_entity_label",
        ],
        default=None,
        help="特定フェーズのみ実行（デフォルト: 全フェーズ）",
    )
    parser.add_argument(
        "--run-final-phase",
        action="store_true",
        help=(
            "Phase 6（Entity ラベル削除）を実行する。全フェーズ実行時もこのフラグが必要"
        ),
    )
    args = parser.parse_args()

    neo4j_password = os.environ.get("NEO4J_PASSWORD")
    if not neo4j_password:
        parser.error(
            "Neo4j password is required. Set NEO4J_PASSWORD environment variable."
        )

    logger.info("Connecting to Neo4j: %s (user: %s)", args.neo4j_uri, args.neo4j_user)
    driver = GraphDatabase.driver(
        args.neo4j_uri,
        auth=(args.neo4j_user, neo4j_password),
    )

    try:
        driver.verify_connectivity()
        logger.info("Connected to Neo4j")

        with driver.session() as session:
            if args.dry_run:
                run_dry_run_summary(session)
                return

            stats = DecompositionStats()
            run_all = args.phase is None

            # Phase 1: Entity:Sector → Topic 変換
            if run_all or args.phase == "sector_to_topic":
                thematic_sectors = fetch_thematic_sector_entities(session)
                stats.sector_converted = convert_sector_to_topic(
                    session, thematic_sectors
                )
                logger.info("Phase 1 complete: converted=%d", stats.sector_converted)

            # Phase 2: NODE KEY 制約作成
            if run_all or args.phase == "node_key":
                stats.constraints_created = create_node_key_constraints(session)
                logger.info(
                    "Phase 2 complete: constraints_created=%d",
                    stats.constraints_created,
                )

            # Phase 3: entity_key プロパティ削除
            if run_all or args.phase == "remove_entity_key":
                stats.entity_key_removed = remove_entity_key_property(session)
                logger.info(
                    "Phase 3 complete: entity_key_removed=%d", stats.entity_key_removed
                )

            # Phase 4: EntityType ノード削除
            if run_all or args.phase == "delete_entity_type":
                stats.entity_type_nodes_deleted = delete_entity_type_nodes(session)
                logger.info(
                    "Phase 4 complete: entity_type_nodes_deleted=%d",
                    stats.entity_type_nodes_deleted,
                )

            # Phase 5: InstrumentClass ノード削除
            if run_all or args.phase == "delete_instrument_class":
                stats.instrument_class_nodes_deleted = delete_instrument_class_nodes(
                    session
                )
                logger.info(
                    "Phase 5 complete: instrument_class_nodes_deleted=%d",
                    stats.instrument_class_nodes_deleted,
                )

            # Phase 6: Entity ラベル削除（最終ステップ・要明示フラグ）
            if (
                run_all or args.phase == "remove_entity_label"
            ) and args.run_final_phase:
                stats.entity_label_removed = remove_entity_label(session)
                logger.info(
                    "Phase 6 complete: entity_label_removed=%d",
                    stats.entity_label_removed,
                )
            elif run_all and not args.run_final_phase:
                logger.warning(
                    "Phase 6 (Entity ラベル削除) はスキップされました。"
                    "--run-final-phase フラグを指定して実行してください。"
                )

            logger.info(
                "Wave 4 migration complete: "
                "sector_converted=%d constraints_created=%d entity_key_removed=%d "
                "entity_type_deleted=%d instrument_class_deleted=%d entity_label_removed=%d",
                stats.sector_converted,
                stats.constraints_created,
                stats.entity_key_removed,
                stats.entity_type_nodes_deleted,
                stats.instrument_class_nodes_deleted,
                stats.entity_label_removed,
            )

    except Exception:
        logger.exception("Migration failed")
        sys.exit(1)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
