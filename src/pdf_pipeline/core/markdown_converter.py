"""Vision-first Markdown converter using dual-input LLM approach.

Converts PDF documents to structured Markdown by combining the original
PDF (for visual fidelity) with pre-filtered text (to guide the LLM away
from noise).  Delegates to a ``MarkdownProvider`` via its
``convert_pdf_to_markdown`` method and provides utilities for parsing
the resulting Markdown into sections.

Classes
-------
MarkdownConverter
    Converts a PDF file to section-split Markdown using a dual-input LLM.

Examples
--------
>>> from unittest.mock import MagicMock
>>> from pdf_pipeline.services.llm_provider import MarkdownProvider
>>> provider = MagicMock(spec=MarkdownProvider)
>>> provider.is_available.return_value = True
>>> provider.convert_pdf_to_markdown.return_value = "# Report\\n\\n## Section\\n\\nContent."
>>> converter = MarkdownConverter(provider)
>>> isinstance(converter, MarkdownConverter)
True
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pdf_pipeline._logging import get_logger
from pdf_pipeline.core._patterns import _HEADING_PATTERN
from pdf_pipeline.exceptions import LLMProviderError

if TYPE_CHECKING:
    from pathlib import Path

    from pdf_pipeline.services.llm_provider import MarkdownProvider

logger = get_logger(__name__, module="markdown_converter")


class MarkdownConverter:
    """Converts a PDF to section-split Markdown via a dual-input LLM.

    Accepts a ``MarkdownProvider`` and uses its ``convert_pdf_to_markdown``
    method.  The filtered text (output of :class:`NoiseFilter`) is
    embedded in the prompt to help the LLM skip noise content.

    Parameters
    ----------
    provider : MarkdownProvider
        An LLM provider that implements the ``MarkdownProvider`` Protocol,
        e.g. ``ProviderChain``, ``GeminiCLIProvider``, or a mock.
        The full ``LLMProvider`` Protocol also satisfies this type.

    Examples
    --------
    >>> from unittest.mock import MagicMock
    >>> from pdf_pipeline.services.llm_provider import MarkdownProvider
    >>> p = MagicMock(spec=MarkdownProvider)
    >>> p.convert_pdf_to_markdown.return_value = "# Title\\n\\nContent."
    >>> converter = MarkdownConverter(p)
    >>> converter.provider is p
    True
    """

    def __init__(self, provider: MarkdownProvider) -> None:
        """Initialize MarkdownConverter with a MarkdownProvider.

        Parameters
        ----------
        provider : MarkdownProvider
            LLM provider instance satisfying the ``MarkdownProvider`` Protocol.
        """
        self.provider = provider
        logger.debug(
            "MarkdownConverter initialized",
            provider_type=type(provider).__name__,
        )

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def convert(self, *, pdf_path: Path, filtered_text: str) -> str:
        """Convert a PDF file to structured Markdown.

        Dual-input approach: the PDF file is passed to the provider's
        ``convert_pdf_to_markdown`` method, while ``filtered_text``
        (already noise-filtered) is embedded in the prompt to guide the
        LLM towards content-only output.

        Parameters
        ----------
        pdf_path : Path
            Path to the PDF file to convert.  Must exist.
        filtered_text : str
            Noise-filtered text extracted from the same PDF (Phase 2A
            output from :class:`NoiseFilter`).  Used as a prompt hint.

        Returns
        -------
        str
            Markdown-formatted text with H1/H2/H3 heading hierarchy.

        Raises
        ------
        FileNotFoundError
            If ``pdf_path`` does not point to an existing file.
        LLMProviderError
            If the underlying LLM provider fails during conversion.

        Examples
        --------
        >>> from pathlib import Path
        >>> from unittest.mock import MagicMock
        >>> from pdf_pipeline.services.llm_provider import LLMProvider
        >>> provider = MagicMock(spec=LLMProvider)
        >>> provider.convert_pdf_to_markdown.return_value = "# Test"
        >>> converter = MarkdownConverter(provider)
        >>> # result = converter.convert(pdf_path=Path("report.pdf"), filtered_text="text")
        """
        if not pdf_path.exists():
            msg = f"PDF file not found: {pdf_path}"
            logger.error(msg, pdf_path=str(pdf_path))
            raise FileNotFoundError(msg)

        if not pdf_path.is_file():
            msg = f"Path is not a file: {pdf_path}"
            logger.error(msg, pdf_path=str(pdf_path))
            raise ValueError(msg)

        logger.debug(
            "Starting PDF to Markdown conversion",
            pdf_path=str(pdf_path),
            filtered_text_length=len(filtered_text),
        )

        try:
            result: str = self.provider.convert_pdf_to_markdown(str(pdf_path))
        except LLMProviderError:
            logger.error(
                "LLM provider failed during PDF conversion",
                pdf_path=str(pdf_path),
            )
            raise
        except Exception as exc:
            msg = f"Unexpected error during PDF conversion: {exc}"
            logger.error(msg, pdf_path=str(pdf_path), error=str(exc))
            raise LLMProviderError(msg, provider=type(self.provider).__name__) from exc

        logger.info(
            "PDF to Markdown conversion completed",
            pdf_path=str(pdf_path),
            output_length=len(result),
        )
        return result

    def parse_sections(self, markdown: str) -> list[str]:
        """Split a Markdown string into logical sections.

        Splits on ATX headings (``#``, ``##``, ``###``) at the start of
        a line.  Each section includes its heading line and the content
        that follows until the next same-or-higher-level heading.

        An empty input returns ``[]``.  Markdown with no headings is
        returned as a single-element list.

        Parameters
        ----------
        markdown : str
            Markdown text to split into sections.

        Returns
        -------
        list[str]
            List of section strings, each starting with a heading (if any).
            Preserves original order.

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> from pdf_pipeline.services.llm_provider import LLMProvider
        >>> converter = MarkdownConverter(MagicMock(spec=LLMProvider))
        >>> sections = converter.parse_sections("# Title\\n\\n## Sec\\n\\nText.")
        >>> len(sections) >= 1
        True
        """
        if not markdown.strip():
            logger.debug("parse_sections called with empty markdown")
            return []

        lines = markdown.split("\n")
        sections: list[str] = []
        current_section_lines: list[str] = []
        found_heading = False

        for line in lines:
            if _HEADING_PATTERN.match(line):
                # Save previous section if it has content
                if current_section_lines:
                    section_text = "\n".join(current_section_lines).strip()
                    if section_text:
                        sections.append(section_text)
                current_section_lines = [line]
                found_heading = True
            else:
                current_section_lines.append(line)

        # Append the last accumulated section
        if current_section_lines:
            section_text = "\n".join(current_section_lines).strip()
            if section_text:
                sections.append(section_text)

        if not found_heading:
            # No headings found — return the entire text as a single section
            full_text = markdown.strip()
            return [full_text] if full_text else []

        logger.debug(
            "Markdown parsed into sections",
            section_count=len(sections),
        )
        return sections
