#!/usr/bin/env python3
"""Emit graph-queue JSON for the user's own note articles (株投資ラボ).

Walks ``articles/{category}/{slug}/{meta.yaml + revised_draft.md}``,
builds an ``own-articles`` input JSON and invokes
``scripts/emit_research_queue.py --command own-articles`` to produce
the graph-queue JSON.

Usage:
    uv run python scripts/emit_own_articles_queue.py [--out PATH] [--dry-run]

Output:
    .tmp/own-articles/input_{ts}.json — own-articles mapper input
    .tmp/graph-queue/own-articles/gq-*.json — graph-queue ready for /save-to-research-graph
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_ROOT = ROOT / "articles"
TMP_DIR = ROOT / ".tmp" / "own-articles"

SYMBOL_FIELDS = ("symbols", "tickers", "fred_series", "indices", "etfs")
KEYWORD_PATTERN = re.compile(r"[A-Z]{2,5}|[一-龥ぁ-んァ-ヴー]{3,}")


def collect_symbols(meta: dict) -> list[str]:
    out: set[str] = set()
    for field in SYMBOL_FIELDS:
        v = meta.get(field)
        if isinstance(v, list):
            out.update(str(s) for s in v if s)
        elif isinstance(v, str) and v.strip():
            out.add(v.strip())
    return sorted(out)


def extract_keywords(text: str, top_n: int = 10) -> list[str]:
    if not text:
        return []
    counter = Counter(t for t in KEYWORD_PATTERN.findall(text) if len(t) >= 3)
    return [t for t, _ in counter.most_common(top_n)]


def to_iso(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()
    return str(value)


def stringify(value: Any) -> str:
    """Flatten dict/list values into a primitive string for Neo4j safety."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if "main" in value:
            return str(value["main"])
        if "title" in value:
            return str(value["title"])
        return " | ".join(f"{k}: {v}" for k, v in value.items())
    if isinstance(value, list):
        return " | ".join(stringify(v) for v in value)
    return str(value)


def load_article(meta_path: Path) -> dict | None:
    try:
        with meta_path.open("r", encoding="utf-8") as f:
            meta = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        logger.warning("Skipping %s: YAML parse error: %s", meta_path, e)
        return None

    article_dir = meta_path.parent
    article_id = meta.get("article_id") or article_dir.name
    category = meta.get("category") or article_dir.parent.name

    draft_candidates = [
        article_dir / "revised_draft.md",
        article_dir / "02_draft" / "revised_draft.md",
        article_dir / "03_published" / "article.md",
        article_dir / "02_draft" / "first_draft.md",
        article_dir / "first_draft.md",
    ]
    draft_path = next((p for p in draft_candidates if p.exists()), None)
    draft_text = draft_path.read_text(encoding="utf-8") if draft_path else ""

    return {
        "article_id": article_id,
        "category": category,
        "topic": stringify(meta.get("topic") or meta.get("title")),
        "title": stringify(meta.get("title") or meta.get("topic")),
        "type": stringify(meta.get("type")),
        "target_audience": stringify(meta.get("target_audience")),
        "target_wordcount": meta.get("target_wordcount") or 0,
        "status": stringify(meta.get("status")) or "unknown",
        "created_at": to_iso(meta.get("created_at")),
        "updated_at": to_iso(meta.get("updated_at")),
        "published_at": to_iso(meta.get("published_at")),
        "draft_url": meta.get("draft_url") or "",
        "symbols": collect_symbols(meta),
        "keywords": extract_keywords(draft_text),
        "draft_chars": len(draft_text),
        "meta_path": str(meta_path.relative_to(ROOT)),
    }


def build_input(stale_days: int = 90) -> dict:
    if not ARTICLES_ROOT.exists():
        raise FileNotFoundError(f"articles/ not found: {ARTICLES_ROOT}")

    now = datetime.now(UTC)
    articles: list[dict] = []
    for meta_path in ARTICLES_ROOT.glob("*/*/meta.yaml"):
        if "templates" in meta_path.parts:
            continue
        art = load_article(meta_path)
        if art:
            articles.append(art)

    return {
        "session_id": f"own-articles-{now.strftime('%Y%m%d%H%M%S')}",
        "generated_at": now.isoformat(),
        "articles": articles,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Emit graph-queue JSON for own note articles"
    )
    parser.add_argument(
        "--out", type=Path, default=None, help="Override input JSON path"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip emit_research_queue.py invocation",
    )
    args = parser.parse_args()

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    input_path = args.out or (TMP_DIR / f"input_{ts}.json")

    payload = build_input()
    with input_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info(
        "Wrote own-articles input JSON: %s (articles=%d)",
        input_path,
        len(payload["articles"]),
    )

    if args.dry_run:
        logger.info("Dry run: skipping emit_research_queue.py")
        return

    cmd = [
        "uv",
        "run",
        "python",
        "scripts/emit_research_queue.py",
        "--command",
        "own-articles",
        "--input",
        str(input_path),
    ]
    logger.info("Invoking: %s", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("emit_research_queue.py failed:\n%s", result.stderr)
        sys.exit(result.returncode)

    queue_dir = ROOT / ".tmp" / "graph-queue" / "own-articles"
    queue_files = sorted(queue_dir.glob("gq-*.json"), reverse=True)
    if not queue_files:
        logger.error("No graph-queue file produced under %s", queue_dir)
        sys.exit(1)

    latest = queue_files[0]
    logger.info("graph-queue JSON ready: %s", latest)
    print(f"\nNext step:\n  /save-to-research-graph {latest}\n")


if __name__ == "__main__":
    main()
