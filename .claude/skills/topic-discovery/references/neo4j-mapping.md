# Neo4j データモデルマッピング（research-neo4j）

topic-discovery の提案結果を research-neo4j に保存するためのデータモデル定義。
KG v2 スキーマ（`data/config/knowledge-graph-schema.yaml`）に準拠する。

## 接続情報

| 項目 | 値 |
|------|-----|
| コンテナ名 | research-neo4j |
| Bolt | bolt://localhost:7688 |
| Browser | http://localhost:7476 |
| ユーザー | neo4j |
| パスワード | `${NEO4J_PASSWORD:-gomasuke}` |

## ノードマッピング

### 1. Source ノード（セッション）

提案セッション全体を1つの Source ノードとして表現する。

| プロパティ | 値 | 備考 |
|-----------|-----|------|
| source_id | `{session_id}` | 例: `topic-suggestion-2026-03-16T1430` |
| title | `トピック提案セッション {YYYY-MM-DD}` | |
| source_type | `"original"` | 自己生成コンテンツ |
| fetched_at | `{generated_at}` | ISO 8601 |
| language | `"ja"` | |
| command_source | `"topic-discovery"` | カスタムプロパティ |
| suggestion_count | suggestions 配列の長さ | カスタムプロパティ |
| top_score | 最高スコア | カスタムプロパティ |
| search_queries_count | 検索実行回数（`--no-search` 時は 0） | カスタムプロパティ |
| recommendation | 推奨カテゴリ文字列 | カスタムプロパティ |

### 2. Topic ノード（記事カテゴリ）

提案に含まれるカテゴリを Topic ノードとして MERGE する。

| プロパティ | 値 | 備考 |
|-----------|-----|------|
| topic_id | `content:{category_key}` | 例: `content:market_report` |
| name | カテゴリ日本語名 | 下表参照 |
| category | `"content_planning"` | 記事計画用カテゴリ |

**カテゴリマッピング**:

| category_key | name |
|-------------|------|
| market_report | マーケットレポート |
| stock_analysis | 個別株分析 |
| macro_economy | マクロ経済 |
| asset_management | 資産形成 |
| side_business | 副業・収益化 |
| quant_analysis | クオンツ分析 |
| investment_education | 投資教育 |

### 3. Claim ノード（各トピック提案）

各トピック提案を Claim（claim_type: "recommendation"）として保存する。

| プロパティ | 値 | 備考 |
|-----------|-----|------|
| claim_id | `ts:{session_id}:rank{rank}` | 例: `ts:topic-suggestion-2026-03-16T1430:rank1` |
| content | `{topic}: {rationale}` | トピック名と提案理由を結合 |
| claim_type | `"recommendation"` | KG v2 スキーマ定義済み |
| sentiment | `"neutral"` | |
| magnitude | スコアから判定（下記参照） | |
| created_at | `{generated_at}` | ISO 8601 |
| rank | 提案順位 | カスタムプロパティ |
| topic_title | トピック名 | カスタムプロパティ |
| total_score | 合計スコア | カスタムプロパティ |
| timeliness | 時事性スコア | カスタムプロパティ |
| information_availability | 情報入手性スコア | カスタムプロパティ |
| reader_interest | 読者関心度スコア | カスタムプロパティ |
| feasibility | 執筆実現性スコア | カスタムプロパティ |
| uniqueness | 独自性スコア | カスタムプロパティ |
| estimated_word_count | 推定文字数 | カスタムプロパティ |
| target_audience | 対象読者層 | カスタムプロパティ |
| selected | 採用状態 | `null`/`true`/`false` |
| key_points | キーポイント | JSON文字列（`'["p1","p2"]'`） |
| suggested_period | 推奨対象期間 | カスタムプロパティ |

**magnitude 判定ルール**:

| total_score | magnitude |
|-------------|-----------|
| >= 40 | `"strong"` |
| >= 30 | `"moderate"` |
| < 30 | `"slight"` |

### 4. Entity ノード（推奨銘柄/指数）

`suggested_symbols` から MERGE で生成する。

| プロパティ | 値 | 備考 |
|-----------|-----|------|
| entity_id | `symbol:{ticker}` | 例: `symbol:^GSPC` |
| name | ティッカー | 例: `^GSPC` |
| entity_type | `^` で始まる → `"index"`, それ以外 → `"stock"` | |
| ticker | ティッカー | 例: `^GSPC` |

### 5. Fact ノード（検索トレンド）

`search_insights.trends` から生成する。`--no-search` 時はスキップ。

各 trend の `key_findings` を個別の Fact ノードとして保存する。

