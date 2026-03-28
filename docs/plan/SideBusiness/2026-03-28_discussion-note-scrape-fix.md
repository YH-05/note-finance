# 議論メモ: note-scrapeスクレイピング修正・launchd定期実行設定

**日付**: 2026-03-28
**参加**: ユーザー + AI

## 背景・コンテキスト

`/note-scrape` で hide_taxnote（110件以上の記事）をスクレイピングしたところ、19件しか検出されなかった。全記事を確実に取得できるようにコードを修正し、併せて launchd による定期実行を設定した。

## 議論のサマリー

### 問題1: プロフィールホームページの限界
- `https://note.com/{username}` は一部の記事のみ表示（hide_taxnote: 37/114件）
- `https://note.com/{username}/all`（「記事」タブ）で全記事が表示される

### 問題2: 非表示ボタンの選択
- note.com は DOM に複数の「もっとみる」ボタンを配置（3つ）
- Playwright の `locator.first` が非表示の1つ目を選択 → タイムアウト
- JS で `offsetParent !== null` の表示中ボタンのみをターゲットする方式に変更

### 問題3: max_pages 上限
- ハードコードの `max_pages=10` では記事数が多いクリエイターで不足
- 上限を撤廃し、`wait_for_function` で DOM 更新を検知、2回連続増加なしで自動停止

### launchd 定期実行
- `com.note-finance.note-com-monitor.plist` を作成
- 毎日 8:00 / 20:00 に `data_pipeline note-com monitor` を実行
- RawStore（NAS: `/Volumes/personal_folder/raw_texts`）への保存のみ
- uv パス: `/Users/yuki/.local/bin/uv`

## 決定事項

1. 記事一覧 URL を `/{username}` → `/{username}/all` に変更
2. 「もっとみる」ボタンのクリックを JS 直接実行に変更（表示中ボタンのみ対象）
3. max_pages 上限を撤廃（ボタンが消えるまで自動全取得）
4. note-com RSSモニターを launchd（8:00/20:00）で定期実行、RawStore保存のみ

## 実績データ

| 項目 | 値 |
|------|-----|
| hide_taxnote 全記事取得 | 114件（修正前: 19件） |
| RawStore 保存 | 109件（無料記事、有料5件スキップ） |
| research-neo4j 投入 | 2,652ノード / 414,727リレーション |
| launchd 初回実行 | 11クリエイター / 126件保存 |

## 変更ファイル

- `src/data_pipeline/collectors/note_com_browser.py` — /all ページ使用、JS ボタンクリック、上限撤廃
- `src/data_pipeline/collectors/note_com.py` — max_pages 引数削除
- `src/data_pipeline/__main__.py` — max_pages ハードコード削除
- `config/launchd/com.note-finance.note-com-monitor.plist` — 新規作成
