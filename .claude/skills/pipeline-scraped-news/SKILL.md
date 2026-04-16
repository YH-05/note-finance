---
name: pipeline-scraped-news
description: NAS（/Volumes/personal_folder/scraped）に蓄積された金融ニュース JSON を research-neo4j に投入する手動実行パイプラインスキル。dedup → graph-queue 生成 → Neo4j 投入の3ステージをオーケストレートする。「スクレイプ済みニュースを投入」「NASのニュースをneo4jに」「pipeline-scraped-news」「finance-news パイプライン手動実行」と言われたら必ずこのスキルを使うこと。
allowed-tools: Read, Bash, Grep, Glob
---

# pipeline-scraped-news スキル

NAS 上の `scraped/` 配下に蓄積されたスクレイピング済み金融ニュース JSON を、research-neo4j (`bolt://localhost:7688`) に投入する手動実行スキル。

> **このスキルは `scripts/pipeline_scraped_to_neo4j.py` のオーケストレーターです。**
> Cypher の直接実行は行いません。`.claude/rules/neo4j-write-rules.md` 参照。

## 処理フロー（3ステージ）

```
Stage 2: dedup_scraped.py          重複排除 → .tmp/deduped-*.json 生成 + processed/ 移動
Stage 3: emit_research_queue.py    finance-news-workflow graph-queue JSON 生成
Stage 4: ingest_graph_queue.py     research-neo4j に投入
```

Stage 1 は事前チェック（NAS マウント確認 / Neo4j 接続確認）。

## 対象ソース（デフォルト全件）

`ars_technica / cnbc / developing_telecoms / federal_reserve / hacker_news / jetro / kabutan / reuters_jp / techcrunch / the_verge / zero_hedge`

`--sources` 引数で絞り込み可能。

## 使用方法

```bash
# 全ソースを投入（標準）
/pipeline-scraped-news

# dry-run（Stage 2 のみ preview、新規件数だけ確認）
/pipeline-scraped-news --dry-run

# 特定ソースのみ
/pipeline-scraped-news --sources cnbc reuters_jp

# NAS パスや Neo4j URI を上書き
/pipeline-scraped-news --scraped-base /path/to/scraped --neo4j-uri bolt://localhost:7688
```

## パラメータ

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| `--scraped-base` | `/Volumes/personal_folder/scraped` | NAS scraped ルート |
| `--sources` | 全11ソース | 対象ソース名（スペース区切り複数可） |
| `--dry-run` | false | Stage 2 のみ preview、Stage 3/4 をスキップ |
| `--skip-precheck` | false | NAS/Neo4j 接続確認をスキップ |
| `--neo4j-uri` | `bolt://localhost:7688` | research-neo4j Bolt URI |
| `--log-level` | INFO | DEBUG/INFO/WARNING/ERROR |

環境変数 `NAS_SCRAPED_BASE` / `NEO4J_RESEARCH_URI` でデフォルト上書き可。

## 実行手順

### ステップ 1: 事前確認（ユーザー向け）

投入対象の件数を把握するため、最初に dry-run を推奨:

```bash
uv run python scripts/pipeline_scraped_to_neo4j.py --dry-run
```

出力から新規件数・対象ソース・スキップ件数を読み取りユーザーに報告。

### ステップ 2: 本実行

```bash
uv run python scripts/pipeline_scraped_to_neo4j.py
```

CLI 内で以下を自動実行:

1. **Stage 1 (pre-check)**: NAS マウント確認 + Neo4j 接続確認（Bolt ポートへ TCP 接続）
2. **Stage 2 (dedup)**: `.tmp/deduped-all-{ts}-{hash}.json` 出力 + 処理済みファイルを `{source}/processed/{date}/` に移動
3. **Stage 3 (emit)**: `.tmp/graph-queue/finance-news-workflow/gq-{ts}-{hash}.json` 出力
4. **Stage 4 (ingest)**: `src/data_pipeline/neo4j_loader.py` 経由で Neo4j に投入（MERGE ベースで冪等）

Stage 2 で新規 0 件なら Stage 3/4 をスキップして正常終了。

### ステップ 3: 投入結果の確認

投入後、以下で直近 10 分の追加ノード数を確認してユーザーに報告:

```bash
uv run python -c "
from datetime import datetime, timedelta, timezone
from neo4j import GraphDatabase
driver = GraphDatabase.driver('bolt://localhost:7688', auth=None)
with driver.session() as s:
    r = s.run(
        'MATCH (n) WHERE n.created_at >= datetime(\$t) '
        'RETURN labels(n)[0] AS l, count(n) AS c ORDER BY c DESC',
        t=(datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(),
    )
    for rec in r: print(rec['l'], rec['c'])
driver.close()
"
```

## エラーハンドリング

| 失敗条件 | 終了コード | 対処 |
|---------|-----------|------|
| NAS 未マウント | 2 | `/Volumes/personal_folder` をマウントして再実行 |
| Neo4j 未起動 | 2 | research-neo4j (7688) を起動、または `--dry-run` で先に確認 |
| Stage 2 失敗 | 1 | dedup_scraped のログを確認 |
| Stage 3 失敗 | 1 | emit_research_queue のログを確認 |
| Stage 4 失敗 | 1 | ingest_graph_queue のログを確認（graph-queue JSON は残るため再試行可） |

`--dry-run` 時は Neo4j 接続チェックをスキップする。

## 前提条件

- `/Volumes/personal_folder/scraped/` が mount されていること
- research-neo4j (bolt://localhost:7688) が起動していること
- `scripts/dedup_scraped.py` / `scripts/emit_research_queue.py` / `scripts/ingest_graph_queue.py` が存在すること

## 関連ファイル

| ファイル | 役割 |
|---------|------|
| `scripts/pipeline_scraped_to_neo4j.py` | 3ステージオーケストレーター本体 |
| `scripts/dedup_scraped.py` | Stage 2: 重複排除 + processed/ 移動 |
| `scripts/emit_research_queue.py` | Stage 3: graph-queue JSON 生成 |
| `scripts/ingest_graph_queue.py` | Stage 4: Neo4j 投入 |
| `src/data_pipeline/neo4j_loader.py` | Stage 4 内部で呼ばれる loader |
| `.claude/rules/neo4j-write-rules.md` | Cypher 直書き禁止ルール |

## 関連コマンド・スキル

- `/save-to-research-graph` — 既存の graph-queue JSON を直接投入する下位スキル
- `/sync-nas` — NAS 同期（scraped/ データは同期対象外、設定ファイルのみ）
