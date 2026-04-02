#!/usr/bin/env python3
"""孤立ノード処理スクリプト。

孤立 Person（Fact/Claim から参照されていない）と
孤立 Fact（RELATES_TO → 個別エンティティラベルノード が欠落）を検出し、
``Archived`` ラベルを付与してアーカイブする。

対象ノードの定義
----------------
- **孤立 Person**: ``Person`` かつ ``RELATES_TO``
  リレーションが一切ない（``IS_TYPE`` のみ保持）
- **孤立 Fact**: ``Fact`` かつ
  ``NOT EXISTS { (f)-[:RELATES_TO]->(e:Company|...|Product) }``

Wave7 (Issue #312) 更新: :Entity → 個別ラベル union、RELATES_TO に統一

Issue #306 - Wave 2: 孤立ノード処理（Entity 64 件・Fact 577 件）

Usage
-----
::

    # ドライランで件数確認（DB 書き込みなし）
    uv run python scripts/process_isolated_nodes.py --dry-run

    # 本番実行（Archived ラベル付与）
    uv run python scripts/process_isolated_nodes.py

    # データベース・出力ディレクトリを指定
    uv run python scripts/process_isolated_nodes.py --database research --output-dir data/migration

Notes
-----
- 冪等実行可能: 既に Archived ラベルが付いているノードは再処理しない
- Neo4j Enterprise Multi-Database 環境（bolt://localhost:7687）を前提とする
- Memory ノードは除外
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

# AIDEV-NOTE: Wave7 (Issue #312) — :Entity → 個別ラベル union、ABOUT/MENTIONS → RELATES_TO に更新

# 孤立 Person 検出クエリ
# RELATES_TO リレーションを一切持たない Person ノードを対象とする
# 既に Archived ラベルが付いているノードは除外（冪等）
_ISOLATED_ENTITY_QUERY = """
MATCH (e:Person)
WHERE NOT 'Archived' IN labels(e)
  AND NOT ()-[:RELATES_TO]->(e)
  AND NOT (e)-[:RELATES_TO]->()
RETURN elementId(e) AS element_id,
       e.name AS name,
       e.name AS entity_key,
       'person' AS entity_type
ORDER BY e.name
"""

# 孤立 Fact 検出クエリ
# 個別エンティティラベルへの RELATES_TO リレーションが欠落した Fact を対象とする
# 既に Archived ラベルが付いているノードは除外（冪等）
_ISOLATED_FACT_QUERY = """
MATCH (f:Fact)
WHERE NOT 'Archived' IN labels(f)
  AND NOT EXISTS { (f)-[:RELATES_TO]->(e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product) }
OPTIONAL MATCH (f)-[:EXTRACTED_FROM]->(s:Source)
RETURN elementId(f) AS element_id,
       f.fact_id AS fact_id,
       f.content AS content,
       s.source_type AS source_type,
       s.url AS source_url
ORDER BY s.source_type, elementId(f)
"""

# Archived ラベル付与クエリ（個別エンティティラベルノード）
_ARCHIVE_ENTITY_QUERY = """
MATCH (e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product)
WHERE elementId(e) IN $element_ids
SET e:Archived
RETURN COUNT(e) AS archived_count
"""

# Archived ラベル付与クエリ（Fact）
_ARCHIVE_FACT_QUERY = """
MATCH (f:Fact)
WHERE elementId(f) IN $element_ids
SET f:Archived
RETURN COUNT(f) AS archived_count
"""

# 検証クエリ: 処理後の孤立ノード残存数
_VERIFY_ENTITY_QUERY = """
MATCH (e:Person)
WHERE NOT 'Archived' IN labels(e)
  AND NOT ()-[:RELATES_TO]->(e)
  AND NOT (e)-[:RELATES_TO]->()
RETURN COUNT(e) AS remaining_count
"""

_VERIFY_FACT_QUERY = """
MATCH (f:Fact)
WHERE NOT 'Archived' IN labels(f)
  AND NOT EXISTS { (f)-[:RELATES_TO]->(e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product) }
