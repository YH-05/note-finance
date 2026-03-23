---
name: neo4j-lifecycle
description: |
  Neo4j ナレッジグラフのライフサイクル管理スキル。オントロジー設計(A)→パイプライン生成(B)→移行(C)→品質検証(D)→運用更新(E)→活用設計(F) の6フェーズを --instance パラメータで動的にインスタンスを切り替えて実行する。
  Use PROACTIVELY when user wants to design, build, migrate, validate, or maintain a Neo4j knowledge graph instance, or when user mentions neo4j-lifecycle, KG lifecycle, ontology design, schema migration, or graph quality check.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, mcp__neo4j-creator__*, mcp__neo4j-research__*, mcp__neo4j-note__*, mcp__neo4j-data-modeling__*, mcp__sequential-thinking__*, mcp__tavily__*, mcp__time__*
---

# neo4j-lifecycle スキル

Neo4j ナレッジグラフのライフサイクルを Phase A-F で管理するオーケストレーター。
各フェーズの詳細手順は `references/` 配下のガイドに委譲する。

---

## パラメータ

| パラメータ | 必須 | 説明 | 例 |
|-----------|------|------|----|
| `--instance` | 必須 | 対象インスタンス名 | `--instance creator` |
| `--phase` | 任意 | 単一フェーズ指定（省略時は中断フェーズから再開） | `--phase D` |
| `--mode` | 任意 | `new`（新規構築）/ `redesign`（再設計）。Phase A で使用 | `--mode new` |
| `--dry-run` | 任意 | データ変更を行わずプレビューのみ実行 | `--dry-run` |

---

## フェーズ概要

```
Phase 0: Init（初期化・接続確認・状態復元）
    |
Phase A: Design（対話型オントロジー・スキーマ設計）
    |
Phase B: Pipeline（パイプラインコンポーネント自動生成）
    |
Phase C: Migration（既存データ移行 — redesign モードのみ）
    |
Phase D: Quality（品質検証・スコアリング）
    |
Phase E: Operations（運用系スキル・クエリ更新）
    |
Phase F: Utilization（対話型活用設計）
```

---

## Phase 0: Init（初期化）

### 0-1. MCP ツール取得

ToolSearch で対象インスタンスの MCP ツールと共通ツールを取得する。

```
ToolSearch: "select:mcp__neo4j-data-modeling__validate_data_model,mcp__neo4j-data-modeling__get_mermaid_config_str"
ToolSearch: "select:mcp__sequential-thinking__sequentialthinking"
ToolSearch: "select:mcp__time__get_current_time"
```

インスタンスの `mcp.tools` に基づき、接続用ツールを取得する:

```
# インスタンス YAML の mcp.tools.read / write / schema から動的に取得
ToolSearch: "select:{mcp_read_tool},{mcp_write_tool},{mcp_schema_tool}"
```

### 0-2. registry.yaml 読み込み・インスタンス存在チェック

```
Read data/config/neo4j-instances/registry.yaml
```

`--instance` で指定されたインスタンス名が `registry.yaml` の `instances` に存在することを確認する。
存在しない場合はエラーメッセージを出力して終了:

```
エラー: インスタンス '{instance}' は registry.yaml に登録されていません。
有効なインスタンス: creator, research, note
```

### 0-3. インスタンス YAML 読み込み

```
Read data/config/neo4j-instances/{instance}.yaml
```

以下の情報を取得する:
- `instance_name`: インスタンス名
- `connection.bolt_uri`: 接続先 URI
- `mcp.tools.read` / `mcp.tools.write` / `mcp.tools.schema`: MCP ツール名
- `schema_version`: スキーマバージョン
- `use_case` / `description`: 用途・説明

### 0-4. 接続確認

インスタンス YAML の `mcp.tools.read` で接続テストを実行する:

```cypher
RETURN 1 AS ok
```

失敗時はエラーメッセージを出力して終了:

```
エラー: {instance} ({bolt_uri}) への接続に失敗しました。
Neo4j が起動しているか確認してください。
```

