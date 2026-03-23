# Phase B: Pipeline Guide

Phase A で確定したオントロジー・スキーマから、データ投入パイプラインの各コンポーネントを自動生成する Phase B の詳細手順。

---

## 前提条件

- Phase A が完了していること
- `data/lifecycle-state/{instance}/ontology.yaml` が存在すること
- `data/lifecycle-state/{instance}/schema.yaml` が存在すること

---

## タスク一覧

| タスク | 内容 | 入力 | 成果物 |
|--------|------|------|--------|
| B-1 | 抽出プロンプト生成 | `ontology.yaml` + `extraction-prompt-template.md` | `extraction-prompt.md` |
| B-2 | Entity Linker 設定 | `ontology.yaml` + インスタンス YAML | `entity-linker-config.yaml` |
| B-3 | Emit Queue スクリプト設定 | `ontology.yaml` | `emit-queue-config.yaml` |
| B-4 | MERGE ガイド生成 | `ontology.yaml` + `schema.yaml` + `merge-patterns-template.md` | `merge-guide.md` |

---

## B-1: 抽出プロンプト生成

### 手順

1. `references/extraction-prompt-template.md` を読み込む
2. `data/lifecycle-state/{instance}/ontology.yaml` を読み込む
3. プレースホルダーを ontology.yaml の値で置換する
4. 生成されたプロンプトを `data/lifecycle-state/{instance}/extraction-prompt.md` として保存する

### ontology-template.yaml からの埋め込みロジック

#### `{{DOMAIN_DESCRIPTION}}` の埋め込み

```python
domain_description = ontology["domain"]
# 例: "コンテンツ創作" → そのまま埋め込み
```

#### `{{ENTITY_TYPES_TABLE}}` の埋め込み

ontology.yaml の `entity_types` をマークダウン表に変換する。

```python
def generate_entity_types_table(ontology: dict) -> str:
    """entity_types からマークダウン表を生成する。"""
    table = "| entity_type | 説明 | 例 |\n|-------------|------|-----|\n"
    for et in ontology["entity_types"]:
        examples = et["examples"]
        if isinstance(examples, list):
            examples = ", ".join(examples)
        table += f"| {et['key']} | {et['description']} | {examples} |\n"
    return table
```

#### `{{CONCEPT_CATEGORIES_TABLE}}` の埋め込み

ontology.yaml の `concept_categories` を Layer 別にグループ化してマークダウン表に変換する。

```python
def generate_concept_categories_table(ontology: dict) -> str:
    """concept_categories を layer 別マークダウン表に変換する。"""
    categories_by_layer: dict[str, list] = {}
    for cc in ontology.get("concept_categories", []):
        layer = cc.get("layer", "Other")
        categories_by_layer.setdefault(layer, []).append(cc)

    if not categories_by_layer:
        return "(ConceptCategory 未定義 - Topic.category プロパティで代替)"

    table = ""
    for layer, cats in categories_by_layer.items():
        table += f"\n#### {layer}層\n\n"
        table += "| カテゴリ | 説明 |\n|---------|------|\n"
        for cc in cats:
            table += f"| {cc['name']} ({cc.get('name_ja', '')}) | {cc['description']} |\n"
    return table
```

#### `{{NORMALIZATION_RULES}}` の埋め込み

```python
def generate_normalization_rules(ontology: dict) -> str:
    """正規化ルールを箇条書きに変換する。"""
    rules = ""
    for rule in ontology["normalization_rules"]["general"]:
        rules += f"- {rule}\n"
    for et_key, rule in ontology["normalization_rules"]["per_entity_type"].items():
        rules += f"- {et_key}: {rule}\n"
    return rules
```

#### `{{CONTENT_TYPES_TABLE}}` の埋め込み

```python
def generate_content_types_table(ontology: dict) -> str:
    """content_types からマークダウン表を生成する。"""
    table = "| タイプ | 説明 | シグナル |\n|--------|------|----------|\n"
    for ct in ontology["content_types"]:
        table += f"| {ct['label']} | {ct['description']} | - |\n"
    return table
```

#### `{{RELATION_TYPES_FOR_EXTRACTION}}` の埋め込み

全リレーションのうち、LLM が抽出すべきリレーションのみを選択する。以下のリレーションは**自動設定**されるため除外する:

- `FROM_SOURCE` / `STATES_FACT` / `MAKES_CLAIM`（ソース接続: パイプラインが自動設定）
- `IN_GENRE`（ジャンル分類: パイプラインが自動設定）
- `FROM_DOMAIN`（ドメイン接続: パイプラインが自動設定）
- `CONTAINS_CHUNK`（チャンク接続: パイプラインが自動設定）
- `EXTRACTED_FROM`（抽出元: パイプラインが自動設定）

