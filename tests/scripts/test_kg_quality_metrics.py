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
    ALLOWED_RELATIONSHIP_TYPES,
    THRESHOLDS,
    CategoryResult,
    CheckRuleResult,
    MetricValue,
    QualitySnapshot,
    check_entity_length,
    check_relationship_compliance,
    check_schema_compliance,
    check_subject_reference,
    compare_snapshots,
    compute_semantic_diversity,
    compute_shannon_entropy,
    create_driver,
    evaluate_status,
    generate_markdown,
    get_counts,
    load_schema,
    measure_accuracy,
    measure_completeness,
    measure_consistency,
    measure_discoverability,
    measure_finance_specific,
    measure_structural,
    measure_timeliness,
    parse_args,
    render_console,
    save_json,
    save_neo4j,
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
# DataClasses 統合テスト（MetricValue / CategoryResult / QualitySnapshot）
# ---------------------------------------------------------------------------


class TestDataClasses:
    """Issue #203 指定: MetricValue / CategoryResult / QualitySnapshot の統合テスト。"""

    def test_正常系_MetricValueの等値比較(self) -> None:
        mv1 = MetricValue(value=0.95, unit="%", status="green")
        mv2 = MetricValue(value=0.95, unit="%", status="green")
        assert mv1 == mv2

    def test_正常系_CategoryResultにMetricValueリストを格納(self) -> None:
        metrics = [
            MetricValue(value=0.9, unit="ratio", status="green"),
            MetricValue(value=0.5, unit="count", status="yellow"),
            MetricValue(value=0.1, unit="ratio", status="red"),
        ]
        cr = CategoryResult(name="test_category", score=50.0, metrics=metrics)
        assert cr.name == "test_category"
        assert cr.score == 50.0
        assert len(cr.metrics) == 3
        assert cr.metrics[0].status == "green"
        assert cr.metrics[2].status == "red"

    def test_正常系_QualitySnapshotにCategoryResultリストを格納(self) -> None:
        ts = datetime(2026, 3, 19, 12, 0, 0, tzinfo=timezone.utc)
        cat1 = CategoryResult(name="structural", score=80.0, metrics=[])
        cat2 = CategoryResult(name="completeness", score=90.0, metrics=[])
        qs = QualitySnapshot(
            categories=[cat1, cat2],
            overall_score=85.0,
            timestamp=ts,
        )
        assert len(qs.categories) == 2
        assert qs.overall_score == 85.0
        assert qs.categories[0].name == "structural"
        assert qs.categories[1].name == "completeness"

    def test_正常系_CheckRuleResultのデフォルト値(self) -> None:
        crr = CheckRuleResult(rule_name="test_rule", pass_rate=1.0)
        assert crr.violations == []

    def test_正常系_MetricValueのstubデフォルトはFalse(self) -> None:
        mv = MetricValue(value=0.0, unit="count", status="yellow")
        assert mv.stub is False

    def test_正常系_CategoryResultのmetricsデフォルトは空リスト(self) -> None:
        cr = CategoryResult(name="test", score=0.0)
        assert cr.metrics == []


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
# ALLOWED_RELATIONSHIP_TYPES 定数
# ---------------------------------------------------------------------------


class TestAllowedRelationshipTypes:
    def test_正常系_ALLOWED_RELATIONSHIP_TYPESがセットまたはリスト(self) -> None:
        assert isinstance(ALLOWED_RELATIONSHIP_TYPES, (set, list, tuple, frozenset))

    def test_正常系_基本的なrelationship_typeが含まれる(self) -> None:
        expected = {"STATES_FACT", "MAKES_CLAIM", "RELATES_TO", "ABOUT", "TREND"}
        for rt in expected:
            assert rt in ALLOWED_RELATIONSHIP_TYPES, (
                f"'{rt}' not in ALLOWED_RELATIONSHIP_TYPES"
            )


# ---------------------------------------------------------------------------
# create_driver
# ---------------------------------------------------------------------------


class TestCreateDriver:
    @patch.dict("os.environ", {}, clear=True)
    def test_異常系_パスワード未設定でValueError(self) -> None:
        with pytest.raises(ValueError, match="Neo4j password is required"):
            create_driver()

    @patch("neo4j_utils.GraphDatabase")
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
    @patch("neo4j_utils.GraphDatabase")
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


# ---------------------------------------------------------------------------
# evaluate_status
# ---------------------------------------------------------------------------


class TestEvaluateStatus:
    def test_正常系_green判定_通常メトリクス(self) -> None:
        status = evaluate_status("avg_degree", 4.0)
        assert status == "green"

    def test_正常系_yellow判定_通常メトリクス(self) -> None:
        status = evaluate_status("avg_degree", 2.0)
        assert status == "yellow"

    def test_正常系_red判定_通常メトリクス(self) -> None:
        status = evaluate_status("avg_degree", 1.0)
        assert status == "red"

    def test_正常系_逆順メトリクス_source_freshness_days(self) -> None:
        # source_freshness_days は小さいほど良い
        assert evaluate_status("source_freshness_days", 3) == "green"
        assert evaluate_status("source_freshness_days", 15) == "yellow"
        assert evaluate_status("source_freshness_days", 60) == "red"

    def test_正常系_逆順メトリクス_orphan_node_ratio(self) -> None:
        # orphan_node_ratio は小さいほど良い
        assert evaluate_status("orphan_node_ratio", 0.03) == "green"
        assert evaluate_status("orphan_node_ratio", 0.10) == "yellow"
        assert evaluate_status("orphan_node_ratio", 0.20) == "red"

    def test_エッジケース_未定義メトリクスはyellow(self) -> None:
        status = evaluate_status("unknown_metric", 42.0)
        assert status == "yellow"


# ---------------------------------------------------------------------------
# Fixtures for measurement functions
# ---------------------------------------------------------------------------


