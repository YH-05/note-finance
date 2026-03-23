# MERGE Patterns Template

neo4j-lifecycle Phase B-4 で使用する MERGE Cypher パターンテンプレート。
`ontology-template.yaml` + `schema.yaml` の確定値を埋め込んで、インスタンス固有の MERGE ガイドを生成する。

## Phase B での埋め込み手順

1. `data/lifecycle-state/{instance}/ontology.yaml` と `data/lifecycle-state/{instance}/schema.yaml` を読み込む
2. 以下のプレースホルダーを確定値で置換する
3. 生成されたガイドを `data/lifecycle-state/{instance}/merge-guide.md` として保存する
4. `save-to-{instance}-graph` スキルがこのガイドを参照して MERGE クエリを実行する

## プレースホルダー一覧

| プレースホルダー | ソース | 説明 |
|-----------------|--------|------|
| `{{SCHEMA_VERSION}}` | `ontology.yaml > schema_version` | スキーマバージョン |
| `{{INSTANCE_NAME}}` | `ontology.yaml > instance_name` | インスタンス名 |
| `{{NODE_DEFINITIONS}}` | `ontology.yaml > content_types + common_nodes` | ノード MERGE パターン |
| `{{RELATION_DEFINITIONS}}` | `ontology.yaml > relation_types` | リレーション MERGE パターン |
| `{{CONSTRAINT_DEFINITIONS}}` | `schema.yaml > constraints` | UNIQUE 制約定義 |
| `{{INDEX_DEFINITIONS}}` | `schema.yaml > indexes` | インデックス定義 |
| `{{INGESTION_ORDER}}` | `ontology.yaml > relation_types` の依存関係から算出 | 投入順序 |
| `{{VERIFICATION_QUERIES}}` | content_types + relation_types から生成 | 投入検証クエリ |

---

## 制約・インデックスセクション

```cypher
-- =================================================================
-- {{INSTANCE_NAME}} 制約・インデックス (schema_version: {{SCHEMA_VERSION}})
-- =================================================================

{{CONSTRAINT_DEFINITIONS}}

-- ================================================================
-- Phase B 埋め込み手順:
-- schema.yaml > constraints から UNIQUE 制約を生成する。
-- 各ノードの key_property に対して1つの制約を作成。
--
-- --- creator v2 参考例 ---
-- CREATE CONSTRAINT unique_creator_concept_category_name IF NOT EXISTS
--   FOR (cc:ConceptCategory) REQUIRE cc.name IS UNIQUE;
-- CREATE CONSTRAINT unique_creator_concept_id IF NOT EXISTS
--   FOR (c:Concept) REQUIRE c.concept_id IS UNIQUE;
-- CREATE CONSTRAINT unique_creator_concept_name IF NOT EXISTS
--   FOR (c:Concept) REQUIRE c.name IS UNIQUE;
-- CREATE CONSTRAINT unique_creator_domain_name IF NOT EXISTS
--   FOR (d:Domain) REQUIRE d.name IS UNIQUE;
-- CREATE CONSTRAINT unique_creator_alias_value IF NOT EXISTS
--   FOR (a:Alias) REQUIRE a.value IS UNIQUE;
--
-- --- research v2 参考例 ---
-- CREATE CONSTRAINT unique_source_id IF NOT EXISTS
--   FOR (s:Source) REQUIRE s.source_id IS UNIQUE;
-- CREATE CONSTRAINT unique_topic_id IF NOT EXISTS
--   FOR (t:Topic) REQUIRE t.topic_id IS UNIQUE;
-- CREATE CONSTRAINT unique_entity_id IF NOT EXISTS
--   FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE;
-- CREATE CONSTRAINT unique_entity_key IF NOT EXISTS
--   FOR (e:Entity) REQUIRE e.entity_key IS UNIQUE;
-- CREATE CONSTRAINT unique_claim_id IF NOT EXISTS
--   FOR (c:Claim) REQUIRE c.claim_id IS UNIQUE;
-- CREATE CONSTRAINT unique_fact_id IF NOT EXISTS
--   FOR (f:Fact) REQUIRE f.fact_id IS UNIQUE;
-- CREATE CONSTRAINT unique_chunk_id IF NOT EXISTS
--   FOR (ch:Chunk) REQUIRE ch.chunk_id IS UNIQUE;
-- ================================================================

{{INDEX_DEFINITIONS}}

-- ================================================================
-- Phase B 埋め込み手順:
-- schema.yaml > indexes からインデックスを生成する。
-- Full-Text Index と通常の B-Tree Index の両方を含む。
--
-- --- creator v2 参考例 ---
-- CREATE FULLTEXT INDEX entity_fulltext IF NOT EXISTS
--   FOR (e:Entity) ON EACH [e.name];
-- CREATE FULLTEXT INDEX concept_fulltext IF NOT EXISTS
--   FOR (c:Concept) ON EACH [c.name];
-- CREATE FULLTEXT INDEX alias_fulltext IF NOT EXISTS
--   FOR (a:Alias) ON EACH [a.value];
-- CREATE INDEX idx_creator_concept_category_layer IF NOT EXISTS
--   FOR (cc:ConceptCategory) ON (cc.layer);
--
-- --- research v2 参考例 ---
-- CREATE FULLTEXT INDEX entity_fulltext IF NOT EXISTS
--   FOR (e:Entity) ON EACH [e.name];
-- CREATE INDEX idx_topic_category IF NOT EXISTS
--   FOR (t:Topic) ON (t.category);
-- ================================================================
```

