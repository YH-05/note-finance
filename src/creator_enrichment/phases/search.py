"""creator_enrichment Phase 2: DirectSearcher.

Step 2a: LLM (SdkLLMClient) でギャップ分析結果から検索クエリを生成
Step 2b: Tavily REST API (httpx) で検索を実行し RawItem[] に変換

Tavily API キーは ``TavilyKeyPool`` で複数ローテーション可能。
432 エラー（上限到達）時に自動で次のキーに切り替える。

Usage
-----
::

    pool = TavilyKeyPool.from_env()  # TAVILY_API_KEYS から読み込み
    searcher = DirectSearcher(
        llm_client=SdkLLMClient(),
        genre_config=config_json["genres"],
        tavily_key_pool=pool,
    )
    items = searcher.search(queries=["FOMO活用", "PASONAの法則"], genre="career")
"""

from __future__ import annotations

import json
import logging
import os
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

_TAVILY_RATE_LIMIT_STATUS = 432
"""Tavily API のプラン上限超過ステータスコード."""


# ---------------------------------------------------------------------------
# TavilyKeyPool
# ---------------------------------------------------------------------------
class TavilyKeyPool:
    """複数の Tavily API キーをローテーションする.

    432 エラー（プラン上限）が発生したキーをプールから除外し、
    次のキーに自動切り替えする。

    Parameters
    ----------
    keys : list[str]
        Tavily API キーのリスト
    """

    def __init__(self, keys: list[str]) -> None:
        self._keys = list(keys)
        self._exhausted: set[str] = set()
        self._index = 0
        logger.info("TavilyKeyPool initialized: %d keys", len(self._keys))

    @classmethod
    def from_env(cls) -> TavilyKeyPool:
        """環境変数から TavilyKeyPool を生成する.

        ``TAVILY_API_KEY_1``, ``TAVILY_API_KEY_2``, ... の連番を収集。
        連番が無い場合は ``TAVILY_API_KEY``（単一キー）にフォールバック。

        Returns
        -------
        TavilyKeyPool
            空の場合もインスタンスは生成される（has_keys() で判定）
        """
        keys: list[str] = []

        # 連番キーを収集: TAVILY_API_KEY_1, _2, _3, ...
        for i in range(1, 100):
            val = os.environ.get(f"TAVILY_API_KEY_{i}", "")
            if not val:
                break
            keys.append(val)

        # フォールバック: TAVILY_API_KEY（単一キー）
        if not keys:
            single = os.environ.get("TAVILY_API_KEY", "")
            if single:
                keys.append(single)

        return cls(keys)

    def has_keys(self) -> bool:
        """利用可能なキーが残っているか."""
        return bool(self._available_keys())

    def get_key(self) -> str | None:
        """次に使用するキーを返す。枯渇時は None."""
        available = self._available_keys()
        if not available:
            return None
        self._index = self._index % len(available)
        key = available[self._index]
        self._index = (self._index + 1) % len(available)
        return key

    def mark_exhausted(self, key: str) -> None:
        """432 エラーのキーを除外する."""
        self._exhausted.add(key)
        remaining = len(self._available_keys())
        logger.warning(
            "Tavily key exhausted (432): ...%s, remaining=%d",
            key[-8:],
            remaining,
        )

    def _available_keys(self) -> list[str]:
        return [k for k in self._keys if k not in self._exhausted]


