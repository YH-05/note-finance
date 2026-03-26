# Gap Analysis Queries — research-neo4j

research-neo4j の知識ギャップを 4 軸で定量評価する Cypher クエリ集と統合スコア算出ロジック。
SKILL.md Phase 1 から参照される。

> **前提**: 全クエリは `mcp__neo4j-research__research-read_neo4j_cypher` で実行する。
> Phase 1 実行前に `research-get_neo4j_schema` でスキーマを取得し、Q1-Q5 のラベル・プロパティが一致することを確認すること（同一会話内で直前に取得済みならスキップ可）。

---

## Q1: カテゴリバランス（ConceptCategory 8 種の facts_per_topic）

ConceptCategory ごとに、紐づく Topic 数と Fact 数を集計し、1 Topic あたりの Fact 密度を算出する。

```cypher
MATCH (cc:ConceptCategory)<-[:IS_CATEGORY]-(t:Topic)
OPTIONAL MATCH (t)<-[:TAGGED]-(f:Fact)
WITH cc.name AS category, cc.name_ja AS category_ja,
     count(DISTINCT t) AS topics, count(DISTINCT f) AS facts
RETURN category, category_ja, topics, facts,
       CASE WHEN topics > 0 THEN round(toFloat(facts)/topics, 1) ELSE 0 END AS facts_per_topic
ORDER BY facts_per_topic ASC
```

### 判定基準

- `facts_per_topic < min_facts_per_topic`（Config デフォルト: 5） → 優先カテゴリ
- 現状、WealthManagement(0.0)・ContentPlanning(1.9)・Technology(2.6) が閾値未満

### スコア算出

```
category_gap = 1 - min(facts_per_topic / min_facts_per_topic, 1.0)
```

| facts_per_topic | category_gap |
|-----------------|-------------|
| 0.0 | 1.00 |
| 1.9 | 0.62 |
| 2.6 | 0.48 |
| 5.0+ | 0.00 |

---

## Q2: Entity 空洞（ticker あり & Fact 0 件）

ticker を持つ Entity のうち、ABOUT・RELATES_TO のいずれでも Fact が接続されていないものを検出する。

```cypher
MATCH (e:Entity)
WHERE e.ticker IS NOT NULL AND e.ticker <> ''
OPTIONAL MATCH (f:Fact)-[:ABOUT|RELATES_TO]->(e)
WITH e, count(DISTINCT f) AS fact_count
WHERE fact_count = 0
OPTIONAL MATCH (e)-[:IN_SECTOR]->(sec:Sector)
RETURN e.name AS name, e.ticker AS ticker, e.entity_key AS entity_key,
       e.sec_cik AS sec_cik, sec.name AS sector, fact_count
LIMIT 30
```

### 判定基準

- Fact 0 件 → entity_gap = 1.0（最優先）
- Fact 1-3 件 → entity_gap = 0.5（中優先、Q3 鮮度と併用）
- Fact 4 件以上 → entity_gap = 0.0

### Fact 件数付きバリアント（1-3 件判定用）

```cypher
MATCH (e:Entity)
WHERE e.ticker IS NOT NULL AND e.ticker <> ''
OPTIONAL MATCH (f:Fact)-[:ABOUT|RELATES_TO]->(e)
WITH e, count(DISTINCT f) AS fact_count
WHERE fact_count BETWEEN 1 AND 3
OPTIONAL MATCH (e)-[:IN_SECTOR]->(sec:Sector)
RETURN e.name AS name, e.ticker AS ticker, e.entity_key AS entity_key,
       fact_count, sec.name AS sector
ORDER BY fact_count ASC
LIMIT 20
```

---

## Q3: 鮮度（as_of_date が古い Entity を昇順）

ticker を持つ Entity について、最新の Fact.as_of_date を取得し、古い順に並べる。

```cypher
MATCH (e:Entity)
WHERE e.ticker IS NOT NULL AND e.ticker <> ''
OPTIONAL MATCH (f:Fact)-[:ABOUT|RELATES_TO]->(e)
WITH e.name AS name, e.ticker AS ticker, e.entity_key AS entity_key,
     max(f.as_of_date) AS latest_fact, count(f) AS fact_count
WHERE fact_count > 0
RETURN name, ticker, entity_key, latest_fact, fact_count
ORDER BY latest_fact ASC
LIMIT 20
```

### スコア算出

```
staleness = min(days_since_latest / staleness_threshold_days, 1.0)
```

- `days_since_latest`: 今日 - latest_fact（日数）
- `staleness_threshold_days`: Config デフォルト 90 日
- Fact 0 件の Entity は Q2 で処理するため、ここでは `fact_count > 0` で除外
- Fact 0 件だが Q2 対象外（ticker なし等）の場合は staleness = 1.0 とする

| days_since_latest | staleness |
|-------------------|-----------|
| 0-7 | 0.00-0.08 |
| 30 | 0.33 |
| 60 | 0.67 |
| 90+ | 1.00 |

---

## Q4: 財務ギャップ（sec_cik あり & FDP 0 件）

SEC EDGAR 取得可能（sec_cik が存在）だが FinancialDataPoint が未収集の Entity を検出する。