### 0-5. lifecycle-state.json 読み込み or 新規作成

```
Read data/lifecycle-state/{instance}/lifecycle-state.json
```

ファイルが存在しない場合（初回実行）は新規作成する:

```json
{
  "instance_name": "{instance}",
  "mode": "{--mode or 'new'}",
  "created_at": "{ISO8601}",
  "updated_at": "{ISO8601}",
  "current_phase": "A",
  "phases": {
    "A": {
      "status": "pending",
      "tasks": {
        "A-1": { "status": "pending", "artifacts": [], "decisions": {} },
        "A-2": { "status": "pending", "artifacts": [], "decisions": {} },
        "A-3": { "status": "pending", "artifacts": [], "decisions": {} },
        "A-4": { "status": "pending", "artifacts": [], "decisions": {} }
      }
    },
    "B": {
      "status": "pending",
      "tasks": {
        "B-1": { "status": "pending", "artifacts": [] },
        "B-2": { "status": "pending", "artifacts": [] },
        "B-3": { "status": "pending", "artifacts": [] },
        "B-4": { "status": "pending", "artifacts": [] }
      }
    },
    "C": {
      "status": "pending",
      "tasks": {
        "C-1": { "status": "pending", "artifacts": [] },
        "C-2": { "status": "pending", "artifacts": [] },
        "C-3": { "status": "pending", "artifacts": [] },
        "C-4": { "status": "pending", "artifacts": [] }
      }
    },
    "D": {
      "status": "pending",
      "tasks": {
        "D-1": { "status": "pending", "artifacts": [] },
        "D-2": { "status": "pending", "artifacts": [] },
        "D-3": { "status": "pending", "artifacts": [] },
        "D-4": { "status": "pending", "artifacts": [] }
      }
    },
    "E": {
      "status": "pending",
      "tasks": {
        "E-1": { "status": "pending", "artifacts": [] },
        "E-2": { "status": "pending", "artifacts": [] },
        "E-3": { "status": "pending", "artifacts": [] }
      }
    },
    "F": {
      "status": "pending",
      "tasks": {
        "F-1": { "status": "pending", "artifacts": [] },
        "F-2": { "status": "pending", "artifacts": [] },
        "F-3": { "status": "pending", "artifacts": [] }
      }
    }
  }
}
```

**ディレクトリの自動作成**: `data/lifecycle-state/{instance}/` が存在しない場合は作成する。

### 0-6. 実行フェーズの決定

| 条件 | 動作 |
|------|------|
| `--phase` 指定あり | そのフェーズのみ実行 |
| `--phase` 未指定 + `in_progress` フェーズあり | AskUserQuestion で確認後、そのフェーズを再開 |
| `--phase` 未指定 + `in_progress` なし | 最初の `pending` フェーズから実行 |

#### in_progress フェーズが存在する場合の確認

```
前回の実行で Phase {phase} が中断しています。

中断状態:
- タスク {task}: {status}
- 最終更新: {updated_at}

1. Phase {phase} を最初からやり直す
2. Phase {phase} の中断タスクから再開する
3. Phase {phase} をスキップして次のフェーズに進む

デフォルト: 2（中断タスクから再開）
```

### 0-7. モード決定

`--mode` が未指定の場合:

- lifecycle-state.json が新規作成された → `new`
- lifecycle-state.json が既存で `mode` フィールドあり → その値を使用
- lifecycle-state.json が既存で `mode` フィールドなし → `new`

`--mode redesign` が指定された場合:
- Phase C（Migration）が実行対象に含まれる
- Phase A-1 で既存スキーマの分析を実施する

---

## Phase A: Design（対話型オントロジー・スキーマ設計）

**ガイド**: `references/phase-a-design-guide.md` を読み込んで実行する。

### 実行手順

1. `Read references/phase-a-design-guide.md`
2. ガイドの手順に従い A-1 → A-2 → A-3 → A-4 を順次実行
3. 各タスク完了時に `lifecycle-state.json` を更新