```python
def generate_extraction_relations(ontology: dict) -> str:
    """LLM が抽出すべきリレーションを選択してマークダウン化する。"""
    auto_rels = {
        "FROM_SOURCE", "STATES_FACT", "MAKES_CLAIM", "IN_GENRE",
        "FROM_DOMAIN", "CONTAINS_CHUNK", "EXTRACTED_FROM",
        "HAS_DATAPOINT", "FOR_PERIOD", "AUTHORED_BY", "TAGGED"
    }
    result = ""
    for rel in ontology["relation_types"]:
        if rel["type"] not in auto_rels:
            result += f"\n### {rel['type']}（{rel['from_label']} -> {rel['to_label']}）\n"
            result += f"{rel['description']}\n"
            if rel.get("properties"):
                result += f"プロパティ: {', '.join(rel['properties'])}\n"
    return result
```

#### `{{OUTPUT_JSON_SCHEMA}}` の埋め込み

content_types と entity_types から出力 JSON スキーマを動的に生成する。

```python
def generate_output_json_schema(ontology: dict) -> str:
    """出力 JSON のスキーマ定義を生成する。"""
    content_types_enum = " | ".join(ct["label"] for ct in ontology["content_types"])
    entity_types_enum = " | ".join(et["key"] for et in ontology["entity_types"])

    schema = {
        "content_type": content_types_enum,
        "title": "元のタイトル",
        "body": "コンテンツの要約（200-500字）",
        "source_url": "{source_url}",
        "language": "{language}",
        "entities": [
            {
                "name": "正規化済みEntity名",
                "entity_type": entity_types_enum
            }
        ]
    }

    # concept_categories がある場合
    if ontology.get("concept_categories"):
        category_enum = " | ".join(cc["name"] for cc in ontology["concept_categories"])
        schema["concepts"] = [
            {
                "name": "Concept名",
                "category": category_enum,
                "new_category": False
            }
        ]

    # LLM 抽出対象リレーションを追加
    # （auto_rels 以外を追加）

    return json.dumps(schema, ensure_ascii=False, indent=2)
```

#### `{{MAX_ENTITIES_PER_CONTENT}}` / `{{MAX_CONCEPTS_PER_CONTENT}}`

インスタンス設定または以下のデフォルト値を使用:

| パラメータ | デフォルト値 |
|-----------|------------|
| MAX_ENTITIES_PER_CONTENT | 10 |
| MAX_CONCEPTS_PER_CONTENT | 5 |

### 成果物

- `data/lifecycle-state/{instance}/extraction-prompt.md`

---

## B-2: Entity Linker 設定

### 手順

1. `ontology.yaml` の `entity_types`, `normalization_rules`, `alias_strategy` を読み込む
2. インスタンス YAML の `connection` 情報を読み込む
3. Entity Linker の設定 YAML を生成
4. `data/lifecycle-state/{instance}/entity-linker-config.yaml` として保存

### 設定 YAML の構造

```yaml
# Entity Linker Configuration
# Generated by neo4j-lifecycle Phase B-2

instance_name: "{instance_name}"
connection:
  bolt_uri: "{bolt_uri}"      # インスタンス YAML から
  user: "{user}"
  password: "{password}"

# 検索設定
search:
  fulltext_index: "{instance_name}_entity_fulltext"
  similarity_threshold: 0.85    # Jaro-Winkler しきい値
  fuzzy_layers: 2               # alias_strategy.fuzzy_layers から

# entity_type 別正規化
normalization:
  general:
    - "全角英数字は半角に統一"
    - "不要なスペースは除去"
  per_type:
    # ontology.yaml > normalization_rules.per_entity_type から生成
    platform: "公式英語表記"
    company: "公式英語表記"

# 有効な entity_type 一覧
valid_entity_types:
  # ontology.yaml > entity_types[].key から生成
  - platform
  - company
  - person
  - organization
```

### 成果物

- `data/lifecycle-state/{instance}/entity-linker-config.yaml`

---

## B-3: Emit Queue スクリプト設定

### 手順

1. `ontology.yaml` の `entity_types`, `content_types`, `concept_categories` を読み込む
2. 有効な enum 値を ontology.yaml から取得
3. Emit Queue の設定 YAML を生成
4. `data/lifecycle-state/{instance}/emit-queue-config.yaml` として保存

### 設定 YAML の構造

