# note.com スクレイピング → RawStore → Neo4j 統合パイプライン

## Context

creator-neo4j と research-neo4j への投入パイプラインにおいて、note.com からスクレイピングしたテキストを一旦保存し、投入先を選んで Neo4j に保存する仕組みが必要。現状は data_pipeline（Python バッチ）と creator-enrichment（スキル）の2系統が独立しており、RawStore を共有していない。また note.com 専用コレクターが存在せず、「一旦保存→後から投入先選択」のフローも未実装。

設計議論の詳細: `docs/plan/SideBusiness/2026-03-25_discussion-notecom-scraping-pipeline.md`

## 合意済み設計判断

1. **Playwright Python** で note.com 専用コレクター新規作成（非公式API不使用）
2. 収集（collect）と投入（ingest）を **2ステップ分離**
3. **creator-enrichment を RawStore 経由に改修**
4. **RSSモニタリング** + JSON config でクリエイター管理
5. 一括スクレイピング後に RSSモニター追加を質問

## ファイルマップ

### 新規作成

| # | ファイル | 内容 |
|---|---------|------|
| 1 | `src/data_pipeline/collectors/note_com_browser.py` | Playwright async ラッパー（note.com 読み取り専用） |
| 2 | `src/data_pipeline/collectors/note_com.py` | NoteComCollector（BaseCollector 継承） |
| 3 | `src/data_pipeline/collectors/note_com_rss.py` | NoteComRssMonitor（RSS新着検知 + Playwright本文取得） |
| 4 | `data/config/note-com-creators.json` | クリエイター管理config |
| 5 | `tests/unit/test_data_pipeline/test_note_com_browser.py` | ブラウザラッパーのテスト |
| 6 | `tests/unit/test_data_pipeline/test_note_com.py` | コレクターのテスト |
| 7 | `tests/unit/test_data_pipeline/test_note_com_rss.py` | RSSモニターのテスト |

### 変更

| # | ファイル | 変更内容 |
|---|---------|---------|
| 8 | `src/data_pipeline/__main__.py` | `note-com` + `ingest` サブコマンド追加 |
| 9 | `src/data_pipeline/pipeline.py` | `run_ingest_from_rawstore()` 追加, collectors に `"note-com"` 追加 |
| 10 | `data/config/collection_methods.json` | `"note-com"` メソッド定義追加 |
| 11 | `data/config/source_registry.json` | note-com ソースエントリ追加 |
| 12 | `src/creator_enrichment/phases/search.py` | DirectSearcher.search() に RawStore 保存追加（L246-247間） |

## 実装詳細

### 1. `note_com_browser.py` — Playwright async ラッパー

既存 `scripts/note_publisher/browser_client.py` のパターンに従う（lazy import, セレクタ集中管理, async context manager）。

```python
class NoteComBrowser:
    _SELECTORS = {
        "article_links": 'a[href*="/n/"]',
        "load_more": 'button:has-text("もっとみる")',
        "article_body": '.note-common-styles__textnote-body',
        "paywall_price": 'button:text-matches("¥")',
        "paywall_purchase": 'button:has-text("購入手続きへ")',
        "json_ld": 'script[type="application/ld+json"]',
        "hashtags": 'a[href*="/hashtag/"]',
    }

    async def __aenter__(self) -> NoteComBrowser: ...
    async def __aexit__(...): ...
    async def list_article_urls(self, username: str, *, max_pages: int = 10) -> list[str]
    async def scrape_article(self, url: str) -> NoteArticle | None  # None = 有料
    async def is_paid(self, page) -> bool
    async def extract_json_ld(self, page) -> dict
    async def extract_body_text(self, page) -> str
```

**有料判定ロジック**（記事ページでのみ判定可能）:
- `button` に "¥" を含むテキストがあるか
- "購入手続きへ" ボタンがあるか
- いずれかが存在 → `True`（有料）

**ページネーション**: "もっとみる" ボタンを max_pages 回クリック、新しい a[href*="/n/"] を蓄積。

### 2. `note_com.py` — NoteComCollector

`BaseCollector` (`src/data_pipeline/collectors/base.py`) を継承。

```python
class NoteComCollector(BaseCollector):
    def __init__(self, *, max_articles: int = 50, request_delay: float = 1.0, headless: bool = True): ...
    def collect(self, source: DataSource) -> CollectionResult:  # asyncio.run() でラップ
    async def _collect_async(self, source: DataSource) -> CollectionResult
```

フロー:
1. `source.config_ref` → `note-com-creators.json` からクリエイター一覧取得
2. 各クリエイター: `browser.list_article_urls(username)` → URL一覧
3. 各URL: `browser.scrape_article(url)` → 有料スキップ or `NoteArticle` 取得
4. `NoteArticle` → `CollectedItem(collection_method="note-com", source_id=f"note-com-{username}")` に変換
5. `result.finish()` して返却

### 3. `note_com_rss.py` — RSSモニタリング

```python
class NoteComRssMonitor:
    def __init__(self, config_path: Path, raw_store: RawStore, *, headless: bool = True): ...
    def monitor(self) -> MonitorResult  # asyncio.run() でラップ
```

フロー:
1. `note-com-creators.json` から `rss_enabled=true` のクリエイターを取得
2. feedparser で `/{username}/rss` をパース → 新着URL一覧
3. `raw_store.exists(url, source_id)` で既存チェック → 新規のみ
4. `NoteComBrowser.scrape_article(url)` で有料判定 + 本文取得
5. `raw_store.save_text()` で保存

