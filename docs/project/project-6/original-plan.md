# save-to-graph スキル設計プラン

## Context

金融コンテンツプロジェクトの各コマンド（`/generate-market-report`, `/finance-news-workflow`, `/ai-research-collect` 等）は、実行時に多数の情報ソースを調査・収集する。しかしこれらのソース情報は使い捨てで、横断的な検索・分析ができない。

Neo4j グラフDB にソース情報を蓄積することで：
- 「この主張の根拠となったソースは何か」のトレーサビリティ
- 「このテーマについて過去にどんなソースを参照したか」の検索
- 将来的には主張間の矛盾検出やエビデンスチェーン構築

を実現する。

**スコープ**: Option A+（Source + Topic + 軽量 Claim + 構造化メタデータからの Entity）。LLM による深い抽出は Phase 2 に先送り。

---

## 1. アーキテクチャ概要

```
各コマンド実行
  └→ 末尾ステップで scripts/emit_graph_queue.py を呼び出し
       └→ .tmp/graph-queue/{command}/{queue_id}.json に出力

/save-to-graph（非同期、手動実行）
  └→ .tmp/graph-queue/ 配下の未処理 JSON を検出
       └→ Neo4j MCP (write_neo4j_cypher) で MERGE ベース投入
            └→ 処理済みファイルを _processed/ に移動
```

**非同期分離の理由**:
- コマンドの実行速度に影響しない
- Neo4j が停止中でもコマンドは正常完了
- 投入失敗時のリトライが独立して可能

### .tmp フォルダ肥大化対策

graph-queue ファイルは中間データであり、投入完了後は不要。以下の3層で肥大化を防ぐ。

| 層 | 対策 | タイミング |
|----|------|-----------|
| 1. 投入時削除 | `/save-to-graph` 成功後にキューファイルを**削除**（`_processed/` に移動しない） | 投入完了時 |
| 2. `--keep` フラグ | デバッグ用に `--keep` 指定時のみ `_processed/` に保存 | 任意 |
| 3. 定期クリーンアップ | `emit_graph_queue.py --cleanup` で7日以上前のキューファイル（未処理含む）を削除 | 手動 or スクリプト末尾 |

**emit_graph_queue.py 実行時の自動クリーンアップ**:
- キュー生成のたびに `.tmp/graph-queue/` 内の7日以上前のファイルを自動削除
- 新しいファイル生成と古いファイル削除を同時に行うことで、手動クリーンアップを不要にする

**ディレクトリ構造（修正版）**:
```
.tmp/graph-queue/
  finance-news-workflow/
    gq-20260307-120000-a1b2.json    # 未処理（/save-to-graph で消える）
  ai-research-collect/
    gq-20260307-130000-c3d4.json
  # _processed/ は --keep 時のみ作成
```

---

## 2. graph-queue 標準フォーマット

全コマンドが出力する統一的な中間 JSON。各コマンドの出力形式の違いをここで吸収する。

```json
{
  "schema_version": "1.0",
  "queue_id": "gq-20260307-120000-a1b2",
  "created_at": "2026-03-07T12:00:00+09:00",
  "command_source": "finance-news-workflow",
  "session_id": "news-20260307-120000",
  "batch_label": "index",

  "sources": [
    {
      "title": "S&P 500 closes at record high",
      "url": "https://www.cnbc.com/...",
      "source_type": "news",
      "publisher": "CNBC - Markets",
      "published_at": "2026-03-07T12:00:00+00:00",
      "collected_at": "2026-03-07T14:30:00+09:00",
      "language": "en",
      "meta": {
        "feed_source": "CNBC - Investing",
        "theme_key": "index",
        "issue_number": 200
      }
    }
  ],

  "topics": [
    { "name": "株価指数", "category": "stock" }
  ],

  "claims": [
    {
      "content": "S&P 500 briefly surpassed 7,000 for the first time",
      "claim_type": "analysis",
      "sentiment": "bullish",
      "source_idx": 0
    }
  ],

  "entities": [
    {
      "name": "S&P 500",
      "entity_type": "index",
      "ticker": "^GSPC",
      "aliases": ["SPX"]
    }
  ],

  "relations": {
    "source_tagged_topic": [
      { "source_idx": 0, "topic_idx": 0 }
    ],
    "source_makes_claim": [
      { "source_idx": 0, "claim_idx": 0 }
    ],
    "claim_about_entity": [
      { "claim_idx": 0, "entity_idx": 0 }
    ]
  }
}
```

### 設計ポイント