### タスク概要

| タスク | 内容 | 対話 | 成果物 |
|--------|------|------|--------|
| A-1 | 目的定義（ユースケース・クエリ要件） | Yes | use_case 確定 |
| A-2 | オントロジー設計（ConceptCategory / Entity Type / Content Type / Relation Type） | Yes | `ontology.yaml` |
| A-3 | スキーマ設計（制約・インデックス） | Yes | `schema.yaml` |
| A-4 | Entity 正規化ルール | Yes | `ontology.yaml` 更新 |

### AskUserQuestion 制限

- **最大3回まで**の質問に制限する
- 各質問にはデフォルト回答を明記する
- 3回の質問で十分な情報が得られない場合は、デフォルト値で先に進む

### 開始条件

- Phase 0 が完了していること

### 終了条件

- `data/lifecycle-state/{instance}/ontology.yaml` が保存されている
- `data/lifecycle-state/{instance}/schema.yaml` が保存されている
- `lifecycle-state.json` の Phase A が `completed`

---

## Phase B: Pipeline（パイプラインコンポーネント自動生成）

**ガイド**: `references/phase-b-pipeline-guide.md` を読み込んで実行する。

### 実行手順

1. `Read references/phase-b-pipeline-guide.md`
2. ガイドの手順に従い B-1 → B-2 → B-3 → B-4 を順次実行
3. 各タスク完了時に `lifecycle-state.json` を更新

### タスク概要

| タスク | 内容 | 入力 | 成果物 |
|--------|------|------|--------|
| B-1 | 抽出プロンプト生成 | `ontology.yaml` + `extraction-prompt-template.md` | `extraction-prompt.md` |
| B-2 | Entity Linker 設定 | `ontology.yaml` + インスタンス YAML | `entity-linker-config.yaml` |
| B-3 | Emit Queue スクリプト設定 | `ontology.yaml` | `emit-queue-config.yaml` |
| B-4 | MERGE ガイド生成 | `ontology.yaml` + `schema.yaml` + `merge-patterns-template.md` | `merge-guide.md` |

### テンプレート参照

各テンプレートは `references/` 配下に存在する:

| テンプレート | パス |
|-------------|------|
| 抽出プロンプト | `references/extraction-prompt-template.md` |
| MERGE パターン | `references/merge-patterns-template.md` |
| 品質クエリ | `references/quality-queries-template.md` |
| オントロジー | `references/ontology-template.yaml` |

### 開始条件

- Phase A が `completed` であること

### 終了条件

- 全4成果物が `data/lifecycle-state/{instance}/` に保存されている
- `lifecycle-state.json` の Phase B が `completed`

---

## Phase C: Migration（既存データ移行）

**ガイド**: `references/phase-c-migration-guide.md` を読み込んで実行する。

### 実行条件

- `--mode redesign` の場合のみ実行
- `--mode new` の場合はスキップし、Phase D に進む

### 実行手順

1. `Read references/phase-c-migration-guide.md`
2. **C-1 前に AuraDB バックアップを確認**（必須）
3. ガイドの手順に従い C-1 → C-2 → C-3 → C-4 を順次実行
4. 各タスク完了時に `lifecycle-state.json` を更新

### タスク概要

| タスク | 内容 | 成果物 |
|--------|------|--------|
| C-1 | Entity 再分類計画 | `migration-plan.md` |
| C-2 | コンテンツ接続バックフィル | ABOUT/MENTIONS 補完 |
| C-3 | プロパティ一括更新 | null 値推定、正規化 |
| C-4 | 旧ラベル・リレーション削除 | クリーンアップ完了 |

### --dry-run の動作

`--dry-run` 指定時は全 Cypher クエリに `EXPLAIN` プレフィックスを付与し、実行計画のみを確認する。データの変更は行わない。

### 開始条件

- Phase B が `completed` であること
- `--mode redesign` であること
- AuraDB バックアップが最新であること

