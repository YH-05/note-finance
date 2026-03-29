# 議論メモ: scraped JSON → Neo4j 投入パイプライン再設計

**日付**: 2026-03-29
**参加**: ユーザー + AI

## 背景・コンテキスト

NASに定期実行RSSスクレイピングのJSONが蓄積されているが、重複排除→Neo4j投入の自動化フローが未完成だった。調査の結果、`scrape_finance_news.py` 内にgraph-queue生成機能が既に存在するが、スクレイピングと同時に実行されるためクロスラン重複がそのままgraph-queueに入る問題が判明。パイプラインを分離して再設計することで合意。

## 議論のサマリー

### 1. 現状の問題

- `scrape_finance_news.py` はスクレイピングと同時にgraph-queueを生成（Phase 2）
- 6時間ごとの実行で同一記事が複数graph-queueファイルに含まれる
- NASに graph-queue 87ファイルが滞留中（Neo4j未投入）
- `dedup_scraped.py` は未実装のまま

### 2. 設計方針の決定

**案A（パイプライン分離）** を採用:

```
Stage 1: scrape_finance_news.py   → scraped JSON保存のみ
Stage 2: dedup_scraped.py         → 重複排除 + 差分抽出
Stage 3: emit_research_queue.py   → graph-queue JSON生成
Stage 4: ingest_graph_queue.py    → Neo4j投入
```

### 3. dedup_scraped.py の責務

**ファイル整理 + 差分抽出** の両方を担う:

1. NAS `scraped/{source}/{date}/` から未処理JSONを読み込み
2. URLキーで全ソース横断の重複排除（最古エントリ採用）
3. レジストリで投入済みURLを除外 → 新規記事のみ抽出
4. `emit_research_queue.py` 入力形式で `.tmp/deduped-*.json` 出力
5. 元scraped JSONを `processed/` に移動
6. レジストリに新規URL追加

### 4. 投入済み管理方式

**ハイブリッド方式**:
- **プライマリ**: ファイル移動（`scraped/{source}/processed/{date}/` に移動）
- **バックアップ**: レジストリファイル（`scraped/_registry/processed_urls.json`）

### 5. NASディレクトリ構造

```
/Volumes/personal_folder/
├── scraped/
│   ├── cnbc/
│   │   ├── 2026-03-28/
│   │   │   ├── news_000012.json      ← 未処理
│   │   │   └── news_060008.json      ← 未処理
│   │   └── processed/
│   │       └── 2026-03-27/
│   │           └── news_000012.json   ← 処理済み
│   ├── ...（全11ソース）
│   └── _registry/
│       └── processed_urls.json        ← レジストリ
├── graph-queue/
│   └── finance-news-workflow/
│       └── gq-*.json                  ← Stage 3 出力
```

## 決定事項

1. **パイプライン分離（案A）**: scrape_finance_news.py からgraph-queue生成を外し、4段パイプラインに再構成
2. **投入済み管理**: ファイル移動 + レジストリのハイブリッド
3. **実行タイミング**: Stage 2-4 は1日1回バッチ（launchd深夜実行）
4. **既存graph-queue破棄**: 87ファイルを捨て、dedup後のクリーンデータから再生成
5. **全11ソース対象**: scrape_finance_news.py に全ソース統合済み（cnbc, developing_telecoms, kabutan, reuters_jp, jetro, techcrunch, ars_technica, the_verge, hacker_news, federal_reserve, zero_hedge）。scrape_jetro.py は廃止

## アクションアイテム

- [ ] `dedup_scraped.py` 実装（URL重複排除 + processed移動 + レジストリ更新） (優先度: 高)
- [ ] `pipeline_scraped_to_neo4j.py` オーケストレーター実装（Stage 2→3→4 順次実行） (優先度: 高)
- [ ] `scrape_finance_news.py` からPhase 2/3削除（新パイプライン安定後） (優先度: 中)
- [ ] `pipeline_scraped_to_neo4j.py` のlaunchd plist作成・1日1回バッチ登録 (優先度: 中)
- [ ] 既存graph-queue 87ファイルをtrash/に移動 (優先度: 低)

## 次回の議論トピック

- `scrape_finance_news.py` のPhase 2/3削除タイミング
- バッチ実行の時刻設定（深夜何時が適切か）

## Neo4j ノード

- Discussion: `disc-2026-03-29-scraped-to-neo4j-pipeline`
- Decision: `dec-2026-03-29-pipeline-separation`, `dec-2026-03-29-ingestion-tracking`, `dec-2026-03-29-batch-schedule`, `dec-2026-03-29-discard-existing-gq`, `dec-2026-03-29-initial-scope`
- ActionItem: `act-2026-03-29-dedup-scraped`, `act-2026-03-29-pipeline-orchestrator`, `act-2026-03-29-scrape-simplify`, `act-2026-03-29-launchd-pipeline`, `act-2026-03-29-discard-gq-files`
