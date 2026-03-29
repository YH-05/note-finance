# 議論メモ: /investment-research Tavily設定修正・Gemini CLI禁止

**日付**: 2026-03-29
**参加**: ユーザー + AI

## 背景・コンテキスト

`/investment-research` スキルで Tavily 検索を使う際に、以下の2つの問題が発覚した。

1. **Gemini CLI 使用問題**: SKILL.md に「日本語テーマ → Gemini Search 推奨」と記載されており、意図せず Gemini CLI が呼ばれる設計になっていた
2. **Tavily キーローテーション未発動問題**: レートリミット時に別の API キーへ切り替わらなかった

## 議論のサマリー

### 問題1: Gemini CLI 使用

ユーザーから「`/investment-research` では Gemini CLI を使ったWeb検索は行わないように」という指示。

- `investment-research/SKILL.md` の Phase 1 に「日本語テーマ → Gemini Search 推奨」と明記されていた
- `web-search/SKILL.md` のパターン2（investment-research 向け）にも同様の推奨があった

### 問題2: キーローテーション未発動の原因特定

キーローテーション実装は `src/tavily_mcp/server.py` に存在していたが、`.mcp.json` が公式 npm パッケージ（`npx tavily-mcp`）を参照しており、カスタムサーバーが使われていなかった。

| 項目 | 修正前 | 修正後 |
|------|--------|--------|
| MCP サーバー | `npx tavily-mcp`（公式npm） | `uv run tavily-mcp`（カスタム） |
| API キー | `TAVILY_API_KEY` × 1 | `TAVILY_API_KEY_1` 〜 `_4` × 4 |
| キーローテーション | 不可能 | 429/432 で自動切替 |

`.env` には `TAVILY_API_KEY_1`〜`_4` の4キーが設定済みだったが、`.mcp.json` に渡されていなかった。

## 決定事項

1. **dec-2026-03-29-001**: `/investment-research` スキルでは Gemini CLI によるWeb検索を禁止。Tavily MCP 優先、フォールバックは WebSearch のみ。
2. **dec-2026-03-29-002**: `.mcp.json` の Tavily 設定をカスタム MCP サーバー（`src/tavily_mcp/server.py`）に切り替え、`TAVILY_API_KEY_1`〜`_4` を全て渡す。

## 修正したファイル

- `.claude/skills/investment-research/SKILL.md` — Phase 1 Web検索部分
- `.claude/skills/web-search/SKILL.md` — パターン2（investment-research）
- `.mcp.json` — Tavily MCP サーバー設定

## アクションアイテム

- [ ] Claude Code を再起動して Tavily カスタム MCP サーバーを有効化する（優先度: 高）

## 参考情報

- カスタム Tavily MCP: `src/tavily_mcp/server.py` — `TavilyKeyPool` + `_post_with_rotation()` で 429/432 自動ローテーション実装済み
- エントリポイント: `pyproject.toml` の `[project.scripts]` に `tavily-mcp = "tavily_mcp.server:main"` 定義済み
