"""PDF to knowledge graph pipeline package for note-finance.

This package provides tools to convert PDF documents into structured
knowledge graphs, supporting LLM-based extraction and Neo4j integration.

Modules
-------
exceptions
    Exception hierarchy: ``PdfPipelineError``, ``LLMProviderError``, etc.
_logging
    Structured logging via structlog.

Examples
--------
>>> from pdf_pipeline import PdfPipelineError, LLMProviderError
>>> from pdf_pipeline.exceptions import ConversionError, ConfigError
"""

from pdf_pipeline.exceptions import (
    ConfigError,
    ConversionError,
    LLMProviderError,
    PdfPipelineError,
)

__all__ = [
    "ConfigError",
    "ConversionError",
    "LLMProviderError",
    "PdfPipelineError",
]