| プロパティ | 値 | 備考 |
|-----------|-----|------|
| fact_id | `trend:{session_id}:{trend_index}:{finding_index}` | 決定論的ID |
| content | key_finding テキスト | |
| fact_type | `"event"` | トレンド情報 |
| as_of_date | `{generated_at}` の日付部分 | |
| created_at | `{generated_at}` | ISO 8601 |
| search_query | 検索クエリ | カスタムプロパティ |
| search_source | `tavily` / `gemini` / `rss` | カスタムプロパティ |

## リレーション

| リレーション | From | To | 用途 |
|-------------|------|-----|------|
| TAGGED | Source | Topic | セッション → 提案に含まれるカテゴリ |
| MAKES_CLAIM | Source | Claim | セッション → 各トピック提案 |
| TAGGED | Claim | Topic | 提案 → そのカテゴリ |
| ABOUT | Claim | Entity | 提案 → 推奨銘柄/指数 |
| STATES_FACT | Source | Fact | セッション → 検索トレンド |

全リレーションは KG v2 スキーマに定義済み。

## 投入方法（パイプライン準拠）

**重要**: Cypher 直書き（`docker exec cypher-shell`）は `.claude/rules/neo4j-write-rules.md` により禁止。
標準パイプライン（`emit_graph_queue.py → /save-to-graph`）経由で投入する。

### 入力JSON → graph-queue JSON → Neo4j

```bash
# 1. 入力JSON を構築して保存
# .tmp/research-input/{session_id}.json

# 2. graph-queue JSON を生成
uv run python scripts/emit_graph_queue.py \
  --command topic-discovery \
  --input .tmp/research-input/{session_id}.json

# 3. Neo4j に投入
# /save-to-graph スキルを呼び出す
```

`emit_graph_queue.py` が `topic-discovery` コマンドをサポートしていない場合は `web-research` で代替する。

### 入力JSON フォーマット

```json
{
  "session_id": "topic-suggestion-2026-03-16T1430",
  "research_topic": "トピック提案セッション 2026-03-16",
  "as_of_date": "2026-03-16",
  "sources": [
    {
      "url": "internal://topic-discovery/topic-suggestion-2026-03-16T1430",
      "title": "トピック提案セッション 2026-03-16",
      "authority_level": "blog",
      "published_at": "2026-03-16",
      "source_type": "original"
    }
  ],
  "entities": [
    { "name": "^GSPC", "entity_type": "index" },
    { "name": "NVDA", "entity_type": "company" }
  ],
  "topics": [
    { "name": "マーケットレポート", "category": "content_planning" }
  ],
  "facts": [
    {
      "content": "S&P 500 が週間で2%上昇",
      "source_url": "internal://topic-discovery/topic-suggestion-2026-03-16T1430",
      "confidence": 0.8
    }
  ]
}
```

## グレースフルデグラデーション

| 状況 | 対処 |
|------|------|
| research-neo4j 未起動 | 警告出力してスキップ。Phase 5.1-5.2 のファイルに保存済み |
| Cypher 実行エラー | エラー内容を警告表示。セッションファイルから再実行可能 |
| Fact 生成で空データ | `--no-search` 時は Fact ノードと STATES_FACT リレーションを省略 |

## グラフクエリ例

```cypher
// 最近のトピック提案セッション一覧
MATCH (s:Source {command_source: 'topic-discovery'})
RETURN s.source_id, s.title, s.suggestion_count, s.top_score
ORDER BY s.fetched_at DESC
LIMIT 10;

// 特定セッションの提案一覧（スコア順）
MATCH (s:Source {source_id: 'topic-suggestion-2026-03-16T1430'})-[:MAKES_CLAIM]->(c:Claim)
OPTIONAL MATCH (c)-[:TAGGED]->(t:Topic)
OPTIONAL MATCH (c)-[:ABOUT]->(e:Entity)
RETURN c.rank, c.topic_title, c.total_score, c.magnitude,
       t.name AS category, collect(e.ticker) AS symbols
ORDER BY c.rank;

// カテゴリ別の提案頻度（どのカテゴリが多く提案されているか）
MATCH (c:Claim {claim_type: 'recommendation'})-[:TAGGED]->(t:Topic {category: 'content_planning'})
RETURN t.name, count(c) AS suggestion_count
ORDER BY suggestion_count DESC;

// 採用率の確認
MATCH (c:Claim {claim_type: 'recommendation'})
RETURN c.selected, count(c) AS count
ORDER BY count DESC;

// トレンドからの提案追跡（どのトレンドがどの提案に影響したか）
MATCH (s:Source {command_source: 'topic-discovery'})-[:STATES_FACT]->(f:Fact)
MATCH (s)-[:MAKES_CLAIM]->(c:Claim)
RETURN s.source_id, f.content AS trend, c.topic_title AS suggestion
ORDER BY s.fetched_at DESC;
```
