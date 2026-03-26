# F-3: ワークフロー統合ガイド

**Instance**: research-neo4j (bolt://localhost:7688)
**Ontology Version**: research-3.0
**Generated**: 2026-03-23

---

## 概要

research-neo4j ナレッジグラフを既存のワークフロー（記事執筆、トピック発見、投資リサーチ、週次レポート、creator-neo4j 連携、emit_graph_queue v3.0）に統合するための設計ドキュメント。

出典品質とレポート利用可否の運用基準は [source-fact-provenance-policy.md](./source-fact-provenance-policy.md) を参照すること。特に、一次ソース不在時の `Source` / `Fact` の扱いは本ガイドではなく同ポリシーを正とする。

### 統合ワークフロー一覧

| ID | ワークフロー | 統合ポイント | 主要クエリ |
|----|-------------|-------------|-----------|
| W1 | article-research | KG 照会 + ギャップ分析 | T1, T4, T5 |
| W2 | topic-discovery | トピックスコアリング | T1-c, P2, P7 |
| W3 | investment-research | Initial Report 構築 | T2, T3, T4, T6 |
| W4 | weekly-report | 直近データ抽出 | T1-b, T7-d, P2-a |
| W5 | creator-enrichment | 共有 Entity 連携 | T6, P1-c |
| W6 | emit_graph_queue v3.0 | Classification Post-Processor | T7-a, T5-e |

---

## W1: article-research 統合

**既存コマンド**: `/article-research`
**統合ポイント**: Step 0（KG 既存データ照会 + ギャップ分析）

### フロー

```
/article-research @articles/{category}/{slug}/
  │
  ├── Step 0: KG 照会 + ギャップ分析
  │   ├── 0-1. meta.yaml からキーワード抽出
  │   ├── 0-2. Entity/Topic 照会（T6-a, T1-b）
  │   ├── 0-3. 既存 Fact/Claim 取得（T1-a）
  │   ├── 0-4. センチメント分布分析（T4-c）
  │   ├── 0-5. カバレッジギャップ検出（T5-a, T5-c）
  │   └── 0-6. kg_gap_report.md 出力
  │
  ├── Step 2: ギャップ優先リサーチ実行
  │   └── （ギャップレポートに基づきWeb検索を実施）
  │
  └── Step 4: KG 永続化
      ├── emit_research_queue.py --command web-research
      └── /save-to-research-graph
```

### 照会クエリ（Step 0 で使用）

#### 0-2: 関連 Entity/Topic の発見

```cypher
// meta.yaml の topic からキーワードを抽出して照会
// パラメータ: $keywords (例: ["日銀", "BOJ", "利上げ", "円", "金利"])

UNWIND $keywords AS keyword
CALL db.index.fulltext.queryNodes('research_entity_fulltext', keyword)
YIELD node AS e, score
WHERE NOT 'Memory' IN labels(e) AND score > 1.0

WITH e, max(score) AS best_score
ORDER BY best_score DESC
LIMIT 20

OPTIONAL MATCH (f:Fact)-[:RELATES_TO]->(e)
OPTIONAL MATCH (c:Claim)-[:MENTIONS]->(e)

RETURN e.name AS entity,
       e.entity_key AS entity_key,
       e.entity_type AS type,
       best_score AS relevance,
       count(DISTINCT f) AS fact_count,
       count(DISTINCT c) AS claim_count
ORDER BY best_score DESC
```

#### 0-3: 既存 Fact/Claim 取得（最新順）

```cypher
// パラメータ: $entity_names (例: ["BOJ", "Japanese Yen"])

MATCH (e:Entity)
WHERE e.name IN $entity_names
AND NOT 'Memory' IN labels(e)

OPTIONAL MATCH (f:Fact)-[:RELATES_TO]->(e)
OPTIONAL MATCH (s:Source)-[:STATES_FACT]->(f)

RETURN e.name AS entity,
       f.content AS fact,
       f.as_of_date AS as_of_date,
       s.title AS source,
       s.url AS source_url,
       toString(s.published_at) AS published_at
ORDER BY s.published_at DESC
LIMIT 20
```

#### 0-4: センチメント分布確認

```cypher
// パラメータ: $entity_names

MATCH (c:Claim)-[:MENTIONS]->(e:Entity)
WHERE e.name IN $entity_names
AND NOT 'Memory' IN labels(e)

RETURN e.name AS entity,
       c.sentiment AS sentiment,
       count(c) AS count
ORDER BY e.name, count DESC
```

#### 0-5: ギャップ判定ロジック

```cypher
// パラメータ: $entity_names

MATCH (e:Entity)
WHERE e.name IN $entity_names
AND NOT 'Memory' IN labels(e)

// 最新ソース日付
OPTIONAL MATCH (content)-[:RELATES_TO|MENTIONS]->(e)
OPTIONAL MATCH (s:Source)-[:STATES_FACT|MAKES_CLAIM]->(content)
WITH e,
     max(s.published_at) AS latest_source_date,
     count(DISTINCT s) AS source_count

// Fact/Claim/FDP カウント
OPTIONAL MATCH (f:Fact)-[:RELATES_TO]->(e)
OPTIONAL MATCH (c:Claim)-[:MENTIONS]->(e)
OPTIONAL MATCH (fdp:FinancialDataPoint)-[:RELATES_TO]-(e)

RETURN e.name AS entity,
       e.entity_type AS type,
       toString(latest_source_date) AS latest_source,
       source_count,
       count(DISTINCT f) AS fact_count,
       count(DISTINCT c) AS claim_count,
       count(DISTINCT fdp) AS fdp_count,
       // ギャップ判定
       CASE WHEN latest_source_date < datetime() - duration({days: 30}) THEN 'stale' ELSE 'fresh' END AS freshness,
       CASE WHEN count(DISTINCT f) = 0 AND count(DISTINCT c) = 0 THEN 'no_coverage' ELSE 'covered' END AS coverage
ORDER BY source_count ASC
```

### kg_gap_report.md 出力フォーマット

```markdown
# KG ギャップレポート

## 既存データサマリー
- 関連エンティティ: X 件
- 関連ファクト: X 件
- 関連クレーム: X 件（bullish: X / bearish: X / neutral: X）
- 最新ソース日: YYYY-MM-DD

## 特定されたギャップ
| 優先度 | ギャップ種別 | 対象 | 説明 |
|--------|------------|------|------|
| HIGH | no_coverage | Entity名 | Fact/Claim が0件 |
| HIGH | stale_data | Entity名 | 最新ソース 30日以上前 |
| MEDIUM | missing_bear_case | Entity名 | bearish Claim が0件 |
| MEDIUM | missing_financials | Entity名 | FDP が0件（company/index） |

## 推奨検索クエリ
1. 「Entity名 + 最新動向」 → stale_data 解消
2. 「Entity名 + リスク」 → missing_bear_case 解消
```

---

## W2: topic-discovery 統合

**既存コマンド**: `/finance-suggest-topics`
**統合ポイント**: トピックスコアリングの入力としてKGデータを活用

### フロー

```
/finance-suggest-topics
  │
  ├── 1. KG からトピック候補を抽出
  │   ├── 新興トピック（P2-a: 成長率の高いトピック）
  │   ├── カバレッジギャップ（T5-d: Source 数が少ないトピック）
  │   └── 隠れた接続（P1-c: Topic ブリッジ経由の新パターン）
  │
  ├── 2. トピックスコアリング
  │   ├── KG 既存カバレッジスコア（多い=記事化しやすい）
  │   ├── ギャップスコア（ギャップ大=新規性あり）
  │   ├── Entity 密度スコア（Entity が多い=具体性あり）
  │   └── センチメント多様性スコア（意見が割れている=議論性あり）
  │
  └── 3. ランク付きトピック提案を出力
```

### スコアリングクエリ

#### トピック候補の総合スコア算出

```cypher
// 全 Topic のスコアリング指標を一括算出

MATCH (t:Topic)
WHERE NOT 'Memory' IN labels(t)

// Source カバレッジ
OPTIONAL MATCH (s:Source)-[:TAGGED]->(t)
WITH t, count(DISTINCT s) AS source_count,
     max(s.collected_at) AS latest_source

// Fact + Claim 密度
OPTIONAL MATCH (f:Fact)-[:ABOUT]->(t)
OPTIONAL MATCH (c:Claim)-[:ABOUT]->(t)
WITH t, source_count, latest_source,
     count(DISTINCT f) AS fact_count,
     count(DISTINCT c) AS claim_count

// Entity 多様性
OPTIONAL MATCH (f2:Fact)-[:ABOUT]->(t)
OPTIONAL MATCH (f2)-[:RELATES_TO]->(e:Entity)
WITH t, source_count, latest_source, fact_count, claim_count,
     count(DISTINCT e) AS entity_diversity

RETURN t.name AS topic,
       t.topic_key AS topic_key,
       t.category AS category,
       source_count,
       fact_count,
       claim_count,
       entity_diversity,
       toString(latest_source) AS latest_source_date,
       // カバレッジスコア（記事化しやすさ）
       source_count * 2 + fact_count + claim_count AS coverage_score,
       // ギャップスコア（新規性・深掘り余地）
       CASE WHEN source_count > 0 AND fact_count < 3 THEN 10
            WHEN source_count = 0 THEN 5
            ELSE 0
       END AS gap_score,
       // 総合スコア
       (source_count * 2 + fact_count + claim_count) * 0.4 +
       entity_diversity * 5 * 0.3 +
       CASE WHEN latest_source >= datetime() - duration({days: 7}) THEN 20 ELSE 0 END * 0.3
       AS total_score
ORDER BY total_score DESC
LIMIT 30
```

---

## W3: investment-research 統合

**既存スキル**: `.claude/skills/investment-research/`
**統合ポイント**: バイサイドアナリスト向け Initial Report の構築素材としてKGデータを使用

### フロー

```
investment-research スキル
  │
  ├── Phase 1: KG データ収集
  │   ├── 1-1. 対象 Entity の基本情報取得（T6-c: entity_key 検索）
  │   ├── 1-2. 企業間関連性マップ取得（T2-a, T2-b）
  │   ├── 1-3. 時系列 FDP 取得（T3-a, T3-b）
  │   ├── 1-4. アナリスト Stance 集約（T4-b, P5-a）
  │   ├── 1-5. サプライチェーン構造取得（P6-c）
  │   └── 1-6. 関連 Fact/Claim 全量取得
  │
  ├── Phase 2: ギャップ分析 + Web リサーチ
  │   ├── KG で不足している情報を特定（T5-c: FDP 未接続）
  │   └── Web 検索で補完
  │
  └── Phase 3: Initial Report 構成
      ├── 会社概要 → Entity + Sector + Industry 情報
      ├── 財務分析 → FDP + Metric + FiscalPeriod データ
      ├── 競合分析 → COMPETES_WITH + P6-c エコシステム
      ├── リスク分析 → bearish Claim + CONTRADICTS
      └── バリュエーション → Stance + target_price
```

### Initial Report 構築用クエリ

#### 1-1: 企業プロファイル取得

```cypher
// パラメータ: $entity_name (例: "Apple")

MATCH (e:Entity {name: $entity_name})
WHERE NOT 'Memory' IN labels(e)

OPTIONAL MATCH (e)-[:IN_SECTOR]->(sec:Sector)

// 全 Fact を取得（最新順）
OPTIONAL MATCH (f:Fact)-[:RELATES_TO]->(e)
OPTIONAL MATCH (sf:Source)-[:STATES_FACT]->(f)

// 全 Claim を取得（最新順）
OPTIONAL MATCH (c:Claim)-[:MENTIONS]->(e)
OPTIONAL MATCH (sc:Source)-[:MAKES_CLAIM]->(c)

RETURN e.name AS entity,
       e.entity_key AS entity_key,
       e.entity_type AS type,
       e.ticker AS ticker,
       sec.name AS sector,
       collect(DISTINCT {
         content: f.content,
         as_of_date: f.as_of_date,
         source: sf.title,
         url: sf.url
       })[..30] AS facts,
       collect(DISTINCT {
         content: c.content,
         sentiment: c.sentiment,
         source: sc.title,
         url: sc.url
       })[..20] AS claims
```

#### 1-3: 財務データ時系列取得

```cypher
// パラメータ: $entity_name

MATCH (e:Entity {name: $entity_name})
WHERE NOT 'Memory' IN labels(e)

MATCH (fdp:FinancialDataPoint)-[:RELATES_TO]-(e)
OPTIONAL MATCH (fdp)-[:FOR_METRIC]->(m:Metric)
OPTIONAL MATCH (fdp)-[:FOR_PERIOD]->(fp:FiscalPeriod)
OPTIONAL MATCH (fdp)-[:IN_UNIT]->(u:UnitOfMeasure)
OPTIONAL MATCH (fdp)-[:IS_DATAPOINT_TYPE]->(dpt:DataPointType)
OPTIONAL MATCH (s:Source)-[:HAS_DATAPOINT]->(fdp)

RETURN m.name AS metric,
       fp.year AS year,
       fp.quarter AS quarter,
       fp.type AS period_type,
       fdp.value AS value,
       u.symbol AS unit,
       COALESCE(dpt.name, 'unknown') AS datapoint_type,
       s.title AS source,
       s.url AS source_url
ORDER BY m.name, fp.year, fp.quarter
```

#### 1-4: アナリスト Stance サマリー

```cypher
// パラメータ: $entity_name

MATCH (st:Stance)-[:ON_ENTITY]->(e:Entity {name: $entity_name})
WHERE NOT 'Memory' IN labels(e)

OPTIONAL MATCH (s:Source)-[:HOLDS_STANCE]->(st)
OPTIONAL MATCH (s)-[:AUTHORED_BY]->(a:Author)

RETURN a.name AS analyst,
       st.sentiment AS sentiment,
       st.rating AS rating,
       st.target_price AS target_price,
       st.as_of_date AS date,
       st.note AS note,
       s.title AS report_title,
       s.url AS report_url
ORDER BY st.as_of_date DESC
```

### Initial Report セクションマッピング

| レポートセクション | KG データソース | クエリ |
|------------------|---------------|--------|
| 会社概要 | Entity + Sector + Industry | T6-c |
| ビジネスモデル | Fact (entity_type=company) | 1-1 (facts) |
| 財務サマリー | FDP + Metric + FiscalPeriod | 1-3 |
| 競合分析 | COMPETES_WITH + エコシステム | T2-a, P6-c |
| 成長戦略 | bullish Claim | T4-c (direction=positive) |
| リスク要因 | bearish Claim + CONTRADICTS | T4-c (direction=negative), P3-b |
| バリュエーション | Stance + target_price | 1-4 |
| アナリストコンセンサス | Stance 集約 | P5-a |
| 参考文献 | Source (url, title) | 全クエリの source_url |

---

## W4: weekly-report 統合

**既存コマンド**: `/generate-market-report`
**統合ポイント**: 直近1週間のデータから市場コメンタリーを構築

### フロー

```
/generate-market-report
  │
  ├── Phase 1: KG からの直近データ抽出
  │   ├── 直近7日の Source + 関連 Fact/Claim（T3-d 改変）
  │   ├── 新興トピック検出（P2-a）
  │   ├── 直近の Stance 変化（P5-b 直近7日限定）
  │   └── セクター別アクティビティ（P4-c）
  │
  ├── Phase 2: 既存の RSS/Web データと統合
  │
  └── Phase 3: レポート生成
```

### 直近データ抽出クエリ

#### 直近7日の主要 Fact/Claim

```cypher
// 直近7日に投入された Source から Fact/Claim を取得

MATCH (s:Source)
WHERE NOT 'Memory' IN labels(s)
AND s.collected_at >= datetime() - duration({days: 7})

// Fact
OPTIONAL MATCH (s)-[:STATES_FACT]->(f:Fact)
OPTIONAL MATCH (f)-[:RELATES_TO]->(fe:Entity)

// Claim
OPTIONAL MATCH (s)-[:MAKES_CLAIM]->(c:Claim)
OPTIONAL MATCH (c)-[:MENTIONS]->(ce:Entity)

// Topic
OPTIONAL MATCH (s)-[:TAGGED]->(t:Topic)

WITH s, f, c, t,
     collect(DISTINCT fe.name) AS fact_entities,
     collect(DISTINCT ce.name) AS claim_entities

RETURN s.title AS source_title,
       s.url AS source_url,
       s.source_type AS type,
       toString(s.published_at) AS published_at,
       collect(DISTINCT {
         content: left(f.content, 200),
         entities: fact_entities
       })[..5] AS facts,
       collect(DISTINCT {
         content: left(c.content, 200),
         sentiment: c.sentiment,
         entities: claim_entities
       })[..5] AS claims,
       collect(DISTINCT t.name) AS topics
ORDER BY s.published_at DESC
LIMIT 50
```

#### 週次トピックアクティビティ

```cypher
// 直近7日に最も Source 数が増えたトピック

MATCH (s:Source)-[:TAGGED]->(t:Topic)
WHERE NOT 'Memory' IN labels(s)
AND s.collected_at >= datetime() - duration({days: 7})

WITH t, count(DISTINCT s) AS weekly_sources,
     collect(DISTINCT s.source_type) AS source_types

ORDER BY weekly_sources DESC
LIMIT 15

OPTIONAL MATCH (f:Fact)-[:ABOUT]->(t)
WHERE f.created_at >= datetime() - duration({days: 7})

RETURN t.name AS topic,
       t.category AS category,
       weekly_sources,
       source_types,
       count(DISTINCT f) AS new_facts
ORDER BY weekly_sources DESC
```

#### 直近 Stance 変化のある Entity

```cypher
// 直近7日に新しい Stance が追加された Entity

MATCH (st:Stance)-[:ON_ENTITY]->(e:Entity)
WHERE NOT 'Memory' IN labels(e)

OPTIONAL MATCH (s:Source)-[:HOLDS_STANCE]->(st)
WHERE s.collected_at >= datetime() - duration({days: 7})
AND s IS NOT NULL

OPTIONAL MATCH (s)-[:AUTHORED_BY]->(a:Author)

RETURN e.name AS entity,
       e.entity_type AS type,
       st.sentiment AS new_sentiment,
       st.rating AS new_rating,
       st.target_price AS target_price,
       a.name AS analyst,
       s.title AS source
ORDER BY s.collected_at DESC
```

---

## W5: creator-enrichment 統合

**既存スキル**: `.claude/skills/creator-enrichment/`
**統合ポイント**: research-neo4j と creator-neo4j の共有 Entity を介したデータ連携

### 前提

- **research-neo4j** (port 7688): 銘柄・マクロ調査データ
- **creator-neo4j** (port 7687): コンテンツ執筆・クリエイター分析データ
- 2つのインスタンスは独立だが、同一 Entity（企業名、指標等）を共有

### 連携パターン

```
research-neo4j                    creator-neo4j
┌──────────────┐                 ┌──────────────┐
│ Entity       │    entity_key   │ Entity       │
│ (Apple::co)  │ ◄═══════════► │ (Apple::co)  │
│              │                 │              │
│ Fact/Claim   │    素材提供     │ Article      │
│ FDP/Stance   │ ─────────────► │ ContentBlock │
│ Source       │                 │ ContentTheme │
└──────────────┘                 └──────────────┘
```

### 連携クエリ

#### 共有 Entity の検出

```cypher
// research-neo4j 側で実行
// creator-neo4j に存在する entity_key のリストを入力として
// 一致する Entity の詳細情報を取得
// パラメータ: $creator_entity_keys (例: ["Apple::company", "NVIDIA::company"])

MATCH (e:Entity)
WHERE e.entity_key IN $creator_entity_keys
AND NOT 'Memory' IN labels(e)

OPTIONAL MATCH (f:Fact)-[:RELATES_TO]->(e)
OPTIONAL MATCH (c:Claim)-[:MENTIONS]->(e)
OPTIONAL MATCH (fdp:FinancialDataPoint)-[:RELATES_TO]-(e)

RETURN e.entity_key AS entity_key,
       e.name AS name,
       count(DISTINCT f) AS research_facts,
       count(DISTINCT c) AS research_claims,
       count(DISTINCT fdp) AS research_fdp
```

#### 記事素材の取得（research -> creator）

```cypher
// パラメータ: $entity_name (例: "Apple")
// 記事執筆の素材として使える Fact/Claim + Source URL を取得

MATCH (e:Entity {name: $entity_name})
WHERE NOT 'Memory' IN labels(e)

// 根拠データ付き Fact
OPTIONAL MATCH (f:Fact)-[:RELATES_TO]->(e)
OPTIONAL MATCH (sf:Source)-[:STATES_FACT]->(f)
WHERE sf.url IS NOT NULL

// センチメント付き Claim
OPTIONAL MATCH (c:Claim)-[:MENTIONS]->(e)
OPTIONAL MATCH (sc:Source)-[:MAKES_CLAIM]->(c)
WHERE sc.url IS NOT NULL

RETURN e.name AS entity,
       // ソースURL付き Fact（記事引用用）
       collect(DISTINCT {
         fact: f.content,
         source_url: sf.url,
         source_title: sf.title,
         published: toString(sf.published_at)
       })[..20] AS citable_facts,
       // センチメント付き Claim（論点整理用）
       collect(DISTINCT {
         claim: c.content,
         sentiment: c.sentiment,
         source_url: sc.url,
         source_title: sc.title
       })[..15] AS claims_for_analysis
```

### データフロー

| 方向 | データ | 用途 |
|------|--------|------|
| research -> creator | Fact + Source URL | 記事の根拠データ・引用元 |
| research -> creator | Claim + sentiment | 論点整理・多角的分析 |
| research -> creator | FDP + Metric | 数値データ・チャート素材 |
| research -> creator | Stance + analyst | アナリスト見解の引用 |
| creator -> research | Article entity_key | 共有 Entity の特定 |
| creator -> research | ContentTheme | リサーチ対象の優先順位づけ |

---

## W6: emit_research_queue.py v3.0 統合

**既存スクリプト**: `scripts/emit_research_queue.py`
**統合ポイント**: Classification Post-Processor（v3.0 で追加予定の分類ハブノード自動生成）

### 現状（v2.x）

```
入力 JSON → emit_research_queue.py → graph-queue JSON → /save-to-research-graph → Neo4j
                                        ↑
                              プロパティベースの分類
                              (entity_type, source_type 等は文字列プロパティ)
```

### v3.0 目標

```
入力 JSON → emit_research_queue.py → Classification Post-Processor → graph-queue JSON → /save-to-research-graph
                                        ↑
                              ハブノードの自動生成・リレーション付与
                              (EntityType, SourceType, Domain, TrustLevel 等)
```

### Classification Post-Processor の仕様

#### 1. EntityType ハブノード自動生成

```python
# emit_research_queue.py 内の Post-Processor ロジック（疑似コード）

ENTITY_TYPE_MAP = {
    # ontology.yaml の canonical_values に基づく
    "company": "company",
    "fintech": "company",          # consolidates
    "subsidiary": "company",       # consolidates
    "fintech_holding": "company",  # consolidates
    "digital_bank": "company",     # consolidates
    "it_services": "company",      # consolidates
    "technology": "technology",
    "system": "technology",        # consolidates
    "organization": "organization",
    "central_bank": "organization", # consolidates
    "government": "organization",   # consolidates
    # ... 以下同様
}

def classify_entity_type(entity: dict) -> dict:
    raw_type = entity.get("entity_type", "concept")
    canonical = ENTITY_TYPE_MAP.get(raw_type, raw_type)

    # EntityType ハブノードを生成
    hub_node = {
        "label": "EntityType",
        "properties": {
            "entity_type_id": canonical,
            "name": canonical,
            "name_ja": CANONICAL_JA[canonical]
        }
    }

    # IS_TYPE リレーションを生成
    rel = {
        "type": "IS_TYPE",
        "from_label": "Entity",
        "from_key": entity["entity_key"],
        "to_label": "EntityType",
        "to_key": canonical
    }

    return {"hub_node": hub_node, "relationship": rel}
```

#### 2. SourceType ハブノード自動生成

```python
SOURCE_TYPE_MAP = {
    # ontology.yaml の canonical_values に基づく
    "news": "news",
    "blog": "blog",
    "web": "web",
    "pdf": "pdf",
    "academic_paper": "academic",  # consolidates
    "paper": "academic",           # consolidates
    "white_paper": "report",       # consolidates
    "media": "news",               # consolidates
    # ... 以下同様
}

def classify_source_type(source: dict) -> dict:
    raw_type = source.get("source_type", "web")
    canonical = SOURCE_TYPE_MAP.get(raw_type, raw_type)

    hub_node = {
        "label": "SourceType",
        "properties": {
            "source_type_id": canonical,
            "name": canonical,
            "name_ja": CANONICAL_JA[canonical]
        }
    }

    rel = {
        "type": "IS_SOURCE_TYPE",
        "from_label": "Source",
        "from_key": source["source_id"],
        "to_label": "SourceType",
        "to_key": canonical
    }

    return {"hub_node": hub_node, "relationship": rel}
```

#### 3. Domain ハブノード自動生成

```python
def classify_domain(source: dict) -> dict | None:
    url = source.get("url")
    if not url:
        return None

    parsed = urlparse(url)
    domain_name = parsed.netloc.lstrip("www.")

    hub_node = {
        "label": "Domain",
        "properties": {
            "domain_id": domain_name,
            "name": domain_name,
            "base_url": f"{parsed.scheme}://{parsed.netloc}"
        }
    }

    rel = {
        "type": "FROM_DOMAIN",
        "from_label": "Source",
        "from_key": source["source_id"],
        "to_label": "Domain",
        "to_key": domain_name
    }

    return {"hub_node": hub_node, "relationship": rel}
```

#### 4. TrustLevel ハブノード自動生成

```python
# authority_level → TrustLevel マッピング
TRUST_LEVEL_MAP = {
    "official": {"rank": 1, "name_ja": "公的機関"},
    "academic": {"rank": 2, "name_ja": "学術"},
    "company": {"rank": 3, "name_ja": "企業公式"},
    "institutional": {"rank": 4, "name_ja": "機関投資家"},
    "analyst": {"rank": 5, "name_ja": "アナリスト"},
    "industry": {"rank": 6, "name_ja": "業界"},
    "media": {"rank": 7, "name_ja": "メディア"},
    "primary": {"rank": 8, "name_ja": "一次データ"},
    "blog": {"rank": 9, "name_ja": "ブログ"},
    "social": {"rank": 10, "name_ja": "ソーシャル"},
}

def classify_trust_level(source: dict) -> dict | None:
    level = source.get("authority_level")
    if not level or level not in TRUST_LEVEL_MAP:
        return None

    config = TRUST_LEVEL_MAP[level]

    hub_node = {
        "label": "TrustLevel",
        "properties": {
            "trust_level_id": level,
            "name": level,
            "name_ja": config["name_ja"],
            "rank": config["rank"]
        }
    }

    rel = {
        "type": "RATED_AS",
        "from_label": "Source",
        "from_key": source["source_id"],
        "to_label": "TrustLevel",
        "to_key": level
    }

    return {"hub_node": hub_node, "relationship": rel}
```

### 投入後の品質検証クエリ

```cypher
// Classification Post-Processor の投入結果を検証

// EntityType ハブノード数
MATCH (et:EntityType)
RETURN 'EntityType' AS label, count(et) AS count

UNION ALL

// SourceType ハブノード数
MATCH (st:SourceType)
RETURN 'SourceType' AS label, count(st) AS count

UNION ALL

// Domain ハブノード数
MATCH (d:Domain)
RETURN 'Domain' AS label, count(d) AS count

UNION ALL

// TrustLevel ハブノード数
MATCH (tl:TrustLevel)
RETURN 'TrustLevel' AS label, count(tl) AS count
```

```cypher
// 未分類ノードの検出（Post-Processor 漏れ）

// IS_TYPE なし Entity
MATCH (e:Entity)
WHERE NOT (e)-[:IS_TYPE]->(:EntityType)
AND NOT 'Memory' IN labels(e)
RETURN 'Entity without IS_TYPE' AS gap, count(e) AS count

UNION ALL

// IS_SOURCE_TYPE なし Source
MATCH (s:Source)
WHERE NOT (s)-[:IS_SOURCE_TYPE]->(:SourceType)
AND NOT 'Memory' IN labels(s)
RETURN 'Source without IS_SOURCE_TYPE' AS gap, count(s) AS count

UNION ALL

// FROM_DOMAIN なし Source（URL ありの場合のみ）
MATCH (s:Source)
WHERE s.url IS NOT NULL
AND NOT (s)-[:FROM_DOMAIN]->(:Domain)
AND NOT 'Memory' IN labels(s)
RETURN 'Source without FROM_DOMAIN' AS gap, count(s) AS count
```

---

## 付録: 統合チェックリスト

### 新規記事作成時

- [ ] `/article-research` Step 0 で KG 照会を実施したか
- [ ] kg_gap_report.md を確認し、ギャップ優先でリサーチしたか
- [ ] リサーチ結果を `emit_research_queue.py --command web-research` で KG に永続化したか
- [ ] 記事内の根拠データに Source URL を埋め込んだか

### 週次レポート作成時

- [ ] 直近7日の Source/Fact/Claim を KG から抽出したか
- [ ] 新興トピック（P2-a）を確認したか
- [ ] 直近の Stance 変化を確認したか

### KG 品質維持

- [ ] Phase D の品質レポートを定期実行しているか
- [ ] 孤立 Entity（T5-b）の数が増加していないか
- [ ] FOR_METRIC カバレッジ（T5-e）が改善傾向にあるか

### emit_graph_queue v3.0 移行

- [ ] Classification Post-Processor のマッピングテーブルが ontology.yaml と同期しているか
- [ ] 新規データ投入時にハブノードが自動生成されているか
- [ ] 投入後の品質検証クエリでギャップが検出されていないか
