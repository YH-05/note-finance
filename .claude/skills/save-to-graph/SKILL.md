---
name: save-to-graph
description: graph-queue JSON を読み込み、Neo4j にノードとリレーションを MERGE ベースで冪等投入するスキル。4フェーズ構成（キュー検出 → ノード投入 → リレーション投入 → 完了処理）。
allowed-tools: Read, Bash, Grep, Glob
---

# save-to-graph スキル

graph-queue JSON ファイルを読み込み、Neo4j にナレッジグラフデータを投入するスキル。
MERGE ベースの Cypher クエリにより冪等性を保証する。

## アーキテクチャ

```
/save-to-graph (このスキル = オーケストレーター)
  |
  +-- Phase 1: キュー検出・検証（接続確認 + 未処理ファイル検出）
  |     +-- Neo4j 接続確認（cypher-shell）
  |     +-- .tmp/graph-queue/ 配下の未処理 JSON を検出
  |     +-- --source / --file によるフィルタリング
  |     +-- JSON スキーマ検証（schema_version, 必須キー）
  |
  +-- Phase 2: ノード投入（MERGE）
  |     +-- Topic ノード MERGE
  |     +-- Entity ノード MERGE
  |     +-- Source ノード MERGE
  |     +-- Claim ノード MERGE
  |
  +-- Phase 3: リレーション投入（MERGE）
  |     +-- TAGGED リレーション MERGE（Source -> Topic）
  |     +-- MAKES_CLAIM リレーション MERGE（Source -> Claim）
  |     +-- ABOUT リレーション MERGE（Claim -> Entity）
  |
  +-- Phase 4: 完了処理
        +-- 処理済みファイルの削除 or 移動（--keep で保持）
        +-- 統計サマリー出力
```

## 使用方法

```bash
# 標準実行（.tmp/graph-queue/ 配下の全未処理 JSON を投入）
/save-to-graph

# 特定コマンドソースのみ
/save-to-graph --source finance-news-workflow

# 特定ファイルのみ
/save-to-graph --file .tmp/graph-queue/finance-news-workflow/gq-20260307120000-a1b2.json

# ドライラン（実際には投入しない）
/save-to-graph --dry-run

# 処理済みファイルを削除せず保持
/save-to-graph --keep
```

## パラメータ一覧

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| --source | all | 対象コマンドソース（finance-news-workflow, ai-research-collect 等） |
| --dry-run | false | Cypher クエリを表示するが実行しない |
| --file | - | 特定の graph-queue JSON ファイルを指定（--source と排他） |
| --keep | false | 処理済みファイルを削除せず保持する |

## 前提条件

1. **Neo4j が起動していること**
   ```bash
   # Docker での起動例（パスワードは環境変数で設定すること）
   docker run -d --name neo4j \
     -p 127.0.0.1:7474:7474 -p 127.0.0.1:7687:7687 \
     -e NEO4J_AUTH=neo4j/${NEO4J_PASSWORD:?NEO4J_PASSWORD is required} \
     neo4j:5-community
   ```

2. **cypher-shell が使用可能であること**
   ```bash
   cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" "RETURN 1"
   ```

3. **初回セットアップが完了していること**
   - 詳細は `guide.md` の「初回セットアップ」セクションを参照
   - UNIQUE 制約（7つ）+ インデックス（4つ）の作成が必要

4. **graph-queue JSON が存在すること**
   - `scripts/emit_graph_queue.py` で生成される
   - 出力先: `.tmp/graph-queue/{command_name}/gq-{timestamp}-{hash4}.json`

## Phase 1: キュー検出・検証

### ステップ 1.1: Neo4j 接続確認

```bash
# 環境変数から接続情報を取得（デフォルト値あり）
NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:?NEO4J_PASSWORD is required}"

# 接続テスト
cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -a "$NEO4J_URI" \
  "RETURN 'connection_ok' AS status"
```

**エラー時**: 接続失敗メッセージを表示して処理中断。

### ステップ 1.2: 未処理ファイル検出

