# 議論メモ: academic パッケージ移植 + パイプライン整合性修正

**日付**: 2026-03-19
**参加**: ユーザー + AI

## 背景・コンテキスト

quants プロジェクトの `academic` パッケージを note-finance に移植した。
alphaxiv MCP で調査した論文の著者・引用文献情報を arXiv / Semantic Scholar API から自動取得し、
Neo4j ナレッジグラフに投入するためのパッケージ。

移植後、research-neo4j データ投入パイプラインとの整合性を検証したところ、5件の不整合を発見した。

## 議論のサマリー

### 検証で発見された5件の不整合

1. **`emit_graph_queue.py` に `academic-fetch` マッパー未登録** — 標準パイプライン経由の投入不可
2. **Source/Author ノードの ID キー名不一致** — `"id"` vs `"source_id"`/`"author_id"`
3. **`authority_level` の欠如** — neo4j-write-rules 投入前チェックリスト違反
4. **CITES/COAUTHORED_WITH Cypher テンプレート未定義** — save-to-graph guide に未記載
5. **backfill 出力パスの不一致** — `/save-to-graph` の自動スキャン対象外

### 修正内容

全5件を一括修正:

| ファイル | 変更 |
|---------|------|
| `src/academic/mapper.py` | `"id"` → `"source_id"`/`"author_id"`, `authority_level: "academic"` 追加 |
| `scripts/emit_graph_queue.py` | `map_academic_fetch` 関数追加, COMMAND_MAPPERS に登録 |
| `.claude/skills/save-to-graph/guide.md` | CITES/COAUTHORED_WITH テンプレート + Author UNIQUE 制約追加 |
| `src/academic/__main__.py` | backfill 出力先を `.tmp/graph-queue/academic-fetch/gq-{queue_id}.json` に変更 |

### テスト結果

- mapper ユニットテスト: 全合格（source_id/author_id キー確認、authority_level 確認）
- emit_graph_queue 統合テスト: 全合格（11コマンド登録確認、ノード/リレーション生成確認）

## 決定事項

1. academic mapper は `emit_graph_queue.py` のラッパー（`map_academic_fetch`）経由で標準パイプラインに統合
2. Source ノードの `authority_level` は `"academic"` 固定
3. backfill 出力は標準パス `.tmp/graph-queue/academic-fetch/` に統一

## アクションアイテム

- [x] research-neo4j に Author UNIQUE 制約を実行（優先度: 高）— 完了
- [x] テストスイート移植: `tests/academic/` の unit/property テスト（優先度: 中）— **34テスト全合格**
- [x] `/academic-fetch` スラッシュコマンド作成（優先度: 中）— `.claude/commands/academic-fetch.md`
- [ ] S2 API キー取得・設定（優先度: 低）— ユーザー手動申請待ち（`S2_API_KEY` 環境変数）

### テストスイート詳細

```
tests/academic/
├── conftest.py                          # 共通フィクスチャ
├── unit/
│   ├── test_mapper.py                   # mapper 単体テスト（20テスト）
│   └── test_cache.py                    # cache 単体テスト（8テスト）
└── property/
    └── test_mapper_property.py          # プロパティベーステスト（6テスト）
```

移植時の変更点:
- `database.id_generator` → `pdf_pipeline.services.id_generator`
- ID キー `"id"` → `"source_id"` / `"author_id"`
- `schema_version "2.1"` → `"2.2"`
- cache テストはスタンドアロン SQLiteCache に対応して再実装

## 参考情報

- 移植レポート: `academic-package-migration-report.md`
- パッケージ構成: `src/academic/` (11ファイル)
- graph-queue スキーマ: v2.2
