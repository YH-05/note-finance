# 議論メモ: PR #225 マージ完了（neo4j-lifecycle スキル実装）

**日付**: 2026-03-23
**参加**: ユーザー + AI

## 背景・コンテキスト

GitHub Project #94 で計画した neo4j-lifecycle スキル実装（Issue #219-#224、4 Wave構成）が全て完了し、PR #225 としてまとめてマージする段階に到達。しかし CI の Unit Tests が10件失敗していたため、修正が必要だった。

## 議論のサマリー

### CI 失敗の原因分析

PR #225 で以下の3つの実装変更に対してテストが追従していなかった：

1. **test_kg_quality_metrics.py（6件失敗）**
   - `measure_structural` に `orphan_entity_count` クエリが新規追加され、戻り値が4指標→5指標に変更
   - モックセッションの `side_effect` に `orphan_entity_count` 用のモックが不足
   - エラー: `KeyError: 'orphan_entity_count'`

2. **test_fix_entity_id_null.py（3件失敗）**
   - `fix_entity_ids` にユニーク制約チェッククエリ（`entity_key` 重複検出）が追加
   - テストのモックが check query を考慮しておらず、`MagicMock > 0` で TypeError
   - エラー: `TypeError: '>' not supported between instances of 'MagicMock' and 'int'`

3. **test_e2e_save_to_article_graph.py（1件失敗）**
   - `emit_research_queue.py` の topic-discovery で `source_type` が `"original"` → `"report"` に変更
   - テストの期待値が未更新
   - エラー: `assert 'report' == 'original'`

### 修正内容

- `_make_mock_session_for_structural()` に `mock_orphan_entity` を追加（7つの side_effect）
- テスト名 `test_正常系_4指標を返す` → `test_正常系_5指標を返す`
- `TestFixEntityIds` の3テストに `mock_check.single.return_value = {"cnt": 0}` のモック追加
- `call_count` アサーションを `2` → `4`（check + update）
- `source_type` の期待値を `"report"` に更新

### マージ・クリーンアップ

- 修正コミット後 CI 全 PASS（7047 passed, 49 skipped）
- squash merge で main にマージ
- worktree `/Users/yukihata/Desktop/.worktrees/note-finance/feature-prj94` を削除
- ローカル・リモートの `feature/prj94` ブランチを削除

## 決定事項

1. CI テスト10件の修正方針（モック追加・期待値更新）を採用しマージ完了
2. Issue #219-#224 全て Done、GitHub Project #94 完了

## アクションアイテム

- [x] PR #225 CI修正 → マージ完了
- [x] worktree feature/prj94 クリーンアップ完了
- [x] ActionItem #219-#224 を completed に更新

## 完了した Issue 一覧

| Issue | Wave | 内容 | 状態 |
|-------|------|------|------|
| #219 | Wave1 | YAML スキーマ + テンプレート | Done |
| #220 | Wave1 | creator-enrichment Skill精緻化 | Done |
| #221 | Wave2 | Phase A-F ガイドファイル群 | Done |
| #222 | Wave3 | SKILL.md オーケストレーター + コマンド | Done |
| #223 | Wave3 | entity_linker --instance 汎用化 | Done |
| #224 | Wave4 | E2E検証（creator-neo4j --mode redesign） | Done |

## 次回の議論トピック

- neo4j-lifecycle スキルの実運用テスト（research-neo4j 等への適用）
- creator-enrichment 次回セッション（Skill精緻化 + Story比率改善）
