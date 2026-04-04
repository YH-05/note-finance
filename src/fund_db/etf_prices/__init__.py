"""ETF price fetching sub-package.

Provides tools to download daily ETF prices from Yahoo Finance,
convert them to typed Pydantic models, and compute performance metrics.

Classes
-------
EtfPriceRecord
    Single day's OHLCV data for an ETF ticker.
EtfPerformanceSummary
    Performance metrics over a period.
EtfPriceFetcher
    Fetcher using yfinance for Yahoo Finance data.

Examples
--------
>>> from fund_db.etf_prices import EtfPriceFetcher, EtfPriceRecord
"""

from fund_db.etf_prices.fetcher import EtfPriceFetcher
from fund_db.etf_prices.models import EtfPerformanceSummary, EtfPriceRecord

__all__ = ["EtfPerformanceSummary", "EtfPriceFetcher", "EtfPriceRecord"]
