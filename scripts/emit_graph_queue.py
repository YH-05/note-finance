#!/usr/bin/env python3
"""Emit graph-queue JSON from various command outputs.

Converts outputs from 8 different finance workflow commands into a
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
- pdf-extraction
- wealth-scrape (supports both JSON file and directory input)

Usage
-----
::

    python3 scripts/emit_graph_queue.py \\
        --command finance-news-workflow \\
        --input .tmp/news-batches/index.json

    python3 scripts/emit_graph_queue.py \\
        --command wealth-scrape \\
        --input data/scraped/wealth/

    python3 scripts/emit_graph_queue.py \\
        --command finance-news-workflow \\
        --input .tmp/news-batches/index.json \\
        --cleanup
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import secrets
import sys
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pdf_pipeline.services.id_generator import (
    generate_claim_id,
    generate_datapoint_id_from_fields,
    generate_entity_id,
    generate_fact_id,
    generate_source_id,
)

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

WEALTH_THEME_CONFIG_PATH = Path("data/config/wealth-management-themes.json")
"""Path to the wealth-management theme configuration file."""

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
# YAML Frontmatter Parsing
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
"""Regex to extract YAML frontmatter block (between ``---`` delimiters)."""

_KV_RE = re.compile(r"^(\w+):\s*(.*)$")
"""Regex to extract ``key: value`` pairs from frontmatter lines."""


def _parse_yaml_frontmatter(file_path: Path) -> dict[str, str] | None:
    """Parse YAML frontmatter from a Markdown file using regex only.

    Extracts key-value pairs from the YAML frontmatter block delimited
    by ``---``.  Supports both quoted (``key: 'value'``) and unquoted
    (``key: value``) formats.  Does **not** use PyYAML.

    Parameters
    ----------
    file_path : Path
        Path to the Markdown file to parse.

    Returns
    -------
    dict[str, str] | None
        A mapping of frontmatter keys to their string values, or ``None``
        if the file does not exist or has no frontmatter block.
    """
    if not file_path.exists():
        logger.warning("File not found: %s", file_path)
        return None

    text = file_path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.search(text)
    if match is None:
        logger.debug("No frontmatter found in %s", file_path)
        return None

    frontmatter_block = match.group(1)
    result: dict[str, str] = {}
    for line in frontmatter_block.splitlines():
        kv_match = _KV_RE.match(line.strip())
        if kv_match is None:
            continue
        key = kv_match.group(1)
        raw_value = kv_match.group(2).strip()
        # Strip surrounding single or double quotes
        if len(raw_value) >= 2 and (
            (raw_value[0] == "'" and raw_value[-1] == "'")
            or (raw_value[0] == '"' and raw_value[-1] == '"')
        ):
            raw_value = raw_value[1:-1]
        result[key] = raw_value

    return result


# ---------------------------------------------------------------------------
# ID Generation
# ---------------------------------------------------------------------------

# generate_source_id, generate_entity_id, generate_claim_id, generate_fact_id
# are imported from pdf_pipeline.services.id_generator.
# generate_datapoint_id_from_fields is also imported; see generate_datapoint_id below.


def generate_datapoint_id(source_hash: str, metric: str, period: str) -> str:
    """Generate a deterministic datapoint ID from source hash, metric, and period.

    Delegates to ``pdf_pipeline.services.id_generator.generate_datapoint_id_from_fields``.

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
    """
    return generate_datapoint_id_from_fields(source_hash, metric, period)


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


def generate_queue_id() -> str:
    """Generate a unique queue ID with timestamp and random suffix.

    Uses ``secrets.token_hex(4)`` to produce an 8-character random hex
    suffix (32-bit entropy / ~4 billion possibilities), which is
    substantially more collision-resistant than the previous SHA-256[:4]
    approach (16-bit / 65 536 possibilities).

    Returns
    -------
    str
        Queue ID in the format ``gq-{timestamp}-{rand8}``.
    """
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d%H%M%S")
    rand8 = secrets.token_hex(4)
    return f"gq-{timestamp}-{rand8}"


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


def _build_chunk_nodes(
    chunk: dict[str, Any],
    source_hash: str,
    source_id: str,
) -> tuple[dict[str, Any], str, list[dict[str, str]]]:
    """Build a Chunk node and its CONTAINS_CHUNK relation.

    Parameters
    ----------
    chunk : dict[str, Any]
        Raw chunk data from the extraction result.
    source_hash : str
        SHA-256 hash of the source document.
    source_id : str
        ID of the parent Source node.

    Returns
    -------
    tuple[dict[str, Any], str, list[dict[str, str]]]
        A 3-tuple of (chunk_node, chunk_id, contains_chunk_rels).
    """
    chunk_index = chunk.get("chunk_index", 0)
    chunk_id = generate_chunk_id(source_hash, chunk_index)

    chunk_node = {
        "chunk_id": chunk_id,
        "chunk_index": chunk_index,
        "section_title": chunk.get("section_title"),
        "content": chunk.get("content", ""),
    }

    contains_chunk_rel = {
        "from_id": source_id,
        "to_id": chunk_id,
        "type": "CONTAINS_CHUNK",
    }

    return chunk_node, chunk_id, [contains_chunk_rel]


def _build_entity_nodes(
    chunk: dict[str, Any],
    seen_entity_keys: set[str],
    entity_name_to_id: dict[str, str],
    entity_name_to_ticker: dict[str, str],
) -> list[dict[str, Any]]:
    """Build Entity nodes from a chunk, deduplicated by name+type.

    Mutates *seen_entity_keys*, *entity_name_to_id*, and
    *entity_name_to_ticker* in-place to maintain cross-chunk dedup state.

    Parameters
    ----------
    chunk : dict[str, Any]
        Raw chunk data containing ``entities[]``.
    seen_entity_keys : set[str]
        Already-seen entity keys (``name:type``).
    entity_name_to_id : dict[str, str]
        Name-to-ID lookup (populated in-place).
    entity_name_to_ticker : dict[str, str]
        Name-to-ticker lookup (populated in-place).

    Returns
    -------
    list[dict[str, Any]]
        Newly created Entity node dicts.
    """
    entities: list[dict[str, Any]] = []

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

    return entities


def _resolve_entity_rels(
    about_entities: list[str],
    from_id: str,
    rel_type: str,
    entity_name_to_id: dict[str, str],
) -> list[dict[str, str]]:
    """Resolve entity names to relation dicts.

    Parameters
    ----------
    about_entities : list[str]
        Entity names to resolve.
    from_id : str
        Source node ID for the relation.
    rel_type : str
        Relation type (e.g. ``RELATES_TO``, ``ABOUT``).
    entity_name_to_id : dict[str, str]
        Name-to-ID lookup.

    Returns
    -------
    list[dict[str, str]]
        Resolved relation dicts.
    """
    result: list[dict[str, str]] = []
    for name in about_entities:
        resolved_id = entity_name_to_id.get(name)
        if resolved_id:
            result.append({"from_id": from_id, "to_id": resolved_id, "type": rel_type})
    return result


def _build_fact_nodes(
    chunk: dict[str, Any],
    source_id: str,
    chunk_id: str,
    entity_name_to_id: dict[str, str],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    """Build Fact nodes and their relations from a chunk.

    Parameters
    ----------
    chunk : dict[str, Any]
        Raw chunk data containing ``facts[]``.
    source_id : str
        ID of the parent Source node.
    chunk_id : str
        ID of the parent Chunk node.
    entity_name_to_id : dict[str, str]
        Name-to-ID lookup for entity resolution.

    Returns
    -------
    tuple
        A 4-tuple of (facts, source_fact_rels, extracted_from_fact_rels,
        fact_entity_rels).
    """
    facts: list[dict[str, Any]] = []
    source_fact_rels: list[dict[str, str]] = []
    extracted_from_fact_rels: list[dict[str, str]] = []
    fact_entity_rels: list[dict[str, str]] = []

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
        extracted_from_fact_rels.append(
            {"from_id": fact_id, "to_id": chunk_id, "type": "EXTRACTED_FROM"}
        )
        fact_entity_rels.extend(
            _resolve_entity_rels(
                fact.get("about_entities", []),
                fact_id,
                "RELATES_TO",
                entity_name_to_id,
            )
        )

    return facts, source_fact_rels, extracted_from_fact_rels, fact_entity_rels


def _build_claim_nodes(
    chunk: dict[str, Any],
    source_id: str,
    chunk_id: str,
    entity_name_to_id: dict[str, str],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    """Build Claim nodes and their relations from a chunk.

    Parameters
    ----------
    chunk : dict[str, Any]
        Raw chunk data containing ``claims[]``.
    source_id : str
        ID of the parent Source node.
    chunk_id : str
        ID of the parent Chunk node.
    entity_name_to_id : dict[str, str]
        Name-to-ID lookup for entity resolution.

    Returns
    -------
    tuple
        A 4-tuple of (claims, source_claim_rels, extracted_from_claim_rels,
        claim_entity_rels).
    """
    claims: list[dict[str, Any]] = []
    source_claim_rels: list[dict[str, str]] = []
    extracted_from_claim_rels: list[dict[str, str]] = []
    claim_entity_rels: list[dict[str, str]] = []

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
        extracted_from_claim_rels.append(
            {"from_id": claim_id, "to_id": chunk_id, "type": "EXTRACTED_FROM"}
        )
        claim_entity_rels.extend(
            _resolve_entity_rels(
                claim.get("about_entities", []),
                claim_id,
                "ABOUT",
                entity_name_to_id,
            )
        )

    return claims, source_claim_rels, extracted_from_claim_rels, claim_entity_rels


def _build_datapoint_nodes(
    chunk: dict[str, Any],
    source_hash: str,
    source_id: str,
    entity_name_to_id: dict[str, str],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, str]],
    list[dict[str, str]],
    dict[int, str],
]:
    """Build FinancialDataPoint nodes and their relations from a chunk.

    Parameters
    ----------
    chunk : dict[str, Any]
        Raw chunk data containing ``financial_datapoints[]``.
    source_hash : str
        SHA-256 hash of the source document.
    source_id : str
        ID of the parent Source node.
    entity_name_to_id : dict[str, str]
        Name-to-ID lookup for entity resolution.

    Returns
    -------
    tuple
        A 4-tuple of (datapoints, has_datapoint_rels,
        datapoint_entity_rels, dp_id_map).
        *dp_id_map* maps datapoint index to its generated ID,
        allowing ``_derive_fiscal_periods`` to reuse IDs without
        recomputing SHA-256 hashes.
    """
    datapoints: list[dict[str, Any]] = []
    has_datapoint_rels: list[dict[str, str]] = []
    datapoint_entity_rels: list[dict[str, str]] = []
    dp_id_map: dict[int, str] = {}

    for idx, dp in enumerate(chunk.get("financial_datapoints", [])):
        metric_name = dp.get("metric_name", "")
        period_label = dp.get("period_label", "")
        dp_id = generate_datapoint_id(source_hash, metric_name, period_label)
        dp_id_map[idx] = dp_id

        datapoints.append(
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

        has_datapoint_rels.append(
            {"from_id": source_id, "to_id": dp_id, "type": "HAS_DATAPOINT"}
        )

        datapoint_entity_rels.extend(
            _resolve_entity_rels(
                dp.get("about_entities", []),
                dp_id,
                "RELATES_TO",
                entity_name_to_id,
            )
        )

    return datapoints, has_datapoint_rels, datapoint_entity_rels, dp_id_map


def _derive_fiscal_periods(
    chunk: dict[str, Any],
    entity_name_to_ticker: dict[str, str],
    seen_period_ids: set[str],
    dp_id_map: dict[int, str],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Derive FiscalPeriod nodes and FOR_PERIOD relations from datapoints.

    Mutates *seen_period_ids* in-place for cross-chunk dedup.

    Parameters
    ----------
    chunk : dict[str, Any]
        Raw chunk data containing ``financial_datapoints[]``.
    entity_name_to_ticker : dict[str, str]
        Name-to-ticker lookup for period ID construction.
    seen_period_ids : set[str]
        Already-seen period IDs for deduplication.
    dp_id_map : dict[int, str]
        Pre-computed datapoint index-to-ID mapping from
        ``_build_datapoint_nodes``, avoiding redundant SHA-256 hashing.

    Returns
    -------
    tuple
        A 2-tuple of (fiscal_periods, for_period_rels).
    """
    fiscal_periods: list[dict[str, Any]] = []
    for_period_rels: list[dict[str, str]] = []

    for idx, dp in enumerate(chunk.get("financial_datapoints", [])):
        period_label = dp.get("period_label", "")
        if not period_label:
            continue

        dp_id = dp_id_map[idx]

        about_entities = dp.get("about_entities", [])
        ticker = (
            entity_name_to_ticker.get(about_entities[0], "") if about_entities else ""
        )

        period_id = f"{ticker}_{period_label}" if ticker else period_label
        if period_id not in seen_period_ids:
            seen_period_ids.add(period_id)
            fiscal_periods.append(
                {
                    "period_id": period_id,
                    "period_type": _infer_period_type(period_label),
                    "period_label": period_label,
                }
            )

        for_period_rels.append(
            {"from_id": dp_id, "to_id": period_id, "type": "FOR_PERIOD"}
        )

    return fiscal_periods, for_period_rels


