"""Table reconstruction via LLM Structured Output.

Takes cropped table images (PNG) produced by
:class:`~pdf_pipeline.core.table_detector.TableDetector`, passes them to
an LLM through a :class:`~pdf_pipeline.services.provider_chain.ProviderChain`,
and reconstructs the data into the 3-tier Pydantic schema.

Tier 1 (:class:`~pdf_pipeline.schemas.tables.RawTable`) is *always* preserved:
even when Tier-2 classification fails (unknown table type or JSON parse error),
the output :class:`~pdf_pipeline.schemas.tables.ExtractedTables` still
contains the raw table.

Classes
-------
TableReconstructor
    Reconstruct tables from RawTable image data using LLM structured output.

Examples
--------
>>> from unittest.mock import MagicMock
>>> chain = MagicMock()
>>> chain.extract_table_json.return_value = '{"table_type": "unknown"}'
>>> reconstructor = TableReconstructor(provider_chain=chain)
>>> from pdf_pipeline.schemas.tables import RawTable, TableCell
>>> raw = RawTable(
...     page_number=1, bbox=[0, 0, 200, 100],
...     cells=[TableCell(row=0, col=0, value="Revenue")]
... )
>>> result = reconstructor.reconstruct(pdf_path="report.pdf", raw_tables=[raw])
>>> len(result.raw_tables)
1
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from pdf_pipeline._logging import get_logger
from pdf_pipeline.exceptions import LLMProviderError, PdfPipelineError
from pdf_pipeline.schemas.tables import (
    EstimateChangeTable,
    ExtractedTables,
    FinancialMetric,
    KeyValueTable,
    RawTable,
    TimeSeriesTable,
)

if TYPE_CHECKING:
    from pdf_pipeline.services.provider_chain import ProviderChain

logger = get_logger(__name__, module="table_reconstructor")


class TableReconstructor:
    """Reconstruct structured Tier-2 table data from Tier-1 RawTables using LLM.

    Calls the :class:`~pdf_pipeline.services.provider_chain.ProviderChain`
    ``extract_table_json`` method for each :class:`~pdf_pipeline.schemas.tables.RawTable`.
    The LLM is expected to return a JSON string matching one of the following
    structures:

    time_series
        ``{"table_type": "time_series", "periods": [...], "metrics": [...]}``

    estimate_change
        ``{"table_type": "estimate_change", "metric_name": "...",
          "previous_estimate": float, "new_estimate": float, "change_rate": float}``

    key_value
        ``{"table_type": "key_value", "entries": {...}}``

    unknown
        ``{"table_type": "unknown"}`` — Tier 2 classification skipped.

    When classification fails (unknown type or JSON parse error), the
    :class:`~pdf_pipeline.schemas.tables.RawTable` is preserved as Tier-1
    fallback in the output.

    Parameters
    ----------
    provider_chain : ProviderChain
        The LLM provider chain to use for structured extraction.

    Examples
    --------
    >>> from unittest.mock import MagicMock
    >>> chain = MagicMock()
    >>> chain.extract_table_json.return_value = '{"table_type": "unknown"}'
    >>> reconstructor = TableReconstructor(provider_chain=chain)
    >>> isinstance(reconstructor, TableReconstructor)
    True
    """

    def __init__(self, provider_chain: ProviderChain) -> None:
        """Initialize TableReconstructor with a ProviderChain.

        Parameters
        ----------
        provider_chain : ProviderChain
            Provider chain instance for LLM calls.
        """
        self.provider_chain = provider_chain
        logger.debug("TableReconstructor initialized")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reconstruct(
        self,
        *,
        pdf_path: str,
        raw_tables: list[RawTable],
    ) -> ExtractedTables:
        """Reconstruct 3-tier structured tables from a list of Tier-1 RawTables.

        Processes each RawTable individually:
        1. Builds a prompt referencing the table's ``image_path`` (if any)
           and the raw cell text for context.
        2. Calls ``provider_chain.extract_table_json`` to obtain a structured
           JSON classification.
        3. Parses the JSON and promotes the RawTable to a Tier-2 model if
           classification succeeds.
        4. Falls back to Tier-1 only when classification fails.

        Parameters
        ----------
        pdf_path : str
            Source PDF path, stored in the output :class:`ExtractedTables`.
        raw_tables : list[RawTable]
            Tier-1 raw tables to classify. Must be non-empty.

        Returns
        -------
        ExtractedTables
            Populated envelope with Tier-1 and optional Tier-2 tables.

        Raises
        ------
        ValueError
            If ``raw_tables`` is empty.
        PdfPipelineError
            If the LLM provider raises :class:`LLMProviderError` for all
            attempts (i.e., the entire ProviderChain fails).

        Examples
        --------
        >>> from unittest.mock import MagicMock
        >>> chain = MagicMock()
        >>> chain.extract_table_json.return_value = '{"table_type": "unknown"}'
        >>> reconstructor = TableReconstructor(provider_chain=chain)
        >>> from pdf_pipeline.schemas.tables import RawTable, TableCell
        >>> raw = RawTable(
        ...     page_number=1, bbox=[0, 0, 200, 100],
        ...     cells=[TableCell(row=0, col=0, value="Revenue")]
        ... )
        >>> result = reconstructor.reconstruct(pdf_path="r.pdf", raw_tables=[raw])
        >>> len(result.raw_tables)
        1
        """
        if not raw_tables:
            msg = "raw_tables must not be empty"
            logger.error(msg)
            raise ValueError(msg)

        logger.info(
            "Starting table reconstruction",
            pdf_path=pdf_path,
            table_count=len(raw_tables),
        )

        time_series: list[TimeSeriesTable] = []
        estimate_changes: list[EstimateChangeTable] = []
        key_values: list[KeyValueTable] = []

        for idx, raw in enumerate(raw_tables):
            logger.debug(
                "Reconstructing table",
                table_idx=idx,
                page=raw.page_number,
                image_path=raw.image_path,
            )
            self._classify_table(
                raw=raw,
                time_series=time_series,
                estimate_changes=estimate_changes,
                key_values=key_values,
            )

        result = ExtractedTables(
            pdf_path=pdf_path,
            raw_tables=raw_tables,
            time_series_tables=time_series,
            estimate_change_tables=estimate_changes,
            key_value_tables=key_values,
        )
        logger.info(
            "Table reconstruction complete",
            pdf_path=pdf_path,
            raw=len(raw_tables),
            time_series=len(time_series),
            estimate_changes=len(estimate_changes),
            key_values=len(key_values),
        )
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _classify_table(
        self,
        *,
        raw: RawTable,
        time_series: list[TimeSeriesTable],
        estimate_changes: list[EstimateChangeTable],
        key_values: list[KeyValueTable],
    ) -> None:
        """Classify a single RawTable and append to the appropriate Tier-2 list.

        On classification failure (JSON parse error or unknown type),
        the method returns without modifying any Tier-2 list, preserving
        the Tier-1 fallback guarantee.

        Parameters
        ----------
        raw : RawTable
            The Tier-1 table to classify.
        time_series : list[TimeSeriesTable]
            Output list for time-series tables.
        estimate_changes : list[EstimateChangeTable]
            Output list for estimate-change tables.
        key_values : list[KeyValueTable]
            Output list for key-value tables.

        Raises
        ------
        PdfPipelineError
            If the LLM provider chain raises :class:`LLMProviderError`.
        """
        prompt = self._build_prompt(raw)

        try:
            raw_json = self.provider_chain.extract_table_json(prompt)
        except LLMProviderError as exc:
            msg = f"LLM provider failed during table reconstruction: {exc}"
            logger.error(msg, error=str(exc))
            raise PdfPipelineError(msg) from exc

        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            logger.warning(
                "LLM returned invalid JSON; falling back to Tier-1",
                error=str(exc),
                raw_response=raw_json[:200],
            )
            return  # Tier-1 fallback

        table_type = data.get("table_type", "unknown")

        if table_type == "time_series":
            self._promote_to_time_series(raw=raw, data=data, output=time_series)
        elif table_type == "estimate_change":
            self._promote_to_estimate_change(
                raw=raw, data=data, output=estimate_changes
            )
        elif table_type == "key_value":
            self._promote_to_key_value(raw=raw, data=data, output=key_values)
        else:
            logger.debug(
                "Unknown table type; keeping Tier-1 only",
                table_type=table_type,
                page=raw.page_number,
            )

    def _build_prompt(self, raw: RawTable) -> str:
        """Build an LLM prompt string from a RawTable.

        Parameters
        ----------
        raw : RawTable
            Source Tier-1 table.

        Returns
        -------
        str
            Prompt text containing image path (if available) and cell values.
        """
        cell_text = " | ".join(c.value for c in raw.cells[:20])
        parts = [
            f"Page: {raw.page_number}",
            f"Bounding box: {raw.bbox}",
            f"Cell sample: {cell_text}",
        ]
        if raw.image_path:
            parts.insert(0, f"Image: {raw.image_path}")
        return "\n".join(parts)

    def _promote_to_time_series(
        self,
        *,
        raw: RawTable,
        data: dict,
        output: list[TimeSeriesTable],
    ) -> None:
        """Promote a RawTable to TimeSeriesTable if data is valid."""
        try:
            metrics = [
                FinancialMetric(
                    name=m["name"],
                    value=m["value"],
                    unit=m.get("unit", ""),
                    period=m.get("period"),
                    notes=m.get("notes"),
                )
                for m in data.get("metrics", [])
            ]
            ts = TimeSeriesTable(
                raw_table=raw,
                periods=data["periods"],
                metrics=metrics,
            )
            output.append(ts)
            logger.debug("Promoted to TimeSeriesTable", page=raw.page_number)
        except Exception as exc:
            logger.warning(
                "Failed to promote to TimeSeriesTable; Tier-1 fallback",
                error=str(exc),
            )

    def _promote_to_estimate_change(
        self,
        *,
        raw: RawTable,
        data: dict,
        output: list[EstimateChangeTable],
    ) -> None:
        """Promote a RawTable to EstimateChangeTable if data is valid."""
        try:
            et = EstimateChangeTable(
                raw_table=raw,
                metric_name=data["metric_name"],
                previous_estimate=float(data["previous_estimate"]),
                new_estimate=float(data["new_estimate"]),
                change_rate=float(data["change_rate"]),
                period=data.get("period"),
            )
            output.append(et)
            logger.debug("Promoted to EstimateChangeTable", page=raw.page_number)
        except Exception as exc:
            logger.warning(
                "Failed to promote to EstimateChangeTable; Tier-1 fallback",
                error=str(exc),
            )

    def _promote_to_key_value(
        self,
        *,
        raw: RawTable,
        data: dict,
        output: list[KeyValueTable],
    ) -> None:
        """Promote a RawTable to KeyValueTable if data is valid."""
        try:
            kv = KeyValueTable(
                raw_table=raw,
                entries=data["entries"],
            )
            output.append(kv)
            logger.debug("Promoted to KeyValueTable", page=raw.page_number)
        except Exception as exc:
            logger.warning(
                "Failed to promote to KeyValueTable; Tier-1 fallback",
                error=str(exc),
            )
