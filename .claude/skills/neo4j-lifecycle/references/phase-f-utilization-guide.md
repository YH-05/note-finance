# Phase F: Utilization Guide

構築されたナレッジグラフの活用設計を行う Phase F の詳細手順。
対話型で、ユーザーのユースケースに合わせたクエリテンプレート、パターン発見クエリ、ダウンストリームワークフロー統合を設計する。

---

## 前提条件

- Phase E が完了していること
- `data/lifecycle-state/{instance}/ontology.yaml` が存在すること
- `data/lifecycle-state/{instance}/quality-report-YYYYMMDD.md` が存在すること
- `data/lifecycle-state/{instance}/gap-analysis-queries.md` が存在すること

---

## タスク一覧

| タスク | 内容 | 対話 | 成果物 |
|--------|------|------|--------|
| F-1 | ユースケース別クエリテンプレート | Yes | `query-templates.md` |
| F-2 | パターン発見クエリ | Yes | `discovery-queries.md` |
| F-3 | ダウンストリームワークフロー統合 | Yes | `workflow-integration.md` |

---

## F-1: ユースケース別クエリテンプレート設計

### 目的

Phase A-1 で定義したユースケースと、Phase D の品質レポートを踏まえて、日常的に使用するクエリテンプレートを設計する。

### 手順

1. **ユースケースの再確認**:

`lifecycle-state.json` の Phase A-1 決定事項からユースケースを読み込む。

2. **AskUserQuestion: クエリニーズの確認**:

```
ナレッジグラフが構築されました。日常的にどのようなクエリを実行したいですか？

現在のデータ概要:
- ノード数: {total_nodes}
- Entity数: {entity_count} ({entity_types の内訳})
- コンテンツ数: {content_count}
- Source数: {source_count}

想定されるクエリパターン:
1. トピック検索: 「{concept_example} に関する全知識を取得」
2. Entity 中心: 「{entity_example} に関連する全情報を取得」
3. 類似検索: 「{concept_example} に似た概念を発見」
4. 時系列: 「直近1ヶ月の {source_type} を時系列で確認」
5. カバレッジ分析: 「情報が少ないカテゴリを特定」
6. その他（自由記述）

よく使いそうなパターンを選択するか、具体的なユースケースを記述してください。

デフォルト: 1, 2, 5（トピック検索 + Entity中心 + カバレッジ分析）
```

3. **クエリテンプレートの生成**:

ユーザーの回答に基づき、ontology.yaml の構造に合わせたパラメータ化クエリを生成する。

### クエリテンプレートカタログ

#### T1: トピック検索（Concept/Topic 中心）

```cypher
-- パラメータ: $topic_name
-- 目的: 特定トピックに関連する全コンテンツと Entity を取得

MATCH (c:{{CONCEPT_LABEL}} {name: $topic_name})
WHERE NOT 'Memory' IN labels(c)
OPTIONAL MATCH (content)-[:{{CONTENT_TO_CONCEPT_REL}}]->(c)
WHERE ({{CONTENT_LABEL_FILTER}})
OPTIONAL MATCH (content)-[:{{CONTENT_TO_ENTITY_REL}}]->(e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product)
RETURN c.name AS topic,
       collect(DISTINCT {
         type: labels(content)[0],
         text: CASE
           WHEN content.text IS NOT NULL THEN left(content.text, 200)
           WHEN content.content IS NOT NULL THEN left(content.content, 200)
           ELSE 'N/A'
         END
       }) AS contents,
       collect(DISTINCT e.name) AS related_entities
```

#### T2: Entity 中心検索

```cypher
-- パラメータ: $entity_name
-- 目的: 特定 Entity に関連する全コンテンツとトピックを取得

MATCH (e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product {name: $entity_name})
WHERE NOT 'Memory' IN labels(e)
OPTIONAL MATCH (content)-[:{{CONTENT_TO_ENTITY_REL}}]->(e)
WHERE ({{CONTENT_LABEL_FILTER}})
OPTIONAL MATCH (content)-[:{{CONTENT_TO_CONCEPT_REL}}]->(c:{{CONCEPT_LABEL}})
OPTIONAL MATCH (content)-[:{{CONTENT_TO_SOURCE_REL}}]->(s:Source)
RETURN e.name AS entity,
       labels(e)[0] AS type,
       collect(DISTINCT c.name) AS topics,
       collect(DISTINCT {
         type: labels(content)[0],
         source: s.title
       }) AS contents
```

