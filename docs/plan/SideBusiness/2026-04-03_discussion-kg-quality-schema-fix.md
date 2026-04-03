# 議論メモ: kg-quality-check Entity廃止後の新スキーマ対応

**日付**: 2026-04-03
**参加**: ユーザー + AI

## 背景・コンテキスト

2026-04-03 に research-neo4j の DB 移行（Project #107: Entity廃止・NODE KEY制約・RELATES_TO統一）を完了した。
その後 `/kg-quality-check` が旧スキーマに依存していることが判明。スクリプトを調査し、互換性修正を実施した。

## 問題の概要

`scripts/kg_quality_metrics.py` は以下の旧スキーマを前提としていた:

| 旧スキーマ | 新スキーマ（Entity廃止後） |
|-----------|--------------------------|
| `entity_type` プロパティ | `labels(n)[0]` でラベル取得 |
| `entity_id` プロパティ | `name` プロパティ（NODE KEY） |
| `ALLOWED_ENTITY_TYPES`（snake_case） | `ALLOWED_ENTITY_LABELS`（PascalCase 13ラベル） |
| `ABOUT` リレーション（存在する前提） | `RELATES_TO` に統一済み（ABOUT は 0件） |
| `Entity` ノード定義 | `Company` ノード定義（NODE KEY name） |

## 修正内容

### 1. ALLOWED_ENTITY_LABELS 改名（dec-2026-04-03-kg-quality-entity-labels）

- `ALLOWED_ENTITY_TYPES`（snake_case: `company`, `technology` 等）を廃止
- `ALLOWED_ENTITY_LABELS`（PascalCase 13ラベル: `Company`, `Technology`, `Organization`, `Person`, `MarketIndex`, `Indicator`, `Instrument`, `Commodity`, `Broker`, `Product`, `Concept`, `Country`, `Regulation`）に全面改名
- `tests/scripts/test_kg_quality_metrics.py` の全参照も同時更新

### 2. Cypher クエリ修正（dec-2026-04-03-kg-quality-cypher-fix）

3箇所の Cypher を新スキーマ対応に修正:

```cypher
-- Before (line ~879): entity_type プロパティ参照（存在しない）
RETURN n.entity_type AS entity_type, count(n) AS count

-- After: labels() でラベル取得
RETURN labels(n)[0] AS label, count(n) AS count
```

```cypher
-- Before (~908): entity_id IS NULL チェック（entity_id は全件削除済み）
WHERE n.entity_id IS NULL

-- After: name IS NULL で必須プロパティチェック
WHERE n.name IS NULL
```

```cypher
-- Before (~2432/2455): entity_type IS NOT NULL フィルタ
WHERE n.entity_type IS NOT NULL RETURN n.entity_type AS et

-- After: labels() 利用
RETURN labels(n)[0] AS et
```

### 3. ABOUT/Entity スキーマ更新（dec-2026-04-03-kg-quality-about-removal）

- `ALLOWED_RELATIONSHIP_TYPES` から `ABOUT` を除外（DB移行で 0件 → チェック不要）
- `_DEFAULT_RELATIONSHIPS_DEF` から `ABOUT` 定義を削除
- `IS_FACT_TYPE`, `IS_CLAIM_TYPE` 等 16件の新リレーションを追加
- ノードスキーマ定義: `Entity`（entity_id, name, entity_type の 3プロパティ）→ `Company`（name の NODE KEY のみ）に更新
- テストモックデータも全て PascalCase に修正

### 4. 事前存在の F841 バグ修正

`frequency_query = ""` の未使用変数（pre-existing bug）を削除

## 検証結果

- `make check-all` 全パス（format, lint, typecheck, test）
- テスト 143本 全 Pass
- commit: `00e8dd4 fix(kg-quality): Entity廃止後の新スキーマに品質計測を対応`

## アクションアイテム

- [ ] `/kg-quality-check` を実行し、スキーマ変更後のデータ整合性・品質を検証する（優先度: 中）
  - `act-2026-04-03-003` として登録済み

## 次回の議論トピック

- `/kg-quality-check` の実行結果を踏まえた品質改善
- `feature/issues-302-308` ブランチの main マージ（`act-2026-04-03-001`）

## 参考情報

- 関連 Discussion: `disc-2026-04-03-entity-redesign-db-migration`（DB移行本体）
- 修正ファイル: `scripts/kg_quality_metrics.py`, `tests/scripts/test_kg_quality_metrics.py`
