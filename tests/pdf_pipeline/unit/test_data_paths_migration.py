"""Tests for data_paths migration in the pdf_pipeline package.

Verifies that hardcoded data paths in pdf_pipeline have been replaced
with data_paths.get_path() calls.

Target files:
- src/pdf_pipeline/cli/main.py (DEFAULT_OUTPUT_DIR, DEFAULT_CONFIG_PATH)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

import pytest

from data_paths import _reset_cache, get_path


@pytest.fixture(autouse=True)
def _clear_data_paths_cache() -> Iterator[None]:
    """各テストの前後でdata_pathsのlru_cacheをクリアする。"""
    _reset_cache()
    yield
    _reset_cache()


class TestCliMainDataPathsMigration:
    """pdf_pipeline.cli.main のハードコードパスが data_paths に移行されていることを検証."""

    def test_正常系_DEFAULT_OUTPUT_DIRがget_pathを使用(self) -> None:
        """cli.main.DEFAULT_OUTPUT_DIR が get_path() 経由で解決される."""
        from pdf_pipeline.cli.main import DEFAULT_OUTPUT_DIR

        expected = get_path("processed")
        assert expected == DEFAULT_OUTPUT_DIR

    def test_正常系_DEFAULT_OUTPUT_DIRはPath型(self) -> None:
        """cli.main.DEFAULT_OUTPUT_DIR が Path 型であることを確認."""
        from pdf_pipeline.cli.main import DEFAULT_OUTPUT_DIR

        assert isinstance(DEFAULT_OUTPUT_DIR, Path)

    def test_正常系_DEFAULT_CONFIG_PATHがget_pathを使用(self) -> None:
        """cli.main.DEFAULT_CONFIG_PATH が get_path() 経由で解決される."""
        from pdf_pipeline.cli.main import DEFAULT_CONFIG_PATH

        expected = get_path("config/pdf-pipeline-config.yaml")
        assert expected == DEFAULT_CONFIG_PATH

    def test_正常系_DEFAULT_CONFIG_PATHはPath型(self) -> None:
        """cli.main.DEFAULT_CONFIG_PATH が Path 型であることを確認."""
        from pdf_pipeline.cli.main import DEFAULT_CONFIG_PATH

        assert isinstance(DEFAULT_CONFIG_PATH, Path)
