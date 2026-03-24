"""session_memory E2E 統合テスト: parse -> chunk -> embed -> extract -> save -> search.

受け入れ条件:
- E2E テストが通過すること
- make check-all が全パスすること
- memory-cli stats が正常動作すること

AIDEV-NOTE: FTS5 の unicode61 トークナイザは日英混在テキスト（例: "PythonのPydantic"）を
正しくトークン分割できない。実プロダクションコード（cli/main.py _search_fts）では
FTS 失敗時に LIKE フォールバックを使用しているため、テストでも同じパターンを検証する。
"""

from __future__ import annotations

import json
import struct
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from session_memory.chunker import parse_transcript
from session_memory.db import SessionMemoryDB
from session_memory.extractor import ChunkExtraction, rule_based_predetect
from session_memory.searcher import merge_rrf

# ---------------------------------------------------------------------------
# sqlite-vec の利用可否判定
# ---------------------------------------------------------------------------

_HAS_SQLITE_VEC = True
try:
    import sqlite_vec
except ImportError:
    _HAS_SQLITE_VEC = False

_skip_no_sqlite_vec = pytest.mark.skipif(
    not _HAS_SQLITE_VEC,
    reason="sqlite-vec が未インストールのためベクトルテストをスキップ",
)

# ---------------------------------------------------------------------------
# embedding モデルの利用可否判定
# ---------------------------------------------------------------------------

_HAS_SENTENCE_TRANSFORMERS = True
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    _HAS_SENTENCE_TRANSFORMERS = False

_skip_no_embedder = pytest.mark.skipif(
    not _HAS_SENTENCE_TRANSFORMERS,
    reason="sentence-transformers が未インストールのため embedding テストをスキップ",
)

# ---------------------------------------------------------------------------
# テスト用 JSONL データ生成
# ---------------------------------------------------------------------------

_SESSION_ID = "e2e-test-session-001"
_CWD = "/Users/user/.worktrees/note-finance/feature-test"


def _make_line(
    *,
    role: str = "user",
    content: str = "Hello",
    session_id: str = _SESSION_ID,
    cwd: str = _CWD,
    is_sidechain: bool = False,
) -> str:
    """transcript.jsonl の1行を生成するヘルパー.

    Parameters
    ----------
    role : str
        メッセージのロール
    content : str
        メッセージ本文
    session_id : str
        セッションID
    cwd : str
        作業ディレクトリ
    is_sidechain : bool
        サブエージェント会話フラグ

    Returns
    -------
    str
        JSON文字列（1行分）
    """
    return json.dumps(
        {
            "isSidechain": is_sidechain,
            "cwd": cwd,
            "sessionId": session_id,
            "message": {
                "role": role,
                "content": content,
            },
        },
        ensure_ascii=False,
    )


def _build_sample_jsonl_lines() -> list[str]:
    """E2E テスト用のサンプル JSONL 行リストを構築する.

    Returns
    -------
    list[str]
        transcript.jsonl 相当の行リスト
    """
    return [
        _make_line(
            role="user",
            content="PythonのPydanticライブラリでデータバリデーションを実装したいです。"
            "BaseModelの使い方を教えてください。",
        ),
        _make_line(
            role="assistant",
            content="PydanticのBaseModelを使うと、型ヒントに基づいたデータバリデーションが "
            "自動的に行われます。FastAPIとの統合も強力です。"
            "Pythonの型システムを活用して、安全なデータ処理が実現できます。",
        ),
        _make_line(
            role="user",
            content="Neo4jのナレッジグラフでエンティティリンキングを実装する方法を教えてください。"
            "SQLiteとの併用も検討しています。",
        ),
        _make_line(
            role="assistant",
            content="Neo4jでナレッジグラフを構築する場合、まずエンティティの正規化が重要です。"
            "SQLiteでローカルキャッシュを管理し、Neo4jでグラフ構造を保持するのは "
            "良いアーキテクチャ設計です。テスト戦略としてはpytestを使った統合テストが推奨されます。",
        ),
        _make_line(
            role="user",
            content="パフォーマンス最適化の方針として、バッチ処理を採用することに決定しました。",
        ),
        _make_line(
            role="assistant",
            content="バッチ処理の採用は良い決定です。Pythonのasyncioと組み合わせることで、"
            "効率的なデータ処理パイプラインが構築できます。",
        ),
    ]


