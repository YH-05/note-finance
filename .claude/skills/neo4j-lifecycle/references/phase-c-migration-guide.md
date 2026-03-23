# Phase C: Migration Guide

`--mode redesign` の場合にのみ実行される、既存データの新スキーマへの移行手順。
既存ノード・リレーションを新オントロジーに再分類・再接続し、旧構造を安全に廃止する。

---

## 前提条件

- Phase B が完了していること
- `--mode redesign` であること（`--mode new` の場合はこの Phase をスキップ）
- `data/lifecycle-state/{instance}/ontology.yaml`（新スキーマ）が存在すること
- `data/lifecycle-state/{instance}/merge-guide.md` が存在すること
- MCP 読み書きツールが接続済みであること

---

## タスク一覧

| タスク | 内容 | 成果物 |
|--------|------|--------|
| C-1 | Entity 再分類計画 | migration-plan.md |
| C-2 | コンテンツ接続バックフィル | ABOUT/MENTIONS 補完 |
| C-3 | プロパティ一括更新 | null 値推定、正規化 |
| C-4 | 旧ラベル・リレーション削除 | クリーンアップ完了 |

---

## C-1 前の必須ステップ: AuraDB バックアップ確認

### バックアップ確認手順

**C-1 の作業を開始する前に、必ず AuraDB バックアップが最新であることを確認する。**

1. **最終バックアップ日時の確認**:

```bash
# AuraDB の最終バックアップ状態を確認
# backup-auradb スキルの実行ログを確認
ls -la data/lifecycle-state/{instance}/backup-*.json 2>/dev/null || echo "バックアップ履歴なし"
```

2. **バックアップの実行（必要な場合）**:

```
/backup-auradb を実行して research-neo4j のデータを AuraDB に同期する
```

3. **バックアップ検証**:

```cypher
-- AuraDB 側のノード数を確認（aura MCP 経由）
MATCH (n)
WHERE NOT 'Memory' IN labels(n)
RETURN labels(n)[0] AS label, count(n) AS cnt
ORDER BY cnt DESC
```

4. **ローカルとの整合性確認**:

```cypher
-- ローカル Neo4j のノード数
MATCH (n)
WHERE NOT 'Memory' IN labels(n)
RETURN labels(n)[0] AS label, count(n) AS cnt
ORDER BY cnt DESC
```

ローカルと AuraDB のノード数が一致していることを確認してから C-1 に進む。

### バックアップが未実施の場合

**バックアップが確認できない場合、C-1 以降の作業は実行しないこと。**
ユーザーにバックアップの実行を促し、完了後に再開する。

---

## --dry-run モード（EXPLAIN プレフィックス）

`--dry-run` フラグが指定されている場合、C-1〜C-4 の全 Cypher クエリに `EXPLAIN` プレフィックスを付与して実行する。データの変更は行わず、実行計画のみを確認する。

### --dry-run の動作

```cypher
-- 通常実行
MATCH (e:Entity)
WHERE e.entity_type = 'old_type'
SET e.entity_type = 'new_type'
RETURN count(e) AS updated

-- --dry-run 実行（EXPLAIN プレフィックス）
EXPLAIN
MATCH (e:Entity)
WHERE e.entity_type = 'old_type'
SET e.entity_type = 'new_type'
RETURN count(e) AS updated
```

### --dry-run の出力

```yaml
dry_run_results:
  c1_entity_reclassification:
    affected_nodes: 150
    reclassification_plan:
      - from: "old_type"
        to: "new_type"
        count: 50
      - from: "removed_type"
        to: "closest_new_type"
        count: 30
    execution_plan: "... (EXPLAIN 出力)"

  c2_backfill:
    missing_about_connections: 45
    missing_mentions_connections: 80
    execution_plan: "..."

  c3_property_updates:
    null_properties_to_fill: 120
    normalization_candidates: 60
    execution_plan: "..."

  c4_cleanup:
    labels_to_remove: ["OldLabel1", "OldLabel2"]
    relations_to_remove: ["OLD_REL1"]
    orphan_nodes_to_delete: 15
    execution_plan: "..."
```

### --dry-run から本番実行への切り替え

```
--dry-run の結果を確認後、ユーザーの明示的な承認を得てから本番実行に切り替える。
承認なしでの本番実行は禁止。
```

---

## C-1: Entity 再分類計画

既存ノードの新オントロジーへのマッピングを計画・実行する。

### 手順

1. **既存 entity_type の一覧を取得**:

```cypher
MATCH (e:Entity)
WHERE NOT 'Memory' IN labels(e)
RETURN e.entity_type AS current_type, count(e) AS cnt
ORDER BY cnt DESC
```

