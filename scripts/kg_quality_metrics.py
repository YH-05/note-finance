#!/usr/bin/env python3
"""KG 品質ダッシュボード — 基盤モジュール。

knowledge-graph-schema.yaml と Neo4j DB を照合し、7カテゴリの品質指標を
計測するための DataClasses・インフラ関数・CLI を提供する。

Usage
-----
::

    # 全カテゴリ計測（デフォルト）
    python scripts/kg_quality_metrics.py

    # 特定カテゴリのみ
    python scripts/kg_quality_metrics.py --category structural

    # ドライラン（DB 接続なし）
    python scripts/kg_quality_metrics.py --dry-run

    # スナップショット保存
    python scripts/kg_quality_metrics.py --save-snapshot

    # レポート出力
    python scripts/kg_quality_metrics.py --report output.md

    # スナップショット比較
    python scripts/kg_quality_metrics.py --compare snapshot_prev.json
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

import yaml

try:
    from neo4j import GraphDatabase
except ImportError:
    print("neo4j driver not installed. Run: uv add neo4j")
    sys.exit(1)

try:
    from finance.utils.logging_config import get_logger

    logger = get_logger(__name__)
except ImportError:
    import logging

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DataClasses
# ---------------------------------------------------------------------------


@dataclass
class MetricValue:
    """個別メトリクスの計測値。

    Attributes
    ----------
    value : float
        計測値。
    unit : str
        単位（"%", "count", "ratio" 等）。
    status : str
        閾値判定結果。"green", "yellow", "red" のいずれか。
    stub : bool
        未実装メトリクスのスタブフラグ。
    """

    value: float
    unit: str
    status: str
    stub: bool = False


@dataclass
class CategoryResult:
    """カテゴリ単位の品質結果。

    Attributes
    ----------
    name : str
        カテゴリ名（"structural", "completeness" 等）。
    score : float
        カテゴリスコア（0.0 - 100.0）。
    metrics : list[MetricValue]
        カテゴリ内の個別メトリクスリスト。
    """

    name: str
    score: float
    metrics: list[MetricValue] = field(default_factory=list)


@dataclass
class CheckRuleResult:
    """チェックルールの検証結果。

    Attributes
    ----------
    rule_name : str
        ルール名（"PascalCase遵守" 等）。
    pass_rate : float
        通過率（0.0 - 1.0）。
    violations : list[str]
        違反サンプルのリスト。
    """

    rule_name: str
    pass_rate: float
    violations: list[str] = field(default_factory=list)


@dataclass
class QualitySnapshot:
    """品質スナップショット全体。

    Attributes
    ----------
    categories : list[CategoryResult]
        全カテゴリの計測結果。
    overall_score : float
        総合スコア（0.0 - 100.0）。
    timestamp : datetime
        計測日時（UTC）。
    """

    categories: list[CategoryResult]
    overall_score: float
    timestamp: datetime


# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

THRESHOLDS: dict[str, dict[str, float]] = {
    "node_count": {"green": 3000, "yellow": 1000},
    "relationship_count": {"green": 5000, "yellow": 2000},
    "avg_degree": {"green": 3.0, "yellow": 1.5},
    "connected_component_ratio": {"green": 0.9, "yellow": 0.7},
    "orphan_node_ratio": {"green": 0.05, "yellow": 0.15},
    "property_fill_rate": {"green": 0.8, "yellow": 0.6},
    "required_property_coverage": {"green": 0.95, "yellow": 0.8},
    "label_consistency": {"green": 0.95, "yellow": 0.8},
    "entity_type_coverage": {"green": 0.9, "yellow": 0.7},
    "source_freshness_days": {"green": 7, "yellow": 30},
    "claim_evidence_ratio": {"green": 0.8, "yellow": 0.5},
    "financial_data_completeness": {"green": 0.7, "yellow": 0.4},
    "path_reachability": {"green": 0.6, "yellow": 0.3},
}
"""各メトリクスの green/yellow/red 閾値。

