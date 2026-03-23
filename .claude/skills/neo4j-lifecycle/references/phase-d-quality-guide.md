# Phase D: Quality Guide

ナレッジグラフの品質を自動検証する Phase D の詳細手順。
`kg-quality-check` スキルに依存せず、`quality-queries-template.md` のテンプレートから
インスタンス固有の品質検証クエリセットを生成し、独立して実行する。

---

## 前提条件

- Phase B が完了していること（`new` モード）、または Phase C が完了していること（`redesign` モード）
- `data/lifecycle-state/{instance}/ontology.yaml` が存在すること
- MCP 読み取りツールが接続済みであること

**重要**: このフェーズは `kg-quality-check` スキルとは独立して実装されている。
`kg-quality-check` は research-neo4j 固有の品質チェックスキルであり、
Phase D はドメイン非依存の汎用品質検証を提供する。

---

## タスク一覧

| タスク | 内容 | 依存 | 成果物 |
|--------|------|------|--------|
| D-1 | オントロジー適合検証 | ontology.yaml | 適合率レポート |
| D-2 | 重複検出・マージ | ontology.yaml | 重複候補リスト |
| D-3 | 孤立ノード検出 | ontology.yaml | 孤立ノードリスト |
| D-4 | カバレッジ計測 | ontology.yaml | カバレッジマトリクス |

---

## 品質クエリ生成: quality-queries-template.md からの変換

### 生成手順

1. `references/quality-queries-template.md` を読み込む
2. `data/lifecycle-state/{instance}/ontology.yaml` を読み込む
3. プレースホルダーを ontology.yaml の値で置換する
4. 生成されたクエリセットを `data/lifecycle-state/{instance}/quality-queries.md` として保存する

### プレースホルダー解決ロジック

```python
def resolve_quality_placeholders(ontology: dict) -> dict:
    """ontology.yaml からクエリプレースホルダーを解決する。"""

    # コンテンツラベルフィルター
    content_labels = [ct["label"] for ct in ontology["content_types"]]
    content_label_filter = " OR ".join(f"n:{label}" for label in content_labels)

    # Concept/Topic ラベル判定
    has_concept_categories = bool(ontology.get("concept_categories"))
    concept_label = "Concept" if has_concept_categories else "Topic"
    category_label = "ConceptCategory" if has_concept_categories else None

    # リレーションタイプ解決
    rel_types = {rel["type"]: rel for rel in ontology["relation_types"]}

    # content → concept リレーション
    content_to_concept = next(
        (rt for rt in ["ABOUT", "TAGGED"] if rt in rel_types),
        "ABOUT"
    )

    # content → entity リレーション
    content_to_entity = next(
        (rt for rt in ["MENTIONS", "RELATES_TO"] if rt in rel_types),
        "RELATES_TO"
    )

    # content → source リレーション
    content_to_source = next(
        (rt for rt in ["FROM_SOURCE", "STATES_FACT"] if rt in rel_types),
        "FROM_SOURCE"
    )

    # concept → category リレーション
    concept_to_category = "IS_A" if has_concept_categories else None

    # entity_types リスト
    entity_types = ", ".join(
        f"'{et['key']}'" for et in ontology["entity_types"]
    )

    # category 名リスト
    category_names = ", ".join(
        f"'{cc['name']}'" for cc in ontology.get("concept_categories", [])
    )

    return {
        "CONTENT_LABELS": content_labels,
        "CONTENT_LABEL_FILTER": content_label_filter,
        "ENTITY_LABEL": "Entity",
        "SOURCE_LABEL": "Source",
        "CONCEPT_LABEL": concept_label,
        "CATEGORY_LABEL": category_label,
        "CONTENT_TO_CONCEPT_REL": content_to_concept,
        "CONTENT_TO_ENTITY_REL": content_to_entity,
        "CONTENT_TO_SOURCE_REL": content_to_source,
        "CONCEPT_TO_CATEGORY_REL": concept_to_category,
        "CATEGORY_NAMES": category_names,
        "ENTITY_TYPES": entity_types,
        "MEMORY_FILTER": "NOT 'Memory' IN labels(n)",
    }
```

