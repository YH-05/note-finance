"""tests/scripts/test_mappers_v4_schema.py — Wave6 mapper v4.0 スキーマ対応テスト。

web_research / ai_research / wealth_scrape マッパーが以下の新スキーマに
準拠していることを検証する:

1. 各 mapper が個別ラベル形式（neo4j_label フィールドあり）のエンティティを生成する
2. ABOUT/MENTIONS リレーションを出力しない
3. entity_key フィールドを生成しない

Issue #311 の受け入れ条件に対応。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator
from mappers.ai_research import AiResearchMapper
from mappers.base import BaseMapper
from mappers.wealth_scrape import WealthScrapeMapper
from mappers.web_research import WebResearchMapper

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_caches() -> Generator[None, None, None]:
    """各テスト前にキャッシュをクリアする。"""
    from ontology_loader import invalidate_cache

    BaseMapper._yaml_cache = None
    invalidate_cache()
    yield
    BaseMapper._yaml_cache = None
    invalidate_cache()


def _make_web_research_input() -> dict[str, Any]:
    """web-research コマンドの最小入力データを返す。"""
    url = "https://example.com/article"
    return {
        "sources": [
            {
                "url": url,
                "title": "Test Article",
                "source_type": "web",
                "authority_level": "media",
                "publisher": "ExampleMedia",
                "data_source": "tavily",
            }
        ],
        "facts": [
            {
                "content": "Apple revenue hit record",
                "source_url": url,
                "confidence": 0.9,
                "fact_type": "financial_metric",
                "about_entities": [{"name": "Apple", "entity_type": "company"}],
            }
        ],
        "claims": [
            {
                "content": "Apple is bullish",
                "source_url": url,
                "claim_type": "analyst_opinion",
                "sentiment": "positive",
                "about_entities": [{"name": "Apple", "entity_type": "company"}],
            }
        ],
        "topics": [{"name": "AI", "category": "technology"}],
        "causal_links": [],
        "session_id": "test-session-web",
    }


def _make_ai_research_input() -> dict[str, Any]:
    """ai-research-collect コマンドの最小入力データを返す。"""
    return {
        "companies": [
            {
                "company_name": "OpenAI",
                "ticker": "",
                "url": "https://openai.com",
                "title": "OpenAI official site",
                "published": "2026-01-01T00:00:00+00:00",
            },
            {
                "company_name": "Anthropic",
                "ticker": "",
                "url": "https://anthropic.com",
                "title": "Anthropic official site",
                "published": "2026-01-01T00:00:00+00:00",
            },
        ],
        "session_id": "ai-research-test",
    }


def _make_wealth_scrape_backfill_input() -> dict[str, Any]:
    """wealth-scrape backfill モードの最小入力データを返す。"""
    return {
        "mode": "backfill",
        "themes": {
            "data_driven_investing": {
                "name_en": "Data-Driven Investing",
                "keywords_en": ["quant", "algorithm"],
                "articles": [
                    {
                        "url": "https://example.com/article1",
                        "title": "Quant Strategies",
                        "summary": "...",
                        "published": "2026-01-01",
                        "domain": "example.com",
                    }
                ],
            }
        },
        "session_id": "wealth-test",
    }


def _make_wealth_scrape_incremental_input() -> dict[str, Any]:
    """wealth-scrape incremental モードの最小入力データを返す。"""
    return {
        "mode": "incremental",
        "themes": {
            "data_driven_investing": {
                "name_en": "Data-Driven Investing",
                "keywords_en": ["quant", "algorithm"],
                "articles": [
                    {
                        "url": "https://example.com/article2",
                        "title": "Quant Strategies Part 2",
                        "summary": "Quantitative methods are effective.",
                        "published": "2026-01-02",
                        "domain": "example.com",
                    }
                ],
            }
        },
        "session_id": "wealth-test-incr",
    }


# ---------------------------------------------------------------------------
# Tests: WebResearchMapper — v4.0 スキーマ準拠
# ---------------------------------------------------------------------------


class TestWebResearchMapperV4Schema:
    """WebResearchMapper が v4.0 スキーマに準拠していることを検証する。"""

    def test_正常系_factエンティティにneo4j_labelがある(self) -> None:
        mapper = WebResearchMapper()
        result = mapper.map(_make_web_research_input())
        entities = result["entities"]
        assert len(entities) > 0, "entities は1件以上必要"
        for entity in entities:
            assert "neo4j_label" in entity, f"entity に neo4j_label がない: {entity}"
            assert entity["neo4j_label"], "neo4j_label は空であってはならない"

    def test_正常系_factエンティティにentity_keyがない(self) -> None:
        mapper = WebResearchMapper()
        result = mapper.map(_make_web_research_input())
        for entity in result["entities"]:
            assert "entity_key" not in entity, (
                f"entity_key は v4.0 で廃止されているが残存: {entity}"
            )

    def test_正常系_companyエンティティのneo4j_labelはCompany(self) -> None:
        mapper = WebResearchMapper()
        result = mapper.map(_make_web_research_input())
        company_entities = [
            e for e in result["entities"] if e["entity_type"] == "company"
        ]
        assert len(company_entities) > 0
        for entity in company_entities:
            assert entity["neo4j_label"] == "Company", (
                f"company の neo4j_label は Company であるべき: {entity['neo4j_label']}"
            )

    def test_正常系_factエンティティリレーションがRELATES_TO(self) -> None:
        mapper = WebResearchMapper()
        result = mapper.map(_make_web_research_input())
        fact_entity_rels = result["relations"].get("fact_entity", [])
        assert len(fact_entity_rels) > 0, "fact_entity リレーションは1件以上必要"
        for rel in fact_entity_rels:
            assert rel["type"] == "RELATES_TO", (
                f"fact_entity リレーションは RELATES_TO であるべき: {rel['type']}"
            )

    def test_正常系_claimエンティティリレーションがRELATES_TO(self) -> None:
        mapper = WebResearchMapper()
        result = mapper.map(_make_web_research_input())
        claim_entity_rels = result["relations"].get("claim_entity", [])
        assert len(claim_entity_rels) > 0, "claim_entity リレーションは1件以上必要"
        for rel in claim_entity_rels:
            assert rel["type"] == "RELATES_TO", (
                f"claim_entity リレーションは RELATES_TO であるべき: {rel['type']}"
            )

    def test_正常系_ABOUTリレーションを出力しない(self) -> None:
        mapper = WebResearchMapper()
        result = mapper.map(_make_web_research_input())
        all_rels: list[dict[str, str]] = []
        for rel_list in result["relations"].values():
            if isinstance(rel_list, list):
                all_rels.extend(rel_list)
        about_rels = [r for r in all_rels if r.get("type") == "ABOUT"]
        assert about_rels == [], f"ABOUT リレーションが存在してはならない: {about_rels}"

    def test_正常系_MENTIONSリレーションを出力しない(self) -> None:
        mapper = WebResearchMapper()
        result = mapper.map(_make_web_research_input())
        all_rels: list[dict[str, str]] = []
        for rel_list in result["relations"].values():
            if isinstance(rel_list, list):
                all_rels.extend(rel_list)
        mentions_rels = [r for r in all_rels if r.get("type") == "MENTIONS"]
        assert mentions_rels == [], (
            f"MENTIONS リレーションが存在してはならない: {mentions_rels}"
        )

    def test_正常系_同一エンティティが複数回参照されても重複しない(self) -> None:
        """同一エンティティが facts と claims の両方に現れても1件のみ生成される。"""
        mapper = WebResearchMapper()
        result = mapper.map(_make_web_research_input())
        entities = result["entities"]
        names = [e["name"] for e in entities]
        assert len(names) == len(set(names)), f"エンティティ名に重複あり: {names}"


# ---------------------------------------------------------------------------
# Tests: AiResearchMapper — v4.0 スキーマ準拠
# ---------------------------------------------------------------------------


class TestAiResearchMapperV4Schema:
    """AiResearchMapper が v4.0 スキーマに準拠していることを検証する。"""

    def test_正常系_エンティティにneo4j_labelがある(self) -> None:
        mapper = AiResearchMapper()
        result = mapper.map(_make_ai_research_input())
        entities = result["entities"]
        assert len(entities) == 2, f"企業2社が期待される: {len(entities)}"
        for entity in entities:
            assert "neo4j_label" in entity, f"entity に neo4j_label がない: {entity}"
            assert entity["neo4j_label"] == "Company", (
                f"company の neo4j_label は Company であるべき: {entity['neo4j_label']}"
            )

    def test_正常系_エンティティにentity_keyがない(self) -> None:
        mapper = AiResearchMapper()
        result = mapper.map(_make_ai_research_input())
        for entity in result["entities"]:
            assert "entity_key" not in entity, (
                f"entity_key は v4.0 で廃止されているが残存: {entity}"
            )

    def test_正常系_重複した会社名はスキップされる(self) -> None:
        """同一会社名が2回現れても1エンティティのみ生成される。"""
        data = _make_ai_research_input()
        data["companies"].append(
            {
                "company_name": "OpenAI",
                "ticker": "",
                "url": "https://openai.com/dup",
                "title": "OpenAI dup",
                "published": "2026-01-02T00:00:00+00:00",
            }
        )
        mapper = AiResearchMapper()
        result = mapper.map(data)
        names = [e["name"] for e in result["entities"]]
        assert names.count("OpenAI") == 1, f"OpenAI が重複している: {names}"


# ---------------------------------------------------------------------------
# Tests: WealthScrapeMapper — v4.0 スキーマ準拠
# ---------------------------------------------------------------------------


class TestWealthScrapeMapperV4Schema:
    """WealthScrapeMapper が v4.0 スキーマに準拠していることを検証する。"""

    def test_正常系_backfillモードのエンティティにneo4j_labelがある(self) -> None:
        mapper = WealthScrapeMapper()
        result = mapper.map(_make_wealth_scrape_backfill_input())
        entities = result["entities"]
        assert len(entities) > 0, "backfill モードでは domain entity が生成される"
        for entity in entities:
            assert "neo4j_label" in entity, f"entity に neo4j_label がない: {entity}"
            # domain → concept consolidation → Concept ラベル
            assert entity["neo4j_label"] == "Concept", (
                f"domain entity の neo4j_label は Concept であるべき: {entity['neo4j_label']}"
            )

    def test_正常系_backfillモードのエンティティにentity_keyがない(self) -> None:
        mapper = WealthScrapeMapper()
        result = mapper.map(_make_wealth_scrape_backfill_input())
        for entity in result["entities"]:
            assert "entity_key" not in entity, (
                f"entity_key は v4.0 で廃止されているが残存: {entity}"
            )

    def test_正常系_incrementalモードにエンティティはない(self) -> None:
        """incremental モードは domain entity を生成しない（Claim のみ）。"""
        mapper = WealthScrapeMapper()
        result = mapper.map(_make_wealth_scrape_incremental_input())
        entities = result["entities"]
        assert entities == [], f"incremental モードでは entities は空のはず: {entities}"

    def test_正常系_incrementalモードにABOUTリレーションはない(self) -> None:
        mapper = WealthScrapeMapper()
        result = mapper.map(_make_wealth_scrape_incremental_input())
        all_rels: list[dict[str, str]] = []
        for rel_list in result["relations"].values():
            if isinstance(rel_list, list):
                all_rels.extend(rel_list)
        about_rels = [r for r in all_rels if r.get("type") == "ABOUT"]
        assert about_rels == [], f"ABOUT リレーションが存在してはならない: {about_rels}"

    def test_正常系_backfillモードにABOUTリレーションはない(self) -> None:
        mapper = WealthScrapeMapper()
        result = mapper.map(_make_wealth_scrape_backfill_input())
        all_rels: list[dict[str, str]] = []
        for rel_list in result["relations"].values():
            if isinstance(rel_list, list):
                all_rels.extend(rel_list)
        about_rels = [r for r in all_rels if r.get("type") == "ABOUT"]
        assert about_rels == [], f"ABOUT リレーションが存在してはならない: {about_rels}"
