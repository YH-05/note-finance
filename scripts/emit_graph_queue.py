#!/usr/bin/env python3
"""Emit graph-queue JSON from various command outputs.

Converts outputs from 6 different finance workflow commands into a
unified graph-queue format. Each command produces data in a different
JSON structure; this script normalises them all into a single schema.

Supported commands
------------------
- finance-news-workflow
- ai-research-collect
- generate-market-report
- asset-management
- reddit-finance-topics
- finance-full

Usage
-----
::

    python3 scripts/emit_graph_queue.py \\
        --command finance-news-workflow \\
        --input .tmp/news-batches/index.json

    python3 scripts/emit_graph_queue.py \\
        --command finance-news-workflow \\
        --input .tmp/news-batches/index.json \\
        --cleanup
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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

COMMANDS: list[str] = [
    "finance-news-workflow",
    "ai-research-collect",
    "generate-market-report",
    "asset-management",
    "reddit-finance-topics",
    "finance-full",
]
"""Supported command names."""

DEFAULT_OUTPUT_BASE = Path(".tmp/graph-queue")
"""Default base directory for output queue files."""

DEFAULT_MAX_AGE_DAYS = 7
"""Default maximum age in days for auto-cleanup."""

SCHEMA_VERSION = "1.0"
"""Graph-queue schema version."""

THEME_TO_CATEGORY: dict[str, str] = {
    "index": "stock",
    "stock": "stock",
    "sector": "sector",
    "macro_cnbc": "macro",
    "macro_other": "macro",
    "ai_cnbc": "ai",
    "ai_nasdaq": "ai",
    "ai_tech": "ai",
    "finance_cnbc": "finance",
    "finance_nasdaq": "finance",
    "finance_other": "finance",
}
"""Theme key to category mapping table."""


# ---------------------------------------------------------------------------
# ID Generation
# ---------------------------------------------------------------------------


def generate_source_id(url: str) -> str:
    """Generate a deterministic source ID from a URL.

    Uses UUID5 with NAMESPACE_URL to produce the same ID for the same URL.

    Parameters
    ----------
    url : str
        The source URL.

    Returns
    -------
    str
        UUID5 string derived from the URL.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, url))


def generate_topic_id(name: str, category: str) -> str:
    """Generate a deterministic topic ID from name and category.

    Parameters
    ----------
    name : str
        Topic name.
    category : str
        Topic category.

    Returns
    -------
    str
        UUID5 string derived from ``topic:{name}:{category}``.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"topic:{name}:{category}"))


def generate_entity_id(name: str, entity_type: str) -> str:
    """Generate a deterministic entity ID from name and type.

    Parameters
    ----------
    name : str
        Entity name.
    entity_type : str
        Entity type (e.g. ``company``, ``ticker``).

    Returns
    -------
    str
        UUID5 string derived from ``entity:{name}:{entity_type}``.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"entity:{name}:{entity_type}"))