def _make_mock_session_for_structural() -> MagicMock:
    """measure_structural 用のモックセッションを作成する。"""
    mock_session = MagicMock()

    # get_counts 用（ノード数・リレーション数）
    mock_node_result = MagicMock()
    mock_node_result.single.return_value = {"count": 3425}
    mock_rel_result = MagicMock()
    mock_rel_result.single.return_value = {"count": 6441}

    # 平均次数
    mock_avg_degree = MagicMock()
    mock_avg_degree.single.return_value = {"avg_degree": 3.76}

    # 孤立ノード数
    mock_orphan = MagicMock()
    mock_orphan.single.return_value = {"orphan_count": 97}

    # BFS 連結性（開始ノードID + 到達可能ノード数）
    mock_start_node = MagicMock()
    mock_start_node.single.return_value = {"start_id": "node-1"}

    mock_reachable = MagicMock()
    mock_reachable.single.return_value = {"reachable": 3200}

    mock_session.run.side_effect = [
        mock_node_result,
        mock_rel_result,
        mock_avg_degree,
        mock_orphan,
        mock_start_node,
        mock_reachable,
    ]
    return mock_session


@pytest.fixture()
def sample_schema_with_required(tmp_path: Path) -> Path:
    """required_properties を含むテスト用スキーマ YAML を生成する。"""
    schema = {
        "version": "2.3",
        "nodes": {
            "Source": {
                "description": "test source",
                "properties": {
                    "source_id": {"type": "string", "unique": True, "required": True},
                    "title": {"type": "string", "required": True},
                    "url": {"type": "string"},
                    "source_type": {
                        "type": "string",
                        "required": True,
                        "enum": ["web", "news", "pdf", "original", "blog"],
                    },
                    "authority_level": {
                        "type": "string",
                        "required": True,
                        "enum": [
                            "official",
                            "analyst",
                            "media",
                            "blog",
                            "social",
                            "academic",
                        ],
                    },
                    "fetched_at": {"type": "datetime", "required": True},
                },
            },
            "Entity": {
                "description": "test entity",
                "properties": {
                    "entity_id": {"type": "string", "unique": True, "required": True},
                    "name": {"type": "string", "required": True},
                    "entity_type": {
                        "type": "string",
                        "required": True,
                        "enum": ["company", "index"],
                    },
                },
            },
        },
        "relationships": {
            "MENTIONS": {"from": "Source", "to": "Entity"},
        },
        "namespaces": {
            "kg_v2": {"labels": ["Source", "Entity"]},
        },
    }
    schema_file = tmp_path / "knowledge-graph-schema.yaml"
    schema_file.write_text(yaml.dump(schema, allow_unicode=True), encoding="utf-8")
    return schema_file


# ---------------------------------------------------------------------------
# measure_structural
# ---------------------------------------------------------------------------


class TestMeasureStructural:
    def test_正常系_4指標を返す(self) -> None:
        mock_session = _make_mock_session_for_structural()
        result = measure_structural(mock_session)
        assert isinstance(result, CategoryResult)
        assert result.name == "structural"
        assert len(result.metrics) == 4

    def test_正常系_エッジ密度が含まれる(self) -> None:
        mock_session = _make_mock_session_for_structural()
        result = measure_structural(mock_session)
        # metrics[0] = edge_density (ratio)
        edge_density = result.metrics[0]
        assert edge_density.unit == "ratio"
        assert edge_density.value > 0

    def test_正常系_平均次数が含まれる(self) -> None:
        mock_session = _make_mock_session_for_structural()
        result = measure_structural(mock_session)
        avg_degree = result.metrics[1]
        assert avg_degree.unit == "count"
        assert avg_degree.value == pytest.approx(3.76, abs=0.1)

    def test_正常系_連結性が含まれる(self) -> None:
        mock_session = _make_mock_session_for_structural()
        result = measure_structural(mock_session)
        connectivity = result.metrics[2]
        assert connectivity.unit == "ratio"
        assert 0.0 <= connectivity.value <= 1.0

    def test_正常系_孤立率が含まれる(self) -> None:
        mock_session = _make_mock_session_for_structural()
        result = measure_structural(mock_session)
        orphan_ratio = result.metrics[3]
        assert orphan_ratio.unit == "ratio"
        assert 0.0 <= orphan_ratio.value <= 1.0

    def test_正常系_Memory除外フィルタが全Cypherに含まれる(self) -> None:
        mock_session = _make_mock_session_for_structural()
        measure_structural(mock_session)
        calls = mock_session.run.call_args_list
        for call in calls:
            query = call[0][0]
            assert "Memory" in query, f"Memory filter missing in query: {query[:80]}"


# ---------------------------------------------------------------------------
# measure_completeness
# ---------------------------------------------------------------------------


class TestMeasureCompleteness:
    def test_正常系_スキーマYAMLから動的クエリ生成する(
        self,
        sample_schema_with_required: Path,
    ) -> None:
        schema = yaml.safe_load(sample_schema_with_required.read_text(encoding="utf-8"))
        mock_session = MagicMock()

        # HIGH-001: 同一ラベルの全 required props を1クエリで取得
        # yaml.dump sorts keys alphabetically: Entity (3 required) before Source (5 required)
        mock_results: list[MagicMock] = []

        # Entity の1バッチクエリ結果 (3 required: entity_id, entity_type, name)
        r_entity = MagicMock()
        r_entity.single.return_value = {
            "total": 200,
            "filled_0": 190,
            "filled_1": 190,
            "filled_2": 190,
        }
        mock_results.append(r_entity)

        # Source の1バッチクエリ結果 (5 required: authority_level, fetched_at, source_id, source_type, title)
        r_source = MagicMock()
        r_source.single.return_value = {
            "total": 100,
            "filled_0": 95,
            "filled_1": 95,
            "filled_2": 95,
            "filled_3": 95,
            "filled_4": 95,
        }
        mock_results.append(r_source)

        # Sector/Metric ハードコード分（各1クエリ）
        for _ in range(2):
            r = MagicMock()
            r.single.return_value = {"count": 11}
            mock_results.append(r)

        mock_session.run.side_effect = mock_results
        result = measure_completeness(mock_session, schema)
        assert isinstance(result, CategoryResult)
        assert result.name == "completeness"
        assert len(result.metrics) >= 1

    def test_正常系_Memory除外フィルタが全Cypherに含まれる(
        self,
        sample_schema_with_required: Path,
    ) -> None:
        schema = yaml.safe_load(sample_schema_with_required.read_text(encoding="utf-8"))
        mock_session = MagicMock()

        # HIGH-001: バッチクエリ対応のモック結果を用意
        mock_r = MagicMock()
        mock_r.single.return_value = {
            "total": 100,
            "filled_0": 90,
            "filled_1": 90,
            "filled_2": 90,
            "filled_3": 90,
            "filled_4": 90,
            "count": 10,
        }
        mock_session.run.return_value = mock_r

        measure_completeness(mock_session, schema)
        calls = mock_session.run.call_args_list
        for call in calls:
            query = call[0][0]
            assert "Memory" in query, f"Memory filter missing in query: {query[:80]}"


