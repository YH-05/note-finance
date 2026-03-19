#!/usr/bin/env python3
"""Emit graph-queue JSON from various command outputs.

Converts outputs from 10 different finance workflow commands into a
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
- topic-discovery
- web-research

Usage
-----
::

    python3 scripts/emit_graph_queue.py \\
        --command finance-news-workflow \\
        --input .tmp/news-batches/index.json

    python3 scripts/emit_graph_queue.py \\
        --command wealth-scrape \\
        --input /Volumes/personal_folder/scraped/wealth/

    python3 scripts/emit_graph_queue.py \\
        --command finance-news-workflow \\
        --input .tmp/news-batches/index.json \\
        --cleanup
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import logging
import os
import re
import secrets
import sys
import time
import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

from authority_classifier import classify_authority

from pdf_pipeline.services.id_generator import (
    generate_author_id,
    generate_claim_id,
    generate_datapoint_id_from_fields,
    generate_entity_id,
    generate_fact_id,
    generate_question_id,
    generate_source_id,
    generate_stance_id,
)

type MapperFn = Callable[[dict[str, Any]], dict[str, Any]]


class StanceBuildResult(TypedDict):
    """Result from _build_stance_nodes."""

    stances: list[dict[str, Any]]
    authors: list[dict[str, Any]]
    holds_stance: list[dict[str, str]]
    on_entity: list[dict[str, str]]
    based_on: list[dict[str, str]]


@dataclass
class ChunkProcessingContext:
    """Cross-chunk shared state for _process_chunk."""

    seen_entity_keys: set[str] = field(default_factory=set)
    entity_name_to_id: dict[str, str] = field(default_factory=dict)
    entity_name_to_ticker: dict[str, str] = field(default_factory=dict)
    seen_period_ids: set[str] = field(default_factory=set)
    seen_author_keys: set[str] = field(default_factory=set)
    author_name_to_id: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

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

SCHEMA_VERSION = "2.2"
"""Graph-queue schema version (v2.2: entity_key/topic_key support)."""

WEALTH_THEME_CONFIG_PATH = Path("data/config/wealth-management-themes.json")
"""Path to the wealth-management theme configuration file."""

DIRECTORY_COMMANDS: frozenset[str] = frozenset({"wealth-scrape"})
"""Commands that accept directory input in addition to JSON files."""

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

_BODY_RE = re.compile(r"^---\n.*?\n---\n*(.*)", re.DOTALL)
"""Regex to extract body text after YAML frontmatter."""


def _parse_frontmatter_from_text(text: str) -> dict[str, str] | None:
    """Parse YAML frontmatter from raw text using regex only.

    Extracts key-value pairs from the YAML frontmatter block delimited
    by ``---``.  Supports both quoted (``key: 'value'``) and unquoted
    (``key: value``) formats.  Does **not** use PyYAML.

    Parameters
    ----------
    text : str
        Raw Markdown text to parse.

    Returns
    -------
    dict[str, str] | None
        A mapping of frontmatter keys to their string values, or ``None``
        if no frontmatter block is found.
    """
    match = _FRONTMATTER_RE.search(text)
    if match is None:
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


def _parse_yaml_frontmatter(file_path: Path) -> dict[str, str] | None:
    """Parse YAML frontmatter from a Markdown file using regex only.

    Thin wrapper around :func:`_parse_frontmatter_from_text` that reads
    the file from disk first.

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
    result = _parse_frontmatter_from_text(text)
    if result is None:
        logger.debug("No frontmatter found in %s", file_path)
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
# Metric alias index (Phase 2 Step B-2)
# ---------------------------------------------------------------------------

_METRIC_MASTER_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "config" / "metric_master.json"
)


@functools.lru_cache(maxsize=1)
def _load_metric_alias_index() -> dict[str, str]:
    """Build a case-insensitive alias → metric_id lookup from metric_master.json.

    Returns
    -------
    dict[str, str]
        Mapping from lowercased alias to metric_id.
        Returns an empty dict if the file is missing or malformed.
    """
    if not _METRIC_MASTER_PATH.exists():
        logger.warning("metric_master.json not found: %s", _METRIC_MASTER_PATH)
        return {}

    try:
        with _METRIC_MASTER_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load metric_master.json: %s", exc)
        return {}

    index: dict[str, str] = {}
    for metric in data.get("metrics", []):
        metric_id = metric.get("metric_id", "")
        if not metric_id:
            continue
        # canonical_name as key
        canonical = metric.get("canonical_name", "")
        if canonical:
            index[canonical.lower()] = metric_id
        # display_name as key
        display = metric.get("display_name", "")
        if display:
            index[display.lower()] = metric_id
        # all aliases as keys
        for alias in metric.get("aliases", []):
            if alias:
                index[alias.lower()] = metric_id

    logger.debug("Loaded metric alias index: %d entries", len(index))
    return index


def resolve_metric_id(metric_name: str) -> str | None:
    """Resolve a metric_name to its canonical metric_id.

    Parameters
    ----------
    metric_name : str
        Raw metric name from FinancialDataPoint (e.g. ``"Total Revenue"``).

    Returns
    -------
    str | None
        Canonical metric_id (e.g. ``"metric-revenue"``) or ``None`` if
        no match is found.
    """
    if not metric_name:
        return None
    return _load_metric_alias_index().get(metric_name.lower())


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


# Regex patterns for period label parsing
_FY_RE = re.compile(r"^FY\s*(\d{4}|\d{2})$", re.IGNORECASE)
"""Match annual period labels like ``FY2025`` or ``FY25``."""

_Q_RE = re.compile(r"^(\d)[Qq]\s*(\d{4}|\d{2})$")
"""Match quarterly period labels like ``3Q25`` or ``4Q2025``."""

_H_RE = re.compile(r"^(\d)[Hh]\s*(\d{4}|\d{2})$")
"""Match half-year period labels like ``1H26`` or ``2H2025``."""


def _normalise_year(raw: str) -> int:
    """Normalise a 2-digit or 4-digit year string to a 4-digit integer.

    Parameters
    ----------
    raw : str
        Year string (e.g. ``'25'`` or ``'2025'``).

    Returns
    -------
    int
        Four-digit year.
    """
    year = int(raw)
    if year < 100:
        year += 2000
    return year


def _period_sort_key(label: str) -> tuple[int, int]:
    """Compute a sortable key from a fiscal period label.

    Used to order FiscalPeriod nodes chronologically within a
    ticker + period_type group.

    Parameters
    ----------
    label : str
        Period label (e.g., ``'FY2025'``, ``'3Q25'``, ``'1H26'``).

    Returns
    -------
    tuple[int, int]
        ``(year, sub_index)`` where *sub_index* is 0 for annual,
        1-4 for quarterly, 1-2 for half-year.  Unrecognised labels
        are placed at ``(9999, 0)`` with a warning.

    Examples
    --------
    >>> _period_sort_key("FY2025")
    (2025, 0)
    >>> _period_sort_key("3Q25")
    (2025, 3)
    >>> _period_sort_key("1H26")
    (2026, 1)
    """
    stripped = label.strip()

    m = _FY_RE.match(stripped)
    if m:
        return (_normalise_year(m.group(1)), 0)

    m = _Q_RE.match(stripped)
    if m:
        return (_normalise_year(m.group(2)), int(m.group(1)))

    m = _H_RE.match(stripped)
    if m:
        return (_normalise_year(m.group(2)), int(m.group(1)))

    logger.warning("Unrecognised period label, placing at end: %s", label)
    return (9999, 0)


_GAP_MONTHS: dict[str, int] = {
    "annual": 12,
    "quarterly": 3,
    "half_year": 6,
}
"""Default gap_months by period_type."""


