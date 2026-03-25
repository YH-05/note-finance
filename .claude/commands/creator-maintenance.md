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
重複検出スクリプトを実行:
```bash
uv run python scripts/creator_detect_duplicates.py
```
- Entity 閾値 0.92、Concept 閾値 0.93（`--entity-threshold` / `--concept-threshold` で変更可）
- 結果は `data/processed/creator_quality/duplicates_YYYYMMDD.json` に保存
- 自動マージはしない（ユーザー確認が必要）
- ユーザーがマージを指示した場合のみ実行

### Step 5: 改善レポート
Before/After 比較を含む改善レポートを出力。

$ARGUMENTS
