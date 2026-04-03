"""ClaudeCodeProvider: Claude Agent SDK-based LLM provider for pdf_pipeline.

Uses ``claude_agent_sdk.query()`` to invoke a separate Claude Code process
for LLM operations. Clears the ``CLAUDECODE`` env var to allow nested
invocation from within a running Claude Code session.

Classes
-------
ClaudeCodeProvider
    LLM provider that delegates to the Claude Agent SDK.

Examples
--------
>>> provider = ClaudeCodeProvider()
>>> isinstance(provider.is_available(), bool)
True
"""

from __future__ import annotations

import asyncio
import importlib
import re
from typing import Any

from pdf_pipeline._logging import get_logger
from pdf_pipeline.exceptions import LLMProviderError

logger = get_logger(__name__, module="claude_provider")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SDK_MODULE = "claude_agent_sdk"

_SYSTEM_PROMPT = "Output ONLY valid JSON. No explanation, commentary, or code fences."

_KNOWLEDGE_EXTRACTION_SYSTEM_PROMPT = """\
You are a financial knowledge extraction engine. Extract entities, facts, claims, \
and financial data points from the provided financial text. Output ONLY valid JSON.

Output format:
{
  "entities": [{"name": "...", "entity_type": "company|index|sector|indicator|currency|commodity|person|organization|country|instrument", "ticker": null, "aliases": []}],
  "facts": [{"content": "...", "fact_type": "statistic|event|data_point|quote|policy_action|economic_indicator|regulatory|corporate_action", "as_of_date": null, "about_entities": ["..."]}],
  "claims": [{"content": "...", "claim_type": "opinion|prediction|recommendation|analysis|assumption|guidance|risk_assessment|policy_stance|sector_view|forecast", "sentiment": "bullish|bearish|neutral|mixed", "magnitude": "strong|moderate|slight", "target_price": null, "rating": null, "time_horizon": null, "about_entities": ["..."]}],
  "financial_datapoints": [{"metric_name": "...", "value": 0.0, "unit": "USD mn", "is_estimate": false, "currency": null, "period_label": null, "about_entities": ["..."]}],
  "stances": [{"author_name": "...", "author_type": "person|sell_side", "organization": null, "entity_name": "...", "rating": null, "sentiment": null, "target_price": null, "target_price_currency": null, "as_of_date": null, "based_on_claims": []}],
  "causal_links": [{"from_type": "fact|claim|datapoint", "from_content": "...", "to_type": "fact|claim|datapoint", "to_content": "...", "mechanism": null, "confidence": null}],
  "questions": [{"content": "...", "question_type": "data_gap|contradiction|prediction_test|assumption_check|consensus_divergence", "priority": null, "about_entities": [], "motivated_by_contents": []}]
}

Rules:
- Output ONLY valid JSON. No explanation, commentary, or code fences.
- Extract ALL entities mentioned.
- Separate facts (verifiable data) from claims (opinions/predictions).
- For financial_datapoints: extract structured numerical data. Set is_estimate=true for forecasts.
- For stances: extract analyst investment stances (rating + target price + sentiment).
- For causal_links: identify cause-effect relationships using exact content strings.
- For questions: identify knowledge gaps (data_gap, contradiction, prediction_test, assumption_check, consensus_divergence).
"""

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?", re.MULTILINE)
_CODE_FENCE_END_RE = re.compile(r"\n?```\s*$", re.MULTILINE)


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences from LLM output."""
    result = _CODE_FENCE_RE.sub("", text)
    result = _CODE_FENCE_END_RE.sub("", result)
    return result.strip()


# ---------------------------------------------------------------------------
# ClaudeCodeProvider class
# ---------------------------------------------------------------------------


class ClaudeCodeProvider:
    """LLM provider backed by the Claude Agent SDK.

    Uses ``claude_agent_sdk.query()`` to spawn a Claude Code subprocess
    for each LLM call. The ``CLAUDECODE`` env var is cleared to permit
    nested invocation from within an existing Claude Code session.

    Attributes
    ----------
    _sdk_available : bool | None
        Cached result of the SDK availability check.
    _model : str
        Model to use for LLM calls. Defaults to ``"haiku"``.

    Examples
    --------
    >>> provider = ClaudeCodeProvider()
    >>> isinstance(provider.is_available(), bool)
    True
    """

    def __init__(self, *, model: str = "haiku") -> None:
        """Initialize ClaudeCodeProvider.

        Parameters
        ----------
        model : str
            Model name for SDK queries. Defaults to ``"haiku"``.
        """
        self._sdk_available: bool | None = None
        self._sdk: Any | None = None
        self._model = model
        logger.debug(
            "ClaudeCodeProvider initialized",
            model=model,
        )

    # -----------------------------------------------------------------------
    # LLMProvider Protocol implementation
    # -----------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check whether the Claude Agent SDK is importable.

        Returns
        -------
        bool
            ``True`` if ``claude_agent_sdk`` can be imported.
        """
        if self._sdk_available is not None:
            return self._sdk_available

        try:
            self._sdk = importlib.import_module(_SDK_MODULE)
            self._sdk_available = True
            logger.debug("ClaudeCodeProvider SDK available", module=_SDK_MODULE)
        except ImportError:
            self._sdk_available = False
            logger.warning("ClaudeCodeProvider SDK not available", module=_SDK_MODULE)

        return self._sdk_available

    def convert_pdf_to_markdown(self, pdf_path: str) -> str:
        """Convert a PDF file to Markdown using the Claude Agent SDK.

        Parameters
        ----------
        pdf_path : str
            Absolute or relative path to the PDF file.

        Returns
        -------
        str
            Markdown-formatted text extracted from the PDF.

        Raises
        ------
        LLMProviderError
            If the SDK is unavailable or the conversion fails.
        """
        prompt = (
            f"Read the PDF file at {pdf_path} and convert it to structured Markdown. "
            "Preserve document structure, tables, and all numerical values. "
            "Remove headers, footers, page numbers, and legal boilerplate. "
            "Output ONLY the Markdown content."
        )
        return self._query_sdk(
            prompt=prompt,
            operation="convert_pdf_to_markdown",
            system_prompt="Output ONLY Markdown content. No explanation or commentary.",
            tools=["Read"],
        )

    def extract_table_json(self, text: str) -> str:
        """Extract table data from text using the Claude Agent SDK.

        Parameters
        ----------
        text : str
            Text containing table data to extract.

        Returns
        -------
        str
            JSON-encoded table data.

        Raises
        ------
        LLMProviderError
            If the SDK is unavailable or extraction fails.
        """
        prompt = (
            "Extract all tables from the following text as a JSON array. "
            'Each table: {"headers": [...], "rows": [...], "caption": ...}. '
            f"Text:\n{text}"
        )
        return self._query_sdk(prompt=prompt, operation="extract_table_json")

    def extract_knowledge(self, text: str) -> str:
        """Extract knowledge graph data from text using the Claude Agent SDK.

        Parameters
        ----------
        text : str
            Financial text from which to extract entities, facts, claims,
            and financial data points.

        Returns
        -------
        str
            JSON-encoded knowledge graph.

        Raises
        ------
        LLMProviderError
            If the SDK is unavailable or extraction fails.
        """
        return self._query_sdk(
            prompt=text,
            operation="extract_knowledge",
            system_prompt=_KNOWLEDGE_EXTRACTION_SYSTEM_PROMPT,
        )

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _query_sdk(
        self,
        *,
        prompt: str,
        operation: str,
        system_prompt: str = _SYSTEM_PROMPT,
        tools: list[str] | None = None,
    ) -> str:
        """Execute a query via ``claude_agent_sdk.query()``.

        Spawns a Claude Code subprocess with nested-session env vars
        cleared. Collects ``TextBlock`` content from ``AssistantMessage``
        responses.

        Parameters
        ----------
        prompt : str
            The prompt to send.
        operation : str
            Name of the calling operation (for logging/errors).
        system_prompt : str
            System prompt for the SDK session.
        tools : list[str] | None
            Tools to make available. Defaults to empty (no tools).

        Returns
        -------
        str
            Concatenated text output from the model.

        Raises
        ------
        LLMProviderError
            If the SDK is unavailable or the query fails.
        """
        sdk = self._get_sdk()
        logger.debug(
            "SDK query starting",
            provider="ClaudeCodeProvider",
            operation=operation,
            prompt_length=len(prompt),
        )

        try:
            result = asyncio.run(
                self._async_query(
                    sdk=sdk,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    tools=tools or [],
                )
            )
        except Exception as exc:
            msg = f"ClaudeCodeProvider.{operation} failed: {exc}"
            logger.error(
                msg,
                provider="ClaudeCodeProvider",
                operation=operation,
                error=str(exc),
            )
            raise LLMProviderError(msg, provider="ClaudeCodeProvider") from exc

        cleaned = _strip_code_fences(result)

        logger.info(
            "ClaudeCodeProvider operation completed",
            operation=operation,
            output_length=len(cleaned),
        )
        return cleaned

    @staticmethod
    async def _async_query(
        *,
        sdk: Any,
        prompt: str,
        system_prompt: str,
        tools: list[str],
    ) -> str:
        """Run an async SDK query and collect text output."""
        opts = sdk.ClaudeAgentOptions(
            max_turns=1,
            permission_mode="bypassPermissions",
            system_prompt=system_prompt,
            tools=tools if tools else [],
            model="haiku",
            env={
                # Clear nested-session detection vars
                "CLAUDECODE": "",
                "CLAUDE_CODE_ENTRYPOINT": "sdk-py",
            },
            setting_sources=[],
        )

        texts: list[str] = []
        # Consume the entire async iterator to avoid GeneratorExit
        # cleanup issues with the subprocess transport.
        async for msg in sdk.query(prompt=prompt, options=opts):
            if isinstance(msg, sdk.AssistantMessage):
                for block in msg.content:
                    if isinstance(block, sdk.TextBlock):
                        texts.append(block.text)

        return "".join(texts)

    def _get_sdk(self) -> Any:
        """Get the loaded SDK module, raising LLMProviderError if unavailable."""
        if not self.is_available() or self._sdk is None:
            msg = (
                "ClaudeCodeProvider is not available: "
                f"'{_SDK_MODULE}' cannot be imported"
            )
            logger.error(msg, provider="ClaudeCodeProvider")
            raise LLMProviderError(msg, provider="ClaudeCodeProvider")
        return self._sdk