```yaml
# Emit Queue Configuration
# Generated by neo4j-lifecycle Phase B-3

instance_name: "{instance_name}"

# 有効な content_type 一覧（emit 時のバリデーションに使用）
valid_content_types:
  # ontology.yaml > content_types[].label から生成
  - Fact
  - Tip
  - Story

# 有効な entity_type 一覧
valid_entity_types:
  # ontology.yaml > entity_types[].key から生成
  - platform
  - company
  - person
  - organization

# 有効な ConceptCategory 一覧（存在する場合）
valid_concept_categories:
  # ontology.yaml > concept_categories[].name から生成
  - MonetizationMethod
  - AcquisitionChannel
  - Skill

# リレーション設定
relation_mappings:
  # content → concept: ABOUT or TAGGED
  content_to_concept: "ABOUT"
  # content → entity: MENTIONS or RELATES_TO
  content_to_entity: "MENTIONS"
  # content → source: FROM_SOURCE or STATES_FACT
  content_to_source: "FROM_SOURCE"

# graph-queue JSON の出力形式
output_format:
  # emit_graph_queue.py が生成する JSON のキー名
  sources_key: "sources"
  entities_key: "entities"
  content_key: "content"      # content_types の label を使用
  relations_key: "relations"
```

### ontology.yaml から enum 値を取得するロジック

```python
def extract_valid_enums(ontology: dict) -> dict:
    """ontology.yaml から emit-queue が使用する enum 値を抽出する。"""
    return {
        "content_types": [ct["label"] for ct in ontology["content_types"]],
        "entity_types": [et["key"] for et in ontology["entity_types"]],
        "concept_categories": [
            cc["name"] for cc in ontology.get("concept_categories", [])
        ],
        "relation_types": {
            rel["type"]: {
                "from": rel["from_label"],
                "to": rel["to_label"]
            }
            for rel in ontology["relation_types"]
        }
    }
```

### 成果物

- `data/lifecycle-state/{instance}/emit-queue-config.yaml`

---

## B-4: MERGE ガイド生成

### 手順

1. `references/merge-patterns-template.md` を読み込む
2. `ontology.yaml` と `schema.yaml` を読み込む
3. プレースホルダーを確定値で置換する
4. 生成されたガイドを `data/lifecycle-state/{instance}/merge-guide.md` として保存する

### プレースホルダー埋め込みロジック

#### `{{CONSTRAINT_DEFINITIONS}}` の埋め込み

```python
def generate_constraints(schema: dict) -> str:
    """schema.yaml > constraints から Cypher 制約定義を生成する。"""
    lines = []
    for c in schema["constraints"]:
        lines.append(
            f"CREATE CONSTRAINT {c['name']} IF NOT EXISTS\n"
            f"  FOR (n:{c['label']}) REQUIRE n.{c['property']} IS UNIQUE;"
        )
    return "\n".join(lines)
```

#### `{{INDEX_DEFINITIONS}}` の埋め込み

```python
def generate_indexes(schema: dict) -> str:
    """schema.yaml > indexes からインデックス定義を生成する。"""
    lines = []
    for idx in schema["indexes"]:
        if idx["type"] == "FULLTEXT":
            props = ", ".join(f"n.{p}" for p in idx["properties"])
            lines.append(
                f"CREATE FULLTEXT INDEX {idx['name']} IF NOT EXISTS\n"
                f"  FOR (n:{idx['label']}) ON EACH [{props}];"
            )
        else:  # BTREE
            props = ", ".join(f"n.{p}" for p in idx["properties"])
            lines.append(
                f"CREATE INDEX {idx['name']} IF NOT EXISTS\n"
                f"  FOR (n:{idx['label']}) ON ({props});"
            )
    return "\n".join(lines)
```

#### `{{NODE_DEFINITIONS}}` の埋め込み

`ontology.yaml` の `content_types` + `common_nodes` から各ノードの MERGE Cypher パターンを生成する。

```python
def generate_node_merge(node_def: dict) -> str:
    """ノード定義から MERGE Cypher パターンを生成する。"""
    label = node_def["label"]
    key_prop = node_def["key_property"]
    required = node_def.get("required_properties", [])
    optional = node_def.get("optional_properties", [])

    param_name = label.lower() + "s"

    lines = [
        f"UNWIND ${param_name} AS row",
        f"MERGE (n:{label} {{{key_prop}: row.{key_prop}}})",
        f"ON CREATE SET n.created_at = datetime()",
    ]

    set_props = [p for p in required if p != key_prop]
    set_props += optional
    if set_props:
        set_lines = [f"    n.{p} = row.{p}" for p in set_props]
        set_lines.append("    n.updated_at = datetime()")
        lines.append("SET " + ",\n".join(set_lines))

    return "\n".join(lines)
```

#### `{{RELATION_DEFINITIONS}}` の埋め込み

`ontology.yaml` の `relation_types` から各リレーションの MERGE Cypher パターンを生成する。

