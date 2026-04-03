"""NISA growth investment target fund subpackage.

Provides models, downloader, and parser for NISA-eligible funds:
non-listed investment trusts and listed ETF/REITs.

Classes
-------
NisaUnlistedFund
    Non-listed investment trust model.
NisaListedEtf
    Listed ETF/REIT model.
NisaDownloader
    Downloads NISA Excel files from IMAJ.
NisaParser
    Parses NISA Excel files into model instances.

Examples
--------
>>> from fund_db.nisa import NisaUnlistedFund, NisaParser
"""

from fund_db.nisa.downloader import NisaDownloader
from fund_db.nisa.models import NisaListedEtf, NisaUnlistedFund
from fund_db.nisa.parser import NisaParser

__all__ = [
    "NisaDownloader",
    "NisaListedEtf",
    "NisaParser",
    "NisaUnlistedFund",
]
