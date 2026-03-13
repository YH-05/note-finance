"""Unit tests for wealth RSS presets structure.

Tests that rss-presets-wealth.json has valid JSON structure, required fields,
unique URLs, valid fetch_interval values, and valid category values.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

WEALTH_PRESETS_PATH = Path("data/config/rss-presets-wealth.json")
"""Path to the wealth RSS presets configuration file."""


@pytest.fixture(scope="module")
def wealth_presets_data() -> dict:
    """Load and return the wealth presets JSON data.

    Returns
    -------
    dict
        Parsed JSON data from rss-presets-wealth.json.
    """
    with WEALTH_PRESETS_PATH.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def presets_list(wealth_presets_data: dict) -> list[dict]:
    """Return the list of preset entries from the wealth presets data.

    Parameters
    ----------
    wealth_presets_data : dict
        Parsed wealth presets JSON.

    Returns
    -------
    list[dict]
        List of preset entry dictionaries.
    """
    return wealth_presets_data["presets"]


# ---------------------------------------------------------------------------
# Test 1: JSON Structure
# ---------------------------------------------------------------------------


class TestWealthPresetsJsonStructure:
    """Test top-level JSON structure of rss-presets-wealth.json."""

    def test_正常系_JSONファイルが存在する(self) -> None:
        """rss-presets-wealth.json ファイルが存在することを確認。"""
        assert WEALTH_PRESETS_PATH.exists(), (
            f"Presets file not found: {WEALTH_PRESETS_PATH}"
        )

    def test_正常系_ルートオブジェクトであること(
        self, wealth_presets_data: dict
    ) -> None:
        """ルートがJSONオブジェクトであることを確認。"""
        assert isinstance(wealth_presets_data, dict), (
            "Root JSON must be an object (dict)"
        )

    def test_正常系_presetsキーが存在すること(self, wealth_presets_data: dict) -> None:
        """'presets' キーが存在することを確認。"""
        assert "presets" in wealth_presets_data, "Root JSON must contain 'presets' key"

    def test_正常系_presetsが配列であること(self, wealth_presets_data: dict) -> None:
        """'presets' の値が配列であることを確認。"""
        assert isinstance(wealth_presets_data["presets"], list), (
            "'presets' must be an array"
        )

    def test_正常系_presetsが空でないこと(self, presets_list: list[dict]) -> None:
        """'presets' 配列が空でないことを確認。"""
        assert len(presets_list) > 0, "presets array must not be empty"

    def test_正常系_versionキーが存在すること(self, wealth_presets_data: dict) -> None:
        """'version' キーが存在することを確認。"""
        assert "version" in wealth_presets_data, (
            "Root JSON should contain 'version' key"
        )


# ---------------------------------------------------------------------------
# Test 2: Required Fields
# ---------------------------------------------------------------------------


REQUIRED_PRESET_FIELDS = ["url", "title", "category", "fetch_interval", "enabled"]
"""Required fields in each preset entry."""


class TestWealthPresetsRequiredFields:
    """Test that each preset entry contains all required fields."""

    def test_正常系_全エントリが必須フィールドを持つこと(
        self, presets_list: list[dict]
    ) -> None:
        """全プリセットエントリが必須フィールドを全て持つことを確認。"""
        missing: list[str] = []
        for i, entry in enumerate(presets_list):
            for field_name in REQUIRED_PRESET_FIELDS:
                if field_name not in entry:
                    missing.append(
                        f"entry[{i}] (title={entry.get('title', 'unknown')}): "
                        f"missing '{field_name}'"
                    )
        assert not missing, "Missing required fields:\n" + "\n".join(missing)

    def test_正常系_URLフィールドが文字列であること(
        self, presets_list: list[dict]
    ) -> None:
        """url フィールドが文字列であることを確認。"""
        invalid: list[str] = []
        for i, entry in enumerate(presets_list):
            url = entry.get("url")
            if not isinstance(url, str):
                invalid.append(
                    f"entry[{i}] (title={entry.get('title', 'unknown')}): "
                    f"url must be str, got {type(url).__name__}"
                )
        assert not invalid, "Invalid url fields:\n" + "\n".join(invalid)

    def test_正常系_URLがhttpまたはhttpsであること(
        self, presets_list: list[dict]
    ) -> None:
        """url フィールドが http:// または https:// で始まることを確認。"""
        invalid: list[str] = []
        for i, entry in enumerate(presets_list):
            url = entry.get("url", "")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                invalid.append(
                    f"entry[{i}] (title={entry.get('title', 'unknown')}): "
                    f"url must start with http:// or https://, got: '{url}'"
                )
        assert not invalid, "Invalid URL schemes:\n" + "\n".join(invalid)

    def test_正常系_enabledフィールドがboolであること(
        self, presets_list: list[dict]
    ) -> None:
        """enabled フィールドが真偽値であることを確認。"""
        invalid: list[str] = []
        for i, entry in enumerate(presets_list):
            enabled = entry.get("enabled")
            if not isinstance(enabled, bool):
                invalid.append(
                    f"entry[{i}] (title={entry.get('title', 'unknown')}): "
                    f"enabled must be bool, got {type(enabled).__name__}"
                )
        assert not invalid, "Invalid enabled fields:\n" + "\n".join(invalid)


