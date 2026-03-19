"""kg_quality_alert.py のユニットテスト。"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from kg_quality_alert import (
    AlertCondition,
    _format_issue_body,
    create_github_issue,
    evaluate_alerts,
    run_alert,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_snapshot(overall_score: float, categories: list | None = None):
    """テスト用 QualitySnapshot を作成する。"""
    mock = MagicMock()
    mock.overall_score = overall_score
    mock.timestamp = datetime(2026, 3, 19, tzinfo=timezone.utc)
    mock.categories = categories or []
    return mock


def _make_check_rule(rule_name: str, pass_rate: float, violations: list | None = None):
    """テスト用 CheckRuleResult を作成する。"""
    mock = MagicMock()
    mock.rule_name = rule_name
    mock.pass_rate = pass_rate
    mock.violations = violations or []
    return mock


# ---------------------------------------------------------------------------
# evaluate_alerts
# ---------------------------------------------------------------------------


class TestEvaluateAlerts:
    def test_正常系_スコア10pt低下でcritical(self) -> None:
        current = _make_snapshot(40.0)
        previous = _make_snapshot(55.0)

        alerts = evaluate_alerts(current, previous, [])

        assert len(alerts) == 1
        assert alerts[0].severity == "critical"
        assert "15.0pt 低下" in alerts[0].message

    def test_正常系_スコア5pt低下でwarning(self) -> None:
        current = _make_snapshot(45.0)
        previous = _make_snapshot(52.0)

        alerts = evaluate_alerts(current, previous, [])

        assert len(alerts) == 1
        assert alerts[0].severity == "warning"

    def test_正常系_スコア安定で0件(self) -> None:
        current = _make_snapshot(50.0)
        previous = _make_snapshot(51.0)

        alerts = evaluate_alerts(current, previous, [])

        assert len(alerts) == 0

    def test_正常系_previousがNoneの場合スコア比較スキップ(self) -> None:
        current = _make_snapshot(30.0)

        alerts = evaluate_alerts(current, None, [])

        assert len(alerts) == 0

    def test_正常系_CheckRule低下でwarning(self) -> None:
        current = _make_snapshot(50.0)
        check_rules = [
            _make_check_rule("schema_compliance", 0.90),
            _make_check_rule("entity_length", 0.98),
        ]

        alerts = evaluate_alerts(current, None, check_rules)

        assert len(alerts) == 1
        assert "schema_compliance" in alerts[0].name

    def test_正常系_複数アラートが同時に発火(self) -> None:
        current = _make_snapshot(30.0)
        previous = _make_snapshot(45.0)
        check_rules = [_make_check_rule("test_rule", 0.80)]

        alerts = evaluate_alerts(current, previous, check_rules)

        assert len(alerts) == 2


# ---------------------------------------------------------------------------
# _format_issue_body
# ---------------------------------------------------------------------------


class TestFormatIssueBody:
    def test_正常系_Markdown形式で生成される(self) -> None:
        current = _make_snapshot(40.0)
        alerts = [
            AlertCondition(
                name="test",
                severity="warning",
                message="test alert",
                current_value=40.0,
                threshold=45.0,
            )
        ]

        body = _format_issue_body(alerts, current)

        assert "## KG品質アラート" in body
        assert "test alert" in body
        assert "推奨アクション" in body


# ---------------------------------------------------------------------------
# create_github_issue
# ---------------------------------------------------------------------------


class TestCreateGithubIssue:
    def test_正常系_dry_runではNoneを返す(self) -> None:
        current = _make_snapshot(40.0)
        alerts = [
            AlertCondition(
                name="test",
                severity="warning",
                message="test",
                current_value=40.0,
                threshold=45.0,
            )
        ]

        result = create_github_issue(alerts, current, dry_run=True)

        assert result is None

    def test_エッジケース_アラートなしではNone(self) -> None:
        current = _make_snapshot(80.0)
        result = create_github_issue([], current, dry_run=True)
        assert result is None


# ---------------------------------------------------------------------------
# run_alert
# ---------------------------------------------------------------------------


class TestRunAlert:
    def test_正常系_prev_pathがNoneでも動作する(self) -> None:
        snapshot = _make_snapshot(50.0)
        check_rules = [_make_check_rule("test", 0.90)]

        alerts = run_alert(snapshot, check_rules, None, dry_run=True)

        assert len(alerts) == 1

    @patch("kg_quality_alert._load_snapshot_from_json" if False else "kg_quality_alert.create_github_issue")
    def test_正常系_アラートなしではIssue作成しない(self, mock_create: MagicMock) -> None:
        snapshot = _make_snapshot(50.0)
        check_rules = [_make_check_rule("test", 0.99)]

        alerts = run_alert(snapshot, check_rules, None, dry_run=True)

        assert len(alerts) == 0
