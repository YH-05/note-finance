# 議論メモ: 金融ニューススクレイピング → NAS → Neo4j パイプライン構築

**日付**: 2026-03-26
**参加**: ユーザー + AI

## 背景・コンテキスト

`collect_finance_news` ワークフロー（GitHub Issue作成系）を廃止した後、CNBC等の金融ニュースRSSをスクレイピングして原文保存しresearch-neo4jに投入するパイプラインが途切れていた。
`src/news_scraper/` パッケージ（CNBC RSS等）は存在するが、Article → Neo4j の経路がなかった。
加えて、スクレイピング定期実行をMac Mini（別PC）で動かしたいという要件が加わった。

## 議論のサマリー

### パイプライン調査

- `src/news_scraper/unified.py` の Layer 2 hook でRawStoreへの保存は既に実装済み
- `emit_research_queue.py` の `map_finance_news()` → `_build_queue_doc()` で graph-queue JSON 生成が可能
- `src/data_pipeline/neo4j_loader.py` の `ingest_to_neo4j()` で Python ネイティブに Neo4j へ書き込み可能
- これらを組み合わせて `scrape_finance_news.py` から直接パイプライン構築することにした

### Mac Mini 対応

- Mac Mini は `bolt://localhost:7688`（research-neo4j）に接続できない
- 解決策: `--skip-neo4j` フラグでPhase 3（Neo4j投入）をスキップし、graph-queue JSON を NAS に書き出す
- メインマシンが `ingest_graph_queue.py` で NAS の queue を読んで Neo4j に投入する2段構成

### データ保存先の統一

全データを NAS に保存するため、3つのパスを環境変数化:
- `NAS_SCRAPED_BASE` → スクレイプJSON（既存）
- `RAW_STORE_DIR` → RawStore原文JSON
- `GRAPH_QUEUE_DIR` → graph-queue JSON（新規）

## 決定事項

1. **`scrape_finance_news.py` を改修**して graph-queue 生成 + NAS保存 + Neo4j投入の3フェーズ構造を追加
   - Phase 1: graph-queue JSON 生成（常に実行）
   - Phase 2: graph-queue を NAS に書き出し（常に実行、非ブロッキング）
   - Phase 3: Neo4j 投入（`--skip-neo4j` なしの場合のみ）

2. **`--skip-neo4j` フラグ**を追加。Mac Mini での定期実行時は Phase 1+2 のみ実行

3. **`scripts/ingest_graph_queue.py`** を新規作成。NAS の queue ファイルを走査し Neo4j に投入後 `processed/` に移動

4. **3つの環境変数**を Mac Mini の launchd plist に設定する運用とする

5. **`raw_store.py`** の `_DEFAULT_EXTERNAL_DIR` を `RAW_STORE_DIR` 環境変数でオーバーライド可能にした

## アーキテクチャ

```
Mac Mini (launchd 定期実行)
    scrape_finance_news.py --skip-neo4j
    ├── RSSスクレイピング → NAS scraped JSON (NAS_SCRAPED_BASE)
    ├── RawStore 原文保存 → NAS raw_texts (RAW_STORE_DIR)
    └── graph-queue JSON → NAS (GRAPH_QUEUE_DIR/finance-news-workflow/*.json)

メインマシン (手動 or 定期実行)
    ingest_graph_queue.py
    ├── NAS の pending queue files を走査
    ├── Neo4j MERGE 投入 (bolt://localhost:7688)
    └── 成功ファイルを processed/ に移動（失敗ファイルは残留→次回リトライ）
```

## アクションアイテム

- [ ] Mac Mini に launchd plist を作成・登録（`--skip-neo4j` + 3つの env var 設定） (優先度: 高)
- [ ] メインマシンにも `ingest_graph_queue.py` の定期実行を設定（launchd or cron） (優先度: 中)
- [ ] Mac Mini でのテスト実行（`scrape_finance_news.py --skip-neo4j --dry-run` 相当） (優先度: 高)
- [ ] `ingest_graph_queue.py --dry-run` で NAS の queue ファイルが認識されるか確認 (優先度: 高)

## 次回の議論トピック

- Mac Mini での実際の動作検証結果
- launchd の実行間隔設計（1日2回 or 4回等）
- `ingest_graph_queue.py` をメインマシンの launchd に組み込む

## 実装ファイル

| ファイル | 変更内容 |
|---------|---------|
| `scripts/scrape_finance_news.py` | `--skip-neo4j`フラグ追加、`_ingest_source_to_neo4j()`追加、NASパス定数追加 |
| `src/data_pipeline/storage/raw_store.py` | `RAW_STORE_DIR` 環境変数サポート追加 |
| `scripts/ingest_graph_queue.py` | 新規作成（NAS queue → Neo4j 投入スクリプト） |
