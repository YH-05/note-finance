---
name: save-to-graph
description: graph-queue JSON を読み込み、Neo4j にノードとリレーションを MERGE ベースで冪等投入するスキル。5フェーズ構成（キュー検出 → ノード投入 → リレーション投入 → 投入検証 → 完了処理）。v2 スキーマ（9 ノード・9+ リレーション）対応。
allowed-tools: Read, Bash, Grep, Glob
---

# save-to-graph スキル

graph-queue JSON ファイルを読み込み、Neo4j にナレッジグラフデータを投入するスキル。
MERGE ベースの Cypher クエリにより冪等性を保証する。

v2 スキーマでは 9 種のノード（Topic, Entity, Source, Claim, Fact, Chunk, Author, FinancialDataPoint, FiscalPeriod）と 9+ 種のリレーションを投入する。`schema_version` フィールドにより v1（`"1.0"`）と v2（`"2.0"`）の両方を処理できる。

## アーキテクチャ

```
/save-to-graph (このスキル = オーケストレーター)
  |
  +-- Phase 1: キュー検出・検証（接続確認 + 未処理ファイル検出）
  |     +-- Neo4j 接続確認（cypher-shell）
  |     +-- .tmp/graph-queue/ 配下の未処理 JSON を検出
  |     +-- --source / --file によるフィルタリング
  |     +-- JSON スキーマ検証（schema_version '1.0' | '2.0', 必須キー）
  |
  +-- Phase 2: ノード投入（MERGE）
  |     +-- Topic ノード MERGE
  |     +-- Entity ノード MERGE
  |     +-- Source ノード MERGE
  |     +-- Author ノード MERGE           [v2 新規]
  |     +-- Chunk ノード MERGE            [v2 新規]
  |     +-- Fact ノード MERGE             [v2 新規]
  |     +-- Claim ノード MERGE
  |     +-- FinancialDataPoint ノード MERGE [v2 新規]
  |     +-- FiscalPeriod ノード MERGE      [v2 新規]
  |
  +-- Phase 3a: ファイル内リレーション投入（MERGE）
  |     +-- TAGGED リレーション MERGE（Source -> Topic）[同一ファイル内]
  |     +-- MAKES_CLAIM リレーション MERGE（Source -> Claim）[source_id ベース]
  |     +-- ABOUT リレーション MERGE（Claim -> Entity）[同一ファイル内]
  |     +-- CONTAINS_CHUNK リレーション MERGE（Source -> Chunk）[v2 新規]
  |     +-- EXTRACTED_FROM リレーション MERGE（Fact/Claim -> Chunk）[v2 新規]
  |     +-- STATES_FACT リレーション MERGE（Source -> Fact）[v2 新規]
  |     +-- HAS_DATAPOINT リレーション MERGE（Source -> FinancialDataPoint）[v2 新規]
  |     +-- FOR_PERIOD リレーション MERGE（FinancialDataPoint -> FiscalPeriod）[v2 新規]
  |     +-- RELATES_TO リレーション MERGE（Fact/FinancialDataPoint -> Entity）[v2 新規]
  |
  +-- Phase 3b: クロスファイルリレーション（DB既存ノードとの接続）
  |     +-- TAGGED: カテゴリマッチング（新Source↔既存Topic, 新Topic↔既存Source）
  |     +-- ABOUT: コンテンツマッチング（新Claim↔既存Entity, 新Entity↔既存Claim）
  |
  +-- Phase 3c: 投入検証（Ingestion Verification）
  |     +-- graph-queue JSON の期待リレーション数を集計
  |     +-- Neo4j 上の実際のリレーション数をカウント（Source 単位）
  |     +-- 期待値と実績値の差異を判定（OK / WARNING / ERROR）
  |
  +-- Phase 4: 完了処理
        +-- 処理済みファイルの削除 or 移動（--keep で保持）
        +-- 統計サマリー出力（検証結果を含む）
```

## 使用方法

```bash
# 標準実行（.tmp/graph-queue/ 配下の全未処理 JSON を投入）
/save-to-graph

# 特定コマンドソースのみ
/save-to-graph --source finance-news-workflow

# 特定ファイルのみ
/save-to-graph --file .tmp/graph-queue/finance-news-workflow/gq-20260307120000-a1b2.json

# ドライラン（実際には投入しない）
/save-to-graph --dry-run

# 処理済みファイルを削除せず保持
/save-to-graph --keep
```

## パラメータ一覧

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| --source | all | 対象コマンドソース（finance-news-workflow, ai-research-collect 等） |
| --dry-run | false | Cypher クエリを表示するが実行しない |
| --skip-cross-link | false | Phase 3b（クロスファイルリレーション）をスキップする |
| --file | - | 特定の graph-queue JSON ファイルを指定（--source と排他） |
| --keep | false | 処理済みファイルを削除せず保持する |

