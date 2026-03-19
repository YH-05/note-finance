"""PaperMetadata -> graph-queue JSON マッパー.

note-finance の graph-queue スキーマ v2.2 に適合した形式で出力する。
Source, Author, AUTHORED_BY, CITES, COAUTHORED_WITH を生成する。
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from itertools import combinations
from typing import Any

import structlog

from pdf_pipeline.services.id_generator import generate_author_id, generate_source_id

logger = structlog.get_logger(__name__)

MAX_COAUTHOR_COUNT = 50


def map_academic_papers(data: dict[str, Any]) -> dict[str, Any]:
    """Map academic papers to note-finance graph-queue format.

    Input: ``{"papers": [...], "existing_source_ids": [...]}``

    Parameters
    ----------
    data : dict[str, Any]
        ``papers`` (list of paper dicts) and ``existing_source_ids``
        (list of known source IDs for CITES filtering).

    Returns
    -------
    dict[str, Any]
        Complete graph-queue dict.
    """
    papers: list[dict[str, Any]] = data.get("papers", [])
    existing_source_ids: list[str] = data.get("existing_source_ids", [])
    existing_set = set(existing_source_ids)

    queue = _empty_academic_queue(data.get("_input_path", ""))

    if not papers:
        logger.warning("No papers found in academic input")
        return queue

    seen_authors: dict[str, str] = {}
    generated_source_ids: set[str] = set()
    coauthor_pairs: dict[tuple[str, str], _CoauthorInfo] = {}
    ref_source_id_cache: dict[str, str] = {}

    for paper in papers:
        arxiv_id = paper.get("arxiv_id", "")
        title = paper.get("title", "")
        published = paper.get("published", "")

        if not arxiv_id:
            logger.warning("Paper missing arxiv_id, skipping", title=title)
            continue

        url = f"https://arxiv.org/abs/{arxiv_id}"
        source_id = generate_source_id(url)
        generated_source_ids.add(source_id)

        queue["sources"].append(
            {
                "source_id": source_id,
                "url": url,
                "title": title,
                "published": published,
                "source_type": "paper",
                "authority_level": "academic",
                "publisher": "arXiv",
                "arxiv_id": arxiv_id,
            }
        )

        authors_data: list[dict[str, Any]] = paper.get("authors", [])
        paper_author_ids: list[str] = []

        for author_data in authors_data:
            name = author_data.get("name", "")
            if not name:
                continue

            author_key = f"{name}:academic"
            if author_key not in seen_authors:
                author_id = generate_author_id(name, "academic")
                seen_authors[author_key] = author_id
                queue["authors"].append(
                    {
                        "author_id": author_id,
                        "name": name,
                        "author_type": "academic",
                    }
                )
            else:
                author_id = seen_authors[author_key]

            paper_author_ids.append(author_id)

            queue["relations"]["authored_by"].append(
                {"from_id": source_id, "to_id": author_id}
            )

        references: list[dict[str, Any]] = paper.get("references", [])
        for ref in references:
            ref_arxiv_id = ref.get("arxiv_id")
            if not ref_arxiv_id:
                continue

            if ref_arxiv_id in ref_source_id_cache:
                ref_source_id = ref_source_id_cache[ref_arxiv_id]
            else:
                ref_url = f"https://arxiv.org/abs/{ref_arxiv_id}"
                ref_source_id = generate_source_id(ref_url)
                ref_source_id_cache[ref_arxiv_id] = ref_source_id

            if ref_source_id in existing_set or ref_source_id in generated_source_ids:
                queue["relations"]["cites"].append(
                    {"from_id": source_id, "to_id": ref_source_id}
                )

        unique_author_ids = list(dict.fromkeys(paper_author_ids))
        if len(unique_author_ids) > MAX_COAUTHOR_COUNT:
            logger.warning(
                "Skipping COAUTHORED_WITH for paper with too many authors",
                arxiv_id=arxiv_id,
                author_count=len(unique_author_ids),
            )
            unique_author_ids = []
        for a_id, b_id in combinations(unique_author_ids, 2):
            pair_key = (min(a_id, b_id), max(a_id, b_id))
            if pair_key not in coauthor_pairs:
                coauthor_pairs[pair_key] = _CoauthorInfo(
                    paper_count=1, first_collaboration=published
                )
            else:
                coauthor_pairs[pair_key].paper_count += 1

    for (a_id, b_id), info in coauthor_pairs.items():
        queue["relations"]["coauthored_with"].append(
            {
                "from_id": a_id,
                "to_id": b_id,
                "paper_count": info.paper_count,
                "first_collaboration": info.first_collaboration,
            }
        )

    logger.info(
        "Mapped academic papers",
        paper_count=len(papers),
        source_count=len(queue["sources"]),
        author_count=len(queue["authors"]),
        authored_by_count=len(queue["relations"]["authored_by"]),
        cites_count=len(queue["relations"]["cites"]),
        coauthored_with_count=len(queue["relations"]["coauthored_with"]),
    )
    return queue


class _CoauthorInfo:
    __slots__ = ("first_collaboration", "paper_count")

    def __init__(self, paper_count: int, first_collaboration: str) -> None:
        self.paper_count = paper_count
        self.first_collaboration = first_collaboration


def _empty_academic_queue(input_path: str) -> dict[str, Any]:
    """note-finance の graph-queue スキーマ v2.2 に準拠した空構造を生成する."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    rand8 = secrets.token_hex(4)
    queue_id = f"gq-{timestamp}-{rand8}"
    now = datetime.now(timezone.utc)

    return {
        "schema_version": "2.2",
        "queue_id": queue_id,
        "created_at": now.isoformat(),
        "command_source": "academic-fetch",
        "input_path": input_path,
        "sources": [],
        "chunks": [],
        "entities": [],
        "claims": [],
        "facts": [],
        "topics": [],
        "authors": [],
        "financial_datapoints": [],
        "fiscal_periods": [],
        "insights": [],
        "stances": [],
        "questions": [],
        "relations": {
            "tagged": [],
            "makes_claim": [],
            "states_fact": [],
            "about": [],
            "extracted_from": [],
            "has_datapoint": [],
            "for_period": [],
            "supported_by": [],
            "authored_by": [],
            "holds_stance": [],
            "on_entity": [],
            "based_on": [],
            "cites": [],
            "coauthored_with": [],
        },
    }


__all__ = ["map_academic_papers"]
