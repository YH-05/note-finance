"""GeminiCLIProvider: Gemini CLI-based LLM provider for pdf_pipeline.

Invokes the ``gemini`` command-line tool via ``subprocess.run`` for PDF
processing. Availability is determined by ``shutil.which('gemini')``.

Classes
-------
GeminiCLIProvider
    LLM provider that delegates to the Gemini CLI.

Examples
--------
>>> provider = GeminiCLIProvider()
>>> provider.is_available()  # True if `gemini` CLI is installed
True
"""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

from pdf_pipeline._logging import get_logger
from pdf_pipeline.exceptions import LLMProviderError

logger = get_logger(__name__, module="gemini_provider")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CLI_COMMAND = "gemini"
_SUBPROCESS_TIMEOUT = 300  # seconds


# ---------------------------------------------------------------------------
# GeminiCLIProvider class
# ---------------------------------------------------------------------------


class GeminiCLIProvider:
    """LLM provider that uses the Gemini CLI via subprocess.

    Uses ``shutil.which`` to check CLI availability and
    ``subprocess.run`` to execute extraction commands.

    Examples
    --------
    >>> provider = GeminiCLIProvider()
    >>> available = provider.is_available()
    >>> isinstance(available, bool)
    True
    """

    def is_available(self) -> bool:
        """Check whether the ``gemini`` CLI is available.

        Uses ``shutil.which`` to locate the binary in the system PATH.

        Returns
        -------
        bool
            ``True`` if the ``gemini`` command is found; ``False`` otherwise.

        Examples
        --------
        >>> provider = GeminiCLIProvider()
        >>> isinstance(provider.is_available(), bool)
        True
        """
        available = shutil.which(_CLI_COMMAND) is not None
        logger.debug(
            "GeminiCLIProvider availability check",
            command=_CLI_COMMAND,
            available=available,
        )
        return available

    def convert_pdf_to_markdown(self, pdf_path: str) -> str:
        """Convert a PDF file to Markdown using the Gemini CLI.

        Invokes ``gemini convert-pdf <pdf_path>`` as a subprocess.

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
            If the CLI command fails or is not found.

        Examples
        --------
        >>> provider = GeminiCLIProvider()
        >>> result = provider.convert_pdf_to_markdown("report.pdf")
        >>> isinstance(result, str)
        True
        """
        logger.debug(
            "Converting PDF to Markdown",
            provider="GeminiCLIProvider",
            pdf_path=pdf_path,
        )
        return self._run_command(
            [_CLI_COMMAND, "convert-pdf", pdf_path],
            operation="convert_pdf_to_markdown",
        )

    def extract_table_json(self, text: str) -> str:
        """Extract table data from text using the Gemini CLI.

        Pipes the input text to ``gemini extract-tables`` and returns
        JSON-encoded structured table data.

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
            If the CLI command fails.

        Examples
        --------
        >>> provider = GeminiCLIProvider()
        >>> result = provider.extract_table_json("table content here")
        >>> isinstance(result, str)
        True
        """
        logger.debug(
            "Extracting table JSON",
            provider="GeminiCLIProvider",
            text_length=len(text),
        )
        return self._run_command(
            [_CLI_COMMAND, "extract-tables"],
            operation="extract_table_json",
            input_text=text,
        )

    def extract_knowledge(self, text: str) -> str:
        """Extract knowledge graph entities and relations using the Gemini CLI.

        Pipes the input text to ``gemini extract-knowledge`` and returns
        JSON-encoded entities and relations.

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
            If the CLI command fails.

        Examples
        --------
        >>> provider = GeminiCLIProvider()
        >>> result = provider.extract_knowledge("Apple released iPhone")
        >>> isinstance(result, str)
        True
        """
        logger.debug(
            "Extracting knowledge",
            provider="GeminiCLIProvider",
            text_length=len(text),
        )
        return self._run_command(
            [_CLI_COMMAND, "extract-knowledge"],
            operation="extract_knowledge",
            input_text=text,
        )

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _run_command(
        self,
        cmd: list[str],
        *,
        operation: str,
        input_text: str | None = None,
    ) -> str:
        """Execute a subprocess command and return stdout.

        Parameters
        ----------
        cmd : list[str]
            Command and arguments to execute.
        operation : str
            Name of the calling operation (used in error messages).
        input_text : str | None
            Optional text to pipe to stdin.

        Returns
        -------
        str
            Standard output from the command.

        Raises
        ------
        LLMProviderError
            If the command fails (non-zero exit) or raises an OS-level error.
        """
        try:
            result = subprocess.run(
                cmd,
                input=input_text,
                capture_output=True,
                text=True,
                timeout=_SUBPROCESS_TIMEOUT,
                check=False,
            )
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
            msg = f"GeminiCLIProvider.{operation} failed: subprocess error: {exc}"
            logger.error(
                msg,
                provider="GeminiCLIProvider",
                operation=operation,
                error=str(exc),
            )
            raise LLMProviderError(msg, provider="GeminiCLIProvider") from exc

        if result.returncode != 0:
            msg = (
                f"GeminiCLIProvider.{operation} failed: "
                f"exit code {result.returncode}: {result.stderr}"
            )
            logger.error(
                msg,
                provider="GeminiCLIProvider",
                operation=operation,
                returncode=result.returncode,
                stderr=result.stderr,
            )
            raise LLMProviderError(msg, provider="GeminiCLIProvider")

        logger.info(
            "GeminiCLIProvider operation completed",
            operation=operation,
            output_length=len(result.stdout),
        )
        return result.stdout
