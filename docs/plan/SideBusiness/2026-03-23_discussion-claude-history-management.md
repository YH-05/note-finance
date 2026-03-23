# 議論メモ: Claude Code会話履歴管理 & プロジェクト進捗管理方法の決定

**日付**: 2026-03-23
**参加**: ユーザー + AI

## 背景・コンテキスト

本プロジェクトは複数デバイスで同期しており、Claude Codeの会話履歴（374件/597MB）を含むプロジェクト情報を全デバイスで共有したいという要件があった。

## 議論のサマリー

1. **`.tmp/` の中間データ確認**: リサーチ、creator-enrichment、ニュース収集、PDF変換等の中間データが保存されていることを確認
2. **会話履歴の保存場所**: `~/.claude/projects/-Users-yukihata-Desktop-note-finance/` に374件のJSONLファイル（296MB）として保存されていることを確認
3. **同期方法の検討**:
   - A) Git-LFS で同期 → リポジトリが重くなる
   - B) `.gitignore` で除外し別途同期 → 管理が複雑
   - C) 共有ドライブ（NeoData）+ シンボリックリンク → 採用候補に
4. **パス依存問題の発覚**: `~/.claude/projects/` のディレクトリ名がデバイスの絶対パス（`/Users/yukihata/Desktop/...`）に依存。デバイスが異なるとMemory・会話履歴・設定が全て分断される
5. **C案の技術的解決**: シンボリックリンクの元パスはデバイスごとに異なるが、リンク先を同一共有ドライブにすれば解決可能
6. **最終判断**: ファイルシステムベースの同期は断念し、note-neo4jでプロジェクト進捗を管理する方針に決定

## 決定事項

1. **Claude Code会話履歴のファイルシステム同期は行わない** — 技術的には可能だが、複雑さ対効果が見合わない
2. **プロジェクト進捗管理はnote-neo4j (bolt://localhost:7687) で行う** — 構造化クエリで分析しやすく、Discussion/Decision/ActionItemとして管理可能

## 技術的知見（参考）

- Claude Codeの会話履歴: `~/.claude/projects/<encoded-path>/*.jsonl`（JSONL形式、1ファイル=1セッション）
- パスエンコード: `/Users/yukihata/Desktop/note-finance` → `-Users-yukihata-Desktop-note-finance`
- デバイス間でパスが異なると「別プロジェクト」扱いになる

## 次回の議論トピック

- note-neo4jでのプロジェクト進捗管理の具体的な運用設計
