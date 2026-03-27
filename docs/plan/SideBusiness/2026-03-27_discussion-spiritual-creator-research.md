# 議論メモ: スピリチュアル系クリエイターリサーチ実施

**日付**: 2026-03-27
**参加**: ユーザー + AI

## 背景・コンテキスト

スピリチュアル（スピ系）ジャンルのコンテンツ発信情報をcreator-neo4jに蓄積するため、
`/creator-research` スキルを使用してマルチソースリサーチを実施した。
対象ジャンル: `spiritual`（占い・タロット・スピリチュアル・開運）

## 議論のサマリー

### 収集軸の策定

スピ系クリエイターのコンテンツ戦略を理解するため、以下の3軸で情報収集した:

1. **AI占い副業軸**: ChatGPT/Claude活用の鑑定書生成、Threads→LINE→STORESの収益フロー
2. **YouTube収益化軸**: スピリチュアルYouTuberの広告収益・商品販売・コンサルの多角化戦略
3. **占い詐欺懐疑軸**: 信頼性問題、詐欺手口、ユーザーの懐疑コメント

### 技術的課題と対応

| 課題 | 対応 |
|------|------|
| Tavily MCP usage limit | WebSearch（Tier 2）に全面切り替え |
| input.json の JSON syntax error（タイトル内の引用符） | タイトル文字列から二重引用符を除去 |
| emit_creator_queue_v2.py でABOUT関係が0件 | 既存Concept IDを照会し手動でリレーションを作成 |

## 決定事項

1. **スピ系3軸収集方針**: AI占い副業・YouTube収益化・占い詐欺懐疑の3軸でソースを収集する（`dec-2026-03-27-spiritual-collection-axes`）
2. **creator-2.0スキーマ継続**: 既存スキーマがスピ系にも適合。MonetizationMethod・EmotionalHook・Skill・ContentFormatが重点カテゴリ（`dec-2026-03-27-spiritual-neo4j-schema`）

## 投入結果サマリー

| 種別 | 新規 | 更新 |
|------|------|------|
| Concept | 8 | - |
| Entity | 5 | 7 |
| Fact | 7 | - |
| Tip | 9 | - |
| Story | 4 | - |
| Source | 9 | 1 |
| Domain | 5 | - |

**リレーション合計**: 103件
- ABOUT×43, MENTIONS×24, IN_GENRE×20, FROM_SOURCE×20, IS_A×8, ENABLES×5, SERVES_AS×3

### 主要収集情報

- **AI占い副業の収益フロー**: Threads集客→LINE誘導→STORES販売（月収10-50万円事例）
- **グローバル占星術アプリ市場**: 2023年23億USD→2032年142億USD（CAGR 22.5%）
- **スピリチュアルYouTuberの多角化**: 広告収益＋オンラインコース＋グッズ販売
- **占い詐欺手口**: 追加料金誘導・霊感商法・解除料金の3パターン
- **タロット体験談**: 初心者の学習過程と転機体験

### 利用ソース（主要10件）

1. shift-ai.co.jp - AI占い副業収益化ガイド
2. addness.co.jp - 2024年占い市場分析
3. media.brain-market.com - スピリチュアル系副業動向
4. softkingo.com - タロット占いアプリ市場レポート
5. skill-hacks.co.jp - 占い師YouTube戦略
6. intermedialabo.com - スピリチュアルコンテンツ収益化
7. Reddit r/spirituality - 英語圏の懐疑的議論
8. Reddit r/tarot - タロット体験談
9. WebSearch - スピ系クリエイター全般調査
10. WebSearch - AI占いサービス事例収集

## アクションアイテム

- [ ] creator-enrichmentスキルでスピ系の追加リサーチサイクルを実行し残存ギャップを解消する（Conceptカバレッジ80%以上へ）（優先度: 中）[`act-2026-03-27-001`]
- [ ] 未カバーConceptカテゴリ（RiskWarning・ToolEcosystem・CommunityDynamic等）へのコンテンツ補充（優先度: 低）[`act-2026-03-27-002`]

## 次回の議論トピック

- スピ系記事の初稿作成（収集データを使った記事生成）
- 信頼性・リスク情報の補充（RiskWarningカテゴリのコンテンツ不足）
- 他ジャンル（career/beauty-romance）との比較分析

## 参考情報

- Neo4j ノード: `disc-2026-03-27-spiritual-creator-research`
- graph-queue処理済み: `.tmp/creator-graph-queue/.processed/cq-20260327021717-376be80b.json`
- input JSON: `.tmp/creator-research-spiritual_20260327-111500.input.json`
