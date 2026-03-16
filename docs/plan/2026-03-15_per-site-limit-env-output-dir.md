# 実装プラン: per-site limit 追加 + 出力先 .env 設定

## Context

backfill モードで `--limit 200`（デフォルト）が Tier A 最初のサイト `getrichslowly.org`（サイトマップ 2,477 URL）で使い切られ、他の 14 サイトがスクレイピングされない問題を解消する。また、スクレイピング結果の Markdown 出力先を NAS 等の外部パスに切り替えられるよう `.env` で設定可能にする。

---

## 変更ファイル

| ファイル | 変更種別 |
|---------|---------|
| `scripts/scrape_wealth_blogs.py` | 主要変更（定数・CLI・ロジック） |
| `tests/scripts/test_scrape_wealth_blogs.py` | テスト追加 |
| `.env.example` | ドキュメント追加 |

---

## 変更1: `scripts/scrape_wealth_blogs.py`

### 1-1. `import os` 追加（行 28 付近、既存 import ブロックに追加）

```python
import os
```

### 1-2. 定数ブロック変更（行 102-103 付近）

```python
# 変更前
SCRAPED_OUTPUT_DIR = Path("data/scraped/wealth")

# 変更後
SCRAPED_OUTPUT_DIR = Path(
    os.environ.get("WEALTH_SCRAPED_OUTPUT_DIR", "data/scraped/wealth")
)
"""Base directory for scraped Markdown article files.

Override via ``WEALTH_SCRAPED_OUTPUT_DIR`` environment variable.
Default: ``data/scraped/wealth`` (relative to working directory).
"""

DEFAULT_PER_SITE_LIMIT = 20
"""Default per-site scraping limit in backfill mode.

Controls how many articles are scraped per domain per run.
Set to 0 to disable the per-site limit.
"""
```

- `os.environ.get()` はモジュールロード時に一度評価される（既存の `scrape_finance_news.py` と同パターン）

### 1-3. `parse_args()` 変更

**`--per-site-limit` 引数の追加**（`--limit` の直後に挿入）:

```python
parser.add_argument(
    "--per-site-limit",
    type=int,
    default=DEFAULT_PER_SITE_LIMIT,
    dest="per_site_limit",
    help=(
        "Maximum articles to scrape per site in backfill mode. "
        f"0 = no per-site limit. (default: {DEFAULT_PER_SITE_LIMIT})"
    ),
)
```

**validation ブロック追加**（既存の `--days`, `--top-n` validation の後）:

```python
if parsed.limit <= 0:
    parser.error("--limit must be a positive integer")
if parsed.per_site_limit < 0:
    parser.error("--per-site-limit must be 0 or a positive integer")
```

### 1-4. `_run_backfill_async()` シグネチャ変更

`per_site_limit: int` を追加:

```python
async def _run_backfill_async(
    limit: int,
    per_site_limit: int,   # ← 追加
    dry_run: bool,
    ...
) -> int:
```

### 1-5. `_run_backfill_async()` ループ修正

**`site_scraped` カウンター追加**（`for site in tier_sites:` の直後）:

```python
for site in tier_sites:
    if total_scraped >= limit:
        logger.info("backfill_limit_reached", limit=limit)
        break

    site_scraped = 0  # ← 追加: サイトごとにリセット
```

**dry_run 表示に per-site limit 情報を追加**（既存の dry_run ブロック内）:

```python
if dry_run:
    effective = (
        min(len(urls_to_scrape), per_site_limit)
        if per_site_limit > 0
        else len(urls_to_scrape)
    )
    limit_info = (
        f"per-site limit: {per_site_limit}"
        if per_site_limit > 0
        else "per-site limit: none"
    )
    print(f"\n[{tier}] {domain}: {len(urls_to_scrape)} new URLs "
          f"(will scrape: {effective}, {limit_info})")
    ...
    continue
```

**URL ループに per-site チェックを追加**（既存の `if total_scraped >= limit: break` の直後）:

```python
for url in urls_to_scrape:
    if total_scraped >= limit:
        break
    if per_site_limit > 0 and site_scraped >= per_site_limit:   # ← 追加
        logger.info(
            "per_site_limit_reached",
            domain=domain,
            site_scraped=site_scraped,
            per_site_limit=per_site_limit,
        )
        break
```

**成功時のみ `site_scraped` をインクリメント**（`total_scraped += 1` の直後、2 箇所）:

```python
# Tier D 成功時（行 1134 付近）
total_scraped += 1
site_scraped += 1  # ← 追加

# 標準 HTTP 成功時（行 1155 付近）
total_scraped += 1
site_scraped += 1  # ← 追加
```

