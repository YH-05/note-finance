# 議論メモ: mcp__memory__ (neo4j-memory) MCP の整理・無効化

**日付**: 2026-03-28
**参加**: ユーザー + AI

## 背景・コンテキスト

project-discuss スキルが使う MCP サーバーを確認する中で、`mcp__memory__*` (neo4j-memory) が
settings.local.json の allow リストに登録されていることに気づいた。
実際に使われているかを調査し、不要であれば無効化する方針で議論した。

## 議論のサマリー

1. **project-discuss が使う MCP を確認**
   - `mcp__neo4j-note__note-*`（note-neo4j port 7687）
   - `mcp__neo4j-data-modeling__*`
   - `mcp__sequential-thinking__sequentialthinking`
   - `mcp__memory__*` は**使っていない**

2. **プロジェクト全体での mcp__memory__* 使用状況を調査**
   - `grep -r "mcp__memory__"` の結果: `commands_sample/wiki-search.md` 1件のみ
   - スキル・エージェント・コマンドでの実使用なし → **不要と判断**

3. **設定ファイルの確認**
   - `settings.local.json`: allow リストに `mcp__neo4j-memory__*` 5件 + `mcp__memory__read_graph` 1件が存在 → **削除**
   - `.mcp.json`: `neo4j-memory` / `memory` サーバーエントリなし → **変更不要**
   - `claude_desktop_config.json`: `mcpServers: {}` → **変更不要**
   - `mcp__memory__*` は Claude Code ビルトイン機能であり、独立したサーバーエントリを持たない

## 決定事項

1. `settings.local.json` の allow リストから以下6件を削除
   - `mcp__neo4j-memory__create_entities`
   - `mcp__neo4j-memory__create_relations`
   - `mcp__neo4j-memory__search_memories`
   - `mcp__neo4j-memory__delete_entities`
   - `mcp__neo4j-memory__add_observations`
   - `mcp__neo4j-memory__read_graph`
   - `mcp__memory__read_graph`

2. `.mcp.json` / `claude_desktop_config.json` は変更不要（サーバー定義が存在しない）

## アクションアイテム

なし（対応完了）

## 次回の議論トピック

特になし
