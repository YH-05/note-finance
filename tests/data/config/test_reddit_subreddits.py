"""data/config/reddit-subreddits.json のスキーマ・整合性検証テスト。"""

import json
from pathlib import Path
from typing import Any

import pytest

CONFIG_PATH = Path("data/config/reddit-subreddits.json")
EXPECTED_GROUPS = {
    "general_investing",
    "trading",
    "macro_economics",
    "deep_analysis",
    "sector_specific",
}
EXPECTED_TOTAL_SUBREDDITS = 12
REQUIRED_GROUP_FIELDS = {"name", "name_ja", "description", "subreddits"}
REQUIRED_FILTER_FIELDS = {
    "min_score",
    "min_comments",
    "posts_per_subreddit",
    "exclude_flairs",
}


@pytest.fixture
def config() -> dict[str, Any]:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]


class TestRedditSubredditsSchema:
    def test_正常系_全5グループが定義されている(self, config: dict[str, Any]) -> None:
        assert set(config["groups"].keys()) == EXPECTED_GROUPS

    def test_正常系_subreddit合計12件(self, config: dict[str, Any]) -> None:
        total = sum(len(g["subreddits"]) for g in config["groups"].values())
        assert total == EXPECTED_TOTAL_SUBREDDITS

    def test_正常系_各グループに必須フィールドが存在する(
        self, config: dict[str, Any]
    ) -> None:
        for key, group in config["groups"].items():
            missing = REQUIRED_GROUP_FIELDS - set(group.keys())
            assert not missing, f"{key} に必須フィールドが不足: {missing}"

    def test_正常系_subredditsが空でない(self, config: dict[str, Any]) -> None:
        for key, group in config["groups"].items():
            assert len(group["subreddits"]) > 0, f"{key} の subreddits が空"

    def test_正常系_category_mappingとgroupsのキーが完全一致する(
        self, config: dict[str, Any]
    ) -> None:
        group_keys = set(config["groups"].keys())
        mapping_keys = set(config["category_mapping"].keys())
        assert group_keys == mapping_keys, (
            f"groups と category_mapping のキーが不一致: "
            f"groups のみ={group_keys - mapping_keys}, "
            f"category_mapping のみ={mapping_keys - group_keys}"
        )

    def test_正常系_フィルタに必須フィールドが存在する(
        self, config: dict[str, Any]
    ) -> None:
        missing = REQUIRED_FILTER_FIELDS - set(config["filters"].keys())
        assert not missing, f"filters に必須フィールドが不足: {missing}"

    def test_正常系_フィルタ値が正の整数(self, config: dict[str, Any]) -> None:
        filters = config["filters"]
        assert filters["min_score"] > 0, "min_score は正の整数であること"
        assert filters["min_comments"] > 0, "min_comments は正の整数であること"
        assert filters["posts_per_subreddit"] > 0, (
            "posts_per_subreddit は正の整数であること"
        )

    def test_正常系_exclude_flairsが空でない(self, config: dict[str, Any]) -> None:
        assert len(config["filters"]["exclude_flairs"]) > 0

    def test_エッジケース_subreddits重複なし(self, config: dict[str, Any]) -> None:
        all_subreddits: list[str] = []
        for group in config["groups"].values():
            all_subreddits.extend(group["subreddits"])
        assert len(all_subreddits) == len(set(all_subreddits)), (
            "同一 subreddit が複数グループに定義されている"
        )

    def test_エッジケース_category_mappingの値が文字列(
        self, config: dict[str, Any]
    ) -> None:
        for key, value in config["category_mapping"].items():
            assert isinstance(value, str), (
                f"category_mapping[{key}] が文字列でない: {value!r}"
            )
            assert value, f"category_mapping[{key}] が空文字"
