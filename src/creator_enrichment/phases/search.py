"""creator_enrichment Phase 2: DirectSearcher.

Step 2a: LLM (SdkLLMClient) でギャップ分析結果から検索クエリを生成
Step 2b: Tavily REST API (httpx) で検索を実行し RawItem[] に変換

Usage
-----
::

    searcher = DirectSearcher(
        llm_client=SdkLLMClient(),
        genre_config=config_json["genres"],
        tavily_api_key="tvly-...",
    )
    items = searcher.search(queries=["FOMO活用", "PASONAの法則"], genre="career")
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

import httpx

from creator_enrichment.llm_client import LLMClient
from creator_enrichment.types import PhaseError, RawItem
from creator_enrichment.utils import strip_json_codeblock

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------
_TAVILY_SEARCH_URL = "https://api.tavily.com/search"
"""Tavily Search REST API エンドポイント."""

_TAVILY_TIMEOUT = 30
"""Tavily API のタイムアウト（秒）."""

_MAX_RESULTS_PER_QUERY = 5
"""1クエリあたりの最大検索結果数."""

_MAX_QUERY_GENERATION = 12
"""LLM に生成させるクエリの上限数."""

# ---------------------------------------------------------------------------
# クエリ生成プロンプト
# ---------------------------------------------------------------------------
_QUERY_GENERATION_PROMPT = """\
あなたは creator-neo4j ナレッジグラフを拡充するための検索クエリを設計する専門家です。

## コンテキスト

ジャンル: {genre} ({genre_name_ja})
低カバレッジ概念: {low_coverage_concepts}
現在年: {year}

## タスク

以下の2種類の検索クエリを合計 {max_queries} 本生成してください:

### 1. ギャップ補充クエリ（{gap_count}本）
低カバレッジ概念を深掘りする具体的なクエリ。英語3本 + 日本語3本を目安に。

### 2. 探索クエリ（{explore_count}本）
隣接領域・新トレンド・意外な切り口を発見するクエリ。
低カバレッジ概念から連想される未知のトピックを探る。
Reddit の体験談や成功事例を含めること。

## 出力形式

JSON配列で返してください。各要素は {{"query": "検索クエリ文", "type": "gap|explore", "language": "en|ja"}} の形式。

