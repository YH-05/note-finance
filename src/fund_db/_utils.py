"""Shared utility functions for the fund_db package.

Functions
---------
normalize_cell_value
    Normalize an Excel cell value to a string or None.
"""

from __future__ import annotations

from typing import Any


def normalize_cell_value(value: Any, *, nan_check: bool = False) -> str | None:
    """Normalize a cell value to a string or None.

    Converts None, empty strings, and the literal ``"None"`` to None.
    When ``nan_check`` is True, also converts pandas NaN values
    and the literal ``"nan"`` string to None.

    Parameters
    ----------
    value : Any
        Raw cell value from openpyxl or pandas.
    nan_check : bool
        If True, additionally check for NaN via ``pandas.isna``
        and treat the string ``"nan"`` as empty.

    Returns
    -------
    str | None
        Stripped string if non-empty, otherwise None.
    """
    if value is None:
        return None
    if nan_check:
        import pandas as pd

        if pd.isna(value):
            return None
    text = str(value).strip()
    empty_markers = {"", "None"}
    if nan_check:
        empty_markers.add("nan")
    if text in empty_markers:
        return None
    return text
