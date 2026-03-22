#!/usr/bin/env python3
"""Emit creator-graph-queue JSON from enrichment data.

Converts creator-enrichment output (Fact/Tip/Story with Entity extraction)
into a graph-queue format for /save-to-creator-graph.

Output target: .tmp/creator-graph-queue/cq-{timestamp}-{rand8}.json

This is the creator-neo4j (bolt://localhost:7689) counterpart of
emit_graph_queue.py (research-neo4j). The schemas are different:
- creator-neo4j: Genre, Topic, Source, Fact, Tip, Story, Entity
- research-neo4j: Source, Fact, Claim, Entity, Topic, ...

Usage
-----
::

    python3 scripts/emit_creator_queue.py --input cycle-input.json

"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import secrets
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pdf_pipeline.services.id_generator import (
    generate_entity_id,
    generate_source_id,
)

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "creator-1.0"
"""Graph-queue schema version for creator-neo4j."""

DEFAULT_OUTPUT_BASE = Path(".tmp/creator-graph-queue")
"""Default base directory for output queue files."""

VALID_SOURCE_TYPES = frozenset({"web", "reddit", "blog", "report"})
VALID_AUTHORITY_LEVELS = frozenset({"official", "media", "blog", "social"})
VALID_FACT_CATEGORIES = frozenset({"statistics", "market_data", "research", "trend"})
VALID_TIP_CATEGORIES = frozenset({"strategy", "tool", "process", "mindset"})
VALID_STORY_OUTCOMES = frozenset({"success", "failure", "mixed", "ongoing"})
VALID_CONFIDENCE_LEVELS = frozenset({"high", "medium", "low"})
VALID_DIFFICULTY_LEVELS = frozenset({"beginner", "intermediate", "advanced"})
VALID_ENTITY_TYPES = frozenset({
    "person",
    "company",
    "platform",
    "service",
    "occupation",
    "technique",
    "metric",
    "product",
    "concept",
})

GENRE_NAMES: dict[str, str] = {
    "career": "転職・副業",
    "beauty-romance": "美容・恋愛",
    "spiritual": "占い・スピリチュアル",
}


# ---------------------------------------------------------------------------
# ID Generation (creator-specific)
# ---------------------------------------------------------------------------


def _sha256_prefix(key: str, length: int = 8) -> str:
    """Return first *length* hex characters of SHA-256 digest."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:length]


def _slugify(text: str) -> str:
    """Simple slugify for topic ID generation."""
    text = unicodedata.normalize("NFKC", text.strip().lower())
    text = text.replace(" ", "-").replace("　", "-")
    return text


def generate_creator_fact_id(text: str) -> str:
    """Generate fact ID: ``fact-{sha256(text)[:8]}``."""
    return f"fact-{_sha256_prefix(text)}"


def generate_creator_tip_id(text: str) -> str:
    """Generate tip ID: ``tip-{sha256(text)[:8]}``."""
    return f"tip-{_sha256_prefix(text)}"


def generate_creator_story_id(text: str) -> str:
    """Generate story ID: ``story-{sha256(text)[:8]}``."""
    return f"story-{_sha256_prefix(text)}"


def generate_creator_topic_id(name: str, genre_id: str) -> str:
    """Generate topic ID: ``sha256(topic:{slug}:{genre})[:8]``."""
    slug = _slugify(name)
    return _sha256_prefix(f"topic:{slug}:{genre_id}")


def generate_creator_queue_id() -> str:
    """Generate queue ID: ``cq-{timestamp}-{rand8}``."""
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d%H%M%S")
    rand8 = secrets.token_hex(4)
    return f"cq-{timestamp}-{rand8}"


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_enum(value: str, allowed: frozenset[str], field_name: str) -> str:
    """Validate that value is in allowed set, return as-is or warn."""
    if value not in allowed:
        logger.warning(
            "Invalid %s: %r (allowed: %s)", field_name, value, sorted(allowed)
        )
    return value


