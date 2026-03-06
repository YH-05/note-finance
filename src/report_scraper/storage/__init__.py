"""Storage layer for the report_scraper package.

Modules
-------
json_store
    JSON-based persistence for scraped reports.
pdf_store
    PDF file storage organized by source key.

Examples
--------
>>> from report_scraper.storage import JsonReportStore, PdfStore
"""

from report_scraper.storage.json_store import JsonReportStore
from report_scraper.storage.pdf_store import PdfStore

__all__ = ["JsonReportStore", "PdfStore"]
