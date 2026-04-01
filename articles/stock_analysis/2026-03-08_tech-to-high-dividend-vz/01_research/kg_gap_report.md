# KG ギャップ分析レポート

## セッション情報
- **記事スラッグ**: 2026-03-08_tech-to-high-dividend-vz
- **分析日時**: 2026-04-01
- **テーマ**: ハイテクから「退屈な高配当」への資金シフト：ベライゾン（VZ）独走の正体

## 既存データサマリー

| エンティティ | ファクト数 | クレーム数 | 最新ソース日付 |
|------------|-----------|-----------|-------------|
| Verizon (VZ) | 15 | 7 | null（不明） |
| Invesco QQQ Trust (QQQ) | 0 | 1 | null（不明） |

- **クレームセンチメント**: bullish×5, bearish×2, neutral×0
- **ソース総数**: 4件（SEC 10-K, アナリストレポート, ニュース, 市場分析）

## 特定されたギャップ

| # | ギャップ種別 | 内容 | 優先度 |
|---|------------|------|--------|
| 1 | stale_data | 全ソースのpublished_atがnull。記事のdate_range終端が2025-03-08で、現在2026-04-01。約1年分の最新動向が欠落 | HIGH |
| 2 | no_coverage | QQQのFactが0件。ハイテクvsディフェンシブの資金シフト比較に必要なデータなし | HIGH |
| 3 | missing_bear_case | bearish claims 2件に対しbullish 5件。負債水準・競合リスクの詳細が不足 | MEDIUM |
| 4 | missing_financials | VZ・QQQの価格パフォーマンス比較（FinancialDataPoint）が0件 | MEDIUM |

## 推奨検索クエリ（ギャップ優先）

### HIGH優先度（stale_data解消）
1. `Verizon VZ stock 2026 Q1 performance dividend`
2. `Verizon earnings 2025 Q4 results annual outlook 2026`
3. `Frontier acquisition integration Verizon 2026 update`

### HIGH優先度（no_coverage: QQQ）
4. `QQQ Nasdaq 100 performance 2025 2026 tech stock rotation`
5. `tech stock rotation defensive dividend 2025 2026 institutional flows`

### MEDIUM優先度（missing_bear_case）
6. `Verizon debt risk concerns 2026 bearish case`
7. `Verizon competition T-Mobile AT&T market share 2026`

### MEDIUM優先度（missing_financials）
8. `VZ vs QQQ relative performance chart 2024 2025`
9. `telecom sector XLC XLU vs QQQ 2025 sector rotation`
10. `Verizon analyst target price 2026 consensus`

### 通常リサーチ
11. `Verizon 5G FWA Fixed Wireless Access growth 2026`
12. `Verizon dividend safety payout ratio 2026`
