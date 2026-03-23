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

    ctx = _MappingContext(
        seen_authors={},
        generated_source_ids=set(),
        coauthor_pairs={},
        ref_source_id_cache={},
    )

    for paper in papers:
        _process_paper(paper, queue, existing_set, ctx)

    _finalize_coauthor_relations(queue, ctx.coauthor_pairs)

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


class _MappingContext:
    """map_academic_papers の中間状態を保持するコンテキスト."""

    __slots__ = (
        "coauthor_pairs",
        "generated_source_ids",
        "ref_source_id_cache",
        "seen_authors",
    )

    def __init__(
        self,
        *,
        seen_authors: dict[str, str],
        generated_source_ids: set[str],
        coauthor_pairs: dict[tuple[str, str], _CoauthorInfo],
        ref_source_id_cache: dict[str, str],
    ) -> None:
        self.seen_authors = seen_authors
        self.generated_source_ids = generated_source_ids
        self.coauthor_pairs = coauthor_pairs
        self.ref_source_id_cache = ref_source_id_cache


def _process_paper(
    paper: dict[str, Any],
    queue: dict[str, Any],
    existing_set: set[str],
    ctx: _MappingContext,
) -> None:
    """単一論文を処理し queue と ctx を更新する."""
    arxiv_id = paper.get("arxiv_id", "")
    title = paper.get("title", "")
    published = paper.get("published", "")

    if not arxiv_id:
        logger.warning("Paper missing arxiv_id, skipping", title=title)
        return

    url = f"https://arxiv.org/abs/{arxiv_id}"
    source_id = generate_source_id(url)
    ctx.generated_source_ids.add(source_id)

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

    paper_author_ids = _process_authors(paper, source_id, queue, ctx)
    _process_references(paper, source_id, queue, existing_set, ctx)
    _accumulate_coauthor_pairs(paper_author_ids, published, arxiv_id, ctx)


def _process_authors(
    paper: dict[str, Any],
    source_id: str,
    queue: dict[str, Any],
    ctx: _MappingContext,
) -> list[str]:
    """論文の著者を処理し、author_id リストを返す."""
    authors_data: list[dict[str, Any]] = paper.get("authors", [])
    paper_author_ids: list[str] = []

    for author_data in authors_data:
        name = author_data.get("name", "")
        if not name:
            continue

        author_key = f"{name}:academic"
        if author_key not in ctx.seen_authors:
            author_id = generate_author_id(name, "academic")
            ctx.seen_authors[author_key] = author_id
            queue["authors"].append(
                {"author_id": author_id, "name": name, "author_type": "academic"}
            )
        else:
            author_id = ctx.seen_authors[author_key]

        paper_author_ids.append(author_id)
        queue["relations"]["authored_by"].append(
            {"from_id": source_id, "to_id": author_id}
        )

    return paper_author_ids


def _process_references(
    paper: dict[str, Any],
    source_id: str,
    queue: dict[str, Any],
    existing_set: set[str],
    ctx: _MappingContext,
) -> None:
    """論文の参照文献を処理し CITES リレーションを追加する."""
    references: list[dict[str, Any]] = paper.get("references", [])
    for ref in references:
        ref_arxiv_id = ref.get("arxiv_id")
        if not ref_arxiv_id:
            continue

        if ref_arxiv_id in ctx.ref_source_id_cache:
            ref_source_id = ctx.ref_source_id_cache[ref_arxiv_id]
        else:
            ref_url = f"https://arxiv.org/abs/{ref_arxiv_id}"
            ref_source_id = generate_source_id(ref_url)
            ctx.ref_source_id_cache[ref_arxiv_id] = ref_source_id

        if ref_source_id in existing_set or ref_source_id in ctx.generated_source_ids:
            queue["relations"]["cites"].append(
                {"from_id": source_id, "to_id": ref_source_id}
            )


def _accumulate_coauthor_pairs(
    paper_author_ids: list[str],
    published: str,
    arxiv_id: str,
    ctx: _MappingContext,
) -> None:
    """著者ペアの共著情報を蓄積する."""
    unique_author_ids = list(dict.fromkeys(paper_author_ids))
    if len(unique_author_ids) > MAX_COAUTHOR_COUNT:
        logger.warning(
            "Skipping COAUTHORED_WITH for paper with too many authors",
            arxiv_id=arxiv_id,
            author_count=len(unique_author_ids),
        )
        return
    for a_id, b_id in combinations(unique_author_ids, 2):
        pair_key = (min(a_id, b_id), max(a_id, b_id))
        if pair_key not in ctx.coauthor_pairs:
            ctx.coauthor_pairs[pair_key] = _CoauthorInfo(
                paper_count=1, first_collaboration=published
            )
        else:
            ctx.coauthor_pairs[pair_key].paper_count += 1


def _finalize_coauthor_relations(
    queue: dict[str, Any],
    coauthor_pairs: dict[tuple[str, str], _CoauthorInfo],
) -> None:
    """蓄積した共著ペアを queue のリレーションに追加する."""
    for (a_id, b_id), info in coauthor_pairs.items():
        queue["relations"]["coauthored_with"].append(
            {
                "from_id": a_id,
                "to_id": b_id,
                "paper_count": info.paper_count,
                "first_collaboration": info.first_collaboration,
            }
        )


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
