"""mappers/helpers.py — 全マッパープラグインが共有するヘルパー関数・定数。

emit_research_queue.py から抽出されたユーティリティ群。
各マッパーはこのモジュールから直接インポートする。

Usage
-----
::

    from mappers.helpers import (
        _make_source,
        generate_source_id,
        generate_topic_id,
        _build_wr_sources,
        _process_chunk,
        ...
    )
"""

from __future__ import annotations

import functools
import hashlib
import json
import logging
import re
import secrets
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

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Re-export id_generator functions for backward compatibility
# ---------------------------------------------------------------------------

__all__ = [
    "FACT_TYPE_META",
    "RELATION_KEYS",
    "THEME_TO_CATEGORY",
    "TOPIC_DISCOVERY_CATEGORIES",
    "WEALTH_THEME_CONFIG_PATH",
    "_NODE_KEYS",
    "ChunkProcessingContext",
    "StanceBuildResult",
    "_build_authored_by_rels",
    "_build_causal_links",
    "_build_chunk_nodes",
    "_build_claim_nodes",
    "_build_datapoint_nodes",
    "_build_entity_nodes",
    "_build_fact_nodes",
    "_build_next_period_chain",
    "_build_question_nodes",
    "_build_stance_nodes",
    "_build_supersedes_chain",
    "_build_td_claim",
    "_build_td_entities",
    "_build_td_facts",
    "_build_trend_edges",
    "_build_wr_causal_rels",
    "_build_wr_claims",
    "_build_wr_facts",
    "_build_wr_sources",
    "_build_wr_topics",
    "_derive_fiscal_periods",
    "_empty_rels",
    "_extend_rels",
    "_infer_period_type",
    "_load_wealth_themes",
    "_magnitude_from_score",
    "_make_source",
    "_map_wealth_theme_common",
    "_mapped_result",
    "_match_domain_to_theme",
    "_normalize_entity_type",
    "_normalize_source_type",
    "_parse_date_safe",
    "_parse_frontmatter_from_text",
    "_parse_yaml_frontmatter",
    "_period_sort_key",
    "_process_chunk",
    "_process_domain_dir",
    "_process_wealth_article",
    "_scan_wealth_directory",
    "generate_author_id",
    "generate_chunk_id",
    "generate_claim_id",
    "generate_datapoint_id",
    "generate_entity_id",
    "generate_fact_id",
    "generate_question_id",
    "generate_queue_id",
    "generate_source_id",
    "generate_stance_id",
    "generate_topic_id",
    "resolve_category",
    "resolve_metric_id",
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

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

FACT_TYPE_META: dict[str, str] = {
    "statistic": "統計",
    "financial_metric": "財務指標",
    "macro_indicator": "マクロ指標",
    "event": "イベント",
    "empirical": "実証データ",
    "regulatory": "規制",
    "market_data": "市場データ",
    "strategic": "戦略",
    "methodology": "方法論",
    "risk": "リスク",
}
"""FactType name_ja metadata."""

TOPIC_DISCOVERY_CATEGORIES: dict[str, str] = {
    "market_report": "マーケットレポート",
    "stock_analysis": "個別株分析",
    "macro_economy": "マクロ経済",
    "asset_management": "資産形成",
    "quant_analysis": "クオンツ分析",
    "investment_education": "投資教育",
}
"""Category key to Japanese name mapping for topic-discovery."""

WEALTH_THEME_CONFIG_PATH = Path("data/config/wealth-management-themes.json")
"""Path to the wealth-management theme configuration file."""

_VALID_AUTHORITY_LEVELS = frozenset(
    {"official", "analyst", "media", "blog", "social", "academic"}
)
"""Valid authority_level values for web-research sources."""

_SOURCE_TYPE_NORMALIZATION: dict[str, str] = {
    "tower_company_analysis": "analysis",
    "company_analysis": "analysis",
    "digital_services_analysis": "analysis",
    "regulatory_analysis": "analysis",
    "political_analysis": "analysis",
    "macro_data": "data",
    "spectrum_data": "data",
    "web-research": "web",
    "annual_report": "company_filing",
    "regulatory_filing": "company_filing",
    "research": "report",
    "official": "report",
    "original": "report",
    "academic_paper": "academic",
    "academic-paper": "academic",
    "research_paper": "academic",
}
"""source_type normalization mapping."""

_METRIC_MASTER_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "config"
    / "metric_master.json"
)

