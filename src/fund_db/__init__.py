"""Fund database package for note-finance.

This package provides tools to download, parse, and store fund data
from NISA, JPX, and investment trust statistics sources.

Modules
-------
types
    Data models: ``DownloadResult``, ``ParseResult``.
exceptions
    Exception hierarchy: ``FundDbError``, ``DownloadError``, etc.
storage
    Storage layer: ``FundDbStore``.
config
    Configuration constants and column mappings.
_logging
    Structured logging via structlog.

Examples
--------
>>> from fund_db import FundDbError, FundDbStore
"""

from fund_db.exceptions import FundDbError
from fund_db.storage import FundDbStore

__version__ = "0.1.0"

__all__ = ["FundDbError", "FundDbStore", "__version__"]
