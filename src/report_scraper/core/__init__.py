"""Core components for the report_scraper package.

Modules
-------
base_scraper
    Abstract base class for all report scrapers.
scraper_engine
    Composition-based pipeline engine for concurrent report scraping.
scraper_registry
    Registry mapping source keys to scraper instances.

Examples
--------
>>> from report_scraper.core import BaseReportScraper, ScraperEngine, ScraperRegistry
"""

from report_scraper.core.base_scraper import BaseReportScraper
from report_scraper.core.scraper_engine import ScraperEngine
from report_scraper.core.scraper_registry import ScraperRegistry

__all__ = ["BaseReportScraper", "ScraperEngine", "ScraperRegistry"]
