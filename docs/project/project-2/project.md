# Project 2: news_scraper 自動収集 → 週次レポート連携

## 概要

週次マーケットレポートのニュースソースを GitHub Project Issue から、finance パッケージの `news_scraper` でスクレイピングしたローカル JSON ファイルに切り替える。

## ステータス

| 項目 | 値 |
|------|-----|
| 開始日 | 2026-03-01 |
| ステータス | 計画完了・実装待ち |
| GitHub Project | #64 (news_scraper → 週次レポート連携) |
| プランファイル | `original-plan.md` |

## Issue 一覧

| Wave | Issue | タイトル | 依存 |
|------|-------|---------|------|
| 1 | #3680 | スクレイピングスクリプト作成 | - |
| 1 | #3681 | launchd 設定ファイル作成 | #3680 |
| 2 | #3682 | 変換スクリプト作成 | #3680 |
| 2 | #3683 | 変換スクリプトのテスト作成 | #3682 |
| 3 | #3684 | wr-news-aggregator 改修 | #3682 |
| 3 | #3685 | weekly-report-lead 改修 | #3684 |
| 3 | #3686 | SKILL.md + コマンド定義改修 | #3685 |

## 実装順序

```
Wave 1: #3680 → #3681
Wave 2: #3680 → #3682 → #3683
Wave 3: #3682 → #3684 → #3685 → #3686
```

## 検証方法

1. `make check-all` で品質チェック通過
2. 変換スクリプトの単体テスト通過
3. `scripts/scrape_finance_news.py` 手動実行で JSON 保存確認
4. `scripts/convert_scraped_news.py` で出力形式確認
5. `/generate-market-report --weekly --news-dir` でエンドツーエンド実行

## 対象ファイル

| 操作 | ファイル |
|------|---------|
| 新規 | `scripts/scrape_finance_news.py` |
| 新規 | `scripts/convert_scraped_news.py` |
| 新規 | `config/launchd/com.note-finance.scrape-news.plist` |
| 新規 | `tests/scripts/test_convert_scraped_news.py` |
| 変更 | `.claude/agents/wr-news-aggregator.md` |
| 変更 | `.claude/agents/weekly-report-lead.md` |
| 変更 | `.claude/skills/generate-market-report/SKILL.md` |
| 変更 | `.claude/commands/generate-market-report.md` |
