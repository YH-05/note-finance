# Quality Queries Template

neo4j-lifecycle Phase D で使用する品質検証クエリテンプレート。
`ontology-template.yaml` の確定値を埋め込んで、インスタンス固有の品質検証クエリセットを生成する。

## Phase D での埋め込み手順

1. `data/lifecycle-state/{instance}/ontology.yaml` を読み込む
2. 以下のプレースホルダーをインスタンス固有の値で置換する
3. 生成されたクエリセットを `data/lifecycle-state/{instance}/quality-queries.md` として保存する
4. Phase D の自動実行時にこのクエリセットを順次実行する

## プレースホルダー一覧

| プレースホルダー | ソース | 説明 |
|-----------------|--------|------|
| `{{CONTENT_LABELS}}` | `ontology.yaml > content_types[].label` | コンテンツノードラベルのリスト |
| `{{CONTENT_LABEL_FILTER}}` | content_types から生成 | `n:Fact OR n:Tip OR n:Story` 形式 |
| `{{ENTITY_LABEL}}` | 固定: `Entity` | エンティティノードラベル |
| `{{SOURCE_LABEL}}` | 固定: `Source` | ソースノードラベル |
| `{{CONCEPT_LABEL}}` | `ontology.yaml` から判定 | `Concept` or `Topic` |
| `{{CATEGORY_LABEL}}` | `ontology.yaml` から判定 | `ConceptCategory` or なし |
| `{{CONTENT_TO_CONCEPT_REL}}` | `ontology.yaml > relation_types` | `ABOUT` or `TAGGED` |
| `{{CONTENT_TO_ENTITY_REL}}` | `ontology.yaml > relation_types` | `MENTIONS` or `RELATES_TO` |
| `{{CONTENT_TO_SOURCE_REL}}` | `ontology.yaml > relation_types` | `FROM_SOURCE` or `STATES_FACT` |
| `{{CONCEPT_TO_CATEGORY_REL}}` | `ontology.yaml > relation_types` | `IS_A` or なし |
| `{{CATEGORY_NAMES}}` | `ontology.yaml > concept_categories[].name` | カテゴリ名リスト |
| `{{ENTITY_TYPES}}` | `ontology.yaml > entity_types[].key` | entity_type の enum 値 |
| `{{MEMORY_FILTER}}` | 固定 | `NOT 'Memory' IN labels(n)` |

---

## D-1: オントロジー適合検証

スキーマに定義されたルールに対する適合度を検証する。

### D-1-1: 未分類コンテンツ（コンセプト接続なし）

```cypher
-- ================================================================
-- {{CONTENT_TO_CONCEPT_REL}} リレーションを持たないコンテンツノードを検出。
-- 全コンテンツは最低1つの Concept/Topic と接続すべき。
--
-- Phase D 埋め込み手順:
--   {{CONTENT_LABEL_FILTER}} を ontology.yaml > content_types から生成
--   {{CONTENT_TO_CONCEPT_REL}} を relation_types から取得
--   {{CONCEPT_LABEL}} を "Concept" or "Topic" に置換
--
-- --- creator v2 参考例 (creator-neo4j 固有: RELATES_TO → Concept) ---
-- MATCH (n) WHERE (n:Fact OR n:Tip OR n:Story)
-- AND NOT (n)-[:RELATES_TO]->(:Concept)
-- RETURN labels(n)[0] AS label, count(n) AS orphan_count
--
-- --- research v4 参考例 ---
-- MATCH (n) WHERE (n:Fact OR n:Claim)
-- AND NOT 'Memory' IN labels(n)
-- AND NOT (n)-[:RELATES_TO]->(:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product)
-- RETURN labels(n)[0] AS label, count(n) AS orphan_count
-- ================================================================

MATCH (n)
WHERE ({{CONTENT_LABEL_FILTER}})
AND {{MEMORY_FILTER}}
AND NOT (n)-[:{{CONTENT_TO_CONCEPT_REL}}]->(: {{CONCEPT_LABEL}})
RETURN labels(n)[0] AS label, count(n) AS orphan_count
ORDER BY orphan_count DESC
```

