"""LLM抽出: raw_text から Fact/Entity/Claim/Topic を抽出する.

claude_agent_sdk 経由で Claude Haiku を呼び出す。
ANTHROPIC_API_KEY 不要（Claude Code CLI の認証を使用）。

抽出結果は build_from_extracted() の入力形式に変換される。
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from data_pipeline.collectors.base import CollectedItem

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_MAX_TEXT_LENGTH = 8000
_MAX_RETRIES = 2

_SYSTEM_PROMPT = "Return only JSON. No markdown fences, no explanation."

_EXTRACTION_PROMPT = """\
あなたは金融データ抽出の専門家です。以下のテキストから構造化情報を抽出してください。

## 入力テキスト

タイトル: {title}
ソースURL: {url}
言語: {language}

{text}

## 出力形式

以下のJSON形式で出力してください:

{{
  "facts": [
    {{
      "content": "検証可能な事実の記述",
      "fact_type": "financial_metric | operational_kpi | market_event | regulatory | economic_indicator | general",
      "confidence": 0.0-1.0,
      "about_entities": [{{"name": "エンティティ名", "entity_type": "company | person | index | currency | commodity | organization | country | sector | product | metric"}}]
    }}
  ],
  "claims": [
    {{
      "content": "意見・予測・分析の記述",
      "claim_type": "analyst_opinion | analyst_forecast | market_consensus | policy_expectation | risk_assessment",
      "sentiment": "positive | negative | neutral",
      "about_entities": [{{"name": "エンティティ名", "entity_type": "..."}}]
    }}
  ],
  "topics": [
    {{
      "name": "トピック名",
      "category": "equity | macro | fixed_income | sector | commodity | fx | crypto | regulation | technology | general"
    }}
  ]
}}

## ルール

- facts: 検証可能な事実（数値データ、イベント、公式発表）を3-10件抽出
- claims: 意見・予測・分析的判断を0-5件抽出
- topics: 記事のカテゴリを1-3件
- 日本語テキストのエンティティは日本語のまま抽出
- 実質的な情報のみ抽出し、定型文やボイラープレートは無視"""


# ---------------------------------------------------------------------------
# LLM Client Protocol（creator_enrichment と同一パターン）
# ---------------------------------------------------------------------------


@runtime_checkable
class LLMClient(Protocol):
    """LLM クエリのプロトコル."""

    def query(self, prompt: str) -> str: ...


class SdkLLMClient:
    """claude_agent_sdk を使用する LLM クライアント.

    Claude Code CLI の認証を使用するため、ANTHROPIC_API_KEY は不要。
    """

    def __init__(self, *, model: str = _DEFAULT_MODEL) -> None:
        self.model = model

    def query(self, prompt: str) -> str:
        """claude_agent_sdk 経由でプロンプトを送信する."""
        import asyncio
        import os

        try:
            import claude_agent_sdk
        except ImportError:
            msg = "claude_agent_sdk not installed. Run: uv sync --extra automation"
            logger.error(msg)
            raise RuntimeError(msg) from None

        saved_env = os.environ.pop("CLAUDECODE", None)

        options = claude_agent_sdk.ClaudeAgentOptions(
            system_prompt=_SYSTEM_PROMPT,
            model=self.model,
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
                        final_result = msg.result  # type: ignore[union-attr]
                    if hasattr(msg, "content"):
                        for block in msg.content:  # type: ignore[union-attr]
                            if hasattr(block, "text"):
                                result_text += block.text  # type: ignore[union-attr]
            except (RuntimeError, GeneratorExit):
                pass
            return final_result or result_text

        try:
            return asyncio.run(_run())
        finally:
            if saved_env is not None:
                os.environ["CLAUDECODE"] = saved_env


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------


class LlmExtractor:
    """Claude Haiku を使った Fact/Entity/Claim 抽出器.

    Parameters
    ----------
    llm_client : LLMClient | None
        LLMクライアント。None の場合は SdkLLMClient を使用。
        テスト時はモックを注入する。
    max_text_length : int
        入力テキストの最大文字数。
    request_delay : float
        API呼び出し間隔（秒）。

    Examples
    --------
    >>> extractor = LlmExtractor()
    >>> result = extractor.extract_one(item)
    >>> print(result["facts"])

    >>> # テスト時
    >>> class MockLLM:
    ...     def query(self, prompt: str) -> str:
    ...         return '{"facts": [], "claims": [], "topics": []}'
    >>> extractor = LlmExtractor(llm_client=MockLLM())
    """

    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        max_text_length: int = _MAX_TEXT_LENGTH,
        request_delay: float = 0.5,
    ) -> None:
        self.llm_client = llm_client or SdkLLMClient()
        self.max_text_length = max_text_length
        self.request_delay = request_delay

    def extract_one(self, item: CollectedItem) -> dict[str, Any]:
        """1つの CollectedItem から Fact/Claim/Topic を抽出する.

        Returns
        -------
        dict
            {"facts": [...], "claims": [...], "topics": [...]}
        """
        if not item.raw_text.strip():
            return _empty_result()

        text = item.raw_text[: self.max_text_length]
        prompt = _EXTRACTION_PROMPT.format(
            title=item.title,
            url=item.url,
            language=item.language or "unknown",
            text=text,
        )

        for attempt in range(_MAX_RETRIES + 1):
            try:
                raw = self.llm_client.query(prompt)
                return _parse_response(raw)
            except Exception as e:
                logger.warning(
                    "LLM extraction failed (attempt %d/%d): %s",
                    attempt + 1,
                    _MAX_RETRIES + 1,
                    e,
                )
                if attempt < _MAX_RETRIES:
                    time.sleep(2 * (attempt + 1))
                    continue
                return _empty_result()

        return _empty_result()

    def extract_many(
        self,
        items: list[CollectedItem],
    ) -> list[dict[str, Any]]:
        """複数の CollectedItem から一括抽出する.

        Parameters
        ----------
        items : list[CollectedItem]
            抽出対象のアイテムリスト。

        Returns
        -------
        list[dict]
            各アイテムの抽出結果。items と同じ長さ。
        """
        results: list[dict[str, Any]] = []
        for i, item in enumerate(items):
            if i > 0:
                time.sleep(self.request_delay)
            logger.info(
                "Extracting %d/%d: %s",
                i + 1,
                len(items),
                item.title[:50],
            )
            result = self.extract_one(item)
            logger.info(
                "  facts=%d, claims=%d, topics=%d",
                len(result["facts"]),
                len(result["claims"]),
                len(result["topics"]),
            )
            results.append(result)
        return results


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _empty_result() -> dict[str, Any]:
    """空の抽出結果を返す."""
    return {"facts": [], "claims": [], "topics": []}


def _parse_response(raw: str) -> dict[str, Any]:
    """LLM応答をパースする."""
    text = raw.strip()
    # JSON fences を除去
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM response as JSON: %s", text[:200])
        return _empty_result()

    facts = data.get("facts", [])
    claims = data.get("claims", [])
    topics = data.get("topics", [])

    # デフォルト値の補完
    for f in facts:
        f.setdefault("about_entities", [])
        f.setdefault("confidence", 0.8)
        f.setdefault("fact_type", "general")

    for c in claims:
        c.setdefault("about_entities", [])
        c.setdefault("sentiment", "neutral")
        c.setdefault("claim_type", "analyst_opinion")

    return {"facts": facts, "claims": claims, "topics": topics}
