#!/usr/bin/env python3
"""Batch-restructure Neo4j Claim nodes with sentiment and claim_type.

Reads all Claim nodes (with their Source context), classifies each via
Claude API into one of 12 claim types with sentiment/magnitude scores,
and writes the results back to Neo4j.

Usage
-----
::

    # Dry run (classify but don't write to Neo4j)
    ANTHROPIC_API_KEY=sk-... python3 scripts/restructure_claims.py --dry-run

    # Full run
    ANTHROPIC_API_KEY=sk-... python3 scripts/restructure_claims.py

    # Resume from a previous run (skip already-classified claims)
    ANTHROPIC_API_KEY=sk-... python3 scripts/restructure_claims.py --resume

    # Process only N claims (for testing)
    ANTHROPIC_API_KEY=sk-... python3 scripts/restructure_claims.py --limit 10

Environment Variables
---------------------
ANTHROPIC_API_KEY : str
    Anthropic API key (required).
NEO4J_URI : str
    Neo4j connection URI (default: bolt://localhost:7687).
NEO4J_USERNAME : str
    Neo4j username (default: neo4j).
NEO4J_PASSWORD : str
    Neo4j password (required).

References
----------
- dec-schema-003: Claim再構造化の合意
- act-schema-001: Phase 1 実装タスク
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anthropic
from neo4j import GraphDatabase

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CLAIM_TYPES = [
    "bullish",
    "bearish",
    "earnings_beat",
    "earnings_miss",
    "guidance_up",
    "guidance_down",
    "policy_hawkish",
    "policy_dovish",
    "sector_rotation",
    "risk_event",
    "technical",
    "fundamental",
]
"""12 claim types defined in dec-schema-003."""

BATCH_SIZE = 20
"""Number of claims to classify per API call."""

CHECKPOINT_DIR = Path(".tmp/claim-restructure")
"""Directory for checkpoint files."""

CLASSIFICATION_PROMPT = """\
You are a financial analyst. Classify each claim into exactly one of these 12 types:
- bullish: Positive outlook on a stock/market/sector
- bearish: Negative outlook on a stock/market/sector
- earnings_beat: Company exceeded earnings expectations
- earnings_miss: Company missed earnings expectations
- guidance_up: Company raised forward guidance
- guidance_down: Company lowered forward guidance
- policy_hawkish: Tighter monetary/fiscal policy signals
- policy_dovish: Looser monetary/fiscal policy signals
- sector_rotation: Capital flowing between sectors
- risk_event: Geopolitical, regulatory, or systemic risk
- technical: Chart pattern or technical indicator analysis
- fundamental: Valuation, financial ratio, or business model analysis

For each claim, also provide:
- sentiment: float from -1.0 (very negative) to 1.0 (very positive)
- magnitude: float from 0.0 (trivial) to 1.0 (highly significant)

Return ONLY a JSON array. Each element must have:
{{"claim_id": "...", "claim_type": "...", "sentiment": 0.0, "magnitude": 0.0}}

