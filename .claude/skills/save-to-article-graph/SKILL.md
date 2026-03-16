---
name: save-to-article-graph
description: |
  emit_graph_queue.py と save-to-graph を連結するオーケストレータースキル。
  wealth-scrape / topic-discovery の出力を article-neo4j（bolt://localhost:7689）に投入する。
  2フェーズ構成（graph-queue 生成 → Neo4j 投入）。
allowed-tools: Read, Bash, Glob, Grep
---

# save-to-article-graph スキル

`emit_graph_queue.py` による graph-queue JSON 生成と、`save-to-graph` スキルによる Neo4j 投入を一括実行するオーケストレータースキル。
article-neo4j（`bolt://localhost:7689`）を対象とし、wealth-scrape と topic-discovery の 2 コマンドに対応する。

## アーキテクチャ

```
/save-to-article-graph (このスキル = オーケストレーター)
  |
  +-- Phase 1: graph-queue 生成
  |     +-- emit_graph_queue.py --command {command} --input {input}
  |     +-- 出力先: .tmp/graph-queue/{command}/gq-{timestamp}-{hash4}.json
  |
  +-- Phase 2: Neo4j 投入（save-to-graph スキルのロジック）
        +-- NEO4J_URI=bolt://localhost:7689 で article-neo4j に接続
        +-- Phase 1 で生成された graph-queue JSON を投入
        +-- --dry-run / --keep パラメータの伝播
```

## 使用方法

```bash
# wealth-scrape: ディレクトリ入力（バックフィル）
/save-to-article-graph --command wealth-scrape --input data/scraped/wealth/

# wealth-scrape: JSONファイル入力（インクリメンタル）
/save-to-article-graph --command wealth-scrape --input .tmp/wealth-scrape-20260316-120000.json

# topic-discovery: セッションJSON入力
/save-to-article-graph --command topic-discovery --input .tmp/topic-suggestions/2026-03-16_1430.json

# ドライラン（graph-queue 生成のみ、Neo4j 投入は Cypher 表示のみ）
/save-to-article-graph --command wealth-scrape --input data/scraped/wealth/ --dry-run

# 処理済みファイルを保持
/save-to-article-graph --command topic-discovery --input .tmp/topic-suggestions/2026-03-16_1430.json --keep
```

## パラメータ一覧

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| --command | Yes | - | 対象コマンド: `wealth-scrape` \| `topic-discovery` |
| --input | Yes | - | 入力パス（ファイル or ディレクトリ） |
| --dry-run | No | false | Phase 2 の Cypher クエリを表示するが実行しない |
| --keep | No | false | Phase 2 完了後、graph-queue ファイルを削除せず保持する |

## 前提条件

1. **uv**: パッケージマネージャ。`uv run` で `emit_graph_queue.py` を実行
2. **article-neo4j が起動中であること**（Phase 2 のみ）
   ```bash
   docker inspect article-neo4j --format='{{.State.Status}}' 2>/dev/null
   # → "running" であること
   ```
3. **入力ファイル/ディレクトリが存在すること**
4. **pdf_pipeline パッケージ**: `emit_graph_queue.py` が依存する ID 生成ユーティリティ

## 対応コマンド

| コマンド | 入力形式 | 説明 | 生成ノード |
|---------|---------|------|-----------|
| wealth-scrape | ディレクトリ or JSON | 資産形成ブログスクレイピング結果 | Source, Topic, Entity, Claim, Chunk, Fact |
| topic-discovery | JSON | トピック提案セッション | Source, Topic, Claim, Entity, Fact |

### wealth-scrape の入力パターン

| パターン | 入力パス例 | モード |
|---------|-----------|--------|
| バックフィル | `data/scraped/wealth/` | ディレクトリ走査。ドメイン別に複数 graph-queue ファイルを生成 |
| インクリメンタル | `.tmp/wealth-scrape-{YYYYMMDD}-{HHMMSS}.json` | 単一 JSON 入力 |

### topic-discovery の入力パターン

