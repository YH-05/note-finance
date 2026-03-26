#!/usr/bin/env python3
"""Backfill deterministic research-graph gaps in research-neo4j.

Only fills values that can be derived uniquely from existing graph data.
Ambiguous cases are skipped by design.

Usage
-----
::

    uv run python scripts/backfill_deterministic_research_gaps.py --dry-run
    uv run python scripts/backfill_deterministic_research_gaps.py --stage domains
    uv run python scripts/backfill_deterministic_research_gaps.py --stage all --limit 100
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from emit_research_queue import _extract_url_domain, _make_domain_node
from neo4j_utils import create_driver

logger = logging.getLogger(__name__)

STAGES: tuple[str, ...] = ("domains", "facts", "claims", "insights")


@dataclass(slots=True)
class StageResult:
    """Summary for a backfill stage."""

    stage: str
    candidates: int
    to_write: int
    skipped_ambiguous: int
    updated: int = 0
    sample: list[dict[str, Any]] | None = None


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Backfill deterministic research-graph gaps",
    )
    parser.add_argument(
        "--stage",
        default="all",
        choices=(*STAGES, "all"),
        help="Stage to run",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report candidates only, do not write",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional per-stage fetch limit",
    )
    parser.add_argument(
        "--neo4j-uri",
        default="bolt://localhost:7688",
        help="Neo4j URI",
    )
    parser.add_argument(
        "--neo4j-user",
        default="neo4j",
        help="Neo4j username",
    )
    parser.add_argument(
        "--neo4j-password",
        default=None,
        help="Neo4j password (defaults to NEO4J_PASSWORD env var)",
    )
    return parser.parse_args(args)


def _normalize_date_value(value: Any) -> str | None:
    """Normalize a date-like value to ``YYYY-MM-DD``."""
    normalized: str | None = None
    if value is None:
        return normalized
    if isinstance(value, datetime):
        normalized = value.date().isoformat()
    elif isinstance(value, date):
        normalized = value.isoformat()
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if len(text) >= 10:
            prefix = text[:10]
            try:
                normalized = date.fromisoformat(prefix).isoformat()
            except ValueError:
                normalized = None
        if normalized is None:
            try:
                normalized = datetime.fromisoformat(
                    text.replace("Z", "+00:00")
                ).date().isoformat()
            except ValueError:
                normalized = None
    return normalized


def _fetch_domain_candidates(driver: Any, limit: int | None = None) -> list[dict[str, Any]]:
    """Fetch Sources missing domain metadata or FROM_DOMAIN relationships."""
    query = """
    MATCH (s:Source)
    WHERE s.url STARTS WITH 'http'
      AND (
        coalesce(s.domain, '') = ''
        OR NOT EXISTS { MATCH (s)-[:FROM_DOMAIN]->(:Domain) }
      )
    RETURN s.source_id AS source_id,
           s.url AS url,
           s.domain AS domain
    ORDER BY s.source_id
    """
    if limit is not None:
        query += "\nLIMIT $limit"
    with driver.session() as session:
        result = session.run(query, limit=limit)
        return [dict(record) for record in result]


def _build_domain_rows(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Build deterministic domain backfill rows."""
    rows: list[dict[str, Any]] = []
    skipped = 0
    for candidate in candidates:
        domain_name = _extract_url_domain(candidate.get("url", ""))
        if not domain_name:
            skipped += 1
            continue
        domain_node = _make_domain_node(
            domain_name,
            base_url=f"https://{domain_name}",
            default_language="",
        )
        rows.append(
            {
                "source_id": candidate["source_id"],
                "domain_id": domain_node["key_value"],
                "domain_name": domain_name,
                "base_url": domain_node["properties"].get("base_url", ""),
                "default_language": domain_node["properties"].get(
                    "default_language",
                    "",
                ),
            }
        )
    return rows, skipped


def _write_domain_rows(driver: Any, rows: list[dict[str, Any]]) -> int:
    """Write domain backfill rows."""
    if not rows:
        return 0
    with driver.session() as session:
        session.run(
            """
            UNWIND $rows AS row
            MATCH (s:Source {source_id: row.source_id})
            MERGE (d:Domain {domain_id: row.domain_id})
            ON CREATE SET d.name = row.domain_name,
                          d.base_url = row.base_url,
                          d.default_language = row.default_language
            SET s.domain = row.domain_name
            MERGE (s)-[:FROM_DOMAIN]->(d)
            """,
            rows=rows,
        )
    return len(rows)


