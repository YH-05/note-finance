# F-2: パターン発見クエリ

**Instance**: research-neo4j (bolt://localhost:7688)
**Ontology Version**: research-3.0
**Generated**: 2026-03-23
**Graph Size**: 7,383 nodes / 42,961 relationships

---

## 概要

ナレッジグラフ内の隠れたパターン、新しい接続、意外な関係性を発見するための高度なクエリ集。
定型的なクエリテンプレート（F-1）とは異なり、探索的な分析に使用する。

### クエリ一覧

| ID | カテゴリ | 説明 |
|----|---------|------|
| P1 | Hidden Connections | Fact/Claim 経由でのみ接続される Entity ペア |
| P2 | Emerging Topics | Source 数が急増しているトピック |
| P3 | Contrarian Signals | CONTRADICTS 数が多い Claim |
| P4 | Cross-Sector Influences | 異なるセクター間の INFLUENCES 関係 |
| P5 | Analyst Consensus | Entity 別の Stance センチメント合意度 |
| P6 | Supply Chain Mapping | CUSTOMER_OF + SUBSIDIARY_OF チェーン |
| P7 | Knowledge Gaps | entity_type 別の Fact 密度分析 |
| P8 | Temporal Patterns | FiscalPeriod 横断の FDP トレンド |

---

## P1: Hidden Connections（隠れた接続）

**目的**: 直接の Entity-Entity リレーション（COMPETES_WITH 等）は存在しないが、同じ Fact / Claim で言及されている Entity ペアを発見する。これらは潜在的な関係性の候補。

### P1-a: Fact 共有による隠れた接続

```cypher
// Fact を介して間接的に接続される Entity ペア
// 直接の Entity-Entity リレーションを持たないもののみ

MATCH (e1:Entity)<-[:RELATES_TO]-(f:Fact)-[:RELATES_TO]->(e2:Entity)
WHERE NOT 'Memory' IN labels(e1) AND NOT 'Memory' IN labels(e2)
AND elementId(e1) < elementId(e2)
// 直接接続がないペアのみ
AND NOT (e1)-[:COMPETES_WITH|SUBSIDIARY_OF|CUSTOMER_OF|PARTNERS_WITH|
             INVESTED_IN|INFLUENCES|CAUSES|CO_MENTIONED_WITH]-(e2)

WITH e1, e2, count(DISTINCT f) AS shared_facts,
     collect(DISTINCT left(f.content, 100))[..3] AS sample_facts

WHERE shared_facts >= 2

RETURN e1.name AS entity_1,
       e1.entity_type AS type_1,
       e2.name AS entity_2,
       e2.entity_type AS type_2,
       shared_facts,
       sample_facts
ORDER BY shared_facts DESC
LIMIT 30
```

### P1-b: Claim 共有による隠れた接続

```cypher
// 同一 Claim で MENTIONS されている Entity ペア

MATCH (e1:Entity)<-[:MENTIONS]-(c:Claim)-[:MENTIONS]->(e2:Entity)
WHERE NOT 'Memory' IN labels(e1) AND NOT 'Memory' IN labels(e2)
AND elementId(e1) < elementId(e2)
AND NOT (e1)-[:COMPETES_WITH|SUBSIDIARY_OF|CUSTOMER_OF|PARTNERS_WITH|
             INVESTED_IN|INFLUENCES|CAUSES|CO_MENTIONED_WITH]-(e2)

WITH e1, e2, count(DISTINCT c) AS shared_claims,
     collect(DISTINCT c.sentiment)[..5] AS sentiments,
     collect(DISTINCT left(c.content, 100))[..2] AS sample_claims

WHERE shared_claims >= 2

RETURN e1.name AS entity_1,
       e1.entity_type AS type_1,
       e2.name AS entity_2,
       e2.entity_type AS type_2,
       shared_claims,
       sentiments,
       sample_claims
ORDER BY shared_claims DESC
LIMIT 30
```

### P1-c: Topic ブリッジによる間接接続

```cypher
// 同一 Topic に TAGGED された Source を共有する Entity ペア
// Source -> TAGGED -> Topic <- TAGGED <- Source の経路

MATCH (e1:Entity)<-[:RELATES_TO|MENTIONS]-(content1)-[:SOURCED_FROM|EXTRACTED_FROM*0..1]->(s1:Source)
      -[:TAGGED]->(t:Topic)<-[:TAGGED]-(s2:Source)
      <-[:SOURCED_FROM|EXTRACTED_FROM*0..1]-(content2)-[:RELATES_TO|MENTIONS]->(e2:Entity)
WHERE NOT 'Memory' IN labels(e1) AND NOT 'Memory' IN labels(e2)
AND elementId(e1) < elementId(e2)
AND e1.entity_type <> e2.entity_type  // 異なるタイプの Entity ペアに注目

WITH e1, e2, collect(DISTINCT t.name) AS bridge_topics,
     count(DISTINCT t) AS topic_count

WHERE topic_count >= 2

RETURN e1.name AS entity_1,
       e1.entity_type AS type_1,
       e2.name AS entity_2,
       e2.entity_type AS type_2,
       topic_count,
       bridge_topics
ORDER BY topic_count DESC
LIMIT 20
```

---

## P2: Emerging Topics（新興トピック）

**目的**: Source 数が直近で急増しているトピックを検出し、トレンドの早期発見に活用する。

### P2-a: 直近 vs 過去の Source 増加率

```cypher
// 直近7日 vs 前7日の Source 数比較でトピックの成長率を算出

MATCH (s:Source)-[:TAGGED]->(t:Topic)
WHERE NOT 'Memory' IN labels(s)
AND s.collected_at IS NOT NULL

WITH t,
     count(CASE WHEN s.collected_at >= datetime() - duration({days: 7}) THEN 1 END) AS recent_count,
     count(CASE WHEN s.collected_at >= datetime() - duration({days: 14})
                 AND s.collected_at < datetime() - duration({days: 7}) THEN 1 END) AS prev_count,
     count(s) AS total_count

WHERE recent_count > 0

RETURN t.name AS topic,
       t.topic_key AS topic_key,
       t.category AS category,
       recent_count,
       prev_count,
       total_count,
       CASE WHEN prev_count > 0
         THEN toFloat(recent_count - prev_count) / prev_count * 100
         ELSE 999.0  // 新規トピック
       END AS growth_rate_pct
ORDER BY growth_rate_pct DESC
LIMIT 20
```

### P2-b: 月次トピック成長トレンド

```cypher
// トピック別の月次 Source 数推移

MATCH (s:Source)-[:TAGGED]->(t:Topic)
WHERE NOT 'Memory' IN labels(s)
AND s.collected_at IS NOT NULL

WITH t,
     toString(s.collected_at.year) + '-' +
     CASE WHEN s.collected_at.month < 10 THEN '0' ELSE '' END +
     toString(s.collected_at.month) AS year_month,
     count(s) AS monthly_count

WITH t, collect({month: year_month, count: monthly_count}) AS monthly_data,
     sum(monthly_count) AS total

WHERE total >= 5  // 最低5件以上の Source があるトピックのみ

RETURN t.name AS topic,
       t.category AS category,
       total AS total_sources,
       monthly_data
ORDER BY total DESC
LIMIT 30
```

### P2-c: 新規 Entity 出現トレンド

```cypher
// 直近に初めて Source で言及された Entity（新興プレイヤー）

MATCH (e:Entity)
WHERE NOT 'Memory' IN labels(e)

// Entity に言及する最初の Source の日付を取得
OPTIONAL MATCH (content)-[:RELATES_TO|MENTIONS]->(e)
OPTIONAL MATCH (s:Source)-[:STATES_FACT|MAKES_CLAIM]->(content)
WHERE s.collected_at IS NOT NULL

WITH e, min(s.collected_at) AS first_mentioned

WHERE first_mentioned >= datetime() - duration({days: 30})

OPTIONAL MATCH (f:Fact)-[:RELATES_TO]->(e)
OPTIONAL MATCH (c:Claim)-[:MENTIONS]->(e)

RETURN e.name AS entity,
       e.entity_type AS type,
       toString(first_mentioned) AS first_seen,
       count(DISTINCT f) AS fact_count,
       count(DISTINCT c) AS claim_count
ORDER BY first_mentioned DESC
LIMIT 30
```

---

## P3: Contrarian Signals（逆張りシグナル）

**目的**: CONTRADICTS リレーション数が多い Claim を検出し、見解が分かれている論点を特定する。

### P3-a: 矛盾 Claim ペア検出

```cypher
// CONTRADICTS リレーションで接続された Claim ペア

MATCH (c1:Claim)-[:CONTRADICTS]->(c2:Claim)

OPTIONAL MATCH (s1:Source)-[:MAKES_CLAIM]->(c1)
OPTIONAL MATCH (s2:Source)-[:MAKES_CLAIM]->(c2)

RETURN left(c1.content, 150) AS claim_1,
       c1.sentiment AS sentiment_1,
       s1.title AS source_1,
       left(c2.content, 150) AS claim_2,
       c2.sentiment AS sentiment_2,
       s2.title AS source_2
ORDER BY s1.published_at DESC
```

### P3-b: 高矛盾スコア Claim

```cypher
// CONTRADICTS 数が多い Claim（最も議論がある論点）

MATCH (c:Claim)-[:CONTRADICTS]-(other:Claim)

WITH c, count(DISTINCT other) AS contradiction_count,
     collect(DISTINCT other.sentiment) AS opposing_sentiments

WHERE contradiction_count >= 2

OPTIONAL MATCH (s:Source)-[:MAKES_CLAIM]->(c)
OPTIONAL MATCH (c)-[:MENTIONS]->(e:Entity)

RETURN left(c.content, 200) AS claim,
       c.sentiment AS sentiment,
       contradiction_count,
       opposing_sentiments,
       s.title AS source,
       collect(DISTINCT e.name)[..5] AS entities
ORDER BY contradiction_count DESC
LIMIT 20
```

### P3-c: Entity 別の論争度スコア

```cypher
// Entity ごとの矛盾 Claim 数 / 全 Claim 数 の比率

MATCH (e:Entity)
WHERE NOT 'Memory' IN labels(e)

OPTIONAL MATCH (c:Claim)-[:MENTIONS]->(e)
OPTIONAL MATCH (c)-[:CONTRADICTS]-(other:Claim)

WITH e,
     count(DISTINCT c) AS total_claims,
     count(DISTINCT CASE WHEN other IS NOT NULL THEN c END) AS contradicted_claims

WHERE total_claims >= 3

RETURN e.name AS entity,
       e.entity_type AS type,
       total_claims,
       contradicted_claims,
       toFloat(contradicted_claims) / total_claims AS controversy_score
ORDER BY controversy_score DESC
LIMIT 20
```

---

## P4: Cross-Sector Influences（セクター横断影響）

**目的**: 異なる Sector に属する Entity 間の INFLUENCES / CAUSES 関係を発見し、セクター間の波及効果を可視化する。

### P4-a: 異セクター INFLUENCES パス

```cypher
// 異なるセクターに属する Entity 間の INFLUENCES リレーション

MATCH (e1:Entity)-[:INFLUENCES]->(e2:Entity)
WHERE NOT 'Memory' IN labels(e1) AND NOT 'Memory' IN labels(e2)

OPTIONAL MATCH (e1)-[:IN_SECTOR]->(s1:Sector)
OPTIONAL MATCH (e2)-[:IN_SECTOR]->(s2:Sector)

// 異なるセクターの場合のみ（または片方のセクターが未設定）
WHERE (s1 IS NULL OR s2 IS NULL OR s1 <> s2)

RETURN e1.name AS influencer,
       e1.entity_type AS influencer_type,
       COALESCE(s1.name, e1.sector, 'Unknown') AS influencer_sector,
       e2.name AS influenced,
       e2.entity_type AS influenced_type,
       COALESCE(s2.name, e2.sector, 'Unknown') AS influenced_sector
ORDER BY influencer_sector, influenced_sector
```

### P4-b: CAUSES チェーンによる因果連鎖

```cypher
// CAUSES リレーションの連鎖で因果関係のチェーンを探索

MATCH path = (root:Entity)-[:CAUSES*1..4]->(effect:Entity)
WHERE NOT 'Memory' IN labels(root) AND NOT 'Memory' IN labels(effect)

WITH path,
     [n IN nodes(path) | n.name] AS chain_names,
     [n IN nodes(path) | n.entity_type] AS chain_types,
     length(path) AS depth

RETURN chain_names AS causal_chain,
       chain_types AS entity_types,
       depth
ORDER BY depth DESC
LIMIT 30
```

### P4-c: セクター間影響マトリクス

```cypher
// セクター間の INFLUENCES 集約マトリクス

MATCH (e1:Entity)-[:INFLUENCES]->(e2:Entity)
WHERE NOT 'Memory' IN labels(e1) AND NOT 'Memory' IN labels(e2)

WITH COALESCE(e1.sector, 'Unknown') AS from_sector,
     COALESCE(e2.sector, 'Unknown') AS to_sector,
     count(*) AS influence_count

RETURN from_sector,
       to_sector,
       influence_count
ORDER BY influence_count DESC
```

---

## P5: Analyst Consensus（アナリストコンセンサス）

**目的**: Entity ごとの Stance センチメントを集約し、コンセンサス形成の度合いと乖離を検出する。

### P5-a: Entity 別 Stance 分布

```cypher
// Entity 別に Stance のセンチメント分布を集約

MATCH (st:Stance)-[:ON_ENTITY]->(e:Entity)
WHERE NOT 'Memory' IN labels(e)

WITH e,
     count(st) AS total_stances,
     count(CASE WHEN st.sentiment IN ['positive', 'bullish'] THEN 1 END) AS bullish,
     count(CASE WHEN st.sentiment IN ['negative', 'bearish'] THEN 1 END) AS bearish,
     count(CASE WHEN st.sentiment IN ['neutral', 'mixed'] THEN 1 END) AS neutral,
     collect(st.target_price) AS target_prices,
     collect(st.rating) AS ratings

WHERE total_stances >= 2

RETURN e.name AS entity,
       e.entity_type AS type,
       total_stances,
       bullish,
       bearish,
       neutral,
       // コンセンサス度（絶対値が大きいほど合意が強い）
       toFloat(bullish - bearish) / total_stances AS consensus_score,
       // 乖離度（0に近いほど意見が割れている）
       CASE WHEN total_stances > 1
         THEN 1.0 - toFloat(abs(bullish - bearish)) / total_stances
         ELSE 0.0
       END AS divergence_score,
       target_prices,
       ratings
ORDER BY divergence_score DESC  // 意見が割れている Entity を上位に
LIMIT 20
```

### P5-b: 時系列 Stance 変化

```cypher
// Entity の Stance が時間経過でどう変化したかを追跡

MATCH (st:Stance)-[:ON_ENTITY]->(e:Entity {name: $entity_name})
WHERE NOT 'Memory' IN labels(e)
AND st.as_of_date IS NOT NULL

OPTIONAL MATCH (s:Source)-[:HOLDS_STANCE]->(st)
OPTIONAL MATCH (s)-[:AUTHORED_BY]->(a:Author)

RETURN e.name AS entity,
       st.as_of_date AS date,
       st.sentiment AS sentiment,
       st.rating AS rating,
       st.target_price AS target_price,
       a.name AS analyst,
       s.title AS source
ORDER BY st.as_of_date DESC
```

### P5-c: Author 別のセンチメント傾向

```cypher
// Author（アナリスト）ごとのセンチメント偏りを分析

MATCH (a:Author)<-[:AUTHORED_BY]-(s:Source)-[:HOLDS_STANCE]->(st:Stance)

WITH a,
     count(st) AS total_stances,
     count(CASE WHEN st.sentiment IN ['positive', 'bullish'] THEN 1 END) AS bullish_count,
     count(CASE WHEN st.sentiment IN ['negative', 'bearish'] THEN 1 END) AS bearish_count

WHERE total_stances >= 2

RETURN a.name AS author,
       total_stances,
       bullish_count,
       bearish_count,
       toFloat(bullish_count) / total_stances AS bullish_ratio,
       CASE
         WHEN bullish_count > bearish_count * 2 THEN 'strong_bull'
         WHEN bearish_count > bullish_count * 2 THEN 'strong_bear'
         ELSE 'balanced'
       END AS bias_type
ORDER BY total_stances DESC
```

---

## P6: Supply Chain Mapping（サプライチェーンマッピング）

**目的**: CUSTOMER_OF + SUBSIDIARY_OF のチェーンを走査し、サプライチェーン構造を可視化する。

### P6-a: サプライチェーンツリー（下流展開）

```cypher
// パラメータ: $entity_name (例: "Apple")
// CUSTOMER_OF チェーンで下流のサプライヤーを展開

MATCH (root:Entity {name: $entity_name})
WHERE NOT 'Memory' IN labels(root)

MATCH path = (supplier:Entity)-[:CUSTOMER_OF*1..3]->(root)
WHERE NOT 'Memory' IN labels(supplier)

RETURN root.name AS customer,
       [n IN nodes(path) | n.name] AS supply_chain,
       [n IN nodes(path) | n.entity_type] AS types,
       length(path) AS depth
ORDER BY depth, supplier.name
```

### P6-b: 企業グループ構造（子会社ツリー）

```cypher
// パラメータ: $entity_name (例: "Alphabet")
// SUBSIDIARY_OF チェーンで子会社ツリーを展開

MATCH (root:Entity {name: $entity_name})
WHERE NOT 'Memory' IN labels(root)

MATCH path = (child:Entity)-[:SUBSIDIARY_OF*1..4]->(root)
WHERE NOT 'Memory' IN labels(child)

RETURN root.name AS parent,
       [n IN nodes(path) | n.name] AS subsidiary_chain,
       length(path) AS depth
ORDER BY depth, child.name
```

### P6-c: 統合サプライチェーンビュー

```cypher
// パラメータ: $entity_name (例: "Toyota")
// CUSTOMER_OF + SUBSIDIARY_OF + PARTNERS_WITH を統合したエコシステムマップ

MATCH (root:Entity {name: $entity_name})
WHERE NOT 'Memory' IN labels(root)

// 上流（サプライヤー）
OPTIONAL MATCH upstream = (supplier:Entity)-[:CUSTOMER_OF]->(root)
WHERE NOT 'Memory' IN labels(supplier)

// 下流（顧客）
OPTIONAL MATCH downstream = (root)-[:CUSTOMER_OF]->(customer:Entity)
WHERE NOT 'Memory' IN labels(customer)

// 子会社
OPTIONAL MATCH subsidiary = (sub:Entity)-[:SUBSIDIARY_OF]->(root)
WHERE NOT 'Memory' IN labels(sub)

// パートナー
OPTIONAL MATCH partner = (root)-[:PARTNERS_WITH]-(p:Entity)
WHERE NOT 'Memory' IN labels(p)

// 競合
OPTIONAL MATCH competitor = (root)-[:COMPETES_WITH]-(comp:Entity)
WHERE NOT 'Memory' IN labels(comp)

RETURN root.name AS entity,
       collect(DISTINCT {name: supplier.name, rel: 'supplier'}) AS suppliers,
       collect(DISTINCT {name: customer.name, rel: 'customer'}) AS customers,
       collect(DISTINCT {name: sub.name, rel: 'subsidiary'}) AS subsidiaries,
       collect(DISTINCT {name: p.name, rel: 'partner'}) AS partners,
       collect(DISTINCT {name: comp.name, rel: 'competitor'}) AS competitors
```

---

## P7: Knowledge Gaps（ナレッジギャップ）

**目的**: entity_type 別の Fact 密度を分析し、情報が不足しているセグメントを特定する。

### P7-a: entity_type 別 Fact 密度

```cypher
// entity_type ごとの平均 Fact 数を算出

MATCH (e:Entity)
WHERE NOT 'Memory' IN labels(e)

OPTIONAL MATCH (f:Fact)-[:RELATES_TO]->(e)

WITH e.entity_type AS entity_type,
     count(DISTINCT e) AS entity_count,
     count(DISTINCT f) AS total_facts

RETURN entity_type,
       entity_count,
       total_facts,
       toFloat(total_facts) / entity_count AS avg_facts_per_entity
ORDER BY avg_facts_per_entity ASC
```

### P7-b: 高プロファイル低カバレッジ Entity

```cypher
// Source で多く言及されるが Fact が少ない Entity
// =「注目度は高いが構造化知識が少ない」ギャップ

MATCH (e:Entity)
WHERE NOT 'Memory' IN labels(e)

// Source での言及数
OPTIONAL MATCH (content)-[:RELATES_TO|MENTIONS]->(e)
OPTIONAL MATCH (s:Source)-[:STATES_FACT|MAKES_CLAIM]->(content)
WITH e, count(DISTINCT s) AS mention_count

// Fact 数
OPTIONAL MATCH (f:Fact)-[:RELATES_TO]->(e)
WITH e, mention_count, count(DISTINCT f) AS fact_count

WHERE mention_count >= 3 AND fact_count <= 1

RETURN e.name AS entity,
       e.entity_type AS type,
       mention_count,
       fact_count,
       mention_count - fact_count AS gap_score
ORDER BY gap_score DESC
LIMIT 20
```

### P7-c: セクター別カバレッジヒートマップ

```cypher
// Sector ごとのコンテンツ密度（Fact + Claim + FDP）を算出

MATCH (sec:Sector)<-[:IN_SECTOR]-(e:Entity)
WHERE NOT 'Memory' IN labels(e)

OPTIONAL MATCH (f:Fact)-[:RELATES_TO]->(e)
OPTIONAL MATCH (c:Claim)-[:MENTIONS]->(e)
OPTIONAL MATCH (fdp:FinancialDataPoint)-[:RELATES_TO]-(e)

WITH sec,
     count(DISTINCT e) AS entity_count,
     count(DISTINCT f) AS fact_count,
     count(DISTINCT c) AS claim_count,
     count(DISTINCT fdp) AS fdp_count

RETURN sec.name AS sector,
       entity_count,
       fact_count,
       claim_count,
       fdp_count,
       toFloat(fact_count + claim_count + fdp_count) / entity_count AS content_density
ORDER BY content_density ASC
```

### P7-d: 未分類コンテンツ検出

```cypher
// ABOUT / RELATES_TO / MENTIONS が一切ない Fact / Claim

// 孤立 Fact
MATCH (f:Fact)
WHERE NOT (f)-[:ABOUT]->(:Topic)
AND NOT (f)-[:RELATES_TO]->(:Entity)
RETURN 'Fact' AS type,
       f.fact_id AS id,
       left(f.content, 150) AS content,
       'no_topic_no_entity' AS gap_type
LIMIT 20

UNION

// 孤立 Claim
MATCH (c:Claim)
WHERE NOT (c)-[:ABOUT]->(:Topic)
AND NOT (c)-[:MENTIONS]->(:Entity)
RETURN 'Claim' AS type,
       c.claim_id AS id,
       left(c.content, 150) AS content,
       'no_topic_no_entity' AS gap_type
LIMIT 20
```

---

## P8: Temporal Patterns（時系列パターン）

**目的**: FiscalPeriod 横断で複数 Entity の FinancialDataPoint トレンドを比較分析する。

### P8-a: 同一 Metric 複数 Entity 比較

```cypher
// パラメータ: $metric_name (例: "Revenue"), $entity_names (例: ["Apple", "Microsoft", "Google"])
// 同一指標で複数エンティティの時系列を比較

MATCH (fdp:FinancialDataPoint)-[:FOR_METRIC]->(m:Metric)
WHERE m.name = $metric_name

MATCH (fdp)-[:RELATES_TO]-(e:Entity)
WHERE e.name IN $entity_names
AND NOT 'Memory' IN labels(e)

MATCH (fdp)-[:FOR_PERIOD]->(fp:FiscalPeriod)

RETURN e.name AS entity,
       m.name AS metric,
       fp.year AS year,
       fp.quarter AS quarter,
       fdp.value AS value
ORDER BY e.name, fp.year, fp.quarter
```

### P8-b: FiscalPeriod カバレッジマトリクス

```cypher
// どの FiscalPeriod にどの Entity の FDP が存在するかのマトリクス

MATCH (fp:FiscalPeriod)

OPTIONAL MATCH (fdp:FinancialDataPoint)-[:FOR_PERIOD]->(fp)
OPTIONAL MATCH (fdp)-[:RELATES_TO]-(e:Entity)
WHERE NOT 'Memory' IN labels(e)

WITH fp, collect(DISTINCT e.name) AS entities, count(DISTINCT fdp) AS fdp_count

RETURN fp.period_id AS period,
       fp.year AS year,
       fp.quarter AS quarter,
       fp.type AS type,
       fdp_count,
       size(entities) AS entity_count,
       entities[..10] AS sample_entities
ORDER BY fp.year DESC, fp.quarter DESC
```

### P8-c: TREND チェーン断絶検出

```cypher
// TREND チェーンが途切れている FDP を検出
// = 時系列データの欠損ポイント

MATCH (fdp:FinancialDataPoint)-[:FOR_PERIOD]->(fp:FiscalPeriod)
WHERE NOT (fdp)-[:TREND]->(:FinancialDataPoint)

OPTIONAL MATCH (fp)-[:NEXT_PERIOD]->(next_fp:FiscalPeriod)
OPTIONAL MATCH (next_fdp:FinancialDataPoint)-[:FOR_PERIOD]->(next_fp)
OPTIONAL MATCH (fdp)-[:RELATES_TO]-(e:Entity)
OPTIONAL MATCH (fdp)-[:FOR_METRIC]->(m:Metric)

WHERE next_fp IS NOT NULL  // 次の期間が存在する場合のみ

RETURN e.name AS entity,
       m.name AS metric,
       fp.year AS current_year,
       fp.quarter AS current_quarter,
       fdp.value AS current_value,
       CASE WHEN next_fdp IS NOT NULL THEN 'gap_in_trend' ELSE 'no_next_fdp' END AS gap_type
ORDER BY e.name, m.name, fp.year, fp.quarter
LIMIT 50
```

### P8-d: 期間間成長率分析

```cypher
// TREND チェーンで前期比成長率を算出

MATCH (prev:FinancialDataPoint)-[:TREND]->(curr:FinancialDataPoint)

OPTIONAL MATCH (prev)-[:FOR_PERIOD]->(prev_fp:FiscalPeriod)
OPTIONAL MATCH (curr)-[:FOR_PERIOD]->(curr_fp:FiscalPeriod)
OPTIONAL MATCH (curr)-[:RELATES_TO]-(e:Entity)
OPTIONAL MATCH (curr)-[:FOR_METRIC]->(m:Metric)
WHERE NOT 'Memory' IN labels(e)

WITH e, m, prev, curr, prev_fp, curr_fp,
     CASE WHEN prev.value <> 0
       THEN (toFloat(curr.value) - prev.value) / abs(prev.value) * 100
       ELSE NULL
     END AS growth_rate

WHERE growth_rate IS NOT NULL

RETURN e.name AS entity,
       m.name AS metric,
       prev_fp.year AS prev_year,
       prev_fp.quarter AS prev_quarter,
       prev.value AS prev_value,
       curr_fp.year AS curr_year,
       curr_fp.quarter AS curr_quarter,
       curr.value AS curr_value,
       round(growth_rate, 2) AS growth_rate_pct
ORDER BY abs(growth_rate) DESC
LIMIT 30
```

---

## 付録: 発見クエリの活用パターン

### 日常分析での使い方

| 場面 | 推奨クエリ |
|------|-----------|
| 記事テーマ探索 | P1 (隠れた接続) + P2 (新興トピック) |
| 投資アイデア生成 | P3 (逆張りシグナル) + P5 (コンセンサス乖離) |
| セクター分析 | P4 (セクター横断影響) + P7-c (セクターカバレッジ) |
| 企業分析 | P6 (サプライチェーン) + P8 (時系列パターン) |
| KG改善 | P7 (ナレッジギャップ) + P8-c (TREND 断絶) |

### 組み合わせ例

1. **新しい記事テーマ発見**: P2-a (新興トピック) で成長率の高いトピックを特定 -> P1-c (Topic ブリッジ) でそのトピックに間接的に関連する Entity を発見 -> 記事の角度として活用

2. **投資判断サポート**: P5-a (コンセンサス) で意見が割れている Entity を特定 -> P3-b (矛盾 Claim) で論点を整理 -> P8-a (時系列比較) で定量データを確認

3. **ナレッジ拡充計画**: P7-a (Fact 密度) で不足セグメントを特定 -> P7-b (高プロファイル低カバレッジ) で優先的に調査すべき Entity を決定 -> web-research パイプラインで投入