```cypher
MATCH (e:Entity)
WHERE e.ticker IS NOT NULL AND e.ticker <> ''
AND e.sec_cik IS NOT NULL AND e.sec_cik <> ''
AND NOT exists { (fdp:FinancialDataPoint)-[:RELATES_TO]->(e) }
RETURN e.name AS name, e.ticker AS ticker, e.sec_cik AS sec_cik,
       e.entity_key AS entity_key
LIMIT 20
```

### スコア算出

```
financial_gap:
  sec_cik あり & FDP 0 件 → 1.0
  sec_cik あり & FDP 1 件以上 → 0.0
  sec_cik なし → 0.0（SEC EDGAR 取得不可のため対象外）
```

---

## Q5: 重複排除（直近 7 日間の Source URL 一覧）

同一 URL の重複投入を防ぐため、直近 7 日間に投入された Source の URL 一覧を取得する。
Phase 2（検索）の結果と照合し、既に投入済みの URL をスキップする。

```cypher
MATCH (s:Source)
WHERE s.url IS NOT NULL
AND s.created_at >= datetime() - duration('P7D')
RETURN s.url AS url, s.source_type AS source_type, s.title AS title
ORDER BY s.created_at DESC
```

### 用途

- Phase 2 の検索結果 `raw_items[].source_url` と突合
- 一致する URL はスキップ（重複投入防止）
- LIMIT なし（直近 7 日分は全量取得して正確に照合する）

---

## 統合スコア算出

### 重み

```
unified_score = 0.15 * category_gap + 0.35 * entity_gap + 0.30 * staleness + 0.20 * financial_gap
```

| 軸 | 重み | 根拠 |
|----|------|------|
| category_gap (w1) | 0.15 | WealthManagement 等の穴は深刻だが銘柄分析への直接影響は限定的 |
| entity_gap (w2) | 0.35 | 銘柄分析に直結。AMD, Broadcom 等の空洞は最優先 |
| staleness (w3) | 0.30 | Google/Microsoft が 12 ヶ月前では記事の信頼性に影響 |
| financial_gap (w4) | 0.20 | SEC EDGAR 自動取得可能で費用対効果が高い |

### 各軸の正規化

| 軸 | 正規化式 | 範囲 |
|----|----------|------|
| category_gap | `1 - min(facts_per_topic / min_facts_per_topic, 1.0)` | 0.0 - 1.0 |
| entity_gap | Fact 0 件 → 1.0、1-3 件 → 0.5、4+ 件 → 0.0 | 0.0 / 0.5 / 1.0 |
| staleness | `min(days_since_latest / staleness_threshold_days, 1.0)` | 0.0 - 1.0 |
| financial_gap | sec_cik あり & FDP 0 件 → 1.0、それ以外 → 0.0 | 0.0 / 1.0 |

### スコア算出例

| Entity | cat | ent | stale | fin | unified_score |
|--------|-----|-----|-------|-----|---------------|
| AMD (ticker あり, Fact 0, sec_cik=2488, FDP 0) | 0.00 | 0.35 | 0.00 | 0.20 | **0.55** |
| Google (Fact 4+, stale 12mo, FDP あり) | 0.00 | 0.00 | 0.30 | 0.00 | **0.30** |
| WealthManagement Topic (facts/topic=0) | 0.15 | 0.00 | 0.00 | 0.00 | **0.15** |
| Broadcom (Fact 0, sec_cik=1730168, FDP 0) | 0.00 | 0.35 | 0.00 | 0.20 | **0.55** |

---

## セッション内ダンピング

同一セッション内で既に処理済みの Entity が再度上位に来ることを防ぐ。

```
処理済み Entity のスコア: unified_score × 0.3
```

### 適用タイミング

- Phase 1 のスコア算出時、前サイクルまでに処理済みの `entity_key` リストを保持
- 処理済み Entity のスコアに 0.3 を乗じる
- これにより、未処理の Entity が優先的に選択される

### 例

| Entity | 元スコア | 処理済み | 適用後スコア |
|--------|---------|---------|-------------|
| AMD | 0.55 | No | 0.55 |
| Broadcom | 0.55 | Yes（前サイクルで処理） | 0.165 |
| Google | 0.30 | No | 0.30 |

---

## バッチ選定

unified_score の上位 `max_targets_per_cycle` 件（Config デフォルト: 5）を選定し、
そのサイクルの検索・構造化・投入対象とする。

### 選定手順

1. Q1-Q4 を実行し、全候補の各軸スコアを算出
2. unified_score を計算
3. セッション内ダンピングを適用
4. unified_score 降順でソート
5. 上位 `max_targets_per_cycle` 件を選定

### 選定結果の出力形式

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

## 実行順序

1. **Q1** → カテゴリバランスの現状把握 → category_gap 算出
2. **Q2** → Entity 空洞の検出 → entity_gap 算出
3. **Q3** → 鮮度の低い Entity の検出 → staleness 算出
4. **Q4** → 財務データ欠損の検出 → financial_gap 算出
5. **Q5** → 重複排除リスト構築（Phase 2 で使用）
6. **統合スコア算出** → ダンピング適用 → バッチ選定

Q1-Q4 は相互に依存しないため並列実行可能。Q5 もスコア算出には不要だが、
Phase 2 の前に必要なため Phase 1 内で実行する。
