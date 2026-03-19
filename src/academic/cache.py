"""academic パッケージのスタンドアロン SQLite キャッシュ.

quants の market.cache.SQLiteCache に相当する軽量実装。
外部パッケージに依存せず、academic パッケージ内で完結する。
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import structlog

if TYPE_CHECKING:
    from .types import AcademicConfig

logger = structlog.get_logger(__name__)

ACADEMIC_CACHE_DB_PATH: Final[str] = "data/cache/academic.db"
ACADEMIC_CACHE_TTL: Final[int] = 604800  # 7 days
ACADEMIC_CACHE_MAX_ENTRIES: Final[int] = 5000

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS cache (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    created_at REAL NOT NULL
)
"""


class SQLiteCache:
    """Lightweight SQLite-based cache for academic paper metadata."""

    def __init__(
        self,
        db_path: str = ACADEMIC_CACHE_DB_PATH,
        ttl_seconds: int = ACADEMIC_CACHE_TTL,
        max_entries: int = ACADEMIC_CACHE_MAX_ENTRIES,
    ) -> None:
        self._db_path = db_path
        self._ttl = ttl_seconds
        self._max_entries = max_entries

        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(_CREATE_TABLE_SQL)
        self._conn.commit()

    def get(self, key: str) -> dict[str, Any] | None:
        """Get a cached value by key, respecting TTL."""
        cursor = self._conn.execute(
            "SELECT value, created_at FROM cache WHERE key = ?", (key,)
        )
        row = cursor.fetchone()
        if row is None:
            return None

        value_str, created_at = row
        if time.time() - created_at > self._ttl:
            self._conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            self._conn.commit()
            return None

        return json.loads(value_str)

    def set(self, key: str, value: dict[str, Any]) -> None:
        """Set a cached value, evicting old entries if needed."""
        value_str = json.dumps(value, ensure_ascii=False)
        self._conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, created_at) VALUES (?, ?, ?)",
            (key, value_str, time.time()),
        )
        self._conn.commit()
        self._evict_if_needed()

    def _evict_if_needed(self) -> None:
        """Evict oldest entries if cache exceeds max_entries."""
        cursor = self._conn.execute("SELECT COUNT(*) FROM cache")
        count = cursor.fetchone()[0]
        if count > self._max_entries:
            excess = count - self._max_entries
            self._conn.execute(
                "DELETE FROM cache WHERE key IN "
                "(SELECT key FROM cache ORDER BY created_at ASC LIMIT ?)",
                (excess,),
            )
            self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()


_cache_instances: dict[int, SQLiteCache] = {}


def get_academic_cache(config: AcademicConfig | None = None) -> SQLiteCache:
    """academic 用の SQLiteCache インスタンスを取得する."""
    ttl = ACADEMIC_CACHE_TTL
    if config is not None:
        ttl = config.cache_ttl

    if ttl not in _cache_instances:
        _cache_instances[ttl] = SQLiteCache(
            db_path=ACADEMIC_CACHE_DB_PATH,
            ttl_seconds=ttl,
            max_entries=ACADEMIC_CACHE_MAX_ENTRIES,
        )
        logger.debug(
            "Academic cache instance created",
            db_path=ACADEMIC_CACHE_DB_PATH,
            ttl_seconds=ttl,
        )

    return _cache_instances[ttl]


def make_cache_key(arxiv_id: str) -> str:
    """arXiv ID からキャッシュキーを生成する."""
    return f"academic:paper:{arxiv_id}"


__all__ = [
    "SQLiteCache",
    "get_academic_cache",
    "make_cache_key",
]