| パターン | 入力パス例 |
|---------|-----------|
| セッションJSON | `.tmp/topic-suggestions/{YYYY-MM-DD}_{HHMM}.json` |

---

## Phase 1: graph-queue 生成

`emit_graph_queue.py` を実行して graph-queue JSON を生成する。

### 実行コマンド

```bash
uv run python scripts/emit_graph_queue.py \
    --command {command} \
    --input {input}
```

### 入力検証

実行前に以下を検証する:

1. `--command` が `wealth-scrape` または `topic-discovery` であること
2. `--input` が存在するファイルまたはディレクトリであること
3. `wealth-scrape` + ディレクトリの場合、配下に `*.md` ファイルが存在すること

### 出力

- `.tmp/graph-queue/{command}/gq-{timestamp}-{hash4}.json`
- wealth-scrape バックフィルモードでは、ドメインごとに複数ファイルが生成される

### 変数保持（Phase 2 への引き渡し）

| 変数 | 説明 | 取得方法 |
|------|------|---------|
| `GQ_FILES` | 生成された graph-queue JSON のパス一覧 | `.tmp/graph-queue/{command}/` 配下の最新ファイルを取得 |

### graph-queue ファイルの検出

```bash
# emit_graph_queue.py 実行直後に生成ファイルを取得
GQ_FILES=$(ls -t .tmp/graph-queue/{command}/*.json 2>/dev/null | head -20)
```

### エラー時の対処

| エラー | 対処 |
|--------|------|
| --command が不正 | `wealth-scrape` または `topic-discovery` を指定するよう案内 |
| 入力パスが存在しない | パスを確認するよう案内 |
| emit_graph_queue.py 実行エラー | スクリプトのエラーログを表示して処理中断 |

---

## Phase 2: Neo4j 投入

save-to-graph スキルのロジックを使用して、graph-queue JSON を article-neo4j に投入する。

**重要**: `NEO4J_URI` を `bolt://localhost:7689` に設定して article-neo4j に接続する。

### 前提条件チェック

```bash
# article-neo4j コンテナの起動確認
CONTAINER_STATUS=$(docker inspect article-neo4j --format='{{.State.Status}}' 2>/dev/null)
```

- `running` → 投入処理を続行
- それ以外 → 警告を出力し、Phase 2 をスキップ（Phase 1 の成果物は保持）

### 環境変数の設定

```bash
export NEO4J_URI="bolt://localhost:7689"
export NEO4J_USER="${NEO4J_USER:-neo4j}"
export NEO4J_PASSWORD="${NEO4J_PASSWORD:?NEO4J_PASSWORD is required}"
```

### 実行方式

save-to-graph スキル（`.claude/skills/save-to-graph/SKILL.md`）の処理フローに従い、以下を実行:

1. **Neo4j 接続確認**
   ```bash
   docker exec -i article-neo4j cypher-shell \
     -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
     "RETURN 'connection_ok' AS status"
   ```

2. **graph-queue JSON の読み込みと検証**
   - Phase 1 で生成されたファイルを Read ツールで読み込む
   - `schema_version`, 必須キーを検証

3. **ノード投入（MERGE）**: save-to-graph スキルの Phase 2 に準拠
4. **リレーション投入（MERGE）**: save-to-graph スキルの Phase 3a に準拠
5. **クロスファイルリレーション**: save-to-graph スキルの Phase 3b に準拠
6. **完了処理**: graph-queue ファイルの削除 or 保持（`--keep` 指定時）

### ドライランモード

`--dry-run` 指定時:
- Phase 1 は通常通り実行（graph-queue JSON を生成）
- Phase 2 は Cypher クエリを表示するが実行しない

### パラメータ連携

| 本スキルパラメータ | save-to-graph 相当 |
|-------------------|-------------------|
| `--dry-run` | `--dry-run` |
| `--keep` | `--keep` |

### エラー時の対処

Phase 2 で失敗した場合、**graph-queue ファイルは残す**。手動での再実行を案内する。

