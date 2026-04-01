---
name: convert-pdf
description: PDF を Markdown に変換するスキル。auto モード（デフォルト）はプリスキャンで最適方式を自動選択。LiteParse テキスト抽出 → Haiku ディスクレーマー判定 → 必要ページのみ Claude Vision Read → Claude Markdown 構造化の多段パイプライン。claude / llamaparse の明示指定も可。出力は report.md + chunks.json + metadata.json（統一スキーマ）。
allowed-tools: Read, Write, Bash, Glob
---

# convert-pdf スキル

PDF を構造化 Markdown に変換するスキル。`--method` で変換方式を選択できる。

| 方式 | エンジン | 特徴 |
|------|---------|------|
| `auto`（デフォルト） | LiteParse + Claude Vision（必要ページのみ） | 高速・低コスト・表は Vision で正確に取得 |
| `claude` | Claude Code Read ツール（30p 分割） | 全ページ Vision。外部依存なし |
| `llamaparse` | LlamaParse REST API | セルサイドレポート向け。最高精度・有料 |

どの方式でも出力ファイル（`report.md` / `chunks.json` / `metadata.json`）とメタデータスキーマは統一される。

金融レポート・決算資料・リサーチペーパーなど、表・グラフ・複数カラムを含む PDF を高品質に Markdown 化する。

## アーキテクチャ

### auto 方式（デフォルト）

```
/convert-pdf (このスキル = オーケストレーター)
  |
  +-- Step 1:  PDF パス検証
  +-- Step 2:  SHA-256 ハッシュ計算（CLI ヘルパー）
  +-- Step 3:  冪等性チェック（CLI ヘルパー）
  +-- Step 4:  出力ディレクトリ計算（CLI ヘルパー）
  +-- Step A:  PyMuPDF プリスキャン（prescan_pdf.py）
  |     +-- 画像の位置・サイズ・ページを取得
  |     +-- テキスト表を find_tables() で検出
  +-- Step B:  LiteParse テキスト抽出（liteparse_convert.py）
  |     +-- 全ページのテキストを page_texts.json に出力
  +-- Step B': Haiku ディスクレーマー判定（classify_disclaimers.py）
  |     +-- page_texts.json を入力 → disclaimer_pages を出力
  |     +-- ※ 必ず Haiku で実行（モデル固定）
  +-- Step C:  ギャップ検出
  |     +-- プリスキャン結果から大画像ありページを特定
  |     +-- disclaimer_pages を除外
  |     +-- → vision_pages（Vision Read 対象）を決定
  +-- Step D:  対象ページ Claude Vision Read（Read ツール）
  |     +-- vision_pages の各ページを個別に Read
  |     +-- 表が含まれていれば Markdown テーブルとして抽出
  |     +-- 表でない図（チャート・ロゴ等）はスキップ
  +-- Step E:  マージ + Claude Markdown 構造化
  |     +-- LiteParse テキスト（disclaimer 除外）+ Vision 抽出テーブル
  |     +-- Claude が ATX 見出し・テーブル構文等に構造化
  +-- Step F:  report.md / chunks.json / metadata.json / 完了記録
```

### claude / llamaparse 方式

```
/convert-pdf --method claude|llamaparse
  |
  +-- Step 1:  PDF パス検証
  +-- Step 2:  SHA-256 ハッシュ計算（CLI ヘルパー）
  +-- Step 3:  冪等性チェック（CLI ヘルパー）
  +-- Step 4:  出力ディレクトリ計算（CLI ヘルパー）
  +-- Step 5:  ページ数取得（CLI ヘルパー）
  +-- Step 6:  PDF 読込 + Markdown 変換
  |     +-- claude: Read ツール（30p 分割）
  |     +-- llamaparse: scripts/llamaparse_convert.py
  +-- Step 7:  report.md 出力
  +-- Step 8:  chunks.json 生成（CLI ヘルパー）
  +-- Step 9:  metadata.json 生成
  +-- Step 10: 完了記録（CLI ヘルパー）
```

## 使用方法

