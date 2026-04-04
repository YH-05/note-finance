"""Tests for kg_entity_completeness helpers (Wave7 / Issue #312)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path
import yaml

if TYPE_CHECKING:
    from pathlib import Path


class TestPhaseDisplayName:
    """_phase_display_name() のテスト."""

    def test_正常系_既知のキーを変換できる(self) -> None:
        from scripts.kg_entity_completeness import _phase_display_name

        assert _phase_display_name("phase1_overview") == "Phase 1"
        assert _phase_display_name("phase4_financials") == "Phase 4"
        assert _phase_display_name("phase5_valuation") == "Phase 5"
        assert _phase_display_name("phase6_catalysts") == "Phase 6"

    def test_正常系_未知のキーはそのまま返す(self) -> None:
        from scripts.kg_entity_completeness import _phase_display_name

        assert _phase_display_name("custom_phase") == "custom_phase"
        assert _phase_display_name("") == ""


class TestParseCommonChecks:
    """parse_common_checks() のテスト."""

    def _make_schema(self, **sections: dict) -> dict:
        return {"common": sections}

    def test_正常系_factsを抽出できる(self) -> None:
        from scripts.kg_entity_completeness import CheckItem, parse_common_checks

        schema = self._make_schema(
            phase1_overview={
                "facts": [
                    {
                        "label": "事業モデル",
                        "priority": "high",
                        "pattern": "事業.*モデル",
                    },
                ]
            }
        )
        items = parse_common_checks(schema)

        assert len(items) == 1
        assert isinstance(items[0], CheckItem)
        assert items[0].check_type == "fact"
        assert items[0].label == "事業モデル"
        assert items[0].priority == "high"
        assert items[0].phase == "Phase 1"

    def test_正常系_datapointsを抽出できる(self) -> None:
        from scripts.kg_entity_completeness import CheckItem, parse_common_checks

        schema = self._make_schema(
            phase4_financials={
                "datapoints": [
                    {
                        "label": "Revenue",
                        "priority": "high",
                        "metric_pattern": "revenue|売上",
                        "min_periods": 3,
                    }
                ]
            }
        )
        items = parse_common_checks(schema)

        assert len(items) == 1
        assert items[0].check_type == "datapoint"
        assert items[0].min_periods == 3
        assert items[0].pattern == "revenue|売上"

    def test_正常系_claimsを抽出できる(self) -> None:
        from scripts.kg_entity_completeness import CheckItem, parse_common_checks

        schema = self._make_schema(
            phase1_overview={
                "claims": [
                    {
                        "label": "アナリスト評価",
                        "priority": "medium",
                        "pattern": "rates.*Buy",
                    },
                ]
            }
        )
        items = parse_common_checks(schema)

        assert len(items) == 1
        assert items[0].check_type == "claim"

    def test_正常系_relationshipsを抽出できる(self) -> None:
        from scripts.kg_entity_completeness import CheckItem, parse_common_checks

        schema = self._make_schema(
            phase1_overview={
                "relationships": [
                    {"label": "RELATES_TO", "type": "RELATES_TO", "min_count": 2},
                ]
            }
        )
        items = parse_common_checks(schema)

        assert len(items) == 1
        assert items[0].check_type == "relationship"
        assert items[0].min_count == 2
        assert items[0].priority == "medium"

    def test_正常系_空のschemaは空リストを返す(self) -> None:
        from scripts.kg_entity_completeness import parse_common_checks

        assert parse_common_checks({}) == []
        assert parse_common_checks({"common": {}}) == []

    def test_正常系_複数フェーズを連結して返す(self) -> None:
        from scripts.kg_entity_completeness import parse_common_checks

        schema = self._make_schema(
            phase1_overview={
                "facts": [{"label": "F1", "priority": "high", "pattern": "p1"}],
            },
            phase4_financials={
                "facts": [{"label": "F2", "priority": "medium", "pattern": "p2"}],
            },
        )
        items = parse_common_checks(schema)

        assert len(items) == 2
        phases = {item.phase for item in items}
        assert "Phase 1" in phases
        assert "Phase 4" in phases


class TestGetScoringWeights:
    """get_scoring_weights() のテスト."""

    def test_正常系_デフォルト重みを返す(self) -> None:
        from scripts.kg_entity_completeness import get_scoring_weights

        schema: dict = {}
        weights = get_scoring_weights(schema)

        assert weights["high"] == 3
        assert weights["medium"] == 2
        assert weights["low"] == 1

    def test_正常系_カスタム重みを返す(self) -> None:
        from scripts.kg_entity_completeness import get_scoring_weights

        schema = {"scoring": {"weights": {"high": 5, "medium": 3, "low": 1}}}
        weights = get_scoring_weights(schema)

        assert weights["high"] == 5
        assert weights["medium"] == 3

    def test_正常系_scoringキーなしはデフォルトを返す(self) -> None:
        from scripts.kg_entity_completeness import get_scoring_weights

        weights = get_scoring_weights({"other": "value"})
        assert weights["high"] == 3


class TestLoadSchema:
    """load_schema() のテスト."""

    def test_正常系_YAMLを読み込める(self, tmp_path: Path) -> None:
        from scripts.kg_entity_completeness import load_schema

        schema_file = tmp_path / "schema.yaml"
        schema_file.write_text(
            yaml.dump({"version": "1.0", "common": {}}), encoding="utf-8"
        )

        result = load_schema(schema_file)
        assert result["version"] == "1.0"

    def test_異常系_存在しないファイルでFileNotFoundError(self, tmp_path: Path) -> None:
        from scripts.kg_entity_completeness import load_schema

        with pytest.raises(FileNotFoundError):
            load_schema(tmp_path / "nonexistent.yaml")


class TestCheckItemDataclass:
    """CheckItem データクラスのテスト."""

    def test_正常系_デフォルト値が設定される(self) -> None:
        from scripts.kg_entity_completeness import CheckItem

        item = CheckItem(
            phase="Phase 1",
            label="事業モデル",
            priority="high",
            check_type="fact",
            pattern="事業.*モデル",
        )

        assert item.min_periods == 0
        assert item.min_count == 0

    def test_正常系_全フィールドを指定できる(self) -> None:
        from scripts.kg_entity_completeness import CheckItem

        item = CheckItem(
            phase="Phase 4",
            label="Revenue",
            priority="high",
            check_type="datapoint",
            pattern="revenue",
            min_periods=4,
            min_count=2,
        )

        assert item.min_periods == 4
        assert item.min_count == 2


class TestParseSectorChecks:
    """parse_sector_checks() のテスト."""

    def test_正常系_セクターKPIを抽出できる(self) -> None:
        from scripts.kg_entity_completeness import parse_sector_checks

        schema = {
            "sectors": {
                "telecom": {
                    "match_pattern": "telecom|通信",
                    "kpis": [
                        {
                            "label": "ARPU",
                            "priority": "high",
                            "metric_pattern": "arpu",
                            "min_periods": 2,
                        }
                    ],
                }
            }
        }
        result = parse_sector_checks(schema)

        assert "telecom" in result
        match_pat, items = result["telecom"]
        assert match_pat == "telecom|通信"
        assert len(items) == 1
        assert items[0].label == "ARPU"
        assert items[0].check_type == "datapoint"

    def test_正常系_空のsectorsは空dictを返す(self) -> None:
        from scripts.kg_entity_completeness import parse_sector_checks

        assert parse_sector_checks({}) == {}
        assert parse_sector_checks({"sectors": {}}) == {}