def _extend_rels(
    target: dict[str, list[dict[str, str]]],
    updates: dict[str, list[dict[str, str]]],
) -> None:
    """Merge relation lists from *updates* into *target* in-place.

    Parameters
    ----------
    target : dict[str, list[dict[str, str]]]
        Target relation accumulator.
    updates : dict[str, list[dict[str, str]]]
        New relation lists to append.
    """
    for key, values in updates.items():
        target[key].extend(values)


def _empty_rels() -> dict[str, list[dict[str, str]]]:
    """Return an empty relations dict with all 11 relation keys."""
    return {
        "source_fact": [],
        "source_claim": [],
        "fact_entity": [],
        "claim_entity": [],
        "contains_chunk": [],
        "extracted_from_fact": [],
        "extracted_from_claim": [],
        "has_datapoint": [],
        "for_period": [],
        "datapoint_entity": [],
        "tagged": [],
    }


def _process_chunk(
    chunk: dict[str, Any],
    source_hash: str,
    source_id: str,
    seen_entity_keys: set[str],
    entity_name_to_id: dict[str, str],
    entity_name_to_ticker: dict[str, str],
    seen_period_ids: set[str],
) -> dict[str, Any]:
    """Process a single chunk and return all node lists and relations.

    Parameters
    ----------
    chunk : dict[str, Any]
        Raw chunk data.
    source_hash : str
        SHA-256 hash of the source document.
    source_id : str
        ID of the parent Source node.
    seen_entity_keys : set[str]
        Cross-chunk entity dedup state (mutated in-place).
    entity_name_to_id : dict[str, str]
        Cross-chunk name-to-ID lookup (mutated in-place).
    entity_name_to_ticker : dict[str, str]
        Cross-chunk name-to-ticker lookup (mutated in-place).
    seen_period_ids : set[str]
        Cross-chunk period dedup state (mutated in-place).

    Returns
    -------
    dict[str, Any]
        Dict with keys ``chunks``, ``entities``, ``facts``, ``claims``,
        ``datapoints``, ``periods``, and ``rels``.
    """
    chunk_node, chunk_id, cc_rels = _build_chunk_nodes(chunk, source_hash, source_id)

    entities = _build_entity_nodes(
        chunk, seen_entity_keys, entity_name_to_id, entity_name_to_ticker
    )

    facts, sf, ef, fe = _build_fact_nodes(chunk, source_id, chunk_id, entity_name_to_id)
    claims, sc, ec, ce = _build_claim_nodes(
        chunk, source_id, chunk_id, entity_name_to_id
    )
    dps, hd, de, dp_id_map = _build_datapoint_nodes(
        chunk, source_hash, source_id, entity_name_to_id
    )
    periods, fp = _derive_fiscal_periods(
        chunk, entity_name_to_ticker, seen_period_ids, dp_id_map
    )

    rels: dict[str, list[dict[str, str]]] = {
        "contains_chunk": cc_rels,
        "source_fact": sf,
        "extracted_from_fact": ef,
        "fact_entity": fe,
        "source_claim": sc,
        "extracted_from_claim": ec,
        "claim_entity": ce,
        "has_datapoint": hd,
        "datapoint_entity": de,
        "for_period": fp,
    }

    return {
        "chunks": [chunk_node],
        "entities": entities,
        "facts": facts,
        "claims": claims,
        "datapoints": dps,
        "periods": periods,
        "rels": rels,
    }


