"""Unit tests for pdf_pipeline.schemas.tables module.

Tests cover:
- TableCell and RawTable (Tier 1) validation
- FinancialMetric, TimeSeriesTable, EstimateChangeTable, KeyValueTable (Tier 2)
- ExtractedTables envelope (Tier 3)
- RawTable fallback guarantee (Tier 2 failure does not remove Tier 1)
- Multi-level headers (list[list[TableCell]])
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from pdf_pipeline.schemas.tables import (
    EstimateChangeTable,
    ExtractedTables,
    FinancialMetric,
    KeyValueTable,
    RawTable,
    TableCell,
    TimeSeriesTable,
)

# ---------------------------------------------------------------------------
# Tier 1: TableCell
# ---------------------------------------------------------------------------


class TestTableCell:
    """Tests for TableCell Pydantic model."""

    def test_正常系_必須フィールドで生成できる(self) -> None:
        cell = TableCell(row=0, col=0, value="Revenue")
        assert cell.row == 0
        assert cell.col == 0
        assert cell.value == "Revenue"

    def test_正常系_spanフィールドのデフォルト値(self) -> None:
        cell = TableCell(row=0, col=0, value="")
        assert cell.rowspan == 1
        assert cell.colspan == 1

    def test_正常系_spanフィールドをカスタム設定できる(self) -> None:
        cell = TableCell(row=0, col=0, value="Header", rowspan=2, colspan=3)
        assert cell.rowspan == 2
        assert cell.colspan == 3

    def test_正常系_空文字列のvalueを許容する(self) -> None:
        cell = TableCell(row=0, col=0, value="")
        assert cell.value == ""

    def test_正常系_is_headerフィールドのデフォルト値(self) -> None:
        cell = TableCell(row=0, col=0, value="X")
        assert cell.is_header is False

    def test_正常系_is_headerをTrueに設定できる(self) -> None:
        cell = TableCell(row=0, col=0, value="FY2024", is_header=True)
        assert cell.is_header is True

    def test_異常系_rowが負でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            TableCell(row=-1, col=0, value="X")

    def test_異常系_colが負でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            TableCell(row=0, col=-1, value="X")

    def test_異常系_rowspanが0以下でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            TableCell(row=0, col=0, value="X", rowspan=0)

    def test_異常系_colspanが0以下でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            TableCell(row=0, col=0, value="X", colspan=0)


# ---------------------------------------------------------------------------
# Tier 1: RawTable
# ---------------------------------------------------------------------------


class TestRawTable:
    """Tests for RawTable Pydantic model (Tier 1)."""

    def _make_cell(self, row: int, col: int, value: str) -> TableCell:
        return TableCell(row=row, col=col, value=value)

    def test_正常系_必須フィールドで生成できる(self) -> None:
        cells = [self._make_cell(0, 0, "A"), self._make_cell(0, 1, "B")]
        table = RawTable(
            page_number=1,
            bbox=[10.0, 20.0, 200.0, 100.0],
            cells=cells,
        )
        assert table.page_number == 1
        assert len(table.cells) == 2
        assert len(table.bbox) == 4

    def test_正常系_headersのデフォルト値は空リスト(self) -> None:
        cells = [self._make_cell(0, 0, "X")]
        table = RawTable(page_number=1, bbox=[0, 0, 100, 50], cells=cells)
        assert table.headers == []

    def test_正常系_多段ヘッダーを表現できる(self) -> None:
        # Multi-level headers: list[list[TableCell]]
        header_row1 = [TableCell(row=0, col=0, value="FY2024", is_header=True)]
        header_row2 = [TableCell(row=1, col=0, value="Q1", is_header=True)]
        cells = [self._make_cell(2, 0, "100")]
        table = RawTable(
            page_number=2,
            bbox=[0, 0, 200, 150],
            cells=cells,
            headers=[header_row1, header_row2],
        )
        assert len(table.headers) == 2
        assert table.headers[0][0].value == "FY2024"
        assert table.headers[1][0].value == "Q1"

    def test_正常系_row_countとcol_countを設定できる(self) -> None:
        cells = [self._make_cell(0, 0, "X")]
        table = RawTable(
            page_number=1,
            bbox=[0, 0, 100, 50],
            cells=cells,
            row_count=3,
            col_count=4,
        )
        assert table.row_count == 3
        assert table.col_count == 4

    def test_正常系_image_pathを設定できる(self) -> None:
        cells = [self._make_cell(0, 0, "X")]
        table = RawTable(
            page_number=1,
            bbox=[0, 0, 100, 50],
            cells=cells,
            image_path="/tmp/table_p1.png",
        )
        assert table.image_path == "/tmp/table_p1.png"

    def test_正常系_image_pathのデフォルト値はNone(self) -> None:
        cells = [self._make_cell(0, 0, "X")]
        table = RawTable(page_number=1, bbox=[0, 0, 100, 50], cells=cells)
        assert table.image_path is None

    def test_異常系_page_numberが0以下でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            RawTable(
                page_number=0,
                bbox=[0, 0, 100, 50],
                cells=[self._make_cell(0, 0, "X")],
            )

    def test_異常系_bboxが4要素でない場合ValidationError(self) -> None:
        with pytest.raises(ValidationError):
            RawTable(
                page_number=1,
                bbox=[0, 0, 100],
                cells=[self._make_cell(0, 0, "X")],
            )

    def test_異常系_cellsが空リストでValidationError(self) -> None:
        with pytest.raises(ValidationError):
            RawTable(page_number=1, bbox=[0, 0, 100, 50], cells=[])


# ---------------------------------------------------------------------------
# Tier 2: FinancialMetric
# ---------------------------------------------------------------------------


class TestFinancialMetric:
    """Tests for FinancialMetric Pydantic model (Tier 2)."""

    def test_正常系_必須フィールドで生成できる(self) -> None:
        metric = FinancialMetric(name="Revenue", value="100B", unit="JPY")
        assert metric.name == "Revenue"
        assert metric.value == "100B"
        assert metric.unit == "JPY"

    def test_正常系_periodとnotesを設定できる(self) -> None:
        metric = FinancialMetric(
            name="EPS",
            value="123.4",
            unit="JPY",
            period="FY2024",
            notes="Consensus estimate",
        )
        assert metric.period == "FY2024"
        assert metric.notes == "Consensus estimate"

    def test_正常系_periodとnotesのデフォルト値はNone(self) -> None:
        metric = FinancialMetric(name="ROE", value="15%", unit="%")
        assert metric.period is None
        assert metric.notes is None

    def test_異常系_nameが空でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            FinancialMetric(name="", value="100", unit="JPY")


# ---------------------------------------------------------------------------
# Tier 2: TimeSeriesTable
# ---------------------------------------------------------------------------


class TestTimeSeriesTable:
    """Tests for TimeSeriesTable Pydantic model (Tier 2)."""

    def _make_raw_table(self) -> RawTable:
        cells = [TableCell(row=0, col=0, value="Revenue")]
        return RawTable(page_number=1, bbox=[0, 0, 200, 100], cells=cells)

    def test_正常系_必須フィールドで生成できる(self) -> None:
        raw = self._make_raw_table()
        ts_table = TimeSeriesTable(
            raw_table=raw,
            periods=["FY2022", "FY2023", "FY2024"],
            metrics=[
                FinancialMetric(name="Revenue", value="100B", unit="JPY"),
            ],
        )
        assert len(ts_table.periods) == 3
        assert len(ts_table.metrics) == 1
        assert ts_table.raw_table is raw

    def test_正常系_metricsが複数設定できる(self) -> None:
        raw = self._make_raw_table()
        metrics = [
            FinancialMetric(name="Revenue", value="100B", unit="JPY"),
            FinancialMetric(name="OP Income", value="20B", unit="JPY"),
        ]
        ts_table = TimeSeriesTable(raw_table=raw, periods=["FY2024"], metrics=metrics)
        assert len(ts_table.metrics) == 2

    def test_異常系_periodsが空でValidationError(self) -> None:
        raw = self._make_raw_table()
        with pytest.raises(ValidationError):
            TimeSeriesTable(
                raw_table=raw,
                periods=[],
                metrics=[FinancialMetric(name="X", value="1", unit="JPY")],
            )

    def test_異常系_metricsが空でValidationError(self) -> None:
        raw = self._make_raw_table()
        with pytest.raises(ValidationError):
            TimeSeriesTable(raw_table=raw, periods=["FY2024"], metrics=[])


# ---------------------------------------------------------------------------
# Tier 2: EstimateChangeTable
# ---------------------------------------------------------------------------


class TestEstimateChangeTable:
    """Tests for EstimateChangeTable Pydantic model (Tier 2)."""

    def _make_raw_table(self) -> RawTable:
        cells = [TableCell(row=0, col=0, value="EPS")]
        return RawTable(page_number=2, bbox=[0, 0, 200, 100], cells=cells)

    def test_正常系_必須フィールドで生成できる(self) -> None:
        raw = self._make_raw_table()
        table = EstimateChangeTable(
            raw_table=raw,
            metric_name="EPS",
            previous_estimate=120.0,
            new_estimate=135.0,
            change_rate=0.125,
        )
        assert table.metric_name == "EPS"
        assert table.previous_estimate == 120.0
        assert table.new_estimate == 135.0
        assert table.change_rate == pytest.approx(0.125)

    def test_正常系_periodフィールドのデフォルト値はNone(self) -> None:
        raw = self._make_raw_table()
        table = EstimateChangeTable(
            raw_table=raw,
            metric_name="Revenue",
            previous_estimate=100.0,
            new_estimate=110.0,
            change_rate=0.1,
        )
        assert table.period is None

    def test_正常系_periodを設定できる(self) -> None:
        raw = self._make_raw_table()
        table = EstimateChangeTable(
            raw_table=raw,
            metric_name="Revenue",
            previous_estimate=100.0,
            new_estimate=110.0,
            change_rate=0.1,
            period="FY2025E",
        )
        assert table.period == "FY2025E"

    def test_異常系_metric_nameが空でValidationError(self) -> None:
        raw = self._make_raw_table()
        with pytest.raises(ValidationError):
            EstimateChangeTable(
                raw_table=raw,
                metric_name="",
                previous_estimate=100.0,
                new_estimate=110.0,
                change_rate=0.1,
            )


# ---------------------------------------------------------------------------
# Tier 2: KeyValueTable
# ---------------------------------------------------------------------------


class TestKeyValueTable:
    """Tests for KeyValueTable Pydantic model (Tier 2)."""

    def _make_raw_table(self) -> RawTable:
        cells = [TableCell(row=0, col=0, value="Rating")]
        return RawTable(page_number=3, bbox=[0, 0, 200, 100], cells=cells)

    def test_正常系_必須フィールドで生成できる(self) -> None:
        raw = self._make_raw_table()
        table = KeyValueTable(
            raw_table=raw,
            entries={"Rating": "Buy", "Target Price": "3000 JPY"},
        )
        assert table.entries["Rating"] == "Buy"
        assert table.entries["Target Price"] == "3000 JPY"

    def test_正常系_entriesが単一エントリでも動作する(self) -> None:
        raw = self._make_raw_table()
        table = KeyValueTable(raw_table=raw, entries={"Rating": "Overweight"})
        assert len(table.entries) == 1

    def test_異常系_entriesが空でValidationError(self) -> None:
        raw = self._make_raw_table()
        with pytest.raises(ValidationError):
            KeyValueTable(raw_table=raw, entries={})


# ---------------------------------------------------------------------------
# Tier 3: ExtractedTables
# ---------------------------------------------------------------------------


class TestExtractedTables:
    """Tests for ExtractedTables envelope Pydantic model (Tier 3)."""

    def _make_raw_table(self, page: int = 1) -> RawTable:
        cells = [TableCell(row=0, col=0, value="X")]
        return RawTable(page_number=page, bbox=[0, 0, 100, 50], cells=cells)

    def test_正常系_raw_tablesのみで生成できる(self) -> None:
        raw = self._make_raw_table()
        extracted = ExtractedTables(
            pdf_path="data/raw/report.pdf",
            raw_tables=[raw],
        )
        assert extracted.pdf_path == "data/raw/report.pdf"
        assert len(extracted.raw_tables) == 1

    def test_正常系_全フィールドで生成できる(self) -> None:
        raw = self._make_raw_table()
        ts_table = TimeSeriesTable(
            raw_table=raw,
            periods=["FY2024"],
            metrics=[FinancialMetric(name="Revenue", value="100B", unit="JPY")],
        )
        extracted = ExtractedTables(
            pdf_path="data/raw/report.pdf",
            raw_tables=[raw],
            time_series_tables=[ts_table],
        )
        assert len(extracted.time_series_tables) == 1

    def test_正常系_tier2フィールドのデフォルト値は空リスト(self) -> None:
        raw = self._make_raw_table()
        extracted = ExtractedTables(
            pdf_path="data/raw/report.pdf",
            raw_tables=[raw],
        )
        assert extracted.time_series_tables == []
        assert extracted.estimate_change_tables == []
        assert extracted.key_value_tables == []

    def test_正常系_複数raw_tablesを保持できる(self) -> None:
        raw1 = self._make_raw_table(page=1)
        raw2 = self._make_raw_table(page=2)
        extracted = ExtractedTables(
            pdf_path="report.pdf",
            raw_tables=[raw1, raw2],
        )
        assert len(extracted.raw_tables) == 2

    def test_異常系_raw_tablesが空でValidationError(self) -> None:
        # Tier 1 (RawTable) は必ず存在することを保証
        with pytest.raises(ValidationError):
            ExtractedTables(pdf_path="report.pdf", raw_tables=[])

    def test_正常系_JSONシリアライズが動作する(self) -> None:
        raw = self._make_raw_table()
        extracted = ExtractedTables(
            pdf_path="data/raw/report.pdf",
            raw_tables=[raw],
        )
        json_str = extracted.model_dump_json()
        data = json.loads(json_str)
        assert data["pdf_path"] == "data/raw/report.pdf"
        assert len(data["raw_tables"]) == 1


# ---------------------------------------------------------------------------
# Fallback guarantee: RawTable is always present even when Tier 2 fails
# ---------------------------------------------------------------------------


class TestRawTableFallback:
    """Tests for RawTable fallback guarantee in ExtractedTables.

    Verifies that Tier 1 (RawTable) is always preserved even when
    Tier 2 classification fails (no TimeSeriesTable produced).
    """

    def test_正常系_Tier2失敗時もTier1が保持される(self) -> None:
        """When Tier 2 classification fails, ExtractedTables still contains raw_tables."""
        raw = RawTable(
            page_number=1,
            bbox=[0.0, 0.0, 200.0, 100.0],
            cells=[TableCell(row=0, col=0, value="Unknown Table")],
        )
        # Tier 2 fields are empty (classification failed)
        extracted = ExtractedTables(
            pdf_path="report.pdf",
            raw_tables=[raw],
            time_series_tables=[],
            estimate_change_tables=[],
            key_value_tables=[],
        )
        # Tier 1 must always be present
        assert len(extracted.raw_tables) == 1
        assert extracted.raw_tables[0].cells[0].value == "Unknown Table"
        # Tier 2 classification results are empty but that is valid
        assert extracted.time_series_tables == []

    def test_正常系_多段ヘッダーがRawTableで正しく表現できる(self) -> None:
        """Multi-level headers (list[list[TableCell]]) are correctly represented."""
        header_row_1 = [
            TableCell(row=0, col=0, value="Financial Data", is_header=True, colspan=3),
        ]
        header_row_2 = [
            TableCell(row=1, col=0, value="FY2023", is_header=True),
            TableCell(row=1, col=1, value="FY2024", is_header=True),
            TableCell(row=1, col=2, value="FY2025E", is_header=True),
        ]
        cells = [
            TableCell(row=2, col=0, value="100B"),
            TableCell(row=2, col=1, value="120B"),
            TableCell(row=2, col=2, value="135B"),
        ]
        raw = RawTable(
            page_number=1,
            bbox=[0, 0, 300, 200],
            cells=cells,
            headers=[header_row_1, header_row_2],
        )
        assert len(raw.headers) == 2
        assert raw.headers[0][0].colspan == 3
        assert len(raw.headers[1]) == 3
