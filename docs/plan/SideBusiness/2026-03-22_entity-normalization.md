# 議論メモ: creator-neo4j A-4 Entity 正規化ルール

**日付**: 2026-03-22
**参加**: ユーザー + AI

## 正準名ルール

### Entity（entity_type 別）

| entity_type | 正準名の言語 | ルール | 例 |
|-------------|------------|--------|-----|
| platform | 公式英語表記 | 運営者が使っている表記 | Instagram, Coconala, ChatGPT |
| company | 公式英語表記 | 上場名 or 公式サイト表記 | Match Group, Google |
| person | 原語表記 | 日本人は漢字、外国人はアルファベット | 林知佳, Elon Musk |
| organization | 公式名称 | 略称は Alias に | 厚生労働省 |

### Concept

| 場合 | 正準名の言語 | 例 |
|------|------------|-----|
| 日本語で定着 | 日本語 | SNS集客, 副業, 確定申告 |
| 英語のまま使用 | 英語 | AIDA, PAS, SEO |
| カタカナ外来語 | カタカナ | アフィリエイト, ドロップシッピング |

### 表記揺れ吸収ルール

| パターン | 正規化 | 例 |
|---------|--------|-----|
| 全角/半角 | 半角に統一 | Ｉｎｓｔａｇｒａｍ → Instagram |
| 大小文字 | 公式表記に合わせる | chatgpt → ChatGPT |
| スペース有無 | 不要スペース除去 | マッチング アプリ → マッチングアプリ |
| 長音符の揺れ | 一般的な表記 | サーバ → サーバー |
| 中黒の有無 | なしに統一 | ソーシャル・メディア → ソーシャルメディア |

## Alias ノード設計

### aliases をリレーション化する決定

LIST&lt;STRING&gt; プロパティではなく Alias ノード + ALIAS_OF リレーションで実装。

**理由**: Neo4j の Full-Text Index は LIST&lt;STRING&gt; の個別要素に適用できない。Alias ノード化により alias_fulltext Index で高速 fuzzy 検索が可能になり、ファジーマッチングの第2層+第3層が1クエリに統合される。

### スキーマ

```
Alias ノード:
  value: STRING (UNIQUE)
  language: STRING — ja, en
  created_at: DATETIME

リレーション:
  Alias ──ALIAS_OF──→ Entity
  Alias ──ALIAS_OF──→ Concept

インデックス:
  CREATE FULLTEXT INDEX alias_fulltext FOR (a:Alias) ON EACH [a.value]
```

### 統合クエリ（第2+3層）

```cypher
CALL db.index.fulltext.queryNodes("alias_fulltext", $name)
YIELD node AS alias, score
WHERE score > 0.5
MATCH (alias)-[:ALIAS_OF]->(target)
WITH target, alias, score,
     apoc.text.levenshteinSimilarity(alias.value, $name) AS lev
WHERE lev > 0.8
RETURN target, alias.value, lev
```

### 曖昧性の表現

同一 alias が複数 Entity/Concept を指すケースを自然に表現:

```
Alias("パイソン") ──ALIAS_OF──→ Entity("Python"::platform)
Alias("パイソン") ──ALIAS_OF──→ Concept("ニシキヘビ")
```

## 最終スキーマ（A-3 + A-4 統合）

- ノード: **10種**（+Alias）
- リレーション: **11種**（+ALIAS_OF）
- 制約: **11個**（+Alias.value UNIQUE）
- Full-Text Index: **3本**（entity_fulltext, concept_fulltext, alias_fulltext）

## 初期 Alias セット（主要 Entity）

```yaml
Instagram: [インスタ, インスタグラム, IG, instagram]
Coconala: [ココナラ, coconala]
ChatGPT: [チャットGPT, チャットジーピーティー, chatgpt]
TikTok: [ティックトック, tiktok]
YouTube: [ユーチューブ, youtube, YT]
Twitter: [ツイッター, X, 旧Twitter]
LinkedIn: [リンクトイン, linkedin]
Pairs: [ペアーズ, pairs]
Canva: [キャンバ, canva]
```

## 次のタスク

- B-1: Entity 抽出プロンプト改修（14カテゴリ準拠 + 正規化ルール組み込み）
- B-2: Entity リンキング実装（3層マッチング: Full-Text統合 + Embedding）
