# Genre Configuration Reference

ジャンル別の検索戦略リファレンス。
設定値は `data/config/creator-enrichment-config.json` で管理される。

---

## ジャンル一覧

| genre key | name_ja | 主な検索対象 |
|-----------|---------|-------------|
| `career` | 転職・副業 | 副業ノウハウ、フリーランス収入、転職体験談 |
| `beauty-romance` | 美容・恋愛 | マッチングアプリ、美容トレンド、婚活体験談 |
| `spiritual` | 占い・スピリチュアル | 占いビジネス、タロット副業、スピリチュアル SNS集客 |

---

## career（転職・副業）

### Tavily 英語クエリ

| # | クエリテンプレート |
|---|-------------------|
| 1 | `side hustle {topic} tips {year}` |
| 2 | `freelance {topic} income statistics {year}` |
| 3 | `career change {topic} success story {year}` |
| 4 | `{topic} remote work tips` |

### Tavily 日本語クエリ

| # | クエリテンプレート |
|---|-------------------|
| 1 | `{topic} 副業 成功事例 {year}` |
| 2 | `{topic} フリーランス 収入 {year}` |
| 3 | `{topic} 転職 体験談 {year}` |

### WebFetch サイト

| ドメイン | 検索プレフィックス |
|---------|-------------------|
| note.com | `site:note.com 副業 {topic}` |
| hatenablog.com | `site:hatenablog.com 副業 {topic}` |

### Reddit サブレディット

- r/sidehustle
- r/careerguidance
- r/Entrepreneur
- r/freelance

### Entity タイプフォーカス

`occupation`, `platform`, `company`, `technique`

---

## beauty-romance（美容・恋愛）

### Tavily 英語クエリ

| # | クエリテンプレート |
|---|-------------------|
| 1 | `dating app {topic} statistics {year}` |
| 2 | `skincare {topic} trend {year}` |
| 3 | `relationship advice {topic} tips` |

### Tavily 日本語クエリ

| # | クエリテンプレート |
|---|-------------------|
| 1 | `{topic} マッチングアプリ 成功率 {year}` |
| 2 | `{topic} 美容 トレンド {year}` |
| 3 | `{topic} 婚活 体験談 {year}` |

### WebFetch サイト

| ドメイン | 検索プレフィックス |
|---------|-------------------|
| note.com | `site:note.com 恋愛 {topic}` |
| ameblo.jp | `site:ameblo.jp 美容 {topic}` |

### Reddit サブレディット

- r/SkincareAddiction
- r/dating_advice
- r/relationship_advice

### Entity タイプフォーカス

`service`, `product`, `technique`, `metric`

---

## spiritual（占い・スピリチュアル）

### Tavily 英語クエリ

| # | クエリテンプレート |
|---|-------------------|
| 1 | `astrology business {topic} monetization {year}` |
| 2 | `tarot reading {topic} online business {year}` |
| 3 | `spiritual coaching {topic} income` |

### Tavily 日本語クエリ

| # | クエリテンプレート |
|---|-------------------|
| 1 | `{topic} 占い ビジネス 収益化 {year}` |
| 2 | `{topic} タロット 副業 {year}` |
| 3 | `{topic} スピリチュアル SNS集客 {year}` |

### WebFetch サイト

| ドメイン | 検索プレフィックス |
|---------|-------------------|
| note.com | `site:note.com 占い {topic}` |
| ameblo.jp | `site:ameblo.jp スピリチュアル {topic}` |

### Reddit サブレディット

- r/tarot
- r/astrology
- r/psychic

### Entity タイプフォーカス

`platform`, `service`, `technique`, `concept`

---

## How層向け検索テンプレート（全ジャンル共通）

Gap Analysis Q2/Q3 で How層カテゴリ（EmotionalHook/CopyFramework/Objection/PersuasionTechnique）が
不足と判定された場合、ジャンル固有クエリに加えて以下のテンプレートを使用する。

### Tavily 英語クエリ（How層）

| # | カテゴリ | クエリテンプレート |
|---|---------|-------------------|
| H1 | EmotionalHook | `emotional hook copywriting {topic} examples` |
| H2 | EmotionalHook | `headline hook formulas that convert {topic}` |
| H3 | CopyFramework | `copywriting framework {topic} PASONA AIDA PAS` |
| H4 | CopyFramework | `{topic} sales page structure template` |
| H5 | Objection | `common objections {topic} how to overcome` |
| H6 | Objection | `{topic} customer hesitation barriers buying` |
| H7 | PersuasionTechnique | `persuasion techniques {topic} social proof scarcity` |
| H8 | PersuasionTechnique | `influence psychology {topic} Cialdini principles` |

### Tavily 日本語クエリ（How層）

| # | カテゴリ | クエリテンプレート |
|---|---------|-------------------|
| H1 | EmotionalHook | `{topic} 感情に刺さる キャッチコピー 作り方` |
| H2 | EmotionalHook | `{topic} 読者の心を掴む フック 書き出し` |
| H3 | CopyFramework | `{topic} セールスライティング テンプレート PASONAの法則` |
| H4 | CopyFramework | `{topic} LP 構成 コピーライティング フレームワーク` |
| H5 | Objection | `{topic} よくある反論 不安 解消 方法` |
| H6 | Objection | `{topic} 購入障壁 心理的ハードル 克服` |
| H7 | PersuasionTechnique | `{topic} 説得力 社会的証明 権威性 テクニック` |
| H8 | PersuasionTechnique | `{topic} 限定性 希少性 マーケティング 心理学` |

### Reddit サブレディット（How層）

- r/copywriting
- r/marketing
- r/Entrepreneur（セールス・説得系投稿）

### 使用基準

Q3 で以下のいずれかが低カバレッジ TOP 5 に入った場合、そのカテゴリの H* クエリを優先的に実行する：

- EmotionalHook（現在1件）
- CopyFramework（現在1件）
- Objection（現在1件）
- PersuasionTechnique（現在0件）

---

## プレースホルダー

| プレースホルダー | 置換内容 | ソース |
|-----------------|---------|--------|
| `{topic}` | 検索トピック | Gap Analysis Q3 の低カバレッジトピック |
| `{year}` | 現在の西暦年 | `mcp__time__get_current_time` から取得 |

---

## 設定ファイル

全ジャンル設定は以下の JSON ファイルで一元管理されている:

```
data/config/creator-enrichment-config.json
```

新しいジャンルの追加やクエリの変更は、この JSON ファイルを編集すること。
