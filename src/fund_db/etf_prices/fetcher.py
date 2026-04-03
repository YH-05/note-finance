"""ETF price fetcher using yfinance.

Fetches daily OHLCV data for ETF tickers from Yahoo Finance
and converts the results into typed Pydantic models.

Classes
-------
EtfPriceFetcher
    Fetches ETF prices and computes performance metrics.

Examples
--------
>>> fetcher = EtfPriceFetcher()  # doctest: +SKIP
>>> records = fetcher.fetch(["1306"], start="2026-01-01")  # doctest: +SKIP
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any, cast

import numpy as np
import pandas as pd
import yfinance as yf

from fund_db._logging import get_logger
from fund_db.etf_prices.models import EtfPerformanceSummary, EtfPriceRecord

logger = get_logger(__name__)

# Trading days per year (Tokyo Stock Exchange)
_TRADING_DAYS_PER_YEAR = 252


def _ensure_t_suffix(ticker: str) -> str:
    """Ensure ticker has '.T' suffix for Tokyo Stock Exchange.

    Parameters
    ----------
    ticker : str
        Ticker code, with or without '.T' suffix.

    Returns
    -------
    str
        Ticker with '.T' suffix.

    Examples
    --------
    >>> _ensure_t_suffix("1306")
    '1306.T'
    >>> _ensure_t_suffix("1306.T")
    '1306.T'
    """
    if not ticker.endswith(".T"):
        return f"{ticker}.T"
    return ticker


def _wrap_value(v: Any) -> float | None:
    """Convert NaN/None to None, otherwise return float.

    Parameters
    ----------
    v : Any
        Value to convert.

    Returns
    -------
    float | None
        None if input is None or NaN, otherwise float.

    Examples
    --------
    >>> _wrap_value(100.5)
    100.5
    >>> _wrap_value(float('nan')) is None
    True
    >>> _wrap_value(None) is None
    True
    """
    if v is None:
        return None
    if isinstance(v, float) and (pd.isna(v) or math.isnan(v)):
        return None
    return float(v)


def _wrap_volume(v: Any) -> int | None:
    """Convert volume value to int or None.

    Parameters
    ----------
    v : Any
        Volume value to convert.

    Returns
    -------
    int | None
        None if input is None or NaN, otherwise int.

    Examples
    --------
    >>> _wrap_volume(1000000.0)
    1000000
    >>> _wrap_volume(float('nan')) is None
    True
    """
    wrapped = _wrap_value(v)
    if wrapped is None:
        return None
    return int(wrapped)


class EtfPriceFetcher:
    """Fetches ETF prices from Yahoo Finance via yfinance.

    Methods
    -------
    fetch(tickers, start, end=None)
        Fetch daily OHLCV data for the given tickers.
    get_performance(tickers, years=3)
        Compute performance metrics over the specified period.
    """

    def fetch(
        self,
        tickers: list[str],
        start: str,
        end: str | None = None,
    ) -> list[EtfPriceRecord]:
        """Fetch daily OHLCV data for ETF tickers.

        Parameters
        ----------
        tickers : list[str]
            List of ticker codes (e.g. ["1306", "1321"]).
        start : str
            Start date in 'YYYY-MM-DD' format.
        end : str | None
            End date in 'YYYY-MM-DD' format. Defaults to today.

        Returns
        -------
        list[EtfPriceRecord]
            List of daily price records.
        """
        symbols = [_ensure_t_suffix(t) for t in tickers]
        logger.info(
            "Fetching ETF prices",
            symbols=symbols,
            start=start,
            end=end,
        )

        result = yf.download(
            symbols,
            start=start,
            end=end,
            auto_adjust=True,
        )
        df = cast("pd.DataFrame", result)

        if df.empty:
            logger.warning("No data returned from yfinance", symbols=symbols)
            return []

        records: list[EtfPriceRecord] = []

        if len(symbols) == 1:
            # Single ticker: columns are ['Open', 'High', 'Low', 'Close', 'Volume']
            ticker_sym = symbols[0]
            records = self._convert_single_ticker_df(df, ticker_sym)
        else:
            # Multiple tickers: MultiIndex columns (metric, ticker)
            for ticker_sym in symbols:
                try:
                    ticker_df = cast("pd.DataFrame", df.xs(ticker_sym, level=1, axis=1))
                except KeyError:
                    logger.warning(
                        "Ticker not found in downloaded data",
                        ticker=ticker_sym,
                    )
                    continue
                records.extend(self._convert_single_ticker_df(ticker_df, ticker_sym))

        logger.info(
            "Fetched ETF prices",
            record_count=len(records),
            symbols=symbols,
        )
        return records

    def _convert_single_ticker_df(
        self,
        df: pd.DataFrame,
        ticker: str,
    ) -> list[EtfPriceRecord]:
        """Convert a single-ticker DataFrame to EtfPriceRecord list.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame with OHLCV columns for one ticker.
        ticker : str
            The ticker symbol.

        Returns
        -------
        list[EtfPriceRecord]
            Converted records. Rows with NaN close are skipped.
        """
        records: list[EtfPriceRecord] = []
        for idx, row in df.iterrows():
            close_val = _wrap_value(row.get("Close"))
            if close_val is None:
                logger.debug(
                    "Skipping row with NaN close",
                    ticker=ticker,
                    date=str(idx),
                )
                continue

            record = EtfPriceRecord(
                ticker=ticker,
                date=cast("date", pd.Timestamp(cast("Any", idx)).date()),
                open=_wrap_value(row.get("Open")),
                high=_wrap_value(row.get("High")),
                low=_wrap_value(row.get("Low")),
                close=close_val,
                volume=_wrap_volume(row.get("Volume")),
            )
            records.append(record)
        return records

    def get_performance(
        self,
        tickers: list[str],
        years: int = 3,
    ) -> list[EtfPerformanceSummary]:
        """Compute performance metrics for ETF tickers.

        Parameters
        ----------
        tickers : list[str]
            List of ticker codes.
        years : int
            Number of years to look back. Default is 3.

        Returns
        -------
        list[EtfPerformanceSummary]
            Performance summaries for each ticker.
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=years * 365)

        records = self.fetch(
            tickers,
            start=start_date.isoformat(),
            end=end_date.isoformat(),
        )

        if not records:
            return []

        # Group records by ticker
        ticker_records: dict[str, list[EtfPriceRecord]] = {}
        for r in records:
            ticker_records.setdefault(r.ticker, []).append(r)

        summaries: list[EtfPerformanceSummary] = []
        for ticker, recs in ticker_records.items():
            recs_sorted = sorted(recs, key=lambda x: x.date)
            if len(recs_sorted) < 2:
                logger.warning(
                    "Not enough data for performance calculation",
                    ticker=ticker,
                    records=len(recs_sorted),
                )
                continue

            closes = np.array([r.close for r in recs_sorted], dtype=np.float64)
            daily_returns = np.diff(closes) / closes[:-1]

            total_return = float((closes[-1] - closes[0]) / closes[0])
            annualized_vol = float(
                np.std(daily_returns, ddof=1) * np.sqrt(_TRADING_DAYS_PER_YEAR)
            )

            # Max drawdown
            cumulative = np.cumprod(1 + daily_returns)
            running_max = np.maximum.accumulate(cumulative)
            drawdowns = (cumulative - running_max) / running_max
            max_dd = float(np.min(drawdowns))

            summaries.append(
                EtfPerformanceSummary(
                    ticker=ticker,
                    period_start=recs_sorted[0].date,
                    period_end=recs_sorted[-1].date,
                    total_return=total_return,
                    annualized_volatility=annualized_vol,
                    max_drawdown=max_dd,
                )
            )

        logger.info(
            "Computed performance summaries",
            summary_count=len(summaries),
        )
        return summaries
