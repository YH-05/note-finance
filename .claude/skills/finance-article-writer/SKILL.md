---
name: finance-article-writer
description: note.com向け金融記事の初稿を生成するオーケストレータースキル。カテゴリ判定→執筆ルール読込→Agentスポーン→出力検証を一体で実行する。/article-draftコマンドから呼び出される。記事の初稿作成時に必���使用すること。「記事を書いて」「初稿を作成」「ドラフト生成」「article-draft」と言われたら必ずこのスキルを使うこと。
---

# finance-article-writer ���キル

note.com 向け金融記事の初稿を生成するオーケストレーター。カテゴリ判定 → ルール読込 → Agent スポーン → 出力検証を一体で実行する。

## 対象カテゴリ

stock_analysis, macro_economy, investment_education, quant_analysis, market_report, asset_management, earnings, life_planning

## 引数

- `article_dir`: 記事ディレクトリのパス（例: `articles/stock_analysis/2026-03-28_us-telecom-sector/`）

## オーケストレーションフロー

### Step 1: 入力確認

1. 引数から `article_dir` を受け取る
2. `{article_dir}/meta.yaml` を Read し `category` を取得
3. `workflow.research` が `"done"` であることを確認
   - `"done"` でない場合 → エラー:「/article-research を先に実行してください」

### Step 2: ルール読込

4. `.claude/skills/finance-article-writer/references/common-rules.md` を Read → `{common_rules}` に格納
5. category に応じた references フ���イルを Read → `{category_rules}` に格納:

| category | ファイル |
|----------|---------|
| stock_analysis | `references/stock-analysis.md` |
| macro_economy | `references/macro-economy.md` |
| investment_education | `references/investment-education.md` |
| quant_analysis | `references/quant-analysis.md` |
| market_report | `references/market-report.md` |
| asset_management | `references/asset-management.md` |
| earnings | `references/earnings.md` |
| life_planning | `references/life-planning.md`（+ `references/cfp-grade-rules.md` を `quality_tier: cfp_grade` 時に追加読込） |

### Step 3: Agent ���ポーン

6. `Agent(subagent_type="general-purpose")` をスポーンする。プロンプトは以下の構造で構築:

```
あなたは note.com 向け金融記事のライターです。
以下のルールに厳密に従って、記事の初稿を生成してください。

## 共通執筆ルール

{common_rules}

## ��テゴリ別ルール（{category}）

{category_rules}

## 入力データ

以下のファイルを読み込んで記事を生成してください:

- meta.yaml: {article_dir}/meta.yaml
- リサーチデータ: {article_dir}/01_research/ 配下
  - decisions.json（採用された主張 — accept のみ使用）
  - sources.json（出典情報）
  - claims.json（存在する場合）

## 出力

以下のファイルを Write で保存してください:

- `{article_dir}/02_draft/first_draft.md` — 記事の初稿

{asset_management の場合のみ:}
- `{article_dir}/02_draft/curated_sources.json` — キュレーション済みソース一覧

## 品質チェック

出力前に、カテゴリ別ルール末尾のチェックリストを全て確認してください。
```

スポーン時の設定:
- `mode`: ファイル書き込みを許可する設定で起動
- `description`: `"{category} 記事の初稿生成"`

### Step 4: 出力検証

7. `{article_dir}/02_draft/first_draft.md` の存在を確認
   - 存在しない場合 → エラー報告
8. asset_management の場合: `{article_dir}/02_draft/curated_sources.json` の存在確認

### Step 5: meta.yaml 更新

9. `{article_dir}/meta.yaml` を Edit:
   - `workflow.draft` を `"done"` に更新
   - `updated_at` を今日の日付に更新

### Step 6: 完了報告

10. 以下を報告:

```
## ドラフト作成完了

- **カテゴリ**: {category}
- **出力**: 02_draft/first_draft.md

### 次のステップ
1. 初稿を確認・編集
2. 批評・修正: `/article-critique @{article_dir}`
```

## ファイル構成

| ファイル | 内容 |
|---------|------|
| `SKILL.md` | このファイル（オーケストレーション手順） |
| `references/common-rules.md` | 全カテゴリ��通ルール（表現・コンプラ・品質・note特性） |
| `references/stock-analysis.md` | 個別銘柄分析の構��・テンプレート |
| `references/macro-economy.md` | マクロ経済分析の構成・テンプレ��ト |
| `references/investment-education.md` | ��資教育記事の構成・テンプレート |
| `references/quant-analysis.md` | クオンツ分析の構成・テンプレート |
| `references/market-report.md` | 週次市場レポートの構成・テンプレート |
| `references/asset-management.md` | 資産形成記事の構成・テンプレート・ソースキュレーション |
| `references/earnings.md` | 決算プレビュー記事の構成・テンプレート（設計中） |

## エラーハンドリング

### リサーチ未完了

```
エラー: リサーチが完了していません
現在のステータス: workflow.research = "{status}"
対処法: /article-research @{article_dir} を先に実行してください
```

### Agent 出力なし

```
エラー: 初稿の生成に失敗しました
対処法:
1. 01_research/ のデータが正しく生成されているか確認
2. 再実行: /article-draft @{article_dir}
```

### 対象外カテゴリ

side_business, experience 等はこのスキルの対象外。`/article-draft` コマンドが別のエージェントにルーティングする。
