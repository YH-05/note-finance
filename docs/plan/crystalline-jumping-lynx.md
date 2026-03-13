# Wealth Finance Blog RSS収集・スクレイピング実装計画

## Context

`data/rss_sources/` から特定した投資・資産形成関連の英語ブログ群を、既存のRSSインフラ（`src/rss/`）に統合する。18サイト候補を調査した結果、15サイト（Tier 1: 11, Tier 2: 3, Tier 3: 1）を採用。主な発見：

- **Alpha Architect**: hCaptchaはフォームのみ → RSS (`/feed/`) が正常動作 → Tier 1に昇格
- **Kiplinger**: RSS 403 だが Playwright でブログ一覧・記事本文とも取得可 → Tier 3
- **Good Financial Cents**: 2024年6月以降更新なし → 除外
- **Penny Hoarder / Investopedia**: 日付不明・bot検出 → 除外

取得間隔は `daily`（note記事を毎日書くため）。スキル `/scrape-finance-blog` から随時呼び出し可能にする。

---

## 対象フィード一覧（15サイト）

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
    "thecollegeinvestor.com": 10.0,
    "moneytalksnews.com": 5.0,
    "marginalrevolution.com": 5.0,
    "kiplinger.com": 10.0,
    "nerdwallet.com": 5.0,
}
```

既存 `ScrapingPolicy(domain_rate_limits=...)` で消費。

---

### Step 2: robots.txt チェッカー（独立ユーティリティ）

#### 2a. `src/rss/utils/robots_checker.py`（新規）

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

#### 2b. `src/rss/utils/__init__.py`（変更）

```python
from rss.utils.robots_checker import RobotsCheckResult, RobotsChecker
```

を `__all__` に追加。

---

### Step 3: メインスクレイパースクリプト（Step 1, 2 に依存）

#### 3a. `scripts/scrape_wealth_blogs.py`（新規）

`prepare_ai_research_session.py` のバッチスクレイピングパターンと `prepare_asset_management_session.py` のテーママッチングパターンを組み合わせ。

**処理フロー:**

```
scrape_wealth_blogs.py
  │
  ├─ Phase 1: 設定読み込み
  │   ├─ rss-presets-wealth.json
  │   ├─ wealth-management-themes.json
  │   ├─ ScrapingPolicy(domain_rate_limits=WEALTH_DOMAIN_RATE_LIMITS)
  │   └─ ArticleExtractor
  │
  ├─ Phase 2: RSS取得 + 本文抽出（Tier 1+2）
  │   ├─ httpx + feedparser で各フィードのRSS取得
  │   ├─ filter_by_date(items, days) で日付フィルタ
  │   ├─ ArticleExtractor.extract() で本文抽出
  │   ├─ ScrapingPolicy.wait_for_domain() でレート制限
  │   └─ Markdown保存: data/scraped/wealth/{YYYY-MM-DD}/{domain}/{slug}.md
  │
  ├─ Phase 3: Playwrightスクレイピング（Tier 3 = Kiplinger）
  │   ├─ httpx + UA rotation で記事一覧ページ取得（403ならPlaywright fallback）
  │   ├─ lxml/cssselect で記事URL・タイトル・要約を抽出
  │   ├─ 各記事: ArticleExtractor.extract() で本文抽出
  │   └─ Markdown保存（同上）
  │
  └─ Phase 4: セッションJSON出力
      ├─ テーマ別キーワードマッチング（themes.json 参照）
      ├─ .tmp/wealth-scrape-{YYYYMMDD}-{HHMMSS}.json
      └─ サマリー統計表示
```

**CLI引数:**

```bash
uv run python scripts/scrape_wealth_blogs.py \
  --days 7        # 日付フィルタ（デフォルト7）
  --tier all      # 1/2/3/all（デフォルト all）
  --top-n 10      # テーマ別最大記事数
  --check-robots  # robots.txt チェック有効
  --dry-run       # フィード一覧表示のみ
  --verbose       # デバッグログ
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
description: 英語Wealth/Financeブログ15サイトからRSS収集+Playwrightスクレイピングし、
  テーマ別に整理してMarkdown保存する。/scrape-finance-blog コマンドで使用。
allowed-tools: Read, Bash, Write, Glob, Grep, ToolSearch, Task
---
```

**3フェーズ構成:**

1. **RSS取得 + Playwright スクレイピング**
   - `scripts/scrape_wealth_blogs.py` を Bash で実行
   - 出力: `data/scraped/wealth/{date}/` + `.tmp/wealth-scrape-*.json`

2. **テーマ別グルーピング + 関連度分析**
   - セッションJSON を読み込み
   - 各テーマの主要記事をサマリー

3. **結果報告**
   - 統計表示（フィード数、記事数、Tier別内訳）
   - テーマ別トップ記事リスト
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
Step 1a,1b,1c (設定ファイル) ──── 並列、依存なし
Step 2a,2b    (robots checker) ── 並列、依存なし

Step 6a (プリセットテスト) ←─── Step 1a
Step 6b (robots テスト) ←────── Step 2a

Step 4  (検証スクリプト) ←───── Step 1a, 2a
Step 3  (メインスクレイパー) ←── Step 1a,1b,1c, 2a

Step 5  (スキル定義) ←────────── Step 3
Step 7  (ワークフロー統合) ←─── Step 1a
```

推奨実装順:
1. Step 1a + 1b + 1c（設定ファイル、並列）
2. Step 2a + 2b（robots checker）
3. Step 6a + 6b（テスト — TDD）
4. Step 3a（メインスクレイパー）
5. Step 4a（検証スクリプト）
6. Step 5a（スキル定義）
7. Step 7a（ワークフロー統合）

---

## ファイル一覧

### 新規作成（10ファイル）

| ファイル | 種別 | 説明 |
|---------|------|------|
| `data/config/rss-presets-wealth.json` | JSON | 15フィードプリセット |
| `data/config/wealth-management-themes.json` | JSON | 6テーマ定義 |
| `src/rss/config/__init__.py` | Python | パッケージ init |
| `src/rss/config/wealth_scraping_config.py` | Python | ドメインレート制限 |
| `src/rss/utils/robots_checker.py` | Python | robots.txt チェッカー |
| `scripts/scrape_wealth_blogs.py` | Python | メインCLIスクリプト |
| `scripts/validate_rss_presets.py` | Python | プリセット検証 |
| `.claude/skills/scrape-finance-blog/SKILL.md` | Markdown | スキル定義 |
| `tests/rss/unit/test_wealth_presets.py` | Python | プリセットテスト |
| `tests/rss/unit/utils/test_robots_checker.py` | Python | robots checker テスト |

### 変更（2ファイル）

| ファイル | 変更内容 |
|---------|---------|
| `src/rss/utils/__init__.py` | RobotsChecker, RobotsCheckResult エクスポート追加 |
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

### 3. スクレイピング実行
```bash
uv run python scripts/scrape_wealth_blogs.py --days 7 --tier all --verbose
```

### 4. スキル経由の実行
```
/scrape-finance-blog --days 7
```

### 5. テスト
```bash
uv run pytest tests/rss/unit/test_wealth_presets.py -v
uv run pytest tests/rss/unit/utils/test_robots_checker.py -v
make check-all
```

### 6. 出力確認
```bash
ls data/scraped/wealth/$(date +%Y-%m-%d)/
cat .tmp/wealth-scrape-*.json | python -m json.tool | head -50
```
