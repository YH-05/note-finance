---
name: creator-enrichment
description: creator-neo4j (bolt://localhost:7689) を自動拡充するスキル。ギャップ分析→Web検索(Tavily+WebFetch+Reddit)→Fact/Tip/Story分類+Entity抽出→パイプライン投入を終了時刻まで繰り返す。
allowed-tools: Read, Write, Bash, Grep, Glob
---

# creator-enrichment スキル

creator-neo4j（bolt://localhost:7689）のナレッジグラフを自動拡充する5フェーズループ。
終了時刻（`--until`）まで、ギャップ分析→検索→分類・Entity抽出→パイプライン投入を繰り返す。

> **警告**: `/save-to-graph` は research-neo4j 専用です。creator-neo4j への投入には必ず `/save-to-creator-graph` を使用してください。

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
ToolSearch: "select:WebFetch"
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

### 0-5. 現在時刻の取得

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

### 2-1. Tavily 英語クエリ（max 3件）

`mcp__tavily__tavily_search` で英語クエリを実行。`{topic}` は Q3 の低カバレッジトピックから選択、`{year}` は現在年。

### 2-2. Tavily 日本語クエリ（max 3件）

同様に日本語クエリを実行。

### 2-3. WebFetch（日本語サイト）

ジャンル設定の `webfetch_sites` から URL を取得し、`WebFetch` で本文を取得する。
Tavily 検索結果の URL のうち、日本語サイト（note.com, ameblo.jp, hatenablog.com 等）を優先的に WebFetch する。

### 2-4. Tavily Extract（高品質ソース）

Tavily 検索結果のうち、信頼性の高いドメイン（公式サイト、統計サイト等）を `mcp__tavily__tavily_extract` で詳細取得。

### 2-5. Reddit

`mcp__reddit__get_subreddit_hot_posts` または `mcp__reddit__get_subreddit_new_posts` でジャンル設定の subreddit から投稿を取得。
有望な投稿は `mcp__reddit__get_post_content` で詳細取得。

### 検索結果の集約

全検索結果を以下の形式に正規化:

```json
{
  "raw_items": [
    {
      "source_url": "https://...",
      "title": "...",
      "content": "...",
      "source_type": "tavily_search | webfetch | reddit",
      "language": "en | ja",
      "fetched_at": "ISO8601"
    }
  ]
}
```

---

## Phase 3: Data Transform（分類・Entity抽出）

`references/entity-extraction-prompt.md` のプロンプトテンプレートを使用する。

### 3-1. コンテンツ分類

各 raw_item を以下の3タイプに分類:

| タイプ | シグナル |
|--------|---------|
| **Fact** | 統計データ、調査結果、公式発表、数値を含む客観的情報 |
| **Tip** | ハウツー、ベストプラクティス、手順、推奨事項 |
| **Story** | 体験談、事例紹介、インタビュー、ケーススタディ |

### 3-2. Entity 抽出

各コンテンツから 1-5 個の Entity を抽出。

許可される `entity_type`:

| entity_type | 説明 |
|-------------|------|
| `occupation` | 職種・役職 |
| `platform` | サービス・プラットフォーム |
| `company` | 企業・組織 |
| `technique` | 手法・テクニック |
| `service` | サービス |
| `product` | 製品 |
| `metric` | 指標・数値 |
| `concept` | 概念・用語 |
| `person` | 人物 |
| `tool` | ツール |

### 3-3. Entity 間リレーション検出

Entity 間の関係を検出する:

```
from_entity::entity_type → to_entity::entity_type (rel_detail)
```

例: `Notion::platform → タスク管理::technique (ENABLES)`

### 3-4. JSON 生成

`emit_creator_queue.py` の入力仕様に合わせた JSON を生成:

```json
{
  "genre": "career",
  "cycle_id": "cycle-{YYYYMMDD-HHmmss}",
  "contents": [
    {
      "content_type": "Fact | Tip | Story",
      "title": "...",
      "body": "...",
      "source_url": "https://...",
      "source_type": "tavily_search | webfetch | reddit",
      "language": "en | ja",
      "topic": "...",
      "entities": [
        {"name": "...", "entity_type": "..."}
      ],
      "entity_relations": [
        {
          "from_entity": "...",
          "from_type": "...",
          "to_entity": "...",
          "to_type": "...",
          "rel_detail": "..."
        }
      ]
    }
  ]
}
```

出力先: `.tmp/creator-cycle-{YYYYMMDD-HHmmss}.json`

---

## Phase 4: Pipeline（パイプライン投入）

> **警告**: `/save-to-graph` は research-neo4j 専用です。creator-neo4j には `/save-to-creator-graph` を使用してください。

### 4-1. graph-queue JSON 生成

```bash
uv run python scripts/emit_creator_queue.py --input .tmp/creator-cycle-{cycle_id}.json
```

出力: `.tmp/creator-graph-queue-{cycle_id}.json`

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
```

### 5-2. 時刻チェック

`mcp__time__get_current_time` で現在時刻を取得。

- 現在時刻 < `--until` → Phase 1 に戻る
- 現在時刻 >= `--until` → 最終サマリーを出力して終了

### 5-3. 空サイクル制御

検索結果が 0 件のサイクルが連続した場合:

- `max_consecutive_empty_cycles`（デフォルト 3）回連続 → 終了
- 空サイクル間は `empty_cycle_wait_seconds`（デフォルト 60秒）待機

---

## エラーハンドリング

| エラー | 対応 |
|--------|------|
| Neo4j 接続失敗 | Phase 0 で即座に終了。エラーメッセージを出力 |
| Tavily API エラー | 該当クエリをスキップし、他の検索ソースで続行 |
| WebFetch タイムアウト | 該当 URL をスキップ。セッションログに記録 |
| Reddit API エラー | Reddit 検索をスキップし、Tavily 結果のみで続行 |
| emit_creator_queue.py 失敗 | セッションログにエラーを記録し、次サイクルへ |
| /save-to-creator-graph 失敗 | セッションログにエラーを記録し、次サイクルへ。JSON は保持 |
| --until 時刻パース失敗 | エラーメッセージを出力して終了 |

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