### D-1-2: ソース接続なしコンテンツ

```cypher
-- ================================================================
-- ソースへの接続を持たないコンテンツノードを検出。
-- トレーサビリティの確保のため、全コンテンツはソースと接続すべき。
--
-- --- creator v2 参考例 ---
-- MATCH (n) WHERE (n:Fact OR n:Tip OR n:Story)
-- AND NOT (n)-[:FROM_SOURCE]->(:Source)
-- RETURN labels(n)[0] AS label, count(n) AS no_source_count
--
-- --- research v2 参考例 ---
-- MATCH (f:Fact)
-- WHERE NOT 'Memory' IN labels(f)
-- AND NOT (f)<-[:STATES_FACT]-(:Source)
-- AND NOT (f)-[:EXTRACTED_FROM]->(:Chunk)
-- RETURN count(f) AS no_provenance_facts
-- ================================================================

MATCH (n)
WHERE ({{CONTENT_LABEL_FILTER}})
AND {{MEMORY_FILTER}}
AND NOT (n)-[:{{CONTENT_TO_SOURCE_REL}}]->(: {{SOURCE_LABEL}})
RETURN labels(n)[0] AS label, count(n) AS no_source_count
ORDER BY no_source_count DESC
```

### D-1-3: 未分類 Concept/Topic（カテゴリ接続なし）

```cypher
-- ================================================================
-- ConceptCategory への IS_A 接続を持たない Concept を検出。
-- ontology.yaml で concept_categories が定義されている場合のみ実行。
-- concept_categories が未定義（research v2 等）の場合はスキップ。
--
-- --- creator v2 参考例 ---
-- MATCH (c:Concept) WHERE NOT (c)-[:IS_A]->(:ConceptCategory)
-- RETURN c.name AS concept_name, count(*) AS cnt
--
-- --- research v2 参考例 ---
-- Topic の category プロパティが null のものを検出
-- MATCH (t:Topic)
-- WHERE NOT 'Memory' IN labels(t)
-- AND t.category IS NULL
-- RETURN t.name AS topic_name
-- ================================================================

-- ConceptCategory が存在する場合:
MATCH (c:{{CONCEPT_LABEL}})
WHERE {{MEMORY_FILTER}}
AND NOT (c)-[:{{CONCEPT_TO_CATEGORY_REL}}]->(: {{CATEGORY_LABEL}})
RETURN c.name AS name, count(*) AS cnt

-- ConceptCategory が存在しない場合（category プロパティで代替）:
-- MATCH (t:{{CONCEPT_LABEL}})
-- WHERE {{MEMORY_FILTER}}
-- AND t.category IS NULL
-- RETURN t.name AS name
```

### D-1-4: 不正な entity_type

```cypher
-- ================================================================
-- ontology.yaml に定義されていない entity_type を持つ Entity を検出。
--
-- Phase D 埋め込み手順:
--   {{ENTITY_TYPES}} を ontology.yaml > entity_types[].key のリストに置換
--
-- --- creator v2 参考例 (creator-neo4j 固有: Entity ラベルを維持) ---
-- MATCH (e:Company|Technology|Organization|Person)
-- WHERE NOT labels(e)[0] IN ['Platform', 'Company', 'Person', 'Organization']
-- RETURN labels(e)[0] AS invalid_label, count(e) AS cnt
--
-- --- research v4 参考例 (v4.0: entity_type 廃止 → ラベルで判定) ---
-- MATCH (e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product)
-- WHERE NOT 'Memory' IN labels(e)
-- RETURN labels(e)[0] AS label, count(e) AS cnt
-- ORDER BY cnt DESC
-- ================================================================

MATCH (e:{{ENTITY_LABEL}})
WHERE {{MEMORY_FILTER}}
AND NOT e.entity_type IN [{{ENTITY_TYPES}}]
RETURN e.entity_type AS invalid_type, count(e) AS cnt
ORDER BY cnt DESC
```