def _extract_ticker_from_period_id(period_id: str) -> str:
    """Extract the ticker prefix from a period_id.

    Parameters
    ----------
    period_id : str
        Period ID in ``{ticker}_{period_label}`` or ``{period_label}`` format.

    Returns
    -------
    str
        Ticker prefix, or empty string if no prefix found.
    """
    parts = period_id.rsplit("_", 1)
    return parts[0] if len(parts) > 1 else ""


def _parse_date_safe(raw: str | None) -> date:
    """Parse an ISO 8601 date string safely for sorting.

    Parameters
    ----------
    raw : str | None
        Date string in ``YYYY-MM-DD`` format, or ``None``.

    Returns
    -------
    date
        Parsed date, or ``date.min`` for unparseable/missing values.
    """
    if not raw:
        return date.min
    try:
        return date.fromisoformat(raw)
    except (ValueError, TypeError):
        logger.warning("Unparseable as_of_date for sorting: %s", raw)
        return date.min


def _build_content_id_map(
    facts: list[dict[str, Any]],
    claims: list[dict[str, Any]],
) -> dict[tuple[str, str], str]:
    """Build a content-to-ID mapping from facts and claims.

    Parameters
    ----------
    facts : list[dict[str, Any]]
        Fact node dicts with ``fact_id`` and ``content``.
    claims : list[dict[str, Any]]
        Claim node dicts with ``claim_id`` and ``content``.

    Returns
    -------
    dict[tuple[str, str], str]
        Mapping from ``(type, content)`` to node ID.
    """
    content_to_id: dict[tuple[str, str], str] = {}
    for fact_item in facts:
        content_to_id[("fact", fact_item["content"])] = fact_item["fact_id"]
    for claim_item in claims:
        content_to_id[("claim", claim_item["content"])] = claim_item["claim_id"]
    return content_to_id


