# Creator Research 検索戦略

creator-research スキルで使用する、ジャンル別・深度別の検索クエリテンプレート。

> 詳細なジャンル設定（webfetch_sites, subreddit 一覧等）は
> `.claude/skills/creator-enrichment/references/genre-config.md` も参照すること。

---

## プレースホルダー

| プレースホルダー | 置換内容 |
|-----------------|---------|
| `{topic}` | `--topic` パラメータの値 |
| `{year}` | 現在の西暦年（`mcp__time__get_current_time` から取得） |

---

## career（転職・副業）

### 英語クエリ（Tavily → WebSearch）

| 優先度 | テンプレート | 用途 |
|--------|-----------|------|
| HIGH | `{topic} side hustle how to start {year}` | 始め方・入門 |
| HIGH | `{topic} freelance income statistics {year}` | 収入データ |
| HIGH | `{topic} success story how I made money reddit` | 体験談（Story） |
| MEDIUM | `{topic} career change tips before after {year}` | 転職体験 |
| MEDIUM | `{topic} first year results income report` | 初年度報告（Story） |
| MEDIUM | `{topic} beginner mistakes lessons learned` | 失敗談（Story） |
| MEDIUM | `{topic} remote work tips tools {year}` | リモートワーク |
| LOW | `{topic} salary negotiation strategies` | 年収交渉 |
| LOW | `{topic} job market trends hiring {year}` | 市場データ |

### 日本語クエリ（Tavily → WebSearch）

| 優先度 | テンプレート | 用途 |
|--------|-----------|------|
| HIGH | `{topic} 副業 始め方 {year}` | 入門 |
| HIGH | `{topic} 体験談 実体験 {year}` | 体験談（Story） |
| HIGH | `{topic} フリーランス 収入 {year}` | 収入データ |
| MEDIUM | `{topic} 月収報告 ヶ月目 結果` | 月次報告（Story） |
| MEDIUM | `{topic} 転職 成功 失敗談 {year}` | 転職体験 |
| MEDIUM | `{topic} 面接 対策 コツ` | 面接対策（Tip） |
| MEDIUM | `{topic} 副業 ビフォーアフター 変化` | 変化記録（Story） |
| LOW | `{topic} 年収交渉 内定後` | 年収交渉 |
| LOW | `{topic} 転職市場 求人動向 {year}` | 市場データ |

### Reddit サブレディット

| 優先度 | subreddit | 取得対象 |
|--------|----------|---------|
| HIGH | r/sidehustle | 副業収入報告・始め方質問 |
| HIGH | r/careerguidance | キャリア相談 |
| MEDIUM | r/freelance | フリーランス体験 |
| MEDIUM | r/Entrepreneur | 起業・副業体験 |
| LOW | r/cscareerquestions | IT系キャリア |
| LOW | r/recruitinghell | 転職・就活体験 |

### コンテンツ抽出（WebFetch/Tavily Extract）

| 用途 | 検索クエリ |
|------|-----------|
| note.com | `site:note.com {topic} 副業` |
| note.com | `site:note.com {topic} 転職 体験談` |
| hatenablog.com | `site:hatenablog.com {topic} 副業` |

---

## beauty-romance（美容・恋愛）

### 英語クエリ（Tavily → WebSearch）

| 優先度 | テンプレート | 用途 |
|--------|-----------|------|
| HIGH | `{topic} dating app success rate statistics {year}` | マッチングデータ |
| HIGH | `{topic} my dating experience story reddit` | 恋愛体験（Story） |
| HIGH | `{topic} skincare routine results before after` | 美容体験（Story） |
| MEDIUM | `{topic} relationship advice tips {year}` | 恋愛Tip |
| MEDIUM | `{topic} beauty trend {year}` | 美容トレンド |
| LOW | `{topic} marriage counseling advice` | 婚活 |

### 日本語クエリ（Tavily → WebSearch）

| 優先度 | テンプレート | 用途 |
|--------|-----------|------|
| HIGH | `{topic} マッチングアプリ 体験談 {year}` | マッチング体験（Story） |
| HIGH | `{topic} 美容 やってみた 効果` | 美容体験（Story） |
| HIGH | `{topic} 婚活 成功 失敗 {year}` | 婚活体験（Story） |
| MEDIUM | `{topic} スキンケア おすすめ 方法` | スキンケアTip |
| MEDIUM | `{topic} 恋愛 アドバイス コツ` | 恋愛Tip |
| LOW | `{topic} 美容 トレンド {year}` | 美容トレンド |

