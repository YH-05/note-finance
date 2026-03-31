#!/usr/bin/env python3
"""Emit graph-queue JSON from various command outputs.

Thin CLI entrypoint that delegates mapping to the plugin mapper
architecture in ``scripts/mappers/``.  Use ``--command`` to select a
mapper and ``--input`` to provide the input JSON file (or directory for
wealth-scrape).

Supported commands
------------------
- academic-fetch
- ai-research-collect
- asset-management
- finance-full
- finance-news-workflow
- generate-market-report
- pdf-extraction
- reddit-finance-topics
- topic-discovery
- wealth-scrape (directory or JSON file)
- web-research

Usage
-----
::

    uv run python scripts/emit_research_queue.py \\
        --command finance-news-workflow \\
        --input .tmp/news-batches/index.json

    uv run python scripts/emit_research_queue.py \\
        --command wealth-scrape \\
        --input /Volumes/personal_folder/scraped/wealth/
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mappers import COMMAND_MAPPERS, WealthScrapeMapper
from mappers.classification import apply_classification_layer, get_schema_version
from mappers.helpers import (
    # constants
    THEME_TO_CATEGORY,
    TOPIC_DISCOVERY_CATEGORIES,
    # build helpers (backward compat re-exports for tests)
    _build_authored_by_rels,
    _build_causal_links,
    _build_next_period_chain,
    _build_question_nodes,
    _build_stance_nodes,
    _build_supersedes_chain,
    _build_trend_edges,
    _infer_period_type,
    _load_metric_alias_index,
    _load_wealth_themes,
    _magnitude_from_score,
    _match_domain_to_theme,
    _parse_yaml_frontmatter,
    _period_sort_key,
    # wealth directory scanning
    _scan_wealth_directory,
    # id generators
    generate_chunk_id,
    generate_claim_id,
    generate_datapoint_id,
    generate_entity_id,
    generate_fact_id,
    generate_queue_id,
    generate_source_id,
    generate_topic_id,
    # category / metric helpers
    resolve_category,
    resolve_metric_id,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMMANDS: list[str] = list(COMMAND_MAPPERS.keys())
DEFAULT_OUTPUT_BASE = Path(".tmp/graph-queue")
DEFAULT_MAX_AGE_DAYS = 7
SCHEMA_VERSION: str = get_schema_version()
WEALTH_THEME_CONFIG_PATH = Path("data/config/wealth-management-themes.json")
DIRECTORY_COMMANDS: frozenset[str] = frozenset({"wealth-scrape"})

# ---------------------------------------------------------------------------
# Backward-compat map_* wrappers (task-008 will remove these)
# ---------------------------------------------------------------------------

_wealth_scrape_mapper = WealthScrapeMapper()


def map_academic_fetch(data: dict[str, Any]) -> dict[str, Any]:
    return COMMAND_MAPPERS["academic-fetch"](data)


def map_ai_research(data: dict[str, Any]) -> dict[str, Any]:
    return COMMAND_MAPPERS["ai-research-collect"](data)


def map_asset_management(data: dict[str, Any]) -> dict[str, Any]:
    return COMMAND_MAPPERS["asset-management"](data)


def map_finance_full(data: dict[str, Any]) -> dict[str, Any]:
    return COMMAND_MAPPERS["finance-full"](data)


def map_finance_news(data: dict[str, Any]) -> dict[str, Any]:
    return COMMAND_MAPPERS["finance-news-workflow"](data)


def map_market_report(data: dict[str, Any]) -> dict[str, Any]:
    return COMMAND_MAPPERS["generate-market-report"](data)


def map_pdf_extraction(data: dict[str, Any]) -> dict[str, Any]:
    return COMMAND_MAPPERS["pdf-extraction"](data)


def map_reddit_topics(data: dict[str, Any]) -> dict[str, Any]:
    return COMMAND_MAPPERS["reddit-finance-topics"](data)


def map_topic_discovery(data: dict[str, Any]) -> dict[str, Any]:
    return COMMAND_MAPPERS["topic-discovery"](data)


def map_web_research(data: dict[str, Any]) -> dict[str, Any]:
    return COMMAND_MAPPERS["web-research"](data)


def map_wealth_scrape(data: dict[str, Any]) -> dict[str, Any]:
    return COMMAND_MAPPERS["wealth-scrape"](data)


def map_wealth_scrape_backfill(data: dict[str, Any]) -> dict[str, Any]:
    return _wealth_scrape_mapper._map_backfill(data)


def map_wealth_scrape_incremental(data: dict[str, Any]) -> dict[str, Any]:
    return _wealth_scrape_mapper._map_incremental(data)


# ---------------------------------------------------------------------------
# Auto-cleanup
# ---------------------------------------------------------------------------


def cleanup_old_files(directory: Path, *, max_age_days: int = 7) -> int:
    """Delete queue files older than *max_age_days* in *directory*."""
    if not directory.exists():
        logger.debug("Cleanup skipped: directory does not exist: %s", directory)
        return 0

    cutoff = time.time() - (max_age_days * 24 * 3600)
    deleted = 0
    for file_path in directory.iterdir():
        if not file_path.is_file():
            continue
        try:
            if file_path.stat().st_mtime < cutoff:
                file_path.unlink()
                logger.info("Deleted old queue file: %s", file_path)
                deleted += 1
        except OSError as exc:
            logger.warning("Failed to delete %s: %s", file_path, exc)

    logger.info("Cleanup complete: %d file(s) deleted from %s", deleted, directory)
    return deleted


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Emit graph-queue JSON from command outputs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--command", required=True, choices=COMMANDS)
    parser.add_argument("--input", required=True, help="Input file or directory path")
    parser.add_argument(
        "--cleanup",
        action="store_true",
        default=False,
        help="Delete queue files older than 7 days",
    )
    return parser.parse_args(args)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def _load_and_parse(
    command: str, input_path: Path
) -> dict[str, Any] | list[dict[str, Any]] | None:
    """Load input data and map it through the appropriate command mapper."""
    if not input_path.exists():
        logger.error("Input path does not exist: %s", input_path)
        print(f"Error: Input path does not exist: {input_path}", file=sys.stderr)
        return None

    # Directory input: wealth-scrape backfill scanning
    if command in DIRECTORY_COMMANDS and input_path.is_dir():
        logger.info("Scanning wealth directory: %s", input_path)
        results = _scan_wealth_directory(input_path)
        if not results:
            logger.error("No articles found in directory: %s", input_path)
            print(
                f"Error: No articles found in directory: {input_path}", file=sys.stderr
            )
            return None
        return results

    # File input: standard JSON loading
    try:
        with input_path.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON in %s: %s", input_path, exc)
        print(f"Error: Invalid JSON in {input_path}: {exc}", file=sys.stderr)
        return None

    # AIDEV-NOTE: Layer 2 原文保存フック — 全コマンドの入力JSONから原文をRawStoreに保存
    try:
        from data_pipeline.integrations.bridge import save_from_emit_input

        save_result = save_from_emit_input(data, command)
        logger.info(
            "RawStore: saved=%d, dup=%d, empty=%d (command=%s)",
            save_result.saved,
            save_result.skipped_duplicate,
            save_result.skipped_empty,
            command,
        )
    except Exception as exc:
        logger.warning("RawStore save failed (non-blocking): %s", exc)

    mapper = COMMAND_MAPPERS.get(command)
    if mapper is None:
        logger.error("Unknown command: %s", command)
        print(f"Error: Unknown command: {command}", file=sys.stderr)
        return None

    logger.info("Mapping data for command: %s", command)
    return mapper(data)


def _build_queue_doc(command: str, mapped: dict[str, Any]) -> dict[str, Any]:
    """Build the graph-queue document from mapped data."""
    apply_classification_layer(mapped, command)
    queue_id = generate_queue_id()
    now = datetime.now(timezone.utc)
    return {
        "schema_version": SCHEMA_VERSION,
        "queue_id": queue_id,
        "created_at": now.isoformat(),
        "command_source": command,
        "session_id": mapped.get("session_id", ""),
        "batch_label": mapped.get("batch_label", ""),
        "sources": mapped.get("sources", []),
        "topics": mapped.get("topics", []),
        "claims": mapped.get("claims", []),
        "facts": mapped.get("facts", []),
        "entities": mapped.get("entities", []),
        "chunks": mapped.get("chunks", []),
        "financial_datapoints": mapped.get("financial_datapoints", []),
        "fiscal_periods": mapped.get("fiscal_periods", []),
        "authors": mapped.get("authors", []),
        "stances": mapped.get("stances", []),
        "questions": mapped.get("questions", []),
        "relations": mapped.get("relations", {}),
        "classification_nodes": mapped.get("classification_nodes", []),
        "classification_rels": mapped.get("classification_rels", []),
    }


def _write_output(
    queue_doc: dict[str, Any],
    command: str,
    output_base: Path,
    *,
    cleanup: bool = False,
) -> Path:
    """Write the queue document to disk."""
    output_dir = output_base / command
    output_dir.mkdir(parents=True, exist_ok=True)

    if cleanup:
        cleanup_old_files(output_dir, max_age_days=DEFAULT_MAX_AGE_DAYS)

    output_file = output_dir / f"{queue_doc['queue_id']}.json"
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(queue_doc, f, ensure_ascii=False, indent=2)

    logger.info("Queue file written: %s", output_file)
    return output_file


def run(
    *,
    command: str,
    input_path: Path,
    output_base: Path = DEFAULT_OUTPUT_BASE,
    cleanup: bool = False,
) -> int:
    """Execute the graph-queue emission pipeline."""
    mapped = _load_and_parse(command, input_path)
    if mapped is None:
        return 1

    if isinstance(mapped, list):
        output_files: list[Path] = []
        for item in mapped:
            queue_doc = _build_queue_doc(command, item)
            output_file = _write_output(
                queue_doc, command, output_base, cleanup=cleanup
            )
            output_files.append(output_file)
            cleanup = False  # only cleanup on first iteration
        for f in output_files:
            print(f"Queue file: {f}")
        logger.info("Generated %d queue file(s)", len(output_files))
        return 0

    queue_doc = _build_queue_doc(command, mapped)
    output_file = _write_output(queue_doc, command, output_base, cleanup=cleanup)
    print(f"Queue file: {output_file}")
    return 0


def main(args: list[str] | None = None) -> int:
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    parsed = parse_args(args)
    return run(
        command=parsed.command,
        input_path=Path(parsed.input),
        cleanup=parsed.cleanup,
    )


if __name__ == "__main__":
    sys.exit(main())
