# Extraction Prompt Template

neo4j-lifecycle Phase B-1 で使用する LLM 抽出プロンプトテンプレート。
`ontology-template.yaml` の確定値を埋め込んで、インスタンス固有の抽出プロンプトを生成する。

## Phase B での埋め込み手順

1. `data/lifecycle-state/{instance}/ontology.yaml` を読み込む
2. 以下のプレースホルダーを ontology.yaml の値で置換する
3. 生成されたプロンプトを `data/lifecycle-state/{instance}/extraction-prompt.md` として保存する
4. enrichment スキルや emit_queue スクリプトがこのプロンプトを参照する

## プレースホルダー一覧

| プレースホルダー | ソース | 説明 |
|-----------------|--------|------|
| `{{DOMAIN_DESCRIPTION}}` | `ontology.yaml > domain` | ドメインの説明 |
| `{{ENTITY_TYPES_TABLE}}` | `ontology.yaml > entity_types` | entity_type のマークダウン表 |
| `{{CONCEPT_CATEGORIES_TABLE}}` | `ontology.yaml > concept_categories` | ConceptCategory のマークダウン表 |
| `{{NORMALIZATION_RULES}}` | `ontology.yaml > normalization_rules` | 正規化ルールの箇条書き |
| `{{CONTENT_TYPES_TABLE}}` | `ontology.yaml > content_types` | content_type の分類基準 |
| `{{RELATION_TYPES_FOR_EXTRACTION}}` | `ontology.yaml > relation_types` | 抽出対象リレーション |
| `{{OUTPUT_JSON_SCHEMA}}` | content_types + entity_types から生成 | 出力 JSON の構造定義 |
| `{{MAX_ENTITIES_PER_CONTENT}}` | インスタンス設定 | 1コンテンツあたりの Entity 上限 |
| `{{MAX_CONCEPTS_PER_CONTENT}}` | インスタンス設定 | 1コンテンツあたりの Concept 上限 |

---

## プロンプトテンプレート本体

