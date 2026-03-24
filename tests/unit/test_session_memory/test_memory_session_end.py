"""scripts/memory_session_end.py のユニットテスト."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch


class TestMain:
    """main() エントリポイントのテスト."""

    def test_正常系_有効な入力で正常終了(self) -> None:
        """有効な JSON 入力で exit code 0 を返すことを確認する."""
        from scripts.memory_session_end import main

        hook_input_data = {
            "session_id": "test-session-001",
            "cwd": "/Users/test/note-finance",
            "duration_ms": 5000,
            "num_turns": 3,
            "result": "success",
        }
        mock_result = {"status": "skipped", "reason": "Non-target project: test"}

        with (
            patch("sys.stdin") as mock_stdin,
            patch(
                "session_memory.hook.run_session_end_hook",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            mock_stdin.read.return_value = json.dumps(hook_input_data)
            exit_code = main()

        assert exit_code == 0

    def test_正常系_不正入力でスキップ(self) -> None:
        """不正な JSON 入力で parse_hook_input が None を返し、exit code 0 になる."""
        from scripts.memory_session_end import main

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.return_value = "not a json"
            exit_code = main()

        assert exit_code == 0

    def test_異常系_Hook実行失敗でexit_code_1(self) -> None:
        """run_session_end_hook が例外を投げた場合 exit code 1 を返す."""
        from scripts.memory_session_end import main

        hook_input_data = {
            "session_id": "test-session-002",
            "cwd": "/Users/test/note-finance",
            "duration_ms": 5000,
            "num_turns": 3,
            "result": "success",
        }

        with (
            patch("sys.stdin") as mock_stdin,
            patch(
                "session_memory.hook.run_session_end_hook",
                new_callable=AsyncMock,
                side_effect=RuntimeError("Hook failed"),
            ),
        ):
            mock_stdin.read.return_value = json.dumps(hook_input_data)
            exit_code = main()

        assert exit_code == 1

    def test_異常系_stdin読み込み失敗でexit_code_1(self) -> None:
        """stdin.read() が例外を投げた場合 exit code 1 を返す."""
        from scripts.memory_session_end import main

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.read.side_effect = OSError("stdin broken")
            exit_code = main()

        assert exit_code == 1

    def test_正常系_エラーステータスでexit_code_1(self) -> None:
        """result の status が 'error' の場合 exit code 1 を返す."""
        from scripts.memory_session_end import main

        hook_input_data = {
            "session_id": "test-session-003",
            "cwd": "/Users/test/note-finance",
            "duration_ms": 5000,
            "num_turns": 3,
            "result": "success",
        }
        mock_result = {"status": "error", "reason": "Something went wrong"}

        with (
            patch("sys.stdin") as mock_stdin,
            patch(
                "session_memory.hook.run_session_end_hook",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            mock_stdin.read.return_value = json.dumps(hook_input_data)
            exit_code = main()

        assert exit_code == 1