_NODE_KEYS = ("entities", "facts", "claims", "chunks", "datapoints", "periods")
"""Keys shared between _process_chunk output and the node accumulator."""


def map_pdf_extraction(data: dict[str, Any]) -> dict[str, Any]:
    """Map pdf-extraction to graph-queue via per-chunk helper delegation.

    Parameters
    ----------
    data : dict[str, Any]
        Input with ``source_hash``, ``chunks[]``.

    Returns
    -------
    dict[str, Any]
        Graph-queue components (nodes + 11 relation types).
    """
    source_hash = data.get("source_hash", "")
    source_id = generate_source_id(f"pdf:{source_hash}")
    sources = [_make_source(f"pdf:{source_hash}", source_type="pdf")]

    seen_entities: set[str] = set()
    seen_periods: set[str] = set()
    name_to_id: dict[str, str] = {}
    name_to_ticker: dict[str, str] = {}
    nodes: dict[str, list[Any]] = {k: [] for k in _NODE_KEYS}
    rels = _empty_rels()

    for chunk in data.get("chunks", []):
        r = _process_chunk(
            chunk,
            source_hash,
            source_id,
            seen_entities,
            name_to_id,
            name_to_ticker,
            seen_periods,
        )
        for k in _NODE_KEYS:
            nodes[k].extend(r[k])
        _extend_rels(rels, r["rels"])

    return _mapped_result(
        data,
        "pdf-extraction",
        sources=sources,
        entities=nodes["entities"],
        facts=nodes["facts"],
        claims=nodes["claims"],
        chunks=nodes["chunks"],
        financial_datapoints=nodes["datapoints"],
        fiscal_periods=nodes["periods"],
        relations=rels,
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
# Wealth-scrape backfill: directory scanning
# ---------------------------------------------------------------------------


def _load_wealth_themes(
    config_path: Path = WEALTH_THEME_CONFIG_PATH,
) -> dict[str, Any]:
    """Load wealth-management theme configuration.

    Parameters
    ----------
    config_path : Path
        Path to the theme configuration JSON file.

    Returns
    -------
    dict[str, Any]
        Theme configuration data, or empty dict on failure.
    """
    if not config_path.exists():
        logger.warning("Theme config not found: %s", config_path)
        return {}

    try:
        with config_path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to load theme config %s: %s", config_path, exc)
        return {}

    return data.get("themes", {})


def _match_domain_to_theme(
    domain: str, themes: dict[str, Any]
) -> tuple[str, str] | None:
    """Match a domain name to a wealth theme via ``target_sources``.

    Parameters
    ----------
    domain : str
        Domain directory name (e.g. ``"ofdollarsanddata.com"``).
    themes : dict[str, Any]
        Theme configuration from ``wealth-management-themes.json``.

    Returns
    -------
    tuple[str, str] | None
        ``(theme_key, theme_name_en)`` if matched, otherwise ``None``.
    """
    # Strip TLD variations for fuzzy matching
    domain_base = domain.replace(".com", "").replace(".org", "").replace(".net", "")

    for theme_key, theme_data in themes.items():
        target_sources = theme_data.get("target_sources", [])
        for source in target_sources:
            if source in domain_base or domain_base in source:
                return (theme_key, theme_data.get("name_en", theme_key))

    return None


def _scan_wealth_directory(
    dir_path: Path,
    *,
    theme_config_path: Path = WEALTH_THEME_CONFIG_PATH,
) -> list[dict[str, Any]]:
    """Scan a wealth-scrape backfill directory for Markdown articles.

    Expects a directory structure of ``{domain}/*.md`` where each Markdown
    file has YAML frontmatter with ``url``, ``title``, ``published``, etc.

    Groups articles by domain and returns one mapped dict per domain,
    enriched with theme information from ``wealth-management-themes.json``.

    Parameters
    ----------
    dir_path : Path
        Root directory to scan (e.g. ``data/scraped/wealth/``).
    theme_config_path : Path
        Path to the wealth-management theme configuration JSON.

    Returns
    -------
    list[dict[str, Any]]
        List of mapped dicts, one per domain.  Each dict follows the
        standard mapper result format (has ``sources``, ``topics``, etc.).
    """
    if not dir_path.is_dir():
        logger.error("Not a directory: %s", dir_path)
        return []

    themes = _load_wealth_themes(theme_config_path)
    results: list[dict[str, Any]] = []

    # Iterate over subdirectories (each = a domain)
    domain_dirs = sorted(
        [d for d in dir_path.iterdir() if d.is_dir()],
        key=lambda p: p.name,
    )

    if not domain_dirs:
        logger.warning("No domain subdirectories found in %s", dir_path)
        return []

    for domain_dir in domain_dirs:
        domain = domain_dir.name
        md_files = sorted(domain_dir.glob("*.md"))
        if not md_files:
            logger.debug("No .md files in %s", domain_dir)
            continue

        sources: list[dict[str, Any]] = []
        chunks: list[dict[str, Any]] = []

        for md_file in md_files:
            frontmatter = _parse_yaml_frontmatter(md_file)
            if frontmatter is None:
                logger.debug("Skipping file without frontmatter: %s", md_file)
                continue

            url = frontmatter.get("url", "")
            if not url:
                logger.debug("Skipping file without URL: %s", md_file)
                continue

            sources.append(
                _make_source(
                    url,
                    title=frontmatter.get("title", ""),
                    published=frontmatter.get("published", frontmatter.get("date", "")),
                    domain=domain,
                    source_key=frontmatter.get("source", ""),
                )
            )

            # Read body text (after frontmatter) as a chunk
            text = md_file.read_text(encoding="utf-8")
            body_match = re.search(r"^---\n.*?\n---\n*(.*)", text, re.DOTALL)
            body = body_match.group(1).strip() if body_match else ""
            if body:
                source_id = generate_source_id(url)
                chunks.append(
                    {
                        "chunk_id": f"{source_id}:0",
                        "source_id": source_id,
                        "content": body,
                        "index": 0,
                    }
                )

        if not sources:
            logger.debug("No valid articles found in %s", domain_dir)
            continue

        # Build topics from theme matching
        topics: list[dict[str, Any]] = []
        theme_match = _match_domain_to_theme(domain, themes)
        if theme_match:
            theme_key, theme_name = theme_match
            topics.append(
                {
                    "topic_id": generate_topic_id(theme_name, "wealth"),
                    "name": theme_name,
                    "category": "wealth",
                    "theme_key": theme_key,
                }
            )

        session_data: dict[str, Any] = {
            "session_id": f"wealth-backfill-{domain}",
        }
        mapped = _mapped_result(
            session_data,
            f"wealth-scrape:{domain}",
            sources=sources,
            topics=topics,
            chunks=chunks,
        )

        logger.info(
            "Scanned domain %s: %d sources, %d chunks, %d topics",
            domain,
            len(sources),
            len(chunks),
            len(topics),
        )
        results.append(mapped)

    logger.info(
        "Wealth directory scan complete: %d domain(s) with articles", len(results)
    )
    return results


def map_wealth_scrape(data: dict[str, Any]) -> dict[str, Any]:
    """Map wealth-scrape session JSON to graph-queue components.

    Handles both backfill and incremental mode session data.  The data
    structure mirrors ``map_asset_management`` with ``themes.{key}.articles[]``.

    Parameters
    ----------
    data : dict[str, Any]
        Input data with ``themes.{key}.articles[]``, ``session_id``.

    Returns
    -------
    dict[str, Any]
        Mapped components with ``sources[]`` and ``topics[]``.
    """
    themes = data.get("themes", {})
    sources: list[dict[str, Any]] = []
    topics: list[dict[str, Any]] = []

    for theme_key, theme_data in themes.items():
        name_en = theme_data.get("name_en", theme_key)

        topics.append(
            {
                "topic_id": generate_topic_id(name_en, "wealth"),
                "name": name_en,
                "category": "wealth",
                "theme_key": theme_key,
            }
        )

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
                        domain=article.get("domain", ""),
                    )
                )

    return _mapped_result(data, "wealth-scrape", sources=sources, topics=topics)


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
    "wealth-scrape": map_wealth_scrape,
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


