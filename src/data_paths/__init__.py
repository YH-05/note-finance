"""data_paths — DATA_ROOT 環境変数によるデータパス一元管理パッケージ。

全パッケージが参照する共通のパス解決APIを提供する。

Functions
---------
get_path
    サブパスをデータルートに結合して返す。
get_data_root
    DATA_ROOT or {project}/data をデータルートとして返す。
get_config_dir
    常に {project}/data/config を返す（プロジェクトローカル固定）。
get_project_root
    pyproject.toml を含むプロジェクトルートを返す。
ensure_data_dirs
    標準ディレクトリ構造をデータルート配下に作成する。
_reset_cache
    テスト用: lru_cache をクリアする。

Exceptions
----------
DataPathError
    パス解決時のエラー（DATA_ROOT が存在しない等）。

Examples
--------
>>> from data_paths import get_data_root, get_path
>>> root = get_data_root()
>>> fred_path = get_path("raw/fred")
"""

from data_paths._logging import get_logger
from data_paths.paths import (
    DataPathError,
    _reset_cache,
    ensure_data_dirs,
    get_config_dir,
    get_data_root,
    get_path,
    get_project_root,
)

__all__ = [
    "DataPathError",
    "_reset_cache",
    "ensure_data_dirs",
    "get_config_dir",
    "get_data_root",
    "get_logger",
    "get_path",
    "get_project_root",
]

__version__ = "0.1.0"
