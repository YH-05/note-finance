# 投資レポートスクレイパーパッケージ (`report_scraper`) 実装計画

## Context

週次マーケットレポート作成にあたり、主要セルサイド・バイサイドの無料公開レポートを効率的に収集する仕組みが必要。現在は手動でWebサイトを巡回しているが、約25以上のソースがあり自動化の効果が大きい。`src/report_scraper/` として新規独立パッケージを作成し、CLIから週次で手動実行する。

---

## 調査結果: 無料で取得可能なソース一覧

### Tier A: バイサイド（資産運用会社）

| Provider | URL | 取得方法 | コンテンツ種別 |
|----------|-----|----------|--------------|
| **BlackRock (BII)** | `blackrock.com/corporate/insights/blackrock-investment-institute/archives` | 静的HTML + PDF | 週次コメンタリー、年次アウトルック |
| **Vanguard** | `advisors.vanguard.com/insights/article/series/market-perspectives` | 静的HTML | マーケットパースペクティブ |
| **PIMCO** | `pimco.com/gbl/en/insights` | Playwright (Coveo JS) | 投資アイデア、アウトルック |
| **State Street (SSGA)** | `ssga.com/us/en/institutional/insights` | 静的HTML | グローバルマーケットアウトルック |
| **Fidelity** | `fidelity.com/learning-center/trading-investing/economic-outlook` | 静的HTML | 経済見通し、四半期更新 |
| **T. Rowe Price** | `troweprice.com/en/us/insights/global-market-outlook` | 静的HTML | グローバルマーケットアウトルック |
| **Invesco** | `invesco.com/us/en/insights/global-investment-outlook.html` | 静的HTML | 投資アウトルック |
| **Schroders** | `schroders.com/en/global/individual/outlook/` | 静的HTML | 投資アウトルック |
| **Lazard AM** | `lazardassetmanagement.com/us/en_us/research-insights` | 静的HTML | グローバルアウトルック |
| **Northern Trust** | `ntam.northerntrust.com/.../global-investment-outlook` | 静的HTML | グローバル投資見通し |
| **Charles Schwab** | `schwab.com/learn/market-commentary` | 静的HTML | マーケットパースペクティブ、セクター見通し |

### Tier B: セルサイド（投資銀行）

| Provider | URL | 取得方法 | コンテンツ種別 |
|----------|-----|----------|--------------|
| **Goldman Sachs** | `goldmansachs.com/insights/goldman-sachs-research` | Playwright (React SPA) | リサーチインサイト |
| **JP Morgan** | `jpmorgan.com/insights/markets-and-economy` | Playwright (動的ローディング) | マーケット&エコノミー |
| **Morgan Stanley** | `morganstanley.com/im/.../all-insights.html` | 静的HTML + JSON API | インサイト（JSON API `/im/json/imwebdata/data`） |
| **Bank of America** | `privatebank.bankofamerica.com/articles` | 静的HTML | プライベートバンク週次レキャップ |
| **Deutsche Bank** | `dbresearch.com` | 静的HTML | リサーチ、Chart of the Day |
| **UBS** | `ubs.com/global/en/wealthmanagement/insights` | 混在 | CIO House View（週次/日次） |
| **Barclays** | `ib.barclays/our-insights.html` | 混在 | 週次インサイト、アウトルック |
| **Citi** | `citigroup.com/global/insights/all` | 混在 | Citi GPS、リサーチ |
| **Nomura** | `nomuraconnects.com` | 混在 | エコノミクス、マーケットインサイト |
| **Wells Fargo** | `wellsfargoadvisors.com/research-analysis/strategy/weekly.htm` | 静的HTML | 投資戦略ウィークリー |
| **HSBC** | `privatebanking.hsbc.com` | 静的HTML | 投資アウトルック |

### Tier C: アグリゲーター

| Provider | URL | 取得方法 | 特徴 |
|----------|-----|----------|------|
| **Advisor Perspectives** | `advisorperspectives.com/commentaries.rss` | **RSS** | 50社以上のコメンタリーを集約。**最も取得が容易** |

