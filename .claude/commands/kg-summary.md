---
description: トピックのKGアセット（Fact/Claim/Source件数・鮮度・未回答Question）をCypherで即時照会します。LLM不使用。
argument-hint: [@<article_dir> | --topic <keyword>]
---

research-neo4j に蓄積されたトピック関連データを即時照会します。
**LLMは一切使用しません（Cypherクエリのみ）。**

## 入力パラメータ

| パラメータ | 必須 | 説明 |
|-----------|------|------|
| @article_dir | ○※ | 記事ディレクトリ（meta.yamlからキーワード抽出） |
| --topic `<keyword>` | ○※ | 検索キーワード（直接指定、スペース区切りで複数可） |

※ いずれか1つを指定

## 処理フロー

### Step 1: キーワード抽出

**`@article_dir` 指定時**:
- `meta.yaml` の `topic` フィールドからキーワードを2-4語抽出
- `symbols` があれば各シンボルをキーワードに追加（例: `TSLA` → `"Tesla"` で照会）
- `fred_series` があれば各指標をキーワードに追加

**`--topic` 指定時**:
- 引数をそのままキーワードとして使用

### Step 2: Cypherクエリ実行（5クエリ）

`mcp__neo4j-research__research-read_neo4j_cypher` を ToolSearch でロードして実行。
各キーワードについてQ1-Q5を実行する。

**Q1: Entity・Fact・Claim・Source件数**

```cypher
MATCH (e)
WHERE (e:Company OR e:Technology OR e:Organization OR e:Person
    OR e:MarketIndex OR e:Indicator OR e:Instrument OR e:Commodity
    OR e:Country OR e:Concept OR e:Regulation OR e:Broker OR e:Product)
  AND e.name CONTAINS $keyword
OPTIONAL MATCH (f:Fact)-[:RELATES_TO]->(e)
OPTIONAL MATCH (c:Claim)-[:RELATES_TO]->(e)
OPTIONAL MATCH (s:Source)-[:RELATES_TO]->(e)
RETURN e.name AS entity,
       [l IN labels(e) WHERE l <> 'Memory'][0] AS type,
       count(DISTINCT f) AS facts,
       count(DISTINCT c) AS claims,
       count(DISTINCT s) AS sources
ORDER BY facts + claims DESC
LIMIT 10
```

**Q2: ソース鮮度**

```cypher
MATCH (s:Source)-[:RELATES_TO]->(e)
WHERE (e:Company OR e:Technology OR e:Organization OR e:Person
    OR e:MarketIndex OR e:Indicator OR e:Instrument OR e:Commodity
    OR e:Country OR e:Concept OR e:Regulation OR e:Broker OR e:Product)
  AND e.name CONTAINS $keyword
RETURN max(s.published_at) AS latest_source,
       count(DISTINCT s) AS total_sources
```

**Q3: 未回答Question**

```cypher
MATCH (q:Question)-[:ASKS_ABOUT]->(t:Topic)
WHERE t.name CONTAINS $keyword
  AND q.status IN ['open', 'investigating']
RETURN count(q) AS open_questions,
       collect(q.content)[0..3] AS sample_questions
```

**Q4: Claimセンチメント分布**

```cypher
MATCH (c:Claim)-[:RELATES_TO]->(e)
WHERE (e:Company OR e:Technology OR e:Organization OR e:Person
    OR e:MarketIndex OR e:Indicator OR e:Instrument OR e:Commodity
    OR e:Country OR e:Concept OR e:Regulation OR e:Broker OR e:Product)
  AND e.name CONTAINS $keyword
RETURN c.sentiment AS sentiment,
       count(c) AS count
ORDER BY count DESC
```

**Q5: FinancialDataPoint（Company/Instrument/MarketIndex のみ）**

```cypher
MATCH (e)
WHERE (e:Company OR e:Instrument OR e:MarketIndex)
  AND e.name CONTAINS $keyword
OPTIONAL MATCH (fdp:FinancialDataPoint)-[:RELATES_TO]->(e)
RETURN e.name AS entity,
       count(DISTINCT fdp) AS fdp_count,
       max(fdp.as_of_date) AS latest_fdp
```

### Step 3: 結果表示

クエリ結果をそのまま整形して表示（LLM生成テキストなし）:

```
## KGサマリー: {keyword}
照会日時: {YYYY-MM-DD HH:MM}

### エンティティ別アセット
| Entity | Type | Fact | Claim | Source |
|--------|------|------|-------|--------|
| {name} | {type} | {n} | {n} | {n} |

### データ鮮度
- 最新ソース: {date}（{N}日前）
- 総ソース数: {n}件

### Claimセンチメント
- bullish: {n}件 / bearish: {n}件 / neutral: {n}件

### 未回答Question: {n}件
{- 質問内容（最大3件）}

### FinancialDataPoint
- {entity}: {n}件（最新: {date}）

---

### 判定サマリー
✓ リサーチ不要: Fact {n}件・Claim {n}件・最新ソース {N}日前
⚠ 追加推奨: {理由（例: 最新ソースが30日超 / Fact 5件未満 / Question残存）}
```

**判定ロジック（LLMなし、単純閾値）**:

| 条件 | 表示 |
|------|------|
| max(published_at) < today - 30日 | ⚠ データが古い（最新: {date}） |
| facts + claims < 5 | ⚠ KGカバレッジ薄（Fact+Claim: {n}件） |
| open_questions > 0 | ⚠ 未回答Question {n}件あり |
| 全条件クリア | ✓ KGに十分なデータあり |

**Neo4j未起動時**: 以下を表示してスキップ:

```
⚠ KGサマリーをスキップ: research-neo4j（bolt://localhost:7688）に接続できません
  Neo4j起動後に再実行: /kg-summary @{article_dir}
```

## 出力

コンソール表示のみ。ファイルへの保存・LLM呼び出しなし。

## 使用例

```bash
# 記事ディレクトリを指定
/kg-summary @articles/stock_analysis/2026-03-15_tsla-earnings-analysis/

# キーワード直接指定
/kg-summary --topic 日銀

# 複数キーワード
/kg-summary --topic "テスラ TSLA EV"
```

## 関連コマンド

- `/article-init` — 完了時に自動実行（Phase 5）
- `/article-research` — リサーチ実行（Step 0で同様のKG照会を実施）
- `topic-suggest` スキル — トピック提案（旧 `/topic-discovery` は廃止）
