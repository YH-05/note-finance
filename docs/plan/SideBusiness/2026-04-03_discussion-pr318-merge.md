# 議論メモ: PR #318 Entity ノード正規化 Wave1-4 マージ完了

**日付**: 2026-04-03
**参加**: ユーザー + AI

## 背景・コンテキスト

Project #107 の Entity ノード正規化 Wave1-4（#302-#308）を実装した PR #318 のマージを実行。
Wave1 は先に PR #317 で squash merge 済み。PR #318 は残りの Wave2-4 の移行スクリプト・テストを含む。

## CI 修正のサマリー

### 失敗原因1: Unit Tests（6件失敗）

Neo4j Enterprise 統合後のポート番号不一致。Community 時代の個別ポート（7688/7689）がテストに残存していた。

**修正ファイル（5件）**:
- `tests/scripts/test_backfill_creator_source_published_at.py` — 7689→7687
- `tests/scripts/test_entity_linker.py` — 7689→7687
- `tests/scripts/test_fix_entity_id_null.py` — 7688→7687
- `tests/scripts/test_kg_quality_metrics.py` — 7688→7687
- `tests/scripts/test_strengthen_entity_connections.py` — 7688→7687（2箇所）

### 失敗原因2: Lint（pre-commit spawn error）

pre-commit が uv 依存に含まれておらず `uv run pre-commit` が CI で失敗。
`ruff format` + `ruff check --fix` で代替修正（50ファイルフォーマット、42 lint fix）。

### 失敗原因3: ruff format によるコンフリクト

ruff format を全体適用したことで main との差分が拡大し、8ファイルでコンフリクト発生。

**解消方法**: `git merge origin/main` で解消
- AA（add/add）4件: main の版を採用（Wave1 PR #317 で既にマージ済みのファイル）
- UD（update/delete）1件: feature branch の版を採用（entity_backfill.py）
- UU（content）3件: 手動マージ（mappers/base.py 等）

### 失敗原因4: 孤立テストファイル

`tests/scripts/test_fix_entity_id_null.py` が `scripts/fix_entity_id_null.py`（Wave1 PR #317 で削除済み）をインポートして `ModuleNotFoundError`。テストファイルを削除して解消。

## 決定事項

1. PR #318 を squash merge で main に統合（コミット: b1950b6）
2. CI 修正方針: ポート番号統一 + 孤立テスト削除 + ruff format 後の merge 戦略

## アクションアイテム

- [x] act-2026-04-03-001: PR #318 マージ（完了）
- [x] act-2026-04-03-003: kg-quality-check スキーマ修正後の検証（PR #318 に含まれて完了）

## 次回の議論トピック

- Project #107 の残 Issue 確認（Wave2 以降の DB 運用）
- act-2026-04-03-002: project-29 ドキュメント更新
- act-2026-04-03-004: dec-2026-03-30-entity-multilabel の status 更新
