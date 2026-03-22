# creator-neo4j 自動拡充スキル実装プラン

## Context

creator-neo4j（bolt://localhost:7689）は副業コンテンツ制作用のナレッジグラフで、3ジャンル（career / beauty-romance / spiritual）の Fact/Tip/Story を蓄積している。現在 ~1,670 ノードが手動投入されているが、パイプラインが未構築のため自動拡充ができない。

本プランでは以下を実装する：
1. **パイプライン基盤**（emit_creator_queue.py + /save-to-creator-graph スキル）
2. **自動拡充スキル**（/creator-enrichment）— 指定終了時刻まで Web検索 + Reddit からデータを収集・投入し続ける

### 設計判断（2026-03-22 議論）

- 書き込み方式: パイプライン構築を先行
- ジャンル制御: 3ジャンル自動ローテーション（--genre パラメータなし）
- Topic 生成: 新 Topic は自動生成する
- **検索ソース: Gemini CLI 廃止 → Tavily + WebFetch に統一**（理由: ソースURLがNeo4j投入に必須だが、Gemini CLIはURLを返さない）
- **Entity + トリプル抽出: KG v2 準拠で Entity ノードを追加**（理由: Fact/Tip/Storyをテキスト塊でなくエンティティレベルで接続し、グラフの接続性と検索性を向上）

---

## スキーマ

### 既存ノード（変更なし）

| ノード | キープロパティ | 説明 |
|--------|--------------|------|
| Genre | genre_id, name | 3固定: career, beauty-romance, spiritual |
| Topic | topic_id, name, genre_id | テーマ |
| Source | source_id, url, title, source_type, authority_level, collected_at | 情報ソース |
| Fact | fact_id, text, category, confidence | データ・統計 |
| Tip | tip_id, text, category, difficulty | ノウハウ・アドバイス |
| Story | story_id, text, outcome, timeline | 成功/失敗事例 |
| Service | service_id, name | ASP紹介サービス（16件） |
| Account | account_id | アカウント情報（3件） |

### 追加ノード

| ノード | キープロパティ | 説明 |
|--------|--------------|------|
| Entity | entity_id, name, entity_type, entity_key | KG v2準拠。entity_key = `{name}::{entity_type}` |

**entity_type 許可値**（creator ドメイン）: `person`, `company`, `platform`, `service`, `occupation`, `technique`, `metric`, `product`, `concept`

### 既存リレーション（変更なし）

| リレーション | 方向 | 説明 |
|-------------|------|------|
| ABOUT | Fact/Tip/Story → Topic | コンテンツがトピックに関連 |
| IN_GENRE | Topic → Genre | トピックのジャンル所属 |
| FROM_SOURCE | Fact/Tip/Story → Source | コンテンツの情報源 |

### 追加リレーション

| リレーション | 方向 | 説明 |
|-------------|------|------|
| MENTIONS | Fact/Tip/Story → Entity | コンテンツがエンティティに言及 |
| RELATES_TO | Entity → Entity | エンティティ間関係（rel_detail プロパティ付き） |

### 全体構造

```
Genre ← IN_GENRE ← Topic ← ABOUT ← Fact/Tip/Story → FROM_SOURCE → Source
                                          ↓
                                    MENTIONS → Entity
                                               ↕ RELATES_TO
                                            Entity
```

### 制約・インデックス

```cypher
CREATE CONSTRAINT unique_creator_entity_id IF NOT EXISTS
  FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE;
CREATE CONSTRAINT unique_creator_entity_key IF NOT EXISTS
  FOR (e:Entity) REQUIRE e.entity_key IS UNIQUE;
CREATE INDEX idx_creator_entity_type IF NOT EXISTS
  FOR (e:Entity) ON (e.entity_type);
```

---

## Step 1: emit_creator_queue.py（パイプライン前段）

**ファイル**: `scripts/emit_creator_queue.py`（~400行）

research-neo4j 用の `emit_graph_queue.py` とはスキーマが異なるため独立スクリプトとして作成。ただし Entity ID 生成は共有。