## 前提条件

1. **Neo4j が起動していること**
   ```bash
   # Docker での起動例（パスワードは環境変数で設定すること）
   docker run -d --name neo4j \
     -p 127.0.0.1:7474:7474 -p 127.0.0.1:7687:7687 \
     -e NEO4J_AUTH=neo4j/${NEO4J_PASSWORD:?NEO4J_PASSWORD is required} \
     neo4j:5-community
   ```

2. **cypher-shell が使用可能であること**
   ```bash
   cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" "RETURN 1"
   ```

3. **初回セットアップが完了していること**
   - 詳細は `guide.md` の「初回セットアップ」セクションを参照
   - v2: UNIQUE 制約（10個）+ インデックス（13個）の作成が必要

4. **graph-queue JSON が存在すること**
   - `scripts/emit_graph_queue.py` で生成される
   - 出力先: `.tmp/graph-queue/{command_name}/gq-{timestamp}-{hash4}.json`

## Phase 1: キュー検出・検証

### ステップ 1.1: Neo4j 接続確認

```bash
# 環境変数から接続情報を取得（デフォルト値あり）
NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:?NEO4J_PASSWORD is required}"

# 接続テスト
cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -a "$NEO4J_URI" \
  "RETURN 'connection_ok' AS status"
```

**エラー時**: 接続失敗メッセージを表示して処理中断。

### ステップ 1.2: 未処理ファイル検出

```bash
# --source 指定時: 特定コマンドのディレクトリのみ
ls .tmp/graph-queue/${SOURCE}/*.json

# --file 指定時: 指定ファイルのみ
ls ${FILE}

# 指定なし: 全コマンドディレクトリを走査
find .tmp/graph-queue/ -name "*.json" -type f
```

### ステップ 1.3: JSON スキーマ検証

各 JSON ファイルに対して以下を検証:

```python
# v1/v2 共通の必須キー
required_keys_common = {
    "schema_version",  # "1.0" | "2.0"
    "queue_id",        # "gq-{timestamp}-{hash4}"
    "created_at",      # ISO 8601 datetime
    "command_source",  # コマンド名
    "sources",         # Source ノードデータ配列
    "topics",          # Topic ノードデータ配列
    "claims",          # Claim ノードデータ配列
    "entities",        # Entity ノードデータ配列
    "relations",       # リレーションデータ
}

# v2 で追加される必須キー
required_keys_v2 = {
    "facts",                  # Fact ノードデータ配列
    "chunks",                 # Chunk ノードデータ配列
    "financial_datapoints",   # FinancialDataPoint ノードデータ配列
    "fiscal_periods",         # FiscalPeriod ノードデータ配列
}

# schema_version に応じて検証キーを決定
schema_version = data.get("schema_version", "1.0")
if schema_version == "2.0":
    required_keys = required_keys_common | required_keys_v2
else:
    required_keys = required_keys_common
```

**検証失敗時**: ファイル名とエラー内容を警告表示し、スキップして次のファイルへ。

## Phase 2: ノード投入（MERGE）

投入順序は依存関係に基づく: **Topic -> Entity -> FiscalPeriod -> Source -> Author -> Chunk -> Fact -> Claim -> FinancialDataPoint**

v1 キューファイル（`schema_version: "1.0"`）の場合、ステップ 2.5〜2.9 はスキップされる（対象データが空配列）。

### ステップ 2.1: Topic ノード MERGE

> **MERGEキー**: `topic_key`（ビジネスキー）を使用する。
> `topic_id` はパイプラインごとに異なる値が生成される可能性があるため、
> UNIQUE制約がある `topic_key` でMERGEし、`topic_id` は ON CREATE で設定する。

```cypher
MERGE (t:Topic {topic_key: $topic_key})
ON CREATE SET t.topic_id = $topic_id
SET t.name = $name,
    t.category = $category
```

### ステップ 2.2: Entity ノード MERGE

> **MERGEキー**: `entity_key`（ビジネスキー）を使用する。
> `entity_id` はパイプラインごとに異なる値が生成される可能性があるため、
> UNIQUE制約がある `entity_key` でMERGEし、`entity_id` は ON CREATE で設定する。

```cypher
MERGE (e:Entity {entity_key: $entity_key})
ON CREATE SET e.entity_id = $entity_id
SET e.name = $name,
    e.entity_type = $entity_type
```

### ステップ 2.3: FiscalPeriod ノード MERGE [v2 新規]