```python
def generate_rel_merge(rel_def: dict, ontology: dict) -> str:
    """リレーション定義から MERGE Cypher パターンを生成する。"""
    rel_type = rel_def["type"]
    from_label = rel_def["from_label"]
    to_label = rel_def["to_label"]
    properties = rel_def.get("properties", [])

    from_key = get_key_property(ontology, from_label)
    to_key = get_key_property(ontology, to_label)

    lines = [
        "UNWIND $rels AS row",
        f"MATCH (a:{from_label} {{{from_key}: row.from_id}})",
        f"MATCH (b:{to_label} {{{to_key}: row.to_id}})",
        f"MERGE (a)-[r:{rel_type}]->(b)",
    ]

    if properties:
        set_lines = [f"r.{p} = row.{p}" for p in properties]
        lines.append("SET " + ", ".join(set_lines))

    return "\n".join(lines)
```

#### `{{INGESTION_ORDER}}` の埋め込み

`relation_types` の依存関係からトポロジカルソートで投入順序を算出する。

```python
def calculate_ingestion_order(ontology: dict) -> str:
    """リレーションの依存関係から投入順序を算出する。"""
    # 1. 全ノードラベルを収集
    all_labels = set()
    for ct in ontology["content_types"]:
        all_labels.add(ct["label"])
    for cn in ontology["common_nodes"]:
        all_labels.add(cn["label"])
    if ontology.get("concept_categories"):
        all_labels.add("ConceptCategory")
        all_labels.add("Concept")

    # 2. 依存グラフを構築
    # リレーションの to_label が先に存在する必要がある
    dependencies = {}
    for rel in ontology["relation_types"]:
        from_l = rel["from_label"].strip("[]").split("|")
        to_l = rel["to_label"].strip("[]").split("|")
        for fl in from_l:
            fl = fl.strip()
            for tl in to_l:
                tl = tl.strip()
                dependencies.setdefault(fl, set()).add(tl)

    # 3. トポロジカルソートで順序を決定
    # ... (標準的なトポロジカルソートアルゴリズム)

    # 4. Phase 2（ノード投入）→ Phase 3（リレーション投入）の2段階で出力
    return result
```

#### `{{VERIFICATION_QUERIES}}` の埋め込み

content_types + relation_types から投入後の検証クエリを生成する。

```python
def generate_verification_queries(ontology: dict) -> str:
    """投入検証クエリを生成する。"""
    queries = []

    # ノード数確認
    queries.append(
        "-- ノード数確認\n"
        "MATCH (n)\n"
        "WHERE NOT 'Memory' IN labels(n)\n"
        "RETURN labels(n)[0] AS label, count(n) AS cnt\n"
        "ORDER BY cnt DESC"
    )

    # 各コンテンツタイプの孤立チェック
    for ct in ontology["content_types"]:
        # コンテンツ → ソース接続チェック
        source_rel = get_content_to_source_rel(ontology)
        queries.append(
            f"-- {ct['label']} の孤立チェック\n"
            f"MATCH (n:{ct['label']})\n"
            f"WHERE NOT 'Memory' IN labels(n)\n"
            f"AND NOT (n)-[:{source_rel}]->()\n"
            f"RETURN count(n) AS orphan_{ct['label'].lower()}s"
        )

    return "\n\n".join(queries)
```

### 成果物

- `data/lifecycle-state/{instance}/merge-guide.md`

---

## Phase B 完了条件

- [ ] B-1: `extraction-prompt.md` が生成され、全プレースホルダーが置換済み
- [ ] B-2: `entity-linker-config.yaml` が生成されている
- [ ] B-3: `emit-queue-config.yaml` が生成され、有効な enum 値が含まれている
- [ ] B-4: `merge-guide.md` が生成され、制約・インデックス・MERGE パターン・投入順序が含まれている
- [ ] lifecycle-state.json の Phase B が `completed` になっている

---

## Phase B → Phase C/D への受け渡し

| ファイル | 用途 |
|---------|------|
| `extraction-prompt.md` | Phase E: enrichment スキルが参照 |
| `entity-linker-config.yaml` | entity_linker.py が参照 |
| `emit-queue-config.yaml` | emit_queue スクリプトが参照 |
| `merge-guide.md` | `save-to-{instance}-graph` スキルが参照、Phase C の移行 Cypher のベース |

---

## エラーハンドリング

| エラー | 対処 |
|--------|------|
| ontology.yaml が不完全 | 不足セクションを Phase A に差し戻して補完 |
| concept_categories 未定義 | Topic.category プロパティによる代替パスを生成 |
| relation_types に循環参照 | 警告を出力し、投入順序から除外して手動対応を推奨 |
| schema.yaml の制約名重複 | インスタンス名プレフィックスで一意性を保証 |

---

## 関連リソース

| リソース | パス |
|---------|------|
| 抽出プロンプトテンプレート | `references/extraction-prompt-template.md` |
| MERGE パターンテンプレート | `references/merge-patterns-template.md` |
| オントロジーテンプレート | `references/ontology-template.yaml` |
| インスタンス設定 | `data/config/neo4j-instances/{instance}.yaml` |