### 入力 JSON 仕様

```json
{
  "genre": "career",
  "sources": [
    {
      "url": "https://example.com/article",
      "title": "副業で月5万円を稼ぐ方法",
      "source_type": "web|reddit|blog|report",
      "authority_level": "official|media|blog|social",
      "collected_at": "2026-03-22T14:00:00+09:00"
    }
  ],
  "facts": [
    {
      "text": "フリーランスの平均年収は600万円（2026年調査）",
      "category": "statistics|market_data|research|trend",
      "confidence": "high|medium|low",
      "source_url": "https://example.com/article",
      "about_topics": ["フリーランス収入"],
      "about_entities": [
        {"name": "フリーランス", "entity_type": "occupation"},
        {"name": "日本", "entity_type": "concept"}
      ]
    }
  ],
  "tips": [
    {
      "text": "副業開始3ヶ月は収益よりスキル構築に集中する",
      "category": "strategy|tool|process|mindset",
      "difficulty": "beginner|intermediate|advanced",
      "source_url": "https://example.com/article",
      "about_topics": ["副業の始め方"],
      "about_entities": [
        {"name": "スキル構築", "entity_type": "technique"}
      ]
    }
  ],
  "stories": [
    {
      "text": "IT未経験から副業Webライターで月10万円達成した体験談",
      "outcome": "success|failure|mixed|ongoing",
      "timeline": "3ヶ月",
      "source_url": "https://example.com/article",
      "about_topics": ["副業体験談"],
      "about_entities": [
        {"name": "Webライター", "entity_type": "occupation"},
        {"name": "クラウドワークス", "entity_type": "platform"}
      ]
    }
  ],
  "entity_relations": [
    {
      "from_entity": "Webライター::occupation",
      "to_entity": "クラウドワークス::platform",
      "rel_detail": "主要な案件獲得プラットフォーム"
    }
  ]
}
```

### 出力 graph-queue JSON

```json
{
  "schema_version": "creator-1.0",
  "queue_id": "cq-{timestamp}-{hash8}",
  "created_at": "ISO8601",
  "command_source": "creator-enrichment",
  "genre_id": "career",
  "genres": [{"genre_id": "career", "name": "転職・副業"}],
  "topics": [{"topic_id": "...", "name": "...", "genre_id": "career"}],
  "sources": [{"source_id": "...", "url": "...", "title": "...", "source_type": "...", "authority_level": "...", "collected_at": "..."}],
  "entities": [
    {
      "entity_id": "UUID5-based",
      "name": "Webライター",
      "entity_type": "occupation",
      "entity_key": "Webライター::occupation"
    }
  ],
  "facts": [{"fact_id": "...", "text": "...", "category": "...", "confidence": "..."}],
  "tips": [{"tip_id": "...", "text": "...", "category": "...", "difficulty": "..."}],
  "stories": [{"story_id": "...", "text": "...", "outcome": "...", "timeline": "..."}],
  "relations": {
    "in_genre": [{"from_id": "topic_id", "to_id": "genre_id"}],
    "about_fact": [{"from_id": "fact_id", "to_id": "topic_id"}],
    "about_tip": [{"from_id": "tip_id", "to_id": "topic_id"}],
    "about_story": [{"from_id": "story_id", "to_id": "topic_id"}],
    "from_source_fact": [{"from_id": "fact_id", "to_id": "source_id"}],
    "from_source_tip": [{"from_id": "tip_id", "to_id": "source_id"}],
    "from_source_story": [{"from_id": "story_id", "to_id": "source_id"}],
    "mentions_fact": [{"from_id": "fact_id", "to_id": "entity_id"}],
    "mentions_tip": [{"from_id": "tip_id", "to_id": "entity_id"}],
    "mentions_story": [{"from_id": "story_id", "to_id": "entity_id"}],
    "relates_to": [{"from_id": "entity_id", "to_id": "entity_id", "rel_detail": "..."}]
  }
}
```

### ID 生成方式

