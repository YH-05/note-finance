"""Unit tests for data_pipeline.storage.raw_store."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest

from data_pipeline.collectors.base import CollectedItem, CollectionResult
from data_pipeline.storage.raw_store import RawStore, SaveResult, _url_hash

if TYPE_CHECKING:
    from pathlib import Path


def _make_item(
    source_id: str = "test",
    url: str = "https://example.com/article/1",
    title: str = "Test Article",
    raw_text: str = "Article content.",
    **kwargs,
) -> CollectedItem:
    """テスト用 CollectedItem を生成するヘルパー."""
    return CollectedItem(
        source_id=source_id,
        url=url,
        title=title,
        raw_text=raw_text,
        collection_method="rss",
        **kwargs,
    )


class TestUrlHash:
    """_url_hash のテスト."""

    def test_正常系_同じURLは同じハッシュ(self) -> None:
        h1 = _url_hash("https://example.com/a")
        h2 = _url_hash("https://example.com/a")
        assert h1 == h2

    def test_正常系_異なるURLは異なるハッシュ(self) -> None:
        h1 = _url_hash("https://example.com/a")
        h2 = _url_hash("https://example.com/b")
        assert h1 != h2

    def test_正常系_ハッシュ長は16文字(self) -> None:
        h = _url_hash("https://example.com")
        assert len(h) == 16


class TestRawStoreSaveItem:
    """RawStore.save_item のテスト."""

    def test_正常系_アイテムを保存できる(self, tmp_path: Path) -> None:
        store = RawStore(base_dir=tmp_path)
        item = _make_item()
        outcome = store.save_item(item)

        assert outcome == "saved"
        # ファイルが作成されていることを確認
        json_files = list(tmp_path.rglob("*.json"))
        assert len(json_files) == 1

    def test_正常系_重複保存はduplicate(self, tmp_path: Path) -> None:
        store = RawStore(base_dir=tmp_path)
        item = _make_item()

        assert store.save_item(item) == "saved"
        assert store.save_item(item) == "duplicate"

    def test_正常系_空テキストはempty(self, tmp_path: Path) -> None:
        store = RawStore(base_dir=tmp_path)
        item = _make_item(raw_text="")
        assert store.save_item(item) == "empty"

    def test_正常系_空白のみのテキストもempty(self, tmp_path: Path) -> None:
        store = RawStore(base_dir=tmp_path)
        item = _make_item(raw_text="   \n  ")
        assert store.save_item(item) == "empty"

    def test_正常系_skip_empty_falseなら空テキストも保存(self, tmp_path: Path) -> None:
        store = RawStore(base_dir=tmp_path, skip_empty=False)
        item = _make_item(raw_text="")
        assert store.save_item(item) == "saved"

    def test_正常系_異なるURLは別ファイル(self, tmp_path: Path) -> None:
        store = RawStore(base_dir=tmp_path)
        item1 = _make_item(url="https://example.com/a")
        item2 = _make_item(url="https://example.com/b")

        store.save_item(item1)
        store.save_item(item2)

        json_files = list(tmp_path.rglob("*.json"))
        assert len(json_files) == 2


class TestRawStoreSave:
    """RawStore.save (バッチ) のテスト."""

    def test_正常系_CollectionResultを一括保存(self, tmp_path: Path) -> None:
        store = RawStore(base_dir=tmp_path)
        result = CollectionResult(source_id="test")
        result.items = [
            _make_item(url="https://example.com/1"),
            _make_item(url="https://example.com/2"),
            _make_item(url="https://example.com/3"),
        ]

        save_result = store.save(result)
        assert isinstance(save_result, SaveResult)
        assert save_result.saved == 3
        assert save_result.skipped_duplicate == 0
        assert save_result.skipped_empty == 0

    def test_正常系_空テキストと重複が混在(self, tmp_path: Path) -> None:
        store = RawStore(base_dir=tmp_path)

        # 最初のバッチ
        result1 = CollectionResult(source_id="test")
        result1.items = [
            _make_item(url="https://example.com/1"),
            _make_item(url="https://example.com/2", raw_text=""),
        ]
        save1 = store.save(result1)
        assert save1.saved == 1
        assert save1.skipped_empty == 1

        # 2回目のバッチ（重複あり）
        result2 = CollectionResult(source_id="test")
        result2.items = [
            _make_item(url="https://example.com/1"),  # 重複
            _make_item(url="https://example.com/3"),  # 新規
        ]
        save2 = store.save(result2)
        assert save2.saved == 1
        assert save2.skipped_duplicate == 1


class TestRawStoreExists:
    """RawStore.exists のテスト."""

    def test_正常系_保存済みURLはTrue(self, tmp_path: Path) -> None:
        store = RawStore(base_dir=tmp_path)
        item = _make_item(url="https://example.com/exists")
        store.save_item(item)

        assert store.exists("https://example.com/exists", "test") is True

    def test_正常系_未保存URLはFalse(self, tmp_path: Path) -> None:
        store = RawStore(base_dir=tmp_path)
        assert store.exists("https://example.com/nope", "test") is False

    def test_正常系_日付指定で検索(self, tmp_path: Path) -> None:
        store = RawStore(base_dir=tmp_path)
        item = _make_item(url="https://example.com/dated")
        store.save_item(item)

        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        assert store.exists("https://example.com/dated", "test", date=today) is True
        assert (
            store.exists("https://example.com/dated", "test", date="2020-01-01")
            is False
        )


class TestRawStoreLoad:
    """RawStore.load_items のテスト."""

    def test_正常系_保存したアイテムをロードできる(self, tmp_path: Path) -> None:
        store = RawStore(base_dir=tmp_path)
        original = _make_item(
            url="https://example.com/load-test",
            title="Load Test",
            raw_text="Content to load.",
        )
        store.save_item(original)

        items = store.load_items("test")
        assert len(items) == 1
        assert items[0].url == "https://example.com/load-test"
        assert items[0].title == "Load Test"
        assert items[0].raw_text == "Content to load."

    def test_正常系_日付指定でロード(self, tmp_path: Path) -> None:
        store = RawStore(base_dir=tmp_path)
        store.save_item(_make_item(url="https://example.com/1"))

        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        items = store.load_items("test", date=today)
        assert len(items) == 1

        items_empty = store.load_items("test", date="2020-01-01")
        assert len(items_empty) == 0

    def test_正常系_存在しないソースIDで空リスト(self, tmp_path: Path) -> None:
        store = RawStore(base_dir=tmp_path)
        assert store.load_items("nonexistent") == []


class TestRawStoreSaveText:
    """RawStore.save_text / save_many_texts のテスト."""

    def test_正常系_save_textで直接保存(self, tmp_path: Path) -> None:
        store = RawStore(base_dir=tmp_path)
        outcome = store.save_text(
            source_id="jp-finance",
            url="https://www.fsa.go.jp/news/article.html",
            title="金融庁ニュース",
            raw_text="本文テキスト",
            collection_method="rss",
        )
        assert outcome == "saved"

        # ロードして確認
        items = store.load_items("jp-finance")
        assert len(items) == 1
        assert items[0].title == "金融庁ニュース"
        assert items[0].raw_text == "本文テキスト"

    def test_正常系_save_textで重複排除(self, tmp_path: Path) -> None:
        store = RawStore(base_dir=tmp_path)
        store.save_text(
            source_id="test",
            url="https://example.com/dup",
            title="Test",
            raw_text="content",
            collection_method="rss",
        )
        outcome = store.save_text(
            source_id="test",
            url="https://example.com/dup",
            title="Test",
            raw_text="content",
            collection_method="rss",
        )
        assert outcome == "duplicate"

    def test_正常系_save_many_textsで一括保存(self, tmp_path: Path) -> None:
        store = RawStore(base_dir=tmp_path)
        items = [
            {"url": "https://a.com/1", "title": "A1", "raw_text": "Text 1"},
            {"url": "https://a.com/2", "title": "A2", "raw_text": "Text 2"},
            {"url": "https://a.com/3", "title": "A3", "text": "Text 3"},  # textキー
        ]
        result = store.save_many_texts(
            items,
            source_id="test",
            collection_method="scraping",
        )
        assert result.saved == 3
        assert result.skipped_duplicate == 0

    def test_正常系_save_many_textsで空テキストスキップ(self, tmp_path: Path) -> None:
        store = RawStore(base_dir=tmp_path)
        items = [
            {"url": "https://a.com/1", "title": "A1", "raw_text": "Text"},
            {"url": "https://a.com/2", "title": "A2", "raw_text": ""},
        ]
        result = store.save_many_texts(
            items,
            source_id="test",
            collection_method="rss",
        )
        assert result.saved == 1
        assert result.skipped_empty == 1


class TestRawStoreMetadata:
    """RawStore のメタデータ系メソッドのテスト."""

    @pytest.fixture
    def populated_store(self, tmp_path: Path) -> RawStore:
        """データが入ったストア."""
        store = RawStore(base_dir=tmp_path)
        store.save_item(_make_item(source_id="src-a", url="https://a.com/1"))
        store.save_item(_make_item(source_id="src-a", url="https://a.com/2"))
        store.save_item(_make_item(source_id="src-b", url="https://b.com/1"))
        return store

    def test_正常系_ソース一覧(self, populated_store: RawStore) -> None:
        sources = populated_store.list_sources()
        assert sources == ["src-a", "src-b"]

    def test_正常系_日付一覧(self, populated_store: RawStore) -> None:
        dates = populated_store.list_dates("src-a")
        assert len(dates) == 1
        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        assert dates[0] == today

    def test_正常系_件数カウント(self, populated_store: RawStore) -> None:
        assert populated_store.count("src-a") == 2
        assert populated_store.count("src-b") == 1
        assert populated_store.count("nonexistent") == 0

    def test_正常系_空ストアのメタデータ(self, tmp_path: Path) -> None:
        store = RawStore(base_dir=tmp_path)
        assert store.list_sources() == []
        assert store.list_dates("any") == []
        assert store.count("any") == 0
