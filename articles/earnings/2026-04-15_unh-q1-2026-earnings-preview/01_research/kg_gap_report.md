# KGギャップレポート: UNH Q1 2026

作成日: 2026-04-15  
ステータス: **スキップ**（research-neo4j 未起動のため照会不可）

## 照会結果

research-neo4j (bolt://localhost:7688) に接続できませんでした。

KGの既存データ照会はスキップし、Web検索で全リサーチを実施しました。

## 推奨アクション

Neo4j起動後に以下のクエリでUNH関連データを照会可能:

```cypher
MATCH (f:Fact)-[:RELATES_TO]->(c:Company)
WHERE c.name CONTAINS 'UnitedHealth' OR c.ticker = 'UNH'
RETURN c.name AS entity, count(f) AS fact_count
LIMIT 20
```

```cypher
MATCH (cl:Claim)-[:RELATES_TO]->(c:Company)
WHERE c.name CONTAINS 'UnitedHealth' OR c.ticker = 'UNH'
RETURN cl.sentiment AS sentiment, count(cl) AS cnt
ORDER BY cnt DESC
```