_GAP_MONTHS: dict[str, int] = {
    "annual": 12,
    "quarterly": 3,
    "half_year": 6,
}
"""Default gap_months by period_type."""

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
_KV_RE = re.compile(r"^(\w+):\s*(.*)$")
_BODY_RE = re.compile(r"^---\n.*?\n---\n*(.*)", re.DOTALL)
_FY_RE = re.compile(r"^FY\s*(\d{4}|\d{2})$", re.IGNORECASE)
_Q_RE = re.compile(r"^(\d)[Qq]\s*(\d{4}|\d{2})$")
_H_RE = re.compile(r"^(\d)[Hh]\s*(\d{4}|\d{2})$")

_LABEL_MAP: dict[str, str] = {
    "fact": "Fact",
    "claim": "Claim",
    "datapoint": "FinancialDataPoint",
}

RELATION_KEYS: frozenset[str] = frozenset(
    {
        # v2.1 relation keys (21)
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
        # v3.0 classification relation keys (20)
        "is_source_type",
        "from_domain",
        "rated_as",
        "in_language",
        "ingested_via",
        "is_type",
        "has_identifier",
        "in_industry",
        "is_fact_type",
        "is_claim_type",
        "in_unit",
        "is_datapoint_type",
        "is_category",
        "is_author_type",
        "affiliated_with",
        "alias_of",
        "parent_class",
        "in_parent_sector",
        "issued_by",
        "is_instrument_class",
    }
)
"""All 41 relation keys in the graph-queue schema (v3.0)."""

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


# ---------------------------------------------------------------------------
# TypedDict / dataclasses
# ---------------------------------------------------------------------------


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
# ID generators (unique to this module — not in pdf_pipeline)
# ---------------------------------------------------------------------------


def generate_datapoint_id(source_hash: str, metric: str, period: str) -> str:
    """Generate a deterministic datapoint ID from source_hash, metric and period.

    Delegates to ``pdf_pipeline.services.id_generator.generate_datapoint_id_from_fields``.
    Returns first 32 hex characters (128-bit) of the SHA-256 hash.
    """
    return generate_datapoint_id_from_fields(source_hash, metric, period)


def generate_topic_id(name: str, category: str) -> str:
    """Generate a deterministic topic ID from name and category.

    Returns a UUID5 string derived from ``topic:{name}:{category}``.
    """
    import uuid

    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"topic:{name}:{category}"))


def generate_chunk_id(source_hash: str, chunk_index: int) -> str:
    """Generate a deterministic chunk ID from source_hash and chunk_index.

    Returns a string in the format ``{source_hash}_chunk_{chunk_index}``.
    """
    return f"{source_hash}_chunk_{chunk_index}"


def generate_queue_id() -> str:
    """Generate a unique queue ID with timestamp and random suffix."""
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d%H%M%S")
    rand8 = secrets.token_hex(4)
    return f"gq-{timestamp}-{rand8}"


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def _normalize_source_type(raw: str) -> str:
    """Normalize source_type to one of 12 canonical values."""
    return _SOURCE_TYPE_NORMALIZATION.get(raw, raw)


def _normalize_entity_type(raw: str) -> str:
    """Normalize entity_type to lowercase."""
    return raw.lower() if raw else raw


# ---------------------------------------------------------------------------
# Category / metric resolution
# ---------------------------------------------------------------------------


def resolve_category(theme_key: str) -> str:
    """Resolve a theme key to its canonical category."""
    return THEME_TO_CATEGORY.get(theme_key, "other")


