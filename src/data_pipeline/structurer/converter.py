"""CollectedItem → StructuredOutput 変換器.

2段構成:
1. メタデータ変換（決定論的）: CollectedItem の url/title/source_id → SourceEntry
2. テキスト構造化（LLMまたはルールベース）: raw_text → Facts/Claims/Topics/Entities

LLM抽出を使わない場合でも、メタデータ変換だけで最低限の StructuredOutput を生成できる。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from data_pipeline.structurer.models import (
    AboutEntity,
    ClaimEntry,
    FactEntry,
    SourceEntry,
    StructuredOutput,
    TopicEntry,
)

if TYPE_CHECKING:
    from data_pipeline.collectors.base import CollectedItem

# authority_level マッピング: source_registry の数値 → emit_graph_queue の文字列
_AUTHORITY_MAP = {
    5: "official",
    4: "analyst",
    3: "media",
    2: "blog",
    1: "social",
}


_AuthorityLevel = Literal["official", "analyst", "media", "blog", "social", "academic"]


def _map_authority(level: int | None) -> _AuthorityLevel:
    """数値 authority_level を文字列に変換する."""
    if level is None:
        return "media"
    return _AUTHORITY_MAP.get(level, "media")  # type: ignore[return-value]


def _infer_source_type(item: CollectedItem) -> str:
    """収集方法からソースタイプを推定する."""
    method_to_type = {
        "rss": "rss",
        "scraping": "web",
        "api": "web",
        "web_search": "web",
        "pdf": "pdf",
        "manual": "web",
    }
    return method_to_type.get(item.collection_method, "web")


# ---------------------------------------------------------------------------
# メタデータ変換（決定論的）
# ---------------------------------------------------------------------------


def build_source_entry(
    item: CollectedItem,
    authority_level: int | None = None,
    publisher: str | None = None,
) -> SourceEntry:
    """CollectedItem から SourceEntry を生成する（決定論的）."""
    return SourceEntry(
        url=item.url,
        title=item.title,
        source_type=_infer_source_type(item),
        authority_level=_map_authority(authority_level),
        publisher=publisher or item.metadata.get("feed_title", ""),
        data_source=item.collection_method,
        published_at=item.published_at.isoformat() if item.published_at else "",
    )


def build_minimal_output(
    items: list[CollectedItem],
    authority_level: int | None = None,
) -> StructuredOutput:
    """CollectedItem リストから最低限の StructuredOutput を生成する.

    LLM抽出なし。各アイテムを1 Source + 1 Fact（raw_text全文）に変換する。
    テキストが空のアイテムはスキップする。

    Parameters
    ----------
    items : list[CollectedItem]
        変換元のアイテムリスト。
    authority_level : int | None
        全アイテム共通の authority_level (1-5)。

    Returns
    -------
    StructuredOutput
        最低限の構造化出力（Source + Fact のみ）。
    """
    sources: list[SourceEntry] = []
    facts: list[FactEntry] = []
    seen_urls: set[str] = set()

    for item in items:
        if not item.raw_text.strip():
            continue

        # Source（重複排除）
        if item.url not in seen_urls:
            sources.append(build_source_entry(item, authority_level))
            seen_urls.add(item.url)

        # raw_text 全文を1つの Fact として登録
        facts.append(
            FactEntry(
                content=item.raw_text,
                source_url=item.url,
                confidence=0.9,
                fact_type="general",
            ),
        )

    return StructuredOutput(sources=sources, facts=facts)


def build_from_extracted(
    items: list[CollectedItem],
    extractions: list[dict],
    authority_level: int | None = None,
) -> StructuredOutput:
    """LLM抽出結果を含む StructuredOutput を生成する.

    Parameters
    ----------
    items : list[CollectedItem]
        元のアイテムリスト。
    extractions : list[dict]
        各アイテムに対するLLM抽出結果。各dictのキー:
        - facts: list[dict] (content, fact_type, confidence, about_entities)
        - claims: list[dict] (content, claim_type, sentiment, about_entities)
        - topics: list[dict] (name, category)
    authority_level : int | None
        全アイテム共通の authority_level。

    Returns
    -------
    StructuredOutput
        LLM抽出結果を含む構造化出力。
    """
    sources: list[SourceEntry] = []
    facts: list[FactEntry] = []
    claims: list[ClaimEntry] = []
    topics: list[TopicEntry] = []
    seen_urls: set[str] = set()
    seen_topics: set[str] = set()

    for item, extraction in zip(items, extractions, strict=False):
        # Source
        if item.url not in seen_urls:
            sources.append(build_source_entry(item, authority_level))
            seen_urls.add(item.url)

        # Facts
        for f in extraction.get("facts", []):
            about = [
                AboutEntity(name=e["name"], entity_type=e.get("entity_type", ""))
                for e in f.get("about_entities", [])
            ]
            facts.append(
                FactEntry(
                    content=f["content"],
                    source_url=item.url,
                    confidence=f.get("confidence", 0.8),
                    fact_type=f.get("fact_type", "general"),
                    about_entities=about,
                ),
            )

        # Claims
        for c in extraction.get("claims", []):
            about = [
                AboutEntity(name=e["name"], entity_type=e.get("entity_type", ""))
                for e in c.get("about_entities", [])
            ]
            claims.append(
                ClaimEntry(
                    content=c["content"],
                    source_url=item.url,
                    claim_type=c.get("claim_type", "analyst_opinion"),
                    sentiment=c.get("sentiment", "neutral"),
                    about_entities=about,
                ),
            )

        # Topics
        for t in extraction.get("topics", []):
            topic_key = t["name"].lower()
            if topic_key not in seen_topics:
                topics.append(
                    TopicEntry(name=t["name"], category=t.get("category", "")),
                )
                seen_topics.add(topic_key)

    return StructuredOutput(
        sources=sources,
        facts=facts,
        claims=claims,
        topics=topics,
    )
