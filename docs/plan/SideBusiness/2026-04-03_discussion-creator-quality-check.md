# 議論メモ: creator-neo4j 品質チェック（2026-04-03）

**日付**: 2026-04-03
**参加**: ユーザー + AI

## 背景・コンテキスト

creator-neo4j（bolt://localhost:7689）のナレッジグラフ品質を定期計測。
前回スナップショット: 2026-03-26（78.2点）→ 今回: 2026-04-03

## 計測結果サマリー

**総合スコア: 83.6 / 100（Rating: B）**

ノード総数: 10,945（前回比 +1,357）
リレーション総数: 19,348（前回比 +1,645）

| ノード | 件数 | 前回比 |
|-------|------|--------|
| Concept | 4,843 | +666 |
| Entity | 955 | +221 |
| Fact | 1,018 | +74 |
| Tip | 901 | +96 |
| Story | 501 | +96 |
| Source | 1,868 | +160 |
| Genre | 6 | +2 |
| ConceptCategory | 19 | +5 |

### カテゴリ別スコア

| カテゴリ | スコア | 前回 | 差分 |
|---------|--------|------|------|
| Completeness（完全性） | 92.3% | 85.8% | **+6.5** |
| Consistency（一貫性） | 97.0% | 100.0% | -3.0 |
| Structural（構造） | 88.0% | 90.0% | -2.0 |
| Orphan（孤立ノード） | 90.8% | 80.0% | **+10.8** |
| Content Balance | 50.0% | 55.0% | -5.0 |
| Source Quality | 95.0% | 85.0% | **+10.0** |
| Taxonomy Quality | 62.0% | 60.0% | +2.0 |

## 主要課題

### 1. Content Balance（50%）― 最重要課題
- career ジャンルが全体の **56%** を独占（1,353件）
- asset-management: 19件（0.8%）、self-understanding: 15件（0.6%）
- ジャンル最大/最小比 = **90:1**（基準 3:1）
- Concept の **56.3%**（2,728件）がコンテンツ未接続

### 2. Taxonomy Quality（62%）
- IS_A 接続率: 98.2%（良好）
- ABOUT 接続率: **43.7%**（半数以上のConceptがコンテンツ未接続）
- ConceptCategory の偏り: Skill=1,242件 vs Barrier=1件（1,242倍）
- **Concept 誤分類 3件**:
  - `自己認識` → IS_A: Objection（正しくは SelfAwarenessMethod か Skill）
  - `Strategy` → IS_A: Skill（ConceptCategory に "Strategy" が存在するのに Skill に分類）
  - `OEM化粧品` → IS_A: Skill（正しくは MonetizationMethod か RevenueModel）

### 3. Orphan Entity（35.1%）
- 335 / 955 Entity が MENTIONS・SERVES_AS・RELATES_TO なしの孤立状態
- 多くは enrichment 未処理のノードと推定

### 4. Source タイトル未設定（185件）
- afb.com、influenceflow.com 等

## 良好な点

- **LLM Judge 総合スコア: 0.757**（前回 0.615 → +0.14 大幅改善）
- Source Quality: 95%（URL 100%・authority_level 99.9%）
- コンテンツ孤立: 3件のみ（0.12%）
- 平均リレーション数: 4.61（閾値 2.0 を大幅超過）
- 高品質コンテンツ例: tip-9e4836ef（0.93）、fact-cc5083ee（0.90）、story-33ca0811（0.87）

## 決定事項

1. Concept 誤分類 3件の IS_A リレーションを修正する
2. asset-management・self-understanding ジャンルの enrichment を優先実施
3. 孤立 Entity（335件）への MENTIONS/SERVES_AS リレーション補完バッチを計画

## アクションアイテム

- [ ] Concept誤分類修正: `自己認識`→SelfAwarenessMethod, `Strategy`→Strategyカテゴリ, `OEM化粧品`→MonetizationMethod（優先度: 高）
- [ ] asset-management・self-understanding ジャンルの enrichment 実施（優先度: 高）
- [ ] 孤立 Entity 335件の MENTIONS/SERVES_AS リレーション補完（優先度: 中）
- [ ] Source タイトルなし 185件の title 取得・補完（優先度: 中）
- [ ] Concept genre プロパティのバッチ補完（IS_A先 ConceptCategory から推定）（優先度: 低）

## 次回の議論トピック

- creator-neo4j A 評価（90点超）への改善ロードマップ
- asset-management・self-understanding ジャンルのデータソース戦略
- ABOUT 未接続 Concept（2,728件）の活用方針

## 参考情報

- スナップショット: `data/processed/creator_quality/snapshot_20260403.json`
- コンテンツ品質キャッシュ: `data/processed/creator_quality/content_quality_cache.json`
- 前回スナップショット: `data/processed/creator_quality/snapshot_20260326.json`
