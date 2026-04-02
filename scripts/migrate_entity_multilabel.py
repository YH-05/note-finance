#!/usr/bin/env python3
"""Entity マルチラベル移行スクリプト。

既存の Entity ノードに Company/Organization 等のマルチラベルを追加し、
``sub_type`` プロパティを設定する。また不要な ``isin`` プロパティを削除する。

マッピングテーブルは ``ontology_loader`` 経由で ``ontology.yaml`` から読み込む。

Usage
-----
::

    # 対象件数確認（DB への書き込みなし）
    uv run python scripts/migrate_entity_multilabel.py --dry-run

    # 本番実行
    uv run python scripts/migrate_entity_multilabel.py

    # 接続先を指定
    uv run python scripts/migrate_entity_multilabel.py --neo4j-uri bolt://localhost:7688

設計方針
--------
- 冪等実行可能: 既にマルチラベルが付いているノードは検出・スキップ
- sub_type: 統合前の生 entity_type を保存（例: central_bank → sub_type='central_bank'）
- isin 削除: 0% 使用率のため全 Entity から削除
- APOC が存在しない場合は Cypher ``SET e:Label`` でフォールバック
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ontology_loader import load_consolidation_mapping as _ol_load_consolidation_mapping
from ontology_loader import load_multilabel_types as _ol_load_multilabel_types

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

# デフォルト接続情報（環境変数でオーバーライド可能）
_DEFAULT_NEO4J_URI = "bolt://localhost:7687"
_DEFAULT_NEO4J_USER = "neo4j"

# 正規 entity_type → PascalCase マルチラベルへのマッピング
# SSOT: ontology.yaml (via ontology_loader)
# index だけ "MarketIndex" という特殊マッピング（YAML の multilabel_types 定義に準拠）
CANONICAL_TO_LABEL: dict[str, str] = {
    "company": "Company",
    "technology": "Technology",
    "organization": "Organization",
    "person": "Person",
    "index": "MarketIndex",
    "indicator": "Indicator",
    "instrument": "Instrument",
    "commodity": "Commodity",
    "country": "Country",
    "sector": "Sector",
    "concept": "Concept",
    "regulation": "Regulation",
    "broker": "Broker",
    "product": "Product",
}
"""14 種の正規 entity_type から PascalCase マルチラベルへのマッピング。"""

# 14 種の全マルチラベル（未移行判定クエリで使用）
_ALL_MULTILABELS: list[str] = list(CANONICAL_TO_LABEL.values())


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass
class MigrationStats:
    """移行統計情報。"""

    applied: int = 0
    failed: int = 0
    skipped: int = 0
    isin_removed: int = 0


@dataclass
class MigrationOp:
    """単一ノードの移行操作。"""

    entity_key: str
    label: str
    sub_type: str


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def load_consolidation_rules(schema_path: Path | None = None) -> dict[str, str]:
    """ontology_loader 経由で consolidation_rules を読み込む。

    Parameters
    ----------
    schema_path : Path | None
        ontology.yaml のパス。None の場合はデフォルトパスを使用。
        後方互換のためパラメータを残すが、ontology_loader にパスを委譲する。

    Returns
    -------
    dict[str, str]
        ``{raw_entity_type: canonical_entity_type}`` のマッピング辞書。

    Raises
    ------
    FileNotFoundError
        ontology.yaml が存在しない場合。
    ValueError
        EntityType の canonical_values が見つからない場合。
    """
    return _ol_load_consolidation_mapping(ontology_path=schema_path)


def build_raw_to_label_map(consolidation_rules: dict[str, str]) -> dict[str, str]:
    """生 entity_type → PascalCase マルチラベルのマップを構築する。

    Parameters
    ----------
    consolidation_rules : dict[str, str]
        ``{raw: canonical}`` のマッピング辞書（load_consolidation_rules の戻り値）。

    Returns
    -------
    dict[str, str]
        ``{raw_entity_type: PascalCase_label}`` のマッピング辞書。

    Raises
    ------
    KeyError
        canonical_type が CANONICAL_TO_LABEL に存在しない場合。
    """
    result: dict[str, str] = {}
    for raw_type, canonical_type in consolidation_rules.items():
        result[raw_type] = CANONICAL_TO_LABEL[canonical_type]
    return result


def build_migration_ops(
    raw_entities: list[dict[str, Any]],
    raw_to_label: dict[str, str],
) -> list[dict[str, str]]:
    """未移行ノードリストから移行操作のリストを構築する。

    Parameters
    ----------
    raw_entities : list[dict[str, Any]]
        未移行 Entity ノードのリスト。各要素に ``entity_key`` と ``entity_type`` が必要。
    raw_to_label : dict[str, str]
        ``{raw_entity_type: PascalCase_label}`` のマッピング辞書。

    Returns
    -------
    list[dict[str, str]]
        移行操作のリスト。各要素は ``{entity_key, label, sub_type}`` を持つ。
        raw_to_label に存在しない entity_type のノードはスキップされる。
    """
    ops: list[dict[str, str]] = []
    for node in raw_entities:
        entity_key: str = node["entity_key"]
        entity_type: str = node.get("entity_type", "")
        label = raw_to_label.get(entity_type)
        if label is None:
            logger.warning(
                "Unknown entity_type, skipping: entity_key=%s entity_type=%s",
                entity_key,
                entity_type,
            )
            continue
        ops.append(
            {
                "entity_key": entity_key,
                "label": label,
                "sub_type": entity_type,  # 統合前の生 entity_type を保存
            }
        )
    return ops


def apply_multilabel_batch(
    session: Any,
    ops: list[dict[str, str]],
    dry_run: bool = False,
) -> MigrationStats:
    """移行操作リストを Neo4j セッションで実行する。

    Cypher は冪等設計: ``MATCH ... SET e:Label, e.sub_type = ...``
    既にラベルが付いているノードは上書きされるが副作用なし。

    Parameters
    ----------
    session : Any
        Neo4j セッション。
    ops : list[dict[str, str]]
        移行操作のリスト（build_migration_ops の戻り値）。
    dry_run : bool
        True の場合、実際の書き込みをスキップして件数のみカウント。

    Returns
    -------
    MigrationStats
        実行結果の統計情報。
    """
    stats = MigrationStats()

    if not ops:
        return stats

    for op in ops:
        entity_key = op["entity_key"]
        label = op["label"]
        sub_type = op["sub_type"]

        if dry_run:
            logger.debug(
                "[dry-run] Would apply: entity_key=%s label=%s sub_type=%s",
                entity_key,
                label,
                sub_type,
            )
            stats.skipped += 1
            continue

        # AIDEV-NOTE: ラベルは CANONICAL_TO_LABEL の固定値のみ使用するため安全。
        # SET e:$(label) の動的構文は Neo4j 5.x 未サポートのため、
        # 許可リストから取得した label を文字列フォーマットで埋め込む。
        cypher = (
            f"MATCH (e:Entity {{entity_key: $entity_key}}) "
            f"SET e:`{label}` "
            f"SET e.sub_type = $sub_type"
        )
        try:
            session.run(cypher, entity_key=entity_key, sub_type=sub_type)
            stats.applied += 1
            logger.debug(
                "Applied: entity_key=%s label=%s sub_type=%s",
                entity_key,
                label,
                sub_type,
            )
        except Exception:
            stats.failed += 1
            logger.exception(
                "Failed to apply multilabel: entity_key=%s label=%s",
                entity_key,
                label,
            )

    return stats


def remove_isin_property(session: Any, dry_run: bool = False) -> int:
    """全 Entity ノードから isin プロパティを削除する。

    Parameters
    ----------
    session : Any
        Neo4j セッション。
    dry_run : bool
        True の場合、削除せずに 0 を返す。

    Returns
    -------
    int
        削除した件数（dry_run=True の場合は 0）。
    """
    if dry_run:
        logger.debug("[dry-run] Would remove isin property from all Entity nodes")
        return 0

    cypher = (
        "MATCH (e:Entity) WHERE e.isin IS NOT NULL "
        "REMOVE e.isin "
        "RETURN count(e) AS removed_count"
    )
    result = session.run(cypher)
    record = result.single()
    count: int = record["removed_count"] if record else 0
    logger.info("Removed isin property from %d Entity nodes", count)
    return count


def fetch_unmigrated_entities(session: Any) -> list[dict[str, Any]]:
    """マルチラベルが付与されていない Entity ノードを取得する。

    「マルチラベルなし」の判定: 14 種のいずれのマルチラベルも持っていないノード。

    Parameters
    ----------
    session : Any
        Neo4j セッション。

    Returns
    -------
    list[dict[str, Any]]
        未移行ノードのリスト。各要素に ``entity_key`` と ``entity_type`` を含む。
    """
    # 全14種のマルチラベルを OR 条件で除外
    label_checks = " OR ".join([f"e:{label}" for label in _ALL_MULTILABELS])
    cypher = (
        "MATCH (e:Entity) "
        f"WHERE NOT ({label_checks}) "
        "RETURN e.entity_key AS entity_key, e.entity_type AS entity_type"
    )
    result = session.run(cypher)
    records = [
        {"entity_key": record["entity_key"], "entity_type": record["entity_type"]}
        for record in result
    ]
    logger.info("Found %d unmigrated Entity nodes", len(records))
    return records


def run_dry_run_summary(
    session: Any,
    raw_to_label: dict[str, str],
) -> None:
    """dry-run 時のサマリーを出力する。"""
    unmigrated = fetch_unmigrated_entities(session)
    ops = build_migration_ops(unmigrated, raw_to_label)
    skipped_count = len(unmigrated) - len(ops)

    # isin 対象件数
    isin_cypher = "MATCH (e:Entity) WHERE e.isin IS NOT NULL RETURN count(e) AS cnt"
    isin_result = session.run(isin_cypher)
    isin_record = isin_result.single()
    isin_count = isin_record["cnt"] if isin_record else 0

    print("\n=== dry-run サマリー ===")
    print(f"  未移行 Entity ノード数  : {len(unmigrated):,} 件")
    print(f"  移行操作数 (有効)        : {len(ops):,} 件")
    print(f"  スキップ (未知 type)     : {skipped_count:,} 件")
    print(f"  isin 削除対象           : {isin_count:,} 件")
    print("  ※ --dry-run のため DB への書き込みは行いません")

    # ラベル別件数の内訳
    label_counts: dict[str, int] = {}
    for op in ops:
        label_counts[op["label"]] = label_counts.get(op["label"], 0) + 1
    if label_counts:
        print("\n  ラベル別件数:")
        for label, cnt in sorted(label_counts.items(), key=lambda x: -x[1]):
            print(f"    {label:<20} : {cnt:,} 件")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """エンティティマルチラベル移行スクリプトのエントリーポイント。"""
    parser = argparse.ArgumentParser(
        description="Entity ノードにマルチラベルを付与し sub_type を設定する移行スクリプト",
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
        "--schema-path",
        type=Path,
        default=None,
        help="ontology.yaml のパス (デフォルト: 自動検出)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="変更対象件数のみ表示し、DB への書き込みは行わない",
    )
    args = parser.parse_args()

    # スキーマ読み込み (ontology_loader 経由)
    logger.info("Loading consolidation rules via ontology_loader")
    try:
        consolidation_rules = load_consolidation_rules(schema_path=args.schema_path)
    except (FileNotFoundError, KeyError, ValueError) as e:
        logger.error("Failed to load schema: %s", e)
        sys.exit(1)

    raw_to_label = build_raw_to_label_map(consolidation_rules)
    logger.info("Loaded %d raw entity_type mappings", len(raw_to_label))

    # dry-run でも DB 接続を行うためパスワードは必須
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
                run_dry_run_summary(session, raw_to_label)
                return

            # Phase 1: 未移行ノードを取得
            unmigrated = fetch_unmigrated_entities(session)
            if not unmigrated:
                logger.info("No unmigrated Entity nodes found. Nothing to do.")
            else:
                # Phase 2: 移行操作リストを構築
                ops = build_migration_ops(unmigrated, raw_to_label)
                logger.info(
                    "Migration plan: %d ops (%d skipped due to unknown type)",
                    len(ops),
                    len(unmigrated) - len(ops),
                )

                # Phase 3: マルチラベル付与
                stats = apply_multilabel_batch(session, ops)
                logger.info(
                    "Multilabel migration complete: applied=%d failed=%d skipped=%d",
                    stats.applied,
                    stats.failed,
                    stats.skipped,
                )

                if stats.failed > 0:
                    logger.error(
                        "%d nodes failed to migrate. Check logs for details.",
                        stats.failed,
                    )

            # Phase 4: isin プロパティ削除
            isin_removed = remove_isin_property(session)
            logger.info("isin property removed from %d nodes", isin_removed)

        logger.info("Migration finished successfully")

    except Exception:
        logger.exception("Migration failed")
        sys.exit(1)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
