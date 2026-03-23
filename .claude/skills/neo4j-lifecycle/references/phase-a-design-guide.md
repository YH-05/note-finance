# Phase A: Design Guide

対話的にオントロジーとスキーマを設計する Phase A の詳細手順。
`project-discuss` スキルの AskUserQuestion パターンを採用し、ユーザーとの対話を通じてドメイン固有のナレッジグラフ構造を決定する。

---

## 前提条件

- Phase 0（Init）が完了していること
- インスタンス YAML が `data/config/neo4j-instances/{instance}.yaml` に存在すること
- MCP 接続テスト（`RETURN 1 AS ok`）が成功していること
- `--mode` が `new` または `redesign` のいずれかが確定していること

---

## タスク一覧

| タスク | 内容 | 対話 | 成果物 |
|--------|------|------|--------|
| A-1 | 目的定義 | Yes | use_case 確定 |
| A-2 | オントロジー設計 | Yes | `ontology.yaml` |
| A-3 | スキーマ設計 | Yes | `schema.yaml` |
| A-4 | Entity 正規化ルール | Yes | `ontology.yaml` 更新 |

---

## A-1: 目的定義（ユースケース・クエリ要件）

### 手順

1. インスタンス YAML の `use_case` と `description` を読み込む
2. `--mode redesign` の場合: MCP read で既存スキーマ・ノード件数を取得
3. ユーザーに目的を確認する（AskUserQuestion）
4. 回答を `data/lifecycle-state/{instance}/lifecycle-state.json` に記録

### AskUserQuestion プロンプト例

#### 質問1: ドメイン確認（必須）

```
このナレッジグラフの主な目的を教えてください。

現在のインスタンス設定:
- インスタンス名: {instance_name}
- 用途: {use_case}
- 説明: {description}

以下のいずれかを選択するか、自由に記述してください:

1. 上記の設定でそのまま進める
2. 用途を修正したい（具体的に記述してください）
3. ユースケースを追加したい

デフォルト: 1（上記の設定でそのまま進める）
```

#### 質問2: クエリ要件（必須）

```
このナレッジグラフに対して、どのようなクエリを実行したいですか？

例:
- 「あるトピックに関連する全てのソースを取得したい」
- 「企業間の関連性を探索したい」
- 「特定のカテゴリの知識量（コンテンツ件数）を把握したい」
- 「時系列でデータの変化を追跡したい」

デフォルト: インスタンス YAML の use_case から推定
```

#### 質問3: 対象データの確認（redesign モードのみ）

```
既存データの分析結果:
- ノード数: {node_count}
- リレーション数: {rel_count}
- ラベル別分布: {label_distribution}

既存データについて:
1. 全て新スキーマに移行する
2. 一部のデータのみ移行する（対象を指定してください）
3. 既存データは保持し、新規データのみ新スキーマで管理する

デフォルト: 1（全て移行）
```

### AskUserQuestion 制限

- **最大3回まで**の質問に制限する
- 3回の質問で十分な情報が得られない場合は、デフォルト値で先に進み、後のフェーズで調整する
- 各質問にはデフォルト回答を明記し、ユーザーが「デフォルトで」と回答できるようにする

### 成果物

`lifecycle-state.json` の `phases.A.tasks.A-1` を更新:

```json
{
  "status": "completed",
  "artifacts": [],
  "decisions": {
    "domain": "コンテンツ創作",
    "use_cases": ["テーマ別知識検索", "コンテンツ企画支援"],
    "query_requirements": ["トピック横断検索", "カバレッジ分析"],
    "data_migration_strategy": "full"
  }
}
```

---

## A-2: オントロジー設計

### 手順

1. `ontology-template.yaml` を読み込む
2. A-1 の決定事項に基づき、ConceptCategory を設計
3. ユーザーに ConceptCategory の確認を求める
4. Entity Type を設計
5. Content Type を設計
6. Relation Type を設計
7. 確定した ontology を `data/lifecycle-state/{instance}/ontology.yaml` に保存

### ontology-template.yaml のプレースホルダー埋め込みロジック

#### Step 1: メタ情報の埋め込み