---

## ノード MERGE パターン

{{NODE_DEFINITIONS}}

<!-- ================================================================
  Phase B 埋め込み手順:
  ontology.yaml > content_types + common_nodes から各ノードの
  MERGE パターンを生成する。

  生成ルール:
  1. common_nodes (Source, Entity) は常に含める
  2. content_types の各 label に対して MERGE パターンを生成
  3. concept_categories が定義されている場合は ConceptCategory ノードを追加
  4. key_property を MERGE キーとして使用
  5. required_properties は SET 句に含める
  6. optional_properties は CASE/coalesce でガード

  --- 汎用パターン ---

  ### {LABEL} ノード

  ```cypher
  UNWIND ${param_name} AS row
  MERGE (n:{LABEL} {{key_property}: row.{key_property}})
  ON CREATE SET n.created_at = datetime()
  SET n.{prop1} = row.{prop1},
      n.{prop2} = row.{prop2},
      n.updated_at = datetime()
  ```

  --- creator v2 参考例 ---

  ### ConceptCategory

  ```cypher
  UNWIND $categories AS row
  MERGE (cc:ConceptCategory {name: row.name})
  SET cc.name_ja = row.name_ja,
      cc.layer = row.layer,
      cc.created_at = coalesce(cc.created_at, datetime())
  ```

  ### Concept

  ```cypher
  UNWIND $concepts AS row
  MERGE (c:Concept {concept_id: row.concept_id})
  SET c.name = row.name,
      c.created_at = coalesce(c.created_at, datetime()),
      c.updated_at = datetime()
  ```

  ### Entity

  ```cypher
  UNWIND $entities AS row
  MERGE (e:Entity {entity_key: row.entity_key})
  ON CREATE SET e.entity_id = row.entity_id,
                e.created_at = datetime()
  SET e.name = row.name,
      e.entity_type = row.entity_type,
      e.updated_at = datetime()
  ```

  ### Source

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

  ### Fact

  ```cypher
  UNWIND $facts AS row
  MERGE (f:Fact {fact_id: row.fact_id})
  SET f.text = row.text,
      f.category = row.category,
      f.confidence = row.confidence,
      f.created_at = coalesce(f.created_at, datetime())
  ```

  --- research v2 参考例 ---

  ### Topic

  ```cypher
  UNWIND $topics AS row
  MERGE (t:Topic {topic_key: row.topic_key})
  ON CREATE SET t.topic_id = row.topic_id,
                t.created_at = datetime()
  SET t.name = row.name,
      t.category = row.category
  ```

  ### Chunk

  ```cypher
  UNWIND $chunks AS row
  MERGE (ch:Chunk {chunk_id: row.chunk_id})
  SET ch.text = row.text,
      ch.chunk_index = row.chunk_index,
      ch.token_count = row.token_count,
      ch.created_at = coalesce(ch.created_at, datetime())
  ```

  ### Claim

  ```cypher
  UNWIND $claims AS row
  MERGE (c:Claim {claim_id: row.claim_id})
  SET c.content = row.content,
      c.claim_type = row.claim_type,
      c.stance = row.stance,
      c.created_at = coalesce(c.created_at, datetime())
  ```
  ================================================================ -->

---

## リレーション MERGE パターン

{{RELATION_DEFINITIONS}}