### 終了条件

- 全 Entity が新 ontology の entity_types に準拠
- 未接続コンテンツのバックフィルが完了
- 旧ラベル・リレーションが削除済み
- `lifecycle-state.json` の Phase C が `completed`

---

## Phase D: Quality（品質検証・スコアリング）

**ガイド**: `references/phase-d-quality-guide.md` を読み込んで実行する。

### 実行手順

1. `Read references/phase-d-quality-guide.md`
2. `Read references/quality-queries-template.md`
3. ガイドの手順に従い D-1 → D-2 → D-3 → D-4 を順次実行
4. 品質スコアを算出し、レーティング（A/B/C/D）を決定
5. 品質レポートを保存
6. `lifecycle-state.json` を更新

### タスク概要

| タスク | 内容 | 成果物 |
|--------|------|--------|
| D-1 | オントロジー適合検証 | 適合率レポート |
| D-2 | 重複検出・マージ | 重複候補リスト |
| D-3 | 孤立ノード検出 | 孤立ノードリスト |
| D-4 | カバレッジ計測 | カバレッジマトリクス |

### 品質スコアの重み

| カテゴリ | 重み |
|---------|------|
| D-1 オントロジー適合 | 30% |
| D-2 重複 | 20% |
| D-3 孤立ノード | 25% |
| D-4 カバレッジ | 25% |

### 開始条件

- Phase B が `completed`（`new` モード）
- Phase C が `completed`（`redesign` モード）

### 終了条件

- `data/lifecycle-state/{instance}/quality-queries.md` が保存されている
- `data/lifecycle-state/{instance}/quality-report-YYYYMMDD.md` が保存されている
- `lifecycle-state.json` の Phase D が `completed`

---

## Phase E: Operations（運用系スキル・クエリ更新）

**ガイド**: `references/phase-e-operations-guide.md` を読み込んで実行する。

### 実行手順

1. `Read references/phase-e-operations-guide.md`
2. ガイドの手順に従い E-1 → E-2 → E-3 を順次実行
3. 各タスク完了時に `lifecycle-state.json` を更新

### タスク概要

| タスク | 内容 | 成果物 |
|--------|------|--------|
| E-1 | enrichment スキルの更新/生成 | `enrichment-config.yaml` |
| E-2 | ギャップ分析クエリの更新 | `gap-analysis-queries.md` |
| E-3 | 横断リレーション強化ルール | `cross-rel-rules.yaml` |

### 開始条件

- Phase D が `completed` であること

### 終了条件

- 全3成果物が `data/lifecycle-state/{instance}/` に保存されている
- `lifecycle-state.json` の Phase E が `completed`

---

## Phase F: Utilization（対話型活用設計）

**ガイド**: `references/phase-f-utilization-guide.md` を読み込んで実行する。

### 実行手順

1. `Read references/phase-f-utilization-guide.md`
2. ガイドの手順に従い F-1 → F-2 → F-3 を順次実行
3. 各タスク完了時に `lifecycle-state.json` を更新
4. Phase F 完了後、lifecycle-state.json の全体ステータスを `completed` に設定

### タスク概要

| タスク | 内容 | 対話 | 成果物 |
|--------|------|------|--------|
| F-1 | ユースケース別クエリテンプレート設計 | Yes | `query-templates.md` |
| F-2 | パターン発見クエリ設計 | Yes | `discovery-queries.md` |
| F-3 | ダウンストリームワークフロー統合 | Yes | `workflow-integration.md` |

### AskUserQuestion 制限

- Phase F 全体で**最大3回まで**の質問に制限する
- 各質問にはデフォルト回答を明記する

### 開始条件

- Phase E が `completed` であること

### 終了条件

- 全3成果物が `data/lifecycle-state/{instance}/` に保存されている
- `lifecycle-state.json` の Phase F が `completed`
- `lifecycle-state.json` の全体ステータスが `completed`

---

## lifecycle-state.json の更新ルール

### フェーズステータス遷移