---

## D-1: オントロジー適合検証

スキーマに定義されたルールに対する適合度を検証する。

### D-1-1: 未分類コンテンツ（コンセプト接続なし）

**目的**: 全コンテンツが最低1つの Concept/Topic と接続されているか確認する。

**実行クエリ**: `quality-queries-template.md` の D-1-1 をプレースホルダー解決して実行。

**判定基準**:

| 未分類率 | 評価 |
|---------|------|
| 0-5% | 良好 |
| 5-15% | 要改善 |
| 15%+ | 問題あり |

### D-1-2: ソース接続なしコンテンツ

**目的**: 全コンテンツがソース（出典）と接続されているか確認する。トレーサビリティの確保。

**判定基準**:

| 未接続率 | 評価 |
|---------|------|
| 0-3% | 良好 |
| 3-10% | 要改善 |
| 10%+ | 問題あり |

### D-1-3: 未分類 Concept/Topic

**目的**: ConceptCategory への接続（または category プロパティ）の欠落を検出する。

**実行条件**: `concept_categories` が定義されている場合のみ実行。未定義の場合は category プロパティの null チェックで代替する。

### D-1-4: 不正な entity_type

**目的**: ontology.yaml に定義されていない entity_type を持つ Entity を検出する。

**判定基準**: 不正な entity_type が1件でもある場合は「問題あり」。

---

## D-2: 重複検出・マージ

名前が類似する Entity/Concept を検出し、マージ候補を提示する。

### D-2-1: 完全一致重複

**目的**: 大文字小文字・全角半角の違いによる重複を検出する。

**実行クエリ**: toLower(trim()) で正規化し、同一グループに2件以上存在するものを検出。

### D-2-2: 部分一致重複

**目的**: 略称・別名による重複候補を検出する。

**実行条件**: APOC が利用可能な場合は Jaro-Winkler 類似度で検出。利用不可の場合は Full-Text Index フォールバック。

**APOC 可用性チェック**:

```cypher
CALL apoc.help('text')
YIELD name
RETURN count(name) > 0 AS apoc_available
```

APOC 不可の場合のフォールバック:

```cypher
-- Full-Text Index を使用した類似検索
CALL db.index.fulltext.queryNodes('{instance}_entity_fulltext', $entity_name)
YIELD node, score
WHERE score > 0.8 AND node.name <> $entity_name
RETURN node.name, score
```

### D-2-3: Concept/Topic 重複

**目的**: Concept/Topic 名の重複を検出する。

---

## D-3: 孤立ノード検出

リレーションを1つも持たないノードを検出する。

### D-3-1: 孤立 Entity

**目的**: どのコンテンツからも参照されていない Entity を検出する。

### D-3-2: 孤立 Source

**目的**: どのコンテンツとも接続されていない Source を検出する。

### D-3-3: 孤立 Concept/Topic

**目的**: どのコンテンツからも参照されていない Concept/Topic を検出する。

### D-3-4: 完全孤立ノード

**目的**: リレーションが1つもないノードを全ラベルで横断的に検出する。最も基本的な孤立検出。

---

## D-4: カバレッジ計測

オントロジーで定義された分類軸に対するデータのカバレッジを計測する。

### D-4-1: ノードラベル別件数

**目的**: 基本的な健全性チェック。ラベル別のノード数を確認する。

### D-4-2: ConceptCategory/Topic カテゴリ別カバレッジ

**目的**: カテゴリ別のコンテンツ件数を計測し、ギャップ（コンテンツが少ないカテゴリ）を特定する。

**実行条件**: ConceptCategory が存在する場合は IS_A リレーション経由で集計。Topic の場合は category プロパティで直接集計。

### D-4-3: entity_type 別分布

**目的**: entity_type ごとの Entity 件数を確認し、偏りを検出する。

### D-4-4: リレーション種別分布

**目的**: リレーション種別ごとの件数を確認し、期待値とのギャップを検出する。

