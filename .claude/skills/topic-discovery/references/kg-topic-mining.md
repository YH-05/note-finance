# KG トピック発掘リファレンス

research-neo4j（bolt://localhost:7688）から既存データを照会し、データ駆動のトピック候補を発掘するためのCypherクエリテンプレート集。

## 使用タイミング

topic-discovery の Phase 0（KG照会でトピック発掘）で使用する。
`mcp__neo4j-research__research-read_neo4j_cypher` で実行すること（読み取り専用）。

## Phase 0-A: KG データマイニング

### Q1: 未回答の Question ノード（知識ギャップ → トピック候補）

KG v2 の Question ノードは「何が分かっていないか」を構造化している。
status: open の Question はそのまま記事トピックの種になる。

```cypher
MATCH (q:Question)
WHERE q.status IN ['open', 'investigating']
OPTIONAL MATCH (q)-[:ASKS_ABOUT]->(e:Entity)
OPTIONAL MATCH (q)-[:MOTIVATED_BY]->(m)
RETURN q.content AS question,
       q.question_type AS type,
       q.priority AS priority,
       collect(DISTINCT e.name) AS related_entities,
       count(DISTINCT m) AS motivation_count
ORDER BY
  CASE q.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
  motivation_count DESC
LIMIT 15
```

Question.question_type と記事カテゴリの対応:

| question_type | 推奨カテゴリ |
|--------------|------------|
| data_gap | stock_analysis / macro_economy |
| contradiction | stock_analysis / macro_economy |
| prediction_test | quant_analysis / market_report |
| assumption_check | stock_analysis |
| consensus_divergence | stock_analysis |

### Q2: Insight (type: gap) — AI検出済みの情報ギャップ

```cypher
MATCH (ins:Insight)
WHERE ins.insight_type = 'gap' AND ins.status = 'draft'
OPTIONAL MATCH (ins)-[:TAGGED]->(t:Topic)
OPTIONAL MATCH (ins)-[:DERIVED_FROM]->(src)
RETURN ins.content AS gap_description,
       ins.insight_id AS id,
       collect(DISTINCT t.name) AS related_topics,
       count(DISTINCT src) AS evidence_count
ORDER BY evidence_count DESC
LIMIT 10
```

### Q3: Entity カバレッジ密度（薄いエンティティ → 深掘り記事チャンス）

Fact/Claim が少ないが、他エンティティとの関連が多いエンティティは「重要だが記事が不足」。

```cypher
MATCH (e:Entity)
WHERE NOT 'Memory' IN labels(e)
  AND e.entity_type IN ['company', 'index', 'sector', 'etf', 'central_bank', 'commodity']
OPTIONAL MATCH (f:Fact)-[:RELATES_TO]->(e)
OPTIONAL MATCH (c:Claim)-[:ABOUT]->(e)
OPTIONAL MATCH (e)-[r]-(other:Entity)
WITH e,
     count(DISTINCT f) AS fact_count,
     count(DISTINCT c) AS claim_count,
     count(DISTINCT r) AS relation_count
WHERE fact_count + claim_count < 5 AND relation_count >= 3
RETURN e.name AS entity,
       e.entity_type AS type,
       e.ticker AS ticker,
       fact_count,
       claim_count,
       relation_count,
       relation_count - (fact_count + claim_count) AS gap_score
ORDER BY gap_score DESC
LIMIT 15
```

### Q4: ソース急増エンティティ（トレンド検出）

直近30日でソースが急増しているエンティティはホットトピック。

```cypher
MATCH (s:Source)-[:MENTIONS]->(e:Entity)
WHERE s.published_at > datetime() - duration('P30D')
  AND NOT 'Memory' IN labels(e)
WITH e, count(DISTINCT s) AS recent_source_count
ORDER BY recent_source_count DESC
LIMIT 20

// 比較: 全期間のソース数
MATCH (s2:Source)-[:MENTIONS]->(e)
WITH e, recent_source_count, count(DISTINCT s2) AS total_source_count
WHERE total_source_count > 0
RETURN e.name AS entity,
       e.entity_type AS type,
       recent_source_count,
       total_source_count,
       toFloat(recent_source_count) / total_source_count AS recency_ratio
ORDER BY recency_ratio DESC, recent_source_count DESC
LIMIT 15
```

recency_ratio が高い（> 0.5）= 最近急速に注目が集まっている。

### Q5: 過去の topic-discovery 提案（再評価候補）

前回提案で `selected: null`（未決定）のまま残っているものを再評価。

```cypher
MATCH (c:Claim {claim_type: 'recommendation'})
WHERE c.selected IS NULL
OPTIONAL MATCH (c)-[:TAGGED]->(t:Topic)
RETURN c.topic_title AS topic,
       c.total_score AS score,
       c.timeliness AS timeliness,
       c.created_at AS proposed_at,
       t.name AS category
ORDER BY c.total_score DESC
LIMIT 10
```

### Q6: Entity 間リレーションからのクロスカッティング切り口

COMPETES_WITH, CAUSES, INFLUENCES 等のリレーションは、複数エンティティを横断する記事テーマを示唆する。

```cypher
MATCH (e1:Entity)-[r]->(e2:Entity)
WHERE type(r) IN ['COMPETES_WITH', 'CAUSES', 'INFLUENCES', 'CUSTOMER_OF', 'PARTNERS_WITH']
  AND NOT 'Memory' IN labels(e1) AND NOT 'Memory' IN labels(e2)
WITH type(r) AS rel_type, e1, e2,
     e1.name + ' → ' + e2.name AS pair
RETURN rel_type,
       e1.name AS entity1,
       e1.entity_type AS type1,
       e2.name AS entity2,
       e2.entity_type AS type2
ORDER BY rel_type, e1.name
LIMIT 30
```

