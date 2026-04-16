---
description: NAS上のスクレイプ済み金融ニュースをresearch-neo4jに投入する手動実行パイプライン。
argument-hint: [--dry-run] [--sources cnbc reuters_jp ...] [--scraped-base PATH] [--neo4j-uri URI] [--skip-precheck]
---

# /pipeline-scraped-news - NASスクレイプニュースをresearch-neo4jに投入

`/Volumes/personal_folder/scraped/` 配下の金融ニュース JSON（cnbc / reuters_jp / kabutan / jetro 等11ソース）を重複排除し、graph-queue を生成して research-neo4j に投入するコマンドです。

## 使用例

```bash
# 標準実行（全ソース投入）
/pipeline-scraped-news

# dry-run（新規件数だけ確認）
/pipeline-scraped-news --dry-run

# 特定ソースのみ
/pipeline-scraped-news --sources cnbc reuters_jp

# NAS/Neo4j 接続確認をスキップ
/pipeline-scraped-news --skip-precheck
```

## 引数

| 引数 | デフォルト | 説明 |
|------|-----------|------|
| `--scraped-base` | `/Volumes/personal_folder/scraped` | NAS scraped ルート |
| `--sources` | 全11ソース | 対象ソース名（スペース区切り複数可） |
| `--dry-run` | false | Stage 2 のみ preview、Stage 3/4 をスキップ |
| `--skip-precheck` | false | NAS/Neo4j 接続確認をスキップ |
| `--neo4j-uri` | `bolt://localhost:7688` | research-neo4j Bolt URI |
| `--log-level` | INFO | DEBUG/INFO/WARNING/ERROR |

## 処理フロー

```
Stage 1: pre-check        NAS マウント確認 + Neo4j 接続確認
Stage 2: dedup            重複排除 → .tmp/deduped-*.json + processed/ 移動
Stage 3: emit             .tmp/graph-queue/finance-news-workflow/gq-*.json 生成
Stage 4: ingest           research-neo4j に MERGE 投入（冪等）
```

このコマンドは `pipeline-scraped-news` スキルに処理を委譲します。

## スキル呼び出し

`pipeline-scraped-news` スキルを呼び出し、受け取った引数をそのまま `scripts/pipeline_scraped_to_neo4j.py` に渡して実行します。

## 関連リソース

| リソース | パス |
|---------|------|
| スキル | `.claude/skills/pipeline-scraped-news/SKILL.md` |
| CLI 本体 | `scripts/pipeline_scraped_to_neo4j.py` |
| Stage 2 | `scripts/dedup_scraped.py` |
| Stage 3 | `scripts/emit_research_queue.py` |
| Stage 4 | `scripts/ingest_graph_queue.py` |

## 関連コマンド

- `/save-to-research-graph` — 既存の graph-queue JSON を直接投入
- `/sync-nas` — NAS 設定ファイル同期（scraped/ 本体は同期対象外）
