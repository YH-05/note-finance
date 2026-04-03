# 議論メモ: PR #317 Wave1 マージ & worktree クリーンアップ

**日付**: 2026-04-03
**参加**: ユーザー + AI

## 背景・コンテキスト

research-neo4j KG v3 移行プロジェクト（Project #107）の Wave1 として、移行前バックアップ・データクレンジングツール群を実装した PR #317 がマージ可能な状態になった。

## 実施内容

### PR #317 マージ

- **タイトル**: [Wave1] 移行前バックアップ・スナップショット取得 (#302)
- **ブランチ**: feature/issues-302-316 → main（squash merge）
- **変更規模**: 83ファイル、+11,171行、-2,677行
- **CI**: 全パス（Unit Tests, Type Check, KG Quality, Lint）

#### 主な変更内容

**新規スクリプト**:
- `scripts/snapshot_pre_migration.py` — 移行前スナップショット取得
- `scripts/process_isolated_nodes.py` — 孤立ノード処理
- `scripts/dedup_entities.py` — エンティティ重複排除
- `scripts/migrate_relations_to_relates_to.py` — RELATES_TO リレーション移行

**削除（Entity廃止関連の旧スクリプト）**:
- `scripts/entity_backfill.py`
- `scripts/fix_entity_id_null.py`
- `scripts/migrate_entity_multilabel.py`

**強化**:
- `src/data_pipeline/neo4j_loader.py` — 大幅強化
- `scripts/entity_linker.py` — 更新
- `scripts/ontology_loader.py` — 強化

**テスト追加**:
- `tests/scripts/test_snapshot_pre_migration.py`
- `tests/scripts/test_process_isolated_nodes.py`
- `tests/scripts/test_dedup_entities.py`
- `tests/scripts/test_migrate_relations_to_relates_to.py`
- その他テスト更新多数

### Worktree クリーンアップ

- **削除 worktree**: `/Users/yukihata/Desktop/.worktrees/note-finance/feature-prj107`
- **削除ブランチ**: `feature/issues-302-316`（ローカル + リモート）
- **未コミット変更**: main に既に含まれていたため安全に破棄

## 決定事項

1. Wave1（PR #317）を main にスカッシュマージ完了。移行前ツール群がメインラインに統合された。

## アクションアイテム

- [ ] Wave2 以降の Issue 確認と実行計画策定（Project #107 の残 Issue を確認し、次の Wave のスコープを決定する）(優先度: 高)

## 次回の議論トピック

- Wave2 のスコープ決定（実際の KG v3 移行実行）
- 移行前スナップショットの実行タイミング
