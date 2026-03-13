# Wealth Finance Blog RSS収集・スクレイピング実装計画

## Context

`data/rss_sources/` から特定した投資・資産形成関連の英語ブログ群を、既存のRSSインフラ（`src/rss/`）に統合する。18サイト候補を調査した結果、15サイト（Tier 1: 11, Tier 2: 3, Tier 3: 1）を採用。主な発見：

- **Alpha Architect**: hCaptchaはフォームのみ → RSS (`/feed/`) が正常動作 → Tier 1に昇格
- **Kiplinger**: RSS 403 だが Playwright でブログ一覧・記事本文とも取得可 → Tier 3
- **Good Financial Cents**: 2024年6月以降更新なし → 除外
- **Penny Hoarder / Investopedia**: 日付不明・bot検出 → 除外

取得間隔は `daily`（note記事を毎日書くため）。スキル `/scrape-finance-blog` から随時呼び出し可能にする。

---

## アーキテクチャ: 2モード動作

### 設計思想

RSSフィードは最新10-20件しか返さないため、**過去記事の全件取得はRSS経由では不可能**。
そのため、以下の2モードを設ける：

- **backfill**: サイトマップ/アーカイブページから全記事URLを収集 → httpx + BeautifulSoup / Playwright でスクレイピング
- **incremental**: RSSフィードで新着記事を検出 → 状態DBと突き合わせて未取得分のみスクレイピング

両モードは**状態DB（SQLite）**を共有し、重複取得を排除する。

```
                    ┌─────────────────────────────┐
                    │     スクレイピング状態DB       │
                    │  (scraped済みURL・ステータス)   │
                    │     data/wealth_scrape.db    │
                    └──────┬──────────┬────────────┘
                           │          │
              ┌────────────▼──┐  ┌────▼────────────┐
              │  backfill     │  │  incremental     │
              │  全件取得      │  │  差分取得         │
              └───────────────┘  └─────────────────┘
                     │                    │
              sitemap.xml             RSS feed
              パース                  最新記事
                     │                    │
                     ▼                    ▼
              URL一覧収集          新規URL検出
                     │                    │
                     └────────┬───────────┘
                              ▼
                   状態DBで未取得URLをフィルタ
                              │
                              ▼
                httpx + BeautifulSoup (静的サイト)
                Playwright (JS必須サイト)
                              │
                              ▼
                ArticleExtractor で本文抽出
                              │
                              ▼
                Markdown保存 + 状態DB更新
```

### 状態DB設計（SQLite）

Python組み込みの `sqlite3` モジュールを使用（依存追加不要）。

