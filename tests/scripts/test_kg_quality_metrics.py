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
    evaluate_status,
    get_counts,
    load_schema,
    measure_accuracy,
    measure_completeness,
    measure_consistency,
    measure_finance_specific,
    measure_structural,
    measure_timeliness,
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

        # Source: 3 required (source_id, title, source_type, authority_level, fetched_at=5)
        # Entity: 3 required (entity_id, name, entity_type)
        # Each query returns {total, filled}
        mock_results: list[MagicMock] = []
        # Source の5つの required property
        for _ in range(5):
            r = MagicMock()
            r.single.return_value = {"total": 100, "filled": 95}
            mock_results.append(r)
        # Entity の3つの required property
        for _ in range(3):
            r = MagicMock()
            r.single.return_value = {"total": 200, "filled": 190}
            mock_results.append(r)

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

        # 十分なモック結果を用意
        mock_r = MagicMock()
        mock_r.single.return_value = {"total": 100, "filled": 90, "count": 10}
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

        # 鮮度: 最新 Source の fetched_at からの経過日数
        mock_freshness = MagicMock()
        mock_freshness.single.return_value = {"avg_age_days": 5.2}

        # 更新頻度: 過去30日のSource投入数
        mock_frequency = MagicMock()
        mock_frequency.single.return_value = {"recent_count": 45}

        # 時間カバレッジ: fetched_at の最古/最新
        mock_coverage = MagicMock()
        mock_coverage.single.return_value = {
            "earliest": "2025-01-01T00:00:00Z",
            "latest": "2026-03-19T00:00:00Z",
        }

        mock_session.run.side_effect = [mock_freshness, mock_frequency, mock_coverage]

        result = measure_timeliness(mock_session)
        assert isinstance(result, CategoryResult)
        assert result.name == "timeliness"
        assert len(result.metrics) == 3

    def test_正常系_Memory除外フィルタが全Cypherに含まれる(self) -> None:
        mock_session = MagicMock()

        mock_freshness = MagicMock()
        mock_freshness.single.return_value = {"avg_age_days": 5.0}
        mock_frequency = MagicMock()
        mock_frequency.single.return_value = {"recent_count": 30}
        mock_coverage = MagicMock()
        mock_coverage.single.return_value = {
            "earliest": "2025-01-01T00:00:00Z",
            "latest": "2026-03-19T00:00:00Z",
        }
        mock_session.run.side_effect = [mock_freshness, mock_frequency, mock_coverage]

        measure_timeliness(mock_session)
        calls = mock_session.run.call_args_list
        for call in calls:
            query = call[0][0]
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