def generate_claim_id(content: str) -> str:
    """Generate a deterministic claim ID from content.

    Parameters
    ----------
    content : str
        Claim content text.

    Returns
    -------
    str
        First 16 hex characters of the SHA-256 hash of *content*.
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def generate_queue_id() -> str:
    """Generate a unique queue ID with timestamp and short hash.

    Returns
    -------
    str
        Queue ID in the format ``gq-{timestamp}-{hash4}``.
    """
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d%H%M%S")
    # Use a hash of the full ISO timestamp for the 4-char suffix
    hash4 = hashlib.sha256(now.isoformat().encode("utf-8")).hexdigest()[:4]
    return f"gq-{timestamp}-{hash4}"


# ---------------------------------------------------------------------------
# Category resolution
# ---------------------------------------------------------------------------


def resolve_category(theme_key: str) -> str:
    """Resolve a theme key to its canonical category.

    Parameters
    ----------
    theme_key : str
        Theme key from the workflow (e.g. ``index``, ``macro_cnbc``).

    Returns
    -------
    str
        Canonical category (``stock``, ``sector``, ``macro``, ``ai``,
        ``finance``).  Falls back to ``"other"`` for unknown keys.
    """
    return THEME_TO_CATEGORY.get(theme_key, "other")


# ---------------------------------------------------------------------------
# Mapping functions
# ---------------------------------------------------------------------------


def map_finance_news(data: dict[str, Any]) -> dict[str, Any]:
    """Map finance-news-workflow batch to graph-queue components.

    Parameters
    ----------
    data : dict[str, Any]
        Input data with ``articles[]``, ``session_id``, ``batch_label``.

    Returns
    -------
    dict[str, Any]
        Mapped components: ``sources``, ``claims``, ``topics``,
        ``entities``, ``relations``, ``session_id``, ``batch_label``.
    """
    articles = data.get("articles", [])
    sources: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []

    for article in articles:
        url = article.get("url", "")
        source_id = generate_source_id(url)

        sources.append(
            {
                "source_id": source_id,
                "url": url,
                "title": article.get("title", ""),
                "published": article.get("published", ""),
                "feed_source": article.get("feed_source", ""),
            }
        )

        summary = article.get("summary", "")
        if summary:
            claims.append(
                {
                    "claim_id": generate_claim_id(summary),
                    "content": summary,
                    "source_id": source_id,
                    "category": resolve_category(data.get("batch_label", "")),
                }
            )

    return {
        "session_id": data.get("session_id", ""),
        "batch_label": data.get("batch_label", ""),
        "sources": sources,
        "claims": claims,
        "topics": [],
        "entities": [],
        "relations": {},
    }


def map_ai_research(data: dict[str, Any]) -> dict[str, Any]:
    """Map ai-research-collect batch to graph-queue components.

    Parameters
    ----------
    data : dict[str, Any]
        Input data with ``companies[]``, ``session_id``.

    Returns
    -------
    dict[str, Any]
        Mapped components with ``entities[]`` and ``sources[]``.
    """
    companies = data.get("companies", [])
    entities: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []

    for company in companies:
        company_name = company.get("company_name", "")
        ticker = company.get("ticker", "")
        url = company.get("url", "")

        # Create entity for the company
        entities.append(
            {
                "entity_id": generate_entity_id(company_name, "company"),
                "name": company_name,
                "entity_type": "company",
                "ticker": ticker,
            }
        )

        # Create source
        if url:
            sources.append(
                {
                    "source_id": generate_source_id(url),
                    "url": url,
                    "title": company.get("title", ""),
                    "published": company.get("published", ""),
                }
            )

    return {
        "session_id": data.get("session_id", ""),
        "batch_label": "ai",
        "sources": sources,
        "claims": [],
        "topics": [],
        "entities": entities,
        "relations": {},
    }


def map_market_report(data: dict[str, Any]) -> dict[str, Any]:
    """Map generate-market-report data to graph-queue components.

    Parameters
    ----------
    data : dict[str, Any]
        Input data with ``sections[]``, ``session_id``.

    Returns
    -------
    dict[str, Any]
        Mapped components with sources from sections and claims from
        section content.
    """
    sections = data.get("sections", [])
    sources: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for section in sections:
        # Collect sources from section
        for source in section.get("sources", []):
            url = source.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                sources.append(
                    {
                        "source_id": generate_source_id(url),
                        "url": url,
                        "title": source.get("title", ""),
                        "published": source.get("published", ""),
                    }
                )

        # Create claim from section content
        content = section.get("content", "")
        if content:
            claims.append(
                {
                    "claim_id": generate_claim_id(content),
                    "content": content,
                    "section_title": section.get("title", ""),
                    "category": "macro",
                }
            )

    return {
        "session_id": data.get("session_id", ""),
        "batch_label": "market-report",
        "sources": sources,
        "claims": claims,
        "topics": [],
        "entities": [],
        "relations": {},
    }


def map_asset_management(data: dict[str, Any]) -> dict[str, Any]:
    """Map asset-management batch to graph-queue components.

    Parameters
    ----------
    data : dict[str, Any]
        Input data with ``themes.{key}.articles[]``, ``session_id``.

    Returns
    -------
    dict[str, Any]
        Mapped components with ``sources[]`` from theme articles and
        ``topics[]`` from theme names.
    """
    themes = data.get("themes", {})
    sources: list[dict[str, Any]] = []
    topics: list[dict[str, Any]] = []

    for theme_key, theme_data in themes.items():
        name_ja = theme_data.get("name_ja", theme_key)

        # Create topic for the theme
        topics.append(
            {
                "topic_id": generate_topic_id(name_ja, "asset-management"),
                "name": name_ja,
                "category": "asset-management",
                "theme_key": theme_key,
            }
        )

        # Map articles to sources
        articles = theme_data.get("articles", [])
        for article in articles:
            url = article.get("url", "")
            if url:
                sources.append(
                    {
                        "source_id": generate_source_id(url),
                        "url": url,
                        "title": article.get("title", ""),
                        "published": article.get("published", ""),
                        "feed_source": article.get("feed_source", ""),
                    }
                )

    return {
        "session_id": data.get("session_id", ""),
        "batch_label": "asset-management",
        "sources": sources,
        "claims": [],
        "topics": topics,
        "entities": [],
        "relations": {},
    }


def map_reddit_topics(data: dict[str, Any]) -> dict[str, Any]:
    """Map reddit-finance-topics batch to graph-queue components.

    Parameters
    ----------
    data : dict[str, Any]
        Input data with ``topics[]``, ``session_id``.

    Returns
    -------
    dict[str, Any]
        Mapped components with ``sources[]`` from Reddit posts and
        ``topics[]`` from discussion topics.
    """
    input_topics = data.get("topics", [])
    sources: list[dict[str, Any]] = []
    topics: list[dict[str, Any]] = []

    for topic in input_topics:
        name = topic.get("name", "")
        url = topic.get("url", "")

        # Create topic
        topics.append(
            {
                "topic_id": generate_topic_id(name, "reddit"),
                "name": name,
                "category": "reddit",
                "subreddit": topic.get("subreddit", ""),
            }
        )

        # Create source from Reddit post
        if url:
            sources.append(
                {
                    "source_id": generate_source_id(url),
                    "url": url,
                    "title": topic.get("title", ""),
                    "published": topic.get("published", ""),
                    "subreddit": topic.get("subreddit", ""),
                    "score": topic.get("score", 0),
                }
            )

    return {
        "session_id": data.get("session_id", ""),
        "batch_label": "reddit",
        "sources": sources,
        "claims": [],
        "topics": topics,
        "entities": [],
        "relations": {},
    }


def map_finance_full(data: dict[str, Any]) -> dict[str, Any]:
    """Map finance-full data to graph-queue components.

    Parameters
    ----------
    data : dict[str, Any]
        Input data with ``sources[]`` and ``claims[]``, ``session_id``.

    Returns
    -------
    dict[str, Any]
        Mapped components preserving sources and claims with generated IDs.
    """
    input_sources = data.get("sources", [])
    input_claims = data.get("claims", [])
    sources: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []

    for source in input_sources:
        url = source.get("url", "")
        sources.append(
            {
                "source_id": generate_source_id(url),
                "url": url,
                "title": source.get("title", ""),
                "published": source.get("published", ""),
            }
        )

    for claim in input_claims:
        content = claim.get("content", "")
        claims.append(
            {
                "claim_id": generate_claim_id(content),
                "content": content,
                "source_url": claim.get("source_url", ""),
                "category": claim.get("category", ""),
            }
        )

    return {
        "session_id": data.get("session_id", ""),
        "batch_label": "finance-full",
        "sources": sources,
        "claims": claims,
        "topics": [],
        "entities": [],
        "relations": {},
    }


# ---------------------------------------------------------------------------
# Command → Mapper dispatch
# ---------------------------------------------------------------------------

COMMAND_MAPPERS: dict[str, Any] = {
    "finance-news-workflow": map_finance_news,
    "ai-research-collect": map_ai_research,
    "generate-market-report": map_market_report,
    "asset-management": map_asset_management,
    "reddit-finance-topics": map_reddit_topics,
    "finance-full": map_finance_full,
}
"""Dispatch table mapping command names to their mapper functions."""


# ---------------------------------------------------------------------------
# Auto-cleanup
# ---------------------------------------------------------------------------


def cleanup_old_files(directory: Path, *, max_age_days: int = 7) -> int:
    """Delete queue files older than *max_age_days* in *directory*.

    Parameters
    ----------
    directory : Path
        Directory to scan for old files.
    max_age_days : int
        Maximum age in days.  Files older than this are deleted.

    Returns
    -------
    int
        Number of files deleted.
    """
    if not directory.exists():
        logger.debug("Cleanup skipped: directory does not exist: %s", directory)
        return 0

    cutoff = time.time() - (max_age_days * 24 * 3600)
    deleted = 0

    for file_path in directory.iterdir():
        if not file_path.is_file():
            continue
        try:
            mtime = file_path.stat().st_mtime
            if mtime < cutoff:
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
    """Parse command-line arguments.

    Parameters
    ----------
    args : list[str] | None
        Command-line arguments.  If ``None``, uses ``sys.argv``.

    Returns
    -------
    argparse.Namespace
        Parsed arguments with ``command``, ``input``, and ``cleanup``.
    """
    parser = argparse.ArgumentParser(
        description="Emit graph-queue JSON from command outputs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--command",
        type=str,
        required=True,
        choices=COMMANDS,
        help="Source command name",
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Input file or directory path",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        default=False,
        help="Delete queue files older than 7 days",
    )

    return parser.parse_args(args)


# ---------------------------------------------------------------------------
# Main execution
# ---------------------------------------------------------------------------


def run(
    *,
    command: str,
    input_path: Path,
    output_base: Path = DEFAULT_OUTPUT_BASE,
    cleanup: bool = False,
) -> int:
    """Execute the graph-queue emission pipeline.

    Parameters
    ----------
    command : str
        Source command name (one of :data:`COMMANDS`).
    input_path : Path
        Path to the input JSON file.
    output_base : Path
        Base directory for output queue files.
    cleanup : bool
        If ``True``, delete files older than 7 days before writing.

    Returns
    -------
    int
        Exit code — ``0`` for success, ``1`` for failure.
    """
    # Validate input
    if not input_path.exists():
        logger.error("Input path does not exist: %s", input_path)
        print(f"Error: Input path does not exist: {input_path}", file=sys.stderr)
        return 1

    # Read input data
    try:
        with input_path.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON in %s: %s", input_path, exc)
        print(f"Error: Invalid JSON in {input_path}: {exc}", file=sys.stderr)
        return 1

    # Get mapper
    mapper = COMMAND_MAPPERS.get(command)
    if mapper is None:
        logger.error("Unknown command: %s", command)
        print(f"Error: Unknown command: {command}", file=sys.stderr)
        return 1

    # Map data
    logger.info("Mapping data for command: %s", command)
    mapped = mapper(data)

    # Build queue document
    queue_id = generate_queue_id()
    now = datetime.now(timezone.utc)

    queue_doc: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "queue_id": queue_id,
        "created_at": now.isoformat(),
        "command_source": command,
        "session_id": mapped.get("session_id", ""),
        "batch_label": mapped.get("batch_label", ""),
        "sources": mapped.get("sources", []),
        "topics": mapped.get("topics", []),
        "claims": mapped.get("claims", []),
        "entities": mapped.get("entities", []),
        "relations": mapped.get("relations", {}),
    }

    # Output directory
    output_dir = output_base / command
    output_dir.mkdir(parents=True, exist_ok=True)

    # Cleanup old files if requested
    if cleanup:
        cleanup_old_files(output_dir, max_age_days=DEFAULT_MAX_AGE_DAYS)

    # Write queue file
    output_file = output_dir / f"{queue_id}.json"
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(queue_doc, f, ensure_ascii=False, indent=2)

    logger.info("Queue file written: %s", output_file)
    print(f"Queue file: {output_file}")

    return 0


def main(args: list[str] | None = None) -> int:
    """Main entry point.

    Parameters
    ----------
    args : list[str] | None
        Command-line arguments.

    Returns
    -------
    int
        Exit code (0 for success).
    """
    parsed = parse_args(args)

    return run(
        command=parsed.command,
        input_path=Path(parsed.input),
        cleanup=parsed.cleanup,
    )


if __name__ == "__main__":
    sys.exit(main())
