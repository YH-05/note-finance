"""mappers/finance_full.py — finance-full コマンドのプラグインマッパー。

``BaseMapper`` を継承し、``map()`` メソッドに
``--command finance-full`` 固有のロジックのみを実装する。

入力フォーマット
---------------
::

    {
        "sources": [
            {
                "url": "https://example.com/article",
                "title": "...",
                "published": "2026-01-01T00:00:00+00:00"
            }
        ],
        "claims": [
            {
                "content": "...",
                "source_url": "https://example.com/article",
                "category": "macro"
            }
        ],
        "session_id": "finance-full-20260307"
    }

Usage
-----
::

    from mappers.finance_full import FinanceFullMapper

    mapper = FinanceFullMapper()
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


class FinanceFullMapper(BaseMapper):
    """finance-full コマンド専用マッパー。

    記事作成全工程データから Source と Claim ノードを生成する。
    共通処理（``build_result``）は ``BaseMapper`` に委譲する。

    Notes
    -----
    - Source: 入力ソースのIDを生成して保持
    - Claim: 入力クレームのIDを生成して保持
    - ``batch_label`` は ``"finance-full"`` 固定
    """

    def map(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """finance-full 入力データをグラフキューコンポーネントにマップする。

        Parameters
        ----------
        input_data : dict[str, Any]
            ``sources[]``, ``claims[]``, ``session_id`` を含む入力データ。

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

        input_sources = input_data.get("sources", [])
        input_claims = input_data.get("claims", [])
        sources: list[dict[str, Any]] = []
        claims: list[dict[str, Any]] = []

        logger.debug(
            "FinanceFullMapper.map: sources=%d, claims=%d",
            len(input_sources),
            len(input_claims),
        )

        for source in input_sources:
            url = source.get("url", "")
            sources.append(
                _make_source(
                    url,
                    title=source.get("title", ""),
                    published=source.get("published", ""),
                )
            )

        for claim in input_claims:
            content = claim.get("content", "")
            claims.append(
                {
                    "claim_id": generate_claim_id(content),
                    "content": content,
                    "source_url": claim.get("source_url", ""),
                    "category": claim.get("category", ""),
                }
            )

        logger.info(
            "FinanceFullMapper.map: sources=%d, claims=%d",
            len(sources),
            len(claims),
        )

        return self.build_result(
            input_data,
            "finance-full",
            sources=sources,
            claims=claims,
        )
