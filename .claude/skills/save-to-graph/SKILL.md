---
name: save-to-graph
description: graph-queue JSON を読み込み、Neo4j にノードとリレーションを MERGE ベースで冪等投入するスキル。4フェーズ構成（キュー検出 → ノード投入 → リレーション投入 → 完了処理）。v2 スキーマ（9 ノード・9+ リレーション）対応。
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
  +-- Phase 4: 完了処理
        +-- 処理済みファイルの削除 or 移動（--keep で保持）
        +-- 統計サマリー出力
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

```cypher
MERGE (t:Topic {topic_id: $topic_id})
SET t.name = $name,
    t.category = $category,
    t.topic_key = $name + '::' + $category
```

### ステップ 2.2: Entity ノード MERGE

```cypher
MERGE (e:Entity {entity_id: $entity_id})
SET e.name = $name,
    e.entity_type = $entity_type,
    e.entity_key = $name + '::' + $entity_type
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
[DRY-RUN] MERGE (t:Topic {topic_id: "abc-123"})
          SET t.name = "S&P 500", t.category = "stock", t.topic_key = "S&P 500::stock"
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
