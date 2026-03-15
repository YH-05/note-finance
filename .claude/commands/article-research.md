---
description: カテゴリに応じたリサーチを実行します。
argument-hint: @<article_dir>
---

カテゴリに応じたリサーチを実行します。

## 入力パラメータ

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| @article_dir | ○ | - | 記事ディレクトリのパス（`articles/{category}/{YYYY-MM-DD}_{slug}/`） |

## 引数の解釈ルール

共通パス解決ロジックに従う。詳細は `.claude/commands/_shared/path-resolution.md` を参照。

```
/article-research @articles/stock_analysis/2026-03-15_tsla-earnings-analysis/
```

## 処理フロー

```
Step 1: meta.yaml 読み込み
├── category を取得
└── カテゴリ別追加パラメータを取得

Step 2: カテゴリ別リサーチ実行
├── stock_analysis    → investment-research スキル
├── macro_economy     → investment-research スキル
├── quant_analysis    → investment-research スキル
├── asset_formation   → asset-management-workflow Phase 1
├── side_business     → experience-db-workflow Phase 1-2
└── weekly_report     → generate-market-report Phase 2-3

Step 3: 結果保存・ステータス更新
├── 01_research/ にリサーチ成果物を保存
└── meta.yaml の workflow.research = "done"
```

## 実行手順

### Step 1: meta.yaml 読み込み

1. **記事ディレクトリの解決**

   引数から記事ディレクトリを特定し、`meta.yaml` を読み込みます。

   ```yaml
   # 以下のフィールドを確認
   category: "stock_analysis"    # 必須
   symbols: [...]                # stock_analysis, quant_analysis
   fred_series: [...]            # macro_economy
   theme: "..."                  # side_business
   date_range: { start, end }   # stock_analysis, macro_economy, quant_analysis
   ```

2. **ステータス確認**

   `workflow.research` が既に `"done"` の場合は再実行の確認を行います：

   ```
   リサーチは既に完了しています。再実行しますか？ (y/n)
   ```

### Step 2: カテゴリ別リサーチ実行

#### stock_analysis / macro_economy / quant_analysis

既存の `investment-research` スキルに処理を委譲します。

```
実行内容:
- クエリ生成（finance-query-generator）
- データ収集（並列）
  - finance-market-data（シンボル/指標データ）
  - finance-web（Web検索）
  - finance-wiki（Wikipedia参照）
  - finance-sec-filings（SEC開示情報、stock_analysis時）
- データ処理
  - finance-source（ソース整理）
  - finance-claims（主張抽出）
- 分析・検証
  - finance-claims-analyzer
  - finance-fact-checker
  - finance-decisions
```

出力先: `01_research/` 配下に各成果物を保存

#### asset_formation

既存の `asset-management-workflow` スキルの Phase 1 に処理を委譲します。

```
実行内容:
- JP RSSプリセットからソース収集
- テーマ別キーワードマッチング
- 公開日時フィルタリング
- ソースキュレーション
```

出力先: `01_research/` 配下にセッションデータとソースを保存

#### side_business

既存の `experience-db-workflow` スキルの Phase 1-2 に処理を委譲します。

```
実行内容:
- Phase 1: ソース収集（Reddit + RSS + Web検索 + note.com巡回）
- Phase 2: 合成パターン生成（experience-synthesizer）
```

出力先: `01_research/` 配下にソースと合成データを保存

#### weekly_report

既存の `generate-market-report` コマンドの Phase 2-3 に処理を委譲します。

```
実行内容:
- 市場データ収集（yahoo_finance, FRED）
- ニュース検索（RSS/Tavily またはローカルJSON）
- データ整理・分析
```

出力先: `01_research/` 配下に市場データとニュースを保存

### Step 3: 結果保存・ステータス更新

3. **meta.yaml の更新**

   ```yaml
   workflow:
     research: "done"    # ← 更新
   updated_at: "YYYY-MM-DD"
   ```

4. **リサーチ結果の報告**

   ```markdown
   ## リサーチ完了

   ### 記事情報
   - **トピック**: {topic}
   - **カテゴリ**: {category}

   ### 収集結果
   - ソース数: {source_count}件
   - 主張/ポイント: {claims_count}件
   - データファイル: {file_count}件

   ### 出力先
   `articles/{category}/{YYYY-MM-DD}_{slug}/01_research/`

   ### 次のステップ
   1. リサーチ結果を確認
   2. ドラフト作成: `/article-draft @articles/{category}/{YYYY-MM-DD}_{slug}/`
   ```

## エラーハンドリング

### meta.yaml が見つからない

```
エラー: meta.yaml が見つかりません

指定パス: {article_dir}

対処法:
- /article-init でフォルダを初期化してください
- パスが正しいか確認してください
```

### カテゴリが不明

```
エラー: 不明なカテゴリです: {category}

有効なカテゴリ:
- asset_formation, side_business, macro_economy
- stock_analysis, weekly_report, quant_analysis
```

### データ収集失敗

```
エラー: データ収集中に問題が発生しました

失敗した処理: {failed_step}
エラー内容: {error_message}

対処法:
1. ネットワーク接続を確認
2. シンボル/指標名が正しいか確認
3. 再実行: /article-research @{article_dir}
```

## 関連コマンド

- **前提コマンド**: `/article-init`
- **後続コマンド**: `/article-draft`
- **統合コマンド**: `/article-full`
- **使用スキル**: investment-research, asset-management-workflow, experience-db-workflow
