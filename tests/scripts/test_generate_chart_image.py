"""generate_chart_image のテスト."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from scripts.generate_chart_image import (
    _RENDERERS,
    SUPPORTED_CHART_TYPES,
    _format_axis,
    generate_chart_image,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def tmp_output(tmp_path: Path) -> Path:
    """一時出力パス."""
    return tmp_path / "test_chart.png"


class TestRendererRegistry:
    """レンダラーレジストリのテスト."""

    def test_正常系_全チャートタイプが登録済み(self) -> None:
        for chart_type in SUPPORTED_CHART_TYPES:
            assert chart_type in _RENDERERS, f"{chart_type} is not registered"

    def test_正常系_レンダラーはcallable(self) -> None:
        for name, renderer in _RENDERERS.items():
            assert callable(renderer), f"{name} renderer is not callable"


class TestGenerateChartImage:
    """generate_chart_image 関数のテスト."""

    def test_正常系_棒グラフ生成(self, tmp_output: Path) -> None:
        spec = {
            "chart_type": "bar",
            "title": "テスト棒グラフ",
            "data": {
                "categories": ["A", "B", "C"],
                "series": [{"label": "値", "values": [10, 20, 15]}],
            },
        }
        result = generate_chart_image(spec, tmp_output)
        assert result.exists()
        assert result.stat().st_size > 0

    def test_正常系_折れ線グラフ生成(self, tmp_output: Path) -> None:
        spec = {
            "chart_type": "line",
            "title": "テスト折れ線",
            "data": {
                "x": ["1月", "2月", "3月"],
                "series": [{"label": "売上", "values": [100, 150, 130]}],
            },
        }
        result = generate_chart_image(spec, tmp_output)
        assert result.exists()

    def test_正常系_横棒グラフ生成(self, tmp_output: Path) -> None:
        spec = {
            "chart_type": "hbar",
            "title": "セクター別",
            "data": {
                "categories": ["XLK", "XLE"],
                "series": [{"label": "リターン", "values": [3.5, -1.2]}],
                "color_by_value": True,
            },
        }
        result = generate_chart_image(spec, tmp_output)
        assert result.exists()

    def test_正常系_散布図生成(self, tmp_output: Path) -> None:
        spec = {
            "chart_type": "scatter",
            "title": "ドットプロット",
            "data": {
                "points": [
                    {"x": 2026, "y": 4.25},
                    {"x": 2027, "y": 3.75},
                ],
                "x_label": "年",
                "y_label": "FF金利 (%)",
            },
        }
        result = generate_chart_image(spec, tmp_output)
        assert result.exists()

    def test_正常系_面グラフ生成(self, tmp_output: Path) -> None:
        spec = {
            "chart_type": "area",
            "title": "資産推移",
            "data": {
                "x": [0, 5, 10, 15],
                "series": [{"label": "積立", "values": [0, 180, 400, 700]}],
            },
        }
        result = generate_chart_image(spec, tmp_output)
        assert result.exists()

    def test_正常系_コンボチャート生成(self, tmp_output: Path) -> None:
        spec = {
            "chart_type": "combo",
            "title": "出来高とリターン",
            "data": {
                "x": ["Mon", "Tue", "Wed"],
                "bar_series": [{"label": "出来高", "values": [320, 450, 380]}],
                "line_series": [{"label": "リターン", "values": [0.2, -0.5, 0.8]}],
                "left_label": "出来高",
                "right_label": "リターン (%)",
            },
        }
        result = generate_chart_image(spec, tmp_output)
        assert result.exists()

    def test_正常系_ヒートマップ生成(self, tmp_output: Path) -> None:
        spec = {
            "chart_type": "heatmap",
            "title": "相関行列",
            "data": {
                "labels": ["A", "B", "C"],
                "matrix": [[1.0, 0.5, -0.3], [0.5, 1.0, 0.2], [-0.3, 0.2, 1.0]],
                "annotate": True,
                "cmap": "RdBu_r",
                "vmin": -1,
                "vmax": 1,
            },
        }
        result = generate_chart_image(spec, tmp_output)
        assert result.exists()

    def test_正常系_円グラフ生成(self, tmp_output: Path) -> None:
        spec = {
            "chart_type": "pie",
            "title": "ポートフォリオ",
            "data": {
                "labels": ["米国株", "先進国株", "債券"],
                "values": [50, 30, 20],
            },
        }
        result = generate_chart_image(spec, tmp_output)
        assert result.exists()

    def test_正常系_ドーナツチャート生成(self, tmp_output: Path) -> None:
        spec = {
            "chart_type": "donut",
            "title": "アセットアロケーション",
            "data": {
                "labels": ["株式", "債券", "不動産"],
                "values": [60, 30, 10],
            },
        }
        result = generate_chart_image(spec, tmp_output)
        assert result.exists()

    def test_正常系_サブタイトルとキャプション付き(self, tmp_output: Path) -> None:
        spec = {
            "chart_type": "bar",
            "title": "メインタイトル",
            "subtitle": "サブタイトル",
            "caption": "出典: Yahoo Finance",
            "data": {
                "categories": ["A"],
                "series": [{"label": "値", "values": [10]}],
            },
        }
        result = generate_chart_image(spec, tmp_output)
        assert result.exists()

    def test_正常系_カスタムカラー指定(self, tmp_output: Path) -> None:
        spec = {
            "chart_type": "bar",
            "title": "カスタム色",
            "colors": ["#FF0000", "#00FF00"],
            "data": {
                "categories": ["X", "Y"],
                "series": [{"label": "v", "values": [5, 8]}],
            },
        }
        result = generate_chart_image(spec, tmp_output)
        assert result.exists()

    def test_正常系_スケール指定(self, tmp_output: Path) -> None:
        spec = {
            "chart_type": "bar",
            "data": {
                "categories": ["A"],
                "series": [{"label": "v", "values": [1]}],
            },
        }
        result = generate_chart_image(spec, tmp_output, scale=1)
        assert result.exists()

    def test_正常系_ソート付き棒グラフ(self, tmp_output: Path) -> None:
        spec = {
            "chart_type": "bar",
            "data": {
                "categories": ["C", "A", "B"],
                "series": [{"label": "v", "values": [30, 10, 20]}],
                "sort": "descending",
            },
        }
        result = generate_chart_image(spec, tmp_output)
        assert result.exists()

    def test_正常系_color_by_value棒グラフ(self, tmp_output: Path) -> None:
        spec = {
            "chart_type": "bar",
            "data": {
                "categories": ["Up", "Down"],
                "series": [{"label": "v", "values": [5, -3]}],
                "color_by_value": True,
            },
        }
        result = generate_chart_image(spec, tmp_output)
        assert result.exists()

    def test_正常系_複数シリーズ棒グラフ(self, tmp_output: Path) -> None:
        spec = {
            "chart_type": "bar",
            "data": {
                "categories": ["Q1", "Q2"],
                "series": [
                    {"label": "2025", "values": [100, 120]},
                    {"label": "2026", "values": [110, 130]},
                ],
            },
        }
        result = generate_chart_image(spec, tmp_output)
        assert result.exists()

    def test_正常系_複数シリーズ折れ線(self, tmp_output: Path) -> None:
        spec = {
            "chart_type": "line",
            "data": {
                "x": ["1月", "2月"],
                "series": [
                    {
                        "label": "A",
                        "values": [10, 20],
                        "style": "solid",
                        "marker": True,
                    },
                    {"label": "B", "values": [15, 12], "style": "dashed"},
                ],
            },
        }
        result = generate_chart_image(spec, tmp_output)
        assert result.exists()

    def test_正常系_アノテーション付き折れ線(self, tmp_output: Path) -> None:
        spec = {
            "chart_type": "line",
            "data": {
                "x": ["A", "B", "C"],
                "series": [{"label": "v", "values": [1, 3, 2]}],
                "annotations": [{"x": "B", "y": 3, "text": "ピーク", "arrow": True}],
            },
        }
        result = generate_chart_image(spec, tmp_output)
        assert result.exists()

    def test_正常系_スタック面グラフ(self, tmp_output: Path) -> None:
        spec = {
            "chart_type": "area",
            "data": {
                "x": [1, 2, 3],
                "series": [
                    {"label": "A", "values": [10, 20, 30]},
                    {"label": "B", "values": [5, 10, 15]},
                ],
                "stacked": True,
            },
        }
        result = generate_chart_image(spec, tmp_output)
        assert result.exists()

    def test_正常系_散布図median表示(self, tmp_output: Path) -> None:
        spec = {
            "chart_type": "scatter",
            "data": {
                "points": [{"x": 1, "y": 10}, {"x": 2, "y": 20}, {"x": 3, "y": 15}],
                "show_median": True,
            },
        }
        result = generate_chart_image(spec, tmp_output)
        assert result.exists()

    def test_正常系_出力ディレクトリが自動作成される(self, tmp_path: Path) -> None:
        nested = tmp_path / "sub" / "dir" / "chart.png"
        spec = {
            "chart_type": "bar",
            "data": {
                "categories": ["A"],
                "series": [{"label": "v", "values": [1]}],
            },
        }
        result = generate_chart_image(spec, nested)
        assert result.exists()

    def test_異常系_未知のchart_typeでValueError(self, tmp_output: Path) -> None:
        spec = {"chart_type": "unknown_type", "data": {}}
        with pytest.raises(ValueError, match="Unknown chart_type 'unknown_type'"):
            generate_chart_image(spec, tmp_output)

    def test_異常系_未知のテーマ名でValueError(self, tmp_output: Path) -> None:
        spec = {
            "chart_type": "bar",
            "data": {
                "categories": ["A"],
                "series": [{"label": "v", "values": [1]}],
            },
        }
        with pytest.raises(ValueError, match="Unknown theme"):
            generate_chart_image(spec, tmp_output, theme_name="nonexistent")


class TestFormatAxis:
    """_format_axis のテスト."""

    def test_正常系_fmtがNoneで何も起きない(self) -> None:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        _, ax = plt.subplots()
        _format_axis(ax, None)
        plt.close()

    def test_正常系_未知のfmtで何も起きない(self) -> None:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        _, ax = plt.subplots()
        _format_axis(ax, "unknown_format")
        plt.close()


class TestChartPresets:
    """chart_presets のテスト."""

    def test_正常系_indices_barプリセット(self, tmp_output: Path) -> None:
        from scripts.chart_presets import apply_preset

        data = {
            "indices": [
                {"name": "S&P 500", "return": 1.5},
                {"name": "NASDAQ", "return": -0.3},
            ]
        }
        spec = apply_preset("indices_bar", data)
        result = generate_chart_image(spec, tmp_output)
        assert result.exists()

    def test_正常系_sectors_barプリセット(self, tmp_output: Path) -> None:
        from scripts.chart_presets import apply_preset

        data = {
            "sectors": [
                {"name": "XLK", "return": 3.77},
                {"name": "XLE", "return": -1.2},
            ]
        }
        spec = apply_preset("sectors_bar", data)
        result = generate_chart_image(spec, tmp_output)
        assert result.exists()

    def test_正常系_mag7_barプリセット(self, tmp_output: Path) -> None:
        from scripts.chart_presets import apply_preset

        data = {
            "stocks": [
                {"ticker": "AAPL", "return": 2.1},
                {"ticker": "MSFT", "return": -0.5},
            ]
        }
        spec = apply_preset("mag7_bar", data)
        result = generate_chart_image(spec, tmp_output)
        assert result.exists()

    def test_正常系_asset_simulationプリセット(self, tmp_output: Path) -> None:
        from scripts.chart_presets import apply_preset

        data = {
            "years": [0, 5, 10],
            "series": [{"label": "積立NISA", "values": [0, 200, 500]}],
        }
        spec = apply_preset("asset_simulation", data)
        result = generate_chart_image(spec, tmp_output)
        assert result.exists()

    def test_正常系_dot_plotプリセット(self, tmp_output: Path) -> None:
        from scripts.chart_presets import apply_preset

        data = {"points": [{"x": 2026, "y": 4.25}, {"x": 2027, "y": 3.5}]}
        spec = apply_preset("dot_plot", data)
        result = generate_chart_image(spec, tmp_output)
        assert result.exists()

    def test_異常系_未知のプリセット名でValueError(self) -> None:
        from scripts.chart_presets import apply_preset

        with pytest.raises(ValueError, match="Unknown preset"):
            apply_preset("nonexistent", {})

    def test_正常系_list_presets(self) -> None:
        from scripts.chart_presets import list_presets

        presets = list_presets()
        assert "indices_bar" in presets
        assert "sectors_bar" in presets
        assert "mag7_bar" in presets
        assert "asset_simulation" in presets
        assert "dot_plot" in presets