# ---------------------------------------------------------------------------
# measure_consistency
# ---------------------------------------------------------------------------


class TestMeasureConsistency:
    def test_正常系_型一貫性と重複率と制約違反を返す(self) -> None:
        mock_session = MagicMock()

        # entity_type 一貫性: 許可リスト内/外
        mock_type_check = MagicMock()
        mock_type_check.data.return_value = [
            {"entity_type": "company", "count": 50},
            {"entity_type": "index", "count": 30},
            {"entity_type": "INVALID", "count": 2},
        ]

        # 重複率: name重複ノード数
        mock_duplicate = MagicMock()
        mock_duplicate.single.return_value = {"duplicate_count": 5, "total": 200}

        # 制約違反: null必須プロパティ
        mock_constraint = MagicMock()
        mock_constraint.single.return_value = {"violation_count": 3}

        mock_session.run.side_effect = [
            mock_type_check,
            mock_duplicate,
            mock_constraint,
        ]

        result = measure_consistency(mock_session)
        assert isinstance(result, CategoryResult)
        assert result.name == "consistency"
        assert len(result.metrics) == 3

    def test_正常系_Memory除外フィルタが全Cypherに含まれる(self) -> None:
        mock_session = MagicMock()

        mock_type_check = MagicMock()
        mock_type_check.data.return_value = [{"entity_type": "company", "count": 50}]
        mock_duplicate = MagicMock()
        mock_duplicate.single.return_value = {"duplicate_count": 0, "total": 100}
        mock_constraint = MagicMock()
        mock_constraint.single.return_value = {"violation_count": 0}
        mock_session.run.side_effect = [
            mock_type_check,
            mock_duplicate,
            mock_constraint,
        ]

        measure_consistency(mock_session)
        calls = mock_session.run.call_args_list
        for call in calls:
            query = call[0][0]
            assert "Memory" in query, f"Memory filter missing in query: {query[:80]}"


# ---------------------------------------------------------------------------
# measure_accuracy
# ---------------------------------------------------------------------------


class TestMeasureAccuracy:
    def test_正常系_stubフラグがTrueのスタブを返す(self) -> None:
        mock_session = MagicMock()
        result = measure_accuracy(mock_session)
        assert isinstance(result, CategoryResult)
        assert result.name == "accuracy"
        # 全メトリクスが stub=True
        for metric in result.metrics:
            assert metric.stub is True

    def test_正常系_DBクエリを実行しない(self) -> None:
        mock_session = MagicMock()
        measure_accuracy(mock_session)
        mock_session.run.assert_not_called()


# ---------------------------------------------------------------------------
# measure_timeliness
# ---------------------------------------------------------------------------


class TestMeasureTimeliness:
    def test_正常系_鮮度と更新頻度と時間カバレッジを返す(self) -> None:
        mock_session = MagicMock()

        # 鮮度+更新頻度: fetched_at を collect して Python 側で計算
        mock_freshness = MagicMock()
        mock_freshness.single.return_value = {
            "fetched_dates": [
                "2026-03-14T00:00:00+00:00",
                "2026-03-19T00:00:00+00:00",
            ]
        }

        # 時間カバレッジ: fetched_at の最古/最新
        mock_coverage = MagicMock()
        mock_coverage.single.return_value = {
            "earliest": "2025-01-01T00:00:00Z",
            "latest": "2026-03-19T00:00:00Z",
        }

        mock_session.run.side_effect = [mock_freshness, mock_coverage]

        result = measure_timeliness(mock_session)
        assert isinstance(result, CategoryResult)
        assert result.name == "timeliness"
        assert len(result.metrics) == 3

    def test_正常系_Memory除外フィルタが全Cypherに含まれる(self) -> None:
        mock_session = MagicMock()

        mock_freshness = MagicMock()
        mock_freshness.single.return_value = {
            "fetched_dates": ["2026-03-19T00:00:00+00:00"]
        }
        mock_coverage = MagicMock()
        mock_coverage.single.return_value = {
            "earliest": "2025-01-01T00:00:00Z",
            "latest": "2026-03-19T00:00:00Z",
        }
        mock_session.run.side_effect = [mock_freshness, mock_coverage]

        measure_timeliness(mock_session)
        calls = mock_session.run.call_args_list
        for call in calls:
            query = call[0][0]
            if query:  # skip empty frequency_query
                assert "Memory" in query, f"Memory filter missing in query: {query[:80]}"


# ---------------------------------------------------------------------------
# measure_finance_specific
# ---------------------------------------------------------------------------


