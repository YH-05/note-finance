"""Tests for scripts/mappers/helpers.py.

generate_source_id / generate_fact_id / generate_entity_id / generate_topic_id
の冪等性、_parse_date_safe / _normalize_entity_type / _normalize_source_type /
_validate_confidence / _make_source / _build_wr_sources / _build_wr_topics /
_build_wr_facts の単体テスト。
"""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import patch

import pytest

from mappers.helpers import (
    _SOURCE_TYPE_NORMALIZATION,
    _build_wr_facts,
    _build_wr_sources,
    _build_wr_topics,
    _make_source,
    _normalize_entity_type,
    _normalize_source_type,
    _parse_date_safe,
    _validate_confidence,
    generate_entity_id,
    generate_fact_id,
    generate_source_id,
    generate_topic_id,
)


# ---------------------------------------------------------------------------
# generate_source_id / generate_fact_id / generate_entity_id / generate_topic_id
# ---------------------------------------------------------------------------


class TestGenerateSourceId:
    def test_正常系_同じURLで同じIDが生成される(self) -> None:
        url = "https://example.com/report.pdf"
        assert generate_source_id(url) == generate_source_id(url)

    def test_正常系_異なるURLで異なるIDが生成される(self) -> None:
        assert generate_source_id("https://a.com") != generate_source_id("https://b.com")

    def test_正常系_返り値は文字列(self) -> None:
        result = generate_source_id("https://example.com")
        assert isinstance(result, str)
        assert len(result) > 0


class TestGenerateFactId:
    def test_正常系_同じコンテンツで同じIDが生成される(self) -> None:
        content = "GDP grew by 3.5% in Q4 2025."
        assert generate_fact_id(content) == generate_fact_id(content)

    def test_正常系_異なるコンテンツで異なるIDが生成される(self) -> None:
        assert generate_fact_id("fact A") != generate_fact_id("fact B")

    def test_正常系_返り値は文字列(self) -> None:
        result = generate_fact_id("some fact")
        assert isinstance(result, str)
        assert len(result) > 0


class TestGenerateEntityId:
    def test_正常系_同じ名前とタイプで同じIDが生成される(self) -> None:
        assert generate_entity_id("Apple", "company") == generate_entity_id("Apple", "company")

    def test_正常系_名前が異なれば異なるIDが生成される(self) -> None:
        assert generate_entity_id("Apple", "company") != generate_entity_id("Google", "company")

    def test_正常系_タイプが異なれば異なるIDが生成される(self) -> None:
        assert generate_entity_id("USD", "currency") != generate_entity_id("USD", "instrument")

    def test_正常系_返り値は文字列(self) -> None:
        result = generate_entity_id("TestEntity", "company")
        assert isinstance(result, str)
        assert len(result) > 0


class TestGenerateTopicId:
    def test_正常系_同じ名前とカテゴリで同じIDが生成される(self) -> None:
        assert generate_topic_id("AI", "technology") == generate_topic_id("AI", "technology")

    def test_正常系_名前が異なれば異なるIDが生成される(self) -> None:
        assert generate_topic_id("AI", "technology") != generate_topic_id("ML", "technology")

    def test_正常系_カテゴリが異なれば異なるIDが生成される(self) -> None:
        assert generate_topic_id("AI", "technology") != generate_topic_id("AI", "macro")

    def test_正常系_返り値は文字列(self) -> None:
        result = generate_topic_id("test", "macro")
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# _parse_date_safe
# ---------------------------------------------------------------------------


