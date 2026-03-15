---
name: pdf-to-knowledge
description: PDF -> Markdown -> Knowledge Extraction -> Graph-Queue -> Neo4j 投入を一括実行するワークフロースキル。4 フェーズ構成でグレースフルデグラデーション対応。Neo4j 未起動でも Phase 1-3 は正常完了する。
allowed-tools: Read, Write, Bash, Glob, Grep
---

# pdf-to-knowledge スキル

PDF ファイルからナレッジグラフ投入までを一括実行するワークフロースキル。以下の 4 フェーズを順次実行し、各フェーズの成果物を次のフェーズへ引き渡す。

## アーキテクチャ

```
/pdf-to-knowledge (このスキル = オーケストレーター)
  |
  +-- Phase 1: PDF -> Markdown (convert-pdf スキルのロジック)
  |     +-- Step 1:  PDF パス検証
  |     +-- Step 2:  SHA-256 ハッシュ計算（CLI ヘルパー）
  |     +-- Step 3:  冪等性チェック（CLI ヘルパー）
  |     +-- Step 4:  出力ディレクトリ計算（CLI ヘルパー）
  |     +-- Step 5:  ページ数取得（CLI ヘルパー）
  |     +-- Step 6:  PDF 読込 + Markdown 変換（Read ツール + 30p 分割）
  |     +-- Step 7:  report.md 出力（Write ツール）
  |     +-- Step 8:  chunks.json 生成（CLI ヘルパー）
  |     +-- Step 9:  metadata.json 生成（CLI ヘルパー）
  |     +-- Step 10: 完了記録（CLI ヘルパー）
  |
  +-- Phase 2: Knowledge Extraction
  |     +-- extraction.json 生成（CLI ヘルパー）
  |
  +-- Phase 3: Graph-Queue 生成
  |     +-- emit_graph_queue.py でキュー JSON 出力
  |
  +-- Phase 4: Neo4j 投入 (save-to-graph スキルのロジック)
        +-- キュー検出・検証
        +-- ノード投入（MERGE）
        +-- リレーション投入（MERGE）
        +-- 完了処理
```

## 使用方法

```bash
# 単一 PDF をナレッジグラフに投入
/pdf-to-knowledge /path/to/report.pdf

# 複数 PDF を連続処理
/pdf-to-knowledge /path/to/report1.pdf /path/to/report2.pdf

# 強制再変換（冪等性チェックをスキップ）
/pdf-to-knowledge --force /path/to/report.pdf

# Phase 1-3 のみ実行（Neo4j 投入をスキップ）
/pdf-to-knowledge --skip-neo4j /path/to/report.pdf

# ドライラン（Neo4j 投入の Cypher を表示するが実行しない）
/pdf-to-knowledge --dry-run /path/to/report.pdf
```

## パラメータ一覧

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| pdf_path | (必須) | 変換対象の PDF ファイルパス（複数指定可） |
| --force | false | 冪等性チェックをスキップし強制再変換する |
| --skip-neo4j | false | Phase 4（Neo4j 投入）をスキップする |
| --dry-run | false | Phase 4 の Cypher クエリを表示するが実行しない |
| --keep | false | Phase 4 完了後、graph-queue ファイルを削除せず保持する |

## 前提条件

1. **uv**: パッケージマネージャ。`uv run` で CLI ヘルパーを実行
2. **PyMuPDF (fitz)**: ページ数取得に使用。`pdf_pipeline` の依存関係に含まれている
3. **pdf_pipeline パッケージ**: `src/pdf_pipeline/` が利用可能であること
4. **Neo4j**（Phase 4 のみ）: 起動していること。未起動でも Phase 1-3 は正常完了する

## 出力パス形式

各フェーズの成果物は以下のパスに保存される:

```
{DATA_ROOT}/processed/{mirror_subpath}/{stem}_{hash8}/
├── report.md           # Phase 1: Markdown 変換結果
├── chunks.json         # Phase 1: セクション分割チャンク
├── metadata.json       # Phase 1: 処理メタデータ
└── extraction.json     # Phase 2: 知識抽出結果

.tmp/graph-queue/pdf-extraction/
└── gq-{timestamp}-{hash4}.json  # Phase 3: Graph-Queue JSON
```