# ---------------------------------------------------------------------------
# Test 3: URL Uniqueness
# ---------------------------------------------------------------------------


class TestWealthPresetsUrlUniqueness:
    """Test that all preset URLs are unique."""

    def test_正常系_URLが重複していないこと(self, presets_list: list[dict]) -> None:
        """全プリセットのURLが一意であることを確認。"""
        urls = [entry.get("url", "") for entry in presets_list]
        seen: set[str] = set()
        duplicates: list[str] = []

        for url in urls:
            if url in seen:
                duplicates.append(url)
            else:
                seen.add(url)

        assert not duplicates, "Duplicate URLs found:\n" + "\n".join(duplicates)

    def test_正常系_titleが重複していないこと(self, presets_list: list[dict]) -> None:
        """全プリセットのtitleが一意であることを確認。"""
        titles = [entry.get("title", "") for entry in presets_list]
        seen: set[str] = set()
        duplicates: list[str] = []

        for title in titles:
            if title in seen:
                duplicates.append(title)
            else:
                seen.add(title)

        assert not duplicates, "Duplicate titles found:\n" + "\n".join(duplicates)


# ---------------------------------------------------------------------------
# Test 4: fetch_interval Values
# ---------------------------------------------------------------------------

VALID_FETCH_INTERVALS = {"daily", "weekly", "monthly", "hourly"}
"""Valid fetch_interval values."""


class TestWealthPresetsFetchInterval:
    """Test fetch_interval field values."""

    def test_正常系_fetch_intervalが有効な値であること(
        self, presets_list: list[dict]
    ) -> None:
        """fetch_interval が有効な値（daily/weekly/monthly/hourly）であることを確認。"""
        invalid: list[str] = []
        for i, entry in enumerate(presets_list):
            fetch_interval = entry.get("fetch_interval", "")
            if fetch_interval not in VALID_FETCH_INTERVALS:
                invalid.append(
                    f"entry[{i}] (title={entry.get('title', 'unknown')}): "
                    f"fetch_interval='{fetch_interval}' not in {sorted(VALID_FETCH_INTERVALS)}"
                )
        assert not invalid, "Invalid fetch_interval values:\n" + "\n".join(invalid)

    def test_正常系_fetch_intervalが文字列であること(
        self, presets_list: list[dict]
    ) -> None:
        """fetch_interval が文字列であることを確認。"""
        invalid: list[str] = []
        for i, entry in enumerate(presets_list):
            fetch_interval = entry.get("fetch_interval")
            if not isinstance(fetch_interval, str):
                invalid.append(
                    f"entry[{i}] (title={entry.get('title', 'unknown')}): "
                    f"fetch_interval must be str, got {type(fetch_interval).__name__}"
                )
        assert not invalid, "Invalid fetch_interval types:\n" + "\n".join(invalid)


# ---------------------------------------------------------------------------
# Test 5: Category Values
# ---------------------------------------------------------------------------

VALID_CATEGORIES = {
    "personal_finance",
    "fire_wealth_building",
    "data_driven_investing",
    "dividend_income",
    "academic_finance",
    "financial_infrastructure",
}
"""Valid category values for wealth presets."""


class TestWealthPresetsCategory:
    """Test category field values."""

    def test_正常系_categoryが有効な値であること(
        self, presets_list: list[dict]
    ) -> None:
        """category が有効な値であることを確認。"""
        invalid: list[str] = []
        for i, entry in enumerate(presets_list):
            category = entry.get("category", "")
            if category not in VALID_CATEGORIES:
                invalid.append(
                    f"entry[{i}] (title={entry.get('title', 'unknown')}): "
                    f"category='{category}' not in {sorted(VALID_CATEGORIES)}"
                )
        assert not invalid, "Invalid category values:\n" + "\n".join(invalid)

    def test_正常系_categoryが文字列であること(self, presets_list: list[dict]) -> None:
        """category が文字列であることを確認。"""
        invalid: list[str] = []
        for i, entry in enumerate(presets_list):
            category = entry.get("category")
            if not isinstance(category, str):
                invalid.append(
                    f"entry[{i}] (title={entry.get('title', 'unknown')}): "
                    f"category must be str, got {type(category).__name__}"
                )
        assert not invalid, "Invalid category types:\n" + "\n".join(invalid)

    def test_正常系_全カテゴリが少なくとも1件存在すること(
        self, presets_list: list[dict]
    ) -> None:
        """有効なカテゴリのうち少なくとも1つが使用されていることを確認。"""
        used_categories = {entry.get("category", "") for entry in presets_list}
        assert used_categories & VALID_CATEGORIES, (
            f"No valid categories found. Used: {sorted(used_categories)}, "
            f"Valid: {sorted(VALID_CATEGORIES)}"
        )