class TestParseDateSafe:
    def test_正常系_ISO8601形式でdateオブジェクトが返る(self) -> None:
        result = _parse_date_safe("2025-12-31")
        assert result == date(2025, 12, 31)

    def test_正常系_日時文字列でもdateが返る(self) -> None:
        result = _parse_date_safe("2025-01-15")
        assert isinstance(result, date)
        assert result == date(2025, 1, 15)

    def test_異常系_Noneでdate_minが返る(self) -> None:
        assert _parse_date_safe(None) == date.min

    def test_異常系_空文字でdate_minが返る(self) -> None:
        assert _parse_date_safe("") == date.min

    def test_異常系_不正形式でdate_minが返る(self) -> None:
        assert _parse_date_safe("not-a-date") == date.min

    def test_異常系_スラッシュ区切りでdate_minが返る(self) -> None:
        # fromisoformat はスラッシュ区切りを受け付けないためdate.minが返る
        result = _parse_date_safe("2025/01/15")
        assert result == date.min

    def test_エッジケース_最小日付文字列でdateが返る(self) -> None:
        result = _parse_date_safe("0001-01-01")
        assert isinstance(result, date)


# ---------------------------------------------------------------------------
# _normalize_entity_type
# ---------------------------------------------------------------------------


class TestNormalizeEntityType:
    def test_正常系_大文字をlowercaseに変換する(self) -> None:
        assert _normalize_entity_type("Company") == "company"

    def test_正常系_すでにlowercaseの場合はそのまま返る(self) -> None:
        assert _normalize_entity_type("company") == "company"

    def test_正常系_大文字混在でlowercaseに変換する(self) -> None:
        assert _normalize_entity_type("TECHNOLOGY") == "technology"

    def test_エッジケース_空文字はそのまま返る(self) -> None:
        # 空文字はtruthy判定でfalseのためrawをそのまま返す
        assert _normalize_entity_type("") == ""

    def test_正常系_未知のタイプもlowercaseに変換する(self) -> None:
        assert _normalize_entity_type("UnknownType") == "unknowntype"


# ---------------------------------------------------------------------------
# _normalize_source_type
# ---------------------------------------------------------------------------


class TestNormalizeSourceType:
    def test_正常系_tower_company_analysisがanalysisにマップされる(self) -> None:
        assert _normalize_source_type("tower_company_analysis") == "analysis"

    def test_正常系_company_analysisがanalysisにマップされる(self) -> None:
        assert _normalize_source_type("company_analysis") == "analysis"

    def test_正常系_macro_dataがdataにマップされる(self) -> None:
        assert _normalize_source_type("macro_data") == "data"

    def test_正常系_web_researchがwebにマップされる(self) -> None:
        assert _normalize_source_type("web-research") == "web"

    def test_正常系_annual_reportがcompany_filingにマップされる(self) -> None:
        assert _normalize_source_type("annual_report") == "company_filing"

    def test_正常系_regulatory_filingがcompany_filingにマップされる(self) -> None:
        assert _normalize_source_type("regulatory_filing") == "company_filing"

    def test_正常系_researchがreportにマップされる(self) -> None:
        assert _normalize_source_type("research") == "report"

    def test_正常系_academic_paperがacademicにマップされる(self) -> None:
        assert _normalize_source_type("academic_paper") == "academic"

    def test_正常系_academic_paper_ハイフン形式がacademicにマップされる(self) -> None:
        assert _normalize_source_type("academic-paper") == "academic"

    def test_正常系_未知のタイプはそのまま返る(self) -> None:
        assert _normalize_source_type("unknown_type_xyz") == "unknown_type_xyz"

    def test_正常系_マッピング全エントリが期待する値に変換される(self) -> None:
        canonical_values = {
            "analysis", "data", "web", "company_filing", "report", "academic"
        }
        for raw, canonical in _SOURCE_TYPE_NORMALIZATION.items():
            result = _normalize_source_type(raw)
            assert result in canonical_values, f"{raw!r} -> {result!r} は canonical_values に含まれない"


# ---------------------------------------------------------------------------
# _validate_confidence
# ---------------------------------------------------------------------------