def _fetch_fact_candidates(driver: Any, limit: int | None = None) -> list[dict[str, Any]]:
    """Fetch Facts linked to extracted Sources."""
    query = """
    MATCH (f:Fact)-[:EXTRACTED_FROM]->(s:Source)
    RETURN f.fact_id AS fact_id,
           f.source_url AS source_url,
           f.as_of_date AS as_of_date,
           count(s) AS source_count,
           collect({
             source_id: s.source_id,
             url: s.url,
             published_at: s.published_at,
             published_date: s.published_date,
             filing_date: s.filing_date
           }) AS sources
    ORDER BY f.fact_id
    """
    if limit is not None:
        query += "\nLIMIT $limit"
    with driver.session() as session:
        result = session.run(query, limit=limit)
        return [dict(record) for record in result]


def _build_fact_rows(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Build deterministic fact backfill rows."""
    rows: list[dict[str, Any]] = []
    skipped = 0
    for candidate in candidates:
        if candidate.get("source_count") != 1:
            skipped += 1
            continue
        sources = candidate.get("sources") or []
        if not sources:
            skipped += 1
            continue
        source = sources[0]
        source_url = None
        if not candidate.get("source_url") and source.get("url"):
            source_url = source["url"]

        as_of_date = None
        if not candidate.get("as_of_date"):
            for key in ("published_at", "published_date", "filing_date"):
                normalized = _normalize_date_value(source.get(key))
                if normalized:
                    as_of_date = normalized
                    break

        if source_url is None and as_of_date is None:
            continue

        rows.append(
            {
                "fact_id": candidate["fact_id"],
                "source_url": source_url,
                "as_of_date": as_of_date,
            }
        )
    return rows, skipped


def _write_fact_rows(driver: Any, rows: list[dict[str, Any]]) -> int:
    """Write fact backfill rows."""
    if not rows:
        return 0
    with driver.session() as session:
        session.run(
            """
            UNWIND $rows AS row
            MATCH (f:Fact {fact_id: row.fact_id})
            SET f.source_url = CASE
                WHEN row.source_url IS NOT NULL AND coalesce(f.source_url, '') = ''
                THEN row.source_url
                ELSE f.source_url
            END,
            f.as_of_date = CASE
                WHEN row.as_of_date IS NOT NULL AND coalesce(f.as_of_date, '') = ''
                THEN row.as_of_date
                ELSE f.as_of_date
            END
            """,
            rows=rows,
        )
    return len(rows)


def _fetch_claim_candidates(driver: Any, limit: int | None = None) -> list[dict[str, Any]]:
    """Fetch Claim->Entity pairs derivable from supported Facts."""
    query = """
    MATCH (c:Claim)-[:SUPPORTED_BY]->(:Fact)-[:RELATES_TO]->(e:Entity)
    WHERE NOT EXISTS { MATCH (c)-[:ABOUT]->(e) }
    RETURN DISTINCT c.claim_id AS claim_id,
                    e.entity_id AS entity_id
    ORDER BY claim_id, entity_id
    """
    if limit is not None:
        query += "\nLIMIT $limit"
    with driver.session() as session:
        result = session.run(query, limit=limit)
        return [dict(record) for record in result]


def _build_claim_rows(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Build Claim->Entity ABOUT rows."""
    seen: set[tuple[str, str]] = set()
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        claim_id = candidate.get("claim_id")
        entity_id = candidate.get("entity_id")
        if not claim_id or not entity_id:
            continue
        key = (claim_id, entity_id)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"claim_id": claim_id, "entity_id": entity_id})
    return rows, 0


def _write_claim_rows(driver: Any, rows: list[dict[str, Any]]) -> int:
    """Write Claim->Entity ABOUT relationships."""
    if not rows:
        return 0
    with driver.session() as session:
        session.run(
            """
            UNWIND $rows AS row
            MATCH (c:Claim {claim_id: row.claim_id})
            MATCH (e:Entity {entity_id: row.entity_id})
            MERGE (c)-[:ABOUT]->(e)
            """,
            rows=rows,
        )
    return len(rows)


def _fetch_insight_candidates(driver: Any, limit: int | None = None) -> list[dict[str, Any]]:
    """Fetch Insights and their derivation context."""
    query = """
    MATCH (i:Insight)
    WHERE NOT EXISTS { MATCH (i)-[:ABOUT]->(:Entity) }
    OPTIONAL MATCH (i)-[:DERIVED_FROM]->(n)
    OPTIONAL MATCH (n)-[r]->(e:Entity)
    WHERE type(r) IN ['ABOUT', 'RELATES_TO']
    RETURN i.insight_id AS insight_id,
           collect(DISTINCT {
             labels: labels(n),
             rel_type: type(r),
             entity_id: e.entity_id
           }) AS derived
    ORDER BY i.insight_id
    """
    if limit is not None:
        query += "\nLIMIT $limit"
    with driver.session() as session:
        result = session.run(query, limit=limit)
        return [dict(record) for record in result]


