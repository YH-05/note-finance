# KG投入レポート

- 実行日: 2026-04-04
- 対象: インデックスファンドの年齢別選び方リサーチ

## 結果

**KG永続化: 成功**

research-neo4j (bolt://localhost:7687, database=research) に正常投入しました。

| 項目 | 件数 |
|------|------|
| nodes | 48 |
| relations | 187 |

### リレーション検証

| リレーション | 期待 | 実際 |
|------------|------|------|
| source_fact | 7 | 7 |
| extracted_from_fact | 7 | 7 |
| tagged | 72 | 72 |
| tagged_fact | 42 | 42 |

### 投入データ概要

| 種別 | 件数 |
|------|------|
| Source | 12 |
| Topic | 6 |
| Fact | 7 |
| Entity (Regulation/Instrument/MarketIndex/Company) | 3 |
| classification_nodes | 20 |

## graph-queue JSON

`.tmp/graph-queue/web-research/gq-20260404042146-3a3835b8.json`

## 投入方法

```python
from data_pipeline.neo4j_loader import ingest_to_neo4j
result = ingest_to_neo4j(data, skip_schema_check=True)
```
