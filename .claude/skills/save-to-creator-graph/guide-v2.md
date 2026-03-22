# save-to-creator-graph v2 詳細ガイド

schema_version: "creator-2.0" 対応の MERGE パターン。
10 ノード・11 リレーション。

---

## スキーマバージョン判定

```
schema_version == "creator-1.0" → guide.md（旧）を使用
schema_version == "creator-2.0" → guide-v2.md（本ファイル）を使用
```

---

## 制約・インデックス（v2 追加分）

既存の v1 制約に加えて以下を作成:

```cypher
// ConceptCategory
CREATE CONSTRAINT unique_creator_concept_category_name IF NOT EXISTS
  FOR (cc:ConceptCategory) REQUIRE cc.name IS UNIQUE;

// Concept
CREATE CONSTRAINT unique_creator_concept_id IF NOT EXISTS
  FOR (c:Concept) REQUIRE c.concept_id IS UNIQUE;
CREATE CONSTRAINT unique_creator_concept_name IF NOT EXISTS
  FOR (c:Concept) REQUIRE c.name IS UNIQUE;

// Domain
CREATE CONSTRAINT unique_creator_domain_name IF NOT EXISTS
  FOR (d:Domain) REQUIRE d.name IS UNIQUE;

// Alias
CREATE CONSTRAINT unique_creator_alias_value IF NOT EXISTS
  FOR (a:Alias) REQUIRE a.value IS UNIQUE;

// Full-Text Index
CREATE FULLTEXT INDEX entity_fulltext IF NOT EXISTS
  FOR (e:Entity) ON EACH [e.name];
CREATE FULLTEXT INDEX concept_fulltext IF NOT EXISTS
  FOR (c:Concept) ON EACH [c.name];
CREATE FULLTEXT INDEX alias_fulltext IF NOT EXISTS
  FOR (a:Alias) ON EACH [a.value];

// インデックス
CREATE INDEX idx_creator_concept_category_layer IF NOT EXISTS
  FOR (cc:ConceptCategory) ON (cc.layer);
```

---

## ノード MERGE パターン（10種）

### 1. Genre（既存維持）

```cypher
MERGE (g:Genre {genre_id: $genre_id})
SET g.name = $name
```

### 2. ConceptCategory（新規）

```cypher
UNWIND $categories AS row
MERGE (cc:ConceptCategory {name: row.name})
SET cc.name_ja = row.name_ja,
    cc.layer = row.layer,
    cc.created_at = coalesce(cc.created_at, datetime())
```

### 3. Concept（新規、Topic を置換）

```cypher
UNWIND $concepts AS row
MERGE (c:Concept {concept_id: row.concept_id})
SET c.name = row.name,
    c.created_at = coalesce(c.created_at, datetime()),
    c.updated_at = datetime()
```

### 4. Entity（既存、embedding プロパティ対応）

```cypher
UNWIND $entities AS row
MERGE (e:Entity {entity_key: row.entity_key})
ON CREATE SET e.entity_id = row.entity_id,
              e.created_at = datetime()
SET e.name = row.name,
    e.entity_type = row.entity_type,
    e.updated_at = datetime()
```

### 5. Source（改修、language/domain 追加）

```cypher
UNWIND $sources AS row
MERGE (s:Source {source_id: row.source_id})
SET s.url = row.url,
    s.title = row.title,
    s.source_type = row.source_type,
    s.authority_level = row.authority_level,
    s.language = row.language,
    s.domain = row.domain,
    s.collected_at = CASE WHEN row.collected_at <> '' THEN datetime(row.collected_at) ELSE null END,
    s.published_at = CASE WHEN row.published_at <> '' THEN datetime(row.published_at) ELSE null END
```

### 6. Domain（新規）

```cypher
UNWIND $domains AS row
MERGE (d:Domain {name: row.name})
SET d.created_at = coalesce(d.created_at, datetime())
```

### 7. Fact（既存維持）

```cypher
UNWIND $facts AS row
MERGE (f:Fact {fact_id: row.fact_id})
SET f.text = row.text,
    f.category = row.category,
    f.confidence = row.confidence,
    f.created_at = coalesce(f.created_at, datetime())
```

### 8. Tip（既存維持）

```cypher
UNWIND $tips AS row
MERGE (t:Tip {tip_id: row.tip_id})
SET t.text = row.text,
    t.category = row.category,
    t.difficulty = row.difficulty,
    t.created_at = coalesce(t.created_at, datetime())
```

### 9. Story（既存維持）

```cypher
UNWIND $stories AS row
MERGE (s:Story {story_id: row.story_id})
SET s.text = row.text,
    s.outcome = row.outcome,
    s.timeline = row.timeline,
    s.created_at = coalesce(s.created_at, datetime())
```

### 10. Alias（新規）

Alias ノードは Entity/Concept 投入後に別途作成する。
初期セットは `data/config/entity-aliases.yaml` から投入。

```cypher
UNWIND $aliases AS row
MERGE (a:Alias {value: row.value})
SET a.language = row.language,
    a.created_at = coalesce(a.created_at, datetime())
```

---

## リレーション MERGE パターン（11種）

### 1. IS_A（Concept → ConceptCategory）

```cypher
UNWIND $rels AS row
MATCH (c:Concept {concept_id: row.from_id})
MATCH (cc:ConceptCategory {name: row.to_id})
MERGE (c)-[:IS_A]->(cc)
```

### 2. SERVES_AS（Entity → Concept）

