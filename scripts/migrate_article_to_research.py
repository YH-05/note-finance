#!/usr/bin/env python3
"""Migrate article-neo4j data into research-neo4j.

Usage:
    uv run python scripts/migrate_article_to_research.py [--dry-run]

Strategy:
- Entity: MERGE on entity_key (semantic key), preserve research-neo4j's entity_id/ticker
- Topic: MERGE on topic_key, preserve research-neo4j's topic_id
- Source/Chunk/Fact/Claim: MERGE on their *_id (UUIDs, no collision expected)
- Article/XPost/Quote: new labels, create constraints first
- Relationships: re-link using unique keys
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections import defaultdict

from neo4j import GraphDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# Connection settings
ARTICLE_URI = "bolt://localhost:7689"
RESEARCH_URI = "bolt://localhost:7688"
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "gomasuke")
AUTH = ("neo4j", NEO4J_PASSWORD)

# Unique key mapping per label (used for MERGE)
LABEL_UNIQUE_KEY: dict[str, str] = {
    "Source": "source_id",
    "Chunk": "chunk_id",
    "Entity": "entity_key",  # Semantic key for dedup
    "Fact": "fact_id",
    "Topic": "topic_key",  # Semantic key for dedup
    "Claim": "claim_id",
    "Article": "article_id",
    "XPost": "xpost_id",
    "Quote": "quote_id",
    "Insight": "insight_id",
    "Stance": "stance_id",
    "Question": "question_id",
}

# Properties to NOT overwrite if node already exists in research
PRESERVE_ON_MERGE: dict[str, set[str]] = {
    "Entity": {"entity_id", "ticker"},
    "Topic": {"topic_id"},
}


def read_all_nodes(session) -> list[dict]:
    """Read all nodes from article-neo4j with labels and properties."""
    result = session.run(
        """
        MATCH (n)
        RETURN labels(n) AS labels, properties(n) AS props, elementId(n) AS eid
        """
    )
    return [dict(r) for r in result]


def read_all_relationships(session) -> list[dict]:
    """Read all relationships with start/end node unique keys."""
    result = session.run(
        """
        MATCH (a)-[r]->(b)
        RETURN
            type(r) AS rel_type,
            properties(r) AS rel_props,
            labels(a) AS start_labels,
            properties(a) AS start_props,
            labels(b) AS end_labels,
            properties(b) AS end_props
        """
    )
    return [dict(r) for r in result]


def get_node_merge_key(labels: list[str], props: dict) -> tuple[str, str, object] | None:
    """Determine the label and unique key for MERGE.

    Returns (label, key_name, key_value) or None if unknown label.
    """
    for label in labels:
        if label in LABEL_UNIQUE_KEY:
            key_name = LABEL_UNIQUE_KEY[label]
            key_value = props.get(key_name)
            if key_value is not None:
                return label, key_name, key_value
    return None


def create_missing_constraints(session, dry_run: bool) -> None:
    """Create constraints for labels that only exist in article-neo4j."""
    new_constraints = [
        ("Article", "article_id", "article_id_uniq"),
        ("XPost", "xpost_id", "xpost_id_uniq"),
        ("Quote", "quote_id", "quote_id_uniq"),
    ]

    # Check existing constraints
    existing = session.run("SHOW CONSTRAINTS")
    existing_names = {r["name"] for r in existing}

    for label, prop, name in new_constraints:
        if name in existing_names:
            logger.info("Constraint already exists: %s", name)
            continue
        cypher = (
            f"CREATE CONSTRAINT {name} IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
        )
        if dry_run:
            logger.info("DRY RUN: Would create constraint: %s", cypher)
        else:
            session.run(cypher)
            logger.info("Created constraint: %s", name)


def merge_node(tx, label: str, key_name: str, key_value: object, props: dict) -> None:
    """MERGE a single node into research-neo4j."""
    preserve = PRESERVE_ON_MERGE.get(label, set())

    # Build SET clause: use SET for new nodes, skip preserved keys for existing
    set_parts = []
    params = {"key_value": key_value}
    for k, v in props.items():
        if k == key_name:
            continue  # Already in MERGE
        if k in preserve:
            # ON CREATE SET only (don't overwrite existing)
            set_parts.append(("create", k, v))
        else:
            set_parts.append(("always", k, v))

    create_sets = []
    match_sets = []
    for mode, k, v in set_parts:
        param_name = f"p_{k}"
        params[param_name] = v
        if mode == "create":
            create_sets.append(f"n.{k} = ${param_name}")
        else:
            match_sets.append(f"n.{k} = ${param_name}")

    cypher = f"MERGE (n:{label} {{{key_name}: $key_value}})"
    if create_sets:
        cypher += f"\nON CREATE SET {', '.join(create_sets + match_sets)}"
        if match_sets:
            cypher += f"\nON MATCH SET {', '.join(match_sets)}"
    elif match_sets:
        cypher += f"\nSET {', '.join(match_sets)}"

    tx.run(cypher, **params)


def merge_relationship(
    tx,
    rel_type: str,
    rel_props: dict,
    start_label: str,
    start_key_name: str,
    start_key_value: object,
    end_label: str,
    end_key_name: str,
    end_key_value: object,
) -> None:
    """MERGE a relationship into research-neo4j."""
    params = {
        "start_key": start_key_value,
        "end_key": end_key_value,
    }

    cypher = (
        f"MATCH (a:{start_label} {{{start_key_name}: $start_key}})\n"
        f"MATCH (b:{end_label} {{{end_key_name}: $end_key}})\n"
        f"MERGE (a)-[r:{rel_type}]->(b)"
    )

    if rel_props:
        set_parts = []
        for k, v in rel_props.items():
            param_name = f"rp_{k}"
            params[param_name] = v
            set_parts.append(f"r.{k} = ${param_name}")
        cypher += f"\nSET {', '.join(set_parts)}"

    tx.run(cypher, **params)


def verify_migration(article_session, research_session) -> bool:
    """Verify migration by comparing counts."""
    art_nodes = article_session.run(
        "MATCH (n) RETURN count(n) AS cnt"
    ).single()["cnt"]
    art_rels = article_session.run(
        "MATCH ()-[r]->() RETURN count(r) AS cnt"
    ).single()["cnt"]

    res_nodes = research_session.run(
        "MATCH (n) RETURN count(n) AS cnt"
    ).single()["cnt"]
    res_rels = research_session.run(
        "MATCH ()-[r]->() RETURN count(r) AS cnt"
    ).single()["cnt"]

    logger.info(
        "Verification — article: %d nodes, %d rels | research: %d nodes, %d rels",
        art_nodes, art_rels, res_nodes, res_rels,
    )
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate article-neo4j → research-neo4j")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    args = parser.parse_args()

    logger.info(
        "Starting migration: %s → %s (dry_run=%s)",
        ARTICLE_URI, RESEARCH_URI, args.dry_run,
    )

    article_driver = GraphDatabase.driver(ARTICLE_URI, auth=AUTH)
    research_driver = GraphDatabase.driver(RESEARCH_URI, auth=AUTH)

    try:
        article_driver.verify_connectivity()
        research_driver.verify_connectivity()
        logger.info("Connected to both databases")

        # Get initial research counts
        with research_driver.session() as rs:
            initial_nodes = rs.run("MATCH (n) RETURN count(n) AS cnt").single()["cnt"]
            initial_rels = rs.run("MATCH ()-[r]->() RETURN count(r) AS cnt").single()["cnt"]
            logger.info("Research DB initial: %d nodes, %d rels", initial_nodes, initial_rels)

        # Phase 1: Read all data from article-neo4j
        with article_driver.session() as asess:
            nodes = read_all_nodes(asess)
            rels = read_all_relationships(asess)
            logger.info("Read from article-neo4j: %d nodes, %d rels", len(nodes), len(rels))

        # Phase 2: Create missing constraints in research-neo4j
        with research_driver.session() as rs:
            create_missing_constraints(rs, args.dry_run)

        # Phase 3: MERGE nodes
        stats: dict[str, int] = defaultdict(int)
        skipped: list[str] = []

        with research_driver.session() as rs:
            for node in nodes:
                labels = node["labels"]
                props = node["props"]
                merge_info = get_node_merge_key(labels, props)

                if merge_info is None:
                    skipped.append(f"Unknown label: {labels}")
                    continue

                label, key_name, key_value = merge_info

                if args.dry_run:
                    logger.debug("DRY RUN: Would merge %s(%s=%s)", label, key_name, key_value)
                else:
                    rs.execute_write(
                        lambda tx, l=label, kn=key_name, kv=key_value, p=props: merge_node(
                            tx, l, kn, kv, p
                        )
                    )
                stats[label] += 1

            logger.info("Nodes processed: %s (skipped: %d)", dict(stats), len(skipped))
            if skipped:
                for s in skipped[:10]:
                    logger.warning("Skipped node: %s", s)

        # Phase 4: MERGE relationships
        rel_stats: dict[str, int] = defaultdict(int)
        rel_skipped: list[str] = []

        with research_driver.session() as rs:
            for rel in rels:
                start_info = get_node_merge_key(rel["start_labels"], rel["start_props"])
                end_info = get_node_merge_key(rel["end_labels"], rel["end_props"])

                if start_info is None or end_info is None:
                    rel_skipped.append(
                        f"Cannot resolve: ({rel['start_labels']})"
                        f"-[:{rel['rel_type']}]->({rel['end_labels']})"
                    )
                    continue

                start_label, start_key_name, start_key_value = start_info
                end_label, end_key_name, end_key_value = end_info

                if args.dry_run:
                    logger.debug(
                        "DRY RUN: Would merge (%s)-[:%s]->(%s)",
                        f"{start_label}({start_key_value})",
                        rel["rel_type"],
                        f"{end_label}({end_key_value})",
                    )
                else:
                    rs.execute_write(
                        lambda tx, rt=rel["rel_type"], rp=rel["rel_props"],
                        sl=start_label, skn=start_key_name, skv=start_key_value,
                        el=end_label, ekn=end_key_name, ekv=end_key_value: merge_relationship(
                            tx, rt, rp, sl, skn, skv, el, ekn, ekv
                        )
                    )
                rel_stats[rel["rel_type"]] += 1

            logger.info("Rels processed: %s (skipped: %d)", dict(rel_stats), len(rel_skipped))
            if rel_skipped:
                for s in rel_skipped[:10]:
                    logger.warning("Skipped rel: %s", s)

        # Phase 5: Verify
        if not args.dry_run:
            with article_driver.session() as asess, research_driver.session() as rs:
                verify_migration(asess, rs)

            with research_driver.session() as rs:
                final_nodes = rs.run("MATCH (n) RETURN count(n) AS cnt").single()["cnt"]
                final_rels = rs.run("MATCH ()-[r]->() RETURN count(r) AS cnt").single()["cnt"]
                logger.info(
                    "Migration complete: %d→%d nodes (+%d), %d→%d rels (+%d)",
                    initial_nodes, final_nodes, final_nodes - initial_nodes,
                    initial_rels, final_rels, final_rels - initial_rels,
                )
        else:
            logger.info(
                "DRY RUN complete: would process %d nodes, %d rels",
                sum(stats.values()), sum(rel_stats.values()),
            )

    except Exception:
        logger.exception("Migration failed")
        sys.exit(1)
    finally:
        article_driver.close()
        research_driver.close()


if __name__ == "__main__":
    main()
