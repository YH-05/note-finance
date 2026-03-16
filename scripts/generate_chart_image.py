"""チャートデータからPNG画像を生成するスクリプト.

matplotlib + seaborn でレンダリングし、note記事用の高品質チャート画像を出力する。

Usage
-----
CLI:
    # JSON ファイルから生成
    uv run python scripts/generate_chart_image.py chart_data.json -o output.png

    # テーマ・スケール指定
    uv run python scripts/generate_chart_image.py chart_data.json -o output.png --theme note_light --scale 2

    # プリセット使用
    uv run python scripts/generate_chart_image.py data.json -o output.png --preset indices_bar

モジュール:
    from scripts.generate_chart_image import generate_chart_image

    generate_chart_image(
        spec={
            "chart_type": "bar",
            "title": "セクター別リターン",
            "data": {
                "categories": ["XLK", "XLE", "XLF"],
                "series": [{"label": "週間", "values": [3.77, 2.67, -0.88]}],
                "color_by_value": True,
            },
        },
        output_path="output.png",
    )

JSON 入力形式
------------
{
    "chart_type": "line|bar|hbar|scatter|area|combo|heatmap|pie|donut",
    "title": "チャートタイトル",
    "subtitle": "サブタイトル（省略可）",
    "caption": "出典: Yahoo Finance（省略可）",
    "width": 800,
    "height": 500,
    "scale": 2,
    "theme": "note_light",
    "colors": null,
    "data": { ... }
}
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger(__name__)

SUPPORTED_CHART_TYPES = [
    "line",
    "bar",
    "hbar",
    "scatter",
    "area",
    "combo",
    "heatmap",
    "pie",
    "donut",
]

DEFAULT_WIDTH = 800
DEFAULT_HEIGHT = 500
DEFAULT_SCALE = 2
DEFAULT_THEME = "note_light"

# ---------------------------------------------------------------------------
# Renderer registry
# ---------------------------------------------------------------------------
_RENDERERS: dict[str, object] = {}


def register_renderer(chart_type: str):
    """レンダラー関数をレジストリに登録するデコレータ."""

    def decorator(func):
        _RENDERERS[chart_type] = func
        return func

    return decorator


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
def _format_axis(ax: object, fmt: str | None, axis: str = "y") -> None:
    """軸のフォーマットを設定する."""
    if not fmt:
        return
    from matplotlib import ticker

    if fmt == "percent":
        formatter = ticker.FuncFormatter(lambda x, _: f"{x:.1f}%")
    elif fmt == "comma":
        formatter = ticker.FuncFormatter(lambda x, _: f"{x:,.0f}")
    elif fmt == "dollar":
        formatter = ticker.FuncFormatter(lambda x, _: f"${x:,.0f}")
    elif fmt == "yen":
        formatter = ticker.FuncFormatter(lambda x, _: f"¥{x:,.0f}")
    else:
        return

    if axis == "y":
        ax.yaxis.set_major_formatter(formatter)
    else:
        ax.xaxis.set_major_formatter(formatter)


def _apply_annotations(
    ax: object, annotations: list[dict] | None, theme: object
) -> None:
    """チャートにアノテーションを追加する."""
    if not annotations:
        return
    for ann in annotations:
        kwargs = {
            "fontsize": theme.caption_size,
            "color": theme.text_color,
            "ha": "center",
        }
        if ann.get("arrow"):
            ax.annotate(
                ann["text"],
                xy=(ann["x"], ann["y"]),
                xytext=(ann["x"], ann["y"] * 1.15 if ann["y"] != 0 else 0.5),
                arrowprops={"arrowstyle": "->", "color": theme.text_color},
                **kwargs,
            )
        else:
            ax.annotate(ann["text"], xy=(ann["x"], ann["y"]), **kwargs)


def _add_caption(fig: object, caption: str | None, theme: object) -> None:
    """図の下部にキャプション（出典等）を追加する."""
    if not caption:
        return
    fig.text(
        0.5,
        0.01,
        caption,
        ha="center",
        va="bottom",
        fontsize=theme.caption_size,
        color="#888888",
        style="italic",
    )


def _color_bars_by_value(bars: object, values: list[float], theme: object) -> None:
    """値の正負に基づいて棒の色を設定する."""
    for bar, val in zip(bars, values, strict=False):
        bar.set_color(theme.positive_color if val >= 0 else theme.negative_color)


def _add_bar_labels(
    ax: object, bars: object, values: list[float], fmt: str | None
) -> None:
    """棒グラフにデータラベルを追加する."""
    for bar, val in zip(bars, values, strict=False):
        label = f"{val:+.2f}%" if fmt == "percent" else f"{val:,.1f}"
        y_pos = bar.get_height()
        va = "bottom" if val >= 0 else "top"
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            y_pos,
            label,
            ha="center",
            va=va,
            fontsize=8,
        )


# ---------------------------------------------------------------------------
# Chart renderers
# ---------------------------------------------------------------------------
@register_renderer("line")
def _render_line(ax: object, data: dict, theme: object) -> None:
    """折れ線グラフを描画する."""
    x = data["x"]
    for i, series in enumerate(data.get("series", [])):
        color = theme.palette[i % len(theme.palette)]
        style = series.get("style", "solid")
        linestyle = {"solid": "-", "dashed": "--", "dotted": ":"}
        ax.plot(
            x,
            series["values"],
            label=series.get("label"),
            color=color,
            linestyle=linestyle.get(style, "-"),
            linewidth=2,
            marker="o" if series.get("marker") else None,
            markersize=5,
        )
    ax.set_xlabel(data.get("x_label", ""))
    ax.set_ylabel(data.get("y_label", ""))
    _format_axis(ax, data.get("y_format"))
    if len(data.get("series", [])) > 1:
        ax.legend()
    _apply_annotations(ax, data.get("annotations"), theme)


@register_renderer("area")
def _render_area(ax: object, data: dict, theme: object) -> None:
    """面グラフを描画する."""
    x = data["x"]
    stacked = data.get("stacked", False)
    if stacked:
        values_list = [s["values"] for s in data.get("series", [])]
        labels = [s.get("label", "") for s in data.get("series", [])]
        colors = [
            theme.palette[i % len(theme.palette)] for i in range(len(values_list))
        ]
        ax.stackplot(x, *values_list, labels=labels, colors=colors, alpha=0.7)
    else:
        for i, series in enumerate(data.get("series", [])):
            color = theme.palette[i % len(theme.palette)]
            ax.fill_between(x, series["values"], alpha=0.3, color=color)
            ax.plot(
                x, series["values"], label=series.get("label"), color=color, linewidth=2
            )
    ax.set_xlabel(data.get("x_label", ""))
    ax.set_ylabel(data.get("y_label", ""))
    _format_axis(ax, data.get("y_format"))
    if len(data.get("series", [])) > 1:
        ax.legend()
    _apply_annotations(ax, data.get("annotations"), theme)


@register_renderer("bar")
def _render_bar(ax: object, data: dict, theme: object) -> None:
    """棒グラフを描画する."""
    import numpy as np

    categories = list(data["categories"])
    series_list = data.get("series", [])
    color_by_value = data.get("color_by_value", False)
    sort_order = data.get("sort")

    if len(series_list) == 1:
        values = list(series_list[0]["values"])
        if sort_order:
            pairs = sorted(
                zip(categories, values, strict=False),
                key=lambda p: p[1],
                reverse=(sort_order == "descending"),
            )
            categories, values = zip(*pairs, strict=False) if pairs else ([], [])
            categories, values = list(categories), list(values)
        bars = ax.bar(categories, values, color=theme.palette[0])
        if color_by_value:
            _color_bars_by_value(bars, values, theme)
        _add_bar_labels(ax, bars, values, data.get("y_format"))
    else:
        x = np.arange(len(categories))
        width = 0.8 / len(series_list)
        for i, series in enumerate(series_list):
            offset = (i - len(series_list) / 2 + 0.5) * width
            ax.bar(
                x + offset,
                series["values"],
                width,
                label=series.get("label"),
                color=theme.palette[i % len(theme.palette)],
            )
        ax.set_xticks(x)
        ax.set_xticklabels(categories)
        ax.legend()

    ax.set_ylabel(data.get("y_label", ""))
    _format_axis(ax, data.get("y_format"))


@register_renderer("hbar")
def _render_hbar(ax: object, data: dict, theme: object) -> None:
    """横棒グラフを描画する."""
    categories = list(data["categories"])
    values = list(data["series"][0]["values"])
    color_by_value = data.get("color_by_value", False)
    sort_order = data.get("sort")

    if sort_order:
        pairs = sorted(
            zip(categories, values, strict=False),
            key=lambda p: p[1],
            reverse=(sort_order == "descending"),
        )
        categories, values = zip(*pairs, strict=False) if pairs else ([], [])
        categories, values = list(categories), list(values)

    bars = ax.barh(categories, values, color=theme.palette[0])
    if color_by_value:
        for bar, val in zip(bars, values, strict=False):
            bar.set_color(theme.positive_color if val >= 0 else theme.negative_color)

    ax.set_xlabel(data.get("x_label", ""))
    _format_axis(ax, data.get("y_format"), axis="x")


@register_renderer("scatter")
def _render_scatter(ax: object, data: dict, theme: object) -> None:
    """散布図を描画する."""
    points = data.get("points", [])
    xs = [p["x"] for p in points]
    ys = [p["y"] for p in points]
    sizes = [p.get("size", 30) for p in points]
    colors = [p.get("color", theme.palette[0]) for p in points]

    ax.scatter(xs, ys, s=sizes, c=colors, alpha=0.7, edgecolors="white", linewidth=0.5)

    if data.get("show_median"):
        import numpy as np

        median_y = float(np.median(ys))
        ax.axhline(
            y=median_y,
            color=theme.negative_color,
            linestyle="--",
            linewidth=1,
            alpha=0.7,
        )
        ax.text(
            ax.get_xlim()[1],
            median_y,
            f" 中央値: {median_y:.2f}",
            va="center",
            fontsize=8,
            color=theme.negative_color,
        )

    ax.set_xlabel(data.get("x_label", ""))
    ax.set_ylabel(data.get("y_label", ""))
    _format_axis(ax, data.get("y_format"))


@register_renderer("combo")
def _render_combo(ax: object, data: dict, theme: object, *, fig: object = None) -> None:
    """棒 + 線のコンボチャートを描画する（左右軸対応）."""
    x_labels = data["x"]
    import numpy as np

    x = np.arange(len(x_labels))

    # 棒グラフ（左軸）
    for i, series in enumerate(data.get("bar_series", [])):
        ax.bar(
            x,
            series["values"],
            label=series.get("label"),
            color=theme.palette[i % len(theme.palette)],
            alpha=0.7,
        )
    ax.set_xticks(x)
    ax.set_xticklabels(x_labels)
    ax.set_ylabel(data.get("left_label", ""))

    # 線グラフ（右軸）
    line_series = data.get("line_series", [])
    if line_series:
        ax2 = ax.twinx()
        for i, series in enumerate(line_series):
            color = theme.palette[
                (len(data.get("bar_series", [])) + i) % len(theme.palette)
            ]
            ax2.plot(
                x,
                series["values"],
                label=series.get("label"),
                color=color,
                linewidth=2,
                marker="o",
                markersize=5,
            )
        ax2.set_ylabel(data.get("right_label", ""))
        # 凡例を結合
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc="upper left")


@register_renderer("heatmap")
def _render_heatmap(ax: object, data: dict, theme: object) -> None:
    """ヒートマップを描画する（seaborn使用）."""
    import numpy as np
    import seaborn as sns

    matrix = np.array(data["matrix"])
    labels = data.get("labels", [])
    cmap = data.get("cmap", "RdBu_r")
    vmin = data.get("vmin")
    vmax = data.get("vmax")
    annotate = data.get("annotate", True)

    sns.heatmap(
        matrix,
        ax=ax,
        xticklabels=labels or True,
        yticklabels=labels or True,
        annot=annotate,
        fmt=".2f" if annotate else "",
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        linewidths=0.5,
        linecolor=theme.grid_color,
        cbar_kws={"shrink": 0.8},
    )


@register_renderer("pie")
def _render_pie(ax: object, data: dict, theme: object) -> None:
    """円グラフを描画する."""
    labels = data["labels"]
    values = data["values"]
    colors = [theme.palette[i % len(theme.palette)] for i in range(len(values))]
    value_format = data.get("value_format", "percent")
    autopct = "%1.1f%%" if value_format == "percent" else "%1.0f"

    ax.pie(
        values,
        labels=labels,
        colors=colors,
        autopct=autopct,
        startangle=90,
        textprops={"fontsize": theme.tick_size},
    )
    ax.set_aspect("equal")


@register_renderer("donut")
def _render_donut(ax: object, data: dict, theme: object) -> None:
    """ドーナツチャートを描画する."""
    labels = data["labels"]
    values = data["values"]
    colors = [theme.palette[i % len(theme.palette)] for i in range(len(values))]
    value_format = data.get("value_format", "percent")
    autopct = "%1.1f%%" if value_format == "percent" else "%1.0f"

    ax.pie(
        values,
        labels=labels,
        colors=colors,
        autopct=autopct,
        startangle=90,
        pctdistance=0.75,
        textprops={"fontsize": theme.tick_size},
    )
    # ドーナツの穴
    from matplotlib.patches import Circle

    centre_circle = Circle(
        (0, 0),
        0.50,
        fc=theme.background_color,
    )
    ax.add_patch(centre_circle)
    ax.set_aspect("equal")


# ---------------------------------------------------------------------------
# Main API
# ---------------------------------------------------------------------------
def generate_chart_image(
    spec: dict,
    output_path: str | Path,
    *,
    theme_name: str | None = None,
    scale: int | None = None,
) -> Path:
    """チャート仕様からPNG画像を生成する.

    Parameters
    ----------
    spec : dict
        チャート仕様（chart_type, title, data 等を含むdict）。
    output_path : str | Path
        出力PNG画像のパス。
    theme_name : str | None
        テーマ名（spec内のthemeを上書き）。
    scale : int | None
        デバイスピクセル比（spec内のscaleを上書き）。

    Returns
    -------
    Path
        生成された画像のパス。

    Raises
    ------
    ValueError
        不正なchart_typeが指定された場合。
    """
    import matplotlib
    import matplotlib.pyplot as plt

    matplotlib.use("Agg")

    try:
        from scripts.chart_theme import apply_theme, get_theme
    except ModuleNotFoundError:
        from chart_theme import apply_theme, get_theme

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    chart_type = spec.get("chart_type", "bar")
    if chart_type not in _RENDERERS:
        available = ", ".join(sorted(_RENDERERS.keys()))
        raise ValueError(f"Unknown chart_type '{chart_type}'. Available: {available}")

    # テーマ適用
    t_name = theme_name or spec.get("theme", DEFAULT_THEME)
    theme = get_theme(t_name)
    apply_theme(theme)

    # カスタムカラー上書き
    if spec.get("colors"):
        from dataclasses import replace

        theme = replace(theme, palette=spec["colors"])

    # 図のサイズ
    width = spec.get("width", DEFAULT_WIDTH)
    height = spec.get("height", DEFAULT_HEIGHT)
    dpi_scale = scale or spec.get("scale", DEFAULT_SCALE)
    fig_w = width / 100
    fig_h = height / 100

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    # タイトル
    title = spec.get("title")
    subtitle = spec.get("subtitle")
    if title:
        if subtitle:
            fig.suptitle(title, fontsize=theme.title_size, fontweight="bold", y=0.98)
            ax.set_title(subtitle, fontsize=theme.label_size, pad=10)
        else:
            ax.set_title(title, fontsize=theme.title_size, fontweight="bold", pad=15)

    # レンダリング
    renderer = _RENDERERS[chart_type]
    data = spec.get("data", {})
    if chart_type == "combo":
        renderer(ax, data, theme, fig=fig)
    else:
        renderer(ax, data, theme)

    # キャプション
    _add_caption(fig, spec.get("caption"), theme)

    # レイアウト調整
    bottom = 0.05 if spec.get("caption") else 0.12
    fig.tight_layout(rect=[0, bottom, 1, 0.95 if subtitle else 1.0])

    # 保存
    fig.savefig(
        str(output_path),
        dpi=100 * dpi_scale,
        bbox_inches="tight",
        facecolor=theme.background_color,
        edgecolor="none",
        pad_inches=0.2,
    )
    plt.close(fig)

    logger.info(
        "Chart image generated",
        chart_type=chart_type,
        output=str(output_path),
        theme=t_name,
        scale=dpi_scale,
    )
    return output_path


async def generate_chart_image_async(
    spec: dict,
    output_path: str | Path,
    *,
    theme_name: str | None = None,
    scale: int | None = None,
) -> Path:
    """チャート仕様からPNG画像を生成する（非同期版）.

    Parameters
    ----------
    spec : dict
        チャート仕様。
    output_path : str | Path
        出力PNG画像のパス。
    theme_name : str | None
        テーマ名。
    scale : int | None
        デバイスピクセル比。

    Returns
    -------
    Path
        生成された画像のパス。
    """
    loop = asyncio.get_running_loop()
    func = partial(
        generate_chart_image,
        spec,
        output_path,
        theme_name=theme_name,
        scale=scale,
    )
    return await loop.run_in_executor(None, func)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _load_json(path: str) -> dict:
    """JSON ファイルを読み込む."""
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    """CLI エントリポイント."""
    parser = argparse.ArgumentParser(
        description="チャートデータからPNG画像を生成する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
JSON入力例:
{
    "chart_type": "bar",
    "title": "セクター別リターン",
    "data": {
        "categories": ["XLK", "XLE", "XLF"],
        "series": [{"label": "週間", "values": [3.77, 2.67, -0.88]}],
        "color_by_value": true
    }
}
        """,
    )
    parser.add_argument("input", help="入力JSONファイルのパス")
    parser.add_argument("-o", "--output", required=True, help="出力PNGファイルのパス")
    parser.add_argument(
        "--theme",
        default=DEFAULT_THEME,
        help=f"テーマ名（デフォルト: {DEFAULT_THEME}）",
    )
    parser.add_argument(
        "--scale",
        type=int,
        default=DEFAULT_SCALE,
        help="デバイスピクセル比（デフォルト: 2）",
    )
    parser.add_argument("--preset", help="プリセット名（chart_presets.py で定義）")

    args = parser.parse_args()

    spec = _load_json(args.input)

    # プリセット適用
    if args.preset:
        try:
            from scripts.chart_presets import apply_preset
        except ModuleNotFoundError:
            from chart_presets import apply_preset

        spec = apply_preset(args.preset, spec)

    generate_chart_image(
        spec=spec,
        output_path=args.output,
        theme_name=args.theme,
        scale=args.scale,
    )

    print(f"Generated: {args.output}")


if __name__ == "__main__":
    main()
