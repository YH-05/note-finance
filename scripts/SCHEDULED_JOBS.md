# 定期実行ジョブ管理

macOS launchd による定期実行スクリプトの一覧と設定手順。

---

## 登録済みジョブ一覧

| Label | スクリプト | スケジュール | ステータス |
|---|---|---|---|
| `com.finance.news-collector` | `collect-news.sh` | 毎朝 7:00 | テンプレート（未登録） |
| `com.note-finance.scrape-jetro` | `scrape_jetro.py` | 毎日 03:00 / 21:00 JST | 登録済み |

> **登録状態の確認**: `launchctl list | grep com.note-finance`

---

## ジョブ詳細

### 1. 金融ニュース収集 `com.finance.news-collector`

- **スクリプト**: `scripts/collect-news.sh`
- **plist テンプレート**: `scripts/com.finance.news-collector.plist`
- **スケジュール**: 毎日 7:00
- **ログ**: `logs/news-collector.log` / `logs/news-collector-error.log`
- **備考**: `automation.news_collector` モジュールを呼び出す

### 2. JETRO スクレイピング `com.note-finance.scrape-jetro`

- **スクリプト**: `scripts/scrape_jetro.py`
- **plist テンプレート**: 下記参照
- **スケジュール**: 毎日 03:00 / 21:00 JST
- **ログ**: `logs/scrape_jetro.log` / `logs/scrape_jetro_error.log`
- **出力先**: NAS `/Volumes/personal_folder/scraped/jetro/` → ローカル `data/scraped/jetro/`（NAS未マウント時）

---

## セットアップ手順

### 共通前提

```bash
# uvのパスを確認（plist に記載するフルパスが必要）
which uv

# ログディレクトリを作成
mkdir -p ~/Desktop/note-finance/logs
```

### JETRO スクレイパーの登録

**1. plist ファイルを作成**

```bash
cat > ~/Library/LaunchAgents/com.note-finance.scrape-jetro.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.note-finance.scrape-jetro</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Users/yukihata/.local/bin/uv</string>
        <string>run</string>
        <string>python</string>
        <string>/Users/yukihata/Desktop/note-finance/scripts/scrape_jetro.py</string>
        <string>--no-playwright</string>
        <string>--cleanup-days</string>
        <string>30</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/yukihata/Desktop/note-finance</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/Users/yukihata/.local/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>/Users/yukihata/Desktop/note-finance/logs/scrape_jetro.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/yukihata/Desktop/note-finance/logs/scrape_jetro_error.log</string>

    <key>RunAtLoad</key>
    <false/>

    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
EOF
```

**2. 登録・テスト**

```bash
# 登録
launchctl load ~/Library/LaunchAgents/com.note-finance.scrape-jetro.plist

# 即時テスト実行
launchctl start com.note-finance.scrape-jetro

# 登録確認（PID欄に数値があれば実行中）
launchctl list | grep scrape-jetro

# ログ確認
tail -f ~/Desktop/note-finance/logs/scrape_jetro.log
```

---

## 管理コマンドリファレンス

```bash
# 登録
launchctl load   ~/Library/LaunchAgents/<label>.plist

# 解除
launchctl unload ~/Library/LaunchAgents/<label>.plist

# 手動実行
launchctl start <label>

# 強制停止
launchctl stop <label>

# plist 変更後の再読み込み
launchctl unload ~/Library/LaunchAgents/<label>.plist
launchctl load   ~/Library/LaunchAgents/<label>.plist

# 全 LaunchAgent の状態確認
launchctl list | grep com.note-finance
```

---

## 注意事項

- **スリープ中はスキップ**: `StartCalendarInterval` は指定時刻に PC が起動していないと実行されない
- **NAS 依存**: JETRO スクレイパーは NAS 未マウント時にローカルへフォールバックする（`data/scraped/jetro/`）
- **uv のフルパス**: launchd は `$PATH` を引き継がないため plist に絶対パスで記載すること
- **ログローテーション**: `--cleanup-days 30` で出力 JSON を自動削除するが、ログファイル自体は手動管理