```cypher
MERGE (fp:FiscalPeriod {period_id: $period_id})
SET fp.period_type = $period_type,
    fp.period_label = $period_label,
    fp.start_date = CASE WHEN $start_date IS NOT NULL AND $start_date <> ''
                    THEN date($start_date) ELSE null END,
    fp.end_date = CASE WHEN $end_date IS NOT NULL AND $end_date <> ''
                  THEN date($end_date) ELSE null END
```

### ステップ 2.4: Source ノード MERGE

```cypher
MERGE (s:Source {source_id: $source_id})
SET s.url = $url,
    s.title = $title,
    s.source_type = $source_type,
    s.authority_level = $authority_level,
    s.collected_at = datetime($collected_at),
    s.published_at = CASE WHEN $published_at IS NOT NULL AND $published_at <> ''
                     THEN datetime($published_at) ELSE null END,
    s.category = $category,
    s.command_source = $command_source
```

### ステップ 2.5: Author ノード MERGE [v2 新規]

```cypher
MERGE (a:Author {author_id: $author_id})
SET a.name = $name,
    a.author_type = $author_type,
    a.organization = $organization
```

### ステップ 2.6: Chunk ノード MERGE [v2 新規]

```cypher
MERGE (ch:Chunk {chunk_id: $chunk_id})
SET ch.chunk_index = $chunk_index,
    ch.section_title = $section_title,
    ch.content = $content,
    ch.char_count = $char_count,
    ch.has_tables = $has_tables,
    ch.created_at = datetime($created_at)
```

### ステップ 2.7: Fact ノード MERGE [v2 新規]

```cypher
MERGE (f:Fact {fact_id: $fact_id})
SET f.content = $content,
    f.fact_type = $fact_type,
    f.as_of_date = CASE WHEN $as_of_date IS NOT NULL AND $as_of_date <> ''
                   THEN date($as_of_date) ELSE null END,
    f.created_at = datetime($created_at)
```

### ステップ 2.8: Claim ノード MERGE

```cypher
MERGE (c:Claim {claim_id: $claim_id})
SET c.content = $content,
    c.claim_type = $claim_type,
    c.sentiment = $sentiment,
    c.magnitude = $magnitude,
    c.created_at = datetime($created_at)
```

> **v2 変更点**: `confidence` プロパティを削除。代わりに `sentiment`、`magnitude`、`created_at` を追加。

### ステップ 2.9: FinancialDataPoint ノード MERGE [v2 新規]

```cypher
MERGE (dp:FinancialDataPoint {datapoint_id: $datapoint_id})
SET dp.metric_name = $metric_name,
    dp.value = $value,
    dp.unit = $unit,
    dp.is_estimate = $is_estimate,
    dp.currency = $currency,
    dp.created_at = datetime($created_at)
```

### ドライランモード

`--dry-run` 指定時は、生成される Cypher クエリを標準出力に表示するが実行しない:

```
[DRY-RUN] MERGE (t:Topic {topic_key: "S&P 500::stock"})
          ON CREATE SET t.topic_id = "abc-123"
          SET t.name = "S&P 500", t.category = "stock"
[DRY-RUN] MERGE (s:Source {source_id: "def-456"})
          SET s.url = "https://...", s.title = "..."
[DRY-RUN] MERGE (ch:Chunk {chunk_id: "a1b2c3_chunk_0"})
          SET ch.section_title = "Valuation", ch.content = "..."
[DRY-RUN] MERGE (f:Fact {fact_id: "e5f6g7h8i9j0k1l2"})
          SET f.content = "Revenue grew 15% YoY", f.fact_type = "statistic"
[DRY-RUN] MERGE (dp:FinancialDataPoint {datapoint_id: "a1b2c3_Revenue_FY2025"})
          SET dp.metric_name = "Revenue", dp.value = 12500.0, dp.unit = "IDR bn"
```

## Phase 3a: ファイル内リレーション投入（MERGE）

同一 graph-queue ファイル内のノード間にリレーションを作成する。

v2 キューファイルでは `relations` オブジェクト内に明示的なリレーション定義が含まれる。v1 では暗黙推論ベース。

### ステップ 3a.1: TAGGED リレーション（Source -> Topic）

graph-queue JSON の `relations.tagged` 配列、または Source と Topic の紐付けから生成。

```cypher
MATCH (s:Source {source_id: $source_id})
MATCH (t:Topic {topic_id: $topic_id})
MERGE (s)-[:TAGGED]->(t)
```

### ステップ 3a.2: MAKES_CLAIM リレーション（Source -> Claim）

Claim の `source_id` フィールドから Source との紐付けを生成。`relations.source_claim` が明示されている場合はそちらを使用。

