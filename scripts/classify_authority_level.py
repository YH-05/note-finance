#!/usr/bin/env python3
"""Classify Source nodes with authority_level property.

Usage:
    uv run python scripts/classify_authority_level.py [--dry-run]

Authority levels (6 categories):
    official  - 企業IR・SEC Filing・中銀・政府機関
    analyst   - セルサイドレポート・格付け機関・自社リサーチ
    media     - 大手報道機関・ニュースメディア
    blog      - 個人メディア・専門ブログ・Seeking Alpha
    social    - SNS・コミュニティ（Reddit, X/Twitter）
    academic  - 学術論文・リサーチペーパー
"""

from __future__ import annotations

import argparse
import logging
import os
from collections import defaultdict

from neo4j import GraphDatabase

from authority_classifier import classify_authority

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RESEARCH_URI = "bolt://localhost:7688"
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "gomasuke")
AUTH = ("neo4j", NEO4J_PASSWORD)


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify Source authority_level")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    driver = GraphDatabase.driver(RESEARCH_URI, auth=AUTH)

    try:
        driver.verify_connectivity()
        logger.info("Connected to %s", RESEARCH_URI)

        # Read all Source nodes
        with driver.session() as session:
            result = session.run(
                "MATCH (s:Source) "
                "RETURN s.source_id AS source_id, s.source_type AS source_type, "
                "       s.url AS url, s.authority_level AS current_level"
            )
            sources = [dict(r) for r in result]

        logger.info("Found %d Source nodes", len(sources))

        # Classify
        stats: dict[str, int] = defaultdict(int)
        updates: list[tuple[str, str]] = []  # (source_id, authority_level)

        for src in sources:
            level = classify_authority(
                source_type=src["source_type"] or "",
                url=src["url"] or "",
            )
            stats[level] += 1
            updates.append((src["source_id"], level))

        logger.info("Classification results: %s", dict(stats))

        if args.dry_run:
            # Show sample per level
            samples: dict[str, list[str]] = defaultdict(list)
            for src, (_, level) in zip(sources, updates):
                if len(samples[level]) < 3:
                    samples[level].append(f"  {src['url'] or '(no url)'} [{src['source_type']}]")
            for level, sample_list in sorted(samples.items()):
                logger.info("--- %s ---", level)
                for s in sample_list:
                    logger.info(s)
            logger.info("DRY RUN complete. No changes made.")
            return

        # Batch update
        with driver.session() as session:
            batch_size = 100
            for i in range(0, len(updates), batch_size):
                batch = updates[i : i + batch_size]
                session.run(
                    "UNWIND $updates AS u "
                    "MATCH (s:Source {source_id: u.source_id}) "
                    "SET s.authority_level = u.level",
                    updates=[{"source_id": sid, "level": lvl} for sid, lvl in batch],
                )

        # Verify
        with driver.session() as session:
            result = session.run(
                "MATCH (s:Source) "
                "RETURN s.authority_level AS level, count(s) AS count "
                "ORDER BY count DESC"
            )
            logger.info("Verification:")
            for r in result:
                logger.info("  %s: %d", r["level"], r["count"])

        logger.info("Done. Updated %d Source nodes.", len(updates))

    except Exception:
        logger.exception("Failed")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