### Reddit サブレディット

| 優先度 | subreddit | 取得対象 |
|--------|----------|---------|
| HIGH | r/dating_advice | 恋愛・婚活相談 |
| HIGH | r/SkincareAddiction | スキンケア体験 |
| MEDIUM | r/relationship_advice | 関係性の悩み |
| LOW | r/MakeupAddiction | メイク体験 |

### コンテンツ抽出（WebFetch/Tavily Extract）

| 用途 | 検索クエリ |
|------|-----------|
| note.com | `site:note.com {topic} 恋愛` |
| ameblo.jp | `site:ameblo.jp {topic} 美容` |

---

## spiritual（占い・スピリチュアル）

### 英語クエリ（Tavily → WebSearch）

| 優先度 | テンプレート | 用途 |
|--------|-----------|------|
| HIGH | `{topic} tarot business how to start {year}` | 占いビジネス |
| HIGH | `{topic} astrology online income story` | 収入体験（Story） |
| MEDIUM | `{topic} spiritual coaching tips {year}` | スピリチュアルTip |
| LOW | `{topic} psychic reading business monetization` | 収益化 |

### 日本語クエリ（Tavily → WebSearch）

| 優先度 | テンプレート | 用途 |
|--------|-----------|------|
| HIGH | `{topic} 占い 副業 始め方 {year}` | 占い副業入門 |
| HIGH | `{topic} タロット 収入 体験談 {year}` | 体験談（Story） |
| HIGH | `{topic} スピリチュアル SNS集客 コツ` | 集客Tip |
| MEDIUM | `{topic} 占い ビジネス 収益化 {year}` | 収益化 |
| LOW | `{topic} 占い 鑑定 料金相場` | 市場データ |

### Reddit サブレディット

| 優先度 | subreddit | 取得対象 |
|--------|----------|---------|
| HIGH | r/tarot | タロット体験 |
| MEDIUM | r/astrology | 占星術体験 |
| LOW | r/psychic | 霊感体験 |

### コンテンツ抽出（WebFetch/Tavily Extract）

| 用途 | 検索クエリ |
|------|-----------|
| note.com | `site:note.com {topic} 占い` |
| ameblo.jp | `site:ameblo.jp {topic} スピリチュアル` |

---

## 深度別クエリ数目安

| depth | 英語クエリ | 日本語クエリ | 抽出URL | Reddit |
|-------|-----------|------------|--------|--------|
| quick | 2件 | 2件 | 2件 | 1 subreddit |
| standard | 4-5件 | 4-5件 | 4-5件 | 2 subreddit |
| deep | 7-8件 | 7-8件 | 8-10件 | 3+ subreddit |

---

## ギャップ別クエリ優先順

Phase 0 で検出されたギャップに応じてクエリを調整する:

| ギャップ種別 | 優先クエリ |
|------------|---------|
| `story_deficit` | Story系クエリを予算の 50% 以上に割り当て。`{topic} 体験談 {year}`・Reddit 重点 |
| `concept_gap` (How層) | How層向けクエリを追加: `{topic} コツ テクニック`, `{topic} psychological hook copywriting` |
| `no_coverage` | ジャンル全般クエリを追加: ジャンル名 + `{topic}` の組み合わせ |
| `entity_gap` | Entity名での直接検索: `{entity_name} {topic} サービス` |
| `stale_data` | 年次フィルタを強制: クエリ末尾に `{year}` を必須追加 |

---

## How層向けクエリ（全ジャンル共通）

Phase 0 の Q2 で How層カテゴリ（EmotionalHook/CopyFramework/Objection/PersuasionTechnique）が
不足と判定された場合、以下を追加する:

### 英語

| カテゴリ | クエリテンプレート |
|---------|-----------------|
| EmotionalHook | `emotional hook {topic} headline examples that convert` |
| CopyFramework | `copywriting framework {topic} AIDA PAS structure` |
| Objection | `common objections {topic} how to overcome hesitation` |
| PersuasionTechnique | `persuasion psychology {topic} social proof scarcity` |

### 日本語

| カテゴリ | クエリテンプレート |
|---------|-----------------|
| EmotionalHook | `{topic} 感情に刺さる キャッチコピー 書き出し` |
| CopyFramework | `{topic} セールスライティング PASONA PAD 構成` |
| Objection | `{topic} よくある反論 不安 購入障壁 克服` |
| PersuasionTechnique | `{topic} 社会的証明 希少性 権威性 テクニック` |
