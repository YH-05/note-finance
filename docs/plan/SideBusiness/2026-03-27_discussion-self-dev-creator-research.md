# 議論メモ: self-dev ジャンル creator-neo4j 初期投入

**日付**: 2026-03-27
**参加**: ユーザー + AI

## 背景・コンテキスト

creator-neo4j（bolt://localhost:7689）のself-dev（自己啓発・自己成長）ジャンルのナレッジが完全にゼロの状態から、
Web情報収集とnote.comスクレイピングで初期データを投入するセッション。

## 実施内容

### 1. creator-research スキル（self-dev, depth: standard）

**ギャップ分析結果**: self-dev関連Concept全20件のcontent_count=0（完全新規ジャンル）

**収集ソース**（13件）:
- Reddit: r/selfimprovement × 3, r/productivity × 2
- Ryan Holiday ブログ（ryanholiday.net）× 1
- yourstory.com, luisazhou.com, makucopywriter.com × 各1
- note.com（#自己啓発タグ、mindset_official、ruinormalhakkar）× 3
- studyhacker.net × 1

**投入結果**:
- Concept×3（感情フック自己啓発コンテンツ/マイクロ習慣による習慣設計/自己啓発コピーフレームワーク）
- Entity×6新規（Carol Dweck/Ryan Holiday/Neil Fiore/Matthew McConaughey/IBISWorld/Mindset Coaching Academy等）
- Fact×5, Tip×5, Story×4
- リレーション計57件（IS_A×3/FROM_DOMAIN×13/ABOUT×2/FROM_SOURCE×14/MENTIONS×10/IN_GENRE×14/ENABLES×1）

### 2. note-scrape スキル

| クリエイター | 記事数 | Fact | Tip | Story | ノード | リレーション |
|------------|--------|------|-----|-------|--------|------------|
| mindset_official | 19 | 1 | 1 | 17 | 142 | 131 |
| ruinormalhakkar | 19 | 1 | 5 | 13 | 62 | 90 |
| studyhacker | 2 | 1 | 0 | 1 | 13 | 13 |
| **合計** | **40** | **3** | **6** | **31** | **217** | **234** |

3クリエイター全員をRSSモニター（genre: career）に登録済み。

## 決定事項

1. **self-devはcareerジャンルで管理**: creator-neo4jのジャンルはcareer/beauty-romance/spiritualの3種のみ。self-devはcareerに包含して管理する。
2. **note.comクリエイター3名をRSSモニター登録**: mindset_official/ruinormalhakkar/studyhacker。Playwright経由での本文取得が有効と確認。

## アクションアイテム

- [ ] self-devのConceptカバレッジ拡充（MonetizationMethod/Skill/Tool/AcquisitionChannelカテゴリのコンテンツ追加）(優先度: 中)
- [ ] 日本語圏の自己啓発系note有名クリエイター追加収集（フォロワー1万以上、5名程度）(優先度: 低)

## 次回の議論トピック

- self-devナレッジを活用したキャリアお姉さん（career_sister）投稿コンテンツ強化
- みつき（美月）ペルソナとの差別化軸（self-dev × スピリチュアル vs self-dev × キャリア）

## 参考情報

- Tavily API制限 → WebSearch（Tier 2）フォールバック
- note.comはJSレンダリングのためWebFetch不可 → note-scrapeスキルで解決
- ruinormalhakkar: ミニマリスト×自己整理系（比較癖の手放し方/偽物の夢の仕分け等）
- mindset_official: 認知科学コーチング×自己変革（Storyが17件と最多）