```sql
CREATE TABLE IF NOT EXISTS scraped_articles (
    url TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    title TEXT,
    author TEXT,
    published TEXT,              -- ISO 8601
    scraped_at TEXT NOT NULL,    -- ISO 8601
    status TEXT NOT NULL,        -- 'success' | 'failed' | 'skipped'
    extraction_method TEXT,      -- 'trafilatura' | 'bs4' | 'playwright'
    file_path TEXT,              -- 保存先相対パス
    content_hash TEXT,           -- SHA-256（変更検出用）
    error_message TEXT,          -- 失敗時のエラーメッセージ
    retry_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_domain ON scraped_articles(domain);
CREATE INDEX IF NOT EXISTS idx_status ON scraped_articles(status);
CREATE INDEX IF NOT EXISTS idx_scraped_at ON scraped_articles(scraped_at);

CREATE TABLE IF NOT EXISTS sitemap_state (
    domain TEXT PRIMARY KEY,
    sitemap_url TEXT NOT NULL,
    last_fetched TEXT,           -- サイトマップ最終取得日時
    total_urls INTEGER,          -- サイトマップ内のURL総数
    scraped_urls INTEGER,        -- 取得済みURL数
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

**状態DBの役割：**

| 操作 | 説明 |
|------|------|
| 重複チェック | `url` で既存レコードを検索し、スキップ |
| 進捗追跡 | `sitemap_state` でドメイン別の取得進捗を管理 |
| リトライ | `status='failed'` かつ `retry_count < 3` のURLを再取得 |
| 変更検出 | `content_hash` で記事更新を検出（オプション） |

---

## サイトマップ調査結果（2026-03-13 実施）

### 全15サイトにサイトマップが存在

ページネーション巡回のフォールバックは不要。全サイトでサイトマップベースのバックフィルが可能。

| # | サイト | Sitemap URL | 種別 | 推定記事数 | プラットフォーム | 制約 |
|---|--------|-------------|------|-----------|----------------|------|
| 1 | Of Dollars and Data | `/sitemap_index.xml` | Index (Rank Math) | ~141 | WordPress | — |
| 2 | A Wealth of Common Sense | `/sitemap.xml` | Index (Rank Math) | ~3,500-4,000 | WordPress | robots.txtに記載なし |
| 3 | The Big Picture (Ritholtz) | `/sitemap.xml` | Index (Yoast) | ~44,000+ | WordPress | crawl-delay: 10s |
| 4 | The Dividend Guy Blog | `/sitemap_index.xml` | Index (Yoast) | ~1,000+ | WordPress | — |
| 5 | Money Crashers | `/wp-sitemap.xml` | Index (WP native) | ~800-1,000 | WordPress | www リダイレクト |
| 6 | Clever Girl Finance | `/sitemap.xml` | Index (Yoast) | ~500-1,000 | WordPress | www リダイレクト |
| 7 | Afford Anything | `/sitemap_index.xml` | Index (Yoast) | ~201 | WordPress | — |
| 8 | Bits about Money | `/sitemap.xml` | Index (Ghost) | ~66 | Ghost | — |
| 9 | Monevator | `/sitemap.xml` | Index (Yoast) | ~3,000+ | WordPress | **crawl-delay: 240s** |
| 10 | Money Talks News | WP sitemaps (個別) | WP native | ~10,000+ | WordPress | **sitemap index 403、重レート制限、ai-train=no** |
| 11 | Alpha Architect | `/sitemap_index.xml` | Index (Yoast) | ~2,000+ | WordPress | 一部ツールで403 |
| 12 | The College Investor | `/sitemap_index.xml` | Index (Rank Math) | ~6,000+ | WordPress | **ClaudeBot明示ブロック、ai-train=no** |
| 13 | Marginal Revolution | `/sitemap_index.xml` | Index (Yoast) | ~40,000+ | WordPress | **crawl-delay: 600s** |
| 14 | NerdWallet | `/blog/wp-sitemap.xml` | Index (WP native) | ~6,600+ | WordPress | 大規模サイト |
| 15 | Kiplinger | `/sitemap.xml` | Index (custom monthly) | ~10,000+ | Custom | AIクローラー複数ブロック |

### コンテンツ量 Tier

| 分類 | サイト | 記事数 |
|------|--------|--------|
| Massive (10,000+) | ritholtz, marginalrevolution, kiplinger, moneytalksnews | 10K-44K |
| Large (2,000-10,000) | nerdwallet, thecollegeinvestor, awealthofcommonsense, monevator, alphaarchitect | 2K-6.6K |
| Medium (500-2,000) | thedividendguyblog, moneycrashers, clevergirlfinance | 500-1K |
| Small (<500) | affordanything, ofdollarsanddata, bitsaboutmoney | 66-201 |

### バックフィル方式 Tier（新規分類）

サイトマップのアクセシビリティとレート制限に基づく分類：

| Tier | 方式 | サイト | 備考 |
|------|------|--------|------|
| **A: 高速バックフィル** | httpx + sitemap | ofdollarsanddata, affordanything, bitsaboutmoney, thedividendguyblog, moneycrashers, clevergirlfinance | 制約少、記事数少-中 |
| **B: 低速バックフィル** | httpx + sitemap + レート制限厳守 | awealthofcommonsense, alphaarchitect, nerdwallet, ritholtz(10s), monevator(240s) | crawl-delay 遵守必須 |
| **C: 慎重バックフィル** | UA rotation + sitemap | thecollegeinvestor, moneytalksnews | ボットブロック・重レート制限 |
| **D: Playwright バックフィル** | Playwright + sitemap | kiplinger, marginalrevolution(600s) | JS必須 or 極端なcrawl-delay |

---

## 対象フィード一覧（15サイト）— RSS用分類

### Tier 1: RSS取得（11サイト）

| サイト | RSS URL | 更新頻度 |
|--------|---------|----------|
| Of Dollars and Data | `ofdollarsanddata.com/feed/` | 週1 |
| A Wealth of Common Sense | `awealthofcommonsense.com/feed/` | 1-2日 |
| The Big Picture (Ritholtz) | `ritholtz.com/feed/` | 1-3日 |
| The Dividend Guy Blog | `thedividendguyblog.com/feed/` | 3-4日 |
| Money Crashers | `moneycrashers.com/feed/` | 週2-3 |
| Clever Girl Finance | `clevergirlfinance.com/feed/` | 1-2週 |
| Afford Anything | `affordanything.com/feed/` | 3-4日 |
| Bits about Money | `bitsaboutmoney.com/archive/rss/` | 月1 |
| Monevator | `monevator.com/feed/` | 2-3日 |
| Money Talks News | `moneytalksnews.com/feed/` | 毎日 |
| Alpha Architect | `alphaarchitect.com/feed/` | 週1 |

### Tier 2: 条件付きRSS（3サイト）

| サイト | RSS URL | 制約 |
|--------|---------|------|
| The College Investor | `thecollegeinvestor.com/feed/` | AIボット明示ブロック → UA rotation |
| Marginal Revolution | `marginalrevolution.com/feed` | 1日3+回更新 |
| NerdWallet | `nerdwallet.com/blog/feed/` | 大規模サイト |

### Tier 3: Playwright必須（1サイト）

| サイト | URL | 状況 |
|--------|-----|------|
| Kiplinger | `kiplinger.com/investing` | RSS 403。Playwright でページ取得・記事抽出 |

---

## 実装ステップ

### Step 1: 設定ファイル（並列作成可、依存なし）

#### 1a. `data/config/rss-presets-wealth.json`（新規）

既存 `rss-presets-jp.json` と同一フォーマット。`tier` と `note` は追加メタデータ（`apply_presets()` が無視するため安全）。

```json
{
    "version": "1.0",
    "presets": [
        {
            "url": "https://ofdollarsanddata.com/feed/",
            "title": "Of Dollars and Data",
            "category": "wealth",
            "fetch_interval": "daily",
            "enabled": true,
            "tier": 1,
            "note": "Data-driven investing, weekly updates"
        }
    ]
}
```

- Tier 1+2（14フィード）: `enabled: true`
- Kiplinger（Tier 3）: `enabled: false`, note に "Playwright required" 記載
- 全フィード: `category: "wealth"`, `fetch_interval: "daily"`

#### 1b. `data/config/wealth-management-themes.json`（新規）

既存 `asset-management-themes.json` のフォーマットに準拠。英語ソース用に `name_en`/`keywords_en` を使用。

6テーマ:
- `data_driven_investing`: ofdollarsanddata, awealthofcommonsense, ritholtz
- `dividend_income`: dividendguy
- `fire_wealth_building`: affordanything, clevergirlfinance
- `financial_infrastructure`: bitsaboutmoney
- `personal_finance`: moneycrashers, monevator, marginalrevolution, nerdwallet, collegeinvestor, moneytalksnews, kiplinger
- `academic_finance`: alphaarchitect

#### 1c. `src/rss/config/__init__.py` + `wealth_scraping_config.py`（新規）

`src/rss/config/` ディレクトリを新規作成。

```python
# wealth_scraping_config.py
WEALTH_DOMAIN_RATE_LIMITS: dict[str, float] = {
    "monevator.com": 240.0,
    "marginalrevolution.com": 600.0,  # robots.txt 指定値
    "thecollegeinvestor.com": 10.0,
    "moneytalksnews.com": 5.0,
    "kiplinger.com": 10.0,
    "nerdwallet.com": 5.0,
    "ritholtz.com": 10.0,  # robots.txt 指定値
}

