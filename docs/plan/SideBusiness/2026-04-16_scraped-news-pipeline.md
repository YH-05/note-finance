# 議論メモ: NASスクレイプ済み金融ニュースをresearch-neo4jに投入する手動実行パイプライン構築

**日付**: 2026-04-16
**参加**: ユーザー + AI
**Discussion ID**: `disc-2026-04-16-scraped-news-pipeline`

## 背景・コンテキスト

NAS (`/Volumes/personal_folder/scraped`) には 11 ソースの金融ニュース JSON（cnbc, reuters_jp, kabutan, jetro, federal_reserve, zero_hedge, hacker_news, techcrunch, the_verge, ars_technica, developing_telecoms）が連日蓄積されているものの、research-neo4j への投入経路は:

- コードとしては `scripts/pipeline_scraped_to_neo4j.py` が存在したが、
- 定期実行の LaunchAgent が別リポジトリを指して停止、
- 最新の 4/15 分（合計 122 新規記事）が未投入、
- 過去実行時のログに "ServiceUnavailable on 7688"（旧 Community コンテナ向けデフォルト）の失敗履歴、

という状態だった。今回は「まず手動実行できる経路を整えて確実に投入する」ことを目的に、CLI・スキル・コマンドを整備しながら複数のバグを発見・修正した。

## 議論のサマリー

本セッションは対話型の議論というより、実装→検証→バグ修正の反復だったため、時系列で整理する。

### 1. 現状調査（NAS と Neo4j の確認）

- NAS 側: `scraped/_registry/processed_urls.jsonl` に 3,324 URL 登録済み、4/15 の未処理ファイルには新規 URL が含まれることを抜き取り確認。
- Neo4j 側: `docker ps` で `neo4j-enterprise` が healthy、multi-database で `research/note/creator/quants` がすべて `online`。つまり再起動は不要で、デフォルト URI を 7687 に合わせれば良い。

### 2. CLI / スキル / コマンドの整備

- `scripts/pipeline_scraped_to_neo4j.py` に `_check_nas_mounted` / `_check_neo4j_available` の pre-check を追加。`--skip-precheck` / `--neo4j-uri` フラグを追加。
- `NEO4J_RESEARCH_URI` デフォルトを `NEO4J_URI` 環境変数優先、未設定時は `bolt://localhost:7687`（Enterprise）に変更。
- `.claude/skills/pipeline-scraped-news/SKILL.md` を作成し、`/pipeline-scraped-news` コマンドから呼び出せるようにした。

### 3. dry-run バグの発見と修正

`--dry-run` で「新規 0 件」と出るのは誤表示だった。原因は `_run_stage2_dedup` が常に stdout 最終行をパスと解釈していたが、`dedup_scraped.py` は dry-run 時にはパスを `print` しない仕様。修正内容:

- `capture_output=True` にしてサブプロセスログをユーザーへパススルー
- dry-run 時は stdout 最終行の解析をスキップし、sentinel (None) を返して Stage 3/4 をスキップ

修正後、dry-run で各ソース別新規件数と合計 122 が正しく報告されるようになった。

### 4. 本実行時に発覚した Mapper バグ

本実行は exit 0 で完走し「ingest 完了」と出たが、`MATCH (s:Source) ... new_sources` で 0 件。graph-queue JSON を確認すると `sources: 0 / claims: 0 / chunks: 0 / ...` と完全に空。

原因: **`FinanceNewsMapper.map()` が `input_data.get("news", [])` しか読んでいなかった**。`dedup_scraped.py` の出力は `{"articles": [...], "session_id": ..., "batch_label": ...}` なので、122 記事すべてが `articles` キーから拾えずスルー。

修正内容（`scripts/mappers/finance_news.py`）:

```python
# scrape_finance_news.py 出力は "news"、dedup_scraped.py 出力は "articles" を使う
articles = input_data.get("news") or input_data.get("articles", [])
...
feed_source=article.get("source") or article.get("feed_source", ""),
```

