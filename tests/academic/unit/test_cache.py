"""academic.cache の単体テスト.

スタンドアロン SQLiteCache とキャッシュキー生成のテスト。
note-finance 移植版: quants の create_persistent_cache ラッパーではなく
スタンドアロン SQLiteCache を直接テストする。
"""

from __future__ import annotations

import time

import pytest

from academic.cache import SQLiteCache, make_cache_key


class TestMakeCacheKey:
    """make_cache_key() のテスト."""

    def test_正常系_キャッシュキーが正しい形式で生成される(self) -> None:
        key = make_cache_key("2301.00001")
        assert key == "academic:paper:2301.00001"

    def test_正常系_異なるIDで異なるキーが生成される(self) -> None:
        key1 = make_cache_key("2301.00001")
        key2 = make_cache_key("2301.00002")
        assert key1 != key2

    def test_正常系_バージョン付きIDでもキーが生成される(self) -> None:
        key = make_cache_key("2301.00001v2")
        assert key == "academic:paper:2301.00001v2"


class TestSQLiteCache:
    """SQLiteCache の単体テスト."""

    @pytest.fixture
    def cache(self, tmp_path: object) -> SQLiteCache:
        """テスト用の一時 SQLiteCache を生成するフィクスチャ."""
        db_path = str(tmp_path) + "/test_cache.db"  # type: ignore[operator]
        return SQLiteCache(db_path=db_path, ttl_seconds=60, max_entries=10)

    def test_正常系_setとgetで値を取得できる(self, cache: SQLiteCache) -> None:
        cache.set("key1", {"title": "Test Paper"})
        result = cache.get("key1")

        assert result is not None
        assert result["title"] == "Test Paper"

    def test_正常系_存在しないキーでNoneが返る(self, cache: SQLiteCache) -> None:
        result = cache.get("nonexistent")

        assert result is None

    def test_正常系_TTL超過でNoneが返る(self, tmp_path: object) -> None:
        db_path = str(tmp_path) + "/ttl_test.db"  # type: ignore[operator]
        cache = SQLiteCache(db_path=db_path, ttl_seconds=0, max_entries=10)

        cache.set("key1", {"data": "value"})
        time.sleep(0.01)
        result = cache.get("key1")

        assert result is None

    def test_正常系_上書きで値が更新される(self, cache: SQLiteCache) -> None:
        cache.set("key1", {"v": 1})
        cache.set("key1", {"v": 2})
        result = cache.get("key1")

        assert result is not None
        assert result["v"] == 2

    def test_正常系_max_entries超過で古いエントリが削除される(
        self, tmp_path: object
    ) -> None:
        db_path = str(tmp_path) + "/evict_test.db"  # type: ignore[operator]
        cache = SQLiteCache(db_path=db_path, ttl_seconds=60, max_entries=3)

        cache.set("key1", {"v": 1})
        cache.set("key2", {"v": 2})
        cache.set("key3", {"v": 3})
        cache.set("key4", {"v": 4})  # key1 が evict されるはず

        assert cache.get("key4") is not None
        assert cache.get("key1") is None
