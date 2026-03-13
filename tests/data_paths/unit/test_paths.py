"""Unit tests for data_paths.paths module."""

import os
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from data_paths import (
    DataPathError,
    _reset_cache,
    get_config_dir,
    get_data_root,
    get_path,
    get_project_root,
)


@pytest.fixture(autouse=True)
def _clear_cache() -> Iterator[None]:
    """各テストの前後でlru_cacheをクリアする。"""
    _reset_cache()
    yield
    _reset_cache()


class TestGetProjectRoot:
    """get_project_root のテスト。"""

    def test_正常系_pyproject_tomlを含むルートを返す(self) -> None:
        """プロジェクトルートが正しく検出されることを確認。"""
        root = get_project_root()
        assert (root / "pyproject.toml").exists()

    def test_正常系_返り値がPathオブジェクト(self) -> None:
        """返り値がPathオブジェクトであることを確認。"""
        root = get_project_root()
        assert isinstance(root, Path)


class TestGetDataRoot:
    """get_data_root のテスト。"""

    def test_正常系_DATA_ROOT未設定でデフォルトパスを返す(self) -> None:
        """DATA_ROOT未設定時にproject/dataを返すことを確認。"""
        with patch.dict(os.environ, {}, clear=False):
            # DATA_ROOTが環境変数にない場合を確認
            env = {k: v for k, v in os.environ.items() if k != "DATA_ROOT"}
            with patch.dict(os.environ, env, clear=True):
                _reset_cache()
                root = get_data_root()
                project_root = get_project_root()
                assert root == project_root / "data"

    def test_正常系_DATA_ROOT設定済みで存在するパスを返す(self, tmp_path: Path) -> None:
        """DATA_ROOT設定時にそのパスを返すことを確認。"""
        data_dir = tmp_path / "custom_data"
        data_dir.mkdir()
        with patch.dict(os.environ, {"DATA_ROOT": str(data_dir)}):
            _reset_cache()
            root = get_data_root()
            assert root == data_dir

    def test_異常系_DATA_ROOT設定済みで存在しないパスでDataPathError(
        self, tmp_path: Path
    ) -> None:
        """DATA_ROOT設定時にパスが存在しない場合DataPathErrorを送出することを確認。"""
        non_existent = tmp_path / "does_not_exist"
        with patch.dict(os.environ, {"DATA_ROOT": str(non_existent)}):
            _reset_cache()
            with pytest.raises(DataPathError, match="DATA_ROOT"):
                get_data_root()


class TestGetConfigDir:
    """get_config_dir のテスト。"""

    def test_正常系_常にプロジェクトローカルのconfigパスを返す(self) -> None:
        """config/パスが常にプロジェクトローカルであることを確認。"""
        config_dir = get_config_dir()
        project_root = get_project_root()
        assert config_dir == project_root / "data" / "config"

    def test_正常系_DATA_ROOT設定時もプロジェクトローカル(self, tmp_path: Path) -> None:
        """DATA_ROOT設定時もconfig/はプロジェクトローカルを返すことを確認。"""
        data_dir = tmp_path / "external_data"
        data_dir.mkdir()
        with patch.dict(os.environ, {"DATA_ROOT": str(data_dir)}):
            _reset_cache()
            config_dir = get_config_dir()
            project_root = get_project_root()
            assert config_dir == project_root / "data" / "config"


class TestGetPath:
    """get_path のテスト。"""

    def test_正常系_サブパスを結合して返す(self) -> None:
        """サブパスがデータルートに結合されることを確認。"""
        with patch.dict(os.environ, {}, clear=False):
            env = {k: v for k, v in os.environ.items() if k != "DATA_ROOT"}
            with patch.dict(os.environ, env, clear=True):
                _reset_cache()
                path = get_path("raw/fred")
                data_root = get_data_root()
                assert path == data_root / "raw" / "fred"

    def test_正常系_Path型のサブパスも受け付ける(self) -> None:
        """Path型のサブパスが正しく結合されることを確認。"""
        with patch.dict(os.environ, {}, clear=False):
            env = {k: v for k, v in os.environ.items() if k != "DATA_ROOT"}
            with patch.dict(os.environ, env, clear=True):
                _reset_cache()
                path = get_path(Path("raw") / "fred")
                data_root = get_data_root()
                assert path == data_root / "raw" / "fred"


class TestEnsureDataDirs:
    """ensure_data_dirs のテスト。"""

    def test_正常系_標準4ディレクトリが作成されてPathのリストを返す(
        self, tmp_path: Path
    ) -> None:
        """標準ディレクトリ構造（raw/processed/config/cache）が作成されることを確認。"""
        from data_paths import ensure_data_dirs

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        with patch.dict(os.environ, {"DATA_ROOT": str(data_dir)}):
            _reset_cache()
            created = ensure_data_dirs()
            # _STANDARD_DIRS の4件が正確に作成される
            assert len(created) == 4
            created_names = [d.name for d in created]
            assert "raw" in created_names
            assert "processed" in created_names
            assert "config" in created_names
            assert "cache" in created_names
            # 作成されたパスが全て存在する
            for d in created:
                assert d.exists()
                assert d.is_dir()


class TestResetCache:
    """_reset_cache のテスト。"""

    def test_正常系_キャッシュクリア後に再計算される(self, tmp_path: Path) -> None:
        """キャッシュクリア後にget_data_rootが再計算されることを確認。"""
        # 1回目: デフォルト
        env_no_data_root = {k: v for k, v in os.environ.items() if k != "DATA_ROOT"}
        with patch.dict(os.environ, env_no_data_root, clear=True):
            _reset_cache()
            root1 = get_data_root()

        # 2回目: DATA_ROOT設定
        data_dir = tmp_path / "new_data"
        data_dir.mkdir()
        with patch.dict(os.environ, {"DATA_ROOT": str(data_dir)}):
            _reset_cache()
            root2 = get_data_root()

        assert root1 != root2
        assert root2 == data_dir
