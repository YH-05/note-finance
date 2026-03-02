# 推奨アクション全実装計画

## Context

PR #7 のレビューで特定された 7 つの推奨アクション（必須 3 件 + 推奨 4 件）を実装する。

## 実装対象（7 件）

| # | 優先度 | 内容 | 対象ファイル |
|---|--------|------|-------------|
| 1 | 必須 | SEC-001: `--cleanup-days/--max-articles` 正数バリデーション | `scripts/scrape_finance_news.py` |
| 2 | 必須 | SEC-004: plist ユーザー名をプレースホルダーに置換 | `config/launchd/com.note-finance.scrape-news.plist` |
| 3 | 必須 | `pythonpath` に `"scripts"` 追加 | `pyproject.toml` |
| 4 | 推奨 | ThreadPoolExecutor 並列化 (42 秒 → 5 秒) | `cnbc.py`, `nasdaq.py`, `unified.py` |
| 5 | 推奨 | `nasdaq.py:220` を httpx params に変更 + カテゴリ whitelist | `src/news_scraper/nasdaq.py` |
| 6 | 推奨 | `CATEGORY_MAP` を CNBC/NASDAQ 別に分割 + KEYWORD_MAP 事前コンパイル | `scripts/convert_scraped_news.py` |
| 7 | 推奨 | `cnbc.py` / `nasdaq.py` 内部関数ユニットテスト | 新規 `tests/news_scraper/unit/test_cnbc.py`, `test_nasdaq.py` |

---

## 実装詳細

### 1. pyproject.toml — pythonpath 追加

```toml
# 変更前
pythonpath = ["src"]
# 変更後
pythonpath = ["src", "scripts"]
```

→ `tests/scripts/test_convert_scraped_news.py:L19` の `sys.path.insert` を削除可能になる。

### 2. scrape_finance_news.py — バリデーション + import 整理

```python
# ファイル先頭に追加
import shutil  # ループ内 import を移動

# _parse_args() の前に追加
def _positive_int(value: str) -> int:
    """Validate that a CLI argument is a positive integer."""
    ivalue = int(value)
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(
            f"{value} は 1 以上の整数を指定してください"
        )
    return ivalue

# parser.add_argument 変更
parser.add_argument("--cleanup-days", type=_positive_int, ...)
parser.add_argument("--max-articles", type=_positive_int, ...)

# _cleanup_old_data 内の import shutil を削除
```

### 3. plist — ユーザー名プレースホルダー化

`/Users/yukihata/` → `/Users/YOUR_USERNAME/` (全 4 箇所)

### 4. convert_scraped_news.py — CATEGORY_MAP 分割 + KEYWORD_MAP 事前コンパイル

```python
# CATEGORY_MAP を分割
CNBC_CATEGORY_MAP: dict[str, str] = {
    "economy": "macro", "finance": "finance", "investing": "indices",
    "earnings": "mag7", "bonds": "macro", "commodities": "sectors",
    "technology": "tech", "energy": "sectors", "health_care": "sectors",
    "real_estate": "sectors", "autos": "sectors", "top_news": "indices",
    "business": "finance", "markets": "indices",
}

NASDAQ_CATEGORY_MAP: dict[str, str] = {
    "Markets": "indices", "Earnings": "mag7", "Economy": "macro",
    "Commodities": "sectors", "Currencies": "macro", "Technology": "tech",
    "Stocks": "mag7", "ETFs": "sectors",
}

# KEYWORD_MAP を事前コンパイル
import re
_COMPILED_KEYWORD_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(pattern, re.IGNORECASE), cat)
    for pattern, cat in [
        (r"S&P\s*500|Nasdaq|Dow Jones|...", "indices"),
        ...
    ]
]

# _map_category を更新
def _map_category(category, title, summary):
    if category is not None:
        mapped = CNBC_CATEGORY_MAP.get(category) or NASDAQ_CATEGORY_MAP.get(category)
        if mapped is not None:
            return mapped
    text = title + " " + (summary or "")
    for pattern, cat in _COMPILED_KEYWORD_MAP:
        if pattern.search(text):
            return cat
    return "other"
```

### 5. nasdaq.py — httpx params + whitelist + ThreadPoolExecutor

```python
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

# whitelist セット追加
NASDAQ_API_CATEGORIES_SET: frozenset[str] = frozenset(NASDAQ_API_CATEGORIES)

# _fetch_category: URL エンコード + whitelist
def _fetch_category(client, category, max_per_source):
    if category not in NASDAQ_API_CATEGORIES_SET:
        logger.warning("Invalid NASDAQ category, skipping", category=category)
        return []
    params = {"category": category, "limit": max_per_source}
    url = f"{NASDAQ_API_BASE}/category"
    response = client.get(url, params=params)  # httpx が自動エンコード
    ...

# collect_news: ThreadPoolExecutor 並列化
def collect_news(config=None, categories=None):
    ...
    with httpx.Client(...) as client:
        def _task(cat: str) -> list[Article]:
            return _fetch_category(client, cat, max_per_source)

        with ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(_task, categories_to_fetch))

    for articles in results:
        all_articles.extend(articles)
    ...
```

