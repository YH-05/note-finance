"""session_memory CLI bulk-import のユニットテスト.

~/.claude/projects/ 全走査バルクインポート機能を検証する:
- ディレクトリ走査とセッション発見
- import_log による中断再開（重複スキップ）
- --progress / --parallel オプション
- プロジェクト別分類
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import pytest
from click.testing import CliRunner

from session_memory.cli.main import cli
from session_memory.db import SessionMemoryDB

# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner() -> CliRunner:
    """Click テストランナー."""
    return CliRunner()


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    """テスト用 SQLite DB パス."""
    return tmp_path / "test_session_memory.db"


@pytest.fixture()
def fake_claude_projects(tmp_path: Path) -> Path:
    """テスト用の ~/.claude/projects/ ディレクトリ構造を作成する.

    構造:
      projects/
        -Users-user-Desktop-note-finance/
          session-001.jsonl
          session-002.jsonl
        -Users-user-Desktop-other-project/
          session-003.jsonl
    """
    projects_dir = tmp_path / ".claude" / "projects"

    # プロジェクト1: note-finance
    proj1 = projects_dir / "-Users-user-Desktop-note-finance"
    proj1.mkdir(parents=True)
    _write_transcript(
        proj1 / "session-001.jsonl",
        session_id="session-001",
        cwd="/Users/user/Desktop/note-finance",
    )
    _write_transcript(
        proj1 / "session-002.jsonl",
        session_id="session-002",
        cwd="/Users/user/Desktop/note-finance",
    )

    # プロジェクト2: other-project
    proj2 = projects_dir / "-Users-user-Desktop-other-project"
    proj2.mkdir(parents=True)
    _write_transcript(
        proj2 / "session-003.jsonl",
        session_id="session-003",
        cwd="/Users/user/Desktop/other-project",
    )

    return projects_dir


def _write_transcript(
    path: Path,
    *,
    session_id: str,
    cwd: str,
) -> None:
    """テスト用 transcript.jsonl ファイルを作成する."""
    lines = [
        json.dumps(
            {
                "type": "message",
                "sessionId": session_id,
                "cwd": cwd,
                "message": {"role": "user", "content": "テスト質問です"},
            }
        ),
        json.dumps(
            {
                "type": "message",
                "sessionId": session_id,
                "cwd": cwd,
                "message": {
                    "role": "assistant",
                    "content": "テスト回答です。詳細な説明を含みます。",
                },
            }
        ),
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# discover_sessions テスト
# ---------------------------------------------------------------------------


class TestDiscoverSessions:
    """discover_sessions() のテスト."""

    def test_正常系_全セッションを発見できる(self, fake_claude_projects: Path) -> None:
        """~/.claude/projects/ 配下の全 .jsonl を発見できる."""
        from session_memory.cli.bulk_import import discover_sessions

        sessions = discover_sessions(fake_claude_projects)
        assert len(sessions) == 3
        session_ids = {s.session_id for s in sessions}
        assert session_ids == {"session-001", "session-002", "session-003"}

    def test_正常系_プロジェクト別に分類される(
        self, fake_claude_projects: Path
    ) -> None:
        """セッションがプロジェクトディレクトリ名で分類される."""
        from session_memory.cli.bulk_import import discover_sessions

        sessions = discover_sessions(fake_claude_projects)
        projects = {s.project_dir_name for s in sessions}
        assert "-Users-user-Desktop-note-finance" in projects
        assert "-Users-user-Desktop-other-project" in projects

    def test_エッジケース_空ディレクトリで空リスト(self, tmp_path: Path) -> None:
        """空のプロジェクトディレクトリでは空リストを返す."""
        from session_memory.cli.bulk_import import discover_sessions

        empty_dir = tmp_path / "empty_projects"
        empty_dir.mkdir(parents=True)
        sessions = discover_sessions(empty_dir)
        assert sessions == []

    def test_エッジケース_存在しないディレクトリで空リスト(
        self, tmp_path: Path
    ) -> None:
        """存在しないディレクトリでは空リストを返す."""
        from session_memory.cli.bulk_import import discover_sessions

        sessions = discover_sessions(tmp_path / "nonexistent")
        assert sessions == []

    def test_正常系_jsonl以外のファイルは無視(self, tmp_path: Path) -> None:
        """.jsonl 以外のファイル（ディレクトリ含む）は無視される."""
        from session_memory.cli.bulk_import import discover_sessions

        projects_dir = tmp_path / "projects"
        proj = projects_dir / "-Users-user-Desktop-test"
        proj.mkdir(parents=True)

        # .jsonl ファイル
        _write_transcript(
            proj / "session-abc.jsonl",
            session_id="session-abc",
            cwd="/Users/user/Desktop/test",
        )
        # 非 .jsonl ファイル
        (proj / "config.json").write_text("{}", encoding="utf-8")
        # サブディレクトリ（セッションID名だが非ファイル）
        (proj / "session-xyz").mkdir()

        sessions = discover_sessions(projects_dir)
        assert len(sessions) == 1
        assert sessions[0].session_id == "session-abc"


# ---------------------------------------------------------------------------
# filter_already_imported テスト
# ---------------------------------------------------------------------------


class TestFilterAlreadyImported:
    """filter_already_imported() のテスト."""

    def test_正常系_未インポートセッションのみ残る(
        self,
        tmp_db: Path,
        fake_claude_projects: Path,
    ) -> None:
        """import_log に存在するセッションはフィルタされる."""
        from session_memory.cli.bulk_import import (
            discover_sessions,
            filter_already_imported,
        )

        # session-001 をインポート済みにする
        with SessionMemoryDB(tmp_db) as db:
            db.log_import(
                session_id="session-001",
                chunk_count=1,
                status="success",
            )

        sessions = discover_sessions(fake_claude_projects)

        with SessionMemoryDB(tmp_db) as db:
            filtered = filter_already_imported(db, sessions)

        filtered_ids = {s.session_id for s in filtered}
        assert "session-001" not in filtered_ids
        assert "session-002" in filtered_ids
        assert "session-003" in filtered_ids

    def test_エッジケース_全て未インポートなら全て残る(
        self,
        tmp_db: Path,
        fake_claude_projects: Path,
    ) -> None:
        """全て未インポートなら全セッションが残る."""
        from session_memory.cli.bulk_import import (
            discover_sessions,
            filter_already_imported,
        )

        sessions = discover_sessions(fake_claude_projects)

        with SessionMemoryDB(tmp_db) as db:
            filtered = filter_already_imported(db, sessions)

        assert len(filtered) == len(sessions)


# ---------------------------------------------------------------------------
# import_single_session テスト
# ---------------------------------------------------------------------------


class TestImportSingleSession:
    """import_single_session() のテスト."""

    def test_正常系_単一セッションをインポートできる(
        self,
        tmp_db: Path,
        fake_claude_projects: Path,
    ) -> None:
        """1つのセッションを正常にインポートできる."""
        from session_memory.cli.bulk_import import (
            ImportResult,
            discover_sessions,
            import_single_session,
        )

        sessions = discover_sessions(fake_claude_projects)
        target = next(s for s in sessions if s.session_id == "session-001")

        with SessionMemoryDB(tmp_db) as db:
            result = import_single_session(db, target)

        assert isinstance(result, ImportResult)
        assert result.session_id == "session-001"
        assert result.status == "success"
        assert result.chunk_count > 0

    def test_正常系_インポート後にimport_logが記録される(
        self,
        tmp_db: Path,
        fake_claude_projects: Path,
    ) -> None:
        """インポート後に import_log が記録される."""
        from session_memory.cli.bulk_import import (
            discover_sessions,
            import_single_session,
        )

        sessions = discover_sessions(fake_claude_projects)
        target = next(s for s in sessions if s.session_id == "session-001")

        with SessionMemoryDB(tmp_db) as db:
            import_single_session(db, target)
            logs = db.get_import_logs("session-001")

        assert len(logs) == 1
        assert logs[0]["status"] == "success"


# ---------------------------------------------------------------------------
# CLI bulk-import-all テスト
# ---------------------------------------------------------------------------


class TestBulkImportAllCli:
    """CLI bulk-import-all サブコマンドのテスト."""

    def test_正常系_全プロジェクトをインポートできる(
        self,
        runner: CliRunner,
        tmp_db: Path,
        fake_claude_projects: Path,
    ) -> None:
        """bulk-import-all で全プロジェクトの全セッションをインポートできる."""
        result = runner.invoke(
            cli,
            [
                "--db-path",
                str(tmp_db),
                "bulk-import-all",
                "--projects-dir",
                str(fake_claude_projects),
            ],
        )
        assert result.exit_code == 0

        # DB にチャンクが保存されている
        with SessionMemoryDB(tmp_db) as db:
            assert db.count_chunks() > 0

    def test_正常系_json出力モード(
        self,
        runner: CliRunner,
        tmp_db: Path,
        fake_claude_projects: Path,
    ) -> None:
        """--json オプションで JSON 出力が得られる."""
        result = runner.invoke(
            cli,
            [
                "--db-path",
                str(tmp_db),
                "bulk-import-all",
                "--projects-dir",
                str(fake_claude_projects),
                "--json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "total_discovered" in data
        assert "imported" in data
        assert "skipped" in data

    def test_正常系_中断再開で重複スキップ(
        self,
        runner: CliRunner,
        tmp_db: Path,
        fake_claude_projects: Path,
    ) -> None:
        """2回実行すると、2回目は既インポート分をスキップする."""
        # 1回目
        runner.invoke(
            cli,
            [
                "--db-path",
                str(tmp_db),
                "bulk-import-all",
                "--projects-dir",
                str(fake_claude_projects),
            ],
        )

        # 2回目
        result = runner.invoke(
            cli,
            [
                "--db-path",
                str(tmp_db),
                "bulk-import-all",
                "--projects-dir",
                str(fake_claude_projects),
                "--json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["imported"] == 0
        assert data["skipped"] == 3

    def test_正常系_progress表示(
        self,
        runner: CliRunner,
        tmp_db: Path,
        fake_claude_projects: Path,
    ) -> None:
        """--progress オプションでリッチ進捗表示が有効になる."""
        result = runner.invoke(
            cli,
            [
                "--db-path",
                str(tmp_db),
                "bulk-import-all",
                "--projects-dir",
                str(fake_claude_projects),
                "--progress",
            ],
        )
        assert result.exit_code == 0

    def test_正常系_parallel指定(
        self,
        runner: CliRunner,
        tmp_db: Path,
        fake_claude_projects: Path,
    ) -> None:
        """--parallel オプションで並列数を指定できる."""
        result = runner.invoke(
            cli,
            [
                "--db-path",
                str(tmp_db),
                "bulk-import-all",
                "--projects-dir",
                str(fake_claude_projects),
                "--parallel",
                "2",
            ],
        )
        assert result.exit_code == 0

    def test_エッジケース_空ディレクトリで正常終了(
        self,
        runner: CliRunner,
        tmp_db: Path,
        tmp_path: Path,
    ) -> None:
        """空のプロジェクトディレクトリでもエラーなく終了する."""
        empty_dir = tmp_path / "empty_projects"
        empty_dir.mkdir(parents=True)

        result = runner.invoke(
            cli,
            [
                "--db-path",
                str(tmp_db),
                "bulk-import-all",
                "--projects-dir",
                str(empty_dir),
                "--json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_discovered"] == 0
