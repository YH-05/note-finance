# KG Ingestion Report

**記事**: Blue Owl暴落が示すプライベートクレジットの「次の亀裂」
**投入日**: 2026-04-04
**インスタンス**: research-neo4j (bolt://localhost:7687, database=research)
**graph-queue ID**: gq-20260404102138-00e2b7f0

## 投入結果

| ノード種別 | 件数 |
|-----------|------|
| Source | 10件 |
| Fact | 10件 |
| Topic | 5件 |
| Concept (entities) | 9件 |
| **合計ノード** | **51件** |

| リレーション種別 | 件数 |
|----------------|------|
| STATES_FACT | 10件 |
| EXTRACTED_FROM | 10件 |
| TAGGED | 50件 |
| TAGGED_FACT | 50件 |
| **合計リレーション** | **184件** |

## 投入確認

### 主要ソース（確認済み）

- Blue Owl caps private credit funds redemptions at 5%... (CNBC 2026-04-02) ✅
- Asset Manager Stocks Fall as Blue Owl Caps Private Credit Fund... (Bloomberg 2026-04-02) ✅
- Ares Limits Private Credit Fund Withdrawals... (Bloomberg 2026-03-24) ✅
- Private credit defaults, loan quality raise risk... (CNBC 2026-03-25) ✅
- AIMA: private credit market reach $3.5 trillion ✅
- BIS Quarterly Review - private credit AI/SaaS risks ✅

### エンティティ（Concept ラベルで投入）

- Blue Owl Capital, Apollo Global Management, Ares Management
- Blackstone, KKR, BlackRock, OBDC, OWL, APO

## ギャップ解消状況

| ギャップ | 解消状況 |
|---------|---------|
| Blue Owl Capital の data | ✅ 解消（10ファクト投入） |
| プライベートクレジット市場規模・デフォルト率 | ✅ 解消 |
| 競合他社比較データ | ✅ 解消 |
| SaaSリスク・BIS警告データ | ✅ 解消 |
| 日本人投資家視点データ | ✅ 解消（リサーチノートに記録） |

## 備考

- entity_linker.py がエンティティを `Company` ではなく `Concept` ラベルにマッピング（未解決エンティティのフォールバック挙動）
- MCP tool (mcp__neo4j-research) は bolt://localhost:7688 に接続するため、本投入データ（7687 database=research）はMCP経由では参照不可
- 将来の調査時は同一データベース・インスタンスへの接続を確認すること
