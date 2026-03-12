"""Text extraction abstraction for PDF documents.

Defines the ``TextExtractor`` Protocol and the ``FitzTextExtractor``
implementation that delegates to PyMuPDF (fitz).  Extracting this
boundary allows ``PdfPipeline`` to depend on an abstraction rather
than directly importing ``fitz`` (Dependency Inversion Principle).

Classes
-------
TextExtractor
    Protocol for PDF text extraction.
FitzTextExtractor
    PyMuPDF-backed implementation of TextExtractor.

Examples
--------
>>> from pdf_pipeline.core.text_extractor import FitzTextExtractor
>>> extractor = FitzTextExtractor()
>>> isinstance(extractor, FitzTextExtractor)
True
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from pdf_pipeline._logging import get_logger

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__, module="text_extractor")


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class TextExtractor(Protocol):
    """Protocol for extracting raw text from a PDF file.

    Implementors receive a :class:`~pathlib.Path` and return the
    full raw text of the document as a single string.

    Methods
    -------
    extract(pdf_path)
        Extract and return all text from the given PDF.

    Examples
    --------
    >>> class MockExtractor:
    ...     def extract(self, pdf_path: Path) -> str:
    ...         return "mock text"
    """

    def extract(self, pdf_path: Path) -> str:
        """Extract raw text from a PDF file.

        Parameters
        ----------
        pdf_path : Path
            Path to the PDF file.

        Returns
        -------
        str
            All text extracted from the PDF, pages joined by newlines.
            Returns an empty string when extraction is not possible.
        """
        ...


# ---------------------------------------------------------------------------
# FitzTextExtractor
# ---------------------------------------------------------------------------


class FitzTextExtractor:
    """PyMuPDF-backed text extractor.

    Iterates over all pages of the PDF and joins their text with newline
    characters.  Falls back to an empty string when PyMuPDF is not
    installed or when the file cannot be opened.

    Examples
    --------
    >>> extractor = FitzTextExtractor()
    >>> isinstance(extractor, FitzTextExtractor)
    True
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(self, pdf_path: Path) -> str:
        """Extract raw text from a PDF using PyMuPDF.

        Reads the file from ``pdf_path``, iterates over every page,
        and concatenates page texts with newlines.

        Parameters
        ----------
        pdf_path : Path
            Path to the PDF file to process.

        Returns
        -------
        str
            Concatenated text of all pages.  Returns ``""`` when
            PyMuPDF is unavailable or when the PDF cannot be opened.

        Examples
        --------
        >>> from pathlib import Path
        >>> extractor = FitzTextExtractor()
        >>> # result = extractor.extract(Path("report.pdf"))
        """
        text, doc = self.extract_with_doc(pdf_path)
        if doc is not None:
            doc.close()
        return text

    def extract_with_doc(self, pdf_path: Path) -> tuple[str, Any]:
        """Extract raw text and return the open fitz.Document alongside.

        Useful when the caller also needs to pass the document to another
        component (e.g. ``TableDetector``) to avoid opening the file twice.
        **The caller is responsible for closing the returned document.**

        Parameters
        ----------
        pdf_path : Path
            Path to the PDF file to process.

        Returns
        -------
        tuple[str, fitz.Document | None]
            A 2-tuple of ``(text, doc)`` where ``text`` is the concatenated
            page text and ``doc`` is the open ``fitz.Document`` (or ``None``
            when PyMuPDF is unavailable or the file cannot be opened).

        Examples
        --------
        >>> from pathlib import Path
        >>> extractor = FitzTextExtractor()
        >>> # text, doc = extractor.extract_with_doc(Path("report.pdf"))
        >>> # if doc is not None:
        >>> #     doc.close()
        """
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(str(pdf_path))
            texts: list[str] = []
            for page in doc:
                texts.append(str(page.get_text()))
            result = "\n".join(texts)
            logger.debug(
                "Raw text extracted",
                pdf_path=str(pdf_path),
                char_count=len(result),
            )
            return result, doc
        except ImportError:
            logger.warning(
                "PyMuPDF not available, using empty text",
                pdf_path=str(pdf_path),
            )
            return "", None
        except Exception as exc:
            logger.warning(
                "Failed to extract raw text",
                pdf_path=str(pdf_path),
                error=str(exc),
            )
            return "", None