RETURN COUNT(f) AS remaining_count
"""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ProcessConfig:
    """孤立ノード処理設定。

    Attributes
    ----------
    database : str
        Neo4j データベース名。
    uri : str
        Neo4j 接続 URI。
    output_dir : Path
        処理結果 JSON 出力ディレクトリ。
    dry_run : bool
        True の場合 DB 書き込みを行わない。
    batch_size : int
        1バッチあたりの処理ノード数。
    """

    database: str = _DEFAULT_DATABASE
    uri: str = _DEFAULT_URI
    output_dir: Path = field(default_factory=lambda: _DEFAULT_OUTPUT_DIR)
    dry_run: bool = False
    batch_size: int = 100


@dataclass
class IsolatedEntityNode:
    """孤立 Entity ノード情報。

    Attributes
    ----------
    element_id : str
        Neo4j element ID。
    name : str
        ノード name プロパティ。
    entity_key : str | None
        entity_key プロパティ。
    entity_type : str | None
        entity_type プロパティ。
    """

    element_id: str
    name: str
    entity_key: str | None
    entity_type: str | None


@dataclass
class IsolatedFactNode:
    """孤立 Fact ノード情報。

    Attributes
    ----------
    element_id : str
        Neo4j element ID。
    fact_id : str | None
        fact_id プロパティ。
    content : str | None
        content プロパティ（先頭100文字）。
    source_type : str | None
        接続 Source の source_type（なければ None）。
    source_url : str | None
        接続 Source の URL（なければ None）。
    """

    element_id: str
    fact_id: str | None
    content: str | None
    source_type: str | None
    source_url: str | None


@dataclass
class ProcessResult:
    """処理実行結果。

    Attributes
    ----------
    entity_archived : int
        Archived ラベルを付与した Entity 数。
    fact_archived : int
        Archived ラベルを付与した Fact 数。
    entity_remaining : int
        処理後に残存する孤立 Entity 数。
    fact_remaining : int
        処理後に残存する孤立 Fact 数。
    dry_run : bool
        ドライランモードの場合 True。
    """

    entity_archived: int = 0
    fact_archived: int = 0
    entity_remaining: int = 0
    fact_remaining: int = 0
    dry_run: bool = False


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def collect_isolated_entities(
    driver: Any,
    database: str = _DEFAULT_DATABASE,
) -> list[IsolatedEntityNode]:
    """孤立 Entity:Person ノードを全件取得する。

    Parameters
    ----------
    driver : Any
        接続済み Neo4j ドライバー。
    database : str
        対象データベース名。

    Returns
    -------
    list[IsolatedEntityNode]
        孤立 Entity ノードのリスト。孤立がない場合は空リスト。
    """
    logger.info("Collecting isolated Entity:Person nodes from database: %s", database)
    nodes: list[IsolatedEntityNode] = []

    with driver.session(database=database) as session:
        result = session.run(_ISOLATED_ENTITY_QUERY)
        for record in result:
            nodes.append(
                IsolatedEntityNode(
                    element_id=record["element_id"],
                    name=record["name"] or "",
                    entity_key=record["entity_key"],
                    entity_type=record["entity_type"],
                )
            )

    logger.info("Isolated Entity:Person nodes found: %d", len(nodes))
    return nodes


def collect_isolated_facts(
    driver: Any,
    database: str = _DEFAULT_DATABASE,
) -> list[IsolatedFactNode]:
    """孤立 Fact ノードを全件取得する。

    Parameters
    ----------
    driver : Any
        接続済み Neo4j ドライバー。
    database : str
        対象データベース名。

    Returns
    -------
    list[IsolatedFactNode]
        孤立 Fact ノードのリスト。孤立がない場合は空リスト。
    """
    logger.info("Collecting isolated Fact nodes from database: %s", database)
    nodes: list[IsolatedFactNode] = []

    with driver.session(database=database) as session:
        result = session.run(_ISOLATED_FACT_QUERY)
        for record in result:
            content = record["content"]
            # content は長い場合があるので先頭 100 文字のみ記録
            content_preview = (
                (content[:100] + "...") if content and len(content) > 100 else content
            )
            nodes.append(
                IsolatedFactNode(
                    element_id=record["element_id"],
                    fact_id=record["fact_id"],
                    content=content_preview,
                    source_type=record["source_type"],
                    source_url=record["source_url"],
                )
            )

    logger.info("Isolated Fact nodes found: %d", len(nodes))
    return nodes


def archive_nodes(
    driver: Any,
    element_ids: list[str],
    node_type: str,
    database: str = _DEFAULT_DATABASE,
    batch_size: int = 100,
) -> int:
    """ノードに Archived ラベルを付与する。

    Parameters
    ----------
    driver : Any
        接続済み Neo4j ドライバー。
    element_ids : list[str]
        処理対象ノードの element ID リスト。
    node_type : str
        ノード種別（"entity" or "fact"）。ログ・クエリ選択に使用。
    database : str
        対象データベース名。
    batch_size : int
        1バッチあたりの処理件数。

    Returns
    -------
    int
        Archived ラベルを付与したノード総数。
    """
    if not element_ids:
        return 0

    query = _ARCHIVE_ENTITY_QUERY if node_type == "entity" else _ARCHIVE_FACT_QUERY
    total_archived = 0

    # バッチ処理でタイムアウトを回避
    for i in range(0, len(element_ids), batch_size):
        batch = element_ids[i : i + batch_size]
        with driver.session(database=database) as session:
            result = session.run(query, element_ids=batch)
            record = result.single()
            count = record["archived_count"] if record else 0
            total_archived += count
            logger.info(
                "Archived %s nodes: batch=%d/%d count=%d",
                node_type,
                i // batch_size + 1,
                (len(element_ids) + batch_size - 1) // batch_size,
                count,
            )

    logger.info("Total archived %s nodes: %d", node_type, total_archived)
    return total_archived


def verify_isolation_resolved(
    driver: Any,
    database: str = _DEFAULT_DATABASE,
) -> tuple[int, int]:
    """処理後の孤立ノード残存数を検証する。

    Parameters
    ----------
    driver : Any
        接続済み Neo4j ドライバー。
    database : str
        対象データベース名。

    Returns
    -------
    tuple[int, int]
        (entity_remaining, fact_remaining) の残存件数タプル。
        両方 0 が理想。
    """
    logger.info("Verifying isolation resolved in database: %s", database)

    with driver.session(database=database) as session:
        er = session.run(_VERIFY_ENTITY_QUERY).single()
        entity_remaining = er["remaining_count"] if er else 0

        fr = session.run(_VERIFY_FACT_QUERY).single()
        fact_remaining = fr["remaining_count"] if fr else 0

    if entity_remaining == 0 and fact_remaining == 0:
        logger.info(
            "Verification passed: no isolated nodes remain (excluding Archived)"
        )
    else:
        logger.warning(
            "Isolated nodes still remain: entity=%d fact=%d",
            entity_remaining,
            fact_remaining,
        )
    return entity_remaining, fact_remaining


def format_process_report(
    isolated_entities: list[IsolatedEntityNode],
    isolated_facts: list[IsolatedFactNode],
    result: ProcessResult,
    date_str: str,
) -> dict[str, Any]:
    """処理結果をレポート辞書にフォーマットする。

    Parameters
    ----------
    isolated_entities : list[IsolatedEntityNode]
        処理対象だった孤立 Entity ノードリスト。
    isolated_facts : list[IsolatedFactNode]
        処理対象だった孤立 Fact ノードリスト。
    result : ProcessResult
        処理実行結果。
    date_str : str
        実行日付文字列（YYYYMMDD 形式）。

    Returns
    -------
    dict[str, Any]
        レポート辞書（JSON 保存用）。
    """
    # Fact の source_type 別集計
    fact_by_source: dict[str, int] = {}
    for f in isolated_facts:
        key = f.source_type or "null"
        fact_by_source[key] = fact_by_source.get(key, 0) + 1

    return {
        "generated_at": date_str,
        "database": _DEFAULT_DATABASE,
        "dry_run": result.dry_run,
        "issue": "#306",
        "description": "Wave2 孤立ノード処理: Archived ラベル付与",
        "policy": {
            "isolated_entity": "Person かつ RELATES_TO リレーション欠落 → Archived ラベル付与",
            "isolated_fact": "Fact かつ RELATES_TO → 個別エンティティラベル リレーション欠落 → Archived ラベル付与",
        },
        "summary": {
            "entity_detected": len(isolated_entities),
            "entity_archived": result.entity_archived,
            "entity_remaining_after": result.entity_remaining,
            "fact_detected": len(isolated_facts),
            "fact_archived": result.fact_archived,
            "fact_remaining_after": result.fact_remaining,
            "fact_by_source_type": fact_by_source,
        },
        "isolated_entities": [
            {
                "element_id": e.element_id,
                "name": e.name,
                "entity_key": e.entity_key,
                "entity_type": e.entity_type,
            }
            for e in isolated_entities
        ],
        "isolated_facts_sample": [
            {
                "element_id": f.element_id,
                "fact_id": f.fact_id,
                "content_preview": f.content,
                "source_type": f.source_type,
                "source_url": f.source_url,
            }
            for f in isolated_facts[:50]  # サンプルとして先頭 50 件のみ記録
        ],
        "note": (
            "孤立ノードは Archived ラベルで保護。"
            "孤立 Fact の根本修復（LLM NER バッチ）は後続 Wave で実施予定。"
        ),
    }


def save_report(
    report: dict[str, Any],
    output_dir: Path,
    filename: str,
) -> Path:
    """レポートを JSON ファイルに保存する。

    Parameters
    ----------
    report : dict[str, Any]
        保存するレポート辞書。
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

    class _Neo4jJsonEncoder(json.JSONEncoder):
        def default(self, o: Any) -> Any:
            if hasattr(o, "iso_format"):
                return o.iso_format()
            if hasattr(o, "isoformat"):
                return o.isoformat()
            return super().default(o)

    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, cls=_Neo4jJsonEncoder),
        encoding="utf-8",
    )
    logger.info("Report saved: %s", output_path)
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
        description="孤立ノード処理（Archived ラベル付与）（Issue #306 Wave2）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python scripts/process_isolated_nodes.py --dry-run
  uv run python scripts/process_isolated_nodes.py
  uv run python scripts/process_isolated_nodes.py --database research --output-dir data/migration
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
        help="DB 書き込みなしで孤立ノード件数のみ確認",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="1バッチあたりの処理ノード数（デフォルト: 100）",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="ログレベル（デフォルト: INFO）",
    )
    return parser.parse_args(argv)


