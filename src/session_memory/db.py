"""SQLiteベースのセッションメモリDB.

会話セッションのチャンク保存・全文検索・ベクトル検索・
インポート/抽出ログ管理を担うコンテキストマネージャ。

参照パターン: ``src/rss/storage/scrape_state_db.py``
"""

import sqlite3
from pathlib import Path
from types import TracebackType

import sqlite_vec

from session_memory._logging import get_logger
from session_memory.types import ChunkRow, ExtractionLogDict, ImportLogDict

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# 定数: ベクトル次元数
# ---------------------------------------------------------------------------
_EMBEDDING_DIM = 384


class SessionMemoryDB:
    """SQLiteベースのセッションメモリデータベース.

    WALモードで動作し、chunks / chunks_fts / chunks_vec /
    import_log / extraction_log の5テーブルを管理する。

    Parameters
    ----------
    db_path : Path
        SQLiteデータベースファイルのパス

    Examples
    --------
    >>> from pathlib import Path
    >>> with SessionMemoryDB(Path("data/cache/session_memory.db")) as db:
    ...     db.save_chunk(
    ...         chunk_key="s1::0",
    ...         session_id="s1",
    ...         content="Hello",
    ...         role="user",
    ...     )
    ...     row = db.get_chunk("s1::0")
    ...     print(row.content)
    Hello
    """

    def __init__(self, db_path: Path) -> None:
        """SessionMemoryDB を初期化する.

        Parameters
        ----------
        db_path : Path
            SQLiteデータベースファイルのパス
        """
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        logger.debug("SessionMemoryDB initialized", db_path=str(db_path))

    # ------------------------------------------------------------------
    # コンテキストマネージャ
    # ------------------------------------------------------------------

    def __enter__(self) -> "SessionMemoryDB":
        """コンテキストマネージャのエントリポイント.

        Returns
        -------
        SessionMemoryDB
            自身のインスタンス
        """
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._load_extensions()
        self._setup_db()
        logger.debug("SessionMemoryDB connection opened", db_path=str(self._db_path))
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """コンテキストマネージャの終了処理.

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
            logger.debug(
                "SessionMemoryDB connection closed",
                db_path=str(self._db_path),
            )

    # ------------------------------------------------------------------
    # 内部セットアップ
    # ------------------------------------------------------------------

    def _require_conn(self) -> sqlite3.Connection:
        """アクティブな接続を返す。未接続なら RuntimeError を送出する.

        Returns
        -------
        sqlite3.Connection
            アクティブなDB接続

        Raises
        ------
        RuntimeError
            コンテキストマネージャ外で呼ばれた場合
        """
        if self._conn is None:
            raise RuntimeError("SessionMemoryDB is not open. Use as a context manager.")
        return self._conn

    def _load_extensions(self) -> None:
        """sqlite-vec 拡張をロードする."""
        conn = self._require_conn()
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        logger.debug("sqlite-vec extension loaded")

    def _setup_db(self) -> None:
        """WALモード設定とテーブル作成を実行する."""
        conn = self._require_conn()

        # WAL モード
        conn.execute("PRAGMA journal_mode=WAL")

        # chunks テーブル
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_key   TEXT PRIMARY KEY,
                session_id  TEXT NOT NULL,
                content     TEXT NOT NULL,
                role        TEXT NOT NULL DEFAULT 'user',
                token_count INTEGER,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # chunks_fts: 全文検索（FTS5）
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
            USING fts5(
                content,
                content_rowid='rowid',
                tokenize='unicode61'
            )
        """)

        # chunks_vec: ベクトル検索（sqlite-vec）
        conn.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec
            USING vec0(
                embedding float[{_EMBEDDING_DIM}]
            )
        """)

        # import_log テーブル
        conn.execute("""
            CREATE TABLE IF NOT EXISTS import_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL,
                chunk_count INTEGER NOT NULL DEFAULT 0,
                status      TEXT NOT NULL DEFAULT 'success',
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # extraction_log テーブル
        conn.execute("""
            CREATE TABLE IF NOT EXISTS extraction_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id      TEXT NOT NULL,
                entity_count    INTEGER NOT NULL DEFAULT 0,
                relation_count  INTEGER NOT NULL DEFAULT 0,
                status          TEXT NOT NULL DEFAULT 'success',
                created_at      TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        conn.commit()
        logger.debug("SessionMemoryDB tables created/verified")

    # ------------------------------------------------------------------
    # チャンク操作
    # ------------------------------------------------------------------

    def save_chunk(
        self,
        *,
        chunk_key: str,
        session_id: str,
        content: str,
        role: str,
        token_count: int | None = None,
    ) -> None:
        """チャンクを冪等に保存する.

        同一 chunk_key が既に存在する場合は内容を更新する（UPSERT）。

        Parameters
        ----------
        chunk_key : str
            チャンクの一意識別子
        session_id : str
            所属セッションID
        content : str
            チャンク本文
        role : str
            発話者ロール（user / assistant / system）
        token_count : int | None
            トークン数（省略可）
        """
        conn = self._require_conn()
        conn.execute(
            """
            INSERT INTO chunks (chunk_key, session_id, content, role, token_count)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(chunk_key) DO UPDATE SET
                session_id  = excluded.session_id,
                content     = excluded.content,
                role        = excluded.role,
                token_count = excluded.token_count,
                created_at  = datetime('now')
            """,
            (chunk_key, session_id, content, role, token_count),
        )
        logger.debug("Chunk saved", chunk_key=chunk_key, session_id=session_id)

    def get_chunk(self, chunk_key: str) -> ChunkRow | None:
        """chunk_key でチャンクを取得する.

        Parameters
        ----------
        chunk_key : str
            チャンクの一意識別子

        Returns
        -------
        ChunkRow | None
            チャンク行。存在しない場合は None
        """
        conn = self._require_conn()
        cursor = conn.execute(
            "SELECT chunk_key, session_id, content, role, token_count, created_at "
            "FROM chunks WHERE chunk_key = ?",
            (chunk_key,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return ChunkRow(
            chunk_key=row["chunk_key"],
            session_id=row["session_id"],
            content=row["content"],
            role=row["role"],
            token_count=row["token_count"],
            created_at=row["created_at"],
        )

    def count_chunks(self) -> int:
        """chunks テーブルの総レコード数を返す.

        Returns
        -------
        int
            チャンクの総数
        """
        conn = self._require_conn()
        cursor = conn.execute("SELECT COUNT(*) FROM chunks")
        result = cursor.fetchone()
        return int(result[0]) if result else 0

    # ------------------------------------------------------------------
    # インポートログ
    # ------------------------------------------------------------------

    def log_import(
        self,
        *,
        session_id: str,
        chunk_count: int,
        status: str = "success",
    ) -> None:
        """インポートログを記録する.

        Parameters
        ----------
        session_id : str
            セッションID
        chunk_count : int
            インポートしたチャンク数
        status : str
            ステータス（デフォルト: "success"）
        """
        conn = self._require_conn()
        conn.execute(
            """
            INSERT INTO import_log (session_id, chunk_count, status)
            VALUES (?, ?, ?)
            """,
            (session_id, chunk_count, status),
        )
        logger.debug(
            "Import logged",
            session_id=session_id,
            chunk_count=chunk_count,
            status=status,
        )

    def get_import_logs(self, session_id: str) -> list[ImportLogDict]:
        """セッションのインポートログを取得する.

        Parameters
        ----------
        session_id : str
            セッションID

        Returns
        -------
        list[ImportLogDict]
            インポートログのリスト
        """
        conn = self._require_conn()
        cursor = conn.execute(
            """
            SELECT id, session_id, chunk_count, status, created_at
            FROM import_log
            WHERE session_id = ?
            ORDER BY created_at ASC
            """,
            (session_id,),
        )
        return [
            ImportLogDict(
                id=row["id"],
                session_id=row["session_id"],
                chunk_count=row["chunk_count"],
                status=row["status"],
                created_at=row["created_at"],
            )
            for row in cursor.fetchall()
        ]

    # ------------------------------------------------------------------
    # 抽出ログ
    # ------------------------------------------------------------------

    def log_extraction(
        self,
        *,
        session_id: str,
        entity_count: int,
        relation_count: int,
        status: str = "success",
    ) -> None:
        """抽出ログを記録する.

        Parameters
        ----------
        session_id : str
            セッションID
        entity_count : int
            抽出したエンティティ数
        relation_count : int
            抽出したリレーション数
        status : str
            ステータス（デフォルト: "success"）
        """
        conn = self._require_conn()
        conn.execute(
            """
            INSERT INTO extraction_log (session_id, entity_count, relation_count, status)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, entity_count, relation_count, status),
        )
        logger.debug(
            "Extraction logged",
            session_id=session_id,
            entity_count=entity_count,
            relation_count=relation_count,
            status=status,
        )

    def get_extraction_logs(self, session_id: str) -> list[ExtractionLogDict]:
        """セッションの抽出ログを取得する.

        Parameters
        ----------
        session_id : str
            セッションID

        Returns
        -------
        list[ExtractionLogDict]
            抽出ログのリスト
        """
        conn = self._require_conn()
        cursor = conn.execute(
            """
            SELECT id, session_id, entity_count, relation_count, status, created_at
            FROM extraction_log
            WHERE session_id = ?
            ORDER BY created_at ASC
            """,
            (session_id,),
        )
        return [
            ExtractionLogDict(
                id=row["id"],
                session_id=row["session_id"],
                entity_count=row["entity_count"],
                relation_count=row["relation_count"],
                status=row["status"],
                created_at=row["created_at"],
            )
            for row in cursor.fetchall()
        ]
