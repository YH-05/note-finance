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

    def test_異常系_コンテキスト外呼び出しでRuntimeError(self, temp_dir: Path) -> None:
        """with ブロック外（接続前）で操作するとRuntimeErrorが発生することを確認する。"""
        db_path = temp_dir / "scrape_state.db"
        db = ScrapeStateDB(db_path)
        with pytest.raises(RuntimeError, match="context manager"):
            db.is_scraped("https://example.com/article/1")


# ---------------------------------------------------------------------------
# TEST-001: filter_new_urls chunk boundary tests
# ---------------------------------------------------------------------------


class TestFilterNewUrlsChunkBoundary:
    """TEST-001: filter_new_urls のチャンク処理（900件区切り）の境界値テスト。"""

    def test_正常系_901件でチャンク境界を超えても全URLを返す(
        self, temp_dir: Path
    ) -> None:
        """901件のURLリストで2チャンクに分割され正しく動作することを確認する。"""
        db_path = temp_dir / "chunk_test.db"
        urls = [f"https://example.com/article/{i}" for i in range(901)]

        with ScrapeStateDB(db_path) as db:
            # 全URLを未取得状態でフィルタリング
            result = db.filter_new_urls(urls)

        assert len(result) == 901
        assert result == urls

    def test_正常系_1800件で3チャンクに分割されても正しくフィルタリング(
        self, temp_dir: Path
    ) -> None:
        """1800件のURLで先頭900件を取得済みにし、後半900件のみ返されることを確認する。"""
        db_path = temp_dir / "chunk_1800.db"
        all_urls = [f"https://example.com/article/{i}" for i in range(1800)]
        scraped_urls = all_urls[:900]
        new_urls = all_urls[900:]

        with ScrapeStateDB(db_path) as db:
            for url in scraped_urls:
                db.mark_scraped(url, success=True)
            result = db.filter_new_urls(all_urls)

        assert len(result) == 900
        assert result == new_urls

    def test_正常系_900件ちょうどは単一チャンクで処理される(
        self, temp_dir: Path
    ) -> None:
        """900件（チャンクサイズ上限）でも正しく動作することを確認する。"""
        db_path = temp_dir / "chunk_900.db"
        urls = [f"https://example.com/article/{i}" for i in range(900)]

        with ScrapeStateDB(db_path) as db:
            # 奇数インデックスのみ取得済みにする
            for i, url in enumerate(urls):
                if i % 2 == 0:
                    db.mark_scraped(url, success=True)
            result = db.filter_new_urls(urls)

        assert len(result) == 450
        assert all("article/" in u for u in result)


# ---------------------------------------------------------------------------
# TEST-002: get_pending_urls max_retry boundary tests
# ---------------------------------------------------------------------------


class TestGetPendingUrlsMaxRetry:
    """TEST-002: get_pending_urls の max_retry 境界値テスト。"""

    def test_正常系_retry_countがmax_retryと等しい場合は除外される(
        self, temp_dir: Path
    ) -> None:
        """retry_count == max_retry のURLはリトライ対象から除外されることを確認する。"""
        db_path = temp_dir / "maxretry.db"
        url_at_limit = "https://example.com/at_limit"
        url_below_limit = "https://example.com/below_limit"

        with ScrapeStateDB(db_path) as db:
            # url_at_limit を3回失敗させ retry_count = 3 にする
            for _ in range(3):
                db.mark_scraped(url_at_limit, success=False)
            # url_below_limit を2回失敗させ retry_count = 2 にする
            for _ in range(2):
                db.mark_scraped(url_below_limit, success=False)

            pending = db.get_pending_urls(max_retry=3)

        assert url_at_limit not in pending  # retry_count == max_retry → 除外
        assert url_below_limit in pending  # retry_count < max_retry → 対象

    def test_エッジケース_max_retry0では全ての失敗URLが除外される(
        self, temp_dir: Path
    ) -> None:
        """max_retry=0 ではリトライ対象URLがゼロになることを確認する。"""
        db_path = temp_dir / "maxretry0.db"
        url = "https://example.com/failed"

        with ScrapeStateDB(db_path) as db:
            db.mark_scraped(url, success=False)
            pending = db.get_pending_urls(max_retry=0)

        assert pending == []

    def test_正常系_retry_countがmax_retryより大きい場合も除外される(
        self, temp_dir: Path
    ) -> None:
        """retry_count > max_retry のURLも除外されることを確認する（上限超過）。"""
        db_path = temp_dir / "over_limit.db"
        url = "https://example.com/over_limit"

        with ScrapeStateDB(db_path) as db:
            # 5回失敗させ retry_count = 5 にする
            for _ in range(5):
                db.mark_scraped(url, success=False)
            # max_retry=3 で確認
            pending = db.get_pending_urls(max_retry=3)

        assert url not in pending
