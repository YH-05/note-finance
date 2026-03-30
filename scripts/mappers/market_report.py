"""mappers/market_report.py — generate-market-report コマンドのプラグインマッパー。

``BaseMapper`` を継承し、``map()`` メソッドに
``--command generate-market-report`` 固有のロジックのみを実装する。

入力フォーマット
---------------
::

    {
        "sections": [
            {
                "title": "マクロ経済",
                "content": "...",
                "sources": [
                    {
                        "url": "https://example.com/report",
                        "title": "Weekly Report",
                        "published": "2026-01-01T00:00:00+00:00"
                    }
                ]
            }
        ],
        "session_id": "market-report-20260307"
    }

Usage
-----
::

    from mappers.market_report import MarketReportMapper

    mapper = MarketReportMapper()
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


class MarketReportMapper(BaseMapper):
    """generate-market-report コマンド専用マッパー。

    週次マーケットレポートデータから Source と Claim ノードを生成する。
    共通処理（``build_result``）は ``BaseMapper`` に委譲する。

    Notes
    -----
    - Source: セクションのソースから重複排除して生成
    - Claim: セクションのコンテンツから生成（category="macro"）
    - ``batch_label`` は ``"market-report"`` 固定
    """

    def map(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """generate-market-report 入力データをグラフキューコンポーネントにマップする。

        Parameters
        ----------
        input_data : dict[str, Any]
            ``sections[]``, ``session_id`` を含む入力データ。

        Returns
        -------
        dict[str, Any]
            ``sources``, ``claims``, ``session_id``, ``batch_label`` を含む
            標準化されたマッパー結果。
        """
        from emit_research_queue import (  # type: ignore[import]
            _make_source,
            generate_claim_id,
        )

        sections = input_data.get("sections", [])
        sources: list[dict[str, Any]] = []
        claims: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        logger.debug("MarketReportMapper.map: processing %d sections", len(sections))

        for section in sections:
            # Collect sources from section
            for source in section.get("sources", []):
                url = source.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    sources.append(
                        _make_source(
                            url,
                            title=source.get("title", ""),
                            published=source.get("published", ""),
                        )
                    )

            # Create claim from section content
            content = section.get("content", "")
            if content:
                claims.append(
                    {
                        "claim_id": generate_claim_id(content),
                        "content": content,
                        "section_title": section.get("title", ""),
                        "category": "macro",
                    }
                )

        logger.info(
            "MarketReportMapper.map: sources=%d, claims=%d",
            len(sources),
            len(claims),
        )

        return self.build_result(
            input_data,
            "market-report",
            sources=sources,
            claims=claims,
        )
