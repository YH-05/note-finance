#!/usr/bin/env python3
"""Embed Entity/Concept nodes in creator-neo4j with multilingual-e5-small.

Reads all Entity and Concept nodes without an `embedding` property,
generates 384-dim normalized embeddings, and writes them back via Neo4j driver.

Usage
-----
::

    # Embed all unembedded nodes
    uv run --extra embedding python scripts/creator_embed_nodes.py

    # Dry-run (count only)
    uv run --extra embedding python scripts/creator_embed_nodes.py --dry-run

    # Re-embed all nodes (overwrite existing)
    uv run --extra embedding python scripts/creator_embed_nodes.py --force
"""

from __future__ import annotations

import argparse
import logging
import sys

from neo4j import GraphDatabase

logger = logging.getLogger(__name__)

BOLT_URI = "bolt://localhost:7689"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "gomasuke"
BATCH_SIZE = 50
MODEL_NAME = "intfloat/multilingual-e5-small"


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed creator-neo4j Entity/Concept nodes.")
    parser.add_argument("--dry-run", action="store_true", help="Count targets only, don't write")
    parser.add_argument("--force", action="store_true", help="Re-embed all nodes (overwrite)")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help=f"Batch size (default: {BATCH_SIZE})")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    # Load model
    if not args.dry_run:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            logger.error("sentence-transformers not installed. Run: uv sync --extra embedding")
            sys.exit(1)

        logger.info("Loading %s...", MODEL_NAME)
        model = SentenceTransformer(MODEL_NAME, device="cpu")
        logger.info("Model loaded (dim=384).")
    else:
        model = None

    driver = GraphDatabase.driver(BOLT_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        for label, key_prop in [("Entity", "entity_id"), ("Concept", "concept_id")]:
            _embed_label(driver, model, label, key_prop, args)
    finally:
        driver.close()


def _embed_label(
    driver: GraphDatabase.driver,
    model: object | None,
    label: str,
    key_prop: str,
    args: argparse.Namespace,
) -> None:
    where = "" if args.force else "WHERE n.embedding IS NULL"
    count_query = f"MATCH (n:{label}) {where} RETURN count(n) AS cnt"

    with driver.session() as session:
        result = session.run(count_query).single()
        total = result["cnt"] if result else 0

    logger.info("[%s] Target nodes: %d%s", label, total, " (dry-run)" if args.dry_run else "")
    if total == 0 or args.dry_run:
        return

    fetch_query = (
        f"MATCH (n:{label}) {where} "
        f"RETURN n.{key_prop} AS id, n.name AS name "
        f"LIMIT $batch"
    )
    write_query = (
        f"UNWIND $rows AS row "
        f"MATCH (n:{label} {{{key_prop}: row.id}}) "
        f"SET n.embedding = row.embedding"
    )

    processed = 0
    while processed < total:
        with driver.session() as session:
            records = list(session.run(fetch_query, batch=args.batch_size))

        if not records:
            break

        names = [r["name"] or "" for r in records]
        embeddings = model.encode(names, normalize_embeddings=True, show_progress_bar=False)

        rows = [
            {"id": r["id"], "embedding": emb.tolist()}
            for r, emb in zip(records, embeddings)
        ]

        with driver.session() as session:
            session.run(write_query, rows=rows)

        processed += len(rows)
        logger.info("[%s] Embedded %d / %d", label, processed, total)

    logger.info("[%s] Done. Total embedded: %d", label, processed)


if __name__ == "__main__":
    main()
