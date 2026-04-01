# 議論メモ: RSSスクレイピング ログ二重出力対応

**日付**: 2026-04-01
**参加**: ユーザー + AI

## 背景・コンテキスト

RSSスクレイピングの定期実行状況を確認し、ログをローカルだけでなくNASにも出力するよう改善した。

## 作業内容

### 1. スクレイピング稼働状況の確認

全9ソースが正常動作していることを確認（12:00時点）:

| ソース | 記事数 |
|--------|--------|
| ars_technica | 20件 |
| developing_telecoms | 34件 |
| federal_reserve | 20件 |
| hacker_news | 20件 |
| kabutan | 15件 |
| reuters_jp | 23件 |
| techcrunch | 20件 |
| the_verge | 10件 |
| zero_hedge | 25件 |

スケジューラ: macOS LaunchAgent（`~/Library/LaunchAgents/com.note-finance.scrape-*.plist`）
実行頻度: 1日4回（0:00, 6:00, 12:00, 18:00）、jetroは2回（3:00, 21:00）

### 2. ログ出力先の特定

変更前:
- LaunchAgentの `StandardOutPath` / `StandardErrorPath` でローカルのみ出力
- ローカル: `logs/scrape-{source}.log` / `logs/scrape-{source}-error.log`

### 3. ログ二重出力の実装

**方針**: LaunchAgentは `StandardOutPath` を1箇所しか指定できないため、
`tee` を使うラッパースクリプトを作成し、両方に追記する方式を採用。

**作成ファイル**:
- `scripts/scrape-wrapper.sh` — tee で stdout/stderr を両出力先に追記
  - NAS未マウント時はローカルのみにフォールバック
  - NASログディレクトリ: `/Volumes/personal_folder/logs/`

**変更ファイル**:
- 全10個のLaunchAgent plist を `ProgramArguments` 経由でラッパー呼び出しに変更
  - `StandardOutPath` / `StandardErrorPath` を削除（ラッパー内でtee管理）

## 決定事項

1. ログ出力先をローカル+NAS二重出力に統一
2. ラッパースクリプト方式（`scripts/scrape-wrapper.sh`）を採用
3. NASログパス: `/Volumes/personal_folder/logs/scrape-{source}.log`

## アクションアイテム

- [ ] ログローテーションの検討（現在ファイルが追記のみで肥大化中）(優先度: 低)

## 検証結果

the_verge を手動実行し、両方の出力先にログが書き込まれることを確認済み。
