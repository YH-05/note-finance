"""session_memory テスト共通フィクスチャ.

SQLiteコンテキストマネージャ（SessionMemoryDB）のテスト用
フィクスチャを提供する。一時ディレクトリで隔離された環境を使用。
"""

from pathlib import Path

import pytest

from session_memory.db import SessionMemoryDB


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """テスト用DBファイルパスを返す.

    Parameters
    ----------
    tmp_path : Path
        pytest 提供の一時ディレクトリ

    Returns
    -------
    Path
        一時ディレクトリ内のDBファイルパス
    """
    return tmp_path / "test_session_memory.db"


@pytest.fixture
def db(db_path: Path) -> SessionMemoryDB:
    """SessionMemoryDB インスタンスを返す（未接続状態）.

    Parameters
    ----------
    db_path : Path
        テスト用DBファイルパス

    Returns
    -------
    SessionMemoryDB
        未接続のインスタンス
    """
    return SessionMemoryDB(db_path)
