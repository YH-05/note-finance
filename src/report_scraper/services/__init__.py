"""Service layer for the report_scraper package.

Modules
-------
content_extractor
    Content extraction using trafilatura with lxml fallback.
pdf_downloader
    PDF download service using httpx.

Examples
--------
>>> from report_scraper.services import ContentExtractor, PdfDownloader
"""

from report_scraper.services.content_extractor import ContentExtractor
from report_scraper.services.pdf_downloader import PdfDownloader

__all__ = ["ContentExtractor", "PdfDownloader"]