```yaml
schema_version: "{instance_name}-2.0"  # インスタンス YAML の schema_version から
instance_name: "{instance_name}"       # インスタンス YAML の instance_name から
domain: "{description}"                # A-1 で確定した domain 説明
created_at: "{current_datetime}"       # ISO 8601 形式
updated_at: "{current_datetime}"
```

#### Step 2: ConceptCategory の決定

A-1 のドメインに基づき、ConceptCategory 候補を提案する。

**提案生成ロジック**:
1. ドメインキーワードから Layer（What/How/Meta）を判定
2. 各 Layer に 3-7 個のカテゴリを生成
3. creator v2 / research v2 の参考例を参照して、ドメインに適合するカテゴリを選定

**ユーザー確認（AskUserQuestion）**:

```
以下の ConceptCategory を提案します。修正・追加・削除があれば教えてください。

{提案された ConceptCategory の表}

1. この提案で進める
2. カテゴリを追加したい（名前と説明を記述してください）
3. カテゴリを削除・修正したい（対象と変更内容を記述してください）

デフォルト: 1（この提案で進める）
```

#### Step 3: Entity Type の決定

ドメインに固有の Entity Type を定義する。

- `ontology-template.yaml` の参考例（creator v2 / research v2）を参照
- `common_nodes` の Entity は全インスタンス共通のため、ここでは `entity_types` のサブタイプを定義
- 各 entity_type に `normalization` ルールを付与

#### Step 4: Content Type の決定

ナレッジの種類（Fact, Tip, Story, Claim 等）を定義する。

- ドメインに適した content_type を選定
- 各 content_type に `key_property`, `text_property`, `extra_properties` を設定

#### Step 5: Relation Type の決定

ノード間の接続ルールを定義する。

- `ontology-template.yaml` の参考例を参照
- `from_label`, `to_label`, `cardinality` を明示
- `properties` が必要なリレーションを特定

### neo4j-data-modeling MCP による検証

`mcp__neo4j-data-modeling__validate_data_model` でオントロジー構造を検証する。

```
validate_data_model に渡す内容:
- nodes: content_types + common_nodes から全ノード定義
- relationships: relation_types から全リレーション定義
```

検証エラーがある場合は修正してから保存する。

### 成果物

- `data/lifecycle-state/{instance}/ontology.yaml`（確定版）
- `lifecycle-state.json` の `phases.A.tasks.A-2` を更新

---

## A-3: スキーマ設計（制約・インデックス）

### 手順

1. A-2 の `ontology.yaml` を読み込む
2. 各ノードの key_property に対して UNIQUE 制約を生成
3. 検索用 Full-Text Index を生成
4. B-Tree Index が必要なプロパティを特定
5. ユーザーに確認（省略可。A-2 で十分な対話が行われた場合）
6. `data/lifecycle-state/{instance}/schema.yaml` に保存

### 制約生成ルール

```python
# ontology.yaml の content_types + common_nodes から制約を生成
constraints = []
for node in content_types + common_nodes:
    constraint_name = f"unique_{instance_name}_{node['label'].lower()}_{node['key_property']}"
    constraints.append({
        "name": constraint_name,
        "label": node["label"],
        "property": node["key_property"],
        "type": "UNIQUE"
    })
```

### インデックス生成ルール

```python
# Full-Text Index: Entity.name, Concept/Topic.name に対して
indexes = [
    {
        "name": f"{instance_name}_entity_fulltext",
        "type": "FULLTEXT",
        "label": "Entity",
        "properties": ["name"]
    }
]

# concept_categories が定義されている場合
if ontology.get("concept_categories"):
    indexes.append({
        "name": f"{instance_name}_concept_fulltext",
        "type": "FULLTEXT",
        "label": "Concept",  # or Topic
        "properties": ["name"]
    })

# B-Tree Index: 頻繁にフィルターされるプロパティ
for node in content_types:
    for prop in node.get("extra_properties", []):
        if prop in ["category", "entity_type", "source_type"]:
            indexes.append({
                "name": f"idx_{instance_name}_{node['label'].lower()}_{prop}",
                "type": "BTREE",
                "label": node["label"],
                "properties": [prop]
            })
```

### schema.yaml 出力形式