Claims to classify:
{claims_json}
"""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ClaimRecord:
    """A Claim node with Source context."""

    claim_id: str
    content: str
    source_title: str
    source_type: str
    category: str
    entity_names: list[str]


@dataclass
class ClassificationResult:
    """Classification output for a single Claim."""

    claim_id: str
    claim_type: str
    sentiment: float
    magnitude: float


# ---------------------------------------------------------------------------
# Neo4j operations
# ---------------------------------------------------------------------------


def fetch_claims(driver: Any, *, limit: int = 0, resume: bool = False) -> list[ClaimRecord]:
    """Fetch Claim nodes with Source context from Neo4j.

    Parameters
    ----------
    driver
        Neo4j driver instance.
    limit : int
        Max claims to fetch (0 = all).
    resume : bool
        If True, skip claims that already have a non-'analysis' claim_type.

    Returns
    -------
    list[ClaimRecord]
        Claims ready for classification.
    """
    where_clause = ""
    if resume:
        where_clause = "WHERE c.claim_type = 'analysis' OR c.claim_type IS NULL"

    limit_clause = f"LIMIT {limit}" if limit > 0 else ""

    query = f"""
    MATCH (s:Source)-[:MAKES_CLAIM]->(c:Claim)
    {where_clause}
    OPTIONAL MATCH (c)-[:ABOUT]->(e:Entity)
    WITH s, c, collect(DISTINCT e.name) AS entity_names
    RETURN c.claim_id AS claim_id,
           c.content AS content,
           s.title AS source_title,
           s.source_type AS source_type,
           s.category AS category,
           entity_names
    ORDER BY s.collected_at DESC
    {limit_clause}
    """

    with driver.session() as session:
        result = session.run(query)
        records = []
        seen_ids: set[str] = set()
        for record in result:
            cid = record["claim_id"]
            if cid in seen_ids:
                continue
            seen_ids.add(cid)
            records.append(
                ClaimRecord(
                    claim_id=cid,
                    content=record["content"] or "",
                    source_title=record["source_title"] or "",
                    source_type=record["source_type"] or "",
                    category=record["category"] or "",
                    entity_names=record["entity_names"] or [],
                )
            )

    logger.info("Fetched %d claims from Neo4j", len(records))
    return records


def write_classifications(driver: Any, results: list[ClassificationResult]) -> int:
    """Write classification results back to Neo4j.

    Parameters
    ----------
    driver
        Neo4j driver instance.
    results : list[ClassificationResult]
        Classification results to write.

    Returns
    -------
    int
        Number of claims updated.
    """
    query = """
    UNWIND $batch AS item
    MATCH (c:Claim {claim_id: item.claim_id})
    SET c.claim_type = item.claim_type,
        c.sentiment = item.sentiment,
        c.magnitude = item.magnitude,
        c.classified_at = datetime()
    RETURN count(c) AS updated
    """

    batch = [
        {
            "claim_id": r.claim_id,
            "claim_type": r.claim_type,
            "sentiment": r.sentiment,
            "magnitude": r.magnitude,
        }
        for r in results
    ]

    with driver.session() as session:
        result = session.run(query, batch=batch)
        updated = result.single()["updated"]

    logger.info("Updated %d claims in Neo4j", updated)
    return updated


# ---------------------------------------------------------------------------
# Claude API classification
# ---------------------------------------------------------------------------


def classify_batch(
    client: anthropic.Anthropic,
    claims: list[ClaimRecord],
) -> list[ClassificationResult]:
    """Classify a batch of claims via Claude API.

    Parameters
    ----------
    client
        Anthropic client.
    claims : list[ClaimRecord]
        Claims to classify.

    Returns
    -------
    list[ClassificationResult]
        Classification results.
    """
    claims_for_prompt = [
        {
            "claim_id": c.claim_id,
            "content": c.content,
            "source_title": c.source_title,
            "entities": c.entity_names[:5],
        }
        for c in claims
    ]

    prompt = CLASSIFICATION_PROMPT.format(
        claims_json=json.dumps(claims_for_prompt, ensure_ascii=False, indent=2)
    )

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = response.content[0].text.strip()

    # Extract JSON from response (handle markdown code blocks)
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        json_lines = []
        in_block = False
        for line in lines:
            if line.startswith("```") and not in_block:
                in_block = True
                continue
            if line.startswith("```") and in_block:
                break
            if in_block:
                json_lines.append(line)
        response_text = "\n".join(json_lines)

    parsed = json.loads(response_text)

    results = []
    for item in parsed:
        claim_type = item.get("claim_type", "fundamental")
        if claim_type not in CLAIM_TYPES:
            claim_type = "fundamental"

        sentiment = max(-1.0, min(1.0, float(item.get("sentiment", 0.0))))
        magnitude = max(0.0, min(1.0, float(item.get("magnitude", 0.5))))

        results.append(
            ClassificationResult(
                claim_id=item["claim_id"],
                claim_type=claim_type,
                sentiment=sentiment,
                magnitude=magnitude,
            )
        )

    return results


# ---------------------------------------------------------------------------
# Checkpoint management
# ---------------------------------------------------------------------------


def load_checkpoint() -> set[str]:
    """Load previously processed claim IDs from checkpoint.

    Returns
    -------
    set[str]
        Set of already-processed claim IDs.
    """
    checkpoint_file = CHECKPOINT_DIR / "processed_ids.json"
    if checkpoint_file.exists():
        with checkpoint_file.open() as f:
            return set(json.load(f))
    return set()


def save_checkpoint(processed_ids: set[str]) -> None:
    """Save processed claim IDs to checkpoint file.

    Parameters
    ----------
    processed_ids : set[str]
        Set of processed claim IDs.
    """
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    checkpoint_file = CHECKPOINT_DIR / "processed_ids.json"
    with checkpoint_file.open("w") as f:
        json.dump(sorted(processed_ids), f)


def save_results_log(results: list[ClassificationResult]) -> None:
    """Append results to a log file for auditing.

    Parameters
    ----------
    results : list[ClassificationResult]
        Results to log.
    """
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    log_file = CHECKPOINT_DIR / "classification_log.jsonl"
    with log_file.open("a") as f:
        for r in results:
            f.write(
                json.dumps(
                    {
                        "claim_id": r.claim_id,
                        "claim_type": r.claim_type,
                        "sentiment": r.sentiment,
                        "magnitude": r.magnitude,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Batch-restructure Neo4j Claim nodes with sentiment and claim_type.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Classify but don't write to Neo4j",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip already-classified claims",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process only N claims (0 = all)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help=f"Claims per API call (default: {BATCH_SIZE})",
    )
    return parser.parse_args(args)


def main(args: list[str] | None = None) -> int:
    """Main entry point.

    Returns
    -------
    int
        Exit code (0 = success).
    """
    parsed = parse_args(args)

    # Validate environment
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY environment variable is required")
        print("Error: Set ANTHROPIC_API_KEY environment variable", file=sys.stderr)
        return 1

    neo4j_uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.environ.get("NEO4J_USERNAME", "neo4j")
    neo4j_pass = os.environ.get("NEO4J_PASSWORD")
    if not neo4j_pass:
        logger.error("NEO4J_PASSWORD environment variable is required")
        print("Error: Set NEO4J_PASSWORD environment variable", file=sys.stderr)
        return 1

    # Connect
    client = anthropic.Anthropic(api_key=api_key)
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_pass))

    try:
        driver.verify_connectivity()
        logger.info("Connected to Neo4j at %s", neo4j_uri)
    except Exception as exc:
        logger.error("Failed to connect to Neo4j: %s", exc)
        return 1

    try:
        # Fetch claims
        claims = fetch_claims(driver, limit=parsed.limit, resume=parsed.resume)
        if not claims:
            logger.info("No claims to process")
            print("No claims to process.")
            return 0

        # Load checkpoint for additional filtering
        processed_ids = load_checkpoint()
        if parsed.resume and processed_ids:
            claims = [c for c in claims if c.claim_id not in processed_ids]
            logger.info("After checkpoint filter: %d claims remaining", len(claims))

        if not claims:
            logger.info("All claims already processed")
            print("All claims already processed.")
            return 0

        # Process in batches
        total_classified = 0
        total_written = 0
        batch_count = (len(claims) + parsed.batch_size - 1) // parsed.batch_size

        print(f"Processing {len(claims)} claims in {batch_count} batches...")

        for i in range(0, len(claims), parsed.batch_size):
            batch = claims[i : i + parsed.batch_size]
            batch_num = i // parsed.batch_size + 1

            logger.info("Processing batch %d/%d (%d claims)", batch_num, batch_count, len(batch))
            print(f"  Batch {batch_num}/{batch_count}: classifying {len(batch)} claims...", end="")

            try:
                results = classify_batch(client, batch)
                total_classified += len(results)

                # Save to log
                save_results_log(results)

                # Write to Neo4j
                if not parsed.dry_run:
                    written = write_classifications(driver, results)
                    total_written += written

                # Update checkpoint
                for r in results:
                    processed_ids.add(r.claim_id)
                save_checkpoint(processed_ids)

                print(f" done ({len(results)} classified)")

                # Rate limiting: wait between batches
                if i + parsed.batch_size < len(claims):
                    time.sleep(1)

            except json.JSONDecodeError as exc:
                logger.error("Failed to parse API response for batch %d: %s", batch_num, exc)
                print(f" FAILED (JSON parse error)")
                continue
            except anthropic.APIError as exc:
                logger.error("API error for batch %d: %s", batch_num, exc)
                print(f" FAILED (API error: {exc})")
                # Save checkpoint and retry on next run
                save_checkpoint(processed_ids)
                if "rate_limit" in str(exc).lower():
                    logger.info("Rate limited, waiting 60s...")
                    time.sleep(60)
                continue

        # Summary
        mode = "DRY RUN" if parsed.dry_run else "LIVE"
        print(f"\n--- Summary ({mode}) ---")
        print(f"  Claims classified: {total_classified}/{len(claims)}")
        if not parsed.dry_run:
            print(f"  Claims written to Neo4j: {total_written}")
        print(f"  Checkpoint: {CHECKPOINT_DIR / 'processed_ids.json'}")
        print(f"  Log: {CHECKPOINT_DIR / 'classification_log.jsonl'}")

        return 0

    finally:
        driver.close()


if __name__ == "__main__":
    sys.exit(main())