def _allowed_insight_entity_id(entry: dict[str, Any]) -> str | None:
    """Return entity_id when derivation path is deterministic and allowed."""
    entity_id = entry.get("entity_id")
    if not entity_id:
        return None
    labels = set(entry.get("labels") or [])
    rel_type = entry.get("rel_type")
    if "Source" in labels:
        return entity_id if rel_type == "ABOUT" else None
    if labels.intersection({"Fact", "Claim"}):
        return entity_id if rel_type in {"ABOUT", "RELATES_TO"} else None
    return None


def _build_insight_rows(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Build Insight->Entity ABOUT rows when one entity is derivable."""
    rows: list[dict[str, Any]] = []
    skipped = 0
    for candidate in candidates:
        entity_ids = {
            entity_id
            for entry in candidate.get("derived") or []
            if (entity_id := _allowed_insight_entity_id(entry)) is not None
        }
        if len(entity_ids) != 1:
            skipped += 1
            continue
        rows.append(
            {
                "insight_id": candidate["insight_id"],
                "entity_id": next(iter(entity_ids)),
            }
        )
    return rows, skipped


def _write_insight_rows(driver: Any, rows: list[dict[str, Any]]) -> int:
    """Write Insight->Entity ABOUT relationships."""
    if not rows:
        return 0
    with driver.session() as session:
        session.run(
            """
            UNWIND $rows AS row
            MATCH (i:Insight {insight_id: row.insight_id})
            MATCH (e:Entity {entity_id: row.entity_id})
            MERGE (i)-[:ABOUT]->(e)
            """,
            rows=rows,
        )
    return len(rows)


def _run_stage(
    *,
    stage: str,
    driver: Any,
    dry_run: bool,
    limit: int | None,
) -> StageResult:
    """Run a single backfill stage."""
    if stage == "domains":
        candidates = _fetch_domain_candidates(driver, limit=limit)
        rows, skipped = _build_domain_rows(candidates)
        updated = 0 if dry_run else _write_domain_rows(driver, rows)
    elif stage == "facts":
        candidates = _fetch_fact_candidates(driver, limit=limit)
        rows, skipped = _build_fact_rows(candidates)
        updated = 0 if dry_run else _write_fact_rows(driver, rows)
    elif stage == "claims":
        candidates = _fetch_claim_candidates(driver, limit=limit)
        rows, skipped = _build_claim_rows(candidates)
        updated = 0 if dry_run else _write_claim_rows(driver, rows)
    elif stage == "insights":
        candidates = _fetch_insight_candidates(driver, limit=limit)
        rows, skipped = _build_insight_rows(candidates)
        updated = 0 if dry_run else _write_insight_rows(driver, rows)
    else:
        msg = f"Unknown stage: {stage}"
        raise ValueError(msg)

    return StageResult(
        stage=stage,
        candidates=len(candidates),
        to_write=len(rows),
        skipped_ambiguous=skipped,
        updated=updated,
        sample=rows[:3],
    )


def _print_stage_result(result: StageResult, *, dry_run: bool) -> None:
    """Render stage summary."""
    action_label = "planned" if dry_run else "updated"
    print(f"\n[{result.stage}]")
    print(f"  candidates:         {result.candidates}")
    print(f"  {action_label}:            {result.to_write if dry_run else result.updated}")
    print(f"  skipped_ambiguous:  {result.skipped_ambiguous}")
    if result.sample:
        print("  sample:")
        for row in result.sample:
            print(f"    {row}")


def main(args: list[str] | None = None) -> int:
    """CLI entrypoint."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    parsed = parse_args(args)
    stages = list(STAGES) if parsed.stage == "all" else [parsed.stage]
    driver = create_driver(
        uri=parsed.neo4j_uri,
        user=parsed.neo4j_user,
        password=parsed.neo4j_password,
    )

    try:
        print("=== Deterministic Research Backfill ===")
        print(f"dry_run: {parsed.dry_run}")
        print(f"stages:  {', '.join(stages)}")
        if parsed.limit is not None:
            print(f"limit:   {parsed.limit}")

        results: list[StageResult] = []
        for stage in stages:
            logger.info("Running stage: %s", stage)
            result = _run_stage(
                stage=stage,
                driver=driver,
                dry_run=parsed.dry_run,
                limit=parsed.limit,
            )
            results.append(result)
            _print_stage_result(result, dry_run=parsed.dry_run)

        print("\n--- Summary ---")
        print(f"  stages_run:         {len(results)}")
        print(f"  candidates:         {sum(result.candidates for result in results)}")
        print(f"  planned_or_updated: {sum(result.to_write if parsed.dry_run else result.updated for result in results)}")
        print(f"  skipped_ambiguous:  {sum(result.skipped_ambiguous for result in results)}")
        return 0
    finally:
        driver.close()


if __name__ == "__main__":
    raise SystemExit(main())
