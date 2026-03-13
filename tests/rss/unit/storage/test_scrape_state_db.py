"""Unit tests for ScrapeStateDB."""

import sqlite3
from pathlib import Path

import pytest

from rss.storage.scrape_state_db import ScrapeStateDB


class TestScrapeStateDBContextManager:
    """Test ScrapeStateDB as context manager."""

    def test_正常系_URLを記録して取得済み判定(self, temp_dir: Path) -> None:
        """URLをmark_scrapedで記録した後、is_scrapedでTrueが返ることを確認する。"""
        db_path = temp_dir / "scrape_state.db"
        url = "https://example.com/article/1"

        with ScrapeStateDB(db_path) as db:
            assert db.is_scraped(url) is False
            db.mark_scraped(url, success=True)
            assert db.is_scraped(url) is True

    def test_正常系_未取得URLのフィルタリング(self, temp_dir: Path) -> None:
        """filter_new_urlsが既取得URLを除外し、未取得URLのみを返すことを確認する。"""
        db_path = temp_dir / "scrape_state.db"
        existing_url = "https://example.com/article/existing"
        new_url = "https://example.com/article/new"

        with ScrapeStateDB(db_path) as db:
            db.mark_scraped(existing_url, success=True)
            result = db.filter_new_urls([existing_url, new_url])

        assert result == [new_url]

    def test_正常系_失敗URLのリトライ取得(self, temp_dir: Path) -> None:
        """retry_count < 3の失敗URLがget_pending_urlsのリトライ対象として返されることを確認する。"""
        db_path = temp_dir / "scrape_state.db"
        failed_url_1 = "https://example.com/failed/1"
        failed_url_2 = "https://example.com/failed/2"
        success_url = "https://example.com/success/1"

        with ScrapeStateDB(db_path) as db:
            # 失敗URLを登録（retry_count < 3）
            db.mark_scraped(failed_url_1, success=False)
            db.mark_scraped(failed_url_2, success=False)
            db.mark_scraped(failed_url_2, success=False)  # retry_count = 2
            # 成功URLを登録
            db.mark_scraped(success_url, success=True)

            pending = db.get_pending_urls()

        assert failed_url_1 in pending
        assert failed_url_2 in pending
        assert success_url not in pending

    def test_正常系_ドメイン別統計の取得(self, temp_dir: Path) -> None:
        """get_statsがドメイン別の成功・失敗件数を正しく返すことを確認する。"""
        db_path = temp_dir / "scrape_state.db"

        with ScrapeStateDB(db_path) as db:
            db.mark_scraped("https://example.com/article/1", success=True)
            db.mark_scraped("https://example.com/article/2", success=True)
            db.mark_scraped("https://example.com/article/3", success=False)
            db.mark_scraped("https://other.com/article/1", success=True)

            stats = db.get_stats()

        assert stats["example.com"]["success"] == 2
        assert stats["example.com"]["failure"] == 1
        assert stats["other.com"]["success"] == 1
        assert stats["other.com"]["failure"] == 0

    def test_正常系_サイトマップ進捗の更新と取得(self, temp_dir: Path) -> None:
        """update_sitemap_stateで進捗を更新し、get_sitemap_progressで正しく取得できることを確認する。"""
        db_path = temp_dir / "scrape_state.db"
        sitemap_url = "https://example.com/sitemap.xml"

        with ScrapeStateDB(db_path) as db:
            db.update_sitemap_state(
                sitemap_url,
                last_processed_url="https://example.com/article/50",
                processed_count=50,
            )
            progress = db.get_sitemap_progress(sitemap_url)

        assert progress is not None
        assert progress["last_processed_url"] == "https://example.com/article/50"
        assert progress["processed_count"] == 50

    def test_エッジケース_空のDBでの各操作(self, temp_dir: Path) -> None:
        """空のDBでis_scraped/filter_new_urls/get_pending_urls/get_statsが正常に動作することを確認する。"""
        db_path = temp_dir / "scrape_state.db"
        url = "https://example.com/article/1"

        with ScrapeStateDB(db_path) as db:
            assert db.is_scraped(url) is False
            assert db.filter_new_urls([url]) == [url]
            assert db.get_pending_urls() == []
            assert db.get_stats() == {}
            assert db.get_sitemap_progress("https://example.com/sitemap.xml") is None

    def test_正常系_WALモードが有効(self, temp_dir: Path) -> None:
        """WALモードが有効化されていることをPRAGMA journal_modeで確認する。"""
        db_path = temp_dir / "scrape_state.db"

        with ScrapeStateDB(db_path) as db:
            conn = db._conn
            assert conn is not None
            cursor = conn.execute("PRAGMA journal_mode")
            journal_mode = cursor.fetchone()[0]

        assert journal_mode.lower() == "wal"
