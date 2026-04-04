"""Data models for ETF price records and performance summaries.

Provides Pydantic models for storing daily ETF price data
and computing performance metrics over configurable periods.

Classes
-------
EtfPriceRecord
    Single day's OHLCV data for an ETF ticker.
EtfPerformanceSummary
    Performance metrics (return, volatility, drawdown) over a period.

Examples
--------
>>> from datetime import date
>>> record = EtfPriceRecord(
...     ticker="1306.T",
...     date=date(2026, 4, 1),
...     close=2500.0,
... )
>>> record.ticker
'1306.T'
"""

from __future__ import annotations

import math
from datetime import date  # noqa: TC003 — Pydantic needs runtime access

from pydantic import BaseModel, field_validator


class EtfPriceRecord(BaseModel):
    """Single day's OHLCV data for an ETF ticker.

    Attributes
    ----------
    ticker : str
        Ticker symbol in 'XXXX.T' format.
    date : date
        Trading date.
    open : float | None
        Opening price. None if unavailable.
    high : float | None
        High price. None if unavailable.
    low : float | None
        Low price. None if unavailable.
    close : float
        Closing price (adjusted). Must not be NaN or None.
    volume : int | None
        Trading volume. None if unavailable or NaN.
    """

    ticker: str
    date: date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float
    volume: int | None = None

    @field_validator("close")
    @classmethod
    def close_must_not_be_nan(cls, v: float) -> float:
        """Reject NaN values for close price.

        Parameters
        ----------
        v : float
            The close value to validate.

        Returns
        -------
        float
            The validated close value.

        Raises
        ------
        ValueError
            If v is NaN.
        """
        if math.isnan(v):
            msg = "close must not be NaN"
            raise ValueError(msg)
        return v


class EtfPerformanceSummary(BaseModel):
    """Performance metrics for an ETF over a specified period.

    Attributes
    ----------
    ticker : str
        Ticker symbol in 'XXXX.T' format.
    period_start : date
        Start date of the measurement period.
    period_end : date
        End date of the measurement period.
    total_return : float
        Cumulative return over the period (e.g. 0.15 = 15%).
    annualized_volatility : float
        Annualized standard deviation of daily returns.
    max_drawdown : float
        Maximum peak-to-trough decline (negative value, e.g. -0.10 = -10%).
    """

    ticker: str
    period_start: date
    period_end: date
    total_return: float
    annualized_volatility: float
    max_drawdown: float
