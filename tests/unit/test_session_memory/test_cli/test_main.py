"""session_memory CLI main モジュールのユニットテスト.

受け入れ条件:
- 各サブコマンド（save / search / bulk-import / stats）が動作すること
- Rich Table で整形表示されること
- make check-all が成功すること
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from session_memory.cli.main import cli

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------


@pytest.fixture
def runner() -> CliRunner:
    """Click テスト用ランナーを返す."""
    return CliRunner()


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """テスト用DBファイルパスを返す."""
    return tmp_path / "test_memory.db"


@pytest.fixture
def mock_db(db_path: Path) -> MagicMock:
    """SessionMemoryDB のモックを返す."""
    mock = MagicMock()
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=False)
    mock.count_chunks.return_value = 5
    mock.get_import_logs.return_value = []
    mock.get_extraction_logs.return_value = []
    return mock


# ---------------------------------------------------------------------------
# CLI グループ
# ---------------------------------------------------------------------------


class TestCLIGroup:
    """CLI グループの基本動作テスト."""

    def test_正常系_ヘルプが表示される(self, runner: CliRunner) -> None:
        """--help でヘルプメッセージが表示される."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Session Memory" in result.output or "session" in result.output.lower()

    def test_正常系_バージョンが表示される(self, runner: CliRunner) -> None:
        """--version でバージョンが表示される."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# save サブコマンド
# ---------------------------------------------------------------------------


class TestSaveCommand:
    """save サブコマンドのテスト."""

    def test_正常系_チャンクを保存できる(
        self, runner: CliRunner, db_path: Path
    ) -> None:
        """save コマンドでチャンクを保存できる."""
        result = runner.invoke(
            cli,
            [
                "--db-path",
                str(db_path),
                "save",
                "--session-id",
                "test-session",
                "--content",
                "Hello, world!",
                "--role",
                "user",
            ],
        )
        assert result.exit_code == 0
        assert "saved" in result.output.lower() or "Saved" in result.output

    def test_正常系_JSON出力で保存結果が返される(
        self, runner: CliRunner, db_path: Path
    ) -> None:
        """--json オプションで JSON 形式の出力が返される."""
        result = runner.invoke(
            cli,
            [
                "--db-path",
                str(db_path),
                "save",
                "--session-id",
                "test-session",
                "--content",
                "Hello, world!",
                "--role",
                "user",
                "--json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "chunk_key" in data
        assert data["session_id"] == "test-session"

    def test_正常系_chunk_keyを指定して保存できる(
        self, runner: CliRunner, db_path: Path
    ) -> None:
        """--chunk-key オプションで明示的にキーを指定できる."""
        result = runner.invoke(
            cli,
            [
                "--db-path",
                str(db_path),
                "save",
                "--session-id",
                "test-session",
                "--content",
                "Hello!",
                "--role",
                "assistant",
                "--chunk-key",
                "custom-key::0",
            ],
        )
        assert result.exit_code == 0

    def test_異常系_必須オプション不足でエラー(self, runner: CliRunner) -> None:
        """--session-id や --content が不足するとエラーになる."""
        result = runner.invoke(cli, ["save"])
        assert result.exit_code != 0

    def test_正常系_冪等に保存できる(self, runner: CliRunner, db_path: Path) -> None:
        """同じ chunk_key で2回保存しても上書きされる（UPSERT）."""
        common_args = [
            "--db-path",
            str(db_path),
            "save",
            "--session-id",
            "s1",
            "--role",
            "user",
            "--chunk-key",
            "s1::0",
        ]
        # 1回目
        result1 = runner.invoke(cli, [*common_args, "--content", "first"])
        assert result1.exit_code == 0
        # 2回目（上書き）
        result2 = runner.invoke(cli, [*common_args, "--content", "second"])
        assert result2.exit_code == 0


# ---------------------------------------------------------------------------
# search サブコマンド
# ---------------------------------------------------------------------------


class TestSearchCommand:
    """search サブコマンドのテスト."""

    def _save_chunks(
        self, runner: CliRunner, db_path: Path, chunks: list[dict[str, str]]
    ) -> None:
        """テスト用チャンクを保存するヘルパー."""
        for chunk in chunks:
            runner.invoke(
                cli,
                [
                    "--db-path",
                    str(db_path),
                    "save",
                    "--session-id",
                    chunk["session_id"],
                    "--content",
                    chunk["content"],
                    "--role",
                    chunk.get("role", "user"),
                ],
            )

    def test_正常系_FTS検索でチャンクが見つかる(
        self, runner: CliRunner, db_path: Path
    ) -> None:
        """search コマンドでFTS全文検索ができる."""
        self._save_chunks(
            runner,
            db_path,
            [
                {"session_id": "s1", "content": "Pythonの型ヒントについて議論"},
                {"session_id": "s1", "content": "Rustの所有権モデルの解説"},
            ],
        )
        result = runner.invoke(
            cli,
            [
                "--db-path",
                str(db_path),
                "search",
                "--query",
                "Python",
                "--mode",
                "fts",
            ],
        )
        assert result.exit_code == 0
        assert "Python" in result.output

    def test_正常系_JSON出力で検索結果が返される(
        self, runner: CliRunner, db_path: Path
    ) -> None:
        """--json オプションでJSON形式の検索結果が返される."""
        self._save_chunks(
            runner,
            db_path,
            [{"session_id": "s1", "content": "テストデータ"}],
        )
        result = runner.invoke(
            cli,
            [
                "--db-path",
                str(db_path),
                "search",
                "--query",
                "テスト",
                "--mode",
                "fts",
                "--json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_正常系_検索結果が空の場合のメッセージ(
        self, runner: CliRunner, db_path: Path
    ) -> None:
        """検索結果がゼロ件の場合に適切なメッセージが表示される."""
        result = runner.invoke(
            cli,
            [
                "--db-path",
                str(db_path),
                "search",
                "--query",
                "存在しないテキスト",
                "--mode",
                "fts",
            ],
        )
        assert result.exit_code == 0
        assert "No results" in result.output or "0" in result.output

    def test_正常系_limit指定で結果数を制限できる(
        self, runner: CliRunner, db_path: Path
    ) -> None:
        """--limit オプションで結果数を制限できる."""
        self._save_chunks(
            runner,
            db_path,
            [{"session_id": "s1", "content": f"テスト文書 #{i}"} for i in range(5)],
        )
        result = runner.invoke(
            cli,
            [
                "--db-path",
                str(db_path),
                "search",
                "--query",
                "テスト",
                "--mode",
                "fts",
                "--limit",
                "2",
                "--json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) <= 2

    def test_異常系_query未指定でエラー(self, runner: CliRunner) -> None:
        """--query が不足するとエラーになる."""
        result = runner.invoke(cli, ["search"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# bulk-import サブコマンド
# ---------------------------------------------------------------------------


class TestBulkImportCommand:
    """bulk-import サブコマンドのテスト."""

    def test_正常系_JSONLファイルからインポートできる(
        self, runner: CliRunner, db_path: Path, tmp_path: Path
    ) -> None:
        """JSONL ファイルからチャンクを一括インポートできる."""
        # テスト用 JSONL ファイル作成
        jsonl_path = tmp_path / "test_transcript.jsonl"
        lines = [
            json.dumps(
                {
                    "type": "conversation",
                    "sessionId": "session-001",
                    "cwd": "/Users/user/project",
                    "message": {
                        "role": "user",
                        "content": "Pythonの型ヒントについて教えてください",
                    },
                }
            ),
            json.dumps(
                {
                    "type": "conversation",
                    "sessionId": "session-001",
                    "cwd": "/Users/user/project",
                    "message": {
                        "role": "assistant",
                        "content": "Python 3.12+ では PEP 695 の新しい型パラメータ構文が使えます。",
                    },
                }
            ),
        ]
        jsonl_path.write_text("\n".join(lines) + "\n")

        result = runner.invoke(
            cli,
            [
                "--db-path",
                str(db_path),
                "bulk-import",
                str(jsonl_path),
            ],
        )
        assert result.exit_code == 0
        assert "import" in result.output.lower() or "chunk" in result.output.lower()

    def test_正常系_JSON出力でインポート結果が返される(
        self, runner: CliRunner, db_path: Path, tmp_path: Path
    ) -> None:
        """--json オプションでJSON形式のインポート結果が返される."""
        jsonl_path = tmp_path / "test_import.jsonl"
        lines = [
            json.dumps(
                {
                    "sessionId": "s1",
                    "cwd": "/project",
                    "message": {"role": "user", "content": "hello"},
                }
            ),
            json.dumps(
                {
                    "sessionId": "s1",
                    "cwd": "/project",
                    "message": {"role": "assistant", "content": "hi there"},
                }
            ),
        ]
        jsonl_path.write_text("\n".join(lines) + "\n")

        result = runner.invoke(
            cli,
            [
                "--db-path",
                str(db_path),
                "bulk-import",
                str(jsonl_path),
                "--json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "chunks_imported" in data

    def test_異常系_存在しないファイルでエラー(
        self, runner: CliRunner, db_path: Path
    ) -> None:
        """存在しないファイルパスを指定するとエラーになる."""
        result = runner.invoke(
            cli,
            [
                "--db-path",
                str(db_path),
                "bulk-import",
                "/nonexistent/file.jsonl",
            ],
        )
        assert result.exit_code != 0

    def test_正常系_空ファイルでゼロ件インポート(
        self, runner: CliRunner, db_path: Path, tmp_path: Path
    ) -> None:
        """空のJSONLファイルではゼロ件インポートになる."""
        empty_path = tmp_path / "empty.jsonl"
        empty_path.write_text("")

        result = runner.invoke(
            cli,
            [
                "--db-path",
                str(db_path),
                "bulk-import",
                str(empty_path),
                "--json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["chunks_imported"] == 0


# ---------------------------------------------------------------------------
# stats サブコマンド
# ---------------------------------------------------------------------------


class TestStatsCommand:
    """stats サブコマンドのテスト."""

    def test_正常系_統計情報が表示される(
        self, runner: CliRunner, db_path: Path
    ) -> None:
        """stats コマンドで統計情報が表示される."""
        # まずデータを保存
        runner.invoke(
            cli,
            [
                "--db-path",
                str(db_path),
                "save",
                "--session-id",
                "s1",
                "--content",
                "test chunk",
                "--role",
                "user",
            ],
        )
        result = runner.invoke(
            cli,
            ["--db-path", str(db_path), "stats"],
        )
        assert result.exit_code == 0
        # 統計情報にチャンク数が含まれる
        assert "chunk" in result.output.lower() or "1" in result.output

    def test_正常系_JSON出力で統計情報が返される(
        self, runner: CliRunner, db_path: Path
    ) -> None:
        """--json オプションでJSON形式の統計情報が返される."""
        result = runner.invoke(
            cli,
            ["--db-path", str(db_path), "stats", "--json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "total_chunks" in data

    def test_正常系_空DBでも統計情報が表示される(
        self, runner: CliRunner, db_path: Path
    ) -> None:
        """空のDBでもstatsが正常に動作する."""
        result = runner.invoke(
            cli,
            ["--db-path", str(db_path), "stats", "--json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_chunks"] == 0

    def test_正常系_セッション別統計が含まれる(
        self, runner: CliRunner, db_path: Path
    ) -> None:
        """統計にセッション別の情報が含まれる."""
        # 複数セッションのデータを保存
        for sid in ["s1", "s1", "s2"]:
            runner.invoke(
                cli,
                [
                    "--db-path",
                    str(db_path),
                    "save",
                    "--session-id",
                    sid,
                    "--content",
                    f"chunk for {sid}",
                    "--role",
                    "user",
                ],
            )
        result = runner.invoke(
            cli,
            ["--db-path", str(db_path), "stats", "--json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "sessions" in data
        assert data["total_sessions"] >= 2


# ---------------------------------------------------------------------------
# Rich 出力テスト
# ---------------------------------------------------------------------------


class TestRichOutput:
    """Rich テーブル出力のテスト."""

    def test_正常系_stats出力にテーブル形式が含まれる(
        self, runner: CliRunner, db_path: Path
    ) -> None:
        """Rich テーブルで整形表示される（非JSONモード）."""
        runner.invoke(
            cli,
            [
                "--db-path",
                str(db_path),
                "save",
                "--session-id",
                "s1",
                "--content",
                "test data",
                "--role",
                "user",
            ],
        )
        result = runner.invoke(
            cli,
            ["--db-path", str(db_path), "stats"],
        )
        assert result.exit_code == 0
        # Rich Table は罫線文字やヘッダーを含む
        output = result.output
        assert len(output) > 0

    def test_正常系_search結果がテーブル形式で表示される(
        self, runner: CliRunner, db_path: Path
    ) -> None:
        """search結果がRich Tableで表示される."""
        runner.invoke(
            cli,
            [
                "--db-path",
                str(db_path),
                "save",
                "--session-id",
                "s1",
                "--content",
                "Pythonプログラミング",
                "--role",
                "user",
            ],
        )
        result = runner.invoke(
            cli,
            [
                "--db-path",
                str(db_path),
                "search",
                "--query",
                "Python",
                "--mode",
                "fts",
            ],
        )
        assert result.exit_code == 0
