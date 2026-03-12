#!/usr/bin/env python3
"""Emit graph-queue JSON from various command outputs.

Converts outputs from 6 different finance workflow commands into a
unified graph-queue format. Each command produces data in a different
JSON structure; this script normalises them all into a single schema.

Supported commands
------------------
- finance-news-workflow
- ai-research-collect
- generate-market-report
- asset-management
- reddit-finance-topics
- finance-full

Usage
-----
::

    python3 scripts/emit_graph_queue.py \\
        --command finance-news-workflow \\
        --input .tmp/news-batches/index.json

    python3 scripts/emit_graph_queue.py \\
        --command finance-news-workflow \\
        --input .tmp/news-batches/index.json \\
        --cleanup
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

type MapperFn = Callable[[dict[str, Any]], dict[str, Any]]

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMMANDS: list[str] = []  # Populated after COMMAND_MAPPERS definition
"""Supported command names (derived from COMMAND_MAPPERS)."""

DEFAULT_OUTPUT_BASE = Path(".tmp/graph-queue")
"""Default base directory for output queue files."""

DEFAULT_MAX_AGE_DAYS = 7
"""Default maximum age in days for auto-cleanup."""

SCHEMA_VERSION = "2.0"
"""Graph-queue schema version."""

THEME_TO_CATEGORY: dict[str, str] = {
    "index": "stock",
    "stock": "stock",
    "sector": "sector",
    "macro_cnbc": "macro",
    "macro_other": "macro",
    "ai_cnbc": "ai",
    "ai_nasdaq": "ai",
    "ai_tech": "ai",
    "finance_cnbc": "finance",
    "finance_nasdaq": "finance",
    "finance_other": "finance",
}
"""Theme key to category mapping table."""


# ---------------------------------------------------------------------------
# ID Generation
# ---------------------------------------------------------------------------


def generate_source_id(url: str) -> str:
    """Generate a deterministic source ID from a URL.

    Uses UUID5 with NAMESPACE_URL to produce the same ID for the same URL.

    Parameters
    ----------
    url : str
        The source URL.

    Returns
    -------
    str
        UUID5 string derived from the URL.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, url))


def generate_topic_id(name: str, category: str) -> str:
    """Generate a deterministic topic ID from name and category.

    Parameters
    ----------
    name : str
        Topic name.
    category : str
        Topic category.

    Returns
    -------
    str
        UUID5 string derived from ``topic:{name}:{category}``.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"topic:{name}:{category}"))


def generate_entity_id(name: str, entity_type: str) -> str:
    """Generate a deterministic entity ID from name and type.

    Parameters
    ----------
    name : str
        Entity name.
    entity_type : str
        Entity type (e.g. ``company``, ``ticker``).

    Returns
    -------
    str
        UUID5 string derived from ``entity:{name}:{entity_type}``.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"entity:{name}:{entity_type}"))


def generate_claim_id(content: str) -> str:
    """Generate a deterministic claim ID from content.

    Parameters
    ----------
    content : str
        Claim content text.

    Returns
    -------
    str
        First 16 hex characters of the SHA-256 hash of *content*.
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


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
        First 16 hex characters of the SHA-256 hash of ``fact:{content}``.
    """
    return hashlib.sha256(f"fact:{content}".encode("utf-8")).hexdigest()[:16]


def generate_chunk_id(source_hash: str, chunk_index: int) -> str:
    """Generate a deterministic chunk ID from source hash and chunk index.

    Parameters
    ----------
    source_hash : str
        The SHA-256 hash of the source document.
    chunk_index : int
        Zero-based index of the chunk within the document.

    Returns
    -------
    str
        Chunk ID in the format ``{source_hash}_chunk_{chunk_index}``.
    """
    return f"{source_hash}_chunk_{chunk_index}"


