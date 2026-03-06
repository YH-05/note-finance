"""Service layer for the report_scraper package.

Modules
-------
content_extractor
    Content extraction using trafilatura with lxml fallback.

Examples
--------
>>> from report_scraper.services import ContentExtractor
"""

from report_scraper.services.content_extractor import ContentExtractor

__all__ = ["ContentExtractor"]
