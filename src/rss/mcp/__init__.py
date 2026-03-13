"""MCP server module for RSS feed management.

This module provides an MCP (Model Context Protocol) server that allows
AI agents like Claude Code to interact with RSS feed management functionality.
"""

from .cache_security import harden_cache_directory, validate_cache_directory_permissions
from .server import main, serve

__all__ = [
    "harden_cache_directory",
    "main",
    "serve",
    "validate_cache_directory_permissions",
]
