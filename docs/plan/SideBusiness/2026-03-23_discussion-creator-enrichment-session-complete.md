# 議論メモ: creator-neo4j enrichmentセッション + 4残タスク一括実行

**日付**: 2026-03-23
**参加**: ユーザー + AI

## 背景・コンテキスト

creator-neo4j v2再設計(Phase A-E) + 27サイクルenrichment + Phase F(活用)が前セッションで完了。
本セッションでは次のアクションを議論し、enrichment継続を選択。さらに4残タスクを一括実行した。

## 議論のサマリー

### Phase 1: 方向性の議論

4つの選択肢（A: enrichment継続 / B: neo4j-lifecycle開発 / C: 品質チェック整備 / D: 実記事検証）から
**A: enrichment継続**を選択。理由: 記事執筆の素材充実に直結するROIが最も高い。

### Phase 2: Enrichment Cycle 1（美容・恋愛）

| 項目 | 成果 |
|------|------|
| 検索結果 | Tavily EN/JP + Reddit + 美容サロン記事 = 15件 |
| Fact | 3件（婚活アプリ成婚率データ、美容サロン開業費用、プロフィール最適化データ） |
| Tip | 3件（婚活7ステップ、一人サロン客単価戦略、サロン集客3パターン） |
| Story | 4件（マッチングアプリ成婚27事例、結婚相談所年代別体験談、メンズ脱毛サロン独立、婚活失敗3パターン） |
| Concept | 33件（How層+22: PersuasionTechnique, EmotionalHook, CopyFramework, Objection） |
| Source | 6件 |

### Phase 3: Skill精緻化（168件再分類）

| バッチ | サンプル数 | 再分類数 |
|--------|-----------|---------|
| Batch 1 | 50件 | 18件 |
| Batch 2 | 50件 | 20件 |
| Batch 3 | 100件 | 37件 |
| Batch 4 | 100件 | 42件 |
| Batch 5 | 100件 | 44件 |
| **合計** | **500件** | **168件** |

再分類先の内訳:
- ContentFormat +26, Regulation +19, Objection +18
- AcquisitionChannel +16, SuccessMetric +16, Audience +15
- PersuasionTechnique +13, MonetizationMethod +12
- Transformation +9, EmotionalHook +8
- CopyFramework +4, Milestone +3, RevenueModel +0

### Phase 4: Entity誤混入修正（7件）

| Concept名 | 処理 | Entity entity_key |
|-----------|------|-------------------|
| Canva | 既存Entity接続 | Canva::platform |
| Buffer | 新規Entity作成 | Buffer::platform |
| Threads | 新規Entity作成 | Threads::platform |
| note | 既存Entity接続 | note.com::platform |
| Pairs | 既存Entity接続 | Pairs::platform |
| PwC | 新規Entity作成 | PwC::company |
| IBJ | 既存Entity接続 | IBJ::company |

59件のMENTIONSリレーション復元、7件のConceptノード削除。

### Phase 5: entity_linkerバグ修正

- **問題**: `resolve_all()` が `sources/facts/tips/stories/genre` 等の入力フィールドを返却時に落とす
- **原因**: 新規dictを構築する際にentities/concepts/serves_as/concept_relations/statsのみを含め、他のフィールドをコピーしていなかった
- **修正**: 入力dataの全フィールドを保持し、entities/conceptsのみオーバーレイする方式に変更
- **テスト**: 32テスト全PASS

## 決定事項

1. **Skill精緻化168件完了**: 761→593件(51%→39%)、各カテゴリが倍増
2. **Entity誤混入修正手順を確立**: entity_key照合→ABOUT→MENTIONS変換→DETACH DELETE
3. **entity_linkerバグ修正**: resolve_allの入力フィールド保持問題を根本修正

## Before → After

| 指標 | Before | After | 変化 |
|------|--------|-------|------|
| Skill占有率 | 51.2% | 39.2% | **-12.0pt** |
| Skill件数 | 761 | 593 | -168件 |
| Story | 86 | 90 | +4件 |
| Story比率 | 11.6% | 12.0% | +0.4pt |
| How層合計 | 91 | 113 | +22件 |
| Concept合計 | 1,486 | 1,512 | +26件(+33-7) |
| Entity | 61 | 64 | +3件 |
| Source | 445 | 451 | +6件 |
| MENTIONS | 150 | 209 | +59件 |

## アクションアイテム

- [ ] Skill精緻化の継続: 残593件中約150件が再分類対象。30%台を目指す (優先度: 中)
- [ ] Story enrichment継続: 12%→25%目標。推定10サイクル必要 (優先度: 中)
- [ ] Entity誤混入の系統的検出: 英語固有名詞候補を一括抽出・変換 (優先度: 低)

## 次回の議論トピック

- Skill精緻化の残りをどこまで追求するか（39%で十分か、30%を目指すか）
- enrichment自動化の検討（定期実行の仕組み）
- creator-neo4j-quality-check スキルの実装タイミング
- neo4j-lifecycle (Project #94) の着手タイミング
