# Gap Analysis Queries v2

ConceptCategory ベースのギャップ分析。14カテゴリ × 3ジャンルのカバレッジに基づいて検索戦略を決定する。

---

## Q1: ジャンル別コンテンツ数（ローテーション用）

```cypher
MATCH (g:Genre)
OPTIONAL MATCH (content)-[:IN_GENRE]->(g) WHERE content:Fact OR content:Tip OR content:Story
RETURN g.genre_id AS genre, g.name AS name, count(DISTINCT content) AS content_count
ORDER BY content_count ASC
```

---

## Q2: ConceptCategory × ジャンル カバレッジマトリクス

```cypher
MATCH (cc:ConceptCategory)
OPTIONAL MATCH (content)-[:ABOUT]->(concept:Concept)-[:IS_A]->(cc)
WHERE content:Fact OR content:Tip OR content:Story
OPTIONAL MATCH (content)-[:IN_GENRE]->(g:Genre)
WITH cc.name AS category, cc.layer AS layer,
     g.genre_id AS genre, count(DISTINCT content) AS contents
RETURN category, layer, genre, contents
ORDER BY layer, category, genre
```

用途: How 層のギャップ（EmotionalHook/CopyFramework/Objection がほぼ空）を検出し、検索クエリの方向性を調整。

---

## Q3: 低カバレッジ ConceptCategory TOP 5

```cypher
MATCH (cc:ConceptCategory)
OPTIONAL MATCH (concept:Concept)-[:IS_A]->(cc)
OPTIONAL MATCH (content)-[:ABOUT]->(concept) WHERE content:Fact OR content:Tip OR content:Story
WITH cc.name AS category, cc.name_ja AS name_ja, cc.layer AS layer,
     count(DISTINCT concept) AS concept_count, count(DISTINCT content) AS content_count
RETURN category, name_ja, layer, concept_count, content_count
ORDER BY content_count ASC
LIMIT 5
```

用途: enrichment の検索方向を決定。content_count が少ないカテゴリの関連キーワードで検索する。

---

## Q4: 低カバレッジ Concept TOP 10（選択ジャンル内）

```cypher
MATCH (concept:Concept)-[:IS_A]->(cc:ConceptCategory)
OPTIONAL MATCH (content)-[:ABOUT]->(concept)
WHERE (content:Fact OR content:Tip OR content:Story)
OPTIONAL MATCH (content)-[:IN_GENRE]->(g:Genre {genre_id: $genre_id})
WITH concept.name AS name, cc.name AS category,
     count(DISTINCT content) AS content_count
RETURN name, category, content_count
ORDER BY content_count ASC
LIMIT 10
```

---

## Q5: 既存コンテンツサンプル（重複排除用）

```cypher
MATCH (c)
WHERE (c:Fact OR c:Tip OR c:Story) AND c.created_at >= datetime() - duration('P7D')
OPTIONAL MATCH (c)-[:FROM_SOURCE]->(s:Source)
RETURN c.text AS text, s.url AS source_url,
       labels(c)[0] AS content_type
ORDER BY c.created_at DESC
LIMIT 50
```

---

## Q6: Entity の SERVES_AS 接続率

```cypher
MATCH (e:Entity)
OPTIONAL MATCH (e)-[:SERVES_AS]->()
WITH e, count(*) > 0 AS has_serves_as
RETURN count(e) AS total,
       sum(CASE WHEN has_serves_as THEN 1 ELSE 0 END) AS with_role,
       sum(CASE WHEN NOT has_serves_as THEN 1 ELSE 0 END) AS without_role
```

---

## 実行順序

1. **Q1** → ジャンル選択（ローテーション）
2. **Q2** → ConceptCategory のギャップ特定 → 検索キーワード方向の決定
3. **Q3** → 重点拡充カテゴリの選択
4. **Q4** → 具体的な検索トピック選定
5. **Q5** → 重複排除リスト構築
6. **Q6** → Entity の役割接続状況（SERVES_AS 拡充判断）

Q1 でジャンルが確定した後、Q2-Q6 は並列実行可能。