```bash
# auto 方式（デフォルト）— プリスキャンで最適化
/convert-pdf /path/to/report.pdf

# Claude Vision 全ページ Read
/convert-pdf --method claude /path/to/report.pdf

# LlamaParse（最高精度・有料）
/convert-pdf --method llamaparse /path/to/report.pdf

# LlamaParse + tier 指定
/convert-pdf --method llamaparse --tier cost_effective /path/to/report.pdf

# 複数 PDF を連続変換
/convert-pdf /path/to/report1.pdf /path/to/report2.pdf

# 強制再変換（冪等性チェックをスキップ）
/convert-pdf --force /path/to/report.pdf
```

## パラメータ一覧

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| pdf_path | (必須) | 変換対象の PDF ファイルパス（複数指定可） |
| --method | `auto` | 変換方式: `auto` / `claude` / `llamaparse` |
| --force | false | 冪等性チェックをスキップし強制再変換する |
| --tier | `agentic` | llamaparse 方式のみ。パースティア |
| --no-ocr | false | auto 方式の LiteParse で OCR を無効化 |
| --dpi | 150 | auto 方式の LiteParse OCR 解像度 |

## 前提条件

| 方式 | 必要なもの |
|------|-----------|
| 全方式共通 | `uv`, PyMuPDF (fitz), `pdf_pipeline` パッケージ |
| auto | Node.js 18+, `liteparse` pip パッケージ, `ANTHROPIC_API_KEY`（Haiku 判定用） |
| claude | なし（追加依存なし） |
| llamaparse | `LLAMA_CLOUD_API_KEY` |

## 出力パス形式

```
{PROCESSED_DIR}/{mirror_subpath}/{stem}_{hash8}/
├── report.md       # Markdown 変換結果
├── chunks.json     # セクション分割チャンク
└── metadata.json   # 処理メタデータ
```

- `PROCESSED_DIR`: `CONVERT_PDF_DIR` 環境変数（設定時）、未設定なら `DATA_ROOT/processed`
  - 取得: `pdf_pipeline.types.get_processed_dir()` または `uv run python -c "from pdf_pipeline.types import get_processed_dir; print(get_processed_dir())"`
- `mirror_subpath`: PDF が `raw/pdfs/` 配下にある場合、そのサブディレクトリ構造をミラー
- `hash8`: SHA-256 の先頭 8 文字

### 出力例

```
# 入力: data/raw/pdfs/earnings/toyota-q4-2025.pdf (hash: a1b2c3d4...)
# 出力: data/processed/earnings/toyota-q4-2025_a1b2c3d4/
#       ├── report.md
#       ├── chunks.json
#       └── metadata.json

# 入力: /tmp/report.pdf (raw/pdfs 配下でない)
# 出力: data/processed/report_a1b2c3d4/
```

---

## Step 1: PDF パス検証

**実行方式**: スキル直接

入力された PDF パスを検証する。

### 処理内容

1. パスが存在するか確認
2. 拡張子が `.pdf`（大文字小文字不問）であるか確認
3. ファイルサイズが 0 でないか確認

### 実行方法

```bash
# Bash ツールでファイル存在確認
ls -la "{pdf_path}"
```

加えて Read ツールでファイルが読み込み可能か確認してもよい。

### エラー時

| 条件 | メッセージ | 対処 |
|------|-----------|------|
| パス不存在 | `E001: PDF ファイルが見つかりません: {pdf_path}` | パスを確認して再実行 |
| 拡張子不正 | `E002: PDF ファイルではありません（拡張子: {ext}）` | `.pdf` ファイルを指定 |
| ファイルサイズ 0 | `E003: PDF ファイルが空です: {pdf_path}` | 正常な PDF を指定 |

---

## Step 2: SHA-256 ハッシュ計算

**実行方式**: CLI ヘルパー

```bash
uv run python -m pdf_pipeline.cli.helpers compute_hash "{pdf_path}"
```

### 出力

64 文字の SHA-256 hex digest（小文字）を stdout に出力。

### 変数保持

以降のステップで使用するため、出力を `SHA256` として保持する。

### エラー時

| 条件 | メッセージ | 対処 |
|------|-----------|------|
| 読込失敗 | `ScanError` 例外 | ファイル権限・パスを確認 |

---

## Step 3: 冪等性チェック

**実行方式**: CLI ヘルパー

