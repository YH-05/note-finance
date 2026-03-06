"""Storage layer for the report_scraper package.

Modules
-------
json_store
    JSON-based persistence for scraped reports.

Examples
--------
>>> from report_scraper.storage import JsonReportStore
"""

from report_scraper.storage.json_store import JsonReportStore

__all__ = ["JsonReportStore"]
