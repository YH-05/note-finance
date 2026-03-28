# 議論メモ: scrape-news 定期実行除外 & スクレイパー全件確認

**日付**: 2026-03-28
**参加**: ユーザー + AI

## 背景・コンテキスト

launchd に登録されているスクレイパーの全件を把握し、
不要なジョブを整理するセッション。

## 議論のサマリー

### 1. 定期実行スクレイパー全件確認

`~/Library/LaunchAgents/` にロード済みのスクレイパーを一覧化。

| サービス名 | ソース | 実行時刻 | スクリプト |
|---|---|---|---|
| scrape-news | 全ソース（引数なし） | 0/6/12/18時 | scrape_finance_news.py |
| scrape-kabutan | kabutan | 0/6/12/18時 | scrape_finance_news.py |
| scrape-reuters-jp | reuters_jp | 0/6/12/18時 | scrape_finance_news.py |
| scrape-ars-technica | ars_technica | 0/6/12/18時 | scrape_finance_news.py |
| scrape-techcrunch | techcrunch | 0/6/12/18時 | scrape_finance_news.py |
| scrape-hacker-news | hacker_news | 0/6/12/18時 | scrape_finance_news.py |
| scrape-the-verge | the_verge | 0/6/12/18時 | scrape_finance_news.py |
| scrape-zero-hedge | zero_hedge | 0/6/12/18時 | scrape_finance_news.py |
| scrape-federal-reserve | federal_reserve | 0/6/12/18時 | scrape_finance_news.py |
| scrape-jetro | —（専用） | 3時/21時 | scrape_jetro.py |

計10件。全て `--include-content` 付き。

### 2. scrape-news の問題

- `launchctl list` で exit code `78`（設定ファイル関連エラー）
- 引数なし全ソース一括版のため、個別 plist と完全に重複
- 個別 plist（8件）が全ソースをカバー済みで冗長

## 決定事項

1. **scrape-news を定期実行から除外**:
   - `launchctl unload` 実施
   - `~/Library/LaunchAgents/com.note-finance.scrape-news.plist` を `trash/` に移動
   - `config/launchd/com.note-finance.scrape-news.plist`（ソース管理側）は保留

## アクションアイテム

- [ ] `config/launchd/com.note-finance.scrape-news.plist` をソース管理からも削除するか判断 (優先度: 低)

## 次回の議論トピック

- `scripts/dedup_scraped.py` 実装（重複排除）
- JETRO ログ確認（--include-content 追加後の本文取得）