# バックフィル用サイトマップ設定
WEALTH_SITEMAP_URLS: dict[str, str] = {
    "ofdollarsanddata.com": "https://ofdollarsanddata.com/sitemap_index.xml",
    "awealthofcommonsense.com": "https://awealthofcommonsense.com/sitemap.xml",
    "ritholtz.com": "https://ritholtz.com/sitemap.xml",
    "thedividendguyblog.com": "https://thedividendguyblog.com/sitemap_index.xml",
    "moneycrashers.com": "https://www.moneycrashers.com/wp-sitemap.xml",
    "clevergirlfinance.com": "https://www.clevergirlfinance.com/sitemap.xml",
    "affordanything.com": "https://affordanything.com/sitemap_index.xml",
    "bitsaboutmoney.com": "https://www.bitsaboutmoney.com/sitemap.xml",
    "monevator.com": "https://monevator.com/sitemap.xml",
    "moneytalksnews.com": "https://moneytalksnews.com/wp-sitemap.xml",
    "alphaarchitect.com": "https://alphaarchitect.com/sitemap_index.xml",
    "thecollegeinvestor.com": "https://thecollegeinvestor.com/sitemap_index.xml",
    "marginalrevolution.com": "https://marginalrevolution.com/sitemap_index.xml",
    "nerdwallet.com": "https://www.nerdwallet.com/blog/wp-sitemap.xml",
    "kiplinger.com": "https://www.kiplinger.com/sitemap.xml",
}

