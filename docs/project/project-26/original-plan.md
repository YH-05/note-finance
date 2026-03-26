# Plan: rss_recent_articles の取得ロジックを news_scraper パッケージに統合

## Context

`rss_recent_articles.py` は `rss` パッケージ（FeedFetcher + FeedReader）を使い、
feeds.json の 26 フィードをNASに永続保存しながら取得している。一方 `news_scraper` の
`cnbc.py` は 6 フィードのみ対応し、本文取得なし。

**目的**: feeds.json の全26フィードを `news_scraper` に取り込み、
`scrape_finance_news.py → NAS → Neo4j` パイプラインの入口として使えるようにする。
ストレージはメモリのみ（Article オブジェクト）、本文取得は ArticleExtractor（trafilatura）を使用。

## 前提・設計方針

| 項目 | 方針 |
|------|------|
| ファイル単位 | パブリッシャー単位（cnbc.py拡張 + 6新規ファイル） |
| 保存先 | メモリのみ（Article オブジェクト → 後続パイプライン） |
| 本文取得 | `include_content=True` 時のみ ArticleExtractor を使用 |
| RSS全文含むフィード | ZeroHedge/Ars Technica → RSS content から直接取得（ArticleExtractor不要） |
| 重複排除 | URL基準・その場限り（deduplicate_by_url） |
| 非同期 | 全 collect_news を async に統一（cnbc.py も変換） |

## 現状の feeds.json フィード一覧（26本）

| パブリッシャー | フィード数 | カテゴリ | 全文in RSS |
|---|---:|---|---|
| CNBC | 21 | finance/market/tech | ❌（summary のみ） |
| TechCrunch | 1 | tech | ❌ |
| Ars Technica | 1 | tech | ✅ |
| The Verge | 1 | tech | ❌ |
| Hacker News | 1 | tech | ❌ |
| Federal Reserve | 1 | finance | ❌ |
| ZeroHedge | 1 | finance | ✅（HTML形式） |

## 新規作成ファイル（7本）

### 1. `src/news_scraper/_rss_fetcher.py`（共通ユーティリティ）

全ソースファイルが再利用する共通ロジック。

```python
async def fetch_rss_feeds(
    feeds: dict[str, str],           # {category_name: rss_url}
    source_name: str,
    config: ScraperConfig,
    *,
    has_full_content: bool = False,  # ZeroHedge/Ars Technica等
    content_is_html: bool = False,   # RSS content がHTML形式（ZeroHedge）
) -> list[Article]:
```

**内部フロー**:
1. `ThreadPoolExecutor(max_workers=3)` + `asyncio.to_thread` で feedparser.parse() を並列実行
2. 各 entry → Article 変換（title, url, published, summary, tags, author）
3. `has_full_content=True`: RSS の `content[0].value` または `description` からコンテンツ取得
   - `content_is_html=True` の場合: lxml で HTML を strip してプレーンテキスト化
4. `include_content=True` かつ `has_full_content=False` の場合:
   `ArticleExtractor` (from `rss.services`) で URL ごとに非同期フェッチ
5. `deduplicate_by_url(articles)` で重複排除

**依存**: `from rss.services import ArticleExtractor` (`src/rss/services/`)

### 2〜7. 新規ソースファイル（統一テンプレート）

各ファイルは FEEDS dict + collect_news() のみ（最小実装）:

| ファイル | ソース名 | has_full_content | 備考 |
|---------|---------|:---:|---|
| `src/news_scraper/techcrunch.py` | `techcrunch` | false | category: tech |
| `src/news_scraper/ars_technica.py` | `ars_technica` | **true** | RSS に全文 |
| `src/news_scraper/the_verge.py` | `the_verge` | false | category: tech |
| `src/news_scraper/hacker_news.py` | `hacker_news` | false | category: tech |
| `src/news_scraper/federal_reserve.py` | `federal_reserve` | false | category: finance |
| `src/news_scraper/zero_hedge.py` | `zero_hedge` | **true** | HTML in RSS |

```python
# 各ファイルの共通構造
FEEDS: dict[str, str] = {"category_name": "https://rss-url"}

async def collect_news(config: ScraperConfig | None = None) -> list[Article]:
    if config is None:
        config = ScraperConfig()
    return await fetch_rss_feeds(FEEDS, "source_name", config, has_full_content=...)
```

