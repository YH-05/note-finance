# Entity Extraction Prompt Template

コンテンツ分類（Fact/Tip/Story）と Entity 抽出を同時に行う LLM プロンプトテンプレート。
Phase 3 で各 raw_item に対して適用する。

---

## プロンプト

```
あなたはコンテンツ分析の専門家です。以下のテキストを分析し、分類と Entity 抽出を行ってください。

## 入力テキスト

タイトル: {title}
ソースURL: {source_url}
言語: {language}
ジャンル: {genre}

本文:
---
{content}
---

## タスク1: コンテンツ分類

以下の3タイプのいずれかに分類してください。

### 分類ルール

**Fact（事実・データ）**
シグナル:
- 統計データや数値が含まれる（「〇〇%」「〇〇万円」「〇〇人」）
- 調査結果や公式発表の引用がある
- 客観的な事実や現状の説明が主体
- 「〜によると」「〜の調査では」「〜が発表した」

**Tip（ハウツー・ノウハウ）**
シグナル:
- 手順やステップの説明がある（「まず〜」「次に〜」「ステップ1」）
- 推奨事項やベストプラクティスの提示
- 「〜すべき」「〜がおすすめ」「〜のコツ」
- ツールや方法の紹介・比較

**Story（体験談・事例）**
シグナル:
- 個人の体験や経験の記述がある（「私は〜」「〜してみた」）
- 事例紹介やケーススタディ
- インタビューや対談形式
- 時系列での出来事の記述（「最初は〜」「3ヶ月後に〜」）

複数のシグナルが混在する場合は、最も支配的なタイプを選択してください。

## タスク2: Entity 抽出

テキストから重要な Entity を 1-5 個抽出してください。

### 許可される entity_type

| entity_type | 説明 | 例 |
|-------------|------|-----|
| occupation | 職種・役職 | エンジニア、Webデザイナー、占い師 |
| platform | サービス・プラットフォーム | note.com、Coconala、YouTube |
| company | 企業・組織 | Google、リクルート |
| technique | 手法・テクニック | SEO対策、ポモドーロ |
| service | サービス | マッチングアプリ、転職エージェント |
| product | 製品 | iPhone、Notion |
| metric | 指標・数値 | 月収50万円、成功率80% |
| concept | 概念・用語 | パッシブインカム、副業解禁 |
| person | 人物 | 具体的な人名のみ |
| tool | ツール | Canva、ChatGPT |

### 抽出ルール

- 各コンテンツから最低1個、最大5個の Entity を抽出
- Entity の name は具体的かつ簡潔に（1-5語程度）
- 汎用的すぎる Entity は避ける（「仕事」「お金」など）
- ジャンルの entity_types_focus に含まれるタイプを優先的に抽出

## タスク3: Entity 間リレーション検出

抽出した Entity 間に意味的な関係がある場合、リレーションを検出してください。

### リレーション形式

from_entity::entity_type → to_entity::entity_type (rel_detail)

### rel_detail の例

| rel_detail | 説明 | 例 |
|-----------|------|-----|
| ENABLES | AがBを可能にする | Coconala::platform → 占い師::occupation (ENABLES) |
| USES | AがBを使用する | Webデザイナー::occupation → Canva::tool (USES) |
| COMPETES_WITH | AがBと競合する | ランサーズ::platform → Coconala::platform (COMPETES_WITH) |
| PART_OF | AがBの一部である | SEO対策::technique → ブログ運営::concept (PART_OF) |
| MEASURES | AがBを測定する | 月収50万円::metric → 副業::concept (MEASURES) |
| PRODUCES | AがBを生み出す | ChatGPT::tool → ブログ記事::product (PRODUCES) |

リレーションは0-5個。無理に作らず、明確な関係のみ記述してください。

## 出力形式

以下の JSON 形式で出力してください。

```json
{
  "content_type": "Fact | Tip | Story",
  "title": "元のタイトル（必要に応じて簡潔化）",
  "body": "コンテンツの要約（200-500字）",
  "source_url": "{source_url}",
  "source_type": "{source_type}",
  "language": "{language}",
  "topic": "このコンテンツの主要トピック（1-3語）",
  "entities": [
    {
      "name": "Entity名",
      "entity_type": "許可リストからのタイプ"
    }
  ],
  "entity_relations": [
    {
      "from_entity": "Entity名",
      "from_type": "entity_type",
      "to_entity": "Entity名",
      "to_type": "entity_type",
      "rel_detail": "リレーションタイプ"
    }
  ]
}
```

## 注意事項

- body は元テキストのコピーではなく、要約を作成すること
- 日本語コンテンツは日本語で、英語コンテンツは日本語に翻訳して要約
- Entity の name は日本語で統一（英語固有名詞はカタカナ or 原語）
- source_url は入力値をそのまま保持（絶対に変更しない）
```

---

## 出力 JSON と emit_creator_queue.py 入力の対応

このプロンプトの出力は、サイクル単位で以下の構造にラップされる:

```json
{
  "genre": "{selected_genre}",
  "cycle_id": "cycle-{YYYYMMDD-HHmmss}",
  "contents": [
    // ← 各 raw_item のプロンプト出力がここに入る
  ]
}
```

この JSON が `.tmp/creator-cycle-{YYYYMMDD-HHmmss}.json` として保存され、
`emit_creator_queue.py --input` の入力となる。
