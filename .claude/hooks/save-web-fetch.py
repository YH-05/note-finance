#!/usr/bin/env python3
"""PostToolUse hook: WebFetch/WebSearch の結果を RawStore に原文保存する.

Claude Code の PostToolUse イベントで発火し、stdin から
tool_input（URL）と tool_response（取得テキスト）を受け取って
/Volumes/personal_folder/raw_texts に保存する。

設定方法（settings.json）:
    "hooks": {
        "PostToolUse": [
            {
                "matcher": "WebFetch",
                "hooks": [{"type": "command", "command": "uv run python $CLAUDE_PROJECT_DIR/.claude/hooks/save-web-fetch.py"}]
            },
            {
                "matcher": "WebSearch",
                "hooks": [{"type": "command", "command": "uv run python $CLAUDE_PROJECT_DIR/.claude/hooks/save-web-fetch.py"}]
            }
        ]
    }
"""

from __future__ import annotations

import json
import sys


def main() -> None:
    """stdin から hook イベントを読み込み、RawStore に保存する."""
    try:
        raw = sys.stdin.read()
        if not raw:
            return
        event = json.loads(raw)
    except (json.JSONDecodeError, OSError):
        return

    tool_name = event.get("tool_name", "")
    tool_input = event.get("tool_input", {})
    tool_response = event.get("tool_response", {})

    if not tool_response:
        return

    # RawStore に保存
    try:
        from data_pipeline.storage.raw_store import RawStore

        store = RawStore()

        if tool_name == "WebFetch":
            _save_web_fetch(store, tool_input, tool_response)
        elif tool_name == "WebSearch":
            _save_web_search(store, tool_input, tool_response)
        elif tool_name in ("mcp__fetch__fetch", "mcp__tavily__tavily_search"):
            _save_mcp_fetch(store, tool_name, tool_input, tool_response)
    except Exception:  # noqa: BLE001
        # hook の失敗は Claude の動作をブロックしない
        pass


def _save_web_fetch(store, tool_input: dict, tool_response: dict) -> None:
    """WebFetch の結果を保存."""
    url = tool_input.get("url", "")
    content = tool_response.get("content", "")
    if not url or not content:
        return

    store.save_text(
        source_id="webfetch",
        url=url,
        title=url.split("/")[-1][:80] or url[:80],
        raw_text=content,
        collection_method="web_search",
        metadata={"tool": "WebFetch", "prompt": tool_input.get("prompt", "")},
    )


def _save_web_search(store, tool_input: dict, tool_response: dict) -> None:
    """WebSearch の結果を保存."""
    query = tool_input.get("query", "")
    results = tool_response.get("results", [])
    if not results:
        # 結果がリストでない場合（テキスト形式）
        content = tool_response.get("content", "")
        if content:
            store.save_text(
                source_id="websearch",
                url=f"search://{query}",
                title=f"WebSearch: {query[:60]}",
                raw_text=content,
                collection_method="web_search",
                metadata={"tool": "WebSearch", "query": query},
            )
        return

    for result in results:
        url = result.get("url", "")
        text = result.get("snippet", result.get("content", ""))
        title = result.get("title", "")
        if url and text:
            store.save_text(
                source_id="websearch",
                url=url,
                title=title,
                raw_text=text,
                collection_method="web_search",
                metadata={"tool": "WebSearch", "query": query},
            )


def _save_mcp_fetch(store, tool_name: str, tool_input: dict, tool_response: dict) -> None:
    """MCP Fetch/Tavily の結果を保存."""
    url = tool_input.get("url", tool_input.get("query", ""))
    content = tool_response.get("content", "")
    if not url or not content:
        return

    source_id = "tavily" if "tavily" in tool_name else "webfetch"
    store.save_text(
        source_id=source_id,
        url=url,
        title=url[:80],
        raw_text=content,
        collection_method="web_search",
        metadata={"tool": tool_name},
    )


if __name__ == "__main__":
    main()
