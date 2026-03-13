"""Deterministic ID generation for pdf_pipeline entities.

Provides UUID5/SHA-256 based ID generation functions for sources,
chunks, datapoints, and time periods. All functions are deterministic:
the same inputs always produce the same output.

Functions
---------
generate_source_id
    Generate a UUID5-based ID from a source URL.
generate_chunk_id
    Generate a UUID5-based ID for a specific chunk within a source.
generate_datapoint_id
    Generate a SHA-256 based short ID from datapoint content.
generate_period_id
    Generate a UUID5-based ID from a time period string.

Examples
--------
>>> generate_source_id("https://example.com/report.pdf")  # doctest: +ELLIPSIS
'...'
>>> id1 = generate_source_id("https://example.com/report.pdf")
>>> id2 = generate_source_id("https://example.com/report.pdf")
>>> id1 == id2
True
"""

from __future__ import annotations

import hashlib
import uuid


def generate_source_id(url: str) -> str:
    """Generate a deterministic source ID from a URL.

    Uses UUID5 with NAMESPACE_URL to produce the same ID for the same URL.
    Consistent with the pattern used in ``scripts/emit_graph_queue.py``.

    Parameters
    ----------
    url : str
        The source URL (e.g., a PDF download URL or web page URL).

    Returns
    -------
    str
        UUID5 string derived from the URL.

    Examples
    --------
    >>> id1 = generate_source_id("https://example.com/q4.pdf")
    >>> id2 = generate_source_id("https://example.com/q4.pdf")
    >>> id1 == id2
    True
    >>> len(id1)
    36
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, url))


def generate_chunk_id(source_id: str, chunk_index: int) -> str:
    """Generate a deterministic chunk ID from a source ID and chunk index.

    Uses UUID5 to produce the same ID for the same ``(source_id, chunk_index)``
    pair, enabling stable references across pipeline re-runs.

    Parameters
    ----------
    source_id : str
        The ID of the parent source (typically from ``generate_source_id``).
    chunk_index : int
        Zero-based index of the chunk within the source document.

    Returns
    -------
    str
        UUID5 string derived from ``chunk:{source_id}:{chunk_index}``.

    Examples
    --------
    >>> id_a = generate_chunk_id("src-001", 0)
    >>> id_b = generate_chunk_id("src-001", 0)
    >>> id_a == id_b
    True
    >>> generate_chunk_id("src-001", 0) != generate_chunk_id("src-001", 1)
    True
    """
    key = f"chunk:{source_id}:{chunk_index}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def generate_datapoint_id(content: str) -> str:
    """Generate a deterministic datapoint ID from content text.

    Uses the first 32 hex characters (128-bit) of the SHA-256 hash of
    *content*. Consistent with the claim ID pattern in
    ``scripts/emit_graph_queue.py``.

    Parameters
    ----------
    content : str
        The datapoint content text (e.g., a fact or claim statement).

    Returns
    -------
    str
        First 32 hex characters (128-bit) of the SHA-256 hash of *content*.

    Examples
    --------
    >>> id1 = generate_datapoint_id("GDP grew 2.5% in Q4")
    >>> id2 = generate_datapoint_id("GDP grew 2.5% in Q4")
    >>> id1 == id2
    True
    >>> len(id1)
    32
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:32]


def generate_entity_id(name: str, entity_type: str) -> str:
    """Generate a deterministic entity ID from name and type.

    Uses UUID5 with NAMESPACE_URL to produce the same ID for the same
    ``(name, entity_type)`` pair.

    Parameters
    ----------
    name : str
        Entity name (e.g., "Apple", "S&P 500").
    entity_type : str
        Entity type (e.g., "company", "index").

    Returns
    -------
    str
        UUID5 string derived from ``entity:{name}:{entity_type}``.

    Examples
    --------
    >>> id1 = generate_entity_id("Apple", "company")
    >>> id2 = generate_entity_id("Apple", "company")
    >>> id1 == id2
    True
    >>> generate_entity_id("Apple", "company") != generate_entity_id("Google", "company")
    True
    """
    key = f"entity:{name}:{entity_type}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def generate_period_id(period: str) -> str:
    """Generate a deterministic period ID from a time period string.

    Uses UUID5 to produce the same ID for the same period string.
    The period format is flexible (e.g., '2025-Q4', '2025-12', '2025-12-31').

    Parameters
    ----------
    period : str
        Time period string (e.g., '2025-Q4', '2026-01', '2025-12-31').

    Returns
    -------
    str
        UUID5 string derived from ``period:{period}``.

    Examples
    --------
    >>> id1 = generate_period_id("2025-Q4")
    >>> id2 = generate_period_id("2025-Q4")
    >>> id1 == id2
    True
    >>> generate_period_id("2025-Q3") != generate_period_id("2025-Q4")
    True
    >>> len(generate_period_id("2026-01"))
    36
    """
    key = f"period:{period}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))