修正後に再 emit → ingest した結果、**122 Source + 99 Claim = 246 ノード + 488 リレーション** が research DB に投入された（spot-check で ars_technica・cnbc の新規 URL を確認）。

### 5. Stage 4 ログの強化

ingest の「投入 1 件」表示はファイル数ベースで、実体のノード/リレーション数が見えずマッパーバグに気付くのが遅れた。改修内容:

- `scripts/ingest_graph_queue.py` の `process_queue` / `process_single_file` の返り値に `nodes` / `relations` を追加。`main()` のサマリに「投入ノード / 投入リレーション」を追加表示。
- `scripts/pipeline_scraped_to_neo4j.py` の `_run_stage4_ingest` を capture_output 化し、正規表現 `投入ノード:\s*(\d+).*?投入リレーション:\s*(\d+)` でパースして Stage 4 完了ログに `nodes=N relations=M` を付与。

以降は一目で空投入を検出可能。

## 決定事項

| # | 決定 ID | 内容 |
|---|--------|------|
| 1 | `dec-2026-04-16-pipeline-scraped-news-orchestrator` | `pipeline_scraped_to_neo4j.py` + `pipeline-scraped-news` スキル + `/pipeline-scraped-news` コマンドで手動実行経路を一元化 |
| 2 | `dec-2026-04-16-neo4j-uri-default-7687` | Neo4j URI デフォルトを `NEO4J_URI` env（未設定時は `bolt://localhost:7687`）に統一、Enterprise multi-db に揃える |
| 3 | `dec-2026-04-16-dry-run-stage2-only` | dry-run 時は `_run_stage2_dedup` が None を返して Stage 3/4 をスキップ、dedup ログはパススルー |
| 4 | `dec-2026-04-16-finance-news-mapper-articles-key` | `FinanceNewsMapper.map()` を `news` / `articles` 両対応、`source` / `feed_source` 両対応 |
| 5 | `dec-2026-04-16-stage4-node-rel-logging` | Stage 4 ログ + ingest サマリに投入ノード数・リレーション数を常時表示 |

## アクションアイテム

- [ ] `act-2026-04-16-001` (中) LaunchAgent plist を作成し pipeline-scraped-news を日次/週次で定期実行（pre-check 込み）
- [ ] `act-2026-04-16-002` (高) `scrape_finance_news.py` を拡張して `content`（本文）をスクレイプ対象に含める — 現状 Chunk/Author/Topic が 0 件になっている
- [ ] `act-2026-04-16-003` (中) `FinanceNewsMapper` の articles/news 両対応を unit test で固定化（`tests/unit/mappers/test_finance_news.py`）
- [ ] `act-2026-04-16-004` (低) `scraped/*/processed/` 配下の化石データ再投入手段の検討（レジストリ起点の replay CLI or 再処理不要と判断）
- [ ] `act-2026-04-16-005` (中) `_verify_ingestion` を拡張し、expected>0 だが実際のノード作成数が 0 のケースでも WARN を出す（今回のマッパーバグはこの段階で検出できたはず）

## 次回の議論トピック

- LaunchAgent 運用の具体化（cron 時刻、失敗時通知、pre-check 失敗時の挙動）
- scrape_finance_news.py の本文取得拡張によって ingest 下流（Chunk / Author / Topic / RELATES_TO）がどれだけ厚くなるかの評価
- dedup レジストリのガベコレ戦略（現状 3,324 URL、年内に 1 万件に到達見込み）

## 参考情報

- 成功実行ログ: `logs/pipeline-scraped-to-neo4j.log`（最新エントリ）
- 投入済み queue file: `.tmp/graph-queue/finance-news-workflow/processed/processed/gq-20260415234151-5563ac8d.json`
- research DB 現状: Source=4,595 / Fact=3,528 / Claim=3,043 / Chunk=3,024 / Topic=1,375
- feed 別 Source 合計: cnbc 565 / jetro 300 / kabutan 230 / reuters_jp 185 / zero_hedge 185 / hacker_news 143 / techcrunch 98 / the_verge 84 / ars_technica 60 / developing_telecoms 35 / federal_reserve 20
