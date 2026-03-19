# KG ギャップ分析リファレンス

research-neo4j（bolt://localhost:7688）から既存データを照会し、情報ギャップを特定するためのCypherクエリテンプレート集。

## 使用タイミング

article-research の Phase 0（KG照会+ギャップ分析）で使用する。
`mcp__neo4j-research__research-read_neo4j_cypher` で実行すること（読み取り専用）。

## Phase 0-A: 既存データ照会

### Q1: トピックに関連するEntity・Fact・Claimの概要

テーマのキーワードから関連ノードを探索し、既存の知識量を把握する。

```cypher
// テーマキーワードで Entity を検索（部分一致）
MATCH (e:Entity)
WHERE e.name CONTAINS $keyword OR any(a IN coalesce(e.aliases, []) WHERE a CONTAINS $keyword)
WITH e
OPTIONAL MATCH (f:Fact)-[:RELATES_TO]->(e)
OPTIONAL MATCH (c:Claim)-[:ABOUT]->(e)
OPTIONAL MATCH (s:Source)-[:MENTIONS]->(e)
RETURN e.name AS entity,
       e.entity_type AS type,
       count(DISTINCT f) AS fact_count,
       count(DISTINCT c) AS claim_count,
       count(DISTINCT s) AS source_count
ORDER BY fact_count + claim_count DESC
LIMIT 20
```

パラメータ: `$keyword` = テーマから抽出したキーワード（例: "日銀", "BOJ", "NVIDIA"）

### Q2: 関連Topicとそのカバレッジ

```cypher
// テーマに関連する Topic ノードを検索
MATCH (t:Topic)
WHERE t.name CONTAINS $keyword
WITH t
OPTIONAL MATCH (s:Source)-[:TAGGED]->(t)
OPTIONAL MATCH (c:Claim)-[:TAGGED]->(t)
OPTIONAL MATCH (ins:Insight)-[:TAGGED]->(t)
RETURN t.name AS topic,
       t.category AS category,
       count(DISTINCT s) AS source_count,
       count(DISTINCT c) AS claim_count,
       count(DISTINCT ins) AS insight_count
ORDER BY source_count DESC
```

### Q3: 最新ソースの鮮度チェック

```cypher
// 関連エンティティに紐づくソースの鮮度を確認
MATCH (e:Entity)<-[:MENTIONS]-(s:Source)
WHERE e.name CONTAINS $keyword
RETURN s.title AS source_title,
       s.authority_level AS authority,
       s.published_at AS published,
       s.source_type AS type
ORDER BY s.published_at DESC
LIMIT 15
```

### Q4: 既存Factの時系列確認

```cypher
// 関連エンティティの Fact を時系列で取得
MATCH (f:Fact)-[:RELATES_TO]->(e:Entity)
WHERE e.name CONTAINS $keyword
RETURN f.content AS fact,
       f.fact_type AS type,
       f.as_of_date AS date
ORDER BY f.as_of_date DESC
LIMIT 20
```

### Q5: 既存Claimのセンチメント分布

```cypher
// 関連エンティティに対する Claim のセンチメント分布
MATCH (c:Claim)-[:ABOUT]->(e:Entity)
WHERE e.name CONTAINS $keyword
RETURN c.sentiment AS sentiment,
       c.claim_type AS claim_type,
       count(*) AS count
ORDER BY count DESC
```

### Q6: 未回答のQuestionノード（既存ギャップ）

```cypher
// トピック関連で未回答のQuestionを取得
MATCH (q:Question)-[:ASKS_ABOUT]->(e:Entity)
WHERE e.name CONTAINS $keyword AND q.status IN ['open', 'investigating']
RETURN q.content AS question,
       q.question_type AS type,
       q.priority AS priority,
       e.name AS about_entity
ORDER BY
  CASE q.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END
```

## Phase 0-B: ギャップ分析ロジック

照会結果から以下の5観点でギャップを特定する。

### Gap 1: データ鮮度ギャップ

最新ソースの `published_at` が30日以上前の場合、最新情報が不足している。

```
判定: max(published_at) < today - 30d → "stale_data" ギャップ
検索優先度: HIGH
アクション: 最新ニュース・レポートを重点的に検索
```

### Gap 2: センチメント偏りギャップ

Claimのセンチメントが一方向のみ（bullish only / bearish only）の場合、反対意見が不足している。

```
判定:
  - bullish claim > 0 AND bearish claim == 0 → "missing_bear_case"
  - bearish claim > 0 AND bullish claim == 0 → "missing_bull_case"
検索優先度: MEDIUM
アクション: 反対意見の検索クエリを追加
```

### Gap 3: エンティティカバレッジギャップ

記事に登場すべきエンティティが KG に存在しない、または Fact/Claim が0件の場合。

