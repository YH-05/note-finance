# news_scraper 自動収集 → 週次レポート連携

**作成日**: 2026-03-01

## Context

週次マーケットレポート (`/generate-market-report --weekly`) のニュースソースを、GitHub Project #15 の Issue 取得から、finance パッケージの `news_scraper` でスクレイピングしたローカル JSON ファイルに切り替える。

**目的**: CNBC/NASDAQ から直接スクレイピングした記事データを使い、より鮮度と網羅性の高いニュースベースでレポートを生成する。

**運用方針**:
- **スクレイピング**: macOS launchd で1日複数回自動実行 → NAS (`/Volumes/personal_folder/`) に保存
- **レポート生成**: Claude Code で任意タイミング実行、または Claude Agent SDK で自動化

**前提**: `finance` パッケージは `uv add "finance @ git+https://github.com/YH-05/finance.git"` でインストール済み。

## アーキテクチャ全体像

```
┌─────────────────────────────────────────────────────┐
│ macOS launchd（1日複数回）                             │
│                                                      │
│ scripts/scrape_finance_news.py                       │
│   └── news_scraper (finance pkg) を呼び出し           │
│       └── CNBC (30カテゴリ) + NASDAQ (14カテゴリ)      │
│           └── /Volumes/personal_folder/finance-news/  │
│               └── {YYYY-MM-DD}/news_{timestamp}.json  │
└──────────────────────┬──────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
        ▼                             ▼
┌───────────────────┐   ┌──────────────────────────┐
│ Claude Code       │   │ Claude Agent SDK          │
│ (手動実行)         │   │ (自動定期実行)             │
│                   │   │                          │
│ /generate-market  │   │ src/automation/           │
│  -report --weekly │   │   weekly_report.py        │
│  --news-json ...  │   │                          │
└───────┬───────────┘   └───────────┬──────────────┘
        │                           │
        └─────────┬─────────────────┘
                  ▼
        convert_scraped_news.py
            ↓ news_from_project.json 互換
        wr-data-aggregator → wr-comment-generator → レポート
        （以降のパイプラインは変更なし）
```

## 実装タスク

### Task 1: スクレイピングスクリプト作成

**ファイル**: `scripts/scrape_finance_news.py`（新規）

macOS launchd から呼び出される自動収集スクリプト。finance パッケージの `news_scraper` を使い、NAS に JSON を保存する。

```bash
# 手動実行
uv run python scripts/scrape_finance_news.py

# 引数指定
uv run python scripts/scrape_finance_news.py \
    --output-dir /Volumes/personal_folder/finance-news \
    --sources cnbc nasdaq \
    --include-content
```

**処理内容**:
1. 出力ディレクトリ作成: `{output_dir}/{YYYY-MM-DD}/`
2. `news_scraper.collect_financial_news()` 呼び出し
3. JSON 保存: `{output_dir}/{YYYY-MM-DD}/news_{HHMMSS}.json`
4. 古いデータのクリーンアップ（30日以上前を削除、オプション）
5. 実行ログ出力（structlog）

**NAS 非マウント時の対応**: NAS がマウントされていない場合はローカルフォールバック (`data/scraped/`) に保存し、警告ログを出力。

### Task 2: launchd 設定ファイル作成

**ファイル**: `config/launchd/com.note-finance.scrape-news.plist`（新規）

```xml
<!-- 6時間ごとに実行（0:00, 6:00, 12:00, 18:00） -->
<key>StartCalendarInterval</key>
<array>
    <dict><key>Hour</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>6</integer></dict>
    <dict><key>Hour</key><integer>12</integer></dict>
    <dict><key>Hour</key><integer>18</integer></dict>
</array>
```

インストール手順もスクリプトのヘッダーコメントに記載:
```bash
cp config/launchd/com.note-finance.scrape-news.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.note-finance.scrape-news.plist
```

### Task 3: 変換スクリプト作成

**ファイル**: `scripts/convert_scraped_news.py`（新規）

news_scraper の出力 JSON を `news_from_project.json` 互換形式に変換する。

```bash
uv run python scripts/convert_scraped_news.py \
    --input /Volumes/personal_folder/finance-news/2026-03-01/news_120000.json \
    --output articles/weekly_report/2026-03-01/data \
    --start 2026-02-22 \
    --end 2026-03-01
```

複数ファイル指定にも対応（1日複数回のスクレイピング結果をマージ）:
```bash
uv run python scripts/convert_scraped_news.py \
    --input-dir /Volumes/personal_folder/finance-news/ \
    --output articles/weekly_report/2026-03-01/data \
    --start 2026-02-22 \
    --end 2026-03-01
```

`--input-dir` 指定時は期間内の全 JSON ファイルを読み込み、URL で重複排除してマージする。

**カテゴリマッピング**:

```python
CATEGORY_MAP: dict[str, str] = {
    # CNBC
    "economy": "macro",
    "finance": "finance",
    "investing": "indices",
    "earnings": "mag7",
    "bonds": "macro",
    "commodities": "sectors",
    "technology": "tech",
    "energy": "sectors",
    "health_care": "sectors",
    "real_estate": "sectors",
    "autos": "sectors",
    "top_news": "indices",
    "business": "finance",
    # NASDAQ
    "Markets": "indices",
    "Earnings": "mag7",
    "Economy": "macro",
    "Commodities": "sectors",
    "Currencies": "macro",
    "Technology": "tech",
    "Stocks": "mag7",
    "ETFs": "sectors",
}
```

マッピングにない場合はタイトルキーワードで判定（wr-news-aggregator.md L94-99 のロジックを流用）。

**フィールドマッピング**:

