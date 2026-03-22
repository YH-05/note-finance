"""KG 品質アラートモジュール。

品質低下時に GitHub Issue を自動作成し、見逃しを防止する。

Usage
-----
::

    # kg_quality_metrics.py の --alert フラグ経由で呼び出される
    from kg_quality_alert import run_alert
    run_alert(snapshot, check_rules, prev_path)

    # スタンドアロン（dry-run）
    python scripts/kg_quality_alert.py --dry-run
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from quants.utils.logging_config import get_logger

    logger = get_logger(__name__)
except ImportError:
    import logging

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DataClasses
# ---------------------------------------------------------------------------


@dataclass
class AlertCondition:
    """アラート条件。"""

    name: str
    severity: str  # "critical" | "warning"
    message: str
    current_value: float
    threshold: float


# ---------------------------------------------------------------------------
# アラート評価
# ---------------------------------------------------------------------------


def _extract_orphan_entity_count(snapshot: Any) -> int | None:
    """QualitySnapshot の structural カテゴリから Orphan Entity Count を抽出する。

    Parameters
    ----------
    snapshot
        QualitySnapshot インスタンス。

    Returns
    -------
    int | None
        Orphan Entity Count の値。structural カテゴリまたは該当メトリクスが
        見つからない場合は None。
    """
    for cat in snapshot.categories:
        # structural metrics の 5番目（index=4）が Orphan Entity Count
        # _METRIC_LABELS: ["Edge Density", "Avg Degree", "Connected Ratio",
        #                   "Orphan Ratio", "Orphan Entity Count"]
        if cat.name == "structural" and len(cat.metrics) >= 5:
            return int(cat.metrics[4].value)
    return None


def evaluate_alerts(
    current: Any,
    previous: Any | None,
    check_rules: list[Any],
) -> list[AlertCondition]:
    """アラート条件を評価する。

    Parameters
    ----------
    current
        現在の QualitySnapshot。
    previous
        前回の QualitySnapshot（None の場合はスコア比較をスキップ）。
    check_rules : list
        チェックルール結果リスト。

    Returns
    -------
    list[AlertCondition]
        発火したアラート条件のリスト。
    """
    alerts: list[AlertCondition] = []

    # 1. Overall score の前回比較
    if previous is not None:
        score_diff = current.overall_score - previous.overall_score

        if score_diff <= -10.0:
            alerts.append(
                AlertCondition(
                    name="overall_score_critical",
                    severity="critical",
                    message=f"Overall score が {abs(score_diff):.1f}pt 低下 "
                    f"({previous.overall_score:.1f} → {current.overall_score:.1f})",
                    current_value=current.overall_score,
                    threshold=previous.overall_score - 10.0,
                )
            )
        elif score_diff <= -5.0:
            alerts.append(
                AlertCondition(
                    name="overall_score_warning",
                    severity="warning",
                    message=f"Overall score が {abs(score_diff):.1f}pt 低下 "
                    f"({previous.overall_score:.1f} → {current.overall_score:.1f})",
                    current_value=current.overall_score,
                    threshold=previous.overall_score - 5.0,
                )
            )

    # 2. CheckRule pass_rate < 95%
    for rule in check_rules:
        if rule.pass_rate < 0.95:
            alerts.append(
                AlertCondition(
                    name=f"check_rule_{rule.rule_name}",
                    severity="warning",
                    message=f"CheckRule '{rule.rule_name}' pass_rate={rule.pass_rate:.2%} "
                    f"(threshold: 95%)",
                    current_value=rule.pass_rate,
                    threshold=0.95,
                )
            )

    # 3. Orphan Entity 絶対数アラート
    try:
        from kg_quality_metrics import ORPHAN_ENTITY_CRIT, ORPHAN_ENTITY_WARN

        orphan_entity_count = _extract_orphan_entity_count(current)
        if orphan_entity_count is not None:
            if orphan_entity_count >= ORPHAN_ENTITY_CRIT:
                alerts.append(
                    AlertCondition(
                        name="orphan_entity_critical",
                        severity="critical",
                        message=f"Orphan Entity count: {orphan_entity_count} "
                        f"(threshold: {ORPHAN_ENTITY_CRIT})\n"
                        "  → save-to-graph の fact_entity RELATES_TO 投入を確認してください\n"
                        "  → 対処: Entity名でFact.contentを検索し RELATES_TO を接続",
                        current_value=float(orphan_entity_count),
                        threshold=float(ORPHAN_ENTITY_CRIT),
                    )
                )
            elif orphan_entity_count >= ORPHAN_ENTITY_WARN:
                alerts.append(
                    AlertCondition(
                        name="orphan_entity_warning",
                        severity="warning",
                        message=f"Orphan Entity count: {orphan_entity_count} "
                        f"(threshold: {ORPHAN_ENTITY_WARN})\n"
                        "  → 大量投入後の Entity 接続を確認してください",
                        current_value=float(orphan_entity_count),
                        threshold=float(ORPHAN_ENTITY_WARN),
                    )
                )
    except ImportError:
        logger.warning(
            "Could not import orphan entity thresholds from kg_quality_metrics"
        )

    logger.info("Alert evaluation: %d alerts triggered", len(alerts))
    return alerts


# ---------------------------------------------------------------------------
# GitHub Issue 作成
# ---------------------------------------------------------------------------


def _get_repo() -> str:
    """git remote get-url origin からリポジトリを取得する。"""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
        )
        url = result.stdout.strip()
        # https://github.com/user/repo.git or git@github.com:user/repo.git
        repo = url.split("github.com")[-1]
        repo = repo.lstrip("/").lstrip(":").rstrip(".git")
        return repo
    except subprocess.CalledProcessError:
        return "YH-05/note-finance"


def _has_open_alert_issue() -> bool:
    """kg-quality-alert ラベルの open Issue が既に存在するか確認する。"""
    try:
        repo = _get_repo()
        result = subprocess.run(
            [
                "gh",
                "issue",
                "list",
                "--repo",
                repo,
                "--label",
                "kg-quality-alert",
                "--state",
                "open",
                "--json",
                "number",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        issues = json.loads(result.stdout)
        return len(issues) > 0
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return False


def _format_issue_body(
    alerts: list[AlertCondition],
    current: Any,
) -> str:
    """Issue 本文を生成する。"""
    lines: list[str] = [
        "## KG品質アラート",
        "",
        f"**計測日時**: {current.timestamp.isoformat()}",
        f"**Overall Score**: {current.overall_score:.1f}",
        "",
        "## アラート詳細",
        "",
        "| 名前 | 重要度 | 内容 | 現在値 | 閾値 |",
        "|------|--------|------|-------:|-----:|",
    ]

    for alert in alerts:
        lines.append(
            f"| {alert.name} | {alert.severity} | {alert.message} | "
            f"{alert.current_value:.2f} | {alert.threshold:.2f} |"
        )

    lines.extend(
        [
            "",
            "## カテゴリスコア",
            "",
            "| Category | Score |",
            "|----------|------:|",
        ]
    )

    for cat in current.categories:
        lines.append(f"| {cat.name} | {cat.score:.1f} |")

    lines.extend(
        [
            "",
            "## 推奨アクション",
            "",
        ]
    )

    has_critical = any(a.severity == "critical" for a in alerts)
    if has_critical:
        lines.append("- [ ] Critical アラートの原因調査")
        lines.append("- [ ] データ品質修正スクリプトの実行確認")
    lines.append("- [ ] `make kg-quality` で修正後の再計測")
    lines.append("")

    return "\n".join(lines)


def create_github_issue(
    alerts: list[AlertCondition],
    current: Any,
    *,
    dry_run: bool = False,
) -> str | None:
    """GitHub Issue を作成する。

    Parameters
    ----------
    alerts : list[AlertCondition]
        アラート条件リスト。
    current
        現在の QualitySnapshot。
    dry_run : bool
        True の場合は Issue を作成しない。

    Returns
    -------
    str | None
        作成した Issue の URL。dry-run の場合は None。
    """
    if not alerts:
        logger.info("No alerts to report")
        return None

    # 重複防止
    if not dry_run and _has_open_alert_issue():
        logger.info("Open kg-quality-alert issue already exists, skipping")
        return None

    max_severity = (
        "critical" if any(a.severity == "critical" for a in alerts) else "warning"
    )
    title = f"[KG品質] {max_severity}: スコア低下検出 ({current.overall_score:.1f}pt)"
    body = _format_issue_body(alerts, current)

    if dry_run:
        logger.info("[DRY-RUN] Would create issue: %s", title)
        logger.info("[DRY-RUN] Alerts: %d", len(alerts))
        return None

    try:
        repo = _get_repo()
        result = subprocess.run(
            [
                "gh",
                "issue",
                "create",
                "--repo",
                repo,
                "--title",
                title,
                "--body",
                body,
                "--label",
                "kg-quality-alert",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        issue_url = result.stdout.strip()
        logger.info("GitHub Issue created: %s", issue_url)
        return issue_url
    except subprocess.CalledProcessError as e:
        logger.error("Failed to create GitHub Issue: %s", e.stderr)
        return None


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------


def run_alert(
    snapshot: Any,
    check_rules: list[Any],
    prev_path: Path | None,
    *,
    dry_run: bool = False,
) -> list[AlertCondition]:
    """アラート評価 + Issue 作成を実行する。

    Parameters
    ----------
    snapshot
        現在の QualitySnapshot。
    check_rules : list
        チェックルール結果リスト。
    prev_path : Path | None
        前回スナップショットのパス。
    dry_run : bool
        True の場合は Issue を作成しない。

    Returns
    -------
    list[AlertCondition]
        発火したアラート条件のリスト。
    """
    previous = None
    if prev_path is not None:
        try:
            from kg_quality_metrics import _load_snapshot_from_json

            previous = _load_snapshot_from_json(prev_path)
        except Exception as e:
            logger.warning("Could not load previous snapshot: %s", e)

    alerts = evaluate_alerts(snapshot, previous, check_rules)

    if alerts:
        create_github_issue(alerts, snapshot, dry_run=dry_run)
    else:
        logger.info("No quality alerts triggered")

    return alerts
