"""Pydantic schema definitions for knowledge extraction from PDF chunks.

Defines Entity, Fact, and Claim models for structured knowledge extraction
from text chunks, and envelope models for chunk-level and document-level results.

Classes
-------
ExtractedEntity
    An entity mentioned in the text (company, index, person, etc.).
ExtractedFact
    A factual statement with optional date and confidence.
ExtractedClaim
    An opinion, prediction, or recommendation with sentiment.
ChunkExtractionResult
    Extraction result for a single chunk.
DocumentExtractionResult
    Extraction result for an entire document (all chunks).

Examples
--------
>>> entity = ExtractedEntity(name="Apple", entity_type="company", ticker="AAPL")
>>> entity.entity_type
'company'
>>> fact = ExtractedFact(content="Revenue grew 15%", fact_type="statistic")
>>> fact.confidence
0.8
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# ExtractedEntity
# ---------------------------------------------------------------------------


class ExtractedEntity(BaseModel):
    """An entity extracted from text.

    Attributes
    ----------
    name : str
        Entity name (e.g., "Apple", "S&P 500").
    entity_type : str
        Type of entity.
    ticker : str | None
        Stock ticker symbol, if applicable.
    aliases : list[str]
        Alternative names for the entity.

    Examples
    --------
    >>> e = ExtractedEntity(name="Apple", entity_type="company", ticker="AAPL")
    >>> e.aliases
    []
    """

    name: str = Field(min_length=1, description="Entity name")
    entity_type: Literal[
        "company",
        "index",
        "sector",
        "indicator",
        "currency",
        "commodity",
        "person",
        "organization",
    ] = Field(description="Entity type category")
    ticker: str | None = Field(default=None, description="Stock ticker symbol")
    aliases: list[str] = Field(default_factory=list, description="Alternative names")


# ---------------------------------------------------------------------------
# ExtractedFact
# ---------------------------------------------------------------------------


class ExtractedFact(BaseModel):
    """A factual statement extracted from text.

    Attributes
    ----------
    content : str
        The factual statement.
    fact_type : str
        Type of fact.
    as_of_date : str | None
        Date the fact refers to (ISO 8601 or descriptive).
    confidence : float
        Confidence score (0.0 to 1.0).
    about_entities : list[str]
        Names of entities this fact is about.

    Examples
    --------
    >>> f = ExtractedFact(content="Revenue was $100B", fact_type="statistic")
    >>> f.confidence
    0.8
    """

    content: str = Field(min_length=1, description="Factual statement")
    fact_type: Literal["statistic", "event", "data_point", "quote"] = Field(
        description="Type of fact"
    )
    as_of_date: str | None = Field(default=None, description="Date the fact refers to")
    confidence: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Confidence score"
    )
    about_entities: list[str] = Field(
        default_factory=list, description="Related entity names"
    )


# ---------------------------------------------------------------------------
# ExtractedClaim
# ---------------------------------------------------------------------------


class ExtractedClaim(BaseModel):
    """An opinion, prediction, or recommendation extracted from text.

    Attributes
    ----------
    content : str
        The claim statement.
    claim_type : str
        Type of claim.
    sentiment : str | None
        Market sentiment implied by the claim.
    confidence : float
        Confidence score (0.0 to 1.0).
    about_entities : list[str]
        Names of entities this claim is about.

    Examples
    --------
    >>> c = ExtractedClaim(content="Stock will rise", claim_type="prediction")
    >>> c.sentiment is None
    True
    """

    content: str = Field(min_length=1, description="Claim statement")
    claim_type: Literal["opinion", "prediction", "recommendation", "analysis"] = Field(
        description="Type of claim"
    )
    sentiment: Literal["bullish", "bearish", "neutral"] | None = Field(
        default=None, description="Market sentiment"
    )
    confidence: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Confidence score"
    )
    about_entities: list[str] = Field(
        default_factory=list, description="Related entity names"
    )


# ---------------------------------------------------------------------------
# ChunkExtractionResult
# ---------------------------------------------------------------------------


class ChunkExtractionResult(BaseModel):
    """Extraction result for a single text chunk.

    Attributes
    ----------
    chunk_index : int
        Zero-based index of the chunk within the document.
    section_title : str | None
        Section title of the chunk, if available.
    entities : list[ExtractedEntity]
        Entities extracted from this chunk.
    facts : list[ExtractedFact]
        Facts extracted from this chunk.
    claims : list[ExtractedClaim]
        Claims extracted from this chunk.

    Examples
    --------
    >>> r = ChunkExtractionResult(chunk_index=0)
    >>> r.entities
    []
    """

    chunk_index: int = Field(ge=0, description="Zero-based chunk index")
    section_title: str | None = Field(default=None, description="Section title")
    entities: list[ExtractedEntity] = Field(
        default_factory=list, description="Extracted entities"
    )
    facts: list[ExtractedFact] = Field(
        default_factory=list, description="Extracted facts"
    )
    claims: list[ExtractedClaim] = Field(
        default_factory=list, description="Extracted claims"
    )


# ---------------------------------------------------------------------------
# DocumentExtractionResult
# ---------------------------------------------------------------------------


class DocumentExtractionResult(BaseModel):
    """Extraction result for an entire document.

    Attributes
    ----------
    source_hash : str
        SHA-256 hash of the source PDF.
    chunks : list[ChunkExtractionResult]
        Extraction results for each chunk.

    Examples
    --------
    >>> d = DocumentExtractionResult(source_hash="abc123")
    >>> d.chunks
    []
    """

    source_hash: str = Field(min_length=1, description="SHA-256 hash of the source PDF")
    chunks: list[ChunkExtractionResult] = Field(
        default_factory=list, description="Per-chunk extraction results"
    )