### 6. cnbc.py — ThreadPoolExecutor

```python
from concurrent.futures import ThreadPoolExecutor

def collect_news(config=None, categories=None):
    ...
    def _task(category: str) -> list[Article]:
        feed_url = CNBC_FEEDS.get(category)
        if not feed_url:
            logger.warning("Unknown CNBC category, skipping", category=category)
            return []
        try:
            feed = feedparser.parse(feed_url)
            if feed.bozo and not feed.entries:
                return []
            articles: list[Article] = []
            for entry in feed.entries:
                if len(articles) >= max_per_source:
                    break
                article = _entry_to_article(entry, category)
                if article is not None:
                    articles.append(article)
            logger.info("CNBC feed fetched", category=category, count=len(articles))
            return articles
        except Exception as e:
            logger.error("Failed to fetch CNBC feed", category=category, error=str(e), exc_info=True)
            return []

    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(_task, feeds_to_fetch))

    for articles in results:
        all_articles.extend(articles)

    deduplicated = deduplicate_by_url(all_articles)
    ...
```

### 7. unified.py — ソースレベル並列化

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def collect_financial_news(sources=None, config=None):
    ...
    def _collect_source(source_name: SourceName) -> tuple[SourceName, list[Article]]:
        collector = SOURCE_REGISTRY.get(source_name)
        if collector is None:
            logger.warning("Unknown source, skipping", source=source_name)
            return source_name, []
        try:
            articles = collector(config)
            logger.info("Source collection complete", source=source_name, count=len(articles))
            return source_name, articles
        except Exception as e:
            logger.error("Source collection failed", source=source_name, error=str(e), exc_info=True)
            return source_name, []

    with ThreadPoolExecutor(max_workers=len(enabled_sources)) as executor:
        for _, source_articles in executor.map(_collect_source, enabled_sources):
            all_articles.extend(source_articles)
    ...
```

### 8. テストファイル新規作成

**tests/news_scraper/unit/test_cnbc.py** — 主要テストケース:
- `TestParseCnbcDate`: None入力、有効RFC2822、タイムゾーンなし、不正文字列
- `TestGetEntryField`: 複数キー試行、全欠落でNone、非文字列値をスキップ
- `TestExtractTags`: dict形式、str形式、混在、非リスト
- `TestExtractAuthor`: author_detail.name、authorのみ、両方なし
- `TestEntryToArticle`: 有効エントリ、title欠落、url欠落
- `TestCollectNews`: feedparser mock使用、未知カテゴリ、bozo feed、例外

**tests/news_scraper/unit/test_nasdaq.py** — 主要テストケース:
- `TestParseNasdaqDate`: ISO8601(Z付き)、MM/DD/YYYY、None、全フォーマット不一致
- `TestRowToArticle`: 正常、title/url欠落、相対URL変換、500文字切り詰め
- `TestExtractRowsFromResponse`: 5パターン (data.data.rows, data.data, data.rows, data.news, 空)
- `TestFetchCategory`: httpx mock成功、HTTPStatusError、RequestError、whitelist除外
- `TestCollectNews`: ThreadPoolExecutor使用時の統合

---

## 変更ファイル一覧

| ファイル | 変更種別 |
|----------|---------|
| `pyproject.toml` | 修正 |
| `config/launchd/com.note-finance.scrape-news.plist` | 修正 |
| `scripts/scrape_finance_news.py` | 修正 |
| `scripts/convert_scraped_news.py` | 修正 |
| `src/news_scraper/cnbc.py` | 修正 |
| `src/news_scraper/nasdaq.py` | 修正 |
| `src/news_scraper/unified.py` | 修正 |
| `tests/news_scraper/unit/test_cnbc.py` | 新規 |
| `tests/news_scraper/unit/test_nasdaq.py` | 新規 |
| `tests/scripts/test_convert_scraped_news.py` | 修正 (sys.path.insert 削除) |

## 検証

```bash
make check-all  # format → lint → typecheck → test
```

- `test_cnbc.py` / `test_nasdaq.py` が全件パスすること
- `test_convert_scraped_news.py` が sys.path.insert 削除後も全件パスすること
- `uv run python scripts/scrape_finance_news.py --cleanup-days 0` でバリデーションエラーになること
