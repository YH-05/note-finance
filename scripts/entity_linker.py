#!/usr/bin/env python3
"""Entity Linker for Neo4j instances.

Resolves extracted entity/concept names to existing nodes in Neo4j
using a 3-layer matching strategy:

Layer 1: LLM normalization (already done in extraction prompt)
Layer 2+3: Full-Text Index + APOC string similarity (unified via Alias nodes)
Layer 4: multilingual-e5-small embedding similarity

Usage
-----
::

    python scripts/entity_linker.py --input extracted.json --output resolved.json
    python scripts/entity_linker.py --input extracted.json --instance research

Input JSON format::

    {
      "entities": [
        {"name": "Instagram", "entity_type": "platform"}
      ],
      "concepts": [
        {"name": "SNS集客", "category": "AcquisitionChannel"}
      ]
    }

Output JSON format::

    {
      "entities": [
        {"name": "Instagram", "entity_type": "platform",
         "resolved": true, "entity_key": "Instagram::platform",
         "match_layer": "exact"}
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
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse, urlunparse

import yaml
from neo4j import GraphDatabase
from neo4j.exceptions import ClientError

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

try:
    from quants.utils.logging_config import get_logger

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

SIMILARITY_THRESHOLD_APOC = 0.8
SIMILARITY_THRESHOLD_EMBEDDING = 0.8

# Pattern to match environment variable references like ${VAR_NAME}
_ENV_VAR_PATTERN = re.compile(r"^\$\{([^}]+)\}$")


# ---------------------------------------------------------------------------
# Node Resolution Config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _NodeResolveConfig:
    """Configuration for resolving a specific node type (Entity or Concept)."""

    label: str  # "Entity" or "Concept"
    id_key: str  # "entity_id" or "concept_id"
    key_key: str | None  # "entity_key" or None
    alias_index: str  # "alias_fulltext"
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
# Layer 2+3: Full-Text + APOC Matching (unified)
# ---------------------------------------------------------------------------


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
) -> dict[str, Any] | None:
    """Resolve a node by exact match, alias, and fuzzy text similarity.

    This is the unified resolution logic for both Entity and Concept
    nodes, parameterised by ``config``.

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
    """
    ret = _return_clause(config)

    # Step 0 (Entity only): entity_key exact match
    if entity_key is not None and config.key_key is not None:
        results = client.query(
            f"MATCH (n:{config.label} {{{config.key_key}: $key}}) RETURN {ret}",
            key=entity_key,
        )
        if results:
            return _build_result(results[0], config, "exact")

    # Step 1: name exact match
    results = client.query(
        f"MATCH (n:{config.label} {{name: $name}}) RETURN {ret}",
        name=name,
    )
    if results:
        layer = "exact_name" if entity_key is not None else "exact"
        return _build_result(results[0], config, layer)

    # Step 2: Alias Full-Text + APOC similarity
    results = client.query(
        f'CALL db.index.fulltext.queryNodes("{config.alias_index}", $name) '
        f"YIELD node AS alias, score WHERE score > 0.3 "
        f"MATCH (alias)-[:ALIAS_OF]->(n:{config.label}) "
        f"WITH n, alias, score, "
        f"     apoc.text.levenshteinSimilarity(alias.value, $name) AS lev "
        f"WHERE lev > $threshold "
        f"RETURN {ret}, alias.value AS matched_alias, lev AS similarity "
        f"ORDER BY lev DESC LIMIT 1",
        name=name,
        threshold=SIMILARITY_THRESHOLD_APOC,
    )
    if results:
        return _build_result(
            results[0],
            config,
            "alias_fuzzy",
            matched_alias=results[0]["matched_alias"],
            similarity=results[0]["similarity"],
        )

    # Step 3: Node name Full-Text + APOC
    results = client.query(
        f'CALL db.index.fulltext.queryNodes("{config.node_index}", $name) '
        f"YIELD node AS n, score WHERE score > 0.3 "
        f"WITH n, score, "
        f"     apoc.text.levenshteinSimilarity(n.name, $name) AS lev "
        f"WHERE lev > $threshold "
        f"RETURN {ret}, lev AS similarity "
        f"ORDER BY lev DESC LIMIT 1",
        name=name,
        threshold=SIMILARITY_THRESHOLD_APOC,
    )
    if results:
        return _build_result(
            results[0], config, "name_fuzzy", similarity=results[0]["similarity"]
        )

    return None


def resolve_entity_by_text(
    client: Neo4jClient,
    name: str,
    entity_type: str,
) -> dict[str, Any] | None:
    """Resolve entity by exact match, alias, and fuzzy text similarity.

    Parameters
    ----------
    client
        Neo4j client.
    name
        Extracted entity name (already normalized by LLM).
    entity_type
        Entity type (platform, company, person, organization).

    Returns
    -------
    dict or None
        Resolved entity info, or None if no match found.
    """
    return _resolve_by_text(
        client, name, _ENTITY_CONFIG, entity_key=f"{name}::{entity_type}"
    )


def resolve_concept_by_text(
    client: Neo4jClient,
    name: str,
) -> dict[str, Any] | None:
    """Resolve concept by exact match, alias, and fuzzy text similarity.

    Parameters
    ----------
    client
        Neo4j client.
    name
        Extracted concept name.

    Returns
    -------
    dict or None
        Resolved concept info, or None if no match found.
    """
    return _resolve_by_text(client, name, _CONCEPT_CONFIG)


# ---------------------------------------------------------------------------
# Layer 4: Embedding Matching
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def _load_embedding_model() -> Any:
    """Load multilingual-e5-small model (lazy, cached via lru_cache)."""
    try:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading multilingual-e5-small...")
        model = SentenceTransformer("intfloat/multilingual-e5-small", device="cpu")
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
) -> dict[str, dict[str, Any]]:
    """Batch exact match for entities (2 queries instead of 2*N).

    Returns a dict mapping ``name::type`` → resolution result.
    """
    if not entities:
        return {}

    matches: dict[str, dict[str, Any]] = {}

    # Step 1: entity_key exact match
    keys = [f"{e['name']}::{e['entity_type']}" for e in entities]
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
    unresolved = [
        e for e in entities if f"{e['name']}::{e['entity_type']}" not in matches
    ]
    if unresolved:
        names = list({e["name"] for e in unresolved})
        name_results = client.query(
            "UNWIND $names AS n "
            "MATCH (e:Entity {name: n}) "
            "RETURN n AS input_name, e.entity_id AS id, "
            "       e.entity_key AS entity_key, e.name AS name",
            names=names,
        )
        for r in name_results:
            for e in unresolved:
                k = f"{e['name']}::{e['entity_type']}"
                if e["name"] == r["input_name"] and k not in matches:
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

    Returns a dict mapping concept name → resolution result.
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

    Returns
    -------
    dict
        Resolved data with match info added to each entity/concept.
    """
    model = _load_embedding_model() if use_embedding else None
    entities = data.get("entities", [])
    concepts = data.get("concepts", [])

    # Phase 1: Batch exact match (O(1) queries per type)
    entity_exact = _batch_exact_entities(client, entities)
    concept_exact = _batch_exact_concepts(client, concepts)

    # Phase 2: Sequential fuzzy + embedding for unresolved
    resolved_entities = _resolve_items(client, entities, entity_exact, "entity", model)
    resolved_concepts = _resolve_items(
        client, concepts, concept_exact, "concept", model
    )

    return {
        "entities": resolved_entities,
        "concepts": resolved_concepts,
        "serves_as": data.get("serves_as", []),
        "concept_relations": data.get("concept_relations", []),
        "stats": {
            "entities": _compute_stats(resolved_entities),
            "concepts": _compute_stats(resolved_concepts),
        },
    }


