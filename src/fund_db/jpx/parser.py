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

from typing import TYPE_CHECKING

import pandas as pd

from fund_db._logging import get_logger
from fund_db._utils import normalize_cell_value
from fund_db.config.constants import JPX_EXCEL_ENGINE, JPX_LISTED_COLUMNS
from fund_db.exceptions import ParseError
from fund_db.jpx.models import JpxListedStock

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__, module="jpx_parser")


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

        # Drop rows missing required fields
        required_fields = ["ticker_code", "name"]
        for field in required_fields:
            if field not in df.columns:
                logger.warning("Required column missing", column=field)
                return []

        pre_count = len(df)
        df = df.dropna(subset=required_fields)
        dropped = pre_count - len(df)
        if dropped > 0:
            logger.debug(
                "Dropped rows with missing required fields",
                dropped_count=dropped,
            )

        # Convert NaN to None for all columns
        df = df.where(df.notna(), None)

        # Vectorized conversion to list of dicts
        row_dicts: list[dict[str, str | None]] = df.to_dict("records")

        records: list[JpxListedStock] = []
        for row_idx, row_data in enumerate(row_dicts):
            # Normalize cell values for mapped fields
            for field_name in JPX_LISTED_COLUMNS.values():
                if field_name in row_data:
                    raw = row_data[field_name]
                    row_data[field_name] = (
                        normalize_cell_value(raw, nan_check=True)
                        if raw is not None
                        else None
                    )

            try:
                stock = JpxListedStock.model_validate(row_data)
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