_SEARCH_SYSTEM_PROMPT = """\
You are a research assistant. Execute web searches for the given queries \
and return all results as a JSON object.

Return ONLY a JSON object with this structure (no markdown, no explanation):
{"items": [{"url": "...", "title": "...", "content": "...", "source": "web_search"}]}
"""

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
    tavily_key_pool : TavilyKeyPool | None
        Tavily API キープール。None の場合は SDK フォールバックのみ。
    """

    def __init__(
        self,
        llm_client: LLMClient,
        genre_config: dict[str, Any],
        tavily_key_pool: TavilyKeyPool | None = None,
    ) -> None:
        self._llm = llm_client
        self._genre_config = genre_config
        self._key_pool = tavily_key_pool
        logger.info(
            "DirectSearcher initialized (tavily_keys=%s)",
            "available" if tavily_key_pool and tavily_key_pool.has_keys() else "none",
        )

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
    # Step 2b: 検索実行（Tavily → SDK フォールバック）
    # ------------------------------------------------------------------
    def _execute_searches(
        self, search_queries: list[dict[str, str]]
    ) -> list[RawItem]:
        """検索を実行する。Tavily API → SDK WebSearch のフォールバック付き.

        Parameters
        ----------
        search_queries : list[dict[str, str]]
            LLM 生成の検索クエリリスト

        Returns
        -------
        list[RawItem]
            全検索結果の正規化アイテムリスト
        """
        # まず Tavily API を試行
        if self._key_pool and self._key_pool.has_keys():
            items = self._execute_via_tavily(search_queries)
            if items:
                return items
            logger.warning("Tavily returned 0 results, falling back to SDK")

        # フォールバック: SDK WebSearch
        return self._execute_via_sdk(search_queries)

    def _execute_via_tavily(
        self, search_queries: list[dict[str, str]]
    ) -> list[RawItem]:
        """Tavily REST API で検索を実行する."""
        all_items: list[RawItem] = []
        seen_urls: set[str] = set()

        for i, sq in enumerate(search_queries):
            query_text = sq.get("query", "")
            if not query_text:
                continue

            is_reddit = "reddit" in query_text.lower()
            include_domains = ["reddit.com"] if is_reddit else []

            try:
                items = self._tavily_search_with_rotation(
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

            for item in items:
                if item["url"] not in seen_urls:
                    seen_urls.add(item["url"])
                    all_items.append(item)

        return all_items

    def _execute_via_sdk(
        self, search_queries: list[dict[str, str]]
    ) -> list[RawItem]:
        """claude_agent_sdk (max_turns=10) で WebSearch を実行する.

        SdkLLMClient（max_turns=1）ではツール呼び出しできないため、
        専用の SDK セッションを起動する。
        """
        import asyncio

        try:
            import claude_agent_sdk
        except ImportError:
            logger.error("claude_agent_sdk not installed, cannot fallback")
            return []

        from creator_enrichment.config import ANTHROPIC_MODEL

        queries_text = "\n".join(
            f"- {sq['query']}" for sq in search_queries if sq.get("query")
        )
        prompt = (
            f"Execute web searches for ALL of the following queries "
            f"and return results as JSON.\n\n"
            f"Queries:\n{queries_text}\n\n"
            f"Return ONLY JSON: "
            f'{{\"items\": [{{\"url\": \"...\", \"title\": \"...\", '
            f'\"content\": \"...\", \"source\": \"web_search\"}}]}}'
        )

        saved_env = os.environ.pop("CLAUDECODE", None)

        options = claude_agent_sdk.ClaudeAgentOptions(
            system_prompt=_SEARCH_SYSTEM_PROMPT,
            model=ANTHROPIC_MODEL,
            max_turns=10,
            permission_mode="bypassPermissions",
        )

        async def _run() -> str:
            result_text = ""
            final_result: str | None = None
            try:
                async for msg in claude_agent_sdk.query(
                    prompt=prompt, options=options,
                ):
                    if hasattr(msg, "result"):
                        final_result = msg.result
                    if hasattr(msg, "content"):
                        for block in msg.content:  # type: ignore[union-attr]
                            if hasattr(block, "text"):
                                result_text += block.text  # type: ignore[union-attr]
            except (RuntimeError, GeneratorExit):
                pass
            return final_result if final_result else result_text

        try:
            response = asyncio.run(_run())
        except Exception as e:
            logger.error("SDK search failed: %s", e)
            return []
        finally:
            if saved_env is not None:
                os.environ["CLAUDECODE"] = saved_env

        cleaned = strip_json_codeblock(response)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.error("Failed to parse SDK search response")
            return []

        items_raw = parsed.get("items", [])
        if not isinstance(items_raw, list):
            return []

        seen_urls: set[str] = set()
        results: list[RawItem] = []
        for item in items_raw:
            url = str(item.get("url", ""))
            if url and url not in seen_urls:
                seen_urls.add(url)
                results.append(
                    RawItem(
                        url=url,
                        title=str(item.get("title", "")),
                        content=str(item.get("content", "")),
                        source=str(item.get("source", "web_search")),
                    )
                )
        return results

    def _tavily_search_with_rotation(
        self,
        query: str,
        include_domains: list[str] | None = None,
    ) -> list[RawItem]:
        """キーローテーション付きで Tavily REST API を呼び出す.

        432 エラー時にキーを除外して次のキーでリトライする。
        全キーが枯渇した場合は空リストを返す。
        """
        assert self._key_pool is not None

        while self._key_pool.has_keys():
            key = self._key_pool.get_key()
            if key is None:
                break

            payload: dict[str, Any] = {
                "api_key": key,
                "query": query,
                "max_results": _MAX_RESULTS_PER_QUERY,
                "include_raw_content": False,
            }
            if include_domains:
                payload["include_domains"] = include_domains

            response = httpx.post(
                _TAVILY_SEARCH_URL,
                json=payload,
                timeout=_TAVILY_TIMEOUT,
            )

            if response.status_code == _TAVILY_RATE_LIMIT_STATUS:
                self._key_pool.mark_exhausted(key)
                continue

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

        logger.warning("All Tavily API keys exhausted")
        return []