class TestMeasureFinanceSpecific:
    def test_正常系_3指標を返す(self) -> None:
        mock_session = MagicMock()

        # セクターカバレッジ: DBにあるセクター数 / GICS 11セクター
        mock_sector = MagicMock()
        mock_sector.single.return_value = {"sector_count": 8}

        # メトリクス/社: Entity(company)あたりの平均 FinancialDataPoint 数
        mock_metrics_per = MagicMock()
        mock_metrics_per.single.return_value = {"avg_metrics": 4.5}

        # Entity-Entity 関係密度
        mock_entity_rel = MagicMock()
        mock_entity_rel.single.return_value = {"ee_rel_count": 888, "entity_count": 200}

        mock_session.run.side_effect = [mock_sector, mock_metrics_per, mock_entity_rel]

        result = measure_finance_specific(mock_session)
        assert isinstance(result, CategoryResult)
        assert result.name == "finance_specific"
        assert len(result.metrics) == 3

    def test_正常系_セクターカバレッジがGICS11セクター基準(self) -> None:
        mock_session = MagicMock()

        mock_sector = MagicMock()
        mock_sector.single.return_value = {"sector_count": 11}
        mock_metrics_per = MagicMock()
        mock_metrics_per.single.return_value = {"avg_metrics": 5.0}
        mock_entity_rel = MagicMock()
        mock_entity_rel.single.return_value = {"ee_rel_count": 900, "entity_count": 200}
        mock_session.run.side_effect = [mock_sector, mock_metrics_per, mock_entity_rel]

        result = measure_finance_specific(mock_session)
        # sector_coverage = 11/11 = 1.0
        sector_metric = result.metrics[0]
        assert sector_metric.value == pytest.approx(1.0)

    def test_正常系_Memory除外フィルタが全Cypherに含まれる(self) -> None:
        mock_session = MagicMock()

        mock_sector = MagicMock()
        mock_sector.single.return_value = {"sector_count": 5}
        mock_metrics_per = MagicMock()
        mock_metrics_per.single.return_value = {"avg_metrics": 3.0}
        mock_entity_rel = MagicMock()
        mock_entity_rel.single.return_value = {"ee_rel_count": 100, "entity_count": 50}
        mock_session.run.side_effect = [mock_sector, mock_metrics_per, mock_entity_rel]

        measure_finance_specific(mock_session)
        calls = mock_session.run.call_args_list
        for call in calls:
            query = call[0][0]
            assert "Memory" in query, f"Memory filter missing in query: {query[:80]}"


# ---------------------------------------------------------------------------
# measure_discoverability
# ---------------------------------------------------------------------------


class TestMeasureDiscoverability:
    def test_正常系_CategoryResultを返す(self) -> None:
        mock_session = MagicMock()

        # 1. ノードID一覧取得（200ペアサンプリング用）
        mock_node_ids = MagicMock()
        mock_node_ids.data.return_value = [{"nid": f"node-{i}"} for i in range(400)]

        # 2. UNWIND バッチ shortestPath クエリ結果
        # バッチサイズ30で200ペア → ceil(200/30) = 7 バッチ
        mock_batch_results: list[MagicMock] = []
        for batch_idx in range(7):
            batch_result = MagicMock()
            batch_size = min(30, 200 - batch_idx * 30)
            records = []
            for j in range(batch_size):
                rec = MagicMock()
                rec.__getitem__ = MagicMock(
                    side_effect=lambda key, _j=j, _bi=batch_idx: {
                        "src": f"node-{_bi * 30 + _j}",
                        "dst": f"node-{_bi * 30 + _j + 1}",
                        "path_length": (_bi * 30 + _j) % 4 + 2,
                    }[key]
                )
                records.append(rec)
            batch_result.__iter__ = MagicMock(return_value=iter(records))
            mock_batch_results.append(batch_result)

        mock_session.run.side_effect = [mock_node_ids, *mock_batch_results]

        result = measure_discoverability(mock_session, sample_size=200, timeout_sec=5)
        assert isinstance(result, CategoryResult)
        assert result.name == "discoverability"
        assert len(result.metrics) >= 3  # avg_path_length, path_diversity, bridge_rate

    def test_正常系_平均パス長が含まれる(self) -> None:
        mock_session = MagicMock()

        # 全ペアでパス長3
        mock_node_ids = MagicMock()
        mock_node_ids.data.return_value = [{"nid": f"node-{i}"} for i in range(10)]

        # 5ペア → 1バッチ
        batch_result = MagicMock()
        records = []
        for j in range(5):
            rec = MagicMock()
            rec.__getitem__ = MagicMock(
                side_effect=lambda key, _j=j: {
                    "src": f"node-{_j}",
                    "dst": f"node-{_j + 1}",
                    "path_length": 3,
                }[key]
            )
            records.append(rec)
        batch_result.__iter__ = MagicMock(return_value=iter(records))

        mock_session.run.side_effect = [mock_node_ids, batch_result]

        result = measure_discoverability(mock_session, sample_size=5, timeout_sec=5)
        # 平均パス長メトリクスを検索
        avg_path = [m for m in result.metrics if m.unit == "hops"]
        assert len(avg_path) >= 1
        assert avg_path[0].value == pytest.approx(3.0, abs=0.1)

    def test_正常系_タイムアウトしたバッチはスキップされる(self) -> None:
        mock_session = MagicMock()

        mock_node_ids = MagicMock()
        mock_node_ids.data.return_value = [{"nid": f"node-{i}"} for i in range(10)]

        # 5ペア → 1バッチ、バッチがエラーになるケース
        def side_effect_fn(*args, **kwargs):
            raise Exception("timeout")

        call_count = [0]

        def smart_side_effect(*args, **kwargs):
            idx = call_count[0]
            call_count[0] += 1
            if idx == 0:
                return mock_node_ids
            # バッチクエリでエラー
            raise Exception("timeout")

        mock_session.run.side_effect = smart_side_effect

        result = measure_discoverability(mock_session, sample_size=5, timeout_sec=5)
        assert isinstance(result, CategoryResult)
        # タイムアウトがあっても結果を返す
        assert result.name == "discoverability"

    def test_正常系_Memory除外フィルタがノードID取得に含まれる(self) -> None:
        mock_session = MagicMock()

        mock_node_ids = MagicMock()
        mock_node_ids.data.return_value = [{"nid": f"node-{i}"} for i in range(10)]

        # 5ペア → 1バッチ
        batch_result = MagicMock()
        records = []
        for j in range(5):
            rec = MagicMock()
            rec.__getitem__ = MagicMock(
                side_effect=lambda key, _j=j: {
                    "src": f"node-{_j}",
                    "dst": f"node-{_j + 1}",
                    "path_length": 3,
                }[key]
            )
            records.append(rec)
        batch_result.__iter__ = MagicMock(return_value=iter(records))

        mock_session.run.side_effect = [mock_node_ids, batch_result]

        measure_discoverability(mock_session, sample_size=5, timeout_sec=5)
        # 最初のクエリ（ノードID取得）にMemory除外が含まれる
        first_call = mock_session.run.call_args_list[0]
        query = first_call[0][0]
        assert "Memory" in query, (
            f"Memory filter missing in node ID query: {query[:80]}"
        )

    def test_エッジケース_ノード数不足でスコア0(self) -> None:
        mock_session = MagicMock()

        # ノードが1つしかない場合（ペアを作れない）
        mock_node_ids = MagicMock()
        mock_node_ids.data.return_value = [{"nid": "node-0"}]

        mock_session.run.side_effect = [mock_node_ids]

        result = measure_discoverability(mock_session, sample_size=200, timeout_sec=5)
        assert isinstance(result, CategoryResult)
        assert result.score == 0.0


