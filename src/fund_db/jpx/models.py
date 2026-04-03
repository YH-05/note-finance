"""Pydantic models for JPX listed securities.

Provides the data model for securities listed on the Tokyo Stock Exchange
(JPX), parsed from the ``data_j.xls`` file.

Classes
-------
JpxListedStock
    Listed security on the Tokyo Stock Exchange.

Examples
--------
>>> stock = JpxListedStock(
...     ticker_code="7203",
...     name="トヨタ自動車",
...     market_segment="プライム（内国株式）",
... )
>>> stock.is_etf
False
"""

from __future__ import annotations

from pydantic import BaseModel


class JpxListedStock(BaseModel):
    """Listed security on the Tokyo Stock Exchange.

    Attributes
    ----------
    ticker_code : str
        Stock ticker code (e.g., "7203").
    name : str
        Security name.
    market_segment : str | None
        Market/product segment (e.g., "プライム（内国株式）", "ETF・ETN").
    sector_code_33 : str | None
        33-sector classification code.
    sector_name_33 : str | None
        33-sector classification name.
    sector_code_17 : str | None
        17-sector classification code.
    sector_name_17 : str | None
        17-sector classification name.
    size_code : str | None
        Size classification code.
    size_category : str | None
        Size classification name (e.g., "TOPIX Large70").

    Examples
    --------
    >>> stock = JpxListedStock(
    ...     ticker_code="1306",
    ...     name="NEXT FUNDS TOPIX連動型上場投信",
    ...     market_segment="ETF・ETN",
    ... )
    >>> stock.is_etf
    True
    """

    ticker_code: str
    name: str
    market_segment: str | None = None
    sector_code_33: str | None = None
    sector_name_33: str | None = None
    sector_code_17: str | None = None
    sector_name_17: str | None = None
    size_code: str | None = None
    size_category: str | None = None

    @property
    def is_etf(self) -> bool:
        """Check if this security is an ETF/ETN.

        Returns
        -------
        bool
            True if ``market_segment`` contains 'ETF'.
        """
        return self.market_segment is not None and "ETF" in self.market_segment

    @property
    def is_reit(self) -> bool:
        """Check if this security is a REIT/Infrastructure Fund.

        Returns
        -------
        bool
            True if ``market_segment`` contains 'REIT'.
        """
        return self.market_segment is not None and "REIT" in self.market_segment
