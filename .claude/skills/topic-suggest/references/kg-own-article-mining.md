# 自記事 KG マイニングリファレンス

株投資ラボ自身のnote記事（research-neo4j に投入済み、`source_type='blog'` ＋ `command_source='own-articles'` で識別）を対象とした、トピック発掘用 Cypher クエリ集。

## 前提

`scripts/emit_own_articles_queue.py` で投入された `Source` ノード（58件以上）が存在することが前提。投入されていない場合は OWN-Q* クエリは空結果を返す。

`mcp__neo4j-research__research-read_neo4j_cypher` で実行する（読み取り専用）。

## 識別子

| 用途 | 述語 |
|------|------|
| 自記事の Source 識別 | `s:Source AND s.command_source = 'own-articles'` |
| 公開済み記事のみ | `s.status = 'published'` |
| 特定カテゴリ | `s.category = 'macro_economy'` 等 |

## OWN-Q1: 自分が言及した未深掘り Entity（カバレッジ薄）

自記事から関連付けされている Entity のうち、Fact/Claim が少ない＝深掘り余地のあるエンティティを抽出。

```cypher
MATCH (s:Source {command_source: 'own-articles'})
OPTIONAL MATCH (s)-[:RELATES_TO]->(e)
WHERE (e:Company OR e:Technology OR e:Organization OR e:Person
    OR e:MarketIndex OR e:Indicator OR e:Instrument OR e:Commodity
    OR e:Country OR e:Concept OR e:Regulation OR e:Broker OR e:Product)
  AND NOT 'Memory' IN labels(e)
WITH e, count(DISTINCT s) AS own_mentions
WHERE own_mentions >= 1
OPTIONAL MATCH (f:Fact)-[:RELATES_TO]->(e)
OPTIONAL MATCH (c:Claim)-[:RELATES_TO]->(e)
WITH e, own_mentions,
     count(DISTINCT f) AS fact_count,
     count(DISTINCT c) AS claim_count
WHERE fact_count + claim_count < 3
RETURN e.name AS entity,
       labels(e) AS labels,
       own_mentions,
       fact_count,
       claim_count,
       own_mentions * 5 + (3 - fact_count - claim_count) AS gap_score
ORDER BY gap_score DESC
LIMIT 15
```

→ **Underexplored Own-Mentioned Entity**: 自分が触れたが深掘りしていないテーマ。続編記事のチャンス。

## OWN-Q2: 自分のカテゴリ別カバレッジ vs 外部 Source

自分の記事数と、各カテゴリで外部 Source がどれだけあるかを比較。外部 Source 多 vs 自記事少の領域は「外部資料は豊富なのに自分は書いていない」ギャップ。

```cypher
MATCH (own:Source {command_source: 'own-articles'})
WITH own.category AS category, count(*) AS own_count
WITH collect({category: category, own_count: own_count}) AS own_stats

MATCH (ext:Source)
WHERE ext.command_source <> 'own-articles' OR ext.command_source IS NULL
WITH own_stats, ext.category AS category, count(*) AS ext_count
WHERE category IS NOT NULL AND category <> ''

WITH category, ext_count, own_stats,
     [s IN own_stats WHERE s.category = category | s.own_count] AS matched
WITH category,
     ext_count,
     CASE WHEN size(matched) > 0 THEN matched[0] ELSE 0 END AS own_count
WHERE ext_count >= 5
RETURN category,
       own_count,
       ext_count,
       toFloat(ext_count) / (own_count + 1) AS coverage_gap_ratio
ORDER BY coverage_gap_ratio DESC
LIMIT 10
```

→ **Coverage Gap Category**: 外部資料量に対して自分の発信が薄いカテゴリ。

## OWN-Q3: 自分の Claim と外部 Claim の対立検出

自分が記事内で表明した Claim と、外部 Source の Claim が同一 Entity に対して対立しているケースを抽出。

