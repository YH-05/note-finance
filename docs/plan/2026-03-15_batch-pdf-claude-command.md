# Plan: `/batch-pdf-claude` スラッシュコマンドの作成

## Context

`--provider claude` オプションが `pdf-pipeline batch` に追加されたが、毎回 `--provider claude --parallel 3` を手打ちするのは煩雑。
`/convert-pdf-claude`（単一ファイル用）と対になる `/batch-pdf-claude`（ディレクトリ一括用）スラッシュコマンドを作成し、引数を最小化する。

**目標使用例:**
```
/batch-pdf-claude                                          # デフォルトディレクトリ全体
/batch-pdf-claude /Volumes/NeoData/.../ISAT_IJ            # 特定ディレクトリ
```

---

## 設計方針

| 項目 | 値 | 理由 |
|------|-----|------|
| 引数 | ディレクトリパス（省略可） | 唯一変わる要素。省略時はデフォルト |
| `--provider` | `claude` 固定 | コマンドの目的そのもの |
| `--parallel` | `3` 固定デフォルト | 実績のある値。変えたい場合は直接 CLI を使う |
| `--dry-run` | なし | 事前確認は `batch --dry-run` で別途実行 |
| `--extract` | なし | KG抽出は別用途 |

引数は **ディレクトリパス1つだけ**。複雑なフラグは持たない。

---

## 作成ファイル（1ファイル新規）

| ファイル | 内容 |
|---------|------|
| `.claude/commands/batch-pdf-claude.md` | 新規スラッシュコマンド |

---

## コマンド設計

### Frontmatter

```yaml
---
allowed-tools: Bash
description: ディレクトリ内の全PDFをClaudeで並列バッチ変換（--provider claude --parallel 3）
---
```

`skill-preload` は不要（Bash のみで完結）。

### 引数処理ロジック

`$ARGUMENTS` が空の場合は `DATA_ROOT/raw/pdfs` をデフォルトとする。
Pythonの `data_paths.get_path("raw/pdfs")` で取得する。

```bash
# $ARGUMENTS が空なら Python でデフォルトパスを取得
INPUT_DIR="${ARGUMENTS:-$(uv run python -c 'from data_paths import get_path; print(get_path("raw/pdfs"))')}"
uv run pdf-pipeline batch --provider claude --parallel 3 "$INPUT_DIR"
```

### コマンドファイル全体構成

```markdown
---
allowed-tools: Bash
description: ディレクトリ内の全PDFをClaudeで並列バッチ変換（--provider claude --parallel 3）
---

# PDF バッチ変換 — Claude 専用

**引数**: ディレクトリパス（省略時は DATA_ROOT/raw/pdfs）

## 実行

!`INPUT_DIR="${ARGUMENTS:-$(uv run python -c 'from data_paths import get_path; print(get_path("raw/pdfs"))')}" && uv run pdf-pipeline batch --provider claude --parallel 3 "$INPUT_DIR"`

## 関連
- 単一ファイル変換: /convert-pdf-claude <pdf_path>
- parallel・provider変更: uv run pdf-pipeline batch --help
```

`!` プレフィックスで即時実行する形式（`/convert-pdf-claude` と同パターン）。

---

## 検証方法

```bash
# 1. dry-run で引数なしの挙動確認（デフォルトディレクトリが設定されるか）
# → コマンド内の INPUT_DIR が raw/pdfs になることを確認

# 2. dry-run でディレクトリ指定
/batch-pdf-claude /Volumes/NeoData/note-finance-data/raw/pdfs/ISAT_IJ

# 3. ヘルプ表示でオプション確認
uv run pdf-pipeline batch --help
```