同じ PDF が既に処理済みかを確認する。`--force` 指定時はこのステップをスキップする。

```bash
uv run python -m pdf_pipeline.cli.helpers check_idempotency "{SHA256}" "{PROCESSED_DIR}/state.json"
```

### 出力

- `true`: 処理済み。以降のステップをスキップして完了メッセージを出力する。
- `false`: 未処理。Step 4 に進む。

### 処理済みの場合

```
PDF は既に処理済みです（SHA-256: {SHA256[:16]}...）。
再変換するには --force オプションを使用してください。
```

---

## Step 4: 出力ディレクトリ計算

**実行方式**: CLI ヘルパー

```bash
uv run python -m pdf_pipeline.cli.helpers compute_output_dir "{pdf_path}" "{SHA256}"
```

### 出力

出力ディレクトリの絶対パスを stdout に出力。

### 変数保持

以降のステップで使用するため、出力を `OUTPUT_DIR` として保持する。

---

## Step A-F: Auto Method（`--method auto`）

**`--method auto`（デフォルト）の場合、Step 5-10 の代わりに以下を実行する。**

### Step A+B: prescan + LiteParse（convert_auto.py prepare）

prescan（PyMuPDF 構造スキャン）と LiteParse（テキスト抽出）を実行する。API 呼び出しなし。

```bash
uv run python -m pdf_pipeline.cli.convert_auto prepare "{pdf_path}" "{OUTPUT_DIR}" [--no-ocr] [--dpi N]
```

#### 出力

JSON を stdout に出力:

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `page_count` | int | 総ページ数 |
| `prescan_path` | str | prescan.json のパス |
| `page_texts_path` | str | page_texts.json のパス |

#### 変数保持

出力 JSON を `PREP` としてパースし保持する。`PAGE_COUNT = PREP.page_count`。

### Step B': Haiku ディスクレーマー判定（スキルが Agent で実行）

**実行方式**: Agent ツール（`model="haiku"`）

`page_texts.json` を Read で読み込み、`classify_disclaimers.py` の `SYSTEM_PROMPT` をシステムプロンプトに、`format_prompt()` でフォーマットしたテキストをユーザーメッセージとして Haiku サブエージェントに送る。

```
Agent(
    model="haiku",
    system_prompt=SYSTEM_PROMPT,  # classify_disclaimers.py から
    prompt=format_prompt(page_texts),
)
```

Haiku は JSON 配列（例: `[5, 6, 7]`）を返す。これを `DISCLAIMER_PAGES` として保持する。

### Step C: build_plan（convert_auto.py build_plan）

disclaimer_pages を渡して vision_pages / content_pages / content_text を計算する。

```bash
uv run python -m pdf_pipeline.cli.convert_auto build_plan "{OUTPUT_DIR}" '{DISCLAIMER_PAGES_JSON}'
```

#### 出力

JSON を stdout に出力:

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `vision_pages` | list[int] | Vision Read が必要なページ番号 |
| `content_pages` | list[int] | コンテンツページ番号 |
| `content_text_path` | str | disclaimer 除外済みテキストのパス |
| `disclaimer_pages` | list[int] | ディスクレーマーページ番号 |

#### 変数保持

出力 JSON を `PLAN` としてパースし保持する。

#### 中間ファイル

| ファイル | 内容 |
|---------|------|
| `{OUTPUT_DIR}/prescan.json` | PyMuPDF prescan 結果 |
| `{OUTPUT_DIR}/page_texts.json` | LiteParse ページ別テキスト |
| `{OUTPUT_DIR}/content_text.txt` | disclaimer 除外済みテキスト |
| `{OUTPUT_DIR}/plan.json` | 実行プラン |

### Step D: Vision Read（vision_pages が空でない場合のみ）

**実行方式**: Read ツール

`PLAN.vision_pages` の各ページを Read ツールで個別に読み込む。

```
for page in PLAN.vision_pages:
    Read("{pdf_path}", pages="{page}")
```

各ページの内容を確認し:
- **表が含まれている場合**: Markdown テーブル構文に変換して保持
- **チャート・ロゴ等の図の場合**: テキスト記述（「[Figure: 図の簡潔な説明]」）のみ保持
- **テキストのみの場合**: LiteParse テキストで十分なのでスキップ

