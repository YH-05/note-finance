"""Markdown section-based chunker for the pdf_pipeline package.

Splits a Markdown document into section-level chunks at heading boundaries
(ATX headings: ``#``, ``##``, ``###``).  Optionally associates a list of
:class:`~pdf_pipeline.schemas.tables.RawTable` objects with each chunk.

Each chunk is returned as a plain dict with the following fields:

- ``source_hash``: SHA-256 hex digest identifying the source PDF.
- ``chunk_index``: Zero-based ordering index.
- ``section_title``: Heading text (or ``None`` if no heading).
- ``content``: Full section text including the heading line.
- ``tables``: List of :class:`~pdf_pipeline.schemas.tables.RawTable` objects
  associated with this section (may be empty).

Classes
-------
MarkdownChunker
    Splits Markdown into section-level chunks.

Examples
--------
>>> chunker = MarkdownChunker()
>>> chunks = chunker.chunk(markdown="# Section\\n\\nContent.", source_hash="abc")
>>> len(chunks)
1
>>> chunks[0]["section_title"]
'Section'
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pdf_pipeline._logging import get_logger
from pdf_pipeline.core._patterns import _HEADING_PATTERN

if TYPE_CHECKING:
    from pdf_pipeline.schemas.tables import RawTable

logger = get_logger(__name__, module="chunker")

# ---------------------------------------------------------------------------
# MarkdownChunker
# ---------------------------------------------------------------------------


class MarkdownChunker:
    """Splits a Markdown document into section-level chunks.

    Each chunk corresponds to a single ATX heading (``#`` / ``##`` / ``###``)
    plus the body text that follows it until the next heading.  Documents
    with no headings are returned as a single chunk with ``section_title=None``.

    Optionally, a list of :class:`~pdf_pipeline.schemas.tables.RawTable`
    objects may be passed; they are distributed across chunks based on their
    page number position relative to section boundaries.  When page-number
    matching is not possible (no heading pages are known), all tables are
    attached to the first chunk.

    Parameters
    ----------
    None

    Examples
    --------
    >>> chunker = MarkdownChunker()
    >>> chunks = chunker.chunk(
    ...     markdown="# Intro\\n\\nContent.",
    ...     source_hash="deadbeef",
    ... )
    >>> chunks[0]["chunk_index"]
    0
    >>> chunks[0]["section_title"]
    'Intro'
    """

    # -- Public API ----------------------------------------------------------

    def chunk(
        self,
        *,
        markdown: str,
        source_hash: str,
        raw_tables: list[RawTable] | None = None,
    ) -> list[dict[str, Any]]:
        """Split Markdown into section-level chunks.

        Parameters
        ----------
        markdown : str
            Markdown text to split.
        source_hash : str
            SHA-256 hex digest of the source PDF (embedded in each chunk).
        raw_tables : list[RawTable] | None
            Optional list of raw tables to associate with chunks.
            Defaults to an empty list when ``None``.

        Returns
        -------
        list[dict[str, Any]]
            Ordered list of chunk dicts.  Each dict contains:
            ``source_hash``, ``chunk_index``, ``section_title``,
            ``content``, and ``tables``.

        Examples
        --------
        >>> chunker = MarkdownChunker()
        >>> chunker.chunk(markdown="", source_hash="abc")
        []
        >>> chunks = chunker.chunk(
        ...     markdown="# H1\\n\\nBody.",
        ...     source_hash="abc",
        ... )
        >>> chunks[0]["section_title"]
        'H1'
        """
        tables: list[RawTable] = raw_tables if raw_tables is not None else []

        if not markdown.strip():
            logger.debug("chunk called with empty markdown", source_hash=source_hash)
            return []

        sections = self._split_into_sections(markdown)

        if not sections:
            return []

        chunks: list[dict[str, Any]] = []
        num_sections = len(sections)

        for idx, section_text in enumerate(sections):
            title = self._extract_heading(section_text)

            chunk: dict[str, Any] = {
                "source_hash": source_hash,
                "chunk_index": idx,
                "section_title": title,
                "content": section_text,
                "tables": [],
            }
            chunks.append(chunk)

        # Distribute tables across chunks
        self._associate_tables(chunks, tables, num_sections)

        logger.debug(
            "Chunking completed",
            source_hash=source_hash,
            chunk_count=len(chunks),
            table_count=len(tables),
        )

        return chunks

    # -- Internal helpers ----------------------------------------------------

    def _split_into_sections(self, markdown: str) -> list[str]:
        """Split Markdown text at ATX heading boundaries.

        Parameters
        ----------
        markdown : str
            Non-empty Markdown text.

        Returns
        -------
        list[str]
            List of section strings, each starting with a heading line.
            When no headings are present, a single-element list with the
            full text is returned.
        """
        lines = markdown.split("\n")
        sections: list[str] = []
        current: list[str] = []
        found_heading = False

        for line in lines:
            if _HEADING_PATTERN.match(line):
                if current:
                    section_text = "\n".join(current).strip()
                    if section_text:
                        sections.append(section_text)
                current = [line]
                found_heading = True
            else:
                current.append(line)

        # Flush last accumulated section
        if current:
            section_text = "\n".join(current).strip()
            if section_text:
                sections.append(section_text)

        if not found_heading:
            full = markdown.strip()
            return [full] if full else []

        return sections

    def _extract_heading(self, section_text: str) -> str | None:
        """Extract the heading text from the first line of a section.

        Parameters
        ----------
        section_text : str
            Section text, possibly starting with an ATX heading.

        Returns
        -------
        str | None
            Heading title without the ``#`` prefix characters,
            or ``None`` if the section has no heading.
        """
        first_line = section_text.split("\n", maxsplit=1)[0]
        match = _HEADING_PATTERN.match(first_line)
        if match:
            return match.group(2).strip()
        return None

    def _associate_tables(
        self,
        chunks: list[dict[str, Any]],
        tables: list[RawTable],
        num_sections: int,
    ) -> None:
        """Associate raw tables with their closest chunk.

        Tables are distributed evenly across chunks by page number.
        When there is only one chunk or no page-number information is
        available, all tables are attached to the first chunk.

        Parameters
        ----------
        chunks : list[dict[str, Any]]
            Chunk dicts to mutate by appending to their ``tables`` key.
        tables : list[RawTable]
            Raw tables to distribute.
        num_sections : int
            Number of sections (same as ``len(chunks)``).
        """
        if not tables or not chunks:
            return

        if num_sections == 1:
            chunks[0]["tables"] = list(tables)
            return

        # Distribute by page number: evenly split page range per chunk
        # Find max page number across all tables
        max_page = max((t.page_number for t in tables), default=1)
        pages_per_chunk = max(1, max_page / num_sections)

        for table in tables:
            # Determine which chunk this table page falls into
            chunk_idx = min(
                int((table.page_number - 1) / pages_per_chunk),
                num_sections - 1,
            )
            chunks[chunk_idx]["tables"].append(table)
