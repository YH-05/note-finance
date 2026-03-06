"""Markdown summary exporter for report scraping results.

Generates a human-readable Markdown summary from a ``RunSummary``,
including execution timestamp, per-source report counts, error details,
and a list of newly collected reports.

Classes
-------
SummaryExporter
    Generates Markdown summary strings from RunSummary data.

Examples
--------
>>> from datetime import datetime, timezone
>>> from report_scraper.types import RunSummary
>>> exporter = SummaryExporter()
>>> summary = RunSummary(
...     timestamp=datetime(2026, 3, 6, tzinfo=timezone.utc),
...     results=(),
...     total_reports=0,
...     total_errors=0,
... )
>>> md = exporter.export(summary)
>>> "# Report Scraper" in md
True
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from report_scraper._logging import get_logger

if TYPE_CHECKING:
    from report_scraper.types import CollectResult, RunSummary

logger = get_logger(__name__, module="summary_exporter")


class SummaryExporter:
    """Generate Markdown summary strings from RunSummary data.

    The exported Markdown includes:

    - Execution timestamp
    - Per-source report counts with error counts
    - Error details (if any)
    - List of newly collected reports with titles and URLs

    Examples
    --------
    >>> exporter = SummaryExporter()
    >>> exporter  # doctest: +ELLIPSIS
    <report_scraper.services.summary_exporter.SummaryExporter ...>
    """

    def export(self, summary: RunSummary) -> str:
        """Generate a Markdown summary from a RunSummary.

        Parameters
        ----------
        summary : RunSummary
            The completed run summary to export.

        Returns
        -------
        str
            Markdown-formatted summary string.

        Examples
        --------
        >>> from datetime import datetime, timezone
        >>> from report_scraper.types import RunSummary
        >>> exporter = SummaryExporter()
        >>> s = RunSummary(
        ...     timestamp=datetime(2026, 3, 6, tzinfo=timezone.utc),
        ...     results=(), total_reports=0, total_errors=0,
        ... )
        >>> result = exporter.export(s)
        >>> isinstance(result, str)
        True
        """
        logger.info(
            "Exporting summary",
            total_reports=summary.total_reports,
            total_errors=summary.total_errors,
        )

        sections: list[str] = []

        sections.append(self._render_header(summary))
        sections.append(self._render_overview(summary))
        sections.append(self._render_source_table(summary))

        if summary.total_errors > 0:
            sections.append(self._render_errors(summary))

        if summary.total_reports > 0:
            sections.append(self._render_report_list(summary))

        result = "\n\n".join(sections) + "\n"

        logger.debug(
            "Summary exported",
            length=len(result),
        )

        return result

    # -- Private rendering methods -------------------------------------------

    def _render_header(self, summary: RunSummary) -> str:
        """Render the main header with timestamp.

        Parameters
        ----------
        summary : RunSummary
            Run summary data.

        Returns
        -------
        str
            Markdown header section.
        """
        ts_str = summary.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
        return f"# Report Scraper Summary\n\n**Run time**: {ts_str}"

    def _render_overview(self, summary: RunSummary) -> str:
        """Render the overview statistics.

        Parameters
        ----------
        summary : RunSummary
            Run summary data.

        Returns
        -------
        str
            Markdown overview section.
        """
        source_count = len(summary.results)
        lines = [
            "## Overview",
            "",
            f"- **Sources processed**: {source_count}",
            f"- **Total reports**: {summary.total_reports}",
            f"- **Total errors**: {summary.total_errors}",
        ]
        return "\n".join(lines)

    def _render_source_table(self, summary: RunSummary) -> str:
        """Render per-source results as a Markdown table.

        Parameters
        ----------
        summary : RunSummary
            Run summary data.

        Returns
        -------
        str
            Markdown table section.
        """
        lines = [
            "## Source Results",
            "",
            "| Source | Reports | Errors | Duration (s) |",
            "|--------|---------|--------|--------------|",
        ]

        for result in summary.results:
            lines.append(self._format_source_row(result))

        return "\n".join(lines)

    def _format_source_row(self, result: CollectResult) -> str:
        """Format a single source result as a table row.

        Parameters
        ----------
        result : CollectResult
            Per-source collection result.

        Returns
        -------
        str
            Markdown table row.
        """
        return (
            f"| {result.source_key} "
            f"| {len(result.reports)} "
            f"| {len(result.errors)} "
            f"| {result.duration:.1f} |"
        )

    def _render_errors(self, summary: RunSummary) -> str:
        """Render error details section.

        Parameters
        ----------
        summary : RunSummary
            Run summary data.

        Returns
        -------
        str
            Markdown error section.
        """
        lines = [
            "## Errors",
            "",
        ]

        for result in summary.results:
            if result.errors:
                lines.append(f"### {result.source_key}")
                lines.append("")
                for error in result.errors:
                    lines.append(f"- {error}")
                lines.append("")

        return "\n".join(lines).rstrip()

    def _render_report_list(self, summary: RunSummary) -> str:
        """Render the list of newly collected reports.

        Parameters
        ----------
        summary : RunSummary
            Run summary data.

        Returns
        -------
        str
            Markdown report list section.
        """
        lines = [
            "## Collected Reports",
            "",
        ]

        for result in summary.results:
            if result.reports:
                lines.append(f"### {result.source_key}")
                lines.append("")
                for report in result.reports:
                    meta = report.metadata
                    lines.append(f"- [{meta.title}]({meta.url})")
                lines.append("")

        return "\n".join(lines).rstrip()
