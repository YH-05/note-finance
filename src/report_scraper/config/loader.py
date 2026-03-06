"""YAML configuration loader with Pydantic validation.

Loads a YAML configuration file and validates it against the
``ReportScraperConfig`` Pydantic model.

Functions
---------
load_config
    Load and validate a YAML configuration file.

Examples
--------
>>> from pathlib import Path
>>> config = load_config(Path("data/config/report-scraper-config.yaml"))
>>> config.global_config.max_reports_per_source
20
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import yaml
from pydantic import ValidationError

from report_scraper._logging import get_logger
from report_scraper.exceptions import ConfigError
from report_scraper.types import ReportScraperConfig

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__, module="config_loader")


def load_config(path: Path) -> ReportScraperConfig:
    """Load and validate a YAML configuration file.

    Reads the YAML file at ``path``, parses it, and validates the
    contents against ``ReportScraperConfig``.

    Parameters
    ----------
    path : Path
        Path to the YAML configuration file.

    Returns
    -------
    ReportScraperConfig
        Validated configuration object.

    Raises
    ------
    ConfigError
        If the file does not exist, cannot be parsed as YAML,
        or fails Pydantic validation.

    Examples
    --------
    >>> from pathlib import Path
    >>> config = load_config(Path("data/config/report-scraper-config.yaml"))
    >>> len(config.sources) > 0
    True
    """
    logger.debug("Loading configuration", path=str(path))

    if not path.exists():
        msg = f"Configuration file not found: {path}"
        logger.error(msg, path=str(path))
        raise ConfigError(msg, field="path")

    if not path.is_file():
        msg = f"Configuration path is not a file: {path}"
        logger.error(msg, path=str(path))
        raise ConfigError(msg, field="path")

    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as e:
        msg = f"Failed to read configuration file: {e}"
        logger.error(msg, path=str(path))
        raise ConfigError(msg, field="path") from e

    try:
        raw_data = yaml.safe_load(raw_text)
    except yaml.YAMLError as e:
        msg = f"Invalid YAML syntax: {e}"
        logger.error(msg, path=str(path))
        raise ConfigError(msg, field="yaml") from e

    if not isinstance(raw_data, dict):
        msg = f"YAML root must be a mapping, got {type(raw_data).__name__}"
        logger.error(msg, path=str(path))
        raise ConfigError(msg, field="yaml")

    try:
        config = ReportScraperConfig.model_validate(raw_data)
    except ValidationError as e:
        msg = f"Configuration validation failed: {e}"
        logger.error(msg, path=str(path), errors=e.error_count())
        raise ConfigError(msg, field="validation") from e

    logger.info(
        "Configuration loaded successfully",
        path=str(path),
        source_count=len(config.sources),
    )
    return config