```
判定: fact_count == 0 AND claim_count == 0 → "no_coverage"
検索優先度: HIGH
アクション: そのエンティティ名で集中的に検索
```

### Gap 4: 未回答Questionギャップ

既存の Question ノード（status: open）が存在する場合、それを解決するための検索を行う。

```
判定: open Question count > 0 → "open_questions"
検索優先度: HIGH（priority=high の場合）/ MEDIUM（それ以外）
アクション: Question.content を検索クエリとして使用
```

### Gap 5: 数値データギャップ

FinancialDataPoint が存在しない、または最新期のデータがない場合。

```cypher
// 関連エンティティの FinancialDataPoint 有無を確認
MATCH (e:Entity)
WHERE e.name CONTAINS $keyword AND e.entity_type IN ['company', 'etf', 'index']
OPTIONAL MATCH (fdp:FinancialDataPoint)-[:RELATES_TO|MEASURES]->(e)
WITH e, count(fdp) AS dp_count,
     max(fdp.created_at) AS latest_dp
RETURN e.name AS entity,
       dp_count,
       latest_dp
```

```
判定: dp_count == 0 AND entity_type IN ['company', 'etf', 'index'] → "missing_financials"
検索優先度: MEDIUM
アクション: SEC Edgar / 決算データを検索
```

## Phase 0-C: ギャップレポート出力

ギャップ分析結果を以下の形式で `01_research/kg_gap_report.md` に出力する。

```markdown
# KG ギャップ分析レポート

## 照会日時: {datetime}
## テーマ: {theme}

## 既存データサマリー
- 関連エンティティ: {n}件
- 関連ファクト: {n}件
- 関連クレーム: {n}件（bullish: {n}, bearish: {n}, neutral: {n}）
- 関連ソース: {n}件（最新: {date}）
- 未回答Question: {n}件

## 特定されたギャップ

### HIGH 優先度
| ギャップ種別 | 詳細 | 推奨検索クエリ |
|------------|------|--------------|
| {gap_type} | {description} | {query} |

### MEDIUM 優先度
| ギャップ種別 | 詳細 | 推奨検索クエリ |
|------------|------|--------------|
| {gap_type} | {description} | {query} |

## 検索計画
- ギャップ解消用クエリ: {n}件
- 通常リサーチクエリ: {n}件
- 合計検索予算: {n}件
```

## Phase 5: KG永続化

### 検索結果 → 入力JSON変換ルール

Web検索結果を `emit_graph_queue.py --command web-research` の入力JSONに変換する。

```json
{
  "session_id": "article-research-{slug}-{YYYYMMDD-HHMM}",
  "research_topic": "{meta.yaml の topic}",
  "as_of_date": "{today}",
  "sources": [
    {
      "url": "{検索結果のURL}",
      "title": "{記事タイトル}",
      "authority_level": "{tier判定結果}",
      "published_at": "{公開日}",
      "source_type": "{web|news|blog}"
    }
  ],
  "entities": [
    {
      "name": "{エンティティ名}",
      "entity_type": "{company|index|...}"
    }
  ],
  "topics": [
    {
      "name": "{トピック名}",
      "category": "{macro|equity|...}"
    }
  ],
  "facts": [
    {
      "content": "{ファクト内容}",
      "source_url": "{出典URL — sources[].url と一致必須}",
      "confidence": 0.9,
      "about_entities": [
        { "name": "{entity}", "entity_type": "{type}" }
      ]
    }
  ]
}
```

### authority_level 判定基準

ソース信頼度は `references/source-reliability.md` の Tier 分類に対応:

| Tier | authority_level | ソース例 |
|------|----------------|---------|
| Tier 1 | official | 中央銀行声明、SEC filing、企業IR |
| Tier 2 | analyst | セルサイドレポート、格付機関 |
| Tier 2 | media | Reuters, Bloomberg, 日経 |
| Tier 3 | blog | Seeking Alpha, note.com, Substack |
| Tier 4 | social | Reddit, X(Twitter) |

### Question ノード更新

ギャップ解消によりQuestionが回答された場合、検索結果のソースをANSWERED_BY で紐付ける。
ただし Question ノードの status 更新は Cypher 直書きが必要なため、ユーザーに確認の上で実行する。

```cypher
// ユーザー承認後のみ実行
MATCH (q:Question {question_id: $qid})
SET q.status = 'answered'
```

## 関連ファイル

| リソース | パス |
|---------|------|
| emit-research-queue スキル | `.claude/skills/emit-research-queue/SKILL.md` |
| save-to-graph スキル | `.claude/skills/save-to-graph/SKILL.md` |
| Neo4j直書き禁止ルール | `.claude/rules/neo4j-write-rules.md` |
| ソース信頼度定義 | `.claude/skills/investment-research/references/source-reliability.md` |
| KGスキーマ定義 | `data/config/knowledge-graph-schema.yaml` |