Vision 抽出結果を `VISION_TABLES` として保持する（ページ番号 → Markdown テーブルの dict）。

### Step E: マージ + Markdown 構造化

**実行方式**: スキル直接（Claude による構造化）

1. `content_text.txt`（LiteParse テキスト、disclaimer 除外済み）を Read で読み込む
2. `VISION_TABLES` がある場合、該当ページ位置にテーブルをマージ
3. 以下の変換ルールに従って Markdown を構造化:
   - ATX 見出し（`# H1` `## H2` `### H3`）で階層構造を保持
   - テーブルは Markdown テーブル構文（`|` 区切り + `---` ヘッダー行）
   - 数値は正確に保持（四捨五入・丸め禁止）
   - ページ番号・ヘッダー・フッター・透かしを除去
   - 前置き文・コードフェンス・コメント・要約・翻訳は禁止

構造化した Markdown を `MARKDOWN` として保持する。

### Step F: 出力ファイル生成

#### F.1: report.md 出力

```
Write("{OUTPUT_DIR}/report.md", MARKDOWN)
```

#### F.2: chunks.json 生成

```bash
uv run python -m pdf_pipeline.cli.helpers chunk_and_save "{OUTPUT_DIR}/report.md" "{SHA256}" "{OUTPUT_DIR}"
```

`CHUNK_COUNT` を保持する。

#### F.3: metadata.json 生成

```bash
uv run python -m pdf_pipeline.cli.helpers save_metadata "{OUTPUT_DIR}" "{SHA256}" "{pdf_path}" "{PAGE_COUNT}" "{CHUNK_COUNT}" "auto" "{OUTPUT_DIR}/prescan.json"
```

#### F.4: 完了記録

```bash
uv run python -m pdf_pipeline.cli.helpers record_completed "{SHA256}" "{PROCESSED_DIR}/state.json" "{pdf_filename}"
```

---

## Step 5: ページ数取得

**実行方式**: CLI ヘルパー

```bash
uv run python -m pdf_pipeline.cli.helpers get_page_count "{pdf_path}"
```

### 出力

ページ数を文字列で stdout に出力。

### 変数保持

以降のステップで使用するため、出力を `PAGE_COUNT` として保持する。

### エラー時

| 条件 | メッセージ | 対処 |
|------|-----------|------|
| PDF 破損 | `RuntimeError` 例外 | PDF ファイルの整合性を確認 |

---

## Step 6: PDF 読込 + Markdown 変換

**実行方式**: `--method` パラメータにより分岐する。

### llamaparse 方式（`--method llamaparse`）

30 ページ超の PDF を変換する場合、必ずユーザーの承認を得てから実行する:

```
この PDF は {PAGE_COUNT} ページあります。
Agentic tier で変換すると約 {PAGE_COUNT * 10} クレジット（${PAGE_COUNT * 0.0125:.2f}）を消費します。
変換を実行しますか？ (y/n)
```

承認後、llamaparse_convert.py スクリプトを呼び出す:

```bash
uv run python scripts/llamaparse_convert.py \
    --tier "{TIER}" \
    -o "{OUTPUT_DIR}" \
    "{pdf_path}"
```

スクリプトが `report.md` / `chunks.json` / `metadata.json` を生成するため、Step 7-9 は実質的にスキップ（Step 10 の完了記録のみ実行）。

### claude 方式（`--method claude`、デフォルト）

Claude Code の Read ツールで PDF を直接読み込み、Markdown に変換する。

### ページ分割戦略

| 条件 | 戦略 | 読込回数 |
|------|------|---------|
| 30p 以下 | 一括読込 | 1 回 |
| 31-60p | 2 分割 | 2 回 |
| 61-90p | 3 分割 | 3 回 |
| N ページ | ceil(N/30) 分割 | ceil(N/30) 回 |

### 6.1: 一括読込（30p 以下）

```
Read(pdf_path, pages="1-{PAGE_COUNT}")
```

Read ツールが返す PDF の内容を、以下の変換ルールに従って Markdown に変換する。

### 6.2: 分割読込（30p 超）