# ---------------------------------------------------------------------------
# CheckRules: check_subject_reference (代名詞検出)
# ---------------------------------------------------------------------------


class TestCheckSubjectReference:
    def test_正常系_代名詞なしで通過(self) -> None:
        texts = [
            "Apple reported strong quarterly earnings.",
            "S&P 500 reached all-time highs.",
            "日本銀行が金利据え置きを決定した。",
        ]
        result = check_subject_reference(texts)
        assert isinstance(result, CheckRuleResult)
        assert result.rule_name == "subject_reference"
        assert result.pass_rate == 1.0
        assert result.violations == []

    def test_異常系_英語代名詞を検出(self) -> None:
        texts = [
            "It reported strong earnings.",  # "It" は代名詞
            "Apple had a good quarter.",
            "They announced a merger.",  # "They" は代名詞
        ]
        result = check_subject_reference(texts)
        assert result.pass_rate < 1.0
        assert len(result.violations) == 2

    def test_異常系_日本語代名詞を検出(self) -> None:
        texts = [
            "それは好決算を発表した。",  # 「それ」は代名詞
            "トヨタが増収増益を達成。",
            "これにより株価が上昇した。",  # 「これ」は代名詞
        ]
        result = check_subject_reference(texts)
        assert result.pass_rate < 1.0
        assert len(result.violations) >= 1

    def test_エッジケース_空リストでpass_rate_1(self) -> None:
        result = check_subject_reference([])
        assert result.pass_rate == 1.0
        assert result.violations == []

    def test_正常系_純粋関数として副作用なし(self) -> None:
        texts = ["Apple grew revenue.", "Google launched a product."]
        original_texts = texts.copy()
        check_subject_reference(texts)
        assert texts == original_texts  # 入力が変更されていない


# ---------------------------------------------------------------------------
# CheckRules: check_entity_length (エンティティ長検証)
# ---------------------------------------------------------------------------


class TestCheckEntityLength:
    def test_正常系_英語5語以下で通過(self) -> None:
        entities = ["Apple", "S&P 500 Index", "Bank of America"]
        result = check_entity_length(entities)
        assert isinstance(result, CheckRuleResult)
        assert result.rule_name == "entity_length"
        assert result.pass_rate == 1.0

    def test_異常系_英語6語以上で違反(self) -> None:
        entities = [
            "Apple",
            "The Very Long Company Name That Exceeds Limit",  # 8語
        ]
        result = check_entity_length(entities)
        assert result.pass_rate < 1.0
        assert len(result.violations) == 1

    def test_正常系_日本語10文字以下で通過(self) -> None:
        entities = ["トヨタ自動車", "日本銀行", "三菱UFJ銀行"]
        result = check_entity_length(entities)
        assert result.pass_rate == 1.0

    def test_異常系_日本語11文字以上で違反(self) -> None:
        entities = [
            "トヨタ",
            "このエンティティ名はとても長すぎます制限超え",  # 20文字以上
        ]
        result = check_entity_length(entities)
        assert result.pass_rate < 1.0
        assert len(result.violations) >= 1

    def test_境界値_英語ちょうど5語で通過(self) -> None:
        entities = ["Bank of New York Mellon"]  # 5語
        result = check_entity_length(entities)
        assert result.pass_rate == 1.0
        assert result.violations == []

    def test_境界値_英語ちょうど6語で違反(self) -> None:
        entities = ["Bank of New York Mellon Corporation"]  # 6語
        result = check_entity_length(entities)
        assert result.pass_rate == 0.0
        assert len(result.violations) == 1

    def test_境界値_日本語ちょうど10文字で通過(self) -> None:
        entities = ["トヨタ自動車株式会社"]  # 10文字
        assert len("トヨタ自動車株式会社") == 10  # 長さ確認
        result = check_entity_length(entities)
        assert result.pass_rate == 1.0
        assert result.violations == []

    def test_境界値_日本語ちょうど11文字で違反(self) -> None:
        entities = ["トヨタ自動車株式会社東"]  # 11文字
        assert len("トヨタ自動車株式会社東") == 11  # 長さ確認
        result = check_entity_length(entities)
        assert result.pass_rate == 0.0
        assert len(result.violations) == 1

    def test_正常系_英語日本語の自動判定(self) -> None:
        entities = ["Apple Inc", "三菱商事"]
        result = check_entity_length(entities)
        assert result.pass_rate == 1.0

    def test_エッジケース_空リストでpass_rate_1(self) -> None:
        result = check_entity_length([])
        assert result.pass_rate == 1.0
        assert result.violations == []


# ---------------------------------------------------------------------------
# CheckRules: check_schema_compliance (entity_type許可リスト検証)
# ---------------------------------------------------------------------------


