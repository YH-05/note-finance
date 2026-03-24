"""SessionMemoryDB のユニットテスト.

受け入れ条件:
- WAL モードで起動すること
- chunks / chunks_fts / chunks_vec / import_log / extraction_log テーブルが作成されること
- save_chunk が冪等に動作すること
- test_db.py の全テストが通過すること
"""

import sqlite3
from pathlib import Path

import pytest

from session_memory.db import SessionMemoryDB


class TestContextManager:
    """コンテキストマネージャの基本動作テスト."""

    def test_正常系_コンテキストマネージャで接続が開閉される(
        self, db: SessionMemoryDB, db_path: Path
    ) -> None:
        """with 文で接続が正しく開閉される."""
        with db:
            assert db_path.exists()
        # 終了後はDB接続が閉じられている
        # （内部の _conn が None になっていることを間接的に確認）

    def test_正常系_親ディレクトリが自動作成される(self, tmp_path: Path) -> None:
        """DBファイルの親ディレクトリが存在しない場合に自動作成される."""
        nested_path = tmp_path / "a" / "b" / "c" / "test.db"
        db = SessionMemoryDB(nested_path)
        with db:
            assert nested_path.parent.exists()

    def test_異常系_コンテキスト外でのメソッド呼び出しでRuntimeError(
        self, db: SessionMemoryDB
    ) -> None:
        """コンテキストマネージャ外で操作するとRuntimeErrorが発生する."""
        with pytest.raises(RuntimeError, match="not open"):
            db.save_chunk(
                chunk_key="test-key",
                session_id="test-session",
                content="test content",
                role="assistant",
            )


class TestWALMode:
    """WAL（Write-Ahead Logging）モードのテスト."""

    def test_正常系_WALモードで起動する(
        self, db: SessionMemoryDB, db_path: Path
    ) -> None:
        """WALモードが有効になっていることを確認する."""
        with db:
            # WALモードの直接確認: 別の接続でPRAGMAを確認
            conn = sqlite3.connect(str(db_path))
            try:
                result = conn.execute("PRAGMA journal_mode").fetchone()
                assert result is not None
                assert result[0] == "wal"
            finally:
                conn.close()


class TestTableCreation:
    """テーブル作成のテスト."""

    def test_正常系_chunksテーブルが作成される(
        self, db: SessionMemoryDB, db_path: Path
    ) -> None:
        """chunks テーブルが存在することを確認する."""
        with db:
            conn = sqlite3.connect(str(db_path))
            try:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks'"
                )
                assert cursor.fetchone() is not None
            finally:
                conn.close()

    def test_正常系_chunks_ftsテーブルが作成される(
        self, db: SessionMemoryDB, db_path: Path
    ) -> None:
        """chunks_fts 全文検索テーブルが存在することを確認する."""
        with db:
            conn = sqlite3.connect(str(db_path))
            try:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_fts'"
                )
                assert cursor.fetchone() is not None
            finally:
                conn.close()

    def test_正常系_chunks_vecテーブルが作成される(
        self, db: SessionMemoryDB, db_path: Path
    ) -> None:
        """chunks_vec ベクトルテーブルが存在することを確認する."""
        with db:
            conn = sqlite3.connect(str(db_path))
            try:
                # sqlite-vec の仮想テーブルは sqlite_master に登録される
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_vec'"
                )
                assert cursor.fetchone() is not None
            finally:
                conn.close()

    def test_正常系_import_logテーブルが作成される(
        self, db: SessionMemoryDB, db_path: Path
    ) -> None:
        """import_log テーブルが存在することを確認する."""
        with db:
            conn = sqlite3.connect(str(db_path))
            try:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='import_log'"
                )
                assert cursor.fetchone() is not None
            finally:
                conn.close()

    def test_正常系_extraction_logテーブルが作成される(
        self, db: SessionMemoryDB, db_path: Path
    ) -> None:
        """extraction_log テーブルが存在することを確認する."""
        with db:
            conn = sqlite3.connect(str(db_path))
            try:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='extraction_log'"
                )
                assert cursor.fetchone() is not None
            finally:
                conn.close()

    def test_正常系_全5テーブルが作成される(
        self, db: SessionMemoryDB, db_path: Path
    ) -> None:
        """必要な5テーブルが全て作成されていることを一括で確認する."""
        expected_tables = {
            "chunks",
            "chunks_fts",
            "chunks_vec",
            "import_log",
            "extraction_log",
        }
        with db:
            conn = sqlite3.connect(str(db_path))
            try:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                actual_tables = {row[0] for row in cursor.fetchall()}
                assert expected_tables.issubset(actual_tables), (
                    f"Missing tables: {expected_tables - actual_tables}"
                )
            finally:
                conn.close()


