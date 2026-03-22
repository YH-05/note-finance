# Gap Analysis Queries

creator-neo4j のギャップ分析に使用する4つの Cypher クエリ。
全クエリは `mcp__neo4j-creator__creator-read_neo4j_cypher` で実行する。

---

## Q1: ジャンル別コンテンツ数（ローテーション用）

ジャンルごとのコンテンツ総数を取得し、ローテーション優先度の算出に使用する。

```cypher
MATCH (c:Content)
RETURN c.genre AS genre, count(c) AS content_count
ORDER BY content_count ASC
```

### 用途

- `priority_score = 1.0 / (content_count + 1)` で優先度を算出
- 前回と同じジャンルの場合はダンピング係数 `×0.7` を適用
- content_count が少ないジャンルほど高優先度

---

## Q2: コンテンツタイプバランス（Fact / Tip / Story）

各ジャンル内の Fact / Tip / Story の分布を取得する。

```cypher
MATCH (c:Content)
RETURN c.genre AS genre,
       c.content_type AS content_type,
       count(c) AS type_count
ORDER BY genre, content_type
```

### 用途

- 不足しているコンテンツタイプを特定
- 検索クエリの方向性を調整（例: Story が少なければ体験談系クエリを優先）
- 理想バランス目安: Fact 40% / Tip 35% / Story 25%

---

## Q3: 低カバレッジトピック TOP 10

Entity との接続数が少ないトピック（＝深掘りが不足しているトピック）を特定する。

```cypher
MATCH (c:Content)
WITH c.topic AS topic, c.genre AS genre, count(c) AS content_count
OPTIONAL MATCH (c2:Content {topic: topic})-[:MENTIONS]->(e:Entity)
WITH topic, genre, content_count, count(DISTINCT e) AS entity_count
RETURN topic, genre, content_count, entity_count,
       content_count + entity_count AS coverage_score
ORDER BY coverage_score ASC
LIMIT 10
```

### 用途

- 検索クエリの `{topic}` プレースホルダーに使用するトピックを選定
- coverage_score が低い = 深掘りが不足 = 優先的に検索すべき
- ジャンル横断で最もカバレッジが低いトピックを選ぶ

---

## Q4: 既存コンテンツサンプル（重複排除用）

直近投入されたコンテンツの title と source_url を取得し、重複排除に使用する。

```cypher
MATCH (c:Content)
WHERE c.created_at >= datetime() - duration('P7D')
RETURN c.title AS title,
       c.source_url AS source_url,
       c.genre AS genre,
       c.content_type AS content_type
ORDER BY c.created_at DESC
LIMIT 50
```

### 用途

- 検索結果と既存コンテンツの source_url を照合し、重複を排除
- title の類似度チェック（完全一致 + 部分一致）で同一トピックの重複投入を防止
- 直近7日間・最大50件で十分な重複検出が可能

---

## 実行順序

Phase 1 では以下の順序で実行する:

1. **Q1** → ジャンル選択（ローテーション）
2. **Q2** → 不足コンテンツタイプの特定
3. **Q3** → 検索トピックの選定
4. **Q4** → 重複排除リストの構築

Q1 の結果でジャンルが確定した後、Q2-Q4 は並列実行可能。