```yaml
schema_version: "{instance_name}-2.0"
instance_name: "{instance_name}"

constraints:
  - name: "unique_{instance}_entity_key"
    label: Entity
    property: entity_key
    type: UNIQUE
  - name: "unique_{instance}_source_id"
    label: Source
    property: source_id
    type: UNIQUE
  # ... content_types の各ノードも含む

indexes:
  - name: "{instance}_entity_fulltext"
    type: FULLTEXT
    label: Entity
    properties: [name]
  - name: "idx_{instance}_topic_category"
    type: BTREE
    label: Topic
    properties: [category]
  # ... 必要なインデックスを全て含む
```

### 成果物

- `data/lifecycle-state/{instance}/schema.yaml`
- `lifecycle-state.json` の `phases.A.tasks.A-3` を更新

---

## A-4: Entity 正規化ルール

### 手順

1. A-2 の `ontology.yaml` の entity_types を読み込む
2. 各 entity_type に対する正規化ルールを定義
3. Alias 戦略（ファジーマッチング層数）を設定
4. `ontology.yaml` の `normalization_rules` と `alias_strategy` セクションを更新

### 正規化ルール定義

以下の観点でルールを設定:

| 観点 | ルール例 |
|------|---------|
| 文字種統一 | 全角英数字は半角に統一 |
| スペース正規化 | 不要なスペースは除去 |
| 句読点除去 | 末尾の句読点は除去 |
| entity_type 固有 | platform: 公式英語表記、person: 日本人は漢字 等 |

### Alias 戦略

```yaml
alias_strategy:
  enabled: true        # Alias ノードの使用有無
  fuzzy_layers: 2      # ファジーマッチング層数（1-3）
                        # 1: 完全一致のみ
                        # 2: 完全一致 + Jaro-Winkler > 0.85
                        # 3: 2 + Full-Text Index 検索
  sources:
    - entity-aliases.yaml   # 手動定義（存在する場合）
    - auto_detected          # entity_linker.py が自動検出
```

### 成果物

- `data/lifecycle-state/{instance}/ontology.yaml`（normalization_rules, alias_strategy 更新）
- `lifecycle-state.json` の `phases.A.tasks.A-4` を更新

---

## Phase A 完了条件

- [ ] A-1: ユースケースとクエリ要件が確定している
- [ ] A-2: `ontology.yaml` が `data/lifecycle-state/{instance}/` に保存されている
- [ ] A-2: neo4j-data-modeling でオントロジーが検証済み
- [ ] A-3: `schema.yaml` が `data/lifecycle-state/{instance}/` に保存されている
- [ ] A-4: 正規化ルールと Alias 戦略が ontology.yaml に含まれている
- [ ] AskUserQuestion は最大3回以内に収まっている
- [ ] lifecycle-state.json の Phase A が `completed` になっている

---

## Phase A → Phase B への受け渡し

Phase B は以下のファイルを入力として使用する:

| ファイル | Phase B での用途 |
|---------|-----------------|
| `ontology.yaml` | B-1 抽出プロンプト生成、B-2 Entity Linker 設定、B-3 Emit Queue 設定、B-4 MERGE ガイド生成 |
| `schema.yaml` | B-4 MERGE ガイド生成（制約・インデックス定義） |
| `lifecycle-state.json` | フェーズ進捗管理 |

---

## エラーハンドリング

| エラー | 対処 |
|--------|------|
| ユーザーが全てデフォルトで回答 | デフォルト値で ontology.yaml を生成し、Phase B で微調整 |
| neo4j-data-modeling 検証失敗 | エラー内容を表示し、ユーザーに修正方針を確認 |
| 既存スキーマとの競合（redesign） | 既存制約を一覧表示し、削除・変更の承認を得る |
| AskUserQuestion 3回到達 | 未確定項目はデフォルト値で確定し、Phase A を完了 |

---

## 関連リソース

| リソース | パス |
|---------|------|
| オントロジーテンプレート | `references/ontology-template.yaml` |
| project-discuss（AskUserQuestion パターン） | `.claude/skills/project-discuss/SKILL.md` |
| neo4j-data-modeling MCP | `mcp__neo4j-data-modeling__validate_data_model` |
| インスタンス設定 | `data/config/neo4j-instances/{instance}.yaml` |
