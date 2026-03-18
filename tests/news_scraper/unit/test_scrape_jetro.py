"""Unit tests for scripts/scrape_jetro.py.

Tests cover the internal helper functions and the main entry point.
HTTP calls and JETRO collection are mocked to avoid real network access.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Make scripts accessible
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))

from scrape_jetro import (
    _cleanup_old_data,
    _create_dated_output_dir,
    _resolve_output_dir,
    _save_articles_json,
    main,
)

# ---------------------------------------------------------------------------
# TestResolveOutputDir
# ---------------------------------------------------------------------------


class TestResolveOutputDir:
    """Tests for _resolve_output_dir function."""

    def test_正常系_指定パスが存在する場合はそのまま返す(self, tmp_path: Path) -> None:
        result = _resolve_output_dir(tmp_path)
        assert result == tmp_path

    def test_正常系_Noneでデフォルトパスを検索する(self, tmp_path: Path) -> None:
        with (
            patch("scrape_jetro.DEFAULT_NAS_OUTPUT", tmp_path / "nonexistent"),
            patch("scrape_jetro.DEFAULT_LOCAL_FALLBACK", tmp_path / "local"),
        ):
            result = _resolve_output_dir(None)
            assert "local" in str(result)

    def test_正常系_NASがマウントされている場合はNASパスを返す(
        self, tmp_path: Path
    ) -> None:
        nas_path = tmp_path / "nas"
        nas_path.mkdir()
        with patch("scrape_jetro.DEFAULT_NAS_OUTPUT", nas_path):
            result = _resolve_output_dir(None)
            assert result == nas_path


# ---------------------------------------------------------------------------
# TestCreateDatedOutputDir
# ---------------------------------------------------------------------------


class TestCreateDatedOutputDir:
    """Tests for _create_dated_output_dir function."""

    def test_正常系_日付サブディレクトリを作成する(self, tmp_path: Path) -> None:
        date = datetime(2026, 3, 18, 12, 0, tzinfo=timezone.utc)
        result = _create_dated_output_dir(tmp_path, date)
        assert result == tmp_path / "2026-03-18"
        assert result.exists()
        assert result.is_dir()

    def test_正常系_既存ディレクトリでもエラーなし(self, tmp_path: Path) -> None:
        date = datetime(2026, 3, 18, tzinfo=timezone.utc)
        existing = tmp_path / "2026-03-18"
        existing.mkdir()
        result = _create_dated_output_dir(tmp_path, date)
        assert result == existing

    def test_正常系_ネストしたディレクトリを作成する(self, tmp_path: Path) -> None:
        date = datetime(2026, 3, 18, tzinfo=timezone.utc)
        nested_base = tmp_path / "subdir" / "output"
        result = _create_dated_output_dir(nested_base, date)
        assert result.exists()


# ---------------------------------------------------------------------------
# TestSaveArticlesJson
# ---------------------------------------------------------------------------


class TestSaveArticlesJson:
    """Tests for _save_articles_json function."""

    def test_正常系_JSONファイルを保存できる(self, tmp_path: Path) -> None:
        articles = [
            {"title": "テスト", "url": "https://jetro.go.jp/1", "source": "jetro"}
        ]
        timestamp = datetime(2026, 3, 18, 12, 30, 45, tzinfo=timezone.utc)
        output_path = _save_articles_json(articles, tmp_path, timestamp)
        assert output_path.exists()
        assert output_path.name == "news_123045.json"

    def test_正常系_保存したJSONが正しい形式(self, tmp_path: Path) -> None:
        articles = [
            {"title": "Article 1", "url": "https://jetro.go.jp/1"},
            {"title": "Article 2", "url": "https://jetro.go.jp/2"},
        ]
        timestamp = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
        output_path = _save_articles_json(articles, tmp_path, timestamp)
        with output_path.open(encoding="utf-8") as f:
            data = json.load(f)
        assert "collected_at" in data
        assert "total_count" in data
        assert data["total_count"] == 2
        assert "news" in data
        assert len(data["news"]) == 2

    def test_正常系_空の記事リストを保存できる(self, tmp_path: Path) -> None:
        timestamp = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
        output_path = _save_articles_json([], tmp_path, timestamp)
        with output_path.open(encoding="utf-8") as f:
            data = json.load(f)
        assert data["total_count"] == 0
        assert data["news"] == []

    def test_正常系_日本語コンテンツを正しく保存できる(self, tmp_path: Path) -> None:
        articles = [{"title": "JETRO記事タイトル", "summary": "ビジネス短信の概要"}]
        timestamp = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
        output_path = _save_articles_json(articles, tmp_path, timestamp)
        with output_path.open(encoding="utf-8") as f:
            data = json.load(f)
        assert data["news"][0]["title"] == "JETRO記事タイトル"


# ---------------------------------------------------------------------------
# TestCleanupOldData
# ---------------------------------------------------------------------------


class TestCleanupOldData:
    """Tests for _cleanup_old_data function."""

    def test_正常系_古いディレクトリを削除する(self, tmp_path: Path) -> None:
        old_dir = tmp_path / "2020-01-01"
        old_dir.mkdir()
        (old_dir / "news_120000.json").write_text("{}")
        deleted = _cleanup_old_data(tmp_path, max_age_days=30)
        assert deleted == 1
        assert not old_dir.exists()

    def test_正常系_新しいディレクトリは削除しない(self, tmp_path: Path) -> None:
        recent_dir = tmp_path / "2026-02-28"
        recent_dir.mkdir()
        deleted = _cleanup_old_data(tmp_path, max_age_days=30)
        assert deleted == 0
        assert recent_dir.exists()

    def test_正常系_存在しないディレクトリでエラーなし(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "nonexistent"
        deleted = _cleanup_old_data(nonexistent, max_age_days=30)
        assert deleted == 0

    def test_正常系_日付形式でないディレクトリはスキップする(
        self, tmp_path: Path
    ) -> None:
        other_dir = tmp_path / "config"
        other_dir.mkdir()
        deleted = _cleanup_old_data(tmp_path, max_age_days=30)
        assert deleted == 0
        assert other_dir.exists()

    def test_正常系_複数の古いディレクトリを削除する(self, tmp_path: Path) -> None:
        for year in [2020, 2021, 2022]:
            old_dir = tmp_path / f"{year}-01-01"
            old_dir.mkdir()
        deleted = _cleanup_old_data(tmp_path, max_age_days=30)
        assert deleted == 3

    def test_正常系_ファイルはスキップする(self, tmp_path: Path) -> None:
        (tmp_path / "2020-01-01.json").write_text("{}")
        deleted = _cleanup_old_data(tmp_path, max_age_days=30)
        assert deleted == 0
        assert (tmp_path / "2020-01-01.json").exists()


# ---------------------------------------------------------------------------
# TestMain
# ---------------------------------------------------------------------------


class TestMain:
    """Tests for main() entry point."""

    @patch("scrape_jetro.collect_news")
    def test_正常系_no_playwrightモードで記事を収集して保存(
        self, mock_collect: MagicMock, tmp_path: Path
    ) -> None:
        """--no-playwright で RSS のみモード動作を確認。"""
        from news_scraper.types import Article

        mock_articles = [
            Article(
                title=f"JETRO記事 {i}",
                url=f"https://www.jetro.go.jp/biznews/2026/03/article{i}.html",
                published=datetime(2026, 3, 18, 9, 0, tzinfo=timezone.utc),
                source="jetro",
                summary=f"記事 {i} の概要",
            )
            for i in range(3)
        ]
        mock_collect.return_value = mock_articles

        with patch(
            "sys.argv",
            [
                "scrape_jetro.py",
                "--no-playwright",
                "--max-articles",
                "5",
                "--output-dir",
                str(tmp_path),
            ],
        ):
            exit_code = main()

        assert exit_code == 0
        mock_collect.assert_called_once()
        # Verify config passed to collect_news
        call_kwargs = mock_collect.call_args
        config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
        assert config is not None
        assert config.use_playwright is False

    @patch("scrape_jetro.collect_news")
    def test_正常系_記事なしで正常終了(
        self, mock_collect: MagicMock, tmp_path: Path
    ) -> None:
        """記事が0件の場合、保存をスキップして正常終了する。"""
        mock_collect.return_value = []

        with patch(
            "sys.argv",
            [
                "scrape_jetro.py",
                "--no-playwright",
                "--output-dir",
                str(tmp_path),
            ],
        ):
            exit_code = main()

        assert exit_code == 0

    @patch("scrape_jetro.collect_news")
    def test_異常系_collect_news例外発生で終了コード1(
        self, mock_collect: MagicMock, tmp_path: Path
    ) -> None:
        """collect_news が例外を送出した場合、終了コード 1 を返す。"""
        mock_collect.side_effect = ConnectionError("Network error")

        with patch(
            "sys.argv",
            [
                "scrape_jetro.py",
                "--no-playwright",
                "--output-dir",
                str(tmp_path),
            ],
        ):
            exit_code = main()

        assert exit_code == 1

    @patch("scrape_jetro.collect_news")
    def test_正常系_cleanup_daysオプションで古いデータを削除(
        self, mock_collect: MagicMock, tmp_path: Path
    ) -> None:
        """--cleanup-days で古いデータ削除が実行される。"""
        mock_collect.return_value = []

        # Create an old directory
        old_dir = tmp_path / "2020-01-01"
        old_dir.mkdir()
        (old_dir / "news_120000.json").write_text("{}")

        with patch(
            "sys.argv",
            [
                "scrape_jetro.py",
                "--no-playwright",
                "--output-dir",
                str(tmp_path),
                "--cleanup-days",
                "30",
            ],
        ):
            exit_code = main()

        assert exit_code == 0
        assert not old_dir.exists()

    @patch("scrape_jetro.collect_news")
    def test_正常系_categoriesオプションが渡される(
        self, mock_collect: MagicMock, tmp_path: Path
    ) -> None:
        """--categories world が collect_news に渡されることを確認。"""
        mock_collect.return_value = []

        with patch(
            "sys.argv",
            [
                "scrape_jetro.py",
                "--categories",
                "world",
                "--output-dir",
                str(tmp_path),
            ],
        ):
            exit_code = main()

        assert exit_code == 0
        call_kwargs = mock_collect.call_args
        categories = call_kwargs.kwargs.get("categories") or call_kwargs[1].get(
            "categories"
        )
        assert categories == ["world"]

    @patch("scrape_jetro.collect_news")
    def test_正常系_regionsオプションが渡される(
        self, mock_collect: MagicMock, tmp_path: Path
    ) -> None:
        """--regions us cn が collect_news に渡されることを確認。"""
        mock_collect.return_value = []

        with patch(
            "sys.argv",
            [
                "scrape_jetro.py",
                "--regions",
                "us",
                "cn",
                "--output-dir",
                str(tmp_path),
            ],
        ):
            exit_code = main()

        assert exit_code == 0
        call_kwargs = mock_collect.call_args
        regions = call_kwargs.kwargs.get("regions") or call_kwargs[1].get("regions")
        assert regions == ["us", "cn"]

    @patch("scrape_jetro.collect_news")
    def test_正常系_JSONファイルが正しい形式で出力される(
        self, mock_collect: MagicMock, tmp_path: Path
    ) -> None:
        """出力ファイルが {YYYY-MM-DD}/news_{HHMMSS}.json 形式であることを確認。"""
        from news_scraper.types import Article

        mock_articles = [
            Article(
                title="テスト記事",
                url="https://www.jetro.go.jp/biznews/2026/03/test.html",
                published=datetime(2026, 3, 18, 9, 0, tzinfo=timezone.utc),
                source="jetro",
            )
        ]
        mock_collect.return_value = mock_articles

        with patch(
            "sys.argv",
            [
                "scrape_jetro.py",
                "--no-playwright",
                "--output-dir",
                str(tmp_path),
            ],
        ):
            exit_code = main()

        assert exit_code == 0
        # Find the dated subdirectory
        subdirs = [d for d in tmp_path.iterdir() if d.is_dir()]
        assert len(subdirs) == 1
        dated_dir = subdirs[0]
        # Check format: YYYY-MM-DD
        assert len(dated_dir.name) == 10
        assert dated_dir.name[4] == "-"
        assert dated_dir.name[7] == "-"
        # Check JSON file: news_HHMMSS.json
        json_files = list(dated_dir.glob("news_*.json"))
        assert len(json_files) == 1
        # Validate JSON content
        with json_files[0].open(encoding="utf-8") as f:
            data = json.load(f)
        assert data["total_count"] == 1
        assert len(data["news"]) == 1

    @patch("scrape_jetro.collect_news")
    def test_正常系_request_delayオプションが設定される(
        self, mock_collect: MagicMock, tmp_path: Path
    ) -> None:
        """--request-delay 3.0 が ScraperConfig に設定されることを確認。"""
        mock_collect.return_value = []

        with patch(
            "sys.argv",
            [
                "scrape_jetro.py",
                "--no-playwright",
                "--request-delay",
                "3.0",
                "--output-dir",
                str(tmp_path),
            ],
        ):
            exit_code = main()

        assert exit_code == 0
        call_kwargs = mock_collect.call_args
        config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
        assert config.request_delay == 3.0