```cypher
MATCH (own:Source {command_source: 'own-articles'})-[:STATES_FACT|MAKES_CLAIM]->(own_claim:Claim)-[:RELATES_TO]->(e)
WHERE (e:Company OR e:Technology OR e:Organization OR e:Person
    OR e:MarketIndex OR e:Indicator OR e:Instrument OR e:Commodity
    OR e:Country OR e:Concept OR e:Regulation OR e:Broker OR e:Product)
  AND own_claim.sentiment IN ['bullish', 'bearish']
MATCH (ext:Source)-[:MAKES_CLAIM]->(ext_claim:Claim)-[:RELATES_TO]->(e)
WHERE ext.command_source <> 'own-articles' OR ext.command_source IS NULL
  AND ext_claim.sentiment IN ['bullish', 'bearish']
  AND ext_claim.sentiment <> own_claim.sentiment
RETURN e.name AS entity,
       own_claim.content AS my_view,
       own_claim.sentiment AS my_sentiment,
       ext_claim.content AS counter_view,
       ext_claim.sentiment AS counter_sentiment,
       ext.title AS counter_source
LIMIT 10
```

→ **Counter-Claim Topic**: 自説への反論記事 or 自説の検証記事のチャンス。

## OWN-Q4 (補助): 自記事の鮮度別一覧

直近の記事を特定して、続編・補完テーマを発掘するための補助クエリ。

```cypher
MATCH (s:Source {command_source: 'own-articles'})
WHERE s.published IS NOT NULL
RETURN s.title AS title,
       s.category AS category,
       s.published AS published,
       s.status AS status,
       s.target_audience AS audience
ORDER BY s.published DESC
LIMIT 20
```

## OWN-Q5 (補助): 同カテゴリ内で重複する Entity の検出

同じ Entity を複数の自記事で触れている場合、深掘りシリーズ化の余地。

```cypher
MATCH (s:Source {command_source: 'own-articles'})-[:RELATES_TO]->(e)
WHERE (e:Company OR e:Technology OR e:Organization OR e:Person
    OR e:MarketIndex OR e:Indicator OR e:Instrument OR e:Commodity
    OR e:Country OR e:Concept OR e:Regulation OR e:Broker OR e:Product)
WITH e, collect(DISTINCT s.title) AS titles, count(DISTINCT s) AS mentions
WHERE mentions >= 2
RETURN e.name AS entity,
       labels(e) AS labels,
       mentions,
       titles
ORDER BY mentions DESC
LIMIT 15
```

→ **Recurring Own Entity**: シリーズ化候補。

## トピック候補生成ロジック

| クエリ | 候補種別 | 提案文テンプレート |
|--------|---------|------------------|
| OWN-Q1 | Underexplored Own-Mentioned | "{entity} の最新動向と詳細分析（過去記事の深掘り）" |
| OWN-Q2 | Coverage Gap Category | "{category} カテゴリ最新まとめ（外部 {ext_count} ソースの集約）" |
| OWN-Q3 | Counter-Claim | "{entity} 議論：私の {my_sentiment} 見立て vs 外部の {counter_sentiment}" |
| OWN-Q5 | Recurring Series | "{entity} 第 {n+1} 回：シリーズ深掘り" |

各候補に `kg_gap_score` (0-10) を付与:

- OWN-Q1: `min(10, own_mentions * 3 + (3 - fact_count - claim_count))`
- OWN-Q2: `min(10, int(coverage_gap_ratio * 2))`
- OWN-Q3: 8（対立は記事価値高）
- OWN-Q5: `min(10, mentions + 4)`

## 関連ファイル

| リソース | パス |
|---------|------|
| 一般 KG マイニング | `kg-topic-mining.md` |
| 投入スクリプト | `scripts/emit_own_articles_queue.py` |
| 投入マッパー | `scripts/mappers/own_articles.py` |
| 設計メモ | `docs/plan/2026-04-27_own-articles-research-neo4j-pipeline.md` |