```
Phase 2（Neo4j 投入）が失敗しました。
graph-queue ファイルは保持されています: {GQ_FILES}

article-neo4j が利用可能になったら、以下のコマンドで手動投入できます:
  NEO4J_URI=bolt://localhost:7689 /save-to-graph --file {GQ_FILE}
```

---

## エラーハンドリング（グレースフルデグラデーション）

| Phase | エラー | 対処 | 成果物の状態 |
|-------|--------|------|-------------|
| Phase 1 | emit_graph_queue.py 失敗 | **全体中断**（エラーサマリー出力） | なし |
| Phase 2 | article-neo4j 未起動 | Phase 2 スキップ、手動投入を案内 | graph-queue JSON は残す |
| Phase 2 | Cypher 実行エラー | 手動投入を案内 | graph-queue JSON は残す |

### デグラデーション判定フロー

```
Phase 1 実行
  |
  +-- 失敗 → 全体中断（エラーサマリー出力）
  |
  +-- 成功 → article-neo4j 起動確認
                |
                +-- 未起動 → Phase 2 スキップ（部分サマリー出力）
                |
                +-- 起動中 → Phase 2 実行
                              |
                              +-- 失敗 → 手動投入案内（部分サマリー出力）
                              |
                              +-- 成功 → 完了サマリー出力
```

---

## 完了サマリー

### 全フェーズ成功時

```markdown
## save-to-article-graph 完了

| 項目 | 値 |
|------|-----|
| コマンド | {command} |
| 入力 | {input} |
| graph-queue ファイル数 | {gq_count} |
| Neo4j URI | bolt://localhost:7689 |
| 投入ノード数 | {node_count} |
| 投入リレーション数 | {relation_count} |
| ファイル処理 | {deleted / kept} |

### graph-queue ファイル

- {GQ_FILE_1}
- {GQ_FILE_2} (wealth-scrape バックフィル時)
```

### 部分成功時（article-neo4j 未起動）

```markdown
## save-to-article-graph 部分完了

| 項目 | 値 |
|------|-----|
| コマンド | {command} |
| 入力 | {input} |
| graph-queue ファイル数 | {gq_count} |
| Phase 1 | OK |
| Phase 2 | SKIP (article-neo4j 未起動) |

### 手動投入コマンド

article-neo4j 起動後に以下を実行:

```bash
NEO4J_URI=bolt://localhost:7689 /save-to-graph --source {command}
```
```

---

## 環境変数

| 変数名 | デフォルト | 説明 |
|--------|-----------|------|
| NEO4J_URI | bolt://localhost:7689 | article-neo4j Bolt URI（本スキルが自動設定） |
| NEO4J_USER | neo4j | Neo4j ユーザー名 |
| NEO4J_PASSWORD | (必須・環境変数で設定) | Neo4j パスワード |

---

## 関連リソース

| リソース | パス |
|---------|------|
| save-to-graph スキル | `.claude/skills/save-to-graph/SKILL.md` |
| save-to-graph 詳細ガイド | `.claude/skills/save-to-graph/guide.md` |
| graph-queue 生成スクリプト | `scripts/emit_graph_queue.py` |
| topic-discovery スキル | `.claude/skills/topic-discovery/SKILL.md` |
| scrape-finance-blog スキル | `.claude/skills/scrape-finance-blog/SKILL.md` |
| ナレッジグラフスキーマ | `data/config/knowledge-graph-schema.yaml` |
| graph-queue 出力先 | `.tmp/graph-queue/{command}/` |

---

## 変更履歴

### 2026-03-16: 初版作成（Issue #133）

- 2 フェーズ構成オーケストレータースキル新規作成
- Phase 1: emit_graph_queue.py による graph-queue JSON 生成
- Phase 2: save-to-graph スキルのロジックで article-neo4j に投入
- wealth-scrape / topic-discovery の 2 コマンド対応
- --dry-run / --keep パラメータ対応
- グレースフルデグラデーション対応（article-neo4j 未起動時は Phase 2 スキップ）