> **設計判断**: ロボット拒否・HTTP エラーによるスキップは `site_scraped` に加算しない。アクセス不能 URL が多くても実取得数が per-site limit まで確保されるため。

### 1-6. `run_backfill()` シグネチャ変更（行 1191 付近）

```python
def run_backfill(
    limit: int,
    per_site_limit: int = DEFAULT_PER_SITE_LIMIT,   # ← 追加
    dry_run: bool = False,
    ...
) -> int:
```

`asyncio.run()` 呼び出しに `per_site_limit=per_site_limit` を追加。

### 1-7. `main()` での受け渡し（行 1281 付近）

```python
return run_backfill(
    limit=parsed.limit,
    per_site_limit=parsed.per_site_limit,   # ← 追加
    dry_run=parsed.dry_run,
    ...
)
```

---

## 変更2: `.env.example` への追記（行 44 末尾に追加）

```ini
# ===== Wealth Blog Scraper =====
# Output directory for scraped wealth blog Markdown files
# Default: data/scraped/wealth (relative to working directory)
# Example for NAS: WEALTH_SCRAPED_OUTPUT_DIR=/Volumes/NeoData/note-finance-data/wealth
# WEALTH_SCRAPED_OUTPUT_DIR=data/scraped/wealth
```

---

## 変更3: `tests/scripts/test_scrape_wealth_blogs.py`

### テストファイル冒頭の import に追加

```python
from scrape_wealth_blogs import (
    ...
    DEFAULT_PER_SITE_LIMIT,   # ← 追加
    SCRAPED_OUTPUT_DIR,        # ← 追加
    run_backfill,              # ← 追加
)
```

### `TestConstants` クラスに追加（行 543 付近）

```python
def test_正常系_DEFAULT_PER_SITE_LIMITが非負整数(self) -> None:
    assert isinstance(DEFAULT_PER_SITE_LIMIT, int)
    assert DEFAULT_PER_SITE_LIMIT >= 0

def test_正常系_SCRAPED_OUTPUT_DIRがPath型(self) -> None:
    from pathlib import Path
    assert isinstance(SCRAPED_OUTPUT_DIR, Path)
```

### `TestParseArgs` クラスに追加（行 174 付近）

```python
def test_正常系_デフォルト引数にper_site_limitが含まれる(self) -> None:
    args = parse_args([])
    assert args.per_site_limit == DEFAULT_PER_SITE_LIMIT

def test_正常系_per_site_limit引数(self) -> None:
    args = parse_args(["--mode", "backfill", "--per-site-limit", "10"])
    assert args.per_site_limit == 10

def test_正常系_per_site_limit_0は無制限(self) -> None:
    args = parse_args(["--mode", "backfill", "--per-site-limit", "0"])
    assert args.per_site_limit == 0

def test_異常系_per_site_limitが負数でSystemExit(self) -> None:
    with pytest.raises(SystemExit):
        parse_args(["--mode", "backfill", "--per-site-limit", "-1"])

def test_異常系_limitが0以下でSystemExit(self) -> None:
    with pytest.raises(SystemExit):
        parse_args(["--mode", "backfill", "--limit", "0"])
```

### 新クラス `TestRunBackfillPerSiteLimit` を追加（テストファイル末尾）

