#!/usr/bin/env python3
"""RSS Presets Validation Script.

任意のRSSプリセットJSONファイルを検証するスクリプト。
JSON構造バリデーション、HTTP HEADチェック、robots.txt準拠チェックを実行し、
結果テーブルを出力する。

Usage
-----
    # 基本検証（JSON構造 + HTTP HEADチェック）
    uv run python scripts/validate_rss_presets.py data/config/rss-presets-wealth.json

    # robots.txt準拠チェックを含む
    uv run python scripts/validate_rss_presets.py data/config/rss-presets-wealth.json --check-robots

    # 複数ファイルを検証
    uv run python scripts/validate_rss_presets.py data/config/rss-presets-jp.json data/config/rss-presets-wealth.json

    # 有効フィードのみ検証
    uv run python scripts/validate_rss_presets.py data/config/rss-presets-wealth.json --enabled-only

Output
------
    URL | Status | HTTP Code | robots.txt テーブルを標準出力に表示。
    エラーがある場合は非ゼロ終了コードで終了。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

try:
    from rss._logging import get_logger

    logger = get_logger(__name__, module="validate_rss_presets")
except ImportError:
    import logging

    logger = logging.getLogger(__name__)  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_FIELDS: list[str] = ["url", "title", "category", "fetch_interval", "enabled"]
"""Required fields in each preset entry."""

VALID_FETCH_INTERVALS: set[str] = {"daily", "weekly", "monthly", "hourly"}
"""Valid values for fetch_interval field."""

VALID_CATEGORIES: set[str] = {
    "personal_finance",
    "fire_wealth_building",
    "data_driven_investing",
    "dividend_income",
    "academic_finance",
    "financial_infrastructure",
    "stocks",
    "macro",
    "crypto",
    "etf",
    "news",
}
"""Valid values for category field (extensible)."""

HTTP_TIMEOUT_SECONDS: float = 10.0
"""HTTP request timeout in seconds."""

MAX_CONCURRENT_REQUESTS: int = 5
"""Maximum concurrent HTTP requests to avoid overwhelming servers."""

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class PresetValidationResult:
    """Validation result for a single preset entry.

    Attributes
    ----------
    url : str
        RSS feed URL.
    title : str
        Feed title.
    status : str
        Overall status: "OK", "WARN", or "ERROR".
    http_code : int | None
        HTTP response code from HEAD request, or None if not checked.
    robots_status : str
        robots.txt compliance status: "ALLOWED", "BLOCKED", "NO_DIRECTIVES",
        "SKIP", or "ERROR".
    errors : list[str]
        List of validation error messages.
    warnings : list[str]
        List of validation warning messages.
    """

    url: str
    title: str
    status: str = "OK"
    http_code: int | None = None
    robots_status: str = "SKIP"
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class FileValidationSummary:
    """Summary of validation results for a single preset file.

    Attributes
    ----------
    file_path : str
        Path to the validated JSON file.
    total : int
        Total number of presets.
    ok_count : int
        Number of presets with OK status.
    warn_count : int
        Number of presets with WARN status.
    error_count : int
        Number of presets with ERROR status.
    results : list[PresetValidationResult]
        Individual preset validation results.
    """

    file_path: str
    total: int = 0
    ok_count: int = 0
    warn_count: int = 0
    error_count: int = 0
    results: list[PresetValidationResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# JSON Structure Validation
# ---------------------------------------------------------------------------


def validate_json_structure(data: object) -> list[str]:
    """Validate top-level JSON structure of a presets file.

    Parameters
    ----------
    data : object
        Parsed JSON data.

    Returns
    -------
    list[str]
        List of error messages. Empty if valid.
    """
    errors: list[str] = []

    if not isinstance(data, dict):
        errors.append("Root must be a JSON object")
        return errors

    if "presets" not in data:
        errors.append("Missing required top-level key: 'presets'")
        return errors

    if not isinstance(data["presets"], list):
        errors.append("'presets' must be an array")
        return errors

    return errors


def validate_preset_entry(
    entry: object,
    index: int,
) -> tuple[str, str, list[str], list[str]]:
    """Validate a single preset entry.

    Parameters
    ----------
    entry : object
        Preset entry data.
    index : int
        Index in presets array (for error messages).

    Returns
    -------
    tuple[str, str, list[str], list[str]]
        Tuple of (url, title, errors, warnings).
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(entry, dict):
        return "", f"entry[{index}]", [f"Entry {index} must be a JSON object"], []

    url = str(entry.get("url", ""))
    title = str(entry.get("title", f"entry[{index}]"))

    # Check required fields
    for field_name in REQUIRED_FIELDS:
        if field_name not in entry:
            errors.append(f"Missing required field: '{field_name}'")

    # Validate URL format
    if url:
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme not in ("http", "https"):
                errors.append(
                    f"URL scheme must be http or https, got: '{parsed.scheme}'"
                )
            if not parsed.netloc:
                errors.append("URL must have a valid hostname")
        except Exception as e:
            errors.append(f"URL parse error: {e}")
    else:
        errors.append("'url' field is empty or missing")

    # Validate fetch_interval
    fetch_interval = entry.get("fetch_interval", "")
    if fetch_interval and fetch_interval not in VALID_FETCH_INTERVALS:
        warnings.append(
            f"Unexpected fetch_interval '{fetch_interval}'. "
            f"Expected one of: {sorted(VALID_FETCH_INTERVALS)}"
        )

    # Validate enabled field type
    enabled = entry.get("enabled")
    if enabled is not None and not isinstance(enabled, bool):
        errors.append(f"'enabled' must be a boolean, got: {type(enabled).__name__}")

    # Validate tier if present
    tier = entry.get("tier")
    if tier is not None and not isinstance(tier, int):
        warnings.append(f"'tier' should be an integer, got: {type(tier).__name__}")

    return url, title, errors, warnings


