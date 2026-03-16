---
description: graph-queue JSON を生成します（各種ワークフロー出力 → Neo4j 投入用 JSON 変換）
argument-hint: --command <command> --input <path> [--cleanup]
---

# /emit-graph-queue - graph-queue JSON 生成

各種ワークフローの出力データを graph-queue JSON に変換し、`.tmp/graph-queue/` に出力します。
生成された JSON は `/save-to-graph` で Neo4j に投入できます。

## 引数の解析

ユーザーの入力から以下のパラメータを判定してください:

| パラメータ | 必須 | 説明 |
|-----------|------|------|
| `--command` | ✅ | 対象コマンド（下表参照） |
| `--input` | ✅ | 入力ファイル/ディレクトリパス |
| `--cleanup` | - | 7日超の古いキューファイルを削除 |

### 対応コマンド一覧

| コマンド名 | 入力形式 | 入力パス例 | 主な生成ノード |
|-----------|---------|-----------|--------------|
| `finance-news-workflow` | JSON | `.tmp/news-batches/index.json` | Source, Claim |
| `ai-research-collect` | JSON | `.tmp/ai-research-*.json` | Entity, Source |
| `generate-market-report` | JSON | `.tmp/market-report-*.json` | Source, Claim |
| `asset-management` | JSON | `.tmp/asset-mgmt-*.json` | Topic, Source |
| `reddit-finance-topics` | JSON | `.tmp/reddit-topics-*.json` | Topic, Source |
| `finance-full` | JSON | `.tmp/finance-full-*.json` | Source, Claim |
| `pdf-extraction` | JSON | `.tmp/pdf-extraction-*.json` | 全9ノード |
| `wealth-backfill` | **ディレクトリ** | `data/scraped/wealth/` | Source, Topic, Chunk |

## 実行手順

### Step 1: 引数が省略された場合の対話的確認

`--command` または `--input` が未指定の場合、ユーザーに確認してください。

### Step 2: 入力パスの存在確認

```bash
# JSON入力の場合
test -f "${INPUT_PATH}" && echo "OK" || echo "ERROR: File not found"

# wealth-backfill（ディレクトリ入力）の場合
test -d "${INPUT_PATH}" && echo "OK" || echo "ERROR: Directory not found"
```

### Step 3: emit_graph_queue.py の実行

```bash
uv run python scripts/emit_graph_queue.py \
  --command "${COMMAND}" \
  --input "${INPUT_PATH}"
```

`--cleanup` が指定された場合は末尾に `--cleanup` を追加。

### Step 4: 結果報告

```markdown
## graph-queue 生成完了

| 項目 | 値 |
|------|-----|
| コマンド | ${COMMAND} |
| 入力 | ${INPUT_PATH} |
| 出力 | ${OUTPUT_FILE} |

次のステップ: `/save-to-graph` で Neo4j に投入
```

## 使用例

```bash
# wealth-backfill: スクレイプ済み記事からgraph-queue生成
/emit-graph-queue --command wealth-backfill --input data/scraped/wealth/

# finance-news-workflow: ニュースバッチから生成
/emit-graph-queue --command finance-news-workflow --input .tmp/news-batches/index.json

# asset-management: セッションJSONから生成
/emit-graph-queue --command asset-management --input .tmp/asset-mgmt-20260315-120000.json

# 古いキューファイルを削除しつつ生成
/emit-graph-queue --command wealth-backfill --input data/scraped/wealth/ --cleanup
```

## 関連コマンド

- **Neo4j 投入**: `/save-to-graph`（生成済み graph-queue JSON → Neo4j）
- **ウェルスブログ収集**: `/scrape-finance-blog`（backfill 記事を収集）
- **ニュース収集**: `/collect-finance-news`
- **マーケットレポート**: `/generate-market-report`

## 関連リソース

| リソース | パス |
|---------|------|
| 生成スクリプト | `scripts/emit_graph_queue.py` |
| graph-queue 出力先 | `.tmp/graph-queue/{command}/` |
| save-to-graph スキル | `.claude/skills/save-to-graph/SKILL.md` |
| KG スキーマ定義 | `data/config/knowledge-graph-schema.yaml` |
