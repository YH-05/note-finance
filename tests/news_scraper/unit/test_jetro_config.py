"""Unit tests for news_scraper._jetro_config module.

Tests cover URL constants, category URL mappings, CSS selector definitions,
content type lists, and JetroContentMeta dataclass.
"""

from __future__ import annotations

import dataclasses

import pytest

from news_scraper._jetro_config import (
    ARTICLE_SELECTORS,
    CONTENT_TYPES,
    JETRO_BASE_URL,
    JETRO_CATEGORY_URLS,
    JETRO_RSS_BIZNEWS,
    SECTION_SELECTORS,
    JetroContentMeta,
)


class TestUrlConstants:
    """Tests for JETRO URL constants."""

    def test_正常系_JETRO_BASE_URLが定義されている(self) -> None:
        assert isinstance(JETRO_BASE_URL, str)
        assert JETRO_BASE_URL.startswith("https://www.jetro.go.jp")

    def test_正常系_JETRO_RSS_BIZNEWSが定義されている(self) -> None:
        assert isinstance(JETRO_RSS_BIZNEWS, str)
        assert "jetro.go.jp" in JETRO_RSS_BIZNEWS
        assert "biznews" in JETRO_RSS_BIZNEWS

    def test_正常系_URLは末尾スラッシュで終わらない(self) -> None:
        """Base URL should not end with trailing slash for clean path joining."""
        assert not JETRO_BASE_URL.endswith("/")


class TestJetroCategoryUrls:
    """Tests for JETRO_CATEGORY_URLS mapping."""

    def test_正常系_dict型で定義されている(self) -> None:
        assert isinstance(JETRO_CATEGORY_URLS, dict)

    def test_正常系_worldカテゴリが含まれている(self) -> None:
        assert "world" in JETRO_CATEGORY_URLS

    def test_正常系_themeカテゴリが含まれている(self) -> None:
        assert "theme" in JETRO_CATEGORY_URLS

    def test_正常系_industryカテゴリが含まれている(self) -> None:
        assert "industry" in JETRO_CATEGORY_URLS

    def test_正常系_各カテゴリの値がdict_str_strである(self) -> None:
        for category, urls in JETRO_CATEGORY_URLS.items():
            assert isinstance(urls, dict), f"Category '{category}' value is not a dict"
            for key, url in urls.items():
                assert isinstance(key, str), f"Key '{key}' in '{category}' is not str"
                assert isinstance(url, str), (
                    f"URL for '{key}' in '{category}' is not str"
                )

    def test_正常系_worldカテゴリに主要エントリが含まれている(self) -> None:
        world = JETRO_CATEGORY_URLS["world"]
        assert len(world) >= 1, "world category should have at least 1 entry"

    def test_正常系_themeカテゴリに主要エントリが含まれている(self) -> None:
        theme = JETRO_CATEGORY_URLS["theme"]
        assert len(theme) >= 1, "theme category should have at least 1 entry"

    def test_正常系_industryカテゴリに主要エントリが含まれている(self) -> None:
        industry = JETRO_CATEGORY_URLS["industry"]
        assert len(industry) >= 1, "industry category should have at least 1 entry"

    def test_正常系_全URLがhttpsで始まる(self) -> None:
        for category, urls in JETRO_CATEGORY_URLS.items():
            for key, url in urls.items():
                assert url.startswith("https://"), (
                    f"URL '{url}' in {category}/{key} does not start with https://"
                )


class TestArticleSelectors:
    """Tests for ARTICLE_SELECTORS mapping."""

    def test_正常系_dict型で定義されている(self) -> None:
        assert isinstance(ARTICLE_SELECTORS, dict)

    def test_正常系_値がlist_str形式である(self) -> None:
        for key, selectors in ARTICLE_SELECTORS.items():
            assert isinstance(selectors, list), (
                f"ARTICLE_SELECTORS['{key}'] is not a list"
            )
            for selector in selectors:
                assert isinstance(selector, str), (
                    f"Selector in ARTICLE_SELECTORS['{key}'] is not str"
                )

    def test_正常系_空でない(self) -> None:
        assert len(ARTICLE_SELECTORS) >= 1

    def test_正常系_各リストが少なくとも1つのセレクタを持つ(self) -> None:
        for key, selectors in ARTICLE_SELECTORS.items():
            assert len(selectors) >= 1, f"ARTICLE_SELECTORS['{key}'] has no selectors"