class TestValidateConfidence:
    def test_正常系_0点0はそのまま返る(self) -> None:
        assert _validate_confidence(0.0) == 0.0

    def test_正常系_1点0はそのまま返る(self) -> None:
        assert _validate_confidence(1.0) == 1.0

    def test_正常系_中間値はそのまま返る(self) -> None:
        assert _validate_confidence(0.7) == 0.7

    def test_正常系_整数0はfloat0点0を返す(self) -> None:
        assert _validate_confidence(0) == 0.0

    def test_正常系_整数1はfloat1点0を返す(self) -> None:
        assert _validate_confidence(1) == 1.0

    def test_異常系_Noneはそのまま返す(self) -> None:
        assert _validate_confidence(None) is None

    def test_異常系_文字列はNoneを返す(self) -> None:
        assert _validate_confidence("high") is None  # type: ignore[arg-type]

    def test_エッジケース_1以上の値は1点0にクリッピングされる(self) -> None:
        assert _validate_confidence(1.5) == 1.0

    def test_エッジケース_0未満の値は0点0にクリッピングされる(self) -> None:
        assert _validate_confidence(-0.5) == 0.0

    def test_エッジケース_境界値ちょうどの0点0は有効(self) -> None:
        result = _validate_confidence(0.0)
        assert result is not None
        assert 0.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# _make_source
# ---------------------------------------------------------------------------


class TestMakeSource:
    def test_正常系_必須フィールドのみで作成できる(self) -> None:
        url = "https://example.com/report"
        with patch("mappers.helpers.classify_authority", return_value="media"):
            source = _make_source(url)
        assert source["url"] == url
        assert "source_id" in source
        assert isinstance(source["source_id"], str)
        assert len(source["source_id"]) > 0

    def test_正常系_同じURLで同じsource_idが生成される(self) -> None:
        url = "https://example.com/report"
        with patch("mappers.helpers.classify_authority", return_value="media"):
            s1 = _make_source(url)
            s2 = _make_source(url)
        assert s1["source_id"] == s2["source_id"]

    def test_正常系_タイトルと公開日を指定できる(self) -> None:
        url = "https://example.com/report"
        with patch("mappers.helpers.classify_authority", return_value="media"):
            source = _make_source(url, title="Test Report", published="2025-01-01")
        assert source["title"] == "Test Report"
        assert source["published"] == "2025-01-01"

    def test_正常系_source_typeが正規化される(self) -> None:
        url = "https://example.com/report"
        with patch("mappers.helpers.classify_authority", return_value="official"):
            source = _make_source(url, source_type="annual_report")
        assert source["source_type"] == "company_filing"

    def test_正常系_authority_levelが指定されていない場合はclassify_authorityで設定される(self) -> None:
        url = "https://sec.gov/filing"
        with patch("mappers.helpers.classify_authority", return_value="official") as mock_cls:
            source = _make_source(url)
        mock_cls.assert_called_once()
        assert source["authority_level"] == "official"

    def test_正常系_authority_levelを明示指定した場合はclassify_authorityが呼ばれない(self) -> None:
        url = "https://example.com"
        with patch("mappers.helpers.classify_authority") as mock_cls:
            source = _make_source(url, authority_level="analyst")
        mock_cls.assert_not_called()
        assert source["authority_level"] == "analyst"

    def test_正常系_追加フィールドをkwargsで渡せる(self) -> None:
        url = "https://example.com"
        with patch("mappers.helpers.classify_authority", return_value="media"):
            source = _make_source(url, language="ja", extra_key="extra_value")
        assert source["language"] == "ja"
        assert source["extra_key"] == "extra_value"


# ---------------------------------------------------------------------------
# _build_wr_sources
# ---------------------------------------------------------------------------


