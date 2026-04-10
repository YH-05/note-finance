# 議論メモ: RSSスクレイピング停止の原因調査

**日付**: 2026-04-10
**参加**: ユーザー + AI

## 背景・コンテキスト

NASに保存されているRSSスクレイピングデータの最新日付がCNBCを除く全ソースで2026-04-01、CNBCのみ2026-03-28で止まっていることを発見。
定期実行（launchd）で動いていたはずだが、なぜ停止したかを調査した。

## 調査結果

### 各ソースの最新スクレイピング日付

| ソース | 最終データ日付 |
|---|---|
| ars_technica | 2026-04-01 |
| cnbc | **2026-03-28** ← 早期停止 |
| federal_reserve | 2026-04-01 |
| hacker_news | 2026-04-01 |
| jetro | 2026-03-31 |
| kabutan | 2026-04-01 |
| reuters_jp | 2026-04-01 |
| techcrunch | 2026-04-01 |
| the_verge | 2026-04-01 |
| zero_hedge | 2026-04-01 |

### ローカルログの最終更新時刻

`logs/scrape-*.log` 9個すべてが **Apr 1 14:16:54 JST に同一秒で停止**。最終データ保存は同日 12:00:06 JST（NAS出力時刻）。
各ソースのスクレイピング自体は最後まで成功していた（`saved=20, dup=0, empty=0`、エラーなし）。

### マシン再起動履歴

```
reboot time    Sat Apr  4 18:28
shutdown time  Sat Apr  4 17:54
reboot time    Tue Mar 31 20:15
reboot time    Sat Mar 28 09:25
```

4/4 17:54 にshutdown、18:28 reboot されている。

### LaunchAgents の状態

| 確認項目 | 結果 |
|---|---|
| `~/Library/LaunchAgents/scrape-*` | **存在しない（0件）** |
| `launchctl list \| grep note-finance` | **該当なし** |
| `config/launchd/scrape-*.plist` | プロジェクト内に10個存在（テンプレート） |
| plist内の `WorkingDirectory` | `/Users/yuki/Desktop/note-finance`（このマシンは `yukihata`） |
| plist内の Python パス | `/Users/yuki/Desktop/note-finance/.venv/lib/python3.14/...` |

## 原因まとめ

1. **直接原因**: 4/1 14:16:54 を最後に launchd ジョブが一度も実行されていない
2. **根本原因（推定）**:
   - 4/4 のマシン shutdown/reboot で launchd ジョブが unload された
   - もしくはそもそも `~/Library/LaunchAgents/` には正式に登録されていなかった可能性
   - plist内のパスが `/Users/yuki/...` のまま（このマシンに修正コピーされていない）→ 動いていたとしても別ユーザー名前空間
3. **CNBC の早期停止**:
   - 個別の `scrape-cnbc.plist` が存在しない
   - CNBCは旧一括ジョブ `scrape-news.plist`（3/29 で運用停止）でしか拾われていなかった
   - 個別ジョブ運用に移行した3/29以降、CNBCだけ取り残されていた

## 決定事項

1. **復旧作業は今回は保留**（ユーザー指示）
2. 調査結果はnote-neo4jとSideBusinessドキュメントに保存し、後日復旧時に参照

## 今後のアクションアイテム（復旧時）

- [ ] `config/launchd/com.note-finance.scrape-*.plist` 10個の WorkingDirectory・Python パスを `/Users/yukihata/...` に修正（優先度: 高）
- [ ] CNBC 用 plist (`com.note-finance.scrape-cnbc.plist`) を新規作成（優先度: 高）
- [ ] 修正済 plist を `~/Library/LaunchAgents/` にコピーして `launchctl bootstrap gui/$UID ...` で全件ロード（優先度: 高）
- [ ] `launchctl list | grep note-finance` で登録確認（優先度: 中）
- [ ] Mac スリープ中の launchd skip 対策（`pmset` wake schedule もしくは `StartInterval` 併用）（優先度: 中）
- [ ] 復旧後、4/2〜4/9の欠落データをカバーするバックフィル運用方針を決定（優先度: 中）

## 関連ファイル

| ファイル | 役割 |
|---------|------|
| `scripts/scrape_finance_news.py` | スクレイパー本体 |
| `config/launchd/com.note-finance.scrape-*.plist` | launchd ジョブ定義（テンプレート、要修正） |
| `logs/scrape-*.log` | 各ソースのスクレイピングログ（最終 4/1 14:16:54） |
| `/Volumes/personal_folder/scraped/{source}/` | NAS スクレイピング結果保存先 |

## 参考: 前回の議論

- `2026-04-10_discussion-rss-neo4j-pipeline-fix.md` — RSS→Neo4jパイプライン修正・バックフィル投入完了
