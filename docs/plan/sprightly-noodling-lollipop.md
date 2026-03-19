# YouTube Transcript Collector 実装計画

## Context

指定した YouTube チャンネルの全動画トランスクリプトを自動収集するシステムを構築する。
ウォッチ対象チャンネルを登録し、過去の全動画＋今後の新着動画のトランスクリプトを取得・蓄積する。

**技術選定の背景**:
- YouTube Data API v3 でチャンネルの動画一覧を取得（公式API、`playlistItems.list` で quota 効率的）
- `youtube-transcript-api` で生トランスクリプトを取得（忠実な原文、タイムスタンプ付き）
- NotebookLM CLI は大量処理に不向き（ソース上限50/notebook、ブラウザ操作で低速、AI要約であり生テキストではない）

## Phase 1: MVP（コア機能）

### 1.1 パッケージ構造

```
src/youtube_transcript/
├── __init__.py
├── py.typed
├── types.py                # データ型定義
├── exceptions.py           # 例外階層
├── _logging.py             # structlog 初期化
├── core/
│   ├── __init__.py
│   ├── channel_fetcher.py  # YouTube Data API v3 ラッパー
│   ├── transcript_fetcher.py  # youtube-transcript-api ラッパー
│   └── diff_detector.py    # 新着動画検出
├── storage/
│   ├── __init__.py
│   └── json_storage.py     # JSON ファイル永続化
├── services/
│   ├── __init__.py
│   ├── channel_manager.py  # チャンネル CRUD
│   └── collector.py        # 収集オーケストレーター
└── cli/
    ├── __init__.py
    └── main.py             # Click CLI
```

### 1.2 データストレージ

```
data/raw/youtube/
├── channels.json              # チャンネルレジストリ
└── {channel_id}/
    ├── videos.json            # 動画メタデータ一覧
    └── transcripts/
        └── {video_id}.json    # トランスクリプト（タイムスタンプ付き）
```

パス解決: `data_paths.get_path("raw/youtube")`

### 1.3 型定義 — `types.py`

**参照**: `src/rss/types.py` の dataclass パターン

```python
class TranscriptStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    UNAVAILABLE = "unavailable"  # 字幕なし
    FAILED = "failed"

@dataclass
class Channel:
    channel_id: str           # YouTube channel ID (UC...)
    title: str
    uploads_playlist_id: str  # UU... (channel_id から導出)
    language_priority: list[str]  # ["ja", "en"]
    enabled: bool
    created_at: str           # ISO 8601
    last_fetched: str | None
    video_count: int

@dataclass
class Video:
    video_id: str
    channel_id: str
    title: str
    published: str            # ISO 8601
    description: str | None
    transcript_status: TranscriptStatus
    transcript_language: str | None
    fetched_at: str

@dataclass
class TranscriptEntry:
    start: float              # 秒
    duration: float
    text: str

@dataclass
class TranscriptResult:
    video_id: str
    language: str
    entries: list[TranscriptEntry]
    fetched_at: str

    def to_plain_text(self) -> str:
        return " ".join(e.text for e in self.entries)

@dataclass
class CollectResult:
    channel_id: str
    total_videos: int
    new_videos: int
    transcripts_fetched: int
    transcripts_unavailable: int
    transcripts_failed: int
    error_message: str | None
```

### 1.4 コア層

#### `core/channel_fetcher.py`

**役割**: YouTube Data API v3 でチャンネル情報・動画一覧を取得

- `get_channel_info(url_or_id: str) -> Channel` — URL/ハンドル/ID からチャンネル情報取得
- `list_all_videos(channel_id: str) -> list[Video]` — `playlistItems.list`（uploads playlist）で全動画取得、ページネーション対応
- API キー: `YOUTUBE_API_KEY` 環境変数
- quota 効率: `playlistItems.list` = 1 unit/call（`search.list` = 100 units を避ける）

#### `core/transcript_fetcher.py`

**役割**: youtube-transcript-api でトランスクリプト取得

- `fetch(video_id: str, languages: list[str]) -> TranscriptResult | None`
- 字幕なし → `None` を返す（例外ではなく）
- レート制限: リクエスト間 1.0 秒 sleep（設定可能）

#### `core/diff_detector.py`

**参照**: `src/rss/core/diff_detector.py`

- `detect_new(existing: list[Video], fetched: list[Video]) -> list[Video]`
- `video_id` で比較

### 1.5 ストレージ層 — `storage/json_storage.py`

**参照**: `src/rss/storage/json_storage.py`

- `save_channels() / load_channels()`
- `save_videos(channel_id) / load_videos(channel_id)`
- `save_transcript(channel_id, video_id) / load_transcript(channel_id, video_id)`
- `list_transcript_ids(channel_id) -> set[str]`
- filelock で排他制御

### 1.6 サービス層

#### `services/channel_manager.py`

**参照**: `src/rss/services/feed_manager.py`

