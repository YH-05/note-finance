# Phase E: Operations Guide

Phase D の品質検証結果を受けて、運用系スキル・クエリ・ルールを更新する Phase E の詳細手順。
新オントロジーに合わせた enrichment スキル、ギャップ分析クエリ、横断リレーション強化ルールを生成・更新する。

---

## 前提条件

- Phase D が完了していること
- `data/lifecycle-state/{instance}/ontology.yaml` が存在すること
- `data/lifecycle-state/{instance}/quality-report-YYYYMMDD.md` が存在すること
- Phase B の成果物（`extraction-prompt.md`, `merge-guide.md` 等）が存在すること

---

## タスク一覧

| タスク | 内容 | 入力 | 成果物 |
|--------|------|------|--------|
| E-1 | enrichment スキルの更新/生成 | ontology.yaml, extraction-prompt.md | enrichment スキル設定 |
| E-2 | ギャップ分析クエリの更新 | ontology.yaml, quality-report | gap-analysis-queries.md |
| E-3 | 横断リレーション強化ルール | ontology.yaml, quality-report | cross-rel-rules.yaml |

---

## E-1: enrichment スキルの更新/生成

### 目的

Phase B で生成した抽出プロンプトと MERGE ガイドを使用して、インスタンス固有の enrichment スキルの設定を更新する。

### 手順

1. **既存 enrichment スキルの確認**:

```bash
# インスタンスに対応する enrichment スキルが存在するか確認
ls .claude/skills/{instance}-enrichment/ 2>/dev/null
```

2. **enrichment スキル設定の生成**:

enrichment スキルが以下を参照するよう設定を更新する:

```yaml
# enrichment スキルの参照先を更新
enrichment_config:
  instance_name: "{instance_name}"

  # Phase B で生成した抽出プロンプト
  extraction_prompt: "data/lifecycle-state/{instance}/extraction-prompt.md"

  # Phase B で生成した MERGE ガイド
  merge_guide: "data/lifecycle-state/{instance}/merge-guide.md"

  # Phase B で生成した Entity Linker 設定
  entity_linker_config: "data/lifecycle-state/{instance}/entity-linker-config.yaml"

  # Phase B で生成した Emit Queue 設定
  emit_queue_config: "data/lifecycle-state/{instance}/emit-queue-config.yaml"

  # MCP ツール
  mcp_read: "{mcp_read_tool}"
  mcp_write: "{mcp_write_tool}"
  mcp_schema: "{mcp_schema_tool}"
```

3. **抽出プロンプトの反映確認**:

`extraction-prompt.md` がインスタンス固有の entity_types, concept_categories, normalization_rules を正しく含んでいることを確認する。

4. **MERGE ガイドの反映確認**:

`merge-guide.md` が新スキーマの制約・インデックス・MERGE パターンを正しく含んでいることを確認する。

### 成果物

- enrichment スキル設定の更新
- `data/lifecycle-state/{instance}/enrichment-config.yaml`

---

## E-2: ギャップ分析クエリの更新

### 目的

Phase D の品質レポートに基づき、ナレッジグラフのギャップ（カバレッジ不足のカテゴリ、接続密度の低い領域）を特定するクエリを生成する。

### 手順

1. **品質レポートの読み込み**:

`data/lifecycle-state/{instance}/quality-report-YYYYMMDD.md` から以下を取得:
- D-4 カバレッジの低いカテゴリ
- D-3 孤立ノードの多いラベル
- D-1 未分類コンテンツの割合

2. **ギャップ分析クエリの生成**:

ontology.yaml の構造に基づき、以下のクエリカテゴリを生成する。

#### Q1: カテゴリ別カバレッジギャップ

```cypher
-- ConceptCategory/Topic カテゴリ別のコンテンツ件数
-- 件数が閾値以下のカテゴリをギャップとして検出
```

生成ロジック:
- ConceptCategory が存在する場合: IS_A リレーション経由でカテゴリ別集計
- Topic の場合: category プロパティで直接集計
- 閾値: 全カテゴリの平均件数の 50%

#### Q2: Entity タイプ別カバレッジギャップ

```cypher
-- entity_type ごとの Entity 数と、各 Entity が持つコンテンツ接続数
-- 接続数の中央値が低い entity_type をギャップとして検出
```

#### Q3: Source ドメイン別カバレッジ

```cypher
-- source_type または domain ごとの Source 数と接続コンテンツ数
-- ソースの多様性を確認
```

#### Q4: 時系列ギャップ

```cypher
-- Source の published_at の年月別分布で、データが少ない期間を検出
```

#### Q5: Entity 接続密度ギャップ

```cypher
-- 接続リレーション数が 1 の Entity（弱い接続）を検出
-- enrichment の優先対象として提示
```

3. **ギャップ分析結果の保存**:

```markdown
# {instance_name} ギャップ分析 (YYYY-MM-DD)

## カバレッジギャップ

| カテゴリ | 件数 | 平均 | ギャップ率 |
|---------|------|------|----------|
| {category} | N | M | X% |

## enrichment 優先領域

1. {最もギャップの大きいカテゴリ}
2. {次にギャップの大きいカテゴリ}
3. {接続密度の低い Entity 群}

## 推奨検索クエリ

- Tavily: "{keyword1} {keyword2} {year}"
- Reddit: r/{subreddit} "{keyword}"
```

