#!/usr/bin/env python3
"""PostToolUse hook: research-input JSON 書き込み検出 → Neo4j 自動投入.

Write ツールで .tmp/research-input/*.json が作成されたとき、
以下の2ステップを自動実行して research-neo4j に投入する:

  1. emit_research_queue.py --command web-research --input {path}
  2. ingest_graph_queue.py --file {生成された graph-queue JSON}

設定方法（settings.json）:
    "hooks": {
        "PostToolUse": [
            {
                "matcher": "Write",
                "hooks": [
                    {
                        "type": "command",
                        "command": "uv run python $CLAUDE_PROJECT_DIR/.claude/hooks/auto-kg-ingest.py"
                    }
                ]
            }
        ]
    }
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
LOG_FILE = PROJECT_DIR / ".tmp" / "auto-kg-ingest.log"
RESEARCH_INPUT_DIR = PROJECT_DIR / ".tmp" / "research-input"
GRAPH_QUEUE_DIR = PROJECT_DIR / ".tmp" / "graph-queue" / "web-research"

REQUIRED_KEYS = {"session_id", "sources", "facts", "entities", "topics"}


def _log(msg: str) -> None:
    """ログファイルに追記."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")


def _is_research_input(file_path: str) -> bool:
    """Write 先が .tmp/research-input/*.json かを判定."""
    p = Path(file_path)
    return (
        p.suffix == ".json"
        and "research-input" in p.parts
        and ".tmp" in p.parts
    )


def _validate_json(file_path: Path) -> bool:
    """research-input JSON が完全かを検証."""
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return REQUIRED_KEYS.issubset(data.keys())


def _find_latest_graph_queue() -> Path | None:
    """直近に生成された graph-queue JSON を返す."""
    if not GRAPH_QUEUE_DIR.exists():
        return None
    files = sorted(
        (f for f in GRAPH_QUEUE_DIR.glob("gq-*.json") if "processed" not in f.parts),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    return files[0] if files else None


def main() -> None:
    """stdin から hook イベントを読み込み、KG 投入パイプラインを実行."""
    try:
        raw = sys.stdin.read()
        if not raw:
            return
        event = json.loads(raw)
    except (json.JSONDecodeError, OSError):
        return

    tool_input = event.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    # research-input JSON でなければ何もしない
    if not _is_research_input(file_path):
        return

    input_path = Path(file_path)
    _log(f"Detected research-input: {input_path.name}")

    # JSON バリデーション
    if not _validate_json(input_path):
        _log(f"SKIP: validation failed for {input_path.name}")
        return

    # Step 1: emit_research_queue.py で graph-queue JSON 生成
    _log("Step 1: Running emit_research_queue.py")
    emit_result = subprocess.run(
        [
            "uv", "run", "python",
            str(PROJECT_DIR / "scripts" / "emit_research_queue.py"),
            "--command", "web-research",
            "--input", str(input_path),
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_DIR),
        timeout=120,
    )
    if emit_result.returncode != 0:
        _log(f"FAIL: emit_research_queue.py exited {emit_result.returncode}")
        _log(f"  stderr: {emit_result.stderr[:500]}")
        return

    _log(f"  emit stdout: {emit_result.stdout.strip()[:200]}")

    # Step 2: 生成された graph-queue JSON を特定
    gq_file = _find_latest_graph_queue()
    if not gq_file:
        _log("FAIL: No graph-queue JSON found after emit")
        return

    _log(f"Step 2: Ingesting {gq_file.name}")

    # Step 3: ingest_graph_queue.py で Neo4j 投入
    ingest_result = subprocess.run(
        [
            "uv", "run", "python",
            str(PROJECT_DIR / "scripts" / "ingest_graph_queue.py"),
            "--file", str(gq_file),
            "--log-level", "INFO",
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_DIR),
        timeout=300,
    )
    if ingest_result.returncode != 0:
        _log(f"FAIL: ingest_graph_queue.py exited {ingest_result.returncode}")
        _log(f"  stderr: {ingest_result.stderr[:500]}")
        return

    _log(f"SUCCESS: {gq_file.name} ingested to research-neo4j")
    _log(f"  output: {ingest_result.stdout.strip()[:300]}")


if __name__ == "__main__":
    main()