class TestSectionSelectors:
    """Tests for SECTION_SELECTORS mapping."""

    def test_正常系_dict型で定義されている(self) -> None:
        assert isinstance(SECTION_SELECTORS, dict)

    def test_正常系_値がlist_str形式である(self) -> None:
        for key, selectors in SECTION_SELECTORS.items():
            assert isinstance(selectors, list), (
                f"SECTION_SELECTORS['{key}'] is not a list"
            )
            for selector in selectors:
                assert isinstance(selector, str), (
                    f"Selector in SECTION_SELECTORS['{key}'] is not str"
                )

    def test_正常系_空でない(self) -> None:
        assert len(SECTION_SELECTORS) >= 1

    def test_正常系_各リストが少なくとも1つのセレクタを持つ(self) -> None:
        for key, selectors in SECTION_SELECTORS.items():
            assert len(selectors) >= 1, f"SECTION_SELECTORS['{key}'] has no selectors"


class TestContentTypes:
    """Tests for CONTENT_TYPES list."""

    def test_正常系_list型で定義されている(self) -> None:
        assert isinstance(CONTENT_TYPES, list)

    def test_正常系_全要素がstrである(self) -> None:
        for ct in CONTENT_TYPES:
            assert isinstance(ct, str), f"CONTENT_TYPES element '{ct}' is not str"

    def test_正常系_空でない(self) -> None:
        assert len(CONTENT_TYPES) >= 1


class TestJetroContentMeta:
    """Tests for JetroContentMeta dataclass."""

    def test_正常系_dataclassである(self) -> None:
        assert dataclasses.is_dataclass(JetroContentMeta)

    def test_正常系_frozenである(self) -> None:
        """JetroContentMeta should be immutable (frozen=True)."""
        meta = JetroContentMeta(
            title="テスト記事",
            url="https://www.jetro.go.jp/biznews/2026/test.html",
            category="world",
            subcategory="asia",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            meta.title = "変更"  # type: ignore[misc]

    def test_正常系_必須フィールドで作成できる(self) -> None:
        meta = JetroContentMeta(
            title="テスト記事",
            url="https://www.jetro.go.jp/biznews/2026/test.html",
            category="world",
            subcategory="asia",
        )
        assert meta.title == "テスト記事"
        assert meta.url == "https://www.jetro.go.jp/biznews/2026/test.html"
        assert meta.category == "world"
        assert meta.subcategory == "asia"

    def test_正常系_インスタンスは不変である(self) -> None:
        meta = JetroContentMeta(
            title="テスト",
            url="https://www.jetro.go.jp/test",
            category="theme",
            subcategory="digital",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            meta.url = "https://changed.com"  # type: ignore[misc]

    def test_正常系_等価比較ができる(self) -> None:
        """Dataclass provides __eq__ by default."""
        meta1 = JetroContentMeta(
            title="記事A",
            url="https://www.jetro.go.jp/a",
            category="world",
            subcategory="europe",
        )
        meta2 = JetroContentMeta(
            title="記事A",
            url="https://www.jetro.go.jp/a",
            category="world",
            subcategory="europe",
        )
        assert meta1 == meta2

    def test_正常系_異なるインスタンスは不等(self) -> None:
        meta1 = JetroContentMeta(
            title="記事A",
            url="https://www.jetro.go.jp/a",
            category="world",
            subcategory="europe",
        )
        meta2 = JetroContentMeta(
            title="記事B",
            url="https://www.jetro.go.jp/b",
            category="industry",
            subcategory="auto",
        )
        assert meta1 != meta2