```bash
# --source 指定時: 特定コマンドのディレクトリのみ
ls .tmp/graph-queue/${SOURCE}/*.json

# --file 指定時: 指定ファイルのみ
ls ${FILE}

# 指定なし: 全コマンドディレクトリを走査
find .tmp/graph-queue/ -name "*.json" -type f
```

### ステップ 1.3: JSON スキーマ検証

各 JSON ファイルに対して以下を検証:

```python
required_keys = {
    "schema_version",  # "1.0"
    "queue_id",        # "gq-{timestamp}-{hash4}"
    "created_at",      # ISO 8601 datetime
    "command_source",  # コマンド名
    "sources",         # Source ノードデータ配列
    "topics",          # Topic ノードデータ配列
    "claims",          # Claim ノードデータ配列
    "entities",        # Entity ノードデータ配列
    "relations",       # リレーションデータ
}
```

**検証失敗時**: ファイル名とエラー内容を警告表示し、スキップして次のファイルへ。

## Phase 2: ノード投入（MERGE）

投入順序は依存関係に基づく: **Topic -> Entity -> Source -> Claim**

### ステップ 2.1: Topic ノード MERGE

```cypher
MERGE (t:Topic {topic_id: $topic_id})
SET t.name = $name,
    t.category = $category,
    t.topic_key = $name + '::' + $category
```

### ステップ 2.2: Entity ノード MERGE

```cypher
MERGE (e:Entity {entity_id: $entity_id})
SET e.name = $name,
    e.entity_type = $entity_type,
    e.entity_key = $name + '::' + $entity_type
```

### ステップ 2.3: Source ノード MERGE

```cypher
MERGE (s:Source {source_id: $source_id})
SET s.url = $url,
    s.title = $title,
    s.source_type = $source_type,
    s.collected_at = datetime($collected_at),
    s.published_at = CASE WHEN $published_at IS NOT NULL AND $published_at <> ''
                     THEN datetime($published_at) ELSE null END,
    s.category = $category,
    s.command_source = $command_source
```

### ステップ 2.4: Claim ノード MERGE

```cypher
MERGE (c:Claim {claim_id: $claim_id})
SET c.content = $content,
    c.claim_type = $claim_type,
    c.confidence = $confidence
```

### ドライランモード

`--dry-run` 指定時は、生成される Cypher クエリを標準出力に表示するが実行しない:

```
[DRY-RUN] MERGE (t:Topic {topic_id: "abc-123"})
          SET t.name = "S&P 500", t.category = "stock", t.topic_key = "S&P 500::stock"
[DRY-RUN] MERGE (s:Source {source_id: "def-456"})
          SET s.url = "https://...", s.title = "..."
```

## Phase 3: リレーション投入（MERGE）

### ステップ 3.1: TAGGED リレーション

graph-queue JSON の `relations.tagged` 配列、または Source と Topic の紐付けから生成。

```cypher
MATCH (s:Source {source_id: $source_id})
MATCH (t:Topic {topic_id: $topic_id})
MERGE (s)-[:TAGGED]->(t)
```

### ステップ 3.2: MAKES_CLAIM リレーション

Claim の `source_id` フィールドから Source との紐付けを生成。

```cypher
MATCH (s:Source {source_id: $source_id})
MATCH (c:Claim {claim_id: $claim_id})
MERGE (s)-[:MAKES_CLAIM]->(c)
```

### ステップ 3.3: ABOUT リレーション

Claim と Entity の紐付けを生成。

```cypher
MATCH (c:Claim {claim_id: $claim_id})
MATCH (e:Entity {entity_id: $entity_id})
MERGE (c)-[:ABOUT]->(e)
```

## Phase 4: 完了処理

### ステップ 4.1: 処理済みファイルの処理

| モード | 動作 |
|--------|------|
| デフォルト | 処理済み JSON ファイルを削除 |
| `--keep` | 処理済みファイルを `.tmp/graph-queue/.processed/` に移動 |

### ステップ 4.2: 統計サマリー出力

