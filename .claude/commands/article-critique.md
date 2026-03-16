---
description: 初稿の批評と修正を実行します。
argument-hint: @<article_dir> [--mode quick|full]
---

初稿の批評と修正を実行します。

## 入力パラメータ

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| @article_dir | ○ | - | 記事ディレクトリのパス（`articles/{category}/{YYYY-MM-DD}_{slug}/`） |
| --mode | - | full | 編集モード（quick / full） |

## 引数の解釈ルール

共通パス解決ロジックに従う。詳細は `.claude/commands/_shared/path-resolution.md` を参照。

```
/article-critique @articles/stock_analysis/2026-03-15_tsla-earnings-analysis/
/article-critique @articles/stock_analysis/2026-03-15_tsla-earnings-analysis/ --mode quick
```

## 編集モード

| モード | 説明 | 実行する批評エージェント |
|--------|------|------------------------|
| quick | 必須チェックのみ（速報記事向け） | fact, compliance |
| full | 全面チェック（品質重視） | fact, compliance, structure, data_accuracy, readability |

## 処理フロー

```
Step 1: 前提確認
├── meta.yaml 読み込み
└── workflow.draft = "done" を確認

Step 2: 批評（カテゴリ別・並列）
├── stock_analysis / macro_economy / quant_analysis / asset_management / investment_education
│   ├── quick: finance-critic-fact, finance-critic-compliance
│   └── full:  + finance-critic-structure, finance-critic-data, finance-critic-readability
├── side_business (type: case_study)
│   └── case-study-critique スキル（4エージェント並列: data, analysis, actionability, structure）
├── side_business (type: experience)
│   ├── quick: exp-critic-reality, exp-critic-balance
│   └── full:  + exp-critic-empathy, exp-critic-embed
└── market_report
    └── wr-report-validator

Step 3: 批評結果の統合
├── 02_draft/critic.json
└── 02_draft/critic.md

Step 4: 修正
├── finance-reviser または experience-reviser
└── 02_draft/revised_draft.md

Step 5: ステータス更新・最終確認
├── meta.yaml 更新
└── [HF6] 最終確認
```

## 実行手順

### Step 1: 前提確認

1. **meta.yaml 読み込み**

   記事ディレクトリの `meta.yaml` を読み込み、以下を確認:

   ```yaml
   workflow:
     draft: "done"    # ← 必須
   ```

   `workflow.draft` が `"done"` でない場合:

   ```
   エラー: ドラフトが完了していません

   現在のステータス: workflow.draft = "{status}"

   対処法:
   - /article-draft @{article_dir} を先に実行してください
   ```

2. **初稿ファイルの確認**

   `02_draft/first_draft.md` が存在することを確認します。

### Step 2: 批評（並列実行）

カテゴリに応じた批評エージェントを並列で実行します。

#### stock_analysis / macro_economy / quant_analysis / asset_management / investment_education

**quick モード**:
```
Task 1: finance-critic-fact（事実正確性チェック）
Task 2: finance-critic-compliance（コンプライアンスチェック）
```

**full モード**:
```
Task 1: finance-critic-fact（事実正確性チェック）
Task 2: finance-critic-compliance（コンプライアンスチェック）
Task 3: finance-critic-structure（構成チェック）
Task 4: finance-critic-data（データ正確性チェック）
Task 5: finance-critic-readability（読みやすさチェック）
```

#### side_business

**quick モード**:
```
Task 1: exp-critic-reality（リアリティチェック）
Task 2: exp-critic-balance（文字量バランスチェック）
```

**full モード**:
```
Task 1: exp-critic-reality（リアリティチェック）
Task 2: exp-critic-balance（文字量バランスチェック）
Task 3: exp-critic-empathy（共感度チェック）
Task 4: exp-critic-embed（埋め込みリンクチェック）
```

#### market_report

```
Task 1: wr-report-validator（レポート検証）
```

### Step 3: 批評結果の統合

3. **critic.json の生成**

   ```json
   {
     "article_id": "...",
     "category": "...",
     "mode": "quick|full",
     "generated_at": "...",
     "critics": {
       "fact": { ... },
       "compliance": { ... },
       "structure": { ... },
       "data_accuracy": { ... },
       "readability": { ... }
     },
     "overall_score": 82,
     "priority_fixes": [ ... ]
   }
   ```

   出力先: `02_draft/critic.json`

