# 議論メモ: finance-article-writer スキル全面刷新

**日付**: 2026-03-31
**参加**: ユーザー + AI

## 背景・コンテキスト

株投資ラボのasset_management記事発信を強化するため、finance-article-writer スキルの全面的な刷新を実施した。
主な課題は以下の通り：

1. カテゴリごとに文字数が2000-4000字〜4000-6000字とバラバラで統一感がなかった
2. asset-management-workflow スキルと finance-article-writer の二重管理によるルール不整合
3. X投稿機能が asset_management ワークフローに残存（note 投稿のみに集中したい）
4. 免責事項の形式が各カテゴリ reference でバラバラ（`>` 引用ブロック付き等）
5. 共通チェックリスト項目が各カテゴリ references に重複記載
6. note.com での改行ルールが明文化されていなかった

## 議論のサマリー

### 文字数統一

カテゴリごとに文字数目安が異なる状態を解消。note.com 読者（スマホ利用 70% 以上）の読了率と記事の深みを両立するため、全カテゴリを **8000-10000字** に統一。

### asset-management 統合

`.claude/skills/asset-management-workflow/` を廃止し `trash/2026-03-31_asset-management-workflow/` に移動。
finance-article-writer の `references/asset-management.md` に以下を統合：
- 7セクション構成テンプレート（はじめに/基礎知識/データで見る現状/実践ガイド/ケーススタディ/注意点・リスク/まとめ）
- 6テーマ（nisa/fund_selection/asset_allocation/ideco/market_basics/simulation）
- ソース戦略（8件以上、A+B 60%以上）
- 10用語の平易化パターン
- 可視化戦略（3-5枚のチャート/表画像）

article-research コマンドと article-full コマンドの asset_management ルーティングを `asset-management-workflow` から `investment-research` スキルに変更。

### X投稿削除

SKILL.md の Step 6 に残存していた「X投稿告知（asset_management のみ）」ステップを削除。
note 投稿のみに整理。

### 共通ルール整備（common-rules.md 更新）

| 変更内容 | 詳細 |
|---------|------|
| Section 5 モバイル最適化 | 文字数目安 3000-5000字→8000-10000字, 改行ルール（1行空け）追加 |
| Section 9 追加 | 共通チェックリスト（文字数・段落空行・禁止表現・免責・ソースURL・表画像化） |
| verification_status 注記追加 | claims.json に verification_status フィールドがない旨を明記 |

### カテゴリ別 references 更新（6ファイル）

stock-analysis / macro-economy / investment-education / quant-analysis / market-report:
- 文字数を 8000-10000字 に変更
- 免責事項を `{snippets/disclaimer.md の全文を挿入}` 参照形式に統一（`>` 引用ブロック削除）
- common-rules.md と重複するチェックリスト項目を削除し、カテゴリ固有のみ残存

asset-management:
- 上記に加え、7セクションテンプレート・ソース戦略・可視化ガイドを全面刷新
- X投稿セクション削除

### verified/unverified/disputed タグの由来調査

実際の claims.json（複数の記事ディレクトリ）を確認した結果：
- スキーマは `category/claim/evidence/impact` であり `verification_status` フィールドは存在しない
- common-rules.md の verified/unverified/disputed フレームワークは設計上の理想であり、現在の pipeline では自動生成されない
- 対処: ライターは evidence の質（公式データ/メディア報道/推測）から信頼度を自己判断するよう common-rules.md に注記を追加

## 決定事項

1. **全記事カテゴリの文字数を 8000-10000字 に統一** (dec-2026-03-31-001)
2. **asset-management-workflow 廃止・finance-article-writer 一本化** (dec-2026-03-31-002)
3. **asset_management から X投稿機能を削除** (dec-2026-03-31-003)
4. **common-rules.md に共通チェックリスト（section 9）を追加** (dec-2026-03-31-004)
5. **note.com 改行ルール（段落間1行空け）を common-rules.md に明文化** (dec-2026-03-31-005)

## アクションアイテム

- [ ] research-neo4j の asset_management データを拡充（FinancialDataPoint 投入） (act-2026-03-31-001, 優先度: 中)
- [ ] 既存ドラフト記事（articles/asset_management/ 配下）を更新ルールに合わせて完成・公開 (act-2026-03-31-002, 優先度: 高)

## 次回の議論トピック

- research-neo4j への投資信託・ETF データ拡充方法（graph-queue パイプライン経由）
- claims.json pipeline への `verification_status` フィールド追加の実装検討
- 既存ドラフト記事のレビューと公開優先順位

## 参考情報

- asset-management-workflow 廃止先: `trash/2026-03-31_asset-management-workflow/`
- 更新されたスキル: `.claude/skills/finance-article-writer/references/asset-management.md`
- 共通ルール: `.claude/skills/finance-article-writer/references/common-rules.md`
- Neo4j: Discussion `disc-2026-03-31-finance-article-writer-refactor`