| ID | 生成方式 | 備考 |
|----|---------|------|
| fact_id | `fact-{sha256(text)[:8]}` | コンテンツベースハッシュ |
| tip_id | `tip-{sha256(text)[:8]}` | 同上 |
| story_id | `story-{sha256(text)[:8]}` | 同上 |
| source_id | `generate_source_id(url)` | `id_generator.py` (L62) を再利用 |
| entity_id | `generate_entity_id(name, type)` | `id_generator.py` (L273) を再利用。research-neo4j と同一ID |
| topic_id | `sha256(f"topic:{slugify(name)}:{genre_id}")[:8]` | |
| queue_id | `cq-{timestamp}-{rand8}` | |

Entity ID を research-neo4j と共有することで、将来的なクロスグラフ照合を可能にする。

### 出力先

`.tmp/creator-graph-queue/cq-{timestamp}-{hash8}.json`

> **⚠️ `/save-to-graph` は research-neo4j 専用（`.tmp/graph-queue/` をスキャン）。creator の出力は `.tmp/creator-graph-queue/` に完全分離。**

### 実装の参考

- `scripts/emit_graph_queue.py` の構造（argparse, MapperFn, ID 生成ヘルパー）
- `src/pdf_pipeline/services/id_generator.py` の `generate_entity_id()`, `generate_source_id()`

---

## Step 2: /save-to-creator-graph スキル（パイプライン後段）

**ファイル**: `.claude/skills/save-to-creator-graph/SKILL.md`

creator-neo4j 専用の投入スキル。`bolt://localhost:7689` に接続し、MERGE ベースで冪等投入。

> **⚠️ `/save-to-graph`（research-neo4j 専用, bolt://localhost:7688）は使用禁止。creator-neo4j へのデータ投入には必ず `/save-to-creator-graph` を使うこと。**

### 接続情報

```
NEO4J_URI=bolt://localhost:7689
NEO4J_USER=neo4j
NEO4J_PASSWORD=gomasuke
```

### 使用 MCP ツール

```
読み取り: mcp__neo4j-creator__creator-read_neo4j_cypher
書き込み: mcp__neo4j-creator__creator-write_neo4j_cypher
スキーマ: mcp__neo4j-creator__creator-get_neo4j_schema
```

### MERGE 投入順序（依存関係順）

1. Genre（3 固定ノード、初回のみ）
2. Topic → IN_GENRE リレーション
3. Source
4. **Entity**（entity_key で MERGE）
5. Fact → ABOUT + FROM_SOURCE + **MENTIONS** リレーション
6. Tip → ABOUT + FROM_SOURCE + **MENTIONS** リレーション
7. Story → ABOUT + FROM_SOURCE + **MENTIONS** リレーション
8. **RELATES_TO**（Entity-Entity リレーション）

### MERGE Cypher パターン

```cypher
-- Genre
MERGE (g:Genre {genre_id: $genre_id})
SET g.name = $name

-- Topic + IN_GENRE
MERGE (t:Topic {topic_id: $topic_id})
SET t.name = $name, t.updated_at = datetime()
WITH t
MATCH (g:Genre {genre_id: $genre_id})
MERGE (t)-[:IN_GENRE]->(g)

-- Source
MERGE (s:Source {source_id: $source_id})
SET s.url = $url, s.title = $title,
    s.source_type = $source_type,
    s.authority_level = $authority_level,
    s.collected_at = datetime($collected_at)

-- Entity（KG v2 準拠: entity_key で MERGE）
MERGE (e:Entity {entity_key: $entity_key})
ON CREATE SET e.entity_id = $entity_id
SET e.name = $name,
    e.entity_type = $entity_type,
    e.updated_at = datetime()

-- Fact + ABOUT + FROM_SOURCE + MENTIONS
MERGE (f:Fact {fact_id: $fact_id})
SET f.text = $text, f.category = $category,
    f.confidence = $confidence, f.created_at = datetime()
WITH f
MATCH (t:Topic {topic_id: $topic_id})
MERGE (f)-[:ABOUT]->(t)
WITH f
MATCH (s:Source {source_id: $source_id})
MERGE (f)-[:FROM_SOURCE]->(s)
WITH f
MATCH (e:Entity {entity_id: $entity_id})
MERGE (f)-[:MENTIONS]->(e)

-- Tip + ABOUT + FROM_SOURCE + MENTIONS（同構造）
-- Story + ABOUT + FROM_SOURCE + MENTIONS（同構造）

-- RELATES_TO（Entity-Entity）
MATCH (e1:Entity {entity_id: $from_id})
MATCH (e2:Entity {entity_id: $to_id})
MERGE (e1)-[r:RELATES_TO]->(e2)
SET r.rel_detail = $rel_detail
```