@functools.lru_cache(maxsize=1)
def _load_metric_alias_index() -> dict[str, str]:
    """Build a case-insensitive alias → metric_id lookup from metric_master.json."""
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
        for key in [
            metric.get("canonical_name", ""),
            metric.get("display_name", ""),
            *metric.get("aliases", []),
        ]:
            if key:
                index[key.lower()] = metric_id

    logger.debug("Loaded metric alias index: %d entries", len(index))
    return index


def resolve_metric_id(metric_name: str) -> str | None:
    """Resolve a metric_name to its canonical metric_id."""
    if not metric_name:
        return None
    return _load_metric_alias_index().get(metric_name.lower())


# ---------------------------------------------------------------------------
# Period helpers
# ---------------------------------------------------------------------------


def _infer_period_type(label: str) -> str:
    """Infer a period type from a human-readable period label."""
    upper = label.upper()
    if "Q" in upper and "FQ" not in upper:
        return "quarterly"
    if "H" in upper:
        return "half_year"
    return "annual"


def _normalize_year(raw: str) -> int:
    """Normalize a 2-digit or 4-digit year string to a 4-digit integer."""
    year = int(raw)
    if year < 100:
        year += 2000
    return year


def _period_sort_key(label: str) -> tuple[int, int]:
    """Compute a sortable key from a fiscal period label."""
    m = _FY_RE.match(label)
    if m:
        return (_normalize_year(m.group(1)), 0)
    m = _Q_RE.match(label)
    if m:
        return (_normalize_year(m.group(2)), int(m.group(1)))
    m = _H_RE.match(label)
    if m:
        return (_normalize_year(m.group(2)), int(m.group(1)))
    logger.warning("Unrecognised period label for sorting: %s", label)
    return (9999, 0)


def _parse_date_safe(raw: str | None) -> date:
    """Parse an ISO 8601 date string safely for sorting."""
    if not raw:
        return date.min
    try:
        return date.fromisoformat(raw)
    except (ValueError, TypeError):
        logger.warning("Unparseable as_of_date for sorting: %s", raw)
        return date.min


def _extract_ticker_from_period_id(period_id: str) -> str:
    """Extract the ticker prefix from a period_id."""
    parts = period_id.rsplit("_", 1)
    return parts[0] if len(parts) > 1 else ""


# ---------------------------------------------------------------------------
# Source builder
# ---------------------------------------------------------------------------


def _make_source(
    url: str, title: str = "", published: str = "", **extra: Any
) -> dict[str, Any]:
    """Build a Source dict with a deterministic source_id."""
    source = {
        "source_id": generate_source_id(url),
        "url": url,
        "title": title,
        "published": published,
        **extra,
    }
    if "source_type" in source:
        source["source_type"] = _normalize_source_type(source["source_type"])
    if "authority_level" not in source:
        source["authority_level"] = classify_authority(
            source_type=source.get("source_type", ""),
            url=url,
        )
    return source


