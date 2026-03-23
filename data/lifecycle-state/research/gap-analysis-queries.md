# research-neo4j ギャップ分析クエリ集 — Phase E-2

**生成日**: 2026-03-23
**インスタンス**: research-neo4j (bolt://localhost:7688)
**品質ベースライン**: Grade B (83.5)
**オントロジー**: research-3.0

---

## 目次

1. [G1: Entity 孤立ノード分析（254件、25.1%）](#g1-entity-孤立ノード分析)
2. [G2: FOR_METRIC ギャップ分析（5.1% カバレッジ）](#g2-for_metric-ギャップ分析)
3. [G3: Source TAGGED ギャップ分析（247件未分類）](#g3-source-tagged-ギャップ分析)
4. [G4: Entity タイプ正規化（127件統合対象）](#g4-entity-タイプ正規化)
5. [G5: Source タイプ正規化（46件統合対象）](#g5-source-タイプ正規化)
6. [G6: v3.0 分類ハブノード実体化](#g6-v30-分類ハブノード実体化)
7. [G7: Topic カテゴリマッピング補完](#g7-topic-カテゴリマッピング補完)
8. [G8: Entity プロパティ充填](#g8-entity-プロパティ充填)
9. [G9: Source プロパティ充填](#g9-source-プロパティ充填)
10. [G10: 重複ノードマージ](#g10-重複ノードマージ)

---

## G1: Entity 孤立ノード分析

### 現状

254件の Entity（全体の 25.1%）がリレーションゼロの完全孤立状態。
Phase D 品質スコアへの影響: D-3 Score を 6% 以上押し下げている。

### G1-1: 診断クエリ — 孤立 Entity の一覧（タイプ別集計）

```cypher
// 孤立 Entity をタイプ別に集計し、優先度を判定する
MATCH (e:Entity)
WHERE NOT (e)--()
  AND NOT 'Memory' IN labels(e)
RETURN e.entity_type AS entity_type,
       count(e) AS orphan_count,
       collect(e.name)[..5] AS examples
ORDER BY orphan_count DESC
```

### G1-2: 診断クエリ — 孤立 Entity の詳細リスト（接続候補付き）

```cypher
// 孤立 Entity に対し、名前でフルテキスト検索して接続候補の Fact/Claim を探す
MATCH (e:Entity)
WHERE NOT (e)--()
  AND NOT 'Memory' IN labels(e)
WITH e
CALL db.index.fulltext.queryNodes('research_fact_fulltext', e.name)
YIELD node AS fact, score
WHERE score > 1.0
RETURN e.entity_key,
       e.name,
       e.entity_type,
       collect({fact_id: fact.fact_id, score: score, content: left(fact.content, 80)})[..3] AS candidate_facts
ORDER BY size(collect({fact_id: fact.fact_id, score: score, content: left(fact.content, 80)})) DESC
LIMIT 50
```

### G1-3: 診断クエリ — 孤立 Entity と Source.title の照合

```cypher
// 孤立 Entity の名前が Source.title に含まれるケースを検出
MATCH (e:Entity)
WHERE NOT (e)--()
  AND NOT 'Memory' IN labels(e)
WITH e
CALL db.index.fulltext.queryNodes('research_source_fulltext', e.name)
YIELD node AS src, score
WHERE score > 1.0
RETURN e.entity_key,
       e.name,
       e.entity_type,
       collect({source_id: src.source_id, title: src.title, score: score})[..3] AS candidate_sources
LIMIT 50
```

### G1-4: 修正クエリ — Fact.content に名前が含まれる場合に MENTIONS を作成

```cypher
// 孤立 Entity → Fact.content 内のテキストマッチで MENTIONS リレーションを作成
// 注意: emit_graph_queue.py 経由で実行するのが原則。
// このクエリは診断後の緊急修復用。実行前にユーザー承認が必要。
MATCH (e:Entity)
WHERE NOT (e)--()
  AND NOT 'Memory' IN labels(e)
WITH e
CALL db.index.fulltext.queryNodes('research_fact_fulltext', e.name)
YIELD node AS fact, score
WHERE score > 2.0
WITH e, fact, score
ORDER BY score DESC
WITH e, collect(fact)[..5] AS top_facts
UNWIND top_facts AS fact
MERGE (fact)-[:MENTIONS]->(e)
RETURN e.entity_key, e.name, count(*) AS links_created
```

### G1-5: 修正クエリ — Claim.content に名前が含まれる場合に MENTIONS を作成

```cypher
MATCH (e:Entity)
WHERE NOT (e)--()
  AND NOT 'Memory' IN labels(e)
WITH e
CALL db.index.fulltext.queryNodes('research_claim_fulltext', e.name)
YIELD node AS claim, score
WHERE score > 2.0
WITH e, claim, score
ORDER BY score DESC
WITH e, collect(claim)[..5] AS top_claims
UNWIND top_claims AS claim
MERGE (claim)-[:MENTIONS]->(e)
RETURN e.entity_key, e.name, count(*) AS links_created
```

---

## G2: FOR_METRIC ギャップ分析

### 現状

430件の FinancialDataPoint のうち、FOR_METRIC リレーションを持つのは 22件（5.1%）のみ。
55件の Metric ノードが存在するが、FDP.metric_name との紐付けがほぼ未実施。

### G2-1: 診断クエリ — FDP の metric_name 分布

```cypher
// FDP.metric_name の分布を確認し、Metric ノードとのマッチング候補を特定
MATCH (fdp:FinancialDataPoint)
WHERE fdp.metric_name IS NOT NULL
RETURN fdp.metric_name AS metric_name,
       count(fdp) AS fdp_count
ORDER BY fdp_count DESC
LIMIT 30
```

### G2-2: 診断クエリ — 既存 Metric ノードの一覧

```cypher
// 既存 Metric ノードの一覧と、各 Metric に既に FOR_METRIC 接続されている FDP 数
MATCH (m:Metric)
OPTIONAL MATCH (fdp:FinancialDataPoint)-[:FOR_METRIC]->(m)
RETURN m.metric_id,
       m.name,
       count(fdp) AS linked_fdp_count
ORDER BY linked_fdp_count DESC
```

### G2-3: 診断クエリ — FDP.metric_name と Metric.name の照合候補

```cypher
// FDP.metric_name を Metric.name と照合し、マッチング候補を提示
MATCH (fdp:FinancialDataPoint)
WHERE fdp.metric_name IS NOT NULL
  AND NOT (fdp)-[:FOR_METRIC]->()
WITH fdp.metric_name AS metric_name, collect(fdp.datapoint_id) AS fdp_ids, count(*) AS cnt
MATCH (m:Metric)
WHERE toLower(m.name) = toLower(metric_name)
   OR toLower(m.name) CONTAINS toLower(metric_name)
   OR toLower(metric_name) CONTAINS toLower(m.name)
RETURN metric_name,
       cnt AS unlinked_fdp_count,
       m.metric_id,
       m.name AS matched_metric_name,
       fdp_ids[..5] AS sample_fdp_ids
ORDER BY cnt DESC
```

### G2-4: 修正クエリ — 完全一致の FDP → Metric を FOR_METRIC で接続

```cypher
// FDP.metric_name と Metric.name が完全一致（大文字小文字無視）のケースを接続
MATCH (fdp:FinancialDataPoint)
WHERE fdp.metric_name IS NOT NULL
  AND NOT (fdp)-[:FOR_METRIC]->()
WITH fdp
MATCH (m:Metric)
WHERE toLower(m.name) = toLower(fdp.metric_name)
MERGE (fdp)-[:FOR_METRIC]->(m)
RETURN count(*) AS links_created
```

### G2-5: 修正クエリ — metric_name から新規 Metric ノードを作成して接続

```cypher
// 既存 Metric にマッチしない metric_name から新規 Metric を作成
// 注意: 実行前に G2-3 で候補を確認し、手動マッピングを優先すること
MATCH (fdp:FinancialDataPoint)
WHERE fdp.metric_name IS NOT NULL
  AND NOT (fdp)-[:FOR_METRIC]->()
WITH fdp.metric_name AS metric_name, collect(fdp) AS fdps
WHERE NOT EXISTS {
  MATCH (m:Metric)
  WHERE toLower(m.name) = toLower(metric_name)
}
WITH metric_name, fdps,
     toLower(replace(metric_name, ' ', '_')) AS new_metric_id
MERGE (m:Metric {metric_id: new_metric_id})
ON CREATE SET m.name = metric_name
WITH m, fdps
UNWIND fdps AS fdp
MERGE (fdp)-[:FOR_METRIC]->(m)
RETURN m.metric_id, m.name, count(*) AS links_created
ORDER BY links_created DESC
```

---

## G3: Source TAGGED ギャップ分析

### 現状

1,709件の Source のうち 247件（14.5%）が TAGGED リレーションを持たない。
トピック分類されていないソースはグラフの発見性を低下させる。

### G3-1: 診断クエリ — 未分類 Source の一覧

```cypher
// TAGGED リレーションがない Source を source_type 別に集計
MATCH (s:Source)
WHERE NOT (s)-[:TAGGED]->()
RETURN s.source_type AS source_type,
       count(s) AS untagged_count,
       collect(s.title)[..3] AS sample_titles
ORDER BY untagged_count DESC
```

### G3-2: 診断クエリ — 未分類 Source に接続された Fact/Claim の Topic を逆引き

```cypher
// 未分類 Source → Fact/Claim → ABOUT → Topic を逆引きして候補 Topic を提示
MATCH (s:Source)
WHERE NOT (s)-[:TAGGED]->()
OPTIONAL MATCH (s)-[:STATES_FACT]->(f:Fact)-[:ABOUT]->(t:Topic)
OPTIONAL MATCH (s)-[:MAKES_CLAIM]->(c:Claim)-[:ABOUT]->(t2:Topic)
WITH s,
     collect(DISTINCT t.topic_key) + collect(DISTINCT t2.topic_key) AS candidate_topics
WHERE size(candidate_topics) > 0
RETURN s.source_id,
       s.title,
       candidate_topics[..5] AS suggested_topics
LIMIT 30
```

### G3-3: 診断クエリ — 未分類 Source のタイトルからキーワードベースでトピック推定

```cypher
// Source.title をフルテキスト検索で Topic と照合
MATCH (s:Source)
WHERE NOT (s)-[:TAGGED]->()
  AND s.title IS NOT NULL
WITH s, split(s.title, ' ') AS words
WITH s, [w IN words WHERE size(w) > 3] AS keywords
WITH s, keywords[..3] AS search_terms
WHERE size(search_terms) > 0
WITH s, reduce(q = '', w IN search_terms | q + ' ' + w) AS search_query
CALL db.index.fulltext.queryNodes('research_topic_fulltext', trim(search_query))
YIELD node AS topic, score
WHERE score > 0.5
RETURN s.source_id,
       s.title,
       collect({topic_key: topic.topic_key, name: topic.name, score: score})[..3] AS candidate_topics
LIMIT 30
```

### G3-4: 修正クエリ — Fact/Claim 経由の Topic を Source に TAGGED として転写

```cypher
// Source の子コンテンツが持つ Topic を Source 自体にも TAGGED する
MATCH (s:Source)
WHERE NOT (s)-[:TAGGED]->()
WITH s
OPTIONAL MATCH (s)-[:STATES_FACT]->(f:Fact)-[:ABOUT]->(t:Topic)
WITH s, collect(DISTINCT t) AS fact_topics
OPTIONAL MATCH (s)-[:MAKES_CLAIM]->(c:Claim)-[:ABOUT]->(t2:Topic)
WITH s, fact_topics + collect(DISTINCT t2) AS all_topics
UNWIND all_topics AS topic
WITH DISTINCT s, topic
WHERE topic IS NOT NULL
MERGE (s)-[:TAGGED]->(topic)
RETURN count(*) AS tagged_created
```

---

## G4: Entity タイプ正規化

### 現状

127件の Entity（12.5%）が非正規の entity_type を使用。
24件の `macro` タイプは canonical 14種に含まれず、マッピングが必要。

### G4-1: 診断クエリ — 非正規 entity_type の一覧

```cypher
// 非正規 entity_type とその件数・サンプルを表示
MATCH (e:Entity)
WHERE NOT e.entity_type IN [
  'company', 'technology', 'organization', 'person', 'index',
  'indicator', 'instrument', 'commodity', 'country', 'sector',
  'concept', 'regulation', 'broker', 'product'
]
RETURN e.entity_type AS non_canonical_type,
       count(e) AS count,
       collect(e.name)[..5] AS examples
ORDER BY count DESC
```

### G4-2: 修正クエリ — consolidates ルールに基づくタイプ統合

```cypher
// central_bank → organization
MATCH (e:Entity)
WHERE e.entity_type = 'central_bank'
SET e.entity_type = 'organization',
    e.entity_key = e.name + '::organization'
RETURN count(e) AS updated

// government, government_agency, institution, exchange → organization
MATCH (e:Entity)
WHERE e.entity_type IN ['government', 'government_agency', 'institution', 'exchange']
SET e.entity_type = 'organization',
    e.entity_key = e.name + '::organization'
RETURN e.name, e.entity_key AS new_key
```

```cypher
// fintech, subsidiary, fintech_holding, digital_bank, it_services → company
MATCH (e:Entity)
WHERE e.entity_type IN ['fintech', 'subsidiary', 'fintech_holding', 'digital_bank', 'it_services']
SET e.entity_type = 'company',
    e.entity_key = e.name + '::company'
RETURN e.name, e.entity_key AS new_key
```

```cypher
// model, method, theme, article_proposal, event → concept
MATCH (e:Entity)
WHERE e.entity_type IN ['model', 'method', 'theme', 'article_proposal', 'event']
SET e.entity_type = 'concept',
    e.entity_key = e.name + '::concept'
RETURN e.name, e.entity_key AS new_key
```

```cypher
// metric → indicator
MATCH (e:Entity)
WHERE e.entity_type = 'metric'
SET e.entity_type = 'indicator',
    e.entity_key = e.name + '::indicator'
RETURN e.name, e.entity_key AS new_key
```

```cypher
// etf, currency, currency_pair, fund, bond, asset → instrument
MATCH (e:Entity)
WHERE e.entity_type IN ['etf', 'currency', 'currency_pair', 'fund', 'bond', 'asset']
SET e.entity_type = 'instrument',
    e.entity_key = e.name + '::instrument'
RETURN e.name, e.entity_key AS new_key
```

```cypher
// system → technology
MATCH (e:Entity)
WHERE e.entity_type = 'system'
SET e.entity_type = 'technology',
    e.entity_key = e.name + '::technology'
RETURN e.name, e.entity_key AS new_key
```

```cypher
// region → country
MATCH (e:Entity)
WHERE e.entity_type = 'region'
SET e.entity_type = 'country',
    e.entity_key = e.name + '::country'
RETURN e.name, e.entity_key AS new_key
```

```cypher
// market → sector
MATCH (e:Entity)
WHERE e.entity_type = 'market'
SET e.entity_type = 'sector',
    e.entity_key = e.name + '::sector'
RETURN e.name, e.entity_key AS new_key
```

```cypher
// dataset, data_center → product
MATCH (e:Entity)
WHERE e.entity_type IN ['dataset', 'data_center']
SET e.entity_type = 'product',
    e.entity_key = e.name + '::product'
RETURN e.name, e.entity_key AS new_key
```

### G4-3: 修正クエリ — macro タイプのマッピング（手動確認推奨）

```cypher
// macro タイプの Entity を一覧表示し、indicator or concept への分類を判断
MATCH (e:Entity)
WHERE e.entity_type = 'macro'
RETURN e.entity_key,
       e.name,
       CASE
         WHEN e.name CONTAINS 'Rate' OR e.name CONTAINS 'GDP'
              OR e.name CONTAINS 'CPI' OR e.name CONTAINS 'Inflation'
              OR e.name CONTAINS 'Unemployment'
         THEN 'indicator'
         ELSE 'concept'
       END AS suggested_type
ORDER BY e.name
```

---

## G5: Source タイプ正規化

### 現状

46件の Source（2.7%）が非正規の source_type を使用。

### G5-1: 診断クエリ — 非正規 source_type の一覧

```cypher
MATCH (s:Source)
WHERE NOT s.source_type IN [
  'news', 'blog', 'web', 'pdf', 'analysis', 'company_filing',
  'data', 'academic', 'presentation', 'financial_statement',
  'report', 'transcript'
]
RETURN s.source_type AS non_canonical_type,
       count(s) AS count,
       collect(s.title)[..3] AS sample_titles
ORDER BY count DESC
```

### G5-2: 修正クエリ — source_type の正規化

```cypher
// academic_paper, paper → academic
MATCH (s:Source)
WHERE s.source_type IN ['academic_paper', 'paper']
SET s.source_type = 'academic'
RETURN count(s) AS updated

// white_paper → report
MATCH (s:Source)
WHERE s.source_type = 'white_paper'
SET s.source_type = 'report'
RETURN count(s) AS updated

// media → news
MATCH (s:Source)
WHERE s.source_type = 'media'
SET s.source_type = 'news'
RETURN count(s) AS updated
```

---

## G6: v3.0 分類ハブノード実体化

### 現状

ontology.yaml で定義された 16 分類ハブラベルのうち、ノードが実体化されているものは 0。
既存プロパティ値から分類ノードを作成し、リレーションで接続する。

### G6-1: SourceType ノードの実体化

```cypher
// 既存 Source.source_type プロパティから SourceType ノードを作成
WITH [
  {id: 'news', name: 'news', name_ja: 'ニュース'},
  {id: 'blog', name: 'blog', name_ja: 'ブログ'},
  {id: 'web', name: 'web', name_ja: 'ウェブ'},
  {id: 'pdf', name: 'pdf', name_ja: 'PDF'},
  {id: 'analysis', name: 'analysis', name_ja: '分析'},
  {id: 'company_filing', name: 'company_filing', name_ja: '企業開示'},
  {id: 'data', name: 'data', name_ja: 'データ'},
  {id: 'academic', name: 'academic', name_ja: '学術'},
  {id: 'presentation', name: 'presentation', name_ja: 'プレゼンテーション'},
  {id: 'financial_statement', name: 'financial_statement', name_ja: '財務諸表'},
  {id: 'report', name: 'report', name_ja: 'レポート'},
  {id: 'transcript', name: 'transcript', name_ja: '書き起こし'}
] AS types
UNWIND types AS t
MERGE (st:SourceType {source_type_id: t.id})
ON CREATE SET st.name = t.name, st.name_ja = t.name_ja
RETURN count(st) AS created
```

```cypher
// Source → SourceType リレーションを一括作成
MATCH (s:Source)
WHERE s.source_type IS NOT NULL
MATCH (st:SourceType {source_type_id: s.source_type})
MERGE (s)-[:IS_SOURCE_TYPE]->(st)
RETURN count(*) AS linked
```

### G6-2: TrustLevel ノードの実体化

```cypher
WITH [
  {id: 'official', name: 'official', name_ja: '公的機関', rank: 1},
  {id: 'academic', name: 'academic', name_ja: '学術', rank: 2},
  {id: 'company', name: 'company', name_ja: '企業公式', rank: 3},
  {id: 'institutional', name: 'institutional', name_ja: '機関投資家', rank: 4},
  {id: 'analyst', name: 'analyst', name_ja: 'アナリスト', rank: 5},
  {id: 'industry', name: 'industry', name_ja: '業界', rank: 6},
  {id: 'media', name: 'media', name_ja: 'メディア', rank: 7},
  {id: 'primary', name: 'primary', name_ja: '一次データ', rank: 8},
  {id: 'blog', name: 'blog', name_ja: 'ブログ', rank: 9},
  {id: 'social', name: 'social', name_ja: 'ソーシャル', rank: 10}
] AS levels
UNWIND levels AS l
MERGE (tl:TrustLevel {trust_level_id: l.id})
ON CREATE SET tl.name = l.name, tl.name_ja = l.name_ja, tl.rank = l.rank
RETURN count(tl) AS created
```

```cypher
// Source.authority_level → TrustLevel リレーションを一括作成
MATCH (s:Source)
WHERE s.authority_level IS NOT NULL
MATCH (tl:TrustLevel {trust_level_id: s.authority_level})
MERGE (s)-[:RATED_AS]->(tl)
RETURN count(*) AS linked
```

### G6-3: EntityType ノードの実体化

```cypher
WITH [
  {id: 'company', name: 'company', name_ja: '企業'},
  {id: 'technology', name: 'technology', name_ja: 'テクノロジー'},
  {id: 'organization', name: 'organization', name_ja: '機関'},
  {id: 'person', name: 'person', name_ja: '人物'},
  {id: 'index', name: 'index', name_ja: '株価指数'},
  {id: 'indicator', name: 'indicator', name_ja: '経済指標'},
  {id: 'instrument', name: 'instrument', name_ja: '金融商品'},
  {id: 'commodity', name: 'commodity', name_ja: 'コモディティ'},
  {id: 'country', name: 'country', name_ja: '国・地域'},
  {id: 'sector', name: 'sector', name_ja: 'セクター'},
  {id: 'concept', name: 'concept', name_ja: '概念'},
  {id: 'regulation', name: 'regulation', name_ja: '規制・政策'},
  {id: 'broker', name: 'broker', name_ja: 'ブローカー'},
  {id: 'product', name: 'product', name_ja: 'プロダクト'}
] AS types
UNWIND types AS t
MERGE (et:EntityType {entity_type_id: t.id})
ON CREATE SET et.name = t.name, et.name_ja = t.name_ja
RETURN count(et) AS created
```

```cypher
// Entity → EntityType リレーションを一括作成
MATCH (e:Entity)
WHERE e.entity_type IS NOT NULL
  AND NOT 'Memory' IN labels(e)
MATCH (et:EntityType {entity_type_id: e.entity_type})
MERGE (e)-[:IS_TYPE]->(et)
RETURN count(*) AS linked
```

### G6-4: ConceptCategory ノードの実体化

```cypher
WITH [
  {id: 'macro_economics', name: 'MacroEconomics', name_ja: 'マクロ経済', layer: 'What'},
  {id: 'equity_research', name: 'EquityResearch', name_ja: '株式リサーチ', layer: 'What'},
  {id: 'sector_analysis', name: 'SectorAnalysis', name_ja: 'セクター分析', layer: 'What'},
  {id: 'investment_strategy', name: 'InvestmentStrategy', name_ja: '投資戦略', layer: 'What'},
  {id: 'technology', name: 'Technology', name_ja: 'テクノロジー', layer: 'What'},
  {id: 'wealth_management', name: 'WealthManagement', name_ja: '資産形成', layer: 'What'},
  {id: 'regulation', name: 'Regulation', name_ja: '規制', layer: 'What'},
  {id: 'content_planning', name: 'ContentPlanning', name_ja: 'コンテンツ企画', layer: 'Meta'}
] AS categories
UNWIND categories AS c
MERGE (cc:ConceptCategory {concept_category_id: c.id})
ON CREATE SET cc.name = c.name, cc.name_ja = c.name_ja, cc.layer = c.layer
RETURN count(cc) AS created
```

```cypher
// Topic.category → ConceptCategory リレーションを作成
// ontology.yaml の source_categories マッピングに基づく
WITH {
  'macro': 'macro_economics', 'political': 'macro_economics',
  'geopolitical': 'macro_economics', 'geopolitics': 'macro_economics',
  'stock': 'equity_research', 'earnings': 'equity_research',
  'valuation': 'equity_research', 'equity_research': 'equity_research',
  'competition': 'equity_research', 'competitive_analysis': 'equity_research',
  'kpi': 'equity_research',
  'sector': 'sector_analysis', 'sector_analysis': 'sector_analysis',
  'cross_sector': 'sector_analysis', 'industry-trend': 'sector_analysis',
  'cost_competition': 'sector_analysis',
  'investment_strategy': 'investment_strategy', 'investment_framework': 'investment_strategy',
  'investment': 'investment_strategy', 'institutional_investing': 'investment_strategy',
  'capital-allocation': 'investment_strategy', 'fund_comparison': 'investment_strategy',
  'strategy': 'investment_strategy',
  'technology': 'technology', 'ai': 'technology',
  'quantitative_finance': 'technology', 'data_analysis': 'technology',
  'wealth': 'wealth_management', 'assets': 'wealth_management',
  'regulatory': 'regulation', 'regulation': 'regulation',
  'governance': 'regulation', 'corporate-action': 'regulation',
  'content_planning': 'content_planning', 'reddit': 'content_planning',
  'theme': 'content_planning'
} AS category_map
MATCH (t:Topic)
WHERE t.category IS NOT NULL
  AND t.category IN keys(category_map)
WITH t, category_map[t.category] AS cc_id
MATCH (cc:ConceptCategory {concept_category_id: cc_id})
MERGE (t)-[:IS_CATEGORY]->(cc)
RETURN count(*) AS linked
```

### G6-5: Pipeline ノードの実体化

```cypher
// Source.command_source から Pipeline ノードを作成
MATCH (s:Source)
WHERE s.command_source IS NOT NULL
WITH s.command_source AS pipeline_name, count(s) AS usage_count
MERGE (p:Pipeline {pipeline_id: toLower(replace(pipeline_name, ' ', '-'))})
ON CREATE SET p.name = pipeline_name
RETURN p.pipeline_id, p.name, usage_count
ORDER BY usage_count DESC
```

```cypher
// Source → Pipeline リレーションを作成
MATCH (s:Source)
WHERE s.command_source IS NOT NULL
MATCH (p:Pipeline {pipeline_id: toLower(replace(s.command_source, ' ', '-'))})
MERGE (s)-[:INGESTED_VIA]->(p)
RETURN count(*) AS linked
```

### G6-6: FactType ノードの実体化

```cypher
WITH [
  {id: 'statistic', name: 'statistic', name_ja: '統計', category: 'data'},
  {id: 'financial_metric', name: 'financial_metric', name_ja: '財務指標', category: 'data'},
  {id: 'macro_indicator', name: 'macro_indicator', name_ja: 'マクロ指標', category: 'data'},
  {id: 'event', name: 'event', name_ja: 'イベント', category: 'action'},
  {id: 'empirical', name: 'empirical', name_ja: '実証データ', category: 'data'},
  {id: 'regulatory', name: 'regulatory', name_ja: '規制', category: 'action'},
  {id: 'market_data', name: 'market_data', name_ja: '市場データ', category: 'data'},
  {id: 'strategic', name: 'strategic', name_ja: '戦略', category: 'analysis'},
  {id: 'methodology', name: 'methodology', name_ja: '方法論', category: 'analysis'},
  {id: 'risk', name: 'risk', name_ja: 'リスク', category: 'analysis'}
] AS types
UNWIND types AS t
MERGE (ft:FactType {fact_type_id: t.id})
ON CREATE SET ft.name = t.name, ft.name_ja = t.name_ja, ft.category = t.category
RETURN count(ft) AS created
```

```cypher
// Fact.fact_type → FactType リレーションを作成
MATCH (f:Fact)
WHERE f.fact_type IS NOT NULL
MATCH (ft:FactType {fact_type_id: f.fact_type})
MERGE (f)-[:IS_FACT_TYPE]->(ft)
RETURN count(*) AS linked
```

### G6-7: ClaimType ノードの実体化

```cypher
WITH [
  {id: 'fundamental', name: 'fundamental', name_ja: 'ファンダメンタル分析', direction: 'neutral'},
  {id: 'bullish', name: 'bullish', name_ja: '強気', direction: 'positive'},
  {id: 'bearish', name: 'bearish', name_ja: '弱気', direction: 'negative'},
  {id: 'technical', name: 'technical', name_ja: 'テクニカル分析', direction: 'neutral'},
  {id: 'risk_event', name: 'risk_event', name_ja: 'リスクイベント', direction: 'negative'},
  {id: 'policy_hawkish', name: 'policy_hawkish', name_ja: 'タカ派', direction: 'negative'},
  {id: 'sector_rotation', name: 'sector_rotation', name_ja: 'セクターローテーション', direction: 'neutral'},
  {id: 'earnings_beat', name: 'earnings_beat', name_ja: '決算上振れ', direction: 'positive'},
  {id: 'analyst_view', name: 'analyst_view', name_ja: 'アナリスト見解', direction: 'neutral'},
  {id: 'political_risk', name: 'political_risk', name_ja: '政治リスク', direction: 'negative'}
] AS types
UNWIND types AS t
MERGE (ct:ClaimType {claim_type_id: t.id})
ON CREATE SET ct.name = t.name, ct.name_ja = t.name_ja, ct.direction = t.direction
RETURN count(ct) AS created
```

```cypher
// Claim.claim_type → ClaimType リレーションを作成
MATCH (c:Claim)
WHERE c.claim_type IS NOT NULL
MATCH (ct:ClaimType {claim_type_id: c.claim_type})
MERGE (c)-[:IS_CLAIM_TYPE]->(ct)
RETURN count(*) AS linked
```

### G6-8: DataPointType ノードの実体化

```cypher
WITH [
  {id: 'actual', name: 'actual', name_ja: '実績'},
  {id: 'estimate', name: 'estimate', name_ja: '会社予想'},
  {id: 'forecast', name: 'forecast', name_ja: 'アナリスト予測'},
  {id: 'consensus', name: 'consensus', name_ja: 'コンセンサス'}
] AS types
UNWIND types AS t
MERGE (dt:DataPointType {datapoint_type_id: t.id})
ON CREATE SET dt.name = t.name, dt.name_ja = t.name_ja
RETURN count(dt) AS created
```

---

## G7: Topic カテゴリマッピング補完

### 現状

227 Topic のうち、47件が非標準カテゴリ、28件が null カテゴリ。

### G7-1: 診断クエリ — 未マッピングカテゴリの一覧

```cypher
MATCH (t:Topic)
WHERE t.category IS NOT NULL
  AND NOT t.category IN [
    'macro', 'political', 'geopolitical', 'geopolitics',
    'stock', 'earnings', 'valuation', 'equity_research',
    'competition', 'competitive_analysis', 'kpi',
    'sector', 'sector_analysis', 'cross_sector', 'industry-trend', 'cost_competition',
    'investment_strategy', 'investment_framework', 'investment',
    'institutional_investing', 'capital-allocation', 'fund_comparison', 'strategy',
    'technology', 'ai', 'quantitative_finance', 'data_analysis',
    'wealth', 'assets',
    'regulatory', 'regulation', 'governance', 'corporate-action',
    'content_planning', 'reddit', 'theme'
  ]
RETURN t.category AS unmapped_category,
       count(t) AS count,
       collect(t.name)[..5] AS sample_topics
ORDER BY count DESC
```

### G7-2: 修正クエリ — 未マッピングカテゴリの推定マッピング

```cypher
// finance → investment_strategy（最も近い分類）
MATCH (t:Topic)
WHERE t.category = 'finance'
SET t.category = 'investment_strategy'
RETURN count(t) AS updated

// methodology → technology
MATCH (t:Topic)
WHERE t.category = 'methodology'
SET t.category = 'quantitative_finance'
RETURN count(t) AS updated

// segment → sector_analysis
MATCH (t:Topic)
WHERE t.category = 'segment'
SET t.category = 'sector_analysis'
RETURN count(t) AS updated

// market, market_trend, regional_market → macro
MATCH (t:Topic)
WHERE t.category IN ['market', 'market_trend', 'regional_market']
SET t.category = 'macro'
RETURN count(t) AS updated

// business_model → strategy
MATCH (t:Topic)
WHERE t.category = 'business_model'
SET t.category = 'strategy'
RETURN count(t) AS updated

// financial → earnings
MATCH (t:Topic)
WHERE t.category = 'financial'
SET t.category = 'earnings'
RETURN count(t) AS updated

// risk_analysis → macro
MATCH (t:Topic)
WHERE t.category = 'risk_analysis'
SET t.category = 'macro'
RETURN count(t) AS updated
```

### G7-3: 診断クエリ — null カテゴリの Topic

```cypher
MATCH (t:Topic)
WHERE t.category IS NULL
RETURN t.topic_key, t.name
ORDER BY t.name
```

---

## G8: Entity プロパティ充填

### 現状

Entity の enrichment プロパティのカバレッジが低い:
- sector: 13.7%
- ticker: 11.1%
- industry: 9.0%
- enriched_at: 6.8%

### G8-1: 診断クエリ — エンリッチメント対象の company Entity

```cypher
// sector/ticker が未設定の company Entity を優先度順にリスト
MATCH (e:Entity)
WHERE e.entity_type = 'company'
  AND NOT 'Memory' IN labels(e)
  AND (e.sector IS NULL OR e.ticker IS NULL)
OPTIONAL MATCH (e)<-[:RELATES_TO]-(f:Fact)
WITH e, count(f) AS fact_count
RETURN e.entity_key,
       e.name,
       e.sector IS NOT NULL AS has_sector,
       e.ticker IS NOT NULL AS has_ticker,
       e.sec_cik IS NOT NULL AS has_cik,
       e.enriched_at IS NOT NULL AS is_enriched,
       fact_count
ORDER BY fact_count DESC
LIMIT 50
```

### G8-2: 診断クエリ — IN_SECTOR が未設定だが sector プロパティを持つ Entity

```cypher
// sector プロパティは持つが IN_SECTOR リレーションがない Entity
MATCH (e:Entity)
WHERE e.sector IS NOT NULL
  AND NOT (e)-[:IN_SECTOR]->()
  AND NOT 'Memory' IN labels(e)
RETURN e.entity_key,
       e.name,
       e.sector AS sector_value,
       e.entity_type
ORDER BY e.sector
```

---

## G9: Source プロパティ充填

### 現状

- language: 7.5%
- domain: 19.4%

### G9-1: 修正クエリ — URL からドメインを抽出して設定

```cypher
// Source.url からドメイン名を抽出して domain プロパティを設定
MATCH (s:Source)
WHERE s.url IS NOT NULL
  AND s.domain IS NULL
WITH s,
     CASE
       WHEN s.url STARTS WITH 'https://' THEN split(substring(s.url, 8), '/')[0]
       WHEN s.url STARTS WITH 'http://' THEN split(substring(s.url, 7), '/')[0]
       ELSE null
     END AS extracted_domain
WHERE extracted_domain IS NOT NULL
SET s.domain = extracted_domain
RETURN count(s) AS updated
```

### G9-2: 修正クエリ — タイトルから言語を推定

```cypher
// タイトルに日本語文字が含まれる場合は 'ja'、それ以外は 'en'
MATCH (s:Source)
WHERE s.language IS NULL
  AND s.title IS NOT NULL
WITH s,
     CASE
       WHEN s.title =~ '.*[\u3000-\u9FFF\uF900-\uFAFF].*' THEN 'ja'
       ELSE 'en'
     END AS detected_language
SET s.language = detected_language
RETURN detected_language, count(s) AS updated
```

---

## G10: 重複ノードマージ

### 現状

- Entity 真の重複: 7ペア
- Topic 重複: 8ペア
- Source URL 重複: 4ペア

### G10-1: 診断クエリ — Entity 重複ペアの確認

```cypher
// 同一名・同一タイプの Entity ペアを検出
MATCH (e1:Entity), (e2:Entity)
WHERE id(e1) < id(e2)
  AND toLower(e1.name) = toLower(e2.name)
  AND e1.entity_type = e2.entity_type
  AND NOT 'Memory' IN labels(e1)
  AND NOT 'Memory' IN labels(e2)
RETURN e1.entity_key AS key1,
       e2.entity_key AS key2,
       e1.name AS name,
       e1.entity_type AS type
```

### G10-2: 修正クエリ — NVIDIA/Nvidia 重複マージ（例）

```cypher
// Nvidia::company のリレーションを NVIDIA::company に移植後、Nvidia::company を削除
// 注意: 手動確認後にのみ実行すること
MATCH (keep:Entity {entity_key: 'NVIDIA::company'})
MATCH (dup:Entity {entity_key: 'Nvidia::company'})
// 受信リレーションの移植
CALL {
  WITH keep, dup
  MATCH (dup)<-[r]-(other)
  WHERE other <> keep
  WITH keep, type(r) AS rel_type, other, properties(r) AS props
  CALL apoc.create.relationship(other, rel_type, props, keep) YIELD rel
  RETURN count(rel) AS incoming_moved
}
// 送信リレーションの移植
CALL {
  WITH keep, dup
  MATCH (dup)-[r]->(other)
  WHERE other <> keep
  WITH keep, type(r) AS rel_type, other, properties(r) AS props
  CALL apoc.create.relationship(keep, rel_type, props, other) YIELD rel
  RETURN count(rel) AS outgoing_moved
}
// 重複ノードの削除
DETACH DELETE dup
RETURN keep.entity_key AS kept, incoming_moved, outgoing_moved
```

> **注意**: apoc.create.relationship が利用不可の場合は、リレーションタイプごとに個別の MERGE クエリで移植する。

---

## 実行優先順序

| 優先度 | クエリ群 | 期待効果 |
|--------|---------|---------|
| P0 | G1 (Entity 孤立解消) | D-3 Score +6% |
| P0 | G2 (FOR_METRIC 充填) | D-4 Score +5% |
| P1 | G3 (Source TAGGED 充填) | D-3 Score +3% |
| P1 | G4 (Entity タイプ正規化) | D-1 Score +2.5% |
| P1 | G5 (Source タイプ正規化) | D-1 Score +0.5% |
| P2 | G6 (ハブノード実体化) | D-4 Score +3% |
| P2 | G7 (Topic カテゴリ補完) | D-1 Score +1% |
| P2 | G8 (Entity プロパティ充填) | D-4 Score +3% |
| P2 | G9 (Source プロパティ充填) | D-4 Score +1% |
| P3 | G10 (重複マージ) | D-2 Score +0.3% |

全クエリ実行後の期待スコア: **83.5 → 約 92** (Grade A 達成見込み)
