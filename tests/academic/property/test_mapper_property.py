"""academic.mapper のプロパティベーステスト.

Hypothesis を使用して map_academic_papers() の不変条件を検証する。

不変条件
--------
- authored_by.to_id は全て authors.author_id の部分集合
- cites.to_id は全て existing_source_ids union sources.source_id の部分集合
- coauthored_with のペアはユニーク

note-finance 移植版: source_id/author_id キーに適合。
"""

from __future__ import annotations

from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from academic.mapper import map_academic_papers
from pdf_pipeline.services.id_generator import generate_source_id

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

author_name_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
    min_size=1,
    max_size=30,
).filter(lambda s: s.strip() != "")

author_st = st.fixed_dictionaries({"name": author_name_st})

reference_st = st.fixed_dictionaries(
    {
        "title": st.text(min_size=1, max_size=50),
        "arxiv_id": st.one_of(
            st.none(),
            st.from_regex(r"[0-9]{4}\.[0-9]{5}", fullmatch=True),
        ),
        "s2_paper_id": st.none(),
    }
)

paper_st = st.fixed_dictionaries(
    {
        "arxiv_id": st.from_regex(r"[0-9]{4}\.[0-9]{5}", fullmatch=True),
        "title": st.text(min_size=1, max_size=100),
        "authors": st.lists(author_st, min_size=0, max_size=5),
        "references": st.lists(reference_st, min_size=0, max_size=5),
        "citations": st.just([]),
        "abstract": st.text(max_size=200),
        "s2_paper_id": st.none(),
        "published": st.just("2023-01-15"),
        "updated": st.none(),
    }
)


def _make_existing_source_ids(
    papers: list[dict[str, Any]],
) -> list[str]:
    """テスト用に一部の既知 source_id を生成する."""
    ref_arxiv_ids: list[str] = []
    for paper in papers:
        for ref in paper.get("references", []):
            aid = ref.get("arxiv_id")
            if aid:
                ref_arxiv_ids.append(aid)
    half = len(ref_arxiv_ids) // 2
    return [
        generate_source_id(f"https://arxiv.org/abs/{aid}")
        for aid in ref_arxiv_ids[:half]
    ]


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


class TestMapperProperties:
    """map_academic_papers の不変条件テスト."""

    @given(papers=st.lists(paper_st, min_size=0, max_size=5))
    @settings(max_examples=50, deadline=None)
    def test_プロパティ_authored_byのto_idがauthorsのauthor_idに含まれる(
        self,
        papers: list[dict[str, Any]],
    ) -> None:
        data: dict[str, Any] = {
            "papers": papers,
            "existing_source_ids": _make_existing_source_ids(papers),
        }

        result = map_academic_papers(data)

        author_ids = {a["author_id"] for a in result["authors"]}
        for rel in result["relations"]["authored_by"]:
            assert rel["to_id"] in author_ids

    @given(papers=st.lists(paper_st, min_size=0, max_size=5))
    @settings(max_examples=50, deadline=None)
    def test_プロパティ_authored_byのfrom_idがsourcesのsource_idに含まれる(
        self,
        papers: list[dict[str, Any]],
    ) -> None:
        data: dict[str, Any] = {
            "papers": papers,
            "existing_source_ids": _make_existing_source_ids(papers),
        }

        result = map_academic_papers(data)

        source_ids = {s["source_id"] for s in result["sources"]}
        for rel in result["relations"]["authored_by"]:
            assert rel["from_id"] in source_ids

    @given(papers=st.lists(paper_st, min_size=0, max_size=5))
    @settings(max_examples=50, deadline=None)
    def test_プロパティ_citesのto_idがexisting_source_idsまたはsourcesのsource_idに含まれる(
        self,
        papers: list[dict[str, Any]],
    ) -> None:
        existing = _make_existing_source_ids(papers)
        data: dict[str, Any] = {
            "papers": papers,
            "existing_source_ids": existing,
        }

        result = map_academic_papers(data)

        allowed_ids = {s["source_id"] for s in result["sources"]} | set(existing)
        for rel in result["relations"]["cites"]:
            assert rel["to_id"] in allowed_ids

    @given(papers=st.lists(paper_st, min_size=0, max_size=5))
    @settings(max_examples=50, deadline=None)
    def test_プロパティ_coauthored_withのペアがユニーク(
        self,
        papers: list[dict[str, Any]],
    ) -> None:
        data: dict[str, Any] = {
            "papers": papers,
            "existing_source_ids": [],
        }

        result = map_academic_papers(data)

        pairs = set()
        for rel in result["relations"]["coauthored_with"]:
            pair = (
                min(rel["from_id"], rel["to_id"]),
                max(rel["from_id"], rel["to_id"]),
            )
            assert pair not in pairs, f"Duplicate coauthored_with pair: {pair}"
            pairs.add(pair)

    @given(papers=st.lists(paper_st, min_size=0, max_size=5))
    @settings(max_examples=50, deadline=None)
    def test_プロパティ_coauthored_withのpaper_countが1以上(
        self,
        papers: list[dict[str, Any]],
    ) -> None:
        data: dict[str, Any] = {
            "papers": papers,
            "existing_source_ids": [],
        }

        result = map_academic_papers(data)

        for rel in result["relations"]["coauthored_with"]:
            assert rel["paper_count"] >= 1

    @given(papers=st.lists(paper_st, min_size=0, max_size=5))
    @settings(max_examples=50, deadline=None)
    def test_プロパティ_coauthored_withのノードIDがauthorsに含まれる(
        self,
        papers: list[dict[str, Any]],
    ) -> None:
        data: dict[str, Any] = {
            "papers": papers,
            "existing_source_ids": [],
        }

        result = map_academic_papers(data)

        author_ids = {a["author_id"] for a in result["authors"]}
        for rel in result["relations"]["coauthored_with"]:
            assert rel["from_id"] in author_ids
            assert rel["to_id"] in author_ids
