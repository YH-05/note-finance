# 議論メモ: creator-neo4j 品質チェック + メンテナンス一括実行

**日付**: 2026-03-25
**参加**: ユーザー + AI

## 背景・コンテキスト

creator-neo4j (bolt://localhost:7689) は前日(3/24)のenrichmentセッション後、ノード7,361・リレーション13,401に成長。
定期的な品質チェックとメンテナンスを実施し、データ整合性の改善を行った。

## 実施内容

### Phase 1: 品質チェック（7カテゴリ + LLM-as-Judge）

| カテゴリ | スコア | 重み |
|---------|--------|------|
| Completeness | 83% | 20% |
| Consistency | 99% | 15% |
| Structural | 97% | 15% |
| Orphan | 82% | 15% |
| Content Balance | 68% | 10% |
| Source Quality | 93% | 10% |
| Taxonomy | 72% | 15% |

**LLM-as-Judge**: Content Quality Avg 0.685, Concept Classification Avg 0.74

### Phase 2: Embedding 更新

- Entity 7件、Fact 9件、Tip 6件、Story 9件 = 計31件のembedding付与

### Phase 3: 自動修復

| 修正内容 | 件数 | 詳細 |
|---------|------|------|
| IN_GENRE 不整合削除 | 365件 | genre プロパティと IN_GENRE リレーション先の不一致を全削除 |
| Stub Concept 削除 | 3件 | `(stub: SERVES_AS target for ...)` 等のゴミノード |
| 完全孤立 Concept 削除 | 4件 | category="Tip" の不正 Concept |
| 孤立 Entity 接続 | 3件 | Medium, GMOペパボ, TypeScript に MENTIONS 追加 |
| Category タイポ修正 | 1件 | RevenizationMethod → MonetizationMethod |
| Retroactive ABOUT リンキング | 652件 | ABOUT 未接続 Content 315→65件に79%削減 |

### Phase 4: 重複検出 + マージ

**Entity 3件マージ**:
- Google AdSense (company) → Google AdSense (platform) に統合
- note / Note → "note" に統合
- type女性の転職エージェント → type転職エージェント に統合

**Concept 19件マージ**（表記揺れ・和英揺れ・単複揺れ）:
- クリエイター収益化 / クリエイター向け収益化
- 月次収益 / 月間収益
- 従量課金 / 従量課金制
- Cashback / Cash Back
- Sponsorships / Sponsorship
- SNS Marketing / SNSマーケティング
- せどり・転売 / せどり（転売・リセール）/ せどり・物販（3→1に統合）
- 他12件

**月5万円達成 / 月20万円達成** は異なるマイルストーンとしてマージ対象外。

## 決定事項

1. **IN_GENRE は genre プロパティを正とする** — 不整合発生時は IN_GENRE を修正
2. **Retroactive ABOUT リンキングは安全に実行可能** — Concept名4文字以上・上位5件制限で誤接続リスク低
3. **重複マージは Vector Index 類似度で検出し手動確認後に実行** — Entity>0.92, Concept>0.93 が実用的閾値

## アクションアイテム

- [ ] 次回 enrichment で Story 収集を重点化（全ジャンル Story 比率 15-18% → 25% 目標）(優先度: 高)
- [x] enrichment パイプラインの IN_GENRE 付与ロジック修正 → `neo4j_writer.py` に IN_GENRE 専用分岐追加。DELETE old → MERGE で1コンテンツ1ジャンル制約を保証 (優先度: 高) **完了**
- [x] 定期重複検出の仕組み化 → `scripts/creator_detect_duplicates.py` 新規作成。Entity>0.92/Concept>0.93 閾値でJSON出力。`creator-maintenance.md` Step 4 に統合 (優先度: 中) **完了**

## スコア変動

| 指標 | Before (3/24 post-enrichment) | After (3/25 post-maintenance) | 変化 |
|------|------|------|------|
| ノード | 7,707 | 7,515 | -192 |
| リレーション | 11,817 | 13,839 | +2,022 |
| IN_GENRE 不整合 | 365 | 0 | -365 |
| ABOUT 未接続 Content | 315 | 65 | -250 |
| Overall Score | 84.5 (B) | 88.5 (B+) | +4.0 |

## スナップショット

- `data/processed/creator_quality/snapshot_20260325.json` — 品質チェック時点
- `data/processed/creator_quality/snapshot_20260325_post_fix.json` — 品質修正後
- `data/processed/creator_quality/snapshot_20260325_post_maintenance.json` — 全メンテナンス完了後
- `data/processed/creator_quality/content_quality_cache.json` — LLM-as-Judge 評価キャッシュ
