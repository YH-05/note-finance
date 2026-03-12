"""ClaudeCodeProvider: Claude Code SDK-based LLM provider for pdf_pipeline.

Uses a lazy import pattern to load ``claude_agent_sdk`` only when an
operation is first invoked, avoiding hard import failures in environments
without the SDK.

Classes
-------
ClaudeCodeProvider
    LLM provider that delegates to the Claude Code SDK.

Examples
--------
>>> provider = ClaudeCodeProvider()
>>> isinstance(provider.is_available(), bool)
True
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

from pdf_pipeline._logging import get_logger
from pdf_pipeline.exceptions import LLMProviderError

logger = get_logger(__name__, module="claude_provider")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SDK_MODULE = "claude_agent_sdk"


# ---------------------------------------------------------------------------
# ClaudeCodeProvider class
# ---------------------------------------------------------------------------


class ClaudeCodeProvider:
    """LLM provider backed by the Claude Code SDK (lazy import).

    The ``claude_agent_sdk`` module is imported on first use rather than
    at module load time. This allows the class to be instantiated in
    environments that do not have the SDK installed, with ``is_available()``
    returning ``False`` in such environments.

    Attributes
    ----------
    _sdk_available : bool | None
        Cached result of the SDK availability check. ``None`` means
        the check has not been performed yet.

    Examples
    --------
    >>> provider = ClaudeCodeProvider()
    >>> isinstance(provider.is_available(), bool)
    True
    """

    def __init__(self) -> None:
        """Initialize ClaudeCodeProvider without importing the SDK.

        The SDK is loaded lazily on first method call. Instantiation
        always succeeds regardless of whether the SDK is installed.
        """
        self._sdk_available: bool | None = None
        self._sdk: Any | None = None
        logger.debug("ClaudeCodeProvider initialized (lazy import pending)")

    # -----------------------------------------------------------------------
    # LLMProvider Protocol implementation
    # -----------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check whether the Claude Code SDK is importable.

        Uses ``importlib.import_module`` to attempt the SDK import.
        The result is cached after the first call.

        Returns
        -------
        bool
            ``True`` if ``claude_agent_sdk`` can be imported; ``False`` otherwise.

        Examples
        --------
        >>> provider = ClaudeCodeProvider()
        >>> isinstance(provider.is_available(), bool)
        True
        """
        if self._sdk_available is not None:
            return self._sdk_available

        try:
            self._sdk = importlib.import_module(_SDK_MODULE)
            self._sdk_available = True
            logger.debug(
                "ClaudeCodeProvider SDK available",
                module=_SDK_MODULE,
            )
        except ImportError:
            self._sdk_available = False
            logger.warning(
                "ClaudeCodeProvider SDK not available",
                module=_SDK_MODULE,
            )

        return self._sdk_available

    def convert_pdf_to_markdown(self, pdf_path: str) -> str:
        """Convert a PDF file to Markdown using the Claude Code SDK.

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

        Examples
        --------
        >>> provider = ClaudeCodeProvider()
        >>> # result = provider.convert_pdf_to_markdown("report.pdf")
        """
        sdk = self._get_sdk()
        logger.debug(
            "Converting PDF to Markdown",
            provider="ClaudeCodeProvider",
            pdf_path=pdf_path,
        )
        try:
            result: str = sdk.convert_pdf_to_markdown(pdf_path)
        except Exception as exc:
            msg = f"ClaudeCodeProvider.convert_pdf_to_markdown failed: {exc}"
            logger.error(
                msg,
                provider="ClaudeCodeProvider",
                pdf_path=pdf_path,
                error=str(exc),
            )
            raise LLMProviderError(msg, provider="ClaudeCodeProvider") from exc

        logger.info(
            "ClaudeCodeProvider PDF conversion completed",
            pdf_path=pdf_path,
            output_length=len(result),
        )
        return result

    def extract_table_json(self, text: str) -> str:
        """Extract table data from text using the Claude Code SDK.

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
        sdk = self._get_sdk()
        logger.debug(
            "Extracting table JSON",
            provider="ClaudeCodeProvider",
            text_length=len(text),
        )
        try:
            result: str = sdk.extract_table_json(text)
        except Exception as exc:
            msg = f"ClaudeCodeProvider.extract_table_json failed: {exc}"
            logger.error(
                msg,
                provider="ClaudeCodeProvider",
                error=str(exc),
            )
            raise LLMProviderError(msg, provider="ClaudeCodeProvider") from exc

        logger.info(
            "ClaudeCodeProvider table extraction completed",
            output_length=len(result),
        )
        return result

    def extract_knowledge(self, text: str) -> str:
        """Extract knowledge graph data from text using the Claude Code SDK.

        Parameters
        ----------
        text : str
            Text from which to extract entities and relationships.

        Returns
        -------
        str
            JSON-encoded knowledge graph with entities and relations.

        Raises
        ------
        LLMProviderError
            If the SDK is unavailable or extraction fails.
        """
        sdk = self._get_sdk()
        logger.debug(
            "Extracting knowledge",
            provider="ClaudeCodeProvider",
            text_length=len(text),
        )
        try:
            result: str = sdk.extract_knowledge(text)
        except Exception as exc:
            msg = f"ClaudeCodeProvider.extract_knowledge failed: {exc}"
            logger.error(
                msg,
                provider="ClaudeCodeProvider",
                error=str(exc),
            )
            raise LLMProviderError(msg, provider="ClaudeCodeProvider") from exc

        logger.info(
            "ClaudeCodeProvider knowledge extraction completed",
            output_length=len(result),
        )
        return result

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _get_sdk(self) -> Any:
        """Get the loaded SDK module, raising LLMProviderError if unavailable.

        Triggers lazy import on first call.

        Returns
        -------
        Any
            The loaded ``claude_agent_sdk`` module.

        Raises
        ------
        LLMProviderError
            If the SDK is not available.
        """
        if not self.is_available() or self._sdk is None:
            msg = (
                "ClaudeCodeProvider is not available: "
                f"'{_SDK_MODULE}' cannot be imported"
            )
            logger.error(msg, provider="ClaudeCodeProvider")
            raise LLMProviderError(msg, provider="ClaudeCodeProvider")
        return self._sdk
