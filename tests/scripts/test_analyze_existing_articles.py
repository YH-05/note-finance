"""Unit tests for .claude/skills/topic-suggest/scripts/analyze_existing_articles.py."""

from __future__ import annotations

import json
import pathlib
import sys
import warnings
from typing import TYPE_CHECKING

import pytest
import yaml

# The script lives outside the standard src/scripts packages, so we need to
# add its parent directory to sys.path for import.
_SKILL_SCRIPTS_DIR = str(
    pathlib.Path(__file__).resolve().parent.parent.parent
    / ".claude"
    / "skills"
    / "topic-suggest"
    / "scripts"
)
if _SKILL_SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SKILL_SCRIPTS_DIR)

from analyze_existing_articles import _read_meta, analyze_articles  # noqa: E402  # pyright: ignore[reportMissingImports]

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# analyze_articles
# ---------------------------------------------------------------------------


class TestAnalyzeArticles:
    """analyze_articles の単体テスト。"""

    def test_異常系_存在しないディレクトリ(self, tmp_path: Path) -> None:
        """存在しないディレクトリを渡した場合、空の結果を返すことを確認。"""
        result = analyze_articles(tmp_path / "nonexistent")
        assert result == {"total": 0, "categories": {}, "latest_topics": []}

    def test_エッジケース_空ディレクトリ(self, tmp_path: Path) -> None:
        """空のディレクトリを渡した場合、空の結果を返すことを確認。"""
        articles_dir = tmp_path / "articles"
        articles_dir.mkdir()
        result = analyze_articles(articles_dir)
        assert result["total"] == 0
        assert result["categories"] == {}
        assert result["latest_topics"] == []

    def test_正常系_新ネスト構造(self, tmp_path: Path) -> None:
        """新構造 articles/{category}/{slug}/meta.yaml を正しく読み取ることを確認。"""
        articles_dir = tmp_path / "articles"
        # Create category/article structure
        article_dir = articles_dir / "macro_economy" / "2026-03-01_test-article"
        article_dir.mkdir(parents=True)
        meta = {
            "title": "Test Article",
            "category": "macro_economy",
            "created_at": "2026-03-01T00:00:00Z",
        }
        (article_dir / "meta.yaml").write_text(
            yaml.dump(meta, allow_unicode=True), encoding="utf-8"
        )

        result = analyze_articles(articles_dir)

        assert result["total"] == 1
        assert result["categories"] == {"macro_economy": 1}
        assert result["latest_topics"][0]["title"] == "Test Article"

    def test_正常系_レガシー構造(self, tmp_path: Path) -> None:
        """レガシー構造 articles/{slug}/article-meta.json を正しく読み取ることを確認。"""
        articles_dir = tmp_path / "articles"
        article_dir = articles_dir / "old_article_slug"
        article_dir.mkdir(parents=True)
        meta = {
            "title": "Legacy Article",
            "category": "stock_analysis",
            "created_at": "2026-02-15T00:00:00Z",
        }
        (article_dir / "article-meta.json").write_text(
            json.dumps(meta), encoding="utf-8"
        )

        result = analyze_articles(articles_dir)

        assert result["total"] == 1
        assert result["categories"] == {"stock_analysis": 1}
        assert result["latest_topics"][0]["title"] == "Legacy Article"

    def test_正常系_複数記事の最新5件制限(self, tmp_path: Path) -> None:
        """6件以上の記事があっても latest_topics は最大5件であることを確認。"""
        articles_dir = tmp_path / "articles"
        category_dir = articles_dir / "macro_economy"

        for i in range(7):
            article_dir = category_dir / f"2026-03-{i + 1:02d}_article-{i}"
            article_dir.mkdir(parents=True)
            meta = {
                "title": f"Article {i}",
                "category": "macro_economy",
                "created_at": f"2026-03-{i + 1:02d}T00:00:00Z",
            }
            (article_dir / "meta.yaml").write_text(
                yaml.dump(meta, allow_unicode=True), encoding="utf-8"
            )

        result = analyze_articles(articles_dir)

        assert result["total"] == 7
        assert len(result["latest_topics"]) == 5

    def test_正常系_複数カテゴリの集計(self, tmp_path: Path) -> None:
        """複数カテゴリの記事が正しくカウントされることを確認。"""
        articles_dir = tmp_path / "articles"

        for cat, count in [("macro_economy", 2), ("stock_analysis", 3)]:
            for i in range(count):
                article_dir = articles_dir / cat / f"2026-01-{i + 1:02d}_art-{i}"
                article_dir.mkdir(parents=True)
                meta = {
                    "title": f"{cat} {i}",
                    "category": cat,
                    "created_at": f"2026-01-{i + 1:02d}T00:00:00Z",
                }
                (article_dir / "meta.yaml").write_text(
                    yaml.dump(meta, allow_unicode=True), encoding="utf-8"
                )

        result = analyze_articles(articles_dir)

        assert result["total"] == 5
        assert result["categories"]["macro_economy"] == 2
        assert result["categories"]["stock_analysis"] == 3


