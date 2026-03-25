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

| # | クエリテンプレート | 対象領域 |
|---|-------------------|---------|
| 1 | `side hustle {topic} tips {year}` | 副業 |
| 2 | `freelance {topic} income statistics {year}` | フリーランス |
| 3 | `career change {topic} success story {year}` | 転職体験 |
| 4 | `{topic} remote work tips` | リモートワーク |
| 5 | `job interview {topic} tips techniques {year}` | 面接対策 |
| 6 | `salary negotiation {topic} strategies {year}` | 年収交渉 |
| 7 | `resume {topic} writing tips career change` | 書類対策 |
| 8 | `{topic} startup vs corporate career comparison` | 大手vsベンチャー |
| 9 | `{topic} career advice 20s 30s mid-career {year}` | 20-30代キャリア |
| 10 | `{topic} job market trends hiring data {year}` | 転職市場データ |
| 11 | `{topic} career switch failure lesson learned` | 転職失敗談 |

### Tavily 日本語クエリ

| # | クエリテンプレート | 対象領域 |
|---|-------------------|---------|
| 1 | `{topic} 副業 成功事例 {year}` | 副業 |
| 2 | `{topic} フリーランス 収入 {year}` | フリーランス |
| 3 | `{topic} 転職 体験談 {year}` | 転職体験 |
| 4 | `{topic} 面接 対策 コツ {year}` | 面接対策 |
| 5 | `{topic} 年収交渉 内定後 テクニック` | 年収交渉 |
| 6 | `{topic} 職務経歴書 書き方 通過率` | 書類対策 |
| 7 | `{topic} 大手 ベンチャー 比較 転職` | 大手vsベンチャー |
| 8 | `{topic} 20代 30代 キャリア 悩み {year}` | 20-30代キャリア |
| 9 | `{topic} 転職 失敗談 後悔 {year}` | 転職失敗談 |
| 10 | `{topic} 転職市場 求人倍率 動向 {year}` | 市場データ |
| 11 | `{topic} 自己PR 書き方 例文` | 書類対策 |

### WebFetch サイト

| ドメイン | 検索プレフィックス |
|---------|-------------------|
| note.com | `site:note.com 副業 {topic}` |
| note.com | `site:note.com 転職 体験談 {topic}` |
| note.com | `site:note.com 面接 {topic}` |
| hatenablog.com | `site:hatenablog.com 副業 {topic}` |
| hatenablog.com | `site:hatenablog.com 転職 {topic}` |

### Reddit サブレディット

- r/sidehustle
- r/careerguidance
- r/Entrepreneur
- r/freelance
- r/jobs
- r/cscareerquestions
- r/recruitinghell
- r/careeradvice

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

## Story 優先検索テンプレート（全ジャンル共通）

Gap Analysis Q2 で Story 比率が 20% 未満と判定された場合、ジャンル固有クエリに加えて
以下のテンプレートを使用する。**Story 比率が理想値（25%）を下回る限り、
検索クエリの 50% をこれらのテンプレートに割り当てること。**

### Tavily 英語クエリ（Story）

| # | クエリテンプレート |
|---|-------------------|
| S1 | `{topic} my experience success story reddit {year}` |
| S2 | `{topic} case study how I started from scratch` |
| S3 | `{topic} before and after transformation journey {year}` |
| S4 | `{topic} beginner first year results income report` |

### Tavily 日本語クエリ（Story）

| # | クエリテンプレート |
|---|-------------------|
| S1 | `{topic} 体験談 実体験 始めてみた {year}` |
| S2 | `{topic} 成功事例 ケーススタディ 結果報告` |
| S3 | `{topic} ビフォーアフター 変化 体験レポート` |
| S4 | `{topic} 初心者 〇ヶ月目 収入報告 {year}` |

### Reddit サブレディット（Story）

- r/sidehustle（収入報告系投稿）
- r/Entrepreneur（起業・事業開始体験）
- r/personalfinance（資産形成体験）
- r/BeautyGuruChatter（美容体験談）

### Story 判定シグナル（Phase 3 での分類基準）

以下のいずれかを含むコンテンツは Tip ではなく **Story** に分類すること:

- 「〜してみた」「〜した結果」「〜ヶ月目の報告」
- 具体的な金額・期間の before/after（「月収3万円→月収30万円」等）
- 失敗談・反省点の記述
- 一人称視点での時系列ストーリー
- 「私の場合は」「実際にやってみると」などの体験マーカー

### 使用基準

Q2 で以下の条件に該当する場合、そのジャンルの S* クエリを優先的に実行する：

- Story 比率 < 20%（現在全ジャンルで 11-14% のため、当面は常時適用）

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
