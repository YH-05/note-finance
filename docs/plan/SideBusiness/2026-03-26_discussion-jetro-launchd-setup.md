# 議論メモ: JETRO 日次蓄積 & launchd 定期実行セットアップ

**日付**: 2026-03-26
**参加**: ユーザー + AI

## 背景・コンテキスト

前回（disc-2026-03-23-jetro-scraping-test）の「次回の議論トピック」であった launchd 定期実行の検討を実施。
JETRO スクレイパーの日次蓄積運用に向けた設計と、macOS launchd セットアップ手順を整理した。

## 議論のサマリー

### 1. JETRO スクレイピングコード確認

コードの全体像を再確認:

| ファイル | 役割 |
|---|---|
| `scripts/scrape_jetro.py` | CLI エントリーポイント |
| `src/news_scraper/jetro.py` | コアロジック（collect_news 3フェーズ） |
| `src/news_scraper/_jetro_crawler.py` | Playwright ベースクローラー |
| `src/news_scraper/_jetro_config.py` | RSS URL・CSS セレクター設定 |

`collect_news()` の3フェーズ:
- Phase 1: RSS（ビジネス短信 / 地域・分析レポート / 調査レポート）
- Phase 2: Playwright カテゴリページ（`--categories` 指定時）
- Phase 3: アーカイブページ（`--archive-pages N` 指定時）

### 2. 日次蓄積の設計

**RSS-only モード（`--no-playwright`）が最適**と決定。理由:

- RSS フィードは設計上「最新N件のみ」を返すため、毎日実行すれば新着記事のみが自然に蓄積
- `--archive-pages` は歴史的バックフィル用（日次蓄積には不要）
- NAS 未マウント時はローカル（`data/scraped/jetro/`）へ自動フォールバック

**制約（現状）**: クロスラン重複除去は未実装。同じ記事が翌日 RSS に残っていれば重複保存される。後工程で URL キーで排除が必要。

推奨コマンド:
```bash
uv run python scripts/scrape_jetro.py --no-playwright --cleanup-days 30
```

### 3. macOS launchd セットアップ（2026-03-26 完了）

`~/Library/LaunchAgents/` に plist を配置する方式を採用。

**2026-03-26 実施内容**:
- ユーザーリクエストにより スケジュールを **毎日 03:00 / 21:00 JST** に変更
- `~/Library/LaunchAgents/com.note-finance.scrape-jetro.plist` を作成・登録
- `launchctl list | grep scrape-jetro` で待機中（PID=`-`, exitCode=`0`）を確認

登録コマンド:
```bash
launchctl load ~/Library/LaunchAgents/com.note-finance.scrape-jetro.plist
launchctl start com.note-finance.scrape-jetro  # 即時テスト
```

スケジュール: **毎日 03:00 / 21:00 JST**（`StartCalendarInterval` を `<array>` で2エントリ設定）
ログ: `logs/scrape_jetro.log` / `logs/scrape_jetro_error.log`

### 4. launchd vs cron の整理

| 項目 | launchd | cron |
|---|---|---|
| macOS での位置づけ | 推奨・公式 | 非推奨（動くが） |
| スリープ中の挙動 | スキップ（同じ） | スキップ |
| プロセス監視・再起動 | ✅ KeepAlive | ❌ |
| macOS 権限対応 | ✅ 安定 | ⚠️ 制限あり |
| 設定の簡潔さ | XML plist | 1行テキスト |

JETRO スクレイパーは launchd を採用（NAS マウント確認・macOS 権限の安定性が理由）。

### 5. SCHEDULED_JOBS.md 作成

`scripts/SCHEDULED_JOBS.md` を新規作成。内容:
- 登録済みジョブ一覧（ステータス付き）
- 各ジョブの詳細（スクリプト・スケジュール・ログ先）
- セットアップ手順（plist の cat コマンドで一発作成）
- 管理コマンドリファレンス

## 決定事項

1. **日次蓄積は RSS-only モード**: `--no-playwright` + `--cleanup-days 30` を標準コマンドとする
2. **定期実行は launchd**: スケジュール **毎日 03:00 / 21:00 JST**、plist を `~/Library/LaunchAgents/` に配置
3. **定期実行ドキュメント管理**: `scripts/SCHEDULED_JOBS.md` を新設し、全ジョブを一元管理
4. **パスは `/Users/yuki/`**: ドキュメント記載の `yukihata` は誤り、実際のユーザー名は `yuki`

## アクションアイテム

- [x] `com.note-finance.scrape-jetro.plist` を `~/Library/LaunchAgents/` に実際に配置・登録 (完了: 2026-03-26)
- [x] launchd 登録後に `launchctl list` で待機状態を確認 (完了: 2026-03-26)
- [ ] 21:00 または翌 03:00 の自動実行後にログ確認 `tail logs/scrape_jetro.log` (優先度: 高)
- [ ] クロスラン重複排除ロジックの検討（URL キーによるフィルタリング） (優先度: 中)
- [ ] archive_pages モードの実運用テスト（前回からの持ち越し） (優先度: 中)

## 次回の議論トピック

- 自動実行後のログ確認・動作検証
- 日本株ニュース HTML スクレイパー計画への着手判断（複数回持ち越し）
- クロスラン重複排除の実装方針

## 参考情報

- 前回 JETRO 議論: `disc-2026-03-23-jetro-scraping-test`
- 定期実行ドキュメント: `scripts/SCHEDULED_JOBS.md`
