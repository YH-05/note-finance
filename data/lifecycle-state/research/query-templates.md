# F-1: クエリテンプレートカタログ

**Instance**: research-neo4j (bolt://localhost:7688)
**Ontology Version**: research-3.0
**Generated**: 2026-03-23
**Graph Size**: 7,383 nodes / 42,961 relationships

---

## 概要

Phase A-1 で定義した5つのユースケースに対応するパラメータ化クエリテンプレート。
加えて、日常的に使用する Entity 検索、Source ドメイン分析、InstrumentClass 分析のテンプレートを含む。

### テンプレート一覧

| ID | ユースケース | パラメータ |
|----|-------------|-----------|
| T1 | トピック別関連ソース検索 | `$topic_name` |
| T2 | 企業間関連性探索 | `$entity_name`, `$max_depth` |
| T3 | 時系列データ追跡 | `$entity_name`, `$metric_name` |
| T4 | センチメント分析 | `$entity_name` |
| T5 | ギャップ分析 | `$min_fact_count` |
| T6 | Entity 検索（フルテキスト） | `$search_term` |
| T7 | Source ドメイン分析 | `$trust_level`, `$limit` |
| T8 | InstrumentClass 分析 | `$instrument_class` |

### 共通注意事項

- `WHERE NOT 'Memory' IN labels(n)` は全クエリに付与すること（Memory ノード除外）
- パラメータは `$param` 形式で記述（MCP 経由では文字列展開で代用）
- `LIMIT` はデフォルト値を記載するが、用途に応じて変更可

---

## T1: トピック別関連ソース検索

**ユースケース**: 特定トピックに関連する Source、Fact、Claim、Entity を一括取得

### T1-a: トピック名完全一致

```cypher
// パラメータ: $topic_name (例: "AI Investment")
// 戻り値: トピックに紐づく Source, Fact, Claim, Entity の一覧

MATCH (t:Topic)
WHERE t.name = $topic_name
AND NOT 'Memory' IN labels(t)

// Source (TAGGED)
OPTIONAL MATCH (s:Source)-[:TAGGED]->(t)

// Fact (ABOUT)
OPTIONAL MATCH (f:Fact)-[:ABOUT]->(t)
OPTIONAL MATCH (f)-[:RELATES_TO]->(fe:Entity)

// Claim (ABOUT)
OPTIONAL MATCH (c:Claim)-[:ABOUT]->(t)
OPTIONAL MATCH (c)-[:MENTIONS]->(ce:Entity)

RETURN t.name AS topic,
       t.topic_key AS topic_key,
       collect(DISTINCT {
         source_id: s.source_id,
         title: s.title,
         url: s.url,
         published_at: toString(s.published_at),
         source_type: s.source_type
       }) AS sources,
       collect(DISTINCT {
         fact_id: f.fact_id,
         content: left(f.content, 200),
         as_of_date: f.as_of_date,
         entities: collect(DISTINCT fe.name)
       }) AS facts,
       collect(DISTINCT {
         claim_id: c.claim_id,
         content: left(c.content, 200),
         sentiment: c.sentiment,
         entities: collect(DISTINCT ce.name)
       }) AS claims
```

### T1-b: トピック名あいまい検索

```cypher
// パラメータ: $search_term (例: "AI")
// フルテキストインデックス使用

CALL db.index.fulltext.queryNodes('research_topic_fulltext', $search_term)
YIELD node AS t, score
WHERE NOT 'Memory' IN labels(t)

WITH t, score ORDER BY score DESC LIMIT 10

OPTIONAL MATCH (s:Source)-[:TAGGED]->(t)
OPTIONAL MATCH (f:Fact)-[:ABOUT]->(t)
OPTIONAL MATCH (c:Claim)-[:ABOUT]->(t)

RETURN t.name AS topic,
       t.topic_key AS topic_key,
       score,
       count(DISTINCT s) AS source_count,
       count(DISTINCT f) AS fact_count,
       count(DISTINCT c) AS claim_count
ORDER BY score DESC
```

### T1-c: トピック ConceptCategory 横断検索

```cypher
// パラメータ: $category (例: "macro", "stock", "technology")
// ConceptCategory マッピング前の topic.category プロパティで検索

MATCH (t:Topic)
WHERE t.category = $category
AND NOT 'Memory' IN labels(t)

WITH t
OPTIONAL MATCH (s:Source)-[:TAGGED]->(t)

RETURN t.name AS topic,
       t.topic_key AS topic_key,
       count(DISTINCT s) AS source_count
ORDER BY source_count DESC
```

---

## T2: 企業間関連性探索

**ユースケース**: 特定エンティティから出発し、競合・子会社・顧客・パートナー等の関係を探索

### T2-a: 直接関係取得

```cypher
// パラメータ: $entity_name (例: "NVIDIA")
// 全ての Entity-Entity 直接リレーションを取得

MATCH (e:Entity)
WHERE e.name = $entity_name
AND NOT 'Memory' IN labels(e)

OPTIONAL MATCH (e)-[r]->(other:Entity)
WHERE type(r) IN [
  'COMPETES_WITH', 'SUBSIDIARY_OF', 'CUSTOMER_OF',
  'PARTNERS_WITH', 'INVESTED_IN', 'INFLUENCES',
  'GOVERNS', 'OPERATES_IN', 'SPUN_OFF_FROM',
  'LED_BY', 'CAUSES', 'CO_MENTIONED_WITH'
]

RETURN e.name AS entity,
       e.entity_type AS type,
       type(r) AS relationship,
       other.name AS related_entity,
       other.entity_type AS related_type
ORDER BY type(r), other.name
```

### T2-b: 双方向関係取得

```cypher
// パラメータ: $entity_name (例: "Toyota")
// 入出両方向の Entity-Entity リレーションを取得

MATCH (e:Entity {name: $entity_name})
WHERE NOT 'Memory' IN labels(e)

MATCH (e)-[r]-(other:Entity)
WHERE type(r) IN [
  'COMPETES_WITH', 'SUBSIDIARY_OF', 'CUSTOMER_OF',
  'PARTNERS_WITH', 'INVESTED_IN', 'INFLUENCES',
  'GOVERNS', 'OPERATES_IN', 'SPUN_OFF_FROM',
  'LED_BY', 'CAUSES', 'CO_MENTIONED_WITH'
]
AND NOT 'Memory' IN labels(other)

RETURN e.name AS entity,
       CASE WHEN startNode(r) = e THEN '-->' ELSE '<--' END AS direction,
       type(r) AS relationship,
       other.name AS related_entity,
       other.entity_type AS related_type
ORDER BY type(r), direction
```

### T2-c: マルチホップパス探索

```cypher
// パラメータ: $entity_name (例: "Apple"), $max_depth (例: 3)
// 可変長パスでN次関連まで探索

MATCH (start:Entity {name: $entity_name})
WHERE NOT 'Memory' IN labels(start)

MATCH path = (start)-[rels*1..3]-(end:Entity)
WHERE ALL(r IN rels WHERE type(r) IN [
  'COMPETES_WITH', 'SUBSIDIARY_OF', 'CUSTOMER_OF',
  'PARTNERS_WITH', 'INVESTED_IN', 'INFLUENCES',
  'CAUSES', 'CO_MENTIONED_WITH'
])
AND NOT 'Memory' IN labels(end)
AND start <> end

WITH path, end, length(path) AS depth,
     [r IN relationships(path) | type(r)] AS rel_types,
     [n IN nodes(path) | n.name] AS node_names
RETURN node_names AS path_nodes,
       rel_types AS path_rels,
       depth
ORDER BY depth, end.name
LIMIT 50
```

### T2-d: 2エンティティ間の最短パス

```cypher
// パラメータ: $entity_a (例: "Apple"), $entity_b (例: "Samsung")
// 2つのエンティティ間の最短経路を発見

MATCH (a:Entity {name: $entity_a}), (b:Entity {name: $entity_b})
WHERE NOT 'Memory' IN labels(a) AND NOT 'Memory' IN labels(b)

MATCH path = shortestPath((a)-[*..6]-(b))
WHERE ALL(n IN nodes(path) WHERE NOT 'Memory' IN labels(n))

RETURN [n IN nodes(path) | n.name] AS path_nodes,
       [r IN relationships(path) | type(r)] AS path_rels,
       length(path) AS distance
```

---

## T3: 時系列データ追跡

**ユースケース**: 特定エンティティの財務指標を FiscalPeriod 単位で時系列追跡

### T3-a: Entity + Metric 指定で FDP 取得

```cypher
// パラメータ: $entity_name (例: "Apple"), $metric_name (例: "Revenue")
// Entity に紐づく FinancialDataPoint を FiscalPeriod 順で取得

MATCH (e:Entity)-[:RELATES_TO]-(fdp:FinancialDataPoint)
WHERE e.name = $entity_name
AND NOT 'Memory' IN labels(e)

OPTIONAL MATCH (fdp)-[:FOR_METRIC]->(m:Metric)
WHERE m.name = $metric_name OR $metric_name IS NULL

OPTIONAL MATCH (fdp)-[:FOR_PERIOD]->(fp:FiscalPeriod)

RETURN e.name AS entity,
       m.name AS metric,
       fdp.value AS value,
       fp.year AS year,
       fp.quarter AS quarter,
       fp.type AS period_type,
       fdp.datapoint_id AS datapoint_id,
       toString(fdp.created_at) AS created_at
ORDER BY fp.year, fp.quarter
```

### T3-b: TREND チェーン走査

```cypher
// パラメータ: $entity_name (例: "Apple")
// TREND リレーションでリンクされた FDP チェーンを走査

MATCH (e:Entity)-[:RELATES_TO]-(fdp:FinancialDataPoint)
WHERE e.name = $entity_name
AND NOT 'Memory' IN labels(e)

OPTIONAL MATCH chain = (fdp)-[:TREND*1..8]->(next:FinancialDataPoint)
OPTIONAL MATCH (fdp)-[:FOR_PERIOD]->(fp:FiscalPeriod)
OPTIONAL MATCH (fdp)-[:FOR_METRIC]->(m:Metric)
OPTIONAL MATCH (next)-[:FOR_PERIOD]->(nfp:FiscalPeriod)

RETURN e.name AS entity,
       m.name AS metric,
       fdp.value AS start_value,
       fp.year AS start_year,
       fp.quarter AS start_quarter,
       collect({
         value: next.value,
         year: nfp.year,
         quarter: nfp.quarter
       }) AS trend_chain,
       length(chain) AS chain_length
ORDER BY m.name, fp.year, fp.quarter
```

### T3-c: FiscalPeriod 横断比較（同一 Metric 複数 Entity）

```cypher
// パラメータ: $metric_name (例: "Revenue"), $period_year (例: 2025)
// 同一指標・同一年度の複数エンティティ比較

MATCH (fdp:FinancialDataPoint)-[:FOR_METRIC]->(m:Metric {name: $metric_name})
MATCH (fdp)-[:FOR_PERIOD]->(fp:FiscalPeriod {year: $period_year})
MATCH (fdp)-[:RELATES_TO]-(e:Entity)
WHERE NOT 'Memory' IN labels(e)

OPTIONAL MATCH (fdp)-[:IN_UNIT]->(u:UnitOfMeasure)

RETURN e.name AS entity,
       e.entity_type AS type,
       fdp.value AS value,
       u.symbol AS unit,
       fp.year AS year,
       fp.quarter AS quarter
ORDER BY fdp.value DESC
```

### T3-d: 直近 Source からの FDP 取得

```cypher
// パラメータ: $days_ago (例: 30)
// 直近N日以内に投入された Source に紐づく FDP を取得

MATCH (s:Source)-[:HAS_DATAPOINT]->(fdp:FinancialDataPoint)
WHERE s.collected_at >= datetime() - duration({days: $days_ago})
AND NOT 'Memory' IN labels(s)

OPTIONAL MATCH (fdp)-[:RELATES_TO]-(e:Entity)
OPTIONAL MATCH (fdp)-[:FOR_METRIC]->(m:Metric)
OPTIONAL MATCH (fdp)-[:FOR_PERIOD]->(fp:FiscalPeriod)

RETURN s.title AS source_title,
       s.url AS source_url,
       e.name AS entity,
       m.name AS metric,
       fdp.value AS value,
       fp.year AS year,
       fp.quarter AS quarter
ORDER BY s.collected_at DESC
```

---

## T4: センチメント分析

**ユースケース**: 特定エンティティに対する Claim のセンチメント集計、Stance 評価、ClaimType 方向性分析

### T4-a: Entity 別 Claim センチメント集計

```cypher
// パラメータ: $entity_name (例: "Apple")
// Entity に言及する Claim のセンチメント分布を集計

MATCH (c:Claim)-[:MENTIONS]->(e:Entity {name: $entity_name})
WHERE NOT 'Memory' IN labels(e)

RETURN e.name AS entity,
       c.sentiment AS sentiment,
       count(c) AS claim_count,
       avg(c.confidence) AS avg_confidence,
       avg(c.magnitude) AS avg_magnitude,
       collect(DISTINCT left(c.content, 100))[..3] AS sample_claims
ORDER BY claim_count DESC
```

### T4-b: Entity 別 Stance 集約

```cypher
// パラメータ: $entity_name (例: "Apple")
// Entity に対する Stance（アナリスト判断）を集約

MATCH (st:Stance)-[:ON_ENTITY]->(e:Entity {name: $entity_name})
WHERE NOT 'Memory' IN labels(e)

OPTIONAL MATCH (s:Source)-[:HOLDS_STANCE]->(st)
OPTIONAL MATCH (s)-[:AUTHORED_BY]->(a:Author)

RETURN e.name AS entity,
       st.sentiment AS stance_sentiment,
       st.rating AS rating,
       st.target_price AS target_price,
       st.as_of_date AS as_of_date,
       st.note AS note,
       s.title AS source_title,
       a.name AS analyst
ORDER BY st.as_of_date DESC
```

### T4-c: ClaimType 方向性分析

```cypher
// パラメータ: $entity_name (例: "S&P 500")
// Entity に言及する Claim の ClaimType (direction) 分布を分析

MATCH (c:Claim)-[:MENTIONS]->(e:Entity {name: $entity_name})
WHERE NOT 'Memory' IN labels(e)

WITH e, c
// ClaimType ハブノード未実装のため claim_type プロパティで代用
RETURN e.name AS entity,
       c.claim_type AS claim_type,
       CASE c.claim_type
         WHEN 'bullish' THEN 'positive'
         WHEN 'earnings_beat' THEN 'positive'
         WHEN 'bearish' THEN 'negative'
         WHEN 'risk_event' THEN 'negative'
         WHEN 'policy_hawkish' THEN 'negative'
         WHEN 'political_risk' THEN 'negative'
         ELSE 'neutral'
       END AS direction,
       count(c) AS claim_count,
       collect(DISTINCT left(c.content, 100))[..2] AS samples
ORDER BY claim_count DESC
```

### T4-d: 総合センチメントスコア算出

```cypher
// パラメータ: $entity_name (例: "NVIDIA")
// Claim + Stance を統合したセンチメントスコアを算出

MATCH (e:Entity {name: $entity_name})
WHERE NOT 'Memory' IN labels(e)

// Claim 集計
OPTIONAL MATCH (c:Claim)-[:MENTIONS]->(e)
WITH e,
     count(c) AS total_claims,
     sum(CASE WHEN c.sentiment = 'positive' THEN 1 ELSE 0 END) AS positive_claims,
     sum(CASE WHEN c.sentiment = 'negative' THEN 1 ELSE 0 END) AS negative_claims,
     sum(CASE WHEN c.sentiment = 'neutral' THEN 1 ELSE 0 END) AS neutral_claims

// Stance 集計
OPTIONAL MATCH (st:Stance)-[:ON_ENTITY]->(e)
WITH e, total_claims, positive_claims, negative_claims, neutral_claims,
     count(st) AS total_stances,
     sum(CASE WHEN st.sentiment = 'positive' OR st.sentiment = 'bullish' THEN 1 ELSE 0 END) AS positive_stances,
     sum(CASE WHEN st.sentiment = 'negative' OR st.sentiment = 'bearish' THEN 1 ELSE 0 END) AS negative_stances

RETURN e.name AS entity,
       total_claims,
       positive_claims,
       negative_claims,
       neutral_claims,
       CASE WHEN total_claims > 0
         THEN toFloat(positive_claims - negative_claims) / total_claims
         ELSE 0.0
       END AS claim_sentiment_score,
       total_stances,
       positive_stances,
       negative_stances,
       CASE WHEN total_stances > 0
         THEN toFloat(positive_stances - negative_stances) / total_stances
         ELSE 0.0
       END AS stance_sentiment_score
```

---

## T5: ギャップ分析

**ユースケース**: 情報カバレッジが不足している Entity / Topic を特定

### T5-a: 低カバレッジ Entity 検出

```cypher
// パラメータ: $min_fact_count (例: 2)
// Fact 接続数が閾値未満の Entity を検出

MATCH (e:Entity)
WHERE NOT 'Memory' IN labels(e)

OPTIONAL MATCH (f:Fact)-[:RELATES_TO]->(e)
OPTIONAL MATCH (c:Claim)-[:MENTIONS]->(e)
OPTIONAL MATCH (fdp:FinancialDataPoint)-[:RELATES_TO]-(e)
OPTIONAL MATCH (e)-[rel]-()

WITH e,
     count(DISTINCT f) AS fact_count,
     count(DISTINCT c) AS claim_count,
     count(DISTINCT fdp) AS fdp_count,
     count(DISTINCT rel) AS total_rels

WHERE fact_count < $min_fact_count

RETURN e.name AS entity,
       e.entity_type AS type,
       fact_count,
       claim_count,
       fdp_count,
       total_rels,
       CASE
         WHEN total_rels = 0 THEN 'orphan'
         WHEN fact_count = 0 AND claim_count = 0 THEN 'no_content'
         ELSE 'low_coverage'
       END AS gap_type
ORDER BY total_rels ASC, e.name
LIMIT 50
```

### T5-b: 孤立 Entity 一覧（リレーションゼロ）

```cypher
// パラメータ: なし
// リレーションが一切ない完全孤立 Entity を列挙

MATCH (e:Entity)
WHERE NOT 'Memory' IN labels(e)
AND NOT (e)-[]-()

RETURN e.name AS entity,
       e.entity_key AS entity_key,
       e.entity_type AS type
ORDER BY e.entity_type, e.name
```

### T5-c: FDP 未接続 Entity（財務データギャップ）

```cypher
// パラメータ: $entity_type (例: "company")
// 特定タイプの Entity で FDP が存在しないものを検出

MATCH (e:Entity)
WHERE e.entity_type = $entity_type
AND NOT 'Memory' IN labels(e)
AND NOT (e)<-[:RELATES_TO]-(:FinancialDataPoint)

OPTIONAL MATCH (f:Fact)-[:RELATES_TO]->(e)
OPTIONAL MATCH (c:Claim)-[:MENTIONS]->(e)

RETURN e.name AS entity,
       e.entity_key AS entity_key,
       count(DISTINCT f) AS fact_count,
       count(DISTINCT c) AS claim_count
ORDER BY fact_count DESC
```

### T5-d: Topic カバレッジ不足検出

```cypher
// パラメータ: $min_source_count (例: 3)
// Source 数が閾値未満の Topic を検出

MATCH (t:Topic)
WHERE NOT 'Memory' IN labels(t)

OPTIONAL MATCH (s:Source)-[:TAGGED]->(t)
OPTIONAL MATCH (f:Fact)-[:ABOUT]->(t)
OPTIONAL MATCH (c:Claim)-[:ABOUT]->(t)

WITH t,
     count(DISTINCT s) AS source_count,
     count(DISTINCT f) AS fact_count,
     count(DISTINCT c) AS claim_count

WHERE source_count < $min_source_count

RETURN t.name AS topic,
       t.topic_key AS topic_key,
       t.category AS category,
       source_count,
       fact_count,
       claim_count
ORDER BY source_count ASC, fact_count ASC
```

### T5-e: リレーション欠損パターン検出

```cypher
// パラメータ: なし
// 期待されるリレーションが欠損しているノードを種類別にカウント

// Fact: STATES_FACT 欠損
MATCH (f:Fact) WHERE NOT (f)<-[:STATES_FACT]-(:Source)
WITH count(f) AS orphan_facts

// Claim: MAKES_CLAIM 欠損
MATCH (c:Claim) WHERE NOT (c)<-[:MAKES_CLAIM]-(:Source)
WITH orphan_facts, count(c) AS orphan_claims

// FDP: FOR_PERIOD 欠損
MATCH (fdp:FinancialDataPoint) WHERE NOT (fdp)-[:FOR_PERIOD]->(:FiscalPeriod)
WITH orphan_facts, orphan_claims, count(fdp) AS fdp_no_period

// FDP: FOR_METRIC 欠損
MATCH (fdp:FinancialDataPoint) WHERE NOT (fdp)-[:FOR_METRIC]->(:Metric)
WITH orphan_facts, orphan_claims, fdp_no_period, count(fdp) AS fdp_no_metric

// Source: TAGGED 欠損
MATCH (s:Source) WHERE NOT (s)-[:TAGGED]->(:Topic)
AND NOT 'Memory' IN labels(s)

RETURN orphan_facts AS facts_no_source,
       orphan_claims AS claims_no_source,
       fdp_no_period,
       fdp_no_metric,
       count(s) AS sources_no_topic
```

---

## T6: Entity 検索（フルテキスト + Alias フォールバック）

**ユースケース**: Entity を名前で柔軟に検索し、関連情報を取得

### T6-a: フルテキスト検索（プライマリ）

```cypher
// パラメータ: $search_term (例: "nvidia", "トヨタ", "S&P")
// research_entity_fulltext インデックスを使用

CALL db.index.fulltext.queryNodes('research_entity_fulltext', $search_term)
YIELD node AS e, score
WHERE NOT 'Memory' IN labels(e)

OPTIONAL MATCH (f:Fact)-[:RELATES_TO]->(e)
OPTIONAL MATCH (c:Claim)-[:MENTIONS]->(e)
OPTIONAL MATCH (e)-[:IN_SECTOR]->(sec:Sector)

RETURN e.name AS entity,
       e.entity_key AS entity_key,
       e.entity_type AS type,
       score,
       sec.name AS sector,
       count(DISTINCT f) AS fact_count,
       count(DISTINCT c) AS claim_count
ORDER BY score DESC
LIMIT 20
```

### T6-b: Alias フォールバック検索

```cypher
// パラメータ: $search_term (例: "MSFT", "日銀", "BOJ")
// Alias ノード経由で正規 Entity を検索（ハブノード未実装時は name プロパティ直接検索）

// Step 1: フルテキストで Entity を検索
CALL db.index.fulltext.queryNodes('research_entity_fulltext', $search_term)
YIELD node AS e, score
WHERE NOT 'Memory' IN labels(e)
RETURN e.name AS entity, e.entity_key AS entity_key, score, 'direct' AS match_type
ORDER BY score DESC
LIMIT 10

UNION

// Step 2: Alias 経由で検索（Alias ノード実装後）
// CALL db.index.fulltext.queryNodes('research_alias_fulltext', $search_term)
// YIELD node AS alias, score
// MATCH (alias)-[:ALIAS_OF]->(e:Entity)
// RETURN e.name AS entity, e.entity_key AS entity_key, score, 'alias' AS match_type
// ORDER BY score DESC
// LIMIT 10
```

### T6-c: entity_key 直接指定

```cypher
// パラメータ: $entity_key (例: "Apple::company")
// entity_key による正確な検索

MATCH (e:Entity {entity_key: $entity_key})
WHERE NOT 'Memory' IN labels(e)

OPTIONAL MATCH (s:Source)-[:STATES_FACT|MAKES_CLAIM]->()-[:RELATES_TO|MENTIONS]->(e)
OPTIONAL MATCH (e)-[:IN_SECTOR]->(sec:Sector)
OPTIONAL MATCH (e)-[er]-(other:Entity)
WHERE type(er) IN ['COMPETES_WITH', 'SUBSIDIARY_OF', 'CUSTOMER_OF', 'PARTNERS_WITH', 'INVESTED_IN']

RETURN e AS entity_node,
       sec.name AS sector,
       count(DISTINCT s) AS source_count,
       collect(DISTINCT {rel: type(er), entity: other.name})[..10] AS entity_relations
```

---

## T7: Source ドメイン分析

**ユースケース**: Source を Domain / TrustLevel で集約し、情報源の品質分布を把握

### T7-a: authority_level 別集計（ハブノード未実装時）

```cypher
// パラメータ: $trust_level (例: "official", NULL で全件)
// authority_level プロパティベースの集計

MATCH (s:Source)
WHERE NOT 'Memory' IN labels(s)
AND ($trust_level IS NULL OR s.authority_level = $trust_level)

RETURN s.authority_level AS trust_level,
       s.source_type AS source_type,
       count(s) AS source_count,
       count(CASE WHEN s.url IS NOT NULL THEN 1 END) AS with_url,
       min(toString(s.published_at)) AS earliest,
       max(toString(s.published_at)) AS latest
ORDER BY source_count DESC
```

### T7-b: domain プロパティ別集計

```cypher
// パラメータ: $limit (例: 20)
// Source.domain プロパティでドメイン別の Source 数を集計

MATCH (s:Source)
WHERE NOT 'Memory' IN labels(s)
AND s.domain IS NOT NULL

WITH s.domain AS domain,
     count(s) AS source_count,
     collect(DISTINCT s.source_type) AS source_types,
     collect(DISTINCT s.authority_level) AS trust_levels

RETURN domain,
       source_count,
       source_types,
       trust_levels
ORDER BY source_count DESC
LIMIT $limit
```

### T7-c: Domain ハブノード経由集計（Phase B 実行後）

```cypher
// パラメータ: なし
// Domain ハブノード実装後に使用

MATCH (s:Source)-[:FROM_DOMAIN]->(d:Domain)
OPTIONAL MATCH (s)-[:RATED_AS]->(tl:TrustLevel)

RETURN d.name AS domain,
       d.base_url AS base_url,
       tl.name AS trust_level,
       tl.rank AS trust_rank,
       count(s) AS source_count
ORDER BY source_count DESC
```

### T7-d: Pipeline 別データ投入量

```cypher
// パラメータ: なし
// command_source プロパティでパイプライン別の投入量を集計

MATCH (s:Source)
WHERE NOT 'Memory' IN labels(s)
AND s.command_source IS NOT NULL

RETURN s.command_source AS pipeline,
       count(s) AS source_count,
       min(toString(s.collected_at)) AS first_ingested,
       max(toString(s.collected_at)) AS last_ingested
ORDER BY source_count DESC
```

---

## T8: InstrumentClass 分析

**ユースケース**: 金融商品種類階層で Entity をフィルタリング

### T8-a: entity_type ベース検索（ハブノード未実装時）

```cypher
// パラメータ: $instrument_type (例: "instrument", "etf", "fund")
// entity_type プロパティで金融商品エンティティを検索

MATCH (e:Entity)
WHERE e.entity_type IN ['instrument', 'etf', 'currency', 'currency_pair', 'fund', 'bond', 'asset']
AND NOT 'Memory' IN labels(e)
AND ($instrument_type IS NULL OR e.entity_type = $instrument_type)

OPTIONAL MATCH (f:Fact)-[:RELATES_TO]->(e)
OPTIONAL MATCH (fdp:FinancialDataPoint)-[:RELATES_TO]-(e)

RETURN e.name AS entity,
       e.entity_key AS entity_key,
       e.entity_type AS instrument_type,
       count(DISTINCT f) AS fact_count,
       count(DISTINCT fdp) AS fdp_count
ORDER BY fact_count DESC
```

### T8-b: InstrumentClass 階層検索（Phase B 実行後）

```cypher
// パラメータ: $class_name (例: "equity")
// InstrumentClass L1 からの階層展開

MATCH (ic:InstrumentClass {name: $class_name})

// L1 直下の Entity
OPTIONAL MATCH (e:Entity)-[:IS_INSTRUMENT_CLASS]->(ic)
WHERE NOT 'Memory' IN labels(e)

// L2 子クラス経由の Entity
OPTIONAL MATCH (child:InstrumentClass)-[:PARENT_CLASS]->(ic)
OPTIONAL MATCH (e2:Entity)-[:IS_INSTRUMENT_CLASS]->(child)
WHERE NOT 'Memory' IN labels(e2)

RETURN ic.name AS parent_class,
       ic.name_ja AS parent_class_ja,
       collect(DISTINCT {name: e.name, type: e.entity_type}) AS direct_entities,
       collect(DISTINCT {
         child_class: child.name,
         child_class_ja: child.name_ja,
         entities: collect(DISTINCT e2.name)
       }) AS child_class_entities
```

### T8-c: Identifier（ティッカー）検索

```cypher
// パラメータ: $ticker (例: "AAPL")
// ticker プロパティベース検索（Identifier ハブノード未実装時）

MATCH (e:Entity)
WHERE e.ticker = $ticker
AND NOT 'Memory' IN labels(e)

OPTIONAL MATCH (e)-[:IN_SECTOR]->(sec:Sector)
OPTIONAL MATCH (f:Fact)-[:RELATES_TO]->(e)
OPTIONAL MATCH (c:Claim)-[:MENTIONS]->(e)
OPTIONAL MATCH (fdp:FinancialDataPoint)-[:RELATES_TO]-(e)

RETURN e.name AS entity,
       e.entity_key AS entity_key,
       e.entity_type AS type,
       e.ticker AS ticker,
       sec.name AS sector,
       count(DISTINCT f) AS fact_count,
       count(DISTINCT c) AS claim_count,
       count(DISTINCT fdp) AS fdp_count
```

---

## 付録: よく使うフィルタパターン

### 時間フィルタ

```cypher
// 直近N日
WHERE s.collected_at >= datetime() - duration({days: $days})

// 日付範囲
WHERE s.published_at >= date($start_date) AND s.published_at <= date($end_date)

// 月次
WHERE s.published_at.year = $year AND s.published_at.month = $month
```

### entity_type フィルタ

```cypher
// 企業のみ
WHERE e.entity_type IN ['company', 'fintech', 'subsidiary']

// 正規化後のカノニカルタイプ
WHERE e.entity_type = 'company'
```

### source_type フィルタ

```cypher
// 高信頼ソースのみ
WHERE s.authority_level IN ['official', 'academic', 'company']

// ニュース系のみ
WHERE s.source_type = 'news'
```

### Memory 除外（全クエリ必須）

```cypher
WHERE NOT 'Memory' IN labels(n)
```
