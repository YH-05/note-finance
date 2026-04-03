"""Pydantic models for Investment Trust Association statistics.

Provides data models for four statistical report types:
B-1 (Asset Flow), B-2 (Product Class), B-3 (Management Company),
and A-2 (Overall Status).

Classes
-------
AssetFlowRecord
    B-1: Monthly asset flow time series.
ProductClassRecord
    B-2: Product classification breakdown.
ManagementCompanyRecord
    B-3: Management company breakdown.
OverallStatusRecord
    A-2: Overall market status.

Examples
--------
>>> record = AssetFlowRecord(
...     year_month="2024-01",
...     net_assets=1500000.0,
...     inflow=50000.0,
...     outflow=30000.0,
...     net_flow=20000.0,
... )
>>> record.year_month
'2024-01'
"""

from __future__ import annotations

from pydantic import BaseModel


class AssetFlowRecord(BaseModel):
    """B-1: Monthly asset flow time series.

    Tracks monthly changes in net assets, inflows, and outflows
    for the investment trust industry.

    Attributes
    ----------
    year_month : str
        Year-month in "YYYY-MM" format.
    net_assets : float | None
        Total net assets in millions of yen.
    inflow : float | None
        Subscription amount (settings) in millions of yen.
    outflow : float | None
        Redemption amount (cancellations) in millions of yen.
    net_flow : float | None
        Net increase/decrease (inflow - outflow) in millions of yen.
    """

    year_month: str
    net_assets: float | None = None
    inflow: float | None = None
    outflow: float | None = None
    net_flow: float | None = None


class ProductClassRecord(BaseModel):
    """B-2: Product classification breakdown.

    Breakdown of net assets and fund counts by product class.

    Attributes
    ----------
    product_class : str
        Product classification name (from sheet name).
    year_month : str
        Year-month in "YYYY-MM" format.
    net_assets : float | None
        Total net assets in millions of yen.
    fund_count : int | None
        Number of funds in this product class.
    """

    product_class: str
    year_month: str
    net_assets: float | None = None
    fund_count: int | None = None


class ManagementCompanyRecord(BaseModel):
    """B-3: Management company breakdown.

    Breakdown of net assets and fund counts by management company.

    Attributes
    ----------
    company_name : str
        Management company name.
    year_month : str
        Year-month in "YYYY-MM" format.
    net_assets : float | None
        Total net assets in millions of yen.
    fund_count : int | None
        Number of funds managed by this company.
    """

    company_name: str
    year_month: str
    net_assets: float | None = None
    fund_count: int | None = None


class OverallStatusRecord(BaseModel):
    """A-2: Overall market status.

    Aggregate statistics for the entire investment trust market.

    Attributes
    ----------
    year_month : str
        Year-month in "YYYY-MM" format.
    total_net_assets : float | None
        Total net assets across all funds in millions of yen.
    total_fund_count : int | None
        Total number of funds.
    total_inflow : float | None
        Total subscription amount in millions of yen.
    total_outflow : float | None
        Total redemption amount in millions of yen.
    """

    year_month: str
    total_net_assets: float | None = None
    total_fund_count: int | None = None
    total_inflow: float | None = None
    total_outflow: float | None = None
