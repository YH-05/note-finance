# 投資信託・ETFデータベース構築計画

## Context

株投資ラボ（note.com金融ブログ）の記事執筆用に、日本の投資信託・ETFのデータベースを構築する。
以下4つの無料データソースから、マスタデータ・マクロ統計・ETF価格を取得するPythonパッケージを実装する。

**対象外**: eMAXIS CSV（三菱UFJ AM）、EDINET API、証券会社データ

## データソース

| # | ソース | 形式 | 内容 | 件数 |
|---|--------|------|------|------|
| 1 | NISA成長投資枠対象商品リスト（投資信託協会） | Excel .xlsx | 投信+ETF/REITマスタ | 2,260+397件 |
| 2 | JPX東証上場銘柄一覧 | Excel .xls | 全上場銘柄（ETF 452件含む） | 4,444件 |
| 3 | 投資信託協会統計データ | Excel .xlsx | マクロ統計（月次） | B-1/B-2/B-3/A-2 |
| 4 | ETF価格・パフォーマンス | yfinance via quants | 株価・Adj Close | ETF全銘柄 |

## パッケージ設計

`src/fund_db/` を単一パッケージとし、サブパッケージでソースを分離する。
理由: 全ソースが「日本の投信DB」という同一ドメインを構成し、共通型・ストレージ・CLIを共有するため。
既存の `report_scraper`（scrapers/サブモジュール群）と同じアーキテクチャ。

### ディレクトリ構造

```
src/fund_db/
├── __init__.py              # Public API
├── _logging.py              # structlog wrapper
├── py.typed                 # PEP 561
├── exceptions.py            # FundDbError hierarchy
├── types.py                 # 共通型 (DownloadResult, ParseResult)
├── config/
│   ├── __init__.py
│   └── constants.py         # DL URL, シート名, カラムマッピング
├── storage/
│   ├── __init__.py
│   └── json_store.py        # JSON永続化 (data/fund_db/ 配下)
├── nisa/
│   ├── __init__.py
│   ├── downloader.py        # httpx DL (unlisted + listed)
│   ├── parser.py            # openpyxl パース
│   └── models.py            # NisaUnlistedFund, NisaListedEtf
├── jpx/
│   ├── __init__.py
│   ├── downloader.py        # httpx DL (data_j.xls)
│   ├── parser.py            # pandas + xlrd パース
│   └── models.py            # JpxListedStock
├── toushin_stats/
│   ├── __init__.py
│   ├── downloader.py        # httpx DL (B-1, B-2, B-3, A-2)
│   ├── parser.py            # openpyxl 複数シート解析
│   └── models.py            # AssetFlowRecord, ProductClassRecord 等
├── etf_prices/
│   ├── __init__.py
│   ├── fetcher.py           # market.yfinance.YFinanceFetcher wrapper
│   └── models.py            # EtfPriceRecord, EtfPerformanceSummary
└── cli/
    ├── __init__.py
    └── main.py              # Click CLI (fund-db コマンド)
```

## データモデル

### NISA (`nisa/models.py`)

```python
class NisaUnlistedFund(BaseModel):
    """NISA成長投資枠対象 非上場投資信託 (2,260件)."""
    fund_code: str              # 投信協会ファンドコード
    fund_name: str              # ファンド名称
    management_company: str     # 運用会社名
    inception_date: date | None # 設定日
    redemption_date: date | None # 償還日 (None=無期限)
    growth_available_date: date | None
    dividend_frequency: str     # 年1回/年2回/四半期/隔月
    tsumitate_eligible: bool    # つみたて投資枠対象

class NisaListedEtf(BaseModel):
    """NISA成長投資枠対象 上場ETF/REIT (397件)."""
    ticker_code: str            # 銘柄コード (5桁)
    product_type: str           # 上場投信 or 上場投資法人
    fund_name: str
    management_company: str
    inception_date: date | None
    growth_available_date: date | None
    dividend_frequency: str
    tsumitate_eligible: bool
```

### JPX (`jpx/models.py`)

