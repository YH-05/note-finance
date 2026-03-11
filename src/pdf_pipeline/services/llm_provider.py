"""LLMProvider Protocol definition for the pdf_pipeline package.

Defines the ``@runtime_checkable`` Protocol that all LLM provider
implementations must satisfy. Provides extension points for PDF-to-Markdown
conversion, table extraction, and knowledge graph extraction.

Also provides ISP-compliant sub-protocols:

- :class:`MarkdownProvider`: required by :class:`~pdf_pipeline.core.markdown_converter.MarkdownConverter`
- :class:`TableProvider`: required by :class:`~pdf_pipeline.core.table_reconstructor.TableReconstructor`

Classes
-------
MarkdownProvider
    Narrow Protocol for PDF→Markdown conversion (ISP).
TableProvider
    Narrow Protocol for table JSON extraction (ISP).
LLMProvider
    Full runtime-checkable Protocol (backward compatible, extends both).

Examples
--------
>>> from pdf_pipeline.services.llm_provider import LLMProvider
>>> class MyProvider:
...     def convert_pdf_to_markdown(self, pdf_path: str) -> str:
...         return "# Converted"
...     def extract_table_json(self, text: str) -> str:
...         return "{}"
...     def extract_knowledge(self, text: str) -> str:
...         return "{}"
...     def is_available(self) -> bool:
...         return True
>>> isinstance(MyProvider(), LLMProvider)
True
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class MarkdownProvider(Protocol):
    """Narrow Protocol for PDF→Markdown conversion.

    Used by :class:`~pdf_pipeline.core.markdown_converter.MarkdownConverter`.
    Satisfies the Interface Segregation Principle: converters only need
    ``convert_pdf_to_markdown`` and ``is_available``.

    Methods
    -------
    convert_pdf_to_markdown(pdf_path)
        Convert a PDF file to Markdown text.
    is_available()
        Check whether this provider is currently available.

    Examples
    --------
    >>> class MockMarkdownProvider:
    ...     def convert_pdf_to_markdown(self, pdf_path: str) -> str:
    ...         return "# Mock"
    ...     def is_available(self) -> bool:
    ...         return True
    """

    def convert_pdf_to_markdown(self, pdf_path: str) -> str:
        """Convert a PDF file to Markdown text.

        Parameters
        ----------
        pdf_path : str
            Absolute or relative path to the PDF file.

        Returns
        -------
        str
            Markdown-formatted text extracted from the PDF.
        """
        ...

    def is_available(self) -> bool:
        """Check whether this provider is currently available.

        Returns
        -------
        bool
            ``True`` if the provider can be used; ``False`` otherwise.
        """
        ...


class TableProvider(Protocol):
    """Narrow Protocol for table JSON extraction.

    Used by :class:`~pdf_pipeline.core.table_reconstructor.TableReconstructor`.
    Satisfies the Interface Segregation Principle: reconstructors only need
    ``extract_table_json`` and ``is_available``.

    Methods
    -------
    extract_table_json(text)
        Extract structured table data as JSON from text.
    is_available()
        Check whether this provider is currently available.

    Examples
    --------
    >>> class MockTableProvider:
    ...     def extract_table_json(self, text: str) -> str:
    ...         return '{"table_type": "unknown"}'
    ...     def is_available(self) -> bool:
    ...         return True
    """

    def extract_table_json(self, text: str) -> str:
        """Extract structured table data from text as JSON.

        Parameters
        ----------
        text : str
            Text containing table data to extract.

        Returns
        -------
        str
            JSON-encoded table data.
        """
        ...

    def is_available(self) -> bool:
        """Check whether this provider is currently available.

        Returns
        -------
        bool
            ``True`` if the provider can be used; ``False`` otherwise.
        """
        ...


@runtime_checkable
class LLMProvider(Protocol):
    """Runtime-checkable Protocol for LLM provider implementations.

    All concrete providers (GeminiCLIProvider, ClaudeCodeProvider, etc.)
    must implement each of these four methods to satisfy this Protocol.

    The ``@runtime_checkable`` decorator allows ``isinstance()`` checks
    against this Protocol, enabling dynamic provider selection and
    composition (e.g., ProviderChain).

    Methods
    -------
    convert_pdf_to_markdown(pdf_path)
        Convert a PDF file to Markdown text.
    extract_table_json(text)
        Extract structured table data as JSON from text.
    extract_knowledge(text)
        Extract knowledge graph entities and relations as JSON.
    is_available()
        Check whether this provider is currently available.

    Examples
    --------
    >>> class MockProvider:
    ...     def convert_pdf_to_markdown(self, pdf_path: str) -> str:
    ...         return "# Mock"
    ...     def extract_table_json(self, text: str) -> str:
    ...         return "{}"
    ...     def extract_knowledge(self, text: str) -> str:
    ...         return "{}"
    ...     def is_available(self) -> bool:
    ...         return True
    >>> isinstance(MockProvider(), LLMProvider)
    True
    """

    def convert_pdf_to_markdown(self, pdf_path: str) -> str:
        """Convert a PDF file to Markdown text.

        Parameters
        ----------
        pdf_path : str
            Absolute or relative path to the PDF file.

        Returns
        -------
        str
            Markdown-formatted text extracted from the PDF.

        Raises
        ------
        LLMProviderError
            If the conversion fails.
        """
        ...

    def extract_table_json(self, text: str) -> str:
        """Extract structured table data from text as JSON.

        Parameters
        ----------
        text : str
            Text containing table data to extract.

        Returns
        -------
        str
            JSON-encoded table data.

        Raises
        ------
        LLMProviderError
            If the extraction fails.
        """
        ...

    def extract_knowledge(self, text: str) -> str:
        """Extract knowledge graph entities and relations from text as JSON.

        Parameters
        ----------
        text : str
            Text from which to extract entities and relationships.

        Returns
        -------
        str
            JSON-encoded knowledge graph with entities and relations.

        Raises
        ------
        LLMProviderError
            If the extraction fails.
        """
        ...

    def is_available(self) -> bool:
        """Check whether this provider is currently available.

        Returns
        -------
        bool
            ``True`` if the provider can be used; ``False`` otherwise.
            Availability checks may include: command existence (``shutil.which``),
            SDK importability (``importlib``), or API reachability.
        """
        ...