class TestBuildWrSources:
    def _make_valid_src(self, url: str = "https://example.com") -> dict[str, Any]:
        return {
            "url": url,
            "title": "Test Source",
            "published_at": "2025-01-01",
            "source_type": "web-research",
            "authority_level": "media",
        }

    def test_正常系_空リストで空の結果が返る(self) -> None:
        sources, url_map = _build_wr_sources([])
        assert sources == []
        assert url_map == {}

    def test_正常系_単一ソースでsource_idが生成される(self) -> None:
        raw = [self._make_valid_src()]
        sources, url_map = _build_wr_sources(raw)
        assert len(sources) == 1
        assert sources[0]["source_id"] == generate_source_id("https://example.com")
        assert "https://example.com" in url_map

    def test_正常系_複数ソースでurl_to_source_idマッピングが生成される(self) -> None:
        raw = [
            self._make_valid_src("https://a.com"),
            self._make_valid_src("https://b.com"),
        ]
        sources, url_map = _build_wr_sources(raw)
        assert len(sources) == 2
        assert "https://a.com" in url_map
        assert "https://b.com" in url_map
        assert url_map["https://a.com"] != url_map["https://b.com"]

    def test_正常系_source_typeが正規化される(self) -> None:
        raw = [self._make_valid_src()]
        sources, _ = _build_wr_sources(raw)
        assert sources[0]["source_type"] == "web"

    def test_異常系_無効なauthority_levelでValueErrorが発生する(self) -> None:
        raw = [
            {
                "url": "https://example.com",
                "authority_level": "invalid_level",
                "source_type": "web-research",
            }
        ]
        with pytest.raises(ValueError, match="Invalid authority_level"):
            _build_wr_sources(raw)

    def test_エッジケース_urlなしのソースはスキップされる(self) -> None:
        raw = [
            {
                "url": "",
                "authority_level": "media",
                "source_type": "web-research",
            }
        ]
        sources, url_map = _build_wr_sources(raw)
        assert sources == []
        assert url_map == {}


# ---------------------------------------------------------------------------
# _build_wr_topics
# ---------------------------------------------------------------------------


class TestBuildWrTopics:
    def _make_source_node(self, url: str = "https://example.com") -> dict[str, Any]:
        return {"source_id": generate_source_id(url), "url": url}

    def test_正常系_空リストで空の結果が返る(self) -> None:
        topics, tagged = _build_wr_topics([], [])
        assert topics == []
        assert tagged == []

    def test_正常系_単一トピックでtopic_idが生成される(self) -> None:
        raw_topics = [{"name": "AI Investment", "category": "technology"}]
        topics, _ = _build_wr_topics(raw_topics, [])
        assert len(topics) == 1
        assert topics[0]["topic_id"] == generate_topic_id("AI Investment", "technology")
        assert topics[0]["name"] == "AI Investment"
        assert topics[0]["category"] == "technology"
        assert topics[0]["topic_key"] == "AI Investment::technology"

    def test_正常系_複数トピックで複数のtopicが生成される(self) -> None:
        raw_topics = [
            {"name": "AI", "category": "technology"},
            {"name": "FRB", "category": "macro"},
        ]
        topics, _ = _build_wr_topics(raw_topics, [])
        assert len(topics) == 2

    def test_正常系_topic_idの冪等性が保たれる(self) -> None:
        raw_topics = [{"name": "Same Topic", "category": "macro"}]
        t1, _ = _build_wr_topics(raw_topics, [])
        t2, _ = _build_wr_topics(raw_topics, [])
        assert t1[0]["topic_id"] == t2[0]["topic_id"]

    def test_正常系_sourcesがあればTAGGEDリレーションが生成される(self) -> None:
        raw_topics = [{"name": "AI", "category": "technology"}]
        sources = [self._make_source_node()]
        _, tagged = _build_wr_topics(raw_topics, sources)
        assert len(tagged) == 1
        assert tagged[0]["type"] == "TAGGED"

    def test_正常系_複数ソースと複数トピックで積の数のTAGGEDが生成される(self) -> None:
        raw_topics = [
            {"name": "AI", "category": "technology"},
            {"name": "FRB", "category": "macro"},
        ]
        sources = [
            self._make_source_node("https://a.com"),
            self._make_source_node("https://b.com"),
        ]
        _, tagged = _build_wr_topics(raw_topics, sources)
        # 2 topics * 2 sources = 4 rels
        assert len(tagged) == 4


# ---------------------------------------------------------------------------
# _build_wr_facts
# ---------------------------------------------------------------------------


