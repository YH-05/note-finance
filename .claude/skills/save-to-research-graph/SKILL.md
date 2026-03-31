---
name: save-to-research-graph
description: graph-queue JSON を読み込み、Python CLI 経由で research-neo4j にノードとリレーションを投入するオーケストレータースキル。3ステップ構成（emit → link → load）。
allowed-tools: Read, Bash, Grep, Glob
---

# save-to-research-graph スキル

graph-queue JSON ファイルを受け取り、3つの Python CLI を順番に呼び出して research-neo4j (bolt://localhost:7688) にデータを投入するスキル。

> **このスキルは Python CLI のオーケストレーターです。**
> Cypher の直接実行（`mcp__neo4j-research__research-write_neo4j_cypher`）は行いません。
> `.claude/rules/neo4j-write-rules.md` 参照。

## 処理フロー（3ステップ）

```
① emit_research_queue.py   — 入力 JSON → graph-queue JSON 生成
② entity_linker.py         — entity_key / topic_key 解決（前処理）
③ neo4j_loader.py          — graph-queue JSON → Neo4j 投入
```

> **注意**: クロスファイルリレーション（TAGGED / ABOUT: 既存ノードとの接続）は
> 現スコープ外です。後続タスクで対応予定。

## 使用方法

```bash
# 標準実行（.tmp/research-input/ 配下の JSON を投入）
/save-to-research-graph

# 特定ファイルを指定
/save-to-research-graph --file .tmp/research-input/my-data.json

# ドライラン（投入をスキップして件数確認のみ）
/save-to-research-graph --dry-run

# graph-queue JSON を直接渡す（emit ステップをスキップ）
/save-to-research-graph --queue .tmp/graph-queue/web-research/gq-20260330-abc1.json
```

## パラメータ

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| `--file` | - | 入力 JSON ファイルのパス（--queue と排他） |
| `--queue` | - | graph-queue JSON を直接指定（ステップ①をスキップ） |
| `--command` | web-research | emit_research_queue.py の --command 引数 |
| `--dry-run` | false | 投入せずカウントのみ確認 |
| `--keep` | false | 処理済みファイルを削除せず保持 |

## 実行手順

### ステップ 1: 入力ファイル検出

```bash
# --file 指定時
ls {file}

# 指定なし: デフォルトディレクトリを走査
ls .tmp/research-input/*.json
```

ファイルが見つからない場合はエラーメッセージを表示して終了。

### ステップ 2: graph-queue JSON 生成（--queue 未指定時のみ）

```bash
uv run python scripts/emit_research_queue.py \
  --command {command} \
  --input {input_file}
```

出力先: `.tmp/graph-queue/{command}/gq-{timestamp}-{hash4}.json`
生成されたパスを次のステップに渡す。

### ステップ 3: entity_key 解決

```bash
uv run python scripts/entity_linker.py \
  --input {graph_queue_file} \
  --instance research \
  --ner-fallback
```

出力先: `.tmp/graph-queue/{command}/linked-{timestamp}.json`
entity_linker が失敗した場合は警告を出力し、未リンクの graph-queue JSON をそのまま次ステップに渡す（非ブロッキング）。

### ステップ 4: Neo4j 投入

```bash
uv run python src/data_pipeline/neo4j_loader.py \
  --instance research \
  --input {linked_file}
```

`--dry-run` が指定された場合は `--dry-run` フラグを追加。

> **依存**: `neo4j_loader.py` の CLI インターフェース（`--instance`, `--input`）は
> task-011 で実装予定。未実装の場合は `ingest_to_neo4j()` を直接 Python から呼び出す。

### ステップ 5: 完了確認・ログ出力

投入後に以下を確認してユーザーに表示:

```bash
# 直近の投入件数確認
uv run python -c "
from data_pipeline.neo4j_loader import _get_driver
from datetime import datetime, timedelta, timezone
driver = _get_driver()
with driver.session() as s:
    r = s.run(
        'MATCH (n) WHERE n.created_at >= datetime(\$t) RETURN labels(n)[0] AS l, count(n) AS c ORDER BY c DESC',
        t=(datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    )
    for rec in r: print(rec['l'], rec['c'])
driver.close()
"
```

`--keep` が指定されていない場合、処理済みファイルを `.tmp/graph-queue/.processed/` に移動。

## エラーハンドリング

| ステップ | エラー | 対処 |
|---------|--------|------|
| 1 | ファイルなし | エラー表示して終了 |
| 2 | emit_research_queue.py 失敗 | エラー内容を表示して終了 |
| 3 | entity_linker.py 失敗 | 警告表示・未リンクのまま続行 |
| 4 | neo4j_loader.py 失敗 | エラー内容を表示して終了（ロールバックなし） |

ロールバック不可のため、本番投入前は `--dry-run` で事前確認を推奨。

## 前提条件

- research-neo4j (bolt://localhost:7688) が起動していること
- `scripts/emit_research_queue.py` が存在すること
- `scripts/entity_linker.py` が存在すること（任意：失敗しても続行）
- `src/data_pipeline/neo4j_loader.py` が存在すること

## 関連ファイル

| ファイル | 役割 |
|---------|------|
| `scripts/emit_research_queue.py` | graph-queue JSON 生成 |
| `scripts/entity_linker.py` | entity_key / topic_key 解決 |
| `src/data_pipeline/neo4j_loader.py` | Neo4j 投入 |
| `.claude/rules/neo4j-write-rules.md` | Cypher 直書き禁止ルール |
