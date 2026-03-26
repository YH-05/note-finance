# 記事素材クエリ集（Phase F-1）

記事執筆時に creator-neo4j (bolt://localhost:7689) から素材を取得するための6クエリ。
`mcp__neo4j-creator__creator-read_neo4j_cypher` で実行する。

---

## Q1: テーマ×ジャンル → 素材一括取得

記事のテーマキーワードとジャンルを指定し、Fact/Tip/Story を混合取得。

```cypher
MATCH (content)-[:ABOUT]->(c:Concept)-[:IS_A]->(cc:ConceptCategory)
WHERE content.content CONTAINS $keyword OR c.name CONTAINS $keyword
MATCH (content)-[:IN_GENRE]->(g:Genre {genre_id: $genre})
OPTIONAL MATCH (content)-[:FROM_SOURCE]->(s:Source)
RETURN labels(content)[0] AS type, content.content AS text,
       c.name AS concept, cc.name AS category, s.url AS source_url
ORDER BY type, content.created_at DESC
LIMIT 15
```

パラメータ: `{keyword: "副業", genre: "career"}`

---

## Q2: ConceptCategory指定 → How層素材取得

記事に「説得テクニック」「感情フック」等のHow層要素を入れたい場合。

```cypher
MATCH (content)-[:ABOUT]->(c:Concept)-[:IS_A]->(cc:ConceptCategory {name: $category})
OPTIONAL MATCH (content)-[:IN_GENRE]->(g:Genre)
OPTIONAL MATCH (content)-[:FROM_SOURCE]->(s:Source)
RETURN labels(content)[0] AS type, content.content AS text,
       c.name AS concept, g.genre_id AS genre, s.url AS source
ORDER BY content.created_at DESC
LIMIT 10
```

パラメータ: `{category: "PersuasionTechnique"}` (or EmotionalHook/CopyFramework/Objection)

---

## Q3: Entity起点 → 関連コンテンツ取得

特定のプラットフォーム/企業に関する全素材を取得。

```cypher
MATCH (e:Entity {name: $entity_name})<-[:MENTIONS]-(content)
OPTIONAL MATCH (content)-[:ABOUT]->(c:Concept)
OPTIONAL MATCH (content)-[:IN_GENRE]->(g:Genre)
RETURN labels(content)[0] AS type, content.content AS text,
       collect(DISTINCT c.name)[0..3] AS concepts, g.genre_id AS genre
LIMIT 10
```

パラメータ: `{entity_name: "Instagram"}` (or Brain/IBJ/Tinder/ココナラ 等)

---

## Q4: Story（体験談）取得

記事の説得力を高めるための体験談を取得。

```cypher
MATCH (s:Story)-[:IN_GENRE]->(g:Genre {genre_id: $genre})
OPTIONAL MATCH (s)-[:ABOUT]->(c:Concept)
OPTIONAL MATCH (s)-[:FROM_SOURCE]->(src:Source)
WITH s, collect(DISTINCT c.name)[0..3] AS concepts, head(collect(DISTINCT src.url)) AS source
RETURN s.content AS text, s.outcome AS outcome, s.timeline AS timeline, concepts, source
ORDER BY s.created_at DESC
LIMIT 10
```

パラメータ: `{genre: "career"}` (or beauty-romance/spiritual)

---

## Q5: Concept間関係 → 記事の論理構成

ENABLES/REQUIRES/COMPETES_WITH の関係から記事の論理展開を設計。

```cypher
MATCH (c1:Concept)-[r]->(c2:Concept)
WHERE type(r) IN ['ENABLES', 'REQUIRES', 'COMPETES_WITH']
OPTIONAL MATCH (c1)-[:IS_A]->(cc1:ConceptCategory)
OPTIONAL MATCH (c2)-[:IS_A]->(cc2:ConceptCategory)
RETURN c1.name AS from_concept, type(r) AS relation, c2.name AS to_concept,
       cc1.name AS from_category, cc2.name AS to_category
LIMIT 20
```

活用例:
- ENABLES → 「AをすればBが可能になる」の因果関係で記事構成
- COMPETES_WITH → 比較記事の対立軸として活用
- REQUIRES → 前提条件として読者に提示

---

## Q6: クロスジャンルパターン発見

同じConceptが複数ジャンルに登場する＝ジャンル横断の普遍的パターン。
記事の説得力を高める「他業界でも同じ法則が成立」の根拠として使用。

```cypher
MATCH (c:Concept)<-[:ABOUT]-(content)-[:IN_GENRE]->(g:Genre)
WITH c, collect(DISTINCT g.genre_id) AS genres, count(DISTINCT content) AS content_count
WHERE size(genres) >= 2
RETURN c.name AS concept, genres, content_count
ORDER BY content_count DESC
LIMIT 20
```

活用例:
- 「Instagram」が career/beauty-romance/spiritual の全3ジャンルで40件
- → 「どの業界でもInstagram集客は必須」という普遍的主張の根拠に

---

## 使い方ガイド

### 記事執筆フロー

1. **テーマ決定** → Q1 でテーマに関する全素材を取得
2. **How層確認** → Q2 で使える説得テクニック・感情フックを取得
3. **体験談選定** → Q4 で記事に挿入する Story を選定
4. **データ裏付け** → Q1 の Fact から統計・数値データを抽出
5. **論理構成** → Q5 の Concept 間関係から記事の流れを設計
6. **差別化角度** → Q6 のクロスジャンルパターンで独自の切り口を発見

### article-research スキルとの連携

`/article-research` 実行時に、以下の順序で creator-neo4j を参照：
1. Q1 で既存素材を確認（既にある素材は再検索不要）
2. 不足している ConceptCategory を Q2 で特定
3. 不足分のみ Web 検索で補完
