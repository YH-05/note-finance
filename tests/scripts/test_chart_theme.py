"""chart_theme のテスト."""

from __future__ import annotations

import pytest

from scripts.chart_theme import NOTE_DARK, NOTE_LIGHT, ChartTheme, get_theme


class TestChartTheme:
    """ChartTheme データクラスのテスト."""

    def test_正常系_NOTE_LIGHTのデフォルト値が正しい(self) -> None:
        assert NOTE_LIGHT.name == "note_light"
        assert NOTE_LIGHT.font_family == "Noto Sans JP"
        assert NOTE_LIGHT.title_size == 16
        assert NOTE_LIGHT.background_color == "#FFFFFF"
        assert NOTE_LIGHT.text_color == "#333333"
        assert NOTE_LIGHT.positive_color == "#2563EB"
        assert NOTE_LIGHT.negative_color == "#DC2626"
        assert NOTE_LIGHT.spine_visible is False

    def test_正常系_パレットが8色ある(self) -> None:
        assert len(NOTE_LIGHT.palette) == 8
        assert NOTE_LIGHT.palette[0] == "#2563EB"

    def test_正常系_NOTE_DARKの背景色が暗い(self) -> None:
        assert NOTE_DARK.name == "note_dark"
        assert NOTE_DARK.background_color == "#1A1A2E"
        assert NOTE_DARK.text_color == "#E0E0E0"

    def test_正常系_frozen_dataclass(self) -> None:
        with pytest.raises(AttributeError):
            NOTE_LIGHT.name = "modified"  # type: ignore[misc]

    def test_正常系_カスタムテーマ作成(self) -> None:
        custom = ChartTheme(name="custom", positive_color="#00FF00")
        assert custom.positive_color == "#00FF00"
        assert custom.font_family == "Noto Sans JP"  # デフォルト値


class TestGetTheme:
    """get_theme 関数のテスト."""

    def test_正常系_note_lightを取得(self) -> None:
        theme = get_theme("note_light")
        assert theme is NOTE_LIGHT

    def test_正常系_note_darkを取得(self) -> None:
        theme = get_theme("note_dark")
        assert theme is NOTE_DARK

    def test_異常系_未知のテーマ名でValueError(self) -> None:
        with pytest.raises(ValueError, match="Unknown theme 'nonexistent'"):
            get_theme("nonexistent")
