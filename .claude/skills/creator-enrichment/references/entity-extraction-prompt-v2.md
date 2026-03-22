# Entity & Concept Extraction Prompt Template v2

コンテンツ分類（Fact/Tip/Story）、Entity 抽出、Concept 抽出、リレーション検出を行う LLM プロンプトテンプレート。
Phase 3 で各 raw_item に対して適用する。

v1 からの変更点:
- Entity（固有名詞）と Concept（ドメイン概念）を分離
- Concept は 14 の ConceptCategory に分類必須
- SERVES_AS（Entity → Concept の役割関係）を抽出
- 正準名ルールによる正規化を適用
- 出力形式を emit_creator_queue.py v2 に合わせて変更

---

## プロンプト

```
あなたはコンテンツ分析とナレッジグラフ構築の専門家です。
以下のテキストを分析し、分類・Entity抽出・Concept抽出・リレーション検出を行ってください。

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

**Fact（事実・データ）**
シグナル:
- 統計データや数値が含まれる（「〇〇%」「〇〇万円」「〇〇人」）
- 調査結果や公式発表の引用がある
- 客観的な事実や現状の説明が主体

**Tip（ハウツー・ノウハウ）**
シグナル:
- 手順やステップの説明がある
- 推奨事項やベストプラクティスの提示
- ツールや方法の紹介・比較

**Story（体験談・事例）**
シグナル:
- 個人の体験や経験の記述がある
- 事例紹介やケーススタディ
- 時系列での出来事の記述

複数のシグナルが混在する場合は、最も支配的なタイプを選択してください。

## タスク2: Entity 抽出（固有名詞）

テキストから**具体的な固有名詞**を抽出してください。
「固有の運営者・URL・実在の人物がいるもの」が Entity です。

### entity_type（4種のみ）

| entity_type | 説明 | 例 |
|-------------|------|-----|
| platform | サービス・プラットフォーム・ツール | Instagram, Coconala, ChatGPT, Canva |
| company | 企業・組織 | Google, Match Group, リクルート |
| person | 実在の人物 | 林知佳, Elon Musk |
| organization | 公的機関・団体 | 厚生労働省, 国税庁 |

### 正規化ルール（必須）

- platform/company → **公式英語表記**を使え（インスタ → Instagram、ココナラ → Coconala）
- person → 日本人は漢字、外国人はアルファベット
- organization → 公式名称
- 全角英数字 → 半角に統一
- 不要なスペースは除去

### 抽出ルール

- 各コンテンツから 0〜5 個の Entity を抽出
- 汎用的すぎるものは Entity にしない（「アプリ」「サービス」→ これは Concept）
- Entity の name は具体的かつ簡潔に

## タスク3: Concept 抽出（ドメイン概念）

テキストから**一般的なドメイン概念**を抽出し、以下の14カテゴリのいずれかに分類してください。
「○○とは何か」で説明できる一般的な概念が Concept です。

### ConceptCategory（14種）

#### What層（何についてか）

| カテゴリ | 説明 | 例 |
|---------|------|-----|
| MonetizationMethod | 収益化手段 | スキル販売, コンテンツ販売, オンライン鑑定, アフィリエイト |
| AcquisitionChannel | 集客チャネル | SNS集客, SEOブログ集客, 口コミ紹介, プラットフォーム内検索 |
| Skill | スキル・技能 | タロット, プログラミング, ライティング, SNS運用 |
| Audience | ターゲット層 | 副業初心者, 30代婚活女性, フリーランス志望者 |
| RevenueModel | 収益モデル | フロント→バックエンド階段, サブスク, ストック型, 単発受注 |
| SuccessMetric | 成果指標 | 月収30万円, フォロワー1万人, 成婚率17.6%, 成約率 |
| ContentFormat | コンテンツ形式 | リール動画, ブログ記事, PDF教材, LINE配信, ポッドキャスト |
| Regulation | 法規制・コンプライアンス | 景品表示法, 薬機法, 確定申告20万円ルール, 霊感商法規制 |
| Milestone | 時間軸の目安・到達点 | 90日で軌道に乗る, 60投稿でジャンル認知, 3ヶ月で月3万円 |

#### How層（どう書くか・どう伝えるか）

| カテゴリ | 説明 | 例 |
|---------|------|-----|
| PersuasionTechnique | 説得技法 | 社会的証明, 希少性, 権威性, 返報性, バンドワゴン効果 |
| EmotionalHook | 感情トリガー | 「このままでは…」という不安, 「月30万の自由」への憧れ, FOMO |
| CopyFramework | 文章構成パターン | AIDA, PAS, 3択リーディング型, ビフォーアフター, リスト型 |
| Objection | 読者の反論・障壁 | 「スキルがない」, 「初期費用が心配」, 「怪しくないか」 |
| Transformation | 変化パターン | 未経験→月3万円, 会社員→フリーランス, 趣味→プロ占い師 |

### 抽出ルール

- 各コンテンツから 1〜5 個の Concept を抽出
- **必ず1つ以上の ConceptCategory に分類**すること
- 既存の14カテゴリに該当しない場合は、新しいカテゴリ名を提案してよい（new_category フラグを true にする）
- Concept の name は日本語で統一（SEO, AIDA 等の定着した英語略語はそのまま）
- 汎用的すぎるものは避ける（「ビジネス」「成功」→ 抽出しない）

## タスク4: SERVES_AS 関係の検出

抽出した Entity が、抽出した Concept に対して**どのような役割を果たしているか**を検出してください。

形式: Entity名 → Concept名 (context)

例:
- Instagram → SNS集客 (占い師の主要集客チャネルとして)
- Coconala → スキル販売 (占い鑑定の販売プラットフォームとして)
- ChatGPT → AIライティング (記事下書き生成ツールとして)

## タスク5: Concept 間リレーション検出

抽出した Concept 間に意味的な関係がある場合、検出してください。

### リレーションタイプ

| タイプ | 説明 | 例 |
|--------|------|-----|
| ENABLES | AがBを可能にする | SNS集客 → オンライン鑑定 (ENABLES) |
| REQUIRES | AにはBが必要 | アフィリエイト → SEOブログ集客 (REQUIRES) |
| COMPETES_WITH | AとBは代替関係 | SNS集客 ↔ SEOブログ集客 (COMPETES_WITH) |

- 0〜5個。無理に作らず、明確な関係のみ記述してください。
- Entity 間のリレーションは不要（SERVES_AS で十分）。

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
  "entities": [
    {
      "name": "正規化済みEntity名",
      "entity_type": "platform | company | person | organization"
    }
  ],
  "concepts": [
    {
      "name": "Concept名",
      "category": "ConceptCategory名（14種のいずれか）",
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

## 注意事項

- body は元テキストのコピーではなく、要約を作成すること
- 英語コンテンツは日本語に翻訳して要約
- source_url は入力値をそのまま保持（絶対に変更しない）
- Entity と Concept を混同しない（固有名詞 vs 一般概念）
- Concept は必ず ConceptCategory に分類する
```

---

## 出力 JSON と emit_creator_queue.py v2 入力の対応

このプロンプトの出力は、サイクル単位で以下の構造にラップされる:

```json
{
  "genre": "{selected_genre}",
  "cycle_id": "cycle-{YYYYMMDD-HHmmss}",
  "sources": [...],
  "facts": [
    {
      "text": "body の値",
      "category": "statistics | market_data | research | trend",
      "confidence": "high | medium | low",
      "about_concepts": ["Concept名1", "Concept名2"],
      "source_url": "...",
      "about_entities": [{"name": "...", "entity_type": "..."}]
    }
  ],
  "tips": [...],
  "stories": [...],
  "concepts": [...],
  "serves_as": [...],
  "concept_relations": [...]
}
```

### v1 → v2 の対応表

| v1 | v2 | 変更内容 |
|----|-----|---------|
| entities[] (10タイプ混在) | entities[] (4タイプ) + concepts[] (14カテゴリ) | 分離 |
| topic (自由記述1つ) | about_concepts[] (Concept リスト) | 構造化 |
| entity_relations[] | serves_as[] + concept_relations[] | 分離 |
| contents[] 形式 | sources/facts/tips/stories 分離形式 | emit_creator_queue.py v2 対応 |
