"""Unit tests for pdf_pipeline.core.table_reconstructor module.

Tests cover:
- TableReconstructor calls LLM via ProviderChain with table image
- Returns ExtractedTables with populated raw_tables (Tier 1 always present)
- Returns Tier 2 tables when LLM classification succeeds
- Falls back to raw_tables only when LLM returns unclassifiable result
- Error handling: LLMProviderError propagates / wraps correctly
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pdf_pipeline.core.table_reconstructor import TableReconstructor
from pdf_pipeline.exceptions import LLMProviderError, PdfPipelineError
from pdf_pipeline.schemas.tables import (
    ExtractedTables,
    FinancialMetric,
    RawTable,
    TableCell,
    TimeSeriesTable,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_raw_table(page: int = 1) -> RawTable:
    return RawTable(
        page_number=page,
        bbox=[0.0, 0.0, 200.0, 100.0],
        cells=[TableCell(row=0, col=0, value="Revenue")],
        image_path="/tmp/table_p1_t0.png",
    )


def _make_time_series_json(raw_table: RawTable) -> str:
    """Build a valid LLM response JSON for a TimeSeriesTable."""
    return json.dumps(
        {
            "table_type": "time_series",
            "periods": ["FY2023", "FY2024"],
            "metrics": [
                {"name": "Revenue", "value": "100B", "unit": "JPY"},
                {"name": "OP Income", "value": "20B", "unit": "JPY"},
            ],
        }
    )


def _make_unknown_json() -> str:
    return json.dumps({"table_type": "unknown"})


# ---------------------------------------------------------------------------
# TableReconstructor construction
# ---------------------------------------------------------------------------


class TestTableReconstructorInit:
    """Tests for TableReconstructor instantiation."""

    def test_正常系_ProviderChainを受け取ってインスタンス生成できる(self) -> None:
        mock_chain = MagicMock()
        reconstructor = TableReconstructor(provider_chain=mock_chain)
        assert reconstructor.provider_chain is mock_chain


# ---------------------------------------------------------------------------
# TableReconstructor.reconstruct
# ---------------------------------------------------------------------------


class TestTableReconstructorReconstruct:
    """Tests for TableReconstructor.reconstruct method."""

    def test_正常系_raw_tablesのみのextracted_tablesを返す_LLMが未知タイプ返却時(
        self,
    ) -> None:
        """When LLM returns unknown table type, Tier 1 is preserved in output."""
        mock_chain = MagicMock()
        mock_chain.extract_table_json.return_value = _make_unknown_json()

        raw = _make_raw_table()
        reconstructor = TableReconstructor(provider_chain=mock_chain)
        result = reconstructor.reconstruct(pdf_path="report.pdf", raw_tables=[raw])

        assert isinstance(result, ExtractedTables)
        assert result.pdf_path == "report.pdf"
        assert len(result.raw_tables) == 1
        assert result.time_series_tables == []

    def test_正常系_時系列テーブルが分類されてTier2に含まれる(self) -> None:
        """When LLM returns time_series, TimeSeriesTable is populated."""
        mock_chain = MagicMock()
        raw = _make_raw_table()
        mock_chain.extract_table_json.return_value = _make_time_series_json(raw)

        reconstructor = TableReconstructor(provider_chain=mock_chain)
        result = reconstructor.reconstruct(pdf_path="report.pdf", raw_tables=[raw])

        assert len(result.raw_tables) == 1  # Tier 1 always present
        assert len(result.time_series_tables) == 1
        ts = result.time_series_tables[0]
        assert isinstance(ts, TimeSeriesTable)
        assert "FY2023" in ts.periods
        assert len(ts.metrics) == 2

    def test_正常系_複数テーブルを処理できる(self) -> None:
        """Multiple raw tables are processed individually."""
        raw1 = _make_raw_table(page=1)
        raw2 = _make_raw_table(page=2)

        call_count = 0

        def _side_effect(text: str) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_time_series_json(raw1)
            return _make_unknown_json()

        mock_chain = MagicMock()
        mock_chain.extract_table_json.side_effect = _side_effect

        reconstructor = TableReconstructor(provider_chain=mock_chain)
        result = reconstructor.reconstruct(
            pdf_path="report.pdf", raw_tables=[raw1, raw2]
        )

        assert len(result.raw_tables) == 2
        assert len(result.time_series_tables) == 1  # only raw1 classified

    def test_正常系_Tier2分類失敗時もTier1は保持される_フォールバック保証(self) -> None:
        """Fallback guarantee: raw_tables always contains the input tables."""
        mock_chain = MagicMock()
        mock_chain.extract_table_json.return_value = _make_unknown_json()

        raw = _make_raw_table()
        reconstructor = TableReconstructor(provider_chain=mock_chain)
        result = reconstructor.reconstruct(pdf_path="report.pdf", raw_tables=[raw])

        # Tier 1 must always be present
        assert len(result.raw_tables) >= 1
        assert result.raw_tables[0].page_number == raw.page_number

    def test_正常系_LLMがJSON解析失敗してもTier1は保持される(self) -> None:
        """If LLM returns invalid JSON, fallback to raw_tables only."""
        mock_chain = MagicMock()
        mock_chain.extract_table_json.return_value = "this is not json"

        raw = _make_raw_table()
        reconstructor = TableReconstructor(provider_chain=mock_chain)
        result = reconstructor.reconstruct(pdf_path="report.pdf", raw_tables=[raw])

        assert len(result.raw_tables) == 1
        assert result.time_series_tables == []

    def test_異常系_LLMProviderErrorが全プロバイダー失敗時PdfPipelineError(
        self,
    ) -> None:
        """If LLMProviderError is raised, reconstruct wraps it in PdfPipelineError."""
        mock_chain = MagicMock()
        mock_chain.extract_table_json.side_effect = LLMProviderError(
            "All providers failed", provider="ProviderChain"
        )

        raw = _make_raw_table()
        reconstructor = TableReconstructor(provider_chain=mock_chain)
        with pytest.raises(PdfPipelineError):
            reconstructor.reconstruct(pdf_path="report.pdf", raw_tables=[raw])

    def test_正常系_空のraw_tablesでExtractedTablesにするとValidationError回避(
        self,
    ) -> None:
        """reconstruct with no raw_tables raises ValueError before LLM is called."""
        mock_chain = MagicMock()
        reconstructor = TableReconstructor(provider_chain=mock_chain)
        with pytest.raises((ValueError, PdfPipelineError)):
            reconstructor.reconstruct(pdf_path="report.pdf", raw_tables=[])
