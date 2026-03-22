# 議論メモ: creator-neo4j 自動拡充セッション

**日付**: 2026-03-22
**参加**: ユーザー + AI

## 背景・コンテキスト

creator-neo4j（bolt://localhost:7689）のナレッジグラフを `/creator-enrichment --until 16:00` で自動拡充。
3ジャンル（career / beauty-romance / spiritual）をローテーションしながら、
Tavily・Reddit・WebFetch で情報を検索し、Fact/Tip/Story に分類・Entity 抽出後、
emit_creator_queue.py → /save-to-creator-graph パイプラインで投入した。

## セッション結果

### サイクル実績

| Cycle | ジャンル | Fact | Tip | Story | Entity | Relations |
|-------|---------|------|-----|-------|--------|-----------|
| 1 | career（転職・副業） | 3 | 3 | 1 | 30 | 11 |
| 2 | beauty-romance（美容・恋愛） | 3 | 2 | 1 | 21 | 5 |
| 3 | spiritual（占い・スピリチュアル） | 2 | 3 | 1 | 20 | 5 |
| 4 | career（転職・副業） | 2 | 2 | 1 | 19 | 4 |
| **合計** | **3ジャンル** | **10** | **10** | **4** | **90** | **25** |

### グラフ成長

| 項目 | 追加前 | 追加後 | 差分 |
|------|--------|--------|------|
| Topic | 1,049 | 1,058 | +9 |
| Fact | 306 | 313 | +7 |
| Tip | 206 | 213 | +7 |
| Source | 192 | 211 | +19 |
| Entity | 30 | 88 | +58 |
| Story | 58 | 61 | +3 |
| MENTIONS | 30 | 95 | +65 |
| RELATES_TO | 11 | 25 | +14 |

### 主要トピック

- **career**: フリーランス市場規模（2.1兆ドル）、プログラミング副業（Micro-SaaS）、AI副業（月収4.6万vs2.5万）、SNSマーケティング収入（年収73,547ドル）、リモートワークツール
- **beauty-romance**: マッチングアプリ統計（成婚率17.6%）、メンズスキンケア市場（57.8億ドル成長）、2026年美容トレンド5キーワード
- **spiritual**: 占いSNS集客（Instagram×LINE導線）、ココナラ副業占い師、占い副業収入（月20〜30万円事例）

## 決定事項

1. **パイプライン運用方法の確立**: emit_creator_queue.py の入力は sources/facts/tips/stories 分離形式が正しい（contents[] 形式は不可）。Neo4j 制約の並列作成はトランザクション競合を起こすため逐次実行が必要。
2. **ジャンルバランス**: career(412) > spiritual(280) > beauty-romance(225)。次回は beauty-romance と spiritual を優先拡充。

## アクションアイテム

- [ ] 次回 creator-enrichment セッション（beauty-romance/spiritual 優先）(優先度: 中)
- [ ] 日本語コンテンツ比率向上（note.com/ameblo.jp の直接 WebFetch 強化）(優先度: 中)
- [ ] Entity 間 RELATES_TO 充実化（バッチ横断接続の検討）(優先度: 低)

## 技術的な学び

- emit_creator_queue.py は `contents[]` 配列形式ではなく `facts[]`, `tips[]`, `stories[]` の個別配列で入力する
- Neo4j 制約 CREATE CONSTRAINT を8個並列実行するとトランザクションログエラーが発生 → Docker restart で復旧、以降は逐次実行で安定
- entity_relations の from_entity/to_entity は `名前::タイプ` 形式（entity_key 形式）で指定する必要がある
- 日本語 Tavily クエリは time_range=month だと結果が少ない → time_range なしで広く取得すべき

## セッションログ

`.tmp/creator-enrichment-20260322-112348.log.md`