| 決定事項 | 理由 |
|---------|------|
| `sources[]` は必須、他は任意 | Source が最小投入単位。Topic/Claim/Entity は段階的に追加可能 |
| ID は投入時に生成（キュー内は不要） | URL ベース決定論的 UUID で MERGE の冪等性を保証 |
| `source_idx` 等のインデックス参照 | キュー内での軽量な関連付け。ID 生成を遅延できる |
| `collected_at` フィールド | ソースが収集・調査された日時。`published_at`（記事の公開日）とは異なり、「いつこの情報を調べたか」を記録 |
| `meta` フィールド | コマンド固有のメタデータ（issue_number 等）を構造化せずに保存 |

### 出力先

```
.tmp/graph-queue/
  finance-news-workflow/
    gq-20260307-120000-a1b2.json    # 未処理（/save-to-graph 成功後に削除）
  ai-research-collect/
    gq-20260307-130000-c3d4.json
```

---

## 3. コマンド別マッピング定義

### 3.1 finance-news-workflow

**入力**: `.tmp/news-batches/{theme_key}.json`

| 入力フィールド | graph-queue フィールド |
|--------------|---------------------|
| `articles[].url` | `sources[].url` |
| `articles[].title` | `sources[].title` |
| `articles[].feed_source` | `sources[].publisher` |
| `articles[].published` | `sources[].published_at` |
| コマンド実行日時 | `sources[].collected_at` |
| `articles[].summary` | `claims[].content`（軽量 Claim として） |
| `issue_config.theme_label` | `topics[].name` |
| テーマ→カテゴリ変換 | `topics[].category` |
| 固定値 `"news"` | `sources[].source_type` |
| 固定値 `"en"` | `sources[].language` |

**テーマ→Topic カテゴリ変換表**:

| theme_key | topic.name | topic.category |
|-----------|-----------|----------------|
| index | 株価指数 | stock |
| stock | 個別銘柄 | stock |
| sector | セクター | sector |
| macro_cnbc, macro_other | マクロ経済 | macro |
| ai_cnbc, ai_nasdaq, ai_tech | AI関連 | ai |
| finance_cnbc, finance_nasdaq, finance_other | 金融 | finance |

### 3.2 ai-research-collect

**入力**: `.tmp/ai-research-batches/{category_key}.json`

| 入力フィールド | graph-queue フィールド |
|--------------|---------------------|
| `articles[].url` | `sources[].url` |
| `articles[].title` | `sources[].title` |
| `articles[].company_name` | `sources[].publisher` |
| `articles[].published` | `sources[].published_at` |
| `articles[].source_type` | `sources[].source_type`（blog→web, press_release→news） |
| `issue_config.category_label` | `topics[].name` |
| 固定値 `"ai"` | `topics[].category` |
| `articles[].company_name` | `entities[].name`（entity_type: company） |
| `investment_context.key_tickers[]` | `entities[].ticker` |

### 3.3 generate-market-report

**入力**: `articles/market_report/{date}/data/` 配下の複数 JSON

| 入力ファイル | graph-queue マッピング |
|------------|---------------------|
| `news_from_project.json` | Source ノード（source_type: news） |
| `news_supplemental.json` | Source ノード（source_type: web） |
| `indices.json` のティッカー | Entity ノード（entity_type: index） |
| `mag7.json` のティッカー | Entity ノード（entity_type: company） |
| `sectors.json` のティッカー | Entity ノード（entity_type: sector） |
| `hypotheses_*.json` | Claim ノード（claim_type: analysis） |

### 3.4 asset-management

**入力**: `.tmp/asset-mgmt-*.json`

| 入力フィールド | graph-queue フィールド |
|--------------|---------------------|
| `themes.{key}.articles[].url` | `sources[].url` |
| `themes.{key}.articles[].title` | `sources[].title` |
| `themes.{key}.articles[].feed_source` | `sources[].publisher` |
| テーマ名（NISA等） | `topics[].name` |
| 固定値 `"finance"` | `topics[].category` |
| 固定値 `"ja"` | `sources[].language` |

### 3.5 reddit-finance-topics

**入力**: `.tmp/reddit-topics/{timestamp}.json`

| 入力フィールド | graph-queue フィールド |
|--------------|---------------------|
| `topics[].url` | `sources[].url` |
| `topics[].title` | `sources[].title` |
| `"Reddit r/{subreddit}"` | `sources[].publisher` |
| `topics[].created_at` | `sources[].published_at` |
| 固定値 `"web"` | `sources[].source_type` |
| `group_name_ja` | `topics[].name` |
| グループ→カテゴリ変換 | `topics[].category` |
| `score`, `num_comments` 等 | `sources[].meta` |