---

## パッケージ構成

```
src/report_scraper/
├── __init__.py              # Public API (__all__)
├── py.typed                 # PEP 561
├── _logging.py              # structlog lazy init (news_scraper/_logging.py パターン)
├── exceptions.py            # 例外階層
├── types.py                 # Pydantic + frozen dataclass 型定義
├── core/
│   ├── __init__.py
│   ├── base_scraper.py      # ABC: BaseReportScraper
│   ├── scraper_engine.py    # fetch → extract → store パイプライン
│   └── scraper_registry.py  # source_key → scraper インスタンスのレジストリ
├── scrapers/
│   ├── __init__.py
│   ├── _rss_scraper.py      # RSS ベース基底クラス
│   ├── _html_scraper.py     # 静的HTML ベース基底クラス (httpx + lxml/cssselect)
│   ├── _spa_scraper.py      # Playwright ベース基底クラス
│   ├── advisor_perspectives.py  # RSS
│   ├── blackrock.py         # 静的HTML + PDF
│   ├── morgan_stanley.py    # 静的HTML + JSON API
│   ├── goldman_sachs.py     # Playwright
│   ├── jpmorgan.py          # Playwright
│   └── ...                  # 追加ソースは設定ファイルで対応可能
├── services/
│   ├── __init__.py
│   ├── pdf_downloader.py    # PDF ダウンロード + ローカル保存
│   ├── content_extractor.py # テキスト抽出 (trafilatura → lxml フォールバック)
│   └── dedup_tracker.py     # URL ベース重複排除
├── storage/
│   ├── __init__.py
│   ├── json_store.py        # index.json + 実行履歴
│   └── pdf_store.py         # PDF ファイル整理
└── cli/
    ├── __init__.py
    └── main.py              # Click CLI
```

## 再利用する既存コード・パターン

| パターン | 参照元 | 用途 |
|---------|--------|------|
| structlog lazy init | `src/news_scraper/_logging.py` | `_logging.py` をコピー・適応 |
| Pydantic モデル + frozen dataclass | `src/news_scraper/types.py` | 型定義パターン |
| ABC base scraper | `src/rss/services/company_scrapers/base.py` | BaseReportScraper 設計 |
| Registry パターン | `src/rss/services/company_scrapers/registry.py` | ScraperRegistry |
| Engine パイプライン | `src/rss/services/company_scrapers/engine.py` | ScraperEngine 設計 |
| trafilatura + lxml 抽出 | `src/rss/services/article_extractor.py` | content_extractor.py |
| Playwright 3-tier | `src/rss/services/article_content_checker.py` | SPA scraper |
| Click CLI | `src/rss/cli/main.py` | CLI 設計 |
| RSS parsing | `src/rss/core/parser.py` (feedparser) | RSS scraper |

## 設定ファイル

`data/config/report-scraper-config.yaml`:

```yaml
global:
  output_dir: "data/raw/report-scraper"
  pdf_dir: "data/raw/report-scraper/pdfs"
  max_reports_per_source: 20
  request_timeout: 30
  playwright_timeout: 30000
  dedup_days: 30

sources:
  - key: advisor_perspectives
    name: "Advisor Perspectives"
    tier: aggregator
    listing_url: "https://www.advisorperspectives.com/commentaries.rss"
    rendering: rss
    tags: ["multi_firm", "commentary"]

  - key: blackrock_bii
    name: "BlackRock Investment Institute"
    tier: buy_side
    listing_url: "https://www.blackrock.com/corporate/insights/blackrock-investment-institute/archives"
    rendering: static
    pdf_selector: "a[href$='.pdf']"
    tags: ["macro", "weekly"]
    # PDF URL パターン: /corporate/literature/market-commentary/weekly-investment-commentary-en-us-YYYYMMDD-*.pdf

  - key: goldman_sachs
    name: "Goldman Sachs Research"
    tier: sell_side
    listing_url: "https://www.goldmansachs.com/insights/goldman-sachs-research"
    rendering: playwright
    tags: ["macro", "equity", "research"]
  # ... 他ソースも同様に追加
```

