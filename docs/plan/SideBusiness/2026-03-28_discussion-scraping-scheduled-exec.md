# 議論メモ: スクレイピング定期実行の進捗確認・JETRO対応

**日付**: 2026-03-28
**参加**: ユーザー + AI

## 背景・コンテキスト

スクレイピング定期実行の実装進捗を確認し、JETROスクレイパーの残課題を片付けるセッション。
前回（2026-03-26）の「次回の議論トピック」（自動実行後のログ確認・launchd動作検証）を実施した。

## 議論のサマリー

### 1. JETRO launchd 動作確認

- `launchctl list | grep scrape-jetro` → exitCode=0、正常待機中
- 2026-03-26 21:30: `news_213630.json` 100件保存（NAS）
- 2026-03-27 12:00: `news_120005.json` 100件保存（NAS）
- 2026-03-27 18:00: `news_180006.json` 100件保存（NAS）
- エラーなし、NAS自動マウント確認も正常

### 2. archive_pages モードの位置づけ確認

- 日次定期実行には使わない（RSS-only で十分）
- 過去データのバックフィルが必要なときのみ手動実行
- CLIは整備済みで追加実装不要

### 3. 本文取得が無効だった問題の発見と修正

- スクレイプ結果を確認したところ `summary=None`, `content=None`
- 原因: plist に `--include-content` フラグが未指定だったため `include_content=False`（デフォルト）で実行されていた
- JETROのRSS feed 自体が `description` を空で返すため summary も取れない
- 修正: plist に `--include-content` を追加 → launchctl unload/load で再読み込み済み

### 4. クロスラン重複排除の方針

- 同じ記事が複数JSONファイルに重複保存されている（3/26は17ファイル）
- JETRO だけでなく cnbc / reuters_jp / kabutan / nasdaq など全RSSスクレイパーに共通の課題
- 全スクレイパーが同一スキーマ（`url` キーで一意）を使用していることを確認済み
- 独立した定期実行スクリプト `scripts/dedup_scraped.py` として実装予定
- **着手タイミング**: 他のRSSスクレイパーの定期実行整備が完了してから

## 決定事項

1. **archive_pages は手動バックフィル用**: 日次launchd実行には組み込まない。CLIは整備済みで追加実装不要。
2. **plistに `--include-content` 追加**: 2026-03-28 修正・再読み込み済み。次回03:00から本文取得が有効になる。
3. **重複排除は `scripts/dedup_scraped.py` として独立実装**: 他RSSスクレイパーの定期実行を整備してからまとめて対応。

## アクションアイテム

- [ ] 次回 03:00 実行後にログ確認（本文取得が正常に動いているか） (優先度: 高)
- [ ] 金融ニューススクレイピング（`scrape_finance_news.py`）のlaunchd登録 (優先度: 高)
- [ ] `scripts/dedup_scraped.py` 実装（他RSSスクレイパー整備後） (優先度: 中)

## 次回の議論トピック

- 金融ニューススクレイピング (`scrape_finance_news.py`) のlaunchd登録
- Mac Mini 側での `--skip-neo4j` 実行環境セットアップ
- `ingest_graph_queue.py` のメインマシン定期実行設定

## 参考情報

- JETRO plist: `~/Library/LaunchAgents/com.note-finance.scrape-jetro.plist`
- 定期実行管理: `scripts/SCHEDULED_JOBS.md`
- 対象NASパス: `/Volumes/personal_folder/scraped/{source}/`
- 共通スキーマ確認済みソース: jetro / cnbc / reuters_jp / kabutan / nasdaq