### 3.6 finance-full / finance-edit

**入力**: `articles/{id}/01_research/sources.json`, `claims.json`, `article-meta.json`

| 入力フィールド | graph-queue フィールド |
|--------------|---------------------|
| `sources[].url` | `sources[].url` |
| `sources[].title` | `sources[].title` |
| `claims[].content` | `claims[].content` |
| `claims[].type` | `claims[].claim_type` |
| `claims[].sentiment` | `claims[].sentiment` |
| `article-meta.json` の category | `topics[].category` |
| `article-meta.json` の symbols[] | `entities[].ticker` |

---

## 4. scripts/emit_graph_queue.py（共通変換スクリプト）

各コマンドの SKILL.md 末尾から呼び出す共通 Python スクリプト。マッピングロジックを1箇所に集約する。

```bash
# 使用例
python scripts/emit_graph_queue.py \
  --command finance-news-workflow \
  --input .tmp/news-batches/index.json

python scripts/emit_graph_queue.py \
  --command ai-research-collect \
  --input .tmp/ai-research-batches/ai_llm.json

python scripts/emit_graph_queue.py \
  --command generate-market-report \
  --input articles/market_report/2026-03-05/data/
```

**設計**:
- 各コマンドのマッピングロジックを `command_source` 引数で分岐
- マッピング定義は同ファイル内に辞書形式で保持（外部設定ファイル不要）
- 出力先: `.tmp/graph-queue/{command_source}/{queue_id}.json`
- 依存: 標準ライブラリのみ（json, uuid, hashlib, pathlib, argparse）

---

## 5. save-to-graph スキル

### 5.1 ファイル構成

```
.claude/skills/save-to-graph/
  SKILL.md              # メインスキル定義（処理フロー、パラメータ、エラー処理）
  guide.md              # 詳細ガイド（graph-queue フォーマット仕様、Cypher テンプレート）

.claude/commands/save-to-graph.md   # スラッシュコマンド定義
```

### 5.2 処理フロー

```
/save-to-graph [--source <command>] [--dry-run] [--file <path>]
  |
  +-- Phase 1: キュー検出・検証（30秒以内）
  |     +-- .tmp/graph-queue/ 配下の未処理 JSON を Glob で検出
  |     +-- schema_version, sources[] 必須フィールド検証
  |     +-- Neo4j 接続確認（mcp__neo4j-cypher__get_neo4j_schema）
  |
  +-- Phase 2: ノード投入（MERGE ベース、冪等）
  |     +-- Step 2.1: Topic MERGE（name + category で一意）
  |     +-- Step 2.2: Entity MERGE（name + entity_type で一意）
  |     +-- Step 2.3: Source MERGE（url で一意）
  |     +-- Step 2.4: Claim MERGE（content ハッシュで一意）
  |
  +-- Phase 3: リレーション投入（MERGE ベース）
  |     +-- TAGGED, MAKES_CLAIM, ABOUT
  |
  +-- Phase 4: 完了処理
        +-- 処理済みファイルを削除（--keep 時のみ _processed/ に移動）
        +-- 統計サマリー出力
```

### 5.3 ID 生成戦略（冪等性の保証）

| ノード | MERGE キー | ID 生成方法 |
|--------|-----------|------------|
| Source | `url` | `uuid5(NAMESPACE_URL, url)` |
| Topic | `topic_key`（`{name}::{category}`） | `uuid5(NAMESPACE_URL, "topic:{name}:{category}")` |
| Entity | `entity_key`（`{name}::{entity_type}`） | `uuid5(NAMESPACE_URL, "entity:{name}:{entity_type}")` |
| Claim | `claim_id` | `sha256(content)[:16]` |

**注**: Neo4j 5 Community では複合一意制約が使えないため、Topic と Entity は連結キー（`topic_key`, `entity_key`）を単一プロパティとして保持し、そこに UNIQUE 制約をかける。

### 5.4 Cypher テンプレート

**制約作成（初回セットアップ）**:

```cypher
CREATE CONSTRAINT source_url_unique IF NOT EXISTS
FOR (s:Source) REQUIRE s.url IS UNIQUE;

CREATE CONSTRAINT topic_key_unique IF NOT EXISTS
FOR (t:Topic) REQUIRE t.topic_key IS UNIQUE;

CREATE CONSTRAINT entity_key_unique IF NOT EXISTS
FOR (e:Entity) REQUIRE e.entity_key IS UNIQUE;

CREATE CONSTRAINT claim_id_unique IF NOT EXISTS
FOR (c:Claim) REQUIRE c.claim_id IS UNIQUE;

CREATE INDEX source_published_at IF NOT EXISTS FOR (s:Source) ON (s.published_at);
CREATE INDEX source_source_type IF NOT EXISTS FOR (s:Source) ON (s.source_type);
CREATE INDEX entity_ticker IF NOT EXISTS FOR (e:Entity) ON (e.ticker);
CREATE INDEX topic_category IF NOT EXISTS FOR (t:Topic) ON (t.category);
```