<!-- ================================================================
  Phase B 埋め込み手順:
  ontology.yaml > relation_types から各リレーションの
  MERGE パターンを生成する。

  生成ルール:
  1. from_label と to_label の key_property を MATCH キーとして使用
  2. properties がある場合は SET 句に含める
  3. UNWIND + MATCH + MERGE の3行パターンを基本とする
  4. from_label が "[A|B|C]" 形式の場合は各ラベルごとに個別クエリを生成

  --- 汎用パターン ---

  ### {REL_TYPE}（{FROM_LABEL} → {TO_LABEL}）

  ```cypher
  UNWIND $rels AS row
  MATCH (a:{FROM_LABEL} {{from_key}: row.from_id})
  MATCH (b:{TO_LABEL} {{to_key}: row.to_id})
  MERGE (a)-[r:{REL_TYPE}]->(b)
  SET r.{prop} = row.{prop}  // properties がある場合のみ
  ```

  --- creator v2 参考例 ---

  ### IS_A（Concept → ConceptCategory）

  ```cypher
  UNWIND $rels AS row
  MATCH (c:Concept {concept_id: row.from_id})
  MATCH (cc:ConceptCategory {name: row.to_id})
  MERGE (c)-[:IS_A]->(cc)
  ```

  ### SERVES_AS（Entity → Concept）

  ```cypher
  UNWIND $rels AS row
  MATCH (e:Entity {entity_id: row.from_id})
  MATCH (c:Concept {concept_id: row.to_id})
  MERGE (e)-[r:SERVES_AS]->(c)
  SET r.context = row.context
  ```

  ### ABOUT（Fact → Concept）

  ```cypher
  UNWIND $rels AS row
  MATCH (f:Fact {fact_id: row.from_id})
  MATCH (c:Concept {concept_id: row.to_id})
  MERGE (f)-[:ABOUT]->(c)
  ```

  ### MENTIONS（Fact → Entity）

  ```cypher
  UNWIND $rels AS row
  MATCH (f:Fact {fact_id: row.from_id})
  MATCH (e:Entity {entity_id: row.to_id})
  MERGE (f)-[:MENTIONS]->(e)
  ```

  ### FROM_SOURCE（Fact → Source）

  ```cypher
  UNWIND $rels AS row
  MATCH (f:Fact {fact_id: row.from_id})
  MATCH (s:Source {source_id: row.to_id})
  MERGE (f)-[:FROM_SOURCE]->(s)
  ```

  --- research v2 参考例 ---

  ### TAGGED（Source → Topic）

  ```cypher
  UNWIND $rels AS row
  MATCH (s:Source {source_id: row.from_id})
  MATCH (t:Topic {topic_key: row.to_id})
  MERGE (s)-[:TAGGED]->(t)
  ```

  ### RELATES_TO（Fact → Entity）

  ```cypher
  UNWIND $rels AS row
  MATCH (f:Fact {fact_id: row.from_id})
  MATCH (e:Entity {entity_key: row.to_id})
  MERGE (f)-[:RELATES_TO]->(e)
  ```

  ### CONTAINS_CHUNK（Source → Chunk）

  ```cypher
  UNWIND $rels AS row
  MATCH (s:Source {source_id: row.from_id})
  MATCH (ch:Chunk {chunk_id: row.to_id})
  MERGE (s)-[:CONTAINS_CHUNK]->(ch)
  ```

  ### EXTRACTED_FROM（Fact → Chunk）

  ```cypher
  UNWIND $rels AS row
  MATCH (f:Fact {fact_id: row.from_id})
  MATCH (ch:Chunk {chunk_id: row.to_id})
  MERGE (f)-[:EXTRACTED_FROM]->(ch)
  ```
  ================================================================ -->

---

## 投入順序

{{INGESTION_ORDER}}

<!-- ================================================================
  Phase B 埋め込み手順:
  relation_types の依存関係から投入順序を算出する。

  アルゴリズム:
  1. 全ノードラベルを収集
  2. 依存グラフを構築（リレーションの to_label が from_label に依存）
  3. トポロジカルソートで投入順序を決定
  4. Phase 2（ノード投入）→ Phase 3（リレーション投入）の2段階

  --- creator v2 参考例 ---
  Phase 2: ノード投入
    1. Genre（固定マスタ）
    2. ConceptCategory（固定マスタ）
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

  --- research v2 参考例 ---
  Phase 2: ノード投入
    1. Topic
    2. Entity
    3. Source
    4. Author
    5. Chunk
    6. Fact
    7. Claim
    8. FinancialDataPoint
    9. FiscalPeriod

  Phase 3: リレーション投入
    1. TAGGED (Source → Topic)
    2. AUTHORED_BY (Source → Author)
    3. CONTAINS_CHUNK (Source → Chunk)
    4. EXTRACTED_FROM (Fact/Claim → Chunk)
    5. STATES_FACT (Source → Fact)
    6. MAKES_CLAIM (Source → Claim)
    7. RELATES_TO (Fact/FinancialDataPoint → Entity)
    8. HAS_DATAPOINT (Source → FinancialDataPoint)
    9. FOR_PERIOD (FinancialDataPoint → FiscalPeriod)
  ================================================================ -->

---

## 投入検証クエリ

{{VERIFICATION_QUERIES}}