```markdown
## save-to-graph 完了

### 全体統計

| 項目 | 件数 |
|------|------|
| 処理ファイル数 | {file_count} |
| 投入 Source ノード | {source_count} |
| 投入 Topic ノード | {topic_count} |
| 投入 Entity ノード | {entity_count} |
| 投入 Claim ノード | {claim_count} |
| 投入 TAGGED リレーション | {tagged_count} |
| 投入 MAKES_CLAIM リレーション | {makes_claim_count} |
| 投入 ABOUT リレーション | {about_count} |
| スキップ（検証エラー） | {skipped_count} |

### ファイル別統計

| ファイル | コマンドソース | Source | Topic | Entity | Claim | ステータス |
|----------|--------------|--------|-------|--------|-------|-----------|
| gq-20260307...-a1b2.json | finance-news-workflow | 5 | 0 | 0 | 5 | OK |
| gq-20260307...-c3d4.json | ai-research-collect | 3 | 0 | 3 | 0 | OK |

### 実行情報

- **実行モード**: {mode} (standard / dry-run)
- **実行時刻**: {timestamp}
- **Neo4j URI**: {neo4j_uri}
- **ファイル処理**: {file_action} (deleted / moved to .processed / kept)
```

## 冪等性の保証

このスキルの全ての Cypher クエリは `MERGE` ベースであり、冪等性が保証されます:

1. **ノード投入**: `MERGE` はノードが存在すれば更新、存在しなければ作成
2. **リレーション投入**: `MERGE` はリレーションが存在すれば何もしない、存在しなければ作成
3. **ID の決定論性**: 全 ID は入力データから決定論的に生成される（UUID5 / SHA-256）

同じ graph-queue JSON ファイルを複数回投入しても、グラフの状態は変わりません。

## エラーハンドリング

| エラー | 対処 |
|--------|------|
| E001: Neo4j 接続失敗 | 接続情報を確認。`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` 環境変数を設定 |
| E002: graph-queue ディレクトリ未検出 | `scripts/emit_graph_queue.py` を先に実行して JSON を生成 |
| E003: JSON スキーマ検証エラー | ファイルの `schema_version` と必須キーを確認。`emit_graph_queue.py` を再実行 |
| E004: Cypher 実行エラー | Neo4j のログを確認。制約・インデックスが未作成の場合は初回セットアップを実行 |
| E005: ファイル削除/移動エラー | ファイルの権限を確認 |

## 環境変数

| 変数名 | デフォルト | 説明 |
|--------|-----------|------|
| NEO4J_URI | bolt://localhost:7687 | Neo4j Bolt プロトコル URI |
| NEO4J_USER | neo4j | Neo4j ユーザー名 |
| NEO4J_PASSWORD | (必須、デフォルトなし) | Neo4j パスワード |

## 関連リソース

| リソース | パス |
|---------|------|
| 詳細ガイド | `.claude/skills/save-to-graph/guide.md` |
| スラッシュコマンド | `.claude/commands/save-to-graph.md` |
| graph-queue 生成スクリプト | `scripts/emit_graph_queue.py` |
| ナレッジグラフスキーマ | `data/config/knowledge-graph-schema.yaml` |
| graph-queue 出力先 | `.tmp/graph-queue/{command_name}/` |

## 対応コマンドソース

| コマンドソース | 説明 | 主な生成ノード |
|--------------|------|--------------|
| finance-news-workflow | 金融ニュース収集 | Source, Claim |
| ai-research-collect | AI投資リサーチ | Entity, Source |
| generate-market-report | マーケットレポート | Source, Claim |
| asset-management | 資産形成 | Topic, Source |
| reddit-finance-topics | Reddit トピック | Topic, Source |
| finance-full | 記事執筆 | Source, Claim |

## 変更履歴

### 2026-03-07: 初版作成（Issue #47）

- 4フェーズ構成（キュー検出 → ノード投入 → リレーション投入 → 完了処理）
- MERGE ベース冪等投入
- --source, --dry-run, --file, --keep パラメータ対応