#### T3: Source 検索

```cypher
-- パラメータ: $keyword (URL or title の部分一致)
-- 目的: ソースとそこから抽出された知識を取得

MATCH (s:Source)
WHERE NOT 'Memory' IN labels(s)
AND (s.title CONTAINS $keyword OR s.url CONTAINS $keyword)
OPTIONAL MATCH (s)-[]->(content)
WHERE NOT 'Memory' IN labels(content) AND NOT content:Source
RETURN s.title AS source_title,
       s.url AS source_url,
       s.source_type AS type,
       collect(DISTINCT labels(content)[0]) AS content_types,
       count(content) AS content_count
ORDER BY content_count DESC
```

#### T4: 時系列検索

```cypher
-- パラメータ: $days_ago (何日前まで)
-- 目的: 直近のソースとコンテンツを時系列で取得

MATCH (s:Source)
WHERE NOT 'Memory' IN labels(s)
AND s.published_at >= datetime() - duration({days: $days_ago})
OPTIONAL MATCH (s)-[]->(content)
WHERE NOT 'Memory' IN labels(content) AND NOT content:Source
RETURN s.title, s.url, s.published_at,
       collect(DISTINCT labels(content)[0]) AS content_types,
       count(content) AS content_count
ORDER BY s.published_at DESC
```

#### T5: カバレッジ分析ダッシュボード

```cypher
-- パラメータ: なし
-- 目的: グラフ全体の健全性を俯瞰

// ノードラベル別件数
MATCH (n) WHERE NOT 'Memory' IN labels(n)
RETURN labels(n)[0] AS label, count(n) AS cnt
ORDER BY cnt DESC

// リレーション種別分布
MATCH ()-[r]->()
RETURN type(r) AS rel, count(r) AS cnt
ORDER BY cnt DESC

// 最近追加されたノード
MATCH (n) WHERE NOT 'Memory' IN labels(n)
AND n.created_at >= datetime() - duration({days: 7})
RETURN labels(n)[0] AS label, count(n) AS recent_count
ORDER BY recent_count DESC
```

### 成果物

- `data/lifecycle-state/{instance}/query-templates.md`

---

## F-2: パターン発見クエリ設計

### 目的

ナレッジグラフ内の隠れたパターン、新しい接続、意外な関係性を発見するためのクエリを設計する。

### 手順

1. **AskUserQuestion: 発見の方向性**:

```
ナレッジグラフからどのようなパターンやインサイトを発見したいですか？

候補:
1. 概念間の隠れた接続（間接的につながる Concept/Topic）
2. Entity のクラスタリング（共起パターンから Entity グループを発見）
3. 知識の成長トレンド（時間軸での知識量の変化）
4. 情報ソースの偏り分析（特定ドメインへの依存度）
5. その他（自由記述）

デフォルト: 1, 2（隠れた接続 + クラスタリング）
```

2. **パターン発見クエリの生成**:

#### P1: 間接接続パターン（パス探索）

```cypher
-- 2ホップで接続される Concept/Topic ペアを発見
-- 直接の接続がないが、中間ノードを通じて関連する概念

MATCH path = (c1:{{CONCEPT_LABEL}})-[*2..3]-(c2:{{CONCEPT_LABEL}})
WHERE NOT 'Memory' IN labels(c1) AND NOT 'Memory' IN labels(c2)
AND c1 <> c2
AND NOT (c1)--(c2)  -- 直接接続がないもの
WITH c1, c2, count(path) AS path_count
WHERE path_count >= 2
RETURN c1.name AS concept_1, c2.name AS concept_2,
       path_count AS connection_strength
ORDER BY connection_strength DESC
LIMIT 20
```

#### P2: Entity 共起クラスタリング

