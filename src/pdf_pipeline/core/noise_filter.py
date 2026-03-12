"""Regex-based noise filter for PDF text extraction.

Removes boilerplate content (headers, footers, page numbers,
footnotes, disclaimers) from raw PDF text chunks using configurable
regular expression patterns loaded from ``NoiseFilterConfig``.

Classes
-------
NoiseFilter
    Applies regex pattern matching and minimum character length
    filtering to remove noise from extracted PDF text.

Examples
--------
>>> from pdf_pipeline.types import NoiseFilterConfig
>>> config = NoiseFilterConfig(
...     min_chunk_chars=50,
...     skip_patterns=["This report must be read with the disclosures"],
... )
>>> nf = NoiseFilter(config)
>>> nf.is_noise("Short")
True
>>> nf.is_noise("This is a long enough paragraph with valid content.")
False
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from pdf_pipeline._logging import get_logger

if TYPE_CHECKING:
    from pdf_pipeline.types import NoiseFilterConfig

logger = get_logger(__name__, module="noise_filter")


class NoiseFilter:
    """Regex-based noise filter for PDF text chunks.

    Filters out noise text by applying two checks in order:

    1. **Minimum character length**: Chunks shorter than
       ``config.min_chunk_chars`` are discarded.
    2. **Pattern matching**: Chunks matching any pattern in
       ``config.skip_patterns`` (using ``re.search``) are discarded.

    Compiled patterns are cached at initialization time for performance.

    Parameters
    ----------
    config : NoiseFilterConfig
        Noise filter configuration containing ``min_chunk_chars`` and
        ``skip_patterns``.

    Examples
    --------
    >>> from pdf_pipeline.types import NoiseFilterConfig
    >>> config = NoiseFilterConfig(
    ...     min_chunk_chars=10,
    ...     skip_patterns=["^\\\\d+\\\\s*$"],
    ... )
    >>> nf = NoiseFilter(config)
    >>> nf.is_noise("42")
    True
    >>> nf.is_noise("This is valid content.")
    False
    """

    def __init__(self, config: NoiseFilterConfig) -> None:
        """Initialize NoiseFilter with the given configuration.

        Compiles all regex patterns at init time for efficient reuse.

        Parameters
        ----------
        config : NoiseFilterConfig
            Configuration containing ``min_chunk_chars`` and ``skip_patterns``.
        """
        self.config = config
        self._compiled_patterns: list[re.Pattern[str]] = [
            re.compile(pattern) for pattern in config.skip_patterns
        ]
        logger.debug(
            "NoiseFilter initialized",
            min_chunk_chars=config.min_chunk_chars,
            pattern_count=len(self._compiled_patterns),
        )

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def is_noise(self, text: str) -> bool:
        """Check whether a text chunk is noise.

        A chunk is considered noise if:
        - Its character count is less than ``config.min_chunk_chars``, OR
        - It matches any pattern in ``config.skip_patterns``.

        Parameters
        ----------
        text : str
            The text chunk to evaluate.

        Returns
        -------
        bool
            ``True`` if the chunk should be discarded; ``False`` otherwise.

        Examples
        --------
        >>> from pdf_pipeline.types import NoiseFilterConfig
        >>> nf = NoiseFilter(NoiseFilterConfig(min_chunk_chars=10, skip_patterns=[]))
        >>> nf.is_noise("Hi")
        True
        >>> nf.is_noise("This is a long enough sentence.")
        False
        """
        if len(text) < self.config.min_chunk_chars:
            logger.debug(
                "Chunk discarded: too short",
                length=len(text),
                min_chunk_chars=self.config.min_chunk_chars,
            )
            return True

        for pattern in self._compiled_patterns:
            if pattern.search(text):
                logger.debug(
                    "Chunk discarded: matched noise pattern",
                    pattern=pattern.pattern,
                    text_preview=text[:50],
                )
                return True

        return False

    def filter_text(self, text: str) -> str:
        """Filter a single text chunk.

        Returns the original text if it is not noise, otherwise returns
        an empty string.

        Parameters
        ----------
        text : str
            The text chunk to filter.

        Returns
        -------
        str
            The original ``text`` if it passes noise checks; ``""`` otherwise.

        Examples
        --------
        >>> from pdf_pipeline.types import NoiseFilterConfig
        >>> nf = NoiseFilter(NoiseFilterConfig(min_chunk_chars=10, skip_patterns=[]))
        >>> nf.filter_text("Valid content here.")
        'Valid content here.'
        >>> nf.filter_text("Short")
        ''
        """
        if self.is_noise(text):
            return ""
        return text

    def filter_chunks(self, chunks: list[str]) -> list[str]:
        """Filter a list of text chunks, removing all noise entries.

        Iterates over ``chunks`` and discards any chunk for which
        :meth:`is_noise` returns ``True``.  The relative order of
        surviving chunks is preserved.

        Parameters
        ----------
        chunks : list[str]
            List of raw text chunks from PDF extraction.

        Returns
        -------
        list[str]
            Filtered list with noise chunks removed, preserving original order.

        Examples
        --------
        >>> from pdf_pipeline.types import NoiseFilterConfig
        >>> config = NoiseFilterConfig(
        ...     min_chunk_chars=10,
        ...     skip_patterns=["^\\\\d+\\\\s*$"],
        ... )
        >>> nf = NoiseFilter(config)
        >>> nf.filter_chunks(["Valid content here.", "42", "Another valid chunk."])
        ['Valid content here.', 'Another valid chunk.']
        """
        if not chunks:
            logger.debug("filter_chunks called with empty list")
            return []

        original_count = len(chunks)
        filtered = [chunk for chunk in chunks if not self.is_noise(chunk)]
        removed_count = original_count - len(filtered)

        logger.info(
            "Chunks filtered",
            original_count=original_count,
            filtered_count=len(filtered),
            removed_count=removed_count,
        )
        return filtered
