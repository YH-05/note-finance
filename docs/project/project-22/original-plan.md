# neo4j-lifecycle スキル開発プラン

## Context

creator-neo4j で手動実行した Phase A-E（設計→パイプライン実装→データ移行→品質保証→運用改修）を、任意の Neo4j インスタンスに対してドメイン非依存で再現できる汎用スキルを開発する。

**ユーザー要件**:
- 1つのオーケストレータースキルで全フェーズを管理
- 完全にドメイン非依存（コンテンツ以外にも金融リサーチ等に対応）
- 新規DB構築と既存DB再設計（v1→v2型）の両方に対応

---

## ファイル構造

```
.claude/skills/neo4j-lifecycle/
  SKILL.md                              # オーケストレーター本体
  references/
    phase-a-design-guide.md             # Phase A 対話的設計ガイド
    phase-b-pipeline-guide.md           # Phase B パイプライン生成ガイド
    phase-c-migration-guide.md          # Phase C データ移行パターン
    phase-d-quality-guide.md            # Phase D 品質検証クエリ
    phase-e-operations-guide.md         # Phase E 運用スキル更新
    phase-f-utilization-guide.md        # Phase F クエリ設計・統合
    ontology-template.yaml              # オントロジー定義テンプレート
    extraction-prompt-template.md       # 抽出プロンプトテンプレート
    merge-patterns-template.md          # MERGE Cypher テンプレート
    quality-queries-template.md         # 品質検証クエリテンプレート

.claude/commands/neo4j-lifecycle.md     # スラッシュコマンド

data/config/neo4j-instances/
  registry.yaml                         # 全インスタンス一覧
  creator.yaml                          # 既存: creator-neo4j
  research.yaml                         # 既存: research-neo4j
  note.yaml                             # 既存: note-neo4j

data/lifecycle-state/{instance_name}/
  lifecycle-state.json                  # フェーズ/タスク進捗
  ontology.yaml                         # 確定オントロジー
  schema.yaml                           # 確定スキーマ
```

---

## パラメータ

| パラメータ | 必須 | 説明 | 例 |
|-----------|------|------|----|
| `--instance` | Yes | 対象インスタンス名 | `--instance creator` |
| `--phase` | No | 実行フェーズ/タスク | `--phase A-2` |
| `--mode` | No | `new` or `redesign` | `--mode redesign` |
| `--dry-run` | No | プレビューのみ | `--dry-run` |

---

## 6フェーズ構成

### Phase 0: Init
- インスタンスYAML読み込み + MCP ツール取得
- 接続テスト（`RETURN 1 AS ok`）
- 状態ファイル読み込み or 作成
- `--mode redesign` 時: 既存スキーマ分析

### Phase A: Design（対話型、project-discuss パターン）
- A-1: 目的定義（ユースケース・クエリ要件）
- A-2: オントロジー設計（`ontology-template.yaml` ベース、ConceptCategory 等の上位概念定義）
- A-3: スキーマ設計（ノード・リレーション・制約・インデックス、`neo4j-data-modeling` MCP で検証）
- A-4: Entity 正規化ルール（Alias戦略、ファジーマッチング層数）
- **成果物**: `ontology.yaml`, `schema.yaml`, Discussion/Decision nodes

### Phase B: Pipeline（テンプレート + LLM 生成）
- B-1: 抽出プロンプト生成（`extraction-prompt-template.md` + ontology.yaml）
- B-2: Entity Linker 設定（接続先・しきい値・インデックス名を YAML 化）
- B-3: Emit Queue スクリプト設定（有効な enum 値を ontology.yaml から取得）
- B-4: MERGE ガイド生成（`merge-patterns-template.md` + schema.yaml）
- **成果物**: 抽出プロンプト、Entity Linker 設定、Emit 設定、MERGE ガイド

### Phase C: Migration（redesign モードのみ）
- C-1: Entity 再分類計画（既存ノードの新オントロジーへのマッピング）
- C-2: コンテンツ接続バックフィル（ABOUT/MENTIONS 補完）
- C-3: プロパティ一括更新（null 値推定、正規化）
- C-4: 旧ラベル・リレーション削除
- **成果物**: マイグレーション Cypher スクリプト

