# 議論メモ: NFLX Q1 2026 決算プレビュー — 全工程完走 & 表フォーマット刷新

**日付**: 2026-04-15  
**参加**: ユーザー + AI

## 背景・コンテキスト

Netflix（NFLX）のQ1 2026決算プレビュー記事を `/article-full` ワークフローで作成。
決算発表日は2026年4月16日（木）AMC。
完走後、earningsカテゴリの表フォーマットをBLKプレビューに統一する追加作業を実施。

## 議論のサマリー

### Phase 1: 全工程実行

- `article-init` → スラッグ: `2026-04-15_nflx-q1-2026-earnings-preview`
- `article-research`: yfinance + Alpha Vantage SQLite + SEC EDGAR 8-K + Tavily webリサーチ
  - 現在株価: $106.28（2026/4/15終値）
  - Q1 2026コンセンサス: 売上$12.157B(+15.3%), EPS $0.76(+15.2%)
  - 直近8四半期ビート率87.5%、株価上昇確率37.5%（乖離パターンが独特）
- `article-draft`: 初稿4,958字・6セクション構成
- `article-critique`: 2エージェント並列批評（fact: 72/100, compliance: 78/100 → 総合76/100）
  - Critical修正: 売上単位表記誤り（$12.157億→$12.157B）
  - Major修正: Q2 2024乖離ケース欠落・会員開示停止時期誤り
  - Compliance修正: 免責事項不完全・断定的表現
- `article-revision`: 全修正適用、revised_draft.md完成
- `article-publish`: note.com下書き投稿完了（https://editor.note.com/notes/n10cdd5b09035/edit/）

### Phase 2: 表フォーマット刷新（BLKプレビューテンプレート化）

ユーザー要求: "earningsの表の作り方は、Blackrockの決算プレビューで作成した表のフォーマットをテンプレートとして設定し、作り直して"

BLK previewの構成:
- `table_overview.png` → `["項目", "データ", "備考"]` 3列
- `table_earnings_eps.png` → EPS履歴（別表）
- `table_earnings_reaction.png` → 株価反応（別表）

NFLX表の刷新:
- **旧**: `table_overview.png`（コンセンサスのみ）+ `table_earnings_history.png`（EPS+反応混合）
- **新**: `table_overview.png`（銘柄概要・BLK形式）+ `table_earnings_eps.png` + `table_earnings_reaction.png`

テーマカラー: `#e50914`（Netflix赤）、BLKは`#1d4ed8`

## 決定事項

1. earningsカテゴリの表フォーマットをBLKプレビューに統一する（3種類: overview/eps/reaction）
2. `table_overview.png` は `["項目", "データ", "備考"]` 3列のBLK形式を標準とする
3. EPS履歴と株価反応は別々の画像として分離する
4. テーマカラーは銘柄カラーを使用（NFLX: #e50914, BLK: #1d4ed8）

## アクションアイテム

- [x] NFLX Q1 2026 決算プレビュー記事作成・note.com投稿 （完了）
- [x] BLKフォーマット表の作成（table_overview/eps/reaction各PNG生成）（完了）
- [x] revised_draft.md・article.md更新（新画像参照に変更）（完了）
- [ ] 次のearnings記事作成時もBLKフォーマットを踏襲する

## 次回の議論トピック

- NFLX Q1 2026 決算レビュー記事（4/16発表後）
- earningsカテゴリの記事テンプレートをドキュメント化

## 参考情報

- BLK previewリポジトリ: `articles/earnings/2026-04-06_blk-earnings-preview/`
- NFLX previewリポジトリ: `articles/earnings/2026-04-15_nflx-q1-2026-earnings-preview/`
- note.com下書きURL: https://editor.note.com/notes/n10cdd5b09035/edit/
- 表JSONテンプレート: `.tmp/nflx_table_overview.json`, `.tmp/nflx_table_earnings_eps.json`, `.tmp/nflx_table_earnings_reaction.json`