```
あなたはコンテンツ分析とナレッジグラフ構築の専門家です。
以下のテキストを分析し、分類・Entity抽出・Concept抽出・リレーション検出を行ってください。

ドメイン: {{DOMAIN_DESCRIPTION}}

## 入力テキスト

タイトル: {title}
ソースURL: {source_url}
言語: {language}

本文:
---
{content}
---

## タスク1: コンテンツ分類

以下のコンテンツタイプのいずれかに分類してください。

{{CONTENT_TYPES_TABLE}}

<!-- ================================================================
  Phase B 埋め込み手順:
  ontology.yaml > content_types をマークダウン表に変換する。

  --- creator v2 参考例 ---
  | タイプ | 説明 | シグナル |
  |--------|------|---------|
  | Fact | 事実・データ | 統計データ、調査結果、公式発表 |
  | Tip | ハウツー・ノウハウ | 手順、推奨事項、ベストプラクティス |
  | Story | 体験談・事例 | 個人体験、ケーススタディ、時系列 |

  --- research v2 参考例 ---
  | タイプ | 説明 | シグナル |
  |--------|------|---------|
  | Fact | 検証済みの事実・データ | 統計、研究結果、公式データ |
  | Claim | 主張・意見・予測 | アナリスト見解、予測、論評 |
  ================================================================ -->

複数のシグナルが混在する場合は、最も支配的なタイプを選択してください。

## タスク2: Entity 抽出（固有名詞）

テキストから**具体的な固有名詞**を抽出してください。
「固有の運営者・URL・実在の人物がいるもの」が Entity です。

### entity_type 一覧

{{ENTITY_TYPES_TABLE}}

<!-- ================================================================
  Phase B 埋め込み手順:
  ontology.yaml > entity_types をマークダウン表に変換する。

  --- creator v2 参考例 ---
  | entity_type | 説明 | 例 |
  |-------------|------|-----|
  | platform | サービス・プラットフォーム・ツール | Instagram, Coconala, ChatGPT |
  | company | 企業・組織 | Google, Match Group |
  | person | 実在の人物 | 林知佳, Elon Musk |
  | organization | 公的機関・団体 | 厚生労働省, 国税庁 |

  --- research v2 参考例 ---
  | entity_type | 説明 | 例 |
  |-------------|------|-----|
  | company | 上場企業・非上場企業 | Apple Inc., トヨタ自動車 |
  | index | 株価指数・ベンチマーク | S&P 500, TOPIX |
  | commodity | 商品先物・原材料 | WTI Crude Oil, Gold |
  | country | 国家・経済圏 | United States, Indonesia |
  | organization | 中央銀行・規制当局 | Federal Reserve, IMF |
  | person | 経営者・政策担当者 | Jerome Powell |
  | sector | 産業セクター | Technology, Financials |
  | regulation | 法規制・政策 | Basel III, Dodd-Frank Act |
  ================================================================ -->

### 正規化ルール（必須）

{{NORMALIZATION_RULES}}

<!-- ================================================================
  Phase B 埋め込み手順:
  ontology.yaml > normalization_rules を箇条書きに変換する。

  --- creator v2 参考例 ---
  - platform/company: 公式英語表記（インスタ → Instagram）
  - person: 日本人は漢字、外国人はアルファベット
  - organization: 公式名称
  - 全角英数字は半角に統一
  - 不要なスペースは除去

  --- research v2 参考例 ---
  - company: 公式英語表記またはティッカー
  - index: 公式略称
  - country: 英語正式名
  - organization: 公式英語略称
  - 全角英数字は半角に統一
  ================================================================ -->

### 抽出ルール

- 各コンテンツから 0〜{{MAX_ENTITIES_PER_CONTENT}} 個の Entity を抽出
- 汎用的すぎるものは Entity にしない（Concept として抽出）
- Entity の name は具体的かつ簡潔に

## タスク3: Concept 抽出（ドメイン概念）

テキストから**一般的なドメイン概念**を抽出し、以下のカテゴリのいずれかに分類してください。
「○○とは何か」で説明できる一般的な概念が Concept です。

### ConceptCategory 一覧

{{CONCEPT_CATEGORIES_TABLE}}

<!-- ================================================================
  Phase B 埋め込み手順:
  ontology.yaml > concept_categories をマークダウン表（layer 別）に変換する。

  --- creator v2 参考例 ---
  #### What層（何についてか）
  | カテゴリ | 説明 | 例 |
  |---------|------|-----|
  | MonetizationMethod | 収益化手段 | スキル販売, アフィリエイト |
  | AcquisitionChannel | 集客チャネル | SNS集客, SEOブログ集客 |
  | ...

  #### How層（どう書くか）
  | カテゴリ | 説明 | 例 |
  |---------|------|-----|
  | PersuasionTechnique | 説得技法 | 社会的証明, 希少性 |
  | ...

  --- research v2 参考例 ---
  ※ research v2 は ConceptCategory を使用しない場合がある。
  ※ その場合は Topic ノードの category プロパティで代替する。
  ================================================================ -->

### 抽出ルール

- 各コンテンツから 1〜{{MAX_CONCEPTS_PER_CONTENT}} 個の Concept を抽出
- **必ず1つ以上の ConceptCategory に分類**すること
- 既存カテゴリに該当しない場合は、新しいカテゴリ名を提案してよい（new_category: true）
- 汎用的すぎるものは避ける

## タスク4: リレーション検出

抽出した Entity と Concept 間のリレーションを検出してください。

{{RELATION_TYPES_FOR_EXTRACTION}}

<!-- ================================================================
  Phase B 埋め込み手順:
  ontology.yaml > relation_types のうち、LLM 抽出で検出すべきリレーションを選択し、
  マークダウン表に変換する。全リレーションが抽出対象とは限らない。
  （FROM_SOURCE, IN_GENRE 等のメタリレーションは自動設定されるため除外）

  --- creator v2 参考例 ---
  ### SERVES_AS（Entity → Concept）
  Entity が Concept に対してどのような役割を果たしているかを検出。
  形式: Entity名 → Concept名 (context)
  例: Instagram → SNS集客 (占い師の主要集客チャネルとして)

  ### Concept 間リレーション
  | タイプ | 説明 | 例 |
  |--------|------|-----|
  | ENABLES | AがBを可能にする | SNS集客 → オンライン鑑定 |
  | REQUIRES | AにはBが必要 | アフィリエイト → SEOブログ集客 |
  | COMPETES_WITH | AとBは代替関係 | SNS集客 ↔ SEOブログ集客 |

  --- research v2 参考例 ---
  ### RELATES_TO（Fact/Claim → Entity）
  事実や主張が言及するエンティティを検出。
  形式: Fact/Claim → Entity名
  例: "S&P500が過去最高値を更新" → S&P 500
  ================================================================ -->

- 0〜5個。無理に作らず、明確な関係のみ記述してください。

## 出力形式

以下の JSON 形式で出力してください。

{{OUTPUT_JSON_SCHEMA}}

<!-- ================================================================
  Phase B 埋め込み手順:
  content_types と entity_types から出力 JSON スキーマを生成する。

  --- creator v2 参考例 ---
  ```json
  {
    "content_type": "Fact | Tip | Story",
    "title": "元のタイトル",
    "body": "コンテンツの要約（200-500字）",
    "source_url": "{source_url}",
    "source_type": "{source_type}",
    "language": "{language}",
    "entities": [
      {
        "name": "正規化済みEntity名",
        "entity_type": "platform | company | person | organization"
      }
    ],
    "concepts": [
      {
        "name": "Concept名",
        "category": "ConceptCategory名",
        "new_category": false
      }
    ],
    "serves_as": [
      {
        "entity_name": "Entity名",
        "concept_name": "Concept名",
        "context": "役割の説明"
      }
    ],
    "concept_relations": [
      {
        "from_concept": "Concept名",
        "to_concept": "Concept名",
        "rel_type": "ENABLES | REQUIRES | COMPETES_WITH"
      }
    ]
  }
  ```

  --- research v2 参考例 ---
  ```json
  {
    "content_type": "Fact | Claim",
    "title": "元のタイトル",
    "content": "コンテンツの要約",
    "source_url": "{source_url}",
    "language": "{language}",
    "entities": [
      {
        "name": "正規化済みEntity名",
        "entity_type": "company | index | commodity | ..."
      }
    ],
    "topics": [
      {
        "name": "Topic名",
        "category": "macro | equity | ..."
      }
    ],
    "relates_to": [
      {
        "content_ref": "this",
        "entity_name": "Entity名"
      }
    ]
  }
  ```
  ================================================================ -->

## 注意事項

- body/content は元テキストのコピーではなく、要約を作成すること
- 英語コンテンツは日本語に翻訳して要約（インスタンス設定に依存）
- source_url は入力値をそのまま保持（絶対に変更しない）
- Entity と Concept を混同しない（固有名詞 vs 一般概念）
```

