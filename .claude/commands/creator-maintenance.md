---
description: creator-neo4j の評価→改善サイクルを一括実行（embedding更新→品質チェック→自動修復→重複検出）
---

creator-neo4j の評価→改善サイクルを実行してください。

## 実行ステップ

### Step 1: Embedding 更新
新規ノードに embedding を付与:
```bash
uv run --extra embedding python scripts/creator_embed_nodes.py
```

### Step 2: 品質チェック
`/creator-quality-check` スキルを実行し、7カテゴリ + LLM-as-Judge 評価を行う。

### Step 3: 自動修復
品質チェックで検出された問題のうち、以下を自動修復:
- genre=null → IN_GENRE から補完
- ABOUT 未接続 Concept → テキストマッチで retroactive リンキング
- Reddit Source title=null → URL からサブレディット名を抽出

### Step 4: 重複検出
Vector Index を使用して Entity/Concept の重複候補を検出し報告。
自動マージはしない（ユーザー確認が必要）。

### Step 5: 改善レポート
Before/After 比較を含む改善レポートを出力。

$ARGUMENTS
