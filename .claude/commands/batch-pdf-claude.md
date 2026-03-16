---
allowed-tools: Bash
description: ディレクトリ内の全PDFをClaudeで並列バッチ変換（--provider claude --parallel 3）
---

# PDF バッチ変換 — Claude 専用

**引数**: ディレクトリパス（省略時は DATA_ROOT/raw/pdfs）

## 実行

!`INPUT_DIR="${ARGUMENTS:-$(uv run python -c 'from data_paths import get_path; print(get_path("raw"))')}" && uv run pdf-pipeline batch --provider claude --parallel 3 "$INPUT_DIR"`

## 関連

- 単一ファイル変換: `/convert-pdf-claude <pdf_path>`
- parallel・provider 変更: `uv run pdf-pipeline batch --help`
