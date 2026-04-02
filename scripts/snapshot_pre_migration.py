#!/usr/bin/env python3
"""移行前スナップショット取得スクリプト。

Entity ラベル廃止移行を開始する前に、research-neo4j の現状ノード数・
リレーション数を記録し、ロールバック基点データとして保存する。

Issue #302 - Wave 1: 移行前バックアップ・スナップショット取得

Usage
-----
::

    # デフォルト（research DB、data/migration/ に出力）
    uv run python scripts/snapshot_pre_migration.py

    # データベース・出力ディレクトリを指定
    uv run python scripts/snapshot_pre_migration.py --database research --output-dir data/migration

Examples
--------
::

    $ uv run python scripts/snapshot_pre_migration.py
    INFO: Connecting to Neo4j: bolt://localhost:7687
    INFO: Snapshot saved: data/migration/20260402_pre_migration_counts.json
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
_DEFAULT_PASSWORD = os.environ.get("NEO4J_PASSWORD", "gomasuke")
_DEFAULT_DATABASE = "research"
_DEFAULT_OUTPUT_DIR = Path("data/migration")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class SnapshotConfig:
    """スナップショット取得設定。

    Attributes
    ----------
    database : str
        Neo4j データベース名。
    uri : str
        Neo4j 接続 URI。
    output_dir : Path
        出力ディレクトリ。
    """

    database: str = _DEFAULT_DATABASE
    uri: str = _DEFAULT_URI
    output_dir: Path = field(default_factory=lambda: _DEFAULT_OUTPUT_DIR)


@dataclass
class QueryResult:
    """Neo4j クエリ結果。

    Attributes
    ----------
    node_count : int
        全ノード総数。
    rel_count : int
        全リレーション総数。
    label_counts : dict[str, int]
        ラベル別ノード件数。
    rel_type_counts : dict[str, int]
        リレーションタイプ別件数。
    """

    node_count: int
    rel_count: int
    label_counts: dict[str, int] = field(default_factory=dict)
    rel_type_counts: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def collect_counts(driver: Any, database: str = _DEFAULT_DATABASE) -> QueryResult:
    """Neo4j からノード・リレーションの件数を収集する。

    Parameters
    ----------
    driver : Any
        接続済み Neo4j ドライバー。
    database : str
        対象データベース名。

    Returns
    -------
    QueryResult
        ノード数・リレーション数・ラベル別件数・リレーションタイプ別件数。
    """
    logger.info("Collecting counts from database: %s", database)

    with driver.session(database=database) as session:
        # 全ノード総数
        node_result = session.run("MATCH (n) RETURN COUNT(n) AS count")
        node_count: int = node_result.single()["count"]
        logger.info("Total nodes: %d", node_count)

        # 全リレーション総数
        rel_result = session.run("MATCH ()-[r]->() RETURN COUNT(r) AS count")
        rel_count: int = rel_result.single()["count"]
        logger.info("Total relationships: %d", rel_count)

        # ラベル別ノード件数
        label_query = """
        MATCH (n)
        UNWIND labels(n) AS label
        WITH label, COUNT(n) AS count
        RETURN label, count
        ORDER BY count DESC
        """
        label_result = session.run(label_query)
        label_counts: dict[str, int] = {}
        for record in label_result:
            label_counts[record["label"]] = record["count"]
        logger.info("Label counts collected: %d labels", len(label_counts))

        # リレーションタイプ別件数
        rel_type_query = """
        MATCH ()-[r]->()
        WITH type(r) AS type, COUNT(r) AS count
        RETURN type, count
        ORDER BY count DESC
        """
        rel_type_result = session.run(rel_type_query)
        rel_type_counts: dict[str, int] = {}
        for record in rel_type_result:
            rel_type_counts[record["type"]] = record["count"]
        logger.info(
            "Relationship type counts collected: %d types", len(rel_type_counts)
        )

    return QueryResult(
        node_count=node_count,
        rel_count=rel_count,
        label_counts=label_counts,
        rel_type_counts=rel_type_counts,
    )


def format_snapshot(
    result: QueryResult,
    database: str,
    date_str: str,
) -> dict[str, Any]:
    """クエリ結果をスナップショット辞書にフォーマットする。

    Parameters
    ----------
    result : QueryResult
        Neo4j から収集した件数。
    database : str
        データベース名。
    date_str : str
        日付文字列（YYYYMMDD 形式）。

    Returns
    -------
    dict[str, Any]
        スナップショット辞書（JSON 保存用）。
    """
    return {
        "snapshot_date": date_str,
        "database": database,
        "node_count": result.node_count,
        "rel_count": result.rel_count,
        "label_counts": result.label_counts,
        "rel_type_counts": result.rel_type_counts,
        "note": (
            "Entity ラベル廃止移行（Issue #302 Wave1）前のスナップショット。"
            "ロールバック確認用基点データ。"
        ),
    }


def save_snapshot(
    snapshot: dict[str, Any],
    output_dir: Path,
    filename: str,
) -> Path:
    """スナップショットを JSON ファイルに保存する。

    Parameters
    ----------
    snapshot : dict[str, Any]
        保存するスナップショット辞書。
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
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Snapshot saved: %s", output_path)
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
        description="移行前スナップショット取得（Issue #302 Wave1）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y%m%d")
    filename = f"{date_str}_pre_migration_counts.json"

    logger.info("Starting pre-migration snapshot: database=%s", args.database)

    # Neo4j 接続
    password = os.environ.get("NEO4J_PASSWORD", _DEFAULT_PASSWORD)
    try:
        driver = GraphDatabase.driver(args.uri, auth=(_DEFAULT_USER, password))
        driver.verify_connectivity()
        logger.info("Neo4j connection verified: %s", args.uri)
    except Exception as e:
        logger.error("Failed to connect to Neo4j: %s", e)
        return 1

    try:
        # 件数収集
        result = collect_counts(driver, database=args.database)

        # 概要ログ
        logger.info(
            "Snapshot summary — nodes=%d, rels=%d, entity=%d, about=%d, mentions=%d",
            result.node_count,
            result.rel_count,
            result.label_counts.get("Entity", 0),
            result.rel_type_counts.get("ABOUT", 0),
            result.rel_type_counts.get("MENTIONS", 0),
        )

        # スナップショット整形
        snapshot = format_snapshot(result, database=args.database, date_str=date_str)

        # 保存
        output_dir = Path(args.output_dir)
        output_path = save_snapshot(snapshot, output_dir=output_dir, filename=filename)

        print(f"Snapshot saved: {output_path}")
        print(
            f"  nodes={result.node_count}, rels={result.rel_count}, "
            f"Entity={result.label_counts.get('Entity', 0)}, "
            f"ABOUT={result.rel_type_counts.get('ABOUT', 0)}, "
            f"MENTIONS={result.rel_type_counts.get('MENTIONS', 0)}"
        )
        return 0

    except Exception as e:
        logger.error("Snapshot failed: %s", e, exc_info=True)
        return 1
    finally:
        driver.close()


if __name__ == "__main__":
    sys.exit(main())
