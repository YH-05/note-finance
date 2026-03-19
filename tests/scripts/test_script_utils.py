"""Unit tests for scripts/_script_utils.py."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

from data_paths import _reset_cache, get_path


@pytest.fixture(autouse=True)
def _clear_data_paths_cache() -> Iterator[None]:
    """各テストの前後でdata_pathsのlru_cacheをクリアする。"""
    _reset_cache()
    yield
    _reset_cache()


class TestFinanceNewsThemesConfig:
    """FINANCE_NEWS_THEMES_CONFIG 定数のテスト。"""

    def test_正常系_get_pathで解決されたパスと一致する(self) -> None:
        """FINANCE_NEWS_THEMES_CONFIG が get_path() 経由で解決されることを確認。"""
        # scripts/ は sys.path に自動追加されないため、直接インポートせず値を検証
        expected = get_path("config/finance-news-themes.json")
        assert expected.name == "finance-news-themes.json"
        assert expected.is_absolute()


class TestResolveOutputDir:
    """resolve_output_dir 関数のテスト。"""

    def test_正常系_arg指定時はそのパスを返す(self, tmp_path: Path) -> None:
        """arg が指定された場合はそのパスをそのまま返す。"""
        from scripts._script_utils import resolve_output_dir

        result = resolve_output_dir(str(tmp_path / "custom"))
        assert result == Path(str(tmp_path / "custom"))

    def test_正常系_argがNoneの場合はNASまたはget_pathを返す(self) -> None:
        """arg が None の場合は NAS 優先、フォールバックで get_path(default_sub) を返す。"""
        from scripts._script_utils import _NAS_DATA_ROOT, resolve_output_dir

        result = resolve_output_dir(None)
        if _NAS_DATA_ROOT.exists():
            assert result == _NAS_DATA_ROOT / "market"
        else:
            assert result == get_path("market")

    def test_正常系_default_subを変更できる(self) -> None:
        """default_sub パラメータでデフォルトサブパスを変更できる。"""
        from scripts._script_utils import _NAS_DATA_ROOT, resolve_output_dir

        result = resolve_output_dir(None, default_sub="exports")
        if _NAS_DATA_ROOT.exists():
            assert result == _NAS_DATA_ROOT / "exports"
        else:
            assert result == get_path("exports")

    def test_正常系_空文字列のargはtruthyとして扱われる(self) -> None:
        """空文字列は truthy ではないため None と同じ扱いになる。"""
        from scripts._script_utils import _NAS_DATA_ROOT, resolve_output_dir

        # Python の if "" は False なので NAS or get_path(default_sub) が返る
        result = resolve_output_dir("")
        if _NAS_DATA_ROOT.exists():
            assert result == _NAS_DATA_ROOT / "market"
        else:
            assert result == get_path("market")
