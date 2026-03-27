---
name: creator-research
description: |
  特定のトピック・ジャンルについてマルチソースで深掘りリサーチし、creator-neo4j に情報を投入するスキル。
  creator-neo4j から既存データを照会してギャップを特定した上で、
  Tavily・WebSearch・WebFetch・Reddit を組み合わせたコンテンツ収集と
  Fact/Tip/Story/Entity/Concept 抽出を行い、creator-graph-queue パイプラインで永続化する。
  Use PROACTIVELY when 副業・転職・美容・恋愛・占いテーマの深掘りリサーチが必要な場合。
allowed-tools: Read, Write, Bash, Glob, Grep, ToolSearch
---

# creator-research スキル

特定のクリエイタードメイントピック（副業・転職・美容・恋愛・占い）をマルチソースで深掘りし、
creator-neo4j（bolt://localhost:7689）にデータを投入するスキル。

> **パイプライン**: 収集データ → `emit_creator_queue_v2.py` → `.tmp/creator-graph-queue/` → `/save-to-creator-graph`
> **スキーマバージョン**: creator-2.0（Fact/Tip/Story + Entity 4種 + Concept 14カテゴリ）

---

## パラメータ

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| `--topic` | 必須 | - | リサーチトピック（例: "副業ブログ収益化", "マッチングアプリ攻略", "タロット副業"） |
| `--genre` | 推奨 | auto | 対象ジャンル（`career` / `beauty-romance` / `spiritual`）。省略時は自動判定 |
| `--depth` | - | standard | 調査深度。`quick`: 5-8検索, `standard`: 12-18検索, `deep`: 20-30検索 |
| `--dry-run` | - | false | 検索・抽出のみ実行し、パイプライン投入をスキップ |
| `--skip-kg` | - | false | creator-neo4j 照会・投入をスキップ（未起動時） |

---

## 処理フロー

```
Phase 0: creator-neo4j 既存データ照会 + ギャップ分析
Phase 1: マルチソース検索（ギャップ優先）
Phase 2: Fact/Tip/Story/Entity/Concept 抽出
Phase 3: サイクル入力 JSON 構築
Phase 4: パイプライン投入（emit_creator_queue_v2.py → /save-to-creator-graph）
Phase 5: 結果レポート
```

---

## Phase 0: creator-neo4j 既存データ照会 + ギャップ分析

`--skip-kg` 指定時はスキップし、全クエリを新規として扱う。

### 0-1. MCP ツール取得

```
ToolSearch("select:mcp__neo4j-creator__creator-read_neo4j_cypher,mcp__neo4j-creator__creator-get_neo4j_schema")
ToolSearch("select:mcp__tavily__tavily_search,mcp__tavily__tavily_extract")
ToolSearch("select:mcp__reddit__get_subreddit_hot_posts,mcp__reddit__get_post_content")
ToolSearch("select:WebFetch,WebSearch,mcp__time__get_current_time")
```

### 0-2. 接続確認

```cypher
// mcp__neo4j-creator__creator-read_neo4j_cypher
RETURN 1 AS ok
```

失敗時は警告を出力し `--skip-kg` 相当の動作に切り替える。

### 0-3. ジャンル自動判定（`--genre` 省略時）

トピック文字列からジャンルを推定する:

| キーワード | genre |
|-----------|-------|
| 副業・転職・フリーランス・収入・面接・キャリア | `career` |
| 美容・スキンケア・恋愛・婚活・マッチングアプリ | `beauty-romance` |
| 占い・タロット・スピリチュアル・開運 | `spiritual` |

該当しない場合は `career` をデフォルトとし、ユーザーに通知する。

### 0-4. 既存データ照会

以下の Cypher クエリを `mcp__neo4j-creator__creator-read_neo4j_cypher` で実行する。

**Q1: トピック関連の既存コンテンツ数**

```cypher
MATCH (n)
WHERE (n:Fact OR n:Tip OR n:Story)
  AND n.text CONTAINS $keyword
RETURN labels(n)[0] AS content_type, count(n) AS cnt
ORDER BY cnt DESC
```

`$keyword` はトピックから抽出したキーワード（例: "副業ブログ" → "副業", "ブログ"）。

**Q2: 関連 Concept のカバレッジ**

