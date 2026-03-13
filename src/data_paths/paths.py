"""Core path resolution for DATA_ROOT-based data directory management.

Provides a unified API for resolving data paths across all packages.
When DATA_ROOT is set and the path does not exist, DataPathError is raised
(no fallback — intentional design decision: Strategy A).
The config/ sub-path is always project-local.

Functions
---------
get_project_root
    Locate the project root (directory containing pyproject.toml).
get_data_root
    Return DATA_ROOT or {project}/data as the data root.
get_config_dir
    Return {project}/data/config (always project-local).
get_path
    Join a sub-path to the data root.
ensure_data_dirs
    Create standard directory structure under the data root.
_reset_cache
    Clear lru_cache entries (for testing).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from data_paths._logging import get_logger

logger = get_logger(__name__)

# AIDEV-NOTE: 標準ディレクトリ構造。ensure_data_dirs() で作成される。
_STANDARD_DIRS = [
    "raw",
    "processed",
    "config",
    "cache",
]


class DataPathError(Exception):
    """データパス解決時のエラー。

    DATA_ROOT が設定されているがパスが存在しない場合などに送出される。
    """


@lru_cache(maxsize=1)
def get_project_root() -> Path:
    """pyproject.toml を含むプロジェクトルートディレクトリを返す。

    Returns
    -------
    Path
        プロジェクトルートのパス。

    Raises
    ------
    DataPathError
        pyproject.toml が見つからない場合。
    """
    current = Path(__file__).resolve().parent
    # src/data_paths/ → src/ → project_root/
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            logger.debug("Project root found", path=str(parent))
            return parent
    msg = "pyproject.toml not found in any parent directory"
    raise DataPathError(msg)


@lru_cache(maxsize=1)
def get_data_root() -> Path:
    """データルートディレクトリを返す。

    DATA_ROOT 環境変数が設定されている場合はそのパスを使用する。
    設定されていない場合は {project_root}/data をデフォルトとする。

    Returns
    -------
    Path
        データルートのパス。

    Raises
    ------
    DataPathError
        DATA_ROOT が設定されているがパスが存在しない場合。
    """
    env_root = os.environ.get("DATA_ROOT")
    if env_root:
        data_root = Path(env_root).resolve()
        if not data_root.exists():
            msg = (
                f"DATA_ROOT is set to '{env_root}' but the path does not exist. "
                f"Create the directory or unset DATA_ROOT to use the default."
            )
            raise DataPathError(msg)
        logger.debug("Using DATA_ROOT", data_root=str(data_root))
        return data_root

    default_root = get_project_root() / "data"
    logger.debug("Using default data root", data_root=str(default_root))
    return default_root


@lru_cache(maxsize=1)
def get_config_dir() -> Path:
    """設定ディレクトリのパスを返す（常にプロジェクトローカル）。

    DATA_ROOT の設定に関わらず、常に {project_root}/data/config を返す。

    Returns
    -------
    Path
        設定ディレクトリのパス。
    """
    return get_project_root() / "data" / "config"


def get_path(sub_path: str | Path) -> Path:
    """サブパスをデータルートに結合して返す。

    Parameters
    ----------
    sub_path : str | Path
        データルートからの相対パス。

    Returns
    -------
    Path
        データルートにサブパスを結合したパス。
    """
    return get_data_root() / sub_path


def ensure_data_dirs() -> list[Path]:
    """標準ディレクトリ構造をデータルート配下に作成する。

    Returns
    -------
    list[Path]
        作成されたディレクトリのリスト。
    """
    data_root = get_data_root()
    created: list[Path] = []
    for dir_name in _STANDARD_DIRS:
        dir_path = data_root / dir_name
        dir_path.mkdir(parents=True, exist_ok=True)
        created.append(dir_path)
        logger.debug("Ensured directory exists", path=str(dir_path))
    return created


def _reset_cache() -> None:
    """lru_cache をクリアする（テスト用）。"""
    get_project_root.cache_clear()
    get_data_root.cache_clear()
    get_config_dir.cache_clear()
