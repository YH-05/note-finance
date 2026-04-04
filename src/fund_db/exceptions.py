"""Exception hierarchy for the fund_db package.

Provides a structured exception hierarchy for error handling across
the fund database pipeline: download, parse, storage, and configuration.

Classes
-------
FundDbError
    Base exception for all fund_db errors.
DownloadError
    Raised when downloading Excel/data files fails.
ParseError
    Raised when parsing Excel/data content fails.
StorageError
    Raised when storage operations fail.
ConfigError
    Raised when configuration is invalid.

Examples
--------
>>> try:
...     raise DownloadError("Connection timeout", url="https://example.com")
... except FundDbError as e:
...     print(f"Caught: {e}")
Caught: Connection timeout
"""

from __future__ import annotations


class FundDbError(Exception):
    """Base exception for all fund_db errors.

    All fund_db exceptions inherit from this class,
    allowing callers to catch all errors with a single except clause.
    """


class DownloadError(FundDbError):
    """Raised when downloading Excel/data files fails.

    Attributes
    ----------
    url : str
        The URL that failed to download.
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
        """Initialize DownloadError.

        Parameters
        ----------
        message : str
            Human-readable error description.
        url : str
            The URL that failed to download.
        status_code : int | None
            HTTP status code, if available.
        """
        super().__init__(message)
        self.url = url
        self.status_code = status_code


class ParseError(FundDbError):
    """Raised when parsing Excel/data content fails.

    Attributes
    ----------
    source : str
        The source file or data that failed to parse.
    reason : str | None
        Specific reason for the parse failure.
    """

    def __init__(
        self,
        message: str,
        *,
        source: str,
        reason: str | None = None,
    ) -> None:
        """Initialize ParseError.

        Parameters
        ----------
        message : str
            Human-readable error description.
        source : str
            The source file or data that failed to parse.
        reason : str | None
            Specific reason for the parse failure.
        """
        super().__init__(message)
        self.source = source
        self.reason = reason


class StorageError(FundDbError):
    """Raised when storage operations fail.

    Attributes
    ----------
    path : str | None
        The file path involved in the failed operation.
    """

    def __init__(
        self,
        message: str,
        *,
        path: str | None = None,
    ) -> None:
        """Initialize StorageError.

        Parameters
        ----------
        message : str
            Human-readable error description.
        path : str | None
            The file path involved in the failed operation.
        """
        super().__init__(message)
        self.path = path


class ConfigError(FundDbError):
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
        """Initialize ConfigError.

        Parameters
        ----------
        message : str
            Human-readable error description.
        field : str | None
            The configuration field that caused the error.
        """
        super().__init__(message)
        self.field = field