# ---------------------------------------------------------------------------
# Entity processing
# ---------------------------------------------------------------------------


def _build_entities(
    content_items: list[dict[str, Any]],
    entity_relations: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    dict[str, str],
    list[dict[str, str]],
    list[dict[str, Any]],
]:
    """Extract and deduplicate entities from content items.

    Parameters
    ----------
    content_items
        List of (content_id, about_entities) tuples packed as dicts
        with keys: ``content_id``, ``content_type``, ``about_entities``.
    entity_relations
        Raw entity_relations from input JSON.

    Returns
    -------
    tuple
        (entities, entity_key_to_id, mentions_rels, relates_to_rels)
    """
    entity_key_to_id: dict[str, str] = {}
    entities: list[dict[str, Any]] = []
    mentions_rels: list[dict[str, str]] = []

    for item in content_items:
        content_id = item["content_id"]
        content_type = item["content_type"]
        about_entities = item.get("about_entities") or []

        for ent in about_entities:
            name = ent.get("name", "").strip()
            entity_type = ent.get("entity_type", "").strip().lower()

            if not name or not entity_type:
                logger.warning("Skipping entity with empty name/type: %s", ent)
                continue

            if entity_type not in VALID_ENTITY_TYPES:
                logger.warning(
                    "Invalid entity_type %r for %r (allowed: %s)",
                    entity_type,
                    name,
                    sorted(VALID_ENTITY_TYPES),
                )
                continue

            entity_key = f"{name}::{entity_type}"
            if entity_key not in entity_key_to_id:
                eid = generate_entity_id(name, entity_type)
                entity_key_to_id[entity_key] = eid
                entities.append({
                    "entity_id": eid,
                    "name": name,
                    "entity_type": entity_type,
                    "entity_key": entity_key,
                })

            mentions_rels.append({
                "from_id": content_id,
                "to_id": entity_key_to_id[entity_key],
                "content_type": content_type,
            })

    # Process entity relations
    relates_to_rels: list[dict[str, Any]] = []
    for rel in entity_relations:
        from_key = rel.get("from_entity", "")
        to_key = rel.get("to_entity", "")
        rel_detail = rel.get("rel_detail", "")

        if from_key not in entity_key_to_id:
            logger.warning("RELATES_TO from_entity not found: %s", from_key)
            continue
        if to_key not in entity_key_to_id:
            logger.warning("RELATES_TO to_entity not found: %s", to_key)
            continue

        relates_to_rels.append({
            "from_id": entity_key_to_id[from_key],
            "to_id": entity_key_to_id[to_key],
            "rel_detail": rel_detail,
        })

    return entities, entity_key_to_id, mentions_rels, relates_to_rels


# ---------------------------------------------------------------------------
# Main mapper
# ---------------------------------------------------------------------------


