"""creator_enrichment Phase 2: ClaudeCodeSearcher.

Claude Code エージェントを使用して Web 検索を実行し、
Tavily / Reddit から取得した結果を ``RawItem[]`` に変換する。

``claude_agent_sdk`` パッケージの利用可否が不確定であるため、
``AgentProvider`` Protocol で抽象化し、差し替え可能な設計とする。

Usage
-----
::

    # provider を注入する場合
    searcher = ClaudeCodeSearcher(provider=my_provider)
    items = searcher.search(queries=["side hustle tips"], genre="career")

    # デフォルトプロバイダーを使用する場合（claude_agent_sdk 必須）
    searcher = ClaudeCodeSearcher()
    items = searcher.search(queries=["副業 始め方"], genre="career")
"""

from __future__ import annotations

import json
import logging
from typing import Protocol, runtime_checkable

import tenacity

from creator_enrichment.types import PhaseError, RawItem

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------
_TIMEOUT_SECONDS = 120
"""エージェント呼び出しのタイムアウト（秒）."""

_MAX_RETRY_ATTEMPTS = 3
"""最大リトライ回数."""

_RETRY_WAIT_BASE = 2
"""リトライ待機時間の基数（秒）。指数バックオフ: 2s -> 4s -> 8s."""

# ---------------------------------------------------------------------------
# システムプロンプト
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """\
You are a research assistant with access to MCP tools.
Use the following tools to search for information:

1. **tavily_search**: Execute web searches.
   - Run 3 English queries and 3 Japanese queries (6 total).
   - Each query should target different aspects of the topic.

2. **reddit**: Search Reddit for relevant discussions and experiences.
   - Search relevant subreddits for the given genre.

## Output format

Return ONLY a JSON object with the following structure (no markdown, no explanation):

{
  "items": [
    {
      "url": "https://...",
      "title": "Article or post title",
      "content": "Article content or summary text",
      "source": "tavily_search"
    }
  ]
}

The "source" field must be one of: "tavily_search", "reddit".
Include all results from all searches in a single "items" array.
Do NOT include any text before or after the JSON object.
"""

# ---------------------------------------------------------------------------
# AgentProvider Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class AgentProvider(Protocol):
    """Claude Code エージェントプロバイダーのプロトコル.

    ``query()`` メソッドを持つ任意のオブジェクトを受け付ける。
    テスト時にモック注入するためのダックタイピングインターフェース。
    """

    def query(self, *, system_prompt: str, prompt: str, timeout: int) -> str:
        """エージェントにクエリを送信し、テキストレスポンスを返す.

        Parameters
        ----------
        system_prompt : str
            システムプロンプト
        prompt : str
            ユーザープロンプト
        timeout : int
            タイムアウト（秒）

        Returns
        -------
        str
            エージェントのテキストレスポンス
        """
        ...


