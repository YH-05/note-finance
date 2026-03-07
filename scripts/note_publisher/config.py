"""Configuration loader for the note_publisher package.

Provides ``load_config()`` which creates a ``NotePublisherConfig`` instance
with optional overrides from environment variables.

Supported environment variables
-------------------------------
NOTE_HEADLESS
    Override ``headless`` (accepts ``true``/``false``, ``1``/``0``).
NOTE_TIMEOUT_MS
    Override ``timeout_ms`` (integer >= 1000).
NOTE_TYPING_DELAY_MS
    Override ``typing_delay_ms`` (integer >= 0).
NOTE_SESSION_PATH
    Override ``storage_state_path`` (file path string).

Examples
--------
>>> config = load_config()
>>> config.headless
True
>>> config.timeout_ms
30000
"""

from __future__ import annotations

import os
from pathlib import Path

import structlog
from note_publisher.types import NotePublisherConfig
from pydantic import ValidationError

logger = structlog.get_logger(__name__)

# AIDEV-NOTE: Truthy values for boolean environment variable parsing.
_TRUTHY_VALUES = frozenset({"true", "1", "yes"})
_FALSY_VALUES = frozenset({"false", "0", "no"})


def _parse_bool_env(env_var: str) -> bool | None:
    """Parse a boolean environment variable.

    Parameters
    ----------
    env_var : str
        Name of the environment variable to read.

    Returns
    -------
    bool | None
        Parsed boolean value, or ``None`` if the variable is not set
        or has an empty/unrecognised value.
    """
    raw = os.environ.get(env_var, "").strip().lower()
    if not raw:
        return None
    if raw in _TRUTHY_VALUES:
        return True
    if raw in _FALSY_VALUES:
        return False
    logger.warning("invalid_bool_env_var", env_var=env_var, value=raw)
    return None


def _parse_int_env(env_var: str) -> int | None:
    """Parse an integer environment variable.

    Parameters
    ----------
    env_var : str
        Name of the environment variable to read.

    Returns
    -------
    int | None
        Parsed integer value, or ``None`` if the variable is not set,
        empty, or not a valid integer.
    """
    raw = os.environ.get(env_var, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        logger.warning("invalid_int_env_var", env_var=env_var, value=raw)
        return None


def _parse_path_env(env_var: str) -> Path | None:
    """Parse a file-path environment variable.

    Parameters
    ----------
    env_var : str
        Name of the environment variable to read.

    Returns
    -------
    Path | None
        Parsed ``Path`` object, or ``None`` if the variable is not set
        or empty.
    """
    raw = os.environ.get(env_var, "").strip()
    if not raw:
        return None
    return Path(raw)


def load_config() -> NotePublisherConfig:
    """Load a ``NotePublisherConfig``, applying environment-variable overrides.

    Reads the environment variables ``NOTE_HEADLESS``, ``NOTE_TIMEOUT_MS``,
    ``NOTE_TYPING_DELAY_MS``, and ``NOTE_SESSION_PATH``.  For each variable
    that is set and valid, the corresponding config field is overridden.
    Invalid values are logged and silently ignored, falling back to the
    default.

    Returns
    -------
    NotePublisherConfig
        Fully resolved configuration instance.

    Examples
    --------
    >>> import os
    >>> os.environ["NOTE_HEADLESS"] = "false"
    >>> config = load_config()
    >>> config.headless
    False
    """
    logger.debug("loading_config")

    overrides: dict[str, object] = {}

    # --- headless ---
    headless = _parse_bool_env("NOTE_HEADLESS")
    if headless is not None:
        overrides["headless"] = headless

    # --- timeout_ms ---
    timeout_ms = _parse_int_env("NOTE_TIMEOUT_MS")
    if timeout_ms is not None:
        overrides["timeout_ms"] = timeout_ms

    # --- typing_delay_ms ---
    typing_delay_ms = _parse_int_env("NOTE_TYPING_DELAY_MS")
    if typing_delay_ms is not None:
        overrides["typing_delay_ms"] = typing_delay_ms

    # --- storage_state_path ---
    session_path = _parse_path_env("NOTE_SESSION_PATH")
    if session_path is not None:
        overrides["storage_state_path"] = session_path

    # Build config with overrides. If a Pydantic validation error occurs
    # (e.g. timeout_ms < 1000), log the error and fall back to defaults
    # for the offending fields.
    try:
        config = NotePublisherConfig(**overrides)  # type: ignore[arg-type]
    except ValidationError as exc:
        logger.warning(
            "config_validation_error",
            error=str(exc),
            overrides=overrides,
        )
        # Retry without the fields that caused validation failures.
        failed_fields = {e["loc"][0] for e in exc.errors() if e.get("loc")}
        safe_overrides = {k: v for k, v in overrides.items() if k not in failed_fields}
        config = NotePublisherConfig(**safe_overrides)  # type: ignore[arg-type]

    logger.info(
        "config_loaded",
        headless=config.headless,
        timeout_ms=config.timeout_ms,
        typing_delay_ms=config.typing_delay_ms,
        storage_state_path=str(config.storage_state_path),
    )

    return config
