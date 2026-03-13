"""Tests for data_paths migration in the report_scraper package.

Verifies that hardcoded data paths in report_scraper have been replaced
with data_paths.get_path() calls.

Target files:
- src/report_scraper/storage/pdf_store.py (DEFAULT_PDF_DIR)
"""

from __future__ import annotations

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


class TestPdfStoreDataPathsMigration:
    """report_scraper.storage.pdf_store のハードコードパスが data_paths に移行されていることを検証."""

    def test_正常系_DEFAULT_PDF_DIRがget_pathを使用(self) -> None:
        """pdf_store.DEFAULT_PDF_DIR が get_path() 経由で解決される."""
        from report_scraper.storage.pdf_store import DEFAULT_PDF_DIR

        expected = str(get_path("raw/report-scraper/pdfs"))
        assert expected == DEFAULT_PDF_DIR

    def test_正常系_DEFAULT_PDF_DIRはstr型(self) -> None:
        """pdf_store.DEFAULT_PDF_DIR が str 型であることを確認."""
        from report_scraper.storage.pdf_store import DEFAULT_PDF_DIR

        assert isinstance(DEFAULT_PDF_DIR, str)
