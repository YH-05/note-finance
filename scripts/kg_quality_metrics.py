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
import json
import math
import os
import random
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime as dt
from datetime import timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from neo4j_utils import create_driver

if TYPE_CHECKING:
    from datetime import datetime

# Cypher 識別子（ラベル名・プロパティ名）のバリデーション用正規表現
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
# 日本語検出用正規表現（CJK 統合漢字・ひらがな・カタカナ・半角カナ）
_JP_PATTERN = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff\uff66-\uff9f]")

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

ALLOWED_RELATIONSHIP_TYPES: frozenset[str] = frozenset(
    {
        "CONTAINS_CHUNK",
        "EXTRACTED_FROM",
        "STATES_FACT",
        "MAKES_CLAIM",
        "SUPPORTED_BY",
        "CONTRADICTS",
        "RELATES_TO",
        "ABOUT",
        "AUTHORED_BY",
        "TAGGED",
        "FOR_PERIOD",
        "HAS_DATAPOINT",
        "DERIVED_FROM",
        "VALIDATES",
        "CHALLENGES",
        "HOLDS_STANCE",
        "ON_ENTITY",
        "BASED_ON",
        "SUPERSEDES",
        "NEXT_PERIOD",
        "TREND",
        "CAUSES",
        "ASKS_ABOUT",
        "MOTIVATED_BY",
        "ANSWERED_BY",
    }
)
"""リレーションタイプの許可リスト。knowledge-graph-schema.yaml v2.3 準拠。"""

# 代名詞パターン（英語・日本語）
_ENGLISH_PRONOUNS: frozenset[str] = frozenset(
    {
        "it",
        "its",
        "they",
        "them",
        "their",
        "theirs",
        "he",
        "him",
        "his",
        "she",
        "her",
        "hers",
        "this",
        "that",
        "these",
        "those",
    }
)
"""検出対象の英語代名詞（文頭での使用を検出）。"""

_JAPANESE_PRONOUNS: tuple[str, ...] = (
    "それ",
    "これ",
    "あれ",
    "その",
    "この",
    "あの",
    "彼",
    "彼女",
    "彼ら",
)
"""検出対象の日本語代名詞（文頭での使用を検出）。"""


# ---------------------------------------------------------------------------
# インフラ関数
# ---------------------------------------------------------------------------


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
    # セキュリティ強化: 識別子バリデーションで Cypher インジェクションを防止
    # HIGH-001: 同一ラベルの複数プロパティを1クエリで取得（N x M -> N に削減）
    nodes_def = schema.get("nodes", {})
    for label, node_def in nodes_def.items():
        if not _SAFE_IDENTIFIER.match(label):
            logger.warning("Invalid label in schema, skipping: %r", label)
            continue
        props = node_def.get("properties", {})
        required_props = [
            prop_name
            for prop_name, prop_def in props.items()
            if prop_def.get("required", False) and _SAFE_IDENTIFIER.match(prop_name)
        ]
        # 無効な識別子をスキップ（ログ出力）
        for prop_name, prop_def in props.items():
            if prop_def.get("required", False) and not _SAFE_IDENTIFIER.match(
                prop_name
            ):
                logger.warning("Invalid property in schema, skipping: %r", prop_name)

        if not required_props:
            continue

        # 同一ラベルの全 required props を1クエリで取得
        prop_exprs = ", ".join(
            f"count(n.{p}) AS filled_{i}" for i, p in enumerate(required_props)
        )
        query = f"""
        MATCH (n:{label})
        WHERE NOT 'Memory' IN labels(n)
        RETURN count(n) AS total, {prop_exprs}
        """
        result = session.run(query)
        record = result.single()
        total = record["total"]
        for i in range(len(required_props)):
            filled = record[f"filled_{i}"]
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
# measure_discoverability
# ---------------------------------------------------------------------------

_DISCOVERABILITY_BATCH_SIZE = 30
"""UNWIND バッチサイズ（ペア数/バッチ）。"""


