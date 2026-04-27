#!/usr/bin/env python3
"""Mine local articles/ directory and emit topic-suggest Phase 0 input JSON.

Usage:
    uv run python scripts/mine_local_articles.py [--out PATH] [--stale-days N]

Output JSON:
    {
      "generated_at": ...,
      "total": int,
      "by_category": {category: count},
      "by_status": {status: count},
      "by_audience": {audience: count},
      "recent": [{article_id, category, topic, published_at, ...}],
      "stale_categories": [{category, last_updated_days_ago, ...}],
      "all_topics": [{article_id, category, topic, status, ...}],
      "all_symbols": [symbol, ...],
      "draft_keywords": {article_id: [keyword, ...]}
    }
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ARTICLES_ROOT = Path(__file__).resolve().parent.parent / "articles"
DEFAULT_OUT = (
    Path(__file__).resolve().parent.parent / ".tmp" / "topic-suggest" / "local_articles_mining.json"
)

SYMBOL_FIELDS = ("symbols", "tickers", "fred_series", "indices", "etfs")

KEYWORD_PATTERN = re.compile(r"[A-Z]{2,5}|[一-龥ぁ-んァ-ヴー]{3,}")


def parse_date(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError:
            try:
                dt = datetime.strptime(value, "%Y-%m-%d")
                return dt.replace(tzinfo=UTC)
            except ValueError:
                return None
    return None


def collect_symbols(meta: dict) -> list[str]:
    symbols: set[str] = set()
    for field in SYMBOL_FIELDS:
        value = meta.get(field)
        if isinstance(value, list):
            symbols.update(str(v) for v in value if v)
        elif isinstance(value, str) and value.strip():
            symbols.add(value.strip())
    return sorted(symbols)


def extract_keywords(text: str, top_n: int = 10) -> list[str]:
    if not text:
        return []
    tokens = KEYWORD_PATTERN.findall(text)
    counter = Counter(t for t in tokens if len(t) >= 3)
    return [token for token, _ in counter.most_common(top_n)]


def load_article(meta_path: Path) -> dict | None:
    try:
        with meta_path.open("r", encoding="utf-8") as f:
            meta = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        logger.warning("Failed to parse %s: %s", meta_path, e)
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
        "topic": meta.get("topic") or meta.get("title") or "",
        "type": meta.get("type"),
        "status": meta.get("status", "unknown"),
        "target_audience": meta.get("target_audience"),
        "target_wordcount": meta.get("target_wordcount"),
        "created_at": str(meta.get("created_at")) if meta.get("created_at") else None,
        "updated_at": str(meta.get("updated_at")) if meta.get("updated_at") else None,
        "published_at": str(meta.get("published_at")) if meta.get("published_at") else None,
        "draft_url": meta.get("draft_url"),
        "symbols": collect_symbols(meta),
        "keywords": extract_keywords(draft_text),
        "has_draft": draft_path.exists(),
        "draft_chars": len(draft_text),
        "meta_path": str(meta_path.relative_to(meta_path.parents[3])),
    }


def mine_articles(stale_days: int = 90) -> dict:
    if not ARTICLES_ROOT.exists():
        raise FileNotFoundError(f"articles/ not found: {ARTICLES_ROOT}")

    now = datetime.now(UTC)
    stale_threshold = now - timedelta(days=stale_days)
    recent_threshold = now - timedelta(days=30)

    articles: list[dict] = []
    for meta_path in ARTICLES_ROOT.glob("*/*/meta.yaml"):
        if "templates" in meta_path.parts:
            continue
        article = load_article(meta_path)
        if article:
            articles.append(article)

    by_category: Counter[str] = Counter()
    by_status: Counter[str] = Counter()
    by_audience: Counter[str] = Counter()
    category_last_update: dict[str, datetime] = {}
    all_symbols: Counter[str] = Counter()
    recent: list[dict] = []
    draft_keywords: dict[str, list[str]] = {}

    for art in articles:
        by_category[art["category"]] += 1
        by_status[art["status"]] += 1
        if art["target_audience"]:
            by_audience[art["target_audience"]] += 1

        for sym in art["symbols"]:
            all_symbols[sym] += 1

        if art["keywords"]:
            draft_keywords[art["article_id"]] = art["keywords"]

        published = parse_date(art["published_at"]) or parse_date(art["updated_at"]) or parse_date(art["created_at"])
        if published:
            cat = art["category"]
            if cat not in category_last_update or category_last_update[cat] < published:
                category_last_update[cat] = published
            if published >= recent_threshold:
                recent.append({**art, "published_dt": published.isoformat()})

    expected_categories = {"macro_economy", "stock_analysis", "asset_management", "investment_education", "earnings", "market_report"}
    stale_categories = []
    for cat in expected_categories:
        last = category_last_update.get(cat)
        if last is None:
            stale_categories.append({"category": cat, "last_updated": None, "days_ago": None, "article_count": by_category.get(cat, 0)})
        elif last < stale_threshold:
            stale_categories.append(
                {
                    "category": cat,
                    "last_updated": last.isoformat(),
                    "days_ago": (now - last).days,
                    "article_count": by_category.get(cat, 0),
                }
            )

    recent.sort(key=lambda a: a["published_dt"], reverse=True)

    return {
        "generated_at": now.isoformat(),
        "total": len(articles),
        "by_category": dict(by_category),
        "by_status": dict(by_status),
        "by_audience": dict(by_audience),
        "category_last_update": {k: v.isoformat() for k, v in category_last_update.items()},
        "stale_categories": stale_categories,
        "recent_count": len(recent),
        "recent": recent[:20],
        "all_topics": [
            {
                "article_id": a["article_id"],
                "category": a["category"],
                "topic": a["topic"],
                "status": a["status"],
                "symbols": a["symbols"],
            }
            for a in articles
        ],
        "top_symbols": all_symbols.most_common(30),
        "draft_keywords": draft_keywords,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Mine local articles for topic-suggest Phase 0")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output JSON path")
    parser.add_argument("--stale-days", type=int, default=90, help="Stale threshold in days")
    args = parser.parse_args()

    logger.info("Mining articles from %s", ARTICLES_ROOT)
    result = mine_articles(stale_days=args.stale_days)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    logger.info(
        "Mined %d articles | categories=%d | recent=%d | stale_categories=%d -> %s",
        result["total"],
        len(result["by_category"]),
        result["recent_count"],
        len(result["stale_categories"]),
        args.out,
    )


if __name__ == "__main__":
    main()