30 ページ単位でループする:

```
chunk_size = 30
total_chunks = ceil(PAGE_COUNT / chunk_size)

for i in range(total_chunks):
    start = i * chunk_size + 1
    end = min((i + 1) * chunk_size, PAGE_COUNT)
    Read(pdf_path, pages="{start}-{end}")
    # 各チャンクを Markdown に変換
```

### 6.3: マージ処理（分割読込時のみ）

分割読込した Markdown チャンクをマージする際、以下の処理を行う:

1. **セクション境界の重複見出し除去**: チャンク末尾とチャンク先頭で同じ見出しが出現する場合、後続チャンクの重複見出しを除去する
2. **改行の正規化**: チャンク結合部で連続する空行を 2 行以内に正規化する
3. **ページ番号の除去**: チャンク境界に残るページ番号テキストを除去する

### 変換ルール

Read ツールが返す PDF の内容を Markdown に変換する際、以下のルールに厳密に従う。

#### 構造保持

- ATX 見出し（`# H1` `## H2` `### H3`）で階層構造を保持する
- 見出しレベルは元 PDF の構造を反映する（タイトル = `#`、セクション = `##`、サブセクション = `###`）
- 箇条書き・番号付きリストは Markdown 構文で保持する

#### テーブル変換

- テーブルは Markdown テーブル構文（`|` 区切り + `---` ヘッダー行）に変換する
- 列の位置合わせはベストエフォートで実施する
- セルの結合がある場合は、結合セルの内容を最初のセルに記載する
- 数値列は右寄せ（`:---:` または `---:`）を推奨する

#### 数値・通貨の正確性

- 数値は**正確に保持**する（四捨五入・丸め禁止）
- 通貨記号（$, %, bps, 億円 など）を保持する
- 小数点以下の桁数を維持する

#### 除去対象

- **ヘッダー・フッター**: ページ上部/下部の繰り返し要素を除去する
- **ページ番号**: `Page 1 of 10`、`- 3 -`、単独の数字行を除去する
- **免責事項**: 各ページの定型免責文（Disclaimer, Important Notice 等）を除去する
- **透かし**: CONFIDENTIAL、DRAFT 等の透かしテキストを除去する

#### 禁止事項

- **前置き文禁止**: 「以下は PDF の変換結果です」等の説明文を付加しない
- **コードフェンス禁止**: Markdown 全体を ` ```markdown ``` ` で囲まない
- **コメント禁止**: `<!-- -->` 形式の HTML コメントを挿入しない
- **要約禁止**: 原文の内容を要約・省略しない。全ての情報を保持する
- **翻訳禁止**: 原文の言語をそのまま保持する（日本語 PDF は日本語で出力）

### 出力

変換された Markdown テキストを `MARKDOWN` として保持する。

### エラー時

| 条件 | メッセージ | 対処 |
|------|-----------|------|
| Read 失敗 | `E004: PDF 読込に失敗しました: {pdf_path}` | PDF が破損していないか確認 |
| 変換結果が空 | `E005: Markdown 変換結果が空です` | PDF の内容を確認（画像のみの PDF の可能性） |
| 分割チャンクの変換失敗 | `E006: チャンク {i}/{total} の変換に失敗しました` | 該当ページ範囲で再試行（最大 3 回） |

---

## Step 7: report.md 出力

**実行方式**: Write ツール

Step 6 で生成した Markdown を `report.md` として保存する。

```
Write("{OUTPUT_DIR}/report.md", MARKDOWN)
```

### 前処理

出力前に以下を確認する:

1. 出力ディレクトリが存在しない場合は作成する（Bash ツールで `mkdir -p`）
2. Markdown テキストが空でないことを確認する

```bash
mkdir -p "{OUTPUT_DIR}"
```

### 変数保持

`report.md` の絶対パスを `REPORT_PATH` として保持する。

---

## Step 8: chunks.json 生成

**実行方式**: CLI ヘルパー

```bash
uv run python -m pdf_pipeline.cli.helpers chunk_and_save "{REPORT_PATH}" "{SHA256}" "{OUTPUT_DIR}"
```

### 出力

チャンク数を文字列で stdout に出力。

### 変数保持

