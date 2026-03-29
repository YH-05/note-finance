# 議論メモ: /article-revise スキル作成とバックアップ命名規則

**日付**: 2026-03-29
**参加**: ユーザー + AI

## 背景・コンテキスト

note-finance プロジェクトには `/article-critique`（自動批評→機械的修正）があったが、
ユーザーが具体的なフィードバックを与えて記事を修正するスキルが存在しなかった。
インドネシア通信セクター記事の改善作業をきっかけに `/article-revise` スキルを新規作成した。

## 議論のサマリー

### /article-revise スキル設計

- `revised_draft.md`（優先）または `first_draft.md` にユーザーのフィードバックを反映し上書きする
- 上書き前に `02_draft/revisions/` にバックアップを取る
- `/article-critique`（AI自動批評）とは異なり、人間の具体的な指示に基づいて修正する

### バックアップ命名規則の検討

当初はタイムスタンプ形式（`revised_draft_YYYYMMDD_HHMMSS.md`）で実装したが、
ユーザーからリビジョン番号形式への変更指示を受けた。

**決定形式**: `{slug}_rev{N}.md`（例: `2026-03-28_indonesia-telecom-sector_rev1.md`）
- `{slug}` は `meta.yaml` の `article_id` から取得
- `{N}` は `revisions/` 内の既存ファイルから最大番号を自動検出して +1
- 各ファイルの先頭に YAML フロントマター（`revision`, `created_at`, `feedback`, `changes[]`）を付与

### /article-publish との関係明確化

`/article-publish` が投稿するのは常に `02_draft/revised_draft.md`（最新版）のみ。
`revisions/` はバックアップ履歴であり投稿対象ではない。
SKILL.md にこれを明記することで混乱を防ぐ。

### インドネシア通信セクター記事でのテスト

- Rev1: セクション1を大幅拡充（市場構造・統合歴史・競争ポジションの3サブセクション追加）
- Rev2: 冒頭ディスクレーマーを削除し末尾に一本化

## 決定事項

1. `/article-revise` スキル（`.claude/skills/article-revise/SKILL.md`）を新規作成
2. `/article-revise` コマンド（`.claude/commands/article-revise.md`）を新規作成
3. バックアップ命名規則: `{slug}_rev{N}.md` + YAMLフロントマター（タイムスタンプ形式を廃止）
4. `/article-publish` は常に `revised_draft.md` のみを投稿対象とすることを SKILL.md に明記
5. 既存バックアップ2件を新形式に移行（旧ファイルは `trash/` へ）

## アクションアイテム

- 全タスク完了。次の記事への `/article-revise` 活用が次ステップ

## 参考情報

- 作成ファイル: `.claude/skills/article-revise/SKILL.md`
- 作成ファイル: `.claude/commands/article-revise.md`
- テスト記事: `articles/stock_analysis/2026-03-28_indonesia-telecom-sector/`
