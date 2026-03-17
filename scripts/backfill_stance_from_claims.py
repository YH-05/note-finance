#!/usr/bin/env python3
"""Backfill Stance nodes from existing Claim nodes in research-neo4j.

Scans Claims with ``rating`` or ``target_price`` properties, extracts the
analyst/institution name from the content text, and creates:

- Author nodes (``author_type = "sell_side"``)
- Stance nodes with rating/target_price/sentiment
- HOLDS_STANCE, ON_ENTITY, BASED_ON relationships
- SUPERSEDES chains for same (author, entity) pairs
- AUTHORED_BY from Source to Author

Usage
-----
::

    # Dry-run (report only)
    uv run python scripts/backfill_stance_from_claims.py --dry-run

    # Execute
    uv run python scripts/backfill_stance_from_claims.py
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys

from neo4j import GraphDatabase

from pdf_pipeline.services.id_generator import (
    generate_author_id,
    generate_stance_id,
)

logger = logging.getLogger(__name__)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7688")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# Pattern: "<Analyst> rates <Entity> <Rating> with TP <Price>"
_ANALYST_RE = re.compile(
    r"^([A-Z][A-Za-z&./\s]+?)\s+rates\s+",
)

# Rating → sentiment mapping
_SENTIMENT_MAP: dict[str, str] = {
    "Buy": "bullish",
    "Overweight": "bullish",
    "Outperform": "bullish",
    "Hold": "neutral",
    "Neutral": "neutral",
    "Equal-weight": "neutral",
    "Sell": "bearish",
    "Underweight": "bearish",
    "Underperform": "bearish",
}


def _extract_analyst_name(content: str) -> str | None:
    """Extract analyst/institution name from Claim content."""
    m = _ANALYST_RE.match(content)
    if m:
        return m.group(1).strip()
    return None


def _rating_to_sentiment(rating: str) -> str:
    """Map rating string to sentiment."""
    return _SENTIMENT_MAP.get(rating, "neutral")


def _fetch_claims(driver: GraphDatabase.driver) -> list[dict]:
    """Fetch Claims with rating/target_price and their Entity."""
    query = """
    MATCH (c:Claim)
    WHERE c.rating IS NOT NULL OR c.target_price IS NOT NULL
    OPTIONAL MATCH (c)-[:ABOUT]->(e:Entity)
    OPTIONAL MATCH (s:Source)-[:MAKES_CLAIM]->(c)
    RETURN c.claim_id AS claim_id,
           c.rating AS rating,
           c.target_price AS target_price,
           c.content AS content,
           e.entity_id AS entity_id,
           e.name AS entity_name,
           s.source_id AS source_id
    """
    with driver.session() as session:
        result = session.run(query)
        return [dict(record) for record in result]


def _build_backfill_data(claims: list[dict]) -> dict:
    """Build Stance, Author, and relationship data from Claims."""
    authors: dict[str, dict] = {}
    stances: list[dict] = []
    holds_stance: list[dict] = []
    on_entity: list[dict] = []
    based_on: list[dict] = []
    authored_by: list[dict] = []

    for claim in claims:
        content = claim.get("content", "")
        analyst_name = _extract_analyst_name(content)
        if not analyst_name:
            logger.warning(
                "Could not extract analyst from claim: %.60s...",
                content,
            )
            continue

        entity_name = claim.get("entity_name", "")
        entity_id = claim.get("entity_id")
        rating = claim.get("rating", "")
        target_price = claim.get("target_price")

        if not entity_name or not entity_id:
            continue

        # Author
        author_type = "sell_side"
        author_id = generate_author_id(analyst_name, author_type)
        if analyst_name not in authors:
            authors[analyst_name] = {
                "author_id": author_id,
                "name": analyst_name,
                "author_type": author_type,
                "organization": analyst_name,
            }

        # Stance (use empty date since original claims lack as_of_date)
        as_of_date = ""
        stance_id = generate_stance_id(analyst_name, entity_name, as_of_date)
        sentiment = _rating_to_sentiment(rating)

        stances.append(
            {
                "stance_id": stance_id,
                "rating": rating,
                "sentiment": sentiment,
                "target_price": target_price,
                "target_price_currency": "IDR",
                "as_of_date": as_of_date,
                "author_name": analyst_name,
                "entity_name": entity_name,
            }
        )

        # HOLDS_STANCE: Author → Stance
        holds_stance.append(
            {"from_id": author_id, "to_id": stance_id, "type": "HOLDS_STANCE"}
        )

        # ON_ENTITY: Stance → Entity
        on_entity.append(
            {"from_id": stance_id, "to_id": entity_id, "type": "ON_ENTITY"}
        )

        # BASED_ON: Stance → Claim
        claim_id = claim.get("claim_id")
        if claim_id:
            based_on.append(
                {
                    "from_id": stance_id,
                    "to_id": claim_id,
                    "type": "BASED_ON",
                    "role": "supporting",
                }
            )

        # AUTHORED_BY: Source → Author
        source_id = claim.get("source_id")
        if source_id:
            authored_by.append(
                {"from_id": source_id, "to_id": author_id, "type": "AUTHORED_BY"}
            )

    # Deduplicate authored_by
    seen_ab: set[tuple[str, str]] = set()
    unique_ab: list[dict] = []
    for ab in authored_by:
        key = (ab["from_id"], ab["to_id"])
        if key not in seen_ab:
            seen_ab.add(key)
            unique_ab.append(ab)

    return {
        "authors": list(authors.values()),
        "stances": stances,
        "holds_stance": holds_stance,
        "on_entity": on_entity,
        "based_on": based_on,
        "authored_by": unique_ab,
    }


def _write_to_neo4j(driver: GraphDatabase.driver, data: dict) -> dict[str, int]:
    """Write backfill data to Neo4j."""
    counts: dict[str, int] = {}

    with driver.session() as session:
        # Authors
        if data["authors"]:
            session.run(
                """
                UNWIND $authors AS author
                MERGE (a:Author {author_id: author.author_id})
                SET a.name = author.name,
                    a.author_type = author.author_type,
                    a.organization = author.organization
                """,
                authors=data["authors"],
            )
            counts["authors"] = len(data["authors"])

        # Stances
        if data["stances"]:
            session.run(
                """
                UNWIND $stances AS stance
                MERGE (st:Stance {stance_id: stance.stance_id})
                SET st.rating = stance.rating,
                    st.sentiment = stance.sentiment,
                    st.target_price = stance.target_price,
                    st.target_price_currency = stance.target_price_currency,
                    st.as_of_date = stance.as_of_date
                """,
                stances=data["stances"],
            )
            counts["stances"] = len(data["stances"])

        # HOLDS_STANCE
        if data["holds_stance"]:
            session.run(
                """
                UNWIND $rels AS rel
                MATCH (a:Author {author_id: rel.from_id})
                MATCH (st:Stance {stance_id: rel.to_id})
                MERGE (a)-[:HOLDS_STANCE]->(st)
                """,
                rels=data["holds_stance"],
            )
            counts["holds_stance"] = len(data["holds_stance"])

        # ON_ENTITY
        if data["on_entity"]:
            session.run(
                """
                UNWIND $rels AS rel
                MATCH (st:Stance {stance_id: rel.from_id})
                MATCH (e:Entity {entity_id: rel.to_id})
                MERGE (st)-[:ON_ENTITY]->(e)
                """,
                rels=data["on_entity"],
            )
            counts["on_entity"] = len(data["on_entity"])

        # BASED_ON
        if data["based_on"]:
            session.run(
                """
                UNWIND $rels AS rel
                MATCH (st:Stance {stance_id: rel.from_id})
                MATCH (c:Claim {claim_id: rel.to_id})
                MERGE (st)-[r:BASED_ON]->(c)
                SET r.role = rel.role
                """,
                rels=data["based_on"],
            )
            counts["based_on"] = len(data["based_on"])

        # AUTHORED_BY
        if data["authored_by"]:
            session.run(
                """
                UNWIND $rels AS rel
                MATCH (s:Source {source_id: rel.from_id})
                MATCH (a:Author {author_id: rel.to_id})
                MERGE (s)-[:AUTHORED_BY]->(a)
                """,
                rels=data["authored_by"],
            )
            counts["authored_by"] = len(data["authored_by"])

        # Constraints
        session.run(
            "CREATE CONSTRAINT IF NOT EXISTS FOR (a:Author) REQUIRE a.author_id IS UNIQUE"
        )
        session.run(
            "CREATE CONSTRAINT IF NOT EXISTS FOR (st:Stance) REQUIRE st.stance_id IS UNIQUE"
        )

    return counts


def main(args: list[str] | None = None) -> int:
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    parser = argparse.ArgumentParser(description="Backfill Stance from Claims")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no writes")
    parser.add_argument("--uri", default=NEO4J_URI, help="Neo4j URI")
    parsed = parser.parse_args(args)

    driver = GraphDatabase.driver(parsed.uri, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        claims = _fetch_claims(driver)
        logger.info("Found %d claims with rating/target_price", len(claims))

        if not claims:
            print("No claims with rating/target_price found.")
            return 0

        data = _build_backfill_data(claims)

        print(f"\n=== Backfill Stance from Claims {'(DRY RUN)' if parsed.dry_run else ''} ===")
        print(f"  Authors:      {len(data['authors'])}")
        print(f"  Stances:      {len(data['stances'])}")
        print(f"  HOLDS_STANCE: {len(data['holds_stance'])}")
        print(f"  ON_ENTITY:    {len(data['on_entity'])}")
        print(f"  BASED_ON:     {len(data['based_on'])}")
        print(f"  AUTHORED_BY:  {len(data['authored_by'])}")

        for author in data["authors"]:
            print(f"    Author: {author['name']}")
        for stance in data["stances"]:
            print(
                f"    Stance: {stance['author_name']} → {stance['entity_name']} "
                f"({stance['rating']}, TP={stance['target_price']})"
            )

        if parsed.dry_run:
            print("\nDry run complete. No changes written.")
            return 0

        counts = _write_to_neo4j(driver, data)
        print("\n--- Written to Neo4j ---")
        for k, v in counts.items():
            print(f"  {k}: {v}")

        return 0

    finally:
        driver.close()


if __name__ == "__main__":
    sys.exit(main())