### 成果物

- `data/lifecycle-state/{instance}/gap-analysis-queries.md`
- `data/lifecycle-state/{instance}/gap-analysis-YYYYMMDD.md`（実行結果）

---

## E-3: 横断リレーション強化ルール

### 目的

Phase D で検出された孤立ノードや接続密度の低い領域に対して、横断リレーション（Concept-Concept 間、Entity-Entity 間等）を強化するルールを設定する。

### 手順

1. **既存リレーション分析**:

```cypher
-- ontology.yaml で定義されている Concept 間リレーション
-- ENABLES, REQUIRES, COMPETES_WITH 等の件数を確認
MATCH ()-[r]->()
WHERE type(r) IN $concept_relations
RETURN type(r) AS rel_type, count(r) AS cnt
```

2. **強化候補の特定**:

以下の観点で横断リレーションの強化候補を特定する:

| 観点 | クエリ | 条件 |
|------|--------|------|
| 共起関係 | 同一 Source から抽出された Entity/Concept ペア | 共起回数 >= 3 |
| テキスト類似性 | text/content プロパティの類似度 | 類似度 >= 0.8 |
| カテゴリ近接 | 同一 ConceptCategory 内の Concept ペア | リレーション未接続 |

#### 共起関係の検出

```cypher
-- 同じ Source から言及されている Entity ペア
MATCH (s:Source)-[]->(c1)-[:RELATES_TO]->(e1:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product),
      (s)-[]->(c2)-[:RELATES_TO]->(e2:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product)
WHERE e1 <> e2
AND NOT 'Memory' IN labels(e1)
AND NOT 'Memory' IN labels(e2)
WITH e1, e2, count(DISTINCT s) AS co_occurrence
WHERE co_occurrence >= 3
AND NOT (e1)--(e2)
RETURN e1.name, e2.name, co_occurrence
ORDER BY co_occurrence DESC
LIMIT 20
```

3. **強化ルールの生成**:

```yaml
# 横断リレーション強化ルール
cross_relation_rules:
  instance_name: "{instance_name}"
  generated_at: "YYYY-MM-DD"

  # ルール1: 共起ベースの Entity 接続
  co_occurrence_rules:
    min_co_occurrence: 3
    relation_type: "CO_OCCURS_WITH"  # or 既存の RELATES_TO 等
    auto_apply: false  # 手動確認が必要

  # ルール2: Concept 間リレーション候補
  concept_relation_candidates:
    - from: "{concept_1}"
      to: "{concept_2}"
      suggested_type: "ENABLES"
      evidence: "共起回数: N, 同カテゴリ"

  # ルール3: Entity-Concept 接続強化
  entity_concept_candidates:
    - entity: "{entity_name}"
      concept: "{concept_name}"
      suggested_type: "SERVES_AS"
      context: "{推定される文脈}"
```

4. **ルールの適用**:

- `auto_apply: true` のルール: 自動で MERGE を実行
- `auto_apply: false` のルール: ユーザーに候補リストを提示し、承認後に適用

### 成果物

- `data/lifecycle-state/{instance}/cross-rel-rules.yaml`

---

## Phase E 完了条件

- [ ] E-1: enrichment スキル設定が更新され、新 ontology の抽出プロンプト・MERGE ガイドを参照している
- [ ] E-2: ギャップ分析クエリが生成され、カバレッジギャップが特定されている
- [ ] E-3: 横断リレーション強化ルールが生成されている
- [ ] lifecycle-state.json の Phase E が `completed` になっている

---

## Phase E → Phase F への受け渡し

| ファイル | Phase F での用途 |
|---------|-----------------|
| `enrichment-config.yaml` | F-3 ダウンストリームワークフロー統合の入力 |
| `gap-analysis-queries.md` | F-1 ユースケース別クエリテンプレートのベース |
| `cross-rel-rules.yaml` | F-2 パターン発見クエリのシード |

---

## エラーハンドリング

| エラー | 対処 |
|--------|------|
| enrichment スキルが存在しない | 新規作成を提案（SKILL.md テンプレートから生成） |
| 品質レポートが存在しない | Phase D に差し戻し |
| 共起クエリが重い（大規模 DB） | LIMIT を追加し、entity_type でフィルタして分割実行 |
| 横断リレーション候補が多すぎる | 共起回数の閾値を引き上げて絞り込み |

---

## 関連リソース

| リソース | パス |
|---------|------|
| creator-enrichment スキル（参考実装） | `.claude/skills/creator-enrichment/SKILL.md` |
| creator-enrichment references（参考実装） | `.claude/skills/creator-enrichment/references/` |
| 品質レポート | `data/lifecycle-state/{instance}/quality-report-YYYYMMDD.md` |
| 品質クエリ | `data/lifecycle-state/{instance}/quality-queries.md` |