```python
class TestRunBackfillPerSiteLimit:
    """run_backfill の per-site limit 動作テスト。"""

    @pytest.fixture()
    def _mock_sitemap_config(self) -> dict:
        return {
            "sites": [
                {"domain": "site-a.com", "backfill_tier": "A"},
                {"domain": "site-b.com", "backfill_tier": "A"},
            ]
        }

    def _make_entry(self, domain: str, n: int) -> list:
        return [MagicMock(url=f"https://{domain}/post-{i}") for i in range(n)]

    def test_正常系_per_site_limitで1サイト目が制限され2サイト目も処理される(
        self, tmp_path: "Path", _mock_sitemap_config: dict
    ) -> None:
        """per_site_limit=2 のとき site-a は2件で止まり site-b も処理される。"""
        site_a_entries = self._make_entry("site-a.com", 5)
        site_b_entries = self._make_entry("site-b.com", 3)

        mock_result = MagicMock()
        mock_result.status = ExtractionStatus.SUCCESS
        mock_result.text = "body"
        mock_result.title = "title"
        mock_result.date = None
        mock_result.author = None
        mock_result.extraction_method = "http"

        with (
            patch("scrape_wealth_blogs.load_json_config", return_value=_mock_sitemap_config),
            patch("scrape_wealth_blogs.WEALTH_SITEMAP_URLS", {
                "site-a.com": "https://site-a.com/sitemap.xml",
                "site-b.com": "https://site-b.com/sitemap.xml",
            }),
            patch("scrape_wealth_blogs.SitemapParser") as mock_parser_cls,
            patch("scrape_wealth_blogs.ArticleExtractor") as mock_extractor_cls,
            patch("scrape_wealth_blogs.ScrapeStateDB") as mock_db_cls,
            patch("scrape_wealth_blogs.ScrapingPolicy"),
            patch("scrape_wealth_blogs._save_article_markdown"),
        ):
            mock_parser = AsyncMock()
            mock_parser.parse.side_effect = [site_a_entries, site_b_entries]
            mock_parser.filter_post_urls.side_effect = lambda x: x
            mock_parser_cls.return_value = mock_parser

            mock_extractor = AsyncMock()
            mock_extractor.extract.return_value = mock_result
            mock_extractor_cls.return_value = mock_extractor

            mock_db = MagicMock()
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)
            mock_db.filter_new_urls.side_effect = lambda urls: urls
            mock_db.get_stats.return_value = {}
            mock_db_cls.return_value = mock_db

            result = run_backfill(
                limit=100,
                per_site_limit=2,
                dry_run=False,
                db_path=tmp_path / "test.db",
            )

        assert result == 0
        # site-a: 2件, site-b: 3件 = 計5件
        assert mock_extractor.extract.call_count == 5

    def test_正常系_per_site_limit_0で全URLをスクレイプする(
        self, tmp_path: "Path", _mock_sitemap_config: dict
    ) -> None:
        """per_site_limit=0 のとき per-site 制限なしでグローバル limit まで処理。"""
        site_a_entries = self._make_entry("site-a.com", 5)
        site_b_entries = self._make_entry("site-b.com", 3)

        mock_result = MagicMock()
        mock_result.status = ExtractionStatus.SUCCESS
        mock_result.text = "body"
        mock_result.title = "title"
        mock_result.date = None
        mock_result.author = None
        mock_result.extraction_method = "http"

        with (
            patch("scrape_wealth_blogs.load_json_config", return_value=_mock_sitemap_config),
            patch("scrape_wealth_blogs.WEALTH_SITEMAP_URLS", {
                "site-a.com": "https://site-a.com/sitemap.xml",
                "site-b.com": "https://site-b.com/sitemap.xml",
            }),
            patch("scrape_wealth_blogs.SitemapParser") as mock_parser_cls,
            patch("scrape_wealth_blogs.ArticleExtractor") as mock_extractor_cls,
            patch("scrape_wealth_blogs.ScrapeStateDB") as mock_db_cls,
            patch("scrape_wealth_blogs.ScrapingPolicy"),
            patch("scrape_wealth_blogs._save_article_markdown"),
        ):
            mock_parser = AsyncMock()
            mock_parser.parse.side_effect = [site_a_entries, site_b_entries]
            mock_parser.filter_post_urls.side_effect = lambda x: x
            mock_parser_cls.return_value = mock_parser

            mock_extractor = AsyncMock()
            mock_extractor.extract.return_value = mock_result
            mock_extractor_cls.return_value = mock_extractor

            mock_db = MagicMock()
            mock_db.__enter__ = MagicMock(return_value=mock_db)
            mock_db.__exit__ = MagicMock(return_value=False)
            mock_db.filter_new_urls.side_effect = lambda urls: urls
            mock_db.get_stats.return_value = {}
            mock_db_cls.return_value = mock_db

            result = run_backfill(
                limit=100,
                per_site_limit=0,
                dry_run=False,
                db_path=tmp_path / "test.db",
            )

        assert result == 0
        # site-a: 5件, site-b: 3件 = 計8件
        assert mock_extractor.extract.call_count == 8
```

テスト冒頭に `ExtractionStatus` の import 追加:
```python
from rss.services.article_extractor import ExtractionStatus
```

---

## 検証手順

```bash
# 1. テスト実行
uv run pytest tests/scripts/test_scrape_wealth_blogs.py -v

# 2. 型チェック
uv run pyright scripts/scrape_wealth_blogs.py

# 3. dry-run で per-site limit 表示を確認
uv run python scripts/scrape_wealth_blogs.py --mode backfill --dry-run --per-site-limit 5

# 4. 実動作確認（2サイト各5件）
uv run python scripts/scrape_wealth_blogs.py --mode backfill --limit 100 --per-site-limit 5 --backfill-tier A

# 5. .env に WEALTH_SCRAPED_OUTPUT_DIR を設定して出力先変更を確認
WEALTH_SCRAPED_OUTPUT_DIR=/tmp/test-wealth uv run python scripts/scrape_wealth_blogs.py --mode backfill --dry-run
```