```cypher
MATCH (c:Concept)
WHERE c.name CONTAINS $keyword
WITH c
OPTIONAL MATCH (content)-[:ABOUT]->(c)
RETURN c.name AS concept, count(content) AS content_count
ORDER BY content_count ASC
LIMIT 10
```

**Q3: 関連 Entity の既存状況**

```cypher
MATCH (e:Entity)
WHERE e.name CONTAINS $keyword
RETURN e.name AS entity, e.entity_type AS type, count { ()-[:MENTIONS]->(e) } AS mention_count
ORDER BY mention_count ASC
LIMIT 10
```

**Q4: 直近 7 日間の重複排除リスト**

```cypher
MATCH (n)
WHERE (n:Fact OR n:Tip OR n:Story) AND n.created_at >= datetime() - duration('P7D')
MATCH (n)-[:FROM_SOURCE]->(s:Source)
RETURN s.url AS source_url, n.text[..80] AS excerpt
ORDER BY n.created_at DESC
LIMIT 50
```

### 0-5. ギャップ判定

照会結果から以下のギャップを特定する:

| ギャップ種別 | 判定条件 | 検索優先度 |
|------------|---------|-----------|
| `no_coverage` | Q1 の cnt = 0 | HIGH |
| `concept_gap` | Q2 で content_count < 2 の Concept が 3 件以上 | HIGH |
| `story_deficit` | Story 比率 < 20% | MEDIUM |
| `tip_deficit` | Tip 比率 < 30% | MEDIUM |
| `entity_gap` | Q3 で mention_count = 0 の Entity が 3 件以上 | MEDIUM |
| `stale_data` | Q1 の最新データが 30 日以上前 | MEDIUM |

ギャップレポートを `.tmp/creator-research-{slug}_{timestamp}.gap.md` に出力する。

---

## Phase 1: マルチソース検索（ギャップ優先）

参照: `references/search-strategy.md`（ジャンル別クエリテンプレート）

### 検索予算配分

```
depth: quick    → 合計  5-8 検索
depth: standard → 合計 12-18 検索
depth: deep     → 合計 20-30 検索

ギャップ解消クエリ: 予算の 60%
通常リサーチクエリ: 予算の 40%
```

### フォールバック戦略（3段階）

| 機能 | Tier 1 | Tier 2 | Tier 3 |
|------|--------|--------|--------|
| Web検索 | `mcp__tavily__tavily_search` | `WebSearch` | — |
| コンテンツ抽出 | `mcp__tavily__tavily_extract` | `WebFetch` | — |

Tavily が `exceeds your plan's set usage limit` を返したら `tavily_available = false` をセットし、
以降は Tier 2 のみ使用する。

### 1-1. Web検索: 英語クエリ【必須】

`references/search-strategy.md` のジャンル別英語テンプレートを使用。
`{topic}` をパラメータ値で置換、`{year}` を現在年で置換。

- **quick**: 英語クエリ 2件
- **standard**: 英語クエリ 4-5件
- **deep**: 英語クエリ 7-8件

### 1-2. Web検索: 日本語クエリ【必須】

`references/search-strategy.md` のジャンル別日本語テンプレートを使用。

- **quick**: 日本語クエリ 2件
- **standard**: 日本語クエリ 4-5件
- **deep**: 日本語クエリ 7-8件

### 1-3. コンテンツ抽出: 日本語サイト【必須】

検索結果の URL から本文を取得する。

**Tier 1**: `mcp__tavily__tavily_extract`
**Tier 2**: `WebFetch`

- **quick**: 2 URL
- **standard**: 4-5 URL
- **deep**: 8-10 URL

note.com は JavaScript レンダリングのため WebFetch 失敗時はスキップ（browser-use CLI は任意）。

### 1-4. Reddit【必須・省略禁止】

`references/search-strategy.md` のジャンル別 subreddit から投稿を取得。

```
mcp__reddit__get_subreddit_hot_posts または mcp__reddit__get_subreddit_new_posts
→ 有望な投稿は mcp__reddit__get_post_content で詳細取得
```

Reddit は Story（体験談）の主要ソース。最低 1 subreddit から投稿を取得すること。

### 検索結果の集約

全検索結果を以下の形式に正規化して `raw_items` リストに追加する:

