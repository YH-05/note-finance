# 議論メモ: developing_telecoms スクレイパー追加 & launchd登録

**日付**: 2026-03-29
**参加**: ユーザー + AI

## 背景・コンテキスト

ASEAN・新興市場テレコムのリサーチ強化の一環として、英語テレコム専門メディア
developingtelecoms.com をニュースモニタリング対象に追加する作業。

## 議論のサマリー

### RSS調査

- 対象URL: https://developingtelecoms.com/telecom-technology/wireless-networks.html
- RSSフィード: `https://developingtelecoms.com/index.php?format=feed&type=rss`（Joomla CMS形式）
- 標準パス（/feed, /rss.xml, /rss）は404
- トップページのHTMLにはRSSリンクタグなし（`<atom:link rel="self">` のみ）

### カバー範囲（直近34件）

- データ鮮度: 直近5日間（1日4〜10件ペース）
- タグ分類: Wireless Networks(6), Operators(5), Data Centres & Networks(4), Regulation(3), Satellite Networks(3), Mobile Finance(3), 他

### 実装内容

1. `src/news_scraper/developing_telecoms.py` 新規作成
2. `src/news_scraper/types.py` に `"developing_telecoms"` を SourceName Literal に追加
3. `src/news_scraper/unified.py` に `_collect_developing_telecoms` 関数＋SOURCE_REGISTRYへの登録
4. `scripts/scrape_finance_news.py` の `--sources` choices に追加
5. `config/launchd/com.note-finance.scrape-developing-telecoms.plist` 作成・登録

### 全文取得の常時有効化

RSSフィードのcontentはスニペット（1〜2文、約100文字）のみ。
`collect_news()` 内で `config.model_copy(update={"include_content": True})` により、
グローバルconfig設定に関わらず常に trafilatura で全文取得する。

実測: 1,900〜5,071文字の本文を取得確認。34件フル取得で約1分。

## 決定事項

1. RSSフィードURLはJoomla形式（`index.php?format=feed&type=rss`）を使用
2. `developing_telecoms` は常時 `include_content=True` でtrafilatura全文取得
3. launchd スケジュール: 0時・6時・12時・18時（他のスクレイパーと統一）

## アクションアイテム

特になし（すべて完了）

## 参考情報

- フィード生成元: Joomla CMS（MYOB generator）
- 言語: en-gb
- 管理者メール: send@developingtelecoms.com
- NAS出力先: `/Volumes/personal_folder/scraped/developing_telecoms/`
- ログ: `logs/scrape-developing-telecoms.log` / `logs/scrape-developing-telecoms-error.log`
