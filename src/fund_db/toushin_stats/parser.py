"""Parser for Investment Trust Association statistics Excel files.

Reads XLSX files using openpyxl and converts rows into Pydantic
model instances. Currently only B-1 (asset flow) parsing is
implemented; B-2, B-3, and A-2 are placeholders.

Classes
-------
ToushinStatsParser
    Parses statistics Excel files into model instances.

Examples
--------
>>> from pathlib import Path
>>> parser = ToushinStatsParser()
>>> # records = parser.parse_b1(Path(".tmp/toushin_B1_shisan_zougen.xlsx"))
"""

from __future__ import annotations

import contextlib
import math
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any

import openpyxl

if TYPE_CHECKING:
    from pathlib import Path

    from openpyxl.worksheet.worksheet import Worksheet

from fund_db._logging import get_logger
from fund_db.exceptions import ParseError
from fund_db.toushin_stats.models import (
    AssetFlowRecord,
    ManagementCompanyRecord,
    OverallStatusRecord,
    ProductClassRecord,
)

logger = get_logger(__name__, module="toushin_stats_parser")

_EMPTY_MARKERS = {"", "-", "None", "N/A"}
_YM_SLASH_RE = re.compile(r"^(\d{4})/(\d{1,2})$")
_YM_JP_RE = re.compile(r"^(\d{4})年(\d{1,2})月$")


def _to_float(value: Any) -> float | None:
    """Convert a cell value to float or None.

    Parameters
    ----------
    value : Any
        Raw cell value from openpyxl.

    Returns
    -------
    float | None
        Numeric value as float, or None if empty/invalid.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        is_invalid = isinstance(value, float) and (
            math.isnan(value) or math.isinf(value)
        )
        return None if is_invalid else float(value)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if stripped in _EMPTY_MARKERS:
        return None
    try:
        return float(stripped.replace(",", ""))
    except ValueError:
        return None


def _parse_ym_parts(year: int, month: int) -> str | None:
    """Validate and format year/month parts into "YYYY-MM"."""
    if 1 <= month <= 12 and 1900 <= year <= 2100:
        return f"{year:04d}-{month:02d}"
    return None


def _to_year_month(value: Any) -> str | None:
    """Convert a cell value to "YYYY-MM" format string or None.

    Handles various formats: "2024/1", "2024-01", "2024年1月",
    datetime objects, etc.

    Parameters
    ----------
    value : Any
        Raw cell value from openpyxl.

    Returns
    -------
    str | None
        Year-month string in "YYYY-MM" format, or None if invalid.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m")

    text = str(value).strip()
    if not text or text in _EMPTY_MARKERS:
        return None

    # Try "YYYY-MM" format
    result: str | None = None
    if len(text) == 7 and text[4] == "-":
        with contextlib.suppress(ValueError):
            result = _parse_ym_parts(int(text[:4]), int(text[5:7]))

    # Try "YYYY/M" or "YYYY/MM" format
    if result is None:
        m_slash = _YM_SLASH_RE.match(text)
        if m_slash:
            result = _parse_ym_parts(int(m_slash.group(1)), int(m_slash.group(2)))

    # Try "YYYY年M月" format
    if result is None:
        m_jp = _YM_JP_RE.match(text)
        if m_jp:
            result = _parse_ym_parts(int(m_jp.group(1)), int(m_jp.group(2)))

    return result