---

## Phase 1: PDF -> Markdown

convert-pdf スキルのロジックをそのまま実行する。詳細は `.claude/skills/convert-pdf/SKILL.md` を参照。

### 処理概要

| Step | 処理 | 実行方式 |
|------|------|---------|
| 1 | PDF パス検証 | スキル直接 |
| 2 | SHA-256 ハッシュ計算 | CLI ヘルパー |
| 3 | 冪等性チェック | CLI ヘルパー |
| 4 | 出力ディレクトリ計算 | CLI ヘルパー |
| 5 | ページ数取得 | CLI ヘルパー |
| 6 | PDF 読込 + Markdown 変換 | Read ツール（30p 分割） |
| 7 | report.md 出力 | Write ツール |
| 8 | chunks.json 生成 | CLI ヘルパー |
| 9 | metadata.json 生成 | CLI ヘルパー |
| 10 | 完了記録 | CLI ヘルパー |

### 実行コマンド（主要）

```bash
# Step 2: ハッシュ計算
SHA256=$(uv run python -m pdf_pipeline.cli.helpers compute_hash "{pdf_path}")

# Step 3: 冪等性チェック（--force 時はスキップ）
uv run python -m pdf_pipeline.cli.helpers check_idempotency "{SHA256}" "{DATA_ROOT}/processed/state.json"

# Step 4: 出力ディレクトリ計算
OUTPUT_DIR=$(uv run python -m pdf_pipeline.cli.helpers compute_output_dir "{pdf_path}" "{SHA256}")

# Step 5: ページ数取得
PAGE_COUNT=$(uv run python -m pdf_pipeline.cli.helpers get_page_count "{pdf_path}")

# Step 6: PDF 読込（Read ツール。30p 分割戦略は convert-pdf スキルに準拠）

# Step 7: report.md 出力（Write ツール）
mkdir -p "{OUTPUT_DIR}"

# Step 8: chunks.json 生成
CHUNK_COUNT=$(uv run python -m pdf_pipeline.cli.helpers chunk_and_save "{OUTPUT_DIR}/report.md" "{SHA256}" "{OUTPUT_DIR}")

# Step 9: metadata.json 生成
uv run python -m pdf_pipeline.cli.helpers save_metadata "{OUTPUT_DIR}" "{SHA256}" "{pdf_path}" "{PAGE_COUNT}" "{CHUNK_COUNT}"

# Step 10: 完了記録
uv run python -m pdf_pipeline.cli.helpers record_completed "{SHA256}" "{DATA_ROOT}/processed/state.json" "{pdf_filename}"
```

### 変数保持（後続フェーズへの引き渡し）

Phase 1 完了後、以下の変数を後続フェーズで使用する:

| 変数 | 説明 | 使用先 |
|------|------|--------|
| `SHA256` | PDF の SHA-256 hex digest | Phase 2 |
| `OUTPUT_DIR` | 出力ディレクトリ絶対パス | Phase 2, 3 |
| `CHUNK_COUNT` | 生成されたチャンク数 | サマリー |
| `PAGE_COUNT` | PDF のページ数 | サマリー |

### Step 6: Markdown 変換ルール

convert-pdf スキルの変換ルールに準拠する。詳細は `.claude/skills/convert-pdf/SKILL.md` の「変換ルール」セクションを参照。

要点:

- ATX 見出しで階層構造保持
- テーブルは Markdown テーブル構文に変換
- 数値・通貨は正確に保持（四捨五入・丸め禁止）
- ヘッダー・フッター・ページ番号・免責事項・透かしを除去
- 前置き文・コードフェンス・コメント・要約・翻訳は禁止

### エラー時の対処

Phase 1 で失敗した場合、**全体を中断**する。後続の Phase 2-4 は実行しない。