# バックフィルTier（アクセス制約に基づく分類）
BACKFILL_TIER: dict[str, str] = {
    "ofdollarsanddata.com": "A",       # 高速
    "affordanything.com": "A",
    "bitsaboutmoney.com": "A",
    "thedividendguyblog.com": "A",
    "moneycrashers.com": "A",
    "clevergirlfinance.com": "A",
    "awealthofcommonsense.com": "B",   # 低速（大量記事）
    "alphaarchitect.com": "B",
    "nerdwallet.com": "B",
    "ritholtz.com": "B",              # crawl-delay: 10s
    "monevator.com": "B",             # crawl-delay: 240s
    "thecollegeinvestor.com": "C",    # ボットブロック
    "moneytalksnews.com": "C",        # 重レート制限
    "kiplinger.com": "D",             # Playwright必須
    "marginalrevolution.com": "D",    # crawl-delay: 600s
}
```

既存 `ScrapingPolicy(domain_rate_limits=...)` で消費。

#### 1d. `data/config/wealth-sitemap-config.json`（新規）

サイトマップ設定をJSONでも管理（スクリプトからの参照用）。

```json
{
    "version": "1.0",
    "sites": [
        {
            "domain": "ofdollarsanddata.com",
            "sitemap_url": "https://ofdollarsanddata.com/sitemap_index.xml",
            "sitemap_type": "index",
            "platform": "rank_math",
            "backfill_tier": "A",
            "estimated_articles": 141,
            "crawl_delay": null,
            "restrictions": []
        }
    ]
}
```

---

### Step 2: 状態DB + robots.txt チェッカー

#### 2a. `src/rss/storage/scrape_state_db.py`（新規）

```python
class ScrapeStateDB:
    """スクレイピング状態を管理するSQLiteラッパー。

    Parameters
    ----------
    db_path : str | Path
        SQLiteデータベースファイルのパス。
    """

    def __init__(self, db_path: str | Path = "data/wealth_scrape.db") -> None: ...

    def is_scraped(self, url: str) -> bool:
        """URLが取得済みかチェック。"""

    def mark_scraped(
        self,
        url: str,
        domain: str,
        title: str | None,
        status: str,
        extraction_method: str | None,
        file_path: str | None,
        content_hash: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """記事の取得状態を記録。"""

    def get_pending_urls(self, domain: str | None = None) -> list[str]:
        """未取得 or 失敗（リトライ可）のURLを返す。"""

    def get_stats(self, domain: str | None = None) -> dict[str, int]:
        """ドメイン別の取得統計を返す。"""

    def update_sitemap_state(
        self, domain: str, sitemap_url: str, total_urls: int, scraped_urls: int
    ) -> None:
        """サイトマップの取得進捗を更新。"""

    def get_sitemap_progress(self) -> list[dict]:
        """全ドメインの取得進捗を返す。"""

    def filter_new_urls(self, urls: list[str]) -> list[str]:
        """未取得のURLのみをフィルタして返す。"""
```

- `sqlite3` のみ使用（依存追加不要）
- コンテキストマネージャ対応（`__enter__` / `__exit__`）
- スレッドセーフ: `check_same_thread=False`
- WALモード有効化（並行読み取り可）

#### 2b. `src/rss/utils/robots_checker.py`（新規）

```python
@dataclass(frozen=True)
class RobotsCheckResult:
    url: str
    allowed: bool
    crawl_delay: float | None
    ai_directives: dict[str, str]  # {"ai-train": "no"} etc.
    error: str | None

class RobotsChecker:
    def __init__(self, user_agent: str = "rss-feed-collector/0.1.0") -> None: ...
    async def check(self, url: str) -> RobotsCheckResult: ...
    def get_crawl_delay(self, domain: str) -> float | None: ...
```

- `urllib.robotparser.RobotFileParser` + `httpx`（既存依存）
- ドメイン単位キャッシュ: `dict[str, RobotFileParser]`
- 非標準ディレクティブ検出: robots.txt 生テキストから `ai-train`, `GPTBot`, `CCBot` をパース
- `_get_logger()` パターン準拠（structlog/stdlib フォールバック）
- 継続利用前提（FeedFetcherやスクレイパーから呼び出し可）

#### 2c. `src/rss/utils/sitemap_parser.py`（新規）

```python
@dataclass(frozen=True)
class SitemapEntry:
    url: str
    lastmod: str | None
    changefreq: str | None
    priority: float | None

class SitemapParser:
    """サイトマップXMLをパースしてURLリストを返す。

    sitemap index → 子サイトマップを再帰的にパースする。
    post/page タイプのフィルタリング対応。
    """

    def __init__(self, http_client: HTTPClient | None = None) -> None: ...

    async def parse(self, sitemap_url: str) -> list[SitemapEntry]:
        """サイトマップをパースし全記事URLを返す。"""

    async def parse_index(self, index_url: str) -> list[str]:
        """サイトマップインデックスから子サイトマップURLを返す。"""

    def filter_post_urls(self, entries: list[SitemapEntry]) -> list[SitemapEntry]:
        """記事URLのみフィルタ（attachment, category, tag, author を除外）。"""
```

- `xml.etree.ElementTree` でパース（依存追加不要）
- Yoast / Rank Math / WP native / Ghost / custom 各形式対応
- URL フィルタ: `/category/`, `/tag/`, `/author/`, `/attachment/` を除外
- `post-sitemap-*.xml` のような子サイトマップを優先取得

#### 2d. `src/rss/utils/__init__.py`（変更）

```python
from rss.utils.robots_checker import RobotsCheckResult, RobotsChecker
from rss.utils.sitemap_parser import SitemapEntry, SitemapParser
```

を `__all__` に追加。

---

### Step 3: メインスクレイパースクリプト（Step 1, 2 に依存）

#### 3a. `scripts/scrape_wealth_blogs.py`（新規）

`prepare_ai_research_session.py` のバッチスクレイピングパターンと `prepare_asset_management_session.py` のテーママッチングパターンを組み合わせ。

**処理フロー（2モード対応）:**

```
scrape_wealth_blogs.py --mode incremental
  │
  ├─ Phase 1: 設定読み込み
  │   ├─ rss-presets-wealth.json
  │   ├─ wealth-management-themes.json
  │   ├─ ScrapingPolicy(domain_rate_limits=WEALTH_DOMAIN_RATE_LIMITS)
  │   ├─ ArticleExtractor
  │   └─ ScrapeStateDB("data/wealth_scrape.db")
  │
  ├─ Phase 2: RSS取得（Tier 1+2）
  │   ├─ httpx + feedparser で各フィードのRSS取得
  │   ├─ filter_by_date(items, days) で日付フィルタ
  │   ├─ ScrapeStateDB.filter_new_urls() で未取得分のみ抽出
  │   ├─ ArticleExtractor.extract() で本文抽出
  │   ├─ ScrapingPolicy.wait_for_domain() でレート制限
  │   ├─ Markdown保存: data/scraped/wealth/{domain}/{slug}.md
  │   └─ ScrapeStateDB.mark_scraped() で状態記録
  │
  ├─ Phase 3: Playwrightスクレイピング（Tier 3 = Kiplinger）
  │   ├─ httpx + UA rotation で記事一覧ページ取得（403ならPlaywright fallback）
  │   ├─ ScrapeStateDB.filter_new_urls() で未取得分のみ抽出
  │   ├─ 各記事: ArticleExtractor.extract() で本文抽出
  │   ├─ Markdown保存（同上）
  │   └─ ScrapeStateDB.mark_scraped() で状態記録
  │
  └─ Phase 4: セッションJSON出力
      ├─ テーマ別キーワードマッチング（themes.json 参照）
      ├─ .tmp/wealth-scrape-{YYYYMMDD}-{HHMMSS}.json
      └─ サマリー統計表示

scrape_wealth_blogs.py --mode backfill
  │
  ├─ Phase 1: 設定読み込み（同上）
  │
  ├─ Phase 2: サイトマップ取得 + URL収集
  │   ├─ wealth-sitemap-config.json から対象サイト読み込み
  │   ├─ SitemapParser.parse() で全記事URLを収集
  │   ├─ SitemapParser.filter_post_urls() で記事URLのみフィルタ
  │   ├─ ScrapeStateDB.filter_new_urls() で未取得分のみ抽出
  │   └─ ScrapeStateDB.update_sitemap_state() で進捗記録
  │
  ├─ Phase 3: バッチスクレイピング（バックフィルTier順）
  │   ├─ Tier A（高速）: httpx + trafilatura、並列度高
  │   ├─ Tier B（低速）: httpx + trafilatura、crawl-delay厳守
  │   ├─ Tier C（慎重）: UA rotation + trafilatura
  │   ├─ Tier D（Playwright）: Playwright + trafilatura
  │   ├─ 各記事: ArticleExtractor.extract() で本文抽出
  │   ├─ Markdown保存: data/scraped/wealth/{domain}/{slug}.md
  │   ├─ ScrapeStateDB.mark_scraped() で状態記録
  │   └─ 進捗表示（N/total、ETA）
  │
  └─ Phase 4: 統計出力
      ├─ ドメイン別の取得状況テーブル
      ├─ 成功/失敗/スキップの内訳
      └─ ScrapeStateDB.get_sitemap_progress() で進捗サマリー
```

**CLI引数:**

```bash
uv run python scripts/scrape_wealth_blogs.py \
  --mode incremental  # incremental（デフォルト）| backfill
  --days 7            # 日付フィルタ（incremental時のみ、デフォルト7）
  --tier all          # RSS Tier: 1/2/3/all（incremental時）
  --backfill-tier A   # バックフィルTier: A/B/C/D/all（backfill時、デフォルト all）
  --domain example.com  # 特定ドメインのみ処理
  --limit 100         # 最大取得記事数（backfill時のリミット）
  --top-n 10          # テーマ別最大記事数（incremental時）
  --check-robots      # robots.txt チェック有効
  --retry-failed      # 失敗記事の再取得
  --dry-run           # フィード一覧 or URL一覧表示のみ
  --verbose           # デバッグログ
```

**Pydantic モデル:**

```python
class WealthArticleData(BaseModel):
    url: str
    title: str
    text: str
    author: str | None
    published: str
    source: str
    domain: str
    tier: int
    extraction_method: str  # "trafilatura" | "fallback" | "playwright"

class WealthScrapeSession(BaseModel):
    session_id: str  # "wealth-scrape-{YYYYMMDD}-{HHMMSS}"
    timestamp: str
    mode: str  # "incremental" | "backfill"
    themes: dict[str, WealthThemeData]
    stats: WealthScrapeStats
```

**Markdown出力フォーマット:**

```markdown
---
title: "Article Title"
author: "Author Name"
published: "2026-03-10"
source: "Of Dollars and Data"
url: "https://ofdollarsanddata.com/..."
domain: "ofdollarsanddata.com"
tier: 1
category: "wealth"
---

[本文テキスト]
```

**保存ディレクトリ構造:**

```
data/scraped/wealth/
├── ofdollarsanddata.com/
│   ├── why-you-shouldnt-time-the-market.md
│   └── the-power-of-compounding.md
├── bitsaboutmoney.com/
│   ├── salary-transparency.md
│   └── ...
└── ...
```

> **変更**: 日付ベースのサブディレクトリ（`{YYYY-MM-DD}/`）を廃止し、ドメインベースのフラットな構造に変更。
> 理由: backfillモードでは記事の公開日がバラバラになるため、日付ディレクトリは不適切。

**ドメイン→ソースキーマッピング:**

```python
WEALTH_URL_TO_SOURCE_KEY: dict[str, str] = {
    "ofdollarsanddata.com": "ofdollarsanddata",
    "awealthofcommonsense.com": "awealthofcommonsense",
    "ritholtz.com": "ritholtz",
    "thedividendguyblog.com": "dividendguy",
    "moneycrashers.com": "moneycrashers",
    "clevergirlfinance.com": "clevergirlfinance",
    "affordanything.com": "affordanything",
    "bitsaboutmoney.com": "bitsaboutmoney",
    "monevator.com": "monevator",
    "moneytalksnews.com": "moneytalksnews",
    "alphaarchitect.com": "alphaarchitect",
    "thecollegeinvestor.com": "collegeinvestor",
    "marginalrevolution.com": "marginalrevolution",
    "nerdwallet.com": "nerdwallet",
    "kiplinger.com": "kiplinger",
}
```

**再利用する既存コード:**

| コンポーネント | ファイル | 用途 |
|--------------|---------|------|
| `ScrapingPolicy` | `src/rss/services/company_scrapers/scraping_policy.py` | UA rotation, ドメインレート制限 |
| `ArticleExtractor` | `src/rss/services/article_extractor.py` | 本文抽出（trafilatura→lxml fallback） |
| `filter_by_date()` | `scripts/session_utils.py` | 日付フィルタ |
| `select_top_n()` | `scripts/session_utils.py` | 上位N件選択 |
| `write_session_file()` | `scripts/session_utils.py` | セッションJSON出力 |
| `HTTPClient` | `src/rss/core/http_client.py` | HTTP リクエスト |
| `FeedParser` | `src/rss/core/parser.py` | RSS/Atom パース |

---

### Step 4: フィード検証スクリプト（Step 2 に依存）

#### 4a. `scripts/validate_rss_presets.py`（新規）

任意のプリセットJSONを検証する汎用スクリプト。

```bash
uv run python scripts/validate_rss_presets.py \
  data/config/rss-presets-wealth.json --check-robots
```

処理:
1. プリセットJSON読み込み・構造バリデーション
2. 各URL: `HTTPClient.validate_url()` で HTTP HEAD チェック
3. `--check-robots`: `RobotsChecker.check()` で robots.txt 確認
4. 結果テーブル: URL | Status (OK/FAIL/WARN) | HTTP Code | robots.txt

---

### Step 5: スキル定義

#### 5a. `.claude/skills/scrape-finance-blog/SKILL.md`（新規）

```yaml
---
name: scrape-finance-blog
description: 英語Wealth/Financeブログ15サイトからRSS収集+サイトマップバックフィルし、
  テーマ別に整理してMarkdown保存する。/scrape-finance-blog コマンドで使用。
allowed-tools: Read, Bash, Write, Glob, Grep, ToolSearch, Task
---
```

**4フェーズ構成:**

1. **モード判定**
   - `--mode backfill`: サイトマップベースの全件取得
   - `--mode incremental`（デフォルト）: RSSベースの差分取得

2. **スクレイピング実行**
   - `scripts/scrape_wealth_blogs.py` を Bash で実行
   - 出力: `data/scraped/wealth/{domain}/` + `.tmp/wealth-scrape-*.json`

3. **テーマ別グルーピング + 関連度分析**
   - セッションJSON を読み込み
   - 各テーマの主要記事をサマリー

4. **結果報告**
   - 統計表示（フィード数、記事数、Tier別内訳）
   - テーマ別トップ記事リスト
   - 取得進捗（backfill時: N/total per domain）
   - エラー・警告一覧

---

### Step 6: テスト

#### 6a. `tests/rss/unit/test_wealth_presets.py`（新規）

```python
class TestWealthPresetsStructure:
    def test_正常系_プリセットJSONが有効な構造を持つ(self) -> None: ...
    def test_正常系_全プリセットに必須フィールドがある(self) -> None: ...
    def test_正常系_URLがユニーク(self) -> None: ...
    def test_正常系_fetch_intervalが有効な値(self) -> None: ...
    def test_正常系_categoryがwealthである(self) -> None: ...
```

#### 6b. `tests/rss/unit/utils/test_robots_checker.py`（新規）

```python
class TestRobotsChecker:
    def test_正常系_許可されたURLでTrue(self) -> None: ...
    def test_正常系_禁止されたURLでFalse(self) -> None: ...
    def test_正常系_crawl_delayの取得(self) -> None: ...
    def test_正常系_ai_directivesの検出(self) -> None: ...
    def test_異常系_robots_txt取得失敗でデフォルト許可(self) -> None: ...
    def test_正常系_ドメインキャッシュが機能する(self) -> None: ...
```

#### 6c. `tests/rss/unit/storage/test_scrape_state_db.py`（新規）

```python
class TestScrapeStateDB:
    def test_正常系_URLを記録して取得済み判定(self) -> None: ...
    def test_正常系_未取得URLのフィルタリング(self) -> None: ...
    def test_正常系_失敗URLのリトライ取得(self) -> None: ...
    def test_正常系_ドメイン別統計の取得(self) -> None: ...
    def test_正常系_サイトマップ進捗の更新と取得(self) -> None: ...
    def test_エッジケース_空のDBでの各操作(self) -> None: ...
    def test_正常系_WALモードが有効(self) -> None: ...
```

#### 6d. `tests/rss/unit/utils/test_sitemap_parser.py`（新規）

```python
class TestSitemapParser:
    def test_正常系_単一サイトマップのパース(self) -> None: ...
    def test_正常系_サイトマップインデックスの再帰パース(self) -> None: ...
    def test_正常系_記事URLのフィルタリング(self) -> None: ...
    def test_正常系_lastmodの取得(self) -> None: ...
    def test_異常系_不正なXMLでエラー(self) -> None: ...
    def test_正常系_各プラットフォーム形式の対応(self) -> None: ...
```

`pytest-httpserver`（既存dev依存）+ `unittest.mock.patch` でモック。

---

### Step 7: ワークフロー統合

#### 7a. `scripts/prepare_asset_management_session.py`（変更）

- `--presets` 引数追加（デフォルト `jp`、パス指定で任意のプリセット）
- `WEALTH_URL_TO_SOURCE_KEY` マッピング追加
- 既存の `load_rss_presets()` がすでに `presets_path` を受け取るため、CLI引数の追加のみ

---

## 実装順序と依存関係

```
Step 1a,1b,1c,1d (設定ファイル) ──── 並列、依存なし
Step 2a (状態DB) ────────────────── 独立
Step 2b,2c (robots/sitemap) ─────── 独立

Step 6a (プリセットテスト) ←─── Step 1a
Step 6c (状態DBテスト) ←────── Step 2a
Step 6b (robots テスト) ←───── Step 2b
Step 6d (sitemap テスト) ←──── Step 2c

Step 4  (検証スクリプト) ←───── Step 1a, 2b
Step 3  (メインスクレイパー) ←── Step 1a,1b,1c,1d, 2a,2b,2c

Step 5  (スキル定義) ←────────── Step 3
Step 7  (ワークフロー統合) ←─── Step 1a
```

推奨実装順:
1. Step 1a + 1b + 1c + 1d（設定ファイル、並列）
2. Step 2a（状態DB）+ Step 2b + 2c（robots/sitemap）
3. Step 6a + 6b + 6c + 6d（テスト — TDD）
4. Step 3a（メインスクレイパー — incremental モード先行）
5. Step 3a 続き（backfill モード追加）
6. Step 4a（検証スクリプト）
7. Step 5a（スキル定義）
8. Step 7a（ワークフロー統合）

---

## ファイル一覧

### 新規作成（14ファイル）

| ファイル | 種別 | 説明 |
|---------|------|------|
| `data/config/rss-presets-wealth.json` | JSON | 15フィードプリセット |
| `data/config/wealth-management-themes.json` | JSON | 6テーマ定義 |
| `data/config/wealth-sitemap-config.json` | JSON | サイトマップ設定 |
| `src/rss/config/__init__.py` | Python | パッケージ init |
| `src/rss/config/wealth_scraping_config.py` | Python | ドメインレート制限 + サイトマップURL + バックフィルTier |
| `src/rss/storage/scrape_state_db.py` | Python | スクレイピング状態DB（SQLite） |
| `src/rss/utils/robots_checker.py` | Python | robots.txt チェッカー |
| `src/rss/utils/sitemap_parser.py` | Python | サイトマップパーサー |
| `scripts/scrape_wealth_blogs.py` | Python | メインCLIスクリプト（2モード対応） |
| `scripts/validate_rss_presets.py` | Python | プリセット検証 |
| `.claude/skills/scrape-finance-blog/SKILL.md` | Markdown | スキル定義 |
| `tests/rss/unit/test_wealth_presets.py` | Python | プリセットテスト |
| `tests/rss/unit/utils/test_robots_checker.py` | Python | robots checker テスト |
| `tests/rss/unit/utils/test_sitemap_parser.py` | Python | sitemap parser テスト |
| `tests/rss/unit/storage/test_scrape_state_db.py` | Python | 状態DB テスト |

### 変更（2ファイル）

| ファイル | 変更内容 |
|---------|---------|
| `src/rss/utils/__init__.py` | RobotsChecker, SitemapParser エクスポート追加 |
| `scripts/prepare_asset_management_session.py` | `--presets` 引数 + WEALTH_URL_TO_SOURCE_KEY |

### 再利用（変更不要）

| ファイル | 用途 |
|---------|------|
| `src/rss/services/feed_manager.py` | `apply_presets()` でフィード一括登録 |
| `src/rss/services/article_extractor.py` | 本文抽出（3段階フォールバック） |
| `src/rss/services/company_scrapers/scraping_policy.py` | UA rotation + レート制限 |
| `src/rss/core/http_client.py` | HTTP リクエスト |
| `src/rss/core/parser.py` | RSS/Atom パース |
| `scripts/session_utils.py` | filter_by_date, select_top_n, write_session_file |

---

## 検証方法

### 1. プリセット検証
```bash
uv run python scripts/validate_rss_presets.py \
  data/config/rss-presets-wealth.json --check-robots
```

### 2. フィード登録（MCP経由）
```bash
# apply_presets でフィード一括登録
rss_list_feeds(category="wealth")
```

### 3. Incremental スクレイピング
```bash
uv run python scripts/scrape_wealth_blogs.py --mode incremental --days 7 --verbose
```

### 4. Backfill スクレイピング（小規模サイトから）
```bash
# Tier A のみ（小規模サイト）
uv run python scripts/scrape_wealth_blogs.py --mode backfill --backfill-tier A --verbose

# 特定ドメインのみ
uv run python scripts/scrape_wealth_blogs.py --mode backfill --domain bitsaboutmoney.com

# 取得制限付き（テスト用）
uv run python scripts/scrape_wealth_blogs.py --mode backfill --limit 10 --dry-run
```

### 5. 取得進捗確認
```bash
uv run python scripts/scrape_wealth_blogs.py --mode backfill --dry-run
# → ドメイン別の total/scraped/pending を表示
```

### 6. 失敗記事の再取得
```bash
uv run python scripts/scrape_wealth_blogs.py --retry-failed
```

### 7. スキル経由の実行
```
/scrape-finance-blog --mode incremental --days 7
/scrape-finance-blog --mode backfill --backfill-tier A
```

### 8. テスト
```bash
uv run pytest tests/rss/unit/test_wealth_presets.py -v
uv run pytest tests/rss/unit/utils/test_robots_checker.py -v
uv run pytest tests/rss/unit/utils/test_sitemap_parser.py -v
uv run pytest tests/rss/unit/storage/test_scrape_state_db.py -v
make check-all
```

### 9. 出力確認
```bash
ls data/scraped/wealth/
cat .tmp/wealth-scrape-*.json | python -m json.tool | head -50
sqlite3 data/wealth_scrape.db "SELECT domain, COUNT(*), SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) FROM scraped_articles GROUP BY domain;"
```
