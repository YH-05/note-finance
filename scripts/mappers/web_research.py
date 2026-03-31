"""mappers/web_research.py — web-research コマンドのプラグインマッパー。

``BaseMapper`` を継承し、``map()`` メソッドに
``--command web-research`` 固有のロジックのみを実装する。

入力フォーマット
---------------
::

    {
        "sources": [
            {
                "url": "https://...",
                "title": "...",
                "source_type": "web",
                "authority_level": "media",
                "publisher": "...",
                "data_source": "tavily"
            }
        ],
        "facts": [
            {
                "content": "...",
                "source_url": "https://...",
                "confidence": 0.9,
                "fact_type": "financial_metric",
                "about_entities": [{"name": "Apple", "entity_type": "company"}]
            }
        ],
        "claims": [
            {
                "content": "...",
                "source_url": "https://...",
                "claim_type": "analyst_opinion",
                "sentiment": "positive",
                "about_entities": [{"name": "Apple", "entity_type": "company"}]
            }
        ],
        "topics": [
            {"name": "AI", "category": "technology"}
        ],
        "causal_links": [],
        "session_id": "..."
    }

Usage
-----
::

    from mappers.web_research import WebResearchMapper

    mapper = WebResearchMapper()
    result = mapper.map(data)
"""

from __future__ import annotations

import logging
from typing import Any

from mappers.base import BaseMapper

try:
    from utils_core.logging.config import get_logger

    logger = get_logger(__name__)
except ImportError:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger = logging.getLogger(__name__)


class WebResearchMapper(BaseMapper):
    """web-research コマンド専用マッパー。

    アドホック Web リサーチデータをフォーマルなパイプライン形式に変換する。
    共通処理（``build_result``）は ``BaseMapper`` に委譲する。

    Notes
    -----
    - Sources: ``authority_level`` バリデーション付き
    - Facts: ``source_url`` をキーに Source との紐付け
    - Claims: オプションの ``source_url`` によるソース紐付け
    - Topics: Source および Fact と全件クロス積で TAGGED リレーションを生成
    - Causal: CAUSES / CONTRADICTS / SUPPORTED_BY 等のカーサルリレーション

    Raises
    ------
    KeyError
        source に ``authority_level`` が欠落している場合。
    ValueError
        ``authority_level`` の値が無効な場合。
    """

    def map(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """web-research 入力データをグラフキューコンポーネントにマップする。

        Parameters
        ----------
        input_data : dict[str, Any]
            ``sources[]``, ``facts[]``, ``claims[]``, ``topics[]``,
            ``causal_links[]``, ``session_id`` を含む入力データ。

        Returns
        -------
        dict[str, Any]
            ``sources``, ``facts``, ``claims``, ``entities``, ``topics``,
            ``relations`` (``source_fact``, ``fact_entity``,
            ``extracted_from_fact``, ``source_claim``, ``claim_entity``,
            ``tagged``, ``tagged_fact``, ``causal``) を含む標準化された結果。

        Raises
        ------
        KeyError
            source に ``authority_level`` が欠落している場合。
        ValueError
            ``authority_level`` の値が無効な場合。
        """
        from mappers.helpers import (
            _build_wr_causal_rels,
            _build_wr_claims,
            _build_wr_facts,
            _build_wr_sources,
            _build_wr_topics,
        )

        logger.debug(
            "WebResearchMapper.map: sources=%d, facts=%d, claims=%d, topics=%d",
            len(input_data.get("sources", [])),
            len(input_data.get("facts", [])),
            len(input_data.get("claims", [])),
            len(input_data.get("topics", [])),
        )

        sources, url_to_source_id = _build_wr_sources(input_data.get("sources", []))
        topics, tagged_rels = _build_wr_topics(input_data.get("topics", []), sources)
        # AIDEV-NOTE: _build_wr_facts の型アノテーションは4要素を宣言しているが、
        # 実装は5要素 (facts, entities, fact_rels, tagged_rels, entity_id_map) を返す。
        # 型アノテーションの誤りのため type: ignore を使用する。
        facts, entities, fact_rels, fact_tagged, entity_id_map = _build_wr_facts(  # type: ignore[misc]
            input_data.get("facts", []), url_to_source_id, topics
        )
        # AIDEV-NOTE: tagged を Source→Topic と Fact→Topic に分離。
        # neo4j_loader の _REL_ENDPOINTS は tagged=Source→Topic, tagged_fact=Fact→Topic を別キーで処理する。
        # 旧コードでは混在リストだったため Fact→Topic がサイレントに欠落していた。

        claims, _claim_entities, claim_rels = _build_wr_claims(
            input_data.get("claims", []), url_to_source_id, entity_id_map, entities
        )

        # カーサルリレーション（オプション）
        causal_rels = _build_wr_causal_rels(
            input_data.get("causal_links", []), entity_id_map
        )

        logger.info(
            "WebResearchMapper.map: sources=%d, facts=%d, claims=%d, entities=%d",
            len(sources),
            len(facts),
            len(claims),
            len(entities),
        )

        return self.build_result(
            input_data,
            "web-research",
            sources=sources,
            facts=facts,
            claims=claims,
            entities=entities,
            topics=topics,
            relations={
                **fact_rels,
                **claim_rels,
                **causal_rels,
                "tagged": tagged_rels,
                "tagged_fact": fact_tagged,
            },
        )