---

## D-2: 重複検出・マージ

名前が類似する Entity/Concept を検出し、マージ候補を提示する。

### D-2-1: 完全一致重複（名前の正規化ずれ）

```cypher
-- ================================================================
-- 大文字小文字・全角半角の違いによる重複を検出。
--
-- --- 汎用パターン ---
-- toLower() で正規化して GROUP BY し、2件以上のグループを抽出。
-- ================================================================

MATCH (e:{{ENTITY_LABEL}})
WHERE {{MEMORY_FILTER}}
WITH toLower(trim(e.name)) AS normalized, collect(e) AS nodes
WHERE size(nodes) > 1
RETURN normalized,
       size(nodes) AS duplicate_count,
       [n IN nodes | n.name] AS variants,
       [n IN nodes | n.entity_type] AS types
ORDER BY duplicate_count DESC
LIMIT 20
```

### D-2-2: 部分一致重複（略称・別名）

```cypher
-- ================================================================
-- APOC 文字列類似度による重複候補検出。
-- APOC が利用可能な場合のみ実行。
--
-- --- 汎用参考例 (v4.0: 個別ラベルで指定) ---
-- MATCH (e1:Company|Organization|Person), (e2:Company|Organization|Person)
-- WHERE e1 <> e2
-- AND apoc.text.jaroWinklerDistance(e1.name, e2.name) > 0.85
-- RETURN e1.name, e2.name, apoc.text.jaroWinklerDistance(e1.name, e2.name) AS similarity
--
-- APOC なしの場合は Full-Text Index で代替:
-- ================================================================

-- APOC 利用可能時:
MATCH (e1:{{ENTITY_LABEL}}), (e2:{{ENTITY_LABEL}})
WHERE {{MEMORY_FILTER}}
AND elementId(e1) < elementId(e2)
AND e1.entity_type = e2.entity_type
AND apoc.text.jaroWinklerDistance(toLower(e1.name), toLower(e2.name)) > 0.85
RETURN e1.name AS name1, e2.name AS name2,
       e1.entity_type AS type,
       apoc.text.jaroWinklerDistance(toLower(e1.name), toLower(e2.name)) AS similarity
ORDER BY similarity DESC
LIMIT 20

-- APOC なし時（Full-Text Index フォールバック）:
-- CALL db.index.fulltext.queryNodes('entity_fulltext', $search_term)
-- YIELD node, score
-- WHERE score > 0.8
-- RETURN node.name, score
```

### D-2-3: Concept/Topic 重複検出

```cypher
-- ================================================================
-- Concept/Topic の名前重複を検出。
--
-- --- creator v2 参考例 ---
-- MATCH (c:Concept)
-- WITH toLower(trim(c.name)) AS normalized, collect(c) AS nodes
-- WHERE size(nodes) > 1
-- RETURN normalized, [n IN nodes | n.concept_id] AS ids
--
-- --- research v2 参考例 ---
-- MATCH (t:Topic)
-- WHERE NOT 'Memory' IN labels(t)
-- WITH toLower(trim(t.name)) AS normalized, collect(t) AS nodes
-- WHERE size(nodes) > 1
-- RETURN normalized, [n IN nodes | {id: n.topic_id, key: n.topic_key}] AS entries
-- ================================================================

MATCH (c:{{CONCEPT_LABEL}})
WHERE {{MEMORY_FILTER}}
WITH toLower(trim(c.name)) AS normalized, collect(c) AS nodes
WHERE size(nodes) > 1
RETURN normalized,
       size(nodes) AS duplicate_count,
       [n IN nodes | n.name] AS variants
ORDER BY duplicate_count DESC
LIMIT 20
```

---