# ---------------------------------------------------------------------------
# Standard mapper result builder
# ---------------------------------------------------------------------------


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
    classification_nodes: list[dict[str, Any]] | None = None,
    classification_rels: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Build the standard mapper result dict."""
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
        "classification_nodes": classification_nodes or [],
        "classification_rels": classification_rels or [],
    }


# ---------------------------------------------------------------------------
# Relation helpers
# ---------------------------------------------------------------------------


def _empty_rels() -> dict[str, list[dict[str, str]]]:
    """Return an empty relations dict with all relation keys."""
    return {k: [] for k in RELATION_KEYS}


def _extend_rels(
    target: dict[str, list[dict[str, str]]],
    updates: dict[str, list[dict[str, str]]],
) -> None:
    """Merge relation lists from updates into target in-place."""
    for key, values in updates.items():
        target[key].extend(values)


# ---------------------------------------------------------------------------
# Entity / node building helpers
# ---------------------------------------------------------------------------


def _resolve_entity_rels(
    about_entities: list[str] | list[dict[str, Any]],
    from_id: str,
    rel_type: str,
    entity_name_to_id: dict[str, str],
) -> list[dict[str, str]]:
    """Resolve entity names to relation dicts."""
    result: list[dict[str, str]] = []
    for item in about_entities:
        name = item.get("name", "") if isinstance(item, dict) else item
        resolved_id = entity_name_to_id.get(name)
        if resolved_id:
            result.append({"from_id": from_id, "to_id": resolved_id, "type": rel_type})
    return result


def _build_content_id_map(
    facts: list[dict[str, Any]],
    claims: list[dict[str, Any]],
) -> dict[tuple[str, str], str]:
    """Build a content-to-ID mapping from facts and claims."""
    content_to_id: dict[tuple[str, str], str] = {}
    for fact_item in facts:
        content_to_id[("fact", fact_item["content"])] = fact_item["fact_id"]
    for claim_item in claims:
        content_to_id[("claim", claim_item["content"])] = claim_item["claim_id"]
    return content_to_id


def _build_chunk_nodes(
    chunk: dict[str, Any],
    source_hash: str,
    source_id: str,
) -> tuple[dict[str, Any], str, list[dict[str, str]]]:
    """Build a Chunk node and its CONTAINS_CHUNK relation."""
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
    """Build Entity nodes from a chunk, deduplicated by name+type."""
    entities: list[dict[str, Any]] = []

    for entity in chunk.get("entities", []):
        name = entity.get("name", "")
        entity_type = _normalize_entity_type(entity.get("entity_type", ""))
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
    """Build Fact nodes and their relations from a chunk."""
    facts: list[dict[str, Any]] = []
    source_fact_rels: list[dict[str, str]] = []
    extracted_from_fact_rels: list[dict[str, str]] = []
    fact_entity_rels: list[dict[str, str]] = []

    for fact in chunk.get("facts", []):
        content = fact.get("content", "")
        fact_id = generate_fact_id(content)
        raw_ft = fact.get("fact_type", "")
        validated_ft = raw_ft if raw_ft in FACT_TYPE_META else "empirical"
        facts.append(
            {
                "fact_id": fact_id,
                "content": content,
                "source_id": source_id,
                "fact_type": validated_ft,
                "as_of_date": fact.get("as_of_date"),
            }
        )
        source_fact_rels.append(
            {"from_id": source_id, "to_id": fact_id, "type": "STATES_FACT"}
        )
        extracted_from_fact_rels.append(
            {"from_id": fact_id, "to_id": chunk_id, "type": "EXTRACTED_FROM"}
        )
        about = fact.get("about_entities", [])
        if not about:
            about = [
                e.get("name", "") for e in chunk.get("entities", []) if e.get("name")
            ]
        fact_entity_rels.extend(
            _resolve_entity_rels(about, fact_id, "RELATES_TO", entity_name_to_id)
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
    """Build Claim nodes and their relations from a chunk."""
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
    """Build FinancialDataPoint nodes and their relations from a chunk."""
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
    """Derive FiscalPeriod nodes and FOR_PERIOD relations from datapoints."""
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
    """Build Stance and Author nodes with HOLDS_STANCE, ON_ENTITY, BASED_ON relations."""
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

        stance_id = generate_stance_id(author_name, entity_name, as_of_date or "")
        author_id = generate_author_id(author_name, author_type)

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

        holds_stance_rels.append(
            {"from_id": author_id, "to_id": stance_id, "type": "HOLDS_STANCE"}
        )

        entity_id = entity_name_to_id.get(entity_name)
        if entity_id:
            on_entity_rels.append(
                {"from_id": stance_id, "to_id": entity_id, "type": "ON_ENTITY"}
            )

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
    """Build SUPERSEDES relations for stances sharing the same (author, entity)."""
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
    """Build Author node and AUTHORED_BY relation from Source.publisher."""
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


def _build_causal_links(
    chunk: dict[str, Any],
    facts: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    datapoints: list[dict[str, Any]],
    source_id: str,
) -> list[dict[str, str]]:
    """Build CAUSES relation dicts from causal_links in a chunk."""
    causal_links = chunk.get("causal_links", [])
    if not causal_links:
        return []

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
        if link.get("mechanism"):
            rel["mechanism"] = link["mechanism"]
        if link.get("confidence"):
            rel["confidence"] = link["confidence"]

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
    """Build Question nodes and their relations from a chunk."""
    questions: list[dict[str, Any]] = []
    asks_about_rels: list[dict[str, str]] = []
    motivated_by_rels: list[dict[str, str]] = []

    raw_questions = chunk.get("questions", [])
    if not raw_questions:
        return questions, asks_about_rels, motivated_by_rels

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

        asks_about_rels.extend(
            _resolve_entity_rels(
                raw_q.get("about_entities", []),
                question_id,
                "ASKS_ABOUT",
                entity_name_to_id,
            )
        )

        for motivated_content in raw_q.get("motivated_by_contents", []):
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


def _build_next_period_chain(
    fiscal_periods: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build NEXT_PERIOD relations linking consecutive FiscalPeriod nodes."""
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
    """Compute change percentage and direction between two values."""
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

    Groups datapoints by (ticker, metric_key, source_hash) where metric_key
    is resolved via resolve_metric_id when available, falling back to
    metric_name.  Only adds metric_id to the rel dict when resolved.
    """
    dp_to_period: dict[str, str] = {}
    for rel in for_period_rels:
        dp_to_period[rel["from_id"]] = rel["to_id"]

    period_to_label: dict[str, str] = {}
    for fp in fiscal_periods:
        period_to_label[fp["period_id"]] = fp.get("period_label", "")

    groups: dict[tuple[str, str, str], list[tuple[dict[str, Any], str | None]]] = (
        defaultdict(list)
    )
    for dp in financial_datapoints:
        dp_id = dp["datapoint_id"]

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

    trend_rels: list[dict[str, Any]] = []
    for (_ticker, _metric_key, _src), group in groups.items():
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

            trend_rels.append(rel_dict)

    return trend_rels


def _process_chunk(
    chunk: dict[str, Any],
    source_hash: str,
    source_id: str,
    ctx: ChunkProcessingContext,
) -> dict[str, Any]:
    """Process a single chunk and return all node lists and relations."""
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


# ---------------------------------------------------------------------------
# Web-research specific builders
# ---------------------------------------------------------------------------


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


def _build_wr_sources(
    raw_sources: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Build Source nodes from web-research input."""
    sources: list[dict[str, Any]] = []
    url_to_source_id: dict[str, str] = {}

    for src in raw_sources:
        authority = src["authority_level"]
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
        node: dict[str, Any] = {
            "source_id": sid,
            "url": url,
            "title": src.get("title", ""),
            "published": src.get("published_at", ""),
            "source_type": _normalize_source_type(src.get("source_type", "")),
            "authority_level": authority,
            "command_source": "web-research",
        }
        data_source = src.get("data_source", "")
        if data_source:
            node["data_source"] = data_source
        sources.append(node)

    return sources, url_to_source_id


