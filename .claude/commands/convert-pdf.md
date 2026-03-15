---
description: "単一PDFをMarkdownに変換（Claude Code直接Read方式）。report.md + chunks.json + metadata.json を出力。"
argument-hint: <pdf_path>
skill-preload: convert-pdf
---

# /convert-pdf - PDF to Markdown 変換

> **スキル参照**: `.claude/skills/convert-pdf/SKILL.md`

PDF ファイルを Claude Code の Read ツールで直接読み込み、構造化 Markdown に変換します。Method B（メインプロセス直接 Read 方式）の中核コマンドです。

## 使用方法

```bash
# 単一 PDF を変換
/convert-pdf /path/to/report.pdf

# 複数 PDF を連続変換
/convert-pdf /path/to/report1.pdf /path/to/report2.pdf

# 強制再変換（冪等性チェックをスキップ）
/convert-pdf --force /path/to/report.pdf
```

## 出力ファイル

| ファイル | 説明 |
|---------|------|
| `report.md` | Markdown 変換結果 |
| `chunks.json` | セクション分割チャンク |
| `metadata.json` | 処理メタデータ |

## 引数

対象 PDF: $ARGUMENTS
