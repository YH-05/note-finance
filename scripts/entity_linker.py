#!/usr/bin/env python3
"""Entity Linker for Neo4j instances (v3.0).

Resolves extracted entity/concept names to existing nodes in Neo4j
using a multi-stage matching strategy aligned with research-neo4j v3.0
ontology (EntityType consolidation, Identifier pattern, Alias fallback).

パイプライン位置
-----------------

ステップ2: entity_key 事前解決（neo4j_loader.py の前処理）

  emit_research_queue.py → entity_linker.py → neo4j_loader.py

本スクリプトは neo4j_loader.py がグラフに書き込む前に entity_type の
正規化と entity_key 解決を行う中間処理を担う。

Matching stages
---------------

Stage 1: entity_key exact match (``Name::type``)
Stage 2: Full-text search via ``research_entity_fulltext`` index
Stage 3: Alias fallback via ``research_alias_fulltext`` index
Stage 4 (optional): multilingual-e5-large embedding similarity

Usage
-----
::

    python scripts/entity_linker.py --input extracted.json --output resolved.json
    python scripts/entity_linker.py --input extracted.json --instance research

Input JSON format::

    {
      "entities": [
        {"name": "トヨタ自動車", "entity_type": "company", "ticker": "7203"}
      ],
      "concepts": [
        {"name": "SNS集客", "category": "AcquisitionChannel"}
      ]
    }

Output JSON format::

    {
      "entities": [
        {"name": "トヨタ自動車", "entity_type": "company",
         "canonical_type": "company",
         "resolved": true, "entity_key": "トヨタ自動車::company",
         "match_layer": "exact",
         "identifier": {"type": "ticker", "value": "7203"}}
      ],
      "concepts": [
        {"name": "SNS集客", "category": "AcquisitionChannel",
         "resolved": true, "concept_id": "abc123",
         "match_layer": "embedding"}
      ]
    }

"""

from __future__ import annotations

import argparse
import functools
import json
import logging
import math
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse, urlunparse

import yaml
from neo4j import GraphDatabase
from neo4j.exceptions import ClientError

try:
    import anthropic  # type: ignore[import-untyped]
except ImportError:
    anthropic = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

try:
    from utils_core.logging.config import get_logger

    logger = get_logger(__name__)
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default config directory
_DEFAULT_CONFIG_DIR = (
    Path(__file__).resolve().parent.parent / "data" / "config" / "neo4j-instances"
)

# Default entity-linker config path (v3.0)
_DEFAULT_LINKER_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "lifecycle-state"
    / "research"
    / "entity-linker-config.yaml"
)

SIMILARITY_THRESHOLD_APOC = 0.8
SIMILARITY_THRESHOLD_EMBEDDING = 0.8

# Pattern to match environment variable references like ${VAR_NAME}
_ENV_VAR_PATTERN = re.compile(r"^\$\{([^}]+)\}$")


# ---------------------------------------------------------------------------
# v3.0 EntityType Consolidation (42 -> 14 canonical types)
# ---------------------------------------------------------------------------

# Maps legacy / fine-grained entity_type values to the 14 canonical types
# defined in ontology.yaml (via ontology_loader).
# SSoT: data/lifecycle-state/research/ontology.yaml
from ontology_loader import load_consolidation_mapping  # noqa: E402

ENTITY_TYPE_CONSOLIDATION: dict[str, str] = load_consolidation_mapping()

# The 14 canonical types (for validation)
VALID_ENTITY_TYPES: frozenset[str] = frozenset(
    {
        "company",
        "technology",
        "organization",
        "person",
        "index",
        "indicator",
        "instrument",
        "commodity",
        "country",
        "sector",
        "concept",
        "regulation",
        "broker",
        "product",
    }
)

# Per-entity-type normalization rule descriptions (informational for logging)
NORMALIZATION_RULES: dict[str, str] = {
    "company": "公式英語表記またはティッカー",
    "technology": "公式英語表記",
    "organization": "公式英語略称",
    "person": "アルファベットフルネーム",
    "index": "公式略称",
    "indicator": "公式略称",
    "instrument": "ティッカーまたは公式名称",
    "commodity": "公式英語名",
    "country": "英語正式名",
    "sector": "GICS セクター名",
    "concept": "公式英語表記",
    "regulation": "公式英語名",
    "broker": "公式英語表記",
    "product": "公式英語名",
}


# ---------------------------------------------------------------------------
# v3.0 Search Config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LinkerSearchConfig:
    """Search parameters loaded from entity-linker-config.yaml.

    Attributes
    ----------
    fulltext_index
        Name of the Entity fulltext index (stage 2).
    alias_fulltext_index
        Name of the Alias fulltext index (stage 3).
    similarity_threshold
        Jaro-Winkler similarity threshold for fuzzy matching.
    max_candidates
        Maximum candidate nodes returned from fulltext queries.
    fulltext_score_threshold
        Minimum score from fulltext index to consider a candidate.
    """

    fulltext_index: str = "research_entity_fulltext"
    alias_fulltext_index: str = "research_alias_fulltext"
    similarity_threshold: float = 0.85
    max_candidates: int = 10
    fulltext_score_threshold: float = 0.5