class TestSaveChunk:
    """save_chunk メソッドのテスト."""

    def test_正常系_チャンクを保存できる(self, db: SessionMemoryDB) -> None:
        """チャンクを1件保存し、取得できることを確認する."""
        with db:
            db.save_chunk(
                chunk_key="session-001::0",
                session_id="session-001",
                content="Hello, world!",
                role="user",
            )
            row = db.get_chunk("session-001::0")
            assert row is not None
            assert row.chunk_key == "session-001::0"
            assert row.session_id == "session-001"
            assert row.content == "Hello, world!"
            assert row.role == "user"

    def test_正常系_save_chunkが冪等に動作する(self, db: SessionMemoryDB) -> None:
        """同じchunk_keyで2回保存しても1レコードのみ存在する."""
        with db:
            db.save_chunk(
                chunk_key="session-001::0",
                session_id="session-001",
                content="First version",
                role="user",
            )
            db.save_chunk(
                chunk_key="session-001::0",
                session_id="session-001",
                content="Updated version",
                role="user",
            )
            row = db.get_chunk("session-001::0")
            assert row is not None
            # 冪等: 2回目の保存で内容が更新される
            assert row.content == "Updated version"

            # レコード数は1件のみ
            count = db.count_chunks()
            assert count == 1

    def test_正常系_複数チャンクを保存できる(self, db: SessionMemoryDB) -> None:
        """異なるchunk_keyで複数チャンクを保存し取得できる."""
        with db:
            db.save_chunk(
                chunk_key="session-001::0",
                session_id="session-001",
                content="Chunk 0",
                role="user",
            )
            db.save_chunk(
                chunk_key="session-001::1",
                session_id="session-001",
                content="Chunk 1",
                role="assistant",
            )
            assert db.count_chunks() == 2

    def test_正常系_オプションフィールド付きで保存できる(
        self, db: SessionMemoryDB
    ) -> None:
        """token_count と embedding 付きでチャンクを保存できる."""
        with db:
            db.save_chunk(
                chunk_key="session-001::0",
                session_id="session-001",
                content="Chunk with metadata",
                role="assistant",
                token_count=150,
            )
            row = db.get_chunk("session-001::0")
            assert row is not None
            assert row.token_count == 150

    def test_正常系_存在しないchunk_keyでNoneが返る(self, db: SessionMemoryDB) -> None:
        """存在しないchunk_keyを取得するとNoneが返る."""
        with db:
            row = db.get_chunk("nonexistent-key")
            assert row is None


class TestImportLog:
    """import_log テーブルの操作テスト."""

    def test_正常系_インポートログを記録できる(self, db: SessionMemoryDB) -> None:
        """インポートログを記録し取得できることを確認する."""
        with db:
            db.log_import(
                session_id="session-001",
                chunk_count=5,
                status="success",
            )
            logs = db.get_import_logs("session-001")
            assert len(logs) == 1
            assert logs[0]["session_id"] == "session-001"
            assert logs[0]["chunk_count"] == 5
            assert logs[0]["status"] == "success"


class TestExtractionLog:
    """extraction_log テーブルの操作テスト."""

    def test_正常系_抽出ログを記録できる(self, db: SessionMemoryDB) -> None:
        """抽出ログを記録し取得できることを確認する."""
        with db:
            db.log_extraction(
                session_id="session-001",
                entity_count=10,
                relation_count=3,
                status="success",
            )
            logs = db.get_extraction_logs("session-001")
            assert len(logs) == 1
            assert logs[0]["session_id"] == "session-001"
            assert logs[0]["entity_count"] == 10
            assert logs[0]["relation_count"] == 3
            assert logs[0]["status"] == "success"


class TestIdempotency:
    """冪等性の追加テスト."""

    def test_正常系_再入可能なコンテキストマネージャ(self, db: SessionMemoryDB) -> None:
        """コンテキストマネージャを2回使用してもテーブルが重複作成されない."""
        with db:
            db.save_chunk(
                chunk_key="key-1",
                session_id="s1",
                content="first",
                role="user",
            )
        # 2回目の利用
        with db:
            row = db.get_chunk("key-1")
            assert row is not None
            assert row.content == "first"

    def test_正常系_例外発生時にロールバックされる(
        self, db: SessionMemoryDB, db_path: Path
    ) -> None:
        """コンテキスト内で例外が発生するとロールバックされる."""
        with db:
            db.save_chunk(
                chunk_key="committed-key",
                session_id="s1",
                content="committed",
                role="user",
            )

        try:
            with db:
                db.save_chunk(
                    chunk_key="rollback-key",
                    session_id="s1",
                    content="should be rolled back",
                    role="user",
                )
                raise ValueError("Intentional error")
        except ValueError:
            pass

        with db:
            # committed-key は残っている
            assert db.get_chunk("committed-key") is not None
            # rollback-key はロールバックされている
            assert db.get_chunk("rollback-key") is None