<!-- ================================================================
  Phase B 埋め込み手順:
  content_types + relation_types から投入検証クエリを生成する。

  生成ルール:
  1. 各ノードラベルの件数カウント
  2. 必須リレーションの接続率チェック
  3. 孤立ノード（リレーションなし）の検出

  --- 汎用パターン ---

  ### ノード数確認

  ```cypher
  MATCH (n)
  WHERE NOT 'Memory' IN labels(n)
  RETURN labels(n)[0] AS label, count(n) AS cnt
  ORDER BY cnt DESC
  ```

  ### 孤立コンテンツ検出

  ```cypher
  MATCH (n:{CONTENT_LABEL})
  WHERE NOT (n)-[:{REQUIRED_REL}]->()
  RETURN count(n) AS orphan_count
  ```

  --- creator v2 参考例 ---

  // 孤立コンテンツ（ABOUT なし）
  MATCH (n) WHERE (n:Fact OR n:Tip OR n:Story) AND NOT (n)-[:ABOUT]->()
  RETURN count(n) AS orphan_content

  // IS_A なし Concept
  MATCH (c:Concept) WHERE NOT (c)-[:IS_A]->()
  RETURN count(c) AS unclassified_concepts

  // FROM_DOMAIN なし Source
  MATCH (s:Source) WHERE NOT (s)-[:FROM_DOMAIN]->()
  RETURN count(s) AS no_domain_sources

  --- research v2 参考例 ---

  // 孤立 Fact（RELATES_TO なし）
  MATCH (f:Fact)
  WHERE NOT 'Memory' IN labels(f)
  AND NOT (f)-[:RELATES_TO]->()
  RETURN count(f) AS orphan_facts

  // TAGGED なし Source
  MATCH (s:Source)
  WHERE NOT 'Memory' IN labels(s)
  AND NOT (s)-[:TAGGED]->()
  RETURN count(s) AS untagged_sources

  // EXTRACTED_FROM なし Fact
  MATCH (f:Fact)
  WHERE NOT 'Memory' IN labels(f)
  AND NOT (f)-[:EXTRACTED_FROM]->()
  RETURN count(f) AS no_chunk_facts
  ================================================================ -->

---

## 冪等性の仕組み

全 MERGE クエリは冪等性を保証する。同一データを複数回投入しても副作用がない。

### ノード投入

- `MERGE` は `key_property` でマッチし、存在すれば `SET` でプロパティを更新
- `ON CREATE SET` で作成時のみ設定するプロパティ（`created_at` 等）を分離
- `coalesce()` で既存値を保持しつつ新規時にデフォルト値を設定

### リレーション投入

- `MATCH` + `MERGE` パターンで既存リレーションを再作成しない
- `MATCH` でノードが見つからない場合はリレーションが作成されない（安全）
- `SET` で上書き可能なプロパティのみリレーションに持たせる

### エラーハンドリング

- ノード MERGE 失敗: UNIQUE 制約違反 → key_property の重複を調査
- リレーション MERGE 失敗: MATCH で片方のノードが見つからない → 投入順序を確認
- 部分的投入: トランザクション単位で UNWIND → 1バッチ内の失敗は全ロールバック

---

## MERGE パターン生成ロジック

Phase B-4 でオーケストレーターが実行する変換ロジック。

### ノード MERGE パターン生成

```python
def generate_node_merge(node_def: dict) -> str:
    """ontology.yaml のノード定義から MERGE Cypher を生成する。"""
    label = node_def["label"]
    key_prop = node_def["key_property"]
    required = node_def.get("required_properties", [])
    optional = node_def.get("optional_properties", [])

    param_name = label.lower() + "s"  # 例: "facts", "sources"

    lines = [
        f"UNWIND ${param_name} AS row",
        f"MERGE (n:{label} {{{key_prop}: row.{key_prop}}})",
        f"ON CREATE SET n.created_at = datetime()",
    ]

    set_props = [p for p in required if p != key_prop]
    set_props += optional
    if set_props:
        set_lines = [f"    n.{p} = row.{p}" for p in set_props]
        set_lines.append("    n.updated_at = datetime()")
        lines.append("SET " + ",\n".join(set_lines))

    return "\n".join(lines)
```

### リレーション MERGE パターン生成

```python
def generate_rel_merge(rel_def: dict, ontology: dict) -> str:
    """ontology.yaml のリレーション定義から MERGE Cypher を生成する。"""
    rel_type = rel_def["type"]
    from_label = rel_def["from_label"]
    to_label = rel_def["to_label"]
    properties = rel_def.get("properties", [])

    # key_property をノード定義から取得
    from_key = get_key_property(ontology, from_label)
    to_key = get_key_property(ontology, to_label)

    lines = [
        "UNWIND $rels AS row",
        f"MATCH (a:{from_label} {{{from_key}: row.from_id}})",
        f"MATCH (b:{to_label} {{{to_key}: row.to_id}})",
        f"MERGE (a)-[r:{rel_type}]->(b)",
    ]

    if properties:
        set_lines = [f"r.{p} = row.{p}" for p in properties]
        lines.append("SET " + ", ".join(set_lines))

    return "\n".join(lines)
```
