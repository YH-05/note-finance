"""Exception hierarchy for the report_scraper package.

Provides a structured exception hierarchy for error handling across
the report scraping pipeline: fetch, extraction, and configuration.

Classes
-------
ReportScraperError
    Base exception for all report_scraper errors.
FetchError
    Raised when HTTP fetching fails.
ExtractionError
    Raised when content extraction fails.
ConfigError
    Raised when configuration is invalid.

Examples
--------
>>> try:
...     raise FetchError("Connection timeout", url="https://example.com")
... except ReportScraperError as e:
...     print(f"Caught: {e}")
Caught: Connection timeout
"""

from __future__ import annotations


class ReportScraperError(Exception):
    """Base exception for all report_scraper errors.

    All report_scraper exceptions inherit from this class,
    allowing callers to catch all errors with a single except clause.
    """


class FetchError(ReportScraperError):
    """Raised when HTTP fetching of a report page fails.

    Attributes
    ----------
    url : str
        The URL that failed to fetch.
    status_code : int | None
        HTTP status code, if available.
    """

    def __init__(
        self,
        message: str,
        *,
        url: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.url = url
        self.status_code = status_code


class ExtractionError(ReportScraperError):
    """Raised when content extraction from a fetched page fails.

    Attributes
    ----------
    url : str
        The URL of the page where extraction failed.
    method : str | None
        The extraction method that failed (e.g., 'trafilatura', 'lxml').
    """

    def __init__(
        self,
        message: str,
        *,
        url: str,
        method: str | None = None,
    ) -> None:
        super().__init__(message)
        self.url = url
        self.method = method


class ConfigError(ReportScraperError):
    """Raised when configuration is invalid or missing.

    Attributes
    ----------
    field : str | None
        The configuration field that caused the error.
    """

    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.field = field
