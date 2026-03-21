#!/usr/bin/env python3
"""Normalize EXTRACTED_FROM(Fact/Claim → Source) to v2 schema chains.

Reads existing non-v2 relationships from research-neo4j and generates
a graph-queue JSON that creates the proper v2 chain:

    Source -[CONTAINS_CHUNK]-> Chunk
    Fact/Claim -[EXTRACTED_FROM]-> Chunk  (rewired from Source)
    Source -[STATES_FACT]-> Fact          (where missing)
    Source -[MAKES_CLAIM]-> Claim         (where missing)

Usage
-----
::

    # Phase 1: Generate graph-queue JSON (read-only)
    uv run python scripts/normalize_source_chain.py

    # Phase 2: Ingest via /save-to-graph
    # (run /save-to-graph on the generated JSON)

    # Phase 3: Cleanup old EXTRACTED_FROM(Fact/Claim → Source)
    uv run python scripts/normalize_source_chain.py --cleanup-report
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7688")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")

OUTPUT_DIR = Path(".tmp/graph-queue/normalize")


def _generate_chunk_id(source_id: str, index: int = 0) -> str:
    """Generate a deterministic chunk_id for normalization chunks."""
    raw = f"normalize:{source_id}:chunk:{index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _connect() -> "neo4j.Driver":
    """Connect to research-neo4j."""
    try:
        import neo4j

        driver = neo4j.GraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
        )
        driver.verify_connectivity()
        return driver
    except Exception as e:
        logger.error("Neo4j connection failed: %s", e)
        sys.exit(1)


def _fetch_extracted_from_pairs(driver: "neo4j.Driver") -> list[dict]:
    """Fetch all EXTRACTED_FROM(Fact/Claim → Source) pairs."""
    query = """
    MATCH (f)-[r:EXTRACTED_FROM]->(s:Source)
    WHERE NOT 'Memory' IN labels(f)
    AND (f:Fact OR f:Claim)
    OPTIONAL MATCH (s)-[:CONTAINS_CHUNK]->(existing_ch:Chunk)
    WITH f, s, collect(existing_ch.chunk_id)[0] AS existing_chunk_id,
         CASE WHEN f:Fact THEN 'Fact' ELSE 'Claim' END AS node_type,
         EXISTS { MATCH (s)-[:STATES_FACT]->(f) } AS has_sf,
         EXISTS { MATCH (s)-[:MAKES_CLAIM]->(f) } AS has_mc
    RETURN coalesce(f.fact_id, f.claim_id) AS fc_id,
           node_type,
           s.source_id AS source_id,
           existing_chunk_id,
           has_sf, has_mc
    """
    with driver.session() as session:
        result = session.run(query)
        return [dict(r) for r in result]


def _fetch_source_url_only(driver: "neo4j.Driver") -> list[dict]:
    """Fetch Fact/Claim with source_url but no EXTRACTED_FROM."""
    query = """
    MATCH (f)
    WHERE NOT 'Memory' IN labels(f) AND (f:Fact OR f:Claim)
    AND f.source_url IS NOT NULL
    AND NOT EXISTS { MATCH (f)-[:EXTRACTED_FROM]->(:Source) }
    WITH f, f.source_url AS url,
         CASE WHEN f:Fact THEN 'Fact' ELSE 'Claim' END AS node_type
    OPTIONAL MATCH (s:Source {url: url})
    WHERE s IS NOT NULL
    OPTIONAL MATCH (s)-[:CONTAINS_CHUNK]->(existing_ch:Chunk)
    WITH f, url, node_type, s,
         collect(existing_ch.chunk_id)[0] AS existing_chunk_id,
         CASE WHEN s IS NOT NULL THEN
           CASE WHEN EXISTS { MATCH (s)-[:STATES_FACT]->(f) } THEN true ELSE false END
         ELSE false END AS has_sf,
         CASE WHEN s IS NOT NULL THEN
           CASE WHEN EXISTS { MATCH (s)-[:MAKES_CLAIM]->(f) } THEN true ELSE false END
         ELSE false END AS has_mc
    WHERE s IS NOT NULL
    RETURN coalesce(f.fact_id, f.claim_id) AS fc_id,
           node_type,
           s.source_id AS source_id,
           existing_chunk_id,
           has_sf, has_mc
    """
    with driver.session() as session:
        result = session.run(query)
        return [dict(r) for r in result]


def _build_graph_queue(
    ef_pairs: list[dict],
    url_pairs: list[dict],
) -> dict:
    """Build graph-queue JSON from extracted pairs."""
    all_pairs = ef_pairs + url_pairs
    logger.info(
        "Building graph-queue: %d EXTRACTED_FROM + %d source_url = %d total",
        len(ef_pairs),
        len(url_pairs),
        len(all_pairs),
    )

    # Group by source_id to create one Chunk per Source (where needed)
    source_chunks: dict[str, str] = {}  # source_id → chunk_id
    chunks: list[dict] = []
    contains_chunk_rels: list[dict] = []
    extracted_from_fact_rels: list[dict] = []
    extracted_from_claim_rels: list[dict] = []
    source_fact_rels: list[dict] = []
    source_claim_rels: list[dict] = []

    stats = {
        "chunks_reused": 0,
        "chunks_created": 0,
        "extracted_from_rewired": 0,
        "states_fact_added": 0,
        "makes_claim_added": 0,
    }

    for pair in all_pairs:
        source_id = pair["source_id"]
        fc_id = pair["fc_id"]
        node_type = pair["node_type"]
        existing_chunk_id = pair["existing_chunk_id"]

        # Determine chunk_id: reuse existing or create new
        if source_id in source_chunks:
            chunk_id = source_chunks[source_id]
        elif existing_chunk_id:
            chunk_id = existing_chunk_id
            source_chunks[source_id] = chunk_id
            stats["chunks_reused"] += 1
        else:
            chunk_id = _generate_chunk_id(source_id)
            source_chunks[source_id] = chunk_id
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "chunk_index": 0,
                    "section_title": "normalized_from_extracted_from",
                    "content": "",
                }
            )
            contains_chunk_rels.append(
                {
                    "from_id": source_id,
                    "to_id": chunk_id,
                    "type": "CONTAINS_CHUNK",
                }
            )
            stats["chunks_created"] += 1

        # EXTRACTED_FROM: Fact/Claim → Chunk
        if node_type == "Fact":
            extracted_from_fact_rels.append(
                {"from_id": fc_id, "to_id": chunk_id}
            )
        else:
            extracted_from_claim_rels.append(
                {"from_id": fc_id, "to_id": chunk_id}
            )
        stats["extracted_from_rewired"] += 1

        # STATES_FACT / MAKES_CLAIM: Source → Fact/Claim (where missing)
        if node_type == "Fact" and not pair["has_sf"]:
            source_fact_rels.append(
                {"from_id": source_id, "to_id": fc_id, "type": "STATES_FACT"}
            )
            stats["states_fact_added"] += 1
        elif node_type == "Claim" and not pair["has_mc"]:
            source_claim_rels.append(
                {"from_id": source_id, "to_id": fc_id, "type": "MAKES_CLAIM"}
            )
            stats["makes_claim_added"] += 1

    now = datetime.now(timezone.utc)
    queue_doc = {
        "schema_version": "2.4",
        "queue_id": f"normalize-source-chain-{now.strftime('%Y%m%d%H%M%S')}",
        "created_at": now.isoformat(),
        "command_source": "normalize-source-chain",
        "session_id": f"normalize-{now.strftime('%Y%m%d')}",
        "batch_label": "source-chain-normalization",
        "sources": [],
        "topics": [],
        "claims": [],
        "facts": [],
        "entities": [],
        "chunks": chunks,
        "financial_datapoints": [],
        "fiscal_periods": [],
        "authors": [],
        "stances": [],
        "questions": [],
        "relations": {
            "contains_chunk": contains_chunk_rels,
            "extracted_from_fact": extracted_from_fact_rels,
            "extracted_from_claim": extracted_from_claim_rels,
            "source_fact": source_fact_rels,
            "source_claim": source_claim_rels,
        },
    }

    logger.info("Stats: %s", json.dumps(stats, indent=2))
    logger.info(
        "Graph-queue: %d chunks, %d contains_chunk, "
        "%d extracted_from_fact, %d extracted_from_claim, "
        "%d source_fact, %d source_claim",
        len(chunks),
        len(contains_chunk_rels),
        len(extracted_from_fact_rels),
        len(extracted_from_claim_rels),
        len(source_fact_rels),
        len(source_claim_rels),
    )

    return queue_doc


def _generate_cleanup_report(driver: "neo4j.Driver") -> None:
    """Generate Cypher statements for cleanup (Phase 3)."""
    query = """
    MATCH (f)-[r:EXTRACTED_FROM]->(s:Source)
    WHERE NOT 'Memory' IN labels(f) AND (f:Fact OR f:Claim)
    RETURN count(r) AS rels_to_delete
    """
    with driver.session() as session:
        result = session.run(query).single()
        count = result["rels_to_delete"] if result else 0

    print("\n=== Phase 3: Cleanup Report ===")
    print(f"EXTRACTED_FROM(Fact/Claim → Source) to delete: {count}")
    print("\nVerification query (run BEFORE cleanup):")
    print(
        "  MATCH (f)-[:EXTRACTED_FROM]->(ch:Chunk) "
        "WHERE (f:Fact OR f:Claim) RETURN count(f)"
    )
    print("\nCleanup Cypher (run AFTER verification):")
    print(
        "  MATCH (f)-[r:EXTRACTED_FROM]->(s:Source) "
        "WHERE (f:Fact OR f:Claim) AND NOT 'Memory' IN labels(f) DELETE r"
    )
    print(f"\nExpected: {count} relationships deleted")


def main() -> None:
    """Run normalization pipeline."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Normalize EXTRACTED_FROM to v2 schema"
    )
    parser.add_argument(
        "--cleanup-report",
        action="store_true",
        help="Generate cleanup Cypher for Phase 3",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print stats without writing output",
    )
    args = parser.parse_args()

    driver = _connect()

    if args.cleanup_report:
        _generate_cleanup_report(driver)
        driver.close()
        return

    try:
        logger.info("Phase 1: Fetching EXTRACTED_FROM pairs...")
        ef_pairs = _fetch_extracted_from_pairs(driver)
        logger.info("  Found %d EXTRACTED_FROM pairs", len(ef_pairs))

        logger.info("Phase 1: Fetching source_url-only cases...")
        url_pairs = _fetch_source_url_only(driver)
        logger.info("  Found %d source_url matches", len(url_pairs))

        queue_doc = _build_graph_queue(ef_pairs, url_pairs)

        if args.dry_run:
            logger.info("Dry run — no output written")
            return

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / f"{queue_doc['queue_id']}.json"
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(queue_doc, f, ensure_ascii=False, indent=2)

        logger.info("Graph-queue written: %s", output_path)
        print(f"\nNext steps:")
        print(f"  1. /save-to-graph {output_path}")
        print(f"  2. Verify: MATCH (f)-[:EXTRACTED_FROM]->(ch:Chunk) RETURN count(f)")
        print(f"  3. Cleanup: uv run python scripts/normalize_source_chain.py --cleanup-report")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
