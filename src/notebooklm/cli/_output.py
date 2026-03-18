"""Output formatting helpers for the nlm CLI.

Provides JSON and Rich-based human-readable output.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import click


def output_json(data: Any) -> None:
    """Print data as formatted JSON to stdout.

    Parameters
    ----------
    data : Any
        Data to serialize. Pydantic models are converted via ``.model_dump()``.
    """
    if hasattr(data, "model_dump"):
        data = data.model_dump(mode="json")
    elif isinstance(data, list):
        data = [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in data
        ]
    click.echo(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def output_error(message: str) -> None:
    """Print an error message to stderr and exit with code 1.

    Parameters
    ----------
    message : str
        Error message to display.
    """
    click.echo(f"Error: {message}", err=True)
    sys.exit(1)


def output_success(message: str) -> None:
    """Print a success message to stdout.

    Parameters
    ----------
    message : str
        Success message to display.
    """
    click.echo(message)


__all__ = ["output_error", "output_json", "output_success"]
