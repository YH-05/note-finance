"""Investment Trust Association statistics subpackage.

Provides models, downloader, and parser for IMAJ statistical reports:
B-1 (asset flow), B-2 (product class), B-3 (management company),
and A-2 (overall status).

Classes
-------
AssetFlowRecord
    B-1: Monthly asset flow time series model.
ToushinStatsDownloader
    Downloads statistics Excel files from IMAJ.
ToushinStatsParser
    Parses statistics Excel files into model instances.

Examples
--------
>>> from fund_db.toushin_stats import AssetFlowRecord, ToushinStatsParser
"""

from fund_db.toushin_stats.downloader import ToushinStatsDownloader
from fund_db.toushin_stats.models import (
    AssetFlowRecord,
    ManagementCompanyRecord,
    OverallStatusRecord,
    ProductClassRecord,
)
from fund_db.toushin_stats.parser import ToushinStatsParser

__all__ = [
    "AssetFlowRecord",
    "ManagementCompanyRecord",
    "OverallStatusRecord",
    "ProductClassRecord",
    "ToushinStatsDownloader",
    "ToushinStatsParser",
]