---

## プレースホルダー生成ロジック

Phase B-1 でオーケストレーターが実行する変換ロジック。

### `{{ENTITY_TYPES_TABLE}}` の生成

```python
# ontology.yaml > entity_types からマークダウン表を生成
table = "| entity_type | 説明 | 例 |\n|-------------|------|-----|\n"
for et in ontology["entity_types"]:
    examples = ", ".join(et["examples"]) if isinstance(et["examples"], list) else et["examples"]
    table += f"| {et['key']} | {et['description']} | {examples} |\n"
```

### `{{CONCEPT_CATEGORIES_TABLE}}` の生成

```python
# ontology.yaml > concept_categories を layer 別にグループ化してマークダウン表を生成
from itertools import groupby

categories_by_layer = {}
for cc in ontology["concept_categories"]:
    layer = cc.get("layer", "Other")
    categories_by_layer.setdefault(layer, []).append(cc)

table = ""
for layer, cats in categories_by_layer.items():
    table += f"\n#### {layer}層\n\n| カテゴリ | 説明 | 例 |\n|---------|------|-----|\n"
    for cc in cats:
        table += f"| {cc['name']} | {cc['description']} | - |\n"
```

### `{{NORMALIZATION_RULES}}` の生成

```python
# ontology.yaml > normalization_rules を箇条書きに変換
rules = ""
for rule in ontology["normalization_rules"]["general"]:
    rules += f"- {rule}\n"
for et_key, rule in ontology["normalization_rules"]["per_entity_type"].items():
    rules += f"- {et_key}: {rule}\n"
```

### `{{OUTPUT_JSON_SCHEMA}}` の生成

```python
# content_types + entity_types から出力 JSON 構造を生成
# content_type の enum: content_types の label を列挙
# entities[].entity_type の enum: entity_types の key を列挙
# concepts[].category の enum: concept_categories の name を列挙（存在する場合）
```
