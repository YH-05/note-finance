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

green: 基準値以上で良好。ただし「lower is better」メトリクス
（``LOWER_IS_BETTER`` に含まれるもの）は基準値以下で良好。
yellow: green 未満だが yellow 以上で注意（lower is better は逆）。
それ以外は red。
"""

LOWER_IS_BETTER: frozenset[str] = frozenset(
    {
        "source_freshness_days",
        "orphan_node_ratio",
    }
)
"""値が小さいほど良いメトリクス。evaluate_status で閾値の比較方向を反転する。"""

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


def evaluate_status(metric_name: str, value: float) -> str:
    """メトリクス値を閾値と比較しステータスを返す。

    Parameters
    ----------
    metric_name : str
        メトリクス名。``THRESHOLDS`` に定義されている必要がある。
    value : float
        計測値。

    Returns
    -------
    str
        ``"green"`` / ``"yellow"`` / ``"red"`` のいずれか。
        ``metric_name`` が ``THRESHOLDS`` に未定義の場合は ``"yellow"``。
    """
    thresholds = THRESHOLDS.get(metric_name)
    if thresholds is None:
        return "yellow"

    green_th = thresholds["green"]
    yellow_th = thresholds["yellow"]

    # lower-is-better メトリクスは比較方向を反転
    if metric_name in LOWER_IS_BETTER:
        is_green = value <= green_th
        is_yellow = value <= yellow_th
    else:
        is_green = value >= green_th
        is_yellow = value >= yellow_th

    if is_green:
        return "green"
    return "yellow" if is_yellow else "red"


# ---------------------------------------------------------------------------
# 計測関数（6カテゴリ）
# ---------------------------------------------------------------------------

GICS_SECTOR_COUNT = 11
"""GICS 11セクター数。セクターカバレッジ計算の分母。"""


def _compute_category_score(metrics: list[MetricValue]) -> float:
    """メトリクスリストからカテゴリスコア（0-100）を算出する。

    green=100, yellow=50, red=0 の単純平均。
    """
    if not metrics:
        return 0.0
    return round(
        sum(
            100.0 if m.status == "green" else 50.0 if m.status == "yellow" else 0.0
            for m in metrics
        )
        / len(metrics),
        1,
    )


def measure_structural(session: Any) -> CategoryResult:
    """構造指標を計測する。

    エッジ密度・平均次数・連結性（BFS近似）・孤立率の4指標を返す。

    Parameters
    ----------
    session
        Neo4j セッション。

    Returns
    -------
    CategoryResult
        ``"structural"`` カテゴリの計測結果。
    """
    counts = get_counts(session)
    node_count = counts["node_count"]
    rel_count = counts["relationship_count"]

    # エッジ密度: relationships / (nodes * (nodes - 1))
    if node_count > 1:
        edge_density = rel_count / (node_count * (node_count - 1))
    else:
        edge_density = 0.0

    # 平均次数
    avg_degree_query = """
    MATCH (n)
    WHERE NOT 'Memory' IN labels(n)
    OPTIONAL MATCH (n)-[r]-()
    WITH n, count(r) AS degree
    RETURN avg(degree) AS avg_degree
    """
    avg_degree_result = session.run(avg_degree_query)
    avg_degree: float = avg_degree_result.single()["avg_degree"] or 0.0

    # 孤立ノード数（次数0）
    orphan_query = """
    MATCH (n)
    WHERE NOT 'Memory' IN labels(n)
    AND NOT (n)-[]-()
    RETURN count(n) AS orphan_count
    """
    orphan_result = session.run(orphan_query)
    orphan_count: int = orphan_result.single()["orphan_count"]
    orphan_ratio = orphan_count / node_count if node_count > 0 else 0.0

    # 連結性（BFS 近似）: ランダムな開始ノードから到達可能なノード比率
    start_query = """
    MATCH (n)
    WHERE NOT 'Memory' IN labels(n)
    RETURN elementId(n) AS start_id
    LIMIT 1
    """
    start_result = session.run(start_query)
    start_record = start_result.single()
    if start_record is not None:
        start_id = start_record["start_id"]
        reachable_query = """
        MATCH (start)
        WHERE elementId(start) = $start_id
        AND NOT 'Memory' IN labels(start)
        CALL apoc.path.subgraphNodes(start, {maxLevel: -1}) YIELD node
        WITH node
        WHERE NOT 'Memory' IN labels(node)
        RETURN count(DISTINCT node) AS reachable
        """
        try:
            reachable_result = session.run(reachable_query, start_id=start_id)
            reachable: int = reachable_result.single()["reachable"]
        except Exception:
            # APOC が利用できない場合は BFS フォールバック
            logger.warning("APOC not available, using simple BFS approximation")
            bfs_query = """
            MATCH (start)
            WHERE elementId(start) = $start_id
            AND NOT 'Memory' IN labels(start)
            MATCH path = (start)-[*1..10]-(connected)
            WHERE NOT 'Memory' IN labels(connected)
            RETURN count(DISTINCT connected) + 1 AS reachable
            """
            reachable_result = session.run(bfs_query, start_id=start_id)
            reachable = reachable_result.single()["reachable"]
        connected_ratio = reachable / node_count if node_count > 0 else 0.0
    else:
        connected_ratio = 0.0

    metrics = [
        MetricValue(
            value=round(edge_density, 6),
            unit="ratio",
            status=evaluate_status("connected_component_ratio", edge_density),
        ),
        MetricValue(
            value=round(avg_degree, 2),
            unit="count",
            status=evaluate_status("avg_degree", avg_degree),
        ),
        MetricValue(
            value=round(connected_ratio, 4),
            unit="ratio",
            status=evaluate_status("connected_component_ratio", connected_ratio),
        ),
        MetricValue(
            value=round(orphan_ratio, 4),
            unit="ratio",
            status=evaluate_status("orphan_node_ratio", orphan_ratio),
        ),
    ]

    score = _compute_category_score(metrics)

    logger.info(
        "Structural: edge_density=%.6f, avg_degree=%.2f, "
        "connected_ratio=%.4f, orphan_ratio=%.4f, score=%.1f",
        edge_density,
        avg_degree,
        connected_ratio,
        orphan_ratio,
        score,
    )
    return CategoryResult(name="structural", score=score, metrics=metrics)


def measure_completeness(session: Any, schema: dict[str, Any]) -> CategoryResult:
    """完全性指標を計測する。

    スキーマ YAML の ``required`` プロパティから動的に Cypher クエリを生成し、
    各ラベルの必須プロパティ充填率を計測する。Sector / Metric ノードは
    スキーマ YAML 未定義のためハードコード定義で計測対象に含める。

    Parameters
    ----------
    session
        Neo4j セッション。
    schema : dict[str, Any]
        ``load_schema()`` で読み込んだスキーマ定義。

    Returns
    -------
    CategoryResult
        ``"completeness"`` カテゴリの計測結果。
    """
    fill_rates: list[float] = []

    # スキーマ YAML から required プロパティを抽出して充填率を計測
    # AIDEV-NOTE: label/prop_name は信頼済みスキーマ YAML 由来（ユーザー入力ではない）
    nodes_def = schema.get("nodes", {})
    for label, node_def in nodes_def.items():
        props = node_def.get("properties", {})
        required_props = [
            prop_name
            for prop_name, prop_def in props.items()
            if prop_def.get("required", False)
        ]
        for prop_name in required_props:
            query = f"""
            MATCH (n:{label})
            WHERE NOT 'Memory' IN labels(n)
            RETURN count(n) AS total,
                   count(n.{prop_name}) AS filled
            """
            result = session.run(query)
            record = result.single()
            total = record["total"]
            filled = record["filled"]
            rate = filled / total if total > 0 else 1.0
            fill_rates.append(rate)

    # ハードコード定義: Sector ノード数
    sector_query = """
    MATCH (n:Sector)
    WHERE NOT 'Memory' IN labels(n)
    RETURN count(n) AS count
    """
    sector_result = session.run(sector_query)
    sector_count: int = sector_result.single()["count"]
    sector_coverage = sector_count / GICS_SECTOR_COUNT if GICS_SECTOR_COUNT > 0 else 0.0
    fill_rates.append(sector_coverage)

    # ハードコード定義: Metric (FinancialDataPoint) ノード数
    metric_query = """
    MATCH (n:FinancialDataPoint)
    WHERE NOT 'Memory' IN labels(n)
    RETURN count(n) AS count
    """
    metric_result = session.run(metric_query)
    metric_count: int = metric_result.single()["count"]
    # FinancialDataPoint の存在自体を充填率としてカウント（0件なら0%）
    metric_fill = min(metric_count / 100.0, 1.0) if metric_count > 0 else 0.0
    fill_rates.append(metric_fill)

    # 総合充填率
    overall_fill = sum(fill_rates) / len(fill_rates) if fill_rates else 0.0

    metrics = [
        MetricValue(
            value=round(overall_fill, 4),
            unit="ratio",
            status=evaluate_status("required_property_coverage", overall_fill),
        ),
    ]

    score = _compute_category_score(metrics)

    logger.info(
        "Completeness: overall_fill=%.4f, fill_rates=%d items, score=%.1f",
        overall_fill,
        len(fill_rates),
        score,
    )
    return CategoryResult(name="completeness", score=score, metrics=metrics)


def measure_consistency(session: Any) -> CategoryResult:
    """一貫性指標を計測する。

    型一貫性（Entity.entity_type の許可リスト遵守率）、重複率、
    制約違反数の3指標を返す。

    Parameters
    ----------
    session
        Neo4j セッション。

    Returns
    -------
    CategoryResult
        ``"consistency"`` カテゴリの計測結果。
    """
    # 1. 型一貫性: Entity.entity_type の許可リスト内率
    type_query = """
    MATCH (n:Entity)
    WHERE NOT 'Memory' IN labels(n)
    RETURN n.entity_type AS entity_type, count(n) AS count
    """
    type_result = session.run(type_query)
    type_records = type_result.data()

    total_entities = sum(r["count"] for r in type_records)
    valid_entities = sum(
        r["count"] for r in type_records if r["entity_type"] in ALLOWED_ENTITY_TYPES
    )
    type_consistency = valid_entities / total_entities if total_entities > 0 else 1.0

    # 2. 重複率: Entity.name の重複数
    duplicate_query = """
    MATCH (n:Entity)
    WHERE NOT 'Memory' IN labels(n)
    WITH n.name AS name, count(n) AS cnt
    RETURN sum(CASE WHEN cnt > 1 THEN cnt ELSE 0 END) AS duplicate_count,
           count(name) AS total
    """
    dup_result = session.run(duplicate_query)
    dup_record = dup_result.single()
    dup_count = dup_record["duplicate_count"]
    dup_total = dup_record["total"]
    duplicate_rate = dup_count / dup_total if dup_total > 0 else 0.0
    # 重複率は低いほど良い → 1 - duplicate_rate で一貫性指標に変換
    dedup_score = 1.0 - duplicate_rate

    # 3. 制約違反: entity_id が null の Entity 数
    constraint_query = """
    MATCH (n:Entity)
    WHERE NOT 'Memory' IN labels(n)
    AND n.entity_id IS NULL
    RETURN count(n) AS violation_count
    """
    constraint_result = session.run(constraint_query)
    violation_count: int = constraint_result.single()["violation_count"]

    metrics = [
        MetricValue(
            value=round(type_consistency, 4),
            unit="ratio",
            status=evaluate_status("label_consistency", type_consistency),
        ),
        MetricValue(
            value=round(dedup_score, 4),
            unit="ratio",
            status=evaluate_status("label_consistency", dedup_score),
        ),
        MetricValue(
            value=float(violation_count),
            unit="count",
            status="green" if violation_count == 0 else "red",
        ),
    ]

    score = _compute_category_score(metrics)

    logger.info(
        "Consistency: type_consistency=%.4f, dedup_score=%.4f, "
        "violations=%d, score=%.1f",
        type_consistency,
        dedup_score,
        violation_count,
        score,
    )
    return CategoryResult(name="consistency", score=score, metrics=metrics)


def measure_accuracy(session: Any) -> CategoryResult:
    """正確性指標を計測する（スタブ実装）。

    LLM-as-Judge が未実装のため、全メトリクスを ``stub=True`` で返す。

    Parameters
    ----------
    session
        Neo4j セッション（未使用）。

    Returns
    -------
    CategoryResult
        ``"accuracy"`` カテゴリのスタブ結果。
    """
    _ = session  # 未使用（将来の LLM-as-Judge 実装用）
    metrics = [
        MetricValue(
            value=0.0,
            unit="ratio",
            status="yellow",
            stub=True,
        ),
    ]
    logger.info("Accuracy: stub implementation (LLM-as-Judge not yet implemented)")
    return CategoryResult(name="accuracy", score=0.0, metrics=metrics)


def measure_timeliness(session: Any) -> CategoryResult:
    """適時性指標を計測する。

    鮮度（平均経過日数）、更新頻度（過去30日の Source 数）、
    時間カバレッジ（最古〜最新の期間）の3指標を返す。

    Parameters
    ----------
    session
        Neo4j セッション。

    Returns
    -------
    CategoryResult
        ``"timeliness"`` カテゴリの計測結果。
    """
    # 1. 鮮度: Source.fetched_at からの平均経過日数
    freshness_query = """
    MATCH (s:Source)
    WHERE NOT 'Memory' IN labels(s)
    AND s.fetched_at IS NOT NULL
    RETURN avg(duration.between(s.fetched_at, datetime()).days) AS avg_age_days
    """
    freshness_result = session.run(freshness_query)
    avg_age_days: float = freshness_result.single()["avg_age_days"] or 0.0

    # 2. 更新頻度: 過去30日に追加された Source 数
    frequency_query = """
    MATCH (s:Source)
    WHERE NOT 'Memory' IN labels(s)
    AND s.fetched_at >= datetime() - duration('P30D')
    RETURN count(s) AS recent_count
    """
    frequency_result = session.run(frequency_query)
    recent_count: int = frequency_result.single()["recent_count"]

    # 3. 時間カバレッジ: fetched_at の最古/最新
    coverage_query = """
    MATCH (s:Source)
    WHERE NOT 'Memory' IN labels(s)
    AND s.fetched_at IS NOT NULL
    RETURN min(toString(s.fetched_at)) AS earliest,
           max(toString(s.fetched_at)) AS latest
    """
    coverage_result = session.run(coverage_query)
    coverage_record = coverage_result.single()
    earliest = coverage_record["earliest"] or ""
    latest = coverage_record["latest"] or ""
    # 時間範囲の長さ（日数ベースの概算）
    coverage_span_days = 0.0
    if earliest and latest and len(earliest) >= 10 and len(latest) >= 10:
        try:
            from datetime import datetime as dt

            earliest_dt = dt.fromisoformat(earliest[:19].replace("Z", "+00:00"))
            latest_dt = dt.fromisoformat(latest[:19].replace("Z", "+00:00"))
            coverage_span_days = (latest_dt - earliest_dt).days
        except (ValueError, TypeError):
            coverage_span_days = 0.0

    metrics = [
        MetricValue(
            value=round(float(avg_age_days), 1),
            unit="days",
            status=evaluate_status("source_freshness_days", float(avg_age_days)),
        ),
        MetricValue(
            value=float(recent_count),
            unit="count",
            status="green"
            if recent_count >= 10
            else "yellow"
            if recent_count >= 3
            else "red",
        ),
        MetricValue(
            value=round(coverage_span_days, 0),
            unit="days",
            status="green"
            if coverage_span_days >= 90
            else "yellow"
            if coverage_span_days >= 30
            else "red",
        ),
    ]

    score = _compute_category_score(metrics)

    logger.info(
        "Timeliness: avg_age_days=%.1f, recent_count=%d, "
        "coverage_span_days=%.0f, score=%.1f",
        avg_age_days,
        recent_count,
        coverage_span_days,
        score,
    )
    return CategoryResult(name="timeliness", score=score, metrics=metrics)


def measure_finance_specific(session: Any) -> CategoryResult:
    """金融特化指標を計測する。

    セクターカバレッジ（GICS 11セクター基準）、メトリクス/社
    （Entity(company) あたりの平均 FinancialDataPoint 数）、
    Entity-Entity 関係密度の3指標を返す。

    Parameters
    ----------
    session
        Neo4j セッション。

    Returns
    -------
    CategoryResult
        ``"finance_specific"`` カテゴリの計測結果。
    """
    # 1. セクターカバレッジ: DB にある Sector ノード数 / GICS 11
    sector_query = """
    MATCH (n:Sector)
    WHERE NOT 'Memory' IN labels(n)
    RETURN count(DISTINCT n) AS sector_count
    """
    sector_result = session.run(sector_query)
    sector_count: int = sector_result.single()["sector_count"]
    sector_coverage = sector_count / GICS_SECTOR_COUNT

    # 2. メトリクス/社: company Entity あたりの平均 FinancialDataPoint 数
    metrics_per_query = """
    MATCH (e:Entity)
    WHERE NOT 'Memory' IN labels(e)
    AND e.entity_type = 'company'
    OPTIONAL MATCH (e)<-[:RELATES_TO]-(dp:FinancialDataPoint)
    WHERE NOT 'Memory' IN labels(dp)
    WITH e, count(dp) AS dp_count
    RETURN avg(dp_count) AS avg_metrics
    """
    metrics_per_result = session.run(metrics_per_query)
    avg_metrics: float = metrics_per_result.single()["avg_metrics"] or 0.0

    # 3. Entity-Entity 関係密度
    ee_query = """
    MATCH (e1:Entity)-[r]-(e2:Entity)
    WHERE NOT 'Memory' IN labels(e1)
    AND NOT 'Memory' IN labels(e2)
    AND elementId(e1) < elementId(e2)
    WITH count(r) AS ee_rel_count
    MATCH (e:Entity)
    WHERE NOT 'Memory' IN labels(e)
    RETURN ee_rel_count, count(e) AS entity_count
    """
    ee_result = session.run(ee_query)
    ee_record = ee_result.single()
    ee_rel_count: int = ee_record["ee_rel_count"]
    entity_count: int = ee_record["entity_count"]
    ee_density = ee_rel_count / entity_count if entity_count > 0 else 0.0

    metrics = [
        MetricValue(
            value=round(sector_coverage, 4),
            unit="ratio",
            status=evaluate_status("entity_type_coverage", sector_coverage),
        ),
        MetricValue(
            value=round(avg_metrics, 2),
            unit="count",
            status=evaluate_status("financial_data_completeness", avg_metrics / 10.0),
        ),
        MetricValue(
            value=round(ee_density, 4),
            unit="ratio",
            status=evaluate_status("claim_evidence_ratio", ee_density),
        ),
    ]

    score = _compute_category_score(metrics)

    logger.info(
        "Finance-specific: sector_coverage=%.4f, avg_metrics=%.2f, "
        "ee_density=%.4f, score=%.1f",
        sector_coverage,
        avg_metrics,
        ee_density,
        score,
    )
    return CategoryResult(name="finance_specific", score=score, metrics=metrics)


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
