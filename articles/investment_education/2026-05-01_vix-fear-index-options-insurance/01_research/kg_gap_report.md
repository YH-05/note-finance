# KGギャップ分析レポート

**記事**: VIX恐怖指数の読み方：オプション市場が示す『市場の保険料』の正体
**実行日**: 2026-05-07
**対象DB**: research-neo4j

## 既存データサマリー

| 項目 | 件数 |
|------|------|
| VIX関連ファクト | 3件 |
| VIX関連トピック | 2件（VIX恐怖指数、オプション取引の基礎） |
| ソース鮮度 | published_at未設定（不明） |
| センチメント分布 | 未収集 |

## 特定されたギャップ

| ギャップ種別 | 内容 | 優先度 |
|------------|------|--------|
| no_coverage | VIX計算手法・オプション市場との関係・恐怖指数の読み方が未収集 | HIGH |
| stale_data | published_atがnull（鮮度不明）の古いデータのみ | HIGH |
| missing_financials | VIX履歴水準・閾値データなし | MEDIUM |
| no_coverage | VIX term structure・VIXスパイクのパターン未収集 | HIGH |
| no_coverage | オプションプレミアム→VIX算出ロジック未収集 | HIGH |

## 推奨検索クエリ

1. "VIX指数 計算方法 オプション市場 インプライドボラティリティ"
2. "VIX 恐怖指数 読み方 水準 歴史的高値"
3. "VIX 20以上 30以上 市場暴落 サイン"
4. "CBOE VIX methodology S&P500 options"
5. "implied volatility options premium insurance analogy"
6. "VIX spikes history 2008 2020 Covid"
7. "VIX term structure contango backwardation"
8. "VIX ETF VXX 個人投資家 活用法"
