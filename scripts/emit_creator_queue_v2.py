#!/usr/bin/env python3
"""Emit creator-graph-queue v2 JSON from enrichment data.

Converts creator-enrichment v2 output (Entity/Concept separated, 14 ConceptCategories)
into a graph-queue format for /save-to-creator-graph v2.

Schema changes from v1:
- Entity: 4 types only (platform, company, person, organization)
- Concept: replaces Topic, classified into 14 ConceptCategories via IS_A
- SERVES_AS: Entity → Concept role relationship
- ABOUT: Content → Concept (replaces Content → Topic)
- IN_GENRE: directly on Content (not via Topic)
- Alias: separate nodes for fuzzy matching
- Domain: Source → Domain relationship
- ENABLES/REQUIRES/COMPETES_WITH: replace RELATES_TO

Usage
-----
::

    python3 scripts/emit_creator_queue_v2.py --input cycle-input.json

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
from urllib.parse import urlparse

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

SCHEMA_VERSION = "creator-2.0"

DEFAULT_OUTPUT_BASE = Path(".tmp/creator-graph-queue")

VALID_SOURCE_TYPES = frozenset({"web", "reddit", "blog", "report"})
VALID_AUTHORITY_LEVELS = frozenset({"official", "media", "blog", "social"})
VALID_LANGUAGES = frozenset({"ja", "en"})
VALID_ENTITY_TYPES = frozenset({"platform", "company", "person", "organization"})
VALID_FACT_CATEGORIES = frozenset({"statistics", "market_data", "research", "trend"})
VALID_TIP_CATEGORIES = frozenset({"strategy", "tool", "process", "mindset"})
VALID_STORY_OUTCOMES = frozenset({"success", "failure", "mixed", "ongoing"})
VALID_CONFIDENCE_LEVELS = frozenset({"high", "medium", "low"})
VALID_DIFFICULTY_LEVELS = frozenset({"beginner", "intermediate", "advanced"})
VALID_CONCEPT_CATEGORIES = frozenset({
    # What layer
    "MonetizationMethod", "AcquisitionChannel", "Skill", "Audience",
    "RevenueModel", "SuccessMetric", "ContentFormat", "Regulation", "Milestone",
    # How layer
    "PersuasionTechnique", "EmotionalHook", "CopyFramework",
    "Objection", "Transformation",
})
VALID_CONCEPT_RELATION_TYPES = frozenset({"ENABLES", "REQUIRES", "COMPETES_WITH"})

GENRE_NAMES: dict[str, str] = {
    "career": "転職・副業",
    "beauty-romance": "美容・恋愛",
    "spiritual": "占い・スピリチュアル",
}

CONCEPT_CATEGORY_LAYERS: dict[str, str] = {
    "MonetizationMethod": "what", "AcquisitionChannel": "what",
    "Skill": "what", "Audience": "what", "RevenueModel": "what",
    "SuccessMetric": "what", "ContentFormat": "what",
    "Regulation": "what", "Milestone": "what",
    "PersuasionTechnique": "how", "EmotionalHook": "how",
    "CopyFramework": "how", "Objection": "how", "Transformation": "how",
}

CONCEPT_CATEGORY_NAMES_JA: dict[str, str] = {
    "MonetizationMethod": "収益化手段", "AcquisitionChannel": "集客チャネル",
    "Skill": "スキル・技能", "Audience": "ターゲット層",
    "RevenueModel": "収益モデル", "SuccessMetric": "成果指標",
    "ContentFormat": "コンテンツ形式", "Regulation": "法規制",
    "Milestone": "時間軸目安",
    "PersuasionTechnique": "説得技法", "EmotionalHook": "感情トリガー",
    "CopyFramework": "文章構成パターン", "Objection": "読者の反論・障壁",
    "Transformation": "変化パターン",
}


# ---------------------------------------------------------------------------
# ID Generation
# ---------------------------------------------------------------------------


def _sha256_prefix(key: str, length: int = 8) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:length]


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKC", text.strip().lower())
    return text.replace(" ", "-").replace("　", "-")


def generate_concept_id(name: str) -> str:
    return f"concept-{_sha256_prefix(name)}"


def generate_fact_id(text: str) -> str:
    return f"fact-{_sha256_prefix(text)}"


def generate_tip_id(text: str) -> str:
    return f"tip-{_sha256_prefix(text)}"


def generate_story_id(text: str) -> str:
    return f"story-{_sha256_prefix(text)}"


def generate_queue_id() -> str:
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d%H%M%S")
    rand8 = secrets.token_hex(4)
    return f"cq-{timestamp}-{rand8}"


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_enum(value: str, allowed: frozenset[str], field_name: str) -> str:
    if value not in allowed:
        logger.warning(
            "Invalid %s: %r (allowed: %s)", field_name, value, sorted(allowed)
        )
    return value


# ---------------------------------------------------------------------------
# Main Mapper
# ---------------------------------------------------------------------------


def map_creator_enrichment_v2(data: dict[str, Any]) -> dict[str, Any]:
    """Map enrichment v2 input to creator graph-queue v2 format."""
    genre_id = data.get("genre", "")
    if genre_id not in GENRE_NAMES:
        logger.error("Unknown genre: %r", genre_id)
        sys.exit(1)

    now = datetime.now(timezone.utc).isoformat()

    # --- ConceptCategories (from concepts in input) ---
    used_categories: set[str] = set()
    concept_categories: list[dict[str, Any]] = []

    # --- Sources + Domains ---
    source_url_to_id: dict[str, str] = {}
    sources: list[dict[str, Any]] = []
    domain_set: dict[str, dict[str, Any]] = {}

    for src in data.get("sources", []):
        url = src.get("url", "").strip()
        if not url:
            continue
        sid = generate_source_id(url)
        source_url_to_id[url] = sid

        domain_name = extract_domain(url)

        sources.append({
            "source_id": sid,
            "url": url,
            "title": src.get("title", ""),
            "source_type": _validate_enum(
                src.get("source_type", "web"), VALID_SOURCE_TYPES, "source_type"
            ),
            "authority_level": _validate_enum(
                src.get("authority_level", "blog"),
                VALID_AUTHORITY_LEVELS, "authority_level",
            ),
            "language": _validate_enum(
                src.get("language", "en"), VALID_LANGUAGES, "language"
            ),
            "domain": domain_name,
            "collected_at": src.get("collected_at", ""),
            "published_at": src.get("published_at", ""),
        })

        if domain_name not in domain_set:
            domain_set[domain_name] = {"name": domain_name}

    domains = list(domain_set.values())

    # --- Entities ---
    entities: list[dict[str, Any]] = []
    entity_name_to_id: dict[str, str] = {}

    for ent in data.get("entities", []):
        name = ent.get("name", "").strip()
        entity_type = ent.get("entity_type", "").strip().lower()
        if not name or not entity_type:
            continue
        if entity_type not in VALID_ENTITY_TYPES:
            logger.warning("Invalid entity_type: %r for %r", entity_type, name)
            continue

        entity_key = f"{name}::{entity_type}"
        eid = generate_entity_id(name, entity_type)
        entity_name_to_id[name] = eid

        # Use resolved ID if available
        resolved_id = ent.get("entity_id", eid)
        resolved_key = ent.get("entity_key", entity_key)

        entities.append({
            "entity_id": resolved_id,
            "entity_key": resolved_key,
            "name": name,
            "entity_type": entity_type,
            "resolved": ent.get("resolved", False),
        })

    # --- Concepts ---
    concepts: list[dict[str, Any]] = []
    concept_name_to_id: dict[str, str] = {}

    for con in data.get("concepts", []):
        name = con.get("name", "").strip()
        category = con.get("category", "").strip()
        if not name:
            continue

        # Validate category
        if category and category not in VALID_CONCEPT_CATEGORIES:
            if con.get("new_category"):
                logger.info("New category proposed: %r for concept %r", category, name)
            else:
                logger.warning("Invalid category: %r for %r", category, name)

        cid = generate_concept_id(name)
        concept_name_to_id[name] = cid

        # Use resolved ID if available
        resolved_id = con.get("concept_id", cid)

        concepts.append({
            "concept_id": resolved_id,
            "name": name,
            "category": category,
            "new_category": con.get("new_category", False),
            "resolved": con.get("resolved", False),
        })

        # Track used categories
        if category:
            used_categories.add(category)

    # Build ConceptCategory nodes for used categories
    for cat in used_categories:
        if cat in VALID_CONCEPT_CATEGORIES:
            concept_categories.append({
                "name": cat,
                "name_ja": CONCEPT_CATEGORY_NAMES_JA.get(cat, cat),
                "layer": CONCEPT_CATEGORY_LAYERS.get(cat, "what"),
            })

    # --- Content (Fact/Tip/Story) ---
    def _process_content(
        items: list[dict[str, Any]],
        content_type: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[dict[str, str]],
               list[dict[str, str]], list[dict[str, str]]]:
        """Process content items and return nodes + relations."""
        nodes = []
        about_rels = []
        from_source_rels = []
        mentions_rels = []
        in_genre_rels = []

        for item in items:
            text = item.get("text", "").strip()
            if not text:
                continue

            if content_type == "fact":
                cid = generate_fact_id(text)
                node = {
                    "fact_id": cid,
                    "text": text,
                    "category": _validate_enum(
                        item.get("category", "research"),
                        VALID_FACT_CATEGORIES, "fact.category"
                    ),
                    "confidence": _validate_enum(
                        item.get("confidence", "medium"),
                        VALID_CONFIDENCE_LEVELS, "fact.confidence"
                    ),
                }
            elif content_type == "tip":
                cid = generate_tip_id(text)
                node = {
                    "tip_id": cid,
                    "text": text,
                    "category": _validate_enum(
                        item.get("category", "strategy"),
                        VALID_TIP_CATEGORIES, "tip.category"
                    ),
                    "difficulty": _validate_enum(
                        item.get("difficulty", "beginner"),
                        VALID_DIFFICULTY_LEVELS, "tip.difficulty"
                    ),
                }
            else:  # story
                cid = generate_story_id(text)
                node = {
                    "story_id": cid,
                    "text": text,
                    "outcome": _validate_enum(
                        item.get("outcome", "mixed"),
                        VALID_STORY_OUTCOMES, "story.outcome"
                    ),
                    "timeline": item.get("timeline", ""),
                }

            nodes.append(node)

            # ABOUT → Concept
            for concept_name in item.get("about_concepts", []):
                if concept_name in concept_name_to_id:
                    about_rels.append({
                        "from_id": cid,
                        "to_id": concept_name_to_id[concept_name],
                    })

            # FROM_SOURCE
            source_url = item.get("source_url", "")
            if source_url in source_url_to_id:
                from_source_rels.append({
                    "from_id": cid,
                    "to_id": source_url_to_id[source_url],
                })

            # MENTIONS → Entity
            for ent in item.get("about_entities", []):
                ent_name = ent.get("name", "")
                if ent_name in entity_name_to_id:
                    mentions_rels.append({
                        "from_id": cid,
                        "to_id": entity_name_to_id[ent_name],
                    })

            # IN_GENRE
            in_genre_rels.append({
                "from_id": cid,
                "to_id": genre_id,
            })

        return nodes, about_rels, from_source_rels, mentions_rels, in_genre_rels

    facts, about_fact, fs_fact, men_fact, ig_fact = _process_content(
        data.get("facts", []), "fact"
    )
    tips, about_tip, fs_tip, men_tip, ig_tip = _process_content(
        data.get("tips", []), "tip"
    )
    stories, about_story, fs_story, men_story, ig_story = _process_content(
        data.get("stories", []), "story"
    )

    # --- SERVES_AS (Entity → Concept) ---
    serves_as_rels: list[dict[str, Any]] = []
    for sa in data.get("serves_as", []):
        ent_name = sa.get("entity_name", "")
        con_name = sa.get("concept_name", "")
        if ent_name in entity_name_to_id and con_name in concept_name_to_id:
            serves_as_rels.append({
                "from_id": entity_name_to_id[ent_name],
                "to_id": concept_name_to_id[con_name],
                "context": sa.get("context", ""),
            })

    # --- IS_A (Concept → ConceptCategory) ---
    is_a_rels: list[dict[str, str]] = []
    for con in concepts:
        if con.get("category"):
            is_a_rels.append({
                "from_id": con["concept_id"],
                "to_id": con["category"],
            })

    # --- Concept Relations (ENABLES/REQUIRES/COMPETES_WITH) ---
    concept_rels: list[dict[str, Any]] = []
    for rel in data.get("concept_relations", []):
        from_name = rel.get("from_concept", "")
        to_name = rel.get("to_concept", "")
        rel_type = rel.get("rel_type", "")

        if from_name not in concept_name_to_id:
            logger.warning("concept_relation from not found: %s", from_name)
            continue
        if to_name not in concept_name_to_id:
            logger.warning("concept_relation to not found: %s", to_name)
            continue
        if rel_type not in VALID_CONCEPT_RELATION_TYPES:
            logger.warning("Invalid concept relation type: %s", rel_type)
            continue

        concept_rels.append({
            "from_id": concept_name_to_id[from_name],
            "to_id": concept_name_to_id[to_name],
            "rel_type": rel_type,
        })

    # --- FROM_DOMAIN (Source → Domain) ---
    from_domain_rels: list[dict[str, str]] = []
    for src in sources:
        from_domain_rels.append({
            "from_id": src["source_id"],
            "to_id": src["domain"],
        })

    # --- Build queue document ---
    queue_id = generate_queue_id()
    queue_doc: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "queue_id": queue_id,
        "created_at": now,
        "command_source": "creator-enrichment-v2",
        "genre_id": genre_id,
        "genres": [{"genre_id": genre_id, "name": GENRE_NAMES[genre_id]}],
        "concept_categories": concept_categories,
        "concepts": concepts,
        "sources": sources,
        "domains": domains,
        "entities": entities,
        "facts": facts,
        "tips": tips,
        "stories": stories,
        "relations": {
            "is_a": is_a_rels,
            "serves_as": serves_as_rels,
            "about_fact": about_fact,
            "about_tip": about_tip,
            "about_story": about_story,
            "from_source_fact": fs_fact,
            "from_source_tip": fs_tip,
            "from_source_story": fs_story,
            "from_domain": from_domain_rels,
            "mentions_fact": men_fact,
            "mentions_tip": men_tip,
            "mentions_story": men_story,
            "in_genre_fact": ig_fact,
            "in_genre_tip": ig_tip,
            "in_genre_story": ig_story,
            "concept_relations": concept_rels,
        },
    }

    # --- Summary ---
    total_content = len(facts) + len(tips) + len(stories)
    total_mentions = len(men_fact) + len(men_tip) + len(men_story)
    total_about = len(about_fact) + len(about_tip) + len(about_story)
    logger.info(
        "Mapped: %d sources, %d domains, %d concepts (%d categories), "
        "%d entities, %d facts, %d tips, %d stories, "
        "%d about, %d mentions, %d serves_as, %d concept_rels",
        len(sources), len(domains), len(concepts), len(concept_categories),
        len(entities), len(facts), len(tips), len(stories),
        total_about, total_mentions, len(serves_as_rels), len(concept_rels),
    )
    if total_content == 0:
        logger.warning("No content items found in input")

    return queue_doc


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Emit creator-graph-queue v2 JSON from enrichment data."
    )
    parser.add_argument(
        "--input", required=True, type=Path,
        help="Input JSON file (creator-enrichment v2 format)",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT_BASE,
        help=f"Output directory (default: {DEFAULT_OUTPUT_BASE})",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    input_path: Path = args.input
    if not input_path.exists():
        logger.error("Input file not found: %s", input_path)
        sys.exit(1)

    data = json.loads(input_path.read_text(encoding="utf-8"))
    logger.info("Read input: %s", input_path)

    queue_doc = map_creator_enrichment_v2(data)

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
