"""mappers/asset_management.py — asset-management コマンドのプラグインマッパー。

``BaseMapper`` を継承し、``map()`` メソッドに
``--command asset-management`` 固有のロジックのみを実装する。

入力フォーマット
---------------
::

    {
        "themes": {
            "nisa": {
                "name_ja": "NISA",
                "articles": [
                    {
                        "url": "https://example.com/nisa",
                        "title": "...",
                        "published": "2026-01-01T00:00:00+00:00",
                        "feed_source": "MoneyForward"
                    }
                ]
            }
        },
        "session_id": "asset-management-20260307"
    }

Usage
-----
::

    from mappers.asset_management import AssetManagementMapper

    mapper = AssetManagementMapper()
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


class AssetManagementMapper(BaseMapper):
    """asset-management コマンド専用マッパー。

    資産形成コンテンツデータから Source と Topic ノードを生成する。
    共通処理（``build_result``）は ``BaseMapper`` に委譲する。

    Notes
    -----
    - Topic: テーマごとに1ノード（category="asset-management"）
    - Source: テーマ内の記事ごとに1ノード
    - ``batch_label`` は ``"asset-management"`` 固定
    """

    def map(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """asset-management 入力データをグラフキューコンポーネントにマップする。

        Parameters
        ----------
        input_data : dict[str, Any]
            ``themes.{key}.articles[]``, ``session_id`` を含む入力データ。

        Returns
        -------
        dict[str, Any]
            ``sources``, ``topics``, ``session_id``, ``batch_label`` を含む
            標準化されたマッパー結果。
        """
        from mappers.helpers import (
            _make_source,
            generate_topic_id,
        )

        themes = input_data.get("themes", {})
        sources: list[dict[str, Any]] = []
        topics: list[dict[str, Any]] = []

        logger.debug("AssetManagementMapper.map: processing %d themes", len(themes))

        for theme_key, theme_data in themes.items():
            name_ja = theme_data.get("name_ja", theme_key)

            # Create topic for the theme
            topics.append(
                {
                    "topic_id": generate_topic_id(name_ja, "asset-management"),
                    "name": name_ja,
                    "category": "asset-management",
                    "theme_key": theme_key,
                    "topic_key": f"{name_ja}::asset-management",
                }
            )

            # Map articles to sources
            articles = theme_data.get("articles", [])
            for article in articles:
                url = article.get("url", "")
                if url:
                    sources.append(
                        _make_source(
                            url,
                            title=article.get("title", ""),
                            published=article.get("published", ""),
                            feed_source=article.get("feed_source", ""),
                        )
                    )

        logger.info(
            "AssetManagementMapper.map: sources=%d, topics=%d",
            len(sources),
            len(topics),
        )

        return self.build_result(
            input_data,
            "asset-management",
            sources=sources,
            topics=topics,
        )
