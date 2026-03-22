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

## pdf-to-knowledge との Source 統合に関する注意事項

academic-fetch は **Source + Author メタデータのみ**を Neo4j に投入する（AUTHORED_BY リレーション）。
同一論文に対して `/pdf-to-knowledge` を実行すると、**pdf-extraction 側が別の Source ノードを作成**し、Fact・Claim・Chunk をそちらに紐づける。

この結果、Author と Fact/Claim が別々の Source に紐づき、Author<->Fact の接続が断絶する。

### 推奨ワークフロー

**順序: pdf-to-knowledge を先に実行し、その後 academic-fetch を実行する。**

1. `/pdf-to-knowledge` で PDF を処理 -- Source + Fact + Claim + Chunk が作成される
2. `/academic-fetch --backfill` で著者情報を取得 -- graph-queue 生成時に既存 Source の `arxiv_id` を検出し MERGE される

### 逆順で実行した場合の統合手順

academic-fetch を先に実行してしまい、pdf-to-knowledge が別の Source を作成した場合は、以下の Cypher で統合する:

```cypher
// 1. 重複を検出
MATCH (s1:Source), (s2:Source)
WHERE s1.arxiv_id IS NOT NULL AND s1.arxiv_id = s2.arxiv_id
AND elementId(s1) <> elementId(s2)
RETURN s1.title, s1.source_id, s1.command_source, s2.source_id, s2.command_source

// 2. arxiv_id でマッチしない場合はタイトルでチェック
MATCH (s1:Source {command_source: 'academic-fetch'}), (s2:Source {command_source: 'pdf-extraction'})
WHERE toLower(trim(s1.title)) = toLower(trim(s2.title))
RETURN s1.title, s1.source_id, s2.source_id

// 3. AUTHORED_BY を academic-fetch Source から pdf-extraction Source に移行
MATCH (s_acad:Source {command_source: 'academic-fetch'})
WHERE s_acad.arxiv_id IS NOT NULL
MATCH (s_pdf:Source {command_source: 'pdf-extraction'})
WHERE (s_pdf.arxiv_id = s_acad.arxiv_id)
   OR (s_pdf.arxiv_id IS NULL AND toLower(trim(s_pdf.title)) = toLower(trim(s_acad.title)))
AND elementId(s_acad) <> elementId(s_pdf)
SET s_pdf.arxiv_id = coalesce(s_pdf.arxiv_id, s_acad.arxiv_id)
WITH s_acad, s_pdf
MATCH (s_acad)-[:AUTHORED_BY]->(a:Author)
MERGE (s_pdf)-[:AUTHORED_BY]->(a)
WITH s_acad
DETACH DELETE s_acad
```

### 背景

2026-03-22 に以下の重複が検出・統合された:

| 論文 | academic-fetch Source | pdf-extraction Source | 統合内容 |
|------|----------------------|----------------------|----------|
| Topological Community Detection (2310.05767) | 7d76c43f (削除済) | f87901ae | Author 2名を移行 |
| Why TDA Detects Financial Bubbles (2304.06877) | 3dedc801 (削除済) | ad67fae4 | Author 4名を移行 |

## 関連コマンド

- **graph-queue 生成**: `/emit-graph-queue --command academic-fetch`
- **Neo4j 投入**: `/save-to-graph`
- **PDF 知識抽出**: `/pdf-to-knowledge`

## 関連リソース

| リソース | パス |
|---------|------|
| academic パッケージ | `src/academic/` |
| 移植レポート | `academic-package-migration-report.md` |
| graph-queue 出力先 | `.tmp/graph-queue/academic-fetch/` |
| save-to-graph ガイド | `.claude/skills/save-to-graph/guide.md` |
