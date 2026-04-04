"""Storage layer for the fund_db package.

Modules
-------
json_store
    JSON-based persistence for fund database records.

Examples
--------
>>> from fund_db.storage import FundDbStore
"""

from fund_db.storage.json_store import FundDbStore

__all__ = ["FundDbStore"]
