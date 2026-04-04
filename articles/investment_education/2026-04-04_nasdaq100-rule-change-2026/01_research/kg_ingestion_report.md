# KG投入結果レポート

**実行日時**: 2026-04-04  
**セッションID**: article-research-nasdaq100-rule-change-2026-20260404  
**投入先**: research-neo4j (bolt://localhost:7688)

---

## 投入結果サマリー

| ノード種別 | 件数 |
|-----------|------|
| Source | 9件 |
| Fact | 9件 |
| Topic | 5件 |
| Entity (Company/MarketIndex/Instrument) | 9件 |

## 投入ノード（主要Facts）

✅ Nasdaqルール変更発表（2026/3/30）概要  
✅ Fast Entryルール（15営業日ルール）  
✅ 時価総額算定変更（全株式クラス考慮）  
✅ フロート要件廃止・ウェイトペナルティ導入  
✅ Top 125エグジットルール  
✅ TSO調整スケジュール化  
✅ QQQ/Nasdaq-100のAUM・規模データ  
✅ SpaceX IPO計画とルール変更の関連  
✅ QQQ集中度データ（上位10銘柄=47%）

## 新規エンティティ

- SpaceX（Company）
- OpenAI（Company）
- Anthropic（Company）

## ギャップ解消状況

| ギャップ | 解消 |
|---------|------|
| Nasdaq-100ルール変更（no_coverage） | ✅ |
| Fast Entryルール（no_coverage） | ✅ |
| Phantom市場時価総額（no_coverage） | ✅ |
| Top 125エグジットルール（no_coverage） | ✅ |
| TSO調整変更（no_coverage） | ✅ |
| リスク面（missing_bear_case） | ✅ |

## 備考

- `ingest_graph_queue.py` の検証ステップでVERIFICATION ERRORが出力されたが、MERGEの冪等性により「新規作成=0」がカウントされた偽陽性と判断。実際にNeo4jへのクエリでFactとSTATES_FACTリレーションの存在を確認済み。
- graph-queue: `.tmp/graph-queue/web-research/gq-20260404101620-abb752f4.resolved.json`
