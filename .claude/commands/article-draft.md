---
description: リサーチ結果から初稿を作成します。
argument-hint: @<article_dir>
---

リサーチ結果から初稿を作成します。

## 入力パラメータ

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| @article_dir | ○ | - | 記事ディレクトリのパス（`articles/{category}/{YYYY-MM-DD}_{slug}/`） |

## 引数の解釈ルール

共通パス解決ロジックに従う。詳細は `.claude/commands/_shared/path-resolution.md` を参照。

```
/article-draft @articles/stock_analysis/2026-03-15_tsla-earnings-analysis/
```

## 処理フロー

```
Step 1: 前提確認
├── meta.yaml 読み込み
└── workflow.research = "done" を確認

Step 2: カテゴリ別ライター実行
├── stock_analysis / macro_economy / quant_analysis / investment_education
│   └── finance-article-writer エージェント
├── asset_management
│   └── asset-management-writer エージェント
├── side_business (type: case_study)
│   └── case-study-writer エージェント + case-study-writer スキル参照
├── side_business (type: experience)
│   └── experience-writer エージェント
└── market_report
    └── weekly-report-lead エージェント（→ wr-template-renderer）

Step 3: 結果保存
├── 02_draft/first_draft.md
└── meta.yaml の workflow.draft = "done"

Step 4: [HF5] 初稿レビュー
```

## 実行手順

### Step 1: 前提確認

1. **meta.yaml 読み込み**

   記事ディレクトリの `meta.yaml` を読み込み、以下を確認:

   ```yaml
   workflow:
     research: "done"    # ← 必須
   ```

   `workflow.research` が `"done"` でない場合:

   ```
   エラー: リサーチが完了していません

   現在のステータス: workflow.research = "{status}"

   対処法:
   - /article-research @{article_dir} を先に実行してください
   ```

### Step 2: カテゴリ別ライター実行

#### stock_analysis / macro_economy / quant_analysis / investment_education

```
エージェント: finance-article-writer
入力:
  - 01_research/decisions.json
  - 01_research/sources.json
  - 01_research/claims.json
  - meta.yaml
出力: 02_draft/first_draft.md
```

#### asset_management

```
エージェント: asset-management-writer
入力:
  - 01_research/ 配下のセッションデータ
  - meta.yaml
出力:
  - 02_draft/first_draft.md（note記事、2000-4000字）
  - 02_draft/curated_sources.json（キュレーション済みソース）

X投稿生成（記事完成後に自動実行）:
  /x-post @{article_dir}
  → 02_draft/x_post.md（x-post-generator スキルで層別テンプレート・参照ライブラリ適用）
```

#### side_business

```
エージェント: experience-writer
入力:
  - 01_research/ 配下のソース・合成データ
  - meta.yaml
出力: 02_draft/first_draft.md（6,000-8,000字）
```

#### market_report

```
エージェント: weekly-report-lead → wr-template-renderer
入力:
  - 01_research/ 配下の市場データ・ニュース
  - meta.yaml
出力: 02_draft/first_draft.md（5,000字以上）
```

### Step 3: 結果保存

2. **meta.yaml の更新**

   ```yaml
   workflow:
     draft: "done"    # ← 更新
   updated_at: "YYYY-MM-DD"
   ```

### Step 4: [HF5] 初稿レビュー

3. **初稿サマリーの表示**

   ```markdown
   ## 初稿が完成しました

   - **文字数**: {word_count}字（目標: {target_wordcount}字）
   - **セクション数**: {section_count}
   - **カテゴリ**: {category}

   初稿を確認しますか？ (y/n)

   確認後、修正が必要な場合は 02_draft/first_draft.md を直接編集してください。
   準備ができたら「続行」と入力してください。
   ```

4. **workflow 更新**

   ```yaml
   human_feedback:
     hf5_draft_reviewed: true    # ← 更新
   ```

## 完了報告

```markdown
## ドラフト作成完了

### 記事情報
- **トピック**: {topic}
- **カテゴリ**: {category}
- **文字数**: {word_count}字

### 生成ファイル
- `02_draft/first_draft.md` - 初稿

### 次のステップ

1. 初稿を確認・編集
2. 批評・修正: `/article-critique @{article_dir}`
```

## エラーハンドリング

### リサーチ未完了

```
エラー: リサーチが完了していません

必要な完了状態: workflow.research = "done"

対処法:
- /article-research @{article_dir} を先に実行してください
```

### ライターエージェント失敗

```
エラー: 初稿の生成に失敗しました

エージェント: {agent_name}
エラー内容: {error_message}

対処法:
1. 01_research/ のデータが正しく生成されているか確認
2. 再実行: /article-draft @{article_dir}
```

## 関連コマンド

- **前提コマンド**: `/article-research`
- **後続コマンド**: `/article-critique`
- **統合コマンド**: `/article-full`
- **旧コマンド**: `/finance-edit` Step 1（このコマンドで置き換え）
- **使用エージェント**: finance-article-writer, asset-management-writer, experience-writer, weekly-report-lead
