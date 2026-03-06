"""Investment report scraper package for note-finance.

This package provides tools to collect investment reports from
buy-side, sell-side, and aggregator sources. It supports RSS feeds,
static HTML, and Playwright-rendered (SPA) pages.

Modules
-------
types
    Data models: ``SourceConfig``, ``GlobalConfig``, ``ReportMetadata``, etc.
exceptions
    Exception hierarchy: ``ReportScraperError``, ``FetchError``, etc.
_logging
    Structured logging via structlog.

Examples
--------
>>> from report_scraper import ReportMetadata, SourceConfig
>>> from report_scraper.exceptions import ReportScraperError
"""

from report_scraper.exceptions import (
    ConfigError,
    ExtractionError,
    FetchError,
    ReportScraperError,
)
from report_scraper.types import (
    CollectResult,
    ExtractedContent,
    GlobalConfig,
    PdfMetadata,
    ReportMetadata,
    ReportScraperConfig,
    RunSummary,
    ScrapedReport,
    SourceConfig,
)

__all__ = [
    "CollectResult",
    "ConfigError",
    "ExtractedContent",
    "ExtractionError",
    "FetchError",
    "GlobalConfig",
    "PdfMetadata",
    "ReportMetadata",
    "ReportScraperConfig",
    "ReportScraperError",
    "RunSummary",
    "ScrapedReport",
    "SourceConfig",
]