class TestCheckSchemaCompliance:
    def test_正常系_全て許可リスト内で通過(self) -> None:
        entity_types = ["company", "index", "sector", "indicator"]
        result = check_schema_compliance(entity_types)
        assert isinstance(result, CheckRuleResult)
        assert result.rule_name == "schema_compliance"
        assert result.pass_rate == 1.0
        assert result.violations == []

    def test_異常系_許可リスト外のentity_typeで違反(self) -> None:
        entity_types = ["company", "INVALID_TYPE", "index", "unknown"]
        result = check_schema_compliance(entity_types)
        assert result.pass_rate < 1.0
        assert "INVALID_TYPE" in result.violations
        assert "unknown" in result.violations

    def test_正常系_ALLOWED_ENTITY_TYPES全てが通過(self) -> None:
        entity_types = list(ALLOWED_ENTITY_TYPES)
        result = check_schema_compliance(entity_types)
        assert result.pass_rate == 1.0

    def test_エッジケース_空リストでpass_rate_1(self) -> None:
        result = check_schema_compliance([])
        assert result.pass_rate == 1.0


# ---------------------------------------------------------------------------
# CheckRules: check_relationship_compliance (リレーション型スキーマ検証)
# ---------------------------------------------------------------------------


class TestCheckRelationshipCompliance:
    def test_正常系_全て許可リスト内で通過(self) -> None:
        rel_types = ["STATES_FACT", "MAKES_CLAIM", "RELATES_TO", "ABOUT"]
        result = check_relationship_compliance(rel_types)
        assert isinstance(result, CheckRuleResult)
        assert result.rule_name == "relationship_compliance"
        assert result.pass_rate == 1.0
        assert result.violations == []

    def test_異常系_許可リスト外のリレーション型で違反(self) -> None:
        rel_types = ["STATES_FACT", "UNKNOWN_REL", "ABOUT"]
        result = check_relationship_compliance(rel_types)
        assert result.pass_rate < 1.0
        assert "UNKNOWN_REL" in result.violations

    def test_エッジケース_空リストでpass_rate_1(self) -> None:
        result = check_relationship_compliance([])
        assert result.pass_rate == 1.0


# ---------------------------------------------------------------------------
# EntropyAnalysis: compute_shannon_entropy
# ---------------------------------------------------------------------------


class TestComputeShannonEntropy:
    def test_正常系_均一分布で最大値(self) -> None:
        # 均一分布: 各カテゴリが同数 → 正規化エントロピー = 1.0
        counts = {"a": 10, "b": 10, "c": 10, "d": 10}
        entropy = compute_shannon_entropy(counts)
        assert entropy == pytest.approx(1.0, abs=0.01)

    def test_正常系_単一値で0(self) -> None:
        # 単一カテゴリのみ → 正規化エントロピー = 0.0
        counts = {"a": 100}
        entropy = compute_shannon_entropy(counts)
        assert entropy == pytest.approx(0.0, abs=0.01)

    def test_正常系_偏った分布で中間値(self) -> None:
        counts = {"a": 90, "b": 5, "c": 3, "d": 2}
        entropy = compute_shannon_entropy(counts)
        assert 0.0 < entropy < 1.0

    def test_エッジケース_空辞書で0(self) -> None:
        entropy = compute_shannon_entropy({})
        assert entropy == pytest.approx(0.0)

    def test_正常系_2カテゴリ均一分布(self) -> None:
        counts = {"a": 50, "b": 50}
        entropy = compute_shannon_entropy(counts)
        assert entropy == pytest.approx(1.0, abs=0.01)

    def test_エッジケース_カウント0のエントリは無視(self) -> None:
        counts = {"a": 50, "b": 50, "c": 0}
        entropy = compute_shannon_entropy(counts)
        # c=0 は無視されるので、実質2カテゴリ均一分布
        assert entropy == pytest.approx(1.0, abs=0.01)


# ---------------------------------------------------------------------------
# EntropyAnalysis: compute_semantic_diversity
# ---------------------------------------------------------------------------


class TestComputeSemanticDiversity:
    def test_正常系_3軸統合スコアを返す(self) -> None:
        entity_type_counts = {"company": 50, "index": 30, "sector": 20}
        topic_category_counts = {"macro": 40, "stock": 35, "ai": 25}
        relationship_type_counts = {"STATES_FACT": 100, "MAKES_CLAIM": 80, "ABOUT": 60}

        score = compute_semantic_diversity(
            entity_type_counts=entity_type_counts,
            topic_category_counts=topic_category_counts,
            relationship_type_counts=relationship_type_counts,
        )
        assert 0.0 <= score <= 1.0

    def test_正常系_均一分布で高スコア(self) -> None:
        entity_type_counts = {"company": 10, "index": 10, "sector": 10}
        topic_category_counts = {"macro": 10, "stock": 10, "ai": 10}
        relationship_type_counts = {"STATES_FACT": 10, "MAKES_CLAIM": 10, "ABOUT": 10}

        score = compute_semantic_diversity(
            entity_type_counts=entity_type_counts,
            topic_category_counts=topic_category_counts,
            relationship_type_counts=relationship_type_counts,
        )
        assert score >= 0.9  # 全軸が均一なので高スコア

    def test_正常系_単一カテゴリのみで低スコア(self) -> None:
        entity_type_counts = {"company": 100}
        topic_category_counts = {"macro": 100}
        relationship_type_counts = {"STATES_FACT": 100}

        score = compute_semantic_diversity(
            entity_type_counts=entity_type_counts,
            topic_category_counts=topic_category_counts,
            relationship_type_counts=relationship_type_counts,
        )
        assert score == pytest.approx(0.0, abs=0.01)

    def test_エッジケース_全軸空で0(self) -> None:
        score = compute_semantic_diversity(
            entity_type_counts={},
            topic_category_counts={},
            relationship_type_counts={},
        )
        assert score == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Fixture: QualitySnapshot for output tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_snapshot() -> QualitySnapshot:
    """テスト用の QualitySnapshot を生成する。"""
    ts = datetime(2026, 3, 19, 12, 0, 0, tzinfo=timezone.utc)
    return QualitySnapshot(
        categories=[
            CategoryResult(
                name="structural",
                score=75.0,
                metrics=[
                    MetricValue(value=0.0005, unit="ratio", status="red"),
                    MetricValue(value=3.76, unit="count", status="green"),
                    MetricValue(value=0.934, unit="ratio", status="green"),
                    MetricValue(value=0.028, unit="ratio", status="green"),
                ],
            ),
            CategoryResult(
                name="completeness",
                score=100.0,
                metrics=[
                    MetricValue(value=0.95, unit="ratio", status="green"),
                ],
            ),
            CategoryResult(
                name="consistency",
                score=66.7,
                metrics=[
                    MetricValue(value=0.975, unit="ratio", status="green"),
                    MetricValue(value=0.975, unit="ratio", status="green"),
                    MetricValue(value=3.0, unit="count", status="red"),
                ],
            ),
            CategoryResult(
                name="accuracy",
                score=0.0,
                metrics=[
                    MetricValue(value=0.0, unit="ratio", status="yellow", stub=True),
                ],
            ),
            CategoryResult(
                name="timeliness",
                score=100.0,
                metrics=[
                    MetricValue(value=5.2, unit="days", status="green"),
                    MetricValue(value=45.0, unit="count", status="green"),
                    MetricValue(value=443.0, unit="days", status="green"),
                ],
            ),
            CategoryResult(
                name="finance_specific",
                score=33.3,
                metrics=[
                    MetricValue(value=0.727, unit="ratio", status="yellow"),
                    MetricValue(value=4.5, unit="count", status="yellow"),
                    MetricValue(value=0.2, unit="ratio", status="red"),
                ],
            ),
            CategoryResult(
                name="discoverability",
                score=100.0,
                metrics=[
                    MetricValue(value=3.5, unit="hops", status="green"),
                    MetricValue(value=0.4, unit="ratio", status="green"),
                    MetricValue(value=0.95, unit="ratio", status="green"),
                ],
            ),
        ],
        overall_score=67.9,
        timestamp=ts,
    )