def load_linker_config(
    config_path: Path | None = None,
) -> LinkerSearchConfig:
    """Load entity-linker search config from YAML.

    Parameters
    ----------
    config_path
        Path to ``entity-linker-config.yaml``.
        Defaults to ``data/lifecycle-state/research/entity-linker-config.yaml``.

    Returns
    -------
    LinkerSearchConfig
        Parsed search configuration.
    """
    path = config_path or _DEFAULT_LINKER_CONFIG_PATH
    if not path.exists():
        logger.debug(
            "Linker config not found at %s, using defaults",
            path,
        )
        return LinkerSearchConfig()

    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    search = data.get("search", {})
    return LinkerSearchConfig(
        fulltext_index=search.get("fulltext_index", "research_entity_fulltext"),
        alias_fulltext_index=search.get(
            "alias_fulltext_index",
            "research_alias_fulltext",
        ),
        similarity_threshold=search.get("similarity_threshold", 0.85),
        max_candidates=search.get("max_candidates", 10),
        fulltext_score_threshold=search.get("fulltext_score_threshold", 0.5),
    )


# ---------------------------------------------------------------------------
# Node Resolution Config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _NodeResolveConfig:
    """Configuration for resolving a specific node type (Entity or Concept)."""

    label: str  # "Entity" or "Concept"
    id_key: str  # "entity_id" or "concept_id"
    key_key: str | None  # "entity_key" or None
    alias_index: str  # "alias_fulltext" or v3.0 index name
    node_index: str  # "entity_fulltext" or "concept_fulltext"


_ENTITY_CONFIG = _NodeResolveConfig(
    label="Entity",
    id_key="entity_id",
    key_key="entity_key",
    alias_index="alias_fulltext",
    node_index="entity_fulltext",
)

_CONCEPT_CONFIG = _NodeResolveConfig(
    label="Concept",
    id_key="concept_id",
    key_key=None,
    alias_index="alias_fulltext",
    node_index="concept_fulltext",
)


def _make_v3_entity_config(search_config: LinkerSearchConfig) -> _NodeResolveConfig:
    """Create a v3.0 Entity resolve config using search config index names.

    Parameters
    ----------
    search_config
        Search configuration loaded from entity-linker-config.yaml.

    Returns
    -------
    _NodeResolveConfig
        Entity resolve config using v3.0 index names.
    """
    return _NodeResolveConfig(
        label="Entity",
        id_key="entity_id",
        key_key="entity_key",
        alias_index=search_config.alias_fulltext_index,
        node_index=search_config.fulltext_index,
    )


# ---------------------------------------------------------------------------
# v3.0 Name Normalization
# ---------------------------------------------------------------------------


def normalize_name(name: str) -> str:
    """Apply general normalization rules to an entity name.

    Rules (from ontology.yaml normalization_rules.general):

    1. Convert fullwidth alphanumeric characters to halfwidth.
    2. Strip leading/trailing whitespace and collapse internal runs.
    3. Strip trailing punctuation (。、．，).

    Parameters
    ----------
    name
        Raw entity name.

    Returns
    -------
    str
        Normalized name.
    """
    # Rule 1: fullwidth -> halfwidth (NFKC normalizes CJK compatibility chars)
    normalized = unicodedata.normalize("NFKC", name)

    # Rule 2: strip whitespace, collapse internal runs
    normalized = re.sub(r"\s+", " ", normalized).strip()

    # Rule 3: strip trailing CJK punctuation and trailing commas/semicolons
    # Preserve periods (.) that may be part of abbreviations like "Inc."
    normalized = re.sub(r"[。、．，,;:]+$", "", normalized)

    return normalized


def consolidate_entity_type(raw_type: str) -> str:
    """Map a raw entity_type to one of the 14 canonical types.

    Parameters
    ----------
    raw_type
        Entity type as extracted (may be a legacy fine-grained type).

    Returns
    -------
    str
        Canonical entity type.  Returns the input lowercased if not
        found in the consolidation mapping.
    """
    key = raw_type.lower().strip()
    canonical = ENTITY_TYPE_CONSOLIDATION.get(key)
    if canonical is None:
        logger.warning(
            "Unknown entity_type '%s', passing through as-is",
            raw_type,
        )
        return key
    if canonical != key:
        logger.debug(
            "Consolidated entity_type: %s -> %s",
            raw_type,
            canonical,
        )
    return canonical


def build_entity_key(name: str, entity_type: str) -> str:
    """Build a v3.0 entity_key from name and canonical entity_type.

    Format: ``{name}::{entity_type}``

    Parameters
    ----------
    name
        Normalized entity name.
    entity_type
        Canonical entity type (one of the 14 valid types).

    Returns
    -------
    str
        Entity key in ``Name::type`` format.
    """
    return f"{name}::{entity_type}"


# ---------------------------------------------------------------------------
# v3.0 Identifier Support
# ---------------------------------------------------------------------------


