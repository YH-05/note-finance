---
description: arXiv 論文メタデータを取得し、graph-queue JSON を生成します
argument-hint: --arxiv-id <id> | --arxiv-ids <id1> <id2> ... | --backfill --ids-file <path>
---

# /academic-fetch - 論文メタデータ取得 + graph-queue 生成

alphaxiv MCP で調査した論文の著者・引用文献情報を arXiv / Semantic Scholar API から自動取得し、
graph-queue JSON を生成します。生成された JSON は `/save-to-graph` で Neo4j に投入できます。

## 引数の解析

ユーザーの入力から以下のモードを判定してください:

### モード 1: 単一/複数論文の取得（fetch）

| パラメータ | 必須 | 説明 |
|-----------|------|------|
| `--arxiv-id` | ✅（択一） | 単一の arXiv ID |
| `--arxiv-ids` | ✅（択一） | 複数の arXiv ID（スペース区切り） |

### モード 2: バッチバックフィル（backfill）

| パラメータ | 必須 | 説明 |
|-----------|------|------|
| `--backfill` | ✅ | バックフィルモード |
| `--ids-file` | ✅ | arXiv ID リストファイル（1行1ID） |
| `--existing-ids` | - | 既存 Neo4j Source ID（CITES フィルタ用） |

## 実行手順

### Step 1: モード判定

引数から fetch / backfill モードを判定する。

### Step 2: fetch モード

```bash
uv run python -m academic fetch --arxiv-id ${ARXIV_ID}
# or
uv run python -m academic fetch --arxiv-ids ${ARXIV_IDS}
```

出力: `.tmp/academic/papers.json`

### Step 3: backfill モード（graph-queue 生成）

```bash
uv run python -m academic backfill --ids-file ${IDS_FILE}
```

出力: `.tmp/graph-queue/academic-fetch/gq-{queue_id}.json`

### Step 4: 結果報告

```markdown
## academic-fetch 完了

| 項目 | 値 |
|------|-----|
| モード | fetch / backfill |
| 論文数 | ${PAPER_COUNT} |
| 出力 | ${OUTPUT_PATH} |

次のステップ:
- fetch → 論文データを確認: `cat .tmp/academic/papers.json | python -m json.tool`
- backfill → Neo4j 投入: `/save-to-graph`
```

### Step 5: backfill 後の graph-queue → Neo4j 投入（オプション）

ユーザーが希望する場合、続けて `/save-to-graph` を実行する。

## 使用例

```bash
# 単一論文の取得
/academic-fetch --arxiv-id 2301.08245

# 複数論文の取得
/academic-fetch --arxiv-ids 2301.08245 2303.09406

# バッチバックフィル（graph-queue 生成 → Neo4j 投入）
/academic-fetch --backfill --ids-file data/arxiv-ids.txt

# emit_graph_queue.py 経由でも生成可能
/emit-graph-queue --command academic-fetch --input .tmp/academic/papers.json
```

## 関連コマンド

- **graph-queue 生成**: `/emit-graph-queue --command academic-fetch`
- **Neo4j 投入**: `/save-to-graph`

## 関連リソース

| リソース | パス |
|---------|------|
| academic パッケージ | `src/academic/` |
| 移植レポート | `academic-package-migration-report.md` |
| graph-queue 出力先 | `.tmp/graph-queue/academic-fetch/` |
| save-to-graph ガイド | `.claude/skills/save-to-graph/guide.md` |