**Source MERGE**:

```cypher
UNWIND $sources AS s
MERGE (src:Source {url: s.url})
  ON CREATE SET
    src.source_id = s.source_id,
    src.title = s.title,
    src.source_type = s.source_type,
    src.publisher = s.publisher,
    src.published_at = CASE WHEN s.published_at IS NOT NULL
      THEN datetime(s.published_at) ELSE NULL END,
    src.collected_at = datetime(s.collected_at),
    src.language = s.language,
    src.meta = s.meta,
    src.created_at = datetime()
  ON MATCH SET
    src.title = coalesce(s.title, src.title),
    src.publisher = coalesce(s.publisher, src.publisher)
RETURN count(src) AS source_count
```

**Topic MERGE**:

```cypher
UNWIND $topics AS t
MERGE (topic:Topic {topic_key: t.topic_key})
  ON CREATE SET
    topic.topic_id = t.topic_id,
    topic.name = t.name,
    topic.category = t.category,
    topic.created_at = datetime()
RETURN count(topic) AS topic_count
```

**Entity MERGE**:

```cypher
UNWIND $entities AS e
MERGE (entity:Entity {entity_key: e.entity_key})
  ON CREATE SET
    entity.entity_id = e.entity_id,
    entity.name = e.name,
    entity.entity_type = e.entity_type,
    entity.ticker = e.ticker,
    entity.aliases = e.aliases,
    entity.created_at = datetime()
  ON MATCH SET
    entity.ticker = coalesce(e.ticker, entity.ticker)
RETURN count(entity) AS entity_count
```

**リレーション MERGE**:

```cypher
-- TAGGED
UNWIND $rels AS r
MATCH (src:Source {url: r.source_url})
MATCH (topic:Topic {topic_key: r.topic_key})
MERGE (src)-[:TAGGED]->(topic)
RETURN count(*) AS tagged_count

-- MAKES_CLAIM
UNWIND $rels AS r
MATCH (src:Source {url: r.source_url})
MATCH (claim:Claim {claim_id: r.claim_id})
MERGE (src)-[rel:MAKES_CLAIM]->(claim)
  ON CREATE SET rel.extracted_at = datetime()
RETURN count(*) AS claim_count

-- ABOUT
UNWIND $rels AS r
MATCH (claim:Claim {claim_id: r.claim_id})
MATCH (entity:Entity {entity_key: r.entity_key})
MERGE (claim)-[:ABOUT]->(entity)
RETURN count(*) AS about_count
```

---

## 6. 既存コマンドへの変更（最小限）

各コマンドの SKILL.md 末尾に1ステップ追加するだけ。

### 追加ステップのテンプレート

```markdown
### Step X.Y: graph-queue 出力（任意）

セッション完了後、収集データをナレッジグラフキューに出力する。

\```bash
# テーマ別バッチファイルから graph-queue を生成
for batch_file in .tmp/news-batches/*.json; do
  python scripts/emit_graph_queue.py \
    --command finance-news-workflow \
    --input "$batch_file"
done
echo "graph-queue files generated. Run /save-to-graph to ingest."
\```
```

### 各コマンドの変更量

| コマンド | 追加箇所 | 入力ファイル | 変更量 |
|---------|---------|------------|--------|
| finance-news-workflow | Phase 3 末尾 | `.tmp/news-batches/*.json` | +10行 |
| ai-research-collect | Phase 3 末尾 | `.tmp/ai-research-batches/*.json` | +10行 |
| generate-market-report | Phase 7 末尾 | `articles/market_report/{date}/data/` | +5行 |
| asset-management | Phase 4 末尾 | `.tmp/asset-mgmt-*.json` | +5行 |
| reddit-finance-topics | Phase 1 末尾 | `.tmp/reddit-topics/*.json` | +5行 |
| finance-full | Phase 3 末尾 | `articles/{id}/01_research/` | +5行 |

---

## 7. Phase 1 / Phase 2 スコープ

### Phase 1（今回実装）