```cypher
MATCH (s:Source {source_id: $source_id})
MATCH (c:Claim {claim_id: $claim_id})
MERGE (s)-[:MAKES_CLAIM]->(c)
```

### ステップ 3a.3: ABOUT リレーション（Claim -> Entity）

Claim と Entity の紐付けを生成。`relations.claim_entity` が明示されている場合はそちらを使用。

```cypher
MATCH (c:Claim {claim_id: $claim_id})
MATCH (e:Entity {entity_id: $entity_id})
MERGE (c)-[:ABOUT]->(e)
```

### ステップ 3a.4: CONTAINS_CHUNK リレーション（Source -> Chunk）[v2 新規]

`relations.contains_chunk` 配列から生成。Source が含む Chunk を接続。

```cypher
MATCH (s:Source {source_id: $from_id})
MATCH (ch:Chunk {chunk_id: $to_id})
MERGE (s)-[:CONTAINS_CHUNK {chunk_order: $chunk_order}]->(ch)
```

### ステップ 3a.5: EXTRACTED_FROM リレーション（Fact/Claim -> Chunk）[v2 新規]

`relations.extracted_from_fact` および `relations.extracted_from_claim` 配列から生成。

```cypher
-- Fact -> Chunk
MATCH (f:Fact {fact_id: $from_id})
MATCH (ch:Chunk {chunk_id: $to_id})
MERGE (f)-[:EXTRACTED_FROM]->(ch)

-- Claim -> Chunk
MATCH (c:Claim {claim_id: $from_id})
MATCH (ch:Chunk {chunk_id: $to_id})
MERGE (c)-[:EXTRACTED_FROM]->(ch)
```

### ステップ 3a.6: STATES_FACT リレーション（Source -> Fact）[v2 新規]

`relations.source_fact` 配列から生成。

```cypher
MATCH (s:Source {source_id: $from_id})
MATCH (f:Fact {fact_id: $to_id})
MERGE (s)-[:STATES_FACT]->(f)
```

### ステップ 3a.7: RELATES_TO リレーション（Fact/FinancialDataPoint -> Entity）[v2 新規]

`relations.fact_entity` および `relations.datapoint_entity` 配列から生成。

```cypher
-- Fact -> Entity
MATCH (f:Fact {fact_id: $from_id})
MATCH (e:Entity {entity_id: $to_id})
MERGE (f)-[:RELATES_TO]->(e)

-- FinancialDataPoint -> Entity
MATCH (dp:FinancialDataPoint {datapoint_id: $from_id})
MATCH (e:Entity {entity_id: $to_id})
MERGE (dp)-[:RELATES_TO]->(e)
```

### ステップ 3a.8: HAS_DATAPOINT リレーション（Source -> FinancialDataPoint）[v2 新規]

`relations.has_datapoint` 配列から生成。

```cypher
MATCH (s:Source {source_id: $from_id})
MATCH (dp:FinancialDataPoint {datapoint_id: $to_id})
MERGE (s)-[:HAS_DATAPOINT]->(dp)
```

### ステップ 3a.9: FOR_PERIOD リレーション（FinancialDataPoint -> FiscalPeriod）[v2 新規]

`relations.for_period` 配列から生成。

```cypher
MATCH (dp:FinancialDataPoint {datapoint_id: $from_id})
MATCH (fp:FiscalPeriod {period_id: $to_id})
MERGE (dp)-[:FOR_PERIOD]->(fp)
```

## Phase 3b: クロスファイルリレーション（DB既存ノードとの接続）

Phase 2 で投入したノードを、DB 内の既存ノードとリレーションで接続する。
`--skip-cross-link` 指定時はスキップ。

### ステップ 3b.1: TAGGED カテゴリマッチング

今回投入した Source を、DB 内の同カテゴリの既存 Topic と接続する。
逆方向も同様に、今回投入した Topic を、DB 内の同カテゴリの既存 Source と接続する。

```cypher
// 新 Source → 既存 Topic（カテゴリ一致）
UNWIND $source_ids AS sid
MATCH (s:Source {source_id: sid})
MATCH (t:Topic {category: s.category})
MERGE (s)-[:TAGGED]->(t)
```

```cypher
// 新 Topic → 既存 Source（カテゴリ一致）
UNWIND $topic_ids AS tid
MATCH (t:Topic {topic_id: tid})
MATCH (s:Source {category: t.category})
MERGE (s)-[:TAGGED]->(t)
```

### ステップ 3b.2: ABOUT コンテンツマッチング

今回投入した Claim を、DB 内の既存 Entity と内容ベースで接続する。
逆方向も同様に、今回投入した Entity を、DB 内の既存 Claim と接続する。

**マッチング条件**: Entity 名が2文字以上 かつ Claim.content に Entity.name が含まれる。

