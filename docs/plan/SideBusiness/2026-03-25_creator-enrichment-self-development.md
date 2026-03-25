# creator-enrichment: self-development ジャンル拡充セッション

**日付**: 2026-03-25
**セッション**: Session 1 (12:07-14:04) + Session 2 (14:21-15:22)

## 背景・コンテキスト

creator-neo4j で self-development ジャンルは最もコンテンツが少なく（107件）、他ジャンル（career: 862, beauty-romance: 471, spiritual: 391）と大きな差があった。Story比率も19%で目標25%を下回っていた。

## セッション2 結果（14:21-15:22）

### Enrichment（10サイクル, 14:21-15:11）

| 指標 | Before | After | 増加 |
|------|--------|-------|------|
| Fact | 46 | 76 | +30 |
| Tip | 41 | 61 | +20 |
| Story | 20 | 39 | +19 |
| 合計 | 107 | 176 | **+69** |
| Story比率 | 19% | 22.2% | +3.2pt |
| Concept | - | +100以上 | How層充実 |
| Entity | - | +22名 | 著名人物 |

### カバーしたトピック（31件）

モンクモード, ドーパミンデトックス, ディープワーク, フロー状態, ストイシズム, バイオハッキング, モーニングルーティン, Cialdini説得原則, 億万長者マインドセット, 習慣スタッキング, 2分ルール, パレート原則, タイムブロッキング, 成長マインドセット, コールドシャワー, ジャーナリング, 感謝の実践, アカウンタビリティ, ビジュアライゼーション, エネルギー管理, 決断疲れ, 睡眠最適化(Huberman), 複利効果, 恐怖設定(Ferriss), AIDA/PAS/新PASONA, 深い読書, セルフコンパッション, 16時間断食, システム>目標, メンタルモデル(Munger), 意図的練習(Ericsson)

### 投入Entity（22名）

Cal Newport, Mihaly Csikszentmihalyi, Kelly McGonigal, Brian Tracy, James Clear, Prince EA, Epictetus, David Sinclair, Peter Attia, Bryan Johnson, Wim Hof, Carol Dweck, Robert Cialdini, James Pennebaker, Robert Emmons, Andrew Huberman, Darren Hardy, Tim Ferriss, Kristin Neff, Charlie Munger, Anders Ericsson, Masanori Kanda

### Maintenance（15:12-15:22）

| 改善 | 件数 |
|------|------|
| Concept category補完 | +1,617件（60%→99.9%） |
| ABOUT retroactive | +245件 |
| Concept重複マージ | 14ペア |
| 孤立Entity MENTIONS | +14件 |
| Embedding更新 | Concept 178, Fact 86, Tip 51, Story 60 |
| genre補完 | 138件 |

### 品質スコア: 85.3/100（Rating: B）

## 決定事項

1. self-developmentジャンル初期enrichment完了（107→176）
2. Tavily APIリミット超過時のWebSearchフォールバック戦略が安定稼働
3. IS_AからのConceptCategory.name転記によるcategory補完を標準手順化

## アクションアイテム

- [ ] ABOUT未接続Concept 2,130件のembedding類似度ベースリンキング（優先度: 高）
- [ ] entity_linker.py のNameError修正（優先度: 高）
- [ ] 全ジャンルのStory比率25%達成（優先度: 中）
- [ ] 孤立Entity 169件の解消（優先度: 低）

## Session 3 結果（15:29-16:21）

### Enrichment（20サイクル, 15:29-16:20）

| 指標 | Before | After | 増加 |
|------|--------|-------|------|
| Fact | 76 | 117 | +41 |
| Tip | 61 | 74 | +13 |
| Story | 39 | 55 | +16 |
| 合計 | 176 | 246 | **+70** |
| Story比率 | 22.2% | 22.4% | +0.2pt |
| Concept | - | +86 | 新規テーマ大量追加 |
| Entity | - | +30 | 研究者・著者 |
| Source | - | +67 | Web/Reddit/PMC |

