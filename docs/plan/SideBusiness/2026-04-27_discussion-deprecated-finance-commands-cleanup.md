# 議論メモ: 非推奨 finance-* コマンドの trash 移動

**日付**: 2026-04-27
**参加**: ユーザー + AI

## 背景・コンテキスト

`.claude/commands/` 配下に旧世代の finance-* 系コマンドが非推奨マーカー付きで残存していた。
新世代の article-* 系コマンドおよび topic-discovery に完全に置き換えられているため、混乱を避けるためにファイルごと trash/ へ退避する判断を行った。

## 議論のサマリー

`/finance-suggest-topics` と `/finance-full` の2コマンドが対象。両者ともファイル冒頭に「非推奨」マーカーが入っており、後継コマンドが安定運用フェーズに入っている。

### `/finance-suggest-topics` vs `/topic-discovery`

| 項目 | finance-suggest-topics（旧） | topic-discovery（新） |
|------|----------------------------|----------------------|
| ステータス | 非推奨 | 現行 |
| 機能 | 単純なトピック提案 | research-neo4j 知識ギャップ発掘 + Web検索 + 既存記事ギャップ + topic-suggester スコアリング |
| データ駆動 | × | ○（research-neo4j に永続化） |

### `/finance-full` vs `/article-full`

| 項目 | finance-full（旧） | article-full（新） |
|------|-------------------|-------------------|
| ステータス | 非推奨 | 現行 |
| Phase 数 | 3（init→research→edit） | 5（init→research→draft→critique→**publish**） |
| 投稿フェーズ | なし | あり（note.com 下書き投稿まで一括） |
| ディレクトリ | `articles/{old_format}/` フラット | `articles/{category}/{YYYY-MM-DD}_{slug}/` |
| 設定ファイル | `article-meta.json` | `meta.yaml` |
| カテゴリ | 旧分類（market_report 等） | 8カテゴリ（asset_management/side_business/macro_economy/stock_analysis/market_report/quant_analysis/investment_education/earnings） |
| 画像ポストプロセス | なし | Step 4.4（表/チャート画像化）+ Step 4.5（earnings サムネ） |
| マークダウン表 gate | なし | Step 1.5 で残存表検出→投稿中止 |
| 再開機能 | article_id 再指定 | `@article_dir` から meta.yaml の workflow 状態で自動再開 |

## 決定事項

1. `/finance-suggest-topics`（`.claude/commands/finance-suggest-topics.md`）を `trash/` に移動。今後は `/topic-discovery` を使用する。
2. `/finance-full`（`.claude/commands/finance-full.md`）を `trash/` に移動。今後は `/article-full` を使用する。

## アクションアイテム

- [x] `act-2026-04-27-008` (高) `.claude/commands/finance-suggest-topics.md` を `trash/` に移動（完了）
- [x] `act-2026-04-27-009` (高) `.claude/commands/finance-full.md` を `trash/` に移動（完了）

## 後日の追記（同コミット内）

本セッションと並行して、ユーザー側で `/topic-discovery` コマンド自体も廃止された（コマンド・スキル本体・references を削除、参照箇所を `topic-suggest` スキルへ振り替え）。
本ドキュメントの「後継: `/topic-discovery`」記述は当時の判断としてそのまま残すが、現時点（2026-04-27 同日）でのトピック発掘の標準は **`topic-suggest` スキル** である。

## 次回の議論トピック

- 他の非推奨コマンドの棚卸し（`/asset-management`, `/experience-db-full` 等が `/article-full --category {x}` に統合される旨が article-full.md に記載されている）
- スキル一覧に重複している finance-* 系が他にないか確認

## 参考情報

- `article-full.md` 末尾の「旧コマンド（置き換え対象）」セクション:
  - `/finance-full` → `/article-full`
  - `/asset-management` → `/article-full --category asset_management`
  - `/experience-db-full` → `/article-full --category side_business`
- CLAUDE.md は既に「記事ワークフロー（新コマンド）」として article-* 系に統一されている