### Phase D: Quality（自動実行）
- D-1: オントロジー適合検証（IS_A なし Concept 等）
- D-2: 重複検出・マージ（APOC 類似度）
- D-3: 孤立ノード検出
- D-4: カバレッジ計測（ConceptCategory × ジャンル マトリクス）
- **成果物**: `quality-report-YYYYMMDD.md`

### Phase E: Operations（自動生成）
- E-1: enrichment スキルの更新/生成
- E-2: ギャップ分析クエリの更新
- E-3: 横断リレーション強化ルール設定

### Phase F: Utilization（対話型）
- F-1: ユースケース別クエリテンプレート設計
- F-2: パターン発見クエリ設計
- F-3: ダウンストリームワークフロー統合

---

## 状態管理

**プライマリ**: `data/lifecycle-state/{instance}/lifecycle-state.json`
```json
{
  "instance_name": "creator",
  "mode": "redesign",
  "phases": {
    "A": {
      "status": "completed",
      "tasks": {
        "A-1": {"status": "completed", "artifacts": ["ontology.yaml"]},
        "A-2": {"status": "in_progress"}
      }
    }
  }
}
```

**セカンダリ**: note-neo4j の Discussion/Decision/ActionItem（project-discuss パターン再利用）

---

## テンプレート戦略

| テンプレート | ベースファイル | パラメータ化箇所 |
|-------------|-------------|-----------------|
| ontology-template.yaml | creator ontology.yaml | concept_categories, entity_types, content_types |
| extraction-prompt-template.md | entity-extraction-prompt-v2.md | entity_types 表, ConceptCategory 表, 正規化ルール, 出力形式 |
| merge-patterns-template.md | guide-v2.md | ノード定義, リレーション定義, 制約, インデックス |
| quality-queries-template.md | D-1〜D-4 クエリ | ラベル名, リレーション名, プロパティ名 |

---

## 既存コンポーネントとの接続

| 既存コンポーネント | 接続方法 |
|-------------------|---------|
| `project-discuss` | Phase A で同じ対話パターン（AskUserQuestion + note-neo4j 永続化）を使用 |
| `save-to-{instance}-graph` | Phase B が MERGE ガイドを生成し、このスキルが消費 |
| `entity_linker.py` | Phase B が YAML 設定を生成。将来的にスクリプト自体を `--instance` パラメータ化 |
| `emit_{instance}_queue.py` | 同上。初期は per-instance 生成、将来は統合 |
| `neo4j-data-modeling` MCP | Phase A-3 でスキーマ検証・Mermaid 可視化 |
| `kg-quality-check` | Phase D の品質チェックカテゴリを参照 |

---

## 実装順序

| Step | 内容 | 依存 |
|------|------|------|
| 1 | `data/config/neo4j-instances/` に既存3インスタンスの YAML 作成 | なし |
| 2 | `references/ontology-template.yaml` 作成（creator ontology ベース） | なし |
| 3 | `SKILL.md` 作成（Phase 0 + Phase A） | Step 1-2 |
| 4 | `references/phase-a-design-guide.md` 作成 | Step 3 |
| 5 | `references/extraction-prompt-template.md` 作成 | Step 2 |
| 6 | `references/merge-patterns-template.md` 作成 | Step 2 |
| 7 | Phase B-F を `SKILL.md` に追加 + 各 guide.md | Step 3-6 |
| 8 | `.claude/commands/neo4j-lifecycle.md` 作成 | Step 7 |
| 9 | 既存 creator-neo4j の YAML 設定を作成し、Phase A を検証実行 | Step 8 |

---

## 検証方法

1. **Phase A 検証**: 仮想的な新規インスタンス（`test-neo4j`）に対して Phase A を実行し、ontology.yaml と schema.yaml が正しく生成されるか確認
2. **Phase B 検証**: 生成された抽出プロンプト・MERGE ガイドが構文的に正しいか確認
3. **エンドツーエンド**: 既存 creator-neo4j に対して `--mode redesign --dry-run` で全フェーズを実行し、既存状態と一致するか検証

---

## 今後の拡張

- `entity_linker.py` の `--instance` パラメータ統合（per-instance スクリプト → 単一スクリプト化）
- Docker Compose テンプレート生成（新規 Neo4j インスタンスの自動構築）
- AuraDB バックアップの自動化統合