class TestBuildWrFacts:
    def _make_url_map(self) -> dict[str, str]:
        url = "https://example.com"
        return {url: generate_source_id(url)}

    def test_正常系_空リストで5要素タプルが返る(self) -> None:
        result = _build_wr_facts([], {}, [])
        assert isinstance(result, tuple)
        assert len(result) == 5
        facts, entities, fact_rels, tagged_rels, entity_id_map = result
        assert facts == []
        assert entities == []

    def test_正常系_単一ファクトでfact_idが生成される(self) -> None:
        url = "https://example.com"
        url_map = {url: generate_source_id(url)}
        raw_facts = [
            {
                "content": "GDP grew 3.5%",
                "source_url": url,
                "about_entities": [],
            }
        ]
        facts, _, _, _, _ = _build_wr_facts(raw_facts, url_map, [])
        assert len(facts) == 1
        assert facts[0]["fact_id"] == generate_fact_id("GDP grew 3.5%")
        assert facts[0]["content"] == "GDP grew 3.5%"

    def test_正常系_entity付きファクトでentitiesが生成される(self) -> None:
        url = "https://example.com"
        url_map = {url: generate_source_id(url)}
        raw_facts = [
            {
                "content": "Apple revenue hit record",
                "source_url": url,
                "about_entities": [
                    {"name": "Apple", "entity_type": "company"}
                ],
            }
        ]
        _, entities, fact_rels, _, _ = _build_wr_facts(raw_facts, url_map, [])
        assert len(entities) == 1
        assert entities[0]["name"] == "Apple"
        assert "fact_entity" in fact_rels
        assert len(fact_rels["fact_entity"]) == 1
        assert fact_rels["fact_entity"][0]["type"] == "RELATES_TO"

    def test_正常系_source_urlがurl_mapに存在しない場合はスキップされる(self) -> None:
        raw_facts = [
            {
                "content": "Some fact",
                "source_url": "https://unknown.com",
                "about_entities": [],
            }
        ]
        facts, _, _, _, _ = _build_wr_facts(raw_facts, {}, [])
        assert facts == []

    def test_正常系_fact_relsに必要なキーが含まれる(self) -> None:
        url = "https://example.com"
        url_map = {url: generate_source_id(url)}
        raw_facts = [
            {
                "content": "Test fact",
                "source_url": url,
                "about_entities": [],
            }
        ]
        _, _, fact_rels, _, _ = _build_wr_facts(raw_facts, url_map, [])
        assert "source_fact" in fact_rels
        assert "fact_entity" in fact_rels
        assert "extracted_from_fact" in fact_rels

    def test_正常系_STATES_FACTリレーションが生成される(self) -> None:
        url = "https://example.com"
        url_map = {url: generate_source_id(url)}
        raw_facts = [{"content": "Fact content", "source_url": url, "about_entities": []}]
        _, _, fact_rels, _, _ = _build_wr_facts(raw_facts, url_map, [])
        assert len(fact_rels["source_fact"]) == 1
        assert fact_rels["source_fact"][0]["type"] == "STATES_FACT"

    def test_正常系_同一entityが複数ファクトで参照されても重複しない(self) -> None:
        url = "https://example.com"
        url_map = {url: generate_source_id(url)}
        raw_facts = [
            {
                "content": "Fact 1 about Apple",
                "source_url": url,
                "about_entities": [{"name": "Apple", "entity_type": "company"}],
            },
            {
                "content": "Fact 2 about Apple",
                "source_url": url,
                "about_entities": [{"name": "Apple", "entity_type": "company"}],
            },
        ]
        _, entities, _, _, entity_id_map = _build_wr_facts(raw_facts, url_map, [])
        # entity は1件のみ（entity_id_mapによる重複排除）
        assert len(entities) == 1
        assert "Apple::company" in entity_id_map

    def test_正常系_topicsがあればTAGGEDリレーションが生成される(self) -> None:
        url = "https://example.com"
        url_map = {url: generate_source_id(url)}
        topic_node = {
            "topic_id": generate_topic_id("AI", "technology"),
            "name": "AI",
            "category": "technology",
        }
        raw_facts = [{"content": "AI fact", "source_url": url, "about_entities": []}]
        _, _, _, tagged_rels, _ = _build_wr_facts(raw_facts, url_map, [topic_node])
        assert len(tagged_rels) == 1
        assert tagged_rels[0]["type"] == "TAGGED"