チャンク数を `CHUNK_COUNT` として保持する。

### chunks.json の形式

```json
[
  {
    "source_hash": "a1b2c3d4...",
    "chunk_index": 0,
    "section_title": "Executive Summary",
    "content": "## Executive Summary\n\nThe report highlights...",
    "tables": []
  },
  {
    "source_hash": "a1b2c3d4...",
    "chunk_index": 1,
    "section_title": "Financial Overview",
    "content": "## Financial Overview\n\n| Metric | Value |...",
    "tables": []
  }
]
```

---

## Step 9: metadata.json 生成

**実行方式**: CLI ヘルパー

```bash
uv run python -m pdf_pipeline.cli.helpers save_metadata "{OUTPUT_DIR}" "{SHA256}" "{pdf_path}" "{PAGE_COUNT}" "{CHUNK_COUNT}"
```

### 出力

`"ok"` を stdout に出力。

### metadata.json の形式（統一スキーマ）

全方式共通。方式固有フィールドは該当しない場合 `null`。

```json
{
  "sha256": "a1b2c3d4e5f6...",
  "pdf_path": "/path/to/report.pdf",
  "pages": 30,
  "chunks": 5,
  "converter": "claude",
  "processed_at": "2026-03-15T12:00:00+00:00",
  "pdf_name": null,
  "tier": null,
  "job_id": null,
  "credits_per_page": null,
  "estimated_credits": null
}
```

`llamaparse` 方式の場合、方式固有フィールドに値が入る:

```json
{
  "sha256": "a1b2c3d4...",
  "pdf_path": "/path/to/report.pdf",
  "pages": 15,
  "chunks": 4,
  "converter": "llamaparse",
  "processed_at": "2026-03-18T04:00:00+00:00",
  "pdf_name": "report.pdf",
  "tier": "agentic",
  "job_id": "8208cd81-...",
  "credits_per_page": 10,
  "estimated_credits": 150
}
```

---

## Step 10: 完了記録

**実行方式**: CLI ヘルパー

```bash
uv run python -m pdf_pipeline.cli.helpers record_completed "{SHA256}" "{PROCESSED_DIR}/state.json" "{pdf_filename}"
```

`{pdf_filename}` は PDF ファイルのベース名（例: `report.pdf`）。

### 出力

`"ok"` を stdout に出力。

---

## 完了サマリー

全ステップが正常に完了した場合、以下のサマリーを出力する:

```markdown
## convert-pdf 完了

| 項目 | 値 |
|------|-----|
| 入力 PDF | {pdf_path} |
| SHA-256 | {SHA256[:16]}... |
| ページ数 | {PAGE_COUNT} |
| チャンク数 | {CHUNK_COUNT} |
| 出力ディレクトリ | {OUTPUT_DIR} |
| 変換方式 | Method B (Claude Code Read) |

### 出力ファイル

- `{OUTPUT_DIR}/report.md`
- `{OUTPUT_DIR}/chunks.json`
- `{OUTPUT_DIR}/metadata.json`
```

## 複数 PDF の連続変換

複数の PDF パスが指定された場合、各 PDF に対して Step 1-10 を順次実行する。

```
for pdf_path in pdf_paths:
    Step 1-10 を実行
    成功/失敗を記録

全 PDF 完了後:
    全体サマリーを出力
```

### 全体サマリー

```markdown
## convert-pdf 一括変換完了

| # | PDF | ページ | チャンク | ステータス |
|---|-----|--------|---------|-----------|
| 1 | report1.pdf | 15 | 4 | OK |
| 2 | report2.pdf | 45 | 8 | OK |
| 3 | report3.pdf | - | - | SKIP (処理済み) |
| 4 | report4.pdf | - | - | ERROR: E004 |

- 成功: 2 件
- スキップ: 1 件
- 失敗: 1 件
```

---

## エラーハンドリング

