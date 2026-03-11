"""Exception hierarchy for the pdf_pipeline package.

Provides a structured exception hierarchy for error handling across
the PDF processing pipeline: scanning, conversion, state management,
and configuration.

Classes
-------
PdfPipelineError
    Base exception for all pdf_pipeline errors.
ConfigError
    Raised when configuration is invalid.
ConversionError
    Raised when PDF conversion or extraction fails.
ScanError
    Raised when PDF directory scanning fails.
StateError
    Raised when state persistence operations fail.
LLMProviderError
    Raised when an LLM provider operation fails.
PathTraversalError
    Raised when a path traversal attack is detected.

Examples
--------
>>> try:
...     raise ConfigError("Missing required field", field="input_dirs")
... except PdfPipelineError as e:
...     print(f"Caught: {e}")
Caught: Missing required field
"""

from __future__ import annotations


class PdfPipelineError(Exception):
    """Base exception for all pdf_pipeline errors.

    All pdf_pipeline exceptions inherit from this class,
    allowing callers to catch all errors with a single except clause.
    """


class ConfigError(PdfPipelineError):
    """Raised when configuration is invalid or cannot be loaded.

    Attributes
    ----------
    field : str | None
        The configuration field that caused the error, or ``None`` if unspecified.

    Examples
    --------
    >>> try:
    ...     raise ConfigError("Config file not found", field="path")
    ... except ConfigError as e:
    ...     print(f"Field: {e.field}, Error: {e}")
    Field: path, Error: Config file not found
    """

    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


class ConversionError(PdfPipelineError):
    """Raised when PDF conversion or text extraction fails.

    Attributes
    ----------
    path : str
        The PDF file path that failed to convert.
    step : str | None
        The conversion step that failed, or ``None`` if unspecified.

    Examples
    --------
    >>> try:
    ...     raise ConversionError("Text extraction failed", path="/tmp/report.pdf")
    ... except ConversionError as e:
    ...     print(f"Path: {e.path}, Error: {e}")
    Path: /tmp/report.pdf, Error: Text extraction failed
    """

    def __init__(self, message: str, *, path: str, step: str | None = None) -> None:
        super().__init__(message)
        self.path = path
        self.step = step


class ScanError(PdfPipelineError):
    """Raised when PDF directory scanning fails.

    Attributes
    ----------
    path : str
        The path that caused the scan error.

    Examples
    --------
    >>> try:
    ...     raise ScanError("Directory not found", path="/data/pdfs")
    ... except ScanError as e:
    ...     print(f"Path: {e.path}, Error: {e}")
    Path: /data/pdfs, Error: Directory not found
    """

    def __init__(self, message: str, *, path: str) -> None:
        super().__init__(message)
        self.path = path


class StateError(PdfPipelineError):
    """Raised when state persistence operations fail.

    Attributes
    ----------
    state_file : str
        Path to the state file involved in the error.

    Examples
    --------
    >>> try:
    ...     raise StateError("Cannot write state", state_file=".tmp/state.json")
    ... except StateError as e:
    ...     print(f"State file: {e.state_file}")
    State file: .tmp/state.json
    """

    def __init__(self, message: str, *, state_file: str) -> None:
        super().__init__(message)
        self.state_file = state_file


class LLMProviderError(PdfPipelineError):
    """Raised when an LLM provider operation fails.

    Attributes
    ----------
    provider : str | None
        Name of the provider that raised the error, or ``None`` if unspecified.

    Examples
    --------
    >>> try:
    ...     raise LLMProviderError("Gemini CLI failed", provider="GeminiCLIProvider")
    ... except LLMProviderError as e:
    ...     print(f"Provider: {e.provider}, Error: {e}")
    Provider: GeminiCLIProvider, Error: Gemini CLI failed
    """

    def __init__(self, message: str, *, provider: str | None = None) -> None:
        super().__init__(message)
        self.provider = provider


class PathTraversalError(PdfPipelineError):
    """Raised when a path traversal attack is detected.

    Attributes
    ----------
    path : str
        The malicious path that was detected.
    base_dir : str
        The base directory that was being protected.

    Examples
    --------
    >>> try:
    ...     raise PathTraversalError(
    ...         "Path traversal detected",
    ...         path="../../../etc/passwd",
    ...         base_dir="/data/pdfs",
    ...     )
    ... except PathTraversalError as e:
    ...     print(f"Blocked: {e.path}")
    Blocked: ../../../etc/passwd
    """

    def __init__(self, message: str, *, path: str, base_dir: str) -> None:
        super().__init__(message)
        self.path = path
        self.base_dir = base_dir
