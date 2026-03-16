# Project 13: save-to-article-graph スキル実装

## 概要

wealth blog スクレイピングと topic-discovery スキルが収集した情報を article-neo4j（bolt://localhost:7689）に蓄積するパイプラインを構築する。既存の `emit_graph_queue.py` + `save-to-graph` パターンを拡張し、2つの新コマンドマッパーとオーケストレータースキルを追加する。

## GitHub Project

- **番号**: #82
- **URL**: https://github.com/users/YH-05/projects/82

## Issue 一覧

| Wave | Issue | タイトル | サイズ | 依存 |
|------|-------|---------|--------|------|
| A | #124 | `_empty_rels()` に tagged 追加 | XS | - |
| A | #125 | `_parse_yaml_frontmatter()` 追加 | S | - |
| A | #126 | article-neo4j Author 制約追加 | XS | - |
| A | #127 | テストヘルパーデータ生成関数 | S | - |
| B | #128 | `_scan_wealth_directory()` + ディレクトリ対応 | M | #124, #125 |
| B | #129 | `map_wealth_scrape()` 実装 | L | #124 |
| B | #130 | `map_topic_discovery()` 実装 | L | #124 |
| C | #131 | wealth-scrape テスト | M | #128, #129, #127 |
| C | #132 | topic-discovery テスト | M | #130, #127 |
| C | #133 | save-to-article-graph SKILL.md | S | #129, #130 |
| D | #134 | E2E dry-run 検証 | S | #131, #132, #133 |

## 変更ファイル

| ファイル | 変更種別 |
|---------|---------|
| `scripts/emit_graph_queue.py` | 編集（マッパー2つ + フレームワーク拡張） |
| `docker/article-neo4j/init/01-constraints-indexes.cypher` | 編集（Author 制約） |
| `.claude/skills/save-to-article-graph/SKILL.md` | 新規 |
| `tests/scripts/test_emit_graph_queue.py` | 編集（テスト追加） |

## 設計判断

1. **Author サポート除外**: 全239ファイルの author が空文字のためデッドコード回避
2. **文字列ベース ID（topic-discovery）**: neo4j-mapping.md 準拠、UUID5 不使用
3. **明示的 tagged リレーション**: 暗黙 all-to-all を避けキーワードマッチング使用
4. **ドメイン分割出力**: wealth-scrape backfill の 239 ファイルをドメインごとに分割

## 元プラン

- 精査版: `docs/plan/2026-03-16_save-to-article-graph-refined.md`
- 元プラン: `docs/plan/2026-03-16_save-to-article-graph-skill.md`