| コード | ステップ | 条件 | 対処 |
|--------|---------|------|------|
| E001 | 1 | PDF ファイル不存在 | パスを確認して再実行 |
| E002 | 1 | 拡張子が .pdf でない | `.pdf` ファイルを指定 |
| E003 | 1 | ファイルサイズ 0 | 正常な PDF を指定 |
| E004 | 6 | Read ツールで PDF 読込失敗 | PDF の整合性を確認 |
| E005 | 6 | Markdown 変換結果が空 | 画像のみの PDF の可能性。OCR 対応の別手法を検討 |
| E006 | 6 | 分割チャンク変換失敗 | 該当ページ範囲で最大 3 回再試行 |
| E007 | 7 | report.md 書込失敗 | ディスク容量・書込権限を確認 |
| E008 | 8 | chunks.json 生成失敗 | report.md の内容を確認 |
| E009 | 9 | metadata.json 生成失敗 | ディスク容量・書込権限を確認 |
| E010 | 10 | 完了記録失敗 | state.json のパス・権限を確認 |

### リトライ戦略

Step 6（PDF 読込 + Markdown 変換）のみ、分割チャンク単位で最大 3 回リトライする。
その他のステップは即座に失敗としてエラーメッセージを出力する。

---

## 関連リソース

| リソース | パス |
|---------|------|
| CLI ヘルパー | `src/pdf_pipeline/cli/helpers.py` |
| Auto 準備スクリプト | `src/pdf_pipeline/cli/convert_auto.py` |
| PyMuPDF プリスキャン | `src/pdf_pipeline/cli/prescan_pdf.py` |
| Haiku disclaimer 分類 | `src/pdf_pipeline/cli/classify_disclaimers.py` |
| LiteParse テキスト抽出 | `scripts/liteparse_convert.py` |
| LlamaParse 変換 | `scripts/llamaparse_convert.py` |
| MarkdownChunker | `src/pdf_pipeline/core/chunker.py` |
| StateManager | `src/pdf_pipeline/services/state_manager.py` |
| PdfScanner（SHA-256） | `src/pdf_pipeline/core/pdf_scanner.py` |
| パイプライン設定 | `src/pdf_pipeline/types.py` |
| data_paths | `src/data_paths/` |

## 設計上の決定

### 変換方式の選択

| 項目 | `--method auto`（デフォルト） | `--method claude` | `--method llamaparse` |
|------|------------------------------|-------------------|----------------------|
| エンジン | LiteParse + Claude Vision（対象ページのみ） | Claude Code Read（全ページ） | LlamaParse REST API |
| 外部依存 | Node.js 18+, liteparse, ANTHROPIC_API_KEY | なし | LLAMA_CLOUD_API_KEY |
| 追加コスト | Haiku disclaimer 判定 + Vision（必要ページのみ） | なし | 10 credits/page（Agentic） |
| 表の精度 | 非常に高い（Vision で対象ページのみ精読） | 良好 | 非常に高い |
| 速度 | 高速（大部分は LiteParse ローカル処理） | 中速（30p 分割） | API 依存 |
| 推奨用途 | 汎用（特にセルサイドレポート・決算資料） | Node.js 非対応環境 | 最高精度が必要な場合 |

### 旧 Method A（廃止済み）

Method A（Gemini CLI subprocess 方式）は廃止。`pdf-to-markdown` スキルも廃止。

### 30p 分割の根拠

- Claude Code の Read ツールは PDF を最大 20 ページずつ読み込める制約がある
- 安全マージンを考慮して 30p を上限とした（Read ツール側で 30p 以内に対応）
- 実測では 20-30p が品質と速度のバランスが最適

## 変更履歴

### 2026-03-30: auto メソッド追加・llamaparse 統合

- auto メソッド（デフォルト）を追加: prescan → LiteParse → Haiku disclaimer → Vision → Markdown
- llamaparse を `--method llamaparse` として統合（独立スキル廃止）
- LiteParse（ローカル Node.js ベース）を第3変換方式として追加
- Haiku による disclaimer 分類を code-level で固定
- metadata.json を統一スキーマ化（converter/prescan フィールド追加）
- save_metadata に converter/prescan_json パラメータ追加
- convert_auto.py 準備スクリプト新規作成

### 2026-03-15: 初版作成（Issue #99）

- Method B（Claude Code Read 方式）の中核スキルとして新規作成
- 10 ステップ処理フロー実装
- 30 ページ分割ロジック
- 冪等性チェック対応
- CLI ヘルパー関数連携
