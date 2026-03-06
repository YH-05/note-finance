"""Configuration loading for the report_scraper package.

Modules
-------
loader
    YAML configuration file loader with Pydantic validation.

Examples
--------
>>> from report_scraper.config import load_config
"""

from report_scraper.config.loader import load_config

__all__ = ["load_config"]
