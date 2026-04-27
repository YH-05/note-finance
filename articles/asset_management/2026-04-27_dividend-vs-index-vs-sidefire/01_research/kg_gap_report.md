# KGギャップ分析レポート

**記事スラッグ**: dividend-vs-index-vs-sidefire  
**分析日**: 2026-04-27

## 既存KGデータサマリー

| エンティティ | ファクト数 | 最新ファクト |
|------------|-----------|-------------|
| S&P 500 | 7 | 2026-03-25（やや古い） |
| SCHD | 1 | データなし |
| サイドFIRE | 1 | データなし |
| インデックス投資（Topic） | 1 | — |

**不足エンティティ**: 自社株買い（buyback）、VYM、高配当株戦略、Dividend Yield、Shareholder Yield

## ギャップ分析

| ギャップ種別 | 対象 | 優先度 |
|------------|------|--------|
| stale_data | S&P 500ファクトが1ヶ月以上前 | HIGH |
| no_coverage | SCHD詳細データ（利回り・構成）が不足 | HIGH |
| no_coverage | 自社株買い（buyback）の日本・米国データがない | HIGH |
| no_coverage | サイドFIRE試算データが不足 | HIGH |
| missing_bear_case | 高配当株のデメリット（テック株劣後・税務）が未記録 | MEDIUM |

## 推奨検索クエリ（優先度順）

1. SCHD 配当利回り パフォーマンス 2026年
2. 日本企業 自社株買い 2025年 過去最高
3. サイドFIRE 高配当 インデックス 必要資産額
4. buyback yield shareholder yield S&P500 2026
5. VYM SCHD 10年 総リターン比較