class ToushinStatsParser:
    """Parses Investment Trust Association statistics Excel files.

    Currently implements B-1 (asset flow) parsing only.
    B-2, B-3, and A-2 are placeholder methods that raise
    ``NotImplementedError``.

    Examples
    --------
    >>> parser = ToushinStatsParser()
    """

    def _find_header_row_b1(
        self,
        sheet: Worksheet,
    ) -> tuple[int, dict[int, str]]:
        """Find the header row for B-1 asset flow data.

        Searches for rows containing known column headers such as
        "pure asset total amount" or "subscription" or "redemption" keywords.

        Parameters
        ----------
        sheet : Worksheet
            openpyxl worksheet to search.

        Returns
        -------
        tuple[int, dict[int, str]]
            Header row number (1-based) and mapping from
            column index (0-based) to field name.

        Raises
        ------
        ParseError
            If no header row is found.
        """
        # Known header keywords for B-1
        header_keywords: dict[str, str] = {
            "純資産": "net_assets",
            "設定": "inflow",
            "解約": "outflow",
            "純増減": "net_flow",
            "増減": "net_flow",
        }

        for row_idx, row in enumerate(
            sheet.iter_rows(max_row=30, values_only=False), start=1
        ):
            matched_fields = self._match_header_cells(row, header_keywords)
            if len(matched_fields) >= 2:
                logger.debug(
                    "B-1 header row found",
                    row=row_idx,
                    matched_columns=len(matched_fields),
                )
                return row_idx, matched_fields

        msg = "B-1 header row not found in worksheet"
        raise ParseError(
            msg,
            source=sheet.title or "unknown",
            reason="No matching header row for B-1 data",
        )

    @staticmethod
    def _match_header_cells(
        row: tuple[Any, ...],
        keywords: dict[str, str],
    ) -> dict[int, str]:
        """Match cells in a row against header keyword patterns.

        Parameters
        ----------
        row : tuple
            Row of cells from openpyxl.
        keywords : dict[str, str]
            Mapping from keyword to field name.

        Returns
        -------
        dict[int, str]
            Column index (0-based) -> field name for matched cells.
        """
        matched: dict[int, str] = {}
        for cell in row:
            if cell.value is None:
                continue
            text = str(cell.value).strip()
            for keyword, field_name in keywords.items():
                if keyword in text and field_name not in matched.values():
                    matched[cell.column - 1] = field_name
                    break
        return matched

    def _detect_year_month_column(
        self,
        sheet: Worksheet,
        header_row: int,
        col_map: dict[int, str],
    ) -> int | None:
        """Detect which column contains year-month values.

        Parameters
        ----------
        sheet : Worksheet
            openpyxl worksheet.
        header_row : int
            1-based row number of the header.
        col_map : dict[int, str]
            Known column mappings (to exclude).

        Returns
        -------
        int | None
            0-based column index, or None if not found.
        """
        for row in sheet.iter_rows(
            min_row=header_row + 1,
            max_row=header_row + 5,
            values_only=False,
        ):
            for cell in row:
                if cell.column is None:
                    continue
                col_idx = cell.column - 1
                if col_idx not in col_map:
                    ym = _to_year_month(cell.value)
                    if ym is not None:
                        return col_idx
        return None

    def _extract_year_month(
        self,
        row: tuple[Any, ...],
        year_month_col: int | None,
    ) -> str | None:
        """Extract year-month from a data row.

        Parameters
        ----------
        row : tuple
            Row of cells.
        year_month_col : int | None
            Detected year-month column index.

        Returns
        -------
        str | None
            Year-month in "YYYY-MM" format, or None.
        """
        if year_month_col is not None and year_month_col < len(row):
            ym_value = _to_year_month(row[year_month_col].value)
            if ym_value is not None:
                return ym_value
        # Fallback to first column
        if len(row) > 0:
            return _to_year_month(row[0].value)
        return None

    def parse_b1(self, path: Path) -> list[AssetFlowRecord]:
        """Parse B-1 (asset flow) Excel file.

        Reads the first sheet of the workbook, finds the header row,
        and converts each data row to an ``AssetFlowRecord``.

        Parameters
        ----------
        path : Path
            Path to the B-1 XLSX file.

        Returns
        -------
        list[AssetFlowRecord]
            Parsed asset flow records.

        Raises
        ------
        ParseError
            If the file cannot be read or parsed.
        """
        logger.info("Parsing B-1 asset flow Excel", path=str(path))
        try:
            wb = openpyxl.load_workbook(path, data_only=True)
        except Exception as exc:
            raise ParseError(
                f"Failed to open workbook: {exc}",
                source=str(path),
                reason=str(exc),
            ) from exc

        try:
            sheet = wb.active
            if sheet is None:
                raise ParseError(
                    "No active sheet found",
                    source=str(path),
                    reason="Workbook has no active sheet",
                )

            header_row, col_map = self._find_header_row_b1(sheet)
            year_month_col = self._detect_year_month_column(sheet, header_row, col_map)
            records = self._read_b1_rows(sheet, header_row, col_map, year_month_col)
        finally:
            wb.close()

        logger.info(
            "B-1 parsing complete",
            record_count=len(records),
            path=str(path),
        )
        return records

    def _read_b1_rows(
        self,
        sheet: Worksheet,
        header_row: int,
        col_map: dict[int, str],
        year_month_col: int | None,
    ) -> list[AssetFlowRecord]:
        """Read data rows from B-1 sheet and convert to records.

        Parameters
        ----------
        sheet : Worksheet
            openpyxl worksheet.
        header_row : int
            1-based header row number.
        col_map : dict[int, str]
            Column index -> field name mapping.
        year_month_col : int | None
            Detected year-month column index.

        Returns
        -------
        list[AssetFlowRecord]
            Parsed records.
        """
        records: list[AssetFlowRecord] = []
        for row_idx, row in enumerate(
            sheet.iter_rows(min_row=header_row + 1, values_only=False),
            start=header_row + 1,
        ):
            ym_value = self._extract_year_month(row, year_month_col)
            if ym_value is None:
                continue

            row_data: dict[str, float | None] = {}
            for col_idx, field_name in col_map.items():
                if col_idx < len(row):
                    row_data[field_name] = _to_float(row[col_idx].value)

            if all(v is None for v in row_data.values()):
                continue

            try:
                record = AssetFlowRecord(
                    year_month=ym_value,
                    net_assets=row_data.get("net_assets"),
                    inflow=row_data.get("inflow"),
                    outflow=row_data.get("outflow"),
                    net_flow=row_data.get("net_flow"),
                )
                records.append(record)
            except Exception as exc:
                logger.warning(
                    "Failed to parse B-1 row",
                    row=row_idx,
                    error=str(exc),
                )
        return records

    def parse_b2(self, path: Path) -> list[ProductClassRecord]:
        """Parse B-2 (product class) Excel file.

        Parameters
        ----------
        path : Path
            Path to the B-2 XLSX file.

        Returns
        -------
        list[ProductClassRecord]
            Parsed product class records.

        Raises
        ------
        NotImplementedError
            Always raised; B-2 parsing is not yet implemented.
        """
        raise NotImplementedError("B-2 parsing is not yet implemented")

    def parse_b3(self, path: Path) -> list[ManagementCompanyRecord]:
        """Parse B-3 (management company) Excel file.

        Parameters
        ----------
        path : Path
            Path to the B-3 XLSX file.

        Returns
        -------
        list[ManagementCompanyRecord]
            Parsed management company records.

        Raises
        ------
        NotImplementedError
            Always raised; B-3 parsing is not yet implemented.
        """
        raise NotImplementedError("B-3 parsing is not yet implemented")

    def parse_a2(self, path: Path) -> list[OverallStatusRecord]:
        """Parse A-2 (overall status) Excel file.

        Parameters
        ----------
        path : Path
            Path to the A-2 XLSX file.

        Returns
        -------
        list[OverallStatusRecord]
            Parsed overall status records.

        Raises
        ------
        NotImplementedError
            Always raised; A-2 parsing is not yet implemented.
        """
        raise NotImplementedError("A-2 parsing is not yet implemented")