### 投入検証

```cypher
MATCH (n)
WHERE n.created_at >= datetime($cycle_start)
RETURN labels(n)[0] AS label, count(n) AS cnt
ORDER BY cnt DESC
```

### ファイル構成

```
.claude/skills/save-to-creator-graph/
  SKILL.md          # メインスキル定義
  guide.md          # MERGE パターン詳細・制約定義・セットアップ手順
```

---

## Step 3: /creator-enrichment スキル（自動拡充メインループ）

**ファイル**: `.claude/skills/creator-enrichment/SKILL.md`

### パラメータ

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| --until | Yes | - | 終了時刻（ISO8601 or `+2h` 相対指定） |

### アーキテクチャ

```
/creator-enrichment --until 2026-03-22T18:00
  |
  +-- Phase 0: 初期化（1回のみ）
  |     +-- --until パラメータ解析
  |     +-- ToolSearch: neo4j-creator, tavily, reddit, time MCP ロード
  |     +-- creator-neo4j 接続確認
  |     +-- config 読み込み（data/config/creator-enrichment-config.json）
  |     +-- セッションログ作成（.tmp/creator-enrichment/{session_id}.json）
  |
  +-- [繰り返し: 終了時刻まで]
  |
  +-- Phase 1: ギャップ分析
  |     +-- 1.1: ジャンル別ノード数取得
  |     +-- 1.2: コンテンツタイプ別偏り検出（Fact vs Tip vs Story）
  |     +-- 1.3: 低カバレッジ Topic 特定（コンテンツ数が少ない Topic TOP 10）
  |     +-- 1.4: ターゲットジャンル・Topic・コンテンツタイプ決定
  |
  +-- Phase 2: 検索クエリ生成・実行
  |     +-- 2.1: ギャップに基づく検索クエリ動的生成
  |     +-- 2.2: Tavily search（英語 3-4クエリ + 日本語 2-3クエリ）
  |     +-- 2.3: WebFetch（JP特化サイト, 2-4回）
  |     +-- 2.4: Tavily extract（有望URL深掘り, 1-3回）
  |     +-- 2.5: Reddit 収集（ジャンル別 subreddit, 1-2回）
  |     +-- 2.6: 結果集約
  |
  +-- Phase 3: データ変換
  |     +-- 3.1: 検索結果を Fact/Tip/Story に分類
  |     +-- 3.2: 各 Fact/Tip/Story テキストから Entity 抽出
  |     +-- 3.3: Entity 重複排除（entity_key ベース）
  |     +-- 3.4: Entity 間リレーション検出
  |     +-- 3.5: 構造化 JSON 生成（emit_creator_queue.py 入力形式）
  |     +-- 3.6: 入力 JSON を .tmp/creator-enrichment/cycle-{N}-input.json に保存
  |
  +-- Phase 4: パイプライン投入
  |     +-- 4.1: emit_creator_queue.py 実行 → .tmp/creator-graph-queue/ に JSON 生成
  |     +-- 4.2: /save-to-creator-graph 実行（⚠️ /save-to-graph ではない）
  |     |         → mcp__neo4j-creator__creator-write_neo4j_cypher で MERGE
  |     |         → bolt://localhost:7689 に接続
  |     +-- 4.3: 投入結果の検証（mcp__neo4j-creator__creator-read_neo4j_cypher）
  |
  +-- Phase 5: サイクルレポート + 時間チェック
        +-- 5.1: サイクル統計をセッションログに追記
        +-- 5.2: サイクルサマリーを表示
        +-- 5.3: 現在時刻 vs --until を比較
        +-- 5.4: 残り時間 > 推定サイクル時間 × 1.2 → 次サイクルへ
        +-- 5.5: 時間切れ → 最終レポート出力して終了
```