```cypher
// 新 Claim → 既存 Entity（コンテンツに Entity 名を含む）
UNWIND $claim_ids AS cid
MATCH (c:Claim {claim_id: cid})
MATCH (e:Entity)
WHERE size(e.name) >= 2 AND c.content CONTAINS e.name
MERGE (c)-[:ABOUT]->(e)
```

```cypher
// 新 Entity → 既存 Claim（コンテンツに Entity 名を含む）
UNWIND $entity_ids AS eid
MATCH (e:Entity {entity_id: eid})
MATCH (c:Claim)
WHERE size(e.name) >= 2 AND c.content CONTAINS e.name
MERGE (c)-[:ABOUT]->(e)
```

### ドライランモード

`--dry-run` 指定時は、クロスファイルマッチングの対象数を表示するが実行しない:

```
[DRY-RUN] Cross-link TAGGED: 5 new Sources × 12 existing Topics (category match)
[DRY-RUN] Cross-link TAGGED: 0 new Topics × 0 existing Sources (category match)
[DRY-RUN] Cross-link ABOUT: 8 new Claims × 3 existing Entities (content match)
[DRY-RUN] Cross-link ABOUT: 0 new Entities × 0 existing Claims (content match)
```

## Phase 3c: 投入検証（Ingestion Verification）

Phase 3a/3b 完了後、graph-queue JSON の期待値と Neo4j 上の実際の投入数を比較検証する。
`--dry-run` 指定時はスキップ。

### 背景

Phase 3a で RELATES_TO（fact_entity）リレーションが投入されないケースが過去に234件発生した。
graph-queue JSON には fact_entity が含まれていたにもかかわらず、Neo4j への投入フェーズでスキップまたは失敗していた。
この Phase 3c はそのような投入漏れを即座に検出するための検証ステップである。

### ステップ 3c.1: 期待値の集計

graph-queue JSON の `relations` オブジェクトから、各リレーションタイプの期待件数を集計する。

```python
# graph-queue JSON から期待値を算出
expected = {}
relations = data.get("relations", {})

# 主要リレーションタイプごとに件数を集計
relation_keys = {
    "tagged":               "TAGGED (intra-file)",
    "source_claim":         "MAKES_CLAIM",
    "claim_entity":         "ABOUT (intra-file)",
    "contains_chunk":       "CONTAINS_CHUNK",
    "extracted_from_fact":  "EXTRACTED_FROM (fact)",
    "extracted_from_claim": "EXTRACTED_FROM (claim)",
    "source_fact":          "STATES_FACT",
    "fact_entity":          "RELATES_TO (fact_entity)",
    "datapoint_entity":     "RELATES_TO (datapoint_entity)",
    "has_datapoint":        "HAS_DATAPOINT",
    "for_period":           "FOR_PERIOD",
}

for key, label in relation_keys.items():
    expected[label] = len(relations.get(key, []))
```

### ステップ 3c.2: 実績値のカウント

今回投入した Source の source_id リストを使い、Neo4j 上の実際のリレーション数をカウントする。

```cypher
// RELATES_TO (fact_entity): Source -> Fact -> Entity
UNWIND $source_ids AS sid
MATCH (s:Source {source_id: sid})-[:STATES_FACT]->(f:Fact)-[:RELATES_TO]->(e:Entity)
RETURN count(*) AS actual_count
```

```cypher
// RELATES_TO (datapoint_entity): Source -> FinancialDataPoint -> Entity
UNWIND $source_ids AS sid
MATCH (s:Source {source_id: sid})-[:HAS_DATAPOINT]->(dp:FinancialDataPoint)-[:RELATES_TO]->(e:Entity)
RETURN count(*) AS actual_count
```

```cypher
// STATES_FACT: Source -> Fact
UNWIND $source_ids AS sid
MATCH (s:Source {source_id: sid})-[:STATES_FACT]->(f:Fact)
RETURN count(*) AS actual_count
```

```cypher
// MAKES_CLAIM: Source -> Claim
UNWIND $source_ids AS sid
MATCH (s:Source {source_id: sid})-[:MAKES_CLAIM]->(c:Claim)
RETURN count(*) AS actual_count
```

```cypher
// ABOUT (intra-file): Claim -> Entity（今回投入した Claim のみ）
UNWIND $claim_ids AS cid
MATCH (c:Claim {claim_id: cid})-[:ABOUT]->(e:Entity)
RETURN count(*) AS actual_count
```

```cypher
// CONTAINS_CHUNK: Source -> Chunk
UNWIND $source_ids AS sid
MATCH (s:Source {source_id: sid})-[:CONTAINS_CHUNK]->(ch:Chunk)
RETURN count(*) AS actual_count
```