def _build_identifier_ref(entity: dict[str, Any]) -> dict[str, str] | None:
    """Build an Identifier node reference if the entity has a ticker.

    The Identifier node is not created directly here; it is emitted as
    metadata for ``emit_research_queue.py`` to handle via the classification
    post-processor.

    Parameters
    ----------
    entity
        Entity dict that may contain a ``ticker`` field.

    Returns
    -------
    dict or None
        Identifier reference with ``type``, ``value``, and ``scheme``
        fields, or None if no ticker is present.
    """
    ticker = entity.get("ticker")
    if not ticker:
        return None

    return {
        "type": "ticker",
        "value": str(ticker).strip(),
        "scheme": "exchange_ticker",
    }


# ---------------------------------------------------------------------------
# Instance Config Loader
# ---------------------------------------------------------------------------


def load_instance_config(
    instance: str,
    config_dir: Path | None = None,
) -> dict[str, str]:
    """Load Neo4j instance connection config from YAML.

    Parameters
    ----------
    instance
        Instance name (e.g. "creator", "research", "note").
    config_dir
        Directory containing ``{instance}.yaml`` files.
        Defaults to ``data/config/neo4j-instances/``.

    Returns
    -------
    dict[str, str]
        Connection parameters with keys: ``bolt_uri``, ``user``, ``password``.

    Raises
    ------
    FileNotFoundError
        If the YAML file for the instance does not exist.
    ValueError
        If a ``${ENV_VAR}`` password reference cannot be resolved.
    """
    # Validate instance name to prevent path traversal (CWE-22)
    if not re.match(r"^[a-zA-Z0-9_-]{1,64}$", instance):
        msg = f"Invalid instance name: {instance!r}"
        raise ValueError(msg)

    cfg_dir = config_dir or _DEFAULT_CONFIG_DIR
    yaml_path = cfg_dir / f"{instance}.yaml"

    if not yaml_path.exists():
        msg = f"Instance config not found: {instance} ({yaml_path})"
        raise FileNotFoundError(msg)

    with yaml_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    conn = data["connection"]
    password = conn["password"]

    # Resolve environment variable references
    env_match = _ENV_VAR_PATTERN.match(str(password))
    if env_match:
        env_var = env_match.group(1)
        resolved = os.environ.get(env_var)
        if resolved is None:
            msg = (
                f"Environment variable {env_var} is not set "
                f"(required by {instance}.yaml)"
            )
            raise ValueError(msg)
        password = resolved

    return {
        "bolt_uri": conn["bolt_uri"],
        "user": conn["user"],
        "password": password,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mask_uri(uri: str) -> str:
    """Mask credentials in a bolt URI for safe logging."""
    parsed = urlparse(uri)
    if parsed.password:
        host_port = (
            f"{parsed.hostname}:{parsed.port}" if parsed.port else parsed.hostname
        )
        masked = parsed._replace(netloc=f"{parsed.username}@{host_port}")
        return urlunparse(masked)
    return uri


def _build_result(
    row: dict[str, Any],
    config: _NodeResolveConfig,
    match_layer: str,
    **extra: Any,
) -> dict[str, Any]:
    """Build a resolution result dict from a query row."""
    result: dict[str, Any] = {
        config.id_key: row["id"],
        "matched_name": row["name"],
        "match_layer": match_layer,
    }
    if config.key_key and "key" in row:
        result[config.key_key] = row["key"]
    result.update(extra)
    return result


# ---------------------------------------------------------------------------
# Neo4j Connection
# ---------------------------------------------------------------------------


class Neo4jClient:
    """Generic Neo4j client for any instance.

    Parameters
    ----------
    uri
        Neo4j bolt URI (e.g. ``bolt://localhost:7689``).
    user
        Neo4j user name.
    password
        Neo4j password.
    """

    def __init__(
        self,
        uri: str = "bolt://localhost:7689",
        user: str = "neo4j",
        password: str = "",
    ) -> None:
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        """Close the Neo4j driver connection."""
        self.driver.close()

    def query(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        """Run a read-only Cypher query and return results as dicts.

        Uses ``session.execute_read`` for automatic retry on transient
        errors and read-replica routing.  Returns an empty list when
        a fulltext schema index referenced in the query is missing.
        """

        def _run(tx: Any) -> list[dict[str, Any]]:
            return [dict(r) for r in tx.run(cypher, **params)]

        with self.driver.session() as session:
            try:
                return session.execute_read(_run)
            except ClientError as e:
                if "no such fulltext schema index" in str(e):
                    logger.debug("Full-text index not found, skipping")
                    return []
                raise


# ---------------------------------------------------------------------------
# 3-Stage Linking (v3.0)
# ---------------------------------------------------------------------------


def _escape_lucene(text: str) -> str:
    """Lucene 特殊文字をエスケープする.

    Neo4j の fulltext index は Lucene を使用するため、
    クエリ文字列に含まれる特殊文字をエスケープする必要がある。
    """
    special_chars = r'+-&|!(){}[]^"~*?:\/'
    escaped = []
    for ch in text:
        if ch in special_chars:
            escaped.append(f"\\{ch}")
        else:
            escaped.append(ch)
    return "".join(escaped)


def _return_clause(config: _NodeResolveConfig) -> str:
    """Build the RETURN clause based on node config."""
    parts = [f"n.{config.id_key} AS id"]
    if config.key_key:
        parts.append(f"n.{config.key_key} AS key")
    parts.append("n.name AS name")
    return ", ".join(parts)


def _resolve_by_text(
    client: Neo4jClient,
    name: str,
    config: _NodeResolveConfig,
    *,
    entity_key: str | None = None,
    search_config: LinkerSearchConfig | None = None,
) -> dict[str, Any] | None:
    """Resolve a node using the 3-stage linking strategy.

    This is the unified resolution logic for both Entity and Concept
    nodes, parameterised by ``config``.

    Stages (v3.0)
    --------------
    Stage 1: entity_key exact match (Entity only) + name exact match
    Stage 2: Full-text search on Entity/Concept node name index
    Stage 3: Alias fulltext search + ALIAS_OF traversal

    Parameters
    ----------
    client
        Neo4j client.
    name
        Name to resolve.
    config
        Node type configuration.
    entity_key
        Optional composite key (``name::type``) for Entity-only exact
        match.  Ignored for Concept.
    search_config
        Optional v3.0 search configuration.  When provided, uses the
        configured thresholds instead of defaults.
    """
    ret = _return_clause(config)
    ft_threshold = search_config.fulltext_score_threshold if search_config else 0.3
    sim_threshold = (
        search_config.similarity_threshold
        if search_config
        else SIMILARITY_THRESHOLD_APOC
    )
    max_candidates = search_config.max_candidates if search_config else 10

    # Stage 1a (Entity only): entity_key exact match
    if entity_key is not None and config.key_key is not None:
        results = client.query(
            f"MATCH (n:{config.label} {{{config.key_key}: $key}}) RETURN {ret}",
            key=entity_key,
        )
        if results:
            return _build_result(results[0], config, "exact")

    # Stage 1b: name exact match
    results = client.query(
        f"MATCH (n:{config.label} {{name: $name}}) RETURN {ret}",
        name=name,
    )
    if results:
        layer = "exact_name" if entity_key is not None else "exact"
        return _build_result(results[0], config, layer)

    # Stage 2: Full-text search on node name index + similarity filter
    escaped_name = _escape_lucene(name)
    results = client.query(
        f'CALL db.index.fulltext.queryNodes("{config.node_index}", $ft_name) '
        f"YIELD node AS n, score WHERE score > $ft_threshold "
        f"WITH n, score, "
        f"     apoc.text.levenshteinSimilarity(n.name, $name) AS lev "
        f"WHERE lev > $sim_threshold "
        f"RETURN {ret}, lev AS similarity "
        f"ORDER BY lev DESC LIMIT $max_candidates",
        ft_name=escaped_name,
        name=name,
        ft_threshold=ft_threshold,
        sim_threshold=sim_threshold,
        max_candidates=max_candidates,
    )
    if results:
        return _build_result(
            results[0],
            config,
            "fulltext",
            similarity=results[0]["similarity"],
        )

    # Stage 3: Alias fulltext search + ALIAS_OF traversal
    results = client.query(
        f'CALL db.index.fulltext.queryNodes("{config.alias_index}", $ft_name) '
        f"YIELD node AS alias, score WHERE score > $ft_threshold "
        f"MATCH (alias)-[:ALIAS_OF]->(n:{config.label}) "
        f"WITH n, alias, score, "
        f"     apoc.text.levenshteinSimilarity(alias.name, $name) AS lev "
        f"WHERE lev > $sim_threshold "
        f"RETURN {ret}, alias.name AS matched_alias, lev AS similarity "
        f"ORDER BY lev DESC LIMIT $max_candidates",
        ft_name=escaped_name,
        name=name,
        ft_threshold=ft_threshold,
        sim_threshold=sim_threshold,
        max_candidates=max_candidates,
    )
    if results:
        return _build_result(
            results[0],
            config,
            "alias",
            matched_alias=results[0]["matched_alias"],
            similarity=results[0]["similarity"],
        )

    return None


def resolve_entity_by_text(
    client: Neo4jClient,
    name: str,
    entity_type: str,
    *,
    search_config: LinkerSearchConfig | None = None,
    use_v3: bool = False,
) -> dict[str, Any] | None:
    """Resolve entity by 3-stage matching (exact, fulltext, alias).

    Parameters
    ----------
    client
        Neo4j client.
    name
        Extracted entity name (already normalized by LLM).
    entity_type
        Entity type (may be legacy fine-grained or canonical).
    search_config
        Optional v3.0 search configuration.
    use_v3
        When True, applies v3.0 EntityType consolidation and uses
        v3.0 fulltext index names from ``search_config``.

    Returns
    -------
    dict or None
        Resolved entity info, or None if no match found.
    """
    if use_v3:
        canonical_type = consolidate_entity_type(entity_type)
        normalized = normalize_name(name)
        entity_key = build_entity_key(normalized, canonical_type)
        config = (
            _make_v3_entity_config(search_config) if search_config else _ENTITY_CONFIG
        )
        result = _resolve_by_text(
            client,
            normalized,
            config,
            entity_key=entity_key,
            search_config=search_config,
        )
        if result is not None:
            result["canonical_type"] = canonical_type
        return result

    # Legacy path (backward compatible)
    return _resolve_by_text(
        client,
        name,
        _ENTITY_CONFIG,
        entity_key=f"{name}::{entity_type}",
        search_config=search_config,
    )


def resolve_concept_by_text(
    client: Neo4jClient,
    name: str,
    *,
    search_config: LinkerSearchConfig | None = None,
) -> dict[str, Any] | None:
    """Resolve concept by exact match, fulltext, and alias fallback.

    Parameters
    ----------
    client
        Neo4j client.
    name
        Extracted concept name.
    search_config
        Optional v3.0 search configuration.

    Returns
    -------
    dict or None
        Resolved concept info, or None if no match found.
    """
    return _resolve_by_text(
        client,
        name,
        _CONCEPT_CONFIG,
        search_config=search_config,
    )


# ---------------------------------------------------------------------------
# Layer 4: Embedding Matching
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def _load_embedding_model() -> Any:
    """Load multilingual-e5-large model (lazy, cached via lru_cache)."""
    try:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading multilingual-e5-large...")
        model = SentenceTransformer("intfloat/multilingual-e5-large", device="cpu")
        logger.info("Model loaded.")
        return model
    except ImportError:
        logger.warning("sentence-transformers not installed, skipping embedding layer")
        return None


def _resolve_by_embedding_vector_index(
    client: Neo4jClient,
    target_emb: Any,
    config: _NodeResolveConfig,
) -> dict[str, Any] | None:
    """Attempt resolution via Neo4j Vector Index (5.11+).

    Returns None if the vector index does not exist.
    """
    ret = _return_clause(config)
    index_name = f"{config.label.lower()}_embedding_idx"

    try:
        results = client.query(
            f'CALL db.index.vector.queryNodes("{index_name}", $top_k, $embedding) '
            f"YIELD node AS n, score "
            f"WHERE score >= $threshold "
            f"RETURN {ret}, score AS similarity",
            top_k=5,
            embedding=target_emb.tolist(),
            threshold=SIMILARITY_THRESHOLD_EMBEDDING,
        )
        if results:
            return _build_result(
                results[0],
                config,
                "embedding",
                similarity=round(results[0]["similarity"], 4),
            )
    except Exception:
        logger.debug(
            "Vector index '%s' not available, falling back to brute-force",
            index_name,
        )

    return None


def _resolve_by_embedding_brute_force(
    client: Neo4jClient,
    target_emb: Any,
    config: _NodeResolveConfig,
) -> dict[str, Any] | None:
    """Brute-force embedding resolution with vectorized numpy computation."""
    import numpy as np

    ret = _return_clause(config)
    candidates = client.query(
        f"MATCH (n:{config.label}) WHERE n.embedding IS NOT NULL "
        f"RETURN {ret}, n.embedding AS emb"
    )
    if not candidates:
        return None

    # Vectorized cosine similarity (single BLAS operation)
    embs = np.array([c["emb"] for c in candidates], dtype=np.float32)
    sims = embs @ target_emb  # (N,) — embeddings are already normalized
    best_idx = int(np.argmax(sims))
    best_sim = float(sims[best_idx])

    if best_sim >= SIMILARITY_THRESHOLD_EMBEDDING:
        return _build_result(
            candidates[best_idx],
            config,
            "embedding",
            similarity=round(best_sim, 4),
        )
    return None


def resolve_by_embedding(
    client: Neo4jClient,
    name: str,
    target_type: Literal["entity", "concept"],
    model: Any,
) -> dict[str, Any] | None:
    """Resolve by embedding cosine similarity.

    Attempts Neo4j Vector Index first, then falls back to brute-force
    numpy computation.

    Parameters
    ----------
    client
        Neo4j client.
    name
        Name to resolve.
    target_type
        ``"entity"`` or ``"concept"``.
    model
        SentenceTransformer model.

    Returns
    -------
    dict or None
        Best match above threshold, or None.
    """
    if model is None:
        return None

    config = _ENTITY_CONFIG if target_type == "entity" else _CONCEPT_CONFIG
    target_emb = model.encode(name, normalize_embeddings=True)

    # Try Vector Index (fast, DB-side top-k)
    result = _resolve_by_embedding_vector_index(client, target_emb, config)
    if result is not None:
        return result

    # Fallback: brute-force with vectorized numpy
    return _resolve_by_embedding_brute_force(client, target_emb, config)


# ---------------------------------------------------------------------------
# Batch Exact Match Helpers
# ---------------------------------------------------------------------------


def _batch_exact_entities(
    client: Neo4jClient,
    entities: list[dict[str, Any]],
    *,
    use_v3: bool = False,
) -> dict[str, dict[str, Any]]:
    """Batch exact match for entities (2 queries instead of 2*N).

    Parameters
    ----------
    client
        Neo4j client.
    entities
        List of entity dicts with ``name`` and ``entity_type`` fields.
    use_v3
        When True, applies v3.0 EntityType consolidation and name
        normalization before building entity keys.

    Returns
    -------
    dict[str, dict[str, Any]]
        Mapping of ``name::type`` -> resolution result.
    """
    if not entities:
        return {}

    matches: dict[str, dict[str, Any]] = {}

    # Build keys with optional v3.0 normalization
    def _make_key(e: dict[str, Any]) -> str:
        if use_v3:
            canonical_type = consolidate_entity_type(e["entity_type"])
            normalized_name = normalize_name(e["name"])
            return build_entity_key(normalized_name, canonical_type)
        return f"{e['name']}::{e['entity_type']}"

    keys = [_make_key(e) for e in entities]

    # Step 1: entity_key exact match
    results = client.query(
        "UNWIND $keys AS key "
        "MATCH (e:Entity {entity_key: key}) "
        "RETURN key, e.entity_id AS id, e.entity_key AS entity_key, e.name AS name",
        keys=keys,
    )
    for r in results:
        matches[r["key"]] = {
            "entity_id": r["id"],
            "entity_key": r["entity_key"],
            "matched_name": r["name"],
            "match_layer": "exact",
        }

    # Step 2: name exact match for unresolved
    unresolved = [(e, _make_key(e)) for e in entities if _make_key(e) not in matches]
    if unresolved:
        if use_v3:
            names = list({normalize_name(e["name"]) for e, _ in unresolved})
        else:
            names = list({e["name"] for e, _ in unresolved})
        name_results = client.query(
            "UNWIND $names AS n "
            "MATCH (e:Entity {name: n}) "
            "RETURN n AS input_name, e.entity_id AS id, "
            "       e.entity_key AS entity_key, e.name AS name",
            names=names,
        )
        for r in name_results:
            for e, k in unresolved:
                check_name = normalize_name(e["name"]) if use_v3 else e["name"]
                if check_name == r["input_name"] and k not in matches:
                    matches[k] = {
                        "entity_id": r["id"],
                        "entity_key": r["entity_key"],
                        "matched_name": r["name"],
                        "match_layer": "exact_name",
                    }

    return matches


def _batch_exact_concepts(
    client: Neo4jClient,
    concepts: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Batch exact match for concepts (1 query instead of N).

    Returns a dict mapping concept name -> resolution result.
    """
    if not concepts:
        return {}

    names = list({c["name"] for c in concepts})
    results = client.query(
        "UNWIND $names AS n "
        "MATCH (c:Concept {name: n}) "
        "RETURN n AS input_name, c.concept_id AS id, c.name AS name",
        names=names,
    )
    return {
        r["input_name"]: {
            "concept_id": r["id"],
            "matched_name": r["name"],
            "match_layer": "exact",
        }
        for r in results
    }


# ---------------------------------------------------------------------------
# Main Resolver
# ---------------------------------------------------------------------------


def resolve_all(
    client: Neo4jClient,
    data: dict[str, Any],
    use_embedding: bool = True,
    *,
    use_v3: bool = False,
    search_config: LinkerSearchConfig | None = None,
) -> dict[str, Any]:
    """Resolve all entities and concepts in input data.

    Uses batch exact matching to reduce DB round-trips, then falls
    back to sequential fuzzy + embedding for unresolved items.

    Parameters
    ----------
    client
        Neo4j client.
    data
        Input JSON with "entities" and "concepts" lists.
    use_embedding
        Whether to use embedding layer (layer 4).
    use_v3
        When True, enables v3.0 features: EntityType consolidation,
        name normalization, 3-stage linking, and Identifier output.
    search_config
        Optional v3.0 search configuration.

    Returns
    -------
    dict
        Resolved data with match info added to each entity/concept.
    """
    model = _load_embedding_model() if use_embedding else None
    entities = data.get("entities", [])
    concepts = data.get("concepts", [])

    # Phase 1: Batch exact match (O(1) queries per type)
    entity_exact = _batch_exact_entities(client, entities, use_v3=use_v3)
    concept_exact = _batch_exact_concepts(client, concepts)

    # Phase 2: Sequential fuzzy + embedding for unresolved
    resolved_entities = _resolve_items(
        client,
        entities,
        entity_exact,
        "entity",
        model,
        use_v3=use_v3,
        search_config=search_config,
    )
    resolved_concepts = _resolve_items(
        client,
        concepts,
        concept_exact,
        "concept",
        model,
        search_config=search_config,
    )

    # Preserve all input fields (sources, facts, tips, stories, genre, etc.)
    # and overlay resolved entities/concepts
    result = {k: v for k, v in data.items() if k not in ("entities", "concepts")}
    result.update(
        {
            "entities": resolved_entities,
            "concepts": resolved_concepts,
            "serves_as": data.get("serves_as", []),
            "concept_relations": data.get("concept_relations", []),
            "stats": {
                "entities": _compute_stats(resolved_entities),
                "concepts": _compute_stats(resolved_concepts),
            },
        }
    )
    return result


def _resolve_items(
    client: Neo4jClient,
    items: list[dict[str, Any]],
    exact_matches: dict[str, dict[str, Any]],
    item_type: Literal["entity", "concept"],
    model: Any,
    *,
    use_v3: bool = False,
    search_config: LinkerSearchConfig | None = None,
) -> list[dict[str, Any]]:
    """Resolve items using pre-computed exact matches + sequential fallback.

    Parameters
    ----------
    client
        Neo4j client.
    items
        List of entity or concept dicts.
    exact_matches
        Pre-computed batch exact match results.
    item_type
        ``"entity"`` or ``"concept"``.
    model
        SentenceTransformer model (or None).
    use_v3
        When True, enables v3.0 EntityType consolidation, name
        normalization, and Identifier output for entities.
    search_config
        Optional v3.0 search configuration.
    """
    resolved = []
    for item in items:
        name = item["name"]

        if item_type == "entity":
            if use_v3:
                canonical_type = consolidate_entity_type(item["entity_type"])
                normalized_name = normalize_name(name)
                lookup_key = build_entity_key(normalized_name, canonical_type)
            else:
                lookup_key = f"{name}::{item['entity_type']}"
        else:
            lookup_key = name

        # Check batch exact match first
        match = exact_matches.get(lookup_key)

        # Fallback: sequential fuzzy text matching
        if match is None:
            if item_type == "entity":
                match = resolve_entity_by_text(
                    client,
                    name,
                    item["entity_type"],
                    search_config=search_config,
                    use_v3=use_v3,
                )
            else:
                match = resolve_concept_by_text(
                    client,
                    name,
                    search_config=search_config,
                )

        # Fallback: embedding
        if match is None and model is not None:
            match = resolve_by_embedding(client, name, item_type, model)

        if match is not None:
            item.update({"resolved": True, **match})
        else:
            item["resolved"] = False
            item["match_layer"] = "new"

        # v3.0: Add canonical_type and identifier for entities
        if item_type == "entity" and use_v3:
            item["canonical_type"] = consolidate_entity_type(item["entity_type"])
            identifier = _build_identifier_ref(item)
            if identifier is not None:
                item["identifier"] = identifier

        resolved.append(item)
        layer = item.get("match_layer", "new")
        label = "Entity" if item_type == "entity" else "Concept"
        logger.info(
            "%s: %s -> %s (%s)",
            label,
            name,
            item.get("matched_name", "NEW"),
            layer,
        )

    return resolved


def _compute_stats(items: list[dict[str, Any]]) -> dict[str, int]:
    """Compute resolution statistics."""
    stats: dict[str, int] = {"total": len(items), "resolved": 0, "new": 0}
    for item in items:
        if item.get("resolved"):
            stats["resolved"] += 1
            layer = item.get("match_layer", "unknown")
            stats[f"by_{layer}"] = stats.get(f"by_{layer}", 0) + 1
        else:
            stats["new"] += 1
    return stats


# ---------------------------------------------------------------------------
# NER Fallback: Fill about_entities for empty Fact/Claim
# ---------------------------------------------------------------------------

_NER_SYSTEM_PROMPT = (
    "Extract named entities (companies, organizations, people, assets, markets, "
    "products, economic indicators, countries) from each text. "
    'Return JSON: {"0": ["entity1", "entity2"], "1": [...], ...}'
)

_NER_TIMEOUT_SECONDS = 30


def _collect_empty_about_entity_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return Fact/Claim dicts where ``about_entities`` is an empty list.

    Items where ``about_entities`` key is absent are excluded.
    Items where ``about_entities`` is non-empty are excluded.
    """
    targets: list[dict[str, Any]] = []
    for source in data.get("sources", []):
        for chunk in source.get("chunks", []):
            for item in chunk.get("facts", []) + chunk.get("claims", []):
                if "about_entities" in item and item["about_entities"] == []:
                    targets.append(item)
    return targets


def _ner_call_batch(
    client: Any,
    batch: list[dict[str, Any]],
    batch_idx: int,
    n_batches: int,
) -> dict[str, list[str]] | None:
    """Call Anthropic NER API for a single batch.

    Returns parsed JSON dict on success, None on any error (silent skip).
    """
    contents = [item.get("content", "") for item in batch]
    text_block = "\n".join(f"{i}: {c}" for i, c in enumerate(contents))
    user_message = f"Texts:\n{text_block}"
    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=512,
            timeout=_NER_TIMEOUT_SECONDS,
            system=_NER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        return json.loads(response.content[0].text)  # type: ignore[no-any-return]
    except Exception as exc:
        logger.warning(
            "_ner_fill_about_entities: batch %d/%d failed, skipping — %s",
            batch_idx + 1,
            n_batches,
            exc,
        )
        return None


def _apply_ner_results(
    batch: list[dict[str, Any]],
    ner_result: dict[str, list[str]],
    data: dict[str, Any],
    existing_names: set[str],
) -> None:
    """Write NER results back into batch items and update ``data["entities"]``."""
    for i, item in enumerate(batch):
        entity_names: list[str] = ner_result.get(str(i), [])
        if not entity_names:
            continue
        item["about_entities"] = entity_names
        for name in entity_names:
            if name not in existing_names:
                existing_names.add(name)
                data.setdefault("entities", []).append({"name": name})


def _ner_fill_about_entities(
    data: dict[str, Any],
    batch_size: int = 20,
) -> dict[str, Any]:
    """Fill ``about_entities`` for empty Fact/Claim items using Haiku NER.

    Scans ``sources[].chunks[].facts[]`` and ``claims[]`` for items where
    ``about_entities`` is an empty list, calls Anthropic claude-haiku-4-5 in
    batches to extract named entities, and writes the results back.

    Extracted entity names are also appended to ``data["entities"]``
    (deduplicating by name).

    Parameters
    ----------
    data
        Graph-queue JSON dict (mutated in-place for ``about_entities``).
    batch_size
        Maximum number of items per Anthropic API call.

    Returns
    -------
    dict
        The same ``data`` dict, with ``about_entities`` and ``entities``
        updated.

    Notes
    -----
    * API errors are silently skipped so the pipeline is never blocked.
    * Items where ``about_entities`` key is absent are left untouched.
    * Items where ``about_entities`` is non-empty are skipped.
    """
    if anthropic is None:
        logger.warning("anthropic package not installed, skipping --ner-fallback")
        return data

    targets = _collect_empty_about_entity_items(data)
    if not targets:
        logger.debug("_ner_fill_about_entities: no empty about_entities found, skipping")
        return data

    logger.info(
        "_ner_fill_about_entities: %d items to process (batch_size=%d)",
        len(targets),
        batch_size,
    )

    existing_names: set[str] = {e["name"] for e in data.get("entities", []) if "name" in e}
    client = anthropic.Anthropic()
    n_batches = math.ceil(len(targets) / batch_size)

    for batch_idx in range(n_batches):
        batch = targets[batch_idx * batch_size : (batch_idx + 1) * batch_size]
        ner_result = _ner_call_batch(client, batch, batch_idx, n_batches)
        if ner_result is not None:
            _apply_ner_results(batch, ner_result, data, existing_names)
            logger.debug(
                "_ner_fill_about_entities: batch %d/%d done",
                batch_idx + 1,
                n_batches,
            )

    logger.info("_ner_fill_about_entities: completed for %d items", len(targets))
    return data


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build argument parser for entity_linker CLI.

    Returns
    -------
    argparse.ArgumentParser
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        description="Resolve extracted entities/concepts against a Neo4j instance."
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Input JSON file with extracted entities and concepts",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON file (default: input with .resolved.json suffix)",
    )
    parser.add_argument(
        "--instance",
        type=str,
        default="creator",
        help="Neo4j instance name (default: creator). "
        "Reads config from data/config/neo4j-instances/{instance}.yaml",
    )
    parser.add_argument(
        "--no-embedding",
        action="store_true",
        help="Skip embedding layer (faster, less accurate)",
    )
    parser.add_argument(
        "--v3",
        action="store_true",
        help="Enable v3.0 ontology features: EntityType consolidation, "
        "name normalization, 3-stage linking, Identifier output",
    )
    parser.add_argument(
        "--linker-config",
        type=Path,
        default=None,
        help="Path to entity-linker-config.yaml (default: auto-detect)",
    )
    parser.add_argument(
        "--ner-fallback",
        action="store_true",
        help="Run Haiku NER on Fact/Claim items where about_entities is empty "
        "and set the extracted entities before the normal resolve flow. "
        "Requires the 'anthropic' package. API errors are silently skipped.",
    )
    return parser


def main() -> None:
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Read input
    input_path: Path = args.input
    if not input_path.exists():
        logger.error("Input file not found: %s", input_path)
        sys.exit(1)

    data = json.loads(input_path.read_text(encoding="utf-8"))
    logger.info("Read input: %s", input_path)

    # Load linker config (v3.0)
    search_config: LinkerSearchConfig | None = None
    if args.v3:
        search_config = load_linker_config(args.linker_config)
        logger.info(
            "v3.0 mode enabled: fulltext_index=%s, alias_index=%s, "
            "similarity_threshold=%.2f",
            search_config.fulltext_index,
            search_config.alias_fulltext_index,
            search_config.similarity_threshold,
        )

    # Load instance config and connect
    config = load_instance_config(args.instance)
    logger.info(
        "Connecting to %s (instance: %s)", _mask_uri(config["bolt_uri"]), args.instance
    )

    # --ner-fallback: fill about_entities for empty Fact/Claim before linking
    if args.ner_fallback:
        logger.info("--ner-fallback enabled: running NER pre-fill on empty about_entities")
        data = _ner_fill_about_entities(data)

    client = Neo4jClient(
        uri=config["bolt_uri"],
        user=config["user"],
        password=config["password"],
    )
    try:
        resolved = resolve_all(
            client,
            data,
            use_embedding=not args.no_embedding,
            use_v3=args.v3,
            search_config=search_config,
        )
    finally:
        client.close()

    # Write output
    output_path = args.output or input_path.with_suffix(".resolved.json")
    output_path.write_text(
        json.dumps(resolved, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    logger.info("Written: %s", output_path)
    logger.info("Stats: %s", json.dumps(resolved["stats"], ensure_ascii=False))


if __name__ == "__main__":
    main()
