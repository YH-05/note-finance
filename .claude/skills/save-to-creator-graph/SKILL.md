---
name: save-to-creator-graph
description: creator-graph-queue JSON を読み込み、creator-neo4j にノードとリレーションを MERGE ベースで冪等投入するスキル。5フェーズ構成。Entity/MENTIONS/RELATES_TO対応。
allowed-tools: Read, Bash, Grep, Glob
---

# save-to-creator-graph スキル

creator-graph-queue JSON ファイルを読み込み、**creator-neo4j** (bolt://localhost:7689) にナレッジグラフデータを投入するスキル。
MERGE ベースの Cypher クエリにより冪等性を保証する。

> **⚠️ /save-to-graph（research-neo4j 専用, bolt://localhost:7688）は使用禁止。creator-neo4j へのデータ投入には必ずこのスキルを使うこと。**

## 使用 MCP ツール

- 読み取り: `mcp__neo4j-creator__creator-read_neo4j_cypher`
- 書き込み: `mcp__neo4j-creator__creator-write_neo4j_cypher`
- スキーマ: `mcp__neo4j-creator__creator-get_neo4j_schema`

## 接続情報

- URI: bolt://localhost:7689
- User: neo4j
- Password: gomasuke

## アーキテクチャ

Phase 1: キュー検出・検証
  - creator-neo4j 接続確認（mcp__neo4j-creator__creator-read_neo4j_cypher で RETURN 1）
  - .tmp/creator-graph-queue/ 配下の未処理 JSON を検出
  - JSON スキーマ検証（schema_version: "creator-1.0"、必須キー）

Phase 2: ノード投入（MERGE）
  - Genre ノード MERGE（3固定、初回のみ）
  - Topic ノード MERGE
  - Source ノード MERGE
  - Entity ノード MERGE（entity_key で MERGE）
  - Fact ノード MERGE
  - Tip ノード MERGE
  - Story ノード MERGE

Phase 3: リレーション投入（MERGE）
  - IN_GENRE (Topic → Genre)
  - ABOUT (Fact/Tip/Story → Topic)
  - FROM_SOURCE (Fact/Tip/Story → Source)
  - MENTIONS (Fact/Tip/Story → Entity)
  - RELATES_TO (Entity → Entity)

Phase 4: 投入検証
  - 投入件数の確認（MATCH クエリで created_at >= $cycle_start）
  - 孤立ノードチェック（ABOUT/FROM_SOURCE なしのコンテンツ）
  - MENTIONS なし Entity の警告

Phase 5: 完了処理
  - 処理済みファイルを .tmp/creator-graph-queue/.processed/ に移動
  - 投入サマリーを表示

## 実行手順

### Phase 1: キュー検出・検証

1. ToolSearch で MCP ツールをロード:
   ```
   ToolSearch('+neo4j-creator')
   ```

2. 接続確認:
   ```
   mcp__neo4j-creator__creator-read_neo4j_cypher: "RETURN 1 AS ok"
   ```

3. キューファイル検出:
   ```
   Glob(".tmp/creator-graph-queue/*.json")
   ```
   .processed/ サブディレクトリは除外。

4. 各 JSON ファイルを Read し、schema_version が "creator-1.0" であることを確認。

### Phase 2: ノード投入

guide.md の MERGE パターンに従い、各ノードタイプを順番に投入。
全て `mcp__neo4j-creator__creator-write_neo4j_cypher` を使用。

投入順序（依存関係順）:
1. Genre（genre_id で MERGE）
2. Topic（topic_id で MERGE）→ IN_GENRE は Phase 3
3. Source（source_id で MERGE）
4. Entity（entity_key で MERGE）
5. Fact（fact_id で MERGE）
6. Tip（tip_id で MERGE）
7. Story（story_id で MERGE）

### Phase 3: リレーション投入

guide.md のリレーション MERGE パターンに従い投入。

投入順序:
1. IN_GENRE（Topic → Genre）
2. ABOUT（Fact → Topic, Tip → Topic, Story → Topic）
3. FROM_SOURCE（Fact → Source, Tip → Source, Story → Source）
4. MENTIONS（Fact → Entity, Tip → Entity, Story → Entity）
5. RELATES_TO（Entity → Entity）

### Phase 4: 投入検証

```cypher
-- 投入件数確認
MATCH (n)
WHERE n.created_at >= datetime($cycle_start) OR n.updated_at >= datetime($cycle_start)
RETURN labels(n)[0] AS label, count(n) AS cnt
ORDER BY cnt DESC

-- 孤立コンテンツ検出
MATCH (n) WHERE (n:Fact OR n:Tip OR n:Story) AND NOT (n)-[:ABOUT]->() RETURN count(n) AS orphan_content

-- MENTIONS なし Entity
MATCH (e:Entity) WHERE NOT ()-[:MENTIONS]->(e) RETURN count(e) AS unmention_entities
```

### Phase 5: 完了処理

```bash
mkdir -p .tmp/creator-graph-queue/.processed
mv .tmp/creator-graph-queue/cq-*.json .tmp/creator-graph-queue/.processed/
```

投入サマリーをユーザーに表示:
- 投入ノード数（Genre, Topic, Source, Entity, Fact, Tip, Story）
- 投入リレーション数（IN_GENRE, ABOUT, FROM_SOURCE, MENTIONS, RELATES_TO）
- 孤立ノード警告（あれば）

## 参照

- MERGE パターン詳細: `guide.md`
