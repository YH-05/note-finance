# 議論メモ: RSS → Neo4j パイプライン修正・手動テスト成功

**日付**: 2026-04-10
**参加**: ユーザー + AI

## 背景・コンテキスト

NASに保存されているRSSスクレイピング済みの金融ニュースをresearch-neo4jに投入するパイプラインの
整備状況を確認し、発見した問題を修正・手動テストまで完了した。

## 議論のサマリー

### パイプライン現状診断

3段パイプライン（scrape → emit → ingest）の各コンポーネントは存在するが、**繋がっていなかった**。

| コンポーネント | 状態 | 問題 |
|---|---|---|
| scrape_finance_news.py | ✅ launchd 0/6/12/18時 | NASに実データ蓄積済み |
| FinanceNewsMapper | ✅ 実装済み（2026-04-04拡張） | **入力フォーマット不一致** |
| emit_research_queue.py | ✅ finance-news-workflow対応 | Mapper経由で使用可能 |
| ingest_graph_queue.py | ✅ 実装済み | graph-queueが空だったので未使用 |

### 発見したバグ: 入力フォーマット不一致

FinanceNewsMapper が旧廃止フロー（collect_finance_news）の `articles[]` + `feed_source` 形式を
期待していたが、scraper の実出力は `news[]` + `source` 形式だった（設計ミス）。

| 項目 | scraper出力（正） | Mapper期待値（旧・誤） |
|---|---|---|
| 記事リストキー | `news[]` | `articles[]` |
| ソース名フィールド | `source` (例: `ars_technica`) | `feed_source` (例: `CNBC - Markets`) |

### 修正内容

**`scripts/mappers/finance_news.py`**:
- `input_data.get("articles", [])` → `input_data.get("news", [])`
- `feed_source=article.get("feed_source", "")` → `feed_source=article.get("source", "")`
- `source_type="news"` を `_make_source` 呼び出しに追加

**`tests/scripts/test_emit_graph_queue.py`**:
- `_news_batch()` ヘルパーの返却キーを `articles` → `news` に変更
- デフォルト記事の `feed_source` → `source` に変更（全8テストケース）

### Neo4j 障害の修正

投入テスト中に `TransactionLogError` が発生。原因は
`/data/transactions/research` ディレクトリが `root:root` 所有であったため、
neo4j ユーザーが新規トランザクションログファイルを作成できなかった。

**修正**: `docker exec -u root neo4j-enterprise chown -R neo4j:neo4j /data/transactions/research`

### 手動パイプラインテスト結果

`ars_technica/processed/2026-04-01/news_030006.json`（20記事）で全工程テスト:

| ステップ | コマンド | 結果 |
|---|---|---|
| emit | `uv run python scripts/emit_research_queue.py --command finance-news-workflow --input <json>` | sources:20, claims:20, chunks:20, topics:99, authors:13 |
| ingest (dry-run) | `uv run python scripts/ingest_graph_queue.py --queue-dir .tmp/graph-queue --dry-run` | 1件認識 |
| ingest (実投入) | `uv run python scripts/ingest_graph_queue.py --queue-dir .tmp/graph-queue` | 1件投入成功 |
| Neo4j確認 | MATCH (s:Source)-[:CONTAINS_CHUNK]->(c:Chunk) | 20件リンク確認 |

## 決定事項

1. **FinanceNewsMapper の入力フォーマットを news[] に統一**（実装済み）
2. **source_type="news" を追加**（実装済み）
3. **Neo4j transactions/research パーミッション修正**（適用済み）
4. **手動テストが成功したことで、パイプライン実装は完了とみなす**

## 今後のアクションアイテム

- [ ] NASの既存scraped JSONをバックフィル投入する（優先度: 中）
  - 対象: `/Volumes/personal_folder/scraped/` 配下の全ソースのprocessed/
  - ループで emit → ingest を繰り返す
- [ ] emit + ingest を launchd で定期実行登録（優先度: 中）
  - 推奨: 1日1回（6:00 or 12:00）
- [ ] `/data/transactions/` の他DB（creator/note/quants）も chown 確認（優先度: 高）

## 変更ファイル

| ファイル | 変更内容 |
|---------|---------|
| `scripts/mappers/finance_news.py` | `articles[]` → `news[]`、`feed_source` → `source`、`source_type="news"` 追加 |
| `tests/scripts/test_emit_graph_queue.py` | `_news_batch()` 形式変更、全8テストケースのフィールド修正 |

## テスト

16/16 全通過（変更前後）。
