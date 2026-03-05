"""Shared fixtures for report_scraper tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from report_scraper.types import (
    CollectResult,
    ExtractedContent,
    GlobalConfig,
    PdfMetadata,
    ReportMetadata,
    ScrapedReport,
    SourceConfig,
)


@pytest.fixture
def sample_source_config() -> SourceConfig:
    """Create a sample SourceConfig for testing.

    Returns
    -------
    SourceConfig
        A valid SourceConfig instance.
    """
    return SourceConfig(
        key="test_source",
        name="Test Research",
        tier="sell_side",
        listing_url="https://example.com/research",
        rendering="static",
        tags=["macro", "equity"],
    )


@pytest.fixture
def sample_global_config() -> GlobalConfig:
    """Create a sample GlobalConfig for testing.

    Returns
    -------
    GlobalConfig
        A GlobalConfig with default values.
    """
    return GlobalConfig()


@pytest.fixture
def sample_report_metadata() -> ReportMetadata:
    """Create a sample ReportMetadata for testing.

    Returns
    -------
    ReportMetadata
        A valid ReportMetadata instance.
    """
    return ReportMetadata(
        url="https://example.com/report/q4-2025",
        title="Q4 2025 Market Outlook",
        published=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
        source_key="test_source",
        pdf_url="https://example.com/report/q4-2025.pdf",
        author="Test Author",
        tags=("macro", "outlook"),
    )


@pytest.fixture
def sample_extracted_content() -> ExtractedContent:
    """Create a sample ExtractedContent for testing.

    Returns
    -------
    ExtractedContent
        A valid ExtractedContent instance.
    """
    return ExtractedContent(
        text="This is the extracted report content.",
        method="trafilatura",
        length=37,
    )


@pytest.fixture
def sample_pdf_metadata() -> PdfMetadata:
    """Create a sample PdfMetadata for testing.

    Returns
    -------
    PdfMetadata
        A valid PdfMetadata instance.
    """
    return PdfMetadata(
        url="https://example.com/report/q4-2025.pdf",
        local_path=Path("data/scraped/pdfs/q4-2025.pdf"),
        size_bytes=1024000,
    )


@pytest.fixture
def sample_scraped_report(
    sample_report_metadata: ReportMetadata,
    sample_extracted_content: ExtractedContent,
    sample_pdf_metadata: PdfMetadata,
) -> ScrapedReport:
    """Create a sample ScrapedReport for testing.

    Returns
    -------
    ScrapedReport
        A ScrapedReport with metadata, content, and PDF.
    """
    return ScrapedReport(
        metadata=sample_report_metadata,
        content=sample_extracted_content,
        pdf=sample_pdf_metadata,
    )


@pytest.fixture
def sample_collect_result(sample_scraped_report: ScrapedReport) -> CollectResult:
    """Create a sample CollectResult for testing.

    Returns
    -------
    CollectResult
        A CollectResult with one report and no errors.
    """
    return CollectResult(
        source_key="test_source",
        reports=(sample_scraped_report,),
        errors=(),
        duration=1.5,
    )
