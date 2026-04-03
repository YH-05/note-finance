# 議論メモ: creator-research コーチング・メンタリング・強み発見技術

**日付**: 2026-04-03  
**参加**: ユーザー + AI  
**Discussion ID**: disc-2026-04-03-creator-research-coaching

## 背景・コンテキスト

career ジャンルの creator-neo4j において「コーチング・メンタリング・自己理解・強み発見」関連の Concept カバレッジがゼロだった（concept_gap HIGH）。みつき（キャリア系クリエイター）のコンテンツ生成に向け、この領域の知識グラフを整備するために実施。

## 実施内容

`/creator-research コーチング、メンタリングの技術や指導方法、自己理解や強みを発見する技術について調査して。` を実行。

### 収集ソース（10件）

| ソース | 種別 | 言語 |
|-------|------|------|
| coachingfederation.org（ICF 2025コアコンピテンシー） | official | EN |
| gallup.com（強みベースコーチング） | official | EN |
| viacharacter.org（VIA強みコーチング） | official | EN |
| kaonavi.jp（メンタリングvsコーチング） | media | JA |
| bootcast.net（ICF ACC資格ガイド） | media | JA |
| hr-doctor.com（ストレングスファインダー解説） | media | JA |
| aihr.com（コーチングモデル2026） | media | EN |
| reddit.com r/Coaching（ICF ACCメンタリング体験） | social | EN |
| reddit.com r/careerguidance（31歳テックセールス燃え尽き） | social | EN |
| reddit.com r/careerguidance（29歳フィンテック→陶芸） | social | EN |

## 投入結果

| ノード種別 | 件数 |
|-----------|------|
| Genre | 1（career 更新） |
| ConceptCategory | 2（Skill, MonetizationMethod） |
| Domain | 7（新規） |
| Source | 10（新規） |
| Concept | 12（11既存更新 + 1新規） |
| Entity | 7（新規） |
| Fact | 5（新規） |
| Tip | 9（新規） |
| Story | 3（新規） |
| **リレーション合計** | **118件** |

### 主要 Concept（12件）
- コーチングスキル、自己適用（セルフコーチング）、エグゼクティブコーチング
- 認知科学ベースコーチング、自己の強み・個性の活用、コーチングROI 5.7倍
- コーチングサービス、強み・専門性の言語化、強みの言語化
- コーチング資格プログラム、GROWモデル、アクティブリスニング

### 主要 Entity（7件）
- ICF（国際コーチング連盟）、Gallup（ギャラップ社）、CliftonStrengths
- 銀座コーチングスクール、コーチ・エィ アカデミア、VIA Institute、VIA Survey

## 決定事項

1. コーチング・メンタリング領域のcreator-researchサイクル完了
   - schema_version: creator-2.0 で投入
   - キューファイル `.tmp/creator-graph-queue/cq-20260402220809-f58731a8.json` → `.processed/` に移動済み

## アクションアイテム

- [ ] エグゼクティブコーチング国内事例の追加調査（日系大手での実践ケース）(優先度: 中)
- [ ] 認知科学ベースコーチング詳細手法の追加調査 → `/creator-research` で再投入 (優先度: 中)
- [ ] BusinessModel/Framework/Mindset/MarketTrend の ConceptCategory 追加と IS_A 補完 (優先度: 低)

## 次回の議論トピック

- コーチング副業→本業移行のコンテンツ設計（みつき向け）
- creator-enrichment での定期更新サイクル設計

## 技術メモ

- creator-neo4j DB が `stopping` 状態になったためコンテナ再起動が必要だった（2026-04-03 午前）
- APOC `apoc.merge.relationship` は結果を `{}` で返すが実際には Cypher 実行済み（concept_relations 10件作成確認）
- ConceptCategory の有効値: Skill, MonetizationMethod のみ（BusinessModel/Framework/Mindset/MarketTrend は emit_creator_queue_v2.py で無効判定）