```cypher
-- 同じコンテンツで共起する Entity ペアを発見
-- コンテンツ共有数が多いペアはクラスタを形成

MATCH (e1:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product)<-[:{{CONTENT_TO_ENTITY_REL}}]-(content)-[:{{CONTENT_TO_ENTITY_REL}}]->(e2:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product)
WHERE NOT 'Memory' IN labels(e1) AND NOT 'Memory' IN labels(e2)
AND elementId(e1) < elementId(e2)
WITH e1, e2, count(DISTINCT content) AS shared_content
WHERE shared_content >= 2
RETURN e1.name AS entity_1, labels(e1)[0] AS type_1,
       e2.name AS entity_2, labels(e2)[0] AS type_2,
       shared_content
ORDER BY shared_content DESC
LIMIT 20
```

#### P3: 知識成長トレンド

```cypher
-- 月別のノード追加数推移

MATCH (n)
WHERE NOT 'Memory' IN labels(n)
AND n.created_at IS NOT NULL
WITH toString(n.created_at.year) + '-' +
     CASE WHEN n.created_at.month < 10 THEN '0' ELSE '' END +
     toString(n.created_at.month) AS year_month,
     labels(n)[0] AS label
RETURN year_month, label, count(*) AS cnt
ORDER BY year_month DESC, cnt DESC
```

#### P4: ブリッジノード検出

```cypher
-- 多くの異なるコンテンツ/ソースと接続する「ハブ」ノードを発見
-- 知識のブリッジとして重要な Entity/Concept

MATCH (n)-[r]-()
WHERE NOT 'Memory' IN labels(n)
AND (n:Entity OR n:{{CONCEPT_LABEL}})
WITH n, count(DISTINCT r) AS degree, labels(n)[0] AS label
WHERE degree >= 5
RETURN n.name AS name, label,
       CASE WHEN n.entity_type IS NOT NULL THEN n.entity_type ELSE 'N/A' END AS subtype,
       degree
ORDER BY degree DESC
LIMIT 20
```

#### P5: 情報ソース多様性分析

```cypher
-- source_type 別の情報量と接続コンテンツ数
-- 偏りが大きい場合は情報ソースの多様化が必要

MATCH (s:Source)
WHERE NOT 'Memory' IN labels(s)
OPTIONAL MATCH (s)-[r]->()
WITH s.source_type AS source_type,
     count(DISTINCT s) AS source_count,
     count(DISTINCT r) AS connection_count
RETURN source_type,
       source_count,
       connection_count,
       toFloat(connection_count) / source_count AS avg_connections
ORDER BY source_count DESC
```

### 成果物

- `data/lifecycle-state/{instance}/discovery-queries.md`

---

## F-3: ダウンストリームワークフロー統合

### 目的

構築されたナレッジグラフを既存のワークフロー（enrichment、記事執筆、レポート生成等）にどう統合するかを設計する。

### 手順

1. **AskUserQuestion: ワークフロー確認**:

```
このナレッジグラフを以下のワークフローに統合することを検討しています:

既存のワークフロー:
1. enrichment（自動データ拡充）→ Phase E で設定済み
2. 品質チェック（定期実行）→ Phase D のクエリを定期実行
3. 記事執筆支援（関連知識の提供）
4. レポート生成（カバレッジダッシュボード）
5. その他（自由記述）

統合したいワークフローを選択するか、新しいワークフローを提案してください。

デフォルト: 1, 2, 4（enrichment + 品質チェック + レポート）
```

2. **ワークフロー統合設計**:

#### W1: enrichment ワークフロー統合

```yaml
workflow: enrichment
trigger: "定期実行 or 手動実行"
steps:
  1. gap-analysis-queries.md を実行し、カバレッジギャップを特定
  2. ギャップの大きいカテゴリに対して Web 検索を実行
  3. extraction-prompt.md で抽出
  4. entity-linker-config.yaml で Entity リンキング
  5. merge-guide.md に従って投入
  6. quality-queries.md で投入検証
integration_point: ".claude/skills/{instance}-enrichment/SKILL.md"
```

#### W2: 定期品質チェック統合

