---
description: 週次マーケットレポートを生成します。市場データ収集→ニュースコンテキスト統合→コメント生成→GitHub Issue投稿を自動化します。
---

# 週次マーケットレポート生成

## パラメータ（ユーザーに確認）

| パラメータ  | デフォルト     | 説明                                      |
| ----------- | -------------- | ----------------------------------------- |
| report_date | 今日           | レポート作成日（YYYY-MM-DD）              |
| mode        | weekly-comment | レポートモード（weekly / weekly-comment） |

## モード説明

| モード         | 説明                                  |
| -------------- | ------------------------------------- |
| weekly         | フル週次レポート（6エージェント並列） |
| weekly-comment | 週次コメント（簡易版、3エージェント） |

## 処理フロー

### 1. `generate-market-report` スキルの読み込み

// turbo
`.agents/skills/generate-market-report/SKILL.md` を読み込み、スキルの指示に従う。

### 2. Phase 1: 出力フォルダ作成

// turbo

```bash
mkdir -p articles/weekly_comment_{date}/data
mkdir -p articles/weekly_comment_{date}/02_edit
```

### 3. Phase 2: 市場データ収集

// turbo

```bash
python scripts/weekly_comment_data.py --date {report_date}
```

出力: `data/indices.json`, `data/mag7.json`, `data/sectors.json`, `data/earnings.json`

### 4. Phase 3: ニュースコンテキスト統合

以下のサブエージェント処理を並列実行:

- 指数ニュース収集
- MAG7ニュース収集
- セクターニュース収集

出力: `data/news_context.json`

### 5. Phase 4: コメント生成

テンプレートを読み込み、データを埋め込む。

プレースホルダー置換:

- `{report_date_formatted}`, `{spx_return}`, `{rsp_return}` 等
- `{indices_comment}`, `{mag7_comment}`, `{top_sectors_comment}` 等

### 文字数目標

| セクション           | 最低文字数     |
| -------------------- | -------------- |
| 指数コメント         | 500字          |
| MAG7コメント         | 800字          |
| 上位セクターコメント | 400字          |
| 下位セクターコメント | 400字          |
| 今後の材料           | 200字          |
| **合計**             | **3000字以上** |

### 6. Phase 5: レポート検証

生成されたレポートの品質を検証する。

### 7. Phase 6: Issue 投稿

GitHub Issue を作成し、Project #15 に追加する。

- Issue に `report` ラベルを付与
- Project #15 に追加（`gh project item-add` 実行）
- Status を "Weekly Report" に設定

## 関連リソース

| リソース                      | パス                                                |
| ----------------------------- | --------------------------------------------------- |
| generate-market-report スキル | `.agents/skills/generate-market-report/SKILL.md`    |
| Pythonスクリプト              | `scripts/market_report_data.py`                     |
| 週次コメントスクリプト        | `scripts/weekly_comment_data.py`                    |
| テンプレート                  | `template/market_report/weekly_comment_template.md` |
| サンプル                      | `template/market_report/sample/`                    |
| GitHub Project #15            | https://github.com/users/YH-05/projects/15          |
