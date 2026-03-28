# 議論メモ: RSSスクレイピング定期実行セットアップ

**日付**: 2026-03-28
**参加**: ユーザー + AI

## 背景・コンテキスト

前回（2026-03-28 朝）にJETROスクレイパーのlaunchd定期実行（03:00/21:00）と
`--include-content` の有効化が完了していた。
今回は残タスクである金融ニューススクレイパー（scrape_finance_news.py）の
launchd登録と各ソースの整備を実施した。

## 議論のサマリー

### 1. scrape_finance_news.py の launchd 登録

`config/launchd/com.note-finance.scrape-news.plist` の `YOUR_USERNAME` を `yuki` に修正し、
`~/Library/LaunchAgents/` にコピー・登録。スケジュール: 0:00/6:00/12:00/18:00。

### 2. JETRO の重複問題

`scrape_jetro.py`（ウェブクロール専用）と `scrape_finance_news.py --sources jetro`（RSSベース）
の2系統が存在することが判明。当面は両方並行運用し、統一は後日調査・決定。

### 3. ソースごとの別launchd化

各ソースを個別テスト後に別plistで登録する方針を採用。

**テスト結果:**
| ソース | 結果 | 理由 |
|--------|------|------|
| cnbc | OK | 既存登録済み |
| kabutan | OK | |
| reuters_jp | OK | |
| techcrunch | OK | |
| ars_technica | OK | |
| the_verge | OK | |
| hacker_news | OK | |
| federal_reserve | OK | |
| zero_hedge | OK | |
| nasdaq | NG | API廃止（2026-03、全エンドポイント404） |
| minkabu | NG | スクレイパー不動作（0件） |
| jetro | 保留 | 統一調査待ち |

### 4. --include-content 対応

全plistに `--include-content` を追加。kabutan/reuters_jp は
スクレイパー側が未対応だったため `unified.py` にポスト処理レイヤーを実装。

**実装箇所**: `src/news_scraper/unified.py`
全ソース収集・重複排除後に `content=None` の記事URLへ `ArticleExtractor` で一括アクセスし補完。

### 5. 本番スクレイピング実行確認

全9ソース合計591件取得、504件保存（重複87件スキップ）、content null=0件。

## 決定事項

1. **nasdaq/minkabu を対象外に**: `--sources` の choices から削除済み
2. **ソースごと別launchd**: 登録済み9ジョブ（cnbc/kabutan/reuters-jp/techcrunch/ars-technica/the-verge/hacker-news/federal-reserve/zero-hedge）
3. **全ジョブに --include-content**: 全plistに追加・リロード済み
4. **unified.py ポスト処理**: `content=None` 記事を ArticleExtractor で一括補完

## アクションアイテム

- [ ] JETROログ確認（次回03:00実行後に `tail logs/scrape_jetro.log`）(優先度: 高)
- [ ] `scripts/dedup_scraped.py` 実装（他RSスクレイパー整備後） (優先度: 中)
- [ ] JETRO scraper統一調査（scrape_jetro.py vs scrape_finance_news.py --sources jetro） (優先度: 低)

## 次回の議論トピック

- dedup_scraped.py の設計・実装
- JETRO scraper 統一方針の決定

## 参考情報

- launchd 登録済みジョブ一覧: `launchctl list | grep com.note-finance.scrape`
- plist 保存先: `config/launchd/com.note-finance.scrape-*.plist`
- 本番保存先: `/Volumes/personal_folder/scraped/{source}/`