# ---------------------------------------------------------------------------
# HTTP HEAD Check
# ---------------------------------------------------------------------------


async def check_http_head(
    url: str,
    semaphore: asyncio.Semaphore,
    timeout: float = HTTP_TIMEOUT_SECONDS,
) -> int | None:
    """Perform HTTP HEAD request to check URL accessibility.

    Parameters
    ----------
    url : str
        URL to check.
    semaphore : asyncio.Semaphore
        Semaphore to limit concurrent requests.
    timeout : float
        Request timeout in seconds.

    Returns
    -------
    int | None
        HTTP status code, or None if request failed.
    """
    try:
        import httpx

        async with (
            semaphore,
            httpx.AsyncClient(
                follow_redirects=True,
                timeout=timeout,
            ) as client,
        ):
            response = await client.head(
                url,
                headers={"User-Agent": "rss-feed-collector/0.1.0"},
            )
            return response.status_code
    except Exception as e:
        logger.debug("http_head_failed", url=url, error=str(e))
        return None


# ---------------------------------------------------------------------------
# robots.txt Check
# ---------------------------------------------------------------------------


async def check_robots_compliance(
    url: str,
    semaphore: asyncio.Semaphore,
    checker: Any | None = None,
) -> str:
    """Check robots.txt compliance for a URL.

    Parameters
    ----------
    url : str
        URL to check.
    semaphore : asyncio.Semaphore
        Semaphore to limit concurrent requests.
    checker : Any | None
        Shared RobotsChecker instance.  If None, a new instance is created.
        Pass a shared instance to reuse the domain-level cache across URLs.

    Returns
    -------
    str
        One of: "ALLOWED", "BLOCKED", "NO_DIRECTIVES", "ERROR".
    """
    try:
        from rss.utils.robots_checker import RobotsChecker

        async with semaphore:
            _checker: Any = checker if checker is not None else RobotsChecker()
            result = await _checker.check(url)

        if result.error:
            return "ERROR"

        if result.ai_directives:
            # Check if AI directives block crawling
            for _directive, value in result.ai_directives.items():
                if value.lower() in ("no", "0", "false", "disallow"):
                    return "BLOCKED"
            return "NO_DIRECTIVES"

        return "ALLOWED" if result.allowed else "BLOCKED"

    except ImportError:
        logger.warning("robots_checker_unavailable")
        return "ERROR"
    except Exception as e:
        logger.debug("robots_check_failed", url=url, error=str(e))
        return "ERROR"


# ---------------------------------------------------------------------------
# Main Validation Logic
# ---------------------------------------------------------------------------


def _determine_result_status(
    result: PresetValidationResult,
    http_code: int | None,
    url: str,
) -> None:
    """Determine and set the overall status on a PresetValidationResult.

    Parameters
    ----------
    result : PresetValidationResult
        The result object to update in-place.
    http_code : int | None
        HTTP status code from HEAD request.
    url : str
        The URL being checked.
    """
    if result.errors:
        result.status = "ERROR"
    elif result.warnings:
        result.status = "WARN"
    elif http_code is not None and http_code >= 400:
        result.status = "WARN"
        result.warnings.append(f"HTTP {http_code} response")
    elif http_code is None and url:
        result.status = "WARN"
        result.warnings.append("HTTP HEAD request failed or timed out")
    else:
        result.status = "OK"


def _update_summary_counts(
    summary: FileValidationSummary,
    result: PresetValidationResult,
) -> None:
    """Increment the appropriate count on the summary based on result status.

    Parameters
    ----------
    summary : FileValidationSummary
        The summary object to update in-place.
    result : PresetValidationResult
        The completed result whose status drives the counter.
    """
    summary.total += 1
    if result.status == "OK":
        summary.ok_count += 1
    elif result.status == "WARN":
        summary.warn_count += 1
    else:
        summary.error_count += 1