# ---------------------------------------------------------------------------
# ClaudeCodeSearcher
# ---------------------------------------------------------------------------
class ClaudeCodeSearcher:
    """Claude Code エージェント経由で Web 検索を実行する.

    Parameters
    ----------
    provider : AgentProvider | None
        エージェントプロバイダー。None の場合は ``claude_agent_sdk`` から
        デフォルトプロバイダーをロードする。

    Raises
    ------
    RuntimeError
        provider=None かつ ``claude_agent_sdk`` 未インストールの場合
    """

    def __init__(self, provider: AgentProvider | None = None) -> None:
        self._provider = provider or self._load_default_provider()
        logger.info("ClaudeCodeSearcher initialized")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def search(self, queries: list[str], genre: str) -> list[RawItem]:
        """検索クエリを実行し RawItem リストを返す.

        Parameters
        ----------
        queries : list[str]
            検索クエリのリスト
        genre : str
            対象ジャンル（career / beauty-romance / spiritual）

        Returns
        -------
        list[RawItem]
            検索結果の正規化アイテムリスト

        Raises
        ------
        PhaseError
            リトライ上限超過・タイムアウト・パースエラー時
        """
        logger.info(
            "Search started: genre=%s, query_count=%d",
            genre,
            len(queries),
        )

        try:
            raw_response = self._call_with_retry(queries=queries, genre=genre)
        except TimeoutError as e:
            logger.error("Search timed out: %s", e)
            raise PhaseError(f"Search failed: {e}") from e
        except tenacity.RetryError as e:
            last_exc = e.last_attempt.exception() if e.last_attempt else None
            original: Exception = last_exc if isinstance(last_exc, Exception) else e
            logger.error("Search failed after retries: %s", original)
            raise PhaseError(f"Search failed after retries: {original}") from e
        except (RuntimeError, OSError) as e:
            # reraise=True の場合、tenacity は元の例外を直接 re-raise する
            logger.error("Search failed after retries: %s", e)
            raise PhaseError(f"Search failed: {e}") from e

        try:
            items = self._parse_response(raw_response)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            logger.error("Failed to parse search response: %s", e)
            raise PhaseError(f"Search failed: {e}") from e

        logger.info("Search completed: %d items found", len(items))
        return items

    # ------------------------------------------------------------------
    # Private: リトライ付きエージェント呼び出し
    # ------------------------------------------------------------------
    @tenacity.retry(
        stop=tenacity.stop_after_attempt(_MAX_RETRY_ATTEMPTS),
        wait=tenacity.wait_exponential(multiplier=_RETRY_WAIT_BASE, max=16),
        retry=tenacity.retry_if_exception_type((RuntimeError, OSError)),
        reraise=True,
    )
    def _call_with_retry(self, *, queries: list[str], genre: str) -> str:
        """リトライ付きでエージェントを呼び出す.

        Parameters
        ----------
        queries : list[str]
            検索クエリリスト
        genre : str
            対象ジャンル

        Returns
        -------
        str
            エージェントのテキストレスポンス

        Raises
        ------
        TimeoutError
            タイムアウト時
        RuntimeError
            エージェント呼び出しエラー時（リトライ対象）
        """
        prompt = self._build_user_prompt(queries, genre)

        logger.debug(
            "Calling agent: genre=%s, timeout=%ds",
            genre,
            _TIMEOUT_SECONDS,
        )

        return self._provider.query(
            system_prompt=_SYSTEM_PROMPT,
            prompt=prompt,
            timeout=_TIMEOUT_SECONDS,
        )

    # ------------------------------------------------------------------
    # Private: レスポンスパース
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_response(raw_response: str) -> list[RawItem]:
        """エージェントレスポンスをパースし RawItem リストに変換する.

        ```json ... ``` コードブロックラッピングにも対応する。

        Parameters
        ----------
        raw_response : str
            エージェントのテキストレスポンス

        Returns
        -------
        list[RawItem]
            パースされた RawItem リスト

        Raises
        ------
        json.JSONDecodeError
            JSON パースに失敗した場合
        KeyError
            ``items`` キーが存在しない場合
        TypeError
            ``items`` がリストでない場合
        ValueError
            ``items`` キーが存在しないか不正な型の場合
        """
        text = raw_response.strip()

        # ```json ... ``` コードブロックを除去
        if text.startswith("```"):
            lines = text.split("\n")
            json_lines: list[str] = []
            in_block = False
            for line in lines:
                if line.startswith("```") and not in_block:
                    in_block = True
                    continue
                if line.startswith("```") and in_block:
                    break
                if in_block:
                    json_lines.append(line)
            text = "\n".join(json_lines)

        parsed = json.loads(text)

        if "items" not in parsed:
            raise ValueError("Response JSON missing 'items' key")

        items_raw = parsed["items"]
        if not isinstance(items_raw, list):
            raise TypeError(
                f"Expected 'items' to be a list, got {type(items_raw).__name__}"
            )

        result: list[RawItem] = []
        for item in items_raw:
            result.append(
                RawItem(
                    url=str(item.get("url", "")),
                    title=str(item.get("title", "")),
                    content=str(item.get("content", "")),
                    source=str(item.get("source", "")),
                )
            )

        return result

    # ------------------------------------------------------------------
    # Private: プロンプト構築
    # ------------------------------------------------------------------
    @staticmethod
    def _build_user_prompt(queries: list[str], genre: str) -> str:
        """検索用のユーザープロンプトを構築する.

        Parameters
        ----------
        queries : list[str]
            検索クエリリスト
        genre : str
            対象ジャンル

        Returns
        -------
        str
            構築されたユーザープロンプト
        """
        queries_text = "\n".join(f"- {q}" for q in queries)
        return (
            f"Genre: {genre}\n\n"
            f"Search queries:\n{queries_text}\n\n"
            "Execute tavily_search for each query (EN 3 + JP 3) "
            "and reddit search for relevant subreddits. "
            "Return all results as a single JSON object."
        )

    # ------------------------------------------------------------------
    # Private: デフォルトプロバイダーロード
    # ------------------------------------------------------------------
    @staticmethod
    def _load_default_provider() -> AgentProvider:
        """claude_agent_sdk からデフォルトプロバイダーをロードする.

        Returns
        -------
        AgentProvider
            SDK ラッパープロバイダー

        Raises
        ------
        RuntimeError
            claude_agent_sdk が未インストールの場合
        """
        try:
            import claude_agent_sdk

            class _SdkProvider:
                """claude_agent_sdk.query() をラップするプロバイダー."""

                def query(
                    self, *, system_prompt: str, prompt: str, timeout: int
                ) -> str:
                    import asyncio

                    options = claude_agent_sdk.ClaudeAgentOptions(
                        system_prompt=system_prompt,
                        max_turns=1,
                    )
                    full_prompt = f"{system_prompt}\n\n{prompt}"

                    async def _run() -> str:
                        result_text = ""
                        async for msg in claude_agent_sdk.query(
                            prompt=full_prompt,
                            options=options,
                        ):
                            if hasattr(msg, "content"):
                                for block in msg.content:  # type: ignore[union-attr]
                                    if hasattr(block, "text"):
                                        result_text += block.text  # type: ignore[union-attr]
                        return result_text

                    return asyncio.run(_run())

            logger.info("Default provider loaded from claude_agent_sdk")
            return _SdkProvider()
        except ImportError:
            msg = (
                "claude_agent_sdk not installed. "
                "Install with: uv add --optional automation claude-agent-sdk"
            )
            logger.error(msg)
            raise RuntimeError(msg) from None
