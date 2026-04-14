# KGギャップ分析レポート

**記事**: 原油$200シナリオとXLE投資戦略（2026-04-14_oil-200-xle-strategy）
**生成日時**: 2026-04-14
**照会先**: research-neo4j (bolt://localhost:7688)

## 既存データサマリー

| Entity | Label | Fact | Claim | Source | 最新ソース |
|---|---|---|---|---|---|
| Oil | Commodity | 2 | 25 | 26 | 2026-03-19 |
| Crude Oil | Commodity | 9 | 2 | 5 | 2026-01-27 |
| Energy Select Sector SPDR (XLE) | MarketIndex | 0 | 2 | 2 | 2026-01-27 |

- **関連企業 (XLE constituent) 単独ノード**: 未登録（XOM / CVX / COP / EOG / SLB は KG 未収録）
- **Claim センチメント分布（Oil）**: 弱気優位（-0.6: 16件、その他: 9件）
- **未回答 Question**: 0件

## 特定されたギャップ

| # | ギャップ種別 | 優先度 | 判定根拠 |
|---|---|---|---|
| G1 | stale_data | HIGH | Oil の最新ソースが 2026-03-19（26日前）。4月のスポット価格、停戦合意、Brent$141到達などが未取込 |
| G2 | no_coverage | HIGH | XLE 構成銘柄（XOM/CVX/COP/EOG/SLB）の Fact/Claim が 0件 |
| G3 | missing_financials | MEDIUM | XLE の FinancialDataPoint が 0件（基準価格、YTD リターン、AUM 等なし） |
| G4 | stale_data | MEDIUM | Crude Oil の最新 Fact が 2026-01-27、3月の Strait of Hormuz 封鎖後の価格データは Wikipedia経由のみ |
| G5 | missing_futures_curve | HIGH | 先物カーブ（コンタンゴ/バックワーデーション）に関する定量データなし |

## ギャップ解消用の推奨検索クエリ

- [x] `Brent crude oil price April 2026 Strait of Hormuz supply disruption level`
- [x] `WTI April 21 futures contract expiration 2026 backwardation spread physical`
- [x] `EIA weekly petroleum status report April 2026 crude inventory Cushing`
- [x] `XLE Energy ETF top holdings 2026 XOM CVX COP performance YTD`
- [x] `ExxonMobil Chevron Q1 2026 production earnings oil price leverage`
- [x] `oil futures backwardation cash carry trade short squeeze April 2026 JP Morgan`
- [x] `Goldman Sachs Brent 150 price target Iran war Hormuz April 2026`
- [x] `SPR Strategic Petroleum Reserve release 2026 Biden Trump oil`

全8クエリを Tavily で実行し、G1/G2/G5 を解消。詳細は `research_notes.md` 参照。
