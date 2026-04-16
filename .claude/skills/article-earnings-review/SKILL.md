---
name: article-earnings-review
description: 既に発行した決算プレビュー記事（earnings_preview）に対応するレビュー記事（earnings_review）を生成するスキル。未レビューのプレビュー記事を特定し、決算発表後のデータを収集し、プレビュー記事との対比構造でレビュー記事を執筆する。「決算レビュー記事」「earnings review」「プレビューのレビュー版」「プレビュー記事の振り返り記事」と言われたら必ずこのスキルを使うこと。/article-earnings-review コマンドから呼び出される。
---

# article-earnings-review スキル

株投資ラボの earnings カテゴリで、発行済みプレビュー記事に対する**レビュー記事**（決算発表後の振り返り）を生成するオーケストレータースキル。

## ポジショニング

このスキルは `/article-earnings-review` コマンドの実装本体。
「単なる決算ダイジェスト」ではなく、**プレビュー記事との対比**で差別化されたレビュー記事を機械的に作成するためのガイドラインとロジックを提供する。

## いつ使用するか

- `/article-earnings-review` コマンドを実行したとき
- ユーザーが「決算プレビューのレビュー版を書いて」等と依頼したとき
- 既存のプレビュー記事で、決算発表日を過ぎて note 投稿済みかつ未レビューのものに対して

## 入力

| パラメータ | 必須 | 取得元 | 説明 |
|-----------|------|--------|------|
| `preview_dir` | ○※ | 引数 or 対話選択 | プレビュー記事ディレクトリ（例: `articles/earnings/2026-04-06_blk-earnings-preview/`） |
| `--skip-publish` | - | 引数 | 投稿をスキップ（批評・修正で完了） |
| `--mode` | - | 引数 | 批評モード（`quick` / `full`、デフォルト `full`） |
| `--skip-hf` | - | 引数 | ヒューマンフィードバックをスキップ（非推奨） |

※ `preview_dir` 未指定の場合は候補列挙スクリプトを実行してユーザーに選択させる。

## 処理フロー

```
Phase 0: 候補特定（preview_dir 未指定時のみ）
└─ uv run --with pyyaml python .claude/skills/article-earnings-review/scripts/list_unreviewed_previews.py

Phase 1: レビュー記事フォルダ初期化
├─ プレビュー記事の meta.yaml / revised_draft.md を読み込み
├─ focus_points をプレビュー §2 から抽出
├─ レビュー記事ディレクトリを作成
└─ meta.yaml 生成（type: earnings_review, preview_ref 含む）

Phase 2: リサーチ実行（/article-research）
├─ 発表後の 8-K、株価反応、カンファレンスコール要旨を収集
└─ 01_research/ に成果物保存

Phase 3: ドラフト作成（/article-draft）
├─ プレビュー revised_draft.md を context として参照
├─ references/earnings.md § 「決算レビュー版」に従い執筆
└─ 02_draft/first_draft.md 出力

Phase 4: 批評・修正（/article-critique --mode {mode}）
├─ 批評・リバイザー
├─ Step 4.4: 表・チャート画像ポストプロセス
└─ Step 4.5: サムネイル生成（earnings_review 用）

Phase 5: 投稿（/article-publish、--skip-publish で省略可）
```

## Phase 0: 候補特定ロジック

未レビューのプレビュー記事を列挙するために以下のスクリプトを使用する。

```bash
uv run --with pyyaml python .claude/skills/article-earnings-review/scripts/list_unreviewed_previews.py --format table
```

### 判定ルール

プレビュー記事が以下を**全て**満たす場合に候補とする:

1. ディレクトリ名に `-preview` を含む、または `meta.yaml.type == earnings_preview`
2. `meta.yaml.earnings_date` が今日以前（発表済み）
3. `meta.yaml.workflow.publish == done` または `workflow.publishing.published == done`（プレビュー自身が note 投稿済み）
4. 同一ティッカー・同一 fiscal_quarter・同一 fiscal_year のレビュー記事が存在しない

ティッカー・fiscal_quarter・fiscal_year は meta.yaml のフィールド揺れ（`symbol` / `symbols[0]`, `fiscal_quarter` / `fiscal_quarter_ending`）とディレクトリ名の命名パターン3種に対応している（スクリプト実装参照）。

## Phase 1: レビュー記事フォルダ初期化

### ディレクトリ命名規則

```
articles/earnings/{YYYY-MM-DD}_{ticker-lower}-q{N}-{year}-earnings-review/
```

例: プレビューが `2026-04-06_blk-earnings-preview/`（BLK Q1 2026）で、発表日が 2026-04-14 の場合:

```
articles/earnings/2026-04-15_blk-q1-2026-earnings-review/
```

