"""mappers/ai_research.py — ai-research-collect コマンドのプラグインマッパー。

``BaseMapper`` を継承し、``map()`` メソッドに
``--command ai-research-collect`` 固有のロジックのみを実装する。

入力フォーマット
---------------
::

    {
        "companies": [
            {
                "company_name": "OpenAI",
                "ticker": "",
                "url": "https://openai.com",
                "title": "OpenAI official site",
                "published": "2026-01-01T00:00:00+00:00"
            }
        ],
        "session_id": "ai-research-20260307"
    }

Usage
-----
::

    from mappers.ai_research import AiResearchMapper

    mapper = AiResearchMapper()
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


class AiResearchMapper(BaseMapper):
    """ai-research-collect コマンド専用マッパー。

    AI投資バリューチェーン企業データから Entity と Source ノードを生成する。
    共通処理（``build_result``）は ``BaseMapper`` に委譲する。

    Notes
    -----
    - Entity: 企業ごとに1ノード（entity_type="company"）
    - Source: URL がある企業ごとに1ノード
    - ``batch_label`` は ``"ai"`` 固定
    """

    def map(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """ai-research-collect 入力データをグラフキューコンポーネントにマップする。

        Parameters
        ----------
        input_data : dict[str, Any]
            ``companies[]``, ``session_id`` を含む入力データ。

        Returns
        -------
        dict[str, Any]
            ``entities``, ``sources``, ``session_id``, ``batch_label`` を含む
            標準化されたマッパー結果。
        """
        from mappers.helpers import (
            _make_source,
            generate_entity_id,
        )

        from ontology_loader import ENTITY_TYPE_TO_LABEL  # noqa: PLC0415

        companies = input_data.get("companies", [])
        entities: list[dict[str, Any]] = []
        sources: list[dict[str, Any]] = []
        seen_names: set[str] = set()

        logger.debug("AiResearchMapper.map: processing %d companies", len(companies))

        for company in companies:
            company_name = company.get("company_name", "")
            ticker = company.get("ticker", "")
            url = company.get("url", "")

            # v4.0: name ベース重複排除（entity_key 廃止）
            if not company_name or company_name in seen_names:
                continue
            seen_names.add(company_name)

            # entity_type → Neo4j ラベル
            neo4j_label = ENTITY_TYPE_TO_LABEL.get("company", "Company")

            # Create entity for the company
            entities.append(
                {
                    "entity_id": generate_entity_id(company_name, "company"),
                    "name": company_name,
                    "entity_type": "company",
                    "neo4j_label": neo4j_label,
                    "ticker": ticker,
                    # v4.0: entity_key フィールドは生成しない
                }
            )

            # Create source
            if url:
                sources.append(
                    _make_source(
                        url,
                        title=company.get("title", ""),
                        published=company.get("published", ""),
                    )
                )

        logger.info(
            "AiResearchMapper.map: entities=%d, sources=%d",
            len(entities),
            len(sources),
        )

        return self.build_result(
            input_data,
            "ai",
            sources=sources,
            entities=entities,
        )
