"""Service layer for the report_scraper package.

Modules
-------
content_extractor
    Content extraction using trafilatura with lxml fallback.
pdf_downloader
    PDF download service using httpx.
summary_exporter
    Markdown summary generation from RunSummary data.

Examples
--------
>>> from report_scraper.services import ContentExtractor, PdfDownloader, SummaryExporter
"""

from report_scraper.services.content_extractor import ContentExtractor
from report_scraper.services.pdf_downloader import PdfDownloader
from report_scraper.services.summary_exporter import SummaryExporter

__all__ = ["ContentExtractor", "PdfDownloader", "SummaryExporter"]
