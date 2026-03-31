#!/usr/bin/env python3
"""Source type 正規化移行スクリプト。

既存 Source ノードの ``source_type`` を 27 種から 5 種に正規化し、
NULL の ``command_source`` を ``source_type`` から推定して補完する。

マッピングテーブルは ``data/config/knowledge-graph-schema.yaml`` の
``source_type_normalization`` セクションを SSOT として読み込む。

Usage
-----
::

    # 対象件数確認（DB への書き込みなし）
    uv run python scripts/migrate_source_type.py --dry-run

    # 本番実行
    uv run python scripts/migrate_source_type.py

    # 接続先を指定
    uv run python scripts/migrate_source_type.py --neo4j-uri bolt://localhost:7688

設計方針
--------
- 冪等実行可能: 既に正規化済みの Source はスキップ
- ``--dry-run``: 変更対象件数のみ表示し DB 書き込みを行わない
- ``command_source`` NULL 補完: ``source_type`` からデフォルト値を推定して補完
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from yaml import safe_load
except ImportError:
    print("pyyaml not installed. Run: uv add pyyaml")
    sys.exit(1)

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
_DEFAULT_NEO4J_URI = "bolt://localhost:7688"
_DEFAULT_NEO4J_USER = "neo4j"

# YAML スキーマファイルのデフォルトパス（プロジェクトルートからの相対パス）
_DEFAULT_SCHEMA_PATH = Path("data/config/knowledge-graph-schema.yaml")

# 5 種の正規 source_type 値（SSOT: knowledge-graph-schema.yaml の enum_validations.source_type）
CANONICAL_SOURCE_TYPES: frozenset[str] = frozenset(
    ["web", "news", "pdf", "original", "blog"]
)
"""5 種の正規 source_type 値。"""

# source_type → デフォルト command_source マッピング
# AIDEV-NOTE: command_source は source_type から推定するデフォルト値。
# 実際の投入コマンドが異なる場合でも、NULL を埋めるためのベストエフォート補完。
SOURCE_TYPE_TO_COMMAND_SOURCE: dict[str, str] = {
    "web": "web-research",
    "news": "web-research",
    "pdf": "pdf-pipeline",
    "original": "article-writer",
    "blog": "wealth-scrape",
}
"""正規 source_type → デフォルト command_source のマッピング。"""


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass
class MigrationStats:
    """移行統計情報。"""

    source_type_normalized: int = 0
    source_type_skipped: int = 0
    source_type_failed: int = 0
    command_source_filled: int = 0
    command_source_skipped: int = 0
    command_source_failed: int = 0

    def merge(self, other: "MigrationStats") -> "MigrationStats":
        """2 つの MigrationStats を合算して返す。

        Parameters
        ----------
        other : MigrationStats
            合算対象の統計情報。

        Returns
        -------
        MigrationStats
            合算結果の新しい MigrationStats インスタンス。
        """
        return MigrationStats(
            source_type_normalized=self.source_type_normalized
            + other.source_type_normalized,
            source_type_skipped=self.source_type_skipped + other.source_type_skipped,
            source_type_failed=self.source_type_failed + other.source_type_failed,
            command_source_filled=self.command_source_filled
            + other.command_source_filled,
            command_source_skipped=self.command_source_skipped
            + other.command_source_skipped,
            command_source_failed=self.command_source_failed
            + other.command_source_failed,
        )


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def load_source_type_normalization(schema_path: Path) -> dict[str, str]:
    """YAML スキーマファイルから source_type_normalization マッピングを読み込む。

    Parameters
    ----------
    schema_path : Path
        knowledge-graph-schema.yaml のパス。

    Returns
    -------
    dict[str, str]
        ``{raw_source_type: canonical_source_type}`` のマッピング辞書。

    Raises
    ------
    FileNotFoundError
        スキーマファイルが存在しない場合。
    KeyError
        YAML 構造に ``source_type_normalization.mapping`` が存在しない場合。
    """
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    with schema_path.open(encoding="utf-8") as f:
        schema = safe_load(f)

    mapping: dict[str, str] = schema["source_type_normalization"]["mapping"]
    return mapping


def build_normalization_ops(
    nodes: list[dict[str, Any]],
    normalization_map: dict[str, str],
) -> list[dict[str, str]]:
    """異常な source_type ノードから正規化操作のリストを構築する。

    Parameters
    ----------
    nodes : list[dict[str, Any]]
        正規化対象 Source ノードのリスト。各要素に ``source_id`` と ``source_type`` が必要。
    normalization_map : dict[str, str]
        ``{raw_source_type: canonical_source_type}`` のマッピング辞書。

    Returns
    -------
    list[dict[str, str]]
        正規化操作のリスト。各要素は ``{source_id, new_source_type}`` を持つ。
        normalization_map に存在しない source_type のノードはスキップされる。
    """
    ops: list[dict[str, str]] = []
    for node in nodes:
        source_id: str = node["source_id"]
        source_type: str = node.get("source_type", "")
        new_type = normalization_map.get(source_type)
        if new_type is None:
            logger.warning(
                "Unknown source_type, skipping: source_id=%s source_type=%s",
                source_id,
                source_type,
            )
            continue
        ops.append({"source_id": source_id, "new_source_type": new_type})
    return ops


def build_null_command_source_ops(
    nodes: list[dict[str, Any]],
    source_type_to_command: dict[str, str],
) -> list[dict[str, str]]:
    """NULL command_source ノードから補完操作のリストを構築する。

    Parameters
    ----------
    nodes : list[dict[str, Any]]
        command_source が NULL の Source ノードのリスト。
        各要素に ``source_id`` と ``source_type`` が必要。
    source_type_to_command : dict[str, str]
        ``{source_type: default_command_source}`` のマッピング辞書。

    Returns
    -------
    list[dict[str, str]]
        補完操作のリスト。各要素は ``{source_id, command_source}`` を持つ。
        source_type_to_command に存在しない source_type のノードはスキップされる。
    """
    ops: list[dict[str, str]] = []
    for node in nodes:
        source_id: str = node["source_id"]
        source_type: str = node.get("source_type", "")
        command_source = source_type_to_command.get(source_type)
        if command_source is None:
            logger.warning(
                "No command_source mapping for source_type, skipping: source_id=%s source_type=%s",
                source_id,
                source_type,
            )
            continue
        ops.append({"source_id": source_id, "command_source": command_source})
    return ops


def apply_source_type_batch(
    session: Any,
    ops: list[dict[str, str]],
    mode: str,
    dry_run: bool = False,
) -> MigrationStats:
    """正規化または補完操作のリストを Neo4j セッションで実行する。

    Parameters
    ----------
    session : Any
        Neo4j セッション。
    ops : list[dict[str, str]]
        実行する操作のリスト。
        mode='source_type' の場合: ``{source_id, new_source_type}``
        mode='command_source' の場合: ``{source_id, command_source}``
    mode : str
        実行モード。'source_type' または 'command_source'。
    dry_run : bool
        True の場合、実際の書き込みをスキップして件数のみカウント。

    Returns
    -------
    MigrationStats
        実行結果の統計情報。

    Raises
    ------
    ValueError
        未知の mode が渡された場合。
    """
    if mode not in ("source_type", "command_source"):
        raise ValueError(
            f"Unknown mode: {mode!r}. Must be 'source_type' or 'command_source'."
        )

    stats = MigrationStats()

    if not ops:
        return stats

    if mode == "source_type":
        for op in ops:
            source_id = op["source_id"]
            new_source_type = op["new_source_type"]

            if dry_run:
                logger.debug(
                    "[dry-run] Would normalize: source_id=%s new_source_type=%s",
                    source_id,
                    new_source_type,
                )
                continue

            cypher = (
                "MATCH (s:Source {source_id: $source_id}) "
                "SET s.source_type = $new_source_type"
            )
            try:
                session.run(
                    cypher, source_id=source_id, new_source_type=new_source_type
                )
                stats.source_type_normalized += 1
                logger.debug(
                    "Normalized: source_id=%s new_source_type=%s",
                    source_id,
                    new_source_type,
                )
            except Exception:
                stats.source_type_failed += 1
                logger.exception(
                    "Failed to normalize source_type: source_id=%s",
                    source_id,
                )

    else:  # mode == "command_source"
        for op in ops:
            source_id = op["source_id"]
            command_source = op["command_source"]

            if dry_run:
                logger.debug(
                    "[dry-run] Would fill command_source: source_id=%s command_source=%s",
                    source_id,
                    command_source,
                )
                continue

            # AIDEV-NOTE: WHERE s.command_source IS NULL で冪等性を確保
            # 既に command_source が設定されている場合は上書きしない
            cypher = (
                "MATCH (s:Source {source_id: $source_id}) "
                "WHERE s.command_source IS NULL "
                "SET s.command_source = $command_source"
            )
            try:
                session.run(cypher, source_id=source_id, command_source=command_source)
                stats.command_source_filled += 1
                logger.debug(
                    "Filled command_source: source_id=%s command_source=%s",
                    source_id,
                    command_source,
                )
            except Exception:
                stats.command_source_failed += 1
                logger.exception(
                    "Failed to fill command_source: source_id=%s",
                    source_id,
                )

    return stats


def fetch_abnormal_source_types(
    session: Any,
    canonical_types: frozenset[str],
) -> list[dict[str, Any]]:
    """正規化が必要な（非正規型の）Source ノードを取得する。

    Parameters
    ----------
    session : Any
        Neo4j セッション。
    canonical_types : frozenset[str]
        5 種の正規 source_type 値。これ以外のノードを取得する。

    Returns
    -------
    list[dict[str, Any]]
        非正規 source_type を持つ Source ノードのリスト。
        各要素に ``source_id`` と ``source_type`` を含む。
    """
    # AIDEV-NOTE: NOT s.source_type IN $canonical_types で正規型を除外
    # また source_type が NULL のノードも除外（別途 NULL 補完フェーズで対応）
    cypher = (
        "MATCH (s:Source) "
        "WHERE s.source_type IS NOT NULL "
        "AND NOT s.source_type IN $canonical_types "
        "RETURN s.source_id AS source_id, s.source_type AS source_type"
    )
    result = session.run(cypher, canonical_types=list(canonical_types))
    records = [
        {"source_id": record["source_id"], "source_type": record["source_type"]}
        for record in result
    ]
    logger.info("Found %d Source nodes with non-canonical source_type", len(records))
    return records


def fetch_null_command_source_nodes(session: Any) -> list[dict[str, Any]]:
    """command_source が NULL の Source ノードを取得する。

    Parameters
    ----------
    session : Any
        Neo4j セッション。

    Returns
    -------
    list[dict[str, Any]]
        command_source が NULL の Source ノードのリスト。
        各要素に ``source_id`` と ``source_type`` を含む。
    """
    cypher = (
        "MATCH (s:Source) "
        "WHERE s.command_source IS NULL "
        "AND s.source_type IS NOT NULL "
        "RETURN s.source_id AS source_id, s.source_type AS source_type"
    )
    result = session.run(cypher)
    records = [
        {"source_id": record["source_id"], "source_type": record["source_type"]}
        for record in result
    ]
    logger.info("Found %d Source nodes with NULL command_source", len(records))
    return records


def run_dry_run_summary(
    session: Any,
    normalization_map: dict[str, str],
) -> None:
    """dry-run 時のサマリーを出力する。"""
    abnormal_nodes = fetch_abnormal_source_types(session, CANONICAL_SOURCE_TYPES)
    norm_ops = build_normalization_ops(abnormal_nodes, normalization_map)
    norm_skipped = len(abnormal_nodes) - len(norm_ops)

    null_nodes = fetch_null_command_source_nodes(session)
    null_ops = build_null_command_source_ops(null_nodes, SOURCE_TYPE_TO_COMMAND_SOURCE)
    null_skipped = len(null_nodes) - len(null_ops)

    print("\n=== dry-run サマリー ===")
    print(f"  非正規 source_type ノード数  : {len(abnormal_nodes):,} 件")
    print(f"  正規化操作数 (有効)           : {len(norm_ops):,} 件")
    print(f"  スキップ (未知 type)          : {norm_skipped:,} 件")
    print(f"  NULL command_source ノード数  : {len(null_nodes):,} 件")
    print(f"  補完操作数 (有効)             : {len(null_ops):,} 件")
    print(f"  スキップ (未知 source_type)   : {null_skipped:,} 件")
    print("  ※ --dry-run のため DB への書き込みは行いません")

    # source_type 別件数の内訳（正規化対象）
    type_counts: dict[str, int] = {}
    for op in norm_ops:
        new_type = op["new_source_type"]
        type_counts[new_type] = type_counts.get(new_type, 0) + 1
    if type_counts:
        print("\n  正規化後 source_type 別件数:")
        for st, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f"    {st:<15} : {cnt:,} 件")

    # command_source 別件数の内訳（補完対象）
    cs_counts: dict[str, int] = {}
    for op in null_ops:
        cs = op["command_source"]
        cs_counts[cs] = cs_counts.get(cs, 0) + 1
    if cs_counts:
        print("\n  補完後 command_source 別件数:")
        for cs, cnt in sorted(cs_counts.items(), key=lambda x: -x[1]):
            print(f"    {cs:<25} : {cnt:,} 件")


def print_stats(stats: MigrationStats) -> None:
    """移行統計情報を標準出力に出力する。"""
    print("\n=== 移行結果サマリー ===")
    print(f"  source_type 正規化 : {stats.source_type_normalized:,} 件")
    print(f"  source_type スキップ: {stats.source_type_skipped:,} 件")
    print(f"  source_type 失敗   : {stats.source_type_failed:,} 件")
    print(f"  command_source 補完: {stats.command_source_filled:,} 件")
    print(f"  command_source スキップ: {stats.command_source_skipped:,} 件")
    print(f"  command_source 失敗: {stats.command_source_failed:,} 件")


def run_phase1_source_type(
    session: Any,
    normalization_map: dict[str, str],
) -> MigrationStats:
    """Phase 1: source_type 正規化を実行する。

    Parameters
    ----------
    session : Any
        Neo4j セッション。
    normalization_map : dict[str, str]
        ``{raw_source_type: canonical_source_type}`` のマッピング辞書。

    Returns
    -------
    MigrationStats
        Phase 1 の統計情報。
    """
    logger.info("Phase 1: source_type normalization")
    abnormal_nodes = fetch_abnormal_source_types(session, CANONICAL_SOURCE_TYPES)
    if not abnormal_nodes:
        logger.info("No abnormal source_type nodes found. Skipping Phase 1.")
        return MigrationStats()

    norm_ops = build_normalization_ops(abnormal_nodes, normalization_map)
    skipped_count = len(abnormal_nodes) - len(norm_ops)
    logger.info(
        "Normalization plan: %d ops (%d skipped due to unknown type)",
        len(norm_ops),
        skipped_count,
    )
    stats = apply_source_type_batch(session, norm_ops, mode="source_type")
    stats.source_type_skipped = skipped_count
    logger.info(
        "source_type normalization complete: normalized=%d failed=%d skipped=%d",
        stats.source_type_normalized,
        stats.source_type_failed,
        stats.source_type_skipped,
    )
    if stats.source_type_failed > 0:
        logger.error(
            "%d nodes failed to normalize. Check logs for details.",
            stats.source_type_failed,
        )
    return stats


def run_phase2_command_source(session: Any) -> MigrationStats:
    """Phase 2: command_source NULL 補完を実行する。

    Parameters
    ----------
    session : Any
        Neo4j セッション。

    Returns
    -------
    MigrationStats
        Phase 2 の統計情報。
    """
    logger.info("Phase 2: command_source NULL fill")
    null_nodes = fetch_null_command_source_nodes(session)
    if not null_nodes:
        logger.info("No NULL command_source nodes found. Skipping Phase 2.")
        return MigrationStats()

    null_ops = build_null_command_source_ops(null_nodes, SOURCE_TYPE_TO_COMMAND_SOURCE)
    cs_skipped = len(null_nodes) - len(null_ops)
    logger.info(
        "command_source fill plan: %d ops (%d skipped due to unknown source_type)",
        len(null_ops),
        cs_skipped,
    )
    stats = apply_source_type_batch(session, null_ops, mode="command_source")
    stats.command_source_skipped = cs_skipped
    logger.info(
        "command_source fill complete: filled=%d failed=%d skipped=%d",
        stats.command_source_filled,
        stats.command_source_failed,
        stats.command_source_skipped,
    )
    if stats.command_source_failed > 0:
        logger.error(
            "%d nodes failed to fill command_source. Check logs for details.",
            stats.command_source_failed,
        )
    return stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Source type 正規化移行スクリプトのエントリーポイント。"""
    parser = argparse.ArgumentParser(
        description=(
            "Source ノードの source_type を 27 種から 5 種に正規化し、"
            "NULL の command_source を補完する移行スクリプト"
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
        "--schema-path",
        type=Path,
        default=_DEFAULT_SCHEMA_PATH,
        help=f"knowledge-graph-schema.yaml のパス (デフォルト: {_DEFAULT_SCHEMA_PATH})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="変更対象件数のみ表示し、DB への書き込みは行わない",
    )
    parser.add_argument(
        "--skip-source-type",
        action="store_true",
        help="source_type 正規化をスキップして command_source 補完のみ実行",
    )
    parser.add_argument(
        "--skip-command-source",
        action="store_true",
        help="command_source 補完をスキップして source_type 正規化のみ実行",
    )
    args = parser.parse_args()

    # スキーマ読み込み
    logger.info("Loading source_type_normalization from: %s", args.schema_path)
    try:
        normalization_map = load_source_type_normalization(args.schema_path)
    except (FileNotFoundError, KeyError) as e:
        logger.error("Failed to load schema: %s", e)
        sys.exit(1)

    logger.info("Loaded %d raw source_type mappings", len(normalization_map))

    # パスワード処理（dry-run でも DB 接続を行うため必須）
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
                run_dry_run_summary(session, normalization_map)
                return

            total_stats = MigrationStats()

            if not args.skip_source_type:
                total_stats = total_stats.merge(
                    run_phase1_source_type(session, normalization_map)
                )
            else:
                logger.info("Phase 1: skipped (--skip-source-type)")

            if not args.skip_command_source:
                total_stats = total_stats.merge(run_phase2_command_source(session))
            else:
                logger.info("Phase 2: skipped (--skip-command-source)")

        print_stats(total_stats)
        logger.info("Migration finished successfully")

    except Exception:
        logger.exception("Migration failed")
        sys.exit(1)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