def _sample_node_pairs(session: Any, sample_size: int) -> list[tuple[str, str]]:
    """ノードIDを取得しランダムペアをサンプリングする。

    Parameters
    ----------
    session
        Neo4j セッション。
    sample_size : int
        サンプリングするペア数。

    Returns
    -------
    list[tuple[str, str]]
        サンプリングされたノードペアのリスト。ノード数が2未満の場合は空リスト。
    """
    node_id_query = """
    MATCH (n)
    WHERE NOT 'Memory' IN labels(n)
    RETURN elementId(n) AS nid
    """
    node_id_result = session.run(node_id_query)
    node_ids: list[str] = [r["nid"] for r in node_id_result.data()]

    if len(node_ids) < 2:
        logger.warning(
            "Not enough nodes for discoverability sampling: %d", len(node_ids)
        )
        return []

    actual_sample = min(sample_size, len(node_ids) * (len(node_ids) - 1) // 2)
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    attempts = 0
    max_attempts = actual_sample * 10

    while len(pairs) < actual_sample and attempts < max_attempts:
        a, b = random.sample(node_ids, 2)
        pair_key = (min(a, b), max(a, b))
        if pair_key not in seen:
            seen.add(pair_key)
            pairs.append((a, b))
        attempts += 1

    return pairs


def _measure_path_lengths(
    session: Any,
    pairs: list[tuple[str, str]],
    timeout_sec: int,
) -> tuple[list[int], int, int]:
    """UNWIND バッチで最短パス長を計測する。

    Parameters
    ----------
    session
        Neo4j セッション。
    pairs : list[tuple[str, str]]
        ノードペアのリスト。
    timeout_sec : int
        タイムアウト（秒）。未使用だが互換性のため保持。

    Returns
    -------
    tuple[list[int], int, int]
        (パス長リスト, パスなし数, タイムアウト数)。
    """
    _ = timeout_sec  # UNWIND バッチではペア単位タイムアウト不要
    path_lengths: list[int] = []
    no_path_count = 0
    timeout_count = 0

    batch_query = """
    UNWIND $pairs AS pair
    MATCH (a), (b)
    WHERE elementId(a) = pair[0] AND elementId(b) = pair[1]
    AND NOT 'Memory' IN labels(a) AND NOT 'Memory' IN labels(b)
    OPTIONAL MATCH p = shortestPath((a)-[*..15]-(b))
    RETURN pair[0] AS src, pair[1] AS dst,
           CASE WHEN p IS NULL THEN null ELSE length(p) END AS path_length
    """

    for i in range(0, len(pairs), _DISCOVERABILITY_BATCH_SIZE):
        batch = [[a, b] for a, b in pairs[i : i + _DISCOVERABILITY_BATCH_SIZE]]
        try:
            result = session.run(batch_query, pairs=batch)
            for record in result:
                pl = record["path_length"]
                if pl is not None:
                    path_lengths.append(pl)
                else:
                    no_path_count += 1
        except Exception:
            timeout_count += len(batch)
            logger.debug(
                "Discoverability: timeout/error for batch starting at index %d",
                i,
            )

    return path_lengths, no_path_count, timeout_count


def _compute_discoverability_metrics(
    path_lengths: list[int],
    no_path_count: int,
    pairs_count: int,
) -> tuple[float, float, float]:
    """パス長データから discoverability メトリクスを算出する。

    Parameters
    ----------
    path_lengths : list[int]
        計測されたパス長のリスト。
    no_path_count : int
        パスが見つからなかったペア数。
    pairs_count : int
        試行したペア総数。

    Returns
    -------
    tuple[float, float, float]
        (平均パス長, パス多様性, ブリッジ率)。
    """
    if path_lengths:
        avg_path_length = sum(path_lengths) / len(path_lengths)
        unique_lengths = len(set(path_lengths))
        path_diversity = unique_lengths / len(path_lengths) if path_lengths else 0.0
        reachable_pairs = len(path_lengths)
        bridge_rate = reachable_pairs / pairs_count if pairs_count > 0 else 0.0
    else:
        avg_path_length = 0.0
        path_diversity = 0.0
        bridge_rate = 0.0

    return avg_path_length, path_diversity, bridge_rate


def measure_discoverability(
    session: Any,
    *,
    sample_size: int = 200,
    timeout_sec: int = 5,
) -> CategoryResult:
    """発見可能性指標を計測する。

    ランダムにサンプリングしたノードペア間の最短パスを計測し、
    パス多様性スコア・ブリッジ率・平均パス長を返す。

    Parameters
    ----------
    session
        Neo4j セッション。
    sample_size : int
        サンプリングするペア数。デフォルトは200。
    timeout_sec : int
        shortestPath タイムアウト（秒）。デフォルトは5。

    Returns
    -------
    CategoryResult
        ``"discoverability"`` カテゴリの計測結果。
    """
    pairs = _sample_node_pairs(session, sample_size)

    if not pairs:
        metrics = [
            MetricValue(value=0.0, unit="hops", status="red"),
            MetricValue(value=0.0, unit="ratio", status="red"),
            MetricValue(value=0.0, unit="ratio", status="red"),
        ]
        return CategoryResult(name="discoverability", score=0.0, metrics=metrics)

    path_lengths, no_path_count, timeout_count = _measure_path_lengths(
        session, pairs, timeout_sec
    )
    avg_path_length, path_diversity, bridge_rate = _compute_discoverability_metrics(
        path_lengths, no_path_count, len(pairs)
    )

    metrics = [
        MetricValue(
            value=round(avg_path_length, 2),
            unit="hops",
            status=evaluate_status("path_reachability", bridge_rate),
        ),
        MetricValue(
            value=round(path_diversity, 4),
            unit="ratio",
            status="green"
            if path_diversity >= 0.3
            else "yellow"
            if path_diversity >= 0.1
            else "red",
        ),
        MetricValue(
            value=round(bridge_rate, 4),
            unit="ratio",
            status=evaluate_status("path_reachability", bridge_rate),
        ),
    ]

    score = _compute_category_score(metrics)

    logger.info(
        "Discoverability: avg_path=%.2f, diversity=%.4f, bridge_rate=%.4f, "
        "timeouts=%d, no_path=%d, score=%.1f",
        avg_path_length,
        path_diversity,
        bridge_rate,
        timeout_count,
        no_path_count,
        score,
    )
    return CategoryResult(name="discoverability", score=score, metrics=metrics)


# ---------------------------------------------------------------------------
# CheckRules（4純粋関数）
# ---------------------------------------------------------------------------


def _compute_check_result(
    rule_name: str, total: int, violations: list[str]
) -> CheckRuleResult:
    """チェックルール結果の共通集計を行う。

    Parameters
    ----------
    rule_name : str
        ルール名。
    total : int
        検査対象の総数。
    violations : list[str]
        違反リスト。

    Returns
    -------
    CheckRuleResult
        集計済みのチェックルール結果。
    """
    pass_count = total - len(violations)
    pass_rate = pass_count / total if total > 0 else 1.0
    return CheckRuleResult(
        rule_name=rule_name,
        pass_rate=round(pass_rate, 4),
        violations=violations,
    )


def _is_japanese(text: str) -> bool:
    """テキストが日本語を含むかを判定する。

    正規表現で CJK 統合漢字・ひらがな・カタカナ・半角カナを検出する。

    Parameters
    ----------
    text : str
        判定対象のテキスト。

    Returns
    -------
    bool
        日本語文字を含む場合は True。
    """
    return bool(_JP_PATTERN.search(text))


def check_subject_reference(texts: list[str]) -> CheckRuleResult:
    """代名詞による主語参照を検出する。

    Fact/Claim の content テキストが代名詞で始まっている場合を違反とする。
    英語・日本語の代名詞に対応。

    Parameters
    ----------
    texts : list[str]
        検証対象のテキストリスト。

    Returns
    -------
    CheckRuleResult
        ``"subject_reference"`` ルールの検証結果。
    """
    if not texts:
        return CheckRuleResult(
            rule_name="subject_reference", pass_rate=1.0, violations=[]
        )

    violations: list[str] = []
    for text in texts:
        stripped = text.strip()
        if not stripped:
            continue

        # 英語: 最初の単語が代名詞か
        first_word = stripped.split()[0].lower().rstrip(",.;:")
        if first_word in _ENGLISH_PRONOUNS:
            violations.append(stripped[:80])
            continue

        # 日本語: 先頭が代名詞で始まるか
        for pronoun in _JAPANESE_PRONOUNS:
            if stripped.startswith(pronoun):
                violations.append(stripped[:80])
                break

    return _compute_check_result("subject_reference", len(texts), violations)


def check_entity_length(entities: list[str]) -> CheckRuleResult:
    """エンティティ名の長さを検証する。

    英語は5語以下、日本語は10文字以下を基準とする。
    言語判定は文字種（CJK/ひらがな/カタカナ）の有無で自動判定。

    Parameters
    ----------
    entities : list[str]
        検証対象のエンティティ名リスト。

    Returns
    -------
    CheckRuleResult
        ``"entity_length"`` ルールの検証結果。
    """
    if not entities:
        return CheckRuleResult(rule_name="entity_length", pass_rate=1.0, violations=[])

    violations: list[str] = []
    for entity in entities:
        if _is_japanese(entity):
            # 日本語: 10文字以下
            if len(entity) > 10:
                violations.append(entity)
        else:
            # 英語: 5語以下
            word_count = len(entity.split())
            if word_count > 5:
                violations.append(entity)

    return _compute_check_result("entity_length", len(entities), violations)


def check_schema_compliance(entity_types: list[str]) -> CheckRuleResult:
    """entity_type の許可リスト遵守を検証する。

    Parameters
    ----------
    entity_types : list[str]
        検証対象の entity_type リスト。

    Returns
    -------
    CheckRuleResult
        ``"schema_compliance"`` ルールの検証結果。
    """
    if not entity_types:
        return CheckRuleResult(
            rule_name="schema_compliance", pass_rate=1.0, violations=[]
        )

    violations: list[str] = [
        et for et in entity_types if et not in ALLOWED_ENTITY_TYPES
    ]
    return _compute_check_result("schema_compliance", len(entity_types), violations)


def check_relationship_compliance(rel_types: list[str]) -> CheckRuleResult:
    """リレーションタイプのスキーマ遵守を検証する。

    Parameters
    ----------
    rel_types : list[str]
        検証対象のリレーションタイプリスト。

    Returns
    -------
    CheckRuleResult
        ``"relationship_compliance"`` ルールの検証結果。
    """
    if not rel_types:
        return CheckRuleResult(
            rule_name="relationship_compliance", pass_rate=1.0, violations=[]
        )

    violations: list[str] = [
        rt for rt in rel_types if rt not in ALLOWED_RELATIONSHIP_TYPES
    ]
    return _compute_check_result("relationship_compliance", len(rel_types), violations)


# ---------------------------------------------------------------------------
# EntropyAnalysis
# ---------------------------------------------------------------------------


def compute_shannon_entropy(counts: dict[str, int]) -> float:
    """正規化シャノンエントロピーを計算する。

    均一分布で最大値 1.0、単一値で 0.0 を返す。

    Parameters
    ----------
    counts : dict[str, int]
        カテゴリ名をキー、出現回数を値とする辞書。

    Returns
    -------
    float
        正規化エントロピー（0.0 - 1.0）。
    """
    # 0以下のカウントを除外
    positive_counts = {k: v for k, v in counts.items() if v > 0}
    n_categories = len(positive_counts)

    if n_categories <= 1:
        return 0.0

    total = sum(positive_counts.values())
    if total == 0:
        return 0.0

    # シャノンエントロピー H = -Σ p_i * log2(p_i)
    entropy = 0.0
    for count in positive_counts.values():
        p = count / total
        if p > 0:
            entropy -= p * math.log2(p)

    # 正規化: H / log2(n) で 0-1 にスケーリング
    max_entropy = math.log2(n_categories)
    normalized = entropy / max_entropy if max_entropy > 0 else 0.0

    return round(normalized, 4)


def compute_semantic_diversity(
    *,
    entity_type_counts: dict[str, int],
    topic_category_counts: dict[str, int],
    relationship_type_counts: dict[str, int],
) -> float:
    """3軸統合セマンティック多様性スコアを計算する。

    Entity.entity_type、Topic.category、リレーションタイプの
    3軸の正規化シャノンエントロピーの平均値を返す。

    Parameters
    ----------
    entity_type_counts : dict[str, int]
        Entity.entity_type の分布。
    topic_category_counts : dict[str, int]
        Topic.category の分布。
    relationship_type_counts : dict[str, int]
        リレーションタイプの分布。

    Returns
    -------
    float
        3軸統合多様性スコア（0.0 - 1.0）。
    """
    entity_entropy = compute_shannon_entropy(entity_type_counts)
    topic_entropy = compute_shannon_entropy(topic_category_counts)
    rel_entropy = compute_shannon_entropy(relationship_type_counts)

    # 3軸の単純平均
    diversity = (entity_entropy + topic_entropy + rel_entropy) / 3.0

    logger.info(
        "Semantic diversity: entity=%.4f, topic=%.4f, rel=%.4f, combined=%.4f",
        entity_entropy,
        topic_entropy,
        rel_entropy,
        diversity,
    )
    return round(diversity, 4)


# ---------------------------------------------------------------------------
# Output: Rating Helper
# ---------------------------------------------------------------------------


def _compute_rating(score: float) -> str:
    """総合スコアからレーティング（A-D）を算出する。

    Parameters
    ----------
    score : float
        総合スコア（0.0 - 100.0）。

    Returns
    -------
    str
        ``"A"`` / ``"B"`` / ``"C"`` / ``"D"`` のいずれか。
    """
    if score >= 80.0:
        return "A"
    if score >= 60.0:
        return "B"
    if score >= 40.0:
        return "C"
    return "D"


_METRIC_LABELS: dict[str, list[str]] = {
    "structural": ["Edge Density", "Avg Degree", "Connected Ratio", "Orphan Ratio"],
    "completeness": ["Required Property Coverage"],
    "consistency": ["Type Consistency", "Dedup Score", "Constraint Violations"],
    "accuracy": ["LLM-as-Judge (stub)"],
    "timeliness": [
        "Avg Freshness (days)",
        "Recent Sources (30d)",
        "Coverage Span (days)",
    ],
    "finance_specific": ["Sector Coverage", "Metrics/Company", "Entity-Entity Density"],
    "discoverability": ["Avg Path Length", "Path Diversity", "Bridge Rate"],
}
"""カテゴリごとのメトリクスラベル。render_console / generate_markdown で使用。"""


# ---------------------------------------------------------------------------
# Output: render_console (Rich Console)
# ---------------------------------------------------------------------------


def _get_threshold_str(label: str) -> str:
    """メトリクスラベルに対応する閾値文字列を取得する。"""
    threshold_info = THRESHOLDS.get(label, {})
    if threshold_info:
        return f"G≥{threshold_info.get('green', '-')}"
    for key, th in THRESHOLDS.items():
        if key in label.lower().replace(" ", "_"):
            return f"G≥{th['green']}"
    return ""


def _pass_rate_style(pass_rate: float) -> str:
    """CheckRule 通過率に対応する Rich スタイルを返す。"""
    if pass_rate >= 0.95:
        return "green"
    return "yellow" if pass_rate >= 0.8 else "red"


def _render_category_tables(console: Any, snapshot: QualitySnapshot) -> None:
    """カテゴリ別テーブルを Rich Console に出力する。"""
    from rich.table import Table

    for cat in snapshot.categories:
        table = Table(title=f"[bold]{cat.name}[/bold] (Score: {cat.score:.1f})")
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Value", justify="right")
        table.add_column("Status", justify="center")
        table.add_column("Threshold", justify="right")

        labels = _METRIC_LABELS.get(cat.name, [])
        for i, metric in enumerate(cat.metrics):
            label = labels[i] if i < len(labels) else f"Metric {i + 1}"
            status_style = (
                metric.status
                if metric.status in ("green", "yellow", "red")
                else "white"
            )
            stub_marker = " (stub)" if metric.stub else ""
            table.add_row(
                label,
                f"{metric.value}{stub_marker}",
                f"[{status_style}]{metric.status}[/{status_style}]",
                _get_threshold_str(label),
            )
        console.print(table)
        console.print()


def render_console(
    snapshot: QualitySnapshot,
    check_rules: list[CheckRuleResult],
    entropy: dict[str, float],
) -> None:
    """Rich Console に品質ダッシュボードを出力する。

    カテゴリごとに Table（Metric/Value/Status/Threshold）を表示し、
    全体サマリーを Panel で囲む。

    Parameters
    ----------
    snapshot : QualitySnapshot
        品質スナップショット。
    check_rules : list[CheckRuleResult]
        チェックルール結果リスト。
    entropy : dict[str, float]
        エントロピーデータ。
    """
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
    except ImportError:
        logger.error("Rich is not installed. Run: uv add rich")
        return

    console = Console()
    rating = _compute_rating(snapshot.overall_score)
    console.print()
    console.print(
        Panel(
            f"[bold]KG Quality Dashboard[/bold]\n"
            f"Timestamp: {snapshot.timestamp.isoformat()}\n"
            f"Overall Score: [bold]{snapshot.overall_score:.1f}[/bold] / 100.0\n"
            f"Rating: [bold]{rating}[/bold]",
            title="Summary",
            border_style="blue",
        )
    )

    _render_category_tables(console, snapshot)

    if check_rules:
        cr_table = Table(title="[bold]CheckRules[/bold]")
        cr_table.add_column("Rule", style="cyan")
        cr_table.add_column("Pass Rate", justify="right")
        cr_table.add_column("Violations", justify="right")
        for rule in check_rules:
            style = _pass_rate_style(rule.pass_rate)
            cr_table.add_row(
                rule.rule_name,
                f"[{style}]{rule.pass_rate:.2%}[/{style}]",
                str(len(rule.violations)),
            )
        console.print(cr_table)
        console.print()

    if entropy:
        ent_table = Table(title="[bold]Entropy / Diversity[/bold]")
        ent_table.add_column("Axis", style="cyan")
        ent_table.add_column("Value", justify="right")
        for key, val in entropy.items():
            ent_table.add_row(key, f"{val:.4f}")
        console.print(ent_table)
        console.print()

    logger.info("Console rendering completed")


# ---------------------------------------------------------------------------
# Output: save_json
# ---------------------------------------------------------------------------


def _snapshot_to_dict(
    snapshot: QualitySnapshot,
    check_rules: list[CheckRuleResult],
    entropy: dict[str, float],
) -> dict[str, Any]:
    """QualitySnapshot + CheckRules + Entropy を JSON 出力用辞書に変換する。

    Parameters
    ----------
    snapshot : QualitySnapshot
        品質スナップショット。
    check_rules : list[CheckRuleResult]
        チェックルール結果リスト。
    entropy : dict[str, float]
        エントロピーデータ。

    Returns
    -------
    dict[str, Any]
        JSON シリアライズ可能な辞書。
    """
    categories_data = []
    for cat in snapshot.categories:
        metrics_data = [asdict(m) for m in cat.metrics]
        categories_data.append(
            {
                "name": cat.name,
                "score": cat.score,
                "metrics": metrics_data,
            }
        )

    check_rules_data = [asdict(cr) for cr in check_rules]

    return {
        "timestamp": snapshot.timestamp.isoformat(),
        "overall_score": snapshot.overall_score,
        "rating": _compute_rating(snapshot.overall_score),
        "categories": categories_data,
        "check_rules": check_rules_data,
        "entropy": entropy,
    }


def save_json(
    snapshot: QualitySnapshot,
    check_rules: list[CheckRuleResult],
    entropy: dict[str, float],
    *,
    output_dir: Path | None = None,
) -> Path:
    """計測結果を JSON ファイルとして保存する。

    出力先: ``{output_dir}/snapshot_{date}.json``

    Parameters
    ----------
    snapshot : QualitySnapshot
        品質スナップショット。
    check_rules : list[CheckRuleResult]
        チェックルール結果リスト。
    entropy : dict[str, float]
        エントロピーデータ。
    output_dir : Path | None
        出力先ディレクトリ。``None`` の場合は
        ``data/processed/kg_quality/`` を使用する。

    Returns
    -------
    Path
        保存された JSON ファイルのパス。
    """
    if output_dir is None:
        output_dir = Path("data/processed/kg_quality")

    output_dir.mkdir(parents=True, exist_ok=True)

    date_str = snapshot.timestamp.strftime("%Y%m%d")
    output_path = output_dir / f"snapshot_{date_str}.json"

    data = _snapshot_to_dict(snapshot, check_rules, entropy)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info("JSON snapshot saved: %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# Output: save_neo4j
# ---------------------------------------------------------------------------


def save_neo4j(
    session: Any,
    snapshot: QualitySnapshot,
    *,
    dry_run: bool = False,
) -> None:
    """品質スナップショットを Neo4j に保存する。

    ``MERGE (qs:QualitySnapshot {snapshot_id: $snapshot_id})`` パターンで
    冪等に保存する。``--dry-run`` 時はスキップ。

    Parameters
    ----------
    session
        Neo4j セッション。
    snapshot : QualitySnapshot
        品質スナップショット。
    dry_run : bool
        ``True`` の場合はスキップ。
    """
    if dry_run:
        logger.info("save_neo4j: skipped (dry-run mode)")
        return

    date_str = snapshot.timestamp.strftime("%Y%m%d")
    snapshot_id = f"qs_{date_str}"

    # カテゴリスコアを辞書化
    category_scores = {cat.name: cat.score for cat in snapshot.categories}

    merge_query = """
    MERGE (qs:QualitySnapshot {snapshot_id: $snapshot_id})
    SET qs.timestamp = datetime($timestamp),
        qs.overall_score = $overall_score,
        qs.rating = $rating,
        qs.structural_score = $structural_score,
        qs.completeness_score = $completeness_score,
        qs.consistency_score = $consistency_score,
        qs.accuracy_score = $accuracy_score,
        qs.timeliness_score = $timeliness_score,
        qs.finance_specific_score = $finance_specific_score,
        qs.discoverability_score = $discoverability_score,
        qs.updated_at = datetime()
    """

    params = {
        "snapshot_id": snapshot_id,
        "timestamp": snapshot.timestamp.isoformat(),
        "overall_score": snapshot.overall_score,
        "rating": _compute_rating(snapshot.overall_score),
        "structural_score": category_scores.get("structural", 0.0),
        "completeness_score": category_scores.get("completeness", 0.0),
        "consistency_score": category_scores.get("consistency", 0.0),
        "accuracy_score": category_scores.get("accuracy", 0.0),
        "timeliness_score": category_scores.get("timeliness", 0.0),
        "finance_specific_score": category_scores.get("finance_specific", 0.0),
        "discoverability_score": category_scores.get("discoverability", 0.0),
    }

    session.run(merge_query, params)
    logger.info("QualitySnapshot saved to Neo4j: %s", snapshot_id)


# ---------------------------------------------------------------------------
# Output: generate_markdown
# ---------------------------------------------------------------------------


_RATING_DESCRIPTIONS: dict[str, str] = {
    "A": "> 優秀: KG品質は高水準です。",
    "B": "> 良好: 改善の余地はありますが、実用レベルです。",
    "C": "> 要改善: いくつかのカテゴリで改善が必要です。",
    "D": "> 要対応: 複数のカテゴリで重大な問題があります。",
}
"""レーティング別の評価コメント。"""


def _md_category_details(snapshot: QualitySnapshot) -> list[str]:
    """カテゴリ詳細の Markdown 行を生成する。"""
    lines: list[str] = []
    for cat in snapshot.categories:
        lines.append(f"### {cat.name}")
        lines.append("")
        lines.append("| Metric | Value | Unit | Status |")
        lines.append("|--------|------:|------|--------|")
        labels = _METRIC_LABELS.get(cat.name, [])
        for i, metric in enumerate(cat.metrics):
            label = labels[i] if i < len(labels) else f"Metric {i + 1}"
            stub_marker = " (stub)" if metric.stub else ""
            lines.append(
                f"| {label} | {metric.value}{stub_marker} | {metric.unit} | {metric.status} |"
            )
        lines.append("")
    return lines


def _md_check_rules_section(check_rules: list[CheckRuleResult]) -> list[str]:
    """CheckRules セクションの Markdown 行を生成する。"""
    lines: list[str] = ["## CheckRules", ""]
    if not check_rules:
        lines.append("No check rules executed.")
        return lines

    lines.append("| Rule | Pass Rate | Violations |")
    lines.append("|------|----------:|-----------:|")
    for rule in check_rules:
        lines.append(
            f"| {rule.rule_name} | {rule.pass_rate:.2%} | {len(rule.violations)} |"
        )
    for rule in check_rules:
        if rule.violations:
            lines.append("")
            lines.append(f"**{rule.rule_name} violations** (sample):")
            for v in rule.violations[:5]:
                lines.append(f"- `{v}`")
    return lines


def generate_markdown(
    snapshot: QualitySnapshot,
    check_rules: list[CheckRuleResult],
    entropy: dict[str, float],
) -> str:
    """品質レポートを Markdown 形式で生成する。

    カテゴリ別表・CheckRules・Entropy・総合評価を含む。

    Parameters
    ----------
    snapshot : QualitySnapshot
        品質スナップショット。
    check_rules : list[CheckRuleResult]
        チェックルール結果リスト。
    entropy : dict[str, float]
        エントロピーデータ。

    Returns
    -------
    str
        Markdown 形式のレポート文字列。
    """
    rating = _compute_rating(snapshot.overall_score)
    lines: list[str] = [
        "# KG Quality Report",
        "",
        f"**Timestamp**: {snapshot.timestamp.isoformat()}",
        f"**Overall Score**: {snapshot.overall_score:.1f} / 100.0",
        f"**Rating**: {rating}",
        "",
        "## Categories",
        "",
        "| Category | Score | Rating |",
        "|----------|------:|--------|",
    ]

    for cat in snapshot.categories:
        lines.append(f"| {cat.name} | {cat.score:.1f} | {_compute_rating(cat.score)} |")
    lines.append("")

    lines.extend(_md_category_details(snapshot))
    lines.extend(_md_check_rules_section(check_rules))
    lines.append("")

    # Entropy
    lines.append("## Entropy / Semantic Diversity")
    lines.append("")
    if entropy:
        lines.extend(["| Axis | Value |", "|------|------:|"])
        for key, val in entropy.items():
            lines.append(f"| {key} | {val:.4f} |")
    else:
        lines.append("No entropy data available.")
    lines.append("")

    # 総合評価
    lines.extend(
        [
            "## 総合評価",
            "",
            f"総合スコア **{snapshot.overall_score:.1f}** / 100.0 — レーティング **{rating}**",
            "",
            _RATING_DESCRIPTIONS.get(rating, ""),
            "",
        ]
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Output: compare_snapshots
# ---------------------------------------------------------------------------


def _load_snapshot_from_json(json_path: Path) -> QualitySnapshot:
    """JSON ファイルから QualitySnapshot を読み込む。

    Parameters
    ----------
    json_path : Path
        スナップショット JSON ファイルのパス。

    Returns
    -------
    QualitySnapshot
        読み込んだスナップショット。

    Raises
    ------
    FileNotFoundError
        JSON ファイルが存在しない場合。
    """
    if not json_path.exists():
        msg = f"Snapshot file not found: {json_path}"
        raise FileNotFoundError(msg)

    with json_path.open(encoding="utf-8") as f:
        data = json.load(f)

    categories = []
    for cat_data in data.get("categories", []):
        metrics = [
            MetricValue(
                value=m["value"],
                unit=m["unit"],
                status=m["status"],
                stub=m.get("stub", False),
            )
            for m in cat_data.get("metrics", [])
        ]
        categories.append(
            CategoryResult(
                name=cat_data["name"],
                score=cat_data["score"],
                metrics=metrics,
            )
        )

    timestamp = dt.fromisoformat(data["timestamp"])

    return QualitySnapshot(
        categories=categories,
        overall_score=data["overall_score"],
        timestamp=timestamp,
    )


def _find_latest_snapshot(output_dir: Path | None = None) -> Path | None:
    """最新のスナップショット JSON ファイルを検索する。

    Parameters
    ----------
    output_dir : Path | None
        検索ディレクトリ。``None`` の場合は
        ``data/processed/kg_quality/`` を使用。

    Returns
    -------
    Path | None
        最新のスナップショットファイルのパス。見つからない場合は ``None``。
    """
    if output_dir is None:
        output_dir = Path("data/processed/kg_quality")

    if not output_dir.exists():
        return None

    snapshots = sorted(output_dir.glob("snapshot_*.json"), reverse=True)
    return snapshots[0] if snapshots else None


def compare_snapshots(
    prev: QualitySnapshot,
    current: QualitySnapshot,
) -> str:
    """2つのスナップショットの差分を比較する。

    Parameters
    ----------
    prev : QualitySnapshot
        比較元（前回）のスナップショット。
    current : QualitySnapshot
        比較先（今回）のスナップショット。

    Returns
    -------
    str
        差分比較結果の文字列。
    """
    lines: list[str] = []

    lines.append("# KG Quality Comparison")
    lines.append("")
    lines.append(f"Previous: {prev.timestamp.isoformat()}")
    lines.append(f"Current:  {current.timestamp.isoformat()}")
    lines.append("")

    # Overall score diff
    overall_diff = current.overall_score - prev.overall_score
    sign = "+" if overall_diff >= 0 else ""
    lines.append(
        f"**Overall Score**: {prev.overall_score:.1f} → {current.overall_score:.1f} "
        f"({sign}{overall_diff:.1f})"
    )
    lines.append("")

    # カテゴリ別比較
    lines.append("| Category | Previous | Current | Change |")
    lines.append("|----------|--------:|--------:|-------:|")

    prev_scores = {cat.name: cat.score for cat in prev.categories}
    curr_scores = {cat.name: cat.score for cat in current.categories}

    all_categories = list(
        dict.fromkeys(
            [cat.name for cat in prev.categories]
            + [cat.name for cat in current.categories]
        )
    )

    for cat_name in all_categories:
        p_score = prev_scores.get(cat_name, 0.0)
        c_score = curr_scores.get(cat_name, 0.0)
        diff = c_score - p_score
        sign = "+" if diff >= 0 else ""
        lines.append(
            f"| {cat_name} | {p_score:.1f} | {c_score:.1f} | {sign}{diff:.1f} |"
        )

    lines.append("")

    # 改善/悪化のサマリー
    improved = [
        cat_name
        for cat_name in all_categories
        if curr_scores.get(cat_name, 0.0) > prev_scores.get(cat_name, 0.0)
    ]
    degraded = [
        cat_name
        for cat_name in all_categories
        if curr_scores.get(cat_name, 0.0) < prev_scores.get(cat_name, 0.0)
    ]

    if improved:
        lines.append(f"**改善**: {', '.join(improved)}")
    if degraded:
        lines.append(f"**悪化**: {', '.join(degraded)}")
    if not improved and not degraded:
        lines.append("**変化なし**")
    lines.append("")

    return "\n".join(lines)


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
        default=None,
        help="Neo4j パスワード（環境変数 NEO4J_PASSWORD から取得）",
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


def _collect_check_rules(session: Any) -> list[CheckRuleResult]:
    """CheckRules 用データを Neo4j から取得し、4ルールを検証する。"""
    text_query = """
    MATCH (n) WHERE NOT 'Memory' IN labels(n)
    AND (n:Fact OR n:Claim) AND n.content IS NOT NULL
    RETURN n.content AS text LIMIT 500
    """
    texts = [r["text"] for r in session.run(text_query).data()]

    entity_query = """
    MATCH (n:Entity) WHERE NOT 'Memory' IN labels(n)
    AND n.name IS NOT NULL RETURN n.name AS name
    """
    entity_names = [r["name"] for r in session.run(entity_query).data()]

    et_query = """
    MATCH (n:Entity) WHERE NOT 'Memory' IN labels(n)
    AND n.entity_type IS NOT NULL RETURN n.entity_type AS et
    """
    entity_types = [r["et"] for r in session.run(et_query).data()]

    rt_query = """
    MATCH (a)-[r]->(b) WHERE NOT 'Memory' IN labels(a)
    AND NOT 'Memory' IN labels(b) RETURN DISTINCT type(r) AS rt
    """
    rel_types = [r["rt"] for r in session.run(rt_query).data()]

    return [
        check_subject_reference(texts),
        check_entity_length(entity_names),
        check_schema_compliance(entity_types),
        check_relationship_compliance(rel_types),
    ]


def _collect_entropy(session: Any) -> dict[str, float]:
    """Entropy / Semantic Diversity 用データを Neo4j から取得する。"""
    et_dist_query = """
    MATCH (n:Entity) WHERE NOT 'Memory' IN labels(n)
    AND n.entity_type IS NOT NULL
    RETURN n.entity_type AS et, count(n) AS cnt
    """
    entity_type_counts = {r["et"]: r["cnt"] for r in session.run(et_dist_query).data()}

    tc_dist_query = """
    MATCH (n:Topic) WHERE NOT 'Memory' IN labels(n)
    AND n.category IS NOT NULL
    RETURN n.category AS cat, count(n) AS cnt
    """
    topic_category_counts = {
        r["cat"]: r["cnt"] for r in session.run(tc_dist_query).data()
    }

    rt_dist_query = """
    MATCH (a)-[r]->(b) WHERE NOT 'Memory' IN labels(a)
    AND NOT 'Memory' IN labels(b)
    RETURN type(r) AS rt, count(r) AS cnt
    """
    rel_type_counts = {r["rt"]: r["cnt"] for r in session.run(rt_dist_query).data()}

    return {
        "entity_type_entropy": compute_shannon_entropy(entity_type_counts),
        "topic_category_entropy": compute_shannon_entropy(topic_category_counts),
        "relationship_type_entropy": compute_shannon_entropy(rel_type_counts),
        "semantic_diversity": compute_semantic_diversity(
            entity_type_counts=entity_type_counts,
            topic_category_counts=topic_category_counts,
            relationship_type_counts=rel_type_counts,
        ),
    }


def _run_measurements(
    session: Any,
    schema: dict[str, Any],
    category: str,
) -> tuple[QualitySnapshot, list[CheckRuleResult], dict[str, float]]:
    """指定カテゴリの計測を実行し、QualitySnapshot を構築する。

    Parameters
    ----------
    session
        Neo4j セッション。
    schema : dict[str, Any]
        スキーマ定義。
    category : str
        計測カテゴリ（``"all"`` で全カテゴリ）。

    Returns
    -------
    tuple[QualitySnapshot, list[CheckRuleResult], dict[str, float]]
        スナップショット、チェックルール結果、エントロピーデータ。
    """
    # カテゴリ別計測（ディスパッチテーブル）
    measure_funcs: dict[str, Any] = {
        "structural": lambda: measure_structural(session),
        "completeness": lambda: measure_completeness(session, schema),
        "consistency": lambda: measure_consistency(session),
        "accuracy": lambda: measure_accuracy(session),
        "timeliness": lambda: measure_timeliness(session),
        "finance_specific": lambda: measure_finance_specific(session),
        "discoverability": lambda: measure_discoverability(session),
    }

    categories: list[CategoryResult] = []
    for cat_name, func in measure_funcs.items():
        if category in ("all", cat_name):
            categories.append(func())

    overall_score = (
        round(sum(c.score for c in categories) / len(categories), 1)
        if categories
        else 0.0
    )

    snapshot = QualitySnapshot(
        categories=categories,
        overall_score=overall_score,
        timestamp=dt.now(tz=timezone.utc),
    )

    check_rules = (
        _collect_check_rules(session) if category in ("all", "consistency") else []
    )
    entropy = (
        _collect_entropy(session) if category in ("all", "discoverability") else {}
    )

    return snapshot, check_rules, entropy


def _resolve_compare_path(compare_arg: str) -> Path | None:
    """--compare 引数からスナップショットファイルパスを解決する。

    Parameters
    ----------
    compare_arg : str
        ``"latest"`` または日付文字列またはファイルパス。

    Returns
    -------
    Path | None
        スナップショットファイルのパス。見つからない場合は ``None``。
    """
    if compare_arg == "latest":
        return _find_latest_snapshot()

    search_dir = Path("data/processed/kg_quality")
    candidate = search_dir / f"snapshot_{compare_arg}.json"
    if candidate.exists():
        return candidate

    direct_path = Path(compare_arg)
    return direct_path if direct_path.exists() else None


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
            snapshot, check_rules, entropy = _run_measurements(
                session, schema, args.category
            )
            render_console(snapshot, check_rules, entropy)

            if args.save_snapshot:
                save_json(snapshot, check_rules, entropy)
                save_neo4j(session, snapshot, dry_run=args.dry_run)

            if args.report:
                md = generate_markdown(snapshot, check_rules, entropy)
                report_path = Path(args.report)
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text(md, encoding="utf-8")
                logger.info("Markdown report saved: %s", report_path)

            if args.compare:
                prev_path = _resolve_compare_path(args.compare)
                if prev_path is None:
                    logger.warning("Compare target not found: %s", args.compare)
                else:
                    prev_snapshot = _load_snapshot_from_json(prev_path)
                    print(compare_snapshots(prev_snapshot, snapshot))
    finally:
        driver.close()


if __name__ == "__main__":
    main()
