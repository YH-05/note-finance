"""Concrete scraper implementations for various report sources.

Modules
-------
_rss_scraper
    RSS-based intermediate base class.
advisor_perspectives
    Advisor Perspectives scraper.

Examples
--------
>>> from report_scraper.scrapers.advisor_perspectives import AdvisorPerspectivesScraper
>>> scraper = AdvisorPerspectivesScraper()
>>> scraper.source_key
'advisor_perspectives'
"""

from report_scraper.scrapers._rss_scraper import RssReportScraper
from report_scraper.scrapers.advisor_perspectives import AdvisorPerspectivesScraper

__all__ = [
    "AdvisorPerspectivesScraper",
    "RssReportScraper",
]
