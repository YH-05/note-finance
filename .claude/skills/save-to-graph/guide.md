# save-to-graph 詳細ガイド

このガイドは、save-to-graph スキルの詳細な処理フロー、Cypher テンプレート、graph-queue フォーマット仕様を説明します。

## 目次

1. [初回セットアップ](#初回セットアップ)
2. [graph-queue フォーマット仕様](#graph-queue-フォーマット仕様)
3. [ID 生成戦略](#id-生成戦略)
4. [Cypher テンプレート](#cypher-テンプレート)
5. [ノード投入詳細](#ノード投入詳細)
6. [リレーション投入詳細](#リレーション投入詳細)
7. [冪等性の仕組み](#冪等性の仕組み)
8. [エラーハンドリング詳細](#エラーハンドリング詳細)

---

## 初回セットアップ

Neo4j に初めて接続する際は、以下の制約とインデックスを作成する必要があります。

### 前提: Neo4j 接続

```bash
# 環境変数設定
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="password"

# 接続テスト
cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -a "$NEO4J_URI" \
  "RETURN 'connection_ok' AS status"
```

### UNIQUE 制約の作成（7つ）

```cypher
-- Source ノード制約
CREATE CONSTRAINT unique_source_id IF NOT EXISTS
  FOR (s:Source) REQUIRE s.source_id IS UNIQUE;

CREATE CONSTRAINT unique_source_url IF NOT EXISTS
  FOR (s:Source) REQUIRE s.url IS UNIQUE;

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
```

### インデックスの作成（4つ）

```cypher
-- Source のカテゴリ検索用
CREATE INDEX idx_source_category IF NOT EXISTS
  FOR (s:Source) ON (s.category);

-- Source の収集日時検索用
CREATE INDEX idx_source_collected_at IF NOT EXISTS
  FOR (s:Source) ON (s.collected_at);

-- Topic のカテゴリ検索用
CREATE INDEX idx_topic_category IF NOT EXISTS
  FOR (t:Topic) ON (t.category);

-- Entity のタイプ検索用
CREATE INDEX idx_entity_type IF NOT EXISTS
  FOR (e:Entity) ON (e.entity_type);
```

### 一括セットアップスクリプト

```bash
# 全制約・インデックスを一括作成
cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -a "$NEO4J_URI" << 'CYPHER'
CREATE CONSTRAINT unique_source_id IF NOT EXISTS FOR (s:Source) REQUIRE s.source_id IS UNIQUE;
CREATE CONSTRAINT unique_source_url IF NOT EXISTS FOR (s:Source) REQUIRE s.url IS UNIQUE;
CREATE CONSTRAINT unique_topic_id IF NOT EXISTS FOR (t:Topic) REQUIRE t.topic_id IS UNIQUE;
CREATE CONSTRAINT unique_topic_key IF NOT EXISTS FOR (t:Topic) REQUIRE t.topic_key IS UNIQUE;
CREATE CONSTRAINT unique_entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE;
CREATE CONSTRAINT unique_entity_key IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_key IS UNIQUE;
CREATE CONSTRAINT unique_claim_id IF NOT EXISTS FOR (c:Claim) REQUIRE c.claim_id IS UNIQUE;
CREATE INDEX idx_source_category IF NOT EXISTS FOR (s:Source) ON (s.category);
CREATE INDEX idx_source_collected_at IF NOT EXISTS FOR (s:Source) ON (s.collected_at);
CREATE INDEX idx_topic_category IF NOT EXISTS FOR (t:Topic) ON (t.category);
CREATE INDEX idx_entity_type IF NOT EXISTS FOR (e:Entity) ON (e.entity_type);
CYPHER

# 作成結果を確認
cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -a "$NEO4J_URI" \
  "SHOW CONSTRAINTS"

cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -a "$NEO4J_URI" \
  "SHOW INDEXES"
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

graph-queue JSON は `scripts/emit_graph_queue.py` が生成する中間フォーマットです。
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
  "schema_version": "1.0",
  "queue_id": "gq-20260307120000-a1b2",
  "created_at": "2026-03-07T12:00:00+00:00",
  "command_source": "finance-news-workflow",
  "session_id": "news-20260307-120000",
  "batch_label": "index",
  "sources": [...],
  "topics": [...],
  "claims": [...],
  "entities": [...],
  "relations": {}
}
```

### フィールド定義

| フィールド | 型 | 必須 | 説明 |
|-----------|------|------|------|
| `schema_version` | string | Yes | スキーマバージョン（現在 `"1.0"`） |
| `queue_id` | string | Yes | キュー一意ID（`gq-{timestamp}-{hash4}`） |
| `created_at` | string | Yes | 生成日時（ISO 8601） |
| `command_source` | string | Yes | 生成元コマンド名 |
| `session_id` | string | Yes | セッションID |
| `batch_label` | string | Yes | バッチラベル（テーマキー等） |
| `sources` | array | Yes | Source ノードデータ配列 |
| `topics` | array | Yes | Topic ノードデータ配列 |
| `claims` | array | Yes | Claim ノードデータ配列 |
| `entities` | array | Yes | Entity ノードデータ配列 |
| `relations` | object | Yes | リレーションデータ（現在未使用、将来拡張用） |

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

### relations オブジェクト

現在は空オブジェクト `{}` として出力されます。
リレーションは各ノードデータ内の `source_id` 等のフィールドから推論されます。

将来的に明示的なリレーション定義を追加する場合の拡張ポイントです:

```json
{
  "relations": {
    "tagged": [
      {"source_id": "...", "topic_id": "..."}
    ],
    "makes_claim": [
      {"source_id": "...", "claim_id": "..."}
    ],
    "about": [
      {"claim_id": "...", "entity_id": "..."}
    ]
  }
}
```

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
| `$collected_at` | `created_at`（キューレベル） | ISO 8601 |
| `$published` | `sources[].published` | ISO 8601 or 空文字列 |
| `$category` | `batch_label` から推論 | THEME_TO_CATEGORY 変換 |
| `$command_source` | `command_source`（キューレベル） | |

#### Topic ノード

```cypher
MERGE (t:Topic {topic_id: $topic_id})
SET t.name = $name,
    t.category = $category,
    t.topic_key = $name + '::' + $category
```

**パラメータマッピング**:

| パラメータ | graph-queue フィールド |
|-----------|----------------------|
| `$topic_id` | `topics[].topic_id` |
| `$name` | `topics[].name` |
| `$category` | `topics[].category` |

#### Entity ノード

```cypher
MERGE (e:Entity {entity_id: $entity_id})
SET e.name = $name,
    e.entity_type = $entity_type,
    e.entity_key = $name + '::' + $entity_type
```

**パラメータマッピング**:

| パラメータ | graph-queue フィールド |
|-----------|----------------------|
| `$entity_id` | `entities[].entity_id` |
| `$name` | `entities[].name` |
| `$entity_type` | `entities[].entity_type` |

#### Claim ノード

```cypher
MERGE (c:Claim {claim_id: $claim_id})
SET c.content = $content,
    c.claim_type = $claim_type,
    c.confidence = $confidence
```

**パラメータマッピング**:

| パラメータ | graph-queue フィールド | 補足 |
|-----------|----------------------|------|
| `$claim_id` | `claims[].claim_id` | SHA-256[:16] |
| `$content` | `claims[].content` | |
| `$claim_type` | `claims[].claim_type` | 未設定時は null |
| `$confidence` | `claims[].confidence` | 未設定時は null |

### リレーション MERGE テンプレート

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

#### ABOUT（Claim -> Entity）

```cypher
MATCH (c:Claim {claim_id: $claim_id})
MATCH (e:Entity {entity_id: $entity_id})
MERGE (c)-[:ABOUT]->(e)
```

**リレーション推論ルール**:

現在の graph-queue フォーマットでは Claim と Entity の明示的な紐付けはありません。
将来的に `relations.about` フィールドで明示的に定義される予定です。

暫定的には同一ファイル内の Claim と Entity を全て ABOUT で接続します。

---

## ノード投入詳細

### 投入順序

依存関係に基づき、以下の順序で投入します:

```
1. Topic    (他ノードに依存しない)
2. Entity   (他ノードに依存しない)
3. Source   (他ノードに依存しない)
4. Claim    (他ノードに依存しない、ただし MAKES_CLAIM で Source を参照)
```

ノード自体は独立していますが、リレーション投入時にすべてのノードが存在している必要があります。

### cypher-shell での実行方法

```bash
# 単一ノードの MERGE
cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -a "$NEO4J_URI" \
  "MERGE (t:Topic {topic_id: 'uuid-here'}) SET t.name = 'S&P 500', t.category = 'stock', t.topic_key = 'S&P 500::stock'"

# パラメータ付き実行（推奨）
cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -a "$NEO4J_URI" \
  --param "topic_id => 'uuid-here'" \
  --param "name => 'S&P 500'" \
  --param "category => 'stock'" \
  "MERGE (t:Topic {topic_id: \$topic_id}) SET t.name = \$name, t.category = \$category, t.topic_key = \$name + '::' + \$category"
```

### バッチ投入パターン

大量のノードを効率的に投入するため、UNWIND を使用:

```cypher
-- Topic バッチ投入
UNWIND $topics AS topic
MERGE (t:Topic {topic_id: topic.topic_id})
SET t.name = topic.name,
    t.category = topic.category,
    t.topic_key = topic.name + '::' + topic.category

-- Source バッチ投入
UNWIND $sources AS src
MERGE (s:Source {source_id: src.source_id})
SET s.url = src.url,
    s.title = src.title,
    s.source_type = src.source_type,
    s.collected_at = datetime(src.collected_at),
    s.published_at = CASE
        WHEN src.published IS NOT NULL AND src.published <> ''
        THEN datetime(src.published)
        ELSE null
    END,
    s.category = src.category,
    s.command_source = src.command_source
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

## リレーション投入詳細

### リレーション推論戦略

graph-queue JSON には現在 `relations` フィールドが空オブジェクト `{}` として出力されます。
リレーションは以下のルールで推論します:

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

現在のクロス結合戦略は粗い粒度です。将来的に `relations` フィールドに
明示的な紐付けが定義された場合は、そちらを優先使用してください。

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
1. emit_graph_queue.py が決定論的 ID を生成
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
python3 scripts/emit_graph_queue.py \
  --command finance-news-workflow \
  --input .tmp/news-batches/index.json
```

### E003: JSON スキーマ検証エラー

**発生条件**:
- `schema_version` が `"1.0"` でない
- 必須フィールド（`queue_id`, `command_source`, `sources` 等）が欠落

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
- `scripts/emit_graph_queue.py` が利用可能

### Step 1: graph-queue ファイル生成

finance-news-workflow の実データからキューファイルを生成する。

```bash
# 実データが .tmp/news-batches/ にある場合
python3 scripts/emit_graph_queue.py \
  --command finance-news-workflow \
  --input .tmp/news-batches/index.json

# 複数テーマを連続生成
for theme in index stock sector macro_cnbc ai_cnbc finance_cnbc; do
  input_file=".tmp/news-batches/${theme}.json"
  if [ -f "$input_file" ]; then
    python3 scripts/emit_graph_queue.py \
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

#### Entity 一覧

```cypher
MATCH (e:Entity)
RETURN e.name AS name, e.entity_type AS type, e.ticker AS ticker
ORDER BY e.name
```

#### Claim -> Source 統計（MAKES_CLAIM）

```cypher
MATCH (s:Source)-[:MAKES_CLAIM]->(c:Claim)
RETURN s.title AS source_title, count(c) AS claim_count
ORDER BY claim_count DESC
LIMIT 20
```

#### Claim -> Entity 統計（ABOUT）

```cypher
MATCH (c:Claim)-[:ABOUT]->(e:Entity)
RETURN e.name AS entity, count(c) AS claim_count
ORDER BY claim_count DESC
```

#### ノード総数の確認

```cypher
CALL {
  MATCH (s:Source) RETURN 'Source' AS label, count(s) AS count
  UNION ALL
  MATCH (t:Topic) RETURN 'Topic' AS label, count(t) AS count
  UNION ALL
  MATCH (e:Entity) RETURN 'Entity' AS label, count(e) AS count
  UNION ALL
  MATCH (c:Claim) RETURN 'Claim' AS label, count(c) AS count
}
RETURN label, count ORDER BY label
```

#### リレーション総数の確認

```cypher
CALL {
  MATCH ()-[r:TAGGED]->() RETURN 'TAGGED' AS type, count(r) AS count
  UNION ALL
  MATCH ()-[r:MAKES_CLAIM]->() RETURN 'MAKES_CLAIM' AS type, count(r) AS count
  UNION ALL
  MATCH ()-[r:ABOUT]->() RETURN 'ABOUT' AS type, count(r) AS count
}
RETURN type, count ORDER BY type
```

### Step 6: 冪等性確認

同じデータを再投入して、ノード・リレーションが重複しないことを確認する。

```bash
# Step 6.1: 投入前のノード数を記録
cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -a "$NEO4J_URI" \
  "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY label"

# Step 6.2: 同じキューファイルを再生成して再投入
python3 scripts/emit_graph_queue.py \
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
| TAGGED リレーション数 | 変化なし |
| MAKES_CLAIM リレーション数 | 変化なし |
| ABOUT リレーション数 | 変化なし |

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
| graph-queue 生成 | `scripts/emit_graph_queue.py` | JSON 生成スクリプト |
| graph-queue テスト | `tests/scripts/test_emit_graph_queue.py` | 生成スクリプトのテスト |
| E2E テスト | `tests/scripts/test_e2e_graph_pipeline.py` | E2E 検証・冪等性テスト |
| KG スキーマ定義 | `data/config/knowledge-graph-schema.yaml` | ノード・リレーション・制約の定義 |