```json
{
  "source_url": "https://...",
  "title": "...",
  "content": "...",
  "source_type": "tavily_search | tavily_extract | websearch | webfetch | reddit",
  "language": "en | ja",
  "fetched_at": "ISO8601"
}
```

**重複排除**: Q4 の `source_url` リストと照合し、既存 URL はスキップする。

---

## Phase 2: Fact/Tip/Story/Entity/Concept 抽出

参照: `.claude/skills/creator-enrichment/references/entity-extraction-prompt-v2.md`（プロンプトテンプレート）

各 `raw_item` に対してプロンプトを適用し、以下を抽出する:

| 抽出対象 | 説明 |
|---------|------|
| content_type | Fact / Tip / Story のいずれか |
| body | 要約テキスト（200-500字、英語コンテンツは日本語訳） |
| entities | 固有名詞 4タイプ（platform/company/person/organization） |
| concepts | ドメイン概念 14カテゴリ（MonetizationMethod, Skill, EmotionalHook 等） |
| serves_as | Entity → Concept の役割関係 |
| concept_relations | Concept 間の ENABLES/REQUIRES/COMPETES_WITH |

### Story 優先判定ルール

以下のいずれかを含む場合は **Tip ではなく Story** に分類する:
- 「〜してみた」「〜した結果」「〜ヶ月目の報告」
- 具体的な金額・期間の before/after（「月収3万円→月収30万円」等）
- 失敗談・反省点の記述
- 一人称視点での時系列ストーリー
- 英語: `my experience`, `how I started`, `first year results`

### ギャップ解消の確認

Phase 0 で特定されたギャップが解消されたかを記録する:
- `no_coverage`: 関連コンテンツが 1 件以上抽出されたか
- `concept_gap`: 不足していた Concept がカバーされたか
- `story_deficit`: Story が追加されたか

---

## Phase 3: サイクル入力 JSON 構築

Phase 2 の抽出結果を `emit_creator_queue_v2.py` の入力形式にまとめる。

出力先: `.tmp/creator-research-{slug}_{timestamp}.input.json`

```json
{
  "genre": "{determined_genre}",
  "cycle_id": "creator-research-{slug}-{YYYYMMDD-HHmmss}",
  "sources": [
    {
      "url": "https://...",
      "title": "...",
      "source_type": "web | reddit | blog | report",
      "authority_level": "official | media | blog | social",
      "language": "ja | en",
      "domain": "example.com",
      "collected_at": "ISO8601"
    }
  ],
  "facts": [
    {
      "text": "要約テキスト（200-500字）",
      "category": "statistics | market_data | research | trend",
      "confidence": "high | medium | low",
      "about_concepts": ["Concept名"],
      "source_url": "https://...",
      "about_entities": [{"name": "...", "entity_type": "platform|company|person|organization"}]
    }
  ],
  "tips": [
    {
      "text": "要約テキスト",
      "category": "strategy | tool | process | mindset",
      "difficulty": "beginner | intermediate | advanced",
      "about_concepts": ["Concept名"],
      "source_url": "https://...",
      "about_entities": [{"name": "...", "entity_type": "..."}]
    }
  ],
  "stories": [
    {
      "text": "要約テキスト",
      "outcome": "success | failure | mixed | ongoing",
      "timeline": "時系列の概要",
      "about_concepts": ["Concept名"],
      "source_url": "https://...",
      "about_entities": [{"name": "...", "entity_type": "..."}]
    }
  ],
  "concepts": [
    {
      "name": "Concept名",
      "category": "ConceptCategory名（14種のいずれか）",
      "new_category": false
    }
  ],
  "serves_as": [
    {
      "entity_name": "Entity名",
      "concept_name": "Concept名",
      "context": "役割の説明"
    }
  ],
  "concept_relations": [
    {
      "from_concept": "Concept名",
      "to_concept": "Concept名",
      "rel_type": "ENABLES | REQUIRES | COMPETES_WITH"
    }
  ]
}
```

**必須チェック**:
- 全 sources に `url`, `source_type`, `authority_level` が設定されているか
- 全コンテンツの `source_url` が `sources` 内の URL と一致するか
- `facts/tips/stories` が空でないか（少なくとも 1 件以上）

---

## Phase 4: パイプライン投入

`--dry-run` 指定時はこの Phase をスキップし、Phase 3 の JSON サマリーのみ出力する。