## D-3: 孤立ノード検出

リレーションを1つも持たないノードを検出する。

### D-3-1: 孤立 Entity

```cypher
-- ================================================================
-- どのコンテンツからも参照されていない Entity を検出。
--
-- --- creator v2 参考例 (creator-neo4j 固有: Entity ラベルを維持) ---
-- MATCH (e:Company|Technology|Organization|Person)
-- WHERE NOT (e)<-[:RELATES_TO]-() AND NOT (e)-[:SERVES_AS]->()
-- RETURN e.name, labels(e)[0] AS label
--
-- --- research v4 参考例 ---
-- MATCH (e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product)
-- WHERE NOT 'Memory' IN labels(e)
-- AND NOT (e)<-[:RELATES_TO]-()
-- RETURN e.name, labels(e)[0] AS label
-- ================================================================

MATCH (e:{{ENTITY_LABEL}})
WHERE {{MEMORY_FILTER}}
AND NOT (e)<-[:{{CONTENT_TO_ENTITY_REL}}]-()
RETURN e.name AS entity_name,
       e.entity_type AS entity_type
ORDER BY e.name
LIMIT 50
```

### D-3-2: 孤立 Source

```cypher
-- ================================================================
-- どのコンテンツとも接続されていない Source を検出。
--
-- --- creator v2 参考例 ---
-- MATCH (s:Source) WHERE NOT (s)<-[:FROM_SOURCE]-()
-- RETURN s.url, s.title
--
-- --- research v2 参考例 ---
-- MATCH (s:Source)
-- WHERE NOT 'Memory' IN labels(s)
-- AND NOT (s)-[:STATES_FACT]->() AND NOT (s)-[:MAKES_CLAIM]->()
-- AND NOT (s)-[:TAGGED]->()
-- RETURN s.url, s.title
-- ================================================================

MATCH (s:{{SOURCE_LABEL}})
WHERE {{MEMORY_FILTER}}
AND NOT (s)-[:{{CONTENT_TO_SOURCE_REL}}]->()
RETURN s.url AS source_url,
       s.title AS source_title
ORDER BY s.title
LIMIT 50
```

### D-3-3: 孤立 Concept/Topic

```cypher
-- ================================================================
-- どのコンテンツからも参照されず、カテゴリにも属さない Concept/Topic を検出。
--
-- --- creator v2 参考例 (creator-neo4j 固有: RELATES_TO で代替) ---
-- MATCH (c:Concept)
-- WHERE NOT (c)<-[:RELATES_TO]-() AND NOT (c)-[:IS_A]->()
-- RETURN c.name
--
-- --- research v2 参考例 ---
-- MATCH (t:Topic)
-- WHERE NOT 'Memory' IN labels(t)
-- AND NOT (t)<-[:TAGGED]-()
-- RETURN t.name, t.category
-- ================================================================

MATCH (c:{{CONCEPT_LABEL}})
WHERE {{MEMORY_FILTER}}
AND NOT (c)<-[:{{CONTENT_TO_CONCEPT_REL}}]-()
RETURN c.name AS concept_name
ORDER BY c.name
LIMIT 50
```

### D-3-4: 完全孤立ノード（全ラベル）

```cypher
-- ================================================================
-- リレーションが1つもないノードを全ラベルで検出。
-- 最も基本的な孤立検出クエリ。
-- ================================================================

MATCH (n)
WHERE {{MEMORY_FILTER}}
AND NOT (n)--()
RETURN labels(n)[0] AS label, count(n) AS orphan_count
ORDER BY orphan_count DESC
```

---

## D-4: カバレッジ計測

オントロジーで定義された分類軸に対するデータのカバレッジを計測する。

### D-4-1: ノードラベル別件数

```cypher
-- ================================================================
-- 全ノードのラベル別件数。基本的な健全性チェック。
-- ================================================================

MATCH (n)
WHERE {{MEMORY_FILTER}}
RETURN labels(n)[0] AS label, count(n) AS cnt
ORDER BY cnt DESC
```

