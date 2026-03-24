"""creator_enrichment 共通 LLM クライアント.

claude_agent_sdk を使用して LLM にクエリを送信する共通インターフェース。
ANTHROPIC_API_KEY 不要で Claude Code CLI の認証を使用する。

Usage
-----
::

    # デフォルト（claude_agent_sdk 経由）
    client = SdkLLMClient()
    response = client.query("JSONで返してください: ...")

    # テスト時はモック注入
    class MockClient:
        def query(self, prompt: str) -> str:
            return '{"result": "ok"}'

    extractor = ContentExtractor(llm_client=MockClient())
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------
@runtime_checkable
class LLMClient(Protocol):
    """LLM クエリのプロトコル.

    ``query(prompt)`` メソッドを持つ任意のオブジェクトを受け付ける。
    テスト時にモック注入するためのダックタイピングインターフェース。
    """

    def query(self, prompt: str) -> str:
        """プロンプトを送信しテキストレスポンスを返す.

        Parameters
        ----------
        prompt : str
            ユーザープロンプト

        Returns
        -------
        str
            LLM のテキストレスポンス
        """
        ...


# ---------------------------------------------------------------------------
# SDK 実装
# ---------------------------------------------------------------------------
class SdkLLMClient:
    """claude_agent_sdk を使用する LLM クライアント.

    Claude Code CLI の認証を使用するため、ANTHROPIC_API_KEY は不要。
    ツール呼び出しなしの単純なプロンプト→テキスト応答に特化。
    """

    def query(self, prompt: str) -> str:
        """claude_agent_sdk 経由でプロンプトを送信する.

        Parameters
        ----------
        prompt : str
            ユーザープロンプト

        Returns
        -------
        str
            LLM のテキストレスポンス

        Raises
        ------
        RuntimeError
            SDK 未インストールまたは実行エラー時
        """
        import asyncio
        import os

        try:
            import claude_agent_sdk
        except ImportError:
            msg = "claude_agent_sdk not installed"
            logger.error(msg)
            raise RuntimeError(msg) from None

        from creator_enrichment.config import ANTHROPIC_MODEL

        # ネストセッション回避
        saved_env = os.environ.pop("CLAUDECODE", None)

        options = claude_agent_sdk.ClaudeAgentOptions(
            system_prompt="Return only JSON. No markdown, no explanation.",
            model=ANTHROPIC_MODEL,
            max_turns=1,
            permission_mode="bypassPermissions",
        )

        async def _run() -> str:
            result_text = ""
            final_result: str | None = None
            try:
                async for msg in claude_agent_sdk.query(
                    prompt=prompt,
                    options=options,
                ):
                    if hasattr(msg, "result"):
                        final_result = msg.result
                    if hasattr(msg, "content"):
                        for block in msg.content:  # type: ignore[union-attr]
                            if hasattr(block, "text"):
                                result_text += block.text  # type: ignore[union-attr]
            except (RuntimeError, GeneratorExit):
                pass  # SDK cleanup エラーを許容

            if final_result:
                return final_result
            return result_text

        try:
            return asyncio.run(_run())
        finally:
            if saved_env is not None:
                os.environ["CLAUDECODE"] = saved_env
