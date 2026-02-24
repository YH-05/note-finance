---
description: 新規金融記事フォルダを作成し、カテゴリ別テンプレートから初期構造を生成します。
---

# 新規金融記事フォルダ作成

## パラメータ（ユーザーに確認）

| パラメータ | 必須 | 説明         |
| ---------- | ---- | ------------ |
| トピック名 | ○    | 記事のテーマ |

## 処理フロー

### 1. トピック名の確認

ユーザーからトピック名を取得（未指定の場合は質問する）。

### 2. カテゴリの選択

以下から選択してもらう:

1. `market_report` - 市場レポート・相場解説
2. `stock_analysis` - 個別銘柄・企業分析
3. `economic_indicators` - 経済指標・マクロ分析
4. `investment_education` - 投資教育・基礎知識
5. `quant_analysis` - クオンツ分析・戦略検証

### 3. 英語テーマ名の生成

トピック名からケバブケースの英語テーマ名を生成し、ユーザーに確認する。

例:

- `2025年1月第2週 米国市場週間レビュー` → `us-market-weekly-2025w02`
- `テスラ決算分析` → `tsla-earnings-analysis`

### 4. シンボル・指標の入力（カテゴリ別）

- market_report, stock_analysis, quant_analysis → 対象シンボルを入力
- economic_indicators → FRED指標を入力
- investment_education → スキップ可

### 5. 分析期間の入力

market_report, stock_analysis, economic_indicators, quant_analysis の場合:

- 開始日 (YYYY-MM-DD)
- 終了日 (YYYY-MM-DD)

### 6. article_id の生成と重複確認

形式: `{category}_{seq:03d}_{theme_name_en}`

// turbo

```bash
ls -d articles/{category}_* 2>/dev/null | grep -o '{category}_[0-9]*' | cut -d'_' -f2 | sort -n | tail -1
```

### 7. フォルダ構造の作成

```bash
mkdir -p articles/{article_id}
cp -r template/{category}/* articles/{article_id}/
```

### 8. メタデータの初期化

`articles/{article_id}/article-meta.json` を更新:

- article_id, topic, category, symbols, date_range 等を設定
- status = "research"
- human_feedback の初期化

### 9. 完了報告

作成された記事情報を表示し、次のステップを案内:

1. リサーチ開始
2. 執筆開始（リサーチ完了後）

## カテゴリ別デフォルト設定

| カテゴリ             | target_audience | 主な入力項目            |
| -------------------- | --------------- | ----------------------- |
| market_report        | intermediate    | symbols, date_range     |
| stock_analysis       | intermediate    | symbols, date_range     |
| economic_indicators  | intermediate    | fred_series, date_range |
| investment_education | beginner        | topics                  |
| quant_analysis       | advanced        | symbols, date_range     |

## 関連ワークフロー

- `/finance-full` - 全工程一括実行
- `/finance-suggest-topics` - トピック提案