### D-4-2: ConceptCategory/Topic カテゴリ別カバレッジ

```cypher
-- ================================================================
-- カテゴリ別のコンテンツ件数マトリクス。
-- ギャップ（コンテンツが少ないカテゴリ）を特定する。
--
-- Phase D 埋め込み手順:
--   ConceptCategory が存在する場合は IS_A リレーション経由
--   Topic category プロパティの場合は直接集計
--
-- --- creator v2 参考例 (creator-neo4j 固有: RELATES_TO で代替) ---
-- MATCH (cc:ConceptCategory)
-- OPTIONAL MATCH (content)-[:RELATES_TO]->(concept:Concept)-[:IS_A]->(cc)
-- WHERE content:Fact OR content:Tip OR content:Story
-- WITH cc.name AS category, cc.layer AS layer, count(DISTINCT content) AS contents
-- RETURN category, layer, contents
-- ORDER BY layer, contents ASC
--
-- --- research v2 参考例 ---
-- MATCH (t:Topic)
-- WHERE NOT 'Memory' IN labels(t) AND t.category IS NOT NULL
-- OPTIONAL MATCH (s:Source)-[:TAGGED]->(t)
-- WITH t.category AS category, count(DISTINCT s) AS source_count, count(DISTINCT t) AS topic_count
-- RETURN category, topic_count, source_count
-- ORDER BY source_count ASC
-- ================================================================

-- ConceptCategory が存在する場合:
MATCH (cc:{{CATEGORY_LABEL}})
OPTIONAL MATCH (content)-[:{{CONTENT_TO_CONCEPT_REL}}]->(concept:{{CONCEPT_LABEL}})-[:{{CONCEPT_TO_CATEGORY_REL}}]->(cc)
WHERE ({{CONTENT_LABEL_FILTER}})
WITH cc.name AS category, count(DISTINCT content) AS content_count
RETURN category, content_count
ORDER BY content_count ASC

-- ConceptCategory が存在しない場合:
-- MATCH (t:{{CONCEPT_LABEL}})
-- WHERE {{MEMORY_FILTER}} AND t.category IS NOT NULL
-- WITH t.category AS category, count(DISTINCT t) AS count
-- RETURN category, count
-- ORDER BY count ASC
```

### D-4-3: entity_type 別分布

```cypher
-- ================================================================
-- entity_type ごとの Entity 件数。偏りを検出する。
-- ================================================================

MATCH (e:{{ENTITY_LABEL}})
WHERE {{MEMORY_FILTER}}
RETURN e.entity_type AS entity_type, count(e) AS cnt
ORDER BY cnt DESC
```

### D-4-4: リレーション種別分布

```cypher
-- ================================================================
-- リレーション種別ごとの件数。期待値とのギャップを検出する。
-- ================================================================

MATCH ()-[r]->()
RETURN type(r) AS rel_type, count(r) AS cnt
ORDER BY cnt DESC
```

### D-4-5: Source 年月別分布

```cypher
-- ================================================================
-- Source の published_at/collected_at の年月別分布。
-- データの時間的カバレッジを確認する。
-- ================================================================

MATCH (s:{{SOURCE_LABEL}})
WHERE {{MEMORY_FILTER}}
AND s.published_at IS NOT NULL
RETURN toString(s.published_at.year) + '-' +
       CASE WHEN s.published_at.month < 10 THEN '0' ELSE '' END +
       toString(s.published_at.month) AS year_month,
       count(s) AS source_count
ORDER BY year_month DESC
LIMIT 24
```

### D-4-6: コンテンツ接続密度