def _load_and_parse(
    command: str, input_path: Path
) -> dict[str, Any] | list[dict[str, Any]] | None:
    """Load input data and map it through the appropriate command mapper.

    For most commands the input is a JSON file.  When ``command`` is
    ``"wealth-scrape"`` and *input_path* is a directory, the directory is
    scanned via :func:`_scan_wealth_directory` and a **list** of mapped
    dicts is returned (one per domain).

    Parameters
    ----------
    command : str
        Source command name (one of :data:`COMMANDS`).
    input_path : Path
        Path to the input JSON file **or** directory (wealth-scrape only).

    Returns
    -------
    dict[str, Any] | list[dict[str, Any]] | None
        Mapped data (single dict or list of dicts), or ``None`` on failure.
    """
    if not input_path.exists():
        logger.error("Input path does not exist: %s", input_path)
        print(f"Error: Input path does not exist: {input_path}", file=sys.stderr)
        return None

    # Directory input: wealth-scrape backfill scanning
    if command == "wealth-scrape" and input_path.is_dir():
        logger.info("Scanning wealth directory: %s", input_path)
        results = _scan_wealth_directory(input_path)
        if not results:
            logger.error("No articles found in directory: %s", input_path)
            print(
                f"Error: No articles found in directory: {input_path}",
                file=sys.stderr,
            )
            return None
        return results

    # File input: standard JSON loading
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

    When ``_load_and_parse`` returns a list (e.g. wealth-scrape directory
    input), each element is processed separately through
    ``_build_queue_doc`` and ``_write_output``, producing one queue file
    per domain.

    Parameters
    ----------
    command : str
        Source command name (one of :data:`COMMANDS`).
    input_path : Path
        Path to the input JSON file or directory.
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

    # List input: process each element separately (e.g. directory scan)
    if isinstance(mapped, list):
        output_files: list[Path] = []
        for item in mapped:
            queue_doc = _build_queue_doc(command, item)
            output_file = _write_output(
                queue_doc, command, output_base, cleanup=cleanup
            )
            output_files.append(output_file)
            # Only run cleanup on the first iteration
            cleanup = False

        for f in output_files:
            print(f"Queue file: {f}")
        logger.info("Generated %d queue file(s)", len(output_files))
        return 0

    # Single dict input: standard processing
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
