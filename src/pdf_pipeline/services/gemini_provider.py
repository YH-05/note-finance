"""GeminiCLIProvider: Gemini CLI-based LLM provider for pdf_pipeline.

Invokes the ``gemini`` command-line tool via ``subprocess.run`` for PDF
processing. Uses ``--prompt`` for non-interactive mode and ``--file`` to
attach PDF files. Availability is determined by ``shutil.which('gemini')``.

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

import re
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from pdf_pipeline._logging import get_logger
from pdf_pipeline.exceptions import LLMProviderError, PathTraversalError

logger = get_logger(__name__, module="gemini_provider")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CLI_COMMAND = "gemini"
_SUBPROCESS_TIMEOUT = 300  # seconds

# Prompt for PDF-to-Markdown conversion
_PDF_TO_MARKDOWN_PROMPT = """\
Convert the attached PDF file to structured Markdown.

Rules:
- Output ONLY the Markdown content. Do NOT include any explanation, commentary, or reasoning.
- Preserve the document structure using ATX headings (# H1, ## H2, ### H3).
- Convert all tables to Markdown table syntax with proper alignment.
- Preserve all numerical values exactly as they appear in the PDF.
- Remove headers, footers, page numbers, disclaimers, and legal boilerplate.
- Do NOT wrap output in code fences or add preamble like "Here is the converted markdown:".
"""

# Prompt for table JSON extraction
_TABLE_EXTRACT_PROMPT = """\
Extract all tables from the following text as a JSON array.

Each table should be a JSON object with:
- "headers": array of header row arrays
- "rows": array of data row arrays
- "caption": table caption if present (null otherwise)

Output ONLY valid JSON. No explanation or commentary.

Text:
"""

# Prompt for issuer extraction from a PDF file (Vision-based)
_ISSUER_FROM_PDF_PROMPT = """\
Identify the organization (bank, brokerage, or financial institution) that authored \
or published this report.

Return ONLY the organization name (e.g. "JP Morgan", "HSBC", "Goldman Sachs").
Do NOT include the analyst name, department, or any other text.
If you cannot determine the publishing organization, return exactly: unknown
"""

# Prompt for issuer extraction from report text (text-based fallback)
_ISSUER_FROM_TEXT_PROMPT = """\
From the following text excerpt taken from a financial research report, identify \
the organization (bank, brokerage, or financial institution) that authored or \
published the report.

Return ONLY the organization name (e.g. "JP Morgan", "HSBC", "Goldman Sachs").
Do NOT include the analyst name, department, or any other text.
If you cannot determine the publishing organization, return exactly: unknown

Text:
"""

# Prompt for knowledge extraction (Entity/Fact/Claim/FinancialDataPoint schema v2)
_KNOWLEDGE_EXTRACT_PROMPT = """\
Extract entities, facts, claims, and financial data points from the following text as JSON.

Output format:
{
  "entities": [{"name": "...", "entity_type": "company|index|sector|indicator|currency|commodity|person|organization|country|instrument", "ticker": null, "aliases": []}],
  "facts": [{"content": "...", "fact_type": "statistic|event|data_point|quote|policy_action|economic_indicator|regulatory|corporate_action", "as_of_date": null, "about_entities": ["..."]}],
  "claims": [{"content": "...", "claim_type": "opinion|prediction|recommendation|analysis|assumption|guidance|risk_assessment|policy_stance|sector_view|forecast", "sentiment": "bullish|bearish|neutral|mixed", "magnitude": "strong|moderate|slight", "target_price": null, "rating": null, "time_horizon": null, "about_entities": ["..."]}],
  "financial_datapoints": [{"metric_name": "...", "value": 0.0, "unit": "USD mn", "is_estimate": false, "currency": null, "period_label": null, "about_entities": ["..."]}]
}

Output ONLY valid JSON. No explanation or commentary.

Text:
"""

_STDERR_MAX_LENGTH = 500  # Maximum stderr length for log output (CWE-532)


def _truncate_stderr(stderr: str, max_length: int = _STDERR_MAX_LENGTH) -> str:
    """Truncate stderr output to prevent sensitive data leakage (CWE-532).

    Limits stderr length to avoid exposing API keys, tokens, or other
    sensitive information that may appear in subprocess error output.

    Parameters
    ----------
    stderr : str
        Raw stderr output from subprocess.
    max_length : int
        Maximum number of characters to retain. Defaults to 500.

    Returns
    -------
    str
        Original string if within limit, or truncated with
        ``... [truncated]`` suffix.
    """
    if len(stderr) <= max_length:
        return stderr
    return stderr[:max_length] + "... [truncated]"


# Characters considered dangerous in file names for prompt embedding (CWE-77).
# Allows: alphanumeric, hyphen, underscore, dot, forward slash, spaces,
#          parentheses, and common CJK characters.
# Rejects: control characters, newlines, backticks, semicolons, pipes,
#           dollar signs, and other shell meta-characters.
_DANGEROUS_FILENAME_RE: re.Pattern[str] = re.compile(r"[\x00-\x1f\x7f`;\|&$!{}<>\"\']")


def _sanitize_file_path(
    path: Path,
    *,
    allowed_dir: Path | None = None,
) -> Path:
    """Sanitize a file path before embedding it in a prompt.

    Validates that the file path does not contain dangerous characters
    (control characters, newlines, shell meta-characters) that could
    enable prompt injection (CWE-77). Optionally verifies the resolved
    path is within an allowed directory to prevent path traversal.

    Parameters
    ----------
    path : Path
        The file path to sanitize.
    allowed_dir : Path | None
        If provided, the resolved path must be within this directory.
        Raises ``PathTraversalError`` if the path escapes.

    Returns
    -------
    Path
        The resolved (absolute) path.

    Raises
    ------
    ValueError
        If the file name contains dangerous characters.
    PathTraversalError
        If the resolved path is outside the allowed directory.
    """
    # Check the original (unresolved) path first to catch injection attempts
    # before Path.resolve() which may raise on null bytes etc.
    original_str = str(path)
    if _DANGEROUS_FILENAME_RE.search(original_str):
        msg = (
            f"File path contains dangerous characters that could enable "
            f"prompt injection: {original_str!r}"
        )
        logger.error(msg, path=original_str)
        raise ValueError(msg)

    resolved = path.resolve()

    # Check resolved path too (symlink targets etc.)
    path_str = str(resolved)
    if _DANGEROUS_FILENAME_RE.search(path_str):
        msg = (
            f"File path contains dangerous characters that could enable "
            f"prompt injection: {path_str!r}"
        )
        logger.error(msg, path=path_str)
        raise ValueError(msg)

    # Path traversal check
    if allowed_dir is not None:
        allowed_resolved = allowed_dir.resolve()
        if (
            not str(resolved).startswith(str(allowed_resolved) + "/")
            and resolved != allowed_resolved
        ):
            msg = (
                f"Path traversal detected: {resolved} is outside "
                f"allowed directory {allowed_resolved}"
            )
            logger.error(msg, path=str(resolved), base_dir=str(allowed_resolved))
            raise PathTraversalError(
                msg,
                path=str(resolved),
                base_dir=str(allowed_resolved),
            )

    return resolved


# Patterns to strip from Gemini CLI output (noise/thinking logs)
_NOISE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^MCP issues detected\..*$", re.MULTILINE),
    re.compile(r"^I will .*$", re.MULTILINE),
    re.compile(r"^I'll .*$", re.MULTILINE),
    re.compile(r"^Let me .*$", re.MULTILINE),
    re.compile(r"^First, I will .*$", re.MULTILINE),
    re.compile(
        r"^Here is the (?:converted|extracted|structured) .*:?\s*$", re.MULTILINE
    ),
    re.compile(r"^```(?:markdown|md|json)?\s*$", re.MULTILINE),
    re.compile(r"^```\s*$", re.MULTILINE),
]


# ---------------------------------------------------------------------------
# GeminiCLIProvider class
# ---------------------------------------------------------------------------


class GeminiCLIProvider:
    """LLM provider that uses the Gemini CLI via subprocess.

    Uses ``shutil.which`` to check CLI availability and
    ``subprocess.run`` to execute extraction commands with
    ``--prompt`` for non-interactive mode and ``--file`` for PDF attachment.

    Examples
    --------
    >>> provider = GeminiCLIProvider()
    >>> available = provider.is_available()
    >>> isinstance(available, bool)
    True
    """

    def __init__(self) -> None:
        self._available: bool | None = None

    def is_available(self) -> bool:
        """Check whether the ``gemini`` CLI is available.

        Uses ``shutil.which`` to locate the binary in the system PATH.
        Result is cached after the first call.

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
        if self._available is not None:
            return self._available
        self._available = shutil.which(_CLI_COMMAND) is not None
        logger.debug(
            "GeminiCLIProvider availability check",
            command=_CLI_COMMAND,
            available=self._available,
        )
        return self._available

    def convert_pdf_to_markdown(self, pdf_path: str) -> str:
        """Convert a PDF file to Markdown using the Gemini CLI.

        Invokes ``gemini --file <pdf_path> --prompt <conversion_prompt>``
        in non-interactive (headless) mode.

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
            If the CLI command fails, output is empty, or output
            contains no Markdown headings (validation failure).

        Examples
        --------
        >>> provider = GeminiCLIProvider()
        >>> result = provider.convert_pdf_to_markdown("report.pdf")
        >>> isinstance(result, str)
        True
        """
        resolved = str(Path(pdf_path).resolve())
        if not resolved.endswith(".pdf"):
            raise LLMProviderError(
                f"pdf_path must have a .pdf extension: {pdf_path}",
                provider="GeminiCLIProvider",
            )
        logger.debug(
            "Converting PDF to Markdown",
            provider="GeminiCLIProvider",
            pdf_path=resolved,
        )
        raw_output = self._run_gemini(
            prompt=_PDF_TO_MARKDOWN_PROMPT,
            files=[Path(resolved)],
            operation="convert_pdf_to_markdown",
        )
        cleaned = _sanitize_output(raw_output)

        # Validate: output must contain at least one Markdown heading
        if not re.search(r"^#{1,6}\s+", cleaned, re.MULTILINE):
            msg = (
                "Gemini CLI output contains no Markdown headings — "
                "likely a malformed response"
            )
            logger.error(
                msg,
                provider="GeminiCLIProvider",
                output_preview=cleaned[:200],
            )
            raise LLMProviderError(msg, provider="GeminiCLIProvider")

        return cleaned

    def extract_table_json(self, text: str) -> str:
        """Extract table data from text using the Gemini CLI.

        Pipes the input text via ``--prompt`` to Gemini and returns
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
        prompt = _TABLE_EXTRACT_PROMPT + text
        raw_output = self._run_gemini(
            prompt=prompt,
            operation="extract_table_json",
        )
        return _sanitize_output(raw_output)

    def extract_issuer(self, pdf_path: str) -> str | None:
        """Extract the publishing organisation from a PDF using Vision.

        Sends the PDF to Gemini with a focused prompt asking only for the
        issuer (bank / brokerage / financial institution).  Returns ``None``
        when Gemini cannot determine the organisation (i.e. the response is
        ``"unknown"`` or the call fails).

        Parameters
        ----------
        pdf_path : str
            Absolute or relative path to the PDF file.

        Returns
        -------
        str | None
            Organisation name (e.g. ``"JP Morgan"``) or ``None`` if unknown.

        Examples
        --------
        >>> provider = GeminiCLIProvider()
        >>> result = provider.extract_issuer("report.pdf")
        >>> result is None or isinstance(result, str)
        True
        """
        resolved = str(Path(pdf_path).resolve())
        logger.debug(
            "Extracting issuer from PDF",
            provider="GeminiCLIProvider",
            pdf_path=resolved,
        )
        try:
            raw_output = self._run_gemini(
                prompt=_ISSUER_FROM_PDF_PROMPT,
                files=[Path(resolved)],
                operation="extract_issuer",
            )
        except Exception as exc:
            logger.warning(
                "extract_issuer failed; returning None",
                provider="GeminiCLIProvider",
                error=str(exc),
            )
            return None

        result = _sanitize_output(raw_output).strip()
        if not result or result.lower() == "unknown":
            logger.debug(
                "Gemini could not determine issuer from PDF",
                provider="GeminiCLIProvider",
            )
            return None

        logger.info(
            "Issuer extracted from PDF",
            provider="GeminiCLIProvider",
            issuer=result,
        )
        return result

    def extract_issuer_from_text(self, text: str) -> str | None:
        """Extract the publishing organisation from report body text.

        Text-based fallback used when :meth:`extract_issuer` (Vision) cannot
        identify the issuer from the PDF directly.  Sends the first portion of
        the report body to Gemini as plain text.

        Parameters
        ----------
        text : str
            Text excerpt from the report (typically the first chunk's content).

        Returns
        -------
        str | None
            Organisation name or ``None`` if unknown / call failed.

        Examples
        --------
        >>> provider = GeminiCLIProvider()
        >>> result = provider.extract_issuer_from_text("JP Morgan Research\\n...")
        >>> result is None or isinstance(result, str)
        True
        """
        logger.debug(
            "Extracting issuer from report text",
            provider="GeminiCLIProvider",
            text_length=len(text),
        )
        try:
            raw_output = self._run_gemini(
                prompt=_ISSUER_FROM_TEXT_PROMPT + text,
                operation="extract_issuer_from_text",
            )
        except Exception as exc:
            logger.warning(
                "extract_issuer_from_text failed; returning None",
                provider="GeminiCLIProvider",
                error=str(exc),
            )
            return None

        result = _sanitize_output(raw_output).strip()
        if not result or result.lower() == "unknown":
            logger.debug(
                "Gemini could not determine issuer from text",
                provider="GeminiCLIProvider",
            )
            return None

        logger.info(
            "Issuer extracted from text",
            provider="GeminiCLIProvider",
            issuer=result,
        )
        return result

    def extract_knowledge(self, text: str) -> str:
        """Extract knowledge graph entities and relations using the Gemini CLI.

        Pipes the input text via ``--prompt`` to Gemini and returns
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
        prompt = _KNOWLEDGE_EXTRACT_PROMPT + text
        raw_output = self._run_gemini(
            prompt=prompt,
            operation="extract_knowledge",
        )
        return _sanitize_output(raw_output)

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _run_gemini(
        self,
        *,
        prompt: str,
        files: list[Path] | None = None,
        operation: str,
    ) -> str:
        """Execute a Gemini CLI command in non-interactive mode.

        Uses ``gemini -p <prompt> -y`` for headless execution with
        auto-approval of tool calls (e.g. ``read_file`` for PDF access).

        Parameters
        ----------
        prompt : str
            The prompt text to send to Gemini.
        files : list[Path] | None
            Optional list of file paths. Paths are embedded in the prompt
            as explicit instructions for Gemini to read the files.
        operation : str
            Name of the calling operation (used in error messages/logging).

        Returns
        -------
        str
            Standard output from the command.

        Raises
        ------
        LLMProviderError
            If the command fails (non-zero exit) or raises an OS-level error.
        """
        # Sanitize and embed file paths into the prompt for Gemini to read
        full_prompt = prompt
        if files:
            sanitized_files: list[Path] = []
            for f in files:
                try:
                    sanitized = _sanitize_file_path(f)
                    sanitized_files.append(sanitized)
                except (ValueError, PathTraversalError) as exc:
                    msg = (
                        f"GeminiCLIProvider.{operation} failed: unsafe file path: {exc}"
                    )
                    logger.error(
                        msg,
                        provider="GeminiCLIProvider",
                        operation=operation,
                        path=str(f),
                    )
                    raise LLMProviderError(msg, provider="GeminiCLIProvider") from exc
            file_list = "\n".join(f"- {sf}" for sf in sanitized_files)
            full_prompt = f"Files to process:\n{file_list}\n\n{prompt}"

        cmd: list[str] = [_CLI_COMMAND, "-p", full_prompt, "-y"]

        try:
            result = subprocess.run(
                cmd,
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
            # AIDEV-NOTE: CWE-532 - Do NOT include raw stderr in exception
            # message to prevent leaking API keys or tokens. Log truncated
            # stderr separately via structured logging.
            msg = f"GeminiCLIProvider.{operation} failed: exit code {result.returncode}"
            truncated_stderr = _truncate_stderr(result.stderr)
            logger.error(
                msg,
                provider="GeminiCLIProvider",
                operation=operation,
                returncode=result.returncode,
                stderr=truncated_stderr,
            )
            raise LLMProviderError(msg, provider="GeminiCLIProvider")

        logger.info(
            "GeminiCLIProvider operation completed",
            operation=operation,
            output_length=len(result.stdout),
        )
        return result.stdout


# ---------------------------------------------------------------------------
# Output sanitization
# ---------------------------------------------------------------------------


def _sanitize_output(raw: str) -> str:
    """Remove Gemini CLI noise and thinking logs from output.

    Strips MCP warnings, reasoning traces (``I will...``, ``I'll...``),
    and code fence wrappers that Gemini sometimes includes.

    Parameters
    ----------
    raw : str
        Raw stdout from the Gemini CLI.

    Returns
    -------
    str
        Cleaned output with noise lines removed.
    """
    cleaned = raw
    for pattern in _NOISE_PATTERNS:
        cleaned = pattern.sub("", cleaned)

    # Collapse multiple blank lines into at most two
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()
