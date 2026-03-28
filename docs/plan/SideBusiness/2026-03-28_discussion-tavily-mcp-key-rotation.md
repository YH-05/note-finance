# 議論メモ: Tavily MCP サーバー API キーローテーション統一実装

**日付**: 2026-03-28
**参加**: ユーザー + AI

## 背景・コンテキスト

`creator-enrichment` パイプラインには `TavilyKeyPool` が実装済みで、432エラー時に自動でAPIキーをローテーションする。しかし `/investment-research`, `/article-research`, `/topic-discovery` 等のスキル・コマンドは `mcp__tavily__tavily_search`（MCP経由）を使っており、npm `tavily-mcp` は単一キーのみ対応。キーローテーションの恩恵を受けられていなかった。

## 議論のサマリー

3つの選択肢を検討:

| 選択肢 | 概要 | 評価 |
|--------|------|------|
| MCP設定で対応 | tavily-mcp npm が単一キー前提 | 不可 |
| Pythonラッパー統一 | 全スキルを httpx 直叩きに変更 | 影響範囲大 |
| **カスタムMCPサーバー** | npm → 自作Python MCPに置換 | **最適** |

カスタムMCPサーバーは既存スキルの変更がゼロで、.mcp.json の差し替えだけでキーローテーションを全ツールに適用できる点が決め手。

## 実装内容

### 作成ファイル

- `src/tavily_mcp/__init__.py` — パッケージ
- `src/tavily_mcp/server.py` — FastMCP サーバー（TavilyKeyPool + 5ツール）
- `tests/unit/test_tavily_mcp/test_server.py` — 24テスト（全パス）

### 変更ファイル

- `pyproject.toml` — `tavily-mcp` エントリポイント + パッケージ追加
- `.mcp.json` — `npx tavily-mcp` → `uv run --extra mcp tavily-mcp`
- `.mcp.json.template` — 同上（TAVILY_API_KEY_1, _2 テンプレート）

### 機能

- `TAVILY_API_KEY_1`, `_2`, `_3`... の連番キーをラウンドロビン
- 432/429 エラーでキーを除外→次のキーに自動切替
- 全キー枯渇時はエラー返却（スキル側のフォールバック: Gemini Search / WebSearch）
- `TAVILY_API_KEY`（単一キー）後方互換
- 5ツール: tavily_search, tavily_research, tavily_extract, tavily_crawl, tavily_map

## 決定事項

1. **カスタムMCPサーバー採用**: npm tavily-mcp を廃止し、自作 Python 実装（FastMCP）に置換
2. **キー管理規約**: TAVILY_API_KEY_1, _2, ... の連番環境変数。TAVILY_API_KEY にフォールバック
3. **Drop-in replacement**: ツール名・サーバーキー 'tavily' を維持し、既存スキル変更ゼロ

## アクションアイテム

- [ ] Claude Code 再起動後に動作確認（高）
- [ ] 追加 API キーを設定してローテーション実検証（中）
- [ ] creator-enrichment の TavilyKeyPool を共通モジュール化するリファクタリング検討（低）

## 技術詳細

### キーローテーションの動作フロー

```
リクエスト → key_pool.get_key() → httpx.post(api_key=key)
                                      ↓
                              HTTP 432/429? → mark_exhausted(key) → retry with next key
                              HTTP 200?     → return response
                              HTTP 5xx?     → return error (no retry)
                              Timeout?      → return error (no retry)
```

### 影響を受けるスキル・コマンド（変更不要）

- `/investment-research` — mcp__tavily__tavily_search 使用
- `/article-research` — investment-research に委譲
- `/topic-discovery` — Tavily MCP + Gemini Search
- `/generate-market-report` — RSS → Tavily MCP → Gemini
- `/creator-enrichment` — 独自 TavilyKeyPool（既存のまま動作）