def _run_process(
    driver: Any,
    database: str,
    dry_run: bool,
    batch_size: int,
    date_str: str,
    output_dir: Path,
) -> tuple[int, Path]:
    """孤立ノード処理のコアロジック。

    Parameters
    ----------
    driver : Any
        接続済み Neo4j ドライバー。
    database : str
        対象データベース名。
    dry_run : bool
        True の場合 DB 書き込みを行わない。
    batch_size : int
        1バッチあたりの処理件数。
    date_str : str
        実行日付文字列（YYYYMMDD 形式）。
    output_dir : Path
        レポート出力ディレクトリ。

    Returns
    -------
    tuple[int, Path]
        (exit_code, report_path) のタプル。exit_code は 0: 成功、1: 失敗。
    """
    # 孤立ノード収集
    isolated_entities = collect_isolated_entities(driver, database=database)
    isolated_facts = collect_isolated_facts(driver, database=database)

    if not isolated_entities and not isolated_facts:
        logger.info("No isolated nodes found. Nothing to do.")
        print("孤立 Entity: 0件 / 孤立 Fact: 0件（処理不要）")
        report = format_process_report([], [], ProcessResult(dry_run=dry_run), date_str)
        filename = f"{date_str}_isolated_nodes_report.json"
        output_path = save_report(report, output_dir=output_dir, filename=filename)
        return 0, output_path

    print(
        f"孤立 Entity:Person: {len(isolated_entities)}件 / "
        f"孤立 Fact: {len(isolated_facts)}件"
    )

    result = ProcessResult(dry_run=dry_run)

    if dry_run:
        logger.info(
            "[DRY-RUN] Would archive: entity=%d fact=%d",
            len(isolated_entities),
            len(isolated_facts),
        )
        result.entity_archived = len(isolated_entities)
        result.fact_archived = len(isolated_facts)
    else:
        _archive_all(
            driver, isolated_entities, isolated_facts, database, batch_size, result
        )
        entity_rem, fact_rem = verify_isolation_resolved(driver, database=database)
        result.entity_remaining = entity_rem
        result.fact_remaining = fact_rem

    # レポート生成・保存
    report = format_process_report(
        isolated_entities=isolated_entities,
        isolated_facts=isolated_facts,
        result=result,
        date_str=date_str,
    )
    filename = f"{date_str}_isolated_nodes_report.json"
    output_path = save_report(report, output_dir=output_dir, filename=filename)

    _print_summary(result, dry_run)
    print(f"レポート保存: {output_path}")
    return 0, output_path


