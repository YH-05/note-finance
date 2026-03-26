---
name: research-enrichment
description: research-neo4j (bolt://localhost:7688) の知識ギャップを自動拡充するスキル。ギャップ分析(4軸スコア)→動的ソース選択(Tavily+SEC EDGAR+alphaxiv+Reddit+Wikipedia)→LLM構造化+直接マッピング→パイプライン投入(entity_linker→emit_research_queue→save-to-research-graph)を終了時刻まで繰り返す。
allowed-tools: Read, Write, Bash, Grep, Glob
---

# research-enrichment スキル

research-neo4j（bolt://localhost:7688）のナレッジグラフを自動拡充する 6 フェーズループ。
終了時刻（`--until`）まで、ギャップ分析→検索→LLM 構造化→パイプライン投入を繰り返す。

> **警告**: research-neo4j への投入には必ず `/save-to-research-graph` を使用してください。
> `/save-to-creator-graph` は creator-neo4j 専用です。

---

## パラメータ

| パラメータ | 必須 | 説明 | 例 |
|-----------|------|------|----|
| `--until` | 必須 | 終了時刻（HH:MM 形式、24 時間制） | `--until 23:30` |
| `--focus-entity` | 任意 | 特定 Entity に絞って拡充（entity_key 形式） | `--focus-entity amd::company` |
| `--dry-run` | 任意 | 検索・構造化のみ実行し投入をスキップ | `--dry-run` |

---

## Phase 0: Init（初期化）

### 0-1. MCP ツール取得

ToolSearch で以下の MCP ツールを取得する:

```
ToolSearch: "select:mcp__neo4j-research__research-read_neo4j_cypher,mcp__neo4j-research__research-write_neo4j_cypher,mcp__neo4j-research__research-get_neo4j_schema"
ToolSearch: "select:mcp__sec-edgar-mcp__get_recent_filings,mcp__sec-edgar-mcp__get_financials,mcp__sec-edgar-mcp__get_key_metrics"
ToolSearch: "select:mcp__alphaxiv__embedding_similarity_search,mcp__alphaxiv__get_paper_content"
ToolSearch: "select:mcp__wikipedia__get_summary"
ToolSearch: "select:mcp__tavily__tavily_search,mcp__tavily__tavily_extract"
ToolSearch: "select:mcp__reddit__get_subreddit_hot_posts,mcp__reddit__get_subreddit_new_posts,mcp__reddit__get_post_content"
ToolSearch: "select:mcp__time__get_current_time"
ToolSearch: "select:WebFetch,WebSearch"
```

### 0-2. 接続チェック

```cypher
// mcp__neo4j-research__research-read_neo4j_cypher
RETURN 1 AS ok
```

失敗時はエラーメッセージを出力して終了。

### 0-2.5. Source.created_at インデックス確認

```cypher
// mcp__neo4j-research__research-write_neo4j_cypher
CREATE INDEX source_created_at IF NOT EXISTS FOR (s:Source) ON (s.created_at)
```

### 0-3. 設定ファイル読み込み

```
Read data/config/research-enrichment-config.json
```

### 0-4. セッションログ作成

`.tmp/research-enrichment-{YYYYMMDD-HHmmss}.log.md` を作成。

```markdown
# Research Enrichment Session
- start: {ISO8601}
- until: {--until value}
- focus_entity: {--focus-entity or "auto"}

## Cycles
```

### 0-5. browser-use CLI 可用性チェック

```bash
source ~/.browser-use-env/bin/activate && browser-use state 2>&1 | head -1
```

- 成功時: セッション状態フラグ `browser_use_available = true` をセット
- 失敗時（venv 未存在 or コマンドエラー）: `browser_use_available = false`、セッションログに記録
- browser-use は **フォールバック専用** — Tavily が利用可能な間は使用しない

### 0-6. 現在時刻の取得

`mcp__time__get_current_time` で現在時刻を取得し、`--until` と比較。
既に終了時刻を過ぎている場合はエラー終了。

---

## Phase 1: Gap Analysis（ギャップ分析）

`references/gap-analysis-queries.md` に定義された Q1-Q5 を実行する。

| クエリ | 目的 | 用途 |
|--------|------|------|
| Q1 | ConceptCategory 別 Fact 密度 | category_gap スコア算出 |
| Q2 | ticker あり & Fact 0 件の Entity + バリアント（1-3 件） | entity_gap スコア算出 |
| Q3 | 鮮度（as_of_date が古い Entity 昇順） | staleness スコア算出 |
| Q4 | sec_cik あり & FDP 0 件の Entity | financial_gap スコア算出 |
| Q5 | 直近 7 日間の Source URL 一覧 | 重複排除リスト構築 |

全クエリは `mcp__neo4j-research__research-read_neo4j_cypher` で実行する。
Q1-Q4 は相互に依存しないため並列実行可能。
Q2 はメインクエリ（Fact 0 件）とバリアントクエリ（Fact 1-3 件）の**両方を必ず実行**すること。

### 4 軸スコア算出

```
unified_score = 0.15 * category_gap + 0.35 * entity_gap + 0.30 * staleness + 0.20 * financial_gap
```

| 軸 | 重み | 正規化式 |
|----|------|----------|
| category_gap | 0.15 | `1 - min(facts_per_topic / min_facts_per_topic, 1.0)` |
| entity_gap | 0.35 | Fact 0 件 → 1.0、1-3 件 → 0.5、4+ 件 → 0.0 |
| staleness | 0.30 | `min(days_since_latest / staleness_threshold_days, 1.0)` |
| financial_gap | 0.20 | sec_cik あり & FDP 0 件 → 1.0、それ以外 → 0.0 |

### セッション内ダンピング

同一セッション内で既に処理済みの Entity が再度上位に来ることを防ぐ:

```
処理済み Entity のスコア: unified_score × 0.3
```

### ターゲット選定

`--focus-entity` 指定時はその Entity のみを対象とする。

未指定時は unified_score の上位 `max_targets_per_cycle` 件（Config デフォルト: 5）を選定し、
そのサイクルの検索・構造化・投入対象とする。

選定結果の出力形式:

```json
[
  {
    "entity_key": "amd::company",
    "name": "AMD",
    "ticker": "AMD",
    "sec_cik": "2488",
    "sector": "Technology",
    "scores": {
      "category_gap": 0.0,
      "entity_gap": 1.0,
      "staleness": 0.0,
      "financial_gap": 1.0
    },
    "unified_score": 0.55,
    "damping_applied": false,
    "target_sources": ["web_search", "sec_edgar", "reddit", "alphaxiv"]
  }
]
```

---

## Phase 2: Search（検索）

`references/search-strategy.md` を参照し、ターゲット Entity の属性に基づいてデータソースを動的に選択する。

### ソース選択マトリクス

#### 常時実行（全 Entity 共通）

| ソース | ツール | クエリ数 |
|--------|--------|---------|
| Tavily EN | `mcp__tavily__tavily_search` | 2 |
| Tavily JA | `mcp__tavily__tavily_search` | 2 |
| Reddit | `mcp__reddit__get_subreddit_hot_posts` / `get_subreddit_new_posts` | 1-2 |

#### 条件付き実行

| 条件 | ソース | ツール |
|------|--------|--------|
| `ticker IS NOT NULL` | SEC EDGAR | `get_recent_filings`, `get_financials`, `get_key_metrics` |
| sector = Technology or EquityResearch | alphaxiv | `embedding_similarity_search` 優先、`get_paper_content` 2-3 件 |
| `description IS NULL` or 空文字 | Wikipedia | `get_summary` |

### フォールバックチェーン

```
1st: Tavily MCP (tavily_search)
 │   └─ 432 エラー → キーローテーション → 全キー枯渇
 │
2nd: WebSearch（ビルトイン）
 │   └─ 結果 0 件 or エラー
 │
3rd: browser-use CLI 2.0
      └─ venv 未存在 or コマンドエラー → 当該クエリをスキップ
```

**フォールバック判定**: Tavily が `exceeds your plan's set usage limit` エラーを返した場合、
そのサイクル以降は **Tier 2 以降のみ** を使用する（`tavily_available = false` をセット）。

### SEC EDGAR 実行ルール

ticker を持つ Entity に対し、`search-strategy.md` の「SEC EDGAR」セクションに定義された 3 ツールを**並列実行**する。

**重要**: SEC EDGAR データは `raw_items[]` に格納せず、**直接マッピング**する（Phase 3 で LLM バイパス）。

### alphaxiv 実行ルール

**必ず `.agents/skills/alphaxiv-search/SKILL.md` のルールに従う。**

| 優先度 | ツール | 並列上限 |
|--------|--------|---------|
| **1st（主軸）** | `embedding_similarity_search` | 3 件同時 |
| 2nd（厳選） | `get_paper_content` | **2-3 件ずつ** |
| 使わない | `agentic_paper_retrieval` | — |

**重要**: alphaxiv データは `raw_items[]` に格納せず、**直接マッピング**する（Phase 3 で LLM バイパス）。

### Wikipedia 実行ルール

`description` が NULL または空文字の Entity のみ対象。
取得した summary は Entity の `description` プロパティに SET する。
`raw_items[]` には格納しない（構造化データとして直接利用）。

### Reddit 実行ルール

Entity の `ticker` がある場合はサブレディット内で ticker をキーワードに絞り込む。
`get_post_content` での深掘りは重要な投稿 2-3 件に限定する。
**複数サブレディットの検索は並列実行可能**（Entity 単位でグルーピングして並列化すること）。

### 検索結果の集約

全検索結果を以下の形式に正規化:

```json
{
  "raw_items": [
    {
      "source_url": "https://...",
      "title": "...",
      "content": "...",
      "source_type": "web | social | news | blog",
      "authority_level": "media | analyst | blog | social | official | academic",
      "target_entity": "amd::company"
    }
  ]
}
```

Q5 の重複排除リストと照合し、既存 URL はスキップする。

### RawStore 保存

SEC EDGAR・alphaxiv・Wikipedia **以外**の raw_items を RawStore に保存する:

```python
from data_pipeline.storage.raw_store import RawStore

store = RawStore()
for item in raw_items:
    store.save_text(
        source_id=f"research-{entity_key}",
        url=item["source_url"],
        title=item["title"],
        raw_text=item["content"],
        collection_method=item["source_type"],
    )
```

### コンテキスト肥大化対策

raw_items のコンテンツはコンテキストを圧迫する。Phase 2 完了後、raw_items 全体を
`.tmp/research-raw-{cycle_id}.json` にファイル書き出しし、以降はファイルパスで参照する。

---

## Phase 3: Data Transform（LLM 構造化 + 直接マッピング）

`references/transform-prompt.md` のプロンプトテンプレートを使用する。

### 3-1. LLM 構造化（Web 検索 + Reddit 結果）

raw_items（Web検索・Reddit 等の非構造化テキスト）を `transform-prompt.md` のプロンプトで
`emit_research_queue.py --command web-research` の入力仕様に準拠した JSON に変換する。

**出力 JSON フォーマット**:

```json
{
  "sources": [
    {
      "url": "https://...",
      "title": "...",
      "source_type": "web | social | news | blog",
      "authority_level": "media | analyst | blog | social | official | academic",
      "publisher": "CNBC"
    }
  ],
  "facts": [
    {
      "content": "事実の記述（数値含む）",
      "source_url": "https://...",
      "confidence": 0.9,
      "fact_type": "financial_metric | operational_kpi | market_event | ...",
      "about_entities": [
        {"name": "AMD", "entity_type": "company"}
      ]
    }
  ],
  "claims": [
    {
      "content": "意見・予測の記述",
      "source_url": "https://...",
      "claim_type": "analyst_opinion | analyst_forecast | ...",
      "sentiment": "positive | negative | neutral",
      "about_entities": [
        {"name": "AMD", "entity_type": "company"}
      ]
    }
  ],
  "topics": [
    {
      "name": "AMD AI Chip Revenue Growth",
      "category": "stock"
    }
  ]
}
```

### 3-2. SEC EDGAR 直接マッピング（LLM バイパス）

SEC EDGAR の構造化データは LLM 変換をバイパスして直接マッピングする:

- `get_financials` / `get_key_metrics` → FinancialDataPoint ノード
- `get_recent_filings` → Source ノード（`source_type: "sec_filing"`, `authority_level: "official"`）
- 固定値: `confidence: 1.0`, `fact_type: "financial_metric"`

### 3-3. alphaxiv 直接マッピング（LLM バイパス）

alphaxiv の構造化データも LLM 変換をバイパスして直接マッピングする:

- `embedding_similarity_search` の Abstract → Fact ノード
- `get_paper_content` の Method / Results → Claim ノード
- Source ノード: `source_type: "academic"`, `authority_level: "academic"`
- 固定値: `fact_type: "research_finding"`

### 3-4. JSON 統合

LLM 構造化結果 + SEC EDGAR マッピング + alphaxiv マッピングを 1 つの JSON に統合する。

出力先: `.tmp/research-cycle-{cycle_id}.json`

### コンテキスト肥大化対策

Phase 3 完了後、raw_items のメモリ上のデータは不要。
`.tmp/research-raw-{cycle_id}.json` に書き出し済みのため、以降は参照しない。

---

## Phase 4: Pipeline（パイプライン投入）— 3 段構成

> **Neo4j 直書き禁止**: `mcp__neo4j-research__research-write_neo4j_cypher` で直接ノード・
> リレーションを作成してはならない（スキーマ操作・修復作業を除く）。

### Phase 4 実行前: authority_level バリデーション

投入前に `.tmp/research-cycle-{cycle_id}.json` の全 sources に `authority_level` が
設定されていることを検証する。欠損がある場合は URL ドメインから補完する。

```python
# 検証ロジック
for source in data["sources"]:
    if not source.get("authority_level"):
        raise ValueError(f"authority_level missing for: {source['url']}")
```

### Phase 4-0: Entity リンキング

抽出結果を既存ノードと照合し、重複作成を防ぐ。

```bash
uv run --extra embedding python scripts/entity_linker.py \
  --input .tmp/research-cycle-{cycle_id}.json \
  --instance research \
  --v3
```

出力: `.tmp/research-cycle-{cycle_id}.resolved.json`

> **entity_linker.py `--instance` 省略禁止**:
> `--instance` のデフォルトは `creator` であるため、省略すると creator-neo4j に接続してしまう。
> research-neo4j に接続するには **必ず `--instance research` を指定**すること。

### Phase 4-1: graph-queue JSON 生成

```bash
uv run python scripts/emit_research_queue.py \
  --command web-research \
  --input .tmp/research-cycle-{cycle_id}.resolved.json
```

出力: `.tmp/research-graph-queue/rq-{timestamp}-{rand8}.json`

### Phase 4-2: グラフ投入

`/save-to-research-graph` スキルを呼び出して投入する。

```
/save-to-research-graph .tmp/research-graph-queue/rq-{timestamp}-{rand8}.json
```

内部で `mcp__neo4j-research__research-write_neo4j_cypher` を使用してノード・リレーションを書き込む。

### Phase 4-3: 投入検証

投入後、`mcp__neo4j-research__research-read_neo4j_cypher` で件数を確認する。
resolved.json の sources/facts/claims 件数と投入後のノード件数を比較検証する:

```cypher
// 直近投入分の件数確認（created_at で絞り込み）
MATCH (s:Source)
WHERE s.created_at >= datetime() - duration('PT5M')
RETURN 'Source' AS label, count(s) AS count
UNION ALL
MATCH (f:Fact)
WHERE f.created_at >= datetime() - duration('PT5M')
RETURN 'Fact' AS label, count(f) AS count
UNION ALL
MATCH (c:Claim)
WHERE c.created_at >= datetime() - duration('PT5M')
RETURN 'Claim' AS label, count(c) AS count
```

期待される最低限のノード:
- Source: resolved.json の sources 件数分
- Fact / Claim: resolved.json の facts + claims 件数分
- Entity: about_entities で参照された Entity

`--dry-run` 指定時は Phase 4 をスキップし、生成された JSON のサマリーのみ出力する。

---

## Phase 5: Cycle Report + Time Check

### 5-1. サイクルレポート

セッションログに以下を追記:

```markdown
### Cycle {N} - {entity_names}
- time: {HH:MM:SS}
- targets: [{entity_key_1}, {entity_key_2}, ...]
- search_results: {raw_items count}
- sec_edgar: {filings: N, metrics: N}
- alphaxiv: {papers: N}
- contents_created: {Fact: N, Claim: N}
- topics_tagged: {count}
- pipeline_status: {success | dry-run | error}
```

### 5-2. 時刻チェック（厳密ルール）

`mcp__time__get_current_time` で現在時刻を取得。

**停止判定の厳密ルール:**

```
MAINTENANCE_BUFFER = Config の maintenance_buffer_minutes（デフォルト 5 分）
stop_time = --until - MAINTENANCE_BUFFER

if 現在時刻 < stop_time:
    → Phase 1 に戻る（サイクル継続）
elif 現在時刻 >= stop_time AND 現在時刻 < --until:
    → Phase 6（Post-Session Maintenance）に移行
else:
    → 最終サマリーを出力して即座に終了
```

**禁止事項:**
- `stop_time` より前に「まとめ」「最終サマリー」「Phase 6」に入ってはならない
- 「バックグラウンドエージェントの完了待ち」「コンテキスト節約」を理由に早期停止してはならない
- Phase 6 の所要時間を 5 分超と見積もってはならない（TAGGED retroactive は 2-3 分で完了する）

**例:** `--until 20:50` の場合、`stop_time = 20:45`。20:44 まではサイクルを継続し、20:45 に Phase 6 を開始する。

### 5-3. 空サイクル制御

検索結果が 0 件のサイクルが連続した場合:

- `max_consecutive_empty_cycles`（Config デフォルト 3）回連続 → 終了
- 空サイクル間は `empty_cycle_wait_seconds`（Config デフォルト 60 秒）待機

---

## Phase 6: Post-Session Maintenance（セッション終了時メンテナンス）

`--until` 到達でサイクルループ終了後、**1 回だけ**以下のメンテナンスを実行する。
全サイクルの投入完了後にまとめて実行することで、サイクル間の整合性も含めてチェックできる。

> **Phase 4.5（Cross-Entity RELATES_TO Enrichment）は実施しない。**
> research-neo4j の Entity 間リレーションはパイプラインの RELATES_TO で十分カバーされており、
> creator-neo4j のような共起分析ベースの横断リレーション追加は不要。

### 6-1. TAGGED Retroactive リンキング

未接続の Topic と Fact/Claim のテキストマッチで TAGGED リレーションを補完する。

```cypher
// mcp__neo4j-research__research-read_neo4j_cypher（候補検出）
MATCH (t:Topic)
WHERE NOT (t)<-[:TAGGED]-()
AND t.name IS NOT NULL AND size(t.name) >= 3
WITH t
MATCH (f)
WHERE (f:Fact OR f:Claim)
AND (f.content CONTAINS t.name)
RETURN t.name AS topic_name, t.topic_key AS topic_key,
       elementId(f) AS fact_id, labels(f)[0] AS fact_type,
       left(f.content, 80) AS preview
LIMIT 50
```

```cypher
// mcp__neo4j-research__research-write_neo4j_cypher（補完実行）
MATCH (t:Topic)
WHERE NOT (t)<-[:TAGGED]-()
AND t.name IS NOT NULL AND size(t.name) >= 3
WITH t
MATCH (f)
WHERE (f:Fact OR f:Claim)
AND (f.content CONTAINS t.name)
MERGE (f)-[:TAGGED]->(t)
RETURN count(*) AS tagged_created
```

> **注意**: Phase 6 では Embedding 更新は不要。research-neo4j の embedding は
> `entity_linker.py` の Stage 4 で必要に応じて付与済み。

### 6-2. 簡易品質スコア

メンテナンス結果を簡易スコアとしてセッションログに記録:

```markdown
### Post-Session Maintenance
- tagged_retroactive: {count} new TAGGED relationships
- duration: {seconds}s
```

---

## エラーハンドリング

| エラー | 対応 |
|--------|------|
| Neo4j 接続失敗 | Phase 0 で即座に終了。エラーメッセージを出力 |
| Tavily API リミット超過 | `tavily_available = false` をセットし、以降 WebSearch + browser-use CLI にフォールバック |
| Tavily API その他エラー | 該当クエリをスキップし、他の検索ソースで続行 |
| WebFetch タイムアウト | browser-use CLI にフォールバック（JS サイト）。CLI も失敗時はスキップ |
| browser-use CLI venv 未存在 | `browser_use_available = false`。WebFetch のみで続行 |
| browser-use CLI タイムアウト | 該当 URL をスキップ。セッションログに記録。30 秒タイムアウト推奨 |
| SEC EDGAR API エラー | SEC EDGAR 検索をスキップし、他のソースで続行 |
| alphaxiv エラー | alphaxiv をスキップし、他のソースで続行 |
| Reddit API エラー | Reddit 検索をスキップし、他の検索ソースで続行 |
| Wikipedia API エラー | description 補完をスキップ |
| entity_linker.py 失敗 | Entity Linking をスキップし未 resolved の JSON を Phase 4-1 に渡す。ただし未 resolved Entity が 50% 超の場合は投入をブロックしセッションログに警告を記録 |
| emit_research_queue.py 失敗 | セッションログにエラーを記録し、次サイクルへ |
| /save-to-research-graph 失敗 | セッションログにエラーを記録し、次サイクルへ。JSON は保持 |
| --until 時刻パース失敗 | エラーメッセージを出力して終了 |

---

## MUST / NEVER

### MUST

- Phase 2 で Entity 属性に基づくソース選択マトリクスに従い、該当する全ソースを実行すること。API エラー時のみスキップ可
- Tavily API リミット超過時は `tavily_available = false` をセットし、WebSearch + browser-use CLI に即座にフォールバックすること
- Reddit は毎サイクル最低 1 つの subreddit から投稿を取得すること
- Phase 3 で `transform-prompt.md` のプロンプトテンプレートに従い、Fact / Claim の分類を正確に行うこと
- Phase 3 の LLM 出力は検証チェックリスト（authority_level 存在、source_url 一致等）を必ず実行すること
- SEC EDGAR・alphaxiv のデータは LLM バイパスで直接マッピングすること（`raw_items[]` を経由しない）
- Phase 4 で `entity_linker.py` 実行時に **`--instance research` を必ず指定**すること（デフォルト creator で誤接続防止）
- Phase 4 で `/save-to-research-graph` を使用し、graph-queue JSON 経由で投入すること。Cypher 直書き禁止
- Phase 4 実行前に全 sources の `authority_level` バリデーションを実行すること
- セッションログに各ステップの実行結果（取得件数・スキップ理由・使用した Tier）を記録すること
- `--until - 5分` まではサイクルを継続すること（詳細: Phase 5-2 参照）

### NEVER

- `mcp__neo4j-research__research-write_neo4j_cypher` で直接ノード・リレーションを作成してはならない（スキーマ操作・Phase 6 の修復を除く）
- `entity_linker.py` で `--instance` を省略してはならない（デフォルト creator で誤接続）
- `--until - 5分` より前にサイクルループを終了してはならない。「十分なデータが集まった」「コンテキストが大きくなった」は停止理由にならない
- Phase 6（Post-Session Maintenance）を `--until - 5分` より前に実行してはならない
- Phase 4.5（Cross-Entity RELATES_TO Enrichment）を実施してはならない（research-neo4j では不要）
- browser-use CLI を Tavily が利用可能な間に使用してはならない（フォールバック専用）
- 時間制約やコンテキスト節約を理由に検索ステップを省略してはならない

---

## セッションログ形式

ファイル: `.tmp/research-enrichment-{YYYYMMDD-HHmmss}.log.md`

```markdown
# Research Enrichment Session
- start: 2026-03-25T14:00:00+09:00
- until: 16:30
- focus_entity: auto

## Cycles

### Cycle 1 - AMD, Broadcom, Google
- time: 14:02:35
- targets: [amd::company, broadcom::company, google::company]
- search_results: 18
- sec_edgar: {filings: 6, metrics: 24}
- alphaxiv: {papers: 3}
- contents_created: {Fact: 12, Claim: 5}
- topics_tagged: 4
- pipeline_status: success

### Cycle 2 - Microsoft, NVIDIA
- time: 14:15:42
- targets: [microsoft::company, nvidia::company]
- search_results: 14
- sec_edgar: {filings: 4, metrics: 18}
- alphaxiv: {papers: 2}
- contents_created: {Fact: 9, Claim: 3}
- topics_tagged: 3
- pipeline_status: success

## Summary
- total_cycles: 2
- total_facts: 21
- total_claims: 8
- total_sources: 32
- errors: 0
- end_reason: time_limit_reached

### Post-Session Maintenance
- tagged_retroactive: 7 new TAGGED relationships
- duration: 45s
```

---

## 投入前チェックリスト（5 項目）

Phase 4 実行前に、以下の 5 項目を全て確認すること:

- [ ] 入力 JSON に `sources[].authority_level` が設定されているか
- [ ] `facts[].source_url` が `sources` 内の URL と一致しているか
- [ ] `emit_research_queue.py --command web-research` で graph-queue JSON が生成できるか
- [ ] graph-queue JSON の `fact_entity` のリレーションタイプが `RELATES_TO` であるか
- [ ] `/save-to-research-graph` 実行前に MATCH クエリで対象データ件数を確認したか

---

## 関連ファイル

| ファイル | 説明 |
|---------|------|
| `data/config/research-enrichment-config.json` | Gap 分析重み・検索設定・サイクル設定 |
| `references/gap-analysis-queries.md` | ギャップ分析 Cypher クエリ集（Q1-Q5） |
| `references/search-strategy.md` | 動的ソース選択マトリクス・フォールバック・RawStore |
| `references/transform-prompt.md` | LLM 構造化プロンプトテンプレート |
| `scripts/entity_linker.py` | Entity リンキングスクリプト（`--instance research` 必須） |
| `scripts/emit_research_queue.py` | graph-queue JSON 生成スクリプト |
| `.agents/skills/save-to-research-graph/SKILL.md` | グラフ投入スキル |
| `.agents/skills/alphaxiv-search/SKILL.md` | alphaxiv MCP ルール |
| `.agents/skills/web-search/SKILL.md` | Web 検索ツール選択基準 |
