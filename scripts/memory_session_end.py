"""SessionEnd Hook ラッパースクリプト.

Claude Code の SessionEnd Hook から呼び出される薄いラッパー。
stdin から JSON を読み込み、session_memory.hook.run_session_end_hook() を実行する。

使用方法（settings.json の hooks.SessionEnd で設定）::

    uv run python scripts/memory_session_end.py

stdin JSON 例::

    {
        "session_id": "abc-123-def",
        "cwd": "/path/to/project",
        "duration_ms": 60000,
        "num_turns": 10,
        "result": "success"
    }

終了コード:
- 0: 正常終了（スキップも含む）
- 1: エラー
"""

from __future__ import annotations

import asyncio
import json
import sys


def main() -> int:
    """メインエントリポイント.

    Returns
    -------
    int
        終了コード（0: 成功, 1: エラー）
    """
    # stdin から JSON 読み込み
    try:
        raw_input = sys.stdin.read()
    except Exception:
        sys.stderr.write("ERROR: Failed to read stdin\n")
        return 1

    # 遅延インポート（起動時間短縮）
    try:
        from session_memory.hook import parse_hook_input, run_session_end_hook
    except ImportError as e:
        sys.stderr.write(f"ERROR: Failed to import session_memory: {e}\n")
        return 1

    # Hook 入力パース
    hook_input = parse_hook_input(raw_input)
    if hook_input is None:
        sys.stderr.write("WARN: Invalid hook input, skipping\n")
        return 0  # 不正入力はスキップ扱い（エラーではない）

    # メインフロー実行
    try:
        result = asyncio.run(run_session_end_hook(hook_input=hook_input))
    except Exception as e:
        sys.stderr.write(f"ERROR: Hook execution failed: {e}\n")
        return 1

    # 結果出力（デバッグ用）
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")

    return 0 if result.get("status") != "error" else 1


if __name__ == "__main__":
    sys.exit(main())
