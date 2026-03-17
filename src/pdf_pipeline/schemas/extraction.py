"""Pydantic schema definitions for knowledge extraction from PDF chunks.

Defines Entity, Fact, Claim, FinancialDataPoint, Stance, CausalLink, and
Question models for structured knowledge extraction from text chunks, and
envelope models for chunk-level and document-level results.

Classes
-------
ExtractedEntity
    An entity mentioned in the text (company, index, person, etc.).
ExtractedFact
    A factual statement with optional date.
ExtractedClaim
    An opinion, prediction, or recommendation with sentiment and conviction.
ExtractedFinancialDataPoint
    A structured numerical data point extracted from tables or text.
ExtractedStance
    An analyst investment stance (rating + target price + sentiment).
ExtractedCausalLink
    A causal relationship between Fact/Claim/FinancialDataPoint nodes.
ExtractedQuestion
    A knowledge gap identified during extraction.
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
>>> fact.fact_type
'statistic'
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
        Type of entity (10 types).
    ticker : str | None
        Stock ticker symbol, if applicable.
    isin : str | None
        ISIN code, if applicable.
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
        "country",
        "instrument",
    ] = Field(description="Entity type category")
    ticker: str | None = Field(default=None, description="Stock ticker symbol")
    isin: str | None = Field(default=None, description="ISIN code")
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
        Type of fact (8 types).
    as_of_date : str | None
        Date the fact refers to (ISO 8601 or descriptive).
    about_entities : list[str]
        Names of entities this fact is about.

    Examples
    --------
    >>> f = ExtractedFact(content="Revenue was $100B", fact_type="statistic")
    >>> f.fact_type
    'statistic'
    """

    content: str = Field(min_length=1, description="Factual statement")
    fact_type: Literal[
        "statistic",
        "event",
        "data_point",
        "quote",
        "policy_action",
        "economic_indicator",
        "regulatory",
        "corporate_action",
    ] = Field(description="Type of fact")
    as_of_date: str | None = Field(default=None, description="Date the fact refers to")
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
        Type of claim (10 types).
    sentiment : str | None
        Market sentiment implied by the claim (4 types).
    magnitude : str | None
        Strength of the sentiment or conviction.
    target_price : float | None
        Target price (for recommendation claims).
    rating : str | None
        Rating label (e.g., Buy, Hold, Sell, Overweight).
    time_horizon : str | None
        Time horizon for the claim (e.g., '12M', 'FY26', 'long-term').
    about_entities : list[str]
        Names of entities this claim is about.

    Examples
    --------
    >>> c = ExtractedClaim(content="Stock will rise", claim_type="prediction")
    >>> c.sentiment is None
    True
    """

    content: str = Field(min_length=1, description="Claim statement")
    claim_type: Literal[
        "opinion",
        "prediction",
        "recommendation",
        "analysis",
        "assumption",
        "guidance",
        "risk_assessment",
        "policy_stance",
        "sector_view",
        "forecast",
    ] = Field(description="Type of claim")
    sentiment: Literal["bullish", "bearish", "neutral", "mixed"] | None = Field(
        default=None, description="Market sentiment"
    )
    magnitude: Literal["strong", "moderate", "slight"] | None = Field(
        default=None, description="Strength of the sentiment or conviction"
    )
    target_price: float | None = Field(
        default=None, description="Target price (for recommendation claims)"
    )
    rating: str | None = Field(
        default=None,
        max_length=50,
        description="Rating label (e.g., Buy, Hold, Sell, Overweight)",
    )
    time_horizon: str | None = Field(
        default=None,
        max_length=50,
        description="Time horizon for the claim (e.g., '12M', 'FY26', 'long-term')",
    )
    about_entities: list[str] = Field(
        default_factory=list, description="Related entity names"
    )


# ---------------------------------------------------------------------------
# ExtractedFinancialDataPoint
# ---------------------------------------------------------------------------


class ExtractedFinancialDataPoint(BaseModel):
    """A structured numerical data point extracted from tables or text.

    Supports both actual (historical) and estimated (forecast) values
    via the ``is_estimate`` flag.

    Attributes
    ----------
    metric_name : str
        Metric name (e.g., 'Revenue', 'EBITDA', 'ARPU', 'Net Income').
    value : float
        Numeric value.
    unit : str
        Unit (e.g., 'IDR bn', 'USD mn', '%', 'x').
    is_estimate : bool
        True for analyst estimate/forecast, False for actual reported figure.
    currency : str | None
        ISO 4217 currency code (e.g., 'IDR', 'USD').
    period_label : str | None
        Human-readable period label (e.g., 'FY2025', '4Q25', '1H26').
    about_entities : list[str]
        Names of entities this data point is about.

    Examples
    --------
    >>> dp = ExtractedFinancialDataPoint(
    ...     metric_name="Revenue", value=1000.0, unit="USD mn"
    ... )
    >>> dp.is_estimate
    False
    """

    metric_name: str = Field(min_length=1, description="Metric name")
    value: float = Field(description="Numeric value")
    unit: str = Field(min_length=1, description="Unit (e.g., 'IDR bn', 'USD mn', '%')")
    is_estimate: bool = Field(
        default=False,
        description="True for analyst estimate/forecast, False for actual",
    )
    currency: str | None = Field(default=None, description="ISO 4217 currency code")
    period_label: str | None = Field(
        default=None, description="Period label (e.g., 'FY2025', '4Q25')"
    )
    about_entities: list[str] = Field(
        default_factory=list, description="Related entity names"
    )


# ---------------------------------------------------------------------------
# ExtractedStance
# ---------------------------------------------------------------------------


class ExtractedStance(BaseModel):
    """An analyst investment stance extracted from text.

    Captures rating, target price, and sentiment for an entity,
    attributed to an author.  Used to build HOLDS_STANCE, ON_ENTITY,
    and SUPERSEDES relationships in the knowledge graph.

    Attributes
    ----------
    author_name : str
        Name of the analyst or institution expressing the stance.
    author_type : str
        Type of author (6 types matching Author node).
    organization : str | None
        Organization the author belongs to.
    entity_name : str
        Name of the target entity (company, index, etc.).
    rating : str | None
        Rating label (e.g., Buy, Hold, Sell, Overweight).
    sentiment : str | None
        Market sentiment (4 types).
    target_price : float | None
        Target price value.
    target_price_currency : str | None
        ISO 4217 currency code for the target price.
    as_of_date : str | None
        Date the stance was expressed (ISO 8601 or descriptive).
    based_on_claims : list[str]
        Content strings of claims this stance is based on.

    Examples
    --------
    >>> s = ExtractedStance(
    ...     author_name="Goldman Sachs",
    ...     author_type="sell_side",
    ...     entity_name="Apple",
    ...     rating="Buy",
    ... )
    >>> s.rating
    'Buy'
    """

    author_name: str = Field(min_length=1, max_length=500, description="Author name")
    author_type: Literal[
        "person",
        "sell_side",
        "buy_side",
        "consultant",
        "media",
        "self",
    ] = Field(description="Author type")
    organization: str | None = Field(
        default=None, max_length=500, description="Author's organization"
    )
    entity_name: str = Field(
        min_length=1, max_length=500, description="Target entity name"
    )
    rating: str | None = Field(
        default=None,
        max_length=50,
        description="Rating label (e.g., Buy, Hold, Sell, Overweight)",
    )
    sentiment: Literal["bullish", "bearish", "neutral", "mixed"] | None = Field(
        default=None, description="Market sentiment"
    )
    target_price: float | None = Field(default=None, description="Target price value")
    target_price_currency: str | None = Field(
        default=None,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
        description="ISO 4217 currency code for target price",
    )
    as_of_date: str | None = Field(
        default=None, description="Date the stance was expressed"
    )
    based_on_claims: list[str] = Field(
        default_factory=list,
        description="Content of claims this stance is based on",
    )


# ---------------------------------------------------------------------------
# ExtractedCausalLink
# ---------------------------------------------------------------------------


class ExtractedCausalLink(BaseModel):
    """A causal relationship between Fact/Claim/FinancialDataPoint nodes.

    References from/to nodes by their content text (resolved to IDs at
    graph-queue emission time within chunk scope).

    Attributes
    ----------
    from_type : str
        Type of the cause node (``fact``, ``claim``, or ``datapoint``).
    from_content : str
        Content string of the cause node (used for chunk-scope ID resolution).
    to_type : str
        Type of the effect node (``fact``, ``claim``, or ``datapoint``).
    to_content : str
        Content string of the effect node (used for chunk-scope ID resolution).
    mechanism : str | None
        Description of the causal mechanism.
    confidence : str | None
        Confidence level of the causal link (``high``, ``medium``, ``low``).

    Examples
    --------
    >>> link = ExtractedCausalLink(
    ...     from_type="fact",
    ...     from_content="Revenue grew 15%",
    ...     to_type="claim",
    ...     to_content="Stock will rise",
    ... )
    >>> link.from_type
    'fact'
    """

    from_type: Literal["fact", "claim", "datapoint"] = Field(
        description="Type of the cause node"
    )
    from_content: str = Field(min_length=1, description="Content of the cause node")
    to_type: Literal["fact", "claim", "datapoint"] = Field(
        description="Type of the effect node"
    )
    to_content: str = Field(min_length=1, description="Content of the effect node")
    mechanism: str | None = Field(
        default=None, description="Description of the causal mechanism"
    )
    confidence: Literal["high", "medium", "low"] | None = Field(
        default=None, description="Confidence level of the causal link"
    )


# ---------------------------------------------------------------------------
# ExtractedQuestion
# ---------------------------------------------------------------------------


class ExtractedQuestion(BaseModel):
    """A knowledge gap identified during extraction.

    Represents missing information, contradictions, testable predictions,
    or assumptions that require verification.

    Attributes
    ----------
    content : str
        The question text describing the knowledge gap.
    question_type : str
        Type of knowledge gap (4 types).
    priority : str | None
        Priority level for follow-up research.
    about_entities : list[str]
        Names of entities this question is about.
    motivated_by_contents : list[str]
        Content strings of claims/facts/insights that motivated this question.

    Examples
    --------
    >>> q = ExtractedQuestion(
    ...     content="What is the revenue breakdown by segment?",
    ...     question_type="data_gap",
    ... )
    >>> q.question_type
    'data_gap'
    """

    content: str = Field(min_length=1, description="Question text")
    question_type: Literal[
        "data_gap",
        "contradiction",
        "prediction_test",
        "assumption_check",
    ] = Field(description="Type of knowledge gap")
    priority: Literal["high", "medium", "low"] | None = Field(
        default=None, description="Priority level for follow-up research"
    )
    about_entities: list[str] = Field(
        default_factory=list, description="Related entity names"
    )
    motivated_by_contents: list[str] = Field(
        default_factory=list,
        description="Content strings of claims/facts/insights motivating this question",
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
    financial_datapoints : list[ExtractedFinancialDataPoint]
        Financial data points extracted from this chunk.
    stances : list[ExtractedStance]
        Analyst investment stances extracted from this chunk.
    causal_links : list[ExtractedCausalLink]
        Causal relationships between nodes in this chunk.
    questions : list[ExtractedQuestion]
        Knowledge gaps identified in this chunk.

    Examples
    --------
    >>> r = ChunkExtractionResult(chunk_index=0)
    >>> r.entities
    []
    >>> r.stances
    []
    >>> r.causal_links
    []
    >>> r.questions
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
    financial_datapoints: list[ExtractedFinancialDataPoint] = Field(
        default_factory=list, description="Extracted financial data points"
    )
    stances: list[ExtractedStance] = Field(
        default_factory=list, description="Extracted analyst investment stances"
    )
    causal_links: list[ExtractedCausalLink] = Field(
        default_factory=list, description="Causal relationships between nodes"
    )
    questions: list[ExtractedQuestion] = Field(
        default_factory=list, description="Knowledge gaps identified"
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
