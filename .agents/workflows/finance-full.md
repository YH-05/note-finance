---
description: 記事作成の全工程を一括実行する統合ワークフロー。フォルダ作成→リサーチ→執筆の全ステップを自動化します。
---

# 金融記事 統合ワークフロー

記事作成の全工程（フォルダ作成→リサーチ→執筆）を一括実行します。

## パラメータ（ユーザーに確認）

| パラメータ | 必須 | デフォルト | 説明                                            |
| ---------- | ---- | ---------- | ----------------------------------------------- |
| トピック名 | ○    | -          | 記事のテーマ                                    |
| category   | -    | 対話で選択 | カテゴリ（market_report, stock_analysis, etc.） |
| depth      | -    | auto       | リサーチ深度（auto/shallow/deep）               |
| mode       | -    | quick      | 編集モード（quick/full）                        |

## 処理フロー

```
Phase 1: 記事フォルダ作成 (/new-finance-article)
├── トピック名入力
├── カテゴリ選択
├── シンボル/指標入力
└── article_id 生成 → [HF1] トピック承認

Phase 2: リサーチ実行
├── クエリ生成
├── データ収集（並列: market-data, web, wiki, sec-filings）
├── データ処理・センチメント分析
└── 分析・検証 → [HF3] 主張採用確認

Phase 3: 記事執筆 (/finance-edit)
├── 初稿作成 → [HF5] 初稿レビュー
├── 批評（並列）
└── 修正 → [HF6] 最終確認
```

### 1. Phase 1: 記事フォルダ作成

`/new-finance-article` ワークフローの全機能を実行する:

1. トピック名が未指定なら質問
2. カテゴリが未指定ならユーザーに選択させる
    - market_report / stock_analysis / economic_indicators / investment_education / quant_analysis
3. 英語テーマ名を生成してユーザーに確認
4. シンボル・指標の入力（カテゴリ別）
5. 分析期間の入力
6. article_id の生成とフォルダ構造作成

### 2. [HF1] トピック承認

記事ID、トピック、カテゴリを表示し、ユーザーに確認を求める。

### 3. Phase 2: リサーチ実行

以下を順次実行:

1. クエリ生成（finance-query-generator）
2. データ収集（並列: finance-market-data, finance-web, finance-wiki, finance-sec-filings）
3. データ処理（finance-source, finance-claims）
4. センチメント分析（finance-sentiment-analyzer）
5. 分析・検証（finance-claims-analyzer, finance-fact-checker, finance-decisions）
6. 可視化（finance-visualize）

### 4. [HF3] 主張採用確認

リサーチ結果（収集件数、分析結果）を表示し、decisions.json の確認を促す。

### 5. Phase 3: 記事執筆

`/finance-edit` ワークフローを実行:

1. 初稿作成 → [HF5] 初稿レビュー
2. 批評（quick: fact+compliance / full: 5エージェント）
3. 修正 → [HF6] 最終確認

### 6. 完了報告

以下を表示:

- 記事情報（ID, トピック, カテゴリ）
- 実行時間
- 生成ファイル一覧（01_research/, 02_draft/）
- 最終スコア
- 次のステップ（最終確認 → 公開準備 → note.com 公開）

## カテゴリ別推奨設定

| カテゴリ             | 推奨 depth | 推奨 mode | 理由             |
| -------------------- | ---------- | --------- | ---------------- |
| market_report        | auto       | quick     | 速報性重視       |
| stock_analysis       | deep       | full      | 品質重視         |
| economic_indicators  | deep       | full      | 正確性重視       |
| investment_education | deep       | full      | 読みやすさ重視   |
| quant_analysis       | deep       | full      | データ正確性重視 |

## 実行時間の目安

| 設定            | 所要時間  |
| --------------- | --------- |
| shallow + quick | 約5-10分  |
| auto + quick    | 約10-20分 |
| deep + full     | 約20-40分 |

## 関連ワークフロー

- `/new-finance-article` - Phase 1 のみ実行
- `/finance-edit` - Phase 3 のみ実行
- `/finance-suggest-topics` - トピック提案