### カバーしたトピック（35件・Session 2と重複なし）

ドーパミンデトックス(PMC), 交渉心理学(Cialdini/Harvard PON), バイオハッキング(DO-HEALTH), フロー状態, ストイシズム(90日プログラム), 億万長者の習慣(Corley), Atomic Habits/習慣スタッキング, アカウンタビリティパートナー(Matthews), マインドフルネス瞑想(MBSR), パレートの法則, グリット(Duckworth), 成長マインドセット(Dweck), Ikigai/ブルーゾーン, ジャーナリング(メタ分析), 認知バイアス/デバイアシング, アクティブリーディング, エネルギー管理(Schwartz/HBR), 意図的練習(Ericsson), 睡眠ハイジーン/サーカディアンリズム, 社会的比較理論, 感情知性(Goleman), ポモドーロテクニック, 自己効力感(Bandura), バウンダリー設定, 暗黙知(Polanyi), 意思決定ジャーナル(Annie Duke), セルフコンパッション(Neff), 認知負荷理論(Sweller), セカンドブレイン/PARA(Forte), Wim Hof メソッド, ディープワーク(Newport), 自己決定理論(Deci&Ryan), 注意力残余効果(Leroy), Tiny Habits(Fogg), OKR, ナッジ理論(Thaler), メタ認知, 自己認識2タイプ(Eurich), 学習性楽観主義(Seligman), ABCDE法, 自我消耗理論(Baumeister)

### 新規Entity（30名）

Robert Cialdini, Kelly McGonigal, Brian Tracy, Thomas C. Corley, Mihaly Csikszentmihalyi, Epictetus, Seneca, Marcus Aurelius, Gail Matthews, Dan Buettner, Angela Duckworth, Carol Dweck, James Clear, Daniel Goleman, Andrew Huberman, Albert Bandura, Francesco Cirillo, Annie Duke, Ron Friedman, Michael Polanyi, Kristin Neff, John Sweller, Tiago Forte, Wim Hof, Cal Newport, Edward Deci, Richard Ryan, Sophie Leroy, BJ Fogg, Richard Thaler, Cass Sunstein, Tasha Eurich, Martin Seligman, Roy Baumeister

### Maintenance（16:20-16:21）

| 改善 | 件数 |
|------|------|
| Embedding更新 | Concept 65, Fact 31, Tip 7, Story 10 |
| genre補完 | 46件 |
| ABOUT retroactive | +33件 |

### 技術的課題

- **Tavily API**: Cycle 1 でリミット超過 → 全サイクル WebSearch フォールバック
- **Entity Linker並列処理**: embedding類似度で既存concept_idに解決するが、並列バッチ投入時に対象conceptが未投入の場合ABOUT欠落。Phase 6で部分修復（33件）。`--no-embedding` オプション活用を検討

## 累計結果（Session 1-3）

| 指標 | 初期値 | 最終値 | 総増加 |
|------|--------|--------|--------|
| Fact | 0 | 117 | +117 |
| Tip | 0 | 74 | +74 |
| Story | 0 | 55 | +55 |
| **合計** | **0** | **246** | **+246** |

## アクションアイテム（更新）

- [ ] Entity Linker の --no-embedding オプション活用で並列バッチ投入時のconcept_id不整合解消（優先度: 高）
- [ ] 残りジャンル（spiritual: 391件, beauty-romance: 471件）のenrichmentセッション実施（優先度: 中）
- [ ] creator-quality-checkでself-development拡充後の品質スコア計測（優先度: 中）
- [ ] ABOUT未接続Conceptのembedding類似度ベースリンキング（優先度: 中）

## 次回の議論トピック

- beauty-romance / spiritual ジャンルのenrichment計画
- Entity Linker並列処理の改善策
- creator-neo4j → コンテンツ記事への活用パイプライン設計
