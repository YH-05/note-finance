"""Async-to-sync bridge for Click commands.

All NotebookLM service methods are async (Playwright operations).
Click commands are synchronous. This module provides the bridge.
"""

from __future__ import annotations

import asyncio
from functools import wraps
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

P = ParamSpec("P")
R = TypeVar("R")


def run_async(coro_func: Callable[P, Coroutine[Any, Any, R]]) -> Callable[P, R]:
    """Wrap an async function so it can be called synchronously by Click.

    Parameters
    ----------
    coro_func : Callable
        An async function to wrap.

    Returns
    -------
    Callable
        A synchronous wrapper that calls ``asyncio.run()``.
    """

    @wraps(coro_func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        return asyncio.run(coro_func(*args, **kwargs))

    return wrapper


__all__ = ["run_async"]
