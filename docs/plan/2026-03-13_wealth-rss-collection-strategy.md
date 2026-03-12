# 投資・資産形成ブログのRSS収集・スクレイピング戦略

## Context

`data/rss_sources/` に保存された12個のJSONファイル（Google Sheetsから取得）の中から、投資・資産形成・ウェルスマネジメントに関連する18サイトを特定済み。これらのコンテンツをnote記事のネタ・データ・主張の参照元として活用するため、既存のRSSインフラに統合する。

**既存インフラの活用**: `src/rss/`（FeedManager, FeedFetcher, ArticleExtractor, ScrapingPolicy, MCP Server）を最大限再利用し、新規コード量を最小化する。

---

## 収集対象サイト（全18サイト）

### Tier 1: 無料 + RSS取得可能 + 制限なし（10サイト）

| サイト | RSS URL | テーマ |
|--------|---------|--------|
| Of Dollars and Data | `https://ofdollarsanddata.com/feed/` | データ駆動投資 |
| A Wealth of Common Sense | `https://awealthofcommonsense.com/feed/` | 行動ファイナンス |
| The Big Picture (Ritholtz) | `http://ritholtz.com/feed/` | 市場解説 |
| The Dividend Guy Blog | `https://thedividendguyblog.com/feed/` | 配当成長投資 |
| Good Financial Cents | `https://www.goodfinancialcents.com/feed/` | 退職計画 |
| Money Crashers | `https://www.moneycrashers.com/feed/` | 投資・保険 |
| Clever Girl Finance | `https://clevergirlfinance.com/feed/` | 女性向け資産形成 |
| Afford Anything | `https://affordanything.com/feed/` | FIRE・不動産 |
| Bits about Money | `https://bitsaboutmoney.com/archive/rss/` | 金融インフラ |
| The Penny Hoarder | `https://thepennyhoarder.com/rss/` | パーソナルファイナンス |

### Tier 2: 利用可能だが注意あり（4サイト）

| サイト | RSS URL | 注意点 |
|--------|---------|--------|
| Monevator | `https://monevator.com/feed/` | crawl-delay: 240秒 |
| Money Talks News | `https://moneytalksnews.com/feed/` | ai-train=no |
| The College Investor | `https://thecollegeinvestor.com/feed/` | AIボット明示ブロック |
| Marginal Revolution | `https://marginalrevolution.com/feed` | マクロ経済視点 |

### Tier 3: Playwright必須（1サイト）

| サイト | 状況 |
|--------|------|
| Alpha Architect | hCaptcha + WP Rocket。RSS URL存在するが自動取得不可 |

### 既存プリセット活用（3サイト、重複登録しない）

| サイト | 状態 |
|--------|------|
| Kiplinger | `rss-presets.json` に未登録 → `wealth` プリセットに追加 |
| NerdWallet | `rss-presets.json` に未登録 → `wealth` プリセットに追加 |
| Investopedia | `rss-presets.json` に未登録 → `wealth` プリセットに追加 |

---

## 実装計画

### Step 1: プリセットファイル作成

**ファイル**: `data/config/rss-presets-wealth.json`

```json
{
    "version": "1.0",
    "presets": [
        {
            "url": "https://ofdollarsanddata.com/feed/",
            "title": "Of Dollars and Data",
            "category": "wealth",
            "fetch_interval": "weekly",
            "enabled": true
        },
        ...
    ]
}
```

- カテゴリ: 全フィードに `"wealth"` を使用（既存の `finance`, `market` と分離）
- 取得間隔: ブログの更新頻度に合わせ `"weekly"`
- Tier 1/2: `enabled: true`（14フィード）
- Tier 3 (Alpha Architect): `enabled: false`
- Kiplinger, NerdWallet, Investopedia: `enabled: true`（計17有効フィード）

### Step 2: robots.txt チェッカー