```cypher
// EXTRACTED_FROM (fact): Fact -> Chunk（今回投入した Fact のみ）
UNWIND $fact_ids AS fid
MATCH (f:Fact {fact_id: fid})-[:EXTRACTED_FROM]->(ch:Chunk)
RETURN count(*) AS actual_count
```

```cypher
// EXTRACTED_FROM (claim): Claim -> Chunk（今回投入した Claim のみ）
UNWIND $claim_ids AS cid
MATCH (c:Claim {claim_id: cid})-[:EXTRACTED_FROM]->(ch:Chunk)
RETURN count(*) AS actual_count
```

```cypher
// HAS_DATAPOINT: Source -> FinancialDataPoint
UNWIND $source_ids AS sid
MATCH (s:Source {source_id: sid})-[:HAS_DATAPOINT]->(dp:FinancialDataPoint)
RETURN count(*) AS actual_count
```

```cypher
// FOR_PERIOD: FinancialDataPoint -> FiscalPeriod（今回投入した DP のみ）
UNWIND $datapoint_ids AS dpid
MATCH (dp:FinancialDataPoint {datapoint_id: dpid})-[:FOR_PERIOD]->(fp:FiscalPeriod)
RETURN count(*) AS actual_count
```

### ステップ 3c.3: 差異判定

期待値と実績値を比較し、差異率に応じてアクションを決定する。

| 条件 | 判定 | アクション |
|------|------|----------|
| 全リレーションで期待値 = 実績値 | OK | Phase 4 へ進む |
| いずれかのリレーションで差異あり かつ 差異率 < 10% | WARNING | 差異を報告し Phase 4 へ進む |
| いずれかのリレーションで差異率 >= 10% | ERROR | ユーザーに確認を求める。自動進行しない |

差異率の算出:

```python
def calc_discrepancy_rate(expected: int, actual: int) -> float:
    """期待値と実績値の差異率を算出する。期待値が0の場合は0%を返す。"""
    if expected == 0:
        return 0.0
    return abs(expected - actual) / expected * 100
```

### 検証結果の出力フォーマット

```markdown
### Phase 3c: 投入検証結果

| リレーションタイプ | 期待値 | 実績値 | 差異 | 判定 |
|-------------------|--------|--------|------|------|
| RELATES_TO (fact_entity) | 234 | 234 | 0 | OK |
| RELATES_TO (datapoint_entity) | 12 | 12 | 0 | OK |
| STATES_FACT | 80 | 80 | 0 | OK |
| MAKES_CLAIM | 45 | 45 | 0 | OK |
| ABOUT (intra-file) | 30 | 28 | -2 | WARNING |
| CONTAINS_CHUNK | 16 | 16 | 0 | OK |
| EXTRACTED_FROM (fact) | 60 | 60 | 0 | OK |
| EXTRACTED_FROM (claim) | 20 | 20 | 0 | OK |
| HAS_DATAPOINT | 12 | 12 | 0 | OK |
| FOR_PERIOD | 8 | 8 | 0 | OK |

**総合判定**: WARNING（1件の差異あり、差異率 6.7%）
→ Phase 4 へ進む
```

### ERROR 時の対応手順

差異率が10%以上の場合、以下の情報をユーザーに提示して確認を求める:

1. 差異のあるリレーションタイプと件数
2. graph-queue JSON ファイル名
3. 推奨アクション:
   - graph-queue JSON を `--keep` 付きで再投入する
   - Neo4j ログを確認して失敗原因を調査する
   - `relations.{key}` の from_id / to_id が Phase 2 で投入したノードの ID と一致しているか確認する

## Phase 4: 完了処理

### ステップ 4.1: 処理済みファイルの処理

| モード | 動作 |
|--------|------|
| デフォルト | 処理済み JSON ファイルを削除 |
| `--keep` | 処理済みファイルを `.tmp/graph-queue/.processed/` に移動 |

### ステップ 4.2: 統計サマリー出力