### D-4-5: Source 年月別分布

**目的**: Source の published_at の年月別分布を確認し、時間的カバレッジを確認する。

### D-4-6: コンテンツ接続密度

**目的**: 各コンテンツノードが持つリレーション数の統計（平均・最小・最大）を計測する。接続密度が低いノードはデータ品質の問題を示唆する。

---

## 品質スコア算出

### スコアリング基準

| カテゴリ | 重み | 基準 |
|---------|------|------|
| D-1 オントロジー適合 | 30% | 未分類コンテンツ率、不正 entity_type 率 |
| D-2 重複 | 20% | 完全一致重複率、類似名重複率 |
| D-3 孤立ノード | 25% | 孤立 Entity 率、孤立 Source 率 |
| D-4 カバレッジ | 25% | カテゴリ別偏り（ジニ係数）、接続密度 |

### スコア算出ロジック

```python
def calculate_quality_score(results: dict) -> dict:
    """Phase D の結果から品質スコアを算出する。"""

    # D-1: オントロジー適合（未分類率が低いほど高スコア）
    total_content = results["d1"]["total_content"]
    orphan_content = results["d1"]["orphan_content"]
    d1_score = 1.0 - (orphan_content / max(total_content, 1))

    # D-2: 重複（重複率が低いほど高スコア）
    total_entities = results["d2"]["total_entities"]
    duplicate_entities = results["d2"]["duplicate_entities"]
    d2_score = 1.0 - (duplicate_entities / max(total_entities, 1))

    # D-3: 孤立ノード（孤立率が低いほど高スコア）
    total_nodes = results["d3"]["total_nodes"]
    orphan_nodes = results["d3"]["orphan_nodes"]
    d3_score = 1.0 - (orphan_nodes / max(total_nodes, 1))

    # D-4: カバレッジ（均等分布に近いほど高スコア）
    d4_score = 1.0 - results["d4"]["gini_coefficient"]

    # 加重平均
    overall = (
        d1_score * 0.30
        + d2_score * 0.20
        + d3_score * 0.25
        + d4_score * 0.25
    )

    return {
        "ontology_conformance": round(d1_score, 3),
        "deduplication": round(d2_score, 3),
        "orphan_detection": round(d3_score, 3),
        "coverage": round(d4_score, 3),
        "overall": round(overall, 3),
        "rating": (
            "A" if overall >= 0.9 else
            "B" if overall >= 0.7 else
            "C" if overall >= 0.5 else "D"
        ),
    }
```

### ジニ係数の算出

カテゴリ別カバレッジの偏りを定量化するためにジニ係数を使用する。

```python
def gini_coefficient(values: list[int]) -> float:
    """カテゴリ別コンテンツ件数からジニ係数を算出する。"""
    if not values or sum(values) == 0:
        return 0.0
    sorted_values = sorted(values)
    n = len(sorted_values)
    total = sum(sorted_values)
    cumulative = 0
    gini_sum = 0
    for i, v in enumerate(sorted_values):
        cumulative += v
        gini_sum += (2 * (i + 1) - n - 1) * v
    return gini_sum / (n * total) if total > 0 else 0.0
```

---

## quality-report-YYYYMMDD.md 出力フォーマット

Phase D 完了後に `data/lifecycle-state/{instance}/quality-report-YYYYMMDD.md` として保存する。