async def _run_http_checks(
    http_check_urls: list[tuple[str, int]],
    semaphore: asyncio.Semaphore,
) -> dict[int, int | None]:
    """Run HTTP HEAD checks concurrently and return results by index.

    Parameters
    ----------
    http_check_urls : list[tuple[str, int]]
        List of (url, index) pairs to check.
    semaphore : asyncio.Semaphore
        Semaphore to limit concurrent requests.

    Returns
    -------
    dict[int, int | None]
        HTTP status codes keyed by preset index.
    """
    http_results: dict[int, int | None] = {}
    if not http_check_urls:
        return http_results
    coros = [check_http_head(url, semaphore) for url, _ in http_check_urls]
    codes = await asyncio.gather(*coros)
    for (_url, idx), code in zip(http_check_urls, codes, strict=True):
        http_results[idx] = code
    return http_results


async def _run_robots_checks(
    http_check_urls: list[tuple[str, int]],
    semaphore: asyncio.Semaphore,
    checker: Any | None = None,
) -> dict[int, str]:
    """Run robots.txt compliance checks concurrently and return results by index.

    Parameters
    ----------
    http_check_urls : list[tuple[str, int]]
        List of (url, index) pairs to check.
    semaphore : asyncio.Semaphore
        Semaphore to limit concurrent requests.

    Returns
    -------
    dict[int, str]
        robots.txt status strings keyed by preset index.
    """
    robots_results: dict[int, str] = {}
    if not http_check_urls:
        return robots_results
    # Pass shared checker instance to reuse domain-level robots.txt cache
    coros = [
        check_robots_compliance(url, semaphore, checker) for url, _ in http_check_urls
    ]
    statuses = await asyncio.gather(*coros)
    for (_url, idx), status in zip(http_check_urls, statuses, strict=True):
        robots_results[idx] = status
    return robots_results


