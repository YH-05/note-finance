"""Internal text utility functions."""

from __future__ import annotations

from notebooklm.constants import TRUNCATION_SUFFIX


def truncate_text(text: str, max_length: int) -> tuple[str, bool]:
    """Truncate text to at most max_length characters.

    Parameters
    ----------
    text : str
        The text to potentially truncate.
    max_length : int
        Maximum character length. Must be a positive integer.

    Returns
    -------
    tuple[str, bool]
        (result_text, was_truncated)
    """
    if len(text) > max_length:
        return text[:max_length] + TRUNCATION_SUFFIX, True
    return text, False


__all__ = ["truncate_text"]