### 4. `note-com-creators.json`

```json
{
  "version": "1.0",
  "creators": [],
  "settings": {
    "request_delay_seconds": 2,
    "max_articles_per_scrape": 50,
    "headless": true
  }
}
```

各クリエイター:
```json
{
  "username": "example",
  "display_name": "Example",
  "genres": ["career"],
  "target_instance": "creator",
  "rss_enabled": true,
  "enabled": true,
  "added_at": "2026-03-25T00:00:00+09:00"
}
```

### 5. CLI 拡張 (`__main__.py`)

**note-com サブコマンド**:
```bash
uv run python -m data_pipeline note-com scrape {username} [--max-articles 50]
uv run python -m data_pipeline note-com monitor
uv run python -m data_pipeline note-com add {username} [--genre career]
uv run python -m data_pipeline note-com list
uv run python -m data_pipeline note-com remove {username}
```

`scrape` 完了後: `input("RSSモニターに追加しますか？ [y/N]: ")` → `y` で config に追加。

**ingest サブコマンド**:
```bash
uv run python -m data_pipeline ingest --source note-com-{username} --target creator|research [--date 2026-03-25] [--dry-run]
```

### 6. `pipeline.py` 拡張

```python
def run_ingest_from_rawstore(
    *, source_id: str, target: str = "research",
    date: str | None = None, genre: str = "career",
    link_entities: bool = False, dry_run: bool = False,
) -> PipelineResult:
    """RawStore → Layer 3-4 を実行."""
    store = RawStore()
    all_items = store.load_items(source_id, date)
    # → _run_research_layers() or _run_creator_layers() に渡す
```

`run_pipeline()` の collectors dict に追加:
```python
from data_pipeline.collectors.note_com import NoteComCollector
collectors["note-com"] = NoteComCollector(headless=True)
```

### 7. creator-enrichment RawStore 統合 (`search.py`)

`DirectSearcher.search()` の L246-247 間に追加:

```python
# L246: logger.info("Search completed: %d items found", len(items))
# ↓ 追加
self._save_to_rawstore(items, genre)
# L247: return items
```

```python
def _save_to_rawstore(self, items: list[RawItem], genre: str) -> None:
    try:
        from data_pipeline.storage.raw_store import RawStore
        store = RawStore()
        for item in items:
            store.save_text(
                source_id=f"creator-{genre}",
                url=item["url"], title=item["title"],
                raw_text=item["content"],
                collection_method=item["source"],
            )
    except Exception:
        logger.warning("RawStore save failed (non-blocking)", exc_info=True)
```

try/except で既存フローを壊さない。

## Wave グルーピング

```
Wave 1 (並行可能・依存なし):
  [A] note_com_browser.py      — Playwright async ラッパー
  [B] note-com-creators.json   — 空config作成
  [C] collection_methods.json  — "note-com" メソッド追加
  [D] source_registry.json     — note-com ソース追加

Wave 2 (Wave 1 に依存):
  [E] note_com.py              — NoteComCollector (A, B に依存)
  [F] note_com_rss.py          — NoteComRssMonitor (A, B に依存)
  [G] search.py 改修           — RawStore 統合 (依存なし、独立可能)

Wave 3 (Wave 2 に依存):
  [H] __main__.py              — CLI note-com + ingest (E, F に依存)
  [I] pipeline.py              — run_ingest_from_rawstore + collectors 追加 (E に依存)

Wave 4 (Wave 3 に依存):
  [J] テスト全体               — ユニットテスト + 統合テスト
```

## 検証方法

### ステップ1: 単体テスト
```bash
uv run pytest tests/unit/test_data_pipeline/test_note_com*.py -v
```

### ステップ2: 手動 E2E テスト（一括スクレイピング）
```bash
# 無料記事のみのクリエイターで試行
uv run python -m data_pipeline note-com scrape yukihata --max-articles 5

# RawStore に保存されたか確認
ls /Volumes/personal_folder/raw_texts/note-com-yukihata/
```

### ステップ3: RSSモニタリングテスト
```bash
uv run python -m data_pipeline note-com add yukihata --genre career
uv run python -m data_pipeline note-com monitor
```

### ステップ4: ingest テスト
```bash
# dry-run で確認
uv run python -m data_pipeline ingest --source note-com-yukihata --target creator --dry-run

# 実投入
uv run python -m data_pipeline ingest --source note-com-yukihata --target creator
```

### ステップ5: creator-enrichment RawStore 統合確認
```bash
# enrichment 実行後に RawStore にファイルが増えているか確認
ls /Volumes/personal_folder/raw_texts/creator-career/
```

### ステップ6: 品質チェック
```bash
make check-all
```

## リスク

| リスク | 対策 |
|--------|------|
| note.com DOM 構造変更 | セレクタを `_SELECTORS` dict に集中管理、変更時は1箇所修正 |
| Bot 検出 / レート制限 | ランダム遅延 (1-3s)、headless Chrome、User-Agent 設定 |
| asyncio.run() ネスト問題 | CLI は同期なので問題なし。テスト時は pytest-asyncio |
| creator-enrichment 既存フロー破壊 | try/except ラッパーで非ブロッキング |
| robots.txt 準拠 | 実装前に `https://note.com/robots.txt` を確認 |
