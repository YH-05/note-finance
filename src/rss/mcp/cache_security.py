"""MCP cache directory security hardening.

Mitigates CVE-2025-69872 (diskcache pickle deserialization RCE) by ensuring
cache directories used by fastmcp's transitive dependency (py-key-value-aio
-> diskcache) have restricted permissions.

Background
----------
fastmcp depends on py-key-value-aio[disk] which uses diskcache 5.6.3.
diskcache stores Python objects via pickle, making it vulnerable to arbitrary
code execution if an attacker can write to the cache directory.

Mitigation: restrict cache directory permissions to owner-only (0o700),
preventing other users on the system from reading or writing cache files.

References
----------
- CVE-2025-69872: diskcache pickle deserialization vulnerability
- CWE-502: Deserialization of Untrusted Data
- PR review: #69 (pr-security-infra, INFRA-001)
"""

from __future__ import annotations

import stat
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

# AIDEV-NOTE: 0o700 = owner read/write/execute only.
# This prevents other system users from injecting malicious pickle payloads
# into the diskcache directory.
SECURE_DIR_MODE: int = 0o700


def _get_logger() -> Any:
    """Get logger with lazy initialization to avoid circular imports."""
    try:
        from rss._logging import get_logger

        return get_logger(__name__, module="cache_security")
    except ImportError:
        import logging

        return logging.getLogger(__name__)


logger: Any = _get_logger()


def harden_cache_directory(cache_dir: Path) -> None:
    """Ensure a cache directory exists with secure permissions (0o700).

    Creates the directory if it does not exist. If the directory already
    exists with insecure permissions, it is tightened to owner-only access.

    Parameters
    ----------
    cache_dir : Path
        Path to the cache directory to harden.

    Notes
    -----
    This function is idempotent: calling it on an already-hardened directory
    is a no-op.
    """
    # AIDEV-NOTE: Create parent directories first (inheriting umask),
    # then create the target directory separately so we can set mode
    # atomically. This avoids TOCTOU (CWE-367) between mkdir and chmod.
    cache_dir.parent.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(mode=SECURE_DIR_MODE, exist_ok=True)

    # Always chmod unconditionally to eliminate TOCTOU window.
    # chmod is idempotent and safe to call even if mode is already correct.
    current_mode = stat.S_IMODE(cache_dir.stat().st_mode)
    if current_mode != SECURE_DIR_MODE:
        logger.info(
            "Hardening cache directory permissions",
            path=str(cache_dir),
            old_mode=oct(current_mode),
            new_mode=oct(SECURE_DIR_MODE),
        )
    cache_dir.chmod(SECURE_DIR_MODE)


def validate_cache_directory_permissions(cache_dir: Path) -> bool:
    """Check whether a cache directory has secure permissions.

    Parameters
    ----------
    cache_dir : Path
        Path to the cache directory to validate.

    Returns
    -------
    bool
        True if the directory exists and has 0o700 permissions,
        False otherwise.
    """
    if not cache_dir.exists():
        logger.warning(
            "Cache directory does not exist",
            path=str(cache_dir),
        )
        return False

    current_mode = stat.S_IMODE(cache_dir.stat().st_mode)
    is_secure = current_mode == SECURE_DIR_MODE

    if not is_secure:
        logger.warning(
            "Cache directory has insecure permissions",
            path=str(cache_dir),
            current_mode=oct(current_mode),
            expected_mode=oct(SECURE_DIR_MODE),
        )

    return is_secure
