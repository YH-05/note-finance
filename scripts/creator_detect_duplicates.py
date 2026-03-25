#!/usr/bin/env python3
"""Detect duplicate Entity/Concept nodes in creator-neo4j using Vector Index.

Scans embedding-indexed nodes for high-similarity pairs and outputs
JSON reports for manual review.

Usage
-----
::

    # Detect duplicates with default thresholds
    uv run --extra embedding python scripts/creator_detect_duplicates.py

    # Custom thresholds
    uv run --extra embedding python scripts/creator_detect_duplicates.py \
        --entity-threshold 0.90 --concept-threshold 0.91

    # Output to specific file
    uv run --extra embedding python scripts/creator_detect_duplicates.py \
        --output data/processed/creator_quality/duplicates_20260325.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from neo4j import GraphDatabase

logger = logging.getLogger(__name__)

BOLT_URI = "bolt://localhost:7689"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "gomasuke"
DEFAULT_ENTITY_THRESHOLD = 0.92
DEFAULT_CONCEPT_THRESHOLD = 0.93
DEFAULT_OUTPUT_DIR = Path("data/processed/creator_quality")


def detect_entity_duplicates(
    session: object,
    threshold: float,
    limit: int = 200,
) -> list[dict]:
    """Detect duplicate Entity pairs using vector similarity."""
    query = """
    MATCH (e1:Entity)
    WHERE e1.embedding IS NOT NULL
    WITH e1
    ORDER BY e1.entity_id
    LIMIT $limit
    CALL db.index.vector.queryNodes('entity_embedding_idx', 3, e1.embedding)
    YIELD node AS e2, score
    WHERE e1.entity_id < e2.entity_id
      AND score > $threshold
      AND e1.entity_type = e2.entity_type
    WITH e1, e2, score
    OPTIONAL MATCH (e1)-[r1]-()
    WITH e1, e2, score, count(r1) AS rels1
    OPTIONAL MATCH (e2)-[r2]-()
    WITH e1, e2, score, rels1, count(r2) AS rels2
    RETURN e1.entity_id AS id1, e1.name AS name1, e1.entity_type AS type,
           rels1, e2.entity_id AS id2, e2.name AS name2, rels2,
           round(score * 10000) / 10000.0 AS similarity
    ORDER BY similarity DESC
    LIMIT 50
    """
    records = session.run(query, threshold=threshold, limit=limit)
    results = []
    for r in records:
        results.append({
            "id1": r["id1"],
            "name1": r["name1"],
            "id2": r["id2"],
            "name2": r["name2"],
            "type": r["type"],
            "similarity": r["similarity"],
            "rels1": r["rels1"],
            "rels2": r["rels2"],
            "keep_suggestion": r["id1"] if r["rels1"] >= r["rels2"] else r["id2"],
        })
    return results


def detect_concept_duplicates(
    session: object,
    threshold: float,
    limit: int = 500,
) -> list[dict]:
    """Detect duplicate Concept pairs using vector similarity."""
    query = """
    MATCH (c1:Concept)
    WHERE c1.embedding IS NOT NULL AND c1.category IS NOT NULL
    WITH c1
    ORDER BY c1.concept_id
    LIMIT $limit
    CALL db.index.vector.queryNodes('concept_embedding_idx', 3, c1.embedding)
    YIELD node AS c2, score
    WHERE c1.concept_id < c2.concept_id
      AND score > $threshold
      AND c1.category = c2.category
    WITH c1, c2, score
    OPTIONAL MATCH (c1)<-[r1:ABOUT]-()
    WITH c1, c2, score, count(r1) AS about1
    OPTIONAL MATCH (c2)<-[r2:ABOUT]-()
    WITH c1, c2, score, about1, count(r2) AS about2
    RETURN c1.concept_id AS id1, c1.name AS name1, c1.category AS category,
           about1, c2.concept_id AS id2, c2.name AS name2, about2,
           round(score * 10000) / 10000.0 AS similarity
    ORDER BY similarity DESC
    LIMIT 50
    """
    records = session.run(query, threshold=threshold, limit=limit)
    results = []
    for r in records:
        results.append({
            "id1": r["id1"],
            "name1": r["name1"],
            "id2": r["id2"],
            "name2": r["name2"],
            "category": r["category"],
            "similarity": r["similarity"],
            "about1": r["about1"],
            "about2": r["about2"],
            "keep_suggestion": r["id1"] if r["about1"] >= r["about2"] else r["id2"],
        })
    return results


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Detect duplicate Entity/Concept in creator-neo4j",
    )
    parser.add_argument(
        "--entity-threshold",
        type=float,
        default=DEFAULT_ENTITY_THRESHOLD,
        help=f"Entity similarity threshold (default: {DEFAULT_ENTITY_THRESHOLD})",
    )
    parser.add_argument(
        "--concept-threshold",
        type=float,
        default=DEFAULT_CONCEPT_THRESHOLD,
        help=f"Concept similarity threshold (default: {DEFAULT_CONCEPT_THRESHOLD})",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON path (default: auto-generated with date)",
    )
    args = parser.parse_args()

    # Output path
    if args.output:
        output_path = Path(args.output)
    else:
        today = datetime.now(tz=timezone.utc).strftime("%Y%m%d")
        output_path = DEFAULT_OUTPUT_DIR / f"duplicates_{today}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    driver = GraphDatabase.driver(BOLT_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            logger.info(
                "Detecting Entity duplicates (threshold=%.2f)...",
                args.entity_threshold,
            )
            entity_dups = detect_entity_duplicates(
                session, args.entity_threshold,
            )
            logger.info("Found %d Entity duplicate candidates", len(entity_dups))

            logger.info(
                "Detecting Concept duplicates (threshold=%.2f)...",
                args.concept_threshold,
            )
            concept_dups = detect_concept_duplicates(
                session, args.concept_threshold,
            )
            logger.info("Found %d Concept duplicate candidates", len(concept_dups))
    finally:
        driver.close()

    report = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "thresholds": {
            "entity": args.entity_threshold,
            "concept": args.concept_threshold,
        },
        "entity_duplicates": entity_dups,
        "concept_duplicates": concept_dups,
        "summary": {
            "entity_candidates": len(entity_dups),
            "concept_candidates": len(concept_dups),
            "total": len(entity_dups) + len(concept_dups),
        },
    }

    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    logger.info("Report saved to %s", output_path)

    # Print summary to stdout
    print(f"\n=== Duplicate Detection Report ===")
    print(f"Entity candidates:  {len(entity_dups)}")
    print(f"Concept candidates: {len(concept_dups)}")
    print(f"Output: {output_path}")

    if entity_dups:
        print(f"\nTop Entity duplicates:")
        for d in entity_dups[:5]:
            print(f"  {d['similarity']:.4f}  {d['name1']} / {d['name2']} ({d['type']})")

    if concept_dups:
        print(f"\nTop Concept duplicates:")
        for d in concept_dups[:5]:
            print(f"  {d['similarity']:.4f}  {d['name1']} / {d['name2']} ({d['category']})")

    sys.exit(0)


if __name__ == "__main__":
    main()