### Phase 1: ギャップ分析 Cypher

```cypher
-- Q1: ジャンル別コンテンツ数（ローテーション判断用）
MATCH (g:Genre)
OPTIONAL MATCH (t:Topic)-[:IN_GENRE]->(g)
OPTIONAL MATCH (content)-[:ABOUT]->(t)
WHERE content:Fact OR content:Tip OR content:Story
RETURN g.genre_id AS genre,
       count(DISTINCT t) AS topics,
       count(DISTINCT content) AS content_count
ORDER BY content_count ASC

-- Q2: ターゲットジャンル内のコンテンツタイプ偏り
MATCH (g:Genre {genre_id: $target_genre})<-[:IN_GENRE]-(t:Topic)
OPTIONAL MATCH (f:Fact)-[:ABOUT]->(t)
OPTIONAL MATCH (tip:Tip)-[:ABOUT]->(t)
OPTIONAL MATCH (s:Story)-[:ABOUT]->(t)
RETURN count(DISTINCT f) AS facts,
       count(DISTINCT tip) AS tips,
       count(DISTINCT s) AS stories

-- Q3: 低カバレッジ Topic TOP 10
MATCH (t:Topic)-[:IN_GENRE]->(g:Genre {genre_id: $target_genre})
OPTIONAL MATCH (content)-[:ABOUT]->(t)
WHERE content:Fact OR content:Tip OR content:Story
WITH t, count(content) AS total
RETURN t.topic_id, t.name, total
ORDER BY total ASC LIMIT 10

-- Q4: 既存コンテンツサンプル（重複回避用）
MATCH (content)-[:ABOUT]->(t:Topic)-[:IN_GENRE]->(g:Genre {genre_id: $target_genre})
WHERE content:Fact OR content:Tip OR content:Story
RETURN labels(content)[0] AS type,
       CASE WHEN content:Fact THEN content.text
            WHEN content:Tip THEN content.text
            WHEN content:Story THEN content.text END AS text
ORDER BY rand() LIMIT 20
```

### Phase 2: 検索戦略

#### 検索バジェット（1サイクルあたり）

| ソース | 回数 | 備考 |
|--------|------|------|
| Tavily search (EN) | 3-4 | 英語グローバルコンテンツ |
| Tavily search (JP) | 2-3 | 日本語クエリ（Tavily はJP対応） |
| Tavily extract | 1-3 | 有望URLの本文抽出 |
| WebFetch (JP sites) | 2-4 | note.com, hatena, ameblo 等 |
| Reddit | 1-2 | ジャンル別subreddit |

#### ジャンル別情報ソース

**設定ファイル**: `data/config/creator-enrichment-config.json`

| ジャンル | Tavily（EN） | Tavily（JP） | WebFetch対象 | Reddit |
|---------|-------------|-------------|-------------|--------|
| career | side hustle, freelance tips, career change | 副業 成功事例, 転職 年収アップ | note.com（副業）, hatena | r/sidehustle, r/careerguidance, r/Entrepreneur |
| beauty-romance | dating app statistics, skincare tips | マッチングアプリ 成功率, 美容 トレンド | note.com（恋愛）, ameblo | r/SkincareAddiction, r/dating_advice |
| spiritual | astrology business, tarot monetization | 占い ビジネス 収益化, タロット 副業 | note.com（占い）, ameblo | r/tarot, r/astrology |

#### WebFetch パターン

Tavily で `site:note.com {keyword}` 等のクエリでURL発見 → WebFetch/Tavily extract で本文取得。