| 対象 | 内容 |
|------|------|
| Source ノード | 全6コマンドからの情報ソース |
| Topic ノード + TAGGED | テーマ/カテゴリからの自動生成 |
| Entity ノード | 構造化メタデータから（company_key, ticker 等） |
| Claim ノード + MAKES_CLAIM | RSS summary の軽量 Claim、finance-full の claims.json |
| ABOUT リレーション | Claim → Entity（ticker/company 紐付け） |
| scripts/emit_graph_queue.py | 共通変換スクリプト |
| save-to-graph スキル | Neo4j 投入スキル |

### Phase 2（将来拡張）

| 対象 | 内容 |
|------|------|
| Fact ノード | LLM で Claim から客観的事実を分離 |
| SUPPORTED_BY | エビデンスチェーン（Claim → Fact） |
| CONTRADICTS | 主張間の矛盾検出 |
| Author ノード | 著者/組織の構造化 |
| Entity 充実 | NER による本文からのエンティティ抽出 |
| `/enrich-graph` コマンド | LLM ベースのグラフ充実化 |
| `/query-graph` コマンド | グラフ検索・分析 |
| 自動 emit | コマンド終了時に自動で graph-queue 出力（フック化） |

---

## 8. 実装順序

1. **Neo4j 制約作成** - `mcp__neo4j-cypher__write_neo4j_cypher` で制約・インデックスを作成
2. **scripts/emit_graph_queue.py** - 全6コマンドのマッピングロジックを含む共通スクリプト
3. **save-to-graph スキル** - `.claude/skills/save-to-graph/SKILL.md` + `guide.md`
4. **save-to-graph コマンド** - `.claude/commands/save-to-graph.md`
5. **finance-news-workflow への統合** - 最もシンプルなマッピング、最大データ量で検証
6. **残り5コマンドへの統合** - 1コマンドずつ追加
7. **冪等性テスト** - 同じデータを2回投入して重複なしを確認

---

## 9. 検証方法

### 機能検証

1. `finance-news-workflow` 実行後に `.tmp/graph-queue/` にキューファイルが生成されることを確認
2. `/save-to-graph --dry-run` でファイル検証のみ実行
3. `/save-to-graph` で Neo4j に投入、`mcp__neo4j-cypher__read_neo4j_cypher` で確認:
   ```cypher
   MATCH (s:Source)-[:TAGGED]->(t:Topic)
   RETURN t.name, count(s) ORDER BY count(s) DESC
   ```
4. 同じファイルを再投入して重複ノードが作られないことを確認

### 各コマンド検証

| コマンド | 検証クエリ |
|---------|-----------|
| finance-news | `MATCH (s:Source {source_type:'news'})-[:TAGGED]->(t) RETURN t.name, count(s)` |
| ai-research | `MATCH (s:Source)-[:TAGGED]->(t {category:'ai'}) RETURN count(s)` |
| generate-market-report | `MATCH (e:Entity {entity_type:'index'}) RETURN e.name, e.ticker` |

---

## 10. 対象ファイル一覧

### 新規作成

| ファイル | 説明 |
|---------|------|
| `scripts/emit_graph_queue.py` | graph-queue 生成スクリプト（全マッピングロジック） |
| `.claude/skills/save-to-graph/SKILL.md` | スキル定義 |
| `.claude/skills/save-to-graph/guide.md` | 詳細ガイド |
| `.claude/commands/save-to-graph.md` | スラッシュコマンド |

### 変更（末尾にステップ追加のみ）

| ファイル | 変更内容 |
|---------|---------|
| `.claude/skills/finance-news-workflow/SKILL.md` | Phase 3 末尾に graph-queue 出力ステップ追加 |
| `.claude/skills/ai-research-workflow/SKILL.md` | Phase 3 末尾に追加 |
| `.claude/skills/generate-market-report/SKILL.md` | 最終フェーズ末尾に追加 |
| `.claude/skills/asset-management-workflow/SKILL.md` | Phase 4 末尾に追加 |
| `.claude/skills/reddit-finance-topics/SKILL.md` | Phase 1 末尾に追加 |
| `.claude/commands/finance-full.md` | Phase 3 末尾に追加 |

### 変更（スキーマ更新）

| ファイル | 変更内容 |
|---------|---------|
| `data/config/knowledge-graph-schema.yaml` | Source ノードに `collected_at` フィールド追加、`fetched_at` を `collected_at` にリネーム |

### 参照（変更なし）

| ファイル | 用途 |
|---------|------|
| `docker-compose.yml` | Neo4j 設定確認（APOC 有効化済み） |
| `src/rss/types.py` | FeedItem フィールド定義の参照 |
| `data/config/finance-news-themes.json` | テーマ→カテゴリ変換表の参照 |
