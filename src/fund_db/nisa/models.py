"""Pydantic models for NISA growth investment target funds.

Provides data models for both non-listed (unlisted) investment trusts
and listed ETF/REIT products eligible for NISA growth investment quota.

Classes
-------
NisaUnlistedFund
    Non-listed investment trust eligible for NISA.
NisaListedEtf
    Listed ETF/REIT eligible for NISA.

Examples
--------
>>> fund = NisaUnlistedFund(
...     association_code="01311046",
...     fund_name="eMAXIS Slim 全世界株式",
...     management_company="三菱UFJアセットマネジメント",
... )
>>> fund.association_code
'01311046'
"""

from __future__ import annotations

from pydantic import BaseModel


class NisaUnlistedFund(BaseModel):
    """Non-listed investment trust eligible for NISA.

    Attributes
    ----------
    association_code : str
        Association code identifying the fund.
    fund_name : str
        Official fund name.
    management_company : str
        Name of the asset management company.
    asset_class : str | None
        Investment target asset class (e.g., stocks, bonds).
    investment_region : str | None
        Investment target region (e.g., domestic, international).
    fund_type : str | None
        Fund type classification (e.g., index, active).
    benchmark_index : str | None
        Benchmark index name, if applicable.
    expense_ratio : str | None
        Trust fee ratio including tax (as string from Excel).
    tsumitate_eligible : str | None
        Tsumitate (accumulation) investment quota eligibility mark.
    growth_eligible : str | None
        Growth investment quota eligibility mark.
    """

    association_code: str
    fund_name: str
    management_company: str
    asset_class: str | None = None
    investment_region: str | None = None
    fund_type: str | None = None
    benchmark_index: str | None = None
    expense_ratio: str | None = None
    tsumitate_eligible: str | None = None
    growth_eligible: str | None = None


class NisaListedEtf(BaseModel):
    """Listed ETF/REIT eligible for NISA.

    Attributes
    ----------
    ticker_code : str
        Stock ticker code.
    fund_name : str
        Official ETF/REIT name.
    management_company : str | None
        Name of the management company.
    benchmark_index : str | None
        Benchmark index name, if applicable.
    expense_ratio : str | None
        Trust fee ratio including tax (as string from Excel).
    trading_unit : str | None
        Minimum trading unit (e.g., "1口", "10口").
    """

    ticker_code: str
    fund_name: str
    management_company: str | None = None
    benchmark_index: str | None = None
    expense_ratio: str | None = None
    trading_unit: str | None = None
