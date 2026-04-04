# KG投入結果レポート

**セッション**: article-research-iran-war-20260404  
**投入日時**: 2026-04-04  
**投入先**: research-neo4j (bolt://localhost:7688)

---

## 投入結果

| ノード種別 | 投入数 |
|-----------|--------|
| Source    | 8件    |
| Fact      | 11件   |

## 投入ソース一覧

| URL | authority_level |
|-----|----------------|
| wikipedia.org/wiki/2026_Iran_war | media |
| wikipedia.org/wiki/Economic_impact_of_the_2026_Iran_war | media |
| wikipedia.org/wiki/2026_Strait_of_Hormuz_crisis | media |
| wikipedia.org/wiki/Energy_in_Japan | official |
| wikipedia.org/wiki/Strait_of_Hormuz | media |
| wikipedia.org/wiki/1973_oil_crisis | media |
| wikipedia.org/wiki/1990_oil_price_shock | media |
| wikipedia.org/wiki/Japanese_asset_price_bubble | media |

## ギャップ解消状況

| ギャップ | 解消状況 |
|---------|---------|
| 米イラン戦争シナリオ | ✅ 解消（2026年2月28日開戦の事実を投入） |
| ホルムズ海峡封鎖データ | ✅ 解消（封鎖経緯・原油価格推移を投入） |
| 日本エネルギー依存度 | ✅ 解消（原油93%中東依存、備蓄169日分等） |
| 歴史的先例 | ✅ 解消（1973年・1990年の油価データ投入） |
| 日本株市場影響 | ✅ 解消（日経2%超下落ファクト投入） |
| セーフヘイブン挙動 | ✅ 解消（金が28%下落という異常挙動を投入） |

## パイプライン実行ログ

```
① emit_research_queue.py: gq-20260404140131-d22bc383.json 生成
② entity_linker.py: gq-20260404140131-d22bc383.resolved.json 生成
③ neo4j_loader.py: 投入完了（exit 0）
```
