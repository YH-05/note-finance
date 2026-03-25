"""data/config/research-enrichment-config.json のスキーマ・整合性検証テスト。"""

import json
from pathlib import Path
from typing import Any

import pytest

CONFIG_PATH = Path("data/config/research-enrichment-config.json")

REQUIRED_TOP_LEVEL_KEYS = {"gap_analysis", "search", "fallback", "rawstore", "cycle_settings"}
VALID_AUTHORITY_LEVELS = {"official", "analyst", "media", "blog", "social", "academic"}


@pytest.fixture
def config() -> dict[str, Any]:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]


class TestResearchEnrichmentConfigSchema:
    def test_正常系_必須トップレベルキーが存在する(self, config: dict[str, Any]) -> None:
        missing = REQUIRED_TOP_LEVEL_KEYS - set(config.keys())
        assert not missing, f"必須キーが不足: {missing}"

    def test_正常系_gap_analysis_weightsの合計が1(self, config: dict[str, Any]) -> None:
        weights = config["gap_analysis"]["weights"]
        total = sum(weights.values())
        assert abs(total - 1.0) < 1e-9, f"weights合計が1.0でない: {total}"

    def test_正常系_gap_analysis_weightsに4軸が存在する(
        self, config: dict[str, Any]
    ) -> None:
        expected = {"category", "entity", "staleness", "financial"}
        assert set(config["gap_analysis"]["weights"].keys()) == expected

    def test_正常系_max_targets_per_cycleが正の整数(
        self, config: dict[str, Any]
    ) -> None:
        val = config["gap_analysis"]["max_targets_per_cycle"]
        assert isinstance(val, int) and val > 0, f"正の整数であること: {val}"

    def test_正常系_staleness_threshold_daysが正の整数(
        self, config: dict[str, Any]
    ) -> None:
        val = config["gap_analysis"]["staleness_threshold_days"]
        assert isinstance(val, int) and val > 0, f"正の整数であること: {val}"

    def test_正常系_min_facts_per_topicが正の整数(
        self, config: dict[str, Any]
    ) -> None:
        val = config["gap_analysis"]["min_facts_per_topic"]
        assert isinstance(val, int) and val > 0, f"正の整数であること: {val}"

    def test_正常系_search_reddit_subredditsが空でない(
        self, config: dict[str, Any]
    ) -> None:
        subs = config["search"]["reddit_subreddits"]
        assert len(subs) > 0, "reddit_subreddits が空"

    def test_正常系_search_query_templatesにen_jaが存在する(
        self, config: dict[str, Any]
    ) -> None:
        templates = config["search"]["query_templates"]
        assert "en" in templates, "en テンプレートが不足"
        assert "ja" in templates, "ja テンプレートが不足"
        assert len(templates["en"]) > 0, "en テンプレートが空"
        assert len(templates["ja"]) > 0, "ja テンプレートが空"

    def test_正常系_cycle_settingsの値が正の数値(
        self, config: dict[str, Any]
    ) -> None:
        cs = config["cycle_settings"]
        assert cs["min_cycle_interval_seconds"] > 0
        assert cs["max_consecutive_empty_cycles"] > 0
        assert cs["empty_cycle_wait_seconds"] > 0
        assert cs["maintenance_buffer_minutes"] > 0

    def test_正常系_rawstore_exclude_sourcesが文字列リスト(
        self, config: dict[str, Any]
    ) -> None:
        excludes = config["rawstore"]["exclude_sources"]
        assert isinstance(excludes, list)
        for item in excludes:
            assert isinstance(item, str), f"文字列でない: {item!r}"

    def test_エッジケース_weightsの各値が0以上1以下(
        self, config: dict[str, Any]
    ) -> None:
        for key, val in config["gap_analysis"]["weights"].items():
            assert 0.0 <= val <= 1.0, f"{key} の重みが範囲外: {val}"