def _build_next_period_chain(
    fiscal_periods: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build NEXT_PERIOD relations linking consecutive FiscalPeriod nodes.

    Groups periods by ticker (derived from ``period_id`` prefix) and
    ``period_type``, sorts each group chronologically using
    :func:`_period_sort_key`, and emits one NEXT_PERIOD edge per
    consecutive pair.

    Parameters
    ----------
    fiscal_periods : list[dict[str, Any]]
        FiscalPeriod node dicts with ``period_id``, ``period_type``,
        ``period_label``.

    Returns
    -------
    list[dict[str, Any]]
        NEXT_PERIOD relation dicts with ``from_id``, ``to_id``,
        ``type``, and ``gap_months``.
    """
    # Group by (ticker_prefix, period_type)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for fp in fiscal_periods:
        period_id = fp.get("period_id", "")
        period_type = fp.get("period_type", "")
        ticker_prefix = _extract_ticker_from_period_id(period_id)
        groups[(ticker_prefix, period_type)].append(fp)

    rels: list[dict[str, Any]] = []
    for (_ticker, p_type), group in groups.items():
        sorted_group = sorted(
            group, key=lambda fp: _period_sort_key(fp.get("period_label", ""))
        )
        gap = _GAP_MONTHS.get(p_type, 12)
        for i in range(1, len(sorted_group)):
            rels.append(
                {
                    "from_id": sorted_group[i - 1]["period_id"],
                    "to_id": sorted_group[i]["period_id"],
                    "type": "NEXT_PERIOD",
                    "gap_months": gap,
                }
            )

    return rels


def _compute_trend(prev_val: float, curr_val: float) -> tuple[float, str]:
    """Compute change percentage and direction between two values.

    Returns
    -------
    tuple[float, str]
        ``(change_pct, direction)`` where direction is one of
        ``"up"``, ``"down"``, or ``"flat"``.
    """
    if prev_val == 0:
        change_pct = 0.0
    else:
        change_pct = round((curr_val - prev_val) / abs(prev_val) * 100, 2)

    if change_pct > 1:
        direction = "up"
    elif change_pct < -1:
        direction = "down"
    else:
        direction = "flat"
    return change_pct, direction


def _build_trend_edges(
    financial_datapoints: list[dict[str, Any]],
    fiscal_periods: list[dict[str, Any]],
    for_period_rels: list[dict[str, str]],
    *,
    measures_linked_dp_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Build TREND relations between consecutive FinancialDataPoint nodes.

    Groups datapoints by ``(entity, metric_key)`` where *metric_key* is
    resolved via :func:`resolve_metric_id` when available, falling back
    to the raw ``metric_name``.  Within each group, datapoints are sorted
    by period chronology and a TREND edge is emitted per consecutive pair.

    Parameters
    ----------
    financial_datapoints : list[dict[str, Any]]
        FinancialDataPoint node dicts with ``datapoint_id``,
        ``metric_name``, ``value``, ``period_label``.
    fiscal_periods : list[dict[str, Any]]
        FiscalPeriod node dicts (used to look up period_id → period_label).
    for_period_rels : list[dict[str, str]]
        FOR_PERIOD relation dicts mapping ``from_id`` (datapoint) to
        ``to_id`` (period).
    measures_linked_dp_ids : set[str] | None
        If provided (research-neo4j), only datapoints whose ID is in this
        set are eligible for TREND.  ``None`` (article-neo4j) means all
        datapoints are eligible.

    Returns
    -------
    list[dict[str, Any]]
        TREND relation dicts with ``from_id``, ``to_id``, ``type``,
        ``change_pct``, ``direction``, and ``metric_id``.
    """
    # Build datapoint_id → period_id mapping
    dp_to_period: dict[str, str] = {}
    for rel in for_period_rels:
        dp_to_period[rel["from_id"]] = rel["to_id"]

    # Build period_id → period_label mapping
    period_to_label: dict[str, str] = {}
    for fp in fiscal_periods:
        period_to_label[fp["period_id"]] = fp.get("period_label", "")

    # Group by (ticker_prefix, metric_key, source_hash) — Source-scoped TREND
    # Each sell-side report's projections form a coherent time series;
    # cross-report comparison is invalid due to unit/methodology differences.
    groups: dict[tuple[str, str, str], list[tuple[dict[str, Any], str | None]]] = (
        defaultdict(list)
    )
    for dp in financial_datapoints:
        dp_id = dp["datapoint_id"]

        # Filter by MEASURES link if set is provided (Step B-4)
        if measures_linked_dp_ids is not None and dp_id not in measures_linked_dp_ids:
            continue

        period_id = dp_to_period.get(dp_id, "")
        ticker_prefix = _extract_ticker_from_period_id(period_id)
        metric_name = dp.get("metric_name", "")
        metric_id = resolve_metric_id(metric_name)
        # Use metric_id for grouping when available, fallback to metric_name
        metric_key = metric_id or metric_name
        src_hash = dp.get("source_hash", "")
        groups[(ticker_prefix, metric_key, src_hash)].append((dp, metric_id))

    rels: list[dict[str, Any]] = []
    for (_ticker, _metric_key, _src), group in groups.items():
        # Sort by period chronology
        sorted_group = sorted(
            group,
            key=lambda item: _period_sort_key(
                period_to_label.get(dp_to_period.get(item[0]["datapoint_id"], ""), "")
            ),
        )
        for i in range(1, len(sorted_group)):
            prev_dp, prev_mid = sorted_group[i - 1]
            curr_dp, curr_mid = sorted_group[i]
            prev_val = prev_dp.get("value")
            curr_val = curr_dp.get("value")

            if prev_val is None or curr_val is None:
                continue

            change_pct, direction = _compute_trend(prev_val, curr_val)

            # Use the metric_id from either dp (should be the same within group)
            resolved_mid = curr_mid or prev_mid

            rel_dict: dict[str, Any] = {
                "from_id": prev_dp["datapoint_id"],
                "to_id": curr_dp["datapoint_id"],
                "type": "TREND",
                "change_pct": change_pct,
                "direction": direction,
            }
            if resolved_mid:
                rel_dict["metric_id"] = resolved_mid

            rels.append(rel_dict)

    return rels


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
    source = {
        "source_id": generate_source_id(url),
        "url": url,
        "title": title,
        "published": published,
        **extra,
    }
    if "authority_level" not in source:
        source["authority_level"] = classify_authority(
            source_type=source.get("source_type", ""),
            url=url,
        )
    return source


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
    authors: list[dict[str, Any]] | None = None,
    stances: list[dict[str, Any]] | None = None,
    questions: list[dict[str, Any]] | None = None,
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
    financial_datapoints, fiscal_periods, authors, stances,
    questions : list[dict] | None
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
        "authors": authors or [],
        "stances": stances or [],
        "questions": questions or [],
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
                "entity_key": f"{company_name}::company",
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
                "topic_key": f"{name_ja}::asset-management",
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
                "topic_key": f"{name}::reddit",
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
        entity_key = f"{name}::{entity_type}"
        if entity_key not in seen_entity_keys:
            seen_entity_keys.add(entity_key)
            eid = generate_entity_id(name, entity_type)
            entities.append(
                {
                    "entity_id": eid,
                    "name": name,
                    "entity_type": entity_type,
                    "ticker": entity.get("ticker"),
                    "entity_key": f"{name}::{entity_type}",
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
                "magnitude": claim.get("magnitude"),
                "target_price": claim.get("target_price"),
                "rating": claim.get("rating"),
                "time_horizon": claim.get("time_horizon"),
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
                "source_hash": source_hash,
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


def _build_stance_nodes(
    chunk: dict[str, Any],
    entity_name_to_id: dict[str, str],
    seen_author_keys: set[str],
    author_name_to_id: dict[str, str],
) -> StanceBuildResult:
    """Build Stance and Author nodes with HOLDS_STANCE, ON_ENTITY, BASED_ON relations.

    Authors are deduplicated via *seen_author_keys* (``name:type``).

    Parameters
    ----------
    chunk : dict[str, Any]
        Raw chunk data containing ``stances[]``.
    entity_name_to_id : dict[str, str]
        Name-to-ID lookup for entity resolution.
    seen_author_keys : set[str]
        Already-seen author keys for deduplication (mutated in-place).
    author_name_to_id : dict[str, str]
        Author name-to-ID lookup (mutated in-place).

    Returns
    -------
    tuple
        A 5-tuple of (stances, authors, holds_stance_rels,
        on_entity_rels, based_on_rels).
    """
    stances: list[dict[str, Any]] = []
    authors: list[dict[str, Any]] = []
    holds_stance_rels: list[dict[str, str]] = []
    on_entity_rels: list[dict[str, str]] = []
    based_on_rels: list[dict[str, str]] = []

    for stance in chunk.get("stances", []):
        author_name = stance.get("author_name", "")
        author_type = stance.get("author_type", "")
        entity_name = stance.get("entity_name", "")
        as_of_date = stance.get("as_of_date", "")

        if not author_name or not entity_name:
            continue

        # Generate IDs
        stance_id = generate_stance_id(author_name, entity_name, as_of_date or "")
        author_id = generate_author_id(author_name, author_type)

        # Deduplicate Author
        author_key = f"{author_name}:{author_type}"
        if author_key not in seen_author_keys:
            seen_author_keys.add(author_key)
            authors.append(
                {
                    "author_id": author_id,
                    "name": author_name,
                    "author_type": author_type,
                    "organization": stance.get("organization"),
                }
            )
        author_name_to_id[author_name] = author_id

        # Build Stance node
        stances.append(
            {
                "stance_id": stance_id,
                "rating": stance.get("rating"),
                "sentiment": stance.get("sentiment"),
                "target_price": stance.get("target_price"),
                "target_price_currency": stance.get("target_price_currency"),
                "as_of_date": as_of_date,
                "author_name": author_name,
                "entity_name": entity_name,
            }
        )

        # HOLDS_STANCE: Author -> Stance
        holds_stance_rels.append(
            {"from_id": author_id, "to_id": stance_id, "type": "HOLDS_STANCE"}
        )

        # ON_ENTITY: Stance -> Entity
        entity_id = entity_name_to_id.get(entity_name)
        if entity_id:
            on_entity_rels.append(
                {"from_id": stance_id, "to_id": entity_id, "type": "ON_ENTITY"}
            )

        # BASED_ON: Stance -> Claim (matched by content)
        for claim_content in stance.get("based_on_claims", []):
            claim_id = generate_claim_id(claim_content)
            based_on_rels.append(
                {
                    "from_id": stance_id,
                    "to_id": claim_id,
                    "type": "BASED_ON",
                    "role": "supporting",
                }
            )

    return StanceBuildResult(
        stances=stances,
        authors=authors,
        holds_stance=holds_stance_rels,
        on_entity=on_entity_rels,
        based_on=based_on_rels,
    )


def _build_supersedes_chain(
    stances: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Build SUPERSEDES relations for stances sharing the same (author, entity).

    Within each (author_name, entity_name) group, stances are sorted by
    ``as_of_date`` ascending.  Each newer stance SUPERSEDES the previous one.

    Parameters
    ----------
    stances : list[dict[str, Any]]
        All Stance node dicts accumulated across chunks.

    Returns
    -------
    list[dict[str, str]]
        SUPERSEDES relation dicts (newer -> older).
    """
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for stance in stances:
        key = (stance.get("author_name", ""), stance.get("entity_name", ""))
        groups[key].append(stance)

    supersedes_rels: list[dict[str, str]] = []
    for _key, group in groups.items():
        sorted_group = sorted(
            group, key=lambda s: _parse_date_safe(s.get("as_of_date"))
        )
        for i in range(1, len(sorted_group)):
            newer = sorted_group[i]
            older = sorted_group[i - 1]
            supersedes_rels.append(
                {
                    "from_id": newer["stance_id"],
                    "to_id": older["stance_id"],
                    "type": "SUPERSEDES",
                    "superseded_at": newer.get("as_of_date", ""),
                }
            )

    return supersedes_rels


def _build_authored_by_rels(
    source_id: str,
    publisher: str,
    seen_author_keys: set[str],
    author_name_to_id: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Build Author node and AUTHORED_BY relation from Source.publisher.

    If the publisher is already known (via LLM-extracted stances), the
    existing author_id is reused and no duplicate Author node is emitted.

    Parameters
    ----------
    source_id : str
        ID of the Source node.
    publisher : str
        Publisher/issuer name (e.g. ``"HSBC"``, ``"BofA Securities"``).
    seen_author_keys : set[str]
        Already-seen author keys for deduplication (mutated in-place).
    author_name_to_id : dict[str, str]
        Author name-to-ID lookup (mutated in-place).

    Returns
    -------
    tuple[list[dict[str, Any]], list[dict[str, str]]]
        (new_authors, authored_by_rels).
    """
    if not publisher:
        return [], []

    author_type = "sell_side"
    author_key = f"{publisher}:{author_type}"
    author_id = author_name_to_id.get(publisher)

    new_authors: list[dict[str, Any]] = []
    if author_id is None:
        author_id = generate_author_id(publisher, author_type)
        author_name_to_id[publisher] = author_id

    if author_key not in seen_author_keys:
        seen_author_keys.add(author_key)
        new_authors.append(
            {
                "author_id": author_id,
                "name": publisher,
                "author_type": author_type,
                "organization": publisher,
            }
        )

    authored_by_rels = [
        {
            "from_id": source_id,
            "to_id": author_id,
            "type": "AUTHORED_BY",
        }
    ]

    return new_authors, authored_by_rels


_LABEL_MAP: dict[str, str] = {
    "fact": "Fact",
    "claim": "Claim",
    "datapoint": "FinancialDataPoint",
}
"""Map from LLM-output type names to Neo4j node labels."""


def _build_causal_links(
    chunk: dict[str, Any],
    facts: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    datapoints: list[dict[str, Any]],
    source_id: str,
) -> list[dict[str, str]]:
    """Build CAUSES relation dicts from causal_links in a chunk.

    Resolves ``from_content``/``to_content`` to node IDs using a
    content-to-ID mapping built from the chunk's own facts, claims,
    and financial data points.  Unresolved references are logged as
    warnings and skipped.

    Parameters
    ----------
    chunk : dict[str, Any]
        Raw chunk data containing ``causal_links[]``.
    facts : list[dict[str, Any]]
        Fact node dicts built from this chunk (with ``fact_id``, ``content``).
    claims : list[dict[str, Any]]
        Claim node dicts built from this chunk (with ``claim_id``, ``content``).
    datapoints : list[dict[str, Any]]
        DataPoint node dicts built from this chunk (with ``datapoint_id``,
        ``metric_name``).
    source_id : str
        ID of the parent Source node.

    Returns
    -------
    list[dict[str, str]]
        CAUSES relation dicts with ``from_id``, ``to_id``, ``type``,
        ``mechanism``, ``confidence``, ``source_id``, ``from_label``,
        ``to_label``.
    """
    causal_links = chunk.get("causal_links", [])
    if not causal_links:
        return []

    # Build content-to-ID mapping scoped to this chunk
    content_to_id = _build_content_id_map(facts, claims)
    for dp_item in datapoints:
        content_to_id[("datapoint", dp_item["metric_name"])] = dp_item["datapoint_id"]

    causes_rels: list[dict[str, str]] = []
    for link in causal_links:
        from_type = link.get("from_type", "")
        from_content = link.get("from_content", "")
        to_type = link.get("to_type", "")
        to_content = link.get("to_content", "")

        from_id = content_to_id.get((from_type, from_content))
        to_id = content_to_id.get((to_type, to_content))

        if from_id is None:
            content_hash = hashlib.sha256(from_content.encode()).hexdigest()[:12]
            logger.warning(
                "Causal link from-node unresolved, skipping: type=%s content_hash=%s",
                from_type,
                content_hash,
            )
            continue
        if to_id is None:
            content_hash = hashlib.sha256(to_content.encode()).hexdigest()[:12]
            logger.warning(
                "Causal link to-node unresolved, skipping: type=%s content_hash=%s",
                to_type,
                content_hash,
            )
            continue

        rel: dict[str, str] = {
            "from_id": from_id,
            "to_id": to_id,
            "type": "CAUSES",
            "from_label": _LABEL_MAP.get(from_type, ""),
            "to_label": _LABEL_MAP.get(to_type, ""),
            "source_id": source_id,
        }
        mechanism = link.get("mechanism")
        if mechanism:
            rel["mechanism"] = mechanism
        confidence = link.get("confidence")
        if confidence:
            rel["confidence"] = confidence

        causes_rels.append(rel)

    return causes_rels


def _build_question_nodes(
    chunk: dict[str, Any],
    entity_name_to_id: dict[str, str],
    facts: list[dict[str, Any]],
    claims: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    """Build Question nodes and their relations from a chunk.

    Generates Question nodes with deterministic IDs and two types of
    outgoing relations:

    * **ASKS_ABOUT** (Question -> Entity): resolved via ``about_entities``.
    * **MOTIVATED_BY** (Question -> Claim/Fact/Insight): resolved via
      ``motivated_by_contents`` using chunk-scope content-to-ID mapping.

    Parameters
    ----------
    chunk : dict[str, Any]
        Raw chunk data containing ``questions[]``.
    entity_name_to_id : dict[str, str]
        Name-to-ID lookup for entity resolution.
    facts : list[dict[str, Any]]
        Fact node dicts built from this chunk (with ``fact_id``, ``content``).
    claims : list[dict[str, Any]]
        Claim node dicts built from this chunk (with ``claim_id``, ``content``).

    Returns
    -------
    tuple
        A 3-tuple of (questions, asks_about_rels, motivated_by_rels).
    """
    questions: list[dict[str, Any]] = []
    asks_about_rels: list[dict[str, str]] = []
    motivated_by_rels: list[dict[str, str]] = []

    raw_questions = chunk.get("questions", [])
    if not raw_questions:
        return questions, asks_about_rels, motivated_by_rels

    # Build content-to-ID mapping for MOTIVATED_BY resolution (tuple keys)
    content_to_id = _build_content_id_map(facts, claims)

    for raw_q in raw_questions:
        content = raw_q.get("content", "")
        if not content:
            continue

        question_id = generate_question_id(content)
        questions.append(
            {
                "question_id": question_id,
                "content": content,
                "question_type": raw_q.get("question_type", ""),
                "priority": raw_q.get("priority"),
                "status": "open",
            }
        )

        # ASKS_ABOUT: Question -> Entity
        asks_about_rels.extend(
            _resolve_entity_rels(
                raw_q.get("about_entities", []),
                question_id,
                "ASKS_ABOUT",
                entity_name_to_id,
            )
        )

        # MOTIVATED_BY: Question -> Claim/Fact
        for motivated_content in raw_q.get("motivated_by_contents", []):
            # Try both fact and claim types for resolution
            resolved_id = content_to_id.get(
                ("fact", motivated_content)
            ) or content_to_id.get(("claim", motivated_content))
            if resolved_id:
                motivated_by_rels.append(
                    {
                        "from_id": question_id,
                        "to_id": resolved_id,
                        "type": "MOTIVATED_BY",
                    }
                )
            else:
                content_hash = hashlib.sha256(motivated_content.encode()).hexdigest()[
                    :12
                ]
                logger.warning(
                    "MOTIVATED_BY target unresolved, skipping: content_hash=%s",
                    content_hash,
                )

    return questions, asks_about_rels, motivated_by_rels


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


RELATION_KEYS: frozenset[str] = frozenset(
    {
        "source_fact",
        "source_claim",
        "fact_entity",
        "claim_entity",
        "contains_chunk",
        "extracted_from_fact",
        "extracted_from_claim",
        "has_datapoint",
        "for_period",
        "datapoint_entity",
        "tagged",
        "holds_stance",
        "on_entity",
        "based_on",
        "supersedes",
        "authored_by",
        "causes",
        "next_period",
        "trend",
        "asks_about",
        "motivated_by",
    }
)
"""All 21 relation keys in the graph-queue schema (v2.1)."""


def _empty_rels() -> dict[str, list[dict[str, str]]]:
    """Return an empty relations dict with all relation keys."""
    return {k: [] for k in RELATION_KEYS}


def _process_chunk(
    chunk: dict[str, Any],
    source_hash: str,
    source_id: str,
    ctx: ChunkProcessingContext,
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
    ctx : ChunkProcessingContext
        Cross-chunk shared state (mutated in-place).

    Returns
    -------
    dict[str, Any]
        Dict with keys ``chunks``, ``entities``, ``facts``, ``claims``,
        ``datapoints``, ``periods``, ``stances``, ``authors``,
        ``questions``, and ``rels``.
    """
    chunk_node, chunk_id, cc_rels = _build_chunk_nodes(chunk, source_hash, source_id)

    entities = _build_entity_nodes(
        chunk, ctx.seen_entity_keys, ctx.entity_name_to_id, ctx.entity_name_to_ticker
    )

    facts, sf, ef, fe = _build_fact_nodes(
        chunk, source_id, chunk_id, ctx.entity_name_to_id
    )
    claims, sc, ec, ce = _build_claim_nodes(
        chunk, source_id, chunk_id, ctx.entity_name_to_id
    )
    dps, hd, de, dp_id_map = _build_datapoint_nodes(
        chunk, source_hash, source_id, ctx.entity_name_to_id
    )
    periods, fp = _derive_fiscal_periods(
        chunk, ctx.entity_name_to_ticker, ctx.seen_period_ids, dp_id_map
    )
    stance_result = _build_stance_nodes(
        chunk, ctx.entity_name_to_id, ctx.seen_author_keys, ctx.author_name_to_id
    )
    chunk_stances = stance_result["stances"]
    chunk_authors = stance_result["authors"]
    holds_stance_rels = stance_result["holds_stance"]
    on_entity_rels = stance_result["on_entity"]
    based_on_rels = stance_result["based_on"]

    causes = _build_causal_links(chunk, facts, claims, dps, source_id)

    chunk_questions, asks_about_rels, motivated_by_rels = _build_question_nodes(
        chunk, ctx.entity_name_to_id, facts, claims
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
        "holds_stance": holds_stance_rels,
        "on_entity": on_entity_rels,
        "based_on": based_on_rels,
        "causes": causes,
        "asks_about": asks_about_rels,
        "motivated_by": motivated_by_rels,
    }

    return {
        "chunks": [chunk_node],
        "entities": entities,
        "facts": facts,
        "claims": claims,
        "datapoints": dps,
        "periods": periods,
        "stances": chunk_stances,
        "authors": chunk_authors,
        "questions": chunk_questions,
        "rels": rels,
    }


_NODE_KEYS = (
    "entities",
    "facts",
    "claims",
    "chunks",
    "datapoints",
    "periods",
    "stances",
    "authors",
    "questions",
)
"""Keys shared between _process_chunk output and the node accumulator."""


def map_pdf_extraction(data: dict[str, Any]) -> dict[str, Any]:
    """Map pdf-extraction to graph-queue via per-chunk helper delegation.

    Parameters
    ----------
    data : dict[str, Any]
        Input with ``source_hash``, ``chunks[]``, and optional
        ``publisher`` (issuer name for AUTHORED_BY).

    Returns
    -------
    dict[str, Any]
        Graph-queue components (nodes + 21 relation types).
    """
    source_hash = data.get("source_hash", "")
    source_id = generate_source_id(f"pdf:{source_hash}")
    publisher = data.get("publisher", "")
    sources = [
        _make_source(f"pdf:{source_hash}", source_type="pdf", publisher=publisher)
    ]

    ctx = ChunkProcessingContext()
    nodes: dict[str, list[Any]] = {k: [] for k in _NODE_KEYS}
    rels = _empty_rels()

    for chunk in data.get("chunks", []):
        chunk_result = _process_chunk(
            chunk,
            source_hash,
            source_id,
            ctx,
        )
        for k in _NODE_KEYS:
            nodes[k].extend(chunk_result[k])
        _extend_rels(rels, chunk_result["rels"])

    # Build SUPERSEDES chain across all chunks
    supersedes = _build_supersedes_chain(nodes["stances"])
    rels["supersedes"].extend(supersedes)

    # Build AUTHORED_BY from Source.publisher (Phase 2 Step A-1)
    if publisher:
        new_authors, authored_by = _build_authored_by_rels(
            source_id, publisher, ctx.seen_author_keys, ctx.author_name_to_id
        )
        nodes["authors"].extend(new_authors)
        rels["authored_by"].extend(authored_by)

    # Build NEXT_PERIOD chain across all fiscal periods (Wave 3)
    next_period = _build_next_period_chain(nodes["periods"])
    rels["next_period"].extend(next_period)

    # Build TREND edges across all financial datapoints (Wave 3)
    trend = _build_trend_edges(
        nodes["datapoints"], nodes["periods"], rels["for_period"]
    )
    rels["trend"].extend(trend)

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
        authors=nodes["authors"],
        stances=nodes["stances"],
        questions=nodes["questions"],
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


@functools.lru_cache(maxsize=1)
def _load_wealth_themes(
    config_path: Path = WEALTH_THEME_CONFIG_PATH,
) -> dict[str, Any]:
    """Load wealth-management theme configuration.

    Results are cached (LRU, maxsize=1) to avoid repeated file I/O
    within the same process.

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


def _build_theme_lookup(
    themes: dict[str, Any],
) -> dict[str, tuple[str, str]]:
    """Build a reverse-lookup dict from source key to (theme_key, name_en).

    Parameters
    ----------
    themes : dict[str, Any]
        Theme configuration from ``wealth-management-themes.json``.

    Returns
    -------
    dict[str, tuple[str, str]]
        Mapping of ``{source_key: (theme_key, name_en)}``.
    """
    lookup: dict[str, tuple[str, str]] = {}
    for theme_key, theme_data in themes.items():
        name_en = theme_data.get("name_en", theme_key)
        for source in theme_data.get("target_sources", []):
            lookup[source] = (theme_key, name_en)
    return lookup


def _match_domain_to_theme(
    domain: str, themes: dict[str, Any]
) -> tuple[str, str] | None:
    """Match a domain name to a wealth theme via ``target_sources``.

    Uses a reverse-lookup dictionary for O(1) exact matching on source keys,
    with a linear fallback for substring matching.

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

    lookup = _build_theme_lookup(themes)

    # O(1) exact match
    if domain_base in lookup:
        return lookup[domain_base]

    # Fallback: substring matching for partial overlaps
    for source_key, result in lookup.items():
        if source_key in domain_base or domain_base in source_key:
            return result

    return None


def _process_domain_dir(
    domain_dir: Path,
    themes: dict[str, Any],
) -> dict[str, Any] | None:
    """Process a single domain subdirectory for wealth-scrape backfill.

    Reads Markdown files with YAML frontmatter, builds Source and Chunk
    nodes, and matches the domain to a theme for Topic generation.

    Parameters
    ----------
    domain_dir : Path
        Path to the domain subdirectory (e.g. ``wealth/ofdollarsanddata.com/``).
    themes : dict[str, Any]
        Theme configuration from ``wealth-management-themes.json``.

    Returns
    -------
    dict[str, Any] | None
        Mapped dict following the standard mapper result format, or ``None``
        if no valid articles are found.
    """
    domain = domain_dir.name
    md_files = sorted(domain_dir.glob("*.md"))
    if not md_files:
        logger.debug("No .md files in %s", domain_dir)
        return None

    sources: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []

    for md_file in md_files:
        # Single read per file: parse frontmatter and body from same text
        text = md_file.read_text(encoding="utf-8")
        frontmatter = _parse_frontmatter_from_text(text)
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

        # Extract body text (after frontmatter) as a chunk
        body_match = _BODY_RE.search(text)
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
        return None

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
                "topic_key": f"{theme_name}::wealth",
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
    return mapped


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
        Root directory to scan (e.g. ``/Volumes/personal_folder/scraped/wealth/``).
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
        mapped = _process_domain_dir(domain_dir, themes)
        if mapped is not None:
            results.append(mapped)

    logger.info(
        "Wealth directory scan complete: %d domain(s) with articles", len(results)
    )
    return results


def _map_wealth_theme_common(
    theme_key: str,
    theme_data: dict[str, Any],
    sources: list[dict[str, Any]],
    topics: list[dict[str, Any]],
    tagged_rels: list[dict[str, str]],
    *,
    extra_source_fields: dict[str, str] | None = None,
) -> tuple[str, list[str], list[dict[str, Any]]]:
    """Process the common theme-loop block shared by backfill and incremental.

    Appends a Topic node, pre-computes keyword lists, and iterates over
    articles to build Source nodes and keyword-matched tagged relations.

    Parameters
    ----------
    theme_key : str
        Theme key (e.g. ``"data_driven_investing"``).
    theme_data : dict[str, Any]
        Theme data containing ``name_en``, ``keywords_en``, ``articles``.
    sources : list[dict[str, Any]]
        Accumulated sources list (mutated in-place).
    topics : list[dict[str, Any]]
        Accumulated topics list (mutated in-place).
    tagged_rels : list[dict[str, str]]
        Accumulated tagged relations list (mutated in-place).
    extra_source_fields : dict[str, str] | None
        Additional static fields to include in each Source node
        (e.g. ``{"source_type": "blog"}``).

    Returns
    -------
    tuple[str, list[str], list[dict[str, Any]]]
        A 3-tuple of (topic_id, keywords_lower, articles).
    """
    name_en = theme_data.get("name_en", theme_key)
    topic_id = generate_topic_id(name_en, "wealth-management")

    topics.append(
        {
            "topic_id": topic_id,
            "name": name_en,
            "category": "wealth-management",
            "theme_key": theme_key,
            "topic_key": f"{name_en}::wealth-management",
        }
    )

    keywords_en: list[str] = theme_data.get("keywords_en", [])
    keywords_lower = [kw.lower() for kw in keywords_en]
    articles = theme_data.get("articles", [])

    return topic_id, keywords_lower, articles


def _process_wealth_article(
    article: dict[str, Any],
    topic_id: str,
    keywords_lower: list[str],
    sources: list[dict[str, Any]],
    tagged_rels: list[dict[str, str]],
    **extra_source_fields: Any,
) -> str | None:
    """Process a single wealth article: build Source and tagged relation.

    Parameters
    ----------
    article : dict[str, Any]
        Article data.
    topic_id : str
        Topic ID for tagged relations.
    keywords_lower : list[str]
        Pre-lowered keywords for matching.
    sources : list[dict[str, Any]]
        Accumulated sources list (mutated in-place).
    tagged_rels : list[dict[str, str]]
        Accumulated tagged relations list (mutated in-place).
    **extra_source_fields : Any
        Additional fields for the Source node.

    Returns
    -------
    str | None
        The source_id if the article was processed, or ``None`` if skipped.
    """
    url = article.get("url", "")
    if not url:
        return None

    source = _make_source(
        url,
        title=article.get("title", ""),
        published=article.get("published", ""),
        feed_source=article.get("feed_source", ""),
        domain=article.get("domain", ""),
        **extra_source_fields,
    )
    source_id = source["source_id"]
    sources.append(source)

    # Keyword matching for tagged relation
    title_lower = article.get("title", "").lower()
    for kw_lower in keywords_lower:
        if kw_lower in title_lower:
            tagged_rels.append({"from_id": source_id, "to_id": topic_id})
            break

    return source_id


def map_wealth_scrape_backfill(data: dict[str, Any]) -> dict[str, Any]:
    """Map wealth-scrape backfill session to graph-queue components.

    Backfill mode produces Source, Topic, Entity (domain), and keyword-matched
    ``tagged`` relations.  No claims are generated.

    Parameters
    ----------
    data : dict[str, Any]
        Input data with ``themes.{key}.articles[]``, ``session_id``.
        Each theme may include ``keywords_en`` for title-based tagging.

    Returns
    -------
    dict[str, Any]
        Mapped components with ``sources[]``, ``topics[]``, ``entities[]``,
        and ``relations.tagged[]``.
    """
    themes = data.get("themes", {})
    sources: list[dict[str, Any]] = []
    topics: list[dict[str, Any]] = []
    entities: list[dict[str, Any]] = []
    tagged_rels: list[dict[str, str]] = []
    seen_domains: set[str] = set()

    for theme_key, theme_data in themes.items():
        topic_id, keywords_lower, articles = _map_wealth_theme_common(
            theme_key, theme_data, sources, topics, tagged_rels
        )

        for article in articles:
            source_id = _process_wealth_article(
                article,
                topic_id,
                keywords_lower,
                sources,
                tagged_rels,
                source_type="blog",
            )
            if source_id is None:
                continue

            # Entity: one per unique domain
            domain = article.get("domain", "")
            if domain and domain not in seen_domains:
                seen_domains.add(domain)
                entities.append(
                    {
                        "entity_id": generate_entity_id(domain, "domain"),
                        "name": domain,
                        "entity_type": "domain",
                        "entity_key": f"{domain}::domain",
                    }
                )

    rels = _empty_rels()
    rels["tagged"] = tagged_rels

    return _mapped_result(
        data,
        "wealth-scrape",
        sources=sources,
        topics=topics,
        entities=entities,
        relations=rels,
    )


def map_wealth_scrape_incremental(data: dict[str, Any]) -> dict[str, Any]:
    """Map wealth-scrape incremental session to graph-queue components.

    Incremental mode produces Source, Topic, Claim, and keyword-matched
    ``tagged`` / ``source_claim`` relations.  No domain entities are generated.

    Parameters
    ----------
    data : dict[str, Any]
        Input data with ``themes.{key}.articles[]``, ``session_id``.
        Each article should include ``summary`` for claim generation.

    Returns
    -------
    dict[str, Any]
        Mapped components with ``sources[]``, ``topics[]``, ``claims[]``,
        and ``relations.tagged[]``, ``relations.source_claim[]``.
    """
    themes = data.get("themes", {})
    sources: list[dict[str, Any]] = []
    topics: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    tagged_rels: list[dict[str, str]] = []
    source_claim_rels: list[dict[str, str]] = []

    for theme_key, theme_data in themes.items():
        topic_id, keywords_lower, articles = _map_wealth_theme_common(
            theme_key, theme_data, sources, topics, tagged_rels
        )

        for article in articles:
            source_id = _process_wealth_article(
                article,
                topic_id,
                keywords_lower,
                sources,
                tagged_rels,
            )
            if source_id is None:
                continue

            # Claim from summary
            summary = article.get("summary", "")
            if summary:
                claim_id = generate_claim_id(summary)
                claims.append(
                    {
                        "claim_id": claim_id,
                        "content": summary,
                        "source_id": source_id,
                        "category": "wealth-management",
                    }
                )
                source_claim_rels.append({"from_id": source_id, "to_id": claim_id})

    rels = _empty_rels()
    rels["tagged"] = tagged_rels
    rels["source_claim"] = source_claim_rels

    return _mapped_result(
        data,
        "wealth-scrape",
        sources=sources,
        topics=topics,
        claims=claims,
        relations=rels,
    )


def map_wealth_scrape(data: dict[str, Any]) -> dict[str, Any]:
    """Dispatch wealth-scrape mapping based on ``mode``.

    Delegates to :func:`map_wealth_scrape_backfill` when ``mode == "backfill"``,
    and to :func:`map_wealth_scrape_incremental` otherwise (default).

    Parameters
    ----------
    data : dict[str, Any]
        Input data with ``mode``, ``themes.{key}.articles[]``, ``session_id``.

    Returns
    -------
    dict[str, Any]
        Mapped components (delegated to the appropriate sub-mapper).
    """
    mode = data.get("mode", "")
    if mode == "backfill":
        return map_wealth_scrape_backfill(data)
    return map_wealth_scrape_incremental(data)


# ---------------------------------------------------------------------------
# topic-discovery constants & helpers
# ---------------------------------------------------------------------------

TOPIC_DISCOVERY_CATEGORIES: dict[str, str] = {
    "market_report": "マーケットレポート",
    "stock_analysis": "個別株分析",
    "macro_economy": "マクロ経済",
    "asset_management": "資産形成",
    "side_business": "副業・収益化",
    "quant_analysis": "クオンツ分析",
    "investment_education": "投資教育",
}
"""Category key to Japanese name mapping for topic-discovery."""


def _magnitude_from_score(total: int) -> str:
    """Determine magnitude label from a total suggestion score.

    Parameters
    ----------
    total : int
        Total score (sum of 5 scoring axes).

    Returns
    -------
    str
        ``"strong"`` if >= 40, ``"moderate"`` if >= 30, else ``"slight"``.
    """
    if total >= 40:
        return "strong"
    if total >= 30:
        return "moderate"
    return "slight"


def _build_td_claim(
    suggestion: dict[str, Any],
    session_id: str,
    generated_at: str,
) -> dict[str, Any]:
    """Build a Claim node dict from a single topic-discovery suggestion.

    Parameters
    ----------
    suggestion : dict[str, Any]
        Raw suggestion dict from topic-discovery output.
    session_id : str
        Session identifier for ID construction.
    generated_at : str
        ISO 8601 timestamp.

    Returns
    -------
    dict[str, Any]
        Claim node dict.
    """
    scores = suggestion.get("scores", {})
    total_score = scores.get("total", 0)
    topic_title = suggestion.get("topic", "")
    rationale = suggestion.get("rationale", "")
    key_points = suggestion.get("key_points", [])

    return {
        "claim_id": f"ts:{session_id}:rank{suggestion.get('rank', 0)}",
        "content": f"{topic_title}: {rationale}" if rationale else topic_title,
        "claim_type": "recommendation",
        "sentiment": "neutral",
        "magnitude": _magnitude_from_score(total_score),
        "created_at": generated_at,
        "rank": suggestion.get("rank", 0),
        "topic_title": topic_title,
        "total_score": total_score,
        "timeliness": scores.get("timeliness", 0),
        "information_availability": scores.get("information_availability", 0),
        "reader_interest": scores.get("reader_interest", 0),
        "feasibility": scores.get("feasibility", 0),
        "uniqueness": scores.get("uniqueness", 0),
        "estimated_word_count": suggestion.get("estimated_word_count"),
        "target_audience": suggestion.get("target_audience"),
        "selected": suggestion.get("selected"),
        "key_points": json.dumps(key_points, ensure_ascii=False)
        if key_points
        else "[]",
        "suggested_period": suggestion.get("suggested_period"),
    }


def _build_td_facts(
    search_insights: dict[str, Any],
    session_id: str,
    generated_at: str,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Build Fact nodes and STATES_FACT relations from search trends.

    Parameters
    ----------
    search_insights : dict[str, Any]
        Search insights dict with ``trends[]``.
    session_id : str
        Session identifier for ID construction.
    generated_at : str
        ISO 8601 timestamp.

    Returns
    -------
    tuple[list[dict[str, Any]], list[dict[str, str]]]
        A 2-tuple of (fact_nodes, source_fact_relations).
    """
    generated_at_date = generated_at[:10] if generated_at else ""
    facts: list[dict[str, Any]] = []
    rels: list[dict[str, str]] = []

    for i, trend in enumerate(search_insights.get("trends", [])):
        query = trend.get("query", "")
        source_type = trend.get("source", "")
        for j, finding in enumerate(trend.get("key_findings", [])):
            fact_id = f"trend:{session_id}:{i}:{j}"
            facts.append(
                {
                    "fact_id": fact_id,
                    "content": finding,
                    "fact_type": "event",
                    "as_of_date": generated_at_date,
                    "created_at": generated_at,
                    "search_query": query,
                    "search_source": source_type,
                }
            )
            rels.append(
                {"from_id": session_id, "to_id": fact_id, "type": "STATES_FACT"}
            )

    return facts, rels


def _build_td_entities(
    suggestions: list[dict[str, Any]],
    claims: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], set[str], list[dict[str, str]]]:
    """Build Entity nodes and claim-entity relations from suggested symbols.

    Parameters
    ----------
    suggestions : list[dict[str, Any]]
        List of suggestion dicts, each with optional ``suggested_symbols``.
    claims : list[dict[str, Any]]
        Corresponding list of Claim node dicts (same order as suggestions).

    Returns
    -------
    tuple[list[dict[str, Any]], set[str], list[dict[str, str]]]
        A 3-tuple of (entities, seen_tickers, claim_entity_rels).
    """
    seen_tickers: set[str] = set()
    entities: list[dict[str, Any]] = []
    claim_entity_rels: list[dict[str, str]] = []

    for suggestion, claim in zip(suggestions, claims, strict=True):
        for ticker in suggestion.get("suggested_symbols", []):
            entity_id = f"symbol:{ticker}"
            if ticker not in seen_tickers:
                seen_tickers.add(ticker)
                entity_type = "index" if ticker.startswith("^") else "stock"
                entities.append(
                    {
                        "entity_id": entity_id,
                        "name": ticker,
                        "entity_type": entity_type,
                        "ticker": ticker,
                        "entity_key": f"{ticker}::{entity_type}",
                    }
                )
            claim_entity_rels.append(
                {"from_id": claim["claim_id"], "to_id": entity_id, "type": "ABOUT"}
            )

    return entities, seen_tickers, claim_entity_rels


def map_topic_discovery(data: dict[str, Any]) -> dict[str, Any]:
    """Map topic-discovery session data to graph-queue components.

    Uses string-based IDs (not UUID5) as defined in the neo4j-mapping spec.

    Parameters
    ----------
    data : dict[str, Any]
        Input data with ``session_id``, ``generated_at``, ``suggestions[]``,
        ``search_insights``, ``recommendation``, and optionally
        ``parameters.no_search``.

    Returns
    -------
    dict[str, Any]
        Mapped components with ``sources[]``, ``topics[]``, ``claims[]``,
        ``entities[]``, ``facts[]``, and ``relations``.
    """
    session_id = data.get("session_id", "")
    generated_at = data.get("generated_at", "")
    suggestions = data.get("suggestions", [])
    search_insights = data.get("search_insights") or {}
    recommendation = data.get("recommendation", "")
    no_search = (data.get("parameters") or {}).get("no_search", False)

    # --- Source node (1 per session) ---
    top_score = max(
        (s.get("scores", {}).get("total", 0) for s in suggestions), default=0
    )
    search_queries_count = (
        search_insights.get("queries_executed", 0) if not no_search else 0
    )
    generated_at_date = generated_at[:10] if generated_at else ""

    sources: list[dict[str, Any]] = [
        {
            "source_id": session_id,
            "title": f"トピック提案セッション {generated_at_date}",
            "source_type": "original",
            "fetched_at": generated_at,
            "language": "ja",
            "command_source": "topic-discovery",
            "suggestion_count": len(suggestions),
            "top_score": top_score,
            "search_queries_count": search_queries_count,
            "recommendation": recommendation,
        }
    ]

    # Accumulators for nodes and relations
    seen_categories: set[str] = set()
    topics: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    tagged_rels: list[dict[str, str]] = []
    source_claim_rels: list[dict[str, str]] = []

    for suggestion in suggestions:
        category_key = suggestion.get("category", "")
        topic_id = f"content:{category_key}"

        # Topic node (MERGE semantics via dedup)
        if category_key and category_key not in seen_categories:
            seen_categories.add(category_key)
            topics.append(
                {
                    "topic_id": topic_id,
                    "name": TOPIC_DISCOVERY_CATEGORIES.get(category_key, category_key),
                    "category": "content_planning",
                    "topic_key": f"{TOPIC_DISCOVERY_CATEGORIES.get(category_key, category_key)}::content_planning",
                }
            )
            tagged_rels.append(
                {"from_id": session_id, "to_id": topic_id, "type": "TAGGED"}
            )

        # Claim node
        claim = _build_td_claim(suggestion, session_id, generated_at)
        claims.append(claim)
        source_claim_rels.append(
            {"from_id": session_id, "to_id": claim["claim_id"], "type": "MAKES_CLAIM"}
        )
        if category_key:
            tagged_rels.append(
                {"from_id": claim["claim_id"], "to_id": topic_id, "type": "TAGGED"}
            )

    # Entity nodes from suggested_symbols (delegated to helper)
    entities, _seen_tickers, claim_entity_rels = _build_td_entities(suggestions, claims)

    # Fact nodes from search_insights.trends (skip when no_search)
    if no_search:
        facts: list[dict[str, Any]] = []
        source_fact_rels: list[dict[str, str]] = []
    else:
        facts, source_fact_rels = _build_td_facts(
            search_insights, session_id, generated_at
        )

    return _mapped_result(
        data,
        "topic-discovery",
        sources=sources,
        topics=topics,
        claims=claims,
        entities=entities,
        facts=facts,
        relations={
            "tagged": tagged_rels,
            "source_claim": source_claim_rels,
            "claim_entity": claim_entity_rels,
            "source_fact": source_fact_rels,
        },
    )


# ---------------------------------------------------------------------------
# map_web_research
# ---------------------------------------------------------------------------

_VALID_AUTHORITY_LEVELS = frozenset(
    {"official", "analyst", "media", "blog", "social", "academic"}
)


def _build_wr_sources(
    raw_sources: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Build Source nodes from web-research input.

    Returns
    -------
    tuple
        (sources, url_to_source_id) — source nodes and URL→ID lookup.

    Raises
    ------
    KeyError
        If any source is missing ``authority_level``.
    ValueError
        If any source has an invalid ``authority_level``.
    """
    sources: list[dict[str, Any]] = []
    url_to_source_id: dict[str, str] = {}

    for src in raw_sources:
        authority = src["authority_level"]  # KeyError if missing
        if authority not in _VALID_AUTHORITY_LEVELS:
            msg = (
                f"Invalid authority_level {authority!r}. "
                f"Expected one of {sorted(_VALID_AUTHORITY_LEVELS)}"
            )
            raise ValueError(msg)
        url = src.get("url", "")
        if not url:
            logger.warning(
                "Source missing URL, skipping (title=%r)", src.get("title", "")
            )
            continue
        sid = generate_source_id(url)
        url_to_source_id[url] = sid
        sources.append(
            {
                "source_id": sid,
                "url": url,
                "title": src.get("title", ""),
                "published": src.get("published_at", ""),
                "source_type": src.get("source_type", ""),
                "authority_level": authority,
                "command_source": "web-research",
            }
        )

    return sources, url_to_source_id


def _build_wr_topics(
    raw_topics: list[dict[str, Any]],
    sources: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Build Topic nodes and Source→Topic TAGGED rels.

    All sources are tagged with all topics (full cross-product by design).
    """
    topics: list[dict[str, Any]] = []
    tagged_rels: list[dict[str, str]] = []

    for raw_topic in raw_topics:
        name = raw_topic.get("name", "")
        category = raw_topic.get("category", "")
        tid = generate_topic_id(name, category)
        topics.append(
            {
                "topic_id": tid,
                "name": name,
                "category": category,
                "topic_key": f"{name}::{category}",
            }
        )
        # All sources tagged with each topic (intentional full cross-product)
        for src_node in sources:
            tagged_rels.append(
                {
                    "from_id": src_node["source_id"],
                    "to_id": tid,
                    "type": "TAGGED",
                }
            )

    return topics, tagged_rels


def _validate_confidence(raw_value: object) -> float | None:
    """Validate and clamp confidence to [0.0, 1.0]."""
    if raw_value is None:
        return None
    try:
        value = float(raw_value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        logger.warning("Invalid confidence value: %r, ignoring", raw_value)
        return None
    if not (0.0 <= value <= 1.0):
        logger.warning("confidence out of range [0,1]: %s, clamping", value)
        return max(0.0, min(1.0, value))
    return value


def _build_wr_facts(
    raw_facts: list[dict[str, Any]],
    url_to_source_id: dict[str, str],
    topics: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, list[dict[str, str]]],
    list[dict[str, str]],
]:
    """Build Fact/Entity nodes and all fact-related relations.

    Returns
    -------
    tuple
        (facts, entities, fact_rels, tagged_rels) where fact_rels contains
        source_fact, fact_entity, and extracted_from_fact relation lists.
        All facts are tagged with all topics (intentional full cross-product).
    """
    facts: list[dict[str, Any]] = []
    entities: list[dict[str, Any]] = []
    source_fact_rels: list[dict[str, str]] = []
    fact_entity_rels: list[dict[str, str]] = []
    extracted_from_fact_rels: list[dict[str, str]] = []
    tagged_rels: list[dict[str, str]] = []
    entity_id_map: dict[str, str] = {}  # ekey → eid

    for raw_fact in raw_facts:
        content = raw_fact.get("content", "")
        source_url = raw_fact.get("source_url", "")

        if source_url not in url_to_source_id:
            logger.warning(
                "Fact source_url not found in sources, skipping: %s",
                source_url,
            )
            continue

        fid = generate_fact_id(content)
        sid = url_to_source_id[source_url]

        facts.append(
            {
                "fact_id": fid,
                "content": content,
                "confidence": _validate_confidence(raw_fact.get("confidence")),
            }
        )

        source_fact_rels.append(
            {"from_id": sid, "to_id": fid, "type": "STATES_FACT"}
        )
        extracted_from_fact_rels.append(
            {"from_id": fid, "to_id": sid, "type": "EXTRACTED_FROM"}
        )

        # Entity dedup & RELATES_TO rels
        for ent in raw_fact.get("about_entities", []):
            ename = ent.get("name", "")
            etype = ent.get("entity_type", "")
            ekey = f"{ename}::{etype}"
            eid = generate_entity_id(ename, etype)

            if ekey not in entity_id_map:
                entity_id_map[ekey] = eid
                entities.append(
                    {
                        "entity_id": eid,
                        "name": ename,
                        "entity_type": etype,
                        "entity_key": ekey,
                    }
                )

            fact_entity_rels.append(
                {"from_id": fid, "to_id": eid, "type": "RELATES_TO"}
            )

        # All facts tagged with all topics (intentional full cross-product)
        for topic_node in topics:
            tagged_rels.append(
                {
                    "from_id": fid,
                    "to_id": topic_node["topic_id"],
                    "type": "TAGGED",
                }
            )

    fact_rels = {
        "source_fact": source_fact_rels,
        "fact_entity": fact_entity_rels,
        "extracted_from_fact": extracted_from_fact_rels,
    }
    return facts, entities, fact_rels, tagged_rels


def map_web_research(data: dict[str, Any]) -> dict[str, Any]:
    """Map web-research session data to graph-queue components.

    Converts ad-hoc web research data into the formal pipeline format
    consumed by ``/save-to-graph``.

    Parameters
    ----------
    data : dict[str, Any]
        Input data with ``session_id``, ``sources[]``, ``facts[]``, and
        ``topics[]``.

    Returns
    -------
    dict[str, Any]
        Mapped components with ``sources[]``, ``facts[]``, ``entities[]``,
        ``topics[]``, and ``relations`` containing the four relation types
        ``source_fact``, ``fact_entity``, ``tagged``, and
        ``extracted_from_fact``.

    Raises
    ------
    KeyError
        If any source is missing the ``authority_level`` field.
    ValueError
        If any source has an invalid ``authority_level`` value.
    """
    sources, url_to_source_id = _build_wr_sources(data.get("sources", []))
    topics, tagged_rels = _build_wr_topics(data.get("topics", []), sources)
    facts, entities, fact_rels, fact_tagged = _build_wr_facts(
        data.get("facts", []), url_to_source_id, topics
    )
    tagged_rels.extend(fact_tagged)

    return _mapped_result(
        data,
        "web-research",
        sources=sources,
        facts=facts,
        entities=entities,
        topics=topics,
        relations={**fact_rels, "tagged": tagged_rels},
    )


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
    "topic-discovery": map_topic_discovery,
    "web-research": map_web_research,
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
    if command in DIRECTORY_COMMANDS and input_path.is_dir():
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
        "authors": mapped.get("authors", []),
        "stances": mapped.get("stances", []),
        "questions": mapped.get("questions", []),
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
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    parsed = parse_args(args)

    return run(
        command=parsed.command,
        input_path=Path(parsed.input),
        cleanup=parsed.cleanup,
    )


if __name__ == "__main__":
    sys.exit(main())