# ---------------------------------------------------------------------------
# _read_meta
# ---------------------------------------------------------------------------


class TestReadMeta:
    """_read_meta の単体テスト。"""

    def test_正常系_meta_yaml読み取り(self, tmp_path: Path) -> None:
        """meta.yaml が正しく読み取られ、categories/latest_topics に追加されることを確認。"""
        article_dir = tmp_path / "article"
        article_dir.mkdir()
        meta = {
            "title": "YAML Article",
            "category": "quant_analysis",
            "created_at": "2026-03-10T00:00:00Z",
        }
        (article_dir / "meta.yaml").write_text(
            yaml.dump(meta, allow_unicode=True), encoding="utf-8"
        )

        categories: list[str] = []
        topics: list[dict[str, str]] = []
        _read_meta(article_dir, categories, topics)

        assert categories == ["quant_analysis"]
        assert len(topics) == 1
        assert topics[0]["title"] == "YAML Article"

    def test_正常系_article_meta_jsonフォールバック(self, tmp_path: Path) -> None:
        """meta.yaml がなく article-meta.json がある場合にフォールバックすることを確認。"""
        article_dir = tmp_path / "article"
        article_dir.mkdir()
        meta = {
            "title": "JSON Article",
            "category": "asset_management",
            "created_at": "2026-02-20T00:00:00Z",
        }
        (article_dir / "article-meta.json").write_text(
            json.dumps(meta), encoding="utf-8"
        )

        categories: list[str] = []
        topics: list[dict[str, str]] = []
        _read_meta(article_dir, categories, topics)

        assert categories == ["asset_management"]
        assert topics[0]["title"] == "JSON Article"

    def test_エッジケース_両ファイル不在(self, tmp_path: Path) -> None:
        """meta.yaml も article-meta.json も存在しない場合、何も追加されないことを確認。"""
        article_dir = tmp_path / "empty_article"
        article_dir.mkdir()

        categories: list[str] = []
        topics: list[dict[str, str]] = []
        _read_meta(article_dir, categories, topics)

        assert categories == []
        assert topics == []

    def test_異常系_meta_yamlパースエラーで警告(self, tmp_path: Path) -> None:
        """meta.yaml のパースに失敗した場合 warnings.warn が呼ばれることを確認。"""
        article_dir = tmp_path / "bad_article"
        article_dir.mkdir()
        # Write invalid YAML that will cause a parse error
        (article_dir / "meta.yaml").write_text(
            ":\n  invalid:\n    - [unclosed", encoding="utf-8"
        )

        categories: list[str] = []
        topics: list[dict[str, str]] = []

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _read_meta(article_dir, categories, topics)

            assert len(w) == 1
            assert "Failed to parse" in str(w[0].message)

        # Nothing should be added on parse error
        assert categories == []
        assert topics == []

    def test_異常系_article_meta_jsonパースエラーで警告(self, tmp_path: Path) -> None:
        """article-meta.json のパースに失敗した場合 warnings.warn が呼ばれることを確認。"""
        article_dir = tmp_path / "bad_json"
        article_dir.mkdir()
        (article_dir / "article-meta.json").write_text(
            "{invalid json", encoding="utf-8"
        )

        categories: list[str] = []
        topics: list[dict[str, str]] = []

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _read_meta(article_dir, categories, topics)

            assert len(w) == 1
            assert "Failed to parse" in str(w[0].message)

        assert categories == []
        assert topics == []

    def test_エッジケース_categoryキーなしで未分類(self, tmp_path: Path) -> None:
        """category キーがない場合に '未分類' が使われることを確認。"""
        article_dir = tmp_path / "article"
        article_dir.mkdir()
        meta = {"title": "No Category", "created_at": "2026-01-01T00:00:00Z"}
        (article_dir / "meta.yaml").write_text(
            yaml.dump(meta, allow_unicode=True), encoding="utf-8"
        )

        categories: list[str] = []
        topics: list[dict[str, str]] = []
        _read_meta(article_dir, categories, topics)

        assert categories == ["未分類"]

    def test_エッジケース_titleキーなしでディレクトリ名使用(
        self, tmp_path: Path
    ) -> None:
        """title キーがない場合にディレクトリ名が使われることを確認。"""
        article_dir = tmp_path / "my-article-dir"
        article_dir.mkdir()
        meta = {"category": "macro_economy", "created_at": "2026-01-01T00:00:00Z"}
        (article_dir / "meta.yaml").write_text(
            yaml.dump(meta, allow_unicode=True), encoding="utf-8"
        )

        categories: list[str] = []
        topics: list[dict[str, str]] = []
        _read_meta(article_dir, categories, topics)

        assert topics[0]["title"] == "my-article-dir"
