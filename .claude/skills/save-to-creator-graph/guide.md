# save-to-creator-graph 詳細ガイド

このガイドは、save-to-creator-graph スキルの詳細な MERGE Cypher パターン、制約・インデックス定義、graph-queue フォーマット仕様を説明します。

> **⚠️ /save-to-graph（research-neo4j 専用, bolt://localhost:7688）は使用禁止。creator-neo4j へのデータ投入には必ずこのスキルを使うこと。**

## 目次

1. [接続情報](#接続情報)
2. [初回セットアップ（制約・インデックス）](#初回セットアップ制約インデックス)
3. [graph-queue フォーマット仕様](#graph-queue-フォーマット仕様)
4. [ノード MERGE パターン](#ノード-merge-パターン)
5. [リレーション MERGE パターン](#リレーション-merge-パターン)
6. [バッチ処理（UNWIND）](#バッチ処理unwind)
7. [冪等性の仕組み](#冪等性の仕組み)
8. [エラーハンドリング](#エラーハンドリング)
9. [パイプライン対比表](#パイプライン対比表)

---

## 接続情報

```
NEO4J_URI=bolt://localhost:7689
NEO4J_USER=neo4j
NEO4J_PASSWORD=gomasuke
```

MCP ツール:
- 読み取り: `mcp__neo4j-creator__creator-read_neo4j_cypher`
- 書き込み: `mcp__neo4j-creator__creator-write_neo4j_cypher`
- スキーマ: `mcp__neo4j-creator__creator-get_neo4j_schema`

---

## 初回セットアップ（制約・インデックス）

creator-neo4j に初めて接続する際、または Entity スキーマを追加する際に以下を実行する。
全て `mcp__neo4j-creator__creator-write_neo4j_cypher` で実行。

### UNIQUE 制約の作成（9個）

```cypher
-- Genre ノード制約
CREATE CONSTRAINT unique_creator_genre_id IF NOT EXISTS
  FOR (g:Genre) REQUIRE g.genre_id IS UNIQUE;

-- Topic ノード制約
CREATE CONSTRAINT unique_creator_topic_id IF NOT EXISTS
  FOR (t:Topic) REQUIRE t.topic_id IS UNIQUE;

-- Source ノード制約
CREATE CONSTRAINT unique_creator_source_id IF NOT EXISTS
  FOR (s:Source) REQUIRE s.source_id IS UNIQUE;

-- Entity ノード制約
CREATE CONSTRAINT unique_creator_entity_id IF NOT EXISTS
  FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE;

CREATE CONSTRAINT unique_creator_entity_key IF NOT EXISTS
  FOR (e:Entity) REQUIRE e.entity_key IS UNIQUE;

-- Fact ノード制約
CREATE CONSTRAINT unique_creator_fact_id IF NOT EXISTS
  FOR (f:Fact) REQUIRE f.fact_id IS UNIQUE;

-- Tip ノード制約
CREATE CONSTRAINT unique_creator_tip_id IF NOT EXISTS
  FOR (t:Tip) REQUIRE t.tip_id IS UNIQUE;

-- Story ノード制約
CREATE CONSTRAINT unique_creator_story_id IF NOT EXISTS
  FOR (s:Story) REQUIRE s.story_id IS UNIQUE;
```

### インデックスの作成（2個）

```cypher
-- Entity タイプ検索用
CREATE INDEX idx_creator_entity_type IF NOT EXISTS
  FOR (e:Entity) ON (e.entity_type);

-- Topic のジャンル検索用
CREATE INDEX idx_creator_topic_genre IF NOT EXISTS
  FOR (t:Topic) ON (t.genre_id);
```

### 既存制約確認クエリ

```cypher
SHOW CONSTRAINTS
```

---

## graph-queue フォーマット仕様

### ファイルパス

`.tmp/creator-graph-queue/cq-{timestamp}-{hash8}.json`

### JSON 構造

```json
{
  "schema_version": "creator-1.0",
  "queue_id": "cq-{timestamp}-{hash8}",
  "created_at": "ISO8601",
  "command_source": "creator-enrichment",
  "genre_id": "career",
  "genres": [
    {"genre_id": "career", "name": "転職・副業"}
  ],
  "topics": [
    {"topic_id": "...", "name": "...", "genre_id": "career"}
  ],
  "sources": [
    {
      "source_id": "...",
      "url": "https://...",
      "title": "...",
      "source_type": "web|reddit|blog|report",
      "authority_level": "official|media|blog|social",
      "collected_at": "ISO8601"
    }
  ],
  "entities": [
    {
      "entity_id": "UUID5-based",
      "name": "Webライター",
      "entity_type": "occupation",
      "entity_key": "Webライター::occupation"
    }
  ],
  "facts": [
    {"fact_id": "...", "text": "...", "category": "...", "confidence": "..."}
  ],
  "tips": [
    {"tip_id": "...", "text": "...", "category": "...", "difficulty": "..."}
  ],
  "stories": [
    {"story_id": "...", "text": "...", "outcome": "...", "timeline": "..."}
  ],
  "relations": {
    "in_genre": [{"from_id": "topic_id", "to_id": "genre_id"}],
    "about_fact": [{"from_id": "fact_id", "to_id": "topic_id"}],
    "about_tip": [{"from_id": "tip_id", "to_id": "topic_id"}],
    "about_story": [{"from_id": "story_id", "to_id": "topic_id"}],
    "from_source_fact": [{"from_id": "fact_id", "to_id": "source_id"}],
    "from_source_tip": [{"from_id": "tip_id", "to_id": "source_id"}],
    "from_source_story": [{"from_id": "story_id", "to_id": "source_id"}],
    "mentions_fact": [{"from_id": "fact_id", "to_id": "entity_id"}],
    "mentions_tip": [{"from_id": "tip_id", "to_id": "entity_id"}],
    "mentions_story": [{"from_id": "story_id", "to_id": "entity_id"}],
    "relates_to": [{"from_id": "entity_id", "to_id": "entity_id", "rel_detail": "..."}]
  }
}
```

### 必須キー検証

Phase 1 で以下のキーが存在することを検証:

| キー | 型 | 必須 |
|------|-----|------|
| schema_version | string ("creator-1.0") | Yes |
| queue_id | string | Yes |
| created_at | string (ISO8601) | Yes |
| genres | array | Yes |
| topics | array | Yes |
| sources | array | Yes |
| facts | array | Yes (空配列可) |
| tips | array | Yes (空配列可) |
| stories | array | Yes (空配列可) |
| relations | object | Yes |
| entities | array | No (Entity なしの旧データも許容) |

### ID 生成方式

| ID | 生成方式 | 備考 |
|----|---------|------|
| genre_id | 固定値 | career, beauty-romance, spiritual |
| topic_id | `sha256(f"topic:{slugify(name)}:{genre_id}")[:8]` | |
| source_id | `generate_source_id(url)` | id_generator.py 再利用 |
| entity_id | `generate_entity_id(name, type)` | id_generator.py 再利用。research-neo4j と同一ID |
| entity_key | `{name}::{entity_type}` | MERGE キー |
| fact_id | `fact-{sha256(text)[:8]}` | コンテンツベースハッシュ |
| tip_id | `tip-{sha256(text)[:8]}` | 同上 |
| story_id | `story-{sha256(text)[:8]}` | 同上 |
| queue_id | `cq-{timestamp}-{rand8}` | |

---

## ノード MERGE パターン

全て `mcp__neo4j-creator__creator-write_neo4j_cypher` で実行する。

### Genre ノード（3固定）

```cypher
MERGE (g:Genre {genre_id: $genre_id})
SET g.name = $name
```

パラメータ例:
```json
{"genre_id": "career", "name": "転職・副業"}
{"genre_id": "beauty-romance", "name": "美容・恋愛"}
{"genre_id": "spiritual", "name": "占い・スピリチュアル"}
```

Genre は 3 固定ノード。初回投入時のみ実行し、以降はスキップ可能（MERGE により冪等）。

### Topic ノード

```cypher
MERGE (t:Topic {topic_id: $topic_id})
SET t.name = $name,
    t.genre_id = $genre_id,
    t.updated_at = datetime()
```

パラメータ例:
```json
{"topic_id": "a1b2c3d4", "name": "フリーランス収入", "genre_id": "career"}
```

### Source ノード

```cypher
MERGE (s:Source {source_id: $source_id})
SET s.url = $url,
    s.title = $title,
    s.source_type = $source_type,
    s.authority_level = $authority_level,
    s.collected_at = datetime($collected_at)
```

パラメータ例:
```json
{
  "source_id": "src-abc12345",
  "url": "https://example.com/article",
  "title": "副業で月5万円を稼ぐ方法",
  "source_type": "web",
  "authority_level": "blog",
  "collected_at": "2026-03-22T14:00:00+09:00"
}
```

### Entity ノード（KG v2 準拠）

```cypher
MERGE (e:Entity {entity_key: $entity_key})
ON CREATE SET e.entity_id = $entity_id,
              e.created_at = datetime()
SET e.name = $name,
    e.entity_type = $entity_type,
    e.updated_at = datetime()
```

パラメータ例:
```json
{
  "entity_key": "Webライター::occupation",
  "entity_id": "UUID5-based-id",
  "name": "Webライター",
  "entity_type": "occupation"
}
```

**entity_type 許可値**: `person`, `company`, `platform`, `service`, `occupation`, `technique`, `metric`, `product`, `concept`

MERGE キーは `entity_key`（`{name}::{entity_type}` 形式）。`entity_id` は ON CREATE のみで設定し、既存ノードの ID は変更しない。

### Fact ノード

```cypher
MERGE (f:Fact {fact_id: $fact_id})
SET f.text = $text,
    f.category = $category,
    f.confidence = $confidence,
    f.created_at = datetime()
```

パラメータ例:
```json
{
  "fact_id": "fact-e3f4a5b6",
  "text": "フリーランスの平均年収は600万円（2026年調査）",
  "category": "statistics",
  "confidence": "high"
}
```

**category 許可値**: `statistics`, `market_data`, `research`, `trend`
**confidence 許可値**: `high`, `medium`, `low`

### Tip ノード

```cypher
MERGE (t:Tip {tip_id: $tip_id})
SET t.text = $text,
    t.category = $category,
    t.difficulty = $difficulty,
    t.created_at = datetime()
```

パラメータ例:
```json
{
  "tip_id": "tip-d2c3b4a5",
  "text": "副業開始3ヶ月は収益よりスキル構築に集中する",
  "category": "strategy",
  "difficulty": "beginner"
}
```

**category 許可値**: `strategy`, `tool`, `process`, `mindset`
**difficulty 許可値**: `beginner`, `intermediate`, `advanced`

### Story ノード

```cypher
MERGE (s:Story {story_id: $story_id})
SET s.text = $text,
    s.outcome = $outcome,
    s.timeline = $timeline,
    s.created_at = datetime()
```

パラメータ例:
```json
{
  "story_id": "story-f1e2d3c4",
  "text": "IT未経験から副業Webライターで月10万円達成した体験談",
  "outcome": "success",
  "timeline": "3ヶ月"
}
```

**outcome 許可値**: `success`, `failure`, `mixed`, `ongoing`

---

## リレーション MERGE パターン

全て `mcp__neo4j-creator__creator-write_neo4j_cypher` で実行する。

### IN_GENRE（Topic → Genre）

```cypher
MATCH (t:Topic {topic_id: $from_id})
MATCH (g:Genre {genre_id: $to_id})
MERGE (t)-[:IN_GENRE]->(g)
```

### ABOUT（Fact → Topic）

```cypher
MATCH (f:Fact {fact_id: $from_id})
MATCH (t:Topic {topic_id: $to_id})
MERGE (f)-[:ABOUT]->(t)
```

### ABOUT（Tip → Topic）

```cypher
MATCH (tip:Tip {tip_id: $from_id})
MATCH (t:Topic {topic_id: $to_id})
MERGE (tip)-[:ABOUT]->(t)
```

### ABOUT（Story → Topic）

```cypher
MATCH (s:Story {story_id: $from_id})
MATCH (t:Topic {topic_id: $to_id})
MERGE (s)-[:ABOUT]->(t)
```

### FROM_SOURCE（Fact → Source）

```cypher
MATCH (f:Fact {fact_id: $from_id})
MATCH (s:Source {source_id: $to_id})
MERGE (f)-[:FROM_SOURCE]->(s)
```

### FROM_SOURCE（Tip → Source）

```cypher
MATCH (tip:Tip {tip_id: $from_id})
MATCH (s:Source {source_id: $to_id})
MERGE (tip)-[:FROM_SOURCE]->(s)
```

### FROM_SOURCE（Story → Source）

```cypher
MATCH (st:Story {story_id: $from_id})
MATCH (s:Source {source_id: $to_id})
MERGE (st)-[:FROM_SOURCE]->(s)
```

### MENTIONS（Fact → Entity）

```cypher
MATCH (f:Fact {fact_id: $from_id})
MATCH (e:Entity {entity_id: $to_id})
MERGE (f)-[:MENTIONS]->(e)
```

### MENTIONS（Tip → Entity）

```cypher
MATCH (tip:Tip {tip_id: $from_id})
MATCH (e:Entity {entity_id: $to_id})
MERGE (tip)-[:MENTIONS]->(e)
```

### MENTIONS（Story → Entity）

```cypher
MATCH (st:Story {story_id: $from_id})
MATCH (e:Entity {entity_id: $to_id})
MERGE (st)-[:MENTIONS]->(e)
```

### RELATES_TO（Entity → Entity）

```cypher
MATCH (e1:Entity {entity_id: $from_id})
MATCH (e2:Entity {entity_id: $to_id})
MERGE (e1)-[r:RELATES_TO]->(e2)
SET r.rel_detail = $rel_detail
```

パラメータ例:
```json
{
  "from_id": "entity-uuid5-webwriter",
  "to_id": "entity-uuid5-crowdworks",
  "rel_detail": "主要な案件獲得プラットフォーム"
}
```

---

## バッチ処理（UNWIND）

複数のノードやリレーションを一括投入する場合は UNWIND パターンを使用する。
MCP ツールでは Cypher 文字列内にパラメータを埋め込む必要があるため、リテラルリストを UNWIND に渡す。

### Topic ノードのバッチ MERGE

```cypher
UNWIND [
  {topic_id: "a1b2c3d4", name: "フリーランス収入", genre_id: "career"},
  {topic_id: "e5f6g7h8", name: "副業の始め方", genre_id: "career"}
] AS row
MERGE (t:Topic {topic_id: row.topic_id})
SET t.name = row.name,
    t.genre_id = row.genre_id,
    t.updated_at = datetime()
```

### Entity ノードのバッチ MERGE

```cypher
UNWIND [
  {entity_key: "Webライター::occupation", entity_id: "uuid5-1", name: "Webライター", entity_type: "occupation"},
  {entity_key: "クラウドワークス::platform", entity_id: "uuid5-2", name: "クラウドワークス", entity_type: "platform"}
] AS row
MERGE (e:Entity {entity_key: row.entity_key})
ON CREATE SET e.entity_id = row.entity_id,
              e.created_at = datetime()
SET e.name = row.name,
    e.entity_type = row.entity_type,
    e.updated_at = datetime()
```

### Source ノードのバッチ MERGE

```cypher
UNWIND [
  {source_id: "src-abc12345", url: "https://example.com/1", title: "Title 1", source_type: "web", authority_level: "blog", collected_at: "2026-03-22T14:00:00+09:00"}
] AS row
MERGE (s:Source {source_id: row.source_id})
SET s.url = row.url,
    s.title = row.title,
    s.source_type = row.source_type,
    s.authority_level = row.authority_level,
    s.collected_at = datetime(row.collected_at)
```

### Fact ノードのバッチ MERGE

```cypher
UNWIND [
  {fact_id: "fact-e3f4a5b6", text: "...", category: "statistics", confidence: "high"}
] AS row
MERGE (f:Fact {fact_id: row.fact_id})
SET f.text = row.text,
    f.category = row.category,
    f.confidence = row.confidence,
    f.created_at = datetime()
```

### Tip ノードのバッチ MERGE

```cypher
UNWIND [
  {tip_id: "tip-d2c3b4a5", text: "...", category: "strategy", difficulty: "beginner"}
] AS row
MERGE (t:Tip {tip_id: row.tip_id})
SET t.text = row.text,
    t.category = row.category,
    t.difficulty = row.difficulty,
    t.created_at = datetime()
```

### Story ノードのバッチ MERGE

```cypher
UNWIND [
  {story_id: "story-f1e2d3c4", text: "...", outcome: "success", timeline: "3ヶ月"}
] AS row
MERGE (s:Story {story_id: row.story_id})
SET s.text = row.text,
    s.outcome = row.outcome,
    s.timeline = row.timeline,
    s.created_at = datetime()
```

### IN_GENRE リレーションのバッチ MERGE

```cypher
UNWIND [
  {from_id: "a1b2c3d4", to_id: "career"},
  {from_id: "e5f6g7h8", to_id: "career"}
] AS row
MATCH (t:Topic {topic_id: row.from_id})
MATCH (g:Genre {genre_id: row.to_id})
MERGE (t)-[:IN_GENRE]->(g)
```

### ABOUT リレーションのバッチ MERGE（Fact）

```cypher
UNWIND [
  {from_id: "fact-e3f4a5b6", to_id: "a1b2c3d4"}
] AS row
MATCH (f:Fact {fact_id: row.from_id})
MATCH (t:Topic {topic_id: row.to_id})
MERGE (f)-[:ABOUT]->(t)
```

### ABOUT リレーションのバッチ MERGE（Tip）

```cypher
UNWIND [
  {from_id: "tip-d2c3b4a5", to_id: "e5f6g7h8"}
] AS row
MATCH (tip:Tip {tip_id: row.from_id})
MATCH (t:Topic {topic_id: row.to_id})
MERGE (tip)-[:ABOUT]->(t)
```

### ABOUT リレーションのバッチ MERGE（Story）

```cypher
UNWIND [
  {from_id: "story-f1e2d3c4", to_id: "a1b2c3d4"}
] AS row
MATCH (st:Story {story_id: row.from_id})
MATCH (t:Topic {topic_id: row.to_id})
MERGE (st)-[:ABOUT]->(t)
```

### FROM_SOURCE リレーションのバッチ MERGE（Fact）

```cypher
UNWIND [
  {from_id: "fact-e3f4a5b6", to_id: "src-abc12345"}
] AS row
MATCH (f:Fact {fact_id: row.from_id})
MATCH (s:Source {source_id: row.to_id})
MERGE (f)-[:FROM_SOURCE]->(s)
```

### FROM_SOURCE リレーションのバッチ MERGE（Tip）

```cypher
UNWIND [
  {from_id: "tip-d2c3b4a5", to_id: "src-abc12345"}
] AS row
MATCH (tip:Tip {tip_id: row.from_id})
MATCH (s:Source {source_id: row.to_id})
MERGE (tip)-[:FROM_SOURCE]->(s)
```

### FROM_SOURCE リレーションのバッチ MERGE（Story）

```cypher
UNWIND [
  {from_id: "story-f1e2d3c4", to_id: "src-abc12345"}
] AS row
MATCH (st:Story {story_id: row.from_id})
MATCH (s:Source {source_id: row.to_id})
MERGE (st)-[:FROM_SOURCE]->(s)
```

### MENTIONS リレーションのバッチ MERGE（Fact）

```cypher
UNWIND [
  {from_id: "fact-e3f4a5b6", to_id: "entity-uuid5-1"}
] AS row
MATCH (f:Fact {fact_id: row.from_id})
MATCH (e:Entity {entity_id: row.to_id})
MERGE (f)-[:MENTIONS]->(e)
```

### MENTIONS リレーションのバッチ MERGE（Tip）

```cypher
UNWIND [
  {from_id: "tip-d2c3b4a5", to_id: "entity-uuid5-1"}
] AS row
MATCH (tip:Tip {tip_id: row.from_id})
MATCH (e:Entity {entity_id: row.to_id})
MERGE (tip)-[:MENTIONS]->(e)
```

### MENTIONS リレーションのバッチ MERGE（Story）

```cypher
UNWIND [
  {from_id: "story-f1e2d3c4", to_id: "entity-uuid5-1"}
] AS row
MATCH (st:Story {story_id: row.from_id})
MATCH (e:Entity {entity_id: row.to_id})
MERGE (st)-[:MENTIONS]->(e)
```

### RELATES_TO リレーションのバッチ MERGE

```cypher
UNWIND [
  {from_id: "entity-uuid5-1", to_id: "entity-uuid5-2", rel_detail: "主要な案件獲得プラットフォーム"}
] AS row
MATCH (e1:Entity {entity_id: row.from_id})
MATCH (e2:Entity {entity_id: row.to_id})
MERGE (e1)-[r:RELATES_TO]->(e2)
SET r.rel_detail = row.rel_detail
```

### バッチサイズの目安

| ノード/リレーション | 推奨バッチサイズ |
|-------------------|----------------|
| Genre | 3（全件一括） |
| Topic | 20 |
| Source | 20 |
| Entity | 30 |
| Fact / Tip / Story | 20 |
| リレーション全般 | 50 |

バッチサイズが大きすぎると MCP ツールのレスポンスが遅くなる。上記を目安に分割する。

---

## 冪等性の仕組み

全ノード・リレーションは MERGE で投入するため、同一データの再投入は安全。

### ノードの冪等性

- MERGE キー（genre_id, topic_id, source_id, entity_key, fact_id, tip_id, story_id）で一致判定
- 存在すれば SET でプロパティを上書き
- Entity は `entity_key` で MERGE し、`entity_id` は ON CREATE のみで設定（既存ノードの ID は変更しない）

### リレーションの冪等性

- MERGE は同一ペア間のリレーションが重複作成されないことを保証
- RELATES_TO の `rel_detail` は SET で上書き（最新の説明に更新される）

### 再実行時の挙動

```
1回目: MERGE → CREATE（新規作成）
2回目: MERGE → MATCH（既存発見）→ SET（プロパティ更新）
```

---

## エラーハンドリング

### 接続エラー

Phase 1 で `RETURN 1 AS ok` が失敗した場合、スキルを中断する。

確認事項:
```bash
# Docker コンテナ状態
docker ps | grep creator

# ポート確認
lsof -i :7689
```

### ノード投入エラー

- 制約違反（同一 ID で異なる entity_key 等）: エラーログを表示し、該当ノードをスキップ
- 残りのノードは続行

### リレーション投入エラー

- MATCH 失敗（参照先ノード不存在）: 警告を表示し、該当リレーションをスキップ
- Phase 4 の孤立ノード検出で未接続を確認

### graph-queue JSON 不正

- schema_version が "creator-1.0" でない: ファイルスキップ
- 必須キー欠落: ファイルスキップ、エラーログ表示

---

## パイプライン対比表

| | research-neo4j | creator-neo4j |
|---|---|---|
| Neo4j URI | bolt://localhost:7688 | bolt://localhost:7689 |
| emit スクリプト | emit_graph_queue.py | emit_creator_queue.py |
| 中間ファイル | .tmp/graph-queue/ | .tmp/creator-graph-queue/ |
| 投入スキル | /save-to-graph | /save-to-creator-graph |
| MCP write | research-write_neo4j_cypher | creator-write_neo4j_cypher |
| MCP read | research-read_neo4j_cypher | creator-read_neo4j_cypher |
| schema_version | "2.2" | "creator-1.0" |
| Password | (env var) | gomasuke |

**これらは完全に独立したパイプラインであり、混在させてはならない。**