2. **新旧 entity_type のマッピング表を作成**:

```yaml
entity_type_mapping:
  # 既存 → 新（ontology.yaml の entity_types）
  old_platform: platform    # そのまま
  old_company: company      # そのまま
  service: platform         # service → platform に統合
  tool: platform            # tool → platform に統合
  removed_type: null        # 廃止（ノードも削除する場合）
```

3. **マッピング表をユーザーに確認**（重要な変更がある場合）

4. **entity_type の更新を実行**:

```cypher
-- --dry-run の場合は EXPLAIN を付与
MATCH (e:Entity)
WHERE NOT 'Memory' IN labels(e)
AND e.entity_type = $old_type
SET e.entity_type = $new_type
RETURN count(e) AS updated
```

5. **既存 Concept/Topic の再分類**:

```cypher
-- ConceptCategory マッピングの場合
MATCH (c:Concept)
WHERE NOT (c)-[:IS_A]->(:ConceptCategory)
// 新しい ConceptCategory にマッチさせるロジック
```

### 成果物

- `data/lifecycle-state/{instance}/migration-plan.md`（マッピング表と実行結果）

---

## C-2: コンテンツ接続バックフィル

既存コンテンツノードに不足している ABOUT/MENTIONS/RELATES_TO 等のリレーションを補完する。

### 手順

1. **未接続コンテンツの検出**:

```cypher
-- コンセプト接続なしコンテンツ
MATCH (n)
WHERE (n:Fact OR n:Tip OR n:Story OR n:Claim)
AND NOT 'Memory' IN labels(n)
AND NOT (n)-[:ABOUT|RELATES_TO]->()
RETURN labels(n)[0] AS label, count(n) AS cnt
```

2. **Entity 接続なしコンテンツの検出**:

```cypher
MATCH (n)
WHERE (n:Fact OR n:Tip OR n:Story OR n:Claim)
AND NOT 'Memory' IN labels(n)
AND NOT (n)-[:MENTIONS|RELATES_TO]->(:Entity)
RETURN labels(n)[0] AS label, count(n) AS cnt
```

3. **テキストベースの自動接続**:

LLM を使用して、コンテンツの text/content プロパティから Entity/Concept を推定し、リレーションを作成する。

```cypher
-- バッチ処理: 未接続コンテンツを取得
MATCH (n:Fact)
WHERE NOT 'Memory' IN labels(n)
AND NOT (n)-[:RELATES_TO]->(:Entity)
RETURN n.fact_id AS id, n.text AS text
LIMIT 50
```

取得したテキストを抽出プロンプト（`extraction-prompt.md`）で処理し、検出された Entity/Concept とのリレーションを MERGE で作成する。

4. **Source 接続なしコンテンツの修復**:

```cypher
-- source_url プロパティから Source ノードをマッチ
MATCH (n:Fact)
WHERE NOT 'Memory' IN labels(n)
AND NOT (n)-[:EXTRACTED_FROM|FROM_SOURCE]->()
AND n.source_url IS NOT NULL
MATCH (s:Source {url: n.source_url})
MERGE (n)-[:FROM_SOURCE]->(s)
RETURN count(n) AS connected
```

---

## C-3: プロパティ一括更新

null 値の推定と、既存プロパティの正規化を行う。

### 手順

1. **null プロパティの検出**:

```cypher
-- Entity の entity_type が null
MATCH (e:Entity)
WHERE NOT 'Memory' IN labels(e)
AND e.entity_type IS NULL
RETURN e.name AS name, e.entity_key AS key
LIMIT 50
```

2. **null 値の推定**:

Entity 名から entity_type を推定する。LLM を使用するか、ルールベースで判定する。

```python
# ルールベース推定の例
type_rules = {
    "Inc.": "company",
    "Corp.": "company",
    "Ltd.": "company",
    "省": "organization",
    "庁": "organization",
    "Bank": "organization",
    "Fed": "organization",
}
```

3. **正規化の実行**:

ontology.yaml の `normalization_rules` に基づき、既存 Entity 名を正規化する。

```cypher
-- 全角英数字を半角に統一（APOC 利用可能な場合）
MATCH (e:Entity)
WHERE NOT 'Memory' IN labels(e)
AND e.name =~ '.*[Ａ-Ｚａ-ｚ０-９].*'
SET e.name = apoc.text.replace(e.name, '[Ａ-Ｚ]', /* 半角変換 */)
RETURN count(e) AS normalized
```

4. **updated_at の更新**:

変更されたノードの `updated_at` を更新する。

