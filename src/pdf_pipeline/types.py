"""Type definitions for the pdf_pipeline package.

This module provides core data models for the PDF to knowledge graph pipeline,
combining frozen dataclasses for immutable data and Pydantic BaseModel
for validated configuration.

Classes
-------
LLMConfig
    Pydantic configuration for the LLM provider.
NoiseFilterConfig
    Pydantic configuration for noise filtering during text extraction.
PipelineConfig
    Top-level Pydantic configuration for the entire pipeline.
ProcessingState
    Frozen dataclass representing the processing state of a single PDF.
PdfMetadata
    Frozen dataclass for PDF document metadata.
BatchManifest
    Frozen dataclass for a batch of PDFs to process together.

Examples
--------
>>> config = PipelineConfig(input_dirs=["data/raw/pdfs"])
>>> config.llm.provider
'anthropic'
>>> config.batch_size
10
>>> from pathlib import Path
>>> state = ProcessingState(pdf_path=Path("report.pdf"), status="pending")
>>> state.status
'pending'
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import (
    Path,  # noqa: TC003 — Pydantic needs Path at runtime for field validation
)
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from data_paths import get_path

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

type ProcessingStatus = Literal["pending", "processing", "completed", "failed"]

# ---------------------------------------------------------------------------
# Pydantic configuration models
# ---------------------------------------------------------------------------


class LLMConfig(BaseModel):
    """Configuration for the LLM provider used in extraction.

    Attributes
    ----------
    provider : str
        LLM provider name (e.g., 'anthropic', 'openai').
    model : str
        Model identifier (e.g., 'claude-opus-4-5', 'gpt-4o').
    max_tokens : int
        Maximum tokens for LLM response.
    temperature : float
        Sampling temperature for the LLM (0.0 = deterministic).

    Examples
    --------
    >>> config = LLMConfig()
    >>> config.provider
    'anthropic'
    >>> config.temperature
    0.0
    """

    provider: str = Field(
        default="anthropic",
        min_length=1,
        description="LLM provider name",
    )
    model: str = Field(
        default="claude-opus-4-5",
        min_length=1,
        description="Model identifier",
    )
    max_tokens: int = Field(
        default=4096,
        ge=1,
        le=200000,
        description="Maximum tokens for LLM response",
    )
    temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description="Sampling temperature",
    )


class NoiseFilterConfig(BaseModel):
    """Configuration for noise filtering during text extraction.

    Attributes
    ----------
    min_chunk_chars : int
        Minimum number of characters a chunk must have to be kept.
    skip_patterns : list[str]
        Regular expression patterns; chunks matching any pattern are dropped.

    Examples
    --------
    >>> config = NoiseFilterConfig()
    >>> config.min_chunk_chars
    50
    >>> config.skip_patterns
    []
    """

    min_chunk_chars: int = Field(
        default=50,
        ge=1,
        description="Minimum character count per chunk",
    )
    skip_patterns: list[str] = Field(
        default_factory=list,
        description="Regex patterns for chunks to skip",
    )


class PipelineConfig(BaseModel):
    """Top-level configuration for the PDF to knowledge graph pipeline.

    Attributes
    ----------
    input_dirs : list[Path]
        Directories containing input PDF files.
    output_dir : Path
        Directory for processed output files.
    batch_size : int
        Number of PDFs to process per batch.
    page_chunk_size : int
        Number of pages per chunk for Method B PDF conversion.
    llm : LLMConfig
        LLM provider configuration.
    noise_filter : NoiseFilterConfig
        Noise filter configuration for text extraction.

    Examples
    --------
    >>> from pathlib import Path
    >>> config = PipelineConfig(input_dirs=[Path("data/raw/pdfs")])
    >>> config.output_dir.name
    'processed'
    >>> config.batch_size
    10
    >>> config.page_chunk_size
    30
    """

    input_dirs: list[Path] = Field(
        ...,
        min_length=1,
        description="Input directories containing PDF files",
    )
    output_dir: Path = Field(
        default_factory=lambda: get_path("processed"),
        description="Directory for processed output",
    )
    batch_size: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Number of PDFs per batch",
    )
    page_chunk_size: int = Field(
        default=30,
        ge=1,
        le=200,
        description="Number of pages per chunk for Method B PDF conversion",
    )
    llm: LLMConfig = Field(
        default_factory=LLMConfig,
        description="LLM provider configuration",
    )
    noise_filter: NoiseFilterConfig = Field(
        default_factory=NoiseFilterConfig,
        description="Noise filter configuration",
    )
    text_only: bool = Field(
        default=True,
        description="Skip table detection/reconstruction when True",
    )
    enable_knowledge_extraction: bool = Field(
        default=False,
        description="Enable Phase 5 knowledge extraction (Entity/Fact/Claim)",
    )
    chunk_template: Path = Field(
        default_factory=lambda: get_path("config/chunk-template.md"),
        description="Path to the Markdown output template for report.md rendering",
    )


# ---------------------------------------------------------------------------
# Frozen dataclass models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProcessingState:
    """Processing state for a single PDF document.

    Attributes
    ----------
    pdf_path : Path
        Path to the PDF file being processed.
    status : ProcessingStatus
        Current processing status: 'pending', 'processing', 'completed', or 'failed'.
    error : str | None
        Error message if status is 'failed', otherwise None.
    chunk_count : int
        Number of chunks extracted from the PDF (0 if not yet processed).

    Examples
    --------
    >>> from pathlib import Path
    >>> state = ProcessingState(pdf_path=Path("report.pdf"), status="pending")
    >>> state.status
    'pending'
    >>> state.chunk_count
    0
    """

    pdf_path: Path
    status: ProcessingStatus
    error: str | None = None
    chunk_count: int = 0


@dataclass(frozen=True)
class PdfMetadata:
    """Metadata for a PDF document.

    Attributes
    ----------
    pdf_path : Path
        Local path to the PDF file.
    title : str
        Document title.
    page_count : int
        Total number of pages.
    author : str | None
        Document author, if available.
    publisher : str | None
        Publishing organization, if available.
    language : str
        ISO 639-1 language code (default: 'en').

    Examples
    --------
    >>> from pathlib import Path
    >>> meta = PdfMetadata(
    ...     pdf_path=Path("report.pdf"),
    ...     title="Q4 2025 Market Report",
    ...     page_count=30,
    ... )
    >>> meta.language
    'en'
    """

    pdf_path: Path
    title: str
    page_count: int
    author: str | None = None
    publisher: str | None = None
    language: str = "en"


@dataclass(frozen=True)
class BatchManifest:
    """Manifest for a batch of PDF files to process together.

    Attributes
    ----------
    batch_id : str
        Unique identifier for this batch.
    pdf_paths : tuple[Path, ...]
        Ordered tuple of PDF file paths in this batch.
    total_pages : int
        Total page count across all PDFs in the batch (0 if unknown).
    output_dir : Path | None
        Batch-specific output directory override, if any.

    Examples
    --------
    >>> from pathlib import Path
    >>> manifest = BatchManifest(
    ...     batch_id="batch-001",
    ...     pdf_paths=(Path("a.pdf"), Path("b.pdf")),
    ... )
    >>> len(manifest.pdf_paths)
    2
    >>> manifest.total_pages
    0
    """

    batch_id: str
    pdf_paths: tuple[Path, ...]
    total_pages: int = 0
    output_dir: Path | None = None
