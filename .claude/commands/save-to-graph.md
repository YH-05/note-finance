---
description: graph-queue JSON を Neo4j に投入します（キュー検出 → ノード投入 → リレーション投入 → 完了処理）
argument-hint: [--source <command>] [--dry-run] [--file <path>] [--keep]
---

# /save-to-graph - Neo4j グラフデータ投入

graph-queue JSON ファイルを読み込み、Neo4j にナレッジグラフデータを MERGE ベースで冪等投入します。

## スキル

このコマンドは `save-to-graph` スキルを呼び出します。

- **スキル定義**: `.claude/skills/save-to-graph/SKILL.md`
- **詳細ガイド**: `.claude/skills/save-to-graph/guide.md`

## 使用例

```bash
# 標準実行（.tmp/graph-queue/ 配下の全未処理 JSON を投入）
/save-to-graph

# 特定コマンドソースのみ
/save-to-graph --source finance-news-workflow

# 特定ファイルのみ
/save-to-graph --file .tmp/graph-queue/finance-news-workflow/gq-20260307120000-a1b2.json

# ドライラン（Cypher を表示するが実行しない）
/save-to-graph --dry-run

# 処理済みファイルを削除せず保持
/save-to-graph --keep
```

## パラメータ

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| --source | all | 対象コマンドソース（finance-news-workflow, ai-research-collect, generate-market-report, asset-management, reddit-finance-topics, finance-full） |
| --dry-run | false | Cypher クエリを表示するが実行しない |
| --file | - | 特定の graph-queue JSON ファイルパスを指定（--source と排他） |
| --keep | false | 処理済みファイルを削除せず `.tmp/graph-queue/.processed/` に移動 |

## 前提条件

1. Neo4j が起動中であること
2. 初回セットアップ（制約・インデックス作成）が完了していること
3. graph-queue JSON が `.tmp/graph-queue/` に存在すること

初回セットアップの手順は `.claude/skills/save-to-graph/guide.md` を参照してください。

## 処理フロー

```
Phase 1: キュー検出・検証
  +-- Neo4j 接続確認
  +-- 未処理 JSON 検出
  +-- スキーマ検証

Phase 2: ノード投入（MERGE）
  +-- Topic -> Entity -> Source -> Claim の順で投入

Phase 3: リレーション投入（MERGE）
  +-- TAGGED, MAKES_CLAIM, ABOUT

Phase 4: 完了処理
  +-- ファイル削除 or 移動
  +-- 統計サマリー
```

## 関連コマンド

- **graph-queue 生成**: `python3 scripts/emit_graph_queue.py --command <cmd> --input <file>`
- **ニュース収集**: `/collect-finance-news`（ソースデータ生成）
- **レポート生成**: `/generate-market-report`（ソースデータ生成）
