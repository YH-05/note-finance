# 議論メモ: session-memory（Claude Code 長期記憶システム）計画策定

**日付**: 2026-03-24
**参加**: ユーザー + AI
**ワークフロー**: /plan-project @docs/plan/2026-03-24_session-memory-implementation-plan.md

## 背景・コンテキスト

Claude Code のセッション間で会話コンテキストが失われる課題を解決する。sui-memory アーキテクチャを本プロジェクトに適合させて実装する計画を策定した。

## 実施内容

/plan-project ワークフローの全 5 Phase を完了:

1. **Phase 0（方向確認）**: workflow タイプ（パッケージ + Hook + CLI）に決定
2. **Phase 1（リサーチ）**: コードベース調査。ScrapeStateDB, entity_linker, rss/_logging.py 等の参照パターンを発見。transcript.jsonl の構造を実地検証
3. **Phase 2（計画策定）**: 12 Wave のアーキテクチャ・ファイルマップ・リスク評価を策定
4. **Phase 3（タスク分解）**: 12 GitHub Issue に分解、依存関係図作成
5. **Phase 4（GitHub登録）**: Project #99 作成、Issue #239-#250 登録、project-24/project.md 作成

## 決定事項

1. **Hook×Neo4j**: SessionEnd Hook で SQLite + Neo4j を同時投入（フル一貫性）
2. **Decision 競合**: 既存 Decision ノードへの entity_linker マッチを試み、見つからなければ新規作成
3. **テスト構造**: tests/unit/test_session_memory/（data_pipeline パターン）
4. **DDL 先行実行**: Wave 0 として note-neo4j の制約・fulltext index を先行作成

## リサーチで発見した重要事項

- transcript.jsonl の本文パスは `d['message']['content']`（計画の `d['content']` ではない）
- note-finance の実セッション数は 397（計画の 826 より少ない）、全プロジェクト合計 6,136
- note-neo4j に Session/SessionChunk は未存在（新規作成OK）
- sqlite-vec, sentence-transformers は未インストール（Wave 0/3 で対応）

## アクションアイテム

- [ ] [Wave0] note-neo4j DDL 先行実行 + sqlite-vec 確認 (#239)
- [ ] [Wave1] DB基盤: _logging / types / db + テスト (#240)
- [ ] [Wave2] chunker.py + テスト (#241)
- [ ] [Wave3] embedder.py + pyproject.toml (#242)
- [ ] [Wave4] searcher.py + テスト (#243)
- [ ] [Wave5] extractor.py + テスト (#244)
- [ ] [Wave6] linker.py (#245)
- [ ] [Wave7] CLI cli/main.py (#246)
- [ ] [Wave8] hook.py + 設定ファイル (#247)
- [ ] [Wave9] graph.py (#248)
- [ ] [Wave10] bulk-import + /memory-search (#249)
- [ ] [Wave11] 統合テスト (#250)

## 成果物

| 成果物 | パス |
|--------|------|
| 計画書 | `docs/project/project-24/project.md` |
| 元プラン | `docs/project/project-24/original-plan.md` |
| GitHub Project | [#99](https://github.com/users/YH-05/projects/99) |
| Worktree | `/Users/yukihata/Desktop/.worktrees/note-finance/feature-prj99` |
| リサーチ結果 | `.tmp/plan-project-20260324-092939/research-findings.json` |
| 実装計画 | `.tmp/plan-project-20260324-092939/implementation-plan.json` |
| タスク分解 | `.tmp/plan-project-20260324-092939/task-breakdown.json` |

## 次のステップ

1. worktree に移動: `cd /Users/yukihata/Desktop/.worktrees/note-finance/feature-prj99 && claude`
2. Wave 0 から実装開始: `/issue-implement 239`