```markdown
## save-to-graph 完了

### 全体統計

| 項目 | 件数 |
|------|------|
| 処理ファイル数 | {file_count} |
| スキーマバージョン | {schema_versions} |
| 投入 Source ノード | {source_count} |
| 投入 Topic ノード | {topic_count} |
| 投入 Entity ノード | {entity_count} |
| 投入 Claim ノード | {claim_count} |
| 投入 Fact ノード | {fact_count} |
| 投入 Chunk ノード | {chunk_count} |
| 投入 Author ノード | {author_count} |
| 投入 FinancialDataPoint ノード | {datapoint_count} |
| 投入 FiscalPeriod ノード | {period_count} |
| 投入 TAGGED リレーション（ファイル内） | {tagged_intra_count} |
| 投入 MAKES_CLAIM リレーション | {makes_claim_count} |
| 投入 ABOUT リレーション（ファイル内） | {about_intra_count} |
| 投入 CONTAINS_CHUNK リレーション | {contains_chunk_count} |
| 投入 EXTRACTED_FROM リレーション | {extracted_from_count} |
| 投入 STATES_FACT リレーション | {states_fact_count} |
| 投入 HAS_DATAPOINT リレーション | {has_datapoint_count} |
| 投入 FOR_PERIOD リレーション | {for_period_count} |
| 投入 RELATES_TO リレーション | {relates_to_count} |
| クロスリンク TAGGED | {tagged_cross_count} |
| クロスリンク ABOUT | {about_cross_count} |
| スキップ（検証エラー） | {skipped_count} |

### 投入検証結果（Phase 3c）

| リレーションタイプ | 期待値 | 実績値 | 差異 | 判定 |
|-------------------|--------|--------|------|------|
| RELATES_TO (fact_entity) | {expected} | {actual} | {diff} | {verdict} |
| RELATES_TO (datapoint_entity) | {expected} | {actual} | {diff} | {verdict} |
| STATES_FACT | {expected} | {actual} | {diff} | {verdict} |
| MAKES_CLAIM | {expected} | {actual} | {diff} | {verdict} |
| ABOUT (intra-file) | {expected} | {actual} | {diff} | {verdict} |
| CONTAINS_CHUNK | {expected} | {actual} | {diff} | {verdict} |
| EXTRACTED_FROM (fact) | {expected} | {actual} | {diff} | {verdict} |
| EXTRACTED_FROM (claim) | {expected} | {actual} | {diff} | {verdict} |
| HAS_DATAPOINT | {expected} | {actual} | {diff} | {verdict} |
| FOR_PERIOD | {expected} | {actual} | {diff} | {verdict} |

**総合判定**: {overall_verdict}

### ファイル別統計

| ファイル | コマンドソース | ver | Source | Topic | Entity | Claim | Fact | Chunk | DP | FP | ステータス |
|----------|--------------|-----|--------|-------|--------|-------|------|-------|----|----|-----------|
| gq-...a1b2.json | finance-news-workflow | 1.0 | 5 | 0 | 0 | 5 | 0 | 0 | 0 | 0 | OK |
| gq-...c3d4.json | ai-research-collect | 1.0 | 3 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | OK |
| gq-...e5f6.json | pdf-extraction | 2.0 | 1 | 0 | 5 | 3 | 8 | 4 | 12 | 3 | OK |

### 実行情報

- **実行モード**: {mode} (standard / dry-run)
- **実行時刻**: {timestamp}
- **Neo4j URI**: {neo4j_uri}
- **ファイル処理**: {file_action} (deleted / moved to .processed / kept)
```

## 冪等性の保証

このスキルの全ての Cypher クエリは `MERGE` ベースであり、冪等性が保証されます:

1. **ノード投入**: `MERGE` はノードが存在すれば更新、存在しなければ作成
2. **リレーション投入**: `MERGE` はリレーションが存在すれば何もしない、存在しなければ作成
3. **ID の決定論性**: 全 ID は入力データから決定論的に生成される（UUID5 / SHA-256）

同じ graph-queue JSON ファイルを複数回投入しても、グラフの状態は変わりません。

## エラーハンドリング

| エラー | 対処 |
|--------|------|
| E001: Neo4j 接続失敗 | 接続情報を確認。`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` 環境変数を設定 |
| E002: graph-queue ディレクトリ未検出 | `scripts/emit_graph_queue.py` を先に実行して JSON を生成 |
| E003: JSON スキーマ検証エラー | ファイルの `schema_version` と必須キーを確認。`emit_graph_queue.py` を再実行 |
| E004: Cypher 実行エラー | Neo4j のログを確認。制約・インデックスが未作成の場合は初回セットアップを実行 |
| E005: ファイル削除/移動エラー | ファイルの権限を確認 |
| E006: 投入検証エラー（差異率 >= 10%） | Phase 3c の ERROR 時対応手順に従い原因調査。`--keep` 付きで再投入を検討 |

## 環境変数

| 変数名 | デフォルト | 説明 |
|--------|-----------|------|
| NEO4J_URI | bolt://localhost:7687 | Neo4j Bolt プロトコル URI |
| NEO4J_USER | neo4j | Neo4j ユーザー名 |
| NEO4J_PASSWORD | (必須、デフォルトなし) | Neo4j パスワード |

## 関連リソース