def generate_datapoint_id(
    source_hash: str, metric: str, period: str
) -> str:
    """Generate a deterministic datapoint ID from source hash, metric, and period.

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
        Datapoint ID in the format ``{source_hash}_{metric}_{period}``.
    """
    return f"{source_hash}_{metric}_{period}"


def generate_queue_id() -> str:
    """Generate a unique queue ID with timestamp and short hash.

    Returns
    -------
    str
        Queue ID in the format ``gq-{timestamp}-{hash4}``.
    """
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d%H%M%S")
    # Use a hash of the full ISO timestamp for the 4-char suffix
    hash4 = hashlib.sha256(now.isoformat().encode("utf-8")).hexdigest()[:4]
    return f"gq-{timestamp}-{hash4}"


# ---------------------------------------------------------------------------
# Category resolution
# ---------------------------------------------------------------------------


def resolve_category(theme_key: str) -> str:
    """Resolve a theme key to its canonical category.

    Parameters
    ----------
    theme_key : str
        Theme key from the workflow (e.g. ``index``, ``macro_cnbc``).

    Returns
    -------
    str
        Canonical category (``stock``, ``sector``, ``macro``, ``ai``,
        ``finance``).  Falls back to ``"other"`` for unknown keys.
    """
    return THEME_TO_CATEGORY.get(theme_key, "other")


# ---------------------------------------------------------------------------
# Mapping helpers (DRY)
# ---------------------------------------------------------------------------


def _infer_period_type(label: str) -> str:
    """Infer a period type from a human-readable period label.

    Parameters
    ----------
    label : str
        Period label (e.g., ``'FY2025'``, ``'4Q25'``, ``'1H26'``).

    Returns
    -------
    str
        One of ``'annual'``, ``'quarterly'``, or ``'half_year'``.
        Falls back to ``'annual'`` for unrecognised labels.

    Notes
    -----
    Labels containing ``'FQ'`` (e.g. fiscal quarter references in free text)
    are excluded from the quarterly match to avoid false positives.
    """
    upper = label.upper()
    # Exclude 'FQ' (fiscal quarter reference) from quarterly detection
    if "Q" in upper and "FQ" not in upper:
        return "quarterly"
    if "H" in upper:
        return "half_year"
    return "annual"


def _make_source(
    url: str, title: str = "", published: str = "", **extra: Any
) -> dict[str, Any]:
    """Build a Source dict with a deterministic ``source_id``.

    Parameters
    ----------
    url : str
        Source URL.
    title : str
        Source title.
    published : str
        Publication datetime (ISO 8601).
    **extra : Any
        Additional fields merged into the result.

    Returns
    -------
    dict[str, Any]
        Source dict ready for graph-queue output.
    """
    return {
        "source_id": generate_source_id(url),
        "url": url,
        "title": title,
        "published": published,
        **extra,
    }