クエリはギャップ分析結果に基づき動的に調整:
- ターゲット Topic 名をクエリに組み込む
- 不足コンテンツタイプに応じたキーワード追加（Story 不足 → "体験談", "experience"）
- `{year}` プレースホルダーを当年に置換

### Phase 3: 分類 + Entity 抽出

#### 分類ルール

| 分類 | シグナル |
|------|---------|
| Fact | 数値・統計・調査結果・「〜によると」・verifiable なデータ |
| Tip | 「〜すべき」・ハウツー・推奨・ステップ形式・アドバイス |
| Story | 一人称体験・ケーススタディ・成功/失敗談・時系列ナラティブ |

#### Entity 抽出ルール

Phase 3.2 で LLM が各 Fact/Tip/Story テキストから Entity を抽出する。分類と同一パスで実行（APIコール節約）。

- 各コンテンツから最低1、最大5エンティティ抽出
- entity_type は許可値（person, company, platform, service, occupation, technique, metric, product, concept）に限定
- 抽出失敗時はログ出力のみ（投入はブロックしない）

#### Entity 間リレーション検出

Phase 3.4 で抽出された Entity 間の意味的関係を検出。

- 入力: 同一サイクル内の全 Entity リスト
- 出力: `{from_entity: "name::type", to_entity: "name::type", rel_detail: "関係の説明"}`
- 品質基準: 明確な関係のみ。推測的な関係は除外

### ジャンルローテーション

```
priority_score = 1.0 / (content_count + 1)
前サイクルと同一ジャンル → ×0.7 のダンピング
→ 最高スコアのジャンルを選択
```

### エラーハンドリング

| エラー | 対応 |
|--------|------|
| creator-neo4j 接続失敗 | Phase 0 で中断、Docker 状態を確認 |
| Tavily 全失敗 | WebFetch + Reddit で継続 |
| WebFetch 失敗 | ログ記録、Tavily + Reddit で継続 |
| Reddit fetch 失敗 | ログ記録、他ソースで継続 |
| 全検索結果ゼロ | サイクルスキップ、次サイクルへ |
| パイプライン投入失敗 | エラーログ、次サイクルへ |
| 3連続サイクルゼロ結果 | 60秒待機後リトライ |

### セッションログ

**出力先**: `.tmp/creator-enrichment/{session_id}.json`

```json
{
  "session_id": "ce-20260322T1400",
  "started_at": "...",
  "until": "...",
  "cycles": [{
    "cycle_number": 1,
    "target_genre": "spiritual",
    "target_topics": ["タロット副業"],
    "target_content_type": "story",
    "searches": {
      "tavily_en": 3,
      "tavily_jp": 2,
      "tavily_extract": 1,
      "webfetch": 2,
      "reddit": 1
    },
    "nodes_created": {
      "facts": 4,
      "tips": 3,
      "stories": 2,
      "entities": 8,
      "sources": 5
    },
    "relations_created": {
      "about": 9,
      "from_source": 9,
      "mentions": 15,
      "relates_to": 4
    },
    "duration_seconds": 210
  }],
  "cumulative": {
    "total_cycles": 1,
    "total_facts": 4,
    "total_tips": 3,
    "total_stories": 2,
    "total_entities": 8,
    "total_mentions_rels": 15,
    "total_relates_to_rels": 4,
    "avg_cycle_seconds": 210
  }
}
```

---

## Step 4: 設定ファイル

**ファイル**: `data/config/creator-enrichment-config.json`

各ジャンルの Tavily クエリテンプレート（EN/JP）、WebFetch 対象サイト、subreddit リスト、フィルタ条件、サイクル設定、entity_types_focus を定義。

---

## ファイル一覧

