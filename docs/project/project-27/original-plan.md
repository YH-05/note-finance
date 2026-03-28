# SNS 自動投稿スクリプト設計

## Context

みつき（@mitsuki_fortune）とキャリアお姉さん（@career_sister）の SNS 投稿は現在すべて手動（Claude Code の `/mitsuki-publish`、`/career-sister-publish` コマンド）で行っている。毎日 5+3=8 スロットを手動投稿するのは運用コストが高く、MacBook Pro を常時操作する必要がある。

Mac Mini からも launchd で自動投稿できる `scripts/auto_poster.py` を作成し、Threads / Instagram / note.com への投稿を自動化する。

## 新規作成ファイル

| ファイル | 説明 |
|---------|------|
| `scripts/auto_poster.py` | 自動投稿スクリプト本体 |
| `config/launchd/com.note-finance.auto-poster.plist` | launchd 定期実行設定 |

## 既存ファイルの再利用

| ファイル | 使い方 |
|---------|--------|
| `src/creator/poster.py` | `ThreadsPoster` / `InstagramPoster` クラスを直接 import |
| `src/creator/image_hosting.py` | `R2ImageHost.upload_batch()` で Instagram カルーセル画像を R2 にアップロード |
| `config/launchd/com.note-finance.scrape-news.plist` | plist テンプレートとして踏襲 |

---

## Step 1: `scripts/auto_poster.py` の構造

```
auto_poster.py
 ├── AutoPosterConfig       # CLI引数 → 設定 dataclass
 ├── SlotMatcher            # 現在時刻 ↔ スロット時刻マッチング
 ├── DraftReader            # meta.json 読み込み + 投稿ファイル読み込み
 ├── AccountPoster          # アカウント別投稿実行
 ├── StateUpdater           # meta.json / posting_state.json 更新
 └── main()                 # CLI エントリーポイント
```

### CLI

```bash
uv run python scripts/auto_poster.py                      # 全アカウント、現在時刻基準
uv run python scripts/auto_poster.py --dry-run             # 投稿せず対象表示
uv run python scripts/auto_poster.py --account mitsuki     # 特定アカウントのみ
uv run python scripts/auto_poster.py --include-note        # note.com 投稿も含める
uv run python scripts/auto_poster.py --force-slot S1       # 時刻無視で特定スロット投稿
uv run python scripts/auto_poster.py --tolerance 30        # 時刻許容範囲（分、デフォルト15）
uv run python scripts/auto_poster.py --week 2026-03-31     # 特定週を指定
```

### 処理フロー

```
1. CLI引数パース → AutoPosterConfig
2. load_dotenv() で .env 読み込み
3. for account in [mitsuki, career_sister]:
   a. creator/{account}/drafts/ から現在週のディレクトリ検出
   b. meta.json ロード
   c. 今日の日付に該当する day データ取得
   d. SlotMatcher で現在時刻 ±tolerance にマッチするスロット抽出
      → posted_at/status が既セットのスロットはスキップ（冪等性）
   e. --dry-run なら対象一覧表示して終了
   f. AccountPoster 初期化（get_account_info() でアカウント確認）
   g. 各スロットについて:
      - 投稿ファイル読み込み
      - Threads 投稿（全スロット）
      - Instagram 投稿（career_sister の instagram: true スロットのみ）
      - meta.json 更新（posted_at, permalink）
      - posting_state.json 更新（post_history 追記）
   h. --include-note なら note.com 投稿（mitsuki のみ）
   i. 全スロット投稿済みなら status を published に更新
4. 結果サマリー出力
```

### アカウント間の差異への対応

| 項目 | mitsuki | career_sister |
|------|---------|---------------|
| スロット時刻 | meta.json の `time` フィールドから取得 | スロット名→時刻マップ: 朝=07:30, 昼=12:30, 夜=20:30 |
| 投稿ファイルパス | meta.json の `file` フィールドから取得 | ディレクトリ規則: `day_{N}_{eng}/slot_{M}_{period}/threads_post.md` |
| topic_tag | フロントマターから抽出（あれば） | なし |
| Instagram | なし | `instagram: true` のスロットでカルーセル投稿 |
| Instagram 画像 | - | `carousel/slide_*.png` を R2 アップロード |
| 投稿済みフラグ | `posted_at != null` | `status == "published"` |
| note.com | `note` フィールドの `note_article.md` | なし |

ディレクトリ名マッピング:

```python
DAY_DIR_MAP = {"月": "mon", "火": "tue", "水": "wed", "木": "thu", "金": "fri", "土": "sat", "日": "sun"}
SLOT_DIR_MAP = {"朝": "slot_1_morning", "昼": "slot_2_noon", "夜": "slot_3_evening"}
SLOT_TIME_MAP = {"朝": "07:30", "昼": "12:30", "夜": "20:30"}
```