def _load_presets_from_file(
    preset_file: Path,
    enabled_only: bool,
) -> tuple[list[object] | None, FileValidationSummary | None]:
    """Load and structurally validate the presets JSON file.

    Parameters
    ----------
    preset_file : Path
        Path to the JSON file to load.
    enabled_only : bool
        If True, return only enabled preset entries.

    Returns
    -------
    tuple[list[object] | None, FileValidationSummary | None]
        (presets_list, None) on success, or (None, error_summary) on failure.
    """
    summary_err = FileValidationSummary(file_path=str(preset_file))
    try:
        with preset_file.open(encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.error("file_not_found", path=str(preset_file))
        summary_err.error_count += 1
        return None, summary_err
    except json.JSONDecodeError as e:
        logger.error("json_parse_error", path=str(preset_file), error=str(e))
        summary_err.error_count += 1
        return None, summary_err

    struct_errors = validate_json_structure(data)
    if struct_errors:
        for err in struct_errors:
            logger.error("structure_error", path=str(preset_file), error=err)
        summary_err.error_count += 1
        return None, summary_err

    presets = data["presets"]  # type: ignore[index]
    if enabled_only:
        presets = [p for p in presets if isinstance(p, dict) and p.get("enabled", True)]
    return presets, None


async def validate_presets_file(
    preset_file: Path,
    check_robots: bool = False,
    enabled_only: bool = False,
) -> FileValidationSummary:
    """Validate a single RSS presets JSON file.

    Parameters
    ----------
    preset_file : Path
        Path to the JSON file to validate.
    check_robots : bool
        Whether to check robots.txt compliance.
    enabled_only : bool
        Whether to validate only enabled presets.

    Returns
    -------
    FileValidationSummary
        Validation summary for the file.
    """
    presets, err_summary = _load_presets_from_file(preset_file, enabled_only)
    if err_summary is not None:
        return err_summary

    summary = FileValidationSummary(file_path=str(preset_file))
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    # Validate each preset entry (structural checks only)
    ValidationTask = tuple[str, str, list[str], list[str], int]
    validation_tasks: list[ValidationTask] = []
    for i, entry in enumerate(presets or []):
        url, title, errors, warnings = validate_preset_entry(entry, i)
        validation_tasks.append((url, title, errors, warnings, i))

    # Collect URLs that need HTTP checks (skip if structurally invalid)
    http_check_urls = [
        (url, i)
        for url, _title, errors, _warnings, i in validation_tasks
        if url and not errors
    ]

    http_results = await _run_http_checks(http_check_urls, semaphore)

    # Create a single shared RobotsChecker to reuse the domain-level cache
    # across all URL checks (performance fix: avoid re-fetching robots.txt per URL)
    robots_results: dict[int, str] = {}
    if check_robots:
        try:
            from rss.utils.robots_checker import RobotsChecker as _RobotsChecker

            shared_checker: Any = _RobotsChecker()
        except ImportError:
            shared_checker = None
        robots_results = await _run_robots_checks(
            http_check_urls, semaphore, shared_checker
        )

    for url, title, errors, warnings, i in validation_tasks:
        http_code = http_results.get(i)
        robots_status = robots_results.get(i, "SKIP")
        result = PresetValidationResult(
            url=url,
            title=title,
            http_code=http_code,
            robots_status=robots_status if check_robots else "SKIP",
            errors=errors,
            warnings=warnings,
        )
        _determine_result_status(result, http_code, url)
        summary.results.append(result)
        _update_summary_counts(summary, result)

    return summary


# ---------------------------------------------------------------------------
# Output Formatting
# ---------------------------------------------------------------------------


def format_results_table(
    summary: FileValidationSummary,
    check_robots: bool,
) -> str:
    """Format validation results as a text table.

    Parameters
    ----------
    summary : FileValidationSummary
        Validation summary to format.
    check_robots : bool
        Whether robots.txt check was performed.

    Returns
    -------
    str
        Formatted table string.
    """
    lines: list[str] = []
    lines.append(f"\n{'=' * 70}")
    lines.append(f"File: {summary.file_path}")
    lines.append(f"{'=' * 70}")

    if not summary.results:
        lines.append("No presets to validate.")
        return "\n".join(lines)

    # Table header
    if check_robots:
        header = f"{'URL':<50} {'Status':<8} {'HTTP':<6} {'robots.txt':<15}"
        lines.append(header)
        lines.append("-" * 85)
    else:
        header = f"{'URL':<55} {'Status':<8} {'HTTP':<6}"
        lines.append(header)
        lines.append("-" * 72)

    # Table rows
    for result in summary.results:
        url_display = result.url[:50] if len(result.url) > 50 else result.url
        http_display = str(result.http_code) if result.http_code is not None else "-"

        if check_robots:
            row = (
                f"{url_display:<50} "
                f"{result.status:<8} "
                f"{http_display:<6} "
                f"{result.robots_status:<15}"
            )
        else:
            row = f"{url_display:<55} {result.status:<8} {http_display:<6}"
        lines.append(row)

        # Print errors and warnings indented
        for err in result.errors:
            lines.append(f"  ERROR: {err}")
        for warn in result.warnings:
            lines.append(f"  WARN:  {warn}")

    # Summary line
    lines.append(f"\n{'=' * 70}")
    lines.append(
        f"Total: {summary.total}  "
        f"OK: {summary.ok_count}  "
        f"WARN: {summary.warn_count}  "
        f"ERROR: {summary.error_count}"
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Parameters
    ----------
    args : list[str] | None
        Command-line arguments. If None, uses sys.argv.

    Returns
    -------
    argparse.Namespace
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Validate RSS preset JSON files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="One or more RSS preset JSON files to validate",
    )
    parser.add_argument(
        "--check-robots",
        action="store_true",
        default=False,
        help="Check robots.txt compliance for each feed URL",
    )
    parser.add_argument(
        "--enabled-only",
        action="store_true",
        default=False,
        help="Validate only presets with enabled=true",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser.parse_args(args)


async def _main(args: list[str] | None = None) -> int:
    """Async main entry point.

    Parameters
    ----------
    args : list[str] | None
        Command-line arguments.

    Returns
    -------
    int
        Exit code (0 for success, 1 if any errors found).
    """
    parsed = parse_args(args)

    # Configure logging
    if parsed.verbose:
        import logging

        logging.basicConfig(level=logging.DEBUG)

    total_errors = 0

    for file_path_str in parsed.files:
        preset_file = Path(file_path_str)

        if not preset_file.exists():
            print(f"ERROR: File not found: {preset_file}", file=sys.stderr)
            total_errors += 1
            continue

        logger.info("validating_file", path=str(preset_file))

        summary = await validate_presets_file(
            preset_file,
            check_robots=parsed.check_robots,
            enabled_only=parsed.enabled_only,
        )

        print(format_results_table(summary, check_robots=parsed.check_robots))
        total_errors += summary.error_count

    if total_errors > 0:
        print(f"\nValidation completed with {total_errors} error(s).", file=sys.stderr)
        return 1

    print("\nAll presets validated successfully.")
    return 0


def main(args: list[str] | None = None) -> int:
    """Main entry point.

    Parameters
    ----------
    args : list[str] | None
        Command-line arguments.

    Returns
    -------
    int
        Exit code.
    """
    return asyncio.run(_main(args))


if __name__ == "__main__":
    sys.exit(main())