def _write_sample_jsonl(tmp_path: Path) -> Path:
    """サンプル JSONL ファイルを一時ディレクトリに書き出す.

    Parameters
    ----------
    tmp_path : Path
        pytest 提供の一時ディレクトリ

    Returns
    -------
    Path
        書き出した JSONL ファイルパス
    """
    jsonl_path = tmp_path / f"{_SESSION_ID}.jsonl"
    lines = _build_sample_jsonl_lines()
    jsonl_path.write_text("\n".join(lines), encoding="utf-8")
    return jsonl_path


def _float_list_to_bytes(floats: list[float]) -> bytes:
    """float リストを sqlite-vec 用のバイト列に変換する.

    Parameters
    ----------
    floats : list[float]
        float リスト

    Returns
    -------
    bytes
        リトルエンディアン float32 バイト列
    """
    return struct.pack(f"<{len(floats)}f", *floats)


# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """テスト用 DB ファイルパスを返す.

    Parameters
    ----------
    tmp_path : Path
        pytest 提供の一時ディレクトリ

    Returns
    -------
    Path
        一時ディレクトリ内の DB ファイルパス
    """
    return tmp_path / "e2e_session_memory.db"


@pytest.fixture
def sample_jsonl(tmp_path: Path) -> Path:
    """サンプル JSONL ファイルのパスを返す.

    Parameters
    ----------
    tmp_path : Path
        pytest 提供の一時ディレクトリ

    Returns
    -------
    Path
        サンプル JSONL ファイルパス
    """
    return _write_sample_jsonl(tmp_path)


@pytest.fixture
def sample_lines() -> list[str]:
    """サンプル JSONL 行リストを返す.

    Returns
    -------
    list[str]
        JSONL 行リスト
    """
    return _build_sample_jsonl_lines()


# ---------------------------------------------------------------------------
# E2E 統合テスト: parse -> chunk -> save -> search
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestE2ESaveAndSearch:
    """E2E: parse -> chunk -> save -> search の統合テスト."""

    def test_正常系_JSONLをパースしてチャンクに変換できる(
        self, sample_lines: list[str]
    ) -> None:
        """JSONL 行リストからチャンクが生成される."""
        chunks = parse_transcript(sample_lines)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert chunk.session_id == _SESSION_ID
            assert chunk.content
            assert chunk.chunk_key
            assert chunk.role == "assistant"

    def test_正常系_チャンクをDBに保存して取得できる(
        self, db_path: Path, sample_lines: list[str]
    ) -> None:
        """チャンクを DB に保存し、get_chunk で取得できる."""
        chunks = parse_transcript(sample_lines)
        assert len(chunks) >= 1

        with SessionMemoryDB(db_path) as db:
            for chunk in chunks:
                db.save_chunk(
                    chunk_key=chunk.chunk_key,
                    session_id=chunk.session_id,
                    content=chunk.content,
                    role=chunk.role,
                )

            # 保存されたチャンクを取得して検証
            for chunk in chunks:
                row = db.get_chunk(chunk.chunk_key)
                assert row is not None
                assert row.content == chunk.content
                assert row.session_id == chunk.session_id

            # 総チャンク数を確認
            assert db.count_chunks() == len(chunks)

    def test_正常系_LIKE検索でチャンクが見つかる(
        self, db_path: Path, sample_lines: list[str]
    ) -> None:
        """保存したチャンクを LIKE 検索で取得できる.

        AIDEV-NOTE: FTS5 unicode61 トークナイザは日英混在テキストの
        単語境界を正しく認識できないため、プロダクションコード同様に
        LIKE フォールバックで検索する。
        """
        chunks = parse_transcript(sample_lines)

        with SessionMemoryDB(db_path) as db:
            conn = db._require_conn()

            for chunk in chunks:
                db.save_chunk(
                    chunk_key=chunk.chunk_key,
                    session_id=chunk.session_id,
                    content=chunk.content,
                    role=chunk.role,
                )

            # LIKE 検索: "Pydantic" を含むチャンクを検索
            cursor = conn.execute(
                "SELECT chunk_key, session_id, content, role, "
                "       token_count, created_at "
                "FROM chunks "
                "WHERE content LIKE ? "
                "ORDER BY created_at DESC "
                "LIMIT 10",
                ("%Pydantic%",),
            )
            results = cursor.fetchall()
            assert len(results) >= 1, (
                "LIKE search for 'Pydantic' should return at least 1 result"
            )
            assert any("Pydantic" in r["content"] for r in results)

            # LIKE 検索: "Neo4j" を含むチャンクを検索
            cursor = conn.execute(
                "SELECT chunk_key, content FROM chunks "
                "WHERE content LIKE ? "
                "ORDER BY created_at DESC LIMIT 10",
                ("%Neo4j%",),
            )
            results = cursor.fetchall()
            assert len(results) >= 1, (
                "LIKE search for 'Neo4j' should return at least 1 result"
            )
            assert any("Neo4j" in r["content"] for r in results)

    def test_正常系_インポートログが記録される(
        self, db_path: Path, sample_lines: list[str]
    ) -> None:
        """チャンク保存後にインポートログを記録・取得できる."""
        chunks = parse_transcript(sample_lines)

        with SessionMemoryDB(db_path) as db:
            for chunk in chunks:
                db.save_chunk(
                    chunk_key=chunk.chunk_key,
                    session_id=chunk.session_id,
                    content=chunk.content,
                    role=chunk.role,
                )

            db.log_import(
                session_id=_SESSION_ID,
                chunk_count=len(chunks),
                status="success",
            )

            logs = db.get_import_logs(_SESSION_ID)
            assert len(logs) == 1
            assert logs[0]["chunk_count"] == len(chunks)
            assert logs[0]["status"] == "success"


# ---------------------------------------------------------------------------
# E2E 統合テスト: extract (ルールベース)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestE2EExtraction:
    """E2E: parse -> chunk -> extract の統合テスト（ルールベース抽出）."""

    def test_正常系_チャンクからエンティティが抽出される(
        self, sample_lines: list[str]
    ) -> None:
        """チャンク本文からルールベースでエンティティが検出される."""
        chunks = parse_transcript(sample_lines)
        assert len(chunks) >= 1

        all_entities: list[str] = []
        for chunk in chunks:
            extraction: ChunkExtraction = rule_based_predetect(chunk.content)
            for entity in extraction.entities:
                all_entities.append(entity.name.lower())

        # サンプルデータに含まれるエンティティが検出される
        assert any("pydantic" in e for e in all_entities), (
            f"Pydantic should be detected. Found: {all_entities}"
        )
        assert any("python" in e for e in all_entities), (
            f"Python should be detected. Found: {all_entities}"
        )
        assert any("neo4j" in e for e in all_entities), (
            f"Neo4j should be detected. Found: {all_entities}"
        )

    def test_正常系_チャンクからトピックが抽出される(
        self, sample_lines: list[str]
    ) -> None:
        """チャンク本文からルールベースでトピックが検出される."""
        chunks = parse_transcript(sample_lines)

        all_topics: list[str] = []
        for chunk in chunks:
            extraction = rule_based_predetect(chunk.content)
            for topic in extraction.topics:
                all_topics.append(topic.name)

        # 「データバリデーション」「ナレッジグラフ」等が検出される
        assert any("データバリデーション" in t for t in all_topics), (
            f"データバリデーション should be detected. Found: {all_topics}"
        )
        assert any("ナレッジグラフ" in t for t in all_topics), (
            f"ナレッジグラフ should be detected. Found: {all_topics}"
        )

    def test_正常系_チャンクから決定事項が抽出される(
        self, sample_lines: list[str]
    ) -> None:
        """チャンク本文からルールベースで決定事項が検出される."""
        chunks = parse_transcript(sample_lines)

        all_decisions: list[str] = []
        for chunk in chunks:
            extraction = rule_based_predetect(chunk.content)
            for decision in extraction.decisions:
                all_decisions.append(decision.summary)

        # 「採用」「決定」キーワードを含む決定事項が検出される
        assert len(all_decisions) >= 1, (
            f"At least one decision should be detected. Found: {all_decisions}"
        )

    def test_正常系_抽出ログが記録される(
        self, db_path: Path, sample_lines: list[str]
    ) -> None:
        """抽出結果のログを DB に記録・取得できる."""
        chunks = parse_transcript(sample_lines)

        total_entities = 0
        total_relations = 0
        for chunk in chunks:
            extraction = rule_based_predetect(chunk.content)
            total_entities += len(extraction.entities)
            total_relations += len(extraction.topics) + len(extraction.decisions)

        with SessionMemoryDB(db_path) as db:
            db.log_extraction(
                session_id=_SESSION_ID,
                entity_count=total_entities,
                relation_count=total_relations,
                status="success",
            )

            logs = db.get_extraction_logs(_SESSION_ID)
            assert len(logs) == 1
            assert logs[0]["entity_count"] == total_entities
            assert logs[0]["relation_count"] == total_relations
            assert logs[0]["status"] == "success"


# ---------------------------------------------------------------------------
# E2E 統合テスト: ベクトル保存・検索（sqlite-vec 必須）
# ---------------------------------------------------------------------------


@pytest.mark.integration
@_skip_no_sqlite_vec
class TestE2EVectorSaveSearch:
    """E2E: chunk -> embed -> save -> vector search の統合テスト.

    sqlite-vec が利用可能な場合のみ実行。
    """

    def test_正常系_ダミーembeddingを保存してベクトル検索できる(
        self, db_path: Path, sample_lines: list[str]
    ) -> None:
        """ダミー embedding ベクトルを chunks_vec に保存し、近似検索で取得できる."""
        chunks = parse_transcript(sample_lines)
        assert len(chunks) >= 2

        dim = 384  # _EMBEDDING_DIM と一致

        with SessionMemoryDB(db_path) as db:
            conn = db._require_conn()

            # チャンクを保存
            for chunk in chunks:
                db.save_chunk(
                    chunk_key=chunk.chunk_key,
                    session_id=chunk.session_id,
                    content=chunk.content,
                    role=chunk.role,
                )

            # ダミー embedding を生成して chunks_vec に保存
            for i, chunk in enumerate(chunks):
                embedding = [0.0] * dim
                # i 番目の次元に 1.0 を設定（ワンホット風）
                if i < dim:
                    embedding[i] = 1.0
                emb_bytes = _float_list_to_bytes(embedding)

                row = conn.execute(
                    "SELECT rowid FROM chunks WHERE chunk_key = ?",
                    (chunk.chunk_key,),
                ).fetchone()
                assert row is not None

                conn.execute(
                    "INSERT INTO chunks_vec(rowid, embedding) VALUES (?, ?)",
                    (row[0], emb_bytes),
                )

            conn.commit()

            # ベクトル検索: 最初のチャンクに近いベクトルで検索
            query_vec = [0.0] * dim
            query_vec[0] = 1.0  # 最初のチャンクと同じ方向
            query_bytes = _float_list_to_bytes(query_vec)

            cursor = conn.execute(
                "SELECT rowid, distance FROM chunks_vec "
                "WHERE embedding MATCH ? "
                "ORDER BY distance "
                "LIMIT 5",
                (query_bytes,),
            )
            vec_results = cursor.fetchall()
            assert len(vec_results) >= 1, (
                "Vector search should return at least 1 result"
            )

            # 最近傍は最初のチャンク（distance が最小）
            first_rowid = vec_results[0]["rowid"]
            first_chunk_row = conn.execute(
                "SELECT chunk_key FROM chunks WHERE rowid = ?",
                (first_rowid,),
            ).fetchone()
            assert first_chunk_row is not None
            assert first_chunk_row["chunk_key"] == chunks[0].chunk_key

    @_skip_no_embedder
    def test_正常系_実モデルembeddingを保存して検索できる(
        self, db_path: Path, sample_lines: list[str]
    ) -> None:
        """実際の embedding モデルでベクトルを生成し、検索で類似チャンクが見つかる.

        AIDEV-NOTE: 実モデルの出力次元と DB スキーマ (_EMBEDDING_DIM=384) が
        一致しない場合がある。その場合は専用の vec テーブルを作成して検証する。
        """
        from session_memory.embedder import get_embedder

        model = get_embedder()
        if model is None:
            pytest.skip("Embedding model not available")

        chunks = parse_transcript(sample_lines)
        assert len(chunks) >= 2

        # モデルの出力次元を取得
        sample_emb = model.encode("test", normalize_embeddings=True)
        actual_dim = len(sample_emb)

        with SessionMemoryDB(db_path) as db:
            conn = db._require_conn()

            # モデル次元に合わせた vec テーブルを作成
            # AIDEV-NOTE: DB スキーマの _EMBEDDING_DIM=384 とモデル出力次元が
            # 異なる場合、テスト専用のテーブルを使用する
            if actual_dim != 384:
                conn.execute(
                    f"CREATE VIRTUAL TABLE IF NOT EXISTS test_vec "
                    f"USING vec0(embedding float[{actual_dim}])"
                )
                vec_table = "test_vec"
            else:
                vec_table = "chunks_vec"

            # チャンクを保存 + embedding 生成・保存
            for chunk in chunks:
                db.save_chunk(
                    chunk_key=chunk.chunk_key,
                    session_id=chunk.session_id,
                    content=chunk.content,
                    role=chunk.role,
                )

                emb = model.encode(chunk.content, normalize_embeddings=True)
                emb_bytes = _float_list_to_bytes(emb.tolist())

                row = conn.execute(
                    "SELECT rowid FROM chunks WHERE chunk_key = ?",
                    (chunk.chunk_key,),
                ).fetchone()
                assert row is not None

                conn.execute(
                    f"INSERT INTO {vec_table}(rowid, embedding) VALUES (?, ?)",
                    (row[0], emb_bytes),
                )

            conn.commit()

            # 「Pydantic のバリデーション」で検索
            query_emb = model.encode(
                "Pydantic のバリデーション", normalize_embeddings=True
            )
            query_bytes = _float_list_to_bytes(query_emb.tolist())

            cursor = conn.execute(
                f"SELECT rowid, distance FROM {vec_table} "
                "WHERE embedding MATCH ? "
                "ORDER BY distance "
                "LIMIT 5",
                (query_bytes,),
            )
            vec_results = cursor.fetchall()
            assert len(vec_results) >= 1

            # 最近傍チャンクの内容に Pydantic が含まれるか確認
            top_rowid = vec_results[0]["rowid"]
            top_chunk = conn.execute(
                "SELECT content FROM chunks WHERE rowid = ?",
                (top_rowid,),
            ).fetchone()
            assert top_chunk is not None
            assert "Pydantic" in top_chunk["content"], (
                "Top result should contain 'Pydantic' for the query "
                "'Pydantic のバリデーション'"
            )


# ---------------------------------------------------------------------------
# E2E 統合テスト: RRF 統合検索
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestE2ERRFMergeSearch:
    """E2E: FTS + VEC ランキングの RRF 統合テスト."""

    def test_正常系_FTSとVECのランキングをRRFで統合できる(self) -> None:
        """FTS と VEC の結果を merge_rrf で統合し、スコア降順で返る."""
        fts_ranked: list[tuple[str, int]] = [
            ("chunk-a", 0),
            ("chunk-b", 1),
            ("chunk-c", 2),
        ]
        vec_ranked: list[tuple[str, int]] = [
            ("chunk-b", 0),
            ("chunk-d", 1),
            ("chunk-a", 2),
        ]

        results = merge_rrf(
            fts_ranked=fts_ranked,
            vec_ranked=vec_ranked,
        )

        assert len(results) >= 3
        # chunk-b は FTS(rank=1) + VEC(rank=0) で最高スコア候補
        assert results[0].chunk_key in ("chunk-a", "chunk-b")

        # 全結果がスコア降順
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    @_skip_no_sqlite_vec
    def test_正常系_LIKEとベクトル検索を実DBで統合できる(
        self, db_path: Path, sample_lines: list[str]
    ) -> None:
        """実 DB で LIKE/VEC 検索を行い、RRF で統合する."""
        chunks = parse_transcript(sample_lines)
        dim = 384

        with SessionMemoryDB(db_path) as db:
            conn = db._require_conn()

            for i, chunk in enumerate(chunks):
                db.save_chunk(
                    chunk_key=chunk.chunk_key,
                    session_id=chunk.session_id,
                    content=chunk.content,
                    role=chunk.role,
                )

                # ダミー embedding
                embedding = [0.0] * dim
                if i < dim:
                    embedding[i] = 1.0
                emb_bytes = _float_list_to_bytes(embedding)

                row = conn.execute(
                    "SELECT rowid FROM chunks WHERE chunk_key = ?",
                    (chunk.chunk_key,),
                ).fetchone()
                assert row is not None
                conn.execute(
                    "INSERT INTO chunks_vec(rowid, embedding) VALUES (?, ?)",
                    (row[0], emb_bytes),
                )

            conn.commit()

            # LIKE 検索（FTS フォールバック相当）
            like_cursor = conn.execute(
                "SELECT chunk_key FROM chunks "
                "WHERE content LIKE ? "
                "ORDER BY created_at DESC "
                "LIMIT 10",
                ("%Python%",),
            )
            like_rows = like_cursor.fetchall()
            like_ranked = [
                (row["chunk_key"], rank) for rank, row in enumerate(like_rows)
            ]

            # VEC 検索
            # AIDEV-NOTE: sqlite-vec の KNN クエリは k=? 制約が必要
            query_vec = [0.0] * dim
            query_vec[0] = 1.0
            query_bytes = _float_list_to_bytes(query_vec)

            vec_cursor = conn.execute(
                "SELECT rowid, distance FROM chunks_vec "
                "WHERE embedding MATCH ? AND k = ? "
                "ORDER BY distance",
                (query_bytes, 10),
            )
            vec_rows = vec_cursor.fetchall()
            vec_ranked_items: list[tuple[str, int]] = []
            for rank, vrow in enumerate(vec_rows):
                chunk_row = conn.execute(
                    "SELECT chunk_key FROM chunks WHERE rowid = ?",
                    (vrow["rowid"],),
                ).fetchone()
                if chunk_row is not None:
                    vec_ranked_items.append((chunk_row["chunk_key"], rank))
            vec_ranked = vec_ranked_items

            # RRF 統合
            assert like_ranked or vec_ranked, (
                "At least one search method should return results"
            )
            merged = merge_rrf(
                fts_ranked=like_ranked,
                vec_ranked=vec_ranked,
            )
            assert len(merged) >= 1
            # スコア降順
            scores = [r.score for r in merged]
            assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# E2E 統合テスト: memory-cli stats 相当の集計
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestE2EStats:
    """E2E: CLI stats 相当の統計情報が正しく取得できることを検証."""

    def test_正常系_stats相当の集計が正常動作する(
        self, db_path: Path, sample_lines: list[str]
    ) -> None:
        """チャンク保存後に stats 相当の集計クエリが正常に実行される."""
        chunks = parse_transcript(sample_lines)

        with SessionMemoryDB(db_path) as db:
            conn = db._require_conn()

            for chunk in chunks:
                db.save_chunk(
                    chunk_key=chunk.chunk_key,
                    session_id=chunk.session_id,
                    content=chunk.content,
                    role=chunk.role,
                )

            # インポートログ記録
            db.log_import(
                session_id=_SESSION_ID,
                chunk_count=len(chunks),
                status="success",
            )

            # 抽出ログ記録
            total_entities = 0
            for chunk in chunks:
                extraction = rule_based_predetect(chunk.content)
                total_entities += len(extraction.entities)

            db.log_extraction(
                session_id=_SESSION_ID,
                entity_count=total_entities,
                relation_count=0,
                status="success",
            )

            # stats 集計クエリ（CLI の stats コマンド相当）
            total_chunks = db.count_chunks()
            assert total_chunks == len(chunks)

            # セッション別集計
            cursor = conn.execute(
                "SELECT session_id, COUNT(*) AS chunk_count, "
                "       MIN(created_at) AS first_chunk, "
                "       MAX(created_at) AS last_chunk "
                "FROM chunks "
                "GROUP BY session_id "
                "ORDER BY last_chunk DESC"
            )
            session_rows = cursor.fetchall()
            assert len(session_rows) == 1
            assert session_rows[0]["session_id"] == _SESSION_ID
            assert session_rows[0]["chunk_count"] == len(chunks)

            # インポートログ数
            cursor = conn.execute("SELECT COUNT(*) FROM import_log")
            import_count = cursor.fetchone()[0]
            assert import_count == 1

            # 抽出ログ数
            cursor = conn.execute("SELECT COUNT(*) FROM extraction_log")
            extraction_count = cursor.fetchone()[0]
            assert extraction_count == 1


# ---------------------------------------------------------------------------
# E2E 統合テスト: JSONL ファイル読み込みからの全パイプライン
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestE2EFileBasedPipeline:
    """E2E: JSONL ファイル読み込み -> parse -> extract -> save -> search."""

    def test_正常系_JSONLファイルから全パイプラインが動作する(
        self, db_path: Path, sample_jsonl: Path
    ) -> None:
        """実際の JSONL ファイルから全パイプラインが E2E で動作する."""
        # Step 1: JSONL ファイル読み込み
        lines = sample_jsonl.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) >= 4

        # Step 2: parse -> chunk
        chunks = parse_transcript(lines)
        assert len(chunks) >= 2

        # Step 3: extract（ルールベース）
        extractions: list[ChunkExtraction] = []
        for chunk in chunks:
            extraction = rule_based_predetect(chunk.content)
            extractions.append(extraction)

        total_entities = sum(len(e.entities) for e in extractions)
        total_topics = sum(len(e.topics) for e in extractions)
        assert total_entities >= 3, (
            f"Expected at least 3 entities (Python, Pydantic, Neo4j), got {total_entities}"
        )

        # Step 4: save
        with SessionMemoryDB(db_path) as db:
            conn = db._require_conn()

            for chunk in chunks:
                db.save_chunk(
                    chunk_key=chunk.chunk_key,
                    session_id=chunk.session_id,
                    content=chunk.content,
                    role=chunk.role,
                )

            # ログ記録
            db.log_import(
                session_id=_SESSION_ID,
                chunk_count=len(chunks),
                status="success",
            )
            db.log_extraction(
                session_id=_SESSION_ID,
                entity_count=total_entities,
                relation_count=total_topics,
                status="success",
            )

            # Step 5: search（LIKE フォールバック）
            cursor = conn.execute(
                "SELECT chunk_key, content FROM chunks "
                "WHERE content LIKE ? "
                "ORDER BY created_at DESC LIMIT 10",
                ("%Neo4j%",),
            )
            like_results = cursor.fetchall()
            assert len(like_results) >= 1, (
                "LIKE search for 'Neo4j' should return results"
            )
            assert any("Neo4j" in r["content"] for r in like_results)

            # Step 6: stats 検証
            assert db.count_chunks() == len(chunks)
            import_logs = db.get_import_logs(_SESSION_ID)
            assert len(import_logs) == 1
            extraction_logs = db.get_extraction_logs(_SESSION_ID)
            assert len(extraction_logs) == 1

    def test_正常系_冪等性_同じファイルを2回インポートしても重複しない(
        self, db_path: Path, sample_jsonl: Path
    ) -> None:
        """同じ JSONL を2回インポートしても冪等にチャンクが更新される."""
        lines = sample_jsonl.read_text(encoding="utf-8").strip().splitlines()
        chunks = parse_transcript(lines)

        # 1回目のインポート
        with SessionMemoryDB(db_path) as db:
            for chunk in chunks:
                db.save_chunk(
                    chunk_key=chunk.chunk_key,
                    session_id=chunk.session_id,
                    content=chunk.content,
                    role=chunk.role,
                )
            count_after_first = db.count_chunks()

        # 2回目のインポート（同じデータ）
        with SessionMemoryDB(db_path) as db:
            for chunk in chunks:
                db.save_chunk(
                    chunk_key=chunk.chunk_key,
                    session_id=chunk.session_id,
                    content=chunk.content,
                    role=chunk.role,
                )
            count_after_second = db.count_chunks()

        # 冪等: レコード数は変わらない
        assert count_after_first == count_after_second
