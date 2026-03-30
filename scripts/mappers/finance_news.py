"""mappers/finance_news.py — finance-news-workflow コマンドのプラグインマッパー。

``BaseMapper`` を継承し、``map()`` メソッドに
``--command finance-news-workflow`` 固有のロジックのみを実装する。

入力フォーマット
---------------
::

    {
        "articles": [
            {
                "url": "https://...",
                "title": "...",
                "summary": "...",
                "published": "2026-01-01T00:00:00+00:00",
                "feed_source": "CNBC - Markets"
            }
        ],
        "session_id": "...",
        "batch_label": "index"
    }

Usage
-----
::

    from mappers.finance_news import FinanceNewsMapper

    mapper = FinanceNewsMapper()
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


class FinanceNewsMapper(BaseMapper):
    """finance-news-workflow コマンド専用マッパー。

    ``articles[]`` から Source と Claim ノードを生成する。
    共通処理（``build_result``）は ``BaseMapper`` に委譲する。

    Notes
    -----
    - Source: 各記事1件につき1ノード
    - Claim: ``summary`` が存在する場合のみ生成
    - ``batch_label`` を ``category`` として使用
    """

    def map(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """finance-news-workflow 入力データをグラフキューコンポーネントにマップする。

        Parameters
        ----------
        input_data : dict[str, Any]
            ``articles[]``, ``session_id``, ``batch_label`` を含む入力データ。

        Returns
        -------
        dict[str, Any]
            ``sources``, ``claims``, ``session_id``, ``batch_label`` を含む
            標準化されたマッパー結果。
        """
        # 遅延インポートで循環依存を回避
        from emit_research_queue import (  # type: ignore[import]
            _make_source,
            generate_claim_id,
            generate_source_id,
            resolve_category,
        )

        articles = input_data.get("articles", [])
        sources: list[dict[str, Any]] = []
        claims: list[dict[str, Any]] = []

        logger.debug("FinanceNewsMapper.map: processing %d articles", len(articles))

        for article in articles:
            url = article.get("url", "")
            source_id = generate_source_id(url)

            sources.append(
                _make_source(
                    url,
                    title=article.get("title", ""),
                    published=article.get("published", ""),
                    feed_source=article.get("feed_source", ""),
                )
            )

            summary = article.get("summary", "")
            if summary:
                claims.append(
                    {
                        "claim_id": generate_claim_id(summary),
                        "content": summary,
                        "source_id": source_id,
                        "category": resolve_category(input_data.get("batch_label", "")),
                    }
                )

        logger.info(
            "FinanceNewsMapper.map: sources=%d, claims=%d",
            len(sources),
            len(claims),
        )

        return self.build_result(
            input_data,
            input_data.get("batch_label", ""),
            sources=sources,
            claims=claims,
        )