def _resolve_items(
    client: Neo4jClient,
    items: list[dict[str, Any]],
    exact_matches: dict[str, dict[str, Any]],
    item_type: Literal["entity", "concept"],
    model: Any,
) -> list[dict[str, Any]]:
    """Resolve a list of items using pre-computed exact matches + sequential fallback."""
    resolved = []
    for item in items:
        name = item["name"]
        lookup_key = f"{name}::{item['entity_type']}" if item_type == "entity" else name

        # Check batch exact match first
        match = exact_matches.get(lookup_key)

        # Fallback: sequential fuzzy text matching
        if match is None:
            if item_type == "entity":
                match = resolve_entity_by_text(client, name, item["entity_type"])
            else:
                match = resolve_concept_by_text(client, name)

        # Fallback: embedding
        if match is None and model is not None:
            match = resolve_by_embedding(client, name, item_type, model)

        if match is not None:
            item.update({"resolved": True, **match})
        else:
            item["resolved"] = False
            item["match_layer"] = "new"

        resolved.append(item)
        layer = item.get("match_layer", "new")
        label = "Entity" if item_type == "entity" else "Concept"
        logger.info(
            "%s: %s → %s (%s)", label, name, item.get("matched_name", "NEW"), layer
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

    # Load instance config and connect
    config = load_instance_config(args.instance)
    logger.info(
        "Connecting to %s (instance: %s)", _mask_uri(config["bolt_uri"]), args.instance
    )

    client = Neo4jClient(
        uri=config["bolt_uri"],
        user=config["user"],
        password=config["password"],
    )
    try:
        resolved = resolve_all(client, data, use_embedding=not args.no_embedding)
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
