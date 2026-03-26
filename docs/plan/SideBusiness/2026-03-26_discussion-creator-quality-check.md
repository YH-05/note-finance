# 議論メモ: creator-neo4j 品質チェック & 収益化可能性評価

**日付**: 2026-03-26
**参加**: ユーザー + AI

## 背景・コンテキスト

creator-neo4j が収益化可能なレベルに達しているかを評価するため、
7カテゴリの定量計測（creator-quality-check スキル）と LLM-as-Judge による
コンテンツ品質評価を実施した。

スナップショット: `data/processed/creator_quality/snapshot_20260326.json`
LLMキャッシュ: `data/processed/creator_quality/content_quality_cache.json`

## グラフ現況（2026-03-26時点）

| ノードタイプ | 件数 |
|---|---|
| Concept | 4,177 |
| Source | 1,708 |
| Fact | 944 |
| Tip | 805 |
| Entity | 734 |
| Story | 405 |
| Domain | 797 |
| ConceptCategory | 14 |
| Genre | 4 |
| **総ノード** | **9,588** |
| **総リレーション** | **17,703** |

## 品質スコア（7カテゴリ）

| カテゴリ | スコア | 重み | 加重スコア | 評価 |
|---|---|---|---|---|
| Completeness | 85.8% | 20% | 17.16 | ◎ |
| Consistency | 100.0% | 15% | 15.00 | ✅ |
| Structural | 90.0% | 15% | 13.50 | ◎ |
| Orphan | 80.0% | 15% | 12.00 | ○ |
| Content Balance | 55.0% | 10% | 5.50 | ⚠️ |
| Source Quality | 85.0% | 10% | 8.50 | ◎ |
| Taxonomy | 60.0% | 15% | 9.00 | ⚠️ |
| **総合** | | | **80.66** | **B** |

## LLM-as-Judge 評価（15件サンプル）

| 軸 | 平均スコア |
|---|---|
| Content Quality（実用性・具体性） | 0.663 |
| Source Grounding（ソース根拠） | 0.600 |
| Classification Accuracy（分類精度） | 0.567 |
| **総合** | **0.615** |

### 発見された問題

1. **Genre誤分類（20%）**: サンプル15件中3件が完全な誤分類
   - `tip-6cfdd4b5`: ポイントカード比較 → **spiritual**（本来 career/self-development）
   - `tip-e861128d`: ポイントサイト副業 → **spiritual**（本来 career）
   - `fact-b1c3034f`: YouTube法律解説 → **beauty-romance**（本来 career）
2. **source なし（13%）**: 2件が source 完全なし
3. **記事メタ説明化**: 一部 Tip がコンテンツ自体ではなく「記事の説明文」になっている

### Concept 分類評価（10件）

- 適切: 7/10（70%）
- 問題例: 「資生堂」→ Skill、「将来ビジョン」→ Skill、「SMART目標」→ Skill

## 構造的問題の詳細

### Completeness 主要課題

| 項目 | 充填率 | 重要度 |
|---|---|---|
| Story source_url | **14.1%** | 致命的 |
| Tip source_url | **26.2%** | 重大 |
| Fact source_url | 34.9% | 重大 |
| Concept genre | 33.6% | 中 |

### Content Balance 問題

- Genre偏り: career(1043) vs self-development(249) = **4.2:1**（許容3:1を超過）
- Story比率: **18.8%**（理想25%に対し不足）
- zero_content_concepts: **2,217件（53.1%）**がコンテンツと未接続

### ソース品質

- authority_level: blog 52.1% / official 7.6%（一次情報が少ない）
- 孤立Source（FROM_SOURCEなし）: **228件（13.4%）**

## 決定事項

1. **収益化判定**: careerジャンルのみ先行収益化可能。beauty-romance/spiritual はGenre誤分類修正後。
2. **品質評価**: 総合 78/100（Rating B）。追加enrichmentより構造修正を優先する。
3. **最優先アクション**: Genre誤分類修正（spiritual混入コンテンツの再分類）

## アクションアイテム

- [x] **[高] Genre誤分類の一括修正** — spiritual→career: 13件、beauty-romance→career: 88件、計101件を再分類済み（2026-03-26実行）(`act-2026-03-26-genre-misclassification-fix`)
- [x] **[高] source_url の充填** — Story 326件・Fact 591件・Tip 574件、計1,491件のsource_urlを FROM_SOURCE からコピー充填済み（2026-03-26実行）(`act-2026-03-26-story-source-url-fill`)
- [ ] **[中] 孤立Concept 2,117件の削減** — 重複・細粒度Conceptの統合削除 + コンテンツ生成でABOUT接続追加 (`act-2026-03-26-concept-isolation-reduce`)
- [ ] **[中] self-development ジャンル増強** — 249件 → 600件以上へ増強（現在career比1/4） (`act-2026-03-26-self-development-boost`)

## 次回の議論トピック

- Genre誤分類の根本原因（enrichmentスクリプトのGenre付与ロジック）の調査
- Concept粒度の見直し（4,177件は多すぎる可能性）
- careerジャンルでの記事生成パイプライン設計

## 参考情報

- 高品質コンテンツ例: `tip-30ea71c7`（doda.jp転職逆質問: 0.83）、`tip-2836bc7e`（パーソナルブランド7ステップ: 0.79）
- 問題コンテンツ例: `tip-e7bb15bd`（source完全なし: 0.35）、`tip-e861128d`（誤分類+低品質: 0.37）
- Storyは全体的に品質高め（story-50340897: 0.77）だが source_url 欠落が致命的