ディレクトリの日付部分はレビュー記事の**作成日**（今日）を使用する。

### meta.yaml テンプレート

```yaml
article_id: "{YYYY-MM-DD}_{ticker-lower}-q{N}-{year}-earnings-review"
title: "【🇺🇸米株決算】{企業名}（{TICKER}）Q{N} {year} 決算レビュー"
topic: "{TICKER} Q{N} {year} 決算レビュー"
category: earnings
type: earnings_review
status: draft
created_at: "{YYYY-MM-DD}"
updated_at: "{YYYY-MM-DD}"
symbols:
  - "{TICKER}"
fiscal_quarter: "Q{N}"
fiscal_year: "{year}"
earnings_date: "{プレビューから継承}"
announcement_time: "{プレビューから継承: BMO|AMC}"
target_audience: intermediate
target_wordcount: 4000
preview_ref:
  path: "{プレビュー記事の相対パス}"
  note_url: "{プレビューの note_url または draft_url}"
  focus_points:
    - "{プレビュー §2 から抽出した注目ポイント1}"
    - "{プレビュー §2 から抽出した注目ポイント2}"
    - "{プレビュー §2 から抽出した注目ポイント3}"
status: init
workflow:
  research: pending
  draft: pending
  critique: pending
  revision: pending
  publish: pending
human_feedback:
  hf1_topic_approved: true
  hf3_claims_reviewed: false
  hf5_draft_reviewed: false
  hf6_final_approved: false
```

### focus_points の抽出手順

1. プレビュー記事の `02_draft/revised_draft.md` を Read
2. `## 2. 今回の決算ポイント` セクション（または類似名）を特定
3. 「注目KPI」「着目すべきドライバー」等のリスト要素を抽出
4. 2-5 個に絞り、自然言語の短文で meta.yaml に記録

テンプレートファイルが期待と異なる場合は `meta.yaml.notes` や記事冒頭から抜き出すフォールバックを行う。

## Phase 2-5: 既存コマンド呼び出し

以降の処理は既存の汎用コマンドに委譲する。`meta.yaml.type == earnings_review` を検出した各コマンドが以下のように分岐する:

| コマンド | レビュー版での挙動 |
|---------|-------------------|
| `/article-research` | 決算発表日以降のソース（8-K、カンファレンスコール、株価反応）を優先取得。プレビュー時点の `focus_points` をクエリシードに利用する |
| `/article-draft` (finance-article-writer) | `references/earnings.md` § 「決算レビュー版」を適用。プレビュー記事の revised_draft.md を事前 Read |
| `/article-critique` | finance-critic-writer-rules がレビュー版チェックリストを追加適用 |
| `/article-earnings-thumbnail` | `type == earnings_review` で Pencil nodeId `har1R`（グリーンバッジ）を使用 |
| `/article-publish` | タイトルフォーマットの末尾が「決算レビュー」であることを確認 |

## サブエージェントへの注意喚起

`/article-draft` 実行時、finance-article-writer エージェントに以下を明示的に伝達する:

1. `meta.yaml.preview_ref` を読み、プレビュー記事の `revised_draft.md` を事前 Read すること
2. `references/earnings.md` の **「決算レビュー版（earnings_review）」セクション**（末尾の見出し）を参照すること
3. §0 にプレビュー記事への note.com リンクを必ず貼ること（`preview_ref.note_url`）
4. §2 で `preview_ref.focus_points` の全項目を順序通りに回答すること
5. §3 でプレビュー記事に書かれていない新情報を扱うこと（プレビュー revised_draft.md と内容重複を避ける）

## 完了報告テンプレート

```markdown
## 決算レビュー記事作成完了

### 記事情報
- **プレビュー記事**: {preview_dir}
- **レビュー記事**: {review_dir}
- **ティッカー**: {TICKER} / **会計期**: Q{N} {year}

### 対比構造
- プレビュー時点の注目ポイント: {focus_points の件数} 項目
- §2 で全項目に言及済み
- §3 で扱った新情報: {新情報の件数} 項目

### 投稿状態
- note.com URL: {note_url または "未投稿（--skip-publish）"}
- プレビュー note リンク: §0 に埋め込み済み
```

## 関連ファイル

| ファイル | 役割 |
|---------|------|
| `scripts/list_unreviewed_previews.py` | 未レビューのプレビュー候補を列挙 |
| `.claude/commands/article-earnings-review.md` | ユーザー向けスラッシュコマンド本体 |
| `.claude/skills/finance-article-writer/references/earnings.md` | 執筆ガイドライン（レビュー版セクションあり） |
| `.claude/skills/article-earnings-thumbnail/SKILL.md` | サムネイル生成（`type` で自動分岐） |