## 出力形式

```
data/raw/report-scraper/
├── index.json                   # 全レポートのインデックス
├── runs/
│   └── 2026-03-02T100000.json   # 実行ごとの結果サマリー
├── text/
│   ├── blackrock_bii/
│   │   └── 2026-03-01_weekly-commentary.txt
│   └── goldman_sachs/
│       └── 2026-02-28_markets-outlook.txt
└── pdfs/
    ├── blackrock_bii/
    │   └── 2026-03-01_weekly-commentary.pdf
    └── ...
```

## CLI インターフェース

```bash
# 全ソースから収集
report-scraper collect

# 特定ソースのみ
report-scraper collect --source blackrock_bii --source goldman_sachs

# Tier で絞り込み
report-scraper collect --tier buy_side

# PDF ダウンロードなし（テキストのみ）
report-scraper collect --no-download-pdfs

# ソース一覧表示
report-scraper list

# 単一ソースのテスト（dry run）
report-scraper test-source blackrock_bii

# 収集履歴
report-scraper history --days 7
```

## 段階的実装計画

### Phase 1: 基盤 + RSS ソース
1. パッケージスケルトン作成（`__init__.py`, `py.typed`, `_logging.py`, `exceptions.py`, `types.py`）
2. `config/loader.py`（YAML → Pydantic バリデーション）
3. `core/base_scraper.py`（ABC）
4. `scrapers/_rss_scraper.py` + `scrapers/advisor_perspectives.py`
5. `services/content_extractor.py`（trafilatura + lxml）
6. `storage/json_store.py`
7. 最小限 CLI: `collect --source advisor_perspectives`
8. `pyproject.toml` 更新（packages, scripts）
9. ユニットテスト: types, config loader, RSS scraper

### Phase 2: 静的 HTML ソース + PDF
1. `scrapers/_html_scraper.py`（CSS セレクターベース抽出）
2. `services/pdf_downloader.py` + `storage/pdf_store.py`
3. `services/dedup_tracker.py`
4. `scrapers/blackrock.py`, `scrapers/schwab.py`, `scrapers/morgan_stanley.py`, `scrapers/wells_fargo.py` 等
5. `core/scraper_engine.py`（完全パイプライン）
6. `core/scraper_registry.py`
7. CLI 拡張: `list`, `test-source`
8. ユニットテスト

### Phase 3: Playwright ソース
1. `scrapers/_spa_scraper.py`（Playwright ベース）
2. `scrapers/goldman_sachs.py`, `scrapers/jpmorgan.py`, `scrapers/pimco.py`
3. CLI 完成: `history`
4. 統合テスト

### Phase 4: 追加ソース・仕上げ
1. 残りの Tier A/B ソースを設定ファイルで追加
2. Markdown 形式の収集サマリーレポート出力
3. `README.md`

## pyproject.toml 変更

```toml
# packages に追加
[tool.hatch.build.targets.wheel]
packages = ["src/rss", "src/news", "src/automation", "src/news_scraper", "src/report_scraper"]

# scripts に追加
[project.scripts]
report-scraper = "report_scraper.cli.main:cli"

# cssselect は dev deps に既存、pyyaml を追加
[project.optional-dependencies]
report-scraper = ["pyyaml>=6.0"]
```

## 検証方法

```bash
# Phase 1 完了後
report-scraper collect --source advisor_perspectives
cat data/raw/report-scraper/index.json | python -m json.tool

# Phase 2 完了後
report-scraper collect --tier buy_side --no-download-pdfs
report-scraper collect --source blackrock_bii  # PDF 付き
report-scraper test-source schwab

# Phase 3 完了後
report-scraper collect --source goldman_sachs
report-scraper collect  # 全ソース

# 品質チェック
make check-all
```