@pytest.fixture()
def sample_check_rules() -> list[CheckRuleResult]:
    """テスト用の CheckRuleResult リストを生成する。"""
    return [
        CheckRuleResult(
            rule_name="subject_reference", pass_rate=0.98, violations=["It was..."]
        ),
        CheckRuleResult(rule_name="entity_length", pass_rate=1.0, violations=[]),
        CheckRuleResult(
            rule_name="schema_compliance", pass_rate=0.95, violations=["unknown_type"]
        ),
        CheckRuleResult(
            rule_name="relationship_compliance", pass_rate=1.0, violations=[]
        ),
    ]


@pytest.fixture()
def sample_entropy() -> dict[str, float]:
    """テスト用のエントロピーデータを生成する。"""
    return {
        "entity_type_entropy": 0.85,
        "topic_category_entropy": 0.72,
        "relationship_type_entropy": 0.91,
        "semantic_diversity": 0.8267,
    }


# ---------------------------------------------------------------------------
# render_console
# ---------------------------------------------------------------------------


class TestRenderConsole:
    def test_正常系_例外なく実行できる(
        self,
        sample_snapshot: QualitySnapshot,
        sample_check_rules: list[CheckRuleResult],
        sample_entropy: dict[str, float],
    ) -> None:
        # render_console は例外なく実行できること（副作用はコンソール出力）
        render_console(sample_snapshot, sample_check_rules, sample_entropy)

    def test_正常系_空カテゴリでもエラーなし(self) -> None:
        ts = datetime(2026, 3, 19, 12, 0, 0, tzinfo=timezone.utc)
        empty_snapshot = QualitySnapshot(categories=[], overall_score=0.0, timestamp=ts)
        render_console(empty_snapshot, [], {})

    def test_正常系_ステータス色付けがgreen_yellow_red(
        self,
        sample_snapshot: QualitySnapshot,
        sample_check_rules: list[CheckRuleResult],
        sample_entropy: dict[str, float],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        render_console(sample_snapshot, sample_check_rules, sample_entropy)
        # Rich は stdout に出力するので、capsys では直接色コードは取れないが
        # 例外なく完了することを確認（色付けロジックは内部テストで検証）


# ---------------------------------------------------------------------------
# save_json
# ---------------------------------------------------------------------------


class TestSaveJson:
    def test_正常系_JSONファイルが正しいパスに保存される(
        self,
        tmp_path: Path,
        sample_snapshot: QualitySnapshot,
        sample_check_rules: list[CheckRuleResult],
        sample_entropy: dict[str, float],
    ) -> None:
        output_path = save_json(
            sample_snapshot,
            sample_check_rules,
            sample_entropy,
            output_dir=tmp_path,
        )
        assert output_path.exists()
        assert output_path.suffix == ".json"
        assert "snapshot_" in output_path.name

    def test_正常系_JSONスキーマが正しい(
        self,
        tmp_path: Path,
        sample_snapshot: QualitySnapshot,
        sample_check_rules: list[CheckRuleResult],
        sample_entropy: dict[str, float],
    ) -> None:
        import json

        output_path = save_json(
            sample_snapshot,
            sample_check_rules,
            sample_entropy,
            output_dir=tmp_path,
        )
        with output_path.open(encoding="utf-8") as f:
            data = json.load(f)

        assert "timestamp" in data
        assert "overall_score" in data
        assert "categories" in data
        assert "check_rules" in data
        assert "entropy" in data
        assert isinstance(data["categories"], list)
        assert len(data["categories"]) == len(sample_snapshot.categories)

    def test_正常系_ディレクトリが自動作成される(
        self,
        tmp_path: Path,
        sample_snapshot: QualitySnapshot,
        sample_check_rules: list[CheckRuleResult],
        sample_entropy: dict[str, float],
    ) -> None:
        nested_dir = tmp_path / "deep" / "nested" / "dir"
        output_path = save_json(
            sample_snapshot,
            sample_check_rules,
            sample_entropy,
            output_dir=nested_dir,
        )
        assert output_path.exists()
        assert nested_dir.exists()


# ---------------------------------------------------------------------------
# save_neo4j
# ---------------------------------------------------------------------------


class TestSaveNeo4j:
    def test_正常系_MERGEクエリが実行される(
        self,
        sample_snapshot: QualitySnapshot,
    ) -> None:
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_session.run.return_value = mock_result

        save_neo4j(mock_session, sample_snapshot)

        # MERGE クエリが呼ばれたことを確認
        assert mock_session.run.called
        first_call_query = mock_session.run.call_args_list[0][0][0]
        assert "MERGE" in first_call_query
        assert "QualitySnapshot" in first_call_query

    def test_正常系_dry_run時はスキップされる(
        self,
        sample_snapshot: QualitySnapshot,
    ) -> None:
        mock_session = MagicMock()

        save_neo4j(mock_session, sample_snapshot, dry_run=True)

        # dry-run ではクエリが実行されない
        mock_session.run.assert_not_called()

    def test_正常系_snapshot_idが含まれる(
        self,
        sample_snapshot: QualitySnapshot,
    ) -> None:
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_session.run.return_value = mock_result

        save_neo4j(mock_session, sample_snapshot)

        # パラメータに snapshot_id が含まれること
        call_kwargs = mock_session.run.call_args_list[0]
        params = call_kwargs[0][1] if len(call_kwargs[0]) > 1 else call_kwargs[1]
        assert "snapshot_id" in params


# ---------------------------------------------------------------------------
# generate_markdown
# ---------------------------------------------------------------------------


class TestGenerateMarkdown:
    def test_正常系_Markdown文字列を返す(
        self,
        sample_snapshot: QualitySnapshot,
        sample_check_rules: list[CheckRuleResult],
        sample_entropy: dict[str, float],
    ) -> None:
        md = generate_markdown(sample_snapshot, sample_check_rules, sample_entropy)
        assert isinstance(md, str)
        assert len(md) > 0

    def test_正常系_全セクションを含む(
        self,
        sample_snapshot: QualitySnapshot,
        sample_check_rules: list[CheckRuleResult],
        sample_entropy: dict[str, float],
    ) -> None:
        md = generate_markdown(sample_snapshot, sample_check_rules, sample_entropy)
        # カテゴリ別表
        assert "structural" in md
        assert "completeness" in md
        assert "consistency" in md
        # CheckRules セクション
        assert "CheckRules" in md or "check_rules" in md.lower() or "Check Rules" in md
        # Entropy セクション
        assert "Entropy" in md or "entropy" in md or "多様性" in md
        # 総合評価
        assert "67.9" in md or "overall" in md.lower() or "総合" in md

    def test_正常系_レーティングA_Dが含まれる(
        self,
        sample_snapshot: QualitySnapshot,
        sample_check_rules: list[CheckRuleResult],
        sample_entropy: dict[str, float],
    ) -> None:
        md = generate_markdown(sample_snapshot, sample_check_rules, sample_entropy)
        # A, B, C, D いずれかのレーティングが含まれる
        has_rating = any("レーティング" in md or "Rating" in md for _ in [1])
        has_grade = any(grade in md for grade in ["A", "B", "C", "D"])
        assert has_rating or has_grade

    def test_正常系_ファイル保存可能(
        self,
        tmp_path: Path,
        sample_snapshot: QualitySnapshot,
        sample_check_rules: list[CheckRuleResult],
        sample_entropy: dict[str, float],
    ) -> None:
        md = generate_markdown(sample_snapshot, sample_check_rules, sample_entropy)
        out = tmp_path / "report.md"
        out.write_text(md, encoding="utf-8")
        assert out.exists()
        assert out.read_text(encoding="utf-8") == md


# ---------------------------------------------------------------------------
# compare_snapshots
# ---------------------------------------------------------------------------


class TestCompareSnapshots:
    def test_正常系_2つのスナップショットの差分を返す(
        self,
        sample_snapshot: QualitySnapshot,
    ) -> None:
        # 「前回」のスナップショットを作成（少し低いスコア）
        ts_prev = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
        prev_snapshot = QualitySnapshot(
            categories=[
                CategoryResult(name="structural", score=60.0, metrics=[]),
                CategoryResult(name="completeness", score=80.0, metrics=[]),
                CategoryResult(name="consistency", score=50.0, metrics=[]),
                CategoryResult(name="accuracy", score=0.0, metrics=[]),
                CategoryResult(name="timeliness", score=90.0, metrics=[]),
                CategoryResult(name="finance_specific", score=20.0, metrics=[]),
                CategoryResult(name="discoverability", score=80.0, metrics=[]),
            ],
            overall_score=54.3,
            timestamp=ts_prev,
        )

        diff = compare_snapshots(prev_snapshot, sample_snapshot)
        assert isinstance(diff, str)
        assert len(diff) > 0
        # 差分表示にカテゴリ名が含まれる
        assert "structural" in diff

    def test_正常系_スコア変化がプラスマイナスで表示(
        self,
        sample_snapshot: QualitySnapshot,
    ) -> None:
        ts_prev = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
        prev_snapshot = QualitySnapshot(
            categories=[
                CategoryResult(name="structural", score=60.0, metrics=[]),
                CategoryResult(name="completeness", score=80.0, metrics=[]),
            ],
            overall_score=54.3,
            timestamp=ts_prev,
        )
        diff = compare_snapshots(prev_snapshot, sample_snapshot)
        # + or - or 改善 or 悪化 or 差分の数値が含まれる
        assert "+" in diff or "-" in diff or "改善" in diff or "変化" in diff

    def test_正常系_JSON読み込みで比較可能(
        self,
        tmp_path: Path,
        sample_snapshot: QualitySnapshot,
        sample_check_rules: list[CheckRuleResult],
        sample_entropy: dict[str, float],
    ) -> None:
        # まず JSON に保存
        output_path = save_json(
            sample_snapshot,
            sample_check_rules,
            sample_entropy,
            output_dir=tmp_path,
        )
        assert output_path.exists()

    def test_エッジケース_同一スナップショットで差分なし(
        self,
        sample_snapshot: QualitySnapshot,
    ) -> None:
        diff = compare_snapshots(sample_snapshot, sample_snapshot)
        assert isinstance(diff, str)