| エラーコード | 条件 | 対処 |
|-------------|------|------|
| E001 | PDF ファイル不存在 | パスを確認して再実行 |
| E002 | 拡張子が .pdf でない | `.pdf` ファイルを指定 |
| E003 | ファイルサイズ 0 | 正常な PDF を指定 |
| E004 | Read ツールで PDF 読込失敗 | PDF の整合性を確認 |
| E005 | Markdown 変換結果が空 | 画像のみの PDF の可能性 |
| E006 | 分割チャンク変換失敗 | 該当ページ範囲で最大 3 回再試行 |

---

## Phase 2: Knowledge Extraction

chunks.json から知識を抽出し、extraction.json を生成する。

### 実行コマンド

```bash
uv run python -m pdf_pipeline.cli.helpers extract_knowledge "{OUTPUT_DIR}/chunks.json" "{OUTPUT_DIR}"
```

### 入力

- `{OUTPUT_DIR}/chunks.json`: Phase 1 の Step 8 で生成されたチャンクデータ

### 出力

- `{OUTPUT_DIR}/extraction.json`: 抽出された知識データ（エンティティ、ファクト、クレーム、財務データポイント）
- stdout に統計情報: `entities=N facts=N claims=N datapoints=N`

### 変数保持

| 変数 | 説明 | 使用先 |
|------|------|--------|
| `EXTRACTION_STATS` | 抽出統計（stdout 出力） | サマリー |

### エラー時の対処

Phase 2 で失敗した場合、**report.md と chunks.json は残す**。Phase 3-4 はスキップする。

| エラー | 条件 | 対処 |
|--------|------|------|
| FileNotFoundError | chunks.json が存在しない | Phase 1 の結果を確認 |
| LLM 呼び出し失敗 | ClaudeCodeProvider のエラー | エラーログを確認、再実行 |
| extraction.json 書込失敗 | ディスク容量・権限 | ディスク状態を確認 |

---

## Phase 3: Graph-Queue 生成

extraction.json から graph-queue JSON を生成する。

### 実行コマンド

```bash
python3 scripts/emit_graph_queue.py \
    --command pdf-extraction \
    --input "{OUTPUT_DIR}/extraction.json"
```

### 入力

- `{OUTPUT_DIR}/extraction.json`: Phase 2 で生成された知識データ

### 出力

- `.tmp/graph-queue/pdf-extraction/gq-{timestamp}-{hash4}.json`: Graph-Queue JSON（v2 スキーマ）

### 変数保持

| 変数 | 説明 | 使用先 |
|------|------|--------|
| `GQ_FILE` | 生成された graph-queue JSON のパス | Phase 4 |

### graph-queue JSON の検出

emit_graph_queue.py の出力パスを取得するため、以下のいずれかの方法を使用:

1. **stdout 出力の確認**: スクリプトが出力パスを表示する
2. **ディレクトリ走査**: `.tmp/graph-queue/pdf-extraction/` 配下の最新ファイルを取得

```bash
# 最新の graph-queue ファイルを取得
GQ_FILE=$(ls -t .tmp/graph-queue/pdf-extraction/*.json 2>/dev/null | head -1)
```

### エラー時の対処

Phase 3 で失敗した場合、**extraction.json は残す**。Phase 4 はスキップする。

| エラー | 条件 | 対処 |
|--------|------|------|
| extraction.json 不存在 | Phase 2 の結果が見つからない | Phase 2 を確認 |
| JSON パースエラー | extraction.json の形式不正 | Phase 2 を再実行 |
| emit_graph_queue.py 実行エラー | マッパー関数のエラー | スクリプトのログを確認 |

---

## Phase 4: Neo4j 投入

save-to-graph スキルのロジックを使用して、graph-queue JSON を Neo4j に投入する。詳細は `.claude/skills/save-to-graph/SKILL.md` を参照。

### 前提条件（Phase 4 固有）

- Neo4j が起動していること
- `cypher-shell` が使用可能であること
- UNIQUE 制約・インデックスが作成済みであること

### 実行方式

save-to-graph スキルの処理フローに従い、以下を実行:

1. **Neo4j 接続確認**
   ```bash
   NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
   NEO4J_USER="${NEO4J_USER:-neo4j}"
   NEO4J_PASSWORD="${NEO4J_PASSWORD:?NEO4J_PASSWORD is required}"

   cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -a "$NEO4J_URI" \
     "RETURN 'connection_ok' AS status"
   ```

