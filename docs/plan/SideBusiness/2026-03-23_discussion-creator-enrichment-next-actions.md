# 議論メモ: creator-neo4j 次のアクション決定

**日付**: 2026-03-23
**参加**: ユーザー + AI

## 背景・コンテキスト

creator-neo4j v2再設計(Phase A-E) + 27サイクルenrichment + Phase F(活用)が完了。
未完了ActionItemが11件あり、方向性の選択が必要だった。

## 議論のサマリー

4つの選択肢を検討:
- A: enrichment継続（データ品質向上）→ **採用**
- B: neo4j-lifecycle開発（Project #94 汎用化）→ 後回し
- C: 品質チェック整備（quality-checkスキル）→ 後回し
- D: 実記事での検証（Phase Fクエリ活用）→ 記事執筆時に自然検証

### 現状データ分析

| 指標 | 現状 | 目標 | ギャップ |
|------|------|------|---------|
| Skill占有率 | 51% (761/1486) | 30%以下 | 再分類で約300件移動 |
| Story比率 | 11.6% (86/739) | 25% | +約100件必要 |
| How層合計 | 91件 (6.1%) | 15% | +約130件必要 |
| MENTIONS/Entity | 1.3件 | 3.0+ | backfill Phase 2 |

## 決定事項

1. **enrichment継続を最優先**: Skill精緻化 + Story比率改善を同時進行
2. **neo4j-lifecycle (Project #94)は後回し**: creator-neo4j単体のROIに寄与しない
3. **品質チェックスキルも後回し**: データ充実が先

## アクションアイテム

- [x] enrichment次回セッション: Skill精緻化 + Story比率改善 (優先度: 高) → 本セッションで実行
- [ ] enrichmentさらなるセッション: How層拡充(91件→220件) (優先度: 中)
- [ ] 日本語コンテンツ比率向上（note.com/ameblo.jp直接取得強化） (優先度: 中)

## 次回の議論トピック

- enrichment結果の振り返り（Skill比率・Story比率の変化）
- neo4j-lifecycle 着手タイミングの判断
- creator-neo4j-quality-check スキル実装タイミング
