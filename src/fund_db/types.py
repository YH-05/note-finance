"""Type definitions for the fund_db package.

This module provides core data models for the fund database pipeline,
using frozen dataclasses for immutable result containers.

Classes
-------
DownloadResult
    Result of downloading a file from a remote URL.
ParseResult
    Result of parsing records from a downloaded file.

Examples
--------
>>> from pathlib import Path
>>> from datetime import datetime, timezone
>>> result = DownloadResult(
...     path=Path("data/fund_db/nisa/file.xlsx"),
...     url="https://example.com/file.xlsx",
...     size_bytes=1024,
...     downloaded_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
... )
>>> result.size_bytes
1024
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path


@dataclass(frozen=True)
class DownloadResult:
    """Result of downloading a file from a remote URL.

    Attributes
    ----------
    path : Path
        Local file path where the downloaded file is stored.
    url : str
        The URL from which the file was downloaded.
    size_bytes : int
        File size in bytes.
    downloaded_at : datetime
        Timestamp when the download completed.
    """

    path: Path
    url: str
    size_bytes: int
    downloaded_at: datetime


@dataclass(frozen=True)
class ParseResult[T]:
    """Result of parsing records from a downloaded file.

    Attributes
    ----------
    records : list[T]
        Parsed records.
    source_path : Path
        Path to the source file that was parsed.
    record_count : int
        Number of records parsed.
    parsed_at : datetime
        Timestamp when the parsing completed.
    """

    records: list[T]
    source_path: Path
    record_count: int
    parsed_at: datetime