2. **graph-queue JSON の読み込みと検証**
   - `GQ_FILE` を Read ツールで読み込む
   - `schema_version`, 必須キーを検証

3. **ノード投入（MERGE）**: Topic -> Entity -> FiscalPeriod -> Source -> Author -> Chunk -> Fact -> Claim -> FinancialDataPoint
4. **リレーション投入（MERGE）**: TAGGED, MAKES_CLAIM, ABOUT, CONTAINS_CHUNK, EXTRACTED_FROM, STATES_FACT, HAS_DATAPOINT, FOR_PERIOD, RELATES_TO
5. **クロスファイルリレーション**: 既存ノードとの接続
6. **完了処理**: graph-queue ファイルの削除 or 保持

### パラメータ連携

| 本スキルパラメータ | save-to-graph 相当 |
|-------------------|-------------------|
| `--dry-run` | `--dry-run` |
| `--keep` | `--keep` |
| `--skip-neo4j` | (Phase 4 自体をスキップ) |

### エラー時の対処

Phase 4 で失敗した場合、**graph-queue ファイルは残す**。手動での再実行を案内する。

| エラー | 条件 | 対処 |
|--------|------|------|
| Neo4j 接続失敗 | 環境変数未設定 or Neo4j 未起動 | 以下の手動実行コマンドを案内 |
| Cypher 実行エラー | 制約・インデックス未作成 | 初回セットアップを案内 |

**手動実行案内メッセージ**:

```
Phase 4（Neo4j 投入）が失敗しました。
graph-queue ファイルは保持されています: {GQ_FILE}

Neo4j が利用可能になったら、以下のコマンドで手動投入できます:
  /save-to-graph --file {GQ_FILE}
```

---

## エラーハンドリング（グレースフルデグラデーション）

各フェーズの失敗は後続フェーズのみに影響し、既に生成された成果物は保持される。

| Phase | エラー | 対処 | 成果物の状態 |
|-------|--------|------|-------------|
| Phase 1 | PDF 変換失敗 | **全体中断** | なし |
| Phase 2 | 知識抽出失敗 | Phase 3-4 スキップ | report.md + chunks.json は残す |
| Phase 3 | graph-queue 生成失敗 | Phase 4 スキップ | extraction.json は残す |
| Phase 4 | Neo4j 接続失敗 | 手動実行を案内 | graph-queue は残す |

### デグラデーション判定フロー

```
Phase 1 実行
  |
  +-- 失敗 → 全体中断（エラーサマリー出力）
  |
  +-- 成功 → Phase 2 実行
                |
                +-- 失敗 → Phase 3-4 スキップ（部分サマリー出力）
                |
                +-- 成功 → Phase 3 実行
                              |
                              +-- 失敗 → Phase 4 スキップ（部分サマリー出力）
                              |
                              +-- 成功 → Phase 4 実行
                                            |
                                            +-- 失敗 → 手動実行案内（部分サマリー出力）
                                            |
                                            +-- 成功 → 完了サマリー出力
```

---

## 複数 PDF の連続処理

複数の PDF パスが指定された場合、各 PDF に対して Phase 1-4 を順次実行する。

```
for pdf_path in pdf_paths:
    Phase 1-4 を実行（グレースフルデグラデーション適用）
    成功/部分成功/失敗を記録

全 PDF 完了後:
    全体サマリーを出力
```

各 PDF の処理結果は独立しており、1 つの PDF が失敗しても他の PDF の処理は継続する。

---

## 完了サマリー

### 単一 PDF（全フェーズ成功時）

```markdown
## pdf-to-knowledge 完了

| 項目 | 値 |
|------|-----|
| 入力 PDF | {pdf_path} |
| SHA-256 | {SHA256[:16]}... |
| ページ数 | {PAGE_COUNT} |
| チャンク数 | {CHUNK_COUNT} |
| 抽出統計 | {EXTRACTION_STATS} |
| 出力ディレクトリ | {OUTPUT_DIR} |
| Graph-Queue | {GQ_FILE} |
| Neo4j 投入 | OK |

### 出力ファイル

- `{OUTPUT_DIR}/report.md` (Phase 1)
- `{OUTPUT_DIR}/chunks.json` (Phase 1)
- `{OUTPUT_DIR}/metadata.json` (Phase 1)
- `{OUTPUT_DIR}/extraction.json` (Phase 2)
- `{GQ_FILE}` (Phase 3, --keep 時のみ残存)
```