- `add(url: str, language_priority: list[str]) -> Channel`
- `list(enabled_only: bool) -> list[Channel]`
- `remove(channel_id: str) -> None`
- `update(channel_id: str, **kwargs) -> Channel`

#### `services/collector.py`

**参照**: `src/rss/services/feed_fetcher.py`

- `collect(channel_id: str) -> CollectResult` — 1チャンネルの収集フロー:
  1. `channel_fetcher.list_all_videos()` で動画一覧取得
  2. `diff_detector.detect_new()` で新着抽出
  3. 各新着動画に `transcript_fetcher.fetch()` → ストレージ保存
  4. `CollectResult` 返却
- `collect_all() -> list[CollectResult]` — 全有効チャンネルを順次処理

### 1.7 CLI — `cli/main.py`

**参照**: `src/rss/cli/main.py`（Click + Rich パターン）

```
yt-transcript channel add <url> [--language ja,en]
yt-transcript channel list [--json]
yt-transcript channel remove <channel_id>
yt-transcript collect [--channel-id <id>] [--all] [--json]
yt-transcript videos <channel_id> [--limit 20] [--json]
yt-transcript transcript <video_id> [--json | --plain]
yt-transcript stats [--json]
```

### 1.8 pyproject.toml 変更

```toml
# optional-dependencies に追加
youtube = [
    "google-api-python-client>=2.0.0",
    "youtube-transcript-api>=1.0.0",
]

# scripts に追加
yt-transcript = "youtube_transcript.cli.main:cli"

# wheel packages に追加
packages = [..., "src/youtube_transcript"]
```

### 1.9 環境変数

| 変数 | 必須 | デフォルト | 説明 |
|------|------|-----------|------|
| `YOUTUBE_API_KEY` | Yes | — | YouTube Data API v3 キー |
| `YT_TRANSCRIPT_LANGUAGE` | No | `ja,en` | 言語優先度（カンマ区切り） |
| `YT_TRANSCRIPT_RATE_LIMIT` | No | `1.0` | リクエスト間隔（秒） |

## Phase 2: 拡張機能（MVP 後）

- `--retry-failed` フラグで失敗トランスクリプトの再取得
- `yt-dlp` フォールバック（youtube-transcript-api 失敗時）
- `search` コマンド（トランスクリプト全文検索）
- プレイリスト監視対応
- API quota トラッキング・日次予算管理

## Phase 3: 統合（Phase 2 後）

- NotebookLM パイプライン連携（トランスクリプトをテキストソースとして投入）
- ナレッジグラフ連携（トランスクリプトからエンティティ抽出）
- cron / APScheduler による定期収集

## 実装順序

TDD で以下の順に実装:

1. **`types.py`** + **`exceptions.py`** — データ構造定義
2. **`_logging.py`** — ログ基盤
3. **`storage/json_storage.py`** — 永続化層（テスト: tmp_path）
4. **`core/diff_detector.py`** — 差分検出（テスト: 純粋関数）
5. **`core/transcript_fetcher.py`** — トランスクリプト取得（テスト: モック）
6. **`core/channel_fetcher.py`** — YouTube API ラッパー（テスト: モック）
7. **`services/channel_manager.py`** — チャンネル管理（テスト: tmp_path）
8. **`services/collector.py`** — オーケストレーター（テスト: 全モック）
9. **`cli/main.py`** — CLI
10. **`__init__.py`** — エクスポート
11. **`pyproject.toml`** — 依存・エントリポイント追加

## テスト構造

```
tests/youtube_transcript/
├── conftest.py                    # fixtures: tmp_path, sample Channel/Video
├── unit/
│   ├── core/
│   │   ├── test_diff_detector.py
│   │   ├── test_transcript_fetcher.py
│   │   └── test_channel_fetcher.py
│   ├── storage/
│   │   └── test_json_storage.py
│   ├── services/
│   │   ├── test_channel_manager.py
│   │   └── test_collector.py
│   └── cli/
│       └── test_main.py
└── property/
    └── test_diff_detector_property.py
```

## 検証方法

1. `uv sync --all-extras` で依存インストール
2. `uv run pytest tests/youtube_transcript/ -v` で全テスト実行
3. `uv run yt-transcript channel add "https://www.youtube.com/@ChannelName" --language ja,en` でチャンネル登録
4. `uv run yt-transcript collect --all` でトランスクリプト収集
5. `uv run yt-transcript transcript <video_id> --plain` でテキスト確認
6. `make check-all` で品質チェック

## 参照ファイル（実装時に参照）

| 用途 | ファイル |
|------|---------|
| 型定義パターン | `src/rss/types.py` |
| ストレージパターン | `src/rss/storage/json_storage.py` |
| CLI パターン | `src/rss/cli/main.py` |
| サービスパターン | `src/rss/services/feed_manager.py`, `feed_fetcher.py` |
| 差分検出パターン | `src/rss/core/diff_detector.py` |
| パス解決 | `src/data_paths/paths.py` |
| ログ初期化 | `src/rss/_logging.py` |
| pyproject.toml | `pyproject.toml` (L31-67) |
