"""Constants for the fund_db package.

Provides download URLs, sheet name constants, and column mapping
dictionaries used across the fund database pipeline.

Constants
---------
NISA_UNLISTED_URL
    URL for IMAJ non-listed investment trust Excel file.
NISA_LISTED_URL
    URL for IMAJ listed ETF/REIT Excel file.
JPX_LISTED_URL
    URL for JPX listed securities data file.
TOUSHIN_STATS_PAGE
    URL for Investment Trust Association statistics page.
"""

from __future__ import annotations

from typing import Literal

# ---------------------------------------------------------------------------
# Download URLs
# ---------------------------------------------------------------------------

NISA_UNLISTED_URL: str = (
    "https://www.toushin.or.jp/statistics/tsumitate/files/tsumitate_target.xlsx"
)
"""IMAJ non-listed investment trust Excel download URL."""

NISA_LISTED_URL: str = (
    "https://www.toushin.or.jp/statistics/tsumitate/files/tsumitate_target_etf.xlsx"
)
"""IMAJ listed ETF/REIT Excel download URL."""

JPX_LISTED_URL: str = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
"""JPX listed securities data file download URL."""

TOUSHIN_STATS_PAGE: str = "https://www.toushin.or.jp/statistics/"
"""Investment Trust Association statistics page URL (scraping entry point)."""

# ---------------------------------------------------------------------------
# Sheet name constants
# ---------------------------------------------------------------------------

NISA_UNLISTED_SHEET: str = "つみたて投資枠対象商品"
"""Sheet name for NISA unlisted fund data."""

NISA_LISTED_SHEET: str = "つみたて投資枠対象ETF"
"""Sheet name for NISA listed ETF data."""

NISA_GROWTH_SHEET: str = "成長投資枠対象商品"
"""Sheet name for NISA growth investment target data."""

# ---------------------------------------------------------------------------
# Column mapping dictionaries (Excel column name -> field name)
# ---------------------------------------------------------------------------

NISA_UNLISTED_COLUMNS: dict[str, str] = {
    "協会コード": "association_code",
    "ファンド名称": "fund_name",
    "運用会社名": "management_company",
    "投資対象資産": "asset_class",
    "投資対象地域": "investment_region",
    "インデックス型/アクティブ型": "fund_type",
    "対象インデックス": "benchmark_index",
    "信託報酬（税込）": "expense_ratio",
    "つみたて投資枠": "tsumitate_eligible",
    "成長投資枠": "growth_eligible",
}
"""Column mapping for NISA unlisted fund Excel files."""

NISA_LISTED_COLUMNS: dict[str, str] = {
    "銘柄コード": "ticker_code",
    "銘柄名称": "fund_name",
    "管理会社": "management_company",
    "対象インデックス": "benchmark_index",
    "信託報酬（税込）": "expense_ratio",
    "売買単位": "trading_unit",
}
"""Column mapping for NISA listed ETF Excel files."""

JPX_LISTED_COLUMNS: dict[str, str] = {
    "コード": "ticker_code",
    "銘柄名": "name",
    "市場・商品区分": "market_segment",
    "33業種コード": "sector_code_33",
    "33業種区分": "sector_name_33",
    "17業種コード": "sector_code_17",
    "17業種区分": "sector_name_17",
    "規模コード": "size_code",
    "規模区分": "size_category",
}
"""Column mapping for JPX listed securities data files."""

JPX_EXCEL_ENGINE: Literal["xlrd", "openpyxl", "odf", "pyxlsb", "calamine"] = "xlrd"
"""Excel engine for reading JPX data files (.xls format).

Change to ``'openpyxl'`` if JPX migrates to .xlsx format.
"""