**ファイル**: `src/rss/utils/robots_checker.py`（新規）

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
```

- `urllib.robotparser.RobotFileParser` を使用
- ドメイン単位でキャッシュ（同一ドメインの再取得回避）
- 非標準ディレクティブ（`ai-train`, `GPTBot`等）も検出

**依存**: 標準ライブラリ + httpx（既存依存）

### Step 3: ドメイン別レート制限設定

**ファイル**: `src/rss/config/wealth_scraping_config.py`（新規）

```python
WEALTH_DOMAIN_RATE_LIMITS: dict[str, float] = {
    "monevator.com": 240.0,
    "thecollegeinvestor.com": 10.0,
    "moneytalksnews.com": 5.0,
}
```

- 既存の `ScrapingPolicy(domain_rate_limits=...)` で消費
- `ArticleExtractor` での本文取得時に適用

### Step 4: フィード検証スクリプト

**ファイル**: `scripts/validate_rss_presets.py`（新規）

```bash
uv run python scripts/validate_rss_presets.py \
  --presets data/config/rss-presets-wealth.json \
  --check-robots
```

処理:
1. プリセットJSON読み込み
2. 各URL: HTTP HEAD → RSS形式バリデーション → (optional) robots.txt チェック
3. 結果サマリー出力（OK/FAIL/WARN）

**再利用**: `HTTPClient.validate_url()`, `FeedParser.parse()`

### Step 5: フィード登録・取得スクリプト

**ファイル**: `scripts/register_wealth_feeds.py`（新規）

```bash
# 検証 → 登録 → 取得
uv run python scripts/register_wealth_feeds.py --validate --register --fetch
```

処理:
1. `FeedManager.apply_presets("data/config/rss-presets-wealth.json")` で一括登録
2. `FeedFetcher.fetch_all_async(category="wealth")` で取得
3. 結果: `PresetApplyResult`（added/skipped/failed）+ `BatchStats`

**再利用**: `FeedManager`, `FeedFetcher`（変更不要）

### Step 6: 資産形成ワークフロー統合

**変更ファイル**: `scripts/prepare_asset_management_session.py`

変更内容:
1. `--presets` 引数を追加（デフォルト: `rss-presets-jp.json`、`rss-presets-wealth.json` も指定可能）
2. `URL_TO_SOURCE_KEY` に英語ブログのドメインマッピングを追加

```python
WEALTH_URL_TO_SOURCE_KEY: dict[str, str] = {
    "ofdollarsanddata.com": "ofdollarsanddata",
    "awealthofcommonsense.com": "awealthofcommonsense",
    "ritholtz.com": "ritholtz",
    "thedividendguyblog.com": "dividendguy",
    "goodfinancialcents.com": "goodfinancialcents",
    "moneycrashers.com": "moneycrashers",
    "clevergirlfinance.com": "clevergirlfinance",
    "affordanything.com": "affordanything",
    "bitsaboutmoney.com": "bitsaboutmoney",
    "thepennyhoarder.com": "pennyhoarder",
    "monevator.com": "monevator",
    "moneytalksnews.com": "moneytalksnews",
    "thecollegeinvestor.com": "collegeinvestor",
    "marginalrevolution.com": "marginalrevolution",
}
```

### Step 7: 英語ブログ用テーマ設定

**ファイル**: `data/config/wealth-management-themes.json`（新規）

5テーマ:
- `data_driven_investing`: データ駆動投資（Of Dollars and Data, A Wealth of Common Sense, Ritholtz）
- `dividend_income`: 配当・インカム投資（Dividend Guy, Good Financial Cents）
- `fire_wealth_building`: FIRE・資産形成（Afford Anything, Clever Girl Finance, Penny Hoarder）
- `financial_infrastructure`: 金融インフラ（Bits about Money）
- `personal_finance`: パーソナルファイナンス（Money Crashers, Monevator, Marginal Revolution）

### Step 8: テスト

| テストファイル | 内容 |
|--------------|------|
| `tests/rss/unit/test_wealth_presets.py` | プリセットJSON構造検証、URL重複チェック |
| `tests/rss/unit/utils/test_robots_checker.py` | RobotsChecker のユニットテスト |
| `tests/scripts/test_validate_rss_presets.py` | 検証スクリプトのテスト |

---

## 実装順序

```
Step 1 (プリセットJSON) ─────────────────────┐
Step 2 (robots.txt チェッカー) ────────┐      │
Step 3 (レート制限設定) ──────────┐     │      │
                                 │     │      │