```python
class JpxListedStock(BaseModel):
    """JPX東証上場銘柄 (4,444件, ETF 452件)."""
    ticker_code: str            # コード (1301, 130A等)
    stock_name: str             # 銘柄名
    market_section: str         # プライム/スタンダード/ETF・ETN/REIT等
    sector_33_code: str | None  # 33業種コード (ETFは"-")
    sector_33_name: str | None
    sector_17_code: str | None
    sector_17_name: str | None
    scale_code: str | None      # TOPIX規模コード
    scale_name: str | None

    @property
    def is_etf(self) -> bool:
        return self.market_section == "ETF・ETN"

    @property
    def is_reit(self) -> bool:
        return "REIT" in self.market_section
```

### 統計データ (`toushin_stats/models.py`)

```python
class AssetFlowRecord(BaseModel):
    """B-1: 資産増減状況 (月次, 1989年〜)."""
    year: int
    month: int
    category: str               # 総合計/株式投信/公社債投信/ETF 等
    net_assets_million_yen: float | None  # 純資産総額(百万円)
    fund_count: int | None
    inflow_million_yen: float | None      # 設定額
    outflow_million_yen: float | None     # 解約額

class ProductClassRecord(BaseModel):
    """B-2: 商品分類別内訳 (月次, 2010年〜, 31シート)."""
    year: int
    month: int
    classification: str         # インデックス/アクティブ/ETF/国内株式 等
    net_assets_million_yen: float | None
    fund_count: int | None

class ManagementCompanyRecord(BaseModel):
    """B-3: 運用会社別 (スナップショット, 80社)."""
    company_name: str
    total_net_assets_million_yen: float | None
    stock_fund_net_assets_million_yen: float | None
    fund_count: int | None
```

### ETF価格 (`etf_prices/models.py`)

```python
class EtfPriceRecord(BaseModel):
    """ETF日次価格."""
    ticker_code: str
    date: date
    open: float | None
    high: float | None
    low: float | None
    close: float                # Adj Close (auto_adjust=True)
    volume: int | None

class EtfPerformanceSummary(BaseModel):
    """ETFパフォーマンスサマリー."""
    ticker_code: str
    fund_name: str | None
    period_start: date
    period_end: date
    total_return_pct: float
    annualized_return_pct: float | None
    volatility_pct: float | None
    max_drawdown_pct: float | None
```

## ETF価格取得 (`etf_prices/fetcher.py`)

quantsの `market.yfinance.YFinanceFetcher` を直接利用。薄いwrapperのみ。

```python
from market.yfinance import YFinanceFetcher

class EtfPriceFetcher:
    def __init__(self, fetcher: YFinanceFetcher | None = None):
        self._fetcher = fetcher or YFinanceFetcher()

    def fetch(self, tickers: list[str], start: str, end: str | None = None) -> list[EtfPriceRecord]:
        # 銘柄コード → "XXXX.T" 変換
        yf_symbols = [f"{t}.T" for t in tickers]
        results = self._fetcher.fetch(symbols=yf_symbols, start_date=start, end_date=end)
        return [self._to_record(r) for r in results]
```

## データ永続化

`data_paths.get_path()` でパス解決。日付パーティション。

```
data/fund_db/
├── raw_excel/
│   ├── nisa/{YYYY-MM-DD}/unlisted_fund.xlsx
│   ├── nisa/{YYYY-MM-DD}/listed_fund.xlsx
│   ├── jpx/{YYYY-MM-DD}/data_j.xls
│   └── toushin_stats/{YYYY-MM-DD}/B1_*.xlsx, B2_*.xlsx, ...
├── nisa/{YYYY-MM-DD}/unlisted_funds.json
├── nisa/{YYYY-MM-DD}/listed_etfs.json
├── jpx/{YYYY-MM-DD}/listed_stocks.json
├── jpx/{YYYY-MM-DD}/etfs.json
├── toushin_stats/{YYYY-MM-DD}/asset_flow.json
├── toushin_stats/{YYYY-MM-DD}/product_class.json
├── toushin_stats/{YYYY-MM-DD}/management_company.json
└── etf_prices/{ticker}/{YYYY-MM-DD}.json
```

## CLI設計

