# KG投入レポート

- **記事ID**: 2026-04-01_japan-etf-beginners-guide
- **投入日時**: 2026-04-01
- **graph-queue**: `.tmp/graph-queue/web-research/gq-20260401143237-31f36746.resolved.json`

---

## 投入結果

| 指標 | 件数 |
|------|------|
| 投入ノード数 | **58** |
| 投入リレーション数 | **227** |

## リレーション内訳

| リレーション | 成功 | 失敗 |
|------------|------|------|
| SOURCE → FACT (source_fact) | 11 | 0 |
| FACT → SOURCE (extracted_from_fact) | 11 | 0 |
| FACT → ENTITY (fact_entity) | 9 | 0 |
| TAGGED (Source/Entity → Topic) | 72 | 0 |
| TAGGED (Fact → Topic) | 66 | 0 |

## ギャップ解消状況

| ギャップ | 解消 |
|---------|------|
| ETF銘柄Entityが未登録（1306/1321/1308/1475/2558/2559/1489） | ✅ 解消 |
| 日本証券会社Entityが未登録（SBI/楽天/松井/マネックス） | ✅ 解消 |
| ETF関連Fact/Claimがゼロ | ✅ 解消（11 Fact投入） |
| FinancialDataPoint未登録 | △ 今回は含まず（要追加） |
