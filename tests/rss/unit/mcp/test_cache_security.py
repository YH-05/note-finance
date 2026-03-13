"""Unit tests for MCP cache directory security hardening.

Tests for CVE-2025-69872 mitigation: ensures diskcache directories
have restricted permissions (700) to prevent pickle deserialization attacks.
"""

from __future__ import annotations

import stat
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from rss.mcp.cache_security import (
    SECURE_DIR_MODE,
    harden_cache_directory,
    validate_cache_directory_permissions,
)


class TestHardenCacheDirectory:
    """Test harden_cache_directory function."""

    def test_正常系_新規ディレクトリが700パーミッションで作成される(
        self, tmp_path: Path
    ) -> None:
        """新規キャッシュディレクトリが0o700パーミッションで作成されること。"""
        cache_dir = tmp_path / "mcp_cache"
        harden_cache_directory(cache_dir)

        assert cache_dir.exists()
        mode = stat.S_IMODE(cache_dir.stat().st_mode)
        assert mode == SECURE_DIR_MODE

    def test_正常系_既存ディレクトリのパーミッションが修正される(
        self, tmp_path: Path
    ) -> None:
        """既存のキャッシュディレクトリのパーミッションが0o700に修正されること。"""
        cache_dir = tmp_path / "mcp_cache"
        cache_dir.mkdir(mode=0o755)

        harden_cache_directory(cache_dir)

        mode = stat.S_IMODE(cache_dir.stat().st_mode)
        assert mode == SECURE_DIR_MODE

    def test_正常系_ネストされたディレクトリが作成される(self, tmp_path: Path) -> None:
        """ネストされたキャッシュディレクトリが正しく作成されること。"""
        cache_dir = tmp_path / "deep" / "nested" / "cache"
        harden_cache_directory(cache_dir)

        assert cache_dir.exists()
        mode = stat.S_IMODE(cache_dir.stat().st_mode)
        assert mode == SECURE_DIR_MODE

    def test_正常系_既に700パーミッションのディレクトリは変更なし(
        self, tmp_path: Path
    ) -> None:
        """既に0o700のディレクトリは変更されないこと。"""
        cache_dir = tmp_path / "mcp_cache"
        cache_dir.mkdir(mode=0o700)

        harden_cache_directory(cache_dir)

        mode = stat.S_IMODE(cache_dir.stat().st_mode)
        assert mode == SECURE_DIR_MODE


class TestValidateCacheDirectoryPermissions:
    """Test validate_cache_directory_permissions function."""

    def test_正常系_700パーミッションでTrue(self, tmp_path: Path) -> None:
        """0o700パーミッションのディレクトリでTrueが返ること。"""
        cache_dir = tmp_path / "mcp_cache"
        cache_dir.mkdir(mode=0o700)

        assert validate_cache_directory_permissions(cache_dir) is True

    def test_異常系_755パーミッションでFalse(self, tmp_path: Path) -> None:
        """0o755パーミッションのディレクトリでFalseが返ること。"""
        cache_dir = tmp_path / "mcp_cache"
        cache_dir.mkdir(mode=0o755)

        assert validate_cache_directory_permissions(cache_dir) is False

    def test_異常系_777パーミッションでFalse(self, tmp_path: Path) -> None:
        """0o777パーミッションのディレクトリでFalseが返ること。"""
        cache_dir = tmp_path / "mcp_cache"
        cache_dir.mkdir(mode=0o777)

        assert validate_cache_directory_permissions(cache_dir) is False

    def test_異常系_存在しないディレクトリでFalse(self, tmp_path: Path) -> None:
        """存在しないディレクトリでFalseが返ること。"""
        cache_dir = tmp_path / "nonexistent"

        assert validate_cache_directory_permissions(cache_dir) is False


class TestSecureDirModeConstant:
    """Test SECURE_DIR_MODE constant."""

    def test_正常系_定数値が700である(self) -> None:
        """SECURE_DIR_MODE が 0o700 であること。"""
        assert SECURE_DIR_MODE == 0o700

    def test_正常系_ownerのみrwx権限(self) -> None:
        """SECURE_DIR_MODE がオーナーのみにrwx権限を付与すること。"""
        assert SECURE_DIR_MODE & stat.S_IRWXU == stat.S_IRWXU  # owner rwx
        assert SECURE_DIR_MODE & stat.S_IRWXG == 0  # group none
        assert SECURE_DIR_MODE & stat.S_IRWXO == 0  # other none
