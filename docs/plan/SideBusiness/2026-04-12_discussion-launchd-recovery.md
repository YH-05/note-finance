# 議論メモ: launchd定期実行ジョブの復旧作業

**日付**: 2026-04-12
**参加**: ユーザー + AI

## 背景・コンテキスト

4/10の調査（disc-2026-04-10-rss-scraping-stopped）で、4/1以降全スクレイピングが停止していることが判明。
原因として `~/Library/LaunchAgents/` へのplist未登録、パス不一致、CNBC plist欠如の3点が挙げられていた。
今回、復旧作業を実施した。

## 調査結果: exit 126 の原因

### 現象
- `launchctl list` で全 scrape-* ジョブが exit 126
- 手動実行（ターミナル）では問題なく動作
- plistのパス設定（`/Users/yuki/...`）は正しい

### 原因特定プロセス
1. デバッグ用 plist を作成し、launchd 環境からの実行情報を `/tmp/launchd-debug.log` に出力
2. 決定的な出力:
   ```
   PWD=
   job-working-directory: error retrieving current directory: getcwd: cannot access parent directories: Operation not permitted
   ```

### 根本原因
**macOS プライバシー保護が `Desktop` ディレクトリへの `getcwd()` をブロック**

- launchd から `/bin/bash` を起動する際、`WorkingDirectory` に設定された `/Users/yuki/Desktop/note-finance` で `getcwd()` システムコールが失敗
- `uv run python scripts/scrape_finance_news.py` が相対パス解決に失敗し exit 126
- ターミナルからは Terminal.app がフルディスクアクセスを持つため問題が発生しない

### 修正
システム設定 → プライバシーとセキュリティ → フルディスクアクセス → `/bin/bash` を追加

## 実施した作業

### 1. フルディスクアクセス付与 → exit 126 解消
- `/bin/bash` をフルディスクアクセスに追加
- `scrape-jetro`: launchctl start → 50記事取得成功、exit 0
- `scrape-ars-technica`: launchctl start → exit 0

### 2. CNBC plist 新規作成
- `config/launchd/com.note-finance.scrape-cnbc.plist` を作成
- scrape-wrapper.sh 経由、6時間ごと（0/6/12/18時）
- `~/Library/LaunchAgents/` にコピー・登録
- launchctl start → CNBC記事取得成功

### 3. kuroto-area, mitsuki のlaunchctl登録
- plistは `~/Library/LaunchAgents/` に存在していたが `launchctl load` されていなかった
- 両方とも `launchctl load` で登録完了

### 4. 既存ジョブのリロード
- exit 126 のまま残っていた8ジョブを `unload` → `load` でリセット

## 最終状態: 全16ジョブ

| # | Label | 用途 | exit code |
|---|-------|------|-----------|
| 1 | scrape-ars-technica | RSSスクレイピング | 0 |
| 2 | scrape-cnbc | RSSスクレイピング（新規） | 0 |
| 3 | scrape-developing-telecoms | RSSスクレイピング | 0 |
| 4 | scrape-federal-reserve | RSSスクレイピング | 0 |
| 5 | scrape-hacker-news | RSSスクレイピング | 0 |
| 6 | scrape-jetro | JETROスクレイピング | 0 |
| 7 | scrape-kabutan | RSSスクレイピング | 0 |
| 8 | scrape-reuters-jp | RSSスクレイピング | 0 |
| 9 | scrape-techcrunch | RSSスクレイピング | 0 |
| 10 | scrape-the-verge | RSSスクレイピング | 0 |
| 11 | scrape-zero-hedge | RSSスクレイピング | 0 |
| 12 | auto-poster-career-sister | SNS自動投稿 | 0 |
| 13 | auto-poster-kuroto-area | SNS自動投稿 | 0 |
| 14 | auto-poster-mitsuki | SNS自動投稿 | 0 |
| 15 | note-com-monitor | note.comモニタリング | 0 |
| 16 | pipeline-scraped-to-neo4j | スクレイプ→Neo4j投入 | 0 |

## 決定事項

1. **フルディスクアクセスで対応**: `/bin/bash` にフルディスクアクセスを付与（プロジェクト移動は不要）
2. **CNBC個別plist新規作成**: 6時間ごとスケジュール、wrapper方式
3. **4/10の復旧保留Decision（dec-2026-04-10-defer-recovery）を superseded に更新**

## アクションアイテム

- [ ] Macスリープ中のStartCalendarIntervalスキップ対策（pmset/StartInterval/常時起動）(優先度: 中)
- [ ] 4/2〜4/11の欠落データのバックフィル運用方針決定・実行 (優先度: 中)
- [ ] scripts/SCHEDULED_JOBS.md を全16ジョブの最新状態に更新 (優先度: 低)

## 次回の議論トピック

- バックフィル実施（特にCNBCは3/28以降の欠落）
- スリープ対策の方針決定
- SCHEDULED_JOBS.md の包括的更新

## 関連ファイル

| ファイル | 役割 |
|---------|------|
| `config/launchd/com.note-finance.scrape-cnbc.plist` | CNBC plist（新規作成） |
| `scripts/scrape-wrapper.sh` | 全scrape-*の共通ラッパー |
| `docs/plan/SideBusiness/2026-04-10_discussion-rss-scraping-stopped-investigation.md` | 前回調査 |
