# KGギャップ分析レポート
生成日: 2026-04-09

## 既存データサマリー

| Entity | Type | Fact件数 |
|--------|------|---------|
| 原油WTI | Commodity | 16 |
| WTI原油 | Commodity | 12 |
| Crude Oil | Commodity | 9 |
| 原油 | Commodity | 7 |
| イラン | Country | 5 |
| WTI | Commodity | 5 |
| 中東 | Country/Concept | 4 |
| Brent Crude | Commodity | 2 |
| VIX | MarketIndex | 1 |
| イスラエル | Country | 1 |

- 総ソース数: 59件
- 最新ソース日: 不明（published_dateがnull）
- Claim件数: 96件（全件stance=null、未分類）

## ギャップ一覧

| ギャップ種別 | 内容 | 優先度 |
|------------|------|--------|
| stale_data | 最新ソース日が不明。データ鮮度確認不可 | HIGH |
| no_coverage | イラン戦争（2026年2月開戦）の記録が皆無 | HIGH |
| no_coverage | 株式市場インパクト（S&P500、日経平均等）の地政学的記録なし | HIGH |
| no_coverage | 経済制裁・ホルムズ海峡リスク・原油供給ショックの記録なし | HIGH |
| no_coverage | 2026年2月〜4月の時系列イベントログなし | HIGH |
| missing_bear_case | 全Claimがstance未分類（bullish/bearishなし） | MEDIUM |
| missing_financials | VIX/S&P500/日経平均のFinancialDataPoint=0件 | MEDIUM |

## 推奨検索クエリ（優先順）

1. イラン戦争 2026年 経緯 開戦 時系列
2. Iran war 2026 stock market impact S&P500
3. Iran conflict 2026 oil price WTI Brent spike
4. Iran war economic impact 2026 GDP sanctions
5. イラン 株式市場 2026年 影響 日経平均
6. Strait of Hormuz oil supply disruption 2026
7. Iran war VIX volatility 2026
8. Middle East conflict 2026 interest rates bonds safe haven