### リトライ戦略

- **リトライ対象**: HTTP 429/500/502/503/504、ConnectError、TimeoutError
- **リトライしない**: 400/401/403（設定ミス）、container FAILED（コンテンツエラー）
- **パラメータ**: max 3回、指数バックオフ（5s → 20s → 80s）
- **実装**: tenacity ライブラリ（既存依存）

### 重複投稿防止（3層）

1. **meta.json チェック**: `posted_at != null` / `status == "published"` → スキップ
2. **ファイルロック**: `filelock` で meta.json 排他制御
3. **投稿直前の再読み込み**: 投稿直前に meta.json を再チェック

### ロギング

```python
from utils_core.logging.config import get_logger
logger = get_logger(__name__)
```

- ログファイル: `logs/auto_poster.jsonl`（JSON Lines 形式、append）
- launchd stdout: `logs/auto-poster.log`

---

## Step 2: launchd plist

保存先: `config/launchd/com.note-finance.auto-poster.plist`

既存の `com.note-finance.scrape-news.plist` と同じパターンで、`StartCalendarInterval` に全8スロット時刻を登録:

```
07:00 (mitsuki S1)
07:30 (career_sister 朝)
12:00 (mitsuki S2)
12:30 (career_sister 昼)
15:00 (mitsuki S3)
19:00 (mitsuki S4)
20:30 (career_sister 夜)
22:00 (mitsuki S5)
```

auto_poster.py は内部で時刻マッチングを行うため、毎回全アカウントを走査してマッチするスロットだけ投稿する。マッチなしなら何もせず終了。

Mac Mini 用の差分は `WorkingDirectory` と `ProgramArguments[0]`（uv パス）のみ。

---

## Step 3: マルチマシン対応

- **重複防止**: NAS 上にロックファイル `/Volumes/personal_folder/Projects/note-finance/.auto_poster_lock` を配置。`filelock` で取得できなければスキップ。NAS 未マウント時はローカルロックにフォールバック
- **drafts 同期**: `scripts/sync_nas.sh` の対象に `creator/*/drafts/` と `creator/*/posting_state.json` を追加。投稿前に `--pull`、投稿後に `--push`
- **plist テンプレート化**: `YOUR_USERNAME` プレースホルダ方式を踏襲（既存 plist と同じ）

---

## Step 4: note.com 投稿

- デフォルト OFF（`--include-note` で有効化）
- mitsuki のみ（career_sister は note.com 投稿なし）
- subprocess で `scripts/publish_to_note.py` を呼び出し
- `NOTE_HEADLESS=true` 環境変数で headless Playwright 実行
- 将来的に `publish_to_note.py` に `--creator-mode` を追加し、`note_article.md` を直接受け取れるようにする

---

## 検証方法

### 1. ドライランテスト
```bash
# mitsuki の現在時刻スロットを確認
uv run python scripts/auto_poster.py --dry-run --account mitsuki

# career_sister の全スロットを強制表示
uv run python scripts/auto_poster.py --dry-run --account career_sister --tolerance 1440
```

### 2. 単一スロット投稿テスト
```bash
# mitsuki S1 を強制投稿
uv run python scripts/auto_poster.py --account mitsuki --force-slot S1

# meta.json が更新されたか確認
cat creator/mitsuki/drafts/week_2026-03-31/meta.json | python -m json.tool | grep posted_at
```

### 3. 冪等性テスト
```bash
# 同じスロットを2回実行 → 2回目はスキップされるべき
uv run python scripts/auto_poster.py --account mitsuki --force-slot S1
uv run python scripts/auto_poster.py --account mitsuki --force-slot S1
# → "post_skipped: already_posted" ログが出ること
```

### 4. launchd テスト
```bash
cp config/launchd/com.note-finance.auto-poster.plist ~/Library/LaunchAgents/
# パスを書き換え後:
launchctl load ~/Library/LaunchAgents/com.note-finance.auto-poster.plist
launchctl start com.note-finance.auto-poster
tail -f logs/auto-poster.log
```

---

## 実装順序

1. `auto_poster.py` 基本構造（CLI, Config, SlotMatcher, DraftReader）
2. mitsuki Threads 投稿 + meta.json 更新
3. career_sister Threads 投稿（ディレクトリ構造差異対応）
4. career_sister Instagram 投稿（R2 アップロード + カルーセル）
5. `--dry-run`、`--force-slot` 実装
6. リトライ + エラーハンドリング
7. launchd plist 作成
8. posting_state.json 更新
9. マルチマシンロック
10. note.com 投稿（`--include-note`）