```cypher
MATCH (e:Entity)
WHERE NOT 'Memory' IN labels(e)
AND e.updated_at IS NULL
SET e.updated_at = datetime()
RETURN count(e) AS updated
```

---

## C-4: 旧ラベル・リレーション削除

新スキーマで不要になったラベル・リレーションを安全に削除する。

### 手順

1. **削除対象の特定**:

```cypher
-- 新スキーマに存在しないラベルを検出
MATCH (n)
WHERE NOT 'Memory' IN labels(n)
WITH labels(n) AS lbls
UNWIND lbls AS lbl
WITH DISTINCT lbl
WHERE NOT lbl IN $valid_labels  -- ontology.yaml から取得
RETURN lbl AS obsolete_label
```

```cypher
-- 新スキーマに存在しないリレーションタイプを検出
MATCH ()-[r]->()
WITH DISTINCT type(r) AS rel_type
WHERE NOT rel_type IN $valid_relations  -- ontology.yaml から取得
RETURN rel_type AS obsolete_relation
```

2. **削除前の確認**（必須）:

削除対象のノード数・リレーション数をユーザーに提示し、承認を得る。

```yaml
cleanup_plan:
  obsolete_labels:
    - label: "OldLabel"
      node_count: 25
      action: "ラベル除去（ノードは保持）"
    - label: "DeprecatedNode"
      node_count: 10
      action: "ノードごと削除"
  obsolete_relations:
    - type: "OLD_REL"
      count: 50
      action: "リレーション削除"
  orphan_nodes:
    count: 15
    action: "リレーション喪失により孤立したノードを削除"
```

3. **ラベル除去**:

```cypher
-- ラベルの除去（ノードは保持する場合）
MATCH (n:OldLabel)
WHERE NOT 'Memory' IN labels(n)
REMOVE n:OldLabel
RETURN count(n) AS label_removed
```

4. **リレーション削除**:

```cypher
-- 旧リレーションの削除
MATCH ()-[r:OLD_REL]->()
DELETE r
RETURN count(r) AS relations_deleted
```

5. **孤立ノードの削除**:

```cypher
-- リレーションを1つも持たないノードを削除
MATCH (n)
WHERE NOT 'Memory' IN labels(n)
AND NOT (n)--()
AND NOT n:Source  -- Source は孤立していても保持
DELETE n
RETURN count(n) AS orphans_deleted
```

6. **クリーンアップ検証**:

```cypher
-- 残存する旧ラベルがないことを確認
MATCH (n)
WHERE NOT 'Memory' IN labels(n)
RETURN DISTINCT labels(n) AS remaining_labels
```

---

## Phase C 完了条件

- [ ] C-1 前に AuraDB バックアップが確認済み
- [ ] C-1: entity_type の再分類が完了し、全 Entity が新 ontology の entity_types に準拠
- [ ] C-2: 未接続コンテンツのバックフィルが完了
- [ ] C-3: null プロパティの推定と正規化が完了
- [ ] C-4: 旧ラベル・リレーションが削除され、スキーマがクリーン
- [ ] --dry-run で事前検証済み（本番実行前）
- [ ] lifecycle-state.json の Phase C が `completed` になっている

---

## Phase C → Phase D への受け渡し

Phase D は Phase C で移行されたデータに対して品質検証を行う。

| 確認事項 | Phase D での検証 |
|---------|-----------------|
| entity_type の再分類 | D-1-4 で不正な entity_type がないことを確認 |
| コンテンツ接続 | D-1-1, D-1-2 で未接続コンテンツがないことを確認 |
| 重複ノード | D-2 でマージ漏れがないことを確認 |
| 孤立ノード | D-3 で残存孤立ノードがないことを確認 |

---

## エラーハンドリング

| エラー | 対処 |
|--------|------|
| AuraDB バックアップ未実施 | Phase C を開始しない。ユーザーにバックアップを促す |
| entity_type マッピングで不明な型 | ユーザーに判断を仰ぐ。自動判定しない |
| C-2 バックフィルで LLM 推定の信頼度が低い | confidence < 0.7 の場合はスキップし、手動対応リストに追加 |
| C-4 削除で予想外の件数 | 100件以上の削除は追加確認を求める |
| APOC 未インストール | 文字列操作の代替クエリを使用 |

---

## 関連リソース

| リソース | パス |
|---------|------|
| AuraDB バックアップスキル | `.claude/skills/backup-auradb/SKILL.md` |
| MERGE ガイド | `data/lifecycle-state/{instance}/merge-guide.md` |
| 抽出プロンプト | `data/lifecycle-state/{instance}/extraction-prompt.md` |
| 品質検証ガイド（次フェーズ） | `references/phase-d-quality-guide.md` |