```yaml
workflow: quality_check
trigger: "週次 or データ投入後"
steps:
  1. quality-queries.md のクエリを全実行
  2. 品質スコアを算出
  3. quality-report-YYYYMMDD.md を生成
  4. 前回レポートと比較
  5. 品質低下があればアラート
integration_point: "cron or /neo4j-lifecycle --instance {instance} --phase D"
```

#### W3: 記事執筆支援統合

```yaml
workflow: article_writing
trigger: "記事リサーチフェーズ"
steps:
  1. query-templates.md のトピック検索でテーマの既存知識を取得
  2. discovery-queries.md で関連する隠れた接続を発見
  3. Entity 中心検索で固有名詞の背景情報を取得
  4. 記事ドラフトにソースURLを埋め込み
integration_point: "article-research スキルの入力として"
```

#### W4: カバレッジダッシュボード

```yaml
workflow: dashboard
trigger: "手動実行"
steps:
  1. カバレッジ分析クエリ（T5）を実行
  2. カテゴリ別・entity_type 別・時系列の分布を可視化
  3. gap-analysis の結果と組み合わせて改善提案を生成
output: "Markdown レポート"
```

### 成果物

- `data/lifecycle-state/{instance}/workflow-integration.md`

---

## Phase F 完了条件

- [ ] F-1: ユースケース別クエリテンプレートが設計され、`query-templates.md` に保存
- [ ] F-2: パターン発見クエリが設計され、`discovery-queries.md` に保存
- [ ] F-3: ダウンストリームワークフロー統合が設計され、`workflow-integration.md` に保存
- [ ] lifecycle-state.json の Phase F が `completed` になっている
- [ ] lifecycle-state.json の全体ステータスが `completed` になっている

---

## Phase F 完了後

Phase F の完了をもって、neo4j-lifecycle スキルの全フェーズが完了する。

### 成果物サマリー

| Phase | 主要成果物 |
|-------|-----------|
| A | `ontology.yaml`, `schema.yaml` |
| B | `extraction-prompt.md`, `entity-linker-config.yaml`, `emit-queue-config.yaml`, `merge-guide.md` |
| C | `migration-plan.md`（redesign のみ） |
| D | `quality-queries.md`, `quality-report-YYYYMMDD.md` |
| E | `enrichment-config.yaml`, `gap-analysis-queries.md`, `cross-rel-rules.yaml` |
| F | `query-templates.md`, `discovery-queries.md`, `workflow-integration.md` |

### 全成果物の保存先

```
data/lifecycle-state/{instance}/
  lifecycle-state.json       # フェーズ進捗（completed）
  ontology.yaml              # Phase A
  schema.yaml                # Phase A
  extraction-prompt.md       # Phase B
  entity-linker-config.yaml  # Phase B
  emit-queue-config.yaml     # Phase B
  merge-guide.md             # Phase B
  migration-plan.md          # Phase C（redesign のみ）
  quality-queries.md         # Phase D
  quality-report-YYYYMMDD.md # Phase D
  enrichment-config.yaml     # Phase E
  gap-analysis-queries.md    # Phase E
  gap-analysis-YYYYMMDD.md   # Phase E
  cross-rel-rules.yaml       # Phase E
  query-templates.md         # Phase F
  discovery-queries.md       # Phase F
  workflow-integration.md    # Phase F
```

---

## エラーハンドリング

| エラー | 対処 |
|--------|------|
| ユーザーがクエリニーズを明確にできない | デフォルト値（T1+T2+T5）で進行し、後から追加可能であることを説明 |
| クエリテンプレートが MCP で実行できない | Cypher 構文を修正し、MCP の制約に合わせる |
| ワークフロー統合先のスキルが存在しない | 「将来統合」として設計のみ行い、スキル作成は別 Issue で対応 |
| AskUserQuestion 3回到達 | 未確定項目はデフォルト値で確定 |

---

## 関連リソース

| リソース | パス |
|---------|------|
| project-discuss（対話パターン） | `.claude/skills/project-discuss/SKILL.md` |
| ギャップ分析クエリ | `data/lifecycle-state/{instance}/gap-analysis-queries.md` |
| 品質レポート | `data/lifecycle-state/{instance}/quality-report-YYYYMMDD.md` |
| enrichment 参考実装 | `.claude/skills/creator-enrichment/SKILL.md` |
