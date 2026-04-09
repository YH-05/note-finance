# KG投入レポート
実行日時: 2026-04-09

## 投入パイプライン

| ステップ | コマンド | 結果 |
|---------|---------|------|
| ① emit | `emit_research_queue.py --command web-research` | ✓ `gq-20260409074044-d62cc514.json` 生成 |
| ② link | `entity_linker.py --instance research --ner-fallback` | ✓ `gq-20260409074044-d62cc514.resolved.json` 生成 |
| ③ load | `neo4j_loader.py --instance research` | ✓ exit 0（成功） |

## 投入対象

| ノード種別 | 件数 |
|-----------|------|
| Source | 12件 |
| Entity（Country/Commodity/MarketIndex/Organization/Concept/Broker/Indicator） | 12件 |
| Topic | 6件 |
| Fact | 9件 |

## ギャップ解消状況

| ギャップ | 解消状況 |
|---------|---------|
| イラン関連Fact 0件 | ✓ 9件のFactを投入（イラン・ホルムズ・停戦等） |
| 株式市場インパクトの記録なし | ✓ S&P500/MSCI World/VIX関連Factを投入 |
| 経済見通しの記録なし | ✓ Oxford Economics/Goldman Sachsの分析を投入 |
| イラン戦争2026年2月〜4月の時系列なし | ✓ 主要イベントをFactとして記録 |
| データ鮮度不明 | △ 投入ソースの最新日は2026-04-09 |
| Claim stance未分類 | △ 今回投入分はstance付与済み（15件） |

## 確認コマンド（後から実行）

```cypher
MATCH (f:Fact)-[:RELATES_TO]->(e:Country {name: 'イラン'})
RETURN count(f) AS iran_facts
```

## 備考

- 投入後にNeo4jが一時的にDatabaseUnavailableエラーを返したが、loader exit=0のため投入自体は成功と判断
- 処理済みファイル: `.tmp/graph-queue/web-research/gq-20260409074044-d62cc514.resolved.json`