```cypher
-- ================================================================
-- 各コンテンツノードが持つリレーション数の統計（平均・最小・最大）。
-- 接続密度が低いノードはデータ品質の問題を示唆する。
-- ================================================================

MATCH (n)
WHERE ({{CONTENT_LABEL_FILTER}})
AND {{MEMORY_FILTER}}
OPTIONAL MATCH (n)-[r]->()
WITH labels(n)[0] AS label, n, count(r) AS rel_count
RETURN label,
       count(n) AS node_count,
       avg(rel_count) AS avg_rels,
       min(rel_count) AS min_rels,
       max(rel_count) AS max_rels
ORDER BY label
```

---

## 品質スコア算出ロジック

Phase D の実行結果から品質スコアを算出する。

### スコアリング基準

| カテゴリ | 重み | 基準 |
|---------|------|------|
| D-1 オントロジー適合 | 30% | 未分類コンテンツ率、不正 entity_type 率 |
| D-2 重複 | 20% | 完全一致重複率、類似名重複率 |
| D-3 孤立ノード | 25% | 孤立 Entity 率、孤立 Source 率 |
| D-4 カバレッジ | 25% | カテゴリ別偏り（ジニ係数）、接続密度 |

### スコア算出式

```python
def calculate_quality_score(results: dict) -> dict:
    """Phase D の結果から品質スコアを算出する。"""

    # D-1: オントロジー適合（未分類率が低いほど高スコア）
    total_content = results["d1"]["total_content"]
    orphan_content = results["d1"]["orphan_content"]
    d1_score = 1.0 - (orphan_content / max(total_content, 1))

    # D-2: 重複（重複率が低いほど高スコア）
    total_entities = results["d2"]["total_entities"]
    duplicate_entities = results["d2"]["duplicate_entities"]
    d2_score = 1.0 - (duplicate_entities / max(total_entities, 1))

    # D-3: 孤立ノード（孤立率が低いほど高スコア）
    total_nodes = results["d3"]["total_nodes"]
    orphan_nodes = results["d3"]["orphan_nodes"]
    d3_score = 1.0 - (orphan_nodes / max(total_nodes, 1))

    # D-4: カバレッジ（均等分布に近いほど高スコア）
    d4_score = 1.0 - results["d4"]["gini_coefficient"]

    # 加重平均
    overall = (d1_score * 0.30 + d2_score * 0.20 +
               d3_score * 0.25 + d4_score * 0.25)

    return {
        "ontology_conformance": round(d1_score, 3),
        "deduplication": round(d2_score, 3),
        "orphan_detection": round(d3_score, 3),
        "coverage": round(d4_score, 3),
        "overall": round(overall, 3),
        "rating": "A" if overall >= 0.9 else
                  "B" if overall >= 0.7 else
                  "C" if overall >= 0.5 else "D",
    }
```

---

## レポート出力形式

Phase D 完了後に `data/lifecycle-state/{instance}/quality-report-YYYYMMDD.md` として保存。

```markdown
# {{INSTANCE_NAME}} 品質レポート (YYYY-MM-DD)

## Overall Score: X.XX (Rating: A/B/C/D)

| カテゴリ | スコア | 主要な問題 |
|---------|--------|-----------|
| D-1 オントロジー適合 | X.XX | 未分類コンテンツ N件 |
| D-2 重複 | X.XX | 重複候補 N組 |
| D-3 孤立ノード | X.XX | 孤立 Entity N件 |
| D-4 カバレッジ | X.XX | 低カバレッジカテゴリ: X, Y |

## 詳細

### D-1: オントロジー適合
- 未分類コンテンツ: N / M (X%)
- 不正 entity_type: N件
- ...

### D-2: 重複検出
- 完全一致重複: N組
- 類似名重複候補: N組
- マージ推奨ペア: ...

### D-3: 孤立ノード
- 孤立 Entity: N件
- 孤立 Source: N件
- 孤立 Concept/Topic: N件

### D-4: カバレッジ
- カテゴリ別分布: ...
- entity_type 別分布: ...
- 接続密度: 平均 X.X rel/node

## 改善提案

1. ...
2. ...
```
