---
description: "PDF→Markdown→ナレッジグラフの一括ワークフロー。変換→知識抽出→Neo4j投入を一括実行。"
argument-hint: <pdf_path>
skill-preload: pdf-to-knowledge
---

# /pdf-to-knowledge - PDF to Knowledge Graph ワークフロー

> **スキル参照**: `.claude/skills/pdf-to-knowledge/SKILL.md`

PDF ファイルからナレッジグラフ投入までを一括実行します。4 フェーズ（PDF→Markdown変換 → 知識抽出 → Graph-Queue生成 → Neo4j投入）を順次実行し、グレースフルデグラデーション対応で部分成功時も成果物を保持します。

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

## パラメータ

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| pdf_path | (必須) | 変換対象の PDF ファイルパス（複数指定可） |
| --force | false | 冪等性チェックをスキップし強制再変換する |
| --skip-neo4j | false | Phase 4（Neo4j 投入）をスキップする |
| --dry-run | false | Phase 4 の Cypher クエリを表示するが実行しない |
| --keep | false | Phase 4 完了後、graph-queue ファイルを削除せず保持する |

## 出力ファイル

| ファイル | Phase | 説明 |
|---------|-------|------|
| `report.md` | 1 | Markdown 変換結果 |
| `chunks.json` | 1 | セクション分割チャンク |
| `metadata.json` | 1 | 処理メタデータ |
| `extraction.json` | 2 | 知識抽出結果 |
| `gq-*.json` | 3 | Graph-Queue JSON |

## 前提条件

1. `pdf_pipeline` パッケージが利用可能であること
2. Neo4j が起動していること（Phase 4 のみ。未起動でも Phase 1-3 は正常完了）

## 処理フロー

```
Phase 1: PDF -> Markdown (convert-pdf ロジック)
Phase 2: Knowledge Extraction (知識抽出)
Phase 3: Graph-Queue 生成
Phase 4: Neo4j 投入 (save-to-graph ロジック)
```

## 関連コマンド

- `/convert-pdf` - PDF→Markdown 変換のみ（Phase 1 相当）
- `/save-to-graph` - Neo4j 投入のみ（Phase 4 相当）

## 引数

対象 PDF: $ARGUMENTS
