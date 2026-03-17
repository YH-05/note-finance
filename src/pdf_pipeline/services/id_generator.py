"""Deterministic ID generation for pdf_pipeline entities.

Provides UUID5/SHA-256 based ID generation functions for sources,
chunks, datapoints, claims, facts, and time periods. All functions
are deterministic: the same inputs always produce the same output.

Functions
---------
generate_source_id
    Generate a UUID5-based ID from a source URL.
generate_entity_id
    Generate a UUID5-based ID from an entity name and type.
generate_chunk_id
    Generate a UUID5-based ID for a specific chunk within a source.
generate_datapoint_id
    Generate a SHA-256 based short ID from datapoint content.
generate_datapoint_id_from_fields
    Generate a SHA-256 based short ID from source hash, metric, and period.
generate_claim_id
    Generate a SHA-256 based short ID from claim content.
generate_fact_id
    Generate a SHA-256 based short ID from fact content.
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


def _sha256_prefix(key: str, length: int = 32) -> str:
    """Return the first *length* hex characters of a SHA-256 hash.

    Parameters
    ----------
    key : str
        Input text to hash.
    length : int, optional
        Number of hex characters to return (default 32, i.e. 128-bit).

    Returns
    -------
    str
        First *length* hex characters of the SHA-256 digest.
    """
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:length]


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
    return _sha256_prefix(content)


def generate_datapoint_id_from_fields(
    source_hash: str, metric: str, period: str
) -> str:
    """Generate a deterministic datapoint ID from source hash, metric, and period.

    Uses SHA-256 hashing with colon-delimited fields to prevent ID collisions
    caused by special characters (e.g., underscores) in LLM-generated text.

    Parameters
    ----------
    source_hash : str
        The SHA-256 hash of the source document.
    metric : str
        Metric name (e.g., 'Revenue', 'EBITDA').
    period : str
        Period label (e.g., 'FY2025', '4Q25').

    Returns
    -------
    str
        First 32 hex characters (128-bit) of the SHA-256 hash.

    Notes
    -----
    Previous implementation used string concatenation
    (``f"{source_hash}_{metric}_{period}"``), which caused collision risk
    when fields contained underscores. See Issue #74 (CWE-20).

    Examples
    --------
    >>> id1 = generate_datapoint_id_from_fields("abc", "Revenue", "FY2025")
    >>> id2 = generate_datapoint_id_from_fields("abc", "Revenue", "FY2025")
    >>> id1 == id2
    True
    >>> len(id1)
    32
    """
    key = f"{source_hash}:{metric}:{period}"
    return _sha256_prefix(key)


def generate_claim_id(content: str) -> str:
    """Generate a deterministic claim ID from content.

    Parameters
    ----------
    content : str
        Claim content text.

    Returns
    -------
    str
        First 32 hex characters (128-bit) of the SHA-256 hash of *content*.

    Examples
    --------
    >>> id1 = generate_claim_id("S&P 500 rose 2% this week.")
    >>> id2 = generate_claim_id("S&P 500 rose 2% this week.")
    >>> id1 == id2
    True
    >>> len(id1)
    32
    """
    return _sha256_prefix(content)


def generate_fact_id(content: str) -> str:
    """Generate a deterministic fact ID from content.

    Uses a ``fact:`` prefix before hashing to ensure fact IDs never
    collide with claim IDs even when the content text is identical.

    Parameters
    ----------
    content : str
        Fact content text.

    Returns
    -------
    str
        First 32 hex characters (128-bit) of the SHA-256 hash of ``fact:{content}``.

    Examples
    --------
    >>> id1 = generate_fact_id("Revenue was $100B in Q4")
    >>> id2 = generate_fact_id("Revenue was $100B in Q4")
    >>> id1 == id2
    True
    >>> len(id1)
    32
    """
    return _sha256_prefix(f"fact:{content}")


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


def generate_stance_id(author_name: str, entity_name: str, as_of_date: str) -> str:
    """Generate a deterministic stance ID from author, entity, and date.

    Uses UUID5 with NAMESPACE_URL to produce the same ID for the same
    ``(author_name, entity_name, as_of_date)`` triple.

    Parameters
    ----------
    author_name : str
        Author name (e.g., "Goldman Sachs").
    entity_name : str
        Entity name (e.g., "Apple").
    as_of_date : str
        Date string (e.g., "2026-03-15").

    Returns
    -------
    str
        UUID5 string derived from ``stance:{author_name}:{entity_name}:{as_of_date}``.

    Examples
    --------
    >>> id1 = generate_stance_id("Goldman Sachs", "Apple", "2026-03-15")
    >>> id2 = generate_stance_id("Goldman Sachs", "Apple", "2026-03-15")
    >>> id1 == id2
    True
    >>> generate_stance_id("GS", "Apple", "2026-03-15") != generate_stance_id("MS", "Apple", "2026-03-15")
    True
    >>> len(generate_stance_id("GS", "Apple", "2026-03-15"))
    36
    """
    key = f"stance:{author_name}:{entity_name}:{as_of_date}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def generate_author_id(name: str, author_type: str) -> str:
    """Generate a deterministic author ID from name and type.

    Uses UUID5 with NAMESPACE_URL to produce the same ID for the same
    ``(name, author_type)`` pair.

    Parameters
    ----------
    name : str
        Author name (e.g., "Goldman Sachs", "John Smith").
    author_type : str
        Author type (e.g., "sell_side", "person", "buy_side").

    Returns
    -------
    str
        UUID5 string derived from ``author:{name}:{author_type}``.

    Examples
    --------
    >>> id1 = generate_author_id("Goldman Sachs", "sell_side")
    >>> id2 = generate_author_id("Goldman Sachs", "sell_side")
    >>> id1 == id2
    True
    >>> generate_author_id("GS", "sell_side") != generate_author_id("MS", "sell_side")
    True
    >>> len(generate_author_id("GS", "sell_side"))
    36
    """
    key = f"author:{name}:{author_type}"
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
