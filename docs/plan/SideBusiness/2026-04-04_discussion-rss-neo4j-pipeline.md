# 議論メモ: RSS→research-neo4j パイプライン診断 + マッパー拡張

**日付**: 2026-04-04
**参加**: ユーザー + AI

## 背景・コンテキスト

RSSスクレイピングしたニューステキストを research-neo4j に投入するパイプラインの整合性を確認し、
不足しているマッピングを特定・修正した。

## 議論のサマリー

### パイプライン診断

3段パイプライン（emit_research_queue → entity_linker → neo4j_loader）は全て存在し、
`--command finance-news-workflow` で FinanceNewsMapper が呼ばれる経路も確認済み。

- スクレイパー: 13ソース対応（CNBC, NASDAQ, 株探, ロイターJP, みんかぶ, JETRO 等）
- `Article` モデル: title, url, published, source, category, summary, content, author, tags, metadata
- `include_content=True` で ArticleExtractor(trafilatura) がフル本文を取得可能

### 特定された問題

`FinanceNewsMapper.map()` が以下のフィールドを未使用のまま捨てていた:

| フィールド | 状態 | 修正内容 |
|---|---|---|
| content (本文) | 未使用 | → Chunk ノード + CONTAINS_CHUNK |
| category | 未使用 | → Topic ノード + TAGGED |
| tags | 未使用 | → Topic ノード + TAGGED |
| author | 未使用 | → Author ノード (type=journalist) + AUTHORED_BY |

### 修正内容

`scripts/mappers/finance_news.py` を拡張:
- Chunk 生成: content が存在する場合、source_id + index=0 で Chunk ノードを生成
- Topic 生成: category + tags から重複排除した Topic ノードを生成、各 Source に TAGGED リレーション
- Author 生成: author が存在する場合、journalist タイプの Author ノードを生成（重複排除済み）
- relations dict に tagged / contains_chunk / authored_by を格納

下流（entity_linker, neo4j_loader）は変更不要。build_result() が全ノード種別を受け取れる設計。

## 決定事項

1. FinanceNewsMapper をフルマッピング対応に拡張（実装済み）

## テスト結果

テスト 16件全パス（既存 8件 + 新規 8件）:
- content → Chunk 生成
- content 空 → Chunk 未生成
- category + tags → Topic 生成
- Topic 重複排除
- author → Author 生成
- Author 重複排除
- 全フィールド揃った記事でフルマッピング
- author 空文字 → Author 未生成

## アクションアイテム

- [ ] include_content=True でのフルパイプラインテスト（優先度: 高）
- [ ] Chunk 投入後の LLM エンティティ抽出検討（優先度: 中）

## 変更ファイル

- `scripts/mappers/finance_news.py` — マッパー拡張
- `tests/scripts/test_emit_graph_queue.py` — テスト追加（8件）
