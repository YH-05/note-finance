"""session_memory.hook のユニットテスト.

SessionEnd Hook のエントリポイントを検証する:
- stdin JSON パースの正常動作
- 対象外プロジェクトの早期スキップ
- import_log による重複実行防止
- SQLite + Neo4j 同時投入フロー
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------


@pytest.fixture()
def valid_hook_input() -> dict[str, Any]:
    """有効な SessionEnd hook の stdin JSON."""
    return {
        "session_id": "abc-123-def",
        "cwd": "/Users/user/.worktrees/note-finance/feature-branch",
        "duration_ms": 60000,
        "num_turns": 10,
        "result": "success",
        "transcript_path": "/tmp/test_transcript.jsonl",
    }


@pytest.fixture()
def non_target_hook_input() -> dict[str, Any]:
    """対象外プロジェクトの SessionEnd hook stdin JSON."""
    return {
        "session_id": "xyz-789",
        "cwd": "/Users/user/Desktop/other-project",
        "duration_ms": 30000,
        "num_turns": 5,
        "result": "success",
    }


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    """テスト用 SQLite DB パス."""
    return tmp_path / "test_session_memory.db"


@pytest.fixture()
def transcript_file(tmp_path: Path) -> Path:
    """テスト用 transcript.jsonl ファイル."""
    lines = [
        json.dumps(
            {
                "type": "message",
                "sessionId": "abc-123-def",
                "cwd": "/Users/user/.worktrees/note-finance/feature-branch",
                "message": {"role": "user", "content": "テストメッセージ"},
            }
        ),
        json.dumps(
            {
                "type": "message",
                "sessionId": "abc-123-def",
                "cwd": "/Users/user/.worktrees/note-finance/feature-branch",
                "message": {
                    "role": "assistant",
                    "content": "テストレスポンスです。",
                },
            }
        ),
    ]
    path = tmp_path / "transcript.jsonl"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# parse_hook_input テスト
# ---------------------------------------------------------------------------


class TestParseHookInput:
    """parse_hook_input() のテスト."""

    def test_正常系_有効なJSONをパースできる(
        self, valid_hook_input: dict[str, Any]
    ) -> None:
        """有効な JSON 文字列から HookInput を生成できる."""
        from session_memory.hook import parse_hook_input

        raw = json.dumps(valid_hook_input)
        result = parse_hook_input(raw)
        assert result is not None
        assert result.session_id == "abc-123-def"
        assert "note-finance" in result.cwd

    def test_異常系_不正なJSONでNone返却(self) -> None:
        """不正な JSON 文字列の場合は None を返す."""
        from session_memory.hook import parse_hook_input

        result = parse_hook_input("not-json{{{")
        assert result is None

    def test_異常系_空文字列でNone返却(self) -> None:
        """空文字列の場合は None を返す."""
        from session_memory.hook import parse_hook_input

        result = parse_hook_input("")
        assert result is None

    def test_異常系_session_id欠落でNone返却(self) -> None:
        """session_id が欠落した場合は None を返す."""
        from session_memory.hook import parse_hook_input

        result = parse_hook_input(json.dumps({"cwd": "/some/path"}))
        assert result is None


# ---------------------------------------------------------------------------
# is_target_project テスト
# ---------------------------------------------------------------------------


class TestIsTargetProject:
    """is_target_project() のテスト."""

    def test_正常系_note_financeプロジェクトは対象(self) -> None:
        """note-finance プロジェクトは対象として判定される."""
        from session_memory.hook import is_target_project

        assert is_target_project("note-finance") is True

    def test_正常系_worktreeパスからnote_finance解決(self) -> None:
        """worktree パスから note-finance が解決される場合は対象."""
        from session_memory.hook import is_target_project

        assert is_target_project("note-finance") is True

    def test_正常系_対象外プロジェクトはスキップ(self) -> None:
        """対象外プロジェクトは非対象として判定される."""
        from session_memory.hook import is_target_project

        assert is_target_project("other-project") is False

    def test_正常系_空文字列は非対象(self) -> None:
        """空文字列は非対象として判定される."""
        from session_memory.hook import is_target_project

        assert is_target_project("") is False


# ---------------------------------------------------------------------------
# is_already_imported テスト
# ---------------------------------------------------------------------------


class TestIsAlreadyImported:
    """is_already_imported() のテスト."""

    def test_正常系_未インポートのセッションはFalse(self, tmp_db: Path) -> None:
        """未インポートのセッションは False を返す."""
        from session_memory.db import SessionMemoryDB
        from session_memory.hook import is_already_imported

        with SessionMemoryDB(tmp_db) as db:
            result = is_already_imported(db, "new-session")
            assert result is False

    def test_正常系_インポート済みセッションはTrue(self, tmp_db: Path) -> None:
        """インポート済みのセッションは True を返す."""
        from session_memory.db import SessionMemoryDB
        from session_memory.hook import is_already_imported

        with SessionMemoryDB(tmp_db) as db:
            db.log_import(
                session_id="existing-session",
                chunk_count=5,
                status="success",
            )
            db._require_conn().commit()
            result = is_already_imported(db, "existing-session")
            assert result is True


# ---------------------------------------------------------------------------
# save_chunks_to_sqlite テスト
# ---------------------------------------------------------------------------


class TestSaveChunksToSqlite:
    """save_chunks_to_sqlite() のテスト."""

    def test_正常系_チャンクをDBに保存できる(
        self,
        tmp_db: Path,
    ) -> None:
        """チャンクリストを SQLite DB に保存できる."""
        from session_memory.chunker import Chunk
        from session_memory.db import SessionMemoryDB
        from session_memory.hook import save_chunks_to_sqlite

        chunks = [
            Chunk(
                chunk_key="s1::0",
                session_id="s1",
                content="Test content 1",
                role="assistant",
                project="note-finance",
            ),
            Chunk(
                chunk_key="s1::1",
                session_id="s1",
                content="Test content 2",
                role="assistant",
                project="note-finance",
            ),
        ]

        with SessionMemoryDB(tmp_db) as db:
            save_chunks_to_sqlite(db, chunks)
            assert db.count_chunks() == 2
            row = db.get_chunk("s1::0")
            assert row is not None
            assert row.content == "Test content 1"

    def test_エッジケース_空チャンクリストで正常終了(
        self,
        tmp_db: Path,
    ) -> None:
        """空のチャンクリストでもエラーなく終了する."""
        from session_memory.db import SessionMemoryDB
        from session_memory.hook import save_chunks_to_sqlite

        with SessionMemoryDB(tmp_db) as db:
            save_chunks_to_sqlite(db, [])
            assert db.count_chunks() == 0


# ---------------------------------------------------------------------------
# run_session_end_hook 統合テスト（モック使用）
# ---------------------------------------------------------------------------


class TestRunSessionEndHook:
    """run_session_end_hook() の統合テスト（外部依存はモック）."""

    @pytest.mark.asyncio()
    async def test_正常系_有効な入力でSQLite保存成功(
        self,
        tmp_db: Path,
        transcript_file: Path,
    ) -> None:
        """有効な入力で SQLite 保存が成功する."""
        from session_memory.hook import HookInput, run_session_end_hook

        hook_input = HookInput(
            session_id="abc-123-def",
            cwd="/Users/user/.worktrees/note-finance/feature-branch",
            duration_ms=60000,
            num_turns=10,
            transcript_path=str(transcript_file),
        )

        with patch(
            "session_memory.hook._run_neo4j_pipeline",
            new_callable=AsyncMock,
        ):
            result = await run_session_end_hook(
                hook_input=hook_input,
                db_path=tmp_db,
            )

        assert result["status"] == "success"
        assert result["chunks_saved"] > 0

    @pytest.mark.asyncio()
    async def test_正常系_対象外プロジェクトでスキップ(
        self,
        tmp_db: Path,
    ) -> None:
        """対象外プロジェクトの場合はスキップ結果を返す."""
        from session_memory.hook import HookInput, run_session_end_hook

        hook_input = HookInput(
            session_id="xyz-789",
            cwd="/Users/user/Desktop/other-project",
            duration_ms=30000,
            num_turns=5,
        )

        result = await run_session_end_hook(
            hook_input=hook_input,
            db_path=tmp_db,
        )

        assert result["status"] == "skipped"
        assert (
            "target" in result["reason"].lower()
            or "project" in result["reason"].lower()
        )

    @pytest.mark.asyncio()
    async def test_正常系_重複セッションでスキップ(
        self,
        tmp_db: Path,
    ) -> None:
        """既にインポート済みのセッションはスキップする."""
        from session_memory.db import SessionMemoryDB
        from session_memory.hook import HookInput, run_session_end_hook

        # 事前にインポートログを作成
        with SessionMemoryDB(tmp_db) as db:
            db.log_import(
                session_id="dup-session",
                chunk_count=3,
                status="success",
            )

        hook_input = HookInput(
            session_id="dup-session",
            cwd="/Users/user/.worktrees/note-finance/feature-branch",
            duration_ms=60000,
            num_turns=10,
        )

        result = await run_session_end_hook(
            hook_input=hook_input,
            db_path=tmp_db,
        )

        assert result["status"] == "skipped"
        assert (
            "duplicate" in result["reason"].lower()
            or "already" in result["reason"].lower()
        )

    @pytest.mark.asyncio()
    async def test_正常系_transcript_path未指定でClaude標準パスを探索(
        self,
        tmp_path: Path,
    ) -> None:
        """transcript_path が未指定の場合、Claude 標準パスを探索する."""
        from pathlib import Path as PathCls

        from session_memory.hook import HookInput, resolve_transcript_path

        # テスト用に Claude projects ディレクトリを模擬
        fake_projects_dir = tmp_path / ".claude" / "projects"
        fake_project_dir = fake_projects_dir / "test-project"
        fake_project_dir.mkdir(parents=True)

        # セッション ID に対応する transcript.jsonl を配置
        transcript = fake_project_dir / "test-session-id.jsonl"
        transcript.write_text('{"test": true}', encoding="utf-8")

        hook_input = HookInput(
            session_id="test-session-id",
            cwd="/Users/user/.worktrees/note-finance/feature-branch",
            duration_ms=60000,
            num_turns=10,
        )

        # _CLAUDE_PROJECTS_DIR をモック
        with patch(
            "session_memory.hook._CLAUDE_PROJECTS_DIR",
            fake_projects_dir,
        ):
            path = resolve_transcript_path(hook_input)
            assert path is not None
            assert path.name == "test-session-id.jsonl"

    def test_正常系_transcript_path指定で直接パス使用(
        self,
        transcript_file: Path,
    ) -> None:
        """transcript_path が指定されている場合はそのパスを使用する."""
        from session_memory.hook import HookInput, resolve_transcript_path

        hook_input = HookInput(
            session_id="abc-123-def",
            cwd="/Users/user/.worktrees/note-finance/feature-branch",
            transcript_path=str(transcript_file),
        )

        path = resolve_transcript_path(hook_input)
        assert path is not None
        assert path == transcript_file
