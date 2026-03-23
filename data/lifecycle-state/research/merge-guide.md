# MERGE ガイド — research-neo4j v3.0

> **対象インスタンス**: research-neo4j (bolt://localhost:7688)
> **ドメイン**: 金融リサーチ・銘柄調査のナレッジグラフ
> **ノード数**: 33 ラベル / **リレーション数**: 59 種

---

## 目次

1. [UNIQUE 制約一覧](#1-unique-制約一覧)
2. [インデックス一覧](#2-インデックス一覧)
3. [ノード MERGE パターン（33 ラベル）](#3-ノード-merge-パターン33-ラベル)
4. [リレーション MERGE パターン（59 種）](#4-リレーション-merge-パターン59-種)
5. [投入順序（トポロジカルソート）](#5-投入順序トポロジカルソート)
6. [検証クエリ（孤立ノード検出）](#6-検証クエリ孤立ノード検出)

---

## 1. UNIQUE 制約一覧

```cypher
// Common Nodes
CREATE CONSTRAINT unique_research_source_id IF NOT EXISTS FOR (n:Source) REQUIRE n.source_id IS UNIQUE;
CREATE CONSTRAINT unique_research_entity_key IF NOT EXISTS FOR (n:Entity) REQUIRE n.entity_key IS UNIQUE;

// Content Types
CREATE CONSTRAINT unique_research_fact_id IF NOT EXISTS FOR (n:Fact) REQUIRE n.fact_id IS UNIQUE;
CREATE CONSTRAINT unique_research_claim_id IF NOT EXISTS FOR (n:Claim) REQUIRE n.claim_id IS UNIQUE;
CREATE CONSTRAINT unique_research_chunk_id IF NOT EXISTS FOR (n:Chunk) REQUIRE n.chunk_id IS UNIQUE;
CREATE CONSTRAINT unique_research_datapoint_id IF NOT EXISTS FOR (n:FinancialDataPoint) REQUIRE n.datapoint_id IS UNIQUE;
CREATE CONSTRAINT unique_research_insight_id IF NOT EXISTS FOR (n:Insight) REQUIRE n.insight_id IS UNIQUE;

// Domain Nodes
CREATE CONSTRAINT unique_research_topic_key IF NOT EXISTS FOR (n:Topic) REQUIRE n.topic_key IS UNIQUE;
CREATE CONSTRAINT unique_research_author_id IF NOT EXISTS FOR (n:Author) REQUIRE n.author_id IS UNIQUE;
CREATE CONSTRAINT unique_research_stance_id IF NOT EXISTS FOR (n:Stance) REQUIRE n.stance_id IS UNIQUE;
CREATE CONSTRAINT unique_research_metric_id IF NOT EXISTS FOR (n:Metric) REQUIRE n.metric_id IS UNIQUE;
CREATE CONSTRAINT unique_research_period_id IF NOT EXISTS FOR (n:FiscalPeriod) REQUIRE n.period_id IS UNIQUE;
CREATE CONSTRAINT unique_research_sector_id IF NOT EXISTS FOR (n:Sector) REQUIRE n.sector_id IS UNIQUE;
CREATE CONSTRAINT unique_research_concept_category_id IF NOT EXISTS FOR (n:ConceptCategory) REQUIRE n.concept_category_id IS UNIQUE;
CREATE CONSTRAINT unique_research_author_type_id IF NOT EXISTS FOR (n:AuthorType) REQUIRE n.author_type_id IS UNIQUE;
CREATE CONSTRAINT unique_research_instrument_class_id IF NOT EXISTS FOR (n:InstrumentClass) REQUIRE n.instrument_class_id IS UNIQUE;

// Source Classification Nodes
CREATE CONSTRAINT unique_research_source_type_id IF NOT EXISTS FOR (n:SourceType) REQUIRE n.source_type_id IS UNIQUE;
CREATE CONSTRAINT unique_research_domain_id IF NOT EXISTS FOR (n:Domain) REQUIRE n.domain_id IS UNIQUE;
CREATE CONSTRAINT unique_research_trust_level_id IF NOT EXISTS FOR (n:TrustLevel) REQUIRE n.trust_level_id IS UNIQUE;
CREATE CONSTRAINT unique_research_language_id IF NOT EXISTS FOR (n:Language) REQUIRE n.language_id IS UNIQUE;
CREATE CONSTRAINT unique_research_pipeline_id IF NOT EXISTS FOR (n:Pipeline) REQUIRE n.pipeline_id IS UNIQUE;

// Entity Classification Nodes
CREATE CONSTRAINT unique_research_entity_type_id IF NOT EXISTS FOR (n:EntityType) REQUIRE n.entity_type_id IS UNIQUE;
CREATE CONSTRAINT unique_research_identifier_id IF NOT EXISTS FOR (n:Identifier) REQUIRE n.identifier_id IS UNIQUE;
CREATE CONSTRAINT unique_research_industry_id IF NOT EXISTS FOR (n:Industry) REQUIRE n.industry_id IS UNIQUE;
CREATE CONSTRAINT unique_research_alias_id IF NOT EXISTS FOR (n:Alias) REQUIRE n.alias_id IS UNIQUE;

// Content Classification Nodes
CREATE CONSTRAINT unique_research_fact_type_id IF NOT EXISTS FOR (n:FactType) REQUIRE n.fact_type_id IS UNIQUE;
CREATE CONSTRAINT unique_research_claim_type_id IF NOT EXISTS FOR (n:ClaimType) REQUIRE n.claim_type_id IS UNIQUE;
CREATE CONSTRAINT unique_research_unit_id IF NOT EXISTS FOR (n:UnitOfMeasure) REQUIRE n.unit_id IS UNIQUE;
CREATE CONSTRAINT unique_research_datapoint_type_id IF NOT EXISTS FOR (n:DataPointType) REQUIRE n.datapoint_type_id IS UNIQUE;
```

---

## 2. インデックス一覧

### Full-Text インデックス

```cypher
CREATE FULLTEXT INDEX research_entity_fulltext IF NOT EXISTS FOR (n:Entity) ON EACH [n.name];
CREATE FULLTEXT INDEX research_topic_fulltext IF NOT EXISTS FOR (n:Topic) ON EACH [n.name];
CREATE FULLTEXT INDEX research_fact_fulltext IF NOT EXISTS FOR (n:Fact) ON EACH [n.content];
CREATE FULLTEXT INDEX research_claim_fulltext IF NOT EXISTS FOR (n:Claim) ON EACH [n.content];
CREATE FULLTEXT INDEX research_source_fulltext IF NOT EXISTS FOR (n:Source) ON EACH [n.title];
CREATE FULLTEXT INDEX research_alias_fulltext IF NOT EXISTS FOR (n:Alias) ON EACH [n.name];
```

### B-Tree インデックス

```cypher
CREATE INDEX idx_research_source_published IF NOT EXISTS FOR (n:Source) ON (n.published_at);
CREATE INDEX idx_research_topic_category IF NOT EXISTS FOR (n:Topic) ON (n.category);
CREATE INDEX idx_research_claim_type IF NOT EXISTS FOR (n:Claim) ON (n.claim_type);
CREATE INDEX idx_research_fact_type IF NOT EXISTS FOR (n:Fact) ON (n.fact_type);
CREATE INDEX idx_research_fdp_metric IF NOT EXISTS FOR (n:FinancialDataPoint) ON (n.metric_name);
CREATE INDEX idx_research_identifier_type_value IF NOT EXISTS FOR (n:Identifier) ON (n.type, n.value);
CREATE INDEX idx_research_entity_type_name IF NOT EXISTS FOR (n:EntityType) ON (n.name);
```

---

## 3. ノード MERGE パターン（33 ラベル）

### 3.1 Master Nodes（分類ノード: 14 ラベル）

これらは参照データであり、最初に投入する。

#### ConceptCategory

```cypher
MERGE (n:ConceptCategory {concept_category_id: $concept_category_id})
ON CREATE SET
  n.name = $name,
  n.name_ja = $name_ja,
  n.layer = $layer
ON MATCH SET
  n.name_ja = $name_ja,
  n.layer = $layer
```

#### EntityType

```cypher
MERGE (n:EntityType {entity_type_id: $entity_type_id})
ON CREATE SET
  n.name = $name,
  n.name_ja = $name_ja,
  n.description = $description,
  n.normalization_rule = $normalization_rule
ON MATCH SET
  n.name_ja = $name_ja
```

#### SourceType

```cypher
MERGE (n:SourceType {source_type_id: $source_type_id})
ON CREATE SET
  n.name = $name,
  n.name_ja = $name_ja
ON MATCH SET
  n.name_ja = $name_ja
```

#### TrustLevel

```cypher
MERGE (n:TrustLevel {trust_level_id: $trust_level_id})
ON CREATE SET
  n.name = $name,
  n.name_ja = $name_ja,
  n.rank = $rank
ON MATCH SET
  n.name_ja = $name_ja,
  n.rank = $rank
```

#### Language

```cypher
MERGE (n:Language {language_id: $language_id})
ON CREATE SET
  n.name = $name,
  n.name_ja = $name_ja
ON MATCH SET
  n.name_ja = $name_ja
```

#### Pipeline

```cypher
MERGE (n:Pipeline {pipeline_id: $pipeline_id})
ON CREATE SET
  n.name = $name,
  n.description = $description,
  n.category = $category
ON MATCH SET
  n.description = $description,
  n.category = $category
```

#### FactType

```cypher
MERGE (n:FactType {fact_type_id: $fact_type_id})
ON CREATE SET
  n.name = $name,
  n.name_ja = $name_ja,
  n.category = $category
ON MATCH SET
  n.name_ja = $name_ja
```

#### ClaimType

```cypher
MERGE (n:ClaimType {claim_type_id: $claim_type_id})
ON CREATE SET
  n.name = $name,
  n.name_ja = $name_ja,
  n.direction = $direction
ON MATCH SET
  n.name_ja = $name_ja
```

#### UnitOfMeasure

```cypher
MERGE (n:UnitOfMeasure {unit_id: $unit_id})
ON CREATE SET
  n.name = $name,
  n.symbol = $symbol,
  n.dimension = $dimension
ON MATCH SET
  n.symbol = $symbol,
  n.dimension = $dimension
```

#### DataPointType

```cypher
MERGE (n:DataPointType {datapoint_type_id: $datapoint_type_id})
ON CREATE SET
  n.name = $name,
  n.name_ja = $name_ja
ON MATCH SET
  n.name_ja = $name_ja
```

#### AuthorType

```cypher
MERGE (n:AuthorType {author_type_id: $author_type_id})
ON CREATE SET
  n.name = $name,
  n.name_ja = $name_ja
ON MATCH SET
  n.name_ja = $name_ja
```

#### InstrumentClass

```cypher
MERGE (n:InstrumentClass {instrument_class_id: $instrument_class_id})
ON CREATE SET
  n.name = $name,
  n.name_ja = $name_ja,
  n.fibo_domain = $fibo_domain
ON MATCH SET
  n.name_ja = $name_ja,
  n.fibo_domain = $fibo_domain
```

#### Sector

```cypher
MERGE (n:Sector {sector_id: $sector_id})
ON CREATE SET
  n.name = $name
ON MATCH SET
  n.name = $name
```

#### Industry

```cypher
MERGE (n:Industry {industry_id: $industry_id})
ON CREATE SET
  n.name = $name
ON MATCH SET
  n.name = $name
```

### 3.2 Core Nodes（基盤ノード: 9 ラベル）

Master Nodes が存在する前提で投入する。

#### Source

```cypher
MERGE (n:Source {source_id: $source_id})
ON CREATE SET
  n.url = $url,
  n.title = $title,
  n.collected_at = $collected_at,
  n.published_at = $published_at
ON MATCH SET
  n.title = COALESCE($title, n.title),
  n.published_at = COALESCE($published_at, n.published_at)
```

#### Entity

```cypher
MERGE (n:Entity {entity_key: $entity_key})
ON CREATE SET
  n.entity_id = $entity_id,
  n.name = $name,
  n.enriched_at = $enriched_at,
  n.updated_at = $updated_at
ON MATCH SET
  n.updated_at = $updated_at
```

#### Topic

```cypher
MERGE (n:Topic {topic_key: $topic_key})
ON CREATE SET
  n.topic_id = $topic_id,
  n.name = $name
ON MATCH SET
  n.name = COALESCE($name, n.name)
```

#### Author

```cypher
MERGE (n:Author {author_id: $author_id})
ON CREATE SET
  n.name = $name
ON MATCH SET
  n.name = COALESCE($name, n.name)
```

#### Metric

```cypher
MERGE (n:Metric {metric_id: $metric_id})
ON CREATE SET
  n.name = $name
ON MATCH SET
  n.name = COALESCE($name, n.name)
```

#### FiscalPeriod

```cypher
MERGE (n:FiscalPeriod {period_id: $period_id})
ON CREATE SET
  n.year = $year,
  n.quarter = $quarter,
  n.type = $type
ON MATCH SET
  n.year = $year,
  n.quarter = $quarter,
  n.type = $type
```

#### Domain

```cypher
MERGE (n:Domain {domain_id: $domain_id})
ON CREATE SET
  n.name = $name,
  n.base_url = $base_url,
  n.default_language = $default_language
ON MATCH SET
  n.base_url = COALESCE($base_url, n.base_url),
  n.default_language = COALESCE($default_language, n.default_language)
```

#### Identifier

```cypher
MERGE (n:Identifier {identifier_id: $identifier_id})
ON CREATE SET
  n.type = $type,
  n.value = $value,
  n.scheme = $scheme
ON MATCH SET
  n.value = $value,
  n.scheme = $scheme
```

#### Alias

```cypher
MERGE (n:Alias {alias_id: $alias_id})
ON CREATE SET
  n.name = $name,
  n.alias_type = $alias_type,
  n.language = $language
ON MATCH SET
  n.name = $name
```

### 3.3 Content Nodes（コンテンツノード: 6 ラベル）

Source と Entity が存在する前提で投入する。

#### Fact

```cypher
MERGE (n:Fact {fact_id: $fact_id})
ON CREATE SET
  n.content = $content,
  n.as_of_date = $as_of_date,
  n.created_at = $created_at
ON MATCH SET
  n.content = COALESCE($content, n.content)
```

#### Claim

```cypher
MERGE (n:Claim {claim_id: $claim_id})
ON CREATE SET
  n.content = $content,
  n.sentiment = $sentiment,
  n.confidence = $confidence,
  n.magnitude = $magnitude,
  n.classified_at = $classified_at
ON MATCH SET
  n.content = COALESCE($content, n.content),
  n.sentiment = COALESCE($sentiment, n.sentiment)
```

#### Chunk

```cypher
MERGE (n:Chunk {chunk_id: $chunk_id})
ON CREATE SET
  n.content = $content,
  n.chunk_index = $chunk_index,
  n.section_title = $section_title,
  n.has_tables = $has_tables,
  n.char_count = $char_count,
  n.created_at = $created_at
ON MATCH SET
  n.content = COALESCE($content, n.content)
```

#### FinancialDataPoint

```cypher
MERGE (n:FinancialDataPoint {datapoint_id: $datapoint_id})
ON CREATE SET
  n.value = $value,
  n.created_at = $created_at
ON MATCH SET
  n.value = $value
```

#### Insight

```cypher
MERGE (n:Insight {insight_id: $insight_id})
ON CREATE SET
  n.content = $content,
  n.created_at = $created_at
ON MATCH SET
  n.content = COALESCE($content, n.content)
```

#### Stance

```cypher
MERGE (n:Stance {stance_id: $stance_id})
ON CREATE SET
  n.sentiment = $sentiment,
  n.rating = $rating,
  n.target_price = $target_price,
  n.as_of_date = $as_of_date,
  n.note = $note
ON MATCH SET
  n.sentiment = COALESCE($sentiment, n.sentiment),
  n.rating = COALESCE($rating, n.rating),
  n.target_price = COALESCE($target_price, n.target_price)
```

### 3.4 Operational Nodes（運用ノード: 4 ラベル）

ドメインモデル外。パイプラインでは通常投入しない。

```cypher
// Memory — MCP Memory 経由で作成。直接 MERGE しない。
// SkillRun — スキル実行時に自動作成。
// QualitySnapshot — 品質計測スクリプトが作成。
// Question — 調査質問として手動作成。
```

---

## 4. リレーション MERGE パターン（59 種）

### 4.1 Source 分類リレーション（5 種）

最初に投入する（Source ↔ 分類ノード間）。

```cypher
// IS_SOURCE_TYPE: Source → SourceType
MATCH (s:Source {source_id: $source_id})
MATCH (t:SourceType {source_type_id: $source_type_id})
MERGE (s)-[:IS_SOURCE_TYPE]->(t)

// FROM_DOMAIN: Source → Domain
MATCH (s:Source {source_id: $source_id})
MATCH (d:Domain {domain_id: $domain_id})
MERGE (s)-[:FROM_DOMAIN]->(d)

// RATED_AS: Source → TrustLevel
MATCH (s:Source {source_id: $source_id})
MATCH (t:TrustLevel {trust_level_id: $trust_level_id})
MERGE (s)-[:RATED_AS]->(t)

// IN_LANGUAGE: Source → Language
MATCH (s:Source {source_id: $source_id})
MATCH (l:Language {language_id: $language_id})
MERGE (s)-[:IN_LANGUAGE]->(l)

// INGESTED_VIA: Source → Pipeline
MATCH (s:Source {source_id: $source_id})
MATCH (p:Pipeline {pipeline_id: $pipeline_id})
MERGE (s)-[:INGESTED_VIA]->(p)
```

### 4.2 Entity 分類リレーション（5 種）

```cypher
// IS_TYPE: Entity → EntityType
MATCH (e:Entity {entity_key: $entity_key})
MATCH (t:EntityType {entity_type_id: $entity_type_id})
MERGE (e)-[:IS_TYPE]->(t)

// HAS_IDENTIFIER: Entity → Identifier
MATCH (e:Entity {entity_key: $entity_key})
MATCH (i:Identifier {identifier_id: $identifier_id})
MERGE (e)-[:HAS_IDENTIFIER]->(i)

// IN_INDUSTRY: Entity → Industry
MATCH (e:Entity {entity_key: $entity_key})
MATCH (i:Industry {industry_id: $industry_id})
MERGE (e)-[:IN_INDUSTRY]->(i)

// ALIAS_OF: Alias → Entity|Topic
MATCH (a:Alias {alias_id: $alias_id})
MATCH (t {$target_key_property: $target_key_value})
MERGE (a)-[:ALIAS_OF]->(t)

// IS_INSTRUMENT_CLASS: Entity → InstrumentClass
MATCH (e:Entity {entity_key: $entity_key})
MATCH (ic:InstrumentClass {instrument_class_id: $instrument_class_id})
MERGE (e)-[:IS_INSTRUMENT_CLASS]->(ic)
```

### 4.3 Content 分類リレーション（4 種）

```cypher
// IS_FACT_TYPE: Fact → FactType
MATCH (f:Fact {fact_id: $fact_id})
MATCH (ft:FactType {fact_type_id: $fact_type_id})
MERGE (f)-[:IS_FACT_TYPE]->(ft)

// IS_CLAIM_TYPE: Claim → ClaimType
MATCH (c:Claim {claim_id: $claim_id})
MATCH (ct:ClaimType {claim_type_id: $claim_type_id})
MERGE (c)-[:IS_CLAIM_TYPE]->(ct)

// IN_UNIT: FDP|Stance → UnitOfMeasure
MATCH (n {$source_key_property: $source_key_value})
MATCH (u:UnitOfMeasure {unit_id: $unit_id})
MERGE (n)-[:IN_UNIT]->(u)

// IS_DATAPOINT_TYPE: FinancialDataPoint → DataPointType
MATCH (fdp:FinancialDataPoint {datapoint_id: $datapoint_id})
MATCH (dt:DataPointType {datapoint_type_id: $datapoint_type_id})
MERGE (fdp)-[:IS_DATAPOINT_TYPE]->(dt)
```

### 4.4 Domain 分類リレーション（3 種）

```cypher
// IS_CATEGORY: Topic → ConceptCategory
MATCH (t:Topic {topic_key: $topic_key})
MATCH (cc:ConceptCategory {concept_category_id: $concept_category_id})
MERGE (t)-[:IS_CATEGORY]->(cc)

// AFFILIATED_WITH: Author → Entity
MATCH (a:Author {author_id: $author_id})
MATCH (e:Entity {entity_key: $entity_key})
MERGE (a)-[:AFFILIATED_WITH]->(e)

// IS_AUTHOR_TYPE: Author → AuthorType
MATCH (a:Author {author_id: $author_id})
MATCH (at:AuthorType {author_type_id: $author_type_id})
MERGE (a)-[:IS_AUTHOR_TYPE]->(at)
```

### 4.5 階層・参照リレーション（3 種）

```cypher
// PARENT_CLASS: InstrumentClass (L2) → InstrumentClass (L1)
MATCH (child:InstrumentClass {instrument_class_id: $child_id})
MATCH (parent:InstrumentClass {instrument_class_id: $parent_id})
MERGE (child)-[:PARENT_CLASS]->(parent)

// IN_PARENT_SECTOR: Industry → Sector
MATCH (i:Industry {industry_id: $industry_id})
MATCH (s:Sector {sector_id: $sector_id})
MERGE (i)-[:IN_PARENT_SECTOR]->(s)

// ISSUED_BY: Identifier → Entity
MATCH (id:Identifier {identifier_id: $identifier_id})
MATCH (e:Entity {entity_key: $entity_key})
MERGE (id)-[:ISSUED_BY]->(e)
```

### 4.6 コンテンツ接続リレーション（7 種）

```cypher
// TAGGED: Source → Topic
MATCH (s:Source {source_id: $source_id})
MATCH (t:Topic {topic_key: $topic_key})
MERGE (s)-[:TAGGED]->(t)

// STATES_FACT: Source → Fact
MATCH (s:Source {source_id: $source_id})
MATCH (f:Fact {fact_id: $fact_id})
MERGE (s)-[:STATES_FACT]->(f)

// MAKES_CLAIM: Source → Claim
MATCH (s:Source {source_id: $source_id})
MATCH (c:Claim {claim_id: $claim_id})
MERGE (s)-[:MAKES_CLAIM]->(c)

// CONTAINS_CHUNK: Source → Chunk
MATCH (s:Source {source_id: $source_id})
MATCH (ch:Chunk {chunk_id: $chunk_id})
MERGE (s)-[:CONTAINS_CHUNK]->(ch)

// EXTRACTED_FROM: Fact|Claim → Chunk
MATCH (n {$source_key_property: $source_key_value})
MATCH (ch:Chunk {chunk_id: $chunk_id})
MERGE (n)-[:EXTRACTED_FROM]->(ch)

// HAS_DATAPOINT: Source → FinancialDataPoint
MATCH (s:Source {source_id: $source_id})
MATCH (fdp:FinancialDataPoint {datapoint_id: $datapoint_id})
MERGE (s)-[:HAS_DATAPOINT]->(fdp)

// ABOUT: Fact|Claim → Topic
MATCH (n {$source_key_property: $source_key_value})
MATCH (t:Topic {topic_key: $topic_key})
MERGE (n)-[:ABOUT]->(t)
```

### 4.7 エンティティ関連リレーション（4 種）

```cypher
// RELATES_TO: Fact|FDP → Entity
MATCH (n {$source_key_property: $source_key_value})
MATCH (e:Entity {entity_key: $entity_key})
MERGE (n)-[:RELATES_TO]->(e)

// MENTIONS: Fact|Claim|Chunk → Entity
MATCH (n {$source_key_property: $source_key_value})
MATCH (e:Entity {entity_key: $entity_key})
MERGE (n)-[:MENTIONS]->(e)

// IN_SECTOR: Entity → Sector
MATCH (e:Entity {entity_key: $entity_key})
MATCH (s:Sector {sector_id: $sector_id})
MERGE (e)-[:IN_SECTOR]->(s)

// ON_ENTITY: Stance → Entity
MATCH (st:Stance {stance_id: $stance_id})
MATCH (e:Entity {entity_key: $entity_key})
MERGE (st)-[:ON_ENTITY]->(e)
```

### 4.8 分析・推論リレーション（6 種）

```cypher
// SUPPORTED_BY: Claim → Fact
MATCH (c:Claim {claim_id: $claim_id})
MATCH (f:Fact {fact_id: $fact_id})
MERGE (c)-[:SUPPORTED_BY]->(f)

// CONTRADICTS: Claim → Claim
MATCH (c1:Claim {claim_id: $claim_id_1})
MATCH (c2:Claim {claim_id: $claim_id_2})
MERGE (c1)-[:CONTRADICTS]->(c2)

// INFLUENCES: Entity → Entity
MATCH (e1:Entity {entity_key: $entity_key_1})
MATCH (e2:Entity {entity_key: $entity_key_2})
MERGE (e1)-[:INFLUENCES]->(e2)

// CAUSES: Entity → Entity
MATCH (e1:Entity {entity_key: $entity_key_1})
MATCH (e2:Entity {entity_key: $entity_key_2})
MERGE (e1)-[:CAUSES]->(e2)

// DERIVED_FROM: Insight → Fact
MATCH (i:Insight {insight_id: $insight_id})
MATCH (f:Fact {fact_id: $fact_id})
MERGE (i)-[:DERIVED_FROM]->(f)

// SHARES_TOPIC: Source → Source
MATCH (s1:Source {source_id: $source_id_1})
MATCH (s2:Source {source_id: $source_id_2})
MERGE (s1)-[:SHARES_TOPIC]->(s2)
```

### 4.9 時系列リレーション（3 種）

```cypher
// FOR_PERIOD: FinancialDataPoint → FiscalPeriod
MATCH (fdp:FinancialDataPoint {datapoint_id: $datapoint_id})
MATCH (fp:FiscalPeriod {period_id: $period_id})
MERGE (fdp)-[:FOR_PERIOD]->(fp)

// NEXT_PERIOD: FiscalPeriod → FiscalPeriod
MATCH (fp1:FiscalPeriod {period_id: $period_id_1})
MATCH (fp2:FiscalPeriod {period_id: $period_id_2})
MERGE (fp1)-[:NEXT_PERIOD]->(fp2)

// TREND: FinancialDataPoint → FinancialDataPoint
MATCH (fdp1:FinancialDataPoint {datapoint_id: $datapoint_id_1})
MATCH (fdp2:FinancialDataPoint {datapoint_id: $datapoint_id_2})
MERGE (fdp1)-[:TREND]->(fdp2)
```

### 4.10 エンティティ間リレーション（9 種）

```cypher
// COMPETES_WITH: Entity → Entity
MATCH (e1:Entity {entity_key: $entity_key_1})
MATCH (e2:Entity {entity_key: $entity_key_2})
MERGE (e1)-[:COMPETES_WITH]->(e2)

// CUSTOMER_OF: Entity → Entity
MATCH (e1:Entity {entity_key: $entity_key_1})
MATCH (e2:Entity {entity_key: $entity_key_2})
MERGE (e1)-[:CUSTOMER_OF]->(e2)

// SUBSIDIARY_OF: Entity → Entity
MATCH (child:Entity {entity_key: $child_entity_key})
MATCH (parent:Entity {entity_key: $parent_entity_key})
MERGE (child)-[:SUBSIDIARY_OF]->(parent)

// PARTNERS_WITH: Entity → Entity
MATCH (e1:Entity {entity_key: $entity_key_1})
MATCH (e2:Entity {entity_key: $entity_key_2})
MERGE (e1)-[:PARTNERS_WITH]->(e2)

// INVESTED_IN: Entity → Entity
MATCH (investor:Entity {entity_key: $investor_entity_key})
MATCH (target:Entity {entity_key: $target_entity_key})
MERGE (investor)-[:INVESTED_IN]->(target)

// GOVERNS: Entity → Entity
MATCH (regulator:Entity {entity_key: $regulator_entity_key})
MATCH (regulated:Entity {entity_key: $regulated_entity_key})
MERGE (regulator)-[:GOVERNS]->(regulated)

// OPERATES_IN: Entity → Entity
MATCH (company:Entity {entity_key: $company_entity_key})
MATCH (region:Entity {entity_key: $region_entity_key})
MERGE (company)-[:OPERATES_IN]->(region)

// SPUN_OFF_FROM: Entity → Entity
MATCH (spinoff:Entity {entity_key: $spinoff_entity_key})
MATCH (parent:Entity {entity_key: $parent_entity_key})
MERGE (spinoff)-[:SPUN_OFF_FROM]->(parent)

// LED_BY: Entity → Entity
MATCH (org:Entity {entity_key: $org_entity_key})
MATCH (leader:Entity {entity_key: $leader_entity_key})
MERGE (org)-[:LED_BY]->(leader)
```

### 4.11 メタ・スタンスリレーション（8 種）

```cypher
// AUTHORED_BY: Source → Author
MATCH (s:Source {source_id: $source_id})
MATCH (a:Author {author_id: $author_id})
MERGE (s)-[:AUTHORED_BY]->(a)

// COAUTHORED_WITH: Author → Author
MATCH (a1:Author {author_id: $author_id_1})
MATCH (a2:Author {author_id: $author_id_2})
MERGE (a1)-[:COAUTHORED_WITH]->(a2)

// CO_MENTIONED_WITH: Entity → Entity
MATCH (e1:Entity {entity_key: $entity_key_1})
MATCH (e2:Entity {entity_key: $entity_key_2})
MERGE (e1)-[:CO_MENTIONED_WITH]->(e2)

// MEASURES: Metric → Entity
MATCH (m:Metric {metric_id: $metric_id})
MATCH (e:Entity {entity_key: $entity_key})
MERGE (m)-[:MEASURES]->(e)

// FOR_METRIC: FinancialDataPoint → Metric
MATCH (fdp:FinancialDataPoint {datapoint_id: $datapoint_id})
MATCH (m:Metric {metric_id: $metric_id})
MERGE (fdp)-[:FOR_METRIC]->(m)

// HOLDS_STANCE: Source → Stance
MATCH (s:Source {source_id: $source_id})
MATCH (st:Stance {stance_id: $stance_id})
MERGE (s)-[:HOLDS_STANCE]->(st)

// BASED_ON: Stance → Source
MATCH (st:Stance {stance_id: $stance_id})
MATCH (s:Source {source_id: $source_id})
MERGE (st)-[:BASED_ON]->(s)

// SOURCED_FROM: Fact|Claim → Source
MATCH (n {$source_key_property: $source_key_value})
MATCH (s:Source {source_id: $source_id})
MERGE (n)-[:SOURCED_FROM]->(s)
```

### 4.12 レガシーリレーション（2 種）

```cypher
// BELONGS_TO: Entity|Topic → Sector|Topic
MATCH (n {$source_key_property: $source_key_value})
MATCH (t {$target_key_property: $target_key_value})
MERGE (n)-[:BELONGS_TO]->(t)

// ASKS_ABOUT: Question → Topic
MATCH (q:Question {question_id: $question_id})
MATCH (t:Topic {topic_key: $topic_key})
MERGE (q)-[:ASKS_ABOUT]->(t)
```

---

## 5. 投入順序（トポロジカルソート）

データ投入は以下の順序で実行すること。各フェーズ内は並列実行可能。

### Phase 1: スキーマ作成

```
制約 → Full-Text インデックス → B-Tree インデックス
```

### Phase 2: ノード投入

```
Phase 2-1: Master Nodes（分類ノード）
  ├── ConceptCategory
  ├── EntityType
  ├── SourceType
  ├── TrustLevel
  ├── Language
  ├── Pipeline
  ├── FactType
  ├── ClaimType
  ├── UnitOfMeasure
  ├── DataPointType
  ├── AuthorType
  ├── InstrumentClass
  ├── Sector
  └── Industry
      ↓
Phase 2-2: Core Nodes（基盤ノード）
  ├── Source
  ├── Entity
  ├── Topic
  ├── Author
  ├── Metric
  ├── FiscalPeriod
  ├── Domain
  ├── Identifier
  └── Alias
      ↓
Phase 2-3: Content Nodes（コンテンツノード）
  ├── Fact
  ├── Claim
  ├── Chunk
  ├── FinancialDataPoint
  ├── Insight
  └── Stance
```

### Phase 3: リレーション投入

```
Phase 3-1: 分類リレーション（Master ↔ Core/Content）
  ├── IS_SOURCE_TYPE, FROM_DOMAIN, RATED_AS, IN_LANGUAGE, INGESTED_VIA  (Source分類)
  ├── IS_TYPE, HAS_IDENTIFIER, IN_INDUSTRY, ALIAS_OF, IS_INSTRUMENT_CLASS  (Entity分類)
  ├── IS_FACT_TYPE, IS_CLAIM_TYPE, IN_UNIT, IS_DATAPOINT_TYPE  (Content分類)
  ├── IS_CATEGORY, AFFILIATED_WITH, IS_AUTHOR_TYPE  (Domain分類)
  └── PARENT_CLASS, IN_PARENT_SECTOR, ISSUED_BY  (階層・参照)
      ↓
Phase 3-2: コンテンツ接続リレーション
  ├── TAGGED, STATES_FACT, MAKES_CLAIM, CONTAINS_CHUNK
  ├── EXTRACTED_FROM, HAS_DATAPOINT, ABOUT
  ├── AUTHORED_BY, HOLDS_STANCE, BASED_ON, SOURCED_FROM
  └── IN_SECTOR, ON_ENTITY
      ↓
Phase 3-3: エンティティ関連リレーション
  ├── RELATES_TO, MENTIONS
  ├── COMPETES_WITH, CUSTOMER_OF, SUBSIDIARY_OF
  ├── PARTNERS_WITH, INVESTED_IN, GOVERNS
  ├── OPERATES_IN, SPUN_OFF_FROM, LED_BY
  └── CO_MENTIONED_WITH, COAUTHORED_WITH
      ↓
Phase 3-4: 分析・推論リレーション
  ├── SUPPORTED_BY, CONTRADICTS
  ├── INFLUENCES, CAUSES
  ├── DERIVED_FROM, SHARES_TOPIC
  └── MEASURES, FOR_METRIC
      ↓
Phase 3-5: 時系列リレーション
  ├── FOR_PERIOD, NEXT_PERIOD
  └── TREND
      ↓
Phase 3-6: レガシーリレーション
  ├── BELONGS_TO
  └── ASKS_ABOUT
```

---

## 6. 検証クエリ（孤立ノード検出）

投入完了後に以下のクエリを実行し、リレーション欠落を検出すること。

### 6.1 孤立ノード検出（全般）

```cypher
// リレーションが一切ないノードを検出（Operational Nodes を除外）
MATCH (n)
WHERE NOT (n)--()
  AND NOT 'Memory' IN labels(n)
  AND NOT 'SkillRun' IN labels(n)
  AND NOT 'QualitySnapshot' IN labels(n)
  AND NOT 'Question' IN labels(n)
RETURN labels(n) AS label, count(n) AS orphan_count
ORDER BY orphan_count DESC
```

### 6.2 Source の分類リレーション欠落

```cypher
// IS_SOURCE_TYPE が未設定の Source
MATCH (s:Source)
WHERE NOT (s)-[:IS_SOURCE_TYPE]->()
RETURN s.source_id, s.title
LIMIT 20

// RATED_AS（TrustLevel）が未設定の Source
MATCH (s:Source)
WHERE NOT (s)-[:RATED_AS]->()
RETURN s.source_id, s.title
LIMIT 20

// IN_LANGUAGE が未設定の Source
MATCH (s:Source)
WHERE NOT (s)-[:IN_LANGUAGE]->()
RETURN s.source_id, s.title
LIMIT 20

// INGESTED_VIA が未設定の Source
MATCH (s:Source)
WHERE NOT (s)-[:INGESTED_VIA]->()
RETURN s.source_id, s.title
LIMIT 20
```

### 6.3 Entity の分類リレーション欠落

```cypher
// IS_TYPE が未設定の Entity
MATCH (e:Entity)
WHERE NOT (e)-[:IS_TYPE]->()
RETURN e.entity_key, e.name
LIMIT 20
```

### 6.4 Fact/Claim の接続欠落

```cypher
// SOURCED_FROM も STATES_FACT/MAKES_CLAIM もない Fact
MATCH (f:Fact)
WHERE NOT (f)-[:SOURCED_FROM]->()
  AND NOT ()-[:STATES_FACT]->(f)
RETURN f.fact_id, left(f.content, 80) AS content_preview
LIMIT 20

// MENTIONS も RELATES_TO もない Fact
MATCH (f:Fact)
WHERE NOT (f)-[:MENTIONS]->()
  AND NOT (f)-[:RELATES_TO]->()
RETURN f.fact_id, left(f.content, 80) AS content_preview
LIMIT 20

// SOURCED_FROM も MAKES_CLAIM もない Claim
MATCH (c:Claim)
WHERE NOT (c)-[:SOURCED_FROM]->()
  AND NOT ()-[:MAKES_CLAIM]->(c)
RETURN c.claim_id, left(c.content, 80) AS content_preview
LIMIT 20
```

### 6.5 Topic の分類リレーション欠落

```cypher
// IS_CATEGORY が未設定の Topic
MATCH (t:Topic)
WHERE NOT (t)-[:IS_CATEGORY]->()
RETURN t.topic_key, t.name
LIMIT 20
```

### 6.6 FinancialDataPoint の接続欠落

```cypher
// Source との接続がない FDP
MATCH (fdp:FinancialDataPoint)
WHERE NOT ()-[:HAS_DATAPOINT]->(fdp)
RETURN fdp.datapoint_id, fdp.value
LIMIT 20

// Entity との接続がない FDP
MATCH (fdp:FinancialDataPoint)
WHERE NOT (fdp)-[:RELATES_TO]->()
RETURN fdp.datapoint_id, fdp.value
LIMIT 20
```

### 6.7 統計サマリー

```cypher
// 全ラベル別ノード数
CALL db.labels() YIELD label
CALL {
  WITH label
  MATCH (n)
  WHERE label IN labels(n)
  RETURN count(n) AS cnt
}
RETURN label, cnt
ORDER BY cnt DESC

// 全リレーションタイプ別カウント
MATCH ()-[r]->()
RETURN type(r) AS rel_type, count(r) AS cnt
ORDER BY cnt DESC
```
