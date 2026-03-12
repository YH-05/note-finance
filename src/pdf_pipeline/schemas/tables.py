"""3-tier Pydantic table schema definitions for the pdf_pipeline package.

Defines a 3-tier hierarchy for structured extraction of financial tables
from PDF cell-side reports.

Tier 1 (always generated, fallback guarantee)
---------------------------------------------
TableCell
    A single cell within a table, with position and optional span info.
RawTable
    Raw table extracted from a PDF page: list of cells, optional multi-level
    headers, bounding box, and an optional reference to the cropped image.

Tier 2 (generated only when classification succeeds)
-----------------------------------------------------
FinancialMetric
    A single financial metric extracted from a table (name, value, unit, period).
TimeSeriesTable
    Time-series financial data table (revenue, OP income, EPS over multiple
    fiscal periods).
EstimateChangeTable
    Table showing a change in analyst estimates for a metric.
KeyValueTable
    Generic key-value pairs extracted from a table (e.g., rating, target price).

Tier 3 (1 PDF envelope)
-----------------------
ExtractedTables
    Envelope model for all tables extracted from a single PDF document.
    ``raw_tables`` is always non-empty (Tier 1 fallback guarantee).

Examples
--------
>>> cell = TableCell(row=0, col=0, value="Revenue")
>>> raw = RawTable(page_number=1, bbox=[0, 0, 200, 100], cells=[cell])
>>> extracted = ExtractedTables(pdf_path="report.pdf", raw_tables=[raw])
>>> extracted.pdf_path
'report.pdf'
>>> len(extracted.raw_tables)
1
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Tier 1: TableCell
# ---------------------------------------------------------------------------


class TableCell(BaseModel):
    """A single cell within a table.

    Attributes
    ----------
    row : int
        Zero-based row index of this cell within the table.
    col : int
        Zero-based column index of this cell within the table.
    value : str
        Text content of the cell.
    rowspan : int
        Number of rows this cell spans (default: 1).
    colspan : int
        Number of columns this cell spans (default: 1).
    is_header : bool
        Whether this cell is a header cell (default: False).

    Examples
    --------
    >>> cell = TableCell(row=0, col=0, value="Revenue")
    >>> cell.rowspan
    1
    >>> cell.is_header
    False
    """

    row: Annotated[int, Field(ge=0, description="Zero-based row index")]
    col: Annotated[int, Field(ge=0, description="Zero-based column index")]
    value: str = Field(description="Text content of the cell")
    rowspan: Annotated[int, Field(ge=1, description="Number of rows spanned")] = 1
    colspan: Annotated[int, Field(ge=1, description="Number of columns spanned")] = 1
    is_header: bool = Field(default=False, description="Whether this is a header cell")


# ---------------------------------------------------------------------------
# Tier 1: RawTable
# ---------------------------------------------------------------------------


class RawTable(BaseModel):
    """Raw table extracted from a PDF page.

    This is the Tier 1 representation that is *always* generated.
    Even when Tier 2 classification fails, ``RawTable`` provides a
    fallback guarantee: all cell data is preserved.

    Attributes
    ----------
    page_number : int
        1-based page number where this table appears.
    bbox : list[float]
        Bounding box as ``[x0, y0, x1, y1]`` in PDF point units.
        Must have exactly 4 elements.
    cells : list[TableCell]
        All cells in the table in reading order.  Must be non-empty.
    headers : list[list[TableCell]]
        Multi-level header rows.  Each inner list is one header row.
        Empty list when no headers are identified (default).
    row_count : int | None
        Total number of data rows (excluding headers), if known.
    col_count : int | None
        Total number of columns, if known.
    image_path : str | None
        Absolute path to the PNG image of this table region, set by
        ``TableDetector`` after extracting the table from the PDF.

    Examples
    --------
    >>> cell = TableCell(row=0, col=0, value="Revenue")
    >>> raw = RawTable(page_number=1, bbox=[0.0, 0.0, 200.0, 100.0], cells=[cell])
    >>> raw.headers
    []
    >>> raw.image_path is None
    True
    """

    page_number: Annotated[int, Field(ge=1, description="1-based page number")]
    bbox: Annotated[
        list[float],
        Field(min_length=4, max_length=4, description="[x0, y0, x1, y1] bounding box"),
    ]
    cells: Annotated[
        list[TableCell],
        Field(min_length=1, description="All cells in the table"),
    ]
    headers: list[list[TableCell]] = Field(
        default_factory=list,
        description="Multi-level header rows (list of header rows)",
    )
    row_count: int | None = Field(default=None, description="Total number of data rows")
    col_count: int | None = Field(default=None, description="Total number of columns")
    image_path: str | None = Field(
        default=None,
        description="Path to the PNG image of this table region",
    )


# ---------------------------------------------------------------------------
# Tier 2: FinancialMetric
# ---------------------------------------------------------------------------


class FinancialMetric(BaseModel):
    """A single financial metric extracted from a table.

    Attributes
    ----------
    name : str
        Metric name (e.g., "Revenue", "OP Income", "EPS").  Must be non-empty.
    value : str
        Metric value as a string to preserve original formatting.
    unit : str
        Unit of the value (e.g., "JPY", "%", "Billion JPY").
    period : str | None
        Fiscal period label (e.g., "FY2024", "1H2025").  ``None`` if not
        period-specific.
    notes : str | None
        Any additional notes or footnote references.

    Examples
    --------
    >>> m = FinancialMetric(name="Revenue", value="100B", unit="JPY")
    >>> m.period is None
    True
    """

    name: Annotated[str, Field(min_length=1, description="Metric name")]
    value: str = Field(description="Metric value as string")
    unit: str = Field(description="Unit of the metric value")
    period: str | None = Field(default=None, description="Fiscal period label")
    notes: str | None = Field(default=None, description="Additional notes")


# ---------------------------------------------------------------------------
# Tier 2: TimeSeriesTable
# ---------------------------------------------------------------------------


class TimeSeriesTable(BaseModel):
    """Time-series financial data table (Tier 2).

    Represents a table that shows one or more financial metrics across
    multiple fiscal periods (e.g., revenue for FY2022, FY2023, FY2024).

    Attributes
    ----------
    raw_table : RawTable
        The underlying Tier 1 raw table this was classified from.
    periods : list[str]
        Ordered list of fiscal period labels.  Must be non-empty.
    metrics : list[FinancialMetric]
        Extracted financial metrics.  Must be non-empty.

    Examples
    --------
    >>> cell = TableCell(row=0, col=0, value="Revenue")
    >>> raw = RawTable(page_number=1, bbox=[0, 0, 200, 100], cells=[cell])
    >>> metric = FinancialMetric(name="Revenue", value="100B", unit="JPY")
    >>> ts = TimeSeriesTable(raw_table=raw, periods=["FY2024"], metrics=[metric])
    >>> len(ts.periods)
    1
    """

    raw_table: RawTable = Field(description="Underlying Tier 1 raw table")
    periods: Annotated[
        list[str],
        Field(min_length=1, description="Ordered fiscal period labels"),
    ]
    metrics: Annotated[
        list[FinancialMetric],
        Field(min_length=1, description="Extracted financial metrics"),
    ]


# ---------------------------------------------------------------------------
# Tier 2: EstimateChangeTable
# ---------------------------------------------------------------------------


class EstimateChangeTable(BaseModel):
    """Analyst estimate change table (Tier 2).

    Captures before/after analyst estimate revisions for a specific metric.

    Attributes
    ----------
    raw_table : RawTable
        The underlying Tier 1 raw table.
    metric_name : str
        Name of the metric being revised.  Must be non-empty.
    previous_estimate : float
        Previous (old) estimate value.
    new_estimate : float
        New (revised) estimate value.
    change_rate : float
        Change rate as a decimal fraction (e.g., 0.125 for +12.5%).
    period : str | None
        Fiscal period this estimate applies to (e.g., "FY2025E").

    Examples
    --------
    >>> cell = TableCell(row=0, col=0, value="EPS")
    >>> raw = RawTable(page_number=2, bbox=[0, 0, 200, 100], cells=[cell])
    >>> t = EstimateChangeTable(
    ...     raw_table=raw, metric_name="EPS",
    ...     previous_estimate=120.0, new_estimate=135.0, change_rate=0.125
    ... )
    >>> t.metric_name
    'EPS'
    """

    raw_table: RawTable = Field(description="Underlying Tier 1 raw table")
    metric_name: Annotated[str, Field(min_length=1, description="Metric name")]
    previous_estimate: float = Field(description="Previous estimate value")
    new_estimate: float = Field(description="New estimate value")
    change_rate: float = Field(description="Change rate as decimal fraction")
    period: str | None = Field(
        default=None, description="Fiscal period for this estimate"
    )


# ---------------------------------------------------------------------------
# Tier 2: KeyValueTable
# ---------------------------------------------------------------------------


class KeyValueTable(BaseModel):
    """Generic key-value table (Tier 2).

    Captures tables that represent key-value pairs, such as analyst
    ratings, target prices, and investment summaries.

    Attributes
    ----------
    raw_table : RawTable
        The underlying Tier 1 raw table.
    entries : dict[str, str]
        Extracted key-value pairs.  Must be non-empty.

    Examples
    --------
    >>> cell = TableCell(row=0, col=0, value="Rating")
    >>> raw = RawTable(page_number=3, bbox=[0, 0, 200, 100], cells=[cell])
    >>> kv = KeyValueTable(raw_table=raw, entries={"Rating": "Buy"})
    >>> kv.entries["Rating"]
    'Buy'
    """

    raw_table: RawTable = Field(description="Underlying Tier 1 raw table")
    entries: Annotated[
        dict[str, str],
        Field(min_length=1, description="Key-value pairs extracted from the table"),
    ]


# ---------------------------------------------------------------------------
# Tier 3: ExtractedTables (1-PDF envelope)
# ---------------------------------------------------------------------------


class ExtractedTables(BaseModel):
    """Envelope model for all tables extracted from a single PDF (Tier 3).

    ``raw_tables`` is guaranteed to be non-empty: Tier 1 (RawTable) is
    always produced regardless of whether Tier 2 classification succeeds.

    Attributes
    ----------
    pdf_path : str
        Path to the source PDF file.
    raw_tables : list[RawTable]
        All raw tables extracted from the PDF.  Must be non-empty (Tier 1
        fallback guarantee).
    time_series_tables : list[TimeSeriesTable]
        Time-series tables classified from raw tables.
        Empty when classification failed for all tables.
    estimate_change_tables : list[EstimateChangeTable]
        Estimate change tables classified from raw tables.
        Empty when none were identified.
    key_value_tables : list[KeyValueTable]
        Key-value tables classified from raw tables.
        Empty when none were identified.

    Examples
    --------
    >>> cell = TableCell(row=0, col=0, value="Revenue")
    >>> raw = RawTable(page_number=1, bbox=[0, 0, 200, 100], cells=[cell])
    >>> extracted = ExtractedTables(pdf_path="report.pdf", raw_tables=[raw])
    >>> extracted.time_series_tables
    []
    """

    pdf_path: str = Field(description="Path to the source PDF file")
    raw_tables: Annotated[
        list[RawTable],
        Field(
            min_length=1,
            description="All raw tables (Tier 1, always non-empty)",
        ),
    ]
    time_series_tables: list[TimeSeriesTable] = Field(
        default_factory=list,
        description="Classified time-series tables (Tier 2)",
    )
    estimate_change_tables: list[EstimateChangeTable] = Field(
        default_factory=list,
        description="Classified estimate change tables (Tier 2)",
    )
    key_value_tables: list[KeyValueTable] = Field(
        default_factory=list,
        description="Classified key-value tables (Tier 2)",
    )
