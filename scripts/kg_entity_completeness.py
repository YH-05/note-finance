#!/usr/bin/env python3
"""Entity Completeness チェッカー。

entity-completeness-schema.yaml を読み込み、research-neo4j 上の
company Entity のデータ完備性を評価してギャップレポートを生成する。

Usage
-----
::

    # 全 company Entity を評価
    uv run python scripts/kg_entity_completeness.py

    # 特定 Entity のみ
    uv run python scripts/kg_entity_completeness.py --entity "Indosat Ooredoo Hutchison"

    # レポート出力
    uv run python scripts/kg_entity_completeness.py --report data/processed/kg_quality/completeness_report.md

    # High 優先度ギャップのみ表示
    uv run python scripts/kg_entity_completeness.py --priority high
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime as dt
from datetime import timezone
from pathlib import Path
from typing import Any

import yaml
from neo4j_utils import create_driver

try:
    from quants.utils.logging_config import get_logger

    logger = get_logger(__name__)
except ImportError:
    import logging

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_SCHEMA_PATH = _PROJECT_ROOT / "data" / "config" / "entity-completeness-schema.yaml"
_DEFAULT_REPORT_DIR = _PROJECT_ROOT / "data" / "processed" / "kg_quality"


# ---------------------------------------------------------------------------
# DataClasses
# ---------------------------------------------------------------------------


@dataclass
class CheckItem:
    """スキーマから読み込んだ個別チェック項目。

    Attributes
    ----------
    phase : str
        フェーズ名（例: "Phase 1", "Telecom"）。
    label : str
        項目ラベル（例: "事業モデル", "Revenue"）。
    priority : str
        優先度（"high", "medium", "low"）。
    check_type : str
        チェック種別（"fact", "datapoint", "claim", "relationship"）。
    pattern : str
        正規表現パターン。
    min_periods : int
        最低必要期数（datapoint 用）。0 の場合は期数チェックなし。
    min_count : int
        最低必要件数（relationship 用）。0 の場合は件数チェックなし。
    """

    phase: str
    label: str
    priority: str
    check_type: str
    pattern: str
    min_periods: int = 0
    min_count: int = 0


@dataclass
class CheckResult:
    """個別チェック項目の評価結果。

    Attributes
    ----------
    item : CheckItem
        チェック項目。
    is_satisfied : bool
        充足しているか。
    matched_count : int
        マッチした件数。
    detail : str
        詳細情報（例: "4期"）。
    """

    item: CheckItem
    is_satisfied: bool
    matched_count: int = 0
    detail: str = ""


@dataclass
class EntityReport:
    """Entity 単位の評価レポート。

    Attributes
    ----------
    entity_key : str
        Entity の entity_key。
    name : str
        Entity 名。
    entity_type : str
        Entity タイプ（company）。
    sector : str
        検出されたセクター（未検出の場合は "unknown"）。
    results : list[CheckResult]
        チェック結果リスト。
    completeness_score : float
        完備度スコア（0.0 ~ 1.0）。
    """

    entity_key: str
    name: str
    entity_type: str
    sector: str = "unknown"
    results: list[CheckResult] = field(default_factory=list)
    completeness_score: float = 0.0


# ---------------------------------------------------------------------------
# Schema Loading
# ---------------------------------------------------------------------------


def load_schema(schema_path: Path) -> dict[str, Any]:
    """YAML スキーマを読み込む。

    Parameters
    ----------
    schema_path : Path
        スキーマファイルパス。

    Returns
    -------
    dict[str, Any]
        パース済みスキーマ。

    Raises
    ------
    FileNotFoundError
        スキーマファイルが存在しない場合。
    """
    if not schema_path.exists():
        msg = f"Schema file not found: {schema_path}"
        logger.error(msg)
        raise FileNotFoundError(msg)

    logger.info("Loading schema: %s", schema_path)
    with open(schema_path, encoding="utf-8") as f:
        schema = yaml.safe_load(f)
    logger.debug("Schema loaded", version=schema.get("version"))
    return schema


def _phase_display_name(key: str) -> str:
    """スキーマのフェーズキーを表示用名に変換する。

    Parameters
    ----------
    key : str
        スキーマキー（例: "phase1_overview"）。

    Returns
    -------
    str
        表示名（例: "Phase 1"）。
    """
    mapping = {
        "phase1_overview": "Phase 1",
        "phase4_financials": "Phase 4",
        "phase5_valuation": "Phase 5",
        "phase6_catalysts": "Phase 6",
    }
    return mapping.get(key, key)


def parse_common_checks(schema: dict[str, Any]) -> list[CheckItem]:
    """common セクションからチェック項目を抽出する。

    Parameters
    ----------
    schema : dict[str, Any]
        パース済みスキーマ。

    Returns
    -------
    list[CheckItem]
        チェック項目リスト。
    """
    items: list[CheckItem] = []
    common = schema.get("common", {})

    for phase_key, phase_def in common.items():
        phase_name = _phase_display_name(phase_key)

        # facts
        for fact in phase_def.get("facts", []):
            items.append(
                CheckItem(
                    phase=phase_name,
                    label=fact["label"],
                    priority=fact["priority"],
                    check_type="fact",
                    pattern=fact["pattern"],
                )
            )

        # datapoints
        for dp in phase_def.get("datapoints", []):
            items.append(
                CheckItem(
                    phase=phase_name,
                    label=dp["label"],
                    priority=dp["priority"],
                    check_type="datapoint",
                    pattern=dp["metric_pattern"],
                    min_periods=dp.get("min_periods", 0),
                )
            )

        # claims
        for claim in phase_def.get("claims", []):
            items.append(
                CheckItem(
                    phase=phase_name,
                    label=claim["label"],
                    priority=claim["priority"],
                    check_type="claim",
                    pattern=claim["pattern"],
                )
            )

        # relationships
        for rel in phase_def.get("relationships", []):
            items.append(
                CheckItem(
                    phase=phase_name,
                    label=rel["label"],
                    priority="medium",
                    check_type="relationship",
                    pattern=rel["type"],
                    min_count=rel.get("min_count", 1),
                )
            )

    logger.debug("Parsed %d common check items", len(items))
    return items


def parse_sector_checks(schema: dict[str, Any]) -> dict[str, tuple[str, list[CheckItem]]]:
    """sectors セクションからセクター別チェック項目を抽出する。

    Parameters
    ----------
    schema : dict[str, Any]
        パース済みスキーマ。

    Returns
    -------
    dict[str, tuple[str, list[CheckItem]]]
        セクターキー -> (match_pattern, チェック項目リスト) の辞書。
    """
    sector_map: dict[str, tuple[str, list[CheckItem]]] = {}
    sectors = schema.get("sectors", {})

    for sector_key, sector_def in sectors.items():
        match_pattern = sector_def.get("match_pattern", "")
        items: list[CheckItem] = []
        display_name = sector_key.replace("_", " ").title()

        for kpi in sector_def.get("kpis", []):
            items.append(
                CheckItem(
                    phase=display_name,
                    label=kpi["label"],
                    priority=kpi["priority"],
                    check_type="datapoint",
                    pattern=kpi["metric_pattern"],
                    min_periods=kpi.get("min_periods", 0),
                )
            )

        sector_map[sector_key] = (match_pattern, items)
        logger.debug(
            "Parsed sector '%s': %d KPIs", sector_key, len(items)
        )

    return sector_map


def get_scoring_weights(schema: dict[str, Any]) -> dict[str, int]:
    """スコアリング重みを取得する。

    Parameters
    ----------
    schema : dict[str, Any]
        パース済みスキーマ。

    Returns
    -------
    dict[str, int]
        優先度 -> 重みの辞書。
    """
    default_weights = {"high": 3, "medium": 2, "low": 1}
    scoring = schema.get("scoring", {})
    weights = scoring.get("weights", default_weights)
    return weights


# ---------------------------------------------------------------------------
# Neo4j Queries
# ---------------------------------------------------------------------------


def fetch_company_entities(driver: Any, entity_name: str | None = None) -> list[dict[str, Any]]:
    """company Entity を取得する。

    Parameters
    ----------
    driver : Any
        Neo4j ドライバー。
    entity_name : str | None
        特定 Entity 名でフィルタ。None の場合は全件取得。

    Returns
    -------
    list[dict[str, Any]]
        Entity レコードのリスト。各要素は entity_key, name, entity_type を持つ。
    """
    if entity_name:
        query = """
        MATCH (e:Entity)
        WHERE e.entity_type = 'company' AND e.name CONTAINS $name
        RETURN e.entity_key AS entity_key, e.name AS name, e.entity_type AS entity_type
        ORDER BY e.name
        """
        params = {"name": entity_name}
    else:
        query = """
        MATCH (e:Entity)
        WHERE e.entity_type = 'company'
        RETURN e.entity_key AS entity_key, e.name AS name, e.entity_type AS entity_type
        ORDER BY e.name
        """
        params = {}

    logger.info("Fetching company entities (filter=%s)", entity_name or "all")
    with driver.session() as session:
        result = session.run(query, params)
        entities = [record.data() for record in result]

    logger.info("Found %d company entities", len(entities))
    return entities


def fetch_entity_facts(driver: Any, entity_key: str) -> list[str]:
    """Entity に接続された Fact の content を取得する。

    Parameters
    ----------
    driver : Any
        Neo4j ドライバー。
    entity_key : str
        対象 Entity の entity_key。

    Returns
    -------
    list[str]
        Fact.content のリスト。
    """
    query = """
    MATCH (e:Entity {entity_key: $entity_key})<-[:RELATES_TO]-(f:Fact)
    RETURN f.content AS content
    """
    with driver.session() as session:
        result = session.run(query, {"entity_key": entity_key})
        facts = [record["content"] for record in result if record["content"]]
    logger.debug("Entity '%s': %d facts", entity_key, len(facts))
    return facts


def fetch_entity_datapoints(driver: Any, entity_key: str) -> list[dict[str, Any]]:
    """Entity に接続された FinancialDataPoint を取得する。

    Parameters
    ----------
    driver : Any
        Neo4j ドライバー。
    entity_key : str
        対象 Entity の entity_key。

    Returns
    -------
    list[dict[str, Any]]
        FinancialDataPoint レコードのリスト。各要素は metric_name, value, fiscal_year, fiscal_quarter を持つ。
    """
    query = """
    MATCH (e:Entity {entity_key: $entity_key})<-[:RELATES_TO]-(dp:FinancialDataPoint)
    RETURN dp.metric_name AS metric_name, dp.value AS value,
           dp.fiscal_year AS fiscal_year, dp.fiscal_quarter AS fiscal_quarter
    """
    with driver.session() as session:
        result = session.run(query, {"entity_key": entity_key})
        datapoints = [record.data() for record in result]
    logger.debug("Entity '%s': %d datapoints", entity_key, len(datapoints))
    return datapoints


def fetch_entity_claims(driver: Any, entity_key: str) -> list[str]:
    """Entity に接続された Claim の content を取得する。

    Parameters
    ----------
    driver : Any
        Neo4j ドライバー。
    entity_key : str
        対象 Entity の entity_key。

    Returns
    -------
    list[str]
        Claim.content のリスト。
    """
    query = """
    MATCH (e:Entity {entity_key: $entity_key})<-[:ABOUT]-(c:Claim)
    RETURN c.content AS content
    """
    with driver.session() as session:
        result = session.run(query, {"entity_key": entity_key})
        claims = [record["content"] for record in result if record["content"]]
    logger.debug("Entity '%s': %d claims", entity_key, len(claims))
    return claims


def fetch_entity_fact_count(driver: Any, entity_key: str) -> int:
    """Entity に接続された Fact の件数を取得する。

    Parameters
    ----------
    driver : Any
        Neo4j ドライバー。
    entity_key : str
        対象 Entity の entity_key。

    Returns
    -------
    int
        Fact の件数。
    """
    query = """
    MATCH (e:Entity {entity_key: $entity_key})<-[:RELATES_TO]-(f:Fact)
    RETURN count(f) AS cnt
    """
    with driver.session() as session:
        result = session.run(query, {"entity_key": entity_key})
        record = result.single()
        return record["cnt"] if record else 0


def detect_sector(
    driver: Any,
    entity_key: str,
    facts: list[str],
    sector_map: dict[str, tuple[str, list[CheckItem]]],
) -> str:
    """Entity のセクターを推定する。

    Topic の category、Fact の content からセクターをマッチングする。

    Parameters
    ----------
    driver : Any
        Neo4j ドライバー。
    entity_key : str
        対象 Entity の entity_key。
    facts : list[str]
        Fact.content のリスト。
    sector_map : dict[str, tuple[str, list[CheckItem]]]
        セクターキー -> (match_pattern, チェック項目リスト) の辞書。

    Returns
    -------
    str
        検出されたセクターキー。未検出の場合は "unknown"。
    """
    # 1. Topic の category をチェック
    query = """
    MATCH (e:Entity {entity_key: $entity_key})-[:TAGGED]->(t:Topic)
    RETURN t.category AS category, t.name AS name
    """
    topic_texts: list[str] = []
    with driver.session() as session:
        result = session.run(query, {"entity_key": entity_key})
        for record in result:
            if record["category"]:
                topic_texts.append(record["category"])
            if record["name"]:
                topic_texts.append(record["name"])

    # 全テキストを結合して検索対象にする
    all_text = " ".join(topic_texts + facts)

    for sector_key, (match_pattern, _items) in sector_map.items():
        if re.search(match_pattern, all_text, re.IGNORECASE):
            logger.debug("Entity '%s': detected sector '%s'", entity_key, sector_key)
            return sector_key

    logger.debug("Entity '%s': no sector detected", entity_key)
    return "unknown"


# ---------------------------------------------------------------------------
# Evaluation Logic
# ---------------------------------------------------------------------------


def evaluate_fact_check(item: CheckItem, facts: list[str]) -> CheckResult:
    """Fact チェック項目を評価する。

    Parameters
    ----------
    item : CheckItem
        チェック項目。
    facts : list[str]
        Fact.content のリスト。

    Returns
    -------
    CheckResult
        評価結果。
    """
    matched = [f for f in facts if re.search(item.pattern, f, re.IGNORECASE)]
    is_satisfied = len(matched) > 0
    return CheckResult(
        item=item,
        is_satisfied=is_satisfied,
        matched_count=len(matched),
        detail=f"{len(matched)}件" if matched else "",
    )


def evaluate_datapoint_check(
    item: CheckItem, datapoints: list[dict[str, Any]]
) -> CheckResult:
    """FinancialDataPoint チェック項目を評価する。

    Parameters
    ----------
    item : CheckItem
        チェック項目。
    datapoints : list[dict[str, Any]]
        FinancialDataPoint レコードのリスト。

    Returns
    -------
    CheckResult
        評価結果。
    """
    matched = [
        dp for dp in datapoints
        if dp.get("metric_name") and re.search(item.pattern, dp["metric_name"], re.IGNORECASE)
    ]
    matched_count = len(matched)

    # 期数チェック: fiscal_year + fiscal_quarter のユニーク数
    if item.min_periods > 0 and matched:
        unique_periods = set()
        for dp in matched:
            period_key = (dp.get("fiscal_year"), dp.get("fiscal_quarter"))
            unique_periods.add(period_key)
        period_count = len(unique_periods)
        is_satisfied = period_count >= item.min_periods
        detail = f"{period_count}期"
    else:
        is_satisfied = matched_count > 0
        period_count = matched_count
        detail = f"{matched_count}件" if matched else ""

    return CheckResult(
        item=item,
        is_satisfied=is_satisfied,
        matched_count=matched_count,
        detail=detail,
    )


def evaluate_claim_check(item: CheckItem, claims: list[str]) -> CheckResult:
    """Claim チェック項目を評価する。

    Parameters
    ----------
    item : CheckItem
        チェック項目。
    claims : list[str]
        Claim.content のリスト。

    Returns
    -------
    CheckResult
        評価結果。
    """
    matched = [c for c in claims if re.search(item.pattern, c, re.IGNORECASE)]
    is_satisfied = len(matched) > 0
    return CheckResult(
        item=item,
        is_satisfied=is_satisfied,
        matched_count=len(matched),
        detail=f"{len(matched)}件" if matched else "",
    )


def evaluate_relationship_check(
    item: CheckItem, fact_count: int
) -> CheckResult:
    """Relationship チェック項目を評価する。

    Parameters
    ----------
    item : CheckItem
        チェック項目。
    fact_count : int
        Fact 接続件数。

    Returns
    -------
    CheckResult
        評価結果。
    """
    is_satisfied = fact_count >= item.min_count
    return CheckResult(
        item=item,
        is_satisfied=is_satisfied,
        matched_count=fact_count,
        detail=f"{fact_count}件",
    )


def evaluate_entity(
    driver: Any,
    entity: dict[str, Any],
    common_checks: list[CheckItem],
    sector_map: dict[str, tuple[str, list[CheckItem]]],
    weights: dict[str, int],
) -> EntityReport:
    """Entity の完備性を評価する。

    Parameters
    ----------
    driver : Any
        Neo4j ドライバー。
    entity : dict[str, Any]
        Entity レコード（entity_key, name, entity_type）。
    common_checks : list[CheckItem]
        共通チェック項目リスト。
    sector_map : dict[str, tuple[str, list[CheckItem]]]
        セクター別チェック項目。
    weights : dict[str, int]
        優先度 -> 重みの辞書。

    Returns
    -------
    EntityReport
        評価レポート。
    """
    entity_key = entity["entity_key"]
    name = entity["name"]
    entity_type = entity["entity_type"]

    logger.info("Evaluating entity: %s (%s)", name, entity_key)

    # データ取得
    facts = fetch_entity_facts(driver, entity_key)
    datapoints = fetch_entity_datapoints(driver, entity_key)
    claims = fetch_entity_claims(driver, entity_key)
    fact_count = fetch_entity_fact_count(driver, entity_key)

    # セクター検出
    sector = detect_sector(driver, entity_key, facts, sector_map)

    # 共通チェック評価
    results: list[CheckResult] = []
    for item in common_checks:
        if item.check_type == "fact":
            results.append(evaluate_fact_check(item, facts))
        elif item.check_type == "datapoint":
            results.append(evaluate_datapoint_check(item, datapoints))
        elif item.check_type == "claim":
            results.append(evaluate_claim_check(item, claims))
        elif item.check_type == "relationship":
            results.append(evaluate_relationship_check(item, fact_count))

    # セクター固有チェック評価
    if sector != "unknown" and sector in sector_map:
        _match_pattern, sector_checks = sector_map[sector]
        for item in sector_checks:
            if item.check_type == "datapoint":
                results.append(evaluate_datapoint_check(item, datapoints))
            elif item.check_type == "fact":
                results.append(evaluate_fact_check(item, facts))

    # スコア計算
    total_weight = sum(weights.get(r.item.priority, 1) for r in results)
    satisfied_weight = sum(
        weights.get(r.item.priority, 1) for r in results if r.is_satisfied
    )
    score = satisfied_weight / total_weight if total_weight > 0 else 0.0

    report = EntityReport(
        entity_key=entity_key,
        name=name,
        entity_type=entity_type,
        sector=sector,
        results=results,
        completeness_score=score,
    )

    satisfied_count = sum(1 for r in results if r.is_satisfied)
    logger.info(
        "Entity '%s': score=%.2f (%d/%d items), sector=%s",
        name,
        score,
        satisfied_count,
        len(results),
        sector,
    )
    return report


# ---------------------------------------------------------------------------
# Report Generation
# ---------------------------------------------------------------------------


def generate_report(
    reports: list[EntityReport],
    weights: dict[str, int],
    priority_filter: str | None = None,
) -> str:
    """Markdown 形式のギャップレポートを生成する。

    Parameters
    ----------
    reports : list[EntityReport]
        Entity 別レポートリスト。
    weights : dict[str, int]
        スコアリング重み。
    priority_filter : str | None
        表示する優先度フィルタ（"high", "medium", "low"）。None の場合は全件表示。

    Returns
    -------
    str
        Markdown 形式のレポート。
    """
    lines: list[str] = []
    now = dt.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Summary
    entity_count = len(reports)
    avg_score = (
        sum(r.completeness_score for r in reports) / entity_count
        if entity_count > 0
        else 0.0
    )
    high_gaps = sum(
        1
        for r in reports
        for cr in r.results
        if cr.item.priority == "high" and not cr.is_satisfied
    )

    lines.append("# Entity Completeness Report")
    lines.append("")
    lines.append(f"Generated: {now}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| 指標 | 値 |")
    lines.append("|------|-----|")
    lines.append(f"| 対象Entity数 | {entity_count} |")
    lines.append(f"| 平均完備度 | {avg_score:.2f} |")
    lines.append(f"| High優先度ギャップ | {high_gaps} |")
    lines.append("")

    # Entity 別ギャップ
    lines.append("## Entity別ギャップ")
    lines.append("")

    for report in sorted(reports, key=lambda r: r.completeness_score):
        satisfied_count = sum(1 for r in report.results if r.is_satisfied)
        total_count = len(report.results)

        lines.append(f"### {report.name} ({report.entity_type})")
        lines.append(
            f"Completeness: {report.completeness_score:.2f} ({satisfied_count}/{total_count} items)"
        )
        lines.append(f"Sector: {report.sector}")
        lines.append("")
        lines.append("| フェーズ | 項目 | 優先度 | 状態 |")
        lines.append("|---------|------|--------|------|")

        for cr in report.results:
            # 優先度フィルタ
            if priority_filter and cr.item.priority != priority_filter:
                continue

            if cr.is_satisfied:
                detail_str = f" ({cr.detail})" if cr.detail else ""
                status = f"✅{detail_str}"
            else:
                status = "❌"

            lines.append(
                f"| {cr.item.phase} | {cr.item.label} | {cr.item.priority} | {status} |"
            )

        lines.append("")

    return "\n".join(lines)


def print_summary(reports: list[EntityReport], priority_filter: str | None = None) -> None:
    """コンソールにサマリーを出力する。

    Parameters
    ----------
    reports : list[EntityReport]
        Entity 別レポートリスト。
    priority_filter : str | None
        優先度フィルタ。
    """
    entity_count = len(reports)
    if entity_count == 0:
        print("No company entities found.")
        return

    avg_score = sum(r.completeness_score for r in reports) / entity_count
    high_gaps = sum(
        1
        for r in reports
        for cr in r.results
        if cr.item.priority == "high" and not cr.is_satisfied
    )

    print("\n=== Entity Completeness Summary ===")
    print(f"対象Entity数: {entity_count}")
    print(f"平均完備度:   {avg_score:.2f}")
    print(f"High優先度ギャップ: {high_gaps}")
    print()

    for report in sorted(reports, key=lambda r: r.completeness_score):
        satisfied_count = sum(1 for r in report.results if r.is_satisfied)
        total_count = len(report.results)

        gaps: list[str] = []
        for cr in report.results:
            if not cr.is_satisfied:
                if priority_filter and cr.item.priority != priority_filter:
                    continue
                gaps.append(f"  - [{cr.item.priority}] {cr.item.phase}: {cr.item.label}")

        score_bar = _score_bar(report.completeness_score)
        print(
            f"{report.name} ({report.sector}): "
            f"{score_bar} {report.completeness_score:.2f} "
            f"({satisfied_count}/{total_count})"
        )

        if gaps:
            print("  Gaps:")
            for gap in gaps:
                print(gap)
        print()


def _score_bar(score: float, width: int = 20) -> str:
    """スコアを視覚化したバーを返す。

    Parameters
    ----------
    score : float
        0.0 ~ 1.0 のスコア。
    width : int
        バーの幅。

    Returns
    -------
    str
        視覚化バー。
    """
    filled = int(score * width)
    empty = width - filled
    return f"[{'#' * filled}{'.' * empty}]"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """コマンドライン引数を解析する。

    Parameters
    ----------
    argv : list[str] | None
        引数リスト。None の場合は sys.argv[1:] を使用する。

    Returns
    -------
    argparse.Namespace
        解析済み引数。
    """
    parser = argparse.ArgumentParser(
        description="Entity Completeness チェッカー — company Entity のデータ完備性を評価",
    )
    parser.add_argument(
        "--entity",
        default=None,
        help="特定 Entity 名でフィルタ（部分一致）",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Markdown レポート出力先パス",
    )
    parser.add_argument(
        "--priority",
        choices=["high", "medium", "low"],
        default=None,
        help="表示する優先度フィルタ",
    )
    parser.add_argument(
        "--schema",
        default=str(_DEFAULT_SCHEMA_PATH),
        help=f"スキーマファイルパス（デフォルト: {_DEFAULT_SCHEMA_PATH}）",
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
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """エントリーポイント。"""
    args = parse_args()

    # スキーマ読み込み
    schema_path = Path(args.schema)
    schema = load_schema(schema_path)

    # チェック項目解析
    common_checks = parse_common_checks(schema)
    sector_map = parse_sector_checks(schema)
    weights = get_scoring_weights(schema)

    logger.info(
        "Schema loaded: %d common checks, %d sectors",
        len(common_checks),
        len(sector_map),
    )

    # Neo4j 接続
    driver = create_driver(
        uri=args.neo4j_uri,
        user=args.neo4j_user,
        password=args.neo4j_password,
    )

    try:
        # Entity 取得
        entities = fetch_company_entities(driver, entity_name=args.entity)

        if not entities:
            logger.warning("No company entities found")
            print("No company entities found.")
            return

        # 評価実行
        reports: list[EntityReport] = []
        for entity in entities:
            report = evaluate_entity(
                driver=driver,
                entity=entity,
                common_checks=common_checks,
                sector_map=sector_map,
                weights=weights,
            )
            reports.append(report)

        # コンソール出力
        print_summary(reports, priority_filter=args.priority)

        # レポート出力
        if args.report:
            report_path = Path(args.report)
            report_path.parent.mkdir(parents=True, exist_ok=True)
            md_report = generate_report(
                reports, weights, priority_filter=args.priority
            )
            report_path.write_text(md_report, encoding="utf-8")
            logger.info("Report saved: %s", report_path)
            print(f"Report saved: {report_path}")

    finally:
        driver.close()
        logger.info("Neo4j connection closed")


if __name__ == "__main__":
    main()