```json
[
  {{"query": "affiliate marketing side hustle tips 2026", "type": "gap", "language": "en"}},
  {{"query": "副業 アフィリエイト 成功事例 2026", "type": "gap", "language": "ja"}},
  {{"query": "unconventional side hustle ideas reddit 2026", "type": "explore", "language": "en"}}
]
```
"""


# ---------------------------------------------------------------------------
# DirectSearcher
# ---------------------------------------------------------------------------
class DirectSearcher:
    """LLM でクエリ生成 + Tavily REST API で検索実行する.

    Parameters
    ----------
    llm_client : LLMClient
        クエリ生成に使用する LLM クライアント
    genre_config : dict[str, Any]
        creator-enrichment-config.json の ``genres`` セクション
    tavily_api_key : str
        Tavily REST API キー
    """

    def __init__(
        self,
        llm_client: LLMClient,
        genre_config: dict[str, Any],
        tavily_api_key: str,
    ) -> None:
        self._llm = llm_client
        self._genre_config = genre_config
        self._tavily_api_key = tavily_api_key
        logger.info("DirectSearcher initialized")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def search(self, queries: list[str], genre: str) -> list[RawItem]:
        """検索クエリを生成・実行し RawItem リストを返す.

        Parameters
        ----------
        queries : list[str]
            低カバレッジ概念のリスト（Gap Analysis Q4 由来）
        genre : str
            対象ジャンル（career / beauty-romance / spiritual）

        Returns
        -------
        list[RawItem]
            検索結果の正規化アイテムリスト

        Raises
        ------
        PhaseError
            クエリ生成失敗または全検索失敗時
        """
        logger.info(
            "Search started: genre=%s, concept_count=%d",
            genre,
            len(queries),
        )

        # Step 2a: LLM でクエリ生成
        search_queries = self._generate_queries(queries, genre)
        logger.info("Generated %d search queries", len(search_queries))

        # Step 2b: Tavily REST API で検索実行
        items = self._execute_searches(search_queries)
        logger.info("Search completed: %d items found", len(items))
        return items

    # ------------------------------------------------------------------
    # Step 2a: LLM クエリ生成
    # ------------------------------------------------------------------
    def _generate_queries(
        self, concepts: list[str], genre: str
    ) -> list[dict[str, str]]:
        """LLM で検索クエリを生成する.

        Parameters
        ----------
        concepts : list[str]
            低カバレッジ概念リスト
        genre : str
            対象ジャンル

        Returns
        -------
        list[dict[str, str]]
            生成されたクエリリスト（query, type, language）

        Raises
        ------
        PhaseError
            LLM 呼び出しまたはパースに失敗した場合
        """
        genre_info = self._genre_config.get(genre, {})
        genre_name_ja = genre_info.get("name_ja", genre)
        year = datetime.now().year

        gap_count = min(7, _MAX_QUERY_GENERATION)
        explore_count = _MAX_QUERY_GENERATION - gap_count

        prompt = _QUERY_GENERATION_PROMPT.format(
            genre=genre,
            genre_name_ja=genre_name_ja,
            low_coverage_concepts=", ".join(concepts[:10]),
            year=year,
            max_queries=_MAX_QUERY_GENERATION,
            gap_count=gap_count,
            explore_count=explore_count,
        )

        try:
            response = self._llm.query(prompt)
        except (RuntimeError, OSError) as e:
            logger.error("LLM query generation failed: %s", e)
            raise PhaseError(f"Query generation failed: {e}") from e

        cleaned = strip_json_codeblock(response)

        try:
            generated = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM query response: %s", e)
            raise PhaseError(f"Query generation parse failed: {e}") from e

        if not isinstance(generated, list):
            raise PhaseError(
                f"Expected list of queries, got {type(generated).__name__}"
            )

        logger.info(
            "Query generation: %d gap + %d explore",
            sum(1 for q in generated if q.get("type") == "gap"),
            sum(1 for q in generated if q.get("type") == "explore"),
        )
        return generated[:_MAX_QUERY_GENERATION]

    # ------------------------------------------------------------------
    # Step 2b: Tavily REST API 検索実行
    # ------------------------------------------------------------------
    def _execute_searches(
        self, search_queries: list[dict[str, str]]
    ) -> list[RawItem]:
        """Tavily REST API で検索を実行する.

        各クエリの失敗は個別にスキップし、他のクエリの実行を継続する。

        Parameters
        ----------
        search_queries : list[dict[str, str]]
            LLM 生成の検索クエリリスト

        Returns
        -------
        list[RawItem]
            全検索結果の正規化アイテムリスト
        """
        all_items: list[RawItem] = []
        seen_urls: set[str] = set()

        for i, sq in enumerate(search_queries):
            query_text = sq.get("query", "")
            if not query_text:
                continue

            # Reddit 体験談は include_domains で対応
            is_reddit = "reddit" in query_text.lower()
            include_domains = ["reddit.com"] if is_reddit else []

            try:
                items = self._tavily_search(
                    query=query_text,
                    include_domains=include_domains,
                )
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                logger.warning(
                    "Tavily query %d/%d failed (skipping): %s",
                    i + 1,
                    len(search_queries),
                    e,
                )
                continue

            # URL 重複排除
            for item in items:
                if item["url"] not in seen_urls:
                    seen_urls.add(item["url"])
                    all_items.append(item)

            logger.debug(
                "Query %d/%d: %d results (query=%s)",
                i + 1,
                len(search_queries),
                len(items),
                query_text[:50],
            )

        return all_items

    def _tavily_search(
        self,
        query: str,
        include_domains: list[str] | None = None,
    ) -> list[RawItem]:
        """Tavily REST API を1回呼び出す.

        Parameters
        ----------
        query : str
            検索クエリ文字列
        include_domains : list[str] | None
            結果を限定するドメインリスト

        Returns
        -------
        list[RawItem]
            検索結果

        Raises
        ------
        httpx.HTTPError
            API エラー時
        """
        payload: dict[str, Any] = {
            "query": query,
            "max_results": _MAX_RESULTS_PER_QUERY,
            "include_raw_content": False,
        }
        if include_domains:
            payload["include_domains"] = include_domains

        response = httpx.post(
            _TAVILY_SEARCH_URL,
            json=payload,
            headers={"Authorization": f"Bearer {self._tavily_api_key}"},
            timeout=_TAVILY_TIMEOUT,
        )
        response.raise_for_status()

        data = response.json()
        results = data.get("results", [])

        return [
            RawItem(
                url=str(r.get("url", "")),
                title=str(r.get("title", "")),
                content=str(r.get("content", "")),
                source="tavily",
            )
            for r in results
        ]