def _build_wr_topics(
    raw_topics: list[dict[str, Any]],
    sources: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Build Topic nodes and Source→Topic TAGGED rels."""
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
        for src_node in sources:
            tagged_rels.append(
                {
                    "from_id": src_node["source_id"],
                    "to_id": tid,
                    "type": "TAGGED",
                }
            )

    return topics, tagged_rels


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
    """Build Fact/Entity nodes and all fact-related relations."""
    facts: list[dict[str, Any]] = []
    entities: list[dict[str, Any]] = []
    source_fact_rels: list[dict[str, str]] = []
    fact_entity_rels: list[dict[str, str]] = []
    extracted_from_fact_rels: list[dict[str, str]] = []
    tagged_rels: list[dict[str, str]] = []
    entity_id_map: dict[str, str] = {}

    for raw_fact in raw_facts:
        content = raw_fact.get("content", "")
        source_url = raw_fact.get("source_url", "")

        if source_url not in url_to_source_id:
            logger.warning(
                "Fact source_url not found in sources, skipping: %s", source_url
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

        source_fact_rels.append({"from_id": sid, "to_id": fid, "type": "STATES_FACT"})
        extracted_from_fact_rels.append(
            {"from_id": fid, "to_id": sid, "type": "EXTRACTED_FROM"}
        )

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
    return facts, entities, fact_rels, tagged_rels, entity_id_map  # type: ignore[return-value]


def _build_wr_claims(
    raw_claims: list[dict[str, Any]],
    url_to_source_id: dict[str, str],
    entity_id_map: dict[str, str],
    existing_entities: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, list[dict[str, str]]],
]:
    """Build Claim/Entity nodes and claim-related relations for web-research."""
    claims: list[dict[str, Any]] = []
    new_entities: list[dict[str, Any]] = []
    source_claim_rels: list[dict[str, str]] = []
    claim_entity_rels: list[dict[str, str]] = []

    for raw_claim in raw_claims:
        content = raw_claim.get("content", "")
        if not content:
            continue
        source_url = raw_claim.get("source_url", "")

        if source_url and source_url not in url_to_source_id:
            logger.warning(
                "Claim source_url not found in sources, skipping: %s", source_url
            )
            continue

        sid = url_to_source_id.get(source_url, "")
        cid = generate_claim_id(content)

        claims.append(
            {
                "claim_id": cid,
                "content": content,
                "source_id": sid,
                "claim_type": raw_claim.get("claim_type", ""),
                "sentiment": raw_claim.get("sentiment", ""),
                "category": "web-research",
            }
        )

        if sid:
            source_claim_rels.append(
                {"from_id": sid, "to_id": cid, "type": "MAKES_CLAIM"}
            )

        for ent in raw_claim.get("about_entities", []):
            ename = ent.get("name", "")
            etype = ent.get("entity_type", "")
            ekey = f"{ename}::{etype}"
            eid = generate_entity_id(ename, etype)

            if ekey not in entity_id_map:
                entity_id_map[ekey] = eid
                new_entity = {
                    "entity_id": eid,
                    "name": ename,
                    "entity_type": etype,
                    "entity_key": ekey,
                }
                new_entities.append(new_entity)
                existing_entities.append(new_entity)

            claim_entity_rels.append({"from_id": cid, "to_id": eid, "type": "ABOUT"})

    claim_rels = {
        "source_claim": source_claim_rels,
        "claim_entity": claim_entity_rels,
    }
    return claims, new_entities, claim_rels


def _build_wr_causal_rels(
    causal_links: list[dict[str, Any]],
    entity_id_map: dict[str, str],
) -> dict[str, list[dict[str, str]]]:
    """Build CAUSES / CONTRADICTS / SUPPORTED_BY relations from explicit input."""
    allowed = {"CAUSES", "CONTRADICTS", "SUPPORTED_BY", "DERIVED_FROM", "INFLUENCES"}
    causes_rels: list[dict[str, str]] = []

    for link in causal_links:
        rel_type = link.get("rel_type", "CAUSES")
        if rel_type not in allowed:
            logger.warning("Invalid causal rel_type: %s, skipping", rel_type)
            continue

        from_key = link.get("from_entity", "")
        to_key = link.get("to_entity", "")

        from_id = entity_id_map.get(from_key, "")
        to_id = entity_id_map.get(to_key, "")

        if not from_id or not to_id:
            logger.warning(
                "Causal link entity not found: %s → %s, skipping", from_key, to_key
            )
            continue

        rel_data: dict[str, str] = {
            "from_id": from_id,
            "to_id": to_id,
            "type": rel_type,
        }
        if link.get("mechanism"):
            rel_data["mechanism"] = link["mechanism"]
        if link.get("via"):
            rel_data["via"] = link["via"]

        causes_rels.append(rel_data)

    return {"causal": causes_rels} if causes_rels else {}


# ---------------------------------------------------------------------------
# Topic-discovery specific builders
# ---------------------------------------------------------------------------


def _magnitude_from_score(total: int) -> str:
    """Determine magnitude label from a total suggestion score."""
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
    """Build a Claim node dict from a single topic-discovery suggestion."""
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
    """Build Fact nodes and STATES_FACT relations from search trends."""
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
    """Build Entity nodes and claim-entity relations from suggested symbols."""
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


# ---------------------------------------------------------------------------
# Wealth-scrape helpers
# ---------------------------------------------------------------------------


def _parse_frontmatter_from_text(text: str) -> dict[str, str] | None:
    """Parse YAML frontmatter key-value pairs from markdown text.

    Supports both quoted (``key: 'value'``) and unquoted (``key: value``)
    formats.  Does **not** use PyYAML.
    """
    m = _FRONTMATTER_RE.search(text)
    if not m:
        return None
    frontmatter: dict[str, str] = {}
    for line in m.group(1).splitlines():
        kv = _KV_RE.match(line.strip())
        if kv is None:
            continue
        key = kv.group(1)
        raw_value = kv.group(2).strip()
        # Strip surrounding single or double quotes
        if len(raw_value) >= 2 and (
            (raw_value[0] == "'" and raw_value[-1] == "'")
            or (raw_value[0] == '"' and raw_value[-1] == '"')
        ):
            raw_value = raw_value[1:-1]
        frontmatter[key] = raw_value
    return frontmatter if frontmatter else None


def _parse_yaml_frontmatter(file_path: Path) -> dict[str, str] | None:
    """Parse YAML frontmatter from a markdown file."""
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Failed to read file %s: %s", file_path, exc)
        return None
    return _parse_frontmatter_from_text(text)


def _load_wealth_themes(
    config_path: Path = WEALTH_THEME_CONFIG_PATH,
) -> dict[str, Any]:
    """Load wealth-management theme configuration.

    Returns the ``themes`` dict from the JSON config, or empty dict on failure.
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
    """Build a reverse-lookup dict from source key to (theme_key, name_en)."""
    lookup: dict[str, tuple[str, str]] = {}
    for theme_key, theme_data in themes.items():
        name_en = theme_data.get("name_en", theme_key)
        for source in theme_data.get("target_sources", []):
            lookup[source] = (theme_key, name_en)
    return lookup


def _match_domain_to_theme(
    domain: str,
    themes: dict[str, Any],
) -> tuple[str, str] | None:
    """Match a domain name to a wealth theme via ``target_sources``.

    Uses a reverse-lookup dictionary for O(1) exact matching on source keys,
    with a linear fallback for substring matching.
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


def _map_wealth_theme_common(
    theme_key: str,
    theme_data: dict[str, Any],
    sources: list[dict[str, Any]],
    topics: list[dict[str, Any]],
    tagged_rels: list[dict[str, str]],
    *,
    extra_source_fields: dict[str, str] | None = None,
) -> tuple[str, list[str], list[dict[str, Any]]]:
    """Process the common theme-loop block shared by backfill and incremental."""
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

    Returns the source_id if the article was processed, or ``None`` if skipped.
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


def _process_domain_dir(
    domain_dir: Path,
    themes: dict[str, Any],
) -> dict[str, Any] | None:
    """Process a single domain subdirectory for wealth-scrape backfill.

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

    Parameters
    ----------
    dir_path : Path
        Root directory to scan.
    theme_config_path : Path
        Path to the wealth-management theme configuration JSON.

    Returns
    -------
    list[dict[str, Any]]
        List of mapped dicts, one per domain.
    """
    if not dir_path.is_dir():
        logger.error("Not a directory: %s", dir_path)
        return []

    themes = _load_wealth_themes(theme_config_path)
    results: list[dict[str, Any]] = []

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
