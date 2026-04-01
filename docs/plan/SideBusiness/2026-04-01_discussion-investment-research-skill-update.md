# 議論メモ: investment-research スキル改善 — Web検索生データ保存

**日付**: 2026-04-01  
**参加**: ユーザー + AI

## 背景・コンテキスト

`/investment-research` スキルで「地政学的リスクによる米国セクターローテーション」をリサーチした際、Tavily MCP の検索生レスポンスがセッション内で消費されて廃棄されており、後からデータを参照・再利用できない状態だった。

## 議論のサマリー

- ユーザーが「Web検索の生データはどこに配置した？」と質問
- 生データはファイルとして保存されておらず、処理済みの成果物（リサーチノート・KG投入JSON）のみ保存していたことが判明
- 「保存するようにして」との指示を受け、SKILL.md を修正

## 決定事項

1. `investment-research` スキルに **Phase 1.5「検索生データの保存」** を追加
   - 保存先: `.tmp/raw-search/{session_id}.jsonl`（JSON Lines形式）
   - 各検索レスポンスを 1行 = 1検索のフォーマットで追記
   - フィールド: `query` / `tool` / `timestamp` / `response`
   - 対象: Tavily・RSS・Reddit・SEC Edgar（Neo4j照会は除外）

## 変更済みファイル

- `.claude/skills/investment-research/SKILL.md` — Phase 1.5 セクションを追加

## アクションアイテム

なし（変更は同セッション内で即時適用済み）

## 次回の議論トピック

- 他のリサーチ系スキル（`equity-stock-research`, `macro-economic-research`）にも同様の生データ保存を横展開するか検討