4. **critic.md の生成**（人間可読形式）

   ```markdown
   # 批評レポート

   ## 総合スコア: 82/100

   ## コンプライアンス: 90/100
   - ステータス: pass
   - 問題点: 2件

   ## 事実正確性: 85/100
   - 検証済み: 45件
   - 問題点: 3件

   ...

   ## 優先修正事項
   1. [HIGH] 免責事項の追加が必要
   2. [MEDIUM] 株価データの修正
   ```

   出力先: `02_draft/critic.md`

5. **コンプライアンスチェック**

   compliance.status が `"fail"` の場合:

   ```
   ⚠️ コンプライアンス問題が検出されました。

   critical な問題:
   - {問題1}
   - {問題2}

   これらの問題は修正が必須です。
   続行しますか？ (y/n)
   ```

### Step 4: 修正

6. **カテゴリ別リバイザー実行**

   **stock_analysis / macro_economy / quant_analysis / asset_management / investment_education / market_report**:
   ```
   エージェント: finance-reviser
   入力: 02_draft/first_draft.md, 02_draft/critic.json, 01_research/sources.json
   出力: 02_draft/revised_draft.md
   ```

   **side_business**:
   ```
   エージェント: experience-reviser
   入力: 02_draft/first_draft.md, 02_draft/critic.json
   出力: 02_draft/revised_draft.md
   ```

### Step 5: ステータス更新・最終確認

7. **meta.yaml の更新**

   ```yaml
   workflow:
     critique: "done"    # ← 更新
     revision: "done"    # ← 更新
   updated_at: "YYYY-MM-DD"
   ```

8. **[HF6] 最終確認**

   ```markdown
   ## 修正版が完成しました

   ### 修正サマリー

   - **総修正箇所**: {count}件
   - **compliance 修正**: {count}件
   - **fact 修正**: {count}件
   - **最終スコア**: {score}/100

   ### 修正前後の比較

   | 項目 | 修正前 | 修正後 |
   |------|--------|--------|
   | compliance | {before} | {after} |
   | fact | {before} | {after} |
   | overall | {before} | {after} |

   revised_draft.md を確認してください。

   公開準備ができたら「承認」と入力してください。
   追加修正が必要な場合は「修正」と入力してください。
   ```

9. **承認時の workflow 更新**

   ```yaml
   human_feedback:
     hf6_final_approved: true    # ← 更新
   status: "review"              # ← 更新（公開準備完了）
   ```

## 完了報告

```markdown
## 批評・修正完了

### 記事情報
- **トピック**: {topic}
- **カテゴリ**: {category}
- **編集モード**: {mode}

### 最終スコア
| 項目 | スコア |
|------|--------|
| 総合 | {overall}/100 |
| コンプライアンス | {compliance}/100 |
| 事実正確性 | {fact}/100 |
| 構成 | {structure}/100 (full時) |
| データ正確性 | {data}/100 (full時) |
| 読みやすさ | {readability}/100 (full時) |

### 生成ファイル
- `02_draft/critic.json` - 批評（JSON）
- `02_draft/critic.md` - 批評（人間可読）
- `02_draft/revised_draft.md` - 修正版

### 次のステップ

1. revised_draft.md を最終確認
2. note.com に下書き投稿:
   ```
   /article-publish @{article_dir}
   ```
```

## エラーハンドリング

### ドラフト未完了

```
エラー: ドラフトが完了していません

必要な完了状態: workflow.draft = "done"

対処法:
- /article-draft @{article_dir} を先に実行してください
```

### 批評エージェントの部分失敗

一部のエージェントが失敗しても、必須エージェント（fact, compliance / reality, balance）が成功していれば続行します。

```
警告: 一部の批評エージェントが失敗しました

失敗:
- {agent_name}

成功した批評で続行します。
失敗した批評は critic.json に含まれません。
```

### コンプライアンス fail

```
⚠️ コンプライアンスチェック失敗

この記事には修正が必須の問題が含まれています。

問題:
1. {critical_issue_1}
2. {critical_issue_2}

修正後、再度 /article-critique を実行してください。
```

## 関連コマンド

- **前提コマンド**: `/article-draft`
- **後続コマンド**: `/article-publish`
- **統合コマンド**: `/article-full`
- **旧コマンド**: `/finance-edit` Steps 2-3（このコマンドで置き換え）
- **使用エージェント**: finance-critic-*, exp-critic-*, finance-reviser, experience-reviser, wr-report-validator
