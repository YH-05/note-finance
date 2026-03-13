"""SQLite-based scraping state management for RSS feed collection.

This module provides a SQLite wrapper for tracking URL scraping state,
enabling deduplication, retry management, and sitemap progress tracking.
"""

import sqlite3
from pathlib import Path
from types import TracebackType
from urllib.parse import urlparse

from rss._logging import get_logger

logger = get_logger(__name__)


class ScrapeStateDB:
    """SQLiteベースのスクレイピング状態管理データベース。

    2モード動作（incremental/backfill）における重複取得排除、
    取得状態記録、リトライ管理、サイトマップ進捗追跡を担う。

    Parameters
    ----------
    db_path : Path
        SQLiteデータベースファイルのパス

    Examples
    --------
    >>> from pathlib import Path
    >>> with ScrapeStateDB(Path("scrape_state.db")) as db:
    ...     db.mark_scraped("https://example.com/article/1", success=True)
    ...     db.is_scraped("https://example.com/article/1")
    True
    """

    def __init__(self, db_path: Path) -> None:
        """ScrapeStateDBを初期化する。

        Parameters
        ----------
        db_path : Path
            SQLiteデータベースファイルのパス
        """
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        logger.debug("ScrapeStateDB initialized", db_path=str(db_path))

    def __enter__(self) -> "ScrapeStateDB":
        """コンテキストマネージャのエントリポイント。

        Returns
        -------
        ScrapeStateDB
            自身のインスタンス
        """
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._setup_db()
        logger.debug("ScrapeStateDB connection opened", db_path=str(self._db_path))
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """コンテキストマネージャの終了処理。

        Parameters
        ----------
        exc_type : type[BaseException] | None
            例外の型
        exc_val : BaseException | None
            例外インスタンス
        exc_tb : TracebackType | None
            トレースバック
        """
        if self._conn is not None:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
            self._conn.close()
            self._conn = None
            logger.debug("ScrapeStateDB connection closed", db_path=str(self._db_path))

    def _setup_db(self) -> None:
        """データベーステーブルとWALモードをセットアップする。"""
        assert self._conn is not None
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS scraped_articles (
                url TEXT PRIMARY KEY,
                domain TEXT NOT NULL,
                success INTEGER NOT NULL DEFAULT 0,
                retry_count INTEGER NOT NULL DEFAULT 0,
                scraped_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sitemap_state (
                sitemap_url TEXT PRIMARY KEY,
                last_processed_url TEXT,
                processed_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        self._conn.commit()
        logger.debug("ScrapeStateDB tables created/verified")

    def _extract_domain(self, url: str) -> str:
        """URLからドメインを抽出する。

        Parameters
        ----------
        url : str
            対象URL

        Returns
        -------
        str
            ドメイン名
        """
        parsed = urlparse(url)
        return parsed.netloc or url

    def is_scraped(self, url: str) -> bool:
        """URLが取得済みかどうかを判定する。

        Parameters
        ----------
        url : str
            チェック対象URL

        Returns
        -------
        bool
            取得済みの場合True（成功済みの場合のみTrueを返す）
        """
        assert self._conn is not None
        cursor = self._conn.execute(
            "SELECT success FROM scraped_articles WHERE url = ?",
            (url,),
        )
        row = cursor.fetchone()
        if row is None:
            return False
        return bool(row["success"])

    def mark_scraped(self, url: str, *, success: bool) -> None:
        """URLの取得状態を記録する。

        成功時はsuccess=1を設定する。
        失敗時はretry_countをインクリメントする。

        Parameters
        ----------
        url : str
            記録対象URL
        success : bool
            取得成功の場合True
        """
        assert self._conn is not None
        domain = self._extract_domain(url)

        if success:
            self._conn.execute(
                """
                INSERT INTO scraped_articles (url, domain, success, retry_count)
                VALUES (?, ?, 1, 0)
                ON CONFLICT(url) DO UPDATE SET
                    success = 1,
                    scraped_at = datetime('now')
                """,
                (url, domain),
            )
            logger.debug("URL marked as scraped (success)", url=url)
        else:
            self._conn.execute(
                """
                INSERT INTO scraped_articles (url, domain, success, retry_count)
                VALUES (?, ?, 0, 1)
                ON CONFLICT(url) DO UPDATE SET
                    retry_count = retry_count + 1,
                    scraped_at = datetime('now')
                """,
                (url, domain),
            )
            logger.debug("URL marked as scraped (failure)", url=url)

        self._conn.commit()

    def filter_new_urls(self, urls: list[str]) -> list[str]:
        """未取得URLのみを返す。

        取得済み（success=1）のURLを除外する。

        Parameters
        ----------
        urls : list[str]
            チェック対象URLのリスト

        Returns
        -------
        list[str]
            未取得URLのリスト（入力と同じ順序）
        """
        assert self._conn is not None
        if not urls:
            return []

        placeholders = ",".join("?" * len(urls))
        cursor = self._conn.execute(
            f"SELECT url FROM scraped_articles WHERE url IN ({placeholders}) AND success = 1",
            urls,
        )
        scraped_urls = {row["url"] for row in cursor.fetchall()}
        result = [url for url in urls if url not in scraped_urls]
        logger.debug(
            "Filtered new URLs",
            total=len(urls),
            new=len(result),
            filtered=len(urls) - len(result),
        )
        return result

    def get_pending_urls(self, max_retry: int = 3) -> list[str]:
        """リトライ対象の失敗URLを返す。

        success=0かつretry_count < max_retryのURLを返す。

        Parameters
        ----------
        max_retry : int
            最大リトライ回数（デフォルト: 3）

        Returns
        -------
        list[str]
            リトライ対象URLのリスト
        """
        assert self._conn is not None
        cursor = self._conn.execute(
            """
            SELECT url FROM scraped_articles
            WHERE success = 0 AND retry_count < ?
            ORDER BY scraped_at ASC
            """,
            (max_retry,),
        )
        urls = [row["url"] for row in cursor.fetchall()]
        logger.debug("Retrieved pending URLs", count=len(urls), max_retry=max_retry)
        return urls

    def get_stats(self) -> dict[str, dict[str, int]]:
        """ドメイン別の取得統計を返す。

        Returns
        -------
        dict[str, dict[str, int]]
            ドメインをキーとし、success/failureカウントを値とする辞書
            例: {"example.com": {"success": 10, "failure": 2}}
        """
        assert self._conn is not None
        cursor = self._conn.execute(
            """
            SELECT
                domain,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS success_count,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS failure_count
            FROM scraped_articles
            GROUP BY domain
            """
        )
        stats: dict[str, dict[str, int]] = {}
        for row in cursor.fetchall():
            stats[row["domain"]] = {
                "success": row["success_count"],
                "failure": row["failure_count"],
            }
        logger.debug("Retrieved stats", domain_count=len(stats))
        return stats

    def update_sitemap_state(
        self,
        sitemap_url: str,
        last_processed_url: str,
        processed_count: int,
    ) -> None:
        """サイトマップの処理進捗を更新する。

        Parameters
        ----------
        sitemap_url : str
            サイトマップのURL
        last_processed_url : str
            最後に処理したURLのURL
        processed_count : int
            処理済みのURL件数
        """
        assert self._conn is not None
        self._conn.execute(
            """
            INSERT INTO sitemap_state (sitemap_url, last_processed_url, processed_count)
            VALUES (?, ?, ?)
            ON CONFLICT(sitemap_url) DO UPDATE SET
                last_processed_url = excluded.last_processed_url,
                processed_count = excluded.processed_count,
                updated_at = datetime('now')
            """,
            (sitemap_url, last_processed_url, processed_count),
        )
        self._conn.commit()
        logger.debug(
            "Sitemap state updated",
            sitemap_url=sitemap_url,
            processed_count=processed_count,
        )

    def get_sitemap_progress(self, sitemap_url: str) -> dict[str, str | int] | None:
        """サイトマップの処理進捗を取得する。

        Parameters
        ----------
        sitemap_url : str
            サイトマップのURL

        Returns
        -------
        dict[str, str | int] | None
            進捗情報の辞書、または未登録の場合None
            例: {"last_processed_url": "...", "processed_count": 50}
        """
        assert self._conn is not None
        cursor = self._conn.execute(
            """
            SELECT last_processed_url, processed_count
            FROM sitemap_state
            WHERE sitemap_url = ?
            """,
            (sitemap_url,),
        )
        row = cursor.fetchone()
        if row is None:
            logger.debug("Sitemap progress not found", sitemap_url=sitemap_url)
            return None
        progress: dict[str, str | int] = {
            "last_processed_url": row["last_processed_url"],
            "processed_count": row["processed_count"],
        }
        logger.debug(
            "Sitemap progress retrieved",
            sitemap_url=sitemap_url,
            processed_count=row["processed_count"],
        )
        return progress
