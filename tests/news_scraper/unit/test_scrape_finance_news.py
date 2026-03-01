"""Unit tests for scripts/scrape_finance_news.py."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Make scripts accessible
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))

from scrape_finance_news import (
    _cleanup_old_data,
    _create_dated_output_dir,
    _resolve_output_dir,
    _save_articles_json,
)


class TestResolveOutputDir:
    """Tests for _resolve_output_dir function."""

    def test_正常系_指定パスが存在する場合はそのまま返す(self, tmp_path: Path) -> None:
        """_resolve_output_dir returns requested path when specified."""
        result = _resolve_output_dir(tmp_path)
        assert result == tmp_path

    def test_正常系_Noneでデフォルトパスを検索する(self, tmp_path: Path) -> None:
        """_resolve_output_dir falls back to local when NAS not mounted."""
        with (
            patch("scrape_finance_news.DEFAULT_NAS_OUTPUT", tmp_path / "nonexistent"),
            patch("scrape_finance_news.DEFAULT_LOCAL_FALLBACK", tmp_path / "local"),
        ):
            result = _resolve_output_dir(None)
            assert "local" in str(result)

    def test_正常系_NASがマウントされている場合はNASパスを返す(
        self, tmp_path: Path
    ) -> None:
        """_resolve_output_dir returns NAS path when NAS is mounted."""
        nas_path = tmp_path / "nas"
        nas_path.mkdir()
        with patch("scrape_finance_news.DEFAULT_NAS_OUTPUT", nas_path):
            result = _resolve_output_dir(None)
            assert result == nas_path


class TestCreateDatedOutputDir:
    """Tests for _create_dated_output_dir function."""

    def test_正常系_日付サブディレクトリを作成する(self, tmp_path: Path) -> None:
        """_create_dated_output_dir creates a dated subdirectory."""
        date = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
        result = _create_dated_output_dir(tmp_path, date)
        assert result == tmp_path / "2026-03-01"
        assert result.exists()
        assert result.is_dir()

    def test_正常系_既存ディレクトリでもエラーなし(self, tmp_path: Path) -> None:
        """_create_dated_output_dir succeeds even if directory exists."""
        date = datetime(2026, 3, 1, tzinfo=timezone.utc)
        existing = tmp_path / "2026-03-01"
        existing.mkdir()
        result = _create_dated_output_dir(tmp_path, date)
        assert result == existing

    def test_正常系_ネストしたディレクトリを作成する(self, tmp_path: Path) -> None:
        """_create_dated_output_dir creates nested directories."""
        date = datetime(2026, 3, 1, tzinfo=timezone.utc)
        nested_base = tmp_path / "subdir" / "output"
        result = _create_dated_output_dir(nested_base, date)
        assert result.exists()


class TestSaveArticlesJson:
    """Tests for _save_articles_json function."""

    def test_正常系_JSONファイルを保存できる(self, tmp_path: Path) -> None:
        """_save_articles_json saves articles to JSON file."""
        articles = [{"title": "Test", "url": "https://example.com/1", "source": "cnbc"}]
        timestamp = datetime(2026, 3, 1, 12, 30, 45, tzinfo=timezone.utc)
        output_path = _save_articles_json(articles, tmp_path, timestamp)

        assert output_path.exists()
        assert output_path.name == "news_123045.json"

    def test_正常系_保存したJSONが正しい形式(self, tmp_path: Path) -> None:
        """_save_articles_json saves valid JSON with correct structure."""
        articles = [
            {"title": "Article 1", "url": "https://cnbc.com/1"},
            {"title": "Article 2", "url": "https://cnbc.com/2"},
        ]
        timestamp = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        output_path = _save_articles_json(articles, tmp_path, timestamp)

        with output_path.open(encoding="utf-8") as f:
            data = json.load(f)

        assert "collected_at" in data
        assert "total_count" in data
        assert data["total_count"] == 2
        assert "news" in data
        assert len(data["news"]) == 2

    def test_正常系_空の記事リストを保存できる(self, tmp_path: Path) -> None:
        """_save_articles_json saves empty article list."""
        timestamp = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        output_path = _save_articles_json([], tmp_path, timestamp)
        with output_path.open(encoding="utf-8") as f:
            data = json.load(f)
        assert data["total_count"] == 0
        assert data["news"] == []

    def test_正常系_日本語コンテンツを正しく保存できる(self, tmp_path: Path) -> None:
        """_save_articles_json handles Japanese content correctly."""
        articles = [{"title": "日経平均が上昇", "summary": "東京株式市場で上昇"}]
        timestamp = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        output_path = _save_articles_json(articles, tmp_path, timestamp)
        with output_path.open(encoding="utf-8") as f:
            data = json.load(f)
        assert data["news"][0]["title"] == "日経平均が上昇"


class TestCleanupOldData:
    """Tests for _cleanup_old_data function."""

    def test_正常系_古いディレクトリを削除する(self, tmp_path: Path) -> None:
        """_cleanup_old_data deletes directories older than max_age_days."""
        # Create an old directory (2000 days ago equivalent)
        old_dir = tmp_path / "2020-01-01"
        old_dir.mkdir()
        (old_dir / "news_120000.json").write_text("{}")

        deleted = _cleanup_old_data(tmp_path, max_age_days=30)
        assert deleted == 1
        assert not old_dir.exists()

    def test_正常系_新しいディレクトリは削除しない(self, tmp_path: Path) -> None:
        """_cleanup_old_data keeps directories newer than max_age_days."""
        # Create a recent directory
        recent_dir = tmp_path / "2026-02-28"
        recent_dir.mkdir()

        deleted = _cleanup_old_data(tmp_path, max_age_days=30)
        assert deleted == 0
        assert recent_dir.exists()

    def test_正常系_存在しないディレクトリでエラーなし(self, tmp_path: Path) -> None:
        """_cleanup_old_data handles non-existent base directory gracefully."""
        nonexistent = tmp_path / "nonexistent"
        deleted = _cleanup_old_data(nonexistent, max_age_days=30)
        assert deleted == 0

    def test_正常系_日付形式でないディレクトリはスキップする(
        self, tmp_path: Path
    ) -> None:
        """_cleanup_old_data skips non-dated directories."""
        # Create a non-dated directory
        other_dir = tmp_path / "config"
        other_dir.mkdir()

        deleted = _cleanup_old_data(tmp_path, max_age_days=30)
        assert deleted == 0
        assert other_dir.exists()

    def test_正常系_複数の古いディレクトリを削除する(self, tmp_path: Path) -> None:
        """_cleanup_old_data deletes multiple old directories."""
        for year in [2020, 2021, 2022]:
            old_dir = tmp_path / f"{year}-01-01"
            old_dir.mkdir()

        deleted = _cleanup_old_data(tmp_path, max_age_days=30)
        assert deleted == 3

    def test_正常系_ファイルはスキップする(self, tmp_path: Path) -> None:
        """_cleanup_old_data skips files (only processes directories)."""
        # Create a file that looks like a date
        (tmp_path / "2020-01-01.json").write_text("{}")

        deleted = _cleanup_old_data(tmp_path, max_age_days=30)
        assert deleted == 0
        assert (tmp_path / "2020-01-01.json").exists()