### Q7: Claim センチメント対立（contradiction 検出）

同一 Entity に対して bullish/bearish の Claim が拮抗している場合、論争テーマとして記事価値が高い。

```cypher
MATCH (c:Claim)-[:ABOUT]->(e:Entity)
WHERE c.sentiment IN ['bullish', 'bearish']
  AND NOT 'Memory' IN labels(e)
WITH e,
     sum(CASE WHEN c.sentiment = 'bullish' THEN 1 ELSE 0 END) AS bull_count,
     sum(CASE WHEN c.sentiment = 'bearish' THEN 1 ELSE 0 END) AS bear_count
WHERE bull_count >= 2 AND bear_count >= 2
RETURN e.name AS entity,
       e.entity_type AS type,
       bull_count,
       bear_count,
       abs(bull_count - bear_count) AS divergence
ORDER BY divergence ASC, bull_count + bear_count DESC
LIMIT 10
```

divergence が小さい（= 意見が拮抗） → 論争テーマとして記事価値が高い。

### Q8: KG 全体統計（コンテキスト）

```cypher
MATCH (n)
WHERE NOT 'Memory' IN labels(n) AND NOT 'Archived' IN labels(n)
WITH labels(n) AS lbls, count(n) AS cnt
UNWIND lbls AS label
WITH label, sum(cnt) AS total
WHERE label IN ['Source', 'Entity', 'Fact', 'Claim', 'Topic', 'Question', 'Insight', 'FinancialDataPoint']
RETURN label, total
ORDER BY total DESC
```

## Phase 0-B: KG データからのトピック候補生成

照会結果から以下の4種のトピック候補を生成する。

### 候補種別 1: Knowledge Gap Topics（Q1, Q2 由来）

open Question / Insight(gap) を記事トピックに変換する。

```
入力: Question.content = "NVIDIAのデータセンター売上比率の最新データが不足"
出力: {
  "topic": "NVIDIA データセンター事業の最新動向と成長ドライバー分析",
  "category": "stock_analysis",
  "source_type": "kg_question",
  "kg_gap_score": 8,
  "rationale": "KGに未回答Question（priority: high）として記録。データギャップを埋める記事。"
}
```

### 候補種別 2: Underexplored Entity Topics（Q3 由来）

カバレッジが薄いが関連性の高いエンティティを深掘り記事に。

```
入力: Entity "Tesla" — fact: 2件, claim: 1件, relations: 8件
出力: {
  "topic": "Tesla 2026年の事業戦略と株価ドライバー",
  "category": "stock_analysis",
  "source_type": "kg_underexplored",
  "kg_gap_score": 6,
  "rationale": "KGで8件のリレーションがあるが、Fact/Claimが3件のみ。重要エンティティの深掘り。"
}
```

### 候補種別 3: Trending Entity Topics（Q4 由来）

ソースが急増しているエンティティをタイムリーな記事に。

```
入力: Entity "Bank of Japan" — recent: 12件, total: 15件, recency_ratio: 0.8
出力: {
  "topic": "日銀金融政策の最新動向と市場インパクト",
  "category": "macro_economy",
  "source_type": "kg_trending",
  "kg_gap_score": 4,
  "rationale": "直近30日でソースの80%が集中。注目度急上昇テーマ。"
}
```

### 候補種別 4: Controversy Topics（Q7 由来）

センチメントが拮抗しているエンティティを論争型記事に。

```
入力: Entity "S&P 500" — bullish: 5, bearish: 4, divergence: 1
出力: {
  "topic": "S&P 500 強気 vs 弱気: 両陣営の根拠を徹底比較",
  "category": "market_report",
  "source_type": "kg_controversy",
  "kg_gap_score": 7,
  "rationale": "KGにbullish 5件/bearish 4件のClaimが存在。意見拮抗で記事価値高。"
}
```

## Phase 0-C: KGトピック候補レポート

KG マイニング結果を以下の形式でユーザーに提示する（Phase 3 の topic-suggester への入力にもなる）。

```markdown
# KG トピック発掘レポート

## 照会日時: {datetime}
## KG 統計: Entity {n}件, Fact {n}件, Claim {n}件

## KG由来のトピック候補

### Knowledge Gap Topics（未回答Question由来）
| # | トピック案 | カテゴリ | KG Gap Score | 根拠 |
|---|----------|---------|-------------|------|
| 1 | {topic} | {cat} | {score} | {rationale} |

### Underexplored Entity Topics（カバレッジ薄エンティティ由来）
| # | トピック案 | カテゴリ | KG Gap Score | 根拠 |
|---|----------|---------|-------------|------|

### Trending Entity Topics（ソース急増由来）
| # | トピック案 | カテゴリ | KG Gap Score | 根拠 |
|---|----------|---------|-------------|------|

### Controversy Topics（センチメント拮抗由来）
| # | トピック案 | カテゴリ | KG Gap Score | 根拠 |
|---|----------|---------|-------------|------|

### 再評価候補（前回未決定提案）
| # | トピック | 前回スコア | 提案日 | カテゴリ |
|---|---------|----------|--------|---------|
```

## 関連ファイル

| リソース | パス |
|---------|------|
| KGスキーマ定義 | `data/config/knowledge-graph-schema.yaml` |
| スコアリングルーブリック | `references/scoring-rubric.md` |
| Neo4j保存マッピング | `references/neo4j-mapping.md` |
| article-research KGギャップ | `.claude/skills/investment-research/references/kg-gap-analysis.md` |