```cypher
UNWIND $rels AS row
MATCH (e:Entity {entity_id: row.from_id})
MATCH (c:Concept {concept_id: row.to_id})
MERGE (e)-[r:SERVES_AS]->(c)
SET r.context = row.context
```

### 3. ABOUT（Fact → Concept）

```cypher
UNWIND $rels AS row
MATCH (f:Fact {fact_id: row.from_id})
MATCH (c:Concept {concept_id: row.to_id})
MERGE (f)-[:ABOUT]->(c)
```

### 4. ABOUT（Tip → Concept）

```cypher
UNWIND $rels AS row
MATCH (t:Tip {tip_id: row.from_id})
MATCH (c:Concept {concept_id: row.to_id})
MERGE (t)-[:ABOUT]->(c)
```

### 5. ABOUT（Story → Concept）

```cypher
UNWIND $rels AS row
MATCH (s:Story {story_id: row.from_id})
MATCH (c:Concept {concept_id: row.to_id})
MERGE (s)-[:ABOUT]->(c)
```

### 6. MENTIONS（Fact/Tip/Story → Entity）

```cypher
// Fact
UNWIND $rels AS row
MATCH (f:Fact {fact_id: row.from_id})
MATCH (e:Entity {entity_id: row.to_id})
MERGE (f)-[:MENTIONS]->(e)

// Tip
UNWIND $rels AS row
MATCH (t:Tip {tip_id: row.from_id})
MATCH (e:Entity {entity_id: row.to_id})
MERGE (t)-[:MENTIONS]->(e)

// Story
UNWIND $rels AS row
MATCH (s:Story {story_id: row.from_id})
MATCH (e:Entity {entity_id: row.to_id})
MERGE (s)-[:MENTIONS]->(e)
```

### 7. IN_GENRE（Fact/Tip/Story → Genre）

```cypher
// Fact
UNWIND $rels AS row
MATCH (f:Fact {fact_id: row.from_id})
MATCH (g:Genre {genre_id: row.to_id})
MERGE (f)-[:IN_GENRE]->(g)

// Tip, Story も同様
```

### 8. FROM_SOURCE（Fact/Tip/Story → Source）

```cypher
// v1 と同じパターン
UNWIND $rels AS row
MATCH (f:Fact {fact_id: row.from_id})
MATCH (s:Source {source_id: row.to_id})
MERGE (f)-[:FROM_SOURCE]->(s)
```

### 9. FROM_DOMAIN（Source → Domain）

```cypher
UNWIND $rels AS row
MATCH (s:Source {source_id: row.from_id})
MATCH (d:Domain {name: row.to_id})
MERGE (s)-[:FROM_DOMAIN]->(d)
```

### 10. ALIAS_OF（Alias → Entity/Concept）

```cypher
// Entity
UNWIND $rels AS row
MATCH (a:Alias {value: row.alias_value})
MATCH (e:Entity {entity_id: row.target_id})
MERGE (a)-[:ALIAS_OF]->(e)

// Concept
UNWIND $rels AS row
MATCH (a:Alias {value: row.alias_value})
MATCH (c:Concept {concept_id: row.target_id})
MERGE (a)-[:ALIAS_OF]->(c)
```

### 11. Concept 間リレーション（ENABLES/REQUIRES/COMPETES_WITH）

```cypher
// ENABLES
UNWIND $rels AS row
MATCH (c1:Concept {concept_id: row.from_id})
MATCH (c2:Concept {concept_id: row.to_id})
MERGE (c1)-[r:ENABLES]->(c2)
SET r.context = row.context

// REQUIRES
UNWIND $rels AS row
MATCH (c1:Concept {concept_id: row.from_id})
MATCH (c2:Concept {concept_id: row.to_id})
MERGE (c1)-[:REQUIRES]->(c2)

// COMPETES_WITH
UNWIND $rels AS row
MATCH (c1:Concept {concept_id: row.from_id})
MATCH (c2:Concept {concept_id: row.to_id})
MERGE (c1)-[:COMPETES_WITH]->(c2)
```

---

## 投入順序（依存関係順）

```
Phase 2: ノード投入
  1. Genre（3固定）
  2. ConceptCategory（14種 + 拡張）
  3. Domain
  4. Source
  5. Concept
  6. Entity
  7. Fact / Tip / Story

Phase 3: リレーション投入
  1. IS_A (Concept → ConceptCategory)
  2. FROM_DOMAIN (Source → Domain)
  3. ABOUT (Content → Concept)
  4. MENTIONS (Content → Entity)
  5. IN_GENRE (Content → Genre)
  6. FROM_SOURCE (Content → Source)
  7. SERVES_AS (Entity → Concept)
  8. ENABLES / REQUIRES / COMPETES_WITH (Concept → Concept)
```

---

## 投入検証クエリ（v2）

```cypher
// ノード数確認
MATCH (n)
RETURN labels(n)[0] AS label, count(n) AS cnt
ORDER BY cnt DESC

// 孤立コンテンツ（ABOUT なし）
MATCH (n) WHERE (n:Fact OR n:Tip OR n:Story) AND NOT (n)-[:ABOUT]->()
RETURN count(n) AS orphan_content

// IS_A なし Concept
MATCH (c:Concept) WHERE NOT (c)-[:IS_A]->()
RETURN count(c) AS unclassified_concepts

// FROM_DOMAIN なし Source
MATCH (s:Source) WHERE NOT (s)-[:FROM_DOMAIN]->()
RETURN count(s) AS no_domain_sources
```