## 変更ファイル（4本）

### `src/news_scraper/cnbc.py`

- **CNBC_FEEDS を 6→21 に拡張**（追加分: World News, US News, Technology, Asia News,
  Europe News, Business, Politics, Health Care, Real Estate, Wealth, Autos, Energy, Media, Retail, Travel）
- `collect_news` を **sync → async** に変換
- 内部実装を `fetch_rss_feeds(CNBC_FEEDS, "cnbc", config)` に委譲
- `_parse_cnbc_date`, `_get_entry_field`, `_extract_tags`, `_extract_author` は
  `_rss_fetcher.py` の汎用パーサに統合（cnbc.py からは削除）

### `src/news_scraper/types.py`

`SourceName` リテラル型に 6 ソース名を追加:

```python
SourceName = Literal[
    "cnbc", "jetro", "kabutan", "minkabu", "nasdaq", "reuters_jp",
    # 新規追加
    "techcrunch", "ars_technica", "the_verge", "hacker_news",
    "federal_reserve", "zero_hedge",
]
```

### `src/news_scraper/unified.py`

- `_collect_cnbc` の `asyncio.to_thread` ラッパーを削除（直接 await に変更）
- 6 つの `_collect_*` 関数を追加（`_collect_techcrunch` 等）
- `SOURCE_REGISTRY` に 6 エントリを追加

```python
SOURCE_REGISTRY = {
    ...(既存 6 エントリ)...
    "techcrunch":      _make_registry_fn("_collect_techcrunch"),
    "ars_technica":    _make_registry_fn("_collect_ars_technica"),
    "the_verge":       _make_registry_fn("_collect_the_verge"),
    "hacker_news":     _make_registry_fn("_collect_hacker_news"),
    "federal_reserve": _make_registry_fn("_collect_federal_reserve"),
    "zero_hedge":      _make_registry_fn("_collect_zero_hedge"),
}
```

### `scripts/scrape_finance_news.py`

`--sources` choices に 6 ソース名を追加（DEFAULT_SOURCES は `["cnbc"]` のまま維持）:

```python
choices=[
    "cnbc", "nasdaq", "kabutan", "reuters_jp", "minkabu", "jetro",
    "techcrunch", "ars_technica", "the_verge", "hacker_news",
    "federal_reserve", "zero_hedge",
]
```

## ファイルマップ

```
src/news_scraper/
├── _rss_fetcher.py          ← 新規（共通ユーティリティ）
├── cnbc.py                  ← 変更（21feeds、async化、_rss_fetcherに委譲）
├── techcrunch.py            ← 新規
├── ars_technica.py          ← 新規
├── the_verge.py             ← 新規
├── hacker_news.py           ← 新規
├── federal_reserve.py       ← 新規
├── zero_hedge.py            ← 新規
├── types.py                 ← 変更（SourceName 拡張）
├── unified.py               ← 変更（SOURCE_REGISTRY 拡張、_collect_cnbc 修正）
└── (既存ファイル変更なし)

scripts/
└── scrape_finance_news.py   ← 変更（--sources choices 拡張のみ）
```

## 依存関係

- `news_scraper._rss_fetcher` → `rss.services.ArticleExtractor`（既存パッケージ）
- `rss` パッケージはすでに同プロジェクト内 `src/rss/` に存在し、cross-package import は他箇所（`unified.py`の`data_pipeline`import等）で使用済み

## 検証方法

```bash
# 新規ソース単体確認（少量で）
uv run python scripts/scrape_finance_news.py \
    --sources techcrunch ars_technica zero_hedge \
    --max-articles 5 --log-level DEBUG --skip-neo4j

# 本文取得確認
uv run python scripts/scrape_finance_news.py \
    --sources ars_technica --include-content --max-articles 3 \
    --log-level DEBUG --skip-neo4j

# CNBC 拡張確認（21フィード）
uv run python scripts/scrape_finance_news.py \
    --sources cnbc --max-articles 10 --log-level DEBUG --skip-neo4j

# rss_recent_articles は引き続き独立動作すること
uv run python scripts/rss_recent_articles.py

# 品質チェック
make check-all
```