def _archive_all(
    driver: Any,
    isolated_entities: list[IsolatedEntityNode],
    isolated_facts: list[IsolatedFactNode],
    database: str,
    batch_size: int,
    result: ProcessResult,
) -> None:
    """Entity と Fact に Archived ラベルを付与する。

    Parameters
    ----------
    driver : Any
        接続済み Neo4j ドライバー。
    isolated_entities : list[IsolatedEntityNode]
        アーカイブ対象 Entity ノードリスト。
    isolated_facts : list[IsolatedFactNode]
        アーカイブ対象 Fact ノードリスト。
    database : str
        対象データベース名。
    batch_size : int
        1バッチあたりの処理件数。
    result : ProcessResult
        処理結果オブジェクト（更新される）。
    """
    if isolated_entities:
        entity_ids = [e.element_id for e in isolated_entities]
        result.entity_archived = archive_nodes(
            driver,
            element_ids=entity_ids,
            node_type="entity",
            database=database,
            batch_size=batch_size,
        )

    if isolated_facts:
        fact_ids = [f.element_id for f in isolated_facts]
        result.fact_archived = archive_nodes(
            driver,
            element_ids=fact_ids,
            node_type="fact",
            database=database,
            batch_size=batch_size,
        )


def _print_summary(result: ProcessResult, dry_run: bool) -> None:
    """処理結果サマリーを標準出力に表示する。

    Parameters
    ----------
    result : ProcessResult
        処理実行結果。
    dry_run : bool
        ドライランモードの場合 True。
    """
    mode = "[DRY-RUN] " if dry_run else ""
    print(
        f"{mode}Archived: Entity={result.entity_archived}件 / Fact={result.fact_archived}件"
    )
    if not dry_run:
        print(
            f"残存孤立ノード: Entity={result.entity_remaining}件 / "
            f"Fact={result.fact_remaining}件"
        )
        if result.entity_remaining == 0 and result.fact_remaining == 0:
            print("孤立ノード 0 件確認: OK")
        else:
            logger.warning(
                "Isolated nodes still remain: entity=%d fact=%d",
                result.entity_remaining,
                result.fact_remaining,
            )


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
        "process_isolated_nodes starting: database=%s dry_run=%s",
        args.database,
        args.dry_run,
    )

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
        exit_code, _ = _run_process(
            driver=driver,
            database=args.database,
            dry_run=args.dry_run,
            batch_size=args.batch_size,
            date_str=date_str,
            output_dir=Path(args.output_dir),
        )
        return exit_code

    except Exception as e:
        logger.error("process_isolated_nodes failed: %s", e, exc_info=True)
        return 1
    finally:
        driver.close()


if __name__ == "__main__":
    sys.exit(main())
