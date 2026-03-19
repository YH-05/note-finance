"""Unit tests for scripts/scrape_finance_news.py."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Make scripts accessible
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))

from scrape_finance_news import (
    DEFAULT_SOURCES,
    _cleanup_old_data,
    _create_dated_output_dir,
    _parse_args,
    _resolve_output_dir,
    _save_articles_json,
    main,
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


class TestDefaultSources:
    """Tests for DEFAULT_SOURCES constant."""

    def test_正常系_デフォルトソースはcnbcのみ(self) -> None:
        """DEFAULT_SOURCES should be ['cnbc'] (nasdaq excluded due to 404)."""
        assert DEFAULT_SOURCES == ["cnbc"]


class TestParseArgs:
    """Tests for _parse_args function and CLI choices."""

    ALL_SOURCES: ClassVar[list[str]] = [
        "cnbc",
        "nasdaq",
        "kabutan",
        "reuters_jp",
        "minkabu",
        "jetro",
    ]

    def test_正常系_全6ソースがchoicesとして受け付けられる(self) -> None:
        """--sources should accept all 6 sources."""
        for source in self.ALL_SOURCES:
            with patch("sys.argv", ["scrape_finance_news.py", "--sources", source]):
                args = _parse_args()
                assert args.sources == [source]

    def test_正常系_複数ソースを同時指定できる(self) -> None:
        """--sources should accept multiple sources at once."""
        with patch(
            "sys.argv",
            ["scrape_finance_news.py", "--sources", *self.ALL_SOURCES],
        ):
            args = _parse_args()
            assert set(args.sources) == set(self.ALL_SOURCES)

    def test_異常系_無効なソースでエラーになる(self) -> None:
        """--sources should reject invalid source names."""
        with (
            patch("sys.argv", ["scrape_finance_news.py", "--sources", "invalid"]),
            pytest.raises(SystemExit),
        ):
            _parse_args()

    def test_正常系_デフォルトソースが使用される(self) -> None:
        """Default sources should be used when --sources is not specified."""
        with patch("sys.argv", ["scrape_finance_news.py"]):
            args = _parse_args()
            assert args.sources == ["cnbc"]


class TestJetroCLIArgs:
    """Tests for JETRO-specific CLI arguments."""

    def test_正常系_jetro_categoriesを指定できる(self) -> None:
        """--jetro-categories accepts category values."""
        with patch(
            "sys.argv",
            ["scrape_finance_news.py", "--jetro-categories", "world", "theme"],
        ):
            args = _parse_args()
            assert args.jetro_categories == ["world", "theme"]

    def test_正常系_jetro_categoriesのデフォルトはNone(self) -> None:
        """--jetro-categories defaults to None."""
        with patch("sys.argv", ["scrape_finance_news.py"]):
            args = _parse_args()
            assert args.jetro_categories is None

    def test_正常系_jetro_regionsをJSON形式で指定できる(self) -> None:
        """--jetro-regions accepts JSON string."""
        regions_json = '{"asia": ["cn", "kr"]}'
        with patch(
            "sys.argv",
            ["scrape_finance_news.py", "--jetro-regions", regions_json],
        ):
            args = _parse_args()
            assert args.jetro_regions == regions_json

    def test_正常系_jetro_regionsのデフォルトはNone(self) -> None:
        """--jetro-regions defaults to None."""
        with patch("sys.argv", ["scrape_finance_news.py"]):
            args = _parse_args()
            assert args.jetro_regions is None

    def test_正常系_jetro_archive_pagesを指定できる(self) -> None:
        """--jetro-archive-pages accepts integer value."""
        with patch(
            "sys.argv",
            ["scrape_finance_news.py", "--jetro-archive-pages", "3"],
        ):
            args = _parse_args()
            assert args.jetro_archive_pages == 3

    def test_正常系_jetro_archive_pagesのデフォルトは0(self) -> None:
        """--jetro-archive-pages defaults to 0."""
        with patch("sys.argv", ["scrape_finance_news.py"]):
            args = _parse_args()
            assert args.jetro_archive_pages == 0

    def test_正常系_use_playwrightを指定できる(self) -> None:
        """--use-playwright flag can be set."""
        with patch(
            "sys.argv",
            ["scrape_finance_news.py", "--use-playwright"],
        ):
            args = _parse_args()
            assert args.use_playwright is True

    def test_正常系_use_playwrightのデフォルトはFalse(self) -> None:
        """--use-playwright defaults to False."""
        with patch("sys.argv", ["scrape_finance_news.py"]):
            args = _parse_args()
            assert args.use_playwright is False


class TestMainAsyncCall:
    """Tests for main() function async/sync handling."""

    def test_正常系_asyncio_runでcollect_financial_newsを呼び出す(
        self, tmp_path: Path
    ) -> None:
        """main() should use asyncio.run() to call async collect_financial_news."""
        mock_df = MagicMock()
        mock_df.empty = True
        mock_df.__len__ = lambda self: 0

        with (
            patch(
                "sys.argv", ["scrape_finance_news.py", "--output-dir", str(tmp_path)]
            ),
            patch(
                "scrape_finance_news.collect_financial_news",
                new_callable=AsyncMock,
                return_value=mock_df,
            ) as mock_collect,
            patch("scrape_finance_news.structlog"),
        ):
            result = main()
            # asyncio.run should have been used, so the coroutine should be awaited
            mock_collect.assert_called_once()
            assert result == 0

    def test_正常系_全6ソースがargparse_choicesとして定義されている(self) -> None:
        """All 6 sources should be defined in --sources choices."""
        expected_sources = ["cnbc", "nasdaq", "kabutan", "reuters_jp", "minkabu", "jetro"]
        for source in expected_sources:
            with patch("sys.argv", ["scrape_finance_news.py", "--sources", source]):
                parsed = _parse_args()
                assert source in parsed.sources

    def test_正常系_main_jetro_regions不正JSONでエラー(self) -> None:
        """main() returns 1 when --jetro-regions receives invalid JSON."""
        with (
            patch("sys.argv", [
                "scrape_finance_news.py",
                "--sources", "jetro",
                "--jetro-regions", "invalid{json",
            ]),
            patch("scrape_finance_news.structlog"),
        ):
            result = main()
            assert result == 1

    def test_正常系_main_jetro_regions不正スキーマでエラー(self) -> None:
        """main() returns 1 when --jetro-regions has invalid schema."""
        with (
            patch("sys.argv", [
                "scrape_finance_news.py",
                "--sources", "jetro",
                "--jetro-regions", '{"asia": "not_a_list"}',
            ]),
            patch("scrape_finance_news.structlog"),
        ):
            result = main()
            assert result == 1
