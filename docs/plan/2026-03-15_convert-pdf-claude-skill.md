# PDF-to-Claude Conversion (Method B) - Project #79

## 概要

Claude Code の Read ツールで PDF を直接読み込み、構造化 Markdown に変換する Method B パイプラインの実装計画。

## Wave 構成

### Wave 1: Foundation（基盤）

| Issue | タイトル | 状態 |
|-------|---------|------|
| #95 | feat(pdf-pipeline): compute_sha256_standalone関数を追加 | Open |
| #96 | feat(pdf-pipeline): page_chunk_sizeパラメータ追加 | Open |
| #97 | feat(pdf-pipeline): Method B用Pythonヘルパーモジュール作成 | Open |
| #98 | test(pdf-pipeline): cli/helpers.pyのユニットテスト | Open |

### Wave 2: Core Skill（中核スキル）

| Issue | タイトル | 状態 |
|-------|---------|------|
| #99 | feat(pdf-pipeline): /convert-pdf スキル実装（Method B） | Open |
| #100 | feat(pdf-pipeline): /convert-pdf コマンド作成 | Open |

### Wave 3: Integration（統合）

| Issue | タイトル | 状態 |
|-------|---------|------|
| #101 | feat(pdf-pipeline): ナレッジ抽出ヘルパー関数追加 | Open |
| #102 | feat(pdf-pipeline): /pdf-to-knowledge ワークフロースキル | Open |
| #103 | feat(pdf-pipeline): /pdf-to-knowledge コマンド作成 | Open |

### Wave 4: Cleanup（整理）

| Issue | タイトル | 状態 |
|-------|---------|------|
| #104 | refactor(pdf-pipeline): レガシーコマンド・スキル削除 | Open |
| #105 | docs(pdf-pipeline): CLAUDE.md・ドキュメント更新 | **In Progress** |
| #106 | refactor(pdf-pipeline): GeminiCLIProvider非推奨化マーキング | Open |

## チェックリスト

### ドキュメント更新（#105）

- [x] CLAUDE.md のコマンドテーブルに `/convert-pdf` と `/pdf-to-knowledge` を追加
- [x] CLAUDE.md のコマンド数・スキル数を実態に合わせて更新
- [x] AGENTS.md の AI Agent Integration テーブルを更新
- [x] AGENTS.md の Commands セクションに PDF・ナレッジグラフカテゴリを追加
- [x] 設計ドキュメント（本ファイル）作成

### 非推奨コマンド

| コマンド | 代替 | 状態 |
|---------|------|------|
| `/convert-pdf-claude` | `/convert-pdf` | #104 で削除予定 |
| `/batch-pdf-claude` | `/convert-pdf`（複数PDF対応） | #104 で削除予定 |
