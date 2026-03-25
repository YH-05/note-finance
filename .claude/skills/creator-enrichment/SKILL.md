---
name: creator-enrichment
description: creator-neo4j (bolt://localhost:7689) を自動拡充するスキル。ギャップ分析→Web検索(Tavily+WebSearch+browser-use CLI+Reddit)→Fact/Tip/Story分類+Entity抽出→パイプライン投入を終了時刻まで繰り返す。Tavily API リミット時は WebSearch + browser-use CLI 2.0 に自動フォールバック。
allowed-tools: Read, Write, Bash, Grep, Glob
---

# creator-enrichment スキル

creator-neo4j（bolt://localhost:7689）のナレッジグラフを自動拡充する5フェーズループ。
終了時刻（`--until`）まで、ギャップ分析→検索→分類・Entity抽出→パイプライン投入を繰り返す。

> **警告**: `/save-to-research-graph` は research-neo4j 専用です。creator-neo4j への投入には必ず `/save-to-creator-graph` を使用してください。

---

## パラメータ

| パラメータ | 必須 | 説明 | 例 |
|-----------|------|------|----|
| `--until` | 必須 | 終了時刻（HH:MM 形式、24時間制） | `--until 23:30` |
| `--genre` | 任意 | 対象ジャンル限定（省略時は自動ローテーション） | `--genre career` |
| `--dry-run` | 任意 | 検索・分類のみ実行し投入をスキップ | `--dry-run` |

---

## Phase 0: Init（初期化）

### 0-1. MCP ツール取得

ToolSearch で以下の MCP ツールを取得する:

```
ToolSearch: "select:mcp__neo4j-creator__creator-read_neo4j_cypher,mcp__neo4j-creator__creator-write_neo4j_cypher,mcp__neo4j-creator__creator-get_neo4j_schema"
ToolSearch: "select:mcp__tavily__tavily_search,mcp__tavily__tavily_extract"
ToolSearch: "select:mcp__reddit__get_subreddit_hot_posts,mcp__reddit__get_subreddit_new_posts,mcp__reddit__get_post_content"
ToolSearch: "select:mcp__time__get_current_time"
ToolSearch: "select:WebFetch,WebSearch"
```

### 0-2. 接続チェック

```cypher
// mcp__neo4j-creator__creator-read_neo4j_cypher
RETURN 1 AS ok
```

失敗時はエラーメッセージを出力して終了。

### 0-3. 設定ファイル読み込み

```
Read data/config/creator-enrichment-config.json
```

### 0-4. セッションログ作成

`.tmp/creator-enrichment-{YYYYMMDD-HHmmss}.log.md` を作成。

```markdown
# Creator Enrichment Session
- start: {ISO8601}
- until: {--until value}
- genre_filter: {--genre or "auto"}

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

`references/gap-analysis-queries.md` に定義された4クエリを実行する。

| クエリ | 目的 | 用途 |
|--------|------|------|
| Q1 | ジャンル別コンテンツ数 | ローテーション優先度算出 |
| Q2 | コンテンツタイプバランス（Fact/Tip/Story） | 不足タイプの補充 |
| Q3 | 低カバレッジトピック TOP 10 | 検索クエリのトピック選定 |
| Q4 | 既存コンテンツサンプル | 重複排除 |

全クエリは `mcp__neo4j-creator__creator-read_neo4j_cypher` で実行する。

### ジャンルローテーション

`--genre` 未指定時、以下の式で次のジャンルを決定する:

```
priority_score = 1.0 / (content_count + 1)
```

前回と同じジャンルの場合、ダンピング係数を適用:

```
priority_score *= 0.7  // same genre damping
```

最も priority_score が高いジャンルを選択する。

---

## Phase 2: Search（検索）

`references/genre-config.md` を参照し、選択ジャンルの検索設定を使用する。

**全5ステップは毎サイクル必ず実行すること。** API エラー時のみ該当ステップをスキップしてよいが、
時間制約やコンテキスト節約を理由にステップを省略してはならない。
特に Reddit（2-5）は英語圏の生の体験談・議論を収集する唯一のソースであり、
Story 不足の改善に直結するため省略禁止。

### フォールバック戦略（3段階）

各検索ステップは以下の優先順でフォールバックする:

| 機能 | Tier 1（優先） | Tier 2（フォールバック） | Tier 3（最終手段） |
|------|---------------|----------------------|-------------------|
| Web検索 | `mcp__tavily__tavily_search` | `WebSearch` | — |
| コンテンツ抽出 | `mcp__tavily__tavily_extract` | `WebFetch` | browser-use CLI `open` + `extract` |
| JS レンダリングサイト | `mcp__tavily__tavily_extract` | browser-use CLI | — |

**フォールバック判定**: Tavily が `exceeds your plan's set usage limit` エラーを返した場合、
そのサイクル以降は **Tier 2 以降のみ** を使用する（`tavily_available = false` をセット）。

#### browser-use CLI が特に有効なケース

- **note.com**: JS レンダリングのため WebFetch では本文取得不可 → browser-use CLI 必須
- **ameblo.jp**: 動的ロードコンテンツ → browser-use CLI 推奨
- **SPA サイト全般**: React/Next.js/Nuxt.js 系サイト

### 2-1. Web検索: 英語クエリ（max 3件）【必須】

**Tier 1**: `mcp__tavily__tavily_search` で英語クエリを実行。
**Tier 2**: `WebSearch` で同等のクエリを実行。

`{topic}` は Q3 の低カバレッジトピックから選択、`{year}` は現在年。

### 2-2. Web検索: 日本語クエリ（max 3件）【必須】

**Tier 1**: `mcp__tavily__tavily_search` で日本語クエリを実行。
**Tier 2**: `WebSearch` で同等のクエリを実行。

### 2-3. コンテンツ抽出: 日本語サイト【必須】

ジャンル設定の `webfetch_sites` および検索結果の URL から本文を取得する。

**Tier 1**: `mcp__tavily__tavily_extract` で詳細取得。
**Tier 2**: `WebFetch` で本文取得を試みる。
**Tier 3**: WebFetch 失敗（JS レンダリングサイト）→ browser-use CLI でコンテンツ抽出。

#### browser-use CLI によるコンテンツ抽出手順

```bash
# 1. ページを開く
source ~/.browser-use-env/bin/activate && browser-use open "{url}"

# 2. コンテンツを抽出（自然言語クエリ）
source ~/.browser-use-env/bin/activate && browser-use extract "この記事の本文テキストを全て抽出してください"

# 3. タイトル取得
source ~/.browser-use-env/bin/activate && browser-use get title
```

**重要**: browser-use CLI は1ページずつ逐次処理のため、1サイクルあたり **最大3 URL** に制限する。
取得対象は検索結果の上位から優先度順に選択:
1. note.com の記事ページ（体験談・ノウハウ系）
2. ameblo.jp のブログ記事
3. その他 JS レンダリングサイト

#### browser-use CLI セッション管理

```bash
# 名前付きセッションで管理（サイクル間でブラウザを再起動しない）
source ~/.browser-use-env/bin/activate && browser-use --session enrichment open "{url}"

# サイクル終了時にセッションを閉じる（Phase 5 で実行）
source ~/.browser-use-env/bin/activate && browser-use close
```

### 2-4. コンテンツ抽出: 高品質ソース【必須】

検索結果のうち、信頼性の高いドメイン（公式サイト、統計サイト等）を詳細取得。

**Tier 1**: `mcp__tavily__tavily_extract` で詳細取得。
**Tier 2**: `WebFetch` で取得。
**Tier 3**: WebFetch 失敗時は browser-use CLI（2-3 と同じ手順）。

### 2-5. Reddit【必須・省略禁止】

`mcp__reddit__get_subreddit_hot_posts` または `mcp__reddit__get_subreddit_new_posts` でジャンル設定の subreddit から投稿を取得。
有望な投稿は `mcp__reddit__get_post_content` で詳細取得。

Reddit は Story（体験談・事例）の主要ソースであり、毎サイクル最低1つの subreddit から投稿を取得すること。

> Reddit MCP はフォールバック不要（Tavily リミットの影響を受けない）。

### 検索結果の集約

全検索結果を以下の形式に正規化:

```json
{
  "raw_items": [
    {
      "source_url": "https://...",
      "title": "...",
      "content": "...",
      "source_type": "tavily_search | tavily_extract | websearch | webfetch | browser_use | reddit",
      "language": "en | ja",
      "fetched_at": "ISO8601"
    }
  ]
}
```

---

## Phase 3: Data Transform（分類・Entity/Concept抽出）

`references/entity-extraction-prompt-v2.md` のプロンプトテンプレートを使用する。

> **v2 変更点**: Entity（固有名詞4タイプ）と Concept（14 ConceptCategory）を分離抽出。SERVES_AS・concept_relations も抽出。

### 3-1. コンテンツ分類

各 raw_item を以下の3タイプに分類:

| タイプ | シグナル |
|--------|---------|
| **Fact** | 統計データ、調査結果、公式発表、数値を含む客観的情報 |
| **Tip** | ハウツー、ベストプラクティス、手順、推奨事項 |
| **Story** | 体験談、事例紹介、インタビュー、ケーススタディ |

### 3-2. Entity 抽出（固有名詞のみ）

各コンテンツから 0-5 個の Entity（固有名詞）を抽出。

| entity_type | 説明 | 例 |
|-------------|------|-----|
| `platform` | サービス・プラットフォーム・ツール | Instagram, Coconala, ChatGPT |
| `company` | 企業・組織 | Google, Match Group |
| `person` | 実在の人物 | 林知佳 |
| `organization` | 公的機関・団体 | 厚生労働省 |

正規化ルール: platform/company は公式英語表記を使用（A-4 準拠）。

### 3-3. Concept 抽出（ドメイン概念）

各コンテンツから 1-5 個の Concept を抽出し、14 ConceptCategory に分類。

#### What層（9種）
MonetizationMethod, AcquisitionChannel, Skill, Audience, RevenueModel, SuccessMetric, ContentFormat, Regulation, Milestone

#### How層（5種）
PersuasionTechnique, EmotionalHook, CopyFramework, Objection, Transformation

> **重点**: How層（特に EmotionalHook, CopyFramework, Objection）は現在ほぼ空のため、積極的に抽出すること。

### 3-4. SERVES_AS・concept_relations 検出

- SERVES_AS: Entity → Concept の役割関係（例: Instagram → SNS集客）
- concept_relations: Concept 間の ENABLES / REQUIRES / COMPETES_WITH

### 3-4. JSON 生成

`emit_creator_queue.py` の入力仕様に合わせた JSON を生成する。

> **重要**: `contents[]` 配列形式は不可。`sources[]`, `facts[]`, `tips[]`, `stories[]` の個別配列で入力すること。

```json
{
  "genre": "career",
  "cycle_id": "cycle-{YYYYMMDD-HHmmss}",
  "sources": [
    {
      "url": "https://...",
      "title": "...",
      "source_type": "web | reddit | blog | report",
      "authority_level": "official | media | blog | social",
      "collected_at": "ISO8601"
    }
  ],
  "facts": [
    {
      "text": "要約テキスト（200-500字）",
      "category": "statistics | market_data | research | trend",
      "confidence": "high | medium | low",
      "about_topics": ["トピック名"],
      "source_url": "https://...",
      "about_entities": [
        {"name": "...", "entity_type": "..."}
      ]
    }
  ],
  "tips": [
    {
      "text": "要約テキスト（200-500字）",
      "category": "strategy | tool | process | mindset",
      "difficulty": "beginner | intermediate | advanced",
      "about_topics": ["トピック名"],
      "source_url": "https://...",
      "about_entities": [
        {"name": "...", "entity_type": "..."}
      ]
    }
  ],
  "stories": [
    {
      "text": "要約テキスト（200-500字）",
      "outcome": "success | failure | mixed | ongoing",
      "timeline": "時系列の概要",
      "about_topics": ["トピック名"],
      "source_url": "https://...",
      "about_entities": [
        {"name": "...", "entity_type": "..."}
      ]
    }
  ],
  "entity_relations": [
    {
      "from_entity": "名前::entity_type",
      "to_entity": "名前::entity_type",
      "rel_detail": "ENABLES | USES | COMPETES_WITH | PART_OF | MEASURES | PRODUCES"
    }
  ]
}
```

出力先: `.tmp/creator-cycle-{YYYYMMDD-HHmmss}.json`

---

## Phase 4: Pipeline（パイプライン投入）

> **警告**: `/save-to-research-graph` は research-neo4j 専用です。creator-neo4j には `/save-to-creator-graph` を使用してください。

### 4-0. Entity リンキング（Phase 3.5）

抽出結果を既存ノードと照合し、重複作成を防ぐ。

```bash
# .env から NEO4J_CREATOR_PASSWORD を読み込んで実行
export $(grep -E '^NEO4J_CREATOR_PASSWORD=' .env | xargs) && \
uv run --extra embedding python scripts/entity_linker.py --input .tmp/creator-cycle-{cycle_id}.json
```

出力: `.tmp/creator-cycle-{cycle_id}.resolved.json`

3層マッチング: 完全一致 → Alias Full-Text + APOC → Embedding（`--no-embedding` でスキップ可）。

> **注意**: `NEO4J_CREATOR_PASSWORD` が `.env` に設定されていない場合は Entity Linking をスキップし、
> 未 resolved の JSON をそのまま Phase 4-1 に渡す。スキップ時はセッションログに記録すること。

### 4-1. graph-queue JSON 生成

```bash
uv run python scripts/emit_creator_queue_v2.py --input .tmp/creator-cycle-{cycle_id}.resolved.json
```

出力: `.tmp/creator-graph-queue/cq-{timestamp}-{rand8}.json` (schema_version: "creator-2.0")

### 4-2. グラフ投入

`/save-to-creator-graph` スキルを呼び出して投入する。

```
/save-to-creator-graph .tmp/creator-graph-queue-{cycle_id}.json
```

内部で `mcp__neo4j-creator__creator-write_neo4j_cypher` を使用してノード・リレーションを書き込む。

### 4-3. 投入検証

投入後、`mcp__neo4j-creator__creator-read_neo4j_cypher` で件数を確認:

```cypher
MATCH (n)
WHERE n.cycle_id = $cycle_id
RETURN labels(n)[0] AS label, count(n) AS count
```

`--dry-run` 指定時は Phase 4 をスキップし、生成された JSON のサマリーのみ出力する。

---

## Phase 4.5: Cross-Entity RELATES_TO Enrichment（横断リレーション強化）

サイクル内で検出される RELATES_TO はそのサイクルの検索結果内に限定される。
Phase 4.5 では、**既存 Entity 全体**を対象に共起分析 + LLM 推論で横断リレーションを追加する。

> **実行条件**: 3サイクルに1回実行する（毎サイクル実行するとコスト過大）。
> `--dry-run` 指定時はスキップ。

### 4.5-1. 共起候補の検出（方法B）

同じ Content（Fact/Tip/Story）から MENTIONS されている Entity ペアのうち、
まだ RELATES_TO で接続されていないものを共起回数順に取得する。

```cypher
MATCH (e1:Entity)<-[:MENTIONS]-(c)-[:MENTIONS]->(e2:Entity)
WHERE e1.entity_key < e2.entity_key
  AND NOT (e1)-[:RELATES_TO]-(e2)
WITH e1, e2, count(DISTINCT c) AS co_occurrence
WHERE co_occurrence >= 2
RETURN e1.name AS from_name, e1.entity_type AS from_type, e1.entity_id AS from_id,
       e2.name AS to_name, e2.entity_type AS to_type, e2.entity_id AS to_id,
       co_occurrence
ORDER BY co_occurrence DESC
LIMIT 15
```

### 4.5-2. 同一タイプ未接続ペアの検出

同じ entity_type で RELATES_TO 未接続のペアを追加候補として取得する。

```cypher
MATCH (e1:Entity), (e2:Entity)
WHERE e1.entity_type = e2.entity_type
  AND e1.entity_type IN ['platform', 'technique', 'service']
  AND e1.entity_key < e2.entity_key
  AND NOT (e1)-[:RELATES_TO]-(e2)
WITH e1, e2
// コンテキスト取得: 各 Entity に MENTIONS している Content のテキストを1件取得
OPTIONAL MATCH (c1)-[:MENTIONS]->(e1) WHERE c1:Fact OR c1:Tip OR c1:Story
OPTIONAL MATCH (c2)-[:MENTIONS]->(e2) WHERE c2:Fact OR c2:Tip OR c2:Story
RETURN e1.name AS from_name, e1.entity_type AS from_type, e1.entity_id AS from_id,
       e2.name AS to_name, e2.entity_type AS to_type, e2.entity_id AS to_id,
       head(collect(DISTINCT c1.text)[..1]) AS from_context,
       head(collect(DISTINCT c2.text)[..1]) AS to_context
LIMIT 10
```

### 4.5-3. LLM 推論（方法A）

4.5-1 と 4.5-2 の候補ペア（最大25件）を以下のプロンプトで分析する:

```
以下の Entity ペアについて、意味的な関係があるか判定してください。
関係がある場合のみ、rel_detail を選択してください。

許可される rel_detail:
- ENABLES: AがBを可能にする
- USES: AがBを使用する
- COMPETES_WITH: AとBが競合する
- PART_OF: AがBの一部である
- MEASURES: AがBを測定する
- PRODUCES: AがBを生み出す
- RELATED: 上記に該当しないが関連がある

判定基準:
- 明確な関係がない場合は "SKIP" とする
- 無理にリレーションを作らない
- from_context / to_context を参考に文脈上の関係を判断する

出力形式（JSON配列）:
[
  {"from_id": "...", "to_id": "...", "rel_detail": "COMPETES_WITH"},
  {"from_id": "...", "to_id": "...", "rel_detail": "SKIP"}
]
```

### 4.5-4. バッチ MERGE

LLM が判定した RELATES_TO（SKIP 以外）を `mcp__neo4j-creator__creator-write_neo4j_cypher` で投入する。

```cypher
UNWIND $rels AS row
MATCH (e1:Entity {entity_id: row.from_id})
MATCH (e2:Entity {entity_id: row.to_id})
MERGE (e1)-[r:RELATES_TO]->(e2)
SET r.rel_detail = row.rel_detail,
    r.source = 'cross-entity-enrichment',
    r.created_at = datetime()
```

`r.source = 'cross-entity-enrichment'` を付与し、Phase 3 由来と区別する。

### 4.5-5. 結果記録

セッションログに追記する:

```markdown
#### Phase 4.5 Cross-Entity RELATES_TO
- candidates_detected: {共起候補 + 同一タイプ候補の合計}
- llm_judged: {LLM に渡した件数}
- new_relates_to: {SKIP 以外で追加した件数}
- skipped: {SKIP と判定された件数}
```

---

## Phase 5: Cycle Report + Time Check

### 5-1. サイクルレポート

セッションログに以下を追記:

```markdown
### Cycle {N} - {genre_name_ja}
- time: {HH:MM:SS}
- genre: {genre} ({name_ja})
- search_results: {raw_items count}
- contents_created: {Fact: N, Tip: N, Story: N}
- entities_extracted: {count}
- relations_detected: {count}
- pipeline_status: {success | dry-run | error}
- cross_entity: {candidates: N, added: N, skipped: N} (Phase 4.5 実行時のみ)
```

### 5-2. 時刻チェック（厳密ルール）

`mcp__time__get_current_time` で現在時刻を取得。

**停止判定の厳密ルール:**

```
MAINTENANCE_BUFFER = 5分（Phase 6 所要時間の上限）
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
- Phase 6 の所要時間を5分超と見積もってはならない（embedding 更新は2-3分、修復クエリは1分で完了する）

**例:** `--until 20:50` の場合、`stop_time = 20:45`。20:44 まではサイクルを継続し、20:45 に Phase 6 を開始する。

### 5-3. 空サイクル制御

検索結果が 0 件のサイクルが連続した場合:

- `max_consecutive_empty_cycles`（デフォルト 3）回連続 → 終了
- 空サイクル間は `empty_cycle_wait_seconds`（デフォルト 60秒）待機

---

## Phase 6: Post-Session Maintenance（セッション終了時メンテナンス）

`--until` 到達でサイクルループ終了後、**1回だけ**以下のメンテナンスを実行する。
全サイクルの投入完了後にまとめて実行することで、サイクル間の整合性も含めてチェックできる。

### 6-1. Embedding 更新

新規投入された Entity/Concept に embedding を付与する:

```bash
uv run --extra embedding python scripts/creator_embed_nodes.py
```

差分のみ処理（`WHERE embedding IS NULL`）するため、既存ノードは再計算しない。

### 6-2. 自動修復（Repair Queries）

以下の修復を順に実行する。全て `mcp__neo4j-creator__creator-write_neo4j_cypher` で実行。

**(a) genre プロパティ補完**: IN_GENRE リレーションから genre=null を補完

```cypher
MATCH (c)-[:IN_GENRE]->(g:Genre)
WHERE (c:Fact OR c:Tip OR c:Story) AND c.genre IS NULL
SET c.genre = g.genre_id
RETURN count(*) AS genre_fixed
```

**(b) ABOUT retroactive リンキング**: 未接続 Concept とコンテンツのテキストマッチ

```cypher
MATCH (concept:Concept)
WHERE NOT (concept)<-[:ABOUT]-()
AND concept.name IS NOT NULL AND size(concept.name) >= 4
WITH concept
MATCH (c)
WHERE (c:Fact OR c:Tip OR c:Story)
AND (c.text CONTAINS concept.name OR c.content CONTAINS concept.name)
MERGE (c)-[:ABOUT]->(concept)
RETURN count(*) AS about_created
```

**(c) 重複 Entity 検出（レポートのみ、自動マージしない）**:

```cypher
MATCH (e1:Entity), (e2:Entity)
WHERE e1.embedding IS NOT NULL AND e2.embedding IS NOT NULL
AND elementId(e1) < elementId(e2)
CALL db.index.vector.queryNodes('entity_embedding_idx', 1, e1.embedding)
YIELD node AS similar, score
WHERE similar = e2 AND score >= 0.95
RETURN e1.name AS name1, e2.name AS name2, round(score, 4) AS similarity
```

重複が検出された場合はセッションログに記録し、ユーザーに報告する（自動マージはしない）。

### 6-3. 簡易品質スコア

メンテナンス結果を簡易スコアとしてセッションログに記録:

```markdown
### Post-Session Maintenance
- embedding_updated: {Entity: N, Concept: N}
- genre_fixed: N
- about_created: N
- duplicate_candidates: N pairs (manual review needed)
```

詳細な品質チェックが必要な場合は `/creator-quality-check` を別途実行すること。

---

## エラーハンドリング

| エラー | 対応 |
|--------|------|
| Neo4j 接続失敗 | Phase 0 で即座に終了。エラーメッセージを出力 |
| Tavily API リミット超過 | `tavily_available = false` をセットし、以降 WebSearch + browser-use CLI にフォールバック |
| Tavily API その他エラー | 該当クエリをスキップし、他の検索ソースで続行 |
| WebFetch タイムアウト | browser-use CLI にフォールバック（JS サイト）。CLI も失敗時はスキップ |
| browser-use CLI venv 未存在 | `browser_use_available = false`。WebFetch のみで続行 |
| browser-use CLI タイムアウト | 該当 URL をスキップ。セッションログに記録。30秒タイムアウト推奨 |
| browser-use セッション異常 | `browser-use close --all` で全セッションリセット後、再試行 |
| Reddit API エラー | Reddit 検索をスキップし、他の検索ソースで続行 |
| emit_creator_queue.py 失敗 | セッションログにエラーを記録し、次サイクルへ |
| /save-to-creator-graph 失敗 | セッションログにエラーを記録し、次サイクルへ。JSON は保持 |
| Phase 4.5 共起クエリ失敗 | Phase 4.5 をスキップし、次サイクルへ。セッションログに記録 |
| Phase 4.5 LLM推論エラー | Phase 4.5 をスキップし、次サイクルへ。候補リストは保持 |
| --until 時刻パース失敗 | エラーメッセージを出力して終了 |

---

## MUST / NEVER

### MUST

- Phase 2 の全5ステップ（Web検索英語・Web検索日本語・コンテンツ抽出日本語・コンテンツ抽出高品質・Reddit）を毎サイクル実行すること。API エラー時のみスキップ可
- Tavily API リミット超過時は `tavily_available = false` をセットし、WebSearch + browser-use CLI に即座にフォールバックすること
- note.com 等の JS レンダリングサイトで WebFetch が失敗した場合、`browser_use_available = true` なら browser-use CLI にフォールバックすること
- browser-use CLI 使用時は1サイクルあたり最大3 URL に制限し、30秒タイムアウトを設定すること
- Reddit（Step 2-5）は毎サイクル最低1つの subreddit から投稿を取得すること。Reddit は英語圏の生の体験談・議論の唯一のソースであり、Story 不足改善に直結する
- Phase 3 で Story 優先判定ルール（entity-extraction-prompt-v2.md）を適用し、体験談系コンテンツを Tip ではなく Story に分類すること
- Phase 4 で /save-to-creator-graph を使用し、graph-queue JSON 経由で投入すること。Cypher 直書き禁止
- セッションログに各ステップの実行結果（取得件数・スキップ理由・使用した Tier）を記録すること

### NEVER

- 時間制約やコンテキスト節約を理由に Phase 2 のステップを省略してはならない
- Reddit 検索を「WebSearch で十分な結果が得られたから」という理由で省略してはならない
- browser-use CLI を Tavily が利用可能な間に使用してはならない（フォールバック専用）
- `mcp__neo4j-creator__creator-write_neo4j_cypher` で直接ノード・リレーションを作成してはならない（スキーマ操作を除く）
- `--until - 5分` より前にサイクルループを終了してはならない。「十分なデータが集まった」「コンテキストが大きくなった」は停止理由にならない
- Phase 6（Post-Session Maintenance）を `--until - 5分` より前に実行してはならない。途中のembedding更新は不要（Phase 6 で一括実行する）

---

## セッションログ形式

ファイル: `.tmp/creator-enrichment-{YYYYMMDD-HHmmss}.log.md`

```markdown
# Creator Enrichment Session
- start: 2026-03-22T14:00:00+09:00
- until: 23:30
- genre_filter: auto

## Cycles

### Cycle 1 - 転職・副業
- time: 14:02:35
- genre: career (転職・副業)
- search_results: 12
- contents_created: {Fact: 3, Tip: 5, Story: 2}
- entities_extracted: 18
- relations_detected: 7
- pipeline_status: success

### Cycle 2 - 美容・恋愛
- time: 14:08:12
- genre: beauty-romance (美容・恋愛)
- search_results: 9
- contents_created: {Fact: 2, Tip: 4, Story: 1}
- entities_extracted: 14
- relations_detected: 5
- pipeline_status: success

## Summary
- total_cycles: 2
- total_contents: 17
- total_entities: 32
- total_relations: 12
- errors: 0
- end_reason: time_limit_reached
```

---

## 関連ファイル

| ファイル | 説明 |
|---------|------|
| `data/config/creator-enrichment-config.json` | ジャンル・検索設定 |
| `references/gap-analysis-queries.md` | ギャップ分析クエリ集 |
| `references/genre-config.md` | ジャンル別検索戦略リファレンス |
| `references/entity-extraction-prompt.md` | 分類・Entity抽出プロンプト |
| `.claude/commands/creator-enrichment.md` | スラッシュコマンド定義 |
| `scripts/emit_creator_queue.py` | graph-queue JSON 生成スクリプト |