def _mapped_result(
    data: dict[str, Any],
    batch_label: str,
    *,
    sources: list[dict[str, Any]] | None = None,
    topics: list[dict[str, Any]] | None = None,
    claims: list[dict[str, Any]] | None = None,
    facts: list[dict[str, Any]] | None = None,
    entities: list[dict[str, Any]] | None = None,
    chunks: list[dict[str, Any]] | None = None,
    financial_datapoints: list[dict[str, Any]] | None = None,
    fiscal_periods: list[dict[str, Any]] | None = None,
    relations: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the standard mapper result dict.

    Parameters
    ----------
    data : dict[str, Any]
        Original input data (used to extract ``session_id``).
    batch_label : str
        Label for this batch.
    sources, topics, claims, facts, entities, chunks,
    financial_datapoints, fiscal_periods : list[dict] | None
        Node lists (default to empty lists).
    relations : dict | None
        Relation dict (default to empty dict).

    Returns
    -------
    dict[str, Any]
        Standardised result dict with all keys.
    """
    return {
        "session_id": data.get("session_id", ""),
        "batch_label": batch_label,
        "sources": sources or [],
        "claims": claims or [],
        "facts": facts or [],
        "topics": topics or [],
        "entities": entities or [],
        "chunks": chunks or [],
        "financial_datapoints": financial_datapoints or [],
        "fiscal_periods": fiscal_periods or [],
        "relations": relations or {},
    }


# ---------------------------------------------------------------------------
# Mapping functions
# ---------------------------------------------------------------------------


def map_finance_news(data: dict[str, Any]) -> dict[str, Any]:
    """Map finance-news-workflow batch to graph-queue components.

    Parameters
    ----------
    data : dict[str, Any]
        Input data with ``articles[]``, ``session_id``, ``batch_label``.

    Returns
    -------
    dict[str, Any]
        Mapped components: ``sources``, ``claims``, ``topics``,
        ``entities``, ``relations``, ``session_id``, ``batch_label``.
    """
    articles = data.get("articles", [])
    sources: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []

    for article in articles:
        url = article.get("url", "")
        source_id = generate_source_id(url)

        sources.append(
            _make_source(
                url,
                title=article.get("title", ""),
                published=article.get("published", ""),
                feed_source=article.get("feed_source", ""),
            )
        )

        summary = article.get("summary", "")
        if summary:
            claims.append(
                {
                    "claim_id": generate_claim_id(summary),
                    "content": summary,
                    "source_id": source_id,
                    "category": resolve_category(data.get("batch_label", "")),
                }
            )

    return _mapped_result(
        data,
        data.get("batch_label", ""),
        sources=sources,
        claims=claims,
    )


def map_ai_research(data: dict[str, Any]) -> dict[str, Any]:
    """Map ai-research-collect batch to graph-queue components.

    Parameters
    ----------
    data : dict[str, Any]
        Input data with ``companies[]``, ``session_id``.

    Returns
    -------
    dict[str, Any]
        Mapped components with ``entities[]`` and ``sources[]``.
    """
    companies = data.get("companies", [])
    entities: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []

    for company in companies:
        company_name = company.get("company_name", "")
        ticker = company.get("ticker", "")
        url = company.get("url", "")

        # Create entity for the company
        entities.append(
            {
                "entity_id": generate_entity_id(company_name, "company"),
                "name": company_name,
                "entity_type": "company",
                "ticker": ticker,
            }
        )

        # Create source
        if url:
            sources.append(
                _make_source(
                    url,
                    title=company.get("title", ""),
                    published=company.get("published", ""),
                )
            )

    return _mapped_result(data, "ai", sources=sources, entities=entities)


def map_market_report(data: dict[str, Any]) -> dict[str, Any]:
    """Map generate-market-report data to graph-queue components.

    Parameters
    ----------
    data : dict[str, Any]
        Input data with ``sections[]``, ``session_id``.

    Returns
    -------
    dict[str, Any]
        Mapped components with sources from sections and claims from
        section content.
    """
    sections = data.get("sections", [])
    sources: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for section in sections:
        # Collect sources from section
        for source in section.get("sources", []):
            url = source.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                sources.append(
                    _make_source(
                        url,
                        title=source.get("title", ""),
                        published=source.get("published", ""),
                    )
                )

        # Create claim from section content
        content = section.get("content", "")
        if content:
            claims.append(
                {
                    "claim_id": generate_claim_id(content),
                    "content": content,
                    "section_title": section.get("title", ""),
                    "category": "macro",
                }
            )

    return _mapped_result(data, "market-report", sources=sources, claims=claims)


def map_asset_management(data: dict[str, Any]) -> dict[str, Any]:
    """Map asset-management batch to graph-queue components.

    Parameters
    ----------
    data : dict[str, Any]
        Input data with ``themes.{key}.articles[]``, ``session_id``.

    Returns
    -------
    dict[str, Any]
        Mapped components with ``sources[]`` from theme articles and
        ``topics[]`` from theme names.
    """
    themes = data.get("themes", {})
    sources: list[dict[str, Any]] = []
    topics: list[dict[str, Any]] = []

    for theme_key, theme_data in themes.items():
        name_ja = theme_data.get("name_ja", theme_key)

        # Create topic for the theme
        topics.append(
            {
                "topic_id": generate_topic_id(name_ja, "asset-management"),
                "name": name_ja,
                "category": "asset-management",
                "theme_key": theme_key,
            }
        )

        # Map articles to sources
        articles = theme_data.get("articles", [])
        for article in articles:
            url = article.get("url", "")
            if url:
                sources.append(
                    _make_source(
                        url,
                        title=article.get("title", ""),
                        published=article.get("published", ""),
                        feed_source=article.get("feed_source", ""),
                    )
                )

    return _mapped_result(data, "asset-management", sources=sources, topics=topics)


def map_reddit_topics(data: dict[str, Any]) -> dict[str, Any]:
    """Map reddit-finance-topics batch to graph-queue components.

    Parameters
    ----------
    data : dict[str, Any]
        Input data with ``groups.{key}.topics[]`` or ``topics[]``, ``session_id``.

    Returns
    -------
    dict[str, Any]
        Mapped components with ``sources[]`` from Reddit posts and
        ``topics[]`` from discussion topics.
    """
    input_topics: list[dict[str, Any]] = []

    # Handle nested topics in groups
    groups = data.get("groups", {})
    if groups:
        for group_data in groups.values():
            input_topics.extend(group_data.get("topics", []))
    else:
        # Fallback to root topics
        input_topics = data.get("topics", [])

    sources: list[dict[str, Any]] = []
    topics: list[dict[str, Any]] = []

    for topic in input_topics:
        # Use title as name if name is missing (Reddit posts have title)
        name = topic.get("name", topic.get("title", ""))
        url = topic.get("url", "")

        # Create topic
        topics.append(
            {
                "topic_id": generate_topic_id(name, "reddit"),
                "name": name,
                "category": "reddit",
                "subreddit": topic.get("subreddit", ""),
            }
        )

        # Create source from Reddit post
        if url:
            sources.append(
                _make_source(
                    url,
                    title=topic.get("title", ""),
                    published=topic.get("created_at", ""),
                    subreddit=topic.get("subreddit", ""),
                    score=topic.get("score", 0),
                )
            )

    return _mapped_result(data, "reddit", sources=sources, topics=topics)


def map_pdf_extraction(data: dict[str, Any]) -> dict[str, Any]:
    """Map pdf-extraction (DocumentExtractionResult) to graph-queue components.

    Generates nodes for Source, Chunk, Entity, Fact, Claim,
    FinancialDataPoint, and FiscalPeriod, plus the following relations:

    - ``contains_chunk``: Source → Chunk
    - ``extracted_from_fact``: Fact → Chunk
    - ``extracted_from_claim``: Claim → Chunk
    - ``source_fact``: Source → Fact (STATES_FACT)
    - ``source_claim``: Source → Claim (MAKES_CLAIM)
    - ``fact_entity``: Fact → Entity (RELATES_TO)
    - ``claim_entity``: Claim → Entity (ABOUT)
    - ``has_datapoint``: Source → FinancialDataPoint
    - ``for_period``: FinancialDataPoint → FiscalPeriod
    - ``datapoint_entity``: FinancialDataPoint → Entity (RELATES_TO)

    Parameters
    ----------
    data : dict[str, Any]
        Input data with ``source_hash``, ``chunks[]`` containing
        ``entities[]``, ``facts[]``, ``claims[]``, and optionally
        ``financial_datapoints[]``.

    Returns
    -------
    dict[str, Any]
        Mapped components with ``entities[]``, ``sources[]``,
        ``claims[]``, ``facts[]``, ``chunks[]``,
        ``financial_datapoints[]``, ``fiscal_periods[]``, and
        ``relations``.
    """
    source_hash = data.get("source_hash", "")
    input_chunks = data.get("chunks", [])

    # Create source node for the PDF
    source_id = generate_source_id(f"pdf:{source_hash}")
    sources: list[dict[str, Any]] = [
        {
            "source_id": source_id,
            "url": f"pdf:{source_hash}",
            "title": "",
            "published": "",
            "source_type": "pdf",
        }
    ]

    entities: list[dict[str, Any]] = []
    facts: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    chunk_nodes: list[dict[str, Any]] = []
    financial_datapoints: list[dict[str, Any]] = []
    fiscal_periods: list[dict[str, Any]] = []

    seen_entity_keys: set[str] = set()
    seen_period_ids: set[str] = set()

    # Relations
    source_fact_rels: list[dict[str, str]] = []
    source_claim_rels: list[dict[str, str]] = []
    fact_entity_rels: list[dict[str, str]] = []
    claim_entity_rels: list[dict[str, str]] = []
    contains_chunk_rels: list[dict[str, str]] = []
    extracted_from_fact_rels: list[dict[str, str]] = []
    extracted_from_claim_rels: list[dict[str, str]] = []
    has_datapoint_rels: list[dict[str, str]] = []
    for_period_rels: list[dict[str, str]] = []
    datapoint_entity_rels: list[dict[str, str]] = []

    # Name→ID / Name→ticker maps for O(1) entity resolution
    entity_name_to_id: dict[str, str] = {}
    entity_name_to_ticker: dict[str, str] = {}

    for chunk in input_chunks:
        chunk_index = chunk.get("chunk_index", 0)
        chunk_id = generate_chunk_id(source_hash, chunk_index)

        # Build Chunk node
        chunk_nodes.append(
            {
                "chunk_id": chunk_id,
                "chunk_index": chunk_index,
                "section_title": chunk.get("section_title"),
                "content": chunk.get("content", ""),
            }
        )

        # Source CONTAINS_CHUNK Chunk
        contains_chunk_rels.append(
            {
                "from_id": source_id,
                "to_id": chunk_id,
                "type": "CONTAINS_CHUNK",
            }
        )

        # Entities (deduplicated by name+type)
        for entity in chunk.get("entities", []):
            name = entity.get("name", "")
            entity_type = entity.get("entity_type", "")
            entity_key = f"{name}:{entity_type}"
            if entity_key not in seen_entity_keys:
                seen_entity_keys.add(entity_key)
                eid = generate_entity_id(name, entity_type)
                entities.append(
                    {
                        "entity_id": eid,
                        "name": name,
                        "entity_type": entity_type,
                        "ticker": entity.get("ticker"),
                    }
                )
                entity_name_to_id[name] = eid
                if entity.get("ticker"):
                    entity_name_to_ticker[name] = entity["ticker"]

        # Facts → independent facts[] list
        for fact in chunk.get("facts", []):
            content = fact.get("content", "")
            fact_id = generate_fact_id(content)
            facts.append(
                {
                    "fact_id": fact_id,
                    "content": content,
                    "source_id": source_id,
                    "fact_type": fact.get("fact_type", ""),
                    "as_of_date": fact.get("as_of_date"),
                }
            )
            source_fact_rels.append(
                {"from_id": source_id, "to_id": fact_id, "type": "STATES_FACT"}
            )
            # Fact EXTRACTED_FROM Chunk
            extracted_from_fact_rels.append(
                {"from_id": fact_id, "to_id": chunk_id, "type": "EXTRACTED_FROM"}
            )
            for entity_name in fact.get("about_entities", []):
                resolved_id = entity_name_to_id.get(entity_name)
                if resolved_id:
                    fact_entity_rels.append(
                        {
                            "from_id": fact_id,
                            "to_id": resolved_id,
                            "type": "RELATES_TO",
                        }
                    )

        # Claims
        for claim in chunk.get("claims", []):
            content = claim.get("content", "")
            claim_id = generate_claim_id(content)
            claims.append(
                {
                    "claim_id": claim_id,
                    "content": content,
                    "source_id": source_id,
                    "category": "pdf-claim",
                    "claim_type": claim.get("claim_type", ""),
                    "sentiment": claim.get("sentiment"),
                }
            )
            source_claim_rels.append(
                {"from_id": source_id, "to_id": claim_id, "type": "MAKES_CLAIM"}
            )
            # Claim EXTRACTED_FROM Chunk
            extracted_from_claim_rels.append(
                {"from_id": claim_id, "to_id": chunk_id, "type": "EXTRACTED_FROM"}
            )
            for entity_name in claim.get("about_entities", []):
                resolved_id = entity_name_to_id.get(entity_name)
                if resolved_id:
                    claim_entity_rels.append(
                        {
                            "from_id": claim_id,
                            "to_id": resolved_id,
                            "type": "ABOUT",
                        }
                    )

        # FinancialDataPoints
        for dp in chunk.get("financial_datapoints", []):
            metric_name = dp.get("metric_name", "")
            period_label = dp.get("period_label", "")
            dp_id = generate_datapoint_id(source_hash, metric_name, period_label)

            financial_datapoints.append(
                {
                    "datapoint_id": dp_id,
                    "metric_name": metric_name,
                    "value": dp.get("value"),
                    "unit": dp.get("unit", ""),
                    "is_estimate": dp.get("is_estimate", False),
                    "currency": dp.get("currency"),
                    "period_label": period_label,
                }
            )

            # Source HAS_DATAPOINT FinancialDataPoint
            has_datapoint_rels.append(
                {"from_id": source_id, "to_id": dp_id, "type": "HAS_DATAPOINT"}
            )

            # FiscalPeriod derivation from period_label
            if period_label:
                about_entities = dp.get("about_entities", [])
                ticker = (
                    entity_name_to_ticker.get(about_entities[0], "")
                    if about_entities
                    else ""
                )

                period_id = (
                    f"{ticker}_{period_label}" if ticker else period_label
                )
                if period_id not in seen_period_ids:
                    seen_period_ids.add(period_id)
                    fiscal_periods.append(
                        {
                            "period_id": period_id,
                            "period_type": _infer_period_type(period_label),
                            "period_label": period_label,
                        }
                    )

                # FinancialDataPoint FOR_PERIOD FiscalPeriod
                for_period_rels.append(
                    {"from_id": dp_id, "to_id": period_id, "type": "FOR_PERIOD"}
                )

            # FinancialDataPoint → Entity (RELATES_TO)
            for entity_name in dp.get("about_entities", []):
                resolved_id = entity_name_to_id.get(entity_name)
                if resolved_id:
                    datapoint_entity_rels.append(
                        {
                            "from_id": dp_id,
                            "to_id": resolved_id,
                            "type": "RELATES_TO",
                        }
                    )

    relations: dict[str, Any] = {
        "source_fact": source_fact_rels,
        "source_claim": source_claim_rels,
        "fact_entity": fact_entity_rels,
        "claim_entity": claim_entity_rels,
        "contains_chunk": contains_chunk_rels,
        "extracted_from_fact": extracted_from_fact_rels,
        "extracted_from_claim": extracted_from_claim_rels,
        "has_datapoint": has_datapoint_rels,
        "for_period": for_period_rels,
        "datapoint_entity": datapoint_entity_rels,
    }

    return _mapped_result(
        data,
        "pdf-extraction",
        sources=sources,
        entities=entities,
        facts=facts,
        claims=claims,
        chunks=chunk_nodes,
        financial_datapoints=financial_datapoints,
        fiscal_periods=fiscal_periods,
        relations=relations,
    )


def map_finance_full(data: dict[str, Any]) -> dict[str, Any]:
    """Map finance-full data to graph-queue components.

    Parameters
    ----------
    data : dict[str, Any]
        Input data with ``sources[]`` and ``claims[]``, ``session_id``.

    Returns
    -------
    dict[str, Any]
        Mapped components preserving sources and claims with generated IDs.
    """
    input_sources = data.get("sources", [])
    input_claims = data.get("claims", [])
    sources: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []

    for source in input_sources:
        url = source.get("url", "")
        sources.append(
            _make_source(
                url,
                title=source.get("title", ""),
                published=source.get("published", ""),
            )
        )

    for claim in input_claims:
        content = claim.get("content", "")
        claims.append(
            {
                "claim_id": generate_claim_id(content),
                "content": content,
                "source_url": claim.get("source_url", ""),
                "category": claim.get("category", ""),
            }
        )

    return _mapped_result(data, "finance-full", sources=sources, claims=claims)


# ---------------------------------------------------------------------------
# Command → Mapper dispatch
# ---------------------------------------------------------------------------

COMMAND_MAPPERS: dict[str, MapperFn] = {
    "finance-news-workflow": map_finance_news,
    "ai-research-collect": map_ai_research,
    "generate-market-report": map_market_report,
    "asset-management": map_asset_management,
    "reddit-finance-topics": map_reddit_topics,
    "finance-full": map_finance_full,
    "pdf-extraction": map_pdf_extraction,
}
"""Dispatch table mapping command names to their mapper functions."""

COMMANDS = list(COMMAND_MAPPERS.keys())


# ---------------------------------------------------------------------------
# Auto-cleanup
# ---------------------------------------------------------------------------


def cleanup_old_files(directory: Path, *, max_age_days: int = 7) -> int:
    """Delete queue files older than *max_age_days* in *directory*.

    Parameters
    ----------
    directory : Path
        Directory to scan for old files.
    max_age_days : int
        Maximum age in days.  Files older than this are deleted.

    Returns
    -------
    int
        Number of files deleted.
    """
    if not directory.exists():
        logger.debug("Cleanup skipped: directory does not exist: %s", directory)
        return 0

    cutoff = time.time() - (max_age_days * 24 * 3600)
    deleted = 0

    for file_path in directory.iterdir():
        if not file_path.is_file():
            continue
        try:
            mtime = file_path.stat().st_mtime
            if mtime < cutoff:
                file_path.unlink()
                logger.info("Deleted old queue file: %s", file_path)
                deleted += 1
        except OSError as exc:
            logger.warning("Failed to delete %s: %s", file_path, exc)

    logger.info("Cleanup complete: %d file(s) deleted from %s", deleted, directory)
    return deleted


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Parameters
    ----------
    args : list[str] | None
        Command-line arguments.  If ``None``, uses ``sys.argv``.

    Returns
    -------
    argparse.Namespace
        Parsed arguments with ``command``, ``input``, and ``cleanup``.
    """
    parser = argparse.ArgumentParser(
        description="Emit graph-queue JSON from command outputs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--command",
        type=str,
        required=True,
        choices=COMMANDS,
        help="Source command name",
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Input file or directory path",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        default=False,
        help="Delete queue files older than 7 days",
    )

    return parser.parse_args(args)


# ---------------------------------------------------------------------------
# Main execution
# ---------------------------------------------------------------------------


def _load_and_parse(command: str, input_path: Path) -> dict[str, Any] | None:
    """Load input JSON and map it through the appropriate command mapper.

    Parameters
    ----------
    command : str
        Source command name (one of :data:`COMMANDS`).
    input_path : Path
        Path to the input JSON file.

    Returns
    -------
    dict[str, Any] | None
        Mapped data, or ``None`` on failure (error already logged).
    """
    if not input_path.exists():
        logger.error("Input path does not exist: %s", input_path)
        print(f"Error: Input path does not exist: {input_path}", file=sys.stderr)
        return None

    try:
        with input_path.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON in %s: %s", input_path, exc)
        print(f"Error: Invalid JSON in {input_path}: {exc}", file=sys.stderr)
        return None

    mapper = COMMAND_MAPPERS.get(command)
    if mapper is None:
        logger.error("Unknown command: %s", command)
        print(f"Error: Unknown command: {command}", file=sys.stderr)
        return None

    logger.info("Mapping data for command: %s", command)
    return mapper(data)


def _build_queue_doc(command: str, mapped: dict[str, Any]) -> dict[str, Any]:
    """Build the graph-queue document from mapped data.

    Parameters
    ----------
    command : str
        Source command name.
    mapped : dict[str, Any]
        Output from a mapper function.

    Returns
    -------
    dict[str, Any]
        Complete graph-queue document ready for serialisation.
    """
    queue_id = generate_queue_id()
    now = datetime.now(timezone.utc)

    return {
        "schema_version": SCHEMA_VERSION,
        "queue_id": queue_id,
        "created_at": now.isoformat(),
        "command_source": command,
        "session_id": mapped.get("session_id", ""),
        "batch_label": mapped.get("batch_label", ""),
        "sources": mapped.get("sources", []),
        "topics": mapped.get("topics", []),
        "claims": mapped.get("claims", []),
        "facts": mapped.get("facts", []),
        "entities": mapped.get("entities", []),
        "chunks": mapped.get("chunks", []),
        "financial_datapoints": mapped.get("financial_datapoints", []),
        "fiscal_periods": mapped.get("fiscal_periods", []),
        "relations": mapped.get("relations", {}),
    }


def _write_output(
    queue_doc: dict[str, Any],
    command: str,
    output_base: Path,
    *,
    cleanup: bool = False,
) -> Path:
    """Write the queue document to disk.

    Parameters
    ----------
    queue_doc : dict[str, Any]
        Graph-queue document to write.
    command : str
        Source command name (used as subdirectory).
    output_base : Path
        Base directory for output queue files.
    cleanup : bool
        If ``True``, delete files older than 7 days before writing.

    Returns
    -------
    Path
        Path to the written queue file.
    """
    output_dir = output_base / command
    output_dir.mkdir(parents=True, exist_ok=True)

    if cleanup:
        cleanup_old_files(output_dir, max_age_days=DEFAULT_MAX_AGE_DAYS)

    output_file = output_dir / f"{queue_doc['queue_id']}.json"
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(queue_doc, f, ensure_ascii=False, indent=2)

    logger.info("Queue file written: %s", output_file)
    return output_file


def run(
    *,
    command: str,
    input_path: Path,
    output_base: Path = DEFAULT_OUTPUT_BASE,
    cleanup: bool = False,
) -> int:
    """Execute the graph-queue emission pipeline.

    Parameters
    ----------
    command : str
        Source command name (one of :data:`COMMANDS`).
    input_path : Path
        Path to the input JSON file.
    output_base : Path
        Base directory for output queue files.
    cleanup : bool
        If ``True``, delete files older than 7 days before writing.

    Returns
    -------
    int
        Exit code — ``0`` for success, ``1`` for failure.
    """
    mapped = _load_and_parse(command, input_path)
    if mapped is None:
        return 1

    queue_doc = _build_queue_doc(command, mapped)
    output_file = _write_output(queue_doc, command, output_base, cleanup=cleanup)

    print(f"Queue file: {output_file}")
    return 0


def main(args: list[str] | None = None) -> int:
    """Main entry point.

    Parameters
    ----------
    args : list[str] | None
        Command-line arguments.

    Returns
    -------
    int
        Exit code (0 for success).
    """
    parsed = parse_args(args)

    return run(
        command=parsed.command,
        input_path=Path(parsed.input),
        cleanup=parsed.cleanup,
    )


if __name__ == "__main__":
    sys.exit(main())
