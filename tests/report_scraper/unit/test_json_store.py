"""Tests for report_scraper.storage.json_store module.

Tests cover:
- Index load/save with caching
- Index load with corrupted/missing files (OSError handling)
- save_text source_key validation
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from report_scraper.storage.json_store import JsonReportStore


class TestJsonReportStoreInit:
    """Tests for JsonReportStore initialization."""

    def test_正常系_ディレクトリが作成される(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "reports"
        store = JsonReportStore(data_dir)
        assert data_dir.exists()
        assert (data_dir / "runs").exists()
        assert (data_dir / "text").exists()
        assert store.data_dir == data_dir


class TestJsonReportStoreLoadIndex:
    """Tests for JsonReportStore.load_index."""

    def test_正常系_インデックスファイルがない場合空を返す(
        self, tmp_path: Path
    ) -> None:
        store = JsonReportStore(tmp_path / "reports")
        index = store.load_index()
        assert index == {"reports": {}}

    def test_正常系_インデックスファイルを正しく読み込む(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "reports"
        store = JsonReportStore(data_dir)
        expected = {"reports": {"https://example.com": {"title": "Test"}}}
        (data_dir / "index.json").write_text(json.dumps(expected), encoding="utf-8")
        # Invalidate cache
        store._index_cache = None
        index = store.load_index()
        assert index == expected

    def test_正常系_キャッシュから返却される(self, tmp_path: Path) -> None:
        store = JsonReportStore(tmp_path / "reports")
        first = store.load_index()
        second = store.load_index()
        assert first is second  # Same object (cached)

    def test_異常系_不正JSONで空インデックスを返す(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "reports"
        store = JsonReportStore(data_dir)
        (data_dir / "index.json").write_text("not valid json", encoding="utf-8")
        store._index_cache = None
        index = store.load_index()
        assert index == {"reports": {}}

    def test_異常系_reportsキーがない構造で空インデックスを返す(
        self, tmp_path: Path
    ) -> None:
        data_dir = tmp_path / "reports"
        store = JsonReportStore(data_dir)
        (data_dir / "index.json").write_text(
            json.dumps({"other": "data"}), encoding="utf-8"
        )
        store._index_cache = None
        index = store.load_index()
        assert index == {"reports": {}}


class TestJsonReportStoreSaveIndex:
    """Tests for JsonReportStore.save_index."""

    def test_正常系_インデックスを保存して再読み込みできる(
        self, tmp_path: Path
    ) -> None:
        store = JsonReportStore(tmp_path / "reports")
        expected = {"reports": {"https://example.com": {"title": "T"}}}
        store.save_index(expected)

        # Invalidate cache and reload
        store._index_cache = None
        loaded = store.load_index()
        assert loaded == expected

    def test_正常系_保存後にキャッシュが更新される(self, tmp_path: Path) -> None:
        store = JsonReportStore(tmp_path / "reports")
        data = {"reports": {"url": {"title": "X"}}}
        store.save_index(data)
        assert store._index_cache is data


class TestJsonReportStoreIsKnownUrl:
    """Tests for JsonReportStore.is_known_url."""

    def test_正常系_既知URLでTrue(self, tmp_path: Path) -> None:
        store = JsonReportStore(tmp_path / "reports")
        store.save_index({"reports": {"https://example.com": {"title": "T"}}})
        assert store.is_known_url("https://example.com") is True

    def test_正常系_未知URLでFalse(self, tmp_path: Path) -> None:
        store = JsonReportStore(tmp_path / "reports")
        assert store.is_known_url("https://unknown.com") is False


class TestJsonReportStoreSaveText:
    """Tests for JsonReportStore.save_text."""

    def test_正常系_テキストが保存される(self, tmp_path: Path) -> None:
        store = JsonReportStore(tmp_path / "reports")
        report = MagicMock()
        report.metadata.url = "https://example.com/article"
        report.metadata.source_key = "test_source"
        report.content.text = "Some extracted text"
        report.content.length = 19

        store.save_text(report)

        text_dir = tmp_path / "reports" / "text" / "test_source"
        assert text_dir.exists()
        files = list(text_dir.glob("*.txt"))
        assert len(files) == 1
        assert files[0].read_text(encoding="utf-8") == "Some extracted text"

    def test_正常系_コンテンツがNoneの場合何もしない(self, tmp_path: Path) -> None:
        store = JsonReportStore(tmp_path / "reports")
        report = MagicMock()
        report.content = None
        report.metadata.url = "https://example.com"
        store.save_text(report)
        # No error, no files created
        text_dir = tmp_path / "reports" / "text"
        assert list(text_dir.iterdir()) == []

    def test_異常系_不正source_keyでValueError(self, tmp_path: Path) -> None:
        store = JsonReportStore(tmp_path / "reports")
        report = MagicMock()
        report.metadata.url = "https://example.com"
        report.metadata.source_key = "../../../etc"
        report.content.text = "text"
        report.content.length = 4

        with pytest.raises(ValueError, match="Invalid source_key"):
            store.save_text(report)