| # | ファイル | 種別 | 説明 |
|---|---------|------|------|
| 1 | `scripts/emit_creator_queue.py` | Python | graph-queue JSON 生成（~400行、Entity対応） |
| 2 | `.claude/skills/save-to-creator-graph/SKILL.md` | Skill | Neo4j MERGE投入（Entity/MENTIONS/RELATES_TO対応） |
| 3 | `.claude/skills/save-to-creator-graph/guide.md` | Ref | MERGE パターン詳細・制約定義・セットアップ手順 |
| 4 | `.claude/skills/creator-enrichment/SKILL.md` | Skill | メインの自動拡充ループ |
| 5 | `.claude/skills/creator-enrichment/references/gap-analysis-queries.md` | Ref | Cypher クエリ集 |
| 6 | `.claude/skills/creator-enrichment/references/genre-config.md` | Ref | ジャンル別検索戦略 |
| 7 | `.claude/skills/creator-enrichment/references/entity-extraction-prompt.md` | Ref | Entity抽出LLMプロンプト |
| 8 | `data/config/creator-enrichment-config.json` | Config | ジャンル・Tavily・WebFetch・subreddit定義 |
| 9 | `.claude/commands/creator-enrichment.md` | Command | スラッシュコマンド定義 |

### 既存ファイル（参考・再利用）

| ファイル | 再利用ポイント |
|---------|---------------|
| `src/pdf_pipeline/services/id_generator.py` | `generate_entity_id()` (L273), `generate_source_id()` (L62) |
| `scripts/emit_graph_queue.py` | argparse構造、mapper設計パターン、entity dedup |
| `.claude/skills/web-search/SKILL.md` | Tavily MCP ツール選択ガイド |
| `.claude/skills/investment-research/SKILL.md` | マルチソース検索パターン |
| `data/config/reddit-subreddits.json` | subreddit 設定形式 |

> **⚠️ `/save-to-graph` は参照しない。** MERGE パターンは `/save-to-creator-graph/guide.md` に独立定義する。

### パイプライン対比表

| | research-neo4j | creator-neo4j |
|---|---|---|
| Neo4j URI | bolt://localhost:7688 | bolt://localhost:7689 |
| emit スクリプト | emit_graph_queue.py | emit_creator_queue.py |
| 中間ファイル | .tmp/graph-queue/ | .tmp/creator-graph-queue/ |
| 投入スキル | /save-to-graph | /save-to-creator-graph |
| MCP write | research-write_neo4j_cypher | creator-write_neo4j_cypher |
| MCP read | research-read_neo4j_cypher | creator-read_neo4j_cypher |
| schema_version | "2.2" | "creator-1.0" |

---

## 実装順序

### Phase A: パイプライン基盤

1. `scripts/emit_creator_queue.py` — Entity対応のgraph-queue生成
2. `.claude/skills/save-to-creator-graph/` — Entity/MENTIONS/RELATES_TO対応のMERGE投入

### Phase B: 検索・変換

3. `data/config/creator-enrichment-config.json` — 設定ファイル
4. Entity抽出プロンプト — LLM用の分類+Entity抽出テンプレート
5. `.claude/skills/creator-enrichment/` — メインスキル + references

### Phase C: 統合

6. `.claude/commands/creator-enrichment.md` — コマンド定義

## 検証方法

1. **パイプライン単体テスト**: テスト JSON（Entity付き）→ emit_creator_queue.py → graph-queue JSON の構造確認
2. **Entity ID一貫性テスト**: `generate_entity_id("Webライター", "occupation")` が research-neo4j と同一UUID5を生成することを確認
3. **投入テスト**: /save-to-creator-graph でテストデータを creator-neo4j に投入 → Entity + MENTIONS + RELATES_TO を MATCH で確認
4. **単一サイクルテスト**: /creator-enrichment --until +10m で 1-2 サイクル実行、Tavily EN/JP実行・WebFetch試行・Entity生成を確認
5. **ジャンルローテーション確認**: 3 サイクル以上実行し、ジャンルが順番に選択されることを確認
6. **孤立ノード検出**:
   ```cypher
   -- ABOUT なしコンテンツ
   MATCH (n) WHERE (n:Fact OR n:Tip OR n:Story) AND NOT (n)-[:ABOUT]->() RETURN count(n)
   -- MENTIONS なし Entity（警告のみ）
   MATCH (e:Entity) WHERE NOT ()-[:MENTIONS]->(e) RETURN count(e)
   ```
