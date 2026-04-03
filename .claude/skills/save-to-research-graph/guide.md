# save-to-graph 詳細ガイド

このガイドは、save-to-graph スキルの詳細な処理フロー、Cypher テンプレート、graph-queue フォーマット仕様を説明します。

## 目次

1. [初回セットアップ](#初回セットアップ)
2. [graph-queue フォーマット仕様](#graph-queue-フォーマット仕様)
3. [ID 生成戦略](#id-生成戦略)
4. [Cypher テンプレート](#cypher-テンプレート)
5. [ノード投入詳細](#ノード投入詳細)
6. [Phase 1.5: Classification Node Processing](#phase-15-classification-node-processing)
7. [Phase 3a: ファイル内リレーション投入詳細](#phase-3a-ファイル内リレーション投入詳細)
8. [Phase 3b: クロスファイルリレーション投入詳細](#phase-3b-クロスファイルリレーション投入詳細)
9. [冪等性の仕組み](#冪等性の仕組み)
10. [エラーハンドリング詳細](#エラーハンドリング詳細)

---

## 初回セットアップ

Neo4j に初めて接続する際は、以下の制約とインデックスを作成する必要があります。

### 前提: Neo4j 接続

```bash
# 環境変数設定
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="<your-password-here>"  # 実際のパスワードをコミットしないこと

# 接続テスト
cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -a "$NEO4J_URI" \
  "RETURN 'connection_ok' AS status"
```

### UNIQUE 制約の作成（10個）

```cypher
-- Source ノード制約
CREATE CONSTRAINT unique_source_id IF NOT EXISTS
  FOR (s:Source) REQUIRE s.source_id IS UNIQUE;

-- Topic ノード制約
CREATE CONSTRAINT unique_topic_id IF NOT EXISTS
  FOR (t:Topic) REQUIRE t.topic_id IS UNIQUE;

CREATE CONSTRAINT unique_topic_key IF NOT EXISTS
  FOR (t:Topic) REQUIRE t.topic_key IS UNIQUE;

-- Entity ノード制約
CREATE CONSTRAINT unique_entity_id IF NOT EXISTS
  FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE;

CREATE CONSTRAINT unique_entity_key IF NOT EXISTS
  FOR (e:Entity) REQUIRE e.entity_key IS UNIQUE;

-- Claim ノード制約
CREATE CONSTRAINT unique_claim_id IF NOT EXISTS
  FOR (c:Claim) REQUIRE c.claim_id IS UNIQUE;

-- Fact ノード制約 [v2 新規]
CREATE CONSTRAINT unique_fact_id IF NOT EXISTS
  FOR (f:Fact) REQUIRE f.fact_id IS UNIQUE;

-- Chunk ノード制約 [v2 新規]
CREATE CONSTRAINT unique_chunk_id IF NOT EXISTS
  FOR (ch:Chunk) REQUIRE ch.chunk_id IS UNIQUE;

-- FinancialDataPoint ノード制約 [v2 新規]
CREATE CONSTRAINT unique_datapoint_id IF NOT EXISTS
  FOR (dp:FinancialDataPoint) REQUIRE dp.datapoint_id IS UNIQUE;

-- FiscalPeriod ノード制約 [v2 新規]
CREATE CONSTRAINT unique_period_id IF NOT EXISTS
  FOR (fp:FiscalPeriod) REQUIRE fp.period_id IS UNIQUE;

-- Author ノード制約 [academic-fetch 新規]
CREATE CONSTRAINT unique_author_id IF NOT EXISTS
  FOR (a:Author) REQUIRE a.author_id IS UNIQUE;
```

> **v2 変更点**: `unique_source_url` 制約を削除（PDF ソース等で URL が null になるため）。代わりに `source_hash` インデックスで重複検出。Fact, Chunk, FinancialDataPoint, FiscalPeriod の 4 制約を追加。

### インデックスの作成（13個）

```cypher
-- Source インデックス
CREATE INDEX idx_source_category IF NOT EXISTS
  FOR (s:Source) ON (s.category);

CREATE INDEX idx_source_collected_at IF NOT EXISTS
  FOR (s:Source) ON (s.collected_at);

CREATE INDEX idx_source_type IF NOT EXISTS
  FOR (s:Source) ON (s.source_type);

CREATE INDEX idx_source_hash IF NOT EXISTS
  FOR (s:Source) ON (s.source_hash);

-- Topic インデックス
CREATE INDEX idx_topic_category IF NOT EXISTS
  FOR (t:Topic) ON (t.category);

-- Entity インデックス
CREATE INDEX idx_entity_type IF NOT EXISTS
  FOR (e:Entity) ON (e.entity_type);

CREATE INDEX idx_entity_ticker IF NOT EXISTS
  FOR (e:Entity) ON (e.ticker);

-- Fact インデックス [v2 新規]
CREATE INDEX idx_fact_type IF NOT EXISTS
  FOR (f:Fact) ON (f.fact_type);

CREATE INDEX idx_fact_as_of_date IF NOT EXISTS
  FOR (f:Fact) ON (f.as_of_date);

-- Claim インデックス [v2 新規]
CREATE INDEX idx_claim_type IF NOT EXISTS
  FOR (c:Claim) ON (c.claim_type);

CREATE INDEX idx_claim_sentiment IF NOT EXISTS
  FOR (c:Claim) ON (c.sentiment);

-- FinancialDataPoint インデックス [v2 新規]
CREATE INDEX idx_datapoint_metric IF NOT EXISTS
  FOR (dp:FinancialDataPoint) ON (dp.metric_name);

-- FiscalPeriod インデックス [v2 新規]
CREATE INDEX idx_period_label IF NOT EXISTS
  FOR (fp:FiscalPeriod) ON (fp.period_label);
```

### 一括セットアップスクリプト

```bash
# 全制約・インデックスを一括作成（v2 対応）
cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -a "$NEO4J_URI" << 'CYPHER'
// 制約（10個）
CREATE CONSTRAINT unique_source_id IF NOT EXISTS FOR (s:Source) REQUIRE s.source_id IS UNIQUE;
CREATE CONSTRAINT unique_topic_id IF NOT EXISTS FOR (t:Topic) REQUIRE t.topic_id IS UNIQUE;
CREATE CONSTRAINT unique_topic_key IF NOT EXISTS FOR (t:Topic) REQUIRE t.topic_key IS UNIQUE;
CREATE CONSTRAINT unique_entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE;
CREATE CONSTRAINT unique_entity_key IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_key IS UNIQUE;
CREATE CONSTRAINT unique_claim_id IF NOT EXISTS FOR (c:Claim) REQUIRE c.claim_id IS UNIQUE;
CREATE CONSTRAINT unique_fact_id IF NOT EXISTS FOR (f:Fact) REQUIRE f.fact_id IS UNIQUE;
CREATE CONSTRAINT unique_chunk_id IF NOT EXISTS FOR (ch:Chunk) REQUIRE ch.chunk_id IS UNIQUE;
CREATE CONSTRAINT unique_datapoint_id IF NOT EXISTS FOR (dp:FinancialDataPoint) REQUIRE dp.datapoint_id IS UNIQUE;
CREATE CONSTRAINT unique_period_id IF NOT EXISTS FOR (fp:FiscalPeriod) REQUIRE fp.period_id IS UNIQUE;
CREATE CONSTRAINT unique_author_id IF NOT EXISTS FOR (a:Author) REQUIRE a.author_id IS UNIQUE;
// インデックス（13個）
CREATE INDEX idx_source_category IF NOT EXISTS FOR (s:Source) ON (s.category);
CREATE INDEX idx_source_collected_at IF NOT EXISTS FOR (s:Source) ON (s.collected_at);
CREATE INDEX idx_source_type IF NOT EXISTS FOR (s:Source) ON (s.source_type);
CREATE INDEX idx_source_hash IF NOT EXISTS FOR (s:Source) ON (s.source_hash);
CREATE INDEX idx_topic_category IF NOT EXISTS FOR (t:Topic) ON (t.category);
CREATE INDEX idx_entity_type IF NOT EXISTS FOR (e:Entity) ON (e.entity_type);
CREATE INDEX idx_entity_ticker IF NOT EXISTS FOR (e:Entity) ON (e.ticker);
CREATE INDEX idx_fact_type IF NOT EXISTS FOR (f:Fact) ON (f.fact_type);
CREATE INDEX idx_fact_as_of_date IF NOT EXISTS FOR (f:Fact) ON (f.as_of_date);
CREATE INDEX idx_claim_type IF NOT EXISTS FOR (c:Claim) ON (c.claim_type);
CREATE INDEX idx_claim_sentiment IF NOT EXISTS FOR (c:Claim) ON (c.sentiment);
CREATE INDEX idx_datapoint_metric IF NOT EXISTS FOR (dp:FinancialDataPoint) ON (dp.metric_name);
CREATE INDEX idx_period_label IF NOT EXISTS FOR (fp:FiscalPeriod) ON (fp.period_label);
CYPHER

# 作成結果を確認
cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -a "$NEO4J_URI" \
  "SHOW CONSTRAINTS"

cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -a "$NEO4J_URI" \
  "SHOW INDEXES"
```

### v1 からのマイグレーション

既存の v1 環境を v2 にアップグレードする場合:

```bash
cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -a "$NEO4J_URI" << 'CYPHER'
// v1 の unique_source_url 制約を削除（v2 では不要）
DROP CONSTRAINT unique_source_url IF EXISTS;
// v2 新規の制約を追加
CREATE CONSTRAINT unique_fact_id IF NOT EXISTS FOR (f:Fact) REQUIRE f.fact_id IS UNIQUE;
CREATE CONSTRAINT unique_chunk_id IF NOT EXISTS FOR (ch:Chunk) REQUIRE ch.chunk_id IS UNIQUE;
CREATE CONSTRAINT unique_datapoint_id IF NOT EXISTS FOR (dp:FinancialDataPoint) REQUIRE dp.datapoint_id IS UNIQUE;
CREATE CONSTRAINT unique_period_id IF NOT EXISTS FOR (fp:FiscalPeriod) REQUIRE fp.period_id IS UNIQUE;
// v2 新規のインデックスを追加
CREATE INDEX idx_source_type IF NOT EXISTS FOR (s:Source) ON (s.source_type);
CREATE INDEX idx_source_hash IF NOT EXISTS FOR (s:Source) ON (s.source_hash);
CREATE INDEX idx_entity_ticker IF NOT EXISTS FOR (e:Entity) ON (e.ticker);
CREATE INDEX idx_fact_type IF NOT EXISTS FOR (f:Fact) ON (f.fact_type);
CREATE INDEX idx_fact_as_of_date IF NOT EXISTS FOR (f:Fact) ON (f.as_of_date);
CREATE INDEX idx_claim_type IF NOT EXISTS FOR (c:Claim) ON (c.claim_type);
CREATE INDEX idx_claim_sentiment IF NOT EXISTS FOR (c:Claim) ON (c.sentiment);
CREATE INDEX idx_datapoint_metric IF NOT EXISTS FOR (dp:FinancialDataPoint) ON (dp.metric_name);
CREATE INDEX idx_period_label IF NOT EXISTS FOR (fp:FiscalPeriod) ON (fp.period_label);
CYPHER
```

### Neo4j CE の制約について

Neo4j 5 Community Edition では複合一意制約（Composite Unique Constraint）が使用できません。
そのため、Topic と Entity に**連結キー**プロパティを導入しています:

| ノード | 連結キー | 形式 | 例 |
|--------|---------|------|-----|
| Topic | `topic_key` | `{name}::{category}` | `S&P 500::stock` |
| Entity | `entity_key` | `{name}::{entity_type}` | `NVIDIA::company` |

これにより、単一プロパティの UNIQUE 制約で実質的な複合キー制約を実現しています。

---

## graph-queue フォーマット仕様

### 概要

graph-queue JSON は `scripts/emit_research_queue.py` が生成する中間フォーマットです。
各種ワークフローコマンドの出力を統一的なグラフデータ形式に変換したものです。

### ファイル配置

```
.tmp/graph-queue/
  +-- finance-news-workflow/
  |     +-- gq-20260307120000-a1b2.json
  |     +-- gq-20260307130000-c3d4.json
  +-- ai-research-collect/
  |     +-- gq-20260307140000-e5f6.json
  +-- generate-market-report/
  |     +-- gq-20260307150000-g7h8.json
  +-- asset-management/
  |     +-- gq-20260307160000-i9j0.json
  +-- reddit-finance-topics/
  |     +-- gq-20260307170000-k1l2.json
  +-- finance-full/
        +-- gq-20260307180000-m3n4.json
```

### ファイル命名規則

```
gq-{YYYYMMDDHHmmss}-{hash4}.json
```

- `gq-` : graph-queue プレフィックス
- `{YYYYMMDDHHmmss}` : UTC タイムスタンプ
- `{hash4}` : タイムスタンプの SHA-256 先頭4文字（衝突回避）

### トップレベルスキーマ

```json
{
  "schema_version": "2.0",  // or "2.2" or "3.0"
  "queue_id": "gq-20260307120000-a1b2",
  "created_at": "2026-03-07T12:00:00+00:00",
  "command_source": "pdf-extraction",
  "session_id": "pdf-20260307-120000",
  "batch_label": "pdf-extraction",
  "sources": [...],
  "topics": [...],
  "claims": [...],
  "facts": [...],
  "entities": [...],
  "chunks": [...],
  "financial_datapoints": [...],
  "fiscal_periods": [...],
  "classification_nodes": [...],
  "relations": {
    "contains_chunk": [...],
    "extracted_from_fact": [...],
    "extracted_from_claim": [...],
    "source_fact": [...],
    "source_claim": [...],
    "fact_entity": [...],
    "claim_entity": [...],
    "has_datapoint": [...],
    "for_period": [...],
    "datapoint_entity": [...]
  }
}
```

### フィールド定義

| フィールド | 型 | v1 必須 | v2 必須 | 説明 |
|-----------|------|---------|---------|------|
| `schema_version` | string | Yes | Yes | スキーマバージョン（`"1.0"`, `"2.0"`, `"2.2"`, or `"3.0"`） |
| `queue_id` | string | Yes | Yes | キュー一意ID（`gq-{timestamp}-{hash4}`） |
| `created_at` | string | Yes | Yes | 生成日時（ISO 8601） |
| `command_source` | string | Yes | Yes | 生成元コマンド名 |
| `session_id` | string | Yes | Yes | セッションID |
| `batch_label` | string | Yes | Yes | バッチラベル（テーマキー等） |
| `sources` | array | Yes | Yes | Source ノードデータ配列 |
| `topics` | array | Yes | Yes | Topic ノードデータ配列 |
| `claims` | array | Yes | Yes | Claim ノードデータ配列 |
| `facts` | array | No | Yes | Fact ノードデータ配列 [v2 新規] |
| `entities` | array | Yes | Yes | Entity ノードデータ配列 |
| `chunks` | array | No | Yes | Chunk ノードデータ配列 [v2 新規] |
| `financial_datapoints` | array | No | Yes | FinancialDataPoint ノードデータ配列 [v2 新規] |
| `fiscal_periods` | array | No | Yes | FiscalPeriod ノードデータ配列 [v2 新規] |
| `classification_nodes` | array | No | No | Classification ノードデータ配列 [v3.0 新規] |
| `relations` | object | Yes | Yes | リレーションデータ（v2 では明示的定義を含む） |

### sources 配列の要素

```json
{
  "source_id": "uuid5-string",
  "url": "https://www.cnbc.com/...",
  "title": "S&P 500 hits record high",
  "published": "2026-03-07T10:00:00+00:00",
  "feed_source": "CNBC - Markets"
}
```

| フィールド | 型 | 必須 | 説明 |
|-----------|------|------|------|
| `source_id` | string | Yes | UUID5(NAMESPACE_URL, url) |
| `url` | string | Yes | ソース URL |
| `title` | string | Yes | タイトル |
| `published` | string | No | 公開日時（ISO 8601） |
| `feed_source` | string | No | フィードソース名 |

### topics 配列の要素

```json
{
  "topic_id": "uuid5-string",
  "name": "NISA制度",
  "category": "asset-management",
  "theme_key": "nisa"
}
```

| フィールド | 型 | 必須 | 説明 |
|-----------|------|------|------|
| `topic_id` | string | Yes | UUID5(NAMESPACE_URL, "topic:{name}:{category}") |
| `name` | string | Yes | トピック名 |
| `category` | string | Yes | カテゴリ |
| `theme_key` | string | No | テーマキー |

### claims 配列の要素

```json
{
  "claim_id": "sha256-hex-16",
  "content": "The S&P 500 index reached an all-time high.",
  "source_id": "uuid5-string",
  "category": "stock"
}
```

| フィールド | 型 | 必須 | 説明 |
|-----------|------|------|------|
| `claim_id` | string | Yes | SHA-256(content)[:16] |
| `content` | string | Yes | 主張・事実のテキスト |
| `source_id` | string | No | 関連 Source の ID（MAKES_CLAIM リレーション用） |
| `category` | string | No | カテゴリ |

### entities 配列の要素

```json
{
  "entity_id": "uuid5-string",
  "name": "NVIDIA",
  "entity_type": "company",
  "ticker": "NVDA"
}
```

| フィールド | 型 | 必須 | 説明 |
|-----------|------|------|------|
| `entity_id` | string | Yes | UUID5(NAMESPACE_URL, "entity:{name}:{entity_type}") |
| `name` | string | Yes | エンティティ名 |
| `entity_type` | string | Yes | エンティティ種別 |
| `ticker` | string | No | ティッカーシンボル |

### facts 配列の要素 [v2 新規]

```json
{
  "fact_id": "sha256-hex-16",
  "content": "Revenue grew 15% YoY to IDR 45.2 trillion.",
  "source_id": "uuid5-string",
  "fact_type": "statistic",
  "as_of_date": "2025-12-31"
}
```

| フィールド | 型 | 必須 | 説明 |
|-----------|------|------|------|
| `fact_id` | string | Yes | SHA-256("fact:{content}")[:16] |
| `content` | string | Yes | 事実テキスト |
| `source_id` | string | No | 関連 Source の ID（STATES_FACT リレーション用） |
| `fact_type` | string | No | 事実種別（statistic, event, data_point, quote, policy_action 等） |
| `as_of_date` | string | No | 事実が参照する日付（ISO 8601 date） |

### chunks 配列の要素 [v2 新規]

```json
{
  "chunk_id": "a1b2c3d4_chunk_0",
  "chunk_index": 0,
  "section_title": "Valuation",
  "content": "## Valuation\n\nWe value ISAT using DCF..."
}
```

| フィールド | 型 | 必須 | 説明 |
|-----------|------|------|------|
| `chunk_id` | string | Yes | `{source_hash}_chunk_{index}` |
| `chunk_index` | integer | Yes | 0始まりのチャンクインデックス |
| `section_title` | string | No | セクション見出し |
| `content` | string | Yes | チャンクのテキスト本文（Markdown） |

### financial_datapoints 配列の要素 [v2 新規]

```json
{
  "datapoint_id": "a1b2c3d4_Revenue_FY2025",
  "metric_name": "Revenue",
  "value": 45200.0,
  "unit": "IDR bn",
  "is_estimate": false,
  "currency": "IDR",
  "period_label": "FY2025"
}
```

| フィールド | 型 | 必須 | 説明 |
|-----------|------|------|------|
| `datapoint_id` | string | Yes | `{source_hash}_{metric}_{period}` |
| `metric_name` | string | Yes | 指標名（Revenue, EBITDA, ARPU 等） |
| `value` | float | Yes | 数値 |
| `unit` | string | Yes | 単位（IDR bn, USD mn, %, x 等） |
| `is_estimate` | boolean | Yes | true=アナリスト予想、false=実績値 |
| `currency` | string | No | ISO 4217 通貨コード |
| `period_label` | string | No | 期間ラベル（FY2025, 4Q25 等）→ FiscalPeriod 派生用 |
| `source_hash` | string | No | ソース PDF の SHA-256 ハッシュ（TREND の Source-scoped グルーピング用） |

### fiscal_periods 配列の要素 [v2 新規]

```json
{
  "period_id": "ISAT_FY2025",
  "period_type": "annual",
  "period_label": "FY2025"
}
```

| フィールド | 型 | 必須 | 説明 |
|-----------|------|------|------|
| `period_id` | string | Yes | `{entity_ticker}_{period_label}` or `{period_label}` |
| `period_type` | string | Yes | annual, quarterly, half_year, monthly |
| `period_label` | string | Yes | 人間可読ラベル（FY2025, 4Q25, 1H26 等） |

### classification_nodes 配列の要素 [v3.0 新規]

```json
{
  "label": "SourceType",
  "key_property": "source_type_id",
  "properties": {
    "source_type_id": "news",
    "name": "news",
    "name_ja": "ニュース"
  }
}
```

| フィールド | 型 | 必須 | 説明 |
|-----------|------|------|------|
| `label` | string | Yes | Classification ノードのラベル名（PascalCase） |
| `key_property` | string | Yes | MERGE キーとなるプロパティ名 |
| `properties` | object | Yes | ノードの全プロパティ（key_property の値を含む） |

対応する Classification ノードラベル（16種）:

| ラベル | key_property | 分類カテゴリ |
|--------|-------------|-------------|
| SourceType | source_type_id | Source 由来 |
| Domain | domain_id | Source 由来 |
| TrustLevel | trust_level_id | Source 由来 |
| Language | language_id | Source 由来 |
| Pipeline | pipeline_id | Source 由来 |
| EntityType | entity_type_id | Entity 由来 |
| Identifier | identifier_id | Entity 由来 |
| Industry | industry_id | Entity 由来 |
| Alias | alias_id | Entity 由来 |
| FactType | fact_type_id | Content 由来 |
| ClaimType | claim_type_id | Content 由来 |
| UnitOfMeasure | unit_id | Content 由来 |
| DataPointType | datapoint_type_id | Content 由来 |
| ConceptCategory | concept_category_id | Domain |
| AuthorType | author_type_id | Domain |
| InstrumentClass | instrument_class_id | Domain |

> **後方互換性**: `classification_nodes` が graph-queue JSON に存在しない場合（v2.0/v2.2 キュー）、このフェーズはスキップされる。

### relations オブジェクト

v1 キューでは空オブジェクト `{}` として出力される。リレーションは各ノードデータ内の `source_id` 等のフィールドから暗黙推論される。

v2 キューでは明示的なリレーション定義を含む:

```json
{
  "relations": {
    "tagged": [
      {"source_id": "...", "topic_id": "..."}
    ],
    "source_claim": [
      {"from_id": "source-uuid", "to_id": "claim-hash", "type": "MAKES_CLAIM"}
    ],
    "source_fact": [
      {"from_id": "source-uuid", "to_id": "fact-hash", "type": "STATES_FACT"}
    ],
    "claim_entity": [
      {"from_id": "claim-hash", "to_id": "entity-uuid", "type": "ABOUT"}
    ],
    "fact_entity": [
      {"from_id": "fact-hash", "to_id": "entity-uuid", "type": "RELATES_TO"}
    ],
    "contains_chunk": [
      {"from_id": "source-uuid", "to_id": "chunk-id", "type": "CONTAINS_CHUNK"}
    ],
    "extracted_from_fact": [
      {"from_id": "fact-hash", "to_id": "chunk-id", "type": "EXTRACTED_FROM"}
    ],
    "extracted_from_claim": [
      {"from_id": "claim-hash", "to_id": "chunk-id", "type": "EXTRACTED_FROM"}
    ],
    "has_datapoint": [
      {"from_id": "source-uuid", "to_id": "datapoint-id", "type": "HAS_DATAPOINT"}
    ],
    "for_period": [
      {"from_id": "datapoint-id", "to_id": "period-id", "type": "FOR_PERIOD"}
    ],
    "datapoint_entity": [
      {"from_id": "datapoint-id", "to_id": "entity-uuid", "type": "RELATES_TO"}
    ],
    "classification": [
      {"from_id": "source-uuid", "from_label": "Source", "to_id": "news", "to_label": "SourceType", "type": "IS_SOURCE_TYPE"},
      {"from_id": "source-uuid", "from_label": "Source", "to_id": "example.com", "to_label": "Domain", "type": "FROM_DOMAIN"},
      {"from_id": "source-uuid", "from_label": "Source", "to_id": "media", "to_label": "TrustLevel", "type": "RATED_AS"},
      {"from_id": "source-uuid", "from_label": "Source", "to_id": "en", "to_label": "Language", "type": "IN_LANGUAGE"},
      {"from_id": "source-uuid", "from_label": "Source", "to_id": "finance-news-workflow", "to_label": "Pipeline", "type": "INGESTED_VIA"},
      {"from_id": "entity-key", "from_label": "Entity", "to_id": "company", "to_label": "EntityType", "type": "IS_TYPE"},
      {"from_id": "entity-key", "from_label": "Entity", "to_id": "ticker-id", "to_label": "Identifier", "type": "HAS_IDENTIFIER"},
      {"from_id": "entity-key", "from_label": "Entity", "to_id": "industry-id", "to_label": "Industry", "type": "IN_INDUSTRY"},
      {"from_id": "fact-hash", "from_label": "Fact", "to_id": "statistic", "to_label": "FactType", "type": "IS_FACT_TYPE"},
      {"from_id": "claim-hash", "from_label": "Claim", "to_id": "bullish", "to_label": "ClaimType", "type": "IS_CLAIM_TYPE"},
      {"from_id": "datapoint-id", "from_label": "FinancialDataPoint", "to_id": "usd", "to_label": "UnitOfMeasure", "type": "IN_UNIT"},
      {"from_id": "datapoint-id", "from_label": "FinancialDataPoint", "to_id": "actual", "to_label": "DataPointType", "type": "IS_DATAPOINT_TYPE"},
      {"from_id": "topic-key", "from_label": "Topic", "to_id": "macro", "to_label": "ConceptCategory", "type": "IS_CATEGORY"},
      {"from_id": "author-id", "from_label": "Author", "to_id": "analyst", "to_label": "AuthorType", "type": "IS_AUTHOR_TYPE"},
      {"from_id": "author-id", "from_label": "Author", "to_id": "entity-key", "to_label": "Entity", "type": "AFFILIATED_WITH"},
      {"from_id": "alias-id", "from_label": "Alias", "to_id": "entity-key", "to_label": "Entity", "type": "ALIAS_OF"},
      {"from_id": "child-ic-id", "from_label": "InstrumentClass", "to_id": "parent-ic-id", "to_label": "InstrumentClass", "type": "PARENT_CLASS"},
      {"from_id": "industry-id", "from_label": "Industry", "to_id": "sector-id", "to_label": "Sector", "type": "IN_PARENT_SECTOR"},
      {"from_id": "identifier-id", "from_label": "Identifier", "to_id": "entity-key", "to_label": "Entity", "type": "ISSUED_BY"},
      {"from_id": "entity-key", "from_label": "Entity", "to_id": "ic-id", "to_label": "InstrumentClass", "type": "IS_INSTRUMENT_CLASS"}
    ]
  }
}
```

各リレーション要素の共通形式:

| フィールド | 型 | 説明 |
|-----------|------|------|
| `from_id` | string | 起点ノードの ID |
| `to_id` | string | 終点ノードの ID |
| `type` | string | リレーションタイプ（MERGE に使用） |

---

## ID 生成戦略

全ての ID は**決定論的**に生成されます。同じ入力データからは常に同じ ID が生成されるため、
MERGE クエリによる冪等投入が可能です。

### Source ID

```python
import uuid

def generate_source_id(url: str) -> str:
    """UUID5(NAMESPACE_URL, url) で生成。"""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, url))
```

- **入力**: ソース URL
- **形式**: UUID v5（例: `6ba7b810-9dad-11d1-80b4-00c04fd430c8`）
- **特性**: 同じ URL からは常に同じ ID が生成される

### Topic ID

```python
def generate_topic_id(name: str, category: str) -> str:
    """UUID5(NAMESPACE_URL, 'topic:{name}:{category}') で生成。"""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"topic:{name}:{category}"))
```

- **入力**: トピック名 + カテゴリ
- **形式**: UUID v5
- **特性**: 名前とカテゴリの組み合わせで一意

### Entity ID

```python
def generate_entity_id(name: str, entity_type: str) -> str:
    """UUID5(NAMESPACE_URL, 'entity:{name}:{entity_type}') で生成。"""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"entity:{name}:{entity_type}"))
```

- **入力**: エンティティ名 + エンティティ種別
- **形式**: UUID v5
- **特性**: 名前と種別の組み合わせで一意

### Claim ID

```python
import hashlib

def generate_claim_id(content: str) -> str:
    """SHA-256(content)[:16] で生成。"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
```

- **入力**: 主張・事実のテキスト
- **形式**: SHA-256 ハッシュの先頭16文字（hex）
- **特性**: 同じ内容からは常に同じ ID。テキストが少しでも異なれば別 ID

### Queue ID

```python
def generate_queue_id() -> str:
    """gq-{YYYYMMDDHHmmss}-{hash4} で生成。"""
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d%H%M%S")
    hash4 = hashlib.sha256(now.isoformat().encode("utf-8")).hexdigest()[:4]
    return f"gq-{timestamp}-{hash4}"
```

- **入力**: 現在時刻（UTC）
- **形式**: `gq-{timestamp}-{hash4}`
- **特性**: ファイル命名に使用。タイムスタンプベースで一意性を確保

### 連結キー（Neo4j CE 用）

Neo4j Community Edition では複合一意制約が使えないため、連結キーを使用:

```python
# Topic の連結キー
topic_key = f"{name}::{category}"
# 例: "S&P 500::stock"

# Entity の連結キー
entity_key = f"{name}::{entity_type}"
# 例: "NVIDIA::company"
```

---

## Cypher テンプレート

### ノード MERGE テンプレート

#### Source ノード

```cypher
MERGE (s:Source {source_id: $source_id})
SET s.url = $url,
    s.title = $title,
    s.source_type = $source_type,
    s.authority_level = $authority_level,
    s.collected_at = datetime($collected_at),
    s.published_at = CASE
        WHEN $published IS NOT NULL AND $published <> ''
        THEN datetime($published)
        ELSE null
    END,
    s.category = $category,
    s.command_source = $command_source
```

**パラメータマッピング**:

| パラメータ | graph-queue フィールド | 補足 |
|-----------|----------------------|------|
| `$source_id` | `sources[].source_id` | UUID5 |
| `$url` | `sources[].url` | |
| `$title` | `sources[].title` | |
| `$source_type` | 推論 | `command_source` から推論（rss, report 等） |
| `$authority_level` | `sources[].authority_level` | official/analyst/media/blog/social/academic |
| `$collected_at` | `created_at`（キューレベル） | ISO 8601 |
| `$published` | `sources[].published` | ISO 8601 or 空文字列 |
| `$category` | `batch_label` から推論 | THEME_TO_CATEGORY 変換 |
| `$command_source` | `command_source`（キューレベル） | |

#### Topic ノード

> **MERGEキー**: `topic_key`（ビジネスキー）を使用する。
> `topic_id` はパイプラインごとに異なる値が生成される可能性があるため、
> UNIQUE制約がある `topic_key` でMERGEし、`topic_id` は ON CREATE で設定する。

```cypher
MERGE (t:Topic {topic_key: $topic_key})
ON CREATE SET t.topic_id = $topic_id
SET t.name = $name,
    t.category = $category
```

**パラメータマッピング**:

| パラメータ | graph-queue フィールド |
|-----------|----------------------|
| `$topic_key` | `topics[].topic_key` |
| `$topic_id` | `topics[].topic_id` |
| `$name` | `topics[].name` |
| `$category` | `topics[].category` |

#### Entity ノード

> **v4.0 スキーマ（KG v3.0 / Wave6以降）**: `Entity` ラベルは廃止され、13種の個別ラベルに分解された。
> MERGEキーは `name`（NODE KEY 制約）を使用する。`entity_key` は廃止。
>
> v2/v3 互換情報（歴史的参照）: `entity_key`（`{name}::{entity_type}`形式）でMERGEしていた。

```cypher
// v4.0: 個別ラベルで MERGE（entity_type に応じてラベルを選択）
// 例: Company の場合
MERGE (e:Company {name: $name})
SET e.ticker = $ticker,
    e.description = $description
```

**パラメータマッピング**:

| パラメータ | graph-queue フィールド |
|-----------|----------------------|
| `$name` | `entities[].name` |
| `$ticker` | `entities[].ticker` |

#### Claim ノード

```cypher
MERGE (c:Claim {claim_id: $claim_id})
SET c.content = $content,
    c.claim_type = $claim_type,
    c.sentiment = $sentiment,
    c.magnitude = $magnitude,
    c.target_price = $target_price,
    c.rating = $rating,
    c.time_horizon = $time_horizon,
    c.created_at = datetime($created_at)
```

> **v2 変更点**: `confidence` プロパティを削除。`sentiment`、`magnitude`、`created_at` を追加。

**パラメータマッピング**:

| パラメータ | graph-queue フィールド | 補足 |
|-----------|----------------------|------|
| `$claim_id` | `claims[].claim_id` | SHA-256[:16] |
| `$content` | `claims[].content` | |
| `$claim_type` | `claims[].claim_type` | 未設定時は null |
| `$sentiment` | `claims[].sentiment` | bullish/bearish/neutral/mixed、未設定時は null |
| `$magnitude` | `claims[].magnitude` | strong/moderate/slight、未設定時は null |
| `$target_price` | `claims[].target_price` | 数値文字列、未設定時は null |
| `$rating` | `claims[].rating` | buy/sell/hold 等、未設定時は null |
| `$time_horizon` | `claims[].time_horizon` | 期間文字列、未設定時は null |
| `$created_at` | `created_at`（キューレベル） | ISO 8601 |

#### Fact ノード [v2 新規]

```cypher
MERGE (f:Fact {fact_id: $fact_id})
SET f.content = $content,
    f.fact_type = $fact_type,
    f.as_of_date = CASE
        WHEN $as_of_date IS NOT NULL AND $as_of_date <> ''
        THEN date($as_of_date)
        ELSE null
    END,
    f.created_at = datetime($created_at)
```

**パラメータマッピング**:

| パラメータ | graph-queue フィールド | 補足 |
|-----------|----------------------|------|
| `$fact_id` | `facts[].fact_id` | SHA-256("fact:{content}")[:16] |
| `$content` | `facts[].content` | |
| `$fact_type` | `facts[].fact_type` | statistic/event/data_point/quote 等 |
| `$as_of_date` | `facts[].as_of_date` | ISO 8601 date or 空文字列 |
| `$created_at` | `created_at`（キューレベル） | ISO 8601 |

#### Chunk ノード [v2 新規]

```cypher
MERGE (ch:Chunk {chunk_id: $chunk_id})
SET ch.chunk_index = $chunk_index,
    ch.section_title = $section_title,
    ch.content = $content,
    ch.char_count = size($content),
    ch.created_at = datetime($created_at)
```

**パラメータマッピング**:

| パラメータ | graph-queue フィールド | 補足 |
|-----------|----------------------|------|
| `$chunk_id` | `chunks[].chunk_id` | `{source_hash}_chunk_{index}` |
| `$chunk_index` | `chunks[].chunk_index` | 0始まり |
| `$section_title` | `chunks[].section_title` | |
| `$content` | `chunks[].content` | Markdown テキスト |
| `$created_at` | `created_at`（キューレベル） | ISO 8601 |

#### FinancialDataPoint ノード [v2 新規]

```cypher
MERGE (dp:FinancialDataPoint {datapoint_id: $datapoint_id})
SET dp.metric_name = $metric_name,
    dp.value = $value,
    dp.unit = $unit,
    dp.is_estimate = $is_estimate,
    dp.currency = $currency,
    dp.source_hash = $source_hash,
    dp.created_at = datetime($created_at)
```

**パラメータマッピング**:

| パラメータ | graph-queue フィールド | 補足 |
|-----------|----------------------|------|
| `$datapoint_id` | `financial_datapoints[].datapoint_id` | `{source_hash}_{metric}_{period}` |
| `$metric_name` | `financial_datapoints[].metric_name` | |
| `$value` | `financial_datapoints[].value` | float |
| `$unit` | `financial_datapoints[].unit` | |
| `$is_estimate` | `financial_datapoints[].is_estimate` | boolean |
| `$currency` | `financial_datapoints[].currency` | ISO 4217 or null |
| `$created_at` | `created_at`（キューレベル） | ISO 8601 |

#### FiscalPeriod ノード [v2 新規]

```cypher
MERGE (fp:FiscalPeriod {period_id: $period_id})
SET fp.period_type = $period_type,
    fp.period_label = $period_label
```

**パラメータマッピング**:

| パラメータ | graph-queue フィールド | 補足 |
|-----------|----------------------|------|
| `$period_id` | `fiscal_periods[].period_id` | `{ticker}_{label}` or `{label}` |
| `$period_type` | `fiscal_periods[].period_type` | annual/quarterly/half_year/monthly |
| `$period_label` | `fiscal_periods[].period_label` | FY2025, 4Q25 等 |

### v2 新規リレーション MERGE テンプレート

#### CONTAINS_CHUNK（Source -> Chunk）

```cypher
MATCH (s:Source {source_id: $from_id})
MATCH (ch:Chunk {chunk_id: $to_id})
MERGE (s)-[:CONTAINS_CHUNK]->(ch)
```

#### EXTRACTED_FROM（Fact/Claim -> Chunk or Source）

```cypher
-- Fact -> Chunk（chunk ベースパス: PDF等マルチチャンクソース）
MATCH (f:Fact {fact_id: $from_id})
MATCH (ch:Chunk {chunk_id: $to_id})
MERGE (f)-[:EXTRACTED_FROM]->(ch)

-- Claim -> Chunk（chunk ベースパス）
MATCH (c:Claim {claim_id: $from_id})
MATCH (ch:Chunk {chunk_id: $to_id})
MERGE (c)-[:EXTRACTED_FROM]->(ch)

-- web-research パスでは to_id が source_id を指し、Source に直接リンクする
```

#### STATES_FACT（Source -> Fact）

```cypher
MATCH (s:Source {source_id: $from_id})
MATCH (f:Fact {fact_id: $to_id})
MERGE (s)-[:STATES_FACT]->(f)
```

#### RELATES_TO（Fact/FinancialDataPoint -> Entity系ラベル）

```cypher
-- Fact -> Entity系ラベル（neo4j_loader.py がラベルを動的に選択）
MATCH (f:Fact {fact_id: $from_id})
MATCH (e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product {name: $to_name})
MERGE (f)-[:RELATES_TO]->(e)

-- FinancialDataPoint -> Entity系ラベル
MATCH (dp:FinancialDataPoint {datapoint_id: $from_id})
MATCH (e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product {name: $to_name})
MERGE (dp)-[:RELATES_TO]->(e)
```

#### HAS_DATAPOINT（Source -> FinancialDataPoint）

```cypher
MATCH (s:Source {source_id: $from_id})
MATCH (dp:FinancialDataPoint {datapoint_id: $to_id})
MERGE (s)-[:HAS_DATAPOINT]->(dp)
```

#### FOR_PERIOD（FinancialDataPoint -> FiscalPeriod）

```cypher
MATCH (dp:FinancialDataPoint {datapoint_id: $from_id})
MATCH (fp:FiscalPeriod {period_id: $to_id})
MERGE (dp)-[:FOR_PERIOD]->(fp)
```

### v1 リレーション MERGE テンプレート

#### TAGGED（Source -> Topic）

```cypher
MATCH (s:Source {source_id: $source_id})
MATCH (t:Topic {topic_id: $topic_id})
MERGE (s)-[:TAGGED]->(t)
```

**リレーション推論ルール**:

同一 graph-queue ファイル内の Source と Topic は暗黙的に TAGGED 関係にある。
具体的には:

1. `relations.tagged` が明示的に定義されている場合はそれを使用
2. 定義がない場合、同一ファイル内の全 Source と全 Topic を TAGGED で接続

#### MAKES_CLAIM（Source -> Claim）

```cypher
MATCH (s:Source {source_id: $source_id})
MATCH (c:Claim {claim_id: $claim_id})
MERGE (s)-[:MAKES_CLAIM]->(c)
```

**リレーション推論ルール**:

Claim の `source_id` フィールドから Source との紐付けを推論:

```python
for claim in claims:
    source_id = claim.get("source_id")
    if source_id:
        # source_id が明示的に設定されている場合
        create_makes_claim(source_id, claim["claim_id"])
    else:
        # source_url から source_id を逆算
        source_url = claim.get("source_url", "")
        if source_url:
            source_id = generate_source_id(source_url)
            create_makes_claim(source_id, claim["claim_id"])
```

#### RELATES_TO（Claim -> Entity系ラベル）

> **v4.0 変更点（Wave5）**: `ABOUT` は廃止。Claim → Entity 系の接続は `RELATES_TO` に統一。

```cypher
MATCH (c:Claim {claim_id: $claim_id})
MATCH (e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product {name: $entity_name})
MERGE (c)-[:RELATES_TO]->(e)
```

**リレーション推論ルール**:

現在の graph-queue フォーマットでは Claim と Entity 系ラベルの明示的な紐付けは
`relations.claim_entity` フィールドで定義されます。`type: "RELATES_TO"` を使用すること。

---

## ノード投入詳細

### 投入順序

依存関係に基づき、以下の順序で投入します:

```
Phase 2-0: Master Nodes（v2 互換。v3 では Phase 1.5 で処理）
  -- v2 キューの場合のみ。分類ノードが classification_nodes にない場合のフォールバック。

Phase 1.5: Classification Nodes [v3.0 新規]
  1. SourceType, Domain, TrustLevel, Language, Pipeline   (Source 分類)
  2. EntityType, Identifier, Industry, Alias              (Entity 分類)
  3. FactType, ClaimType, UnitOfMeasure, DataPointType    (Content 分類)
  4. ConceptCategory, AuthorType, InstrumentClass         (Domain 分類)
  -- classification_nodes が JSON にない場合はスキップ（v2.0 互換）

Phase 2: Core Nodes
  1. Topic            (他ノードに依存しない)
  2. Entity           (他ノードに依存しない)
  3. FiscalPeriod     (他ノードに依存しない) [v2 新規]
  4. Source           (他ノードに依存しない)
  5. Author           (他ノードに依存しない) [v2 新規]

Phase 2-3: Content Nodes
  6. Chunk            (CONTAINS_CHUNK で Source を参照) [v2 新規]
  7. Fact             (STATES_FACT で Source を参照、EXTRACTED_FROM で Chunk を参照) [v2 新規]
  8. Claim            (MAKES_CLAIM で Source を参照、EXTRACTED_FROM で Chunk を参照)
  9. FinancialDataPoint (HAS_DATAPOINT で Source を参照、FOR_PERIOD で FiscalPeriod を参照) [v2 新規]

Phase 3-0: Classification Relationships [v3.0 新規]
  -- relations.classification 配列の処理（20種の分類リレーション）
  -- classification_nodes/relations.classification が JSON にない場合はスキップ

Phase 3: Core Relationships
  -- 従来の TAGGED, MAKES_CLAIM, ABOUT, CONTAINS_CHUNK 等
```

全体の処理順序: **Master nodes → Classification nodes → Core nodes → Content nodes → Classification rels → Core rels**

ノード自体は独立していますが、リレーション投入時にすべてのノードが存在している必要があります。
v1 キューファイルの場合、ステップ 3, 5, 6, 7, 9 はスキップされます（対象データが空配列）。
v2 キューファイルの場合、classification_nodes が存在しないため Phase 1.5 / Phase 3-0 はスキップされます。

### cypher-shell での実行方法

```bash
# パラメータ付き実行（シングルクォートを含む値でもインジェクションを防止）
cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -a "$NEO4J_URI" \
  --param "topic_id => 'uuid-here'" \
  --param "name => 'S&P 500'" \
  --param "category => 'stock'" \
  "MERGE (t:Topic {topic_key: \$topic_key}) ON CREATE SET t.topic_id = \$topic_id SET t.name = \$name, t.category = \$category"
```

> **注意**: 値の直接埋め込み（`'S&P 500'` 等）は Cypher インジェクションのリスクがあるため、
> 必ず `--param` 付きパラメータ化形式を使用してください。

### バッチ投入パターン

大量のノードを効率的に投入するため、UNWIND を使用:

```cypher
-- Topic バッチ投入（topic_key でMERGE）
UNWIND $topics AS topic
MERGE (t:Topic {topic_key: topic.topic_key})
ON CREATE SET t.topic_id = topic.topic_id
SET t.name = topic.name,
    t.category = topic.category

-- Source バッチ投入
UNWIND $sources AS src
MERGE (s:Source {source_id: src.source_id})
SET s.url = src.url,
    s.title = src.title,
    s.source_type = src.source_type,
    s.authority_level = src.authority_level,
    s.collected_at = datetime(src.collected_at),
    s.published_at = CASE
        WHEN src.published IS NOT NULL AND src.published <> ''
        THEN datetime(src.published)
        ELSE null
    END,
    s.category = src.category,
    s.command_source = src.command_source
```

### Author バッチ投入 [Wave 1 新規]

```cypher
-- Author バッチ投入
UNWIND $authors AS author
MERGE (a:Author {author_id: author.author_id})
SET a.name = author.name,
    a.author_type = author.author_type,
    a.organization = author.organization
```

### Stance バッチ投入 [Wave 1 新規]

```cypher
-- Stance バッチ投入
UNWIND $stances AS stance
MERGE (st:Stance {stance_id: stance.stance_id})
SET st.rating = stance.rating,
    st.sentiment = stance.sentiment,
    st.target_price = stance.target_price,
    st.target_price_currency = stance.target_price_currency,
    st.as_of_date = CASE
        WHEN stance.as_of_date IS NOT NULL AND stance.as_of_date <> ''
        THEN date(stance.as_of_date)
        ELSE null
    END,
    st.created_at = datetime()
```

### Wave 1 リレーション投入

```cypher
-- HOLDS_STANCE: Author -> Stance
UNWIND $holds_stance AS rel
MATCH (a:Author {author_id: rel.from_id})
MATCH (st:Stance {stance_id: rel.to_id})
MERGE (a)-[:HOLDS_STANCE]->(st)

-- ON_ENTITY: Stance -> Entity系ラベル
UNWIND $on_entity AS rel
MATCH (st:Stance {stance_id: rel.from_id})
MATCH (e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product {name: rel.to_name})
MERGE (st)-[:ON_ENTITY]->(e)

-- BASED_ON: Stance -> Claim
UNWIND $based_on AS rel
MATCH (st:Stance {stance_id: rel.from_id})
MATCH (c:Claim {claim_id: rel.to_id})
MERGE (st)-[r:BASED_ON]->(c)
SET r.role = rel.role

-- SUPERSEDES: Stance -> Stance (newer supersedes older)
UNWIND $supersedes AS rel
MATCH (newer:Stance {stance_id: rel.from_id})
MATCH (older:Stance {stance_id: rel.to_id})
MERGE (newer)-[r:SUPERSEDES]->(older)
SET r.superseded_at = CASE
        WHEN rel.superseded_at IS NOT NULL AND rel.superseded_at <> ''
        THEN datetime(rel.superseded_at)
        ELSE datetime()
    END

-- AUTHORED_BY: Source -> Author (Phase 2)
UNWIND $authored_by AS rel
MATCH (s:Source {source_id: rel.from_id})
MATCH (a:Author {author_id: rel.to_id})
MERGE (s)-[:AUTHORED_BY]->(a)

-- CITES: Source -> Source (academic-fetch)
UNWIND $cites AS rel
MATCH (s1:Source {source_id: rel.from_id})
MATCH (s2:Source {source_id: rel.to_id})
MERGE (s1)-[:CITES]->(s2)

-- COAUTHORED_WITH: Author -> Author (academic-fetch)
UNWIND $coauthored_with AS rel
MATCH (a1:Author {author_id: rel.from_id})
MATCH (a2:Author {author_id: rel.to_id})
MERGE (a1)-[r:COAUTHORED_WITH]->(a2)
SET r.paper_count = rel.paper_count,
    r.first_collaboration = rel.first_collaboration
```

### Wave 2 リレーション投入

```cypher
-- CAUSES: Fact/Claim/FinancialDataPoint -> Fact/Claim/FinancialDataPoint
-- Neo4j CE ではリレーションの from/to に複数ラベルを指定できないため、
-- from_label / to_label プロパティでラベルを分岐して MATCH する。

-- CAUSES (from: Fact)
UNWIND $causes AS rel
WITH rel WHERE rel.from_label = 'Fact'
CALL {
  WITH rel
  MATCH (f:Fact {fact_id: rel.from_id})
  WITH f, rel
  // to_label 分岐
  CALL {
    WITH f, rel
    WITH f, rel WHERE rel.to_label = 'Fact'
    MATCH (t:Fact {fact_id: rel.to_id})
    MERGE (f)-[r:CAUSES]->(t)
    SET r.mechanism = rel.mechanism,
        r.confidence = rel.confidence,
        r.source_id = rel.source_id,
        r.from_label = rel.from_label,
        r.to_label = rel.to_label
    UNION
    WITH f, rel WHERE rel.to_label = 'Claim'
    MATCH (t:Claim {claim_id: rel.to_id})
    MERGE (f)-[r:CAUSES]->(t)
    SET r.mechanism = rel.mechanism,
        r.confidence = rel.confidence,
        r.source_id = rel.source_id,
        r.from_label = rel.from_label,
        r.to_label = rel.to_label
    UNION
    WITH f, rel WHERE rel.to_label = 'FinancialDataPoint'
    MATCH (t:FinancialDataPoint {datapoint_id: rel.to_id})
    MERGE (f)-[r:CAUSES]->(t)
    SET r.mechanism = rel.mechanism,
        r.confidence = rel.confidence,
        r.source_id = rel.source_id,
        r.from_label = rel.from_label,
        r.to_label = rel.to_label
  }
}

-- CAUSES (from: Claim)
UNWIND $causes AS rel
WITH rel WHERE rel.from_label = 'Claim'
CALL {
  WITH rel
  MATCH (c:Claim {claim_id: rel.from_id})
  WITH c, rel
  CALL {
    WITH c, rel
    WITH c, rel WHERE rel.to_label = 'Fact'
    MATCH (t:Fact {fact_id: rel.to_id})
    MERGE (c)-[r:CAUSES]->(t)
    SET r.mechanism = rel.mechanism,
        r.confidence = rel.confidence,
        r.source_id = rel.source_id,
        r.from_label = rel.from_label,
        r.to_label = rel.to_label
    UNION
    WITH c, rel WHERE rel.to_label = 'Claim'
    MATCH (t:Claim {claim_id: rel.to_id})
    MERGE (c)-[r:CAUSES]->(t)
    SET r.mechanism = rel.mechanism,
        r.confidence = rel.confidence,
        r.source_id = rel.source_id,
        r.from_label = rel.from_label,
        r.to_label = rel.to_label
    UNION
    WITH c, rel WHERE rel.to_label = 'FinancialDataPoint'
    MATCH (t:FinancialDataPoint {datapoint_id: rel.to_id})
    MERGE (c)-[r:CAUSES]->(t)
    SET r.mechanism = rel.mechanism,
        r.confidence = rel.confidence,
        r.source_id = rel.source_id,
        r.from_label = rel.from_label,
        r.to_label = rel.to_label
  }
}

-- CAUSES (from: FinancialDataPoint)
UNWIND $causes AS rel
WITH rel WHERE rel.from_label = 'FinancialDataPoint'
CALL {
  WITH rel
  MATCH (dp:FinancialDataPoint {datapoint_id: rel.from_id})
  WITH dp, rel
  CALL {
    WITH dp, rel
    WITH dp, rel WHERE rel.to_label = 'Fact'
    MATCH (t:Fact {fact_id: rel.to_id})
    MERGE (dp)-[r:CAUSES]->(t)
    SET r.mechanism = rel.mechanism,
        r.confidence = rel.confidence,
        r.source_id = rel.source_id,
        r.from_label = rel.from_label,
        r.to_label = rel.to_label
    UNION
    WITH dp, rel WHERE rel.to_label = 'Claim'
    MATCH (t:Claim {claim_id: rel.to_id})
    MERGE (dp)-[r:CAUSES]->(t)
    SET r.mechanism = rel.mechanism,
        r.confidence = rel.confidence,
        r.source_id = rel.source_id,
        r.from_label = rel.from_label,
        r.to_label = rel.to_label
    UNION
    WITH dp, rel WHERE rel.to_label = 'FinancialDataPoint'
    MATCH (t:FinancialDataPoint {datapoint_id: rel.to_id})
    MERGE (dp)-[r:CAUSES]->(t)
    SET r.mechanism = rel.mechanism,
        r.confidence = rel.confidence,
        r.source_id = rel.source_id,
        r.from_label = rel.from_label,
        r.to_label = rel.to_label
  }
}
```

#### NEXT_PERIOD (FiscalPeriod -> FiscalPeriod)

```cypher
-- NEXT_PERIOD: FiscalPeriod -> FiscalPeriod (temporal ordering)
-- ticker別・period_type別に独立した連鎖を構築
UNWIND $rels AS rel
MATCH (from:FiscalPeriod {period_id: rel.from_id})
MATCH (to:FiscalPeriod {period_id: rel.to_id})
MERGE (from)-[r:NEXT_PERIOD]->(to)
SET r.gap_months = rel.gap_months
```

#### TREND (FinancialDataPoint -> FinancialDataPoint)

```cypher
-- TREND: FinancialDataPoint -> FinancialDataPoint (metric trend)
-- 同一 (entity, metric_key) 間の時系列変化率を追跡（metric_id でグルーピング）
UNWIND $rels AS rel
MATCH (from:FinancialDataPoint {datapoint_id: rel.from_id})
MATCH (to:FinancialDataPoint {datapoint_id: rel.to_id})
MERGE (from)-[r:TREND]->(to)
SET r.change_pct = rel.change_pct,
    r.direction = rel.direction,
    r.metric_id = rel.metric_id
```

### Question バッチ投入 [Wave 4 新規]

```cypher
-- Question バッチ投入
UNWIND $questions AS question
MERGE (q:Question {question_id: question.question_id})
SET q.content = question.content,
    q.question_type = question.question_type,
    q.priority = question.priority,
    q.status = question.status,
    q.generated_at = datetime()
```

### Wave 4 リレーション投入

```cypher
-- ASKS_ABOUT: Question -> Entity系ラベル
UNWIND $asks_about AS rel
MATCH (q:Question {question_id: rel.from_id})
MATCH (e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product {name: rel.to_name})
MERGE (q)-[:ASKS_ABOUT]->(e)

-- MOTIVATED_BY: Question -> Claim/Fact/Insight
-- Neo4j CE ではリレーションの to に複数ラベルを指定できないため、
-- 各ラベルを順番に試行する。
UNWIND $motivated_by AS rel
OPTIONAL MATCH (c:Claim {claim_id: rel.to_id})
OPTIONAL MATCH (f:Fact {fact_id: rel.to_id})
OPTIONAL MATCH (i:Insight {insight_id: rel.to_id})
WITH rel,
     COALESCE(c, f, i) AS target
WHERE target IS NOT NULL
MATCH (q:Question {question_id: rel.from_id})
MERGE (q)-[:MOTIVATED_BY]->(target)

-- ANSWERED_BY: Question -> Fact/Claim/Source (future use)
-- Note: ANSWERED_BY は後続の調査・回答フェーズで付与される。
-- graph-queue 生成時には生成されない。
UNWIND $answered_by AS rel
OPTIONAL MATCH (f:Fact {fact_id: rel.to_id})
OPTIONAL MATCH (c:Claim {claim_id: rel.to_id})
OPTIONAL MATCH (s:Source {source_id: rel.to_id})
WITH rel,
     COALESCE(f, c, s) AS target
WHERE target IS NOT NULL
MATCH (q:Question {question_id: rel.from_id})
MERGE (q)-[r:ANSWERED_BY]->(target)
SET r.answered_at = CASE
        WHEN rel.answered_at IS NOT NULL AND rel.answered_at <> ''
        THEN datetime(rel.answered_at)
        ELSE datetime()
    END
```

### source_type の推論

`command_source` から `source_type` を推論:

| command_source | source_type |
|---------------|-------------|
| finance-news-workflow | rss |
| ai-research-collect | report |
| generate-market-report | report |
| asset-management | rss |
| reddit-finance-topics | reddit |
| finance-full | mixed |

---

## Phase 1.5: Classification Node Processing

> **v3.0 新規**。`classification_nodes` 配列が graph-queue JSON に含まれる場合に実行される。
> v2.0/v2.2 キューでは `classification_nodes` が存在しないため、このフェーズ全体をスキップする（後方互換）。

### 概要

Classification ノードは、Core/Content ノードのプロパティを外部化した薄いハブノードです。
v3.0 オントロジーでは 16 種の Classification ノードが定義されており、
Core/Content ノードと分類リレーション（20種）で接続されます。

### 後方互換性チェック

```python
def should_process_classification_nodes(queue_data: dict) -> bool:
    """classification_nodes の存在をチェック。v2.0 互換。"""
    classification_nodes = queue_data.get("classification_nodes")
    if classification_nodes is None or len(classification_nodes) == 0:
        logger.info("classification_nodes not found, skipping Phase 1.5 (v2.0 compat)")
        return False
    return True
```

### schema_version チェック

```python
SUPPORTED_SCHEMA_VERSIONS = {"1.0", "2.0", "2.2", "3.0"}

def validate_schema_version(version: str) -> None:
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        raise ValueError(
            f"Unsupported schema_version: {version}. "
            f"Supported: {', '.join(sorted(SUPPORTED_SCHEMA_VERSIONS))}"
        )
```

### Classification ノードの MERGE パターン

各 Classification ノードは `label` と `key_property` で MERGE される。
MERGE パターンは `merge-guide.md` に準拠する。

#### 汎用 MERGE テンプレート

```python
def merge_classification_node(tx, node: dict) -> None:
    """Classification ノードを MERGE する汎用関数。"""
    label = node["label"]
    key_prop = node["key_property"]
    props = node["properties"]
    key_value = props[key_prop]

    # 動的 Cypher 生成
    set_clauses = ", ".join(
        f"n.{k} = ${k}" for k in props if k != key_prop
    )
    cypher = f"""
        MERGE (n:{label} {{{key_prop}: ${key_prop}}})
        ON CREATE SET {set_clauses}
        ON MATCH SET {set_clauses}
    """
    tx.run(cypher, **props)
```

#### 各ラベルの Cypher パターン（merge-guide.md 準拠）

##### SourceType

```cypher
MERGE (n:SourceType {source_type_id: $source_type_id})
ON CREATE SET n.name = $name, n.name_ja = $name_ja
ON MATCH SET n.name_ja = $name_ja
```

##### Domain

```cypher
MERGE (n:Domain {domain_id: $domain_id})
ON CREATE SET n.name = $name, n.base_url = $base_url, n.default_language = $default_language
ON MATCH SET n.base_url = COALESCE($base_url, n.base_url), n.default_language = COALESCE($default_language, n.default_language)
```

##### TrustLevel

```cypher
MERGE (n:TrustLevel {trust_level_id: $trust_level_id})
ON CREATE SET n.name = $name, n.name_ja = $name_ja, n.rank = $rank
ON MATCH SET n.name_ja = $name_ja, n.rank = $rank
```

##### Language

```cypher
MERGE (n:Language {language_id: $language_id})
ON CREATE SET n.name = $name, n.name_ja = $name_ja
ON MATCH SET n.name_ja = $name_ja
```

##### Pipeline

```cypher
MERGE (n:Pipeline {pipeline_id: $pipeline_id})
ON CREATE SET n.name = $name, n.description = $description, n.category = $category
ON MATCH SET n.description = $description, n.category = $category
```

##### EntityType

```cypher
MERGE (n:EntityType {entity_type_id: $entity_type_id})
ON CREATE SET n.name = $name, n.name_ja = $name_ja, n.description = $description, n.normalization_rule = $normalization_rule
ON MATCH SET n.name_ja = $name_ja
```

##### Identifier

```cypher
MERGE (n:Identifier {identifier_id: $identifier_id})
ON CREATE SET n.type = $type, n.value = $value, n.scheme = $scheme
ON MATCH SET n.value = $value, n.scheme = $scheme
```

##### Industry

```cypher
MERGE (n:Industry {industry_id: $industry_id})
ON CREATE SET n.name = $name
ON MATCH SET n.name = $name
```

##### Alias

```cypher
MERGE (n:Alias {alias_id: $alias_id})
ON CREATE SET n.name = $name, n.alias_type = $alias_type, n.language = $language
ON MATCH SET n.name = $name
```

##### FactType

```cypher
MERGE (n:FactType {fact_type_id: $fact_type_id})
ON CREATE SET n.name = $name, n.name_ja = $name_ja, n.category = $category
ON MATCH SET n.name_ja = $name_ja
```

##### ClaimType

```cypher
MERGE (n:ClaimType {claim_type_id: $claim_type_id})
ON CREATE SET n.name = $name, n.name_ja = $name_ja, n.direction = $direction
ON MATCH SET n.name_ja = $name_ja
```

##### UnitOfMeasure

```cypher
MERGE (n:UnitOfMeasure {unit_id: $unit_id})
ON CREATE SET n.name = $name, n.symbol = $symbol, n.dimension = $dimension
ON MATCH SET n.symbol = $symbol, n.dimension = $dimension
```

##### DataPointType

```cypher
MERGE (n:DataPointType {datapoint_type_id: $datapoint_type_id})
ON CREATE SET n.name = $name, n.name_ja = $name_ja
ON MATCH SET n.name_ja = $name_ja
```

##### ConceptCategory

```cypher
MERGE (n:ConceptCategory {concept_category_id: $concept_category_id})
ON CREATE SET n.name = $name, n.name_ja = $name_ja, n.layer = $layer
ON MATCH SET n.name_ja = $name_ja, n.layer = $layer
```

##### AuthorType

```cypher
MERGE (n:AuthorType {author_type_id: $author_type_id})
ON CREATE SET n.name = $name, n.name_ja = $name_ja
ON MATCH SET n.name_ja = $name_ja
```

##### InstrumentClass

```cypher
MERGE (n:InstrumentClass {instrument_class_id: $instrument_class_id})
ON CREATE SET n.name = $name, n.name_ja = $name_ja, n.fibo_domain = $fibo_domain
ON MATCH SET n.name_ja = $name_ja, n.fibo_domain = $fibo_domain
```

### バッチ投入パターン

```python
def batch_merge_classification_nodes(tx, classification_nodes: list[dict]) -> int:
    """Classification ノードをバッチ MERGE する。"""
    count = 0
    for node in classification_nodes:
        merge_classification_node(tx, node)
        count += 1
    logger.info("Classification nodes merged", count=count)
    return count
```

### Classification リレーション投入（Phase 3-0）

Classification ノード投入後、Core/Content ノードとの分類リレーションを投入する。
`relations.classification` 配列から読み取る。

#### 対応リレーション一覧（20種）

| リレーションタイプ | From | To | 説明 |
|-------------------|------|-----|------|
| IS_SOURCE_TYPE | Source | SourceType | ソースの種類分類 |
| FROM_DOMAIN | Source | Domain | ソースのWebドメイン |
| RATED_AS | Source | TrustLevel | ソースの信頼度評価 |
| IN_LANGUAGE | Source | Language | ソースの言語 |
| INGESTED_VIA | Source | Pipeline | データ投入パイプライン |
| IS_TYPE | Entity | EntityType | エンティティのサブタイプ |
| HAS_IDENTIFIER | Entity | Identifier | FIBO hasIdentifier パターン |
| IN_INDUSTRY | Entity | Industry | 産業分類 |
| ALIAS_OF | Alias | Entity/Topic | 別名の正規化リンク |
| IS_INSTRUMENT_CLASS | Entity | InstrumentClass | FIBO 金融商品種類分類 |
| IS_FACT_TYPE | Fact | FactType | 事実の種類分類 |
| IS_CLAIM_TYPE | Claim | ClaimType | 主張の種類分類 |
| IN_UNIT | FDP/Stance | UnitOfMeasure | 単位（通貨含む） |
| IS_DATAPOINT_TYPE | FinancialDataPoint | DataPointType | 実績/予想/予測/コンセンサス |
| IS_CATEGORY | Topic | ConceptCategory | トピックの上位概念カテゴリ |
| IS_AUTHOR_TYPE | Author | AuthorType | 著者の種類分類 |
| AFFILIATED_WITH | Author | Entity | 著者の所属組織 |
| PARENT_CLASS | InstrumentClass | InstrumentClass | InstrumentClass L2→L1 階層 |
| IN_PARENT_SECTOR | Industry | Sector | 産業の親セクター |
| ISSUED_BY | Identifier | Entity | 識別子の発行機関 |

#### Classification リレーション MERGE テンプレート

```python
# Classification リレーションの MERGE パターンマッピング
CLASSIFICATION_REL_PATTERNS = {
    "IS_SOURCE_TYPE":    {"from": ("Source", "source_id"),       "to": ("SourceType", "source_type_id")},
    "FROM_DOMAIN":       {"from": ("Source", "source_id"),       "to": ("Domain", "domain_id")},
    "RATED_AS":          {"from": ("Source", "source_id"),       "to": ("TrustLevel", "trust_level_id")},
    "IN_LANGUAGE":       {"from": ("Source", "source_id"),       "to": ("Language", "language_id")},
    "INGESTED_VIA":      {"from": ("Source", "source_id"),       "to": ("Pipeline", "pipeline_id")},
    "IS_TYPE":           {"from": ("Entity", "entity_key"),      "to": ("EntityType", "entity_type_id")},
    "HAS_IDENTIFIER":    {"from": ("Entity", "entity_key"),      "to": ("Identifier", "identifier_id")},
    "IN_INDUSTRY":       {"from": ("Entity", "entity_key"),      "to": ("Industry", "industry_id")},
    "ALIAS_OF":          {"from": ("Alias", "alias_id"),         "to": None},  # dynamic target
    "IS_INSTRUMENT_CLASS": {"from": ("Entity", "entity_key"),    "to": ("InstrumentClass", "instrument_class_id")},
    "IS_FACT_TYPE":      {"from": ("Fact", "fact_id"),           "to": ("FactType", "fact_type_id")},
    "IS_CLAIM_TYPE":     {"from": ("Claim", "claim_id"),        "to": ("ClaimType", "claim_type_id")},
    "IN_UNIT":           {"from": None, "to": ("UnitOfMeasure", "unit_id")},  # dynamic source
    "IS_DATAPOINT_TYPE": {"from": ("FinancialDataPoint", "datapoint_id"), "to": ("DataPointType", "datapoint_type_id")},
    "IS_CATEGORY":       {"from": ("Topic", "topic_key"),       "to": ("ConceptCategory", "concept_category_id")},
    "IS_AUTHOR_TYPE":    {"from": ("Author", "author_id"),      "to": ("AuthorType", "author_type_id")},
    "AFFILIATED_WITH":   {"from": ("Author", "author_id"),      "to": ("Entity", "entity_key")},
    "PARENT_CLASS":      {"from": ("InstrumentClass", "instrument_class_id"), "to": ("InstrumentClass", "instrument_class_id")},
    "IN_PARENT_SECTOR":  {"from": ("Industry", "industry_id"),  "to": ("Sector", "sector_id")},
    "ISSUED_BY":         {"from": ("Identifier", "identifier_id"), "to": ("Entity", "entity_key")},
}
```

#### Cypher テンプレート（各リレーション）

```cypher
// IS_SOURCE_TYPE: Source → SourceType
MATCH (s:Source {source_id: $from_id})
MATCH (t:SourceType {source_type_id: $to_id})
MERGE (s)-[:IS_SOURCE_TYPE]->(t)

// FROM_DOMAIN: Source → Domain
MATCH (s:Source {source_id: $from_id})
MATCH (d:Domain {domain_id: $to_id})
MERGE (s)-[:FROM_DOMAIN]->(d)

// RATED_AS: Source → TrustLevel
MATCH (s:Source {source_id: $from_id})
MATCH (t:TrustLevel {trust_level_id: $to_id})
MERGE (s)-[:RATED_AS]->(t)

// IN_LANGUAGE: Source → Language
MATCH (s:Source {source_id: $from_id})
MATCH (l:Language {language_id: $to_id})
MERGE (s)-[:IN_LANGUAGE]->(l)

// INGESTED_VIA: Source → Pipeline
MATCH (s:Source {source_id: $from_id})
MATCH (p:Pipeline {pipeline_id: $to_id})
MERGE (s)-[:INGESTED_VIA]->(p)

// IS_TYPE: Entity系ラベル → EntityType（v4.0: entity_key廃止→nameで照合）
MATCH (e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product {name: $from_name})
MATCH (t:EntityType {entity_type_id: $to_id})
MERGE (e)-[:IS_TYPE]->(t)

// HAS_IDENTIFIER: Entity系ラベル → Identifier
MATCH (e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product {name: $from_name})
MATCH (i:Identifier {identifier_id: $to_id})
MERGE (e)-[:HAS_IDENTIFIER]->(i)

// IN_INDUSTRY: Entity系ラベル → Industry
MATCH (e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product {name: $from_name})
MATCH (i:Industry {industry_id: $to_id})
MERGE (e)-[:IN_INDUSTRY]->(i)

// IS_INSTRUMENT_CLASS: Entity系ラベル → InstrumentClass
MATCH (e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product {name: $from_name})
MATCH (ic:InstrumentClass {instrument_class_id: $to_id})
MERGE (e)-[:IS_INSTRUMENT_CLASS]->(ic)

// IS_FACT_TYPE: Fact → FactType
MATCH (f:Fact {fact_id: $from_id})
MATCH (ft:FactType {fact_type_id: $to_id})
MERGE (f)-[:IS_FACT_TYPE]->(ft)

// IS_CLAIM_TYPE: Claim → ClaimType
MATCH (c:Claim {claim_id: $from_id})
MATCH (ct:ClaimType {claim_type_id: $to_id})
MERGE (c)-[:IS_CLAIM_TYPE]->(ct)

// IN_UNIT: FDP/Stance → UnitOfMeasure (from_label で分岐)
// from_label = "FinancialDataPoint":
MATCH (fdp:FinancialDataPoint {datapoint_id: $from_id})
MATCH (u:UnitOfMeasure {unit_id: $to_id})
MERGE (fdp)-[:IN_UNIT]->(u)
// from_label = "Stance":
MATCH (st:Stance {stance_id: $from_id})
MATCH (u:UnitOfMeasure {unit_id: $to_id})
MERGE (st)-[:IN_UNIT]->(u)

// IS_DATAPOINT_TYPE: FinancialDataPoint → DataPointType
MATCH (fdp:FinancialDataPoint {datapoint_id: $from_id})
MATCH (dt:DataPointType {datapoint_type_id: $to_id})
MERGE (fdp)-[:IS_DATAPOINT_TYPE]->(dt)

// IS_CATEGORY: Topic → ConceptCategory
MATCH (t:Topic {topic_key: $from_id})
MATCH (cc:ConceptCategory {concept_category_id: $to_id})
MERGE (t)-[:IS_CATEGORY]->(cc)

// IS_AUTHOR_TYPE: Author → AuthorType
MATCH (a:Author {author_id: $from_id})
MATCH (at:AuthorType {author_type_id: $to_id})
MERGE (a)-[:IS_AUTHOR_TYPE]->(at)

// AFFILIATED_WITH: Author → Entity系ラベル
MATCH (a:Author {author_id: $from_id})
MATCH (e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product {name: $to_name})
MERGE (a)-[:AFFILIATED_WITH]->(e)

// ALIAS_OF: Alias → Entity系ラベル|Topic (to_label で分岐)
// to_label = Entity系ラベル:
MATCH (al:Alias {alias_id: $from_id})
MATCH (e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product {name: $to_name})
MERGE (al)-[:ALIAS_OF]->(e)
// to_label = "Topic":
MATCH (al:Alias {alias_id: $from_id})
MATCH (t:Topic {topic_key: $to_id})
MERGE (al)-[:ALIAS_OF]->(t)

// PARENT_CLASS: InstrumentClass (L2) → InstrumentClass (L1)
MATCH (child:InstrumentClass {instrument_class_id: $from_id})
MATCH (parent:InstrumentClass {instrument_class_id: $to_id})
MERGE (child)-[:PARENT_CLASS]->(parent)

// IN_PARENT_SECTOR: Industry → Sector
MATCH (i:Industry {industry_id: $from_id})
MATCH (s:Sector {sector_id: $to_id})
MERGE (i)-[:IN_PARENT_SECTOR]->(s)

// ISSUED_BY: Identifier → Entity系ラベル
MATCH (id:Identifier {identifier_id: $from_id})
MATCH (e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product {name: $to_name})
MERGE (id)-[:ISSUED_BY]->(e)
```

#### バッチ処理（擬似コード）

```python
def phase_3_0_classification_relations(
    queue_data: dict,
) -> dict:
    """Phase 3-0: Classification リレーション投入。"""
    relations = queue_data.get("relations", {})
    classification_rels = relations.get("classification", [])

    if not classification_rels:
        logger.info("No classification relations found, skipping Phase 3-0")
        return {"skipped": True}

    stats = {}
    for rel in classification_rels:
        rel_type = rel["type"]
        from_id = rel["from_id"]
        to_id = rel["to_id"]
        from_label = rel.get("from_label", "")
        to_label = rel.get("to_label", "")

        cypher = build_classification_rel_cypher(rel_type, from_label, to_label)
        run_cypher(cypher, from_id=from_id, to_id=to_id)

        stats[rel_type] = stats.get(rel_type, 0) + 1

    logger.info("Classification relations merged", stats=stats)
    return stats
```

---

## Phase 3a: ファイル内リレーション投入詳細

### リレーション推論戦略（ファイル内）

graph-queue JSON には現在 `relations` フィールドが空オブジェクト `{}` として出力されます。
ファイル内リレーションは以下のルールで推論します:

#### TAGGED リレーション

```
条件: 同一 graph-queue ファイル内に Source と Topic が両方存在する場合
戦略: 全 Source x 全 Topic のクロス結合で TAGGED を生成
```

```python
for source in sources:
    for topic in topics:
        create_tagged(source["source_id"], topic["topic_id"])
```

#### MAKES_CLAIM リレーション

```
条件: Claim に source_id または source_url が含まれる場合
戦略: source_id / source_url から対応する Source を特定
```

```python
for claim in claims:
    source_id = claim.get("source_id")
    if not source_id:
        source_url = claim.get("source_url", "")
        if source_url:
            source_id = generate_source_id(source_url)
    if source_id:
        create_makes_claim(source_id, claim["claim_id"])
```

#### ABOUT リレーション

```
条件: 同一 graph-queue ファイル内に Claim と Entity が両方存在する場合
戦略: 全 Claim x 全 Entity のクロス結合で ABOUT を生成
```

```python
for claim in claims:
    for entity in entities:
        create_about(claim["claim_id"], entity["entity_id"])
```

### 注意: リレーションの精度

ファイル内のクロス結合戦略は粗い粒度です。`relations` フィールドに
明示的な紐付けが定義された場合は、そちらを優先使用してください。

---

## Phase 3b: クロスファイルリレーション投入詳細

Phase 2 で投入したノードを、DB 内の既存ノードとリレーションで接続する。
`--skip-cross-link` 指定時はこのフェーズ全体をスキップする。

### 設計原則

1. **カテゴリマッチング**: Source と Topic は `category` フィールドの一致で接続
2. **コンテンツマッチング**: Claim と Entity は `content CONTAINS name` で接続
3. **双方向**: 新ノード→既存ノード、既存ノード→新ノードの両方向を処理
4. **冪等性**: 全クエリが MERGE ベースのため、重複リレーションは作成されない

### ステップ 3b.1: TAGGED カテゴリマッチング

#### 新 Source → 既存 Topic

今回投入した Source の `category` と一致する Topic（既存含む）を接続する。

```cypher
UNWIND $source_ids AS sid
MATCH (s:Source {source_id: sid})
MATCH (t:Topic {category: s.category})
MERGE (s)-[:TAGGED]->(t)
```

**実行方法（cypher-shell）**:

```bash
cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -a "$NEO4J_URI" \
  --param "source_ids => ['uuid-1', 'uuid-2', 'uuid-3']" \
  "UNWIND \$source_ids AS sid
   MATCH (s:Source {source_id: sid})
   MATCH (t:Topic {category: s.category})
   MERGE (s)-[:TAGGED]->(t)"
```

#### 新 Topic → 既存 Source

今回投入した Topic の `category` と一致する Source（既存含む）を接続する。

```cypher
UNWIND $topic_ids AS tid
MATCH (t:Topic {topic_id: tid})
MATCH (s:Source {category: t.category})
MERGE (s)-[:TAGGED]->(t)
```

#### マッチングの仕組み

```
Source.category  ←→  Topic.category
    "stock"      →   Topics where category = "stock"
    "index"      →   Topics where category = "index"
    "macro"      →   Topics where category = "macro"
```

カテゴリは `batch_label` → `category` 変換テーブルに基づく:

| batch_label | category |
|------------|----------|
| index | index |
| stock | stock |
| sector | sector |
| macro_cnbc | macro |
| ai_cnbc | ai |
| finance_cnbc | finance |
| nisa, ideco, tsumitate | asset-management |

### ステップ 3b.2: ABOUT コンテンツマッチング

> **Memory 除外フィルタ**: 全クロスファイルリレーション推論クエリには
> `WHERE NOT 'Memory' IN labels(n)` を付与すること。
> Memory ノードが KG ノードと誤マッチするのを防止するため。
> 参照: `.claude/rules/neo4j-namespace-convention.md`

#### 新 Claim → 既存 Entity

今回投入した Claim の `content` に、既存 Entity の `name` が含まれる場合に接続する。

```cypher
UNWIND $claim_ids AS cid
MATCH (c:Claim {claim_id: cid})
MATCH (e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product)
WHERE NOT 'Memory' IN labels(e)
  AND size(e.name) >= 2 AND c.content CONTAINS e.name
MERGE (c)-[:RELATES_TO]->(e)
```

#### 新 Entity系ラベル → 既存 Claim

今回投入した Entity 系ラベルの `name` が、既存 Claim の `content` に含まれる場合に接続する。

```cypher
UNWIND $entity_names AS ename
MATCH (e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product {name: ename})
WHERE NOT 'Memory' IN labels(e)
MATCH (c:Claim)
WHERE NOT 'Memory' IN labels(c)
  AND size(e.name) >= 2 AND c.content CONTAINS e.name
MERGE (c)-[:RELATES_TO]->(e)
```

#### マッチング条件の詳細

| 条件 | 理由 |
|------|------|
| `size(e.name) >= 2` | 1文字の Entity 名（例: "A"）による偽陽性を防止 |
| `CONTAINS` | 完全一致ではなく部分一致（Entity 名が文中に出現すれば接続） |

#### 偽陽性の考慮

`CONTAINS` による部分一致は偽陽性のリスクがある:

| Entity.name | Claim.content | 判定 | 備考 |
|------------|---------------|------|------|
| "NVIDIA" | "NVIDIA reported strong earnings" | 正（真陽性） | |
| "AI" | "NVIDIA's AI chip demand surges" | 正（真陽性） | |
| "AI" | "said the chairman" | 偽（偽陽性） | 2文字だが意味的に無関係 |

現時点では `size >= 2` のガードのみ。将来的にフルテキストインデックスや
正規表現（`=~ '(?i).*\\bNVIDIA\\b.*'`）の導入を検討。

### パフォーマンス考慮

#### TAGGED（カテゴリマッチング）

- Topic ノード数は通常少ない（数十〜数百）→ 問題なし
- `idx_topic_category` インデックスが効く

#### ABOUT（コンテンツマッチング）

- Claim ノードが増加すると `CONTAINS` の全走査コストが増大
- 対策: 新 Entity → 既存 Claim のクエリは Claim 数が多い場合に重くなるため、
  以下の制限を検討:

```cypher
// Claim 数が多い場合、直近30日の Claim に限定
UNWIND $entity_names AS ename
MATCH (e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product {name: ename})
WHERE NOT 'Memory' IN labels(e)
MATCH (c:Claim)
WHERE NOT 'Memory' IN labels(c)
  AND size(e.name) >= 2
  AND c.content CONTAINS e.name
  AND c.created_at > datetime() - duration('P30D')
MERGE (c)-[:RELATES_TO]->(e)
```

> **注意**: Claim に `created_at` プロパティが必要。未設定の場合は全件走査にフォールバック。

### 実行フロー（擬似コード）

```python
def phase_3b_cross_file_relations(
    source_ids: list[str],
    topic_ids: list[str],
    claim_ids: list[str],
    entity_ids: list[str],
    skip_cross_link: bool = False,
) -> dict:
    """Phase 3b: クロスファイルリレーション投入。"""
    if skip_cross_link:
        return {"skipped": True, "reason": "--skip-cross-link"}

    stats = {"tagged_cross": 0, "about_cross": 0}

    # 3b.1: TAGGED カテゴリマッチング
    if source_ids:
        result = run_cypher("""
            UNWIND $source_ids AS sid
            MATCH (s:Source {source_id: sid})
            MATCH (t:Topic {category: s.category})
            MERGE (s)-[r:TAGGED]->(t)
            RETURN count(r) AS cnt
        """, source_ids=source_ids)
        stats["tagged_cross"] += result["cnt"]

    if topic_ids:
        result = run_cypher("""
            UNWIND $topic_ids AS tid
            MATCH (t:Topic {topic_id: tid})
            MATCH (s:Source {category: t.category})
            MERGE (s)-[r:TAGGED]->(t)
            RETURN count(r) AS cnt
        """, topic_ids=topic_ids)
        stats["tagged_cross"] += result["cnt"]

    # 3b.2: RELATES_TO コンテンツマッチング（v4.0: ABOUT廃止→RELATES_TO統一）
    if claim_ids:
        result = run_cypher("""
            UNWIND $claim_ids AS cid
            MATCH (c:Claim {claim_id: cid})
            MATCH (e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product)
            WHERE NOT 'Memory' IN labels(e)
              AND size(e.name) >= 2 AND c.content CONTAINS e.name
            MERGE (c)-[r:RELATES_TO]->(e)
            RETURN count(r) AS cnt
        """, claim_ids=claim_ids)
        stats["about_cross"] += result["cnt"]

    if entity_names:
        result = run_cypher("""
            UNWIND $entity_names AS ename
            MATCH (e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product {name: ename})
            WHERE NOT 'Memory' IN labels(e)
            MATCH (c:Claim)
            WHERE NOT 'Memory' IN labels(c)
              AND size(e.name) >= 2 AND c.content CONTAINS e.name
            MERGE (c)-[r:RELATES_TO]->(e)
            RETURN count(r) AS cnt
        """, entity_names=entity_names)
        stats["about_cross"] += result["cnt"]

    return stats
```

---

## 冪等性の仕組み

### MERGE の動作

Neo4j の `MERGE` は以下のように動作します:

1. **ノードが存在しない場合**: `CREATE` と同等（新規作成）
2. **ノードが存在する場合**: `MATCH` と同等（既存を更新）

```cypher
-- 1回目: ノードが作成される
MERGE (s:Source {source_id: 'abc-123'})
SET s.url = 'https://example.com', s.title = 'Example'

-- 2回目: 同じノードが更新される（実質変更なし）
MERGE (s:Source {source_id: 'abc-123'})
SET s.url = 'https://example.com', s.title = 'Example'

-- 結果: ノードは1つだけ存在する
```

### 冪等性の保証チェーン

```
1. emit_research_queue.py が決定論的 ID を生成
   ↓
2. graph-queue JSON に ID が記録される
   ↓
3. save-to-graph が MERGE で投入
   ↓
4. 同じ ID のノードは上書き（重複なし）
```

### 再投入の安全性

同じ graph-queue JSON ファイルを複数回投入しても:

- **ノード**: 既存ノードのプロパティが上書きされる（同じ値なので実質変更なし）
- **リレーション**: MERGE により重複作成されない
- **グラフ状態**: 1回投入した場合と同一

---

## エラーハンドリング詳細

### E001: Neo4j 接続失敗

**発生条件**:
- Neo4j が起動していない
- 接続情報（URI, ユーザー名, パスワード）が不正

**対処法**:

```bash
# Neo4j の状態確認
docker ps | grep neo4j

# Neo4j の起動
docker start neo4j

# 接続情報の確認
echo "URI: ${NEO4J_URI:-bolt://localhost:7687}"
echo "USER: ${NEO4J_USER:-neo4j}"

# 接続テスト
cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -a "$NEO4J_URI" \
  "RETURN 1 AS test"
```

### E002: graph-queue ディレクトリ未検出

**発生条件**:
- `.tmp/graph-queue/` ディレクトリが存在しない
- 指定された `--source` のサブディレクトリが存在しない

**対処法**:

```bash
# ディレクトリの確認
ls -la .tmp/graph-queue/

# graph-queue の生成
python3 scripts/emit_research_queue.py \
  --command finance-news-workflow \
  --input .tmp/news-batches/index.json
```

### E003: JSON スキーマ検証エラー

**発生条件**:
- `schema_version` が `"1.0"`, `"2.0"`, `"2.2"`, `"3.0"` のいずれでもない
- 必須フィールド（`queue_id`, `command_source`, `sources` 等）が欠落
- v2 キューで `facts`, `chunks`, `financial_datapoints`, `fiscal_periods` が欠落

**対処法**:

```bash
# JSON の内容確認
python3 -m json.tool .tmp/graph-queue/finance-news-workflow/gq-xxx.json

# 必須フィールドの確認
python3 -c "
import json, sys
data = json.load(open(sys.argv[1]))
required = {'schema_version', 'queue_id', 'created_at', 'command_source',
            'sources', 'topics', 'claims', 'entities', 'relations'}
missing = required - set(data.keys())
if missing:
    print(f'Missing fields: {missing}')
else:
    print('All required fields present')
" .tmp/graph-queue/finance-news-workflow/gq-xxx.json
```

### E004: Cypher 実行エラー

**発生条件**:
- 制約・インデックスが未作成
- データ型の不一致（datetime パース失敗等）

**対処法**:

```bash
# 制約の確認
cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -a "$NEO4J_URI" \
  "SHOW CONSTRAINTS"

# 初回セットアップが未実行の場合
# -> このガイドの「初回セットアップ」セクションを実行

# datetime パースエラーの場合
# -> published フィールドの形式を確認（ISO 8601 必須）
```

### E005: ファイル削除/移動エラー

**発生条件**:
- 処理済みファイルの削除権限がない
- `.tmp/graph-queue/.processed/` ディレクトリの作成権限がない

**対処法**:

```bash
# 権限の確認
ls -la .tmp/graph-queue/

# .processed ディレクトリの手動作成
mkdir -p .tmp/graph-queue/.processed/

# 手動削除
rm .tmp/graph-queue/finance-news-workflow/gq-xxx.json
```

---

## E2E 検証手順

save-to-graph パイプラインの全体検証手順。graph-queue 生成から Neo4j 投入、冪等性確認までを実施する。

### 前提条件

- Neo4j が起動済み（Docker or ローカル）
- 初回セットアップ（制約・インデックス作成）が完了済み
- `scripts/emit_research_queue.py` が利用可能

### Step 1: graph-queue ファイル生成

finance-news-workflow の実データからキューファイルを生成する。

```bash
# 実データが .tmp/news-batches/ にある場合
python3 scripts/emit_research_queue.py \
  --command finance-news-workflow \
  --input .tmp/news-batches/index.json

# 複数テーマを連続生成
for theme in index stock sector macro_cnbc ai_cnbc finance_cnbc; do
  input_file=".tmp/news-batches/${theme}.json"
  if [ -f "$input_file" ]; then
    python3 scripts/emit_research_queue.py \
      --command finance-news-workflow \
      --input "$input_file"
  fi
done

# 生成結果を確認
ls -la .tmp/graph-queue/finance-news-workflow/
```

### Step 2: キューファイルのフォーマット検証

生成された JSON が graph-queue 標準フォーマットに準拠しているか確認する。

```bash
# 必須フィールドの確認
python3 -c "
import json, sys, glob

required = {'schema_version', 'queue_id', 'created_at', 'command_source',
            'session_id', 'batch_label', 'sources', 'topics', 'claims',
            'entities', 'relations'}

for path in glob.glob('.tmp/graph-queue/**/*.json', recursive=True):
    data = json.load(open(path))
    missing = required - set(data.keys())
    status = 'OK' if not missing else f'MISSING: {missing}'
    sources = len(data.get('sources', []))
    topics = len(data.get('topics', []))
    entities = len(data.get('entities', []))
    claims = len(data.get('claims', []))
    print(f'{path}: {status} (S:{sources} T:{topics} E:{entities} C:{claims})')
"
```

### Step 3: dry-run 実行

`/save-to-graph --dry-run` でキューファイルの検証のみ実行する。
実際の Neo4j への投入は行わず、生成される Cypher クエリを確認する。

```bash
/save-to-graph --dry-run
```

期待される出力:

```
[DRY-RUN] MERGE (s:Source {source_id: "..."}) SET s.url = "...", ...
[DRY-RUN] MERGE (c:Claim {claim_id: "..."}) SET c.content = "...", ...
```

### Step 4: Neo4j への投入

```bash
# 全キューファイルを投入
/save-to-graph

# 特定コマンドソースのみ投入
/save-to-graph --source finance-news-workflow

# 処理済みファイルを保持したい場合
/save-to-graph --keep
```

### Step 5: 検証クエリ

投入結果を Cypher クエリで確認する。

#### Source タイプ別統計

```cypher
MATCH (s:Source)
RETURN s.source_type AS type, s.command_source AS command, count(s) AS count
ORDER BY count DESC
```

#### Source -> Topic 統計

```cypher
MATCH (s:Source)-[:TAGGED]->(t:Topic)
RETURN t.name AS topic, t.category AS category, count(s) AS source_count
ORDER BY source_count DESC
```

#### Entity 一覧（v4.0: 個別ラベル別）

```cypher
MATCH (e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product)
WHERE NOT 'Memory' IN labels(e)
RETURN e.name AS name, labels(e)[0] AS type, e.ticker AS ticker
ORDER BY e.name
```

#### Claim -> Source 統計（MAKES_CLAIM）

```cypher
MATCH (s:Source)-[:MAKES_CLAIM]->(c:Claim)
RETURN s.title AS source_title, count(c) AS claim_count
ORDER BY claim_count DESC
LIMIT 20
```

#### Claim -> Entity 統計（RELATES_TO）

```cypher
MATCH (c:Claim)-[:RELATES_TO]->(e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product)
RETURN e.name AS entity, count(c) AS claim_count
ORDER BY claim_count DESC
```

#### ノード総数の確認（v2 対応）

```cypher
// v4.0: Entity ラベルは廃止。個別ラベル別に集計する
CALL {
  MATCH (s:Source) RETURN 'Source' AS label, count(s) AS count
  UNION ALL
  MATCH (t:Topic) RETURN 'Topic' AS label, count(t) AS count
  UNION ALL
  MATCH (e:Company) RETURN 'Company' AS label, count(e) AS count
  UNION ALL
  MATCH (e:Technology) RETURN 'Technology' AS label, count(e) AS count
  UNION ALL
  MATCH (e:Organization) RETURN 'Organization' AS label, count(e) AS count
  UNION ALL
  MATCH (e:Person) RETURN 'Person' AS label, count(e) AS count
  UNION ALL
  MATCH (e:MarketIndex) RETURN 'MarketIndex' AS label, count(e) AS count
  UNION ALL
  MATCH (c:Claim) RETURN 'Claim' AS label, count(c) AS count
  UNION ALL
  MATCH (f:Fact) RETURN 'Fact' AS label, count(f) AS count
  UNION ALL
  MATCH (ch:Chunk) RETURN 'Chunk' AS label, count(ch) AS count
  UNION ALL
  MATCH (dp:FinancialDataPoint) RETURN 'FinancialDataPoint' AS label, count(dp) AS count
  UNION ALL
  MATCH (fp:FiscalPeriod) RETURN 'FiscalPeriod' AS label, count(fp) AS count
}
RETURN label, count ORDER BY label
```

#### リレーション総数の確認（v2 対応）

```cypher
CALL {
  MATCH ()-[r:TAGGED]->() RETURN 'TAGGED' AS type, count(r) AS count
  UNION ALL
  MATCH ()-[r:MAKES_CLAIM]->() RETURN 'MAKES_CLAIM' AS type, count(r) AS count
  UNION ALL
  MATCH ()-[r:RELATES_TO]->() RETURN 'RELATES_TO(v4)' AS type, count(r) AS count
  UNION ALL
  MATCH ()-[r:CONTAINS_CHUNK]->() RETURN 'CONTAINS_CHUNK' AS type, count(r) AS count
  UNION ALL
  MATCH ()-[r:EXTRACTED_FROM]->() RETURN 'EXTRACTED_FROM' AS type, count(r) AS count
  UNION ALL
  MATCH ()-[r:STATES_FACT]->() RETURN 'STATES_FACT' AS type, count(r) AS count
  UNION ALL
  MATCH ()-[r:HAS_DATAPOINT]->() RETURN 'HAS_DATAPOINT' AS type, count(r) AS count
  UNION ALL
  MATCH ()-[r:FOR_PERIOD]->() RETURN 'FOR_PERIOD' AS type, count(r) AS count
  UNION ALL
  MATCH ()-[r:RELATES_TO]->() RETURN 'RELATES_TO' AS type, count(r) AS count
}
RETURN type, count ORDER BY type
```

#### v2 固有の検証クエリ

##### Source -> Chunk -> Fact/Claim チェーン

```cypher
MATCH (s:Source)-[:CONTAINS_CHUNK]->(ch:Chunk)<-[:EXTRACTED_FROM]-(fc)
WHERE fc:Fact OR fc:Claim
RETURN s.title AS source,
       ch.section_title AS section,
       labels(fc)[0] AS node_type,
       fc.content AS content
LIMIT 20
```

##### FinancialDataPoint -> FiscalPeriod -> Entity

```cypher
MATCH (dp:FinancialDataPoint)-[:FOR_PERIOD]->(fp:FiscalPeriod)
OPTIONAL MATCH (dp)-[:RELATES_TO]->(e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product)
RETURN dp.metric_name AS metric,
       dp.value AS value,
       dp.unit AS unit,
       dp.is_estimate AS estimate,
       fp.period_label AS period,
       e.name AS entity
ORDER BY fp.period_label, dp.metric_name
```

##### Fact 統計

```cypher
MATCH (f:Fact)
RETURN f.fact_type AS type, count(f) AS count
ORDER BY count DESC
```

### Step 6: 冪等性確認

同じデータを再投入して、ノード・リレーションが重複しないことを確認する。

```bash
# Step 6.1: 投入前のノード数を記録
cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -a "$NEO4J_URI" \
  "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY label"

# Step 6.2: 同じキューファイルを再生成して再投入
python3 scripts/emit_research_queue.py \
  --command finance-news-workflow \
  --input .tmp/news-batches/index.json

/save-to-graph --source finance-news-workflow

# Step 6.3: 再投入後のノード数を確認（Step 6.1 と同じであること）
cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -a "$NEO4J_URI" \
  "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY label"
```

**冪等性の確認ポイント**:

| 確認項目 | 期待結果 |
|---------|---------|
| Source ノード数 | 変化なし |
| Topic ノード数 | 変化なし |
| Entity ノード数 | 変化なし |
| Claim ノード数 | 変化なし |
| Fact ノード数 | 変化なし |
| Chunk ノード数 | 変化なし |
| FinancialDataPoint ノード数 | 変化なし |
| FiscalPeriod ノード数 | 変化なし |
| Classification ノード数（16種） | 変化なし |
| TAGGED リレーション数 | 変化なし |
| MAKES_CLAIM リレーション数 | 変化なし |
| ABOUT リレーション数 | 変化なし |
| CONTAINS_CHUNK リレーション数 | 変化なし |
| EXTRACTED_FROM リレーション数 | 変化なし |
| STATES_FACT リレーション数 | 変化なし |
| HAS_DATAPOINT リレーション数 | 変化なし |
| FOR_PERIOD リレーション数 | 変化なし |
| RELATES_TO リレーション数 | 変化なし |
| Classification リレーション数（20種） | 変化なし |

冪等性が保証される理由:
1. 全 ID は入力データから**決定論的**に生成される（UUID5 / SHA-256）
2. 全 Cypher クエリは **MERGE** ベース（存在すれば更新、なければ作成）
3. 同じ URL / content / name からは常に同じ ID が生成される

### Step 7: 処理済みファイルの確認

```bash
# デフォルト: 処理済みファイルは削除されている
ls .tmp/graph-queue/finance-news-workflow/
# → 空であること

# --keep 使用時: .processed/ に移動されている
ls .tmp/graph-queue/.processed/
```

### 自動テストの実行

E2E テストスイートでフォーマット準拠・冪等性を自動検証する:

```bash
# E2E テストのみ実行
uv run pytest tests/scripts/test_e2e_graph_pipeline.py -v

# 全テスト（単体 + E2E）
uv run pytest tests/scripts/ -v
```

テストスイートの検証内容:

| テストクラス | 検証内容 | テスト数 |
|-------------|---------|---------|
| `TestGraphQueueFormatCompliance` | 全6コマンドのフォーマット準拠 | 14 |
| `TestIdempotency` | ID 生成の決定論性・冪等性 | 8 |
| `TestMultiCommandPipeline` | マルチコマンド整合性 | 3 |
| `TestNodeCounts` | ノード数の入出力一致 | 5 |
| `TestRelationInference` | リレーション推論データの整合性 | 3 |
| `TestSourceIdUniqueness` | source_id の URL ユニーク性 | 2 |

---

## 関連リソース

| リソース | パス | 説明 |
|---------|------|------|
| スキル定義 | `.claude/skills/save-to-graph/SKILL.md` | メインスキルファイル |
| スラッシュコマンド | `.claude/commands/save-to-graph.md` | コマンド定義 |
| graph-queue 生成 | `scripts/emit_research_queue.py` | JSON 生成スクリプト |
| graph-queue テスト | `tests/scripts/test_emit_research_queue.py` | 生成スクリプトのテスト |
| E2E テスト | `tests/scripts/test_e2e_graph_pipeline.py` | E2E 検証・冪等性テスト |
| KG スキーマ定義 | `data/lifecycle-state/research/ontology.yaml` | ノード・リレーション・制約の定義 |
| v3.0 オントロジー | `data/lifecycle-state/research/ontology.yaml` | v3.0 ノード・リレーション定義（33ラベル/59種） |
| v3.0 MERGE ガイド | `data/lifecycle-state/research/merge-guide.md` | v3.0 MERGE パターン・投入順序 |
