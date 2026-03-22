#!/usr/bin/env python3
"""Entity Linker for creator-neo4j.

Resolves extracted entity/concept names to existing nodes in Neo4j
using a 3-layer matching strategy:

Layer 1: LLM normalization (already done in extraction prompt)
Layer 2+3: Full-Text Index + APOC string similarity (unified via Alias nodes)
Layer 4: multilingual-e5-small embedding similarity

Usage
-----
::

    python scripts/entity_linker.py --input extracted.json --output resolved.json

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
import json
import logging
import sys
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NEO4J_URI = "bolt://localhost:7689"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "gomasuke"

SIMILARITY_THRESHOLD_APOC = 0.8
SIMILARITY_THRESHOLD_EMBEDDING = 0.8

# ---------------------------------------------------------------------------
# Neo4j Connection
# ---------------------------------------------------------------------------


class CreatorNeo4jClient:
    """Neo4j client for creator-neo4j."""

    def __init__(
        self,
        uri: str = NEO4J_URI,
        user: str = NEO4J_USER,
        password: str = NEO4J_PASSWORD,
    ) -> None:
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        self.driver.close()

    def query(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        with self.driver.session() as session:
            try:
                result = session.run(cypher, **params)
                return [dict(record) for record in result]
            except Exception as e:
                if "no such fulltext schema index" in str(e):
                    logger.debug("Full-text index not found, skipping: %s", e)
                    return []
                raise


# ---------------------------------------------------------------------------
# Layer 2+3: Full-Text + APOC Matching
# ---------------------------------------------------------------------------


def resolve_entity_by_text(
    client: CreatorNeo4jClient,
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
    # Step 1: Exact match on entity_key
    results = client.query(
        "MATCH (e:Entity {entity_key: $key}) RETURN e.entity_id AS id, "
        "e.entity_key AS key, e.name AS name",
        key=f"{name}::{entity_type}",
    )
    if results:
        return {
            "entity_key": results[0]["key"],
            "entity_id": results[0]["id"],
            "matched_name": results[0]["name"],
            "match_layer": "exact",
        }

    # Step 2: Exact match on name (type-agnostic)
    results = client.query(
        "MATCH (e:Entity {name: $name}) RETURN e.entity_id AS id, "
        "e.entity_key AS key, e.name AS name",
        name=name,
    )
    if results:
        return {
            "entity_key": results[0]["key"],
            "entity_id": results[0]["id"],
            "matched_name": results[0]["name"],
            "match_layer": "exact_name",
        }

    # Step 3: Alias Full-Text + APOC similarity
    results = client.query(
        """
        CALL db.index.fulltext.queryNodes("alias_fulltext", $name)
        YIELD node AS alias, score
        WHERE score > 0.3
        MATCH (alias)-[:ALIAS_OF]->(e:Entity)
        WITH e, alias, score,
             apoc.text.levenshteinSimilarity(alias.value, $name) AS lev
        WHERE lev > $threshold
        RETURN e.entity_id AS id, e.entity_key AS key, e.name AS name,
               alias.value AS matched_alias, lev AS similarity
        ORDER BY lev DESC
        LIMIT 1
        """,
        name=name,
        threshold=SIMILARITY_THRESHOLD_APOC,
    )
    if results:
        return {
            "entity_key": results[0]["key"],
            "entity_id": results[0]["id"],
            "matched_name": results[0]["name"],
            "matched_alias": results[0]["matched_alias"],
            "similarity": results[0]["similarity"],
            "match_layer": "alias_fuzzy",
        }

    # Step 4: Entity name Full-Text + APOC
    results = client.query(
        """
        CALL db.index.fulltext.queryNodes("entity_fulltext", $name)
        YIELD node AS e, score
        WHERE score > 0.3
        WITH e, score,
             apoc.text.levenshteinSimilarity(e.name, $name) AS lev
        WHERE lev > $threshold
        RETURN e.entity_id AS id, e.entity_key AS key, e.name AS name,
               lev AS similarity
        ORDER BY lev DESC
        LIMIT 1
        """,
        name=name,
        threshold=SIMILARITY_THRESHOLD_APOC,
    )
    if results:
        return {
            "entity_key": results[0]["key"],
            "entity_id": results[0]["id"],
            "matched_name": results[0]["name"],
            "similarity": results[0]["similarity"],
            "match_layer": "name_fuzzy",
        }

    return None


def resolve_concept_by_text(
    client: CreatorNeo4jClient,
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
    # Step 1: Exact match on name
    results = client.query(
        "MATCH (c:Concept {name: $name}) RETURN c.concept_id AS id, c.name AS name",
        name=name,
    )
    if results:
        return {
            "concept_id": results[0]["id"],
            "matched_name": results[0]["name"],
            "match_layer": "exact",
        }

    # Step 2: Alias Full-Text + APOC
    results = client.query(
        """
        CALL db.index.fulltext.queryNodes("alias_fulltext", $name)
        YIELD node AS alias, score
        WHERE score > 0.3
        MATCH (alias)-[:ALIAS_OF]->(c:Concept)
        WITH c, alias, score,
             apoc.text.levenshteinSimilarity(alias.value, $name) AS lev
        WHERE lev > $threshold
        RETURN c.concept_id AS id, c.name AS name,
               alias.value AS matched_alias, lev AS similarity
        ORDER BY lev DESC
        LIMIT 1
        """,
        name=name,
        threshold=SIMILARITY_THRESHOLD_APOC,
    )
    if results:
        return {
            "concept_id": results[0]["id"],
            "matched_name": results[0]["name"],
            "matched_alias": results[0]["matched_alias"],
            "similarity": results[0]["similarity"],
            "match_layer": "alias_fuzzy",
        }

    # Step 3: Concept name Full-Text + APOC
    results = client.query(
        """
        CALL db.index.fulltext.queryNodes("concept_fulltext", $name)
        YIELD node AS c, score
        WHERE score > 0.3
        WITH c, score,
             apoc.text.levenshteinSimilarity(c.name, $name) AS lev
        WHERE lev > $threshold
        RETURN c.concept_id AS id, c.name AS name, lev AS similarity
        ORDER BY lev DESC
        LIMIT 1
        """,
        name=name,
        threshold=SIMILARITY_THRESHOLD_APOC,
    )
    if results:
        return {
            "concept_id": results[0]["id"],
            "matched_name": results[0]["name"],
            "similarity": results[0]["similarity"],
            "match_layer": "name_fuzzy",
        }

    return None


# ---------------------------------------------------------------------------
# Layer 4: Embedding Matching
# ---------------------------------------------------------------------------


def _load_embedding_model() -> Any:
    """Load multilingual-e5-small model (lazy, cached)."""
    try:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading multilingual-e5-small...")
        model = SentenceTransformer("intfloat/multilingual-e5-small", device="cpu")
        logger.info("Model loaded.")
        return model
    except ImportError:
        logger.warning("sentence-transformers not installed, skipping embedding layer")
        return None


def resolve_by_embedding(
    client: CreatorNeo4jClient,
    name: str,
    target_type: str,
    model: Any,
) -> dict[str, Any] | None:
    """Resolve by embedding cosine similarity.

    Parameters
    ----------
    client
        Neo4j client.
    name
        Name to resolve.
    target_type
        "entity" or "concept".
    model
        SentenceTransformer model.

    Returns
    -------
    dict or None
        Best match above threshold, or None.
    """
    if model is None:
        return None

    import numpy as np

    # Encode target name
    target_emb = model.encode(name, normalize_embeddings=True)

    # Get candidates with embeddings from Neo4j
    if target_type == "entity":
        candidates = client.query(
            "MATCH (e:Entity) WHERE e.embedding IS NOT NULL "
            "RETURN e.entity_id AS id, e.entity_key AS key, "
            "e.name AS name, e.embedding AS emb"
        )
    else:
        candidates = client.query(
            "MATCH (c:Concept) WHERE c.embedding IS NOT NULL "
            "RETURN c.concept_id AS id, c.name AS name, c.embedding AS emb"
        )

    if not candidates:
        return None

    # Compute cosine similarities
    best_match = None
    best_sim = 0.0

    for cand in candidates:
        cand_emb = np.array(cand["emb"], dtype=np.float32)
        sim = float(np.dot(target_emb, cand_emb))
        if sim > best_sim:
            best_sim = sim
            best_match = cand

    if best_sim >= SIMILARITY_THRESHOLD_EMBEDDING and best_match is not None:
        result: dict[str, Any] = {
            "matched_name": best_match["name"],
            "similarity": round(best_sim, 4),
            "match_layer": "embedding",
        }
        if target_type == "entity":
            result["entity_key"] = best_match["key"]
            result["entity_id"] = best_match["id"]
        else:
            result["concept_id"] = best_match["id"]
        return result

    return None


# ---------------------------------------------------------------------------
# Main Resolver
# ---------------------------------------------------------------------------


def resolve_all(
    client: CreatorNeo4jClient,
    data: dict[str, Any],
    use_embedding: bool = True,
) -> dict[str, Any]:
    """Resolve all entities and concepts in input data.

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

    # Resolve entities
    resolved_entities = []
    for ent in data.get("entities", []):
        name = ent["name"]
        entity_type = ent["entity_type"]

        # Layer 2+3: Text matching
        match = resolve_entity_by_text(client, name, entity_type)

        # Layer 4: Embedding (if text didn't match)
        if match is None and model is not None:
            match = resolve_by_embedding(client, name, "entity", model)

        if match is not None:
            ent.update({"resolved": True, **match})
        else:
            ent["resolved"] = False
            ent["match_layer"] = "new"

        resolved_entities.append(ent)
        layer = ent.get("match_layer", "new")
        logger.info("Entity: %s → %s (%s)", name, ent.get("matched_name", "NEW"), layer)

    # Resolve concepts
    resolved_concepts = []
    for concept in data.get("concepts", []):
        name = concept["name"]

        # Layer 2+3: Text matching
        match = resolve_concept_by_text(client, name)

        # Layer 4: Embedding
        if match is None and model is not None:
            match = resolve_by_embedding(client, name, "concept", model)

        if match is not None:
            concept.update({"resolved": True, **match})
        else:
            concept["resolved"] = False
            concept["match_layer"] = "new"

        resolved_concepts.append(concept)
        layer = concept.get("match_layer", "new")
        logger.info(
            "Concept: %s → %s (%s)", name, concept.get("matched_name", "NEW"), layer
        )

    # Stats
    entity_stats = _compute_stats(resolved_entities)
    concept_stats = _compute_stats(resolved_concepts)

    return {
        "entities": resolved_entities,
        "concepts": resolved_concepts,
        "serves_as": data.get("serves_as", []),
        "concept_relations": data.get("concept_relations", []),
        "stats": {
            "entities": entity_stats,
            "concepts": concept_stats,
        },
    }


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


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Resolve extracted entities/concepts against creator-neo4j."
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
        "--no-embedding",
        action="store_true",
        help="Skip embedding layer (faster, less accurate)",
    )
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

    # Connect and resolve
    client = CreatorNeo4jClient()
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
