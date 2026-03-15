#!/usr/bin/env python3
"""Migrate articles from old folder structure to unified structure.

This script handles the migration of existing articles from their legacy
folder layout to the new unified structure with standardized sub-directories
(01_research, 02_draft, 03_published) and meta.yaml files.

Usage:
    # Preview all migrations (dry-run)
    uv run python scripts/migrate_articles.py --dry-run

    # Migrate all articles
    uv run python scripts/migrate_articles.py

    # Migrate a single article
    uv run python scripts/migrate_articles.py --article economic_indicators_001_private-credit-bank-shadow-banking-risk

    # Migrate a single article (dry-run)
    uv run python scripts/migrate_articles.py --dry-run --article economic_indicators_001_private-credit-bank-shadow-banking-risk
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from yaml import safe_dump, safe_load

# ---------------------------------------------------------------------------
# Logging setup (follows project convention from _logging.py pattern)
# ---------------------------------------------------------------------------

_log_initialized = False


def _setup_logging() -> None:
    global _log_initialized  # noqa: PLW0603
    if _log_initialized:
        return
    _log_initialized = True

    level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
    level_value = getattr(logging, level_str, logging.INFO)

    logging.basicConfig(
        level=level_value,
        format="%(message)s",
        stream=sys.stderr,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    _setup_logging()
    return structlog.get_logger(name)


logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ARTICLES_DIR = Path(__file__).resolve().parent.parent / "articles"

# Category mapping: old category name -> new category name
CATEGORY_MAP: dict[str, str] = {
    "economic_indicators": "macro_economy",
    "asset_management": "asset_formation",
    "experience_db": "side_business",
    "market_report": "weekly_report",
    "stock_analysis": "stock_analysis",
    "quant_analysis": "quant_analysis",
}

# Status mapping: old status -> new status
STATUS_MAP: dict[str, str] = {
    "research": "draft",
    "edit": "draft",
    "collecting": "draft",
    "revised": "review",
    "ready_for_publish": "review",
    "published": "published",
}

# Type inference from new category
TYPE_MAP: dict[str, str] = {
    "macro_economy": "column",
    "stock_analysis": "data_analysis",
    "asset_formation": "column",
    "side_business": "experience",
    "weekly_report": "weekly_report",
    "quant_analysis": "data_analysis",
}

# Standard sub-directories in new structure
NEW_SUBDIRS = ["01_research", "02_draft", "03_published"]


# ---------------------------------------------------------------------------
# Migration map
# ---------------------------------------------------------------------------


@dataclass
class MigrationEntry:
    """Describes one article migration."""

    old_path: str
    new_path: str
    new_category: str
    skip: bool = False
    notes: str = ""
    # Folder rename mapping: old sub-dir name -> new sub-dir name
    folder_renames: dict[str, str] = field(default_factory=dict)
    # Special handling flags
    flat_structure: bool = False
    sidehustle_layout: bool = False
    weekly_report_layout: bool = False


MIGRATION_MAP: list[MigrationEntry] = [
    # 1. economic_indicators_001
    MigrationEntry(
        old_path="economic_indicators_001_private-credit-bank-shadow-banking-risk",
        new_path="macro_economy/2026-03-07_private-credit-shadow-banking",
        new_category="macro_economy",
        folder_renames={"02_edit": "02_draft", "03_published": "03_published"},
        notes="Category change economic_indicators->macro_economy, 02_edit->02_draft",
    ),
    # 2. economic_indicators_002
    MigrationEntry(
        old_path="economic_indicators_002_boj-rate-hike-takaichi-trade-yen-scenario",
        new_path="macro_economy/2026-03-08_boj-rate-hike-yen-scenario",
        new_category="macro_economy",
        folder_renames={"02_edit": "02_draft", "03_published": "03_published"},
        notes="Category change, 02_edit->02_draft",
    ),
    # 3. economic_indicators_003
    MigrationEntry(
        old_path="economic_indicators_003_oil-150-shock-middle-east-stagflation",
        new_path="macro_economy/2026-03-09_oil-150-shock-stagflation",
        new_category="macro_economy",
        folder_renames={"02_edit": "02_draft", "03_published": "03_published"},
        notes="Category change, 02_edit->02_draft",
    ),
    # 4. stock_analysis_001
    MigrationEntry(
        old_path="stock_analysis_001_tech-to-high-dividend-rotation-vz",
        new_path="stock_analysis/2026-03-08_tech-to-high-dividend-vz",
        new_category="stock_analysis",
        folder_renames={"02_edit": "02_draft", "03_published": "03_published"},
        notes="02_edit->02_draft",
    ),
    # 5. stock_analysis_002 (flat structure)
    MigrationEntry(
        old_path="stock_analysis_002_blackrock-private-credit-liquidity-risk",
        new_path="stock_analysis/2026-03-08_blackrock-private-credit",
        new_category="stock_analysis",
        flat_structure=True,
        notes="Flat->structured, article.md->02_draft/first_draft.md",
    ),
    # 6. asset_management/fund_selection_age_based
    MigrationEntry(
        old_path="asset_management/fund_selection_age_based",
        new_path="asset_formation/2026-03-08_fund-selection-age-based",
        new_category="asset_formation",
        folder_renames={"02_edit": "02_draft"},
        notes="Category change, add 01_research/03_published",
    ),
    # 7. asset_management/index-investing-portfolio-allocation
    MigrationEntry(
        old_path="asset_management/index-investing-portfolio-allocation",
        new_path="asset_formation/2026-03-06_index-investing-portfolio",
        new_category="asset_formation",
        folder_renames={"02_edit": "02_draft"},
        notes="Category change, add missing sub-dirs",
    ),
    # 8. asset_management/index_vs_etf_2026 (flat structure)
    MigrationEntry(
        old_path="asset_management/index_vs_etf_2026",
        new_path="asset_formation/2026-03-08_index-vs-etf-2026",
        new_category="asset_formation",
        flat_structure=True,
        notes="Flat->structured, note_article.md->02_draft/first_draft.md",
    ),
    # 9. exp-sidehustle-002
    MigrationEntry(
        old_path="exp-sidehustle-002-skill-freelance",
        new_path="side_business/2026-03-09_video-editing-freelance",
        new_category="side_business",
        sidehustle_layout=True,
        folder_renames={
            "01_sources": "01_research",
            "03_edit": "02_draft",
        },
        notes="01_sources->01_research, 02_synthesis->01_research/synthesis.json, "
        "03_edit->02_draft, add 03_published",
    ),
    # 10. exp-sidehustle-003
    MigrationEntry(
        old_path="exp-sidehustle-003-pending",
        new_path="side_business/2026-03-09_sidehustle-003-pending",
        new_category="side_business",
        sidehustle_layout=True,
        folder_renames={
            "01_sources": "01_research",
            "03_edit": "02_draft",
            "04_published": "03_published",
        },
        notes="Same sidehustle layout migration",
    ),
    # 11. weekly_report/2026-02-23
    MigrationEntry(
        old_path="weekly_report/2026-02-23",
        new_path="weekly_report/2026-02-23_weekly-market-report",
        new_category="weekly_report",
        weekly_report_layout=True,
        folder_renames={"02_edit": "02_draft", "03_published": "03_published"},
        notes="data->01_research/market, 02_edit->02_draft",
    ),
    # 12. investor_memo_conversion (SKIP)
    MigrationEntry(
        old_path="investor_memo_conversion",
        new_path="",
        new_category="",
        skip=True,
        notes="Not an article, skipped",
    ),
]


# ---------------------------------------------------------------------------
# Meta conversion
# ---------------------------------------------------------------------------


def _map_status(old_status: str) -> str:
    """Map old status value to new status value."""
    return STATUS_MAP.get(old_status, "draft")


def _infer_type(category: str) -> str:
    """Infer article type from category."""
    return TYPE_MAP.get(category, "column")


def _normalize_date_range(
    date_range: dict[str, str] | None,
) -> dict[str, str]:
    """Normalize date_range to use 'start'/'end' keys."""
    if not date_range:
        return {"start": "", "end": ""}
    return {
        "start": date_range.get("start") or date_range.get("start_date", ""),
        "end": date_range.get("end") or date_range.get("end_date", ""),
    }


def _phase_status(phase_data: Any) -> str:
    """Determine if a workflow phase is done, in_progress, or pending.

    Parameters
    ----------
    phase_data : Any
        Phase data — a string status, a dict of sub-statuses, or other.

    Returns
    -------
    str
        One of "done", "in_progress", or "pending".
    """
    if isinstance(phase_data, str):
        return phase_data
    if isinstance(phase_data, dict):
        values = [
            str(v)
            for v in phase_data.values()
            if isinstance(v, str)
        ]
        if not values:
            return "pending"
        if all(v == "done" for v in values):
            return "done"
        if any(v == "done" for v in values):
            return "in_progress"
        return "pending"
    return "pending"


def _best_status(
    keys: list[str],
    workflow: dict[str, Any],
) -> str:
    """Pick the best status from multiple workflow keys.

    Parameters
    ----------
    keys : list[str]
        Old workflow keys to check.
    workflow : dict[str, Any]
        The old workflow dict.

    Returns
    -------
    str
        One of "done", "in_progress", or "pending".
    """
    statuses = [
        _phase_status(workflow[k])
        for k in keys
        if k in workflow
    ]
    if not statuses:
        return "pending"
    if all(s == "done" for s in statuses):
        return "done"
    if any(s in ("done", "in_progress") for s in statuses):
        return "in_progress"
    return "pending"


# Mapping from old workflow keys to new phase names
_WORKFLOW_KEY_MAP: dict[str, list[str]] = {
    "research": ["data_collection", "processing", "research", "collecting"],
    "draft": ["writing"],
    "critique": ["critique"],
    "revision": ["revision"],
    "publish": ["publishing"],
}

_PENDING_WORKFLOW: dict[str, str] = {
    "research": "pending",
    "draft": "pending",
    "critique": "pending",
    "revision": "pending",
    "publish": "pending",
}


def _simplify_workflow(old_workflow: dict[str, Any] | None) -> dict[str, str]:
    """Convert complex nested workflow to simple flat workflow.

    The new schema uses a flat structure with 5 keys:
    research, draft, critique, revision, publish.
    Each has value: pending | in_progress | done.
    """
    if not old_workflow:
        return dict(_PENDING_WORKFLOW)

    return {
        phase: _best_status(keys, old_workflow)
        for phase, keys in _WORKFLOW_KEY_MAP.items()
    }


def _extract_critic_score(workflow_data: dict[str, Any]) -> int | None:
    """Extract critic total score from old workflow critique data."""
    critique_data = workflow_data.get("critique", {})
    if isinstance(critique_data, dict):
        total = critique_data.get("total_score")
        if total is not None:
            return int(total)
    return None


def _extract_research_sources(workflow_data: dict[str, Any]) -> int:
    """Count research sources from collecting workflow data."""
    collecting = workflow_data.get("collecting", {})
    if isinstance(collecting, dict):
        return collecting.get("source_count", 0) or 0
    return 0


def _build_neo4j_meta(old: dict[str, Any]) -> dict[str, Any]:
    """Build neo4j metadata from old meta."""
    old_neo4j = old.get("neo4j", {})
    if old_neo4j:
        return {
            "pattern_node_id": old_neo4j.get("pattern_node_id") or None,
            "source_node_ids": old_neo4j.get("source_node_ids", []),
            "embed_resource_ids": old_neo4j.get("embed_resource_ids", []),
        }
    return {
        "pattern_node_id": None,
        "source_node_ids": [],
        "embed_resource_ids": [],
    }


def _extract_target_wordcount(
    workflow_data: dict[str, Any],
    default: int = 4000,
) -> int:
    """Extract target wordcount from revision data if available."""
    revision_data = workflow_data.get("revision", {})
    if isinstance(revision_data, dict):
        wc = revision_data.get("wordcount", 0)
        if wc and wc > 0:
            return int(wc)
    return default


def convert_meta(
    old_meta_path: Path | None,
    new_category: str,
    old_path: str,
) -> dict[str, Any]:
    """Convert article-meta.json to meta.yaml dict.

    Parameters
    ----------
    old_meta_path : Path | None
        Path to the old article-meta.json file. None if not present.
    new_category : str
        The new category for this article.
    old_path : str
        The old relative path of the article (for legacy tracking).

    Returns
    -------
    dict[str, Any]
        The new meta.yaml content as a dict.
    """
    now_iso = datetime.now(tz=timezone.utc).isoformat()

    if old_meta_path and old_meta_path.exists():
        with old_meta_path.open(encoding="utf-8") as f:
            old: dict[str, Any] = json.load(f)
        logger.info(
            "Loaded old meta",
            path=str(old_meta_path),
            article_id=old.get("article_id", ""),
        )
    else:
        old = {}
        logger.warning(
            "No article-meta.json found, creating minimal meta",
            old_path=old_path,
        )

    workflow_data = old.get("workflow", {})
    spec_card = old.get("spec_card", {})

    return {
        # Core
        "title": old.get("topic") or old.get("title", ""),
        "category": new_category,
        "type": _infer_type(new_category),
        "status": _map_status(old.get("status", "research")),
        # Timestamps
        "created_at": old.get("created_at", now_iso),
        "updated_at": old.get("updated_at", now_iso),
        # Content
        "tags": old.get("tags", []),
        "target_audience": old.get("target_audience", "intermediate"),
        "target_wordcount": _extract_target_wordcount(workflow_data),
        # Category-Specific
        "symbols": old.get("symbols", []),
        "date_range": _normalize_date_range(old.get("date_range")),
        "fred_series": old.get("fred_series", []),
        "theme": old.get("theme", ""),
        "experience": {
            "spec_card": {
                "age_range": spec_card.get("age_range", ""),
                "gender": spec_card.get("gender", ""),
                "occupation": spec_card.get("occupation", ""),
                "income_range": spec_card.get("income_range", ""),
                "duration": spec_card.get("duration", ""),
                "outcome": spec_card.get("outcome", ""),
            },
        },
        # Tracking
        "critic_score": _extract_critic_score(workflow_data),
        "revision_count": 0,
        "note_url": None,
        "x_post_url": None,
        "research_sources": _extract_research_sources(workflow_data),
        # Workflow
        "workflow": _simplify_workflow(workflow_data),
        # Neo4j
        "neo4j": _build_neo4j_meta(old),
        # Legacy
        "legacy": {
            "old_path": old_path,
            "old_article_id": old.get("article_id")
            or old.get("pattern_id")
            or None,
            "migrated_at": now_iso,
        },
    }


# ---------------------------------------------------------------------------
# Migration logic
# ---------------------------------------------------------------------------


def _copy_dir_contents(src: Path, dst: Path, *, dry_run: bool) -> None:
    """Copy all files from src directory to dst directory.

    Parameters
    ----------
    src : Path
        Source directory.
    dst : Path
        Destination directory.
    dry_run : bool
        If True, only log actions without performing them.
    """
    if not src.exists():
        logger.debug("Source dir does not exist, skipping", src=str(src))
        return

    for item in sorted(src.iterdir()):
        dest_item = dst / item.name
        if item.is_dir():
            if not dry_run:
                dest_item.mkdir(parents=True, exist_ok=True)
            logger.info("  Copy dir", src=str(item), dst=str(dest_item))
            _copy_dir_contents(item, dest_item, dry_run=dry_run)
        else:
            if item.name == ".DS_Store":
                continue
            logger.info("  Copy file", src=str(item.name), dst=str(dest_item))
            if not dry_run:
                shutil.copy2(item, dest_item)


def _migrate_standard(
    old_dir: Path,
    new_dir: Path,
    entry: MigrationEntry,
    *,
    dry_run: bool,
) -> None:
    """Migrate an article with standard folder layout (01_research, 02_edit, 03_published).

    Handles folder renames (e.g. 02_edit -> 02_draft) and copies 01_research as-is.
    """
    # Copy 01_research as-is if it exists
    old_research = old_dir / "01_research"
    new_research = new_dir / "01_research"
    if old_research.exists():
        if not dry_run:
            new_research.mkdir(parents=True, exist_ok=True)
        logger.info("  Copy 01_research -> 01_research")
        _copy_dir_contents(old_research, new_research, dry_run=dry_run)

    # Apply folder renames
    for old_sub, new_sub in entry.folder_renames.items():
        old_sub_dir = old_dir / old_sub
        new_sub_dir = new_dir / new_sub
        if old_sub_dir.exists():
            if not dry_run:
                new_sub_dir.mkdir(parents=True, exist_ok=True)
            logger.info("  Rename", old=old_sub, new=new_sub)
            _copy_dir_contents(old_sub_dir, new_sub_dir, dry_run=dry_run)


def _migrate_flat(
    old_dir: Path,
    new_dir: Path,
    _entry: MigrationEntry,
    *,
    dry_run: bool,
) -> None:
    """Migrate a flat article (single .md file, no sub-directories).

    Moves the .md file into 02_draft/first_draft.md.
    """
    # Find the article .md file
    md_files = list(old_dir.glob("*.md"))
    if not md_files:
        logger.warning("No .md file found in flat article", path=str(old_dir))
        return

    md_file = md_files[0]
    draft_dir = new_dir / "02_draft"
    if not dry_run:
        draft_dir.mkdir(parents=True, exist_ok=True)
    dest = draft_dir / "first_draft.md"
    logger.info("  Move flat article", src=md_file.name, dst="02_draft/first_draft.md")
    if not dry_run:
        shutil.copy2(md_file, dest)


def _migrate_sidehustle(
    old_dir: Path,
    new_dir: Path,
    entry: MigrationEntry,
    *,
    dry_run: bool,
) -> None:
    """Migrate a sidehustle (experience_db) article.

    Layout changes:
    - 01_sources/ -> 01_research/ (contents copied)
    - 02_synthesis/synthesis.json -> 01_research/synthesis.json
    - 03_edit/ -> 02_draft/
    - 04_published/ -> 03_published/ (if exists)
    """
    new_research = new_dir / "01_research"

    # 01_sources -> 01_research
    old_sources = old_dir / "01_sources"
    if old_sources.exists():
        if not dry_run:
            new_research.mkdir(parents=True, exist_ok=True)
        logger.info("  Copy 01_sources -> 01_research")
        _copy_dir_contents(old_sources, new_research, dry_run=dry_run)

    # 02_synthesis/synthesis.json -> 01_research/synthesis.json
    old_synthesis = old_dir / "02_synthesis"
    if old_synthesis.exists():
        synthesis_file = old_synthesis / "synthesis.json"
        if synthesis_file.exists():
            dest = new_research / "synthesis.json"
            logger.info(
                "  Move synthesis",
                src="02_synthesis/synthesis.json",
                dst="01_research/synthesis.json",
            )
            if not dry_run:
                new_research.mkdir(parents=True, exist_ok=True)
                shutil.copy2(synthesis_file, dest)

    # 03_edit -> 02_draft
    old_edit = old_dir / "03_edit"
    new_draft = new_dir / "02_draft"
    if old_edit.exists():
        if not dry_run:
            new_draft.mkdir(parents=True, exist_ok=True)
        logger.info("  Rename 03_edit -> 02_draft")
        _copy_dir_contents(old_edit, new_draft, dry_run=dry_run)

    # 04_published -> 03_published (if exists)
    old_published = old_dir / "04_published"
    new_published = new_dir / "03_published"
    if old_published.exists():
        if not dry_run:
            new_published.mkdir(parents=True, exist_ok=True)
        logger.info("  Rename 04_published -> 03_published")
        _copy_dir_contents(old_published, new_published, dry_run=dry_run)


def _migrate_weekly_report(
    old_dir: Path,
    new_dir: Path,
    entry: MigrationEntry,
    *,
    dry_run: bool,
) -> None:
    """Migrate a weekly report article.

    Layout changes:
    - data/ -> 01_research/market/ (entire directory)
    - 02_edit/ -> 02_draft/
    - 03_published/ -> 03_published/
    """
    # data/ -> 01_research/market/
    old_data = old_dir / "data"
    new_market = new_dir / "01_research" / "market"
    if old_data.exists():
        if not dry_run:
            new_market.mkdir(parents=True, exist_ok=True)
        logger.info("  Move data -> 01_research/market")
        _copy_dir_contents(old_data, new_market, dry_run=dry_run)

    # Apply standard folder renames (02_edit -> 02_draft, 03_published)
    for old_sub, new_sub in entry.folder_renames.items():
        old_sub_dir = old_dir / old_sub
        new_sub_dir = new_dir / new_sub
        if old_sub_dir.exists():
            if not dry_run:
                new_sub_dir.mkdir(parents=True, exist_ok=True)
            logger.info("  Rename", old=old_sub, new=new_sub)
            _copy_dir_contents(old_sub_dir, new_sub_dir, dry_run=dry_run)


def migrate_article(
    entry: MigrationEntry,
    *,
    dry_run: bool,
) -> bool:
    """Migrate a single article according to its MigrationEntry.

    Parameters
    ----------
    entry : MigrationEntry
        The migration specification for this article.
    dry_run : bool
        If True, only preview changes without writing.

    Returns
    -------
    bool
        True if migration succeeded (or would succeed in dry-run), False otherwise.
    """
    if entry.skip:
        logger.info("SKIP", old_path=entry.old_path, reason=entry.notes)
        return True

    old_dir = ARTICLES_DIR / entry.old_path
    new_dir = ARTICLES_DIR / entry.new_path

    prefix = "[DRY-RUN] " if dry_run else ""
    logger.info(
        f"{prefix}Migrating article",
        old=entry.old_path,
        new=entry.new_path,
    )

    # Validate old path exists
    if not old_dir.exists():
        logger.error("Old path does not exist", path=str(old_dir))
        return False

    # Check if new path already exists
    if new_dir.exists():
        logger.warning(
            "New path already exists, skipping to avoid overwrite",
            path=str(new_dir),
        )
        return False

    # Create new directory structure
    if not dry_run:
        new_dir.mkdir(parents=True, exist_ok=True)

    # Determine migration strategy and execute
    if entry.flat_structure:
        _migrate_flat(old_dir, new_dir, entry, dry_run=dry_run)
    elif entry.sidehustle_layout:
        _migrate_sidehustle(old_dir, new_dir, entry, dry_run=dry_run)
    elif entry.weekly_report_layout:
        _migrate_weekly_report(old_dir, new_dir, entry, dry_run=dry_run)
    else:
        _migrate_standard(old_dir, new_dir, entry, dry_run=dry_run)

    # Ensure all standard sub-directories exist
    for subdir in NEW_SUBDIRS:
        subdir_path = new_dir / subdir
        if not subdir_path.exists():
            logger.info(f"  Create missing sub-dir: {subdir}")
            if not dry_run:
                subdir_path.mkdir(parents=True, exist_ok=True)

    # Convert article-meta.json -> meta.yaml
    old_meta_path = old_dir / "article-meta.json"
    meta_path = new_dir / "meta.yaml"

    meta = convert_meta(
        old_meta_path if old_meta_path.exists() else None,
        entry.new_category,
        entry.old_path,
    )

    logger.info(
        f"  {prefix}Write meta.yaml",
        status=meta["status"],
        category=meta["category"],
    )
    if not dry_run:
        with meta_path.open("w", encoding="utf-8") as f:
            safe_dump(
                meta,
                f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )

    logger.info(f"{prefix}Done", article=entry.new_path)
    return True


# ---------------------------------------------------------------------------
# Batch migration
# ---------------------------------------------------------------------------


def migrate_all(*, dry_run: bool) -> None:
    """Migrate all articles defined in MIGRATION_MAP.

    Parameters
    ----------
    dry_run : bool
        If True, only preview changes without writing.
    """
    prefix = "[DRY-RUN] " if dry_run else ""
    logger.info(
        f"{prefix}Starting migration of {len(MIGRATION_MAP)} articles",
    )

    success = 0
    skipped = 0
    failed = 0

    for entry in MIGRATION_MAP:
        if entry.skip:
            skipped += 1
            logger.info("SKIP", path=entry.old_path, reason=entry.notes)
            continue

        try:
            ok = migrate_article(entry, dry_run=dry_run)
            if ok:
                success += 1
            else:
                failed += 1
        except Exception:
            logger.error(
                "Migration failed with exception",
                article=entry.old_path,
                exc_info=True,
            )
            failed += 1

    logger.info(
        f"{prefix}Migration complete",
        success=success,
        skipped=skipped,
        failed=failed,
        total=len(MIGRATION_MAP),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _find_entry_by_path(article_path: str) -> MigrationEntry | None:
    """Find a MigrationEntry matching the given old_path.

    Parameters
    ----------
    article_path : str
        The old article path (relative to articles/).

    Returns
    -------
    MigrationEntry | None
        The matching entry, or None if not found.
    """
    # Normalize: strip trailing slashes
    normalized = article_path.rstrip("/")
    for entry in MIGRATION_MAP:
        if entry.old_path == normalized:
            return entry
    return None


def main() -> None:
    """CLI entry point for article migration."""
    parser = argparse.ArgumentParser(
        description="Migrate articles from old folder structure to unified structure.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  # Preview all migrations
  uv run python scripts/migrate_articles.py --dry-run

  # Migrate all articles
  uv run python scripts/migrate_articles.py

  # Migrate a single article
  uv run python scripts/migrate_articles.py --article economic_indicators_001_private-credit-bank-shadow-banking-risk

  # Migrate a nested article
  uv run python scripts/migrate_articles.py --article asset_management/fund_selection_age_based
""",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview migration without making changes",
    )
    parser.add_argument(
        "--article",
        type=str,
        default=None,
        help="Migrate a single article by its old path (relative to articles/)",
    )

    args = parser.parse_args()

    if args.article:
        entry = _find_entry_by_path(args.article)
        if entry is None:
            logger.error(
                "Article not found in migration map",
                article=args.article,
                available=[e.old_path for e in MIGRATION_MAP if not e.skip],
            )
            sys.exit(1)
        ok = migrate_article(entry, dry_run=args.dry_run)
        sys.exit(0 if ok else 1)
    else:
        migrate_all(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
