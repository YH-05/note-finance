#!/usr/bin/env python3
"""Backfill NEXT_PERIOD and TREND relationships in research-neo4j.

Reads existing FiscalPeriod and FinancialDataPoint nodes, builds
temporal chains (NEXT_PERIOD between consecutive periods, TREND between
consecutive datapoints for the same metric), and writes them back.

Only MEASURES-linked datapoints are eligible for TREND (research-neo4j
convention — avoids comparing unresolved metric names).

Usage
-----
::

    # Dry-run (report only)
    uv run python scripts/backfill_temporal_chain.py --dry-run

    # Execute
    uv run python scripts/backfill_temporal_chain.py
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from neo4j import GraphDatabase

# Import shared logic from emit_graph_queue
sys.path.insert(0, str(Path(__file__).resolve().parent))
from emit_graph_queue import (
    _build_next_period_chain,
    _build_trend_edges,
)

logger = logging.getLogger(__name__)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7688")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


def _fetch_fiscal_periods(driver: GraphDatabase.driver) -> list[dict]:
    """Fetch all FiscalPeriod nodes."""
    query = """
    MATCH (fp:FiscalPeriod)
    RETURN fp.period_id AS period_id,
           fp.period_label AS period_label,
           fp.period_type AS period_type,
           fp.year AS year
    """
    with driver.session() as session:
        result = session.run(query)
        return [dict(record) for record in result]


def _fetch_datapoints_with_periods(driver: GraphDatabase.driver) -> dict:
    """Fetch FinancialDataPoints with FOR_PERIOD rels and MEASURES status."""
    dp_query = """
    MATCH (dp:FinancialDataPoint)
    RETURN dp.datapoint_id AS datapoint_id,
           dp.metric_name AS metric_name,
           dp.value AS value
    """
    fp_rel_query = """
    MATCH (dp:FinancialDataPoint)-[:FOR_PERIOD]->(fp:FiscalPeriod)
    RETURN dp.datapoint_id AS from_id, fp.period_id AS to_id
    """
    measures_query = """
    MATCH (dp:FinancialDataPoint)-[:MEASURES]->(m:Metric)
    RETURN dp.datapoint_id AS dp_id
    """
    with driver.session() as session:
        dps = [dict(r) for r in session.run(dp_query)]
        for_period = [dict(r) for r in session.run(fp_rel_query)]
        measures = {r["dp_id"] for r in session.run(measures_query)}

    return {
        "datapoints": dps,
        "for_period": for_period,
        "measures_linked": measures,
    }


def _write_next_period(driver: GraphDatabase.driver, rels: list[dict]) -> int:
    """Write NEXT_PERIOD relationships to Neo4j."""
    if not rels:
        return 0
    with driver.session() as session:
        session.run(
            """
            UNWIND $rels AS rel
            MATCH (from:FiscalPeriod {period_id: rel.from_id})
            MATCH (to:FiscalPeriod {period_id: rel.to_id})
            MERGE (from)-[r:NEXT_PERIOD]->(to)
            SET r.gap_months = rel.gap_months
            """,
            rels=rels,
        )
    return len(rels)


def _write_trend(driver: GraphDatabase.driver, rels: list[dict]) -> int:
    """Write TREND relationships to Neo4j."""
    if not rels:
        return 0
    with driver.session() as session:
        session.run(
            """
            UNWIND $rels AS rel
            MATCH (from:FinancialDataPoint {datapoint_id: rel.from_id})
            MATCH (to:FinancialDataPoint {datapoint_id: rel.to_id})
            MERGE (from)-[r:TREND]->(to)
            SET r.change_pct = rel.change_pct,
                r.direction = rel.direction,
                r.metric_id = rel.metric_id
            """,
            rels=rels,
        )
    return len(rels)


def main(args: list[str] | None = None) -> int:
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    parser = argparse.ArgumentParser(description="Backfill temporal chains")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no writes")
    parser.add_argument("--uri", default=NEO4J_URI, help="Neo4j URI")
    parsed = parser.parse_args(args)

    driver = GraphDatabase.driver(parsed.uri, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        # Fetch data
        periods = _fetch_fiscal_periods(driver)
        dp_data = _fetch_datapoints_with_periods(driver)

        logger.info(
            "Fetched %d FiscalPeriods, %d DataPoints (%d MEASURES-linked)",
            len(periods),
            len(dp_data["datapoints"]),
            len(dp_data["measures_linked"]),
        )

        # Build NEXT_PERIOD chain
        next_period_rels = _build_next_period_chain(periods)

        # Build TREND edges (MEASURES-linked only)
        trend_rels = _build_trend_edges(
            dp_data["datapoints"],
            periods,
            dp_data["for_period"],
            measures_linked_dp_ids=dp_data["measures_linked"],
        )

        # Report
        dry_label = " (DRY RUN)" if parsed.dry_run else ""
        print(f"\n=== Backfill Temporal Chain{dry_label} ===")
        print(f"  FiscalPeriods:    {len(periods)}")
        print(f"  DataPoints:       {len(dp_data['datapoints'])}")
        print(f"  MEASURES-linked:  {len(dp_data['measures_linked'])}")
        print(f"  NEXT_PERIOD rels: {len(next_period_rels)}")
        print(f"  TREND rels:       {len(trend_rels)}")

        if next_period_rels:
            print("\n  NEXT_PERIOD chains:")
            for rel in next_period_rels:
                print(f"    {rel['from_id']} → {rel['to_id']} (gap={rel.get('gap_months', '?')}m)")

        if trend_rels:
            print(f"\n  TREND edges (showing first 20 of {len(trend_rels)}):")
            for rel in trend_rels[:20]:
                mid = rel.get("metric_id", "?")
                print(
                    f"    {rel['from_id'][:16]}.. → {rel['to_id'][:16]}.. "
                    f"({rel['direction']}, {rel['change_pct']:+.1f}%, {mid})"
                )

        if parsed.dry_run:
            print("\nDry run complete. No changes written.")
            return 0

        # Write
        np_count = _write_next_period(driver, next_period_rels)
        trend_count = _write_trend(driver, trend_rels)

        print("\n--- Written to Neo4j ---")
        print(f"  NEXT_PERIOD: {np_count}")
        print(f"  TREND:       {trend_count}")

        return 0

    finally:
        driver.close()


if __name__ == "__main__":
    sys.exit(main())
