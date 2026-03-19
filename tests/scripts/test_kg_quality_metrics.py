"""kg_quality_metrics.py の純粋関数に対するユニットテスト。

DataClasses・インフラ関数・CLI・定数の基盤部分を検証する。
Neo4j 接続はモックで代替し、DB不要でテスト実行可能。
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

# scripts/ をインポートパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from kg_quality_metrics import (
    ALLOWED_ENTITY_TYPES,
    THRESHOLDS,
    CategoryResult,
    CheckRuleResult,
    MetricValue,
    QualitySnapshot,
    create_driver,
    get_counts,
    load_schema,
    parse_args,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_schema_file(tmp_path: Path) -> Path:
    """テスト用スキーマ YAML を生成する。"""
    schema = {
        "version": "2.3",
        "nodes": {
            "Source": {
                "description": "test source",
                "properties": {
                    "source_id": {"type": "string", "unique": True},
                },
            },
            "Entity": {
                "description": "test entity",
                "properties": {
                    "entity_key": {"type": "string", "unique": True},
                    "entity_type": {
                        "type": "string",
                        "enum": ["company", "index"],
                    },
                },
            },
        },
        "relationships": {
            "MENTIONS": {
                "from": "Source",
                "to": "Entity",
            },
        },
        "namespaces": {
            "kg_v2": {
                "labels": ["Source", "Entity"],
            },
        },
    }
    schema_file = tmp_path / "knowledge-graph-schema.yaml"
    schema_file.write_text(yaml.dump(schema, allow_unicode=True), encoding="utf-8")
    return schema_file


# ---------------------------------------------------------------------------
# MetricValue
# ---------------------------------------------------------------------------


class TestMetricValue:
    def test_正常系_デフォルト値でインスタンス生成(self) -> None:
        mv = MetricValue(value=0.95, unit="%", status="green")
        assert mv.value == 0.95
        assert mv.unit == "%"
        assert mv.status == "green"
        assert mv.stub is False

    def test_正常系_stubフラグをTrueに設定(self) -> None:
        mv = MetricValue(value=0.0, unit="count", status="red", stub=True)
        assert mv.stub is True

    def test_正常系_statusはgreen_yellow_redのいずれか(self) -> None:
        for s in ("green", "yellow", "red"):
            mv = MetricValue(value=0.5, unit="%", status=s)
            assert mv.status == s


# ---------------------------------------------------------------------------
# CategoryResult
# ---------------------------------------------------------------------------


class TestCategoryResult:
    def test_正常系_カテゴリ結果を生成(self) -> None:
        metrics = [
            MetricValue(value=0.95, unit="%", status="green"),
            MetricValue(value=0.60, unit="%", status="yellow"),
        ]
        cr = CategoryResult(name="structural", score=77.5, metrics=metrics)
        assert cr.name == "structural"
        assert cr.score == 77.5
        assert len(cr.metrics) == 2

    def test_エッジケース_空メトリクスリスト(self) -> None:
        cr = CategoryResult(name="empty", score=0.0, metrics=[])
        assert cr.metrics == []


# ---------------------------------------------------------------------------
# CheckRuleResult
# ---------------------------------------------------------------------------


class TestCheckRuleResult:
    def test_正常系_チェックルール結果を生成(self) -> None:
        crr = CheckRuleResult(
            rule_name="PascalCase遵守",
            pass_rate=0.95,
            violations=["content_theme", "decision"],
        )
        assert crr.rule_name == "PascalCase遵守"
        assert crr.pass_rate == 0.95
        assert len(crr.violations) == 2

    def test_正常系_違反なし(self) -> None:
        crr = CheckRuleResult(
            rule_name="必須プロパティ存在",
            pass_rate=1.0,
            violations=[],
        )
        assert crr.violations == []


# ---------------------------------------------------------------------------
# QualitySnapshot
# ---------------------------------------------------------------------------


class TestQualitySnapshot:
    def test_正常系_スナップショット生成(self) -> None:
        cat = CategoryResult(
            name="structural",
            score=85.0,
            metrics=[MetricValue(value=0.85, unit="%", status="green")],
        )
        ts = datetime(2026, 3, 19, 12, 0, 0, tzinfo=timezone.utc)
        qs = QualitySnapshot(
            categories=[cat],
            overall_score=85.0,
            timestamp=ts,
        )
        assert qs.overall_score == 85.0
        assert len(qs.categories) == 1
        assert qs.timestamp == ts

    def test_エッジケース_空カテゴリリスト(self) -> None:
        ts = datetime(2026, 3, 19, 12, 0, 0, tzinfo=timezone.utc)
        qs = QualitySnapshot(categories=[], overall_score=0.0, timestamp=ts)
        assert qs.categories == []


# ---------------------------------------------------------------------------
# THRESHOLDS 定数
# ---------------------------------------------------------------------------


class TestThresholds:
    def test_正常系_THRESHOLDS定数が辞書として存在する(self) -> None:
        assert isinstance(THRESHOLDS, dict)
        assert len(THRESHOLDS) >= 13

    def test_正常系_各閾値にgreen_yellow_redキーが含まれる(self) -> None:
        for name, threshold in THRESHOLDS.items():
            assert "green" in threshold, f"{name} missing 'green'"
            assert "yellow" in threshold, f"{name} missing 'yellow'"


# ---------------------------------------------------------------------------
# ALLOWED_ENTITY_TYPES 定数
# ---------------------------------------------------------------------------


class TestAllowedEntityTypes:
    def test_正常系_ALLOWED_ENTITY_TYPESがセットまたはリスト(self) -> None:
        assert isinstance(ALLOWED_ENTITY_TYPES, (set, list, tuple, frozenset))

    def test_正常系_基本的なentity_typeが含まれる(self) -> None:
        expected = {"company", "index", "sector", "indicator", "currency"}
        for et in expected:
            assert et in ALLOWED_ENTITY_TYPES, f"'{et}' not in ALLOWED_ENTITY_TYPES"


# ---------------------------------------------------------------------------
# create_driver
# ---------------------------------------------------------------------------


class TestCreateDriver:
    @patch("kg_quality_metrics.GraphDatabase")
    def test_正常系_デフォルトURIで接続(self, mock_gdb: MagicMock) -> None:
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver

        driver = create_driver()

        mock_gdb.driver.assert_called_once_with(
            "bolt://localhost:7688",
            auth=("neo4j", "gomasuke"),
        )
        mock_driver.verify_connectivity.assert_called_once()
        assert driver is mock_driver

    @patch("kg_quality_metrics.GraphDatabase")
    def test_正常系_カスタムURIとパスワードで接続(self, mock_gdb: MagicMock) -> None:
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver

        driver = create_driver(
            uri="bolt://custom:7689",
            user="admin",
            password="secret",
        )

        mock_gdb.driver.assert_called_once_with(
            "bolt://custom:7689",
            auth=("admin", "secret"),
        )
        assert driver is mock_driver

    @patch.dict("os.environ", {"NEO4J_PASSWORD": "env_pass"})
    @patch("kg_quality_metrics.GraphDatabase")
    def test_正常系_環境変数からパスワード取得(self, mock_gdb: MagicMock) -> None:
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver

        create_driver()

        mock_gdb.driver.assert_called_once_with(
            "bolt://localhost:7688",
            auth=("neo4j", "env_pass"),
        )


# ---------------------------------------------------------------------------
# load_schema
# ---------------------------------------------------------------------------


class TestLoadSchema:
    def test_正常系_スキーマYAMLを読み込む(self, sample_schema_file: Path) -> None:
        schema = load_schema(sample_schema_file)
        assert "nodes" in schema
        assert "Source" in schema["nodes"]

    def test_異常系_存在しないファイルでエラー(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_schema(tmp_path / "nonexistent.yaml")


# ---------------------------------------------------------------------------
# get_counts
# ---------------------------------------------------------------------------


class TestGetCounts:
    def test_正常系_ノード数とリレーション数を取得(self) -> None:
        mock_session = MagicMock()

        # ノード数クエリの結果
        mock_node_result = MagicMock()
        mock_node_result.single.return_value = {"count": 3425}

        # リレーション数クエリの結果
        mock_rel_result = MagicMock()
        mock_rel_result.single.return_value = {"count": 6441}

        mock_session.run.side_effect = [mock_node_result, mock_rel_result]

        counts = get_counts(mock_session)

        assert counts["node_count"] == 3425
        assert counts["relationship_count"] == 6441

    def test_正常系_Memory除外フィルタが含まれる(self) -> None:
        mock_session = MagicMock()

        mock_node_result = MagicMock()
        mock_node_result.single.return_value = {"count": 100}
        mock_rel_result = MagicMock()
        mock_rel_result.single.return_value = {"count": 200}
        mock_session.run.side_effect = [mock_node_result, mock_rel_result]

        get_counts(mock_session)

        # 少なくとも1回のrun呼び出しに Memory フィルタが含まれる
        calls = mock_session.run.call_args_list
        node_query = calls[0][0][0]
        assert "Memory" in node_query
        assert "NOT" in node_query


# ---------------------------------------------------------------------------
# parse_args (CLI)
# ---------------------------------------------------------------------------


class TestParseArgs:
    def test_正常系_デフォルト引数(self) -> None:
        args = parse_args([])
        assert args.category == "all"
        assert args.dry_run is False
        assert args.save_snapshot is False
        assert args.report is None
        assert args.compare is None

    def test_正常系_category指定(self) -> None:
        args = parse_args(["--category", "structural"])
        assert args.category == "structural"

    def test_正常系_全カテゴリ選択肢が有効(self) -> None:
        valid_categories = [
            "structural",
            "completeness",
            "consistency",
            "accuracy",
            "timeliness",
            "finance_specific",
            "discoverability",
            "all",
        ]
        for cat in valid_categories:
            args = parse_args(["--category", cat])
            assert args.category == cat

    def test_異常系_無効なカテゴリでエラー(self) -> None:
        with pytest.raises(SystemExit):
            parse_args(["--category", "invalid"])

    def test_正常系_save_snapshotフラグ(self) -> None:
        args = parse_args(["--save-snapshot"])
        assert args.save_snapshot is True

    def test_正常系_reportオプション(self) -> None:
        args = parse_args(["--report", "output.md"])
        assert args.report == "output.md"

    def test_正常系_compareオプション(self) -> None:
        args = parse_args(["--compare", "snapshot_a.json"])
        assert args.compare == "snapshot_a.json"

    def test_正常系_neo4j接続オプション(self) -> None:
        args = parse_args(
            [
                "--neo4j-uri",
                "bolt://remote:7688",
                "--neo4j-user",
                "admin",
                "--neo4j-password",
                "secret",
            ]
        )
        assert args.neo4j_uri == "bolt://remote:7688"
        assert args.neo4j_user == "admin"
        assert args.neo4j_password == "secret"

    def test_正常系_dry_runフラグ(self) -> None:
        args = parse_args(["--dry-run"])
        assert args.dry_run is True