### 単一 PDF（部分成功時）

```markdown
## pdf-to-knowledge 部分完了

| 項目 | 値 |
|------|-----|
| 入力 PDF | {pdf_path} |
| SHA-256 | {SHA256[:16]}... |
| ページ数 | {PAGE_COUNT} |
| チャンク数 | {CHUNK_COUNT} |
| 完了フェーズ | Phase 1-2 |
| 失敗フェーズ | Phase 3 (graph-queue 生成失敗) |

### 出力ファイル（生成済み）

- `{OUTPUT_DIR}/report.md` (Phase 1)
- `{OUTPUT_DIR}/chunks.json` (Phase 1)
- `{OUTPUT_DIR}/metadata.json` (Phase 1)
- `{OUTPUT_DIR}/extraction.json` (Phase 2)

### エラー詳細

Phase 3 で以下のエラーが発生しました:
{error_message}

Phase 4（Neo4j 投入）はスキップされました。
```

### 複数 PDF（全体サマリー）

```markdown
## pdf-to-knowledge 一括処理完了

| # | PDF | ページ | チャンク | Phase 1 | Phase 2 | Phase 3 | Phase 4 | ステータス |
|---|-----|--------|---------|---------|---------|---------|---------|-----------|
| 1 | report1.pdf | 15 | 4 | OK | OK | OK | OK | COMPLETE |
| 2 | report2.pdf | 45 | 8 | OK | OK | OK | FAIL | PARTIAL |
| 3 | report3.pdf | - | - | SKIP | - | - | - | SKIP (処理済み) |
| 4 | report4.pdf | - | - | FAIL | - | - | - | ERROR |

- 完全成功: 1 件
- 部分成功: 1 件
- スキップ: 1 件
- 失敗: 1 件
```

---

## 環境変数

| 変数名 | デフォルト | 説明 | 使用フェーズ |
|--------|-----------|------|-------------|
| NEO4J_URI | bolt://localhost:7687 | Neo4j Bolt プロトコル URI | Phase 4 |
| NEO4J_USER | neo4j | Neo4j ユーザー名 | Phase 4 |
| NEO4J_PASSWORD | (必須、デフォルトなし) | Neo4j パスワード | Phase 4 |

---

## 関連リソース

| リソース | パス |
|---------|------|
| convert-pdf スキル | `.claude/skills/convert-pdf/SKILL.md` |
| save-to-graph スキル | `.claude/skills/save-to-graph/SKILL.md` |
| save-to-graph 詳細ガイド | `.claude/skills/save-to-graph/guide.md` |
| CLI ヘルパー | `src/pdf_pipeline/cli/helpers.py` |
| KnowledgeExtractor | `src/pdf_pipeline/core/knowledge_extractor.py` |
| MarkdownChunker | `src/pdf_pipeline/core/chunker.py` |
| graph-queue 生成スクリプト | `scripts/emit_graph_queue.py` |
| ナレッジグラフスキーマ | `data/config/knowledge-graph-schema.yaml` |
| StateManager | `src/pdf_pipeline/services/state_manager.py` |
| data_paths | `src/data_paths/` |

## 変更履歴

### 2026-03-15: 初版作成（Issue #102）

- 4 フェーズ構成ワークフロースキル新規作成
- Phase 1: convert-pdf スキルのロジック統合
- Phase 2: extract_knowledge CLI ヘルパー連携
- Phase 3: emit_graph_queue.py (pdf-extraction コマンド) 連携
- Phase 4: save-to-graph スキルのロジック統合
- グレースフルデグラデーション対応
- 複数 PDF 連続処理対応
- --force, --skip-neo4j, --dry-run, --keep パラメータ対応