```
pending → in_progress → completed
                     → skipped (Phase C が --mode new の場合)
```

### タスク完了時の更新

```python
# タスク完了
state["phases"][phase]["tasks"][task]["status"] = "completed"
state["phases"][phase]["tasks"][task]["artifacts"] = [artifact_paths]
state["updated_at"] = current_datetime_iso8601

# フェーズ内の全タスクが completed → フェーズも completed
if all(t["status"] in ("completed", "skipped") for t in tasks.values()):
    state["phases"][phase]["status"] = "completed"
    state["current_phase"] = next_phase  # 次のフェーズに進む
```

### フェーズ開始時の更新

```python
state["phases"][phase]["status"] = "in_progress"
state["current_phase"] = phase
state["updated_at"] = current_datetime_iso8601
```

---

## --dry-run の動作

`--dry-run` フラグが指定された場合の各フェーズの動作:

| フェーズ | --dry-run 時の動作 |
|---------|-------------------|
| Phase A | 通常実行（設計のみで変更なし） |
| Phase B | 通常実行（ファイル生成のみ） |
| Phase C | 全 Cypher に `EXPLAIN` プレフィックス、データ変更なし |
| Phase D | 通常実行（読み取り専用クエリ） |
| Phase E | ファイル生成のみ、スキル設定の反映はスキップ |
| Phase F | 通常実行（設計のみ） |

---

## フェーズ間の受け渡しデータ

| 受渡元 | 受渡先 | データ |
|--------|--------|--------|
| A → B | `ontology.yaml`, `schema.yaml` | オントロジー定義、制約・インデックス定義 |
| B → C | `merge-guide.md`, `extraction-prompt.md` | MERGE パターン、抽出プロンプト |
| B → D | `ontology.yaml` | 品質検証の基準値 |
| C → D | 移行済みデータ | 品質検証の対象 |
| D → E | `quality-report-YYYYMMDD.md`, `quality-queries.md` | ギャップ分析・運用更新の入力 |
| E → F | `enrichment-config.yaml`, `gap-analysis-queries.md`, `cross-rel-rules.yaml` | 活用設計の入力 |

---

## 全成果物の保存先

```
data/lifecycle-state/{instance}/
  lifecycle-state.json       # Phase 0: フェーズ進捗管理
  ontology.yaml              # Phase A: オントロジー定義
  schema.yaml                # Phase A: 制約・インデックス定義
  extraction-prompt.md       # Phase B: 抽出プロンプト
  entity-linker-config.yaml  # Phase B: Entity Linker 設定
  emit-queue-config.yaml     # Phase B: Emit Queue 設定
  merge-guide.md             # Phase B: MERGE ガイド
  migration-plan.md          # Phase C: 移行計画（redesign のみ）
  quality-queries.md         # Phase D: 品質検証クエリ
  quality-report-YYYYMMDD.md # Phase D: 品質レポート
  enrichment-config.yaml     # Phase E: enrichment 設定
  gap-analysis-queries.md    # Phase E: ギャップ分析クエリ
  gap-analysis-YYYYMMDD.md   # Phase E: ギャップ分析結果
  cross-rel-rules.yaml       # Phase E: 横断リレーション強化ルール
  query-templates.md         # Phase F: クエリテンプレート
  discovery-queries.md       # Phase F: パターン発見クエリ
  workflow-integration.md    # Phase F: ワークフロー統合設計
```

---

## エラーハンドリング

