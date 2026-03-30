"""mappers/wealth_scrape.py — wealth-scrape コマンドのプラグインマッパー。

``BaseMapper`` を継承し、``map()`` メソッドに
``--command wealth-scrape`` 固有のロジックのみを実装する。

入力フォーマット
---------------
::

    {
        "mode": "backfill" | "incremental",
        "themes": {
            "data_driven_investing": {
                "name_en": "Data-Driven Investing",
                "keywords_en": ["quant", "algorithm"],
                "articles": [
                    {
                        "url": "https://...",
                        "title": "...",
                        "summary": "...",
                        "published": "...",
                        "domain": "example.com"
                    }
                ]
            }
        },
        "session_id": "..."
    }

Usage
-----
::

    from mappers.wealth_scrape import WealthScrapeMapper

    mapper = WealthScrapeMapper()
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


class WealthScrapeMapper(BaseMapper):
    """wealth-scrape コマンド専用マッパー。

    ``mode`` フィールドに基づいてバックフィルまたはインクリメンタルモードに
    ディスパッチする。共通処理（``build_result``）は ``BaseMapper`` に委譲する。

    Modes
    -----
    backfill
        Source, Topic, Entity (domain), keyword-matched TAGGED リレーション。
        Claim は生成しない。
    incremental (default)
        Source, Topic, Claim, keyword-matched TAGGED / source_claim リレーション。
        Domain Entity は生成しない。
    """

    def map(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """wealth-scrape 入力データをグラフキューコンポーネントにマップする。

        ``mode`` に応じてバックフィルまたはインクリメンタルサブマッパーに委譲する。

        Parameters
        ----------
        input_data : dict[str, Any]
            ``mode``, ``themes``, ``session_id`` を含む入力データ。

        Returns
        -------
        dict[str, Any]
            標準化されたマッパー結果。
        """
        mode = input_data.get("mode", "")
        logger.debug("WealthScrapeMapper.map: mode=%r", mode)

        if mode == "backfill":
            return self._map_backfill(input_data)
        return self._map_incremental(input_data)

    def _map_backfill(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """バックフィルモードのマッピング。

        Source, Topic, Entity (domain), keyword-matched TAGGED リレーションを生成。

        Parameters
        ----------
        input_data : dict[str, Any]
            ``themes.{key}.articles[]`` を含む入力データ。

        Returns
        -------
        dict[str, Any]
            ``sources``, ``topics``, ``entities``, ``relations.tagged`` を含む結果。
        """
        # 遅延インポートで循環依存を回避
        from emit_research_queue import (  # type: ignore[import]
            _empty_rels,
            _map_wealth_theme_common,
            _process_wealth_article,
            generate_entity_id,
        )

        themes = input_data.get("themes", {})
        sources: list[dict[str, Any]] = []
        topics: list[dict[str, Any]] = []
        entities: list[dict[str, Any]] = []
        tagged_rels: list[dict[str, str]] = []
        seen_domains: set[str] = set()

        for theme_key, theme_data in themes.items():
            topic_id, keywords_lower, articles = _map_wealth_theme_common(
                theme_key, theme_data, sources, topics, tagged_rels
            )

            for article in articles:
                source_id = _process_wealth_article(
                    article,
                    topic_id,
                    keywords_lower,
                    sources,
                    tagged_rels,
                    source_type="blog",
                )
                if source_id is None:
                    continue

                # Entity: ユニークドメインごとに1件
                domain = article.get("domain", "")
                if domain and domain not in seen_domains:
                    seen_domains.add(domain)
                    entities.append(
                        {
                            "entity_id": generate_entity_id(domain, "domain"),
                            "name": domain,
                            "entity_type": "domain",
                            "entity_key": f"{domain}::domain",
                        }
                    )

        rels = _empty_rels()
        rels["tagged"] = tagged_rels

        logger.info(
            "WealthScrapeMapper._map_backfill: sources=%d, topics=%d, entities=%d",
            len(sources),
            len(topics),
            len(entities),
        )

        return self.build_result(
            input_data,
            "wealth-scrape",
            sources=sources,
            topics=topics,
            entities=entities,
            relations=rels,
        )

    def _map_incremental(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """インクリメンタルモードのマッピング。

        Source, Topic, Claim, keyword-matched TAGGED / source_claim リレーションを生成。

        Parameters
        ----------
        input_data : dict[str, Any]
            ``themes.{key}.articles[]`` を含む入力データ。

        Returns
        -------
        dict[str, Any]
            ``sources``, ``topics``, ``claims``,
            ``relations.tagged``, ``relations.source_claim`` を含む結果。
        """
        # 遅延インポートで循環依存を回避
        from emit_research_queue import (  # type: ignore[import]
            _empty_rels,
            _map_wealth_theme_common,
            _process_wealth_article,
            generate_claim_id,
        )

        themes = input_data.get("themes", {})
        sources: list[dict[str, Any]] = []
        topics: list[dict[str, Any]] = []
        claims: list[dict[str, Any]] = []
        tagged_rels: list[dict[str, str]] = []
        source_claim_rels: list[dict[str, str]] = []

        for theme_key, theme_data in themes.items():
            topic_id, keywords_lower, articles = _map_wealth_theme_common(
                theme_key, theme_data, sources, topics, tagged_rels
            )

            for article in articles:
                source_id = _process_wealth_article(
                    article,
                    topic_id,
                    keywords_lower,
                    sources,
                    tagged_rels,
                )
                if source_id is None:
                    continue

                # summary から Claim を生成
                summary = article.get("summary", "")
                if summary:
                    claim_id = generate_claim_id(summary)
                    claims.append(
                        {
                            "claim_id": claim_id,
                            "content": summary,
                            "source_id": source_id,
                            "category": "wealth-management",
                        }
                    )
                    source_claim_rels.append({"from_id": source_id, "to_id": claim_id})

        rels = _empty_rels()
        rels["tagged"] = tagged_rels
        rels["source_claim"] = source_claim_rels

        logger.info(
            "WealthScrapeMapper._map_incremental: sources=%d, topics=%d, claims=%d",
            len(sources),
            len(topics),
            len(claims),
        )

        return self.build_result(
            input_data,
            "wealth-scrape",
            sources=sources,
            topics=topics,
            claims=claims,
            relations=rels,
        )
