#!/usr/bin/env python3
"""同ラベル同名重複エンティティの名寄せスクリプト。

同一ラベルで name が重複する Entity/Topic/UnitOfMeasure 等のノードを検出し、
リレーション数が最多のノードを統合先（survivor）として残し、
残りのノードを削除する。

Issue #303 - Wave 2: 同ラベル同名重複 19 件の名寄せ

Usage
-----
::

    # ドライランで重複件数を確認（DB 書き込みなし）
    uv run python scripts/dedup_entities.py --dry-run

    # 本番実行
    uv run python scripts/dedup_entities.py

    # データベース・出力ディレクトリを指定
    uv run python scripts/dedup_entities.py --database research --output-dir data/migration

Notes
-----
- ``data/migration/dedup_entity_mapping.json`` に統合マッピングを記録する
- Neo4j Enterprise Multi-Database 環境（bolt://localhost:7687）を前提とする
- Memory ノードは除外（ ``WHERE NOT 'Memory' IN labels(n)`` ）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from neo4j import GraphDatabase
except ImportError:
    print("ERROR: neo4j driver not installed. Run: uv add neo4j", file=sys.stderr)
    sys.exit(1)

try:
    from utils_core.logging.config import get_logger

    logger = get_logger(__name__)
except ImportError:
    import logging

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
_DEFAULT_USER = os.environ.get("NEO4J_USER", "neo4j")
_DEFAULT_PASSWORD = os.environ.get(
    "NEO4J_PASSWORD"
)  # 本番環境では必須。未設定時は argparse でエラー終了
_DEFAULT_DATABASE = "research"
_DEFAULT_OUTPUT_DIR = Path("data/migration")

# 同ラベル同名重複ノードを全件取得する Cypher クエリ
# Memory ノードを除外し、ラベルセット×name が一致するものを抽出
_DUPLICATE_QUERY = """
MATCH (n)
WHERE NOT 'Memory' IN labels(n) AND n.name IS NOT NULL
WITH labels(n) AS lbls, n.name AS name, COLLECT(n) AS nodes
WHERE SIZE(nodes) > 1
UNWIND nodes AS nd
OPTIONAL MATCH (nd)-[r]-()
WITH lbls, name, nd, COUNT(r) AS rel_count
ORDER BY lbls, name, rel_count DESC
WITH lbls, name, COLLECT({id: elementId(nd), rel_count: rel_count, props: properties(nd)}) AS node_list
RETURN lbls, name, node_list
ORDER BY lbls, name
"""

# 統合後の重複件数確認クエリ
_VERIFY_QUERY = """
MATCH (n)
WHERE NOT 'Memory' IN labels(n) AND n.name IS NOT NULL
WITH labels(n) AS lbls, n.name AS name, COUNT(n) AS cnt
WHERE cnt > 1
RETURN COUNT(*) AS dup_count
"""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class DedupConfig:
    """名寄せ設定。

    Attributes
    ----------
    database : str
        Neo4j データベース名。
    uri : str
        Neo4j 接続 URI。
    output_dir : Path
        マッピング JSON 出力ディレクトリ。
    dry_run : bool
        True の場合 DB 書き込みを行わない。
    """

    database: str = _DEFAULT_DATABASE
    uri: str = _DEFAULT_URI
    output_dir: Path = field(default_factory=lambda: _DEFAULT_OUTPUT_DIR)
    dry_run: bool = False


@dataclass
class NodeInfo:
    """Neo4j ノード情報。

    Attributes
    ----------
    element_id : str
        Neo4j element ID（例: ``4:aff6b542:1151``）。
    rel_count : int
        このノードに接続するリレーション数（survivor 選択の根拠）。
    props : dict[str, Any]
        ノードのプロパティ（``entity_key``, ``entity_id`` 等）。
    """

    element_id: str
    rel_count: int
    props: dict[str, Any]


@dataclass
class DuplicateGroup:
    """同ラベル同名の重複ノードグループ。

    Attributes
    ----------
    labels : list[str]
        このグループのラベルセット（例: ``["Entity", "Organization"]``）。
    name : str
        共通の name プロパティ値。
    nodes : list[NodeInfo]
        重複ノードのリスト（rel_count 降順で格納）。
    """

    labels: list[str]
    name: str
    nodes: list[NodeInfo]


@dataclass
class DedupResult:
    """名寄せ実行結果。

    Attributes
    ----------
    merged_count : int
        統合したグループ数。
    total_deleted : int
        削除したノード総数。
    dry_run : bool
        ドライランモードの場合 True。
    merged_groups : list[dict[str, Any]]
        各グループの統合詳細（survivor/deleted ID 等）。
    """

    merged_count: int
    total_deleted: int
    dry_run: bool
    merged_groups: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def collect_duplicate_groups(
    driver: Any,
    database: str = _DEFAULT_DATABASE,
) -> list[DuplicateGroup]:
    """Neo4j から同ラベル同名の重複ノードグループを全件取得する。

    Parameters
    ----------
    driver : Any
        接続済み Neo4j ドライバー。
    database : str
        対象データベース名。

    Returns
    -------
    list[DuplicateGroup]
        重複グループのリスト。重複がない場合は空リスト。
    """
    logger.info("Collecting duplicate groups from database: %s", database)
    groups: list[DuplicateGroup] = []

    with driver.session(database=database) as session:
        result = session.run(_DUPLICATE_QUERY)
        for record in result:
            lbls: list[str] = record["lbls"]
            name: str = record["name"]
            node_list: list[dict[str, Any]] = record["node_list"]

            nodes = [
                NodeInfo(
                    element_id=n["id"],
                    rel_count=n["rel_count"],
                    props=dict(n["props"]),
                )
                for n in node_list
            ]
            groups.append(DuplicateGroup(labels=list(lbls), name=name, nodes=nodes))

    logger.info("Duplicate groups found: %d", len(groups))
    return groups


def select_survivor(group: DuplicateGroup) -> tuple[NodeInfo, list[NodeInfo]]:
    """重複グループからサバイバーと削除対象を選択する。

    選択基準: リレーション数が最多のノードをサバイバーとする。
    リレーション数が同数の場合は入力リストの最初のノードを優先する。

    Parameters
    ----------
    group : DuplicateGroup
        重複グループ。

    Returns
    -------
    tuple[NodeInfo, list[NodeInfo]]
        (survivor, nodes_to_delete) のタプル。
    """
    # rel_count 最大のノードをサバイバーとして選択
    # 同数の場合はインデックスが小さい（最初に現れた）ものを優先
    survivor = max(group.nodes, key=lambda n: n.rel_count)
    to_delete = [n for n in group.nodes if n is not survivor]
    logger.debug(
        "Survivor selected: name=%s survivor=%s rels=%d delete_count=%d",
        group.name,
        survivor.element_id,
        survivor.rel_count,
        len(to_delete),
    )
    return survivor, to_delete


def merge_duplicate_groups(
    driver: Any,
    groups: list[DuplicateGroup],
    database: str = _DEFAULT_DATABASE,
    dry_run: bool = False,
) -> DedupResult:
    """重複グループを統合する。

    各グループについて:
    1. サバイバーを選択（rel_count 最大）
    2. 削除対象ノードのリレーションをサバイバーに移植
    3. 削除対象ノードを削除

    Parameters
    ----------
    driver : Any
        接続済み Neo4j ドライバー。
    groups : list[DuplicateGroup]
        統合対象の重複グループリスト。
    database : str
        対象データベース名。
    dry_run : bool
        True の場合 DB 書き込みを行わない（統計のみ返す）。

    Returns
    -------
    DedupResult
        統合結果。
    """
    if not groups:
        logger.info("No duplicate groups to merge")
        return DedupResult(
            merged_count=0, total_deleted=0, dry_run=dry_run, merged_groups=[]
        )

    merged_groups: list[dict[str, Any]] = []
    total_deleted = 0

    for group in groups:
        survivor, to_delete = select_survivor(group)
        group_info: dict[str, Any] = {
            "labels": group.labels,
            "name": group.name,
            "survivor_id": survivor.element_id,
            "survivor_rel_count": survivor.rel_count,
            "survivor_props": survivor.props,
            "deleted_ids": [n.element_id for n in to_delete],
            "deleted_props": [n.props for n in to_delete],
        }

        if dry_run:
            logger.info(
                "[DRY-RUN] Would merge: name=%s labels=%s survivor=%s delete_count=%d",
                group.name,
                group.labels,
                survivor.element_id,
                len(to_delete),
            )
        else:
            _execute_merge(driver, database, survivor, to_delete)

        merged_groups.append(group_info)
        total_deleted += len(to_delete)

    logger.info(
        "Merge complete: groups=%d deleted=%d dry_run=%s",
        len(merged_groups),
        total_deleted,
        dry_run,
    )
    return DedupResult(
        merged_count=len(merged_groups),
        total_deleted=total_deleted,
        dry_run=dry_run,
        merged_groups=merged_groups,
    )


def _execute_merge(
    driver: Any,
    database: str,
    survivor: NodeInfo,
    to_delete: list[NodeInfo],
) -> None:
    """サバイバーへのリレーション移植と削除対象ノードの削除を実行する。

    リレーション移植には APOC の ``apoc.refactor.mergeNodes`` を使用する。
    APOC が利用できない場合は手動で MATCH/MERGE/DELETE を実行する。

    Parameters
    ----------
    driver : Any
        接続済み Neo4j ドライバー。
    database : str
        対象データベース名。
    survivor : NodeInfo
        統合先ノード。
    to_delete : list[NodeInfo]
        削除するノードリスト。
    """
    delete_ids = [n.element_id for n in to_delete]

    # APOC mergeNodes で一括統合（リレーション移植 + 重複ノード削除）
    # config: properties = overwrite（survivor のプロパティを優先）
    merge_query = """
    MATCH (survivor)
    WHERE elementId(survivor) = $survivor_id
    WITH survivor
    MATCH (dup)
    WHERE elementId(dup) IN $delete_ids
    WITH survivor, COLLECT(dup) AS dups
    CALL apoc.refactor.mergeNodes([survivor] + dups, {
        properties: 'discard',
        mergeRels: true
    })
    YIELD node
    RETURN elementId(node) AS merged_id
    """

    with driver.session(database=database) as session:
        try:
            result = session.run(
                merge_query,
                survivor_id=survivor.element_id,
                delete_ids=delete_ids,
            )
            merged_id = result.single()
            logger.info(
                "Merged via APOC: merged_id=%s survivor=%s deleted=%s",
                merged_id,
                survivor.element_id,
                delete_ids,
            )
        except Exception as apoc_err:
            # APOC が使えない場合はフォールバック: リレーション手動移植
            logger.warning(
                "APOC merge failed, falling back to manual merge: %s",
                apoc_err,
            )
            _manual_merge(driver, database, survivor, to_delete)


def _manual_merge(
    driver: Any,
    database: str,
    survivor: NodeInfo,
    to_delete: list[NodeInfo],
) -> None:
    """APOC なしのフォールバック統合処理。

    重複ノードのリレーションを survivor に付け替えた後、
    重複ノードを DETACH DELETE で削除する。

    Parameters
    ----------
    driver : Any
        接続済み Neo4j ドライバー。
    database : str
        対象データベース名。
    survivor : NodeInfo
        統合先ノード。
    to_delete : list[NodeInfo]
        削除するノードリスト。
    """
    # AIDEV-NOTE: APOC が利用不可の場合のフォールバック
    # リレーション方向を保持したまま survivor に移植する
    reroute_outgoing = """
    MATCH (survivor)
    WHERE elementId(survivor) = $survivor_id
    MATCH (dup)
    WHERE elementId(dup) = $dup_id
    MATCH (dup)-[r]->(target)
    WHERE elementId(target) <> elementId(survivor)
    WITH survivor, dup, r, target, type(r) AS rtype, properties(r) AS rprops
    CALL apoc.create.relationship(survivor, rtype, rprops, target) YIELD rel
    DELETE r
    RETURN COUNT(rel) AS moved
    """
    reroute_incoming = """
    MATCH (survivor)
    WHERE elementId(survivor) = $survivor_id
    MATCH (dup)
    WHERE elementId(dup) = $dup_id
    MATCH (source)-[r]->(dup)
    WHERE elementId(source) <> elementId(survivor)
    WITH survivor, dup, r, source, type(r) AS rtype, properties(r) AS rprops
    CALL apoc.create.relationship(source, rtype, rprops, survivor) YIELD rel
    DELETE r
    RETURN COUNT(rel) AS moved
    """
    delete_dup = """
    MATCH (dup)
    WHERE elementId(dup) = $dup_id
    DETACH DELETE dup
    """

    with driver.session(database=database) as session:
        for dup in to_delete:
            try:
                session.run(
                    reroute_outgoing,
                    survivor_id=survivor.element_id,
                    dup_id=dup.element_id,
                )
                session.run(
                    reroute_incoming,
                    survivor_id=survivor.element_id,
                    dup_id=dup.element_id,
                )
                session.run(delete_dup, dup_id=dup.element_id)
                logger.info(
                    "Manual merge complete: survivor=%s deleted=%s",
                    survivor.element_id,
                    dup.element_id,
                )
            except Exception as e:
                logger.error(
                    "Manual merge failed: survivor=%s dup=%s error=%s",
                    survivor.element_id,
                    dup.element_id,
                    e,
                    exc_info=True,
                )
                raise


def verify_no_duplicates(
    driver: Any,
    database: str = _DEFAULT_DATABASE,
) -> int:
    """統合後に重複が残っていないことを確認する。

    Parameters
    ----------
    driver : Any
        接続済み Neo4j ドライバー。
    database : str
        対象データベース名。

    Returns
    -------
    int
        残存する重複グループ数（0 が期待値）。
    """
    logger.info("Verifying no duplicates remain in database: %s", database)
    with driver.session(database=database) as session:
        result = session.run(_VERIFY_QUERY)
        record = result.single()
        dup_count: int = record["dup_count"] if record else 0

    if dup_count == 0:
        logger.info("Verification passed: no duplicate groups remain")
    else:
        logger.warning("Verification failed: %d duplicate groups remain", dup_count)
    return dup_count


def format_dedup_mapping(
    groups: list[DuplicateGroup],
    result: DedupResult,
    date_str: str,
) -> dict[str, Any]:
    """統合結果をマッピング辞書にフォーマットする。

    Parameters
    ----------
    groups : list[DuplicateGroup]
        統合対象グループ（survivor 選択の元データ）。
    result : DedupResult
        統合実行結果。
    date_str : str
        日付文字列（YYYYMMDD 形式）。

    Returns
    -------
    dict[str, Any]
        マッピング辞書（JSON 保存用）。
    """
    # groups を name でインデックス化（詳細プロパティ取得用）
    group_by_name: dict[str, DuplicateGroup] = {}
    for g in groups:
        key = (tuple(sorted(g.labels)), g.name)
        group_by_name[key] = g  # type: ignore[assignment]

    mappings: list[dict[str, Any]] = []
    for entry in result.merged_groups:
        name = entry["name"]
        labels = entry["labels"]
        key = (tuple(sorted(labels)), name)
        group = group_by_name.get(key)  # type: ignore[call-overload]

        survivor_props: dict[str, Any] = {}
        if group:
            # survivor は nodes[0]（rel_count 最大）
            survivor_props = dict(group.nodes[0].props)

        mappings.append(
            {
                "labels": labels,
                "name": name,
                "survivor_id": entry["survivor_id"],
                "survivor_rel_count": entry.get("survivor_rel_count", 0),
                "survivor_props": survivor_props,
                "deleted_ids": entry["deleted_ids"],
                "deleted_count": len(entry["deleted_ids"]),
            }
        )

    return {
        "generated_at": date_str,
        "database": _DEFAULT_DATABASE,
        "dry_run": result.dry_run,
        "total_merged_groups": result.merged_count,
        "total_deleted_nodes": result.total_deleted,
        "note": (
            "同ラベル同名重複エンティティの名寄せマッピング（Issue #303 Wave2）。"
            "survivor_id を統合先ノードとして残し、deleted_ids のノードを削除した。"
        ),
        "mappings": mappings,
    }


class _Neo4jJsonEncoder(json.JSONEncoder):
    """Neo4j 型（DateTime、Date 等）を文字列に変換する JSON エンコーダー。"""

    def default(self, o: Any) -> Any:
        # neo4j.time.DateTime / neo4j.time.Date / neo4j.time.Time
        if hasattr(o, "iso_format"):
            return o.iso_format()
        if hasattr(o, "isoformat"):
            return o.isoformat()
        return super().default(o)


def save_mapping(
    mapping: dict[str, Any],
    output_dir: Path,
    filename: str,
) -> Path:
    """マッピングを JSON ファイルに保存する。

    Parameters
    ----------
    mapping : dict[str, Any]
        保存するマッピング辞書。
    output_dir : Path
        出力ディレクトリ（存在しない場合は自動作成）。
    filename : str
        出力ファイル名。

    Returns
    -------
    Path
        保存したファイルのパス。
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    output_path.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2, cls=_Neo4jJsonEncoder),
        encoding="utf-8",
    )
    logger.info("Mapping saved: %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """コマンドライン引数を解析する。

    Parameters
    ----------
    argv : list[str] | None
        引数リスト。None の場合は sys.argv を使用。

    Returns
    -------
    argparse.Namespace
        解析済み引数。
    """
    parser = argparse.ArgumentParser(
        description="同ラベル同名重複エンティティの名寄せ（Issue #303 Wave2）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python scripts/dedup_entities.py --dry-run
  uv run python scripts/dedup_entities.py
  uv run python scripts/dedup_entities.py --database research --output-dir data/migration
        """,
    )
    parser.add_argument(
        "--database",
        default=_DEFAULT_DATABASE,
        help=f"Neo4j データベース名（デフォルト: {_DEFAULT_DATABASE}）",
    )
    parser.add_argument(
        "--uri",
        default=_DEFAULT_URI,
        help=f"Neo4j 接続 URI（デフォルト: {_DEFAULT_URI}）",
    )
    parser.add_argument(
        "--output-dir",
        default=str(_DEFAULT_OUTPUT_DIR),
        help=f"出力ディレクトリ（デフォルト: {_DEFAULT_OUTPUT_DIR}）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="DB 書き込みなしで重複件数のみ確認",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="ログレベル（デフォルト: INFO）",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """メインエントリーポイント。

    Parameters
    ----------
    argv : list[str] | None
        コマンドライン引数。

    Returns
    -------
    int
        終了コード（0: 成功、1: 失敗）。
    """
    args = parse_args(argv)

    import logging

    logging.getLogger().setLevel(getattr(logging, args.log_level, logging.INFO))

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y%m%d")

    logger.info(
        "dedup_entities starting: database=%s dry_run=%s",
        args.database,
        args.dry_run,
    )

    # Neo4j 接続
    password = _DEFAULT_PASSWORD
    if not password:
        logger.error("NEO4J_PASSWORD environment variable is required.")
        return 1
    try:
        driver = GraphDatabase.driver(args.uri, auth=(_DEFAULT_USER, password))
        driver.verify_connectivity()
        logger.info("Neo4j connection verified: %s", args.uri)
    except Exception as e:
        logger.error("Failed to connect to Neo4j: %s", e)
        return 1

    try:
        # 重複グループ収集
        groups = collect_duplicate_groups(driver, database=args.database)

        if not groups:
            logger.info("No duplicate groups found. Nothing to do.")
            print("重複グループ: 0件（処理不要）")
            return 0

        logger.info(
            "Duplicate summary: total_groups=%d total_extra_nodes=%d",
            len(groups),
            sum(len(g.nodes) - 1 for g in groups),
        )

        # 統合実行
        result = merge_duplicate_groups(
            driver,
            groups=groups,
            database=args.database,
            dry_run=args.dry_run,
        )

        # マッピング生成・保存
        mapping = format_dedup_mapping(groups=groups, result=result, date_str=date_str)
        output_dir = Path(args.output_dir)
        filename = "dedup_entity_mapping.json"
        output_path = save_mapping(mapping, output_dir=output_dir, filename=filename)

        # 統合後検証（dry_run でない場合）
        if not args.dry_run:
            remaining = verify_no_duplicates(driver, database=args.database)
            if remaining > 0:
                logger.warning(
                    "Verification failed: %d duplicate groups remain after merge",
                    remaining,
                )
                print(f"警告: 統合後も {remaining} 件の重複グループが残存しています")
                return 1

        # 結果サマリー出力
        mode = "[DRY-RUN] " if args.dry_run else ""
        print(
            f"{mode}統合グループ数: {result.merged_count}件, "
            f"削除ノード数: {result.total_deleted}件"
        )
        print(f"マッピング保存: {output_path}")
        if not args.dry_run:
            print("重複0件確認: OK")

        return 0

    except Exception as e:
        logger.error("dedup_entities failed: %s", e, exc_info=True)
        return 1
    finally:
        driver.close()


if __name__ == "__main__":
    sys.exit(main())