green: 基準値以上（source_freshness_days は以下）で良好。
yellow: green 未満だが yellow 以上で注意。
それ以外は red。
"""

ALLOWED_ENTITY_TYPES: frozenset[str] = frozenset(
    {
        "company",
        "index",
        "sector",
        "indicator",
        "currency",
        "commodity",
        "person",
        "organization",
        "country",
        "instrument",
    }
)
"""Entity.entity_type の許可リスト。knowledge-graph-schema.yaml v2.3 準拠。"""


# ---------------------------------------------------------------------------
# インフラ関数
# ---------------------------------------------------------------------------


def create_driver(
    uri: str = "bolt://localhost:7688",
    user: str = "neo4j",
    password: str | None = None,
) -> Any:
    """Neo4j ドライバーを作成し接続確認を行う。

    Parameters
    ----------
    uri : str
        Neo4j 接続 URI。デフォルトは ``bolt://localhost:7688``。
    user : str
        Neo4j ユーザー名。
    password : str | None
        Neo4j パスワード。``None`` の場合は ``NEO4J_PASSWORD`` 環境変数を
        参照し、未設定時は ``'gomasuke'`` をデフォルト値として使用する。

    Returns
    -------
    Any
        接続確認済みの Neo4j ドライバー。
    """
    if password is None:
        password = os.environ.get("NEO4J_PASSWORD", "gomasuke")

    logger.info("Connecting to Neo4j: %s", uri)
    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
    logger.info("Neo4j connection verified")
    return driver


def load_schema(schema_path: Path) -> dict[str, Any]:
    """knowledge-graph-schema.yaml を読み込む。

    Parameters
    ----------
    schema_path : Path
        YAML スキーマファイルのパス。

    Returns
    -------
    dict[str, Any]
        スキーマ定義の辞書。

    Raises
    ------
    FileNotFoundError
        スキーマファイルが存在しない場合。
    """
    if not schema_path.exists():
        msg = f"Schema file not found: {schema_path}"
        raise FileNotFoundError(msg)

    with schema_path.open(encoding="utf-8") as f:
        schema: dict[str, Any] = yaml.safe_load(f)

    logger.info("Schema loaded: %s (version %s)", schema_path, schema.get("version"))
    return schema


def get_counts(session: Any) -> dict[str, int]:
    """ノード数・リレーション数の基本集計を取得する。

    Memory ノードを除外してカウントする。

    Parameters
    ----------
    session
        Neo4j セッション。

    Returns
    -------
    dict[str, int]
        ``node_count`` と ``relationship_count`` を含む辞書。
    """
    node_query = """
    MATCH (n)
    WHERE NOT 'Memory' IN labels(n)
    RETURN count(n) AS count
    """
    node_result = session.run(node_query)
    node_count: int = node_result.single()["count"]

    rel_query = """
    MATCH (a)-[r]->(b)
    WHERE NOT 'Memory' IN labels(a) AND NOT 'Memory' IN labels(b)
    RETURN count(r) AS count
    """
    rel_result = session.run(rel_query)
    rel_count: int = rel_result.single()["count"]

    logger.info("Counts: nodes=%d, relationships=%d", node_count, rel_count)
    return {"node_count": node_count, "relationship_count": rel_count}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

CATEGORY_CHOICES = [
    "structural",
    "completeness",
    "consistency",
    "accuracy",
    "timeliness",
    "finance_specific",
    "discoverability",
    "all",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """コマンドライン引数を解析する。

    Parameters
    ----------
    argv : list[str] | None
        引数リスト。``None`` の場合は ``sys.argv[1:]`` を使用する。

    Returns
    -------
    argparse.Namespace
        解析済み引数。
    """
    parser = argparse.ArgumentParser(
        description="KG品質ダッシュボード — 7カテゴリの品質指標を計測",
    )
    parser.add_argument(
        "--category",
        choices=CATEGORY_CHOICES,
        default="all",
        help="計測するカテゴリ（デフォルト: all）",
    )
    parser.add_argument(
        "--save-snapshot",
        action="store_true",
        help="計測結果をスナップショットとして保存",
    )
    parser.add_argument(
        "--report",
        help="Markdown レポート出力先パス",
    )
    parser.add_argument(
        "--compare",
        help="比較対象のスナップショット JSON パス",
    )
    parser.add_argument(
        "--neo4j-uri",
        default=os.environ.get("NEO4J_URI", "bolt://localhost:7688"),
        help="Neo4j 接続 URI（デフォルト: bolt://localhost:7688）",
    )
    parser.add_argument(
        "--neo4j-user",
        default=os.environ.get("NEO4J_USER", "neo4j"),
        help="Neo4j ユーザー名（デフォルト: neo4j）",
    )
    parser.add_argument(
        "--neo4j-password",
        default=os.environ.get("NEO4J_PASSWORD", "gomasuke"),
        help="Neo4j パスワード（デフォルト: 環境変数 NEO4J_PASSWORD または 'gomasuke'）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB 接続なしでの動作確認",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """エントリーポイント。"""
    args = parse_args()
    logger.info(
        "KG Quality Metrics started (category=%s, dry_run=%s)",
        args.category,
        args.dry_run,
    )

    if args.dry_run:
        logger.info("Dry-run mode: skipping DB connection")
        schema = load_schema(Path("data/config/knowledge-graph-schema.yaml"))
        logger.info(
            "Schema version: %s, nodes: %d, relationships: %d",
            schema.get("version"),
            len(schema.get("nodes", {})),
            len(schema.get("relationships", {})),
        )
        return

    driver = create_driver(
        uri=args.neo4j_uri,
        user=args.neo4j_user,
        password=args.neo4j_password,
    )

    try:
        schema = load_schema(Path("data/config/knowledge-graph-schema.yaml"))
        with driver.session() as session:
            counts = get_counts(session)
            logger.info("Base counts: %s", counts)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