### 4-1. Entity リンキング（任意）

既存ノードとの重複作成を防ぐ（`NEO4J_CREATOR_PASSWORD` が `.env` に存在する場合のみ実行）:

```bash
export $(grep -E '^NEO4J_CREATOR_PASSWORD=' .env | xargs) && \
uv run --extra embedding python scripts/entity_linker.py \
  --input .tmp/creator-research-{slug}_{timestamp}.input.json
```

成功時: `.tmp/creator-research-{slug}_{timestamp}.input.resolved.json` を使用
失敗時: 元の input.json をそのまま使用（ログに記録）

### 4-2. graph-queue JSON 生成

```bash
uv run python scripts/emit_creator_queue_v2.py \
  --input .tmp/creator-research-{slug}_{timestamp}.input.resolved.json
```

出力: `.tmp/creator-graph-queue/cq-{timestamp}-{rand8}.json` (schema_version: "creator-2.0")

### 4-3. creator-neo4j 投入

`/save-to-creator-graph` スキルを呼び出して graph-queue JSON を投入する:

```
/save-to-creator-graph .tmp/creator-graph-queue/cq-{timestamp}-{rand8}.json
```

内部で `mcp__neo4j-creator__creator-write_neo4j_cypher` を使用。

### 4-4. 投入検証

投入後、`mcp__neo4j-creator__creator-read_neo4j_cypher` で件数を確認:

```cypher
MATCH (n)
WHERE n.created_at >= datetime($session_start)
RETURN labels(n)[0] AS label, count(n) AS cnt
ORDER BY cnt DESC
```

---

## Phase 5: 結果レポート

リサーチノートを `.tmp/creator-research-{slug}_{timestamp}.md` に出力する。

```markdown
# Creator Research: {topic}

- genre: {genre}
- depth: {depth}
- session: {timestamp}

## ギャップ分析サマリー
- 特定ギャップ: {n}件
- 解消ギャップ: {n}件
- 残存ギャップ: {n}件

## 収集サマリー
- 検索件数: {n}
- raw_items: {n}
- Fact: {n}, Tip: {n}, Story: {n}
- Entity: {n}, Concept: {n}

## 投入結果
- Source: {n}
- Fact: {n}, Tip: {n}, Story: {n}
- Entity: {n}（新規: {n}, 既存更新: {n}）
- リレーション: {n}

## 残存ギャップ（次回リサーチで推奨）
- {gap_description}
```

---

## MCP フォールバック戦略

| MCP ツール | 失敗時の対応 |
|-----------|------------|
| Neo4j MCP | Phase 0/4 をスキップ（`--skip-kg` 相当）、警告を出力 |
| Tavily MCP | `tavily_available = false`、WebSearch に切り替え |
| Reddit MCP | `site:reddit.com` クエリで WebSearch 代替 |

---

## MUST / NEVER

### MUST

- Phase 1 の Reddit 検索（1-4）は省略禁止。Story 不足の主要解消手段
- Phase 3 の全コンテンツに `source_url` を設定すること
- `--dry-run` 以外では必ず `/save-to-creator-graph` を使用すること（Cypher 直書き禁止）
- `emit_creator_queue_v2.py` を必ず通すこと（schema_version: "creator-2.0" を保証するため）

### NEVER

- `mcp__neo4j-creator__creator-write_neo4j_cypher` で直接ノード・リレーションを作成してはならない
- `/save-to-research-graph`（research-neo4j 専用）を使用してはならない
- `contents[]` 配列形式で emit_creator_queue_v2.py に渡してはならない（`sources/facts/tips/stories` 分離形式必須）

---

## 関連ファイル

| リソース | パス |
|---------|------|
| 検索戦略 | `references/search-strategy.md` |
| Entity/Concept 抽出プロンプト | `.claude/skills/creator-enrichment/references/entity-extraction-prompt-v2.md` |
| ジャンル設定 | `.claude/skills/creator-enrichment/references/genre-config.md` |
| save-to-creator-graph | `.claude/skills/save-to-creator-graph/SKILL.md` |
| emit_creator_queue_v2.py | `scripts/emit_creator_queue_v2.py` |
| creator-neo4j 直書き禁止 | `.claude/skills/save-to-creator-graph/SKILL.md`（WARNING 参照） |