| Phase | エラー | 対処 |
|-------|--------|------|
| 0 | インスタンス名が registry.yaml に未登録 | エラーメッセージを出力して終了 |
| 0 | MCP 接続テスト失敗 | エラーメッセージを出力して終了 |
| 0 | lifecycle-state.json パースエラー | バックアップを取得後、新規作成を提案 |
| A | AskUserQuestion 3回到達 | デフォルト値で確定し、Phase A を完了 |
| A | neo4j-data-modeling 検証失敗 | エラー内容を表示し、ユーザーに修正方針を確認 |
| B | ontology.yaml が不完全 | Phase A に差し戻し |
| B | relation_types に循環参照 | 警告を出力し、投入順序から除外 |
| C | AuraDB バックアップ未実施 | Phase C を開始しない。ユーザーにバックアップを促す |
| C | entity_type マッピングで不明な型 | ユーザーに判断を仰ぐ |
| C | 100件以上の削除 | 追加確認を求める |
| D | MCP 接続エラー | リトライ3回。失敗時は中断 |
| D | APOC 未インストール | Full-Text Index フォールバック |
| D | クエリタイムアウト | LIMIT を追加して再実行 |
| E | enrichment スキルが存在しない | 新規作成を提案 |
| E | 品質レポートが存在しない | Phase D に差し戻し |
| F | クエリテンプレートが MCP で実行できない | Cypher 構文を修正 |
| F | AskUserQuestion 3回到達 | デフォルト値で確定 |

---

## MUST / SHOULD / NEVER

### MUST

- Phase 0 で必ず registry.yaml と インスタンス YAML を読み込む
- Phase 0 で必ず MCP 接続テスト（`RETURN 1 AS ok`）を実行する
- Phase 0 で必ず lifecycle-state.json を読み込み or 新規作成する
- 各タスク完了時に lifecycle-state.json を更新する
- Phase A/F の AskUserQuestion は最大3回まで、各質問にデフォルト回答を明記する
- Phase C の C-1 前に AuraDB バックアップを確認する
- --dry-run 指定時は Phase C の Cypher に EXPLAIN プレフィックスを付与する
- 全成果物は `data/lifecycle-state/{instance}/` に保存する

### SHOULD

- sequential-thinking を使って設計判断を構造化する
- neo4j-data-modeling で Phase A のオントロジーを検証する
- Phase D の品質レポートに前回比較を含める
- Phase F のクエリテンプレートにパラメータ化されたプレースホルダーを含める

### NEVER

- Phase 0 をスキップしてフェーズを開始する
- lifecycle-state.json を更新せずにフェーズを完了する
- Phase C で AuraDB バックアップ確認なしにデータ変更を実行する
- Phase C で --dry-run の結果確認なしに本番実行する
- registry.yaml に未登録のインスタンス名で実行する

---

## 完了条件

- [ ] Phase 0: インスタンス設定読み込み・接続確認・lifecycle-state.json 準備完了
- [ ] Phase A: ontology.yaml / schema.yaml が確定（--phase A 指定時はここで終了）
- [ ] Phase B: 全4成果物が生成（--phase B 指定時はここで終了）
- [ ] Phase C: データ移行完了（redesign のみ。--phase C 指定時はここで終了）
- [ ] Phase D: 品質レポート・スコア算出完了（--phase D 指定時はここで終了）
- [ ] Phase E: 運用系設定更新完了（--phase E 指定時はここで終了）
- [ ] Phase F: 活用設計完了・lifecycle-state.json が全体 completed

---

## 関連リソース

| リソース | パス |
|---------|------|
| Phase A ガイド | `references/phase-a-design-guide.md` |
| Phase B ガイド | `references/phase-b-pipeline-guide.md` |
| Phase C ガイド | `references/phase-c-migration-guide.md` |
| Phase D ガイド | `references/phase-d-quality-guide.md` |
| Phase E ガイド | `references/phase-e-operations-guide.md` |
| Phase F ガイド | `references/phase-f-utilization-guide.md` |
| オントロジーテンプレート | `references/ontology-template.yaml` |
| 抽出プロンプトテンプレート | `references/extraction-prompt-template.md` |
| MERGE パターンテンプレート | `references/merge-patterns-template.md` |
| 品質クエリテンプレート | `references/quality-queries-template.md` |
| インスタンス設定 | `data/config/neo4j-instances/` |
| 成果物保存先 | `data/lifecycle-state/{instance}/` |
| コマンドファイル | `.claude/commands/neo4j-lifecycle.md` |