| scraper | news_from_project | 変換 |
|---------|-------------------|------|
| `title` | `title` | そのまま |
| `url` | `original_url` | そのまま |
| `url` | `url` | そのまま |
| `published` | `created_at` | ISO 8601 パース |
| `summary` | `summary` | そのまま（空なら content[:200]） |
| `source` | `source` | そのまま（"cnbc", "nasdaq"） |
| `category`（マッピング後） | `category` | CATEGORY_MAP で変換 |
| （なし） | `issue_number` | 連番（1, 2, 3...） |

**出力 JSON 構造**: `news_from_project.json` と完全互換。

### Task 4: テスト作成

**ファイル**: `tests/scripts/test_convert_scraped_news.py`（新規）

- `test_正常系_有効なJSONで変換成功`
- `test_正常系_日付フィルタリングが正しく動作`
- `test_正常系_カテゴリマッピングが正しく変換`
- `test_正常系_キーワードフォールバックが動作`
- `test_正常系_by_categoryとstatisticsが正しく生成`
- `test_正常系_複数ファイルマージと重複排除`
- `test_異常系_存在しないファイルでエラー`
- `test_エッジケース_空配列で空の出力`
- `test_エッジケース_summaryが空でcontentフォールバック`

### Task 5: wr-news-aggregator 改修

**ファイル**: `.claude/agents/wr-news-aggregator.md`

入力パラメータに `news_json_path` / `news_json_dir` を追加。指定時は GitHub Project をスキップし、変換スクリプトを実行する。

**追加内容**:
- `news_json_path`: 単一 JSON ファイル指定
- `news_json_dir`: ディレクトリ指定（期間内の全ファイルをマージ）
- パターン A（ローカル JSON）/ パターン B（従来 GitHub Project）の分岐

### Task 6: weekly-report-lead 改修

**ファイル**: `.claude/agents/weekly-report-lead.md`

task-1 起動時のプロンプトに `news_json_path` / `news_json_dir` を条件付きで渡す。

### Task 7: SKILL.md + コマンド定義改修

**ファイル**:
- `.claude/skills/generate-market-report/SKILL.md`
- `.claude/commands/generate-market-report.md`

- `--news-json` パラメータ追加（単一ファイル指定）
- `--news-dir` パラメータ追加（ディレクトリ指定、期間内全ファイルマージ）
- 使用例の追加

### Task 8: Claude Agent SDK 自動化（将来拡張）

**ファイル**: `src/automation/weekly_report.py`（新規、将来）

Claude Agent SDK でレポート生成を自動化するエントリポイント。launchd と組み合わせて完全自動化する。

**スコープ**: 本プランでは設計のみ。実装は Task 1-7 完了後に別途実施。

```python
# 将来の実行イメージ
# launchd: 毎週月曜朝に実行
uv run python -m automation.weekly_report \
    --news-dir /Volumes/personal_folder/finance-news/ \
    --publish
```

## ユーザーの実行フロー

### パターン A: 手動実行

```bash
# スクレイピングは launchd が自動実行済み
# NAS に /Volumes/personal_folder/finance-news/2026-03-01/ が存在

# レポート生成（NAS のディレクトリを指定）
/generate-market-report --weekly --date 2026-03-01 \
    --news-dir /Volumes/personal_folder/finance-news/
```

### パターン B: 従来フロー（後方互換）

```bash
# --news-json / --news-dir を省略すれば GitHub Project から取得
/generate-market-report --weekly --date 2026-03-01
```

### パターン C: 将来の完全自動化

```bash
# Claude Agent SDK + launchd で毎週自動実行（Task 8 実装後）
```

## 実装順序

```
Task 1 (スクレイピングスクリプト)
    ↓
Task 2 (launchd 設定)
    ↓
Task 3 (変換スクリプト) → Task 4 (テスト)
    ↓
Task 5 (wr-news-aggregator 改修) + Task 6 (リーダー改修) + Task 7 (SKILL/コマンド改修)
    ↓
Task 8 (Agent SDK 自動化 - 将来)
```

## 検証方法

1. `make check-all` で品質チェック通過
2. 変換スクリプトの単体テスト通過
3. `scripts/scrape_finance_news.py` を手動実行し、NAS に JSON が保存されることを確認
4. 保存された JSON で `scripts/convert_scraped_news.py` を実行し、出力形式を確認
5. `/generate-market-report --weekly --news-dir` でエンドツーエンド実行
6. launchd 設定をロードし、自動実行されることを確認

## 対象ファイル一覧

| 操作 | ファイル |
|------|---------|
| 新規 | `scripts/scrape_finance_news.py` |
| 新規 | `scripts/convert_scraped_news.py` |
| 新規 | `config/launchd/com.note-finance.scrape-news.plist` |
| 新規 | `tests/scripts/test_convert_scraped_news.py` |
| 変更 | `.claude/agents/wr-news-aggregator.md` |
| 変更 | `.claude/agents/weekly-report-lead.md` |
| 変更 | `.claude/skills/generate-market-report/SKILL.md` |
| 変更 | `.claude/commands/generate-market-report.md` |
| 将来 | `src/automation/weekly_report.py` |

## NAS ストレージ構造

```
/Volumes/personal_folder/finance-news/
├── 2026-02-28/
│   ├── news_000000.json    # 0:00 実行分
│   ├── news_060000.json    # 6:00 実行分
│   ├── news_120000.json    # 12:00 実行分
│   └── news_180000.json    # 18:00 実行分
├── 2026-03-01/
│   ├── news_000000.json
│   └── ...
└── ...
```

`--news-dir` 指定時は `--start` 〜 `--end` の日付フォルダ内の全 JSON を読み込み、URL で重複排除してマージする。
