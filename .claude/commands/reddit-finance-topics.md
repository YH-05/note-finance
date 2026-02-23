---
description: Reddit金融コミュニティ（r/investing, r/stocks, r/wallstreetbets等）からトピック・議論・センチメントを収集し、投資視点でグループ別に整理します。
argument-hint: [--days 7] [--top-n 10] [--groups all] [--deep]
---

# /reddit-finance-topics - Reddit金融トピック収集

Reddit金融コミュニティから注目トピックを自動収集し、グループ別に整理するコマンドです。

## 使用例

```bash
# 標準実行（デフォルト: 過去7日間、全グループ、各最新10件）
/reddit-finance-topics

# 過去3日間、特定グループ、各最新5件
/reddit-finance-topics --days 3 --groups "general_investing,trading" --top-n 5

# 深掘り収集（コメント詳細・関連スレッドを含む）
/reddit-finance-topics --deep --groups "macro_economics,deep_analysis"

# 過去1日間の速報確認
/reddit-finance-topics --days 1 --top-n 20
```

## 入力パラメータ

| パラメータ | 必須 | デフォルト | 説明 |
|-----------|------|-----------|------|
| --days | - | 7 | 過去何日分の投稿を対象とするか |
| --top-n | - | 10 | 各グループの最大取得件数（スコア降順） |
| --groups | - | all | 対象グループ（カンマ区切り / all）。例: "general_investing,trading" |
| --deep | - | false | 深掘りモード。コメント詳細・関連スレッドを含む |

## パラメータ解析・グループ一覧

パラメータのデフォルト値・解析ロジック・グループ一覧は
`.claude/skills/reddit-finance-topics/SKILL.md` を参照してください。

このコマンドは受け取った引数文字列をそのまま `reddit-finance-topics` スキルに渡します。

## スキル呼び出し

解析したパラメータを `reddit-finance-topics` スキルに渡して実行:

```
Skill: reddit-finance-topics
Input: days, top_n, groups_list, deep
```

## 関連リソース

| リソース | パス |
|---------|------|
| reddit-finance-topics スキル | `.claude/skills/reddit-finance-topics/SKILL.md` |

## 関連コマンド

- **金融ニュース収集**: `/ai-research-collect`（企業ブログ・プレスリリース収集）
- **週次レポート生成**: `/generate-market-report`（週次マーケットレポート）
