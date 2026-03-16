---
description: 全記事のステータス一覧を表示します。
argument-hint: [--category <category>]
---

全記事のステータス一覧を表示します。

## 入力パラメータ

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| --category | - | 全カテゴリ | フィルタするカテゴリ（asset_management / side_business / macro_economy / stock_analysis / market_report / quant_analysis / investment_education） |

## 処理フロー

```
Step 1: 記事スキャン
├── articles/{category}/{slug}/meta.yaml を検索（新形式）
└── articles/{category}_{seq}_{theme}/article-meta.json を検索（旧形式、後方互換）

Step 2: メタデータ読み込み
├── 各 meta.yaml を読み込み
└── ワークフロー状態を取得

Step 3: ステータス表示
├── テーブル形式で表示
├── カテゴリフィルタ適用（--category 指定時）
└── サマリー表示
```

## 実行手順

### Step 1: 記事スキャン

1. **新形式の検索**

   `articles/` ディレクトリ内の全サブディレクトリを走査し、`meta.yaml` を持つフォルダを検出します。

   ```bash
   # 新形式: articles/{category}/{YYYY-MM-DD}_{slug}/meta.yaml
   find articles -name "meta.yaml" -maxdepth 3
   ```

2. **旧形式の検索（後方互換）**

   `article-meta.json` を持つフォルダも検出し、統合表示します。

   ```bash
   # 旧形式: articles/{category}_{seq}_{theme}/article-meta.json
   find articles -name "article-meta.json" -maxdepth 2
   ```

### Step 2: メタデータ読み込み

3. **各記事のメタデータを読み込み**

   新形式（`meta.yaml`）:
   ```yaml
   topic: "..."
   category: "..."
   status: "..."
   workflow:
     research: "done|pending"
     draft: "done|pending"
     critique: "done|pending"
     revision: "done|pending"
     publish: "done|pending"
   ```

   旧形式（`article-meta.json`）:
   ```json
   {
     "topic": "...",
     "category": "...",
     "status": "...",
     "workflow": { ... }
   }
   ```

   旧形式のフィールドは新形式にマッピングして統合表示します。

### Step 3: ステータス表示

4. **テーブル表示**

   ```markdown
   ## 記事ステータス一覧

   | カテゴリ | 記事 | ステータス | Research | Draft | Critique | Revision | Publish |
   |---------|------|----------|----------|-------|----------|----------|---------|
   | asset_management | 新NISAつみたて投資枠の活用法 | review | ✓ | ✓ | ✓ | ✓ | - |
   | stock_analysis | テスラ決算分析 | draft | ✓ | ✓ | - | - | - |
   | macro_economy | 米雇用統計解説 | research | ✓ | - | - | - | - |
   | market_report | 2026年3月第2週レポート | published | ✓ | ✓ | ✓ | ✓ | ✓ |
   | side_business | Webライター体験談 | init | - | - | - | - | - |
   ```

   ワークフロー状態の表示:
   - `✓` = done
   - `-` = pending
   - `!` = error

5. **カテゴリフィルタ**

   `--category` が指定されている場合、該当カテゴリの記事のみ表示します。

   ```
   /article-status --category stock_analysis
   ```

6. **サマリー表示**

   ```markdown
   ## サマリー

   | ステータス | 件数 |
   |----------|------|
   | init | 1 |
   | research | 1 |
   | draft | 1 |
   | review | 1 |
   | published | 1 |
   | **合計** | **5** |

   ### カテゴリ別

   | カテゴリ | 件数 |
   |---------|------|
   | asset_management | 1 |
   | side_business | 1 |
   | macro_economy | 1 |
   | stock_analysis | 1 |
   | market_report | 1 |
   | quant_analysis | 0 |
   | investment_education | 0 |
   ```

## 使用例

```bash
# 全記事のステータス表示
/article-status

# 特定カテゴリのみ
/article-status --category stock_analysis

# 特定カテゴリのみ
/article-status --category market_report
```

## 注意事項

1. **新旧形式の混在**: 新形式（`meta.yaml`）と旧形式（`article-meta.json`）が混在する場合も統合表示します
2. **パフォーマンス**: 記事数が多い場合は、スキャンに数秒かかることがあります
3. **フォルダ構造**:
   - 新形式: `articles/{category}/{YYYY-MM-DD}_{slug}/meta.yaml`
   - 旧形式: `articles/{category}_{seq}_{theme}/article-meta.json`

## 関連コマンド

- **記事作成**: `/article-init`, `/article-full`
- **個別フェーズ**: `/article-research`, `/article-draft`, `/article-critique`, `/article-publish`
