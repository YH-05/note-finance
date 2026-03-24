---
name: creator-quality-check
description: |
  creator-neo4j (bolt://localhost:7689) のナレッジグラフ品質を計測・評価するスキル。
  7カテゴリの定量指標に加え、Claude Code 自身が LLM-as-Judge として
  Fact/Tip/Story のコンテンツ品質と Concept 分類の適切性を直接評価する。
  スナップショット保存・前回比較・Markdownレポート生成を一括で行う。
  「creator品質」「creator-neo4j品質」「クリエイター品質」「コンテンツ品質チェック」
  「creator KG品質」「Fact/Tip/Story品質」「概念分類品質」
  と言われたら必ずこのスキルを使うこと。
  Use PROACTIVELY when the user asks about creator-neo4j quality, content data quality,
  or after creator-enrichment bulk ingestion to verify quality.
---

# creator-quality-check

creator-neo4j (bolt://localhost:7689) のナレッジグラフ品質を計測し、
Claude Code が LLM-as-Judge として Fact/Tip/Story のコンテンツ品質と
Concept 分類の適切性を直接評価するスキル。

## 対象スキーマ

| ノード | 件数目安 | 主キー | 主リレーション |
|--------|---------|--------|---------------|
| Genre | 3（固定） | genre_id | ← IN_GENRE |
| Concept | ~3000+ | concept_id | ← ABOUT, → IS_A |
| ConceptCategory | ~14 | name | ← IS_A |
| Entity | ~500 | entity_id / entity_key | → SERVES_AS, → MENTIONS |
| Source | ~1000 | source_id / url | ← FROM_SOURCE, → FROM_DOMAIN |
| Fact | ~500+ | fact_id | → IN_GENRE, → ABOUT, → FROM_SOURCE, → MENTIONS |
| Tip | ~600+ | tip_id | → IN_GENRE, → ABOUT, → FROM_SOURCE, → MENTIONS |
| Story | ~200+ | story_id | → IN_GENRE, → ABOUT, → FROM_SOURCE, → MENTIONS |
| Domain | ~400+ | name | ← FROM_DOMAIN |

## 処理フロー

```
Phase 1: 7カテゴリ定量計測（Cypher プローブ）
    |  creator-neo4j から7カテゴリの指標を計測
    |  mcp__neo4j-creator__creator-read_neo4j_cypher を使用
    |
Phase 2: コンテンツ品質評価（LLM-as-Judge）
    |  Fact/Tip/Story をサンプリングし3軸で評価
    |  Concept → ConceptCategory の分類適切性を評価
    |
Phase 3: スナップショット保存・比較
    |  JSON スナップショットを保存
    |  前回スナップショットとの比較
    |
Phase 4: レポート出力
    定量スコア + コンテンツ品質評価 + 改善提案をユーザーに提示
```

## Phase 1: 7カテゴリ定量計測

全ての Cypher クエリは `mcp__neo4j-creator__creator-read_neo4j_cypher` で実行する（読み取りのみ）。

### 1.1 Completeness（完全性）— 重み 20%

各ノードタイプのプロパティ充填率を計測する。

**Fact の充填率**:

```cypher
MATCH (f:Fact)
RETURN
    count(f) AS total,
    count(f.fact_id) AS has_id,
    count(f.text) + count(f.content) AS has_text,
    count(f.category) AS has_category,
    count(f.confidence) AS has_confidence,
    count(f.genre) AS has_genre,
    count(f.source_url) AS has_source_url,
    count(f.created_at) AS has_created_at
```

**Tip の充填率**:

```cypher
MATCH (t:Tip)
RETURN
    count(t) AS total,
    count(t.tip_id) AS has_id,
    count(t.text) + count(t.content) AS has_text,
    count(t.category) AS has_category,
    count(t.difficulty) AS has_difficulty,
    count(t.genre) AS has_genre,
    count(t.source_url) AS has_source_url,
    count(t.created_at) AS has_created_at
```

**Story の充填率**:

```cypher
MATCH (s:Story)
RETURN
    count(s) AS total,
    count(s.story_id) AS has_id,
    count(s.text) + count(s.content) AS has_text,
    count(s.outcome) AS has_outcome,
    count(s.timeline) AS has_timeline,
    count(s.genre) AS has_genre,
    count(s.source_url) AS has_source_url,
    count(s.created_at) AS has_created_at
```

**Source の充填率**:

```cypher
MATCH (s:Source)
RETURN
    count(s) AS total,
    count(s.source_id) AS has_id,
    count(s.url) AS has_url,
    count(s.title) AS has_title,
    count(s.source_type) AS has_source_type,
    count(s.authority_level) AS has_authority_level,
    count(s.domain) AS has_domain,
    count(s.created_at) AS has_created_at
```

**Entity の充填率**:

```cypher
MATCH (e:Entity)
RETURN
    count(e) AS total,
    count(e.entity_id) AS has_id,
    count(e.entity_key) AS has_key,
    count(e.name) AS has_name,
    count(e.entity_type) AS has_type,
    count(e.created_at) AS has_created_at
```

**Concept の充填率**:

```cypher
MATCH (c:Concept)
RETURN
    count(c) AS total,
    count(c.concept_id) AS has_id,
    count(c.name) AS has_name,
    count(c.category) AS has_category,
    count(c.genre) AS has_genre,
    count(c.created_at) AS has_created_at
```

**スコア算出**:
- 必須プロパティ（id, text/content/name, url）: 重み 1.0
- 推奨プロパティ（category, genre, source_url, authority_level）: 重み 0.7
- 任意プロパティ（confidence, difficulty, timeline, outcome）: 重み 0.3
- スコア = 加重充填率の全ノードタイプ平均

### 1.2 Consistency（一貫性）— 重み 15%

ID フォーマット、genre 値、entity_type の妥当性を検証する。

**genre 値の検証**（Fact/Tip/Story の genre が Genre ノードに存在するか）:

```cypher
MATCH (g:Genre)
WITH collect(g.genre_id) AS valid_genres
MATCH (f)
WHERE (f:Fact OR f:Tip OR f:Story) AND f.genre IS NOT NULL
AND NOT f.genre IN valid_genres
RETURN labels(f)[0] AS node_type,
       f.genre AS invalid_genre,
       count(*) AS count
```

**entity_type の分布**（異常値検出）:

```cypher
MATCH (e:Entity)
WHERE e.entity_type IS NOT NULL
RETURN e.entity_type AS type, count(e) AS count
ORDER BY count DESC
```

**Source authority_level の検証**:

```cypher
MATCH (s:Source)
WHERE s.authority_level IS NOT NULL
AND NOT s.authority_level IN ['official', 'media', 'blog', 'social', 'academic']
RETURN s.authority_level AS invalid_level, count(*) AS count
```

**重複 ID 検出**:

```cypher
MATCH (e:Entity)
WITH e.entity_key AS key, collect(e) AS nodes
WHERE size(nodes) > 1
RETURN key, size(nodes) AS dup_count
LIMIT 10
```

**スコア算出**:
- 不正 genre 率 + 不正 authority_level 率 + 重複率の逆数の平均

### 1.3 Structural（構造）— 重み 15%

グラフ全体の構造統計を計測する。

**ノード・リレーション総数**:

```cypher
CALL apoc.meta.stats() YIELD nodeCount, relCount
RETURN nodeCount, relCount
```

**ノードタイプ別件数**:

```cypher
MATCH (n)
RETURN labels(n)[0] AS label, count(n) AS count
ORDER BY count DESC
```

**リレーションタイプ別件数**:

```cypher
MATCH ()-[r]->()
RETURN type(r) AS rel_type, count(r) AS count
ORDER BY count DESC
```

**コンテンツ（Fact/Tip/Story）あたりの平均リレーション数**:

```cypher
MATCH (c)
WHERE c:Fact OR c:Tip OR c:Story
OPTIONAL MATCH (c)-[r]->()
WITH c, count(r) AS rel_count
RETURN avg(rel_count) AS avg_rels,
       min(rel_count) AS min_rels,
       max(rel_count) AS max_rels,
       percentileCont(rel_count, 0.5) AS median_rels
```

**スコア算出**:
- 平均リレーション数が 2.0 以上で green（IN_GENRE + ABOUT + FROM_SOURCE が期待値）
- 1.0-2.0 で yellow、1.0 未満で red

### 1.4 Orphan Detection（孤立ノード）— 重み 15%

リレーションを持たないノードを検出する。

**孤立 Fact/Tip/Story**（IN_GENRE も ABOUT も FROM_SOURCE もない）:

```cypher
MATCH (c)
WHERE (c:Fact OR c:Tip OR c:Story)
AND NOT (c)-[:IN_GENRE]->()
AND NOT (c)-[:ABOUT]->()
AND NOT (c)-[:FROM_SOURCE]->()
RETURN labels(c)[0] AS type,
       coalesce(c.fact_id, c.tip_id, c.story_id) AS id,
       left(coalesce(c.text, c.content, ''), 80) AS text_preview
LIMIT 20
```

**孤立 Entity**（MENTIONS も SERVES_AS も RELATES_TO もない）:

```cypher
MATCH (e:Entity)
WHERE NOT (e)-[:MENTIONS]->() AND NOT (e)<-[:MENTIONS]-()
AND NOT (e)-[:SERVES_AS]->()
AND NOT (e)-[:RELATES_TO]-()
RETURN e.entity_id AS id, e.name AS name, e.entity_type AS type
LIMIT 20
```

**孤立 Concept**（ABOUT も IS_A もない）:

```cypher
MATCH (c:Concept)
WHERE NOT (c)<-[:ABOUT]-() AND NOT (c)-[:IS_A]->()
RETURN c.concept_id AS id, c.name AS name, c.category AS category
LIMIT 20
```

**孤立 Source**（FROM_SOURCE がない）:

```cypher
MATCH (s:Source)
WHERE NOT (s)<-[:FROM_SOURCE]-()
RETURN s.source_id AS id, s.title AS title, s.url AS url
LIMIT 20
```

**スコア算出**:
- 各ノードタイプの孤立率を算出
- スコア = 1.0 - (加重孤立率)
- コンテンツ（Fact/Tip/Story）の孤立は重み高（0.5）、その他は 0.5 を分配

### 1.5 Content Balance（コンテンツバランス）— 重み 10%

ジャンル別・タイプ別のコンテンツ分布を評価する。

**ジャンル別コンテンツ数**:

```cypher
MATCH (c)-[:IN_GENRE]->(g:Genre)
WHERE c:Fact OR c:Tip OR c:Story
RETURN g.genre_id AS genre, g.name AS genre_name,
       count(CASE WHEN c:Fact THEN 1 END) AS facts,
       count(CASE WHEN c:Tip THEN 1 END) AS tips,
       count(CASE WHEN c:Story THEN 1 END) AS stories,
       count(c) AS total
ORDER BY total DESC
```

**Concept あたりのコンテンツ数分布**:

```cypher
MATCH (concept:Concept)
OPTIONAL MATCH (content)-[:ABOUT]->(concept)
WHERE content:Fact OR content:Tip OR content:Story OR content:Source
WITH concept, count(content) AS content_count
RETURN
    avg(content_count) AS avg_per_concept,
    min(content_count) AS min_per_concept,
    max(content_count) AS max_per_concept,
    count(CASE WHEN content_count = 0 THEN 1 END) AS zero_content_concepts,
    count(concept) AS total_concepts
```

**スコア算出**:
- ジャンル間偏差: 最大ジャンルと最小ジャンルの比率が 3:1 以内で green
- Fact/Tip/Story 比率: 理想 40/35/25 からの乖離度
- zero_content_concepts の割合

### 1.6 Source Quality（ソース品質）— 重み 10%

ソースの多様性と品質を評価する。

**authority_level 分布**:

```cypher
MATCH (s:Source)
RETURN s.authority_level AS level, count(s) AS count
ORDER BY count DESC
```

**source_type 分布**:

```cypher
MATCH (s:Source)
RETURN s.source_type AS type, count(s) AS count
ORDER BY count DESC
```

**Domain 多様性（上位20ドメイン）**:

```cypher
MATCH (s:Source)-[:FROM_DOMAIN]->(d:Domain)
RETURN d.name AS domain, count(s) AS source_count
ORDER BY source_count DESC
LIMIT 20
```

**URL なし Source**:

```cypher
MATCH (s:Source)
WHERE s.url IS NULL OR s.url = ''
RETURN s.source_id AS id, s.title AS title
LIMIT 10
```

**スコア算出**:
- authority_level 充填率
- source_type 充填率
- URL 充填率
- ドメイン多様性（ユニークドメイン数 / Source 数）の目安: 0.3 以上で green

### 1.7 Taxonomy Quality（分類品質）— 重み 15%

Concept → ConceptCategory の分類構造を評価する。

**ConceptCategory 別 Concept 数**:

```cypher
MATCH (c:Concept)-[:IS_A]->(cc:ConceptCategory)
RETURN cc.name AS category, cc.name_ja AS category_ja, cc.layer AS layer,
       count(c) AS concept_count
ORDER BY concept_count DESC
```

**IS_A リレーションなしの Concept**:

```cypher
MATCH (c:Concept)
WHERE NOT (c)-[:IS_A]->()
RETURN c.concept_id AS id, c.name AS name, c.category AS category
LIMIT 20
```

**ABOUT リレーションなしの Concept（コンテンツ未接続）**:

```cypher
MATCH (c:Concept)
WHERE NOT (c)<-[:ABOUT]-()
RETURN c.concept_id AS id, c.name AS name, c.category AS category
LIMIT 20
```

**ConceptCategory 間のバランス**:
- 各 category の Concept 数が極端に偏っていないか
- layer 属性の分布

**スコア算出**:
- IS_A 接続率（Concept → ConceptCategory）
- ABOUT 接続率（コンテンツ → Concept）
- カテゴリ間バランス（CV: 変動係数が 1.5 以下で green）

## Phase 2: コンテンツ品質評価（LLM-as-Judge）

Claude Code が直接、Fact/Tip/Story と Concept 分類の品質を評価する。

### 2.1 Fact/Tip/Story サンプリング

`mcp__neo4j-creator__creator-read_neo4j_cypher` で各タイプ 5件、計15件をサンプリング:

```cypher
MATCH (c)
WHERE (c:Fact OR c:Tip OR c:Story)
AND (c.text IS NOT NULL OR c.content IS NOT NULL)
OPTIONAL MATCH (c)-[:FROM_SOURCE]->(s:Source)
OPTIONAL MATCH (c)-[:ABOUT]->(concept:Concept)
OPTIONAL MATCH (c)-[:IN_GENRE]->(g:Genre)
RETURN
    coalesce(c.fact_id, c.tip_id, c.story_id) AS content_id,
    labels(c)[0] AS content_type,
    coalesce(c.text, c.content) AS text,
    c.category AS category,
    g.name AS genre_name,
    s.title AS source_title,
    s.url AS source_url,
    s.authority_level AS source_authority,
    collect(DISTINCT concept.name)[..3] AS concepts
ORDER BY rand()
LIMIT 15
```

### 2.2 3軸評価

各 Fact/Tip/Story を以下の3軸で評価する（各 0.0-1.0）:

| 軸 | 重み | 評価基準 |
|---|---:|---|
| Content Quality | 40% | テキストが具体的で有用な情報を含むか。「○○です」のような曖昧な一文ではなく、読者が行動に移せる内容か |
| Source Grounding | 30% | Source ノードとリンクされているか。URL・タイトルが存在するか。authority_level が適切か |
| Classification Accuracy | 30% | 正しい Genre に分類されているか。紐付く Concept が内容と整合しているか |

**評価の目安**:
- **0.8-1.0**: 具体的で有用なコンテンツ、ソースリンクあり、分類適切
- **0.5-0.7**: まあまあ有用、ソース不明瞭、分類おおむね適切
- **0.2-0.4**: 曖昧・表面的、ソースなし、分類ミスの可能性
- **0.0-0.1**: ノイズ（HTML断片・広告文・意味不明テキスト）

### 2.3 Concept 分類サンプリングと評価

IS_A リレーションを持つ Concept を10件サンプリングし、分類の適切性を評価:

```cypher
MATCH (c:Concept)-[:IS_A]->(cc:ConceptCategory)
OPTIONAL MATCH (content)-[:ABOUT]->(c)
WHERE content:Fact OR content:Tip OR content:Story
WITH c, cc, collect(DISTINCT left(coalesce(content.text, content.content, ''), 100))[..2] AS sample_content
RETURN c.name AS concept_name,
       c.category AS concept_category,
       cc.name AS assigned_category,
       cc.name_ja AS assigned_category_ja,
       cc.layer AS category_layer,
       sample_content
ORDER BY rand()
LIMIT 10
```

| 軸 | 評価基準 |
|---|---|
| Category Fit | Concept の name が ConceptCategory（IS_A先）の意味的カテゴリに適合しているか |
| Content Alignment | ABOUT で紐付くコンテンツが Concept の意味と整合しているか |

### 2.4 キャッシュ書き込み

評価結果を `data/processed/creator_quality/content_quality_cache.json` に保存:

```python
import json, hashlib
from datetime import datetime, timezone
from pathlib import Path

def content_hash(c):
    return hashlib.sha256(c.encode('utf-8')).hexdigest()[:16]

cache = {}
now = datetime.now(tz=timezone.utc).isoformat()
for item in evaluated_items:
    key = content_hash(item['text'])
    overall = item['cq'] * 0.4 + item['sg'] * 0.3 + item['ca'] * 0.3
    cache[key] = {
        'content_id': item['content_id'],
        'content_type': item['content_type'],
        'content_quality': item['cq'],
        'source_grounding': item['sg'],
        'classification_accuracy': item['ca'],
        'overall': round(overall, 3),
        'reasoning': item['reasoning'],
        'evaluated_at': now,
    }

p = Path('data/processed/creator_quality/content_quality_cache.json')
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
```

Bash ツールで Python ワンライナーとして実行する。

## Phase 3: スナップショット保存・比較

### 3.1 スナップショット保存

全カテゴリのスコアを `data/processed/creator_quality/snapshot_YYYYMMDD.json` に保存:

```json
{
  "timestamp": "2026-03-24T...",
  "node_counts": {
    "Genre": 3,
    "Concept": 3374,
    "ConceptCategory": 14,
    "Entity": 480,
    "Source": 982,
    "Fact": 538,
    "Tip": 589,
    "Story": 177,
    "Domain": 424
  },
  "categories": {
    "completeness": {"score": 85.0, "details": {}},
    "consistency": {"score": 90.0, "details": {}},
    "structural": {"score": 75.0, "details": {}},
    "orphan": {"score": 80.0, "details": {}},
    "content_balance": {"score": 70.0, "details": {}},
    "source_quality": {"score": 85.0, "details": {}},
    "taxonomy": {"score": 78.0, "details": {}}
  },
  "llm_judge": {
    "content_quality_avg": 0.72,
    "concept_classification_avg": 0.80,
    "sample_size": 15
  },
  "overall_score": 79.5,
  "rating": "B"
}
```

### 3.2 前回比較

前回スナップショットが `data/processed/creator_quality/` に存在する場合、各カテゴリの差分を算出する。

## Phase 4: レポート出力

以下の Markdown 形式でユーザーに提示する:

```markdown
## creator-neo4j 品質チェックレポート

**計測日時**: YYYY-MM-DD HH:MM
**ノード総数**: X,XXX（Genre 3 / Concept X,XXX / Entity XXX / Source XXX / Fact XXX / Tip XXX / Story XXX / Domain XXX / ConceptCategory XX）

### 1. Completeness（完全性）スコア: XX% [重み 20%]

| ノードタイプ | プロパティ | 充填数/総数 | 充填率 | 重要度 |
|-------------|-----------|------------|--------|--------|
| Fact | fact_id | XX/XX | 100% | 必須 |
| Fact | text/content | XX/XX | XX% | 必須 |
...

### 2. Consistency（一貫性）スコア: XX% [重み 15%]

- 不正 genre 値: N件
- 不正 authority_level: N件
- 重複 entity_key: N件

### 3. Structural（構造）スコア: XX% [重み 15%]

- ノード総数: X,XXX
- リレーション総数: X,XXX
- コンテンツあたり平均リレーション数: X.X

### 4. 孤立ノード スコア: XX% [重み 15%]

- 孤立 Fact/Tip/Story: N件
- 孤立 Entity: N件
- 孤立 Concept: N件
- 孤立 Source: N件

### 5. Content Balance（コンテンツバランス）スコア: XX% [重み 10%]

| Genre | Fact | Tip | Story | 合計 | Fact% | Tip% | Story% |
|-------|------|-----|-------|------|-------|------|--------|
| career | XX | XX | XX | XX | XX% | XX% | XX% |
...

理想バランス: Fact 40% / Tip 35% / Story 25%

### 6. Source Quality（ソース品質）スコア: XX% [重み 10%]

- authority_level 充填率: XX%
- source_type 充填率: XX%
- ユニークドメイン数: XXX
- URL なし Source: N件

### 7. Taxonomy Quality（分類品質）スコア: XX% [重み 15%]

- IS_A 接続率: XX%（X,XXX / X,XXX Concepts）
- ABOUT 接続率: XX%
- ConceptCategory 別 Concept 数: [テーブル]

### 8. コンテンツ品質評価（LLM-as-Judge）

| Content ID | Type | Content Quality | Source Grounding | Classification | 総合 | 備考 |
|-----------|------|----------------|-----------------|----------------|------|------|
| fact-xxxx | Fact | 0.8 | 0.7 | 0.9 | 0.80 | - |
...

平均スコア: X.XX

#### Concept 分類評価

| Concept | 割当カテゴリ | Category Fit | Content Alignment | 備考 |
|---------|------------|-------------|-------------------|------|
...

### 総合スコア: XX/100（Rating: X）

| カテゴリ | スコア | 重み | 加重スコア |
|---------|--------|------|-----------|
| Completeness | XX% | 20% | XX |
| Consistency | XX% | 15% | XX |
| Structural | XX% | 15% | XX |
| Orphan | XX% | 15% | XX |
| Content Balance | XX% | 10% | XX |
| Source Quality | XX% | 10% | XX |
| Taxonomy | XX% | 15% | XX |

**Rating**: A (90+) / B (75-89) / C (60-74) / D (<60)

### 前回比較（該当する場合）

| カテゴリ | 前回 | 今回 | 差分 |
|---------|------|------|------|
...

### 改善提案

1. [優先度: 高] ...
2. [優先度: 中] ...
3. [優先度: 低] ...
```

## 使用する MCP ツール

| MCP ツール | 用途 |
|-----------|------|
| `mcp__neo4j-creator__creator-read_neo4j_cypher` | 全ての Cypher プローブ（読み取りのみ） |
| `mcp__neo4j-creator__creator-get_neo4j_schema` | 実行前のスキーマ確認（推奨） |

**注意**: `mcp__neo4j-creator__creator-write_neo4j_cypher` は一切使用しない。

## 関連ファイル

| ファイル | 説明 |
|---------|------|
| `.claude/commands/creator-quality-check.md` | スラッシュコマンド |
| `.claude/skills/kg-quality-check/SKILL.md` | research-neo4j 用の品質チェック（参考） |
| `.claude/skills/note-quality-check/SKILL.md` | note-neo4j 用の品質チェック（参考） |
| `data/processed/creator_quality/` | スナップショット・キャッシュ保存先（必要に応じて作成） |

## MUST / SHOULD / NEVER

### MUST

- Phase 1 の7カテゴリ全ての Cypher プローブを実行すること
- Phase 2 の LLM-as-Judge 評価を Fact/Tip/Story と Concept 分類の両方に実施すること
- 全ての Cypher は `mcp__neo4j-creator__creator-read_neo4j_cypher` で実行すること
- レポートに総合スコア（100点満点）と Rating（A/B/C/D）を算出すること
- 問題が見つかった場合は具体的な改善提案を含めること
- 評価結果をキャッシュファイルに書き込み、スナップショットとして保存すること

### SHOULD

- 各カテゴリでスコアが低い（50%未満）場合は警告マーク付きで報告すること
- 前回スナップショットが存在する場合は比較を行うこと
- 改善提案に優先度（高/中/低）を付けること
- ノイズデータ（HTML断片・広告文等）を特記すること
- Genre 間のコンテンツ偏りが大きい場合は enrichment の優先ジャンルを提案すること

### NEVER

- `mcp__neo4j-creator__creator-write_neo4j_cypher` を使用してはならない（読み取り専用）
- research-neo4j (port 7688) や note-neo4j (port 7687) のツールを使用してはならない
- データを修正してはならない（検出と報告のみ）
- ANTHROPIC_API_KEY に依存する API 呼び出しを行ってはならない

## 完了条件

- [ ] 7カテゴリの Cypher プローブが全て実行されている
- [ ] LLM-as-Judge によるコンテンツ品質評価が実施されている
- [ ] LLM-as-Judge による Concept 分類評価が実施されている
- [ ] 総合スコア（100点満点）と Rating が算出されている
- [ ] スナップショット JSON が保存されている
- [ ] 問題点と改善提案を含む Markdown レポートがユーザーに提示されている
