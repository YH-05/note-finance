# 議論メモ: エージェント検索戦略見直し — Gemini Search フォールバック廃止

**日付**: 2026-04-01
**参加**: ユーザー + AI

## 背景・コンテキスト

gemini-search スキル・コマンド（`/gemini-search`）は日本語検索・コスト節約向けの手動ツールとして維持する方針。
一方、エージェントやパイプラインが自動フォールバックとして Gemini CLI を呼ぶ設計は以下の理由から問題がある：

- Bash 経由 CLI 起動でオーバーヘッド大（5-15秒/クエリ）
- テキスト出力で構造化困難（JSON パース・自動処理に不向き）
- 並列化困難
- エラー時の制御が複雑

## 決定事項

1. **エージェント・パイプラインの自動フォールバックとして Gemini CLI (gemini-search) を使用禁止**
   - Tavily MCP → WebSearch（ビルトイン）の順に統一
2. `/gemini-search` コマンド・スキル自体は手動利用向けとして保持

## 変更ファイル一覧

### エージェント（フォールバック 3rd を Gemini Search → WebSearch に変更）

| ファイル | 変更内容 |
|---------|---------|
| `.claude/agents/weekly-comment-indices-fetcher.md` | 3rd フォールバック + エラーハンドリングコメント |
| `.claude/agents/weekly-comment-mag7-fetcher.md` | 3rd フォールバック |
| `.claude/agents/weekly-comment-sectors-fetcher.md` | 3rd フォールバック |

### エージェント（Gemini Search 言及を削除）

| ファイル | 変更内容 |
|---------|---------|
| `.claude/agents/reddit-topic-analyzer.md` | 日本語クエリ推奨 → Tavily MCP / WebSearch、クエリ例3行更新 |
| `.claude/agents/research-image-collector.md` | `Tavily MCP / Gemini Search 等` → `Tavily MCP / WebSearch` |
| `.claude/agents/api-usage-researcher.md` | `Tavily MCP / Gemini Search 等` → `Tavily MCP / WebSearch` |

### コマンド・スキル

| ファイル | 変更内容 |
|---------|---------|
| `.claude/commands/generate-market-report.md` | Tavily 未発見フォールバック + Phase 3 検索ツール説明更新 |
| `.claude/skills/web-search/SKILL.md` | generate-market-report パターン 3rd + 「推奨改善」注釈削除 |

## アクションアイテム

なし（本セッション内で全変更完了）

## 次回の議論トピック

- `.agents/skills/` 配下の同名スキルにも同様の変更を反映するか検討