| リソース | パス |
|---------|------|
| 詳細ガイド | `.claude/skills/save-to-graph/guide.md` |
| スラッシュコマンド | `.claude/commands/save-to-graph.md` |
| graph-queue 生成スクリプト | `scripts/emit_graph_queue.py` |
| ナレッジグラフスキーマ | `data/config/knowledge-graph-schema.yaml` |
| graph-queue 出力先 | `.tmp/graph-queue/{command_name}/` |

## 対応コマンドソース

| コマンドソース | 説明 | 主な生成ノード |
|--------------|------|--------------|
| finance-news-workflow | 金融ニュース収集 | Source, Claim |
| ai-research-collect | AI投資リサーチ | Entity, Source |
| generate-market-report | マーケットレポート | Source, Claim |
| asset-management | 資産形成 | Topic, Source |
| reddit-finance-topics | Reddit トピック | Topic, Source |
| finance-full | 記事執筆 | Source, Claim |

## 変更履歴

### 2026-03-22: Phase 3c 投入検証を追加

- Phase 3b と Phase 4 の間に Phase 3c（投入検証）を追加
- graph-queue JSON の期待リレーション数と Neo4j 実績値を比較検証
- 差異率に応じた3段階判定: OK / WARNING（< 10%）/ ERROR（>= 10%）
- ERROR 時はユーザーに確認を求め自動進行しない
- Phase 4 の統計サマリーに検証結果テーブルを追加
- エラーコード E006（投入検証エラー）を追加
- 背景: Phase 3a で RELATES_TO（fact_entity）が234件投入漏れした事案の再発防止

### 2026-03-12: v2 スキーマ対応（Issue #67）

- `schema_version` '1.0' | '2.0' 両対応
- `required_keys` に `facts`, `chunks`, `financial_datapoints`, `fiscal_periods` 追加（v2）
- Phase 2 に 5 種の新ノード MERGE 追加: Fact, Chunk, Author, FinancialDataPoint, FiscalPeriod
- Phase 3a に 6 種の新リレーション MERGE 追加: CONTAINS_CHUNK, EXTRACTED_FROM, STATES_FACT, RELATES_TO, HAS_DATAPOINT, FOR_PERIOD
- Claim MERGE から `confidence` プロパティ削除、`sentiment`/`magnitude`/`created_at` 追加
- 統計サマリーに新ノード・新リレーション件数を追加
- 初回セットアップの制約・インデックス数を v2 に更新（10 制約・13 インデックス）

### 2026-03-08: クロスファイルリレーション追加

- Phase 3 を 3a（ファイル内）と 3b（クロスファイル）に分割
- TAGGED: カテゴリマッチングで Source↔Topic を接続
- ABOUT: コンテンツマッチングで Claim↔Entity を接続
- `--skip-cross-link` パラメータ追加
- 統計サマリーにクロスリンク件数を追加

### 2026-03-07: 初版作成（Issue #47）

- 4フェーズ構成（キュー検出 → ノード投入 → リレーション投入 → 完了処理）
- MERGE ベース冪等投入
- --source, --dry-run, --file, --keep パラメータ対応

## Observability

スキル実行のトレースを `scripts/skill_run_tracer.py` で記録する。
Neo4j 未起動時はグレースフルデグラデーションにより合成 ID を返し、スキル実行をブロックしない。

### 実行開始時（Phase 1 の前）

```bash
SKILL_RUN_ID=$(python3 scripts/skill_run_tracer.py start \
    --skill-name save-to-graph \
    --command-source "/save-to-graph" \
    --input-summary "Processing ${FILE_COUNT} graph-queue files")
```

### 実行完了時（成功 — Phase 4 完了後）

```bash
python3 scripts/skill_run_tracer.py complete \
    --skill-run-id "$SKILL_RUN_ID" \
    --status success \
    --output-summary "${NODE_COUNT} nodes, ${REL_COUNT} relations merged from ${FILE_COUNT} files"
```

### 実行完了時（エラー — 任意の Phase で失敗時）

```bash
python3 scripts/skill_run_tracer.py complete \
    --skill-run-id "$SKILL_RUN_ID" \
    --status failure \
    --error-message "Phase ${PHASE}: ${ERROR_MSG}" \
    --error-type "${ERROR_TYPE}"
```

`error_type` の分類:

| error_type | 説明 |
|------------|------|
| neo4j_connection | Neo4j 接続失敗（E001） |
| queue_not_found | graph-queue ディレクトリ未検出（E002） |
| schema_validation | JSON スキーマ検証エラー（E003） |
| cypher_execution | Cypher 実行エラー（E004） |
| file_operation | ファイル削除/移動エラー（E005） |
| ingestion_verification | 投入検証エラー（E006） |
