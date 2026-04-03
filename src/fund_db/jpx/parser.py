"""Parser for JPX listed securities XLS files.

Reads XLS files using ``pandas.read_excel`` with the ``xlrd`` engine,
maps columns via the dictionary in ``fund_db.config.constants``,
and returns ``JpxListedStock`` Pydantic model instances.

Classes
-------
JpxParser
    Parses JPX listed securities XLS files.

Examples
--------
>>> parser = JpxParser()
>>> # stocks = parser.parse(Path(".tmp/jpx_listed_stocks.xls"))
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd

from fund_db._logging import get_logger
from fund_db.config.constants import JPX_EXCEL_ENGINE, JPX_LISTED_COLUMNS
from fund_db.exceptions import ParseError
from fund_db.jpx.models import JpxListedStock

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__, module="jpx_parser")


def _normalize_value(value: Any) -> str | None:
    """Normalize a cell value to a string or None.

    Converts NaN, None, and empty strings to None.
    All other values are converted to stripped strings.

    Parameters
    ----------
    value : Any
        Raw cell value from pandas DataFrame.

    Returns
    -------
    str | None
        Stripped string if non-empty, otherwise None.
    """
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if text in {"", "None", "nan"}:
        return None
    return text


class JpxParser:
    """Parses JPX listed securities XLS files.

    Reads XLS files using pandas with the engine specified by
    ``JPX_EXCEL_ENGINE``, renames columns using ``JPX_LISTED_COLUMNS``,
    and converts each row into a ``JpxListedStock`` Pydantic model.

    Examples
    --------
    >>> parser = JpxParser()
    """

    def parse(self, path: Path) -> list[JpxListedStock]:
        """Parse the JPX listed securities XLS file.

        Parameters
        ----------
        path : Path
            Path to the XLS file.

        Returns
        -------
        list[JpxListedStock]
            Parsed listed stock records.

        Raises
        ------
        ParseError
            If the file cannot be read or parsed.
        """
        logger.info("Parsing JPX listed securities", path=str(path))
        try:
            df = pd.read_excel(path, engine=JPX_EXCEL_ENGINE, dtype=str)
        except Exception as exc:
            raise ParseError(
                f"Failed to read XLS file: {exc}",
                source=str(path),
                reason=str(exc),
            ) from exc

        # Rename columns from Japanese to English field names
        reverse_mapping = {jp: en for jp, en in JPX_LISTED_COLUMNS.items()}
        df = df.rename(columns=reverse_mapping)

        records: list[JpxListedStock] = []
        for row_idx, row in df.iterrows():
            row_data: dict[str, str | None] = {}
            for field_name in JPX_LISTED_COLUMNS.values():
                if field_name in row.index:
                    row_data[field_name] = _normalize_value(row[field_name])
                else:
                    row_data[field_name] = None

            # Required fields check
            ticker = row_data.get("ticker_code")
            name = row_data.get("name")
            if not ticker or not name:
                logger.debug(
                    "Skipping row with missing required fields",
                    row=row_idx,
                )
                continue

            try:
                stock = JpxListedStock(
                    ticker_code=ticker,
                    name=name,
                    market_segment=row_data.get("market_segment"),
                    sector_code_33=row_data.get("sector_code_33"),
                    sector_name_33=row_data.get("sector_name_33"),
                    sector_code_17=row_data.get("sector_code_17"),
                    sector_name_17=row_data.get("sector_name_17"),
                    size_code=row_data.get("size_code"),
                    size_category=row_data.get("size_category"),
                )
                records.append(stock)
            except Exception as exc:
                logger.warning(
                    "Failed to parse row",
                    row=row_idx,
                    error=str(exc),
                )

        logger.info(
            "JPX parsing complete",
            record_count=len(records),
            path=str(path),
        )
        return records

    def parse_etfs_only(self, path: Path) -> list[JpxListedStock]:
        """Parse the JPX file and return only ETF/ETN records.

        Parameters
        ----------
        path : Path
            Path to the XLS file.

        Returns
        -------
        list[JpxListedStock]
            Only records where ``is_etf`` is True.

        Raises
        ------
        ParseError
            If the file cannot be read or parsed.
        """
        all_stocks = self.parse(path)
        etfs = [s for s in all_stocks if s.is_etf]
        logger.info(
            "ETF filtering complete",
            total=len(all_stocks),
            etf_count=len(etfs),
        )
        return etfs
