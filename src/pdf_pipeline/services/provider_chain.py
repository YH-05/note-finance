"""ProviderChain: ordered fallback chain for LLM providers.

Manages a sequence of LLMProvider instances and attempts each one in order.
Skips unavailable providers and falls back to the next on failure.
Raises ``LLMProviderError`` if all providers are exhausted.

Classes
-------
ProviderChain
    Ordered fallback chain for LLMProvider implementations.

Examples
--------
>>> from pdf_pipeline.services.gemini_provider import GeminiCLIProvider
>>> from pdf_pipeline.services.claude_provider import ClaudeCodeProvider
>>> chain = ProviderChain([GeminiCLIProvider(), ClaudeCodeProvider()])
>>> isinstance(chain.is_available(), bool)
True
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from pdf_pipeline._logging import get_logger
from pdf_pipeline.exceptions import LLMProviderError

if TYPE_CHECKING:
    from pdf_pipeline.services.llm_provider import LLMProvider

logger = get_logger(__name__, module="provider_chain")

# ---------------------------------------------------------------------------
# ProviderChain class
# ---------------------------------------------------------------------------


class ProviderChain:
    """Ordered fallback chain for LLM provider implementations.

    Tries each provider in the supplied sequence until one succeeds.
    Providers that report ``is_available() == False`` are skipped entirely.
    Providers that raise ``LLMProviderError`` during an operation trigger
    a fallback to the next provider.

    When all providers are exhausted (either unavailable or failed), a
    ``LLMProviderError`` with the message ``"All providers failed"`` is raised.

    Parameters
    ----------
    providers : list[LLMProvider]
        Ordered list of providers to try. Must be non-empty.

    Raises
    ------
    ValueError
        If ``providers`` is empty.

    Examples
    --------
    >>> from unittest.mock import MagicMock
    >>> p1, p2 = MagicMock(), MagicMock()
    >>> p1.is_available.return_value = False
    >>> p2.is_available.return_value = True
    >>> p2.convert_pdf_to_markdown.return_value = "# Result"
    >>> chain = ProviderChain([p1, p2])
    >>> chain.convert_pdf_to_markdown("report.pdf")
    '# Result'
    """

    def __init__(self, providers: list[LLMProvider]) -> None:
        """Initialize ProviderChain with an ordered list of providers.

        Parameters
        ----------
        providers : list[LLMProvider]
            Non-empty list of LLMProvider instances.

        Raises
        ------
        ValueError
            If ``providers`` is empty.
        """
        if not providers:
            msg = "providers must not be empty"
            logger.error(msg)
            raise ValueError(msg)

        self.providers = list(providers)
        logger.debug(
            "ProviderChain initialized",
            provider_count=len(self.providers),
        )

    # -----------------------------------------------------------------------
    # LLMProvider Protocol implementation
    # -----------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check whether at least one provider in the chain is available.

        Returns
        -------
        bool
            ``True`` if any provider reports ``is_available() == True``;
            ``False`` if all providers are unavailable.

        Examples
        --------
        >>> chain = ProviderChain([p1, p2])
        >>> isinstance(chain.is_available(), bool)
        True
        """
        available = any(p.is_available() for p in self.providers)
        logger.debug(
            "ProviderChain availability",
            available=available,
            provider_count=len(self.providers),
        )
        return available

    def convert_pdf_to_markdown(self, pdf_path: str) -> str:
        """Convert a PDF to Markdown, trying providers in order.

        Parameters
        ----------
        pdf_path : str
            Absolute or relative path to the PDF file.

        Returns
        -------
        str
            Markdown-formatted text from the first succeeding provider.

        Raises
        ------
        LLMProviderError
            If all providers fail or are unavailable.

        Examples
        --------
        >>> chain = ProviderChain([gemini, claude])
        >>> result = chain.convert_pdf_to_markdown("report.pdf")
        >>> isinstance(result, str)
        True
        """
        return self._try_providers(
            operation="convert_pdf_to_markdown",
            invoke=lambda p: p.convert_pdf_to_markdown(pdf_path),
        )

    def extract_table_json(self, text: str) -> str:
        """Extract table data from text, trying providers in order.

        Parameters
        ----------
        text : str
            Text containing table data to extract.

        Returns
        -------
        str
            JSON-encoded table data from the first succeeding provider.

        Raises
        ------
        LLMProviderError
            If all providers fail or are unavailable.
        """
        return self._try_providers(
            operation="extract_table_json",
            invoke=lambda p: p.extract_table_json(text),
        )

    def extract_knowledge(self, text: str) -> str:
        """Extract knowledge graph data from text, trying providers in order.

        Parameters
        ----------
        text : str
            Text from which to extract entities and relationships.

        Returns
        -------
        str
            JSON-encoded knowledge graph from the first succeeding provider.

        Raises
        ------
        LLMProviderError
            If all providers fail or are unavailable.
        """
        return self._try_providers(
            operation="extract_knowledge",
            invoke=lambda p: p.extract_knowledge(text),
        )

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _try_providers(
        self,
        *,
        operation: str,
        invoke: Callable[[LLMProvider], str],
    ) -> str:
        """Attempt an operation on each provider in order.

        Skips providers where ``is_available()`` returns ``False``.
        Falls back to the next provider on ``LLMProviderError``.

        Parameters
        ----------
        operation : str
            Human-readable operation name for logging and error messages.
        invoke : Callable[[LLMProvider], str]
            Callable that accepts a provider and executes the operation.

        Returns
        -------
        str
            Result from the first provider that succeeds.

        Raises
        ------
        LLMProviderError
            If all providers in the chain fail or are unavailable.
        """
        errors: list[str] = []

        for i, provider in enumerate(self.providers):
            provider_name = type(provider).__name__

            if not provider.is_available():
                logger.debug(
                    "Skipping unavailable provider",
                    provider=provider_name,
                    operation=operation,
                    index=i,
                )
                errors.append(f"{provider_name}: unavailable")
                continue

            try:
                logger.debug(
                    "Trying provider",
                    provider=provider_name,
                    operation=operation,
                    index=i,
                )
                result = invoke(provider)
                logger.info(
                    "Provider succeeded",
                    provider=provider_name,
                    operation=operation,
                )
                return result
            except LLMProviderError as exc:
                logger.warning(
                    "Provider failed, trying next",
                    provider=provider_name,
                    operation=operation,
                    error=str(exc),
                )
                errors.append(f"{provider_name}: {exc}")

        msg = (
            f"All providers failed for operation '{operation}'. "
            f"Errors: {'; '.join(errors)}"
        )
        logger.error(
            msg,
            operation=operation,
            provider_count=len(self.providers),
            errors=errors,
        )
        raise LLMProviderError(msg, provider="ProviderChain")