def map_creator_enrichment(data: dict[str, Any]) -> dict[str, Any]:
    """Map enrichment input JSON to creator graph-queue format.

    Parameters
    ----------
    data
        Input JSON conforming to the creator-enrichment input spec.

    Returns
    -------
    dict
        Graph-queue JSON ready for /save-to-creator-graph.
    """
    genre_id = data.get("genre", "")
    if genre_id not in GENRE_NAMES:
        logger.error("Unknown genre: %r", genre_id)
        sys.exit(1)

    # --- Sources ---
    source_url_to_id: dict[str, str] = {}
    sources: list[dict[str, Any]] = []
    for src in data.get("sources", []):
        url = src.get("url", "").strip()
        if not url:
            logger.warning("Skipping source with empty URL")
            continue
        sid = generate_source_id(url)
        source_url_to_id[url] = sid
        sources.append({
            "source_id": sid,
            "url": url,
            "title": src.get("title", ""),
            "source_type": _validate_enum(
                src.get("source_type", "web"), VALID_SOURCE_TYPES, "source_type"
            ),
            "authority_level": _validate_enum(
                src.get("authority_level", "blog"),
                VALID_AUTHORITY_LEVELS,
                "authority_level",
            ),
            "collected_at": src.get("collected_at", ""),
        })

    # --- Topics ---
    topic_name_to_id: dict[str, str] = {}
    topics: list[dict[str, Any]] = []

    def _ensure_topic(name: str) -> str:
        """Ensure a topic exists and return its ID."""
        if name in topic_name_to_id:
            return topic_name_to_id[name]
        tid = generate_creator_topic_id(name, genre_id)
        topic_name_to_id[name] = tid
        topics.append({
            "topic_id": tid,
            "name": name,
            "genre_id": genre_id,
        })
        return tid

    # --- Content items (Fact, Tip, Story) + entity tracking ---
    entity_content_items: list[dict[str, Any]] = []

    # Process Facts
    facts: list[dict[str, Any]] = []
    about_fact_rels: list[dict[str, str]] = []
    from_source_fact_rels: list[dict[str, str]] = []

    for f in data.get("facts", []):
        text = f.get("text", "").strip()
        if not text:
            continue
        fid = generate_creator_fact_id(text)
        facts.append({
            "fact_id": fid,
            "text": text,
            "category": _validate_enum(
                f.get("category", "research"), VALID_FACT_CATEGORIES, "fact.category"
            ),
            "confidence": _validate_enum(
                f.get("confidence", "medium"),
                VALID_CONFIDENCE_LEVELS,
                "fact.confidence",
            ),
        })

        # ABOUT relations (fact -> topic)
        for topic_name in f.get("about_topics", []):
            tid = _ensure_topic(topic_name)
            about_fact_rels.append({"from_id": fid, "to_id": tid})

        # FROM_SOURCE relation
        source_url = f.get("source_url", "")
        if source_url in source_url_to_id:
            from_source_fact_rels.append({
                "from_id": fid,
                "to_id": source_url_to_id[source_url],
            })
        elif source_url:
            logger.warning("Fact source_url not in sources: %s", source_url)

        # Entity tracking
        entity_content_items.append({
            "content_id": fid,
            "content_type": "fact",
            "about_entities": f.get("about_entities", []),
        })

    # Process Tips
    tips: list[dict[str, Any]] = []
    about_tip_rels: list[dict[str, str]] = []
    from_source_tip_rels: list[dict[str, str]] = []

    for t in data.get("tips", []):
        text = t.get("text", "").strip()
        if not text:
            continue
        tid = generate_creator_tip_id(text)
        tips.append({
            "tip_id": tid,
            "text": text,
            "category": _validate_enum(
                t.get("category", "strategy"), VALID_TIP_CATEGORIES, "tip.category"
            ),
            "difficulty": _validate_enum(
                t.get("difficulty", "beginner"),
                VALID_DIFFICULTY_LEVELS,
                "tip.difficulty",
            ),
        })

        for topic_name in t.get("about_topics", []):
            topic_id = _ensure_topic(topic_name)
            about_tip_rels.append({"from_id": tid, "to_id": topic_id})

        source_url = t.get("source_url", "")
        if source_url in source_url_to_id:
            from_source_tip_rels.append({
                "from_id": tid,
                "to_id": source_url_to_id[source_url],
            })
        elif source_url:
            logger.warning("Tip source_url not in sources: %s", source_url)

        entity_content_items.append({
            "content_id": tid,
            "content_type": "tip",
            "about_entities": t.get("about_entities", []),
        })

    # Process Stories
    stories: list[dict[str, Any]] = []
    about_story_rels: list[dict[str, str]] = []
    from_source_story_rels: list[dict[str, str]] = []

    for s in data.get("stories", []):
        text = s.get("text", "").strip()
        if not text:
            continue
        sid = generate_creator_story_id(text)
        stories.append({
            "story_id": sid,
            "text": text,
            "outcome": _validate_enum(
                s.get("outcome", "mixed"), VALID_STORY_OUTCOMES, "story.outcome"
            ),
            "timeline": s.get("timeline", ""),
        })

        for topic_name in s.get("about_topics", []):
            topic_id = _ensure_topic(topic_name)
            about_story_rels.append({"from_id": sid, "to_id": topic_id})

        source_url = s.get("source_url", "")
        if source_url in source_url_to_id:
            from_source_story_rels.append({
                "from_id": sid,
                "to_id": source_url_to_id[source_url],
            })
        elif source_url:
            logger.warning("Story source_url not in sources: %s", source_url)

        entity_content_items.append({
            "content_id": sid,
            "content_type": "story",
            "about_entities": s.get("about_entities", []),
        })

    # --- Entities + Relations ---
    entity_relations_input = data.get("entity_relations", [])
    entities, _entity_key_to_id, mentions_rels, relates_to_rels = _build_entities(
        entity_content_items, entity_relations_input
    )

    # Split mentions by content type
    mentions_fact = [r for r in mentions_rels if r["content_type"] == "fact"]
    mentions_tip = [r for r in mentions_rels if r["content_type"] == "tip"]
    mentions_story = [r for r in mentions_rels if r["content_type"] == "story"]

    # Strip content_type from mentions (not needed in output)
    def _strip_type(rels: list[dict[str, str]]) -> list[dict[str, str]]:
        return [{"from_id": r["from_id"], "to_id": r["to_id"]} for r in rels]

    # --- IN_GENRE relations ---
    in_genre_rels = [
        {"from_id": t["topic_id"], "to_id": genre_id} for t in topics
    ]

    # --- Build queue document ---
    queue_id = generate_creator_queue_id()
    now = datetime.now(timezone.utc).isoformat()

    queue_doc: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "queue_id": queue_id,
        "created_at": now,
        "command_source": "creator-enrichment",
        "genre_id": genre_id,
        "genres": [{"genre_id": genre_id, "name": GENRE_NAMES[genre_id]}],
        "topics": topics,
        "sources": sources,
        "entities": entities,
        "facts": facts,
        "tips": tips,
        "stories": stories,
        "relations": {
            "in_genre": in_genre_rels,
            "about_fact": about_fact_rels,
            "about_tip": about_tip_rels,
            "about_story": about_story_rels,
            "from_source_fact": from_source_fact_rels,
            "from_source_tip": from_source_tip_rels,
            "from_source_story": from_source_story_rels,
            "mentions_fact": _strip_type(mentions_fact),
            "mentions_tip": _strip_type(mentions_tip),
            "mentions_story": _strip_type(mentions_story),
            "relates_to": relates_to_rels,
        },
    }

    # --- Summary ---
    total_content = len(facts) + len(tips) + len(stories)
    total_mentions = len(mentions_fact) + len(mentions_tip) + len(mentions_story)
    logger.info(
        "Mapped: %d sources, %d topics, %d entities, "
        "%d facts, %d tips, %d stories, "
        "%d mentions, %d relates_to",
        len(sources),
        len(topics),
        len(entities),
        len(facts),
        len(tips),
        len(stories),
        total_mentions,
        len(relates_to_rels),
    )
    if total_content == 0:
        logger.warning("No content items found in input")

    return queue_doc


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Emit creator-graph-queue JSON from enrichment data."
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Input JSON file (creator-enrichment format)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_BASE,
        help=f"Output directory (default: {DEFAULT_OUTPUT_BASE})",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Read input
    input_path: Path = args.input
    if not input_path.exists():
        logger.error("Input file not found: %s", input_path)
        sys.exit(1)

    data = json.loads(input_path.read_text(encoding="utf-8"))
    logger.info("Read input: %s", input_path)

    # Map
    queue_doc = map_creator_enrichment(data)

    # Write output
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{queue_doc['queue_id']}.json"
    output_path.write_text(
        json.dumps(queue_doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    logger.info("Written: %s", output_path)


if __name__ == "__main__":
    main()
