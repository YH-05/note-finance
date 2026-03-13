"""Tests for data_paths migration in the news package.

Verifies that hardcoded data paths in the news package have been replaced
with data_paths.get_path() calls (Issue #82).

Target files:
- src/news/config/models.py (export_dir default, DEFAULT_CONFIG_PATH)
- src/news/sources/yfinance/macro.py (DEFAULT_KEYWORDS_FILE)
- src/news/scripts/finance_news_workflow.py (DEFAULT_CONFIG_PATH)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator
from pathlib import Path

import pytest

from data_paths import _reset_cache, get_path


@pytest.fixture(autouse=True)
def _clear_data_paths_cache() -> Iterator[None]:
    """各テストの前後でdata_pathsのlru_cacheをクリアする。"""
    _reset_cache()
    yield
    _reset_cache()


class TestModelsDataPathsMigration:
    """news.config.models のハードコードパスが data_paths に移行されていることを検証."""

    def test_正常系_PublishingConfigのexport_dirがget_pathを使用(self) -> None:
        """PublishingConfig.export_dir のデフォルト値が get_path() 経由で解決される."""
        from news.config.models import PublishingConfig

        config = PublishingConfig()

        expected_path = str(get_path("exports/news-workflow"))
        assert config.export_dir == expected_path

    def test_正常系_PublishingConfigのexport_dirはstr型(self) -> None:
        """PublishingConfig.export_dir が str 型であることを確認."""
        from news.config.models import PublishingConfig

        config = PublishingConfig()

        assert isinstance(config.export_dir, str)

    def test_正常系_PublishingConfigのexport_dirをカスタム値で上書きできる(
        self,
    ) -> None:
        """PublishingConfig.export_dir はカスタム値で上書きできる."""
        from news.config.models import PublishingConfig

        config = PublishingConfig(export_dir="/custom/export/path")

        assert config.export_dir == "/custom/export/path"

    def test_正常系_DEFAULT_CONFIG_PATHがget_pathを使用(self) -> None:
        """models.DEFAULT_CONFIG_PATH が get_path() 経由で解決される."""
        from news.config.models import DEFAULT_CONFIG_PATH

        expected = get_path("config/news_sources.yaml")
        assert expected == DEFAULT_CONFIG_PATH

    def test_正常系_DEFAULT_CONFIG_PATHはPath型(self) -> None:
        """models.DEFAULT_CONFIG_PATH が Path 型であることを確認."""
        from news.config.models import DEFAULT_CONFIG_PATH

        assert isinstance(DEFAULT_CONFIG_PATH, Path)


class TestMacroDataPathsMigration:
    """news.sources.yfinance.macro のハードコードパスが data_paths に移行されていることを検証."""

    def test_正常系_DEFAULT_KEYWORDS_FILEがget_pathを使用(self) -> None:
        """macro.DEFAULT_KEYWORDS_FILE が get_path() 経由で解決される."""
        from news.sources.yfinance.macro import DEFAULT_KEYWORDS_FILE

        expected = get_path("config/news_search_keywords.yaml")
        assert expected == DEFAULT_KEYWORDS_FILE

    def test_正常系_DEFAULT_KEYWORDS_FILEはPath型(self) -> None:
        """macro.DEFAULT_KEYWORDS_FILE が Path 型であることを確認."""
        from news.sources.yfinance.macro import DEFAULT_KEYWORDS_FILE

        assert isinstance(DEFAULT_KEYWORDS_FILE, Path)


class TestWorkflowDataPathsMigration:
    """news.scripts.finance_news_workflow のハードコードパスが data_paths に移行されていることを検証."""

    def test_正常系_DEFAULT_CONFIG_PATHがget_pathを使用(self) -> None:
        """workflow.DEFAULT_CONFIG_PATH が get_path() 経由で解決される."""
        from news.scripts.finance_news_workflow import DEFAULT_CONFIG_PATH

        expected = get_path("config/news-collection-config.yaml")
        assert expected == DEFAULT_CONFIG_PATH

    def test_正常系_DEFAULT_CONFIG_PATHはPath型(self) -> None:
        """workflow.DEFAULT_CONFIG_PATH が Path 型であることを確認."""
        from news.scripts.finance_news_workflow import DEFAULT_CONFIG_PATH

        assert isinstance(DEFAULT_CONFIG_PATH, Path)