```markdown
# {instance_name} 品質レポート (YYYY-MM-DD)

## Overall Score: X.XXX (Rating: A/B/C/D)

| カテゴリ | スコア | 主要な問題 |
|---------|--------|-----------|
| D-1 オントロジー適合 | X.XXX | 未分類コンテンツ N件 |
| D-2 重複 | X.XXX | 重複候補 N組 |
| D-3 孤立ノード | X.XXX | 孤立 Entity N件 |
| D-4 カバレッジ | X.XXX | 低カバレッジカテゴリ: X, Y |

## データ概要

| ラベル | 件数 |
|--------|------|
| Source | N |
| Entity | N |
| {Content_Type_1} | N |
| {Content_Type_2} | N |
| {Concept/Topic} | N |

## D-1: オントロジー適合

### 未分類コンテンツ

- 未分類コンテンツ: N / M (X%)
- ソース未接続コンテンツ: N / M (X%)

### 不正 entity_type

| entity_type | 件数 |
|-------------|------|
| {invalid_type} | N |

## D-2: 重複検出

### 完全一致重複

| 正規化名 | バリエーション | 件数 |
|---------|-------------|------|
| {normalized} | {variant1}, {variant2} | N |

### 類似名重複候補

| 名前1 | 名前2 | 類似度 | entity_type |
|-------|-------|--------|-------------|
| {name1} | {name2} | 0.XX | {type} |

## D-3: 孤立ノード

- 孤立 Entity: N件
- 孤立 Source: N件
- 孤立 {Concept/Topic}: N件
- 完全孤立ノード: N件

## D-4: カバレッジ

### カテゴリ別分布

| カテゴリ | コンテンツ件数 |
|---------|-------------|
| {category_1} | N |
| {category_2} | N |

ジニ係数: X.XXX

### entity_type 別分布

| entity_type | 件数 |
|-------------|------|
| {type_1} | N |
| {type_2} | N |

### 接続密度

| ラベル | ノード数 | 平均リレーション数 | 最小 | 最大 |
|--------|---------|------------------|------|------|
| {label} | N | X.X | N | N |

### Source 年月別分布

| 年月 | 件数 |
|------|------|
| YYYY-MM | N |

## 改善提案

1. {提案1: 最もスコアが低いカテゴリに対する具体的な改善策}
2. {提案2: ...}
3. {提案3: ...}

## 前回比較（前回レポートが存在する場合）

| カテゴリ | 前回 | 今回 | 変化 |
|---------|------|------|------|
| D-1 | X.XXX | X.XXX | +X.XXX |
| D-2 | X.XXX | X.XXX | +X.XXX |
| D-3 | X.XXX | X.XXX | +X.XXX |
| D-4 | X.XXX | X.XXX | +X.XXX |
| Overall | X.XXX | X.XXX | +X.XXX |
```

---

## Phase D 完了条件

- [ ] D-1: オントロジー適合検証クエリが全て実行済み
- [ ] D-2: 重複検出クエリが実行済み（APOC 不可時はフォールバック実行）
- [ ] D-3: 孤立ノード検出クエリが全て実行済み
- [ ] D-4: カバレッジ計測クエリが全て実行済み
- [ ] 品質スコアが算出され、レーティング（A/B/C/D）が決定
- [ ] `quality-report-YYYYMMDD.md` が `data/lifecycle-state/{instance}/` に保存
- [ ] `quality-queries.md` が `data/lifecycle-state/{instance}/` に保存
- [ ] lifecycle-state.json の Phase D が `completed` になっている

---

## Phase D → Phase E への受け渡し

| ファイル | Phase E での用途 |
|---------|-----------------|
| `quality-report-YYYYMMDD.md` | E-2 ギャップ分析クエリ更新の入力 |
| `quality-queries.md` | E-2 定期品質チェックのベースクエリ |
| 品質スコア | E-3 横断リレーション強化の優先順位付け |

---

## エラーハンドリング

| エラー | 対処 |
|--------|------|
| MCP 接続エラー | リトライ3回。失敗時は接続情報を確認して中断 |
| APOC 未インストール | D-2-2 を Full-Text Index フォールバックに切り替え |
| クエリタイムアウト | LIMIT を追加して再実行。大規模 DB では D-2-2 の APOC クエリが重い |
| ontology.yaml の content_types が空 | Phase A に差し戻し |
| 前回レポートが存在しない | 「前回比較」セクションを省略 |

---

## 関連リソース

| リソース | パス |
|---------|------|
| 品質クエリテンプレート | `references/quality-queries-template.md` |
| オントロジーテンプレート | `references/ontology-template.yaml` |
| kg-quality-check（research 固有） | `.claude/skills/kg-quality-check/SKILL.md` |
