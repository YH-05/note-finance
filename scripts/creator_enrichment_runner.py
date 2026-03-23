#!/usr/bin/env python3
"""Creator enrichment CLI runner.

Usage
-----
::

    uv run python scripts/creator_enrichment_runner.py --until 23:30
    uv run python scripts/creator_enrichment_runner.py --until 23:30 --genre career --dry-run
"""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)


def main() -> None:
    """CLI entrypoint for creator-enrichment orchestrator."""
    from creator_enrichment.config import parse_args, load_config
    from creator_enrichment.orchestrator import CreatorEnrichmentOrchestrator, FatalError

    args = parse_args()

    try:
        config = load_config(args)
    except (ValueError, FileNotFoundError) as e:
        logger.error("Configuration error: %s", e)
        sys.exit(1)

    logger.info(
        "Starting creator enrichment",
        extra={"until": str(config.until_time), "genre": config.genre, "dry_run": config.dry_run},
    )

    try:
        orchestrator = CreatorEnrichmentOrchestrator(config)
        orchestrator.run()
    except FatalError as e:
        logger.error("Fatal error: %s", e)
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)

    logger.info("Creator enrichment completed")


if __name__ == "__main__":
    main()
