"""Type definitions for the report_scraper package.

This module provides core data models for the investment report scraper,
combining frozen dataclasses for immutable data and Pydantic BaseModel
for validated configuration.

Classes
-------
SourceConfig
    Pydantic configuration for a single report source.
GlobalConfig
    Pydantic global configuration for the scraper.
ReportMetadata
    Frozen dataclass for report metadata.
ScrapedReport
    Frozen dataclass for a scraped report with content.
ExtractedContent
    Frozen dataclass for extracted text content.
PdfMetadata
    Frozen dataclass for PDF file metadata.
CollectResult
    Frozen dataclass for per-source collection results.
RunSummary
    Frozen dataclass for overall run summary.

Examples
--------
>>> config = GlobalConfig()
>>> config.max_reports_per_source
20
>>> from datetime import datetime, timezone
>>> meta = ReportMetadata(
...     url="https://example.com/report",
...     title="Q4 Earnings Report",
...     published=datetime(2026, 3, 1, tzinfo=timezone.utc),
...     source_key="example",
... )
>>> meta.url
'https://example.com/report'
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path  # noqa: TC003 — required at runtime by Pydantic
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from data_paths import get_path

if TYPE_CHECKING:
    from datetime import datetime

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

type RenderingType = Literal["rss", "static", "playwright"]
type SourceTier = Literal["buy_side", "sell_side", "aggregator"]

# ---------------------------------------------------------------------------
# Pydantic configuration models
# ---------------------------------------------------------------------------


class SourceConfig(BaseModel):
    """Configuration for a single report source.

    Attributes
    ----------
    key : str
        Unique identifier for the source (e.g., "advisor_perspectives").
    name : str
        Human-readable display name.
    tier : SourceTier
        Classification: buy_side, sell_side, or aggregator.
    listing_url : str
        URL of the page listing reports.
    rendering : RenderingType
        How to fetch the page: rss, static HTML, or playwright.
    tags : list[str]
        Categorization tags (e.g., ["macro", "equity"]).
    pdf_selector : str | None
        CSS selector to find PDF links on the page, if applicable.
    article_selector : str | None
        CSS selector for article/report list items.
    max_reports : int | None
        Source-specific override for max reports to collect.

    Examples
    --------
    >>> config = SourceConfig(
    ...     key="example",
    ...     name="Example Research",
    ...     tier="sell_side",
    ...     listing_url="https://example.com/research",
    ...     rendering="static",
    ... )
    >>> config.key
    'example'
    """

    key: str = Field(..., min_length=1, description="Unique source identifier")
    name: str = Field(..., min_length=1, description="Human-readable source name")
    tier: SourceTier = Field(..., description="Source classification tier")
    listing_url: str = Field(
        ..., min_length=1, description="URL of report listing page"
    )
    rendering: RenderingType = Field(..., description="Page rendering method")
    tags: list[str] = Field(default_factory=list, description="Categorization tags")
    pdf_selector: str | None = Field(
        default=None, description="CSS selector for PDF links"
    )
    article_selector: str | None = Field(
        default=None, description="CSS selector for article list items"
    )
    max_reports: int | None = Field(
        default=None, ge=1, description="Source-specific max reports override"
    )


class TimeoutConfig(BaseModel):
    """Timeout configuration for HTTP requests.

    Attributes
    ----------
    connect : int
        Connection timeout in seconds.
    read : int
        Read timeout in seconds.

    Examples
    --------
    >>> t = TimeoutConfig()
    >>> t.connect
    10
    """

    connect: int = Field(default=10, ge=1, le=120, description="Connection timeout (s)")
    read: int = Field(default=30, ge=1, le=300, description="Read timeout (s)")


class GlobalConfig(BaseModel):
    """Global configuration for the report scraper.

    Attributes
    ----------
    output_dir : Path
        Directory for JSON output files.
    pdf_dir : Path
        Directory for downloaded PDF files.
    max_reports_per_source : int
        Default maximum reports to collect per source.
    timeouts : TimeoutConfig
        HTTP timeout configuration.
    dedup_days : int
        Number of days to look back for deduplication.

    Examples
    --------
    >>> config = GlobalConfig()
    >>> config.max_reports_per_source
    20
    >>> config.dedup_days
    30
    """

    output_dir: Path = Field(
        default_factory=lambda: get_path("scraped/reports"),
        description="Directory for JSON output",
    )
    pdf_dir: Path = Field(
        default_factory=lambda: get_path("scraped/pdfs"),
        description="Directory for downloaded PDFs",
    )
    max_reports_per_source: int = Field(
        default=20,
        ge=1,
        le=200,
        description="Default max reports per source",
    )
    timeouts: TimeoutConfig = Field(
        default_factory=TimeoutConfig,
        description="HTTP timeout configuration",
    )
    dedup_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Days to look back for deduplication",
    )


class ReportScraperConfig(BaseModel):
    """Top-level configuration combining global settings and source definitions.

    Attributes
    ----------
    global_config : GlobalConfig
        Global scraper settings (output dirs, timeouts, etc.).
    sources : list[SourceConfig]
        List of report source configurations.

    Examples
    --------
    >>> cfg = ReportScraperConfig(
    ...     global_config=GlobalConfig(),
    ...     sources=[
    ...         SourceConfig(
    ...             key="example",
    ...             name="Example",
    ...             tier="sell_side",
    ...             listing_url="https://example.com",
    ...             rendering="static",
    ...         )
    ...     ],
    ... )
    >>> len(cfg.sources)
    1
    """

    global_config: GlobalConfig = Field(
        default_factory=GlobalConfig,
        alias="global",
        description="Global scraper settings",
    )
    sources: list[SourceConfig] = Field(
        ..., min_length=1, description="List of report source configurations"
    )


# ---------------------------------------------------------------------------
# Frozen dataclass models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReportMetadata:
    """Metadata for a single report.

    Attributes
    ----------
    url : str
        URL of the report page.
    title : str
        Report title.
    published : datetime
        Publication date and time.
    source_key : str
        Key identifying the source (matches SourceConfig.key).
    pdf_url : str | None
        URL of the associated PDF, if available.
    author : str | None
        Report author, if available.
    tags : tuple[str, ...]
        Tags associated with the report.
    """

    url: str
    title: str
    published: datetime
    source_key: str
    pdf_url: str | None = None
    author: str | None = None
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExtractedContent:
    """Extracted text content from a report page.

    Attributes
    ----------
    text : str
        Extracted plain text content.
    method : str
        Extraction method used (e.g., 'trafilatura', 'lxml', 'rss').
    length : int
        Character count of extracted text.
    """

    text: str
    method: str
    length: int


@dataclass(frozen=True)
class PdfMetadata:
    """Metadata for a downloaded PDF file.

    Attributes
    ----------
    url : str
        Remote URL of the PDF.
    local_path : Path
        Local file path where the PDF is stored.
    size_bytes : int
        File size in bytes.
    """

    url: str
    local_path: Path
    size_bytes: int


@dataclass(frozen=True)
class ScrapedReport:
    """A single scraped report with metadata and content.

    Attributes
    ----------
    metadata : ReportMetadata
        Report metadata (URL, title, dates, etc.).
    content : ExtractedContent | None
        Extracted text content, if available.
    pdf : PdfMetadata | None
        PDF metadata, if a PDF was downloaded.
    """

    metadata: ReportMetadata
    content: ExtractedContent | None = None
    pdf: PdfMetadata | None = None


@dataclass(frozen=True)
class CollectResult:
    """Result of collecting reports from a single source.

    Attributes
    ----------
    source_key : str
        Source identifier.
    reports : tuple[ScrapedReport, ...]
        Successfully scraped reports.
    errors : tuple[str, ...]
        Error messages for failed attempts.
    duration : float
        Collection duration in seconds.
    """

    source_key: str
    reports: tuple[ScrapedReport, ...] = ()
    errors: tuple[str, ...] = ()
    duration: float = 0.0


@dataclass(frozen=True)
class RunSummary:
    """Summary of a complete scraping run across all sources.

    Attributes
    ----------
    timestamp : datetime
        When the run started.
    results : tuple[CollectResult, ...]
        Per-source collection results.
    total_reports : int
        Total number of reports collected.
    total_errors : int
        Total number of errors encountered.
    """

    timestamp: datetime
    results: tuple[CollectResult, ...] = ()
    total_reports: int = 0
    total_errors: int = 0