```bash
# NISA
fund-db nisa download          # Excel DL
fund-db nisa parse             # パース → JSON
fund-db nisa sync              # DL + パース (デフォルトワークフロー)
fund-db nisa list              # キャッシュ済みデータ表示

# JPX
fund-db jpx download
fund-db jpx parse
fund-db jpx sync
fund-db jpx list-etfs          # ETFのみフィルタ表示

# 統計
fund-db stats download
fund-db stats parse
fund-db stats sync
fund-db stats summary          # 最新サマリー表示

# ETF価格
fund-db etf fetch --tickers 1306,1321 --start 2024-01-01
fund-db etf performance --tickers 1306,1321 --years 3

# 一括
fund-db sync-all               # 全ソースDL+パース
fund-db status                 # データ鮮度サマリー
```

pyproject.toml entry:
```toml
fund-db = "fund_db.cli.main:cli"
```

## 依存関係の追加

```toml
# pyproject.toml [project] dependencies に追加
"openpyxl>=3.1.0",     # XLSX解析 (NISA, 統計)
"xlrd>=2.0.0",         # XLS解析 (JPX data_j.xls)

# [tool.hatch.build.targets.wheel] packages に追加
"src/fund_db"
```

## 既存コード参照先

| 参照パターン | ファイル |
|-------------|---------|
| パッケージ構造 | `src/report_scraper/` |
| 型定義 (Pydantic + dataclass) | `src/report_scraper/types.py` |
| Click CLI | `src/report_scraper/cli/main.py` |
| JSON永続化 | `src/report_scraper/storage/json_store.py` |
| structlog logging | `src/report_scraper/_logging.py` |
| パス解決 | `src/data_paths/paths.py` (`get_path()`) |
| YFinanceFetcher | `market.yfinance.YFinanceFetcher` (quants pkg, installed) |
| テンプレート | `template/src/template_package/` |

## DL URL (調査済み)

```python
# NISA (投資信託協会 → imaj.or.jp にリダイレクト)
NISA_UNLISTED_URL = "https://www.imaj.or.jp/find/nisa_growth_productslist/xlsx-cms/unlisted_fund_for_investor.xlsx"
NISA_LISTED_URL = "https://www.imaj.or.jp/find/nisa_growth_productslist/xlsx-cms/listed_fund_for_investor.xlsx"

# JPX
JPX_LISTED_URL = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"

# 統計 (URLは統計ページからリンクを辿って取得が必要 - 固定URLパターンは要確認)
TOUSHIN_STATS_PAGE = "https://www.toushin.or.jp/statistics/statistics/index.html"
```

## 実装順序

### Phase 1: 基盤 (fund_db core)
1. `__init__.py`, `_logging.py`, `py.typed`, `exceptions.py`
2. `types.py` (DownloadResult, ParseResult)
3. `config/constants.py` (URL, シート名, カラムマッピング)
4. `storage/json_store.py` (FundDbStore)
5. `pyproject.toml` 更新 (dependencies + packages + scripts)

### Phase 2: NISA (マスタDB基盤)
1. `nisa/models.py` → `nisa/downloader.py` → `nisa/parser.py`
2. テスト: `.tmp/` の既存DL済みExcelでパーサーを検証

### Phase 3: JPX (ETFマスタ)
1. `jpx/models.py` → `jpx/downloader.py` → `jpx/parser.py`
2. テスト: `.tmp/jpx_listed_stocks.xls` で検証

### Phase 4: 統計データ
1. `toushin_stats/models.py` → `toushin_stats/downloader.py` → `toushin_stats/parser.py`
2. B-1(資産増減)から着手、B-2, B-3, A-2を段階追加
3. テスト: `.tmp/toushin_*.xlsx` で検証

### Phase 5: ETF価格
1. `etf_prices/models.py` → `etf_prices/fetcher.py`
2. YFinanceFetcher統合テスト

### Phase 6: CLI + 統合
1. `cli/main.py` (Click group + subcommands)
2. 統合テスト: sync-all ワークフロー

## 検証方法

```bash
# Phase 1: パッケージインポート
uv run python -c "from fund_db import FundDbError; print('OK')"

# Phase 2-4: パーサー単体テスト
uv run pytest tests/unit/fund_db/ -v

# Phase 5: ETF価格取得
uv run python -m fund_db.cli.main etf fetch --tickers 1306 --start 2025-01-01

# Phase 6: 一括同期
uv run fund-db sync-all
uv run fund-db status

# 品質チェック
make check-all
```
