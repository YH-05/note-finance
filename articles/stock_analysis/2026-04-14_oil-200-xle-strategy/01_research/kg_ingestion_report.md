# KG永続化レポート

**投入日時**: 2026-04-14
**session_id**: article-research-oil-200-xle-strategy-20260414-1530
**graph-queue**: `.tmp/graph-queue/web-research/gq-20260414091648-3f8065a3.resolved.json`

## 投入結果

| 種別 | 件数 |
|---|---|
| Source | 12 |
| Entity（Commodity/Company/Index/Organization/Place/Policy） | 13 |
| Topic | 3 |
| Fact | 12 |
| Relations | 50+ （STATES_FACT, RELATES_TO, TAGGED） |

## ギャップ解消状況

| # | ギャップ | 状態 | 備考 |
|---|---|---|---|
| G1 | Oil stale_data | ✓ 解消 | 4月スポット$141/$124、停戦、SPR放出など反映 |
| G2 | XLE構成銘柄 no_coverage | ✓ 部分解消 | XOM/CVX/COP/EOG/SLB をEntity登録、Factで主要数値化 |
| G3 | XLE missing_financials | ⚠ 保留 | YTD +30%はFact化。FinancialDataPointは未生成（必要なら quants DB 連携で補完） |
| G4 | Crude Oil stale_data | ✓ 解消 | Brent/WTIのスプレッドコンテキスト追加 |
| G5 | missing_futures_curve | ✓ 解消 | Brent スポット vs 先物 $30 バックワーデーションをFact化 |

## 検証クエリ

```cypher
MATCH (s:Source) WHERE s.url CONTAINS 'cnbc.com/2026/04/08'
OPTIONAL MATCH (s)-[:STATES_FACT]->(f:Fact)
RETURN s.url, count(f) AS facts
-- 結果: facts=2 ✓
```