Step 4 (検証スクリプト) ←────────┘─────┘──────┘
Step 5 (登録・取得スクリプト) ←── Step 1, 3
Step 6 (ワークフロー統合) ←──── Step 1, 5
Step 7 (テーマ設定) ←─────────── Step 1
Step 8 (テスト) ←─────────────── 全Step
```

並列実行可能: Step 1, 2, 3 は独立

---

## 重要ファイル一覧

### 新規作成（7ファイル）
| ファイル | 説明 |
|---------|------|
| `data/config/rss-presets-wealth.json` | 17フィードのプリセット定義 |
| `data/config/wealth-management-themes.json` | 英語ブログ5テーマ設定 |
| `src/rss/utils/robots_checker.py` | robots.txt チェッカー |
| `src/rss/config/wealth_scraping_config.py` | ドメイン別レート制限 |
| `scripts/validate_rss_presets.py` | フィードURL検証CLIスクリプト |
| `scripts/register_wealth_feeds.py` | フィード登録・取得CLIスクリプト |
| `tests/rss/unit/utils/test_robots_checker.py` | RobotsChecker テスト |

### 変更（1ファイル）
| ファイル | 変更内容 |
|---------|---------|
| `scripts/prepare_asset_management_session.py` | `--presets` 引数追加 + 英語ブログURLマッピング |

### 再利用（変更不要）
| ファイル | 用途 |
|---------|------|
| `src/rss/services/feed_manager.py` | `apply_presets()` でフィード一括登録 |
| `src/rss/services/feed_fetcher.py` | `fetch_all_async(category="wealth")` で取得 |
| `src/rss/services/article_extractor.py` | 3段階フォールバックで本文取得 |
| `src/rss/services/company_scrapers/scraping_policy.py` | UA rotation + レート制限 |
| `src/rss/core/http_client.py` | HTTPリクエスト + リトライ |
| `src/rss/core/parser.py` | RSS/Atom パース |

---

## 検証方法

### 1. プリセット検証
```bash
uv run python scripts/validate_rss_presets.py \
  --presets data/config/rss-presets-wealth.json \
  --check-robots
```

### 2. フィード登録・取得
```bash
uv run python scripts/register_wealth_feeds.py --register --fetch
```

### 3. MCP経由での確認
```
rss_list_feeds(category="wealth")        # 登録確認
rss_search_items(query="dividend", category="wealth")  # 記事検索
```

### 4. テスト実行
```bash
uv run pytest tests/rss/unit/test_wealth_presets.py -v
uv run pytest tests/rss/unit/utils/test_robots_checker.py -v
make check-all
```

### 5. ワークフロー統合テスト
```bash
uv run python scripts/prepare_asset_management_session.py \
  --presets data/config/rss-presets-wealth.json \
  --theme data_driven_investing --days 14 --top-n 5
```

---

## リスクと対策

| リスク | 対策 |
|--------|------|
| Monevator 240秒クロールディレイ | `WEALTH_DOMAIN_RATE_LIMITS` で自動制御 |
| College Investor AIボットブロック | UA rotation + `enabled: true` で試行、失敗時は `enabled: false` に |
| Money Talks News ai-train=no | RSS購読・記事参照は可。AI学習目的の利用は避ける |
| Alpha Architect hCaptcha | `enabled: false`。手動 or Playwright MCP で都度取得 |
| `apply_presets()` 重複実行 | `FeedAlreadyExistsError` を graceful に処理（skipped カウント） |
