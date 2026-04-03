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
    ax: object,
    annotations: list[dict] | None,
    theme: object,
    x_labels: list[str] | None = None,
) -> None:
    """チャートにアノテーションを追加する.

    サポートするタイプ:
    - text / arrow : テキスト＆矢印ラベル
    - circle       : 点線楕円（注目領域ハイライト）
    """
    if not annotations:
        return

    for ann in annotations:
        ann_type = ann.get("type", "text")
        ann_color = ann.get("color", theme.text_color)

        # ── 点線楕円（サンプルチャートの「注目サークル」）──────────────────
        if ann_type == "circle":
            from matplotlib.patches import Ellipse

            # 中心 x の解決（文字列ラベル → インデックス）
            cx_raw = ann.get("cx", ann.get("x"))
            cy = float(ann.get("cy", ann.get("y", 0)))

            if cx_raw is None and x_labels:
                cx = len(x_labels) * 0.85  # デフォルト: 右端付近
            elif isinstance(cx_raw, str) and x_labels:
                xl = list(x_labels)
                if cx_raw in xl:
                    cx = float(xl.index(cx_raw))
                else:
                    cx = next(
                        (float(i) for i, l in enumerate(xl) if l.startswith(cx_raw[:7])),
                        len(xl) * 0.85,
                    )
            else:
                cx = float(cx_raw) if cx_raw is not None else 0.0

            x_span = float(ann.get("x_span", ann.get("width_n", 5)))
            y_span = float(ann.get("y_span", ann.get("height", 4)))
            ls_map = {"dashed": "--", "dotted": ":", "solid": "-"}
            ls = ls_map.get(ann.get("style", "dashed"), "--")

            ellipse = Ellipse(
                xy=(cx, cy),
                width=x_span,
                height=y_span,
                fill=False,
                edgecolor=ann_color,
                linestyle=ls,
                linewidth=float(ann.get("linewidth", 1.8)),
                zorder=10,
            )
            ax.add_patch(ellipse)

        # ── 矢印アノテーション ─────────────────────────────────────────────
        elif ann_type == "arrow" or ann.get("arrow"):
            x_from = ann.get("x_from", ann.get("x_text", ann.get("x")))
            y_from = ann.get("y_from", ann.get("y_text", ann.get("y")))
            x_to = ann.get("x_to", ann.get("x"))
            y_to = ann.get("y_to", ann.get("y"))
            ax.annotate(
                ann.get("text", ""),
                xy=(x_to, y_to),
                xytext=(x_from, y_from),
                fontsize=theme.caption_size,
                color=ann_color,
                ha=ann.get("ha", "center"),
                va=ann.get("va", "center"),
                arrowprops={
                    "arrowstyle": "->",
                    "color": ann_color,
                    "lw": 1.5,
                },
            )

        # ── テキストラベル ─────────────────────────────────────────────────
        else:
            ax.annotate(
                ann.get("text", ""),
                xy=(ann["x"], ann["y"]),
                fontsize=float(ann.get("fontsize", theme.caption_size)),
                color=ann_color,
                ha=ann.get("ha", "center"),
                va=ann.get("va", "center"),
                fontweight=ann.get("fontweight", "normal"),
            )


def _add_caption(fig: object, caption: str | None, theme: object) -> None:
    """図の下部にキャプション（出典等）を追加する.

    jp_analysis テーマでは左揃え（「出所：〜」スタイル）。
    """
    if not caption:
        return
    # jp_analysis: 左揃え・太字なし・サンプルチャート風
    is_jp = getattr(theme, "name", "") == "jp_analysis"
    fig.text(
        0.02 if is_jp else 0.5,
        0.01,
        caption,
        ha="left" if is_jp else "center",
        va="bottom",
        fontsize=theme.caption_size,
        color=theme.text_color if is_jp else "#888888",
        style="normal" if is_jp else "italic",
    )


def _color_bars_by_value(bars: object, values: list[float], theme: object) -> None:
    """値の正負に基づいて棒の色を設定する."""
    for bar, val in zip(bars, values, strict=False):
        bar.set_color(theme.positive_color if val >= 0 else theme.negative_color)


def _render_reference_lines(
    ax: object, ref_lines: list[dict] | None, theme: object
) -> None:
    """水平基準線を描画する（FRB目標・価格閾値・ゼロラインなど）.

    Parameters
    ----------
    ref_lines : list[dict] | None
        各要素: {
            "y": float,
            "label": str,
            "color": str,
            "style": "solid"|"dashed"|"dotted",
            "linewidth": float,   # デフォルト 1.2
            "alpha": float,       # デフォルト 0.75
            "label_side": "right"|"left"  # デフォルト "right"
        }
    """
    if not ref_lines:
        return
    for ref in ref_lines:
        y_val = float(ref["y"])
        color = ref.get("color", "#AAAAAA")
        style = ref.get("style", "dashed")
        linestyle = {"dashed": "--", "dotted": ":", "solid": "-"}.get(style, "--")
        lw = float(ref.get("linewidth", 1.2))
        alpha = float(ref.get("alpha", 0.75))
        label = ref.get("label", "")
        label_side = ref.get("label_side", "right")

        ax.axhline(
            y=y_val,
            color=color,
            linestyle=linestyle,
            linewidth=lw,
            alpha=alpha,
            zorder=1,
        )
        if label:
            x_pos = 1.01 if label_side == "right" else -0.01
            ha = "left" if label_side == "right" else "right"
            ax.text(
                x_pos,
                y_val,
                label,
                transform=ax.get_yaxis_transform(),
                fontsize=theme.caption_size,
                color=color,
                va="center",
                ha=ha,
                clip_on=False,
            )


def _render_event_lines(
    ax: object,
    event_lines: list[dict] | None,
    x_labels: list[str],
    theme: object,
) -> None:
    """垂直イベントラインを描画する（歴史的事件のマーカー）.

    Parameters
    ----------
    event_lines : list[dict] | None
        各要素: {"x": "2022/03", "label": "ウクライナ侵攻", "color": "#D6604D"}
    x_labels : list[str]
        x軸ラベルのリスト
    """
    if not event_lines:
        return
    x_list = list(x_labels)
    for event in event_lines:
        key = event.get("x", "")
        # 完全一致 → 年月前方一致の順で検索
        idx = None
        if key in x_list:
            idx = x_list.index(key)
        else:
            for i, xl in enumerate(x_list):
                if xl.startswith(key[:7]):
                    idx = i
                    break
        if idx is None:
            continue
        color = event.get("color", "#AAAAAA")
        text = event.get("label", "")
        ax.axvline(
            x=x_list[idx],
            color=color,
            linestyle="--",
            linewidth=1.0,
            alpha=0.5,
            zorder=1,
        )
        if text:
            y_top = ax.get_ylim()[1]
            ax.annotate(
                text,
                xy=(x_list[idx], y_top * 0.97),
                fontsize=theme.caption_size - 1,
                color=color,
                ha="center",
                va="top",
                rotation=90,
                zorder=5,
                annotation_clip=False,
            )


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
    """折れ線グラフを描画する.

    シリーズ別オプション（series 要素に追加可能）:
        linewidth  : float  — 個別の線幅（テーマのデフォルトを上書き）
        color      : str    — 個別カラー（パレットを上書き）
        style      : "solid"|"dashed"|"dotted"
        glow       : bool   — 発光（ハロー）エフェクト
        marker     : "circle"|"square"|"triangle"|"diamond"|true|false
        marker_size: float  — マーカーサイズ
        last_label : bool   — 最終値ラベルを表示
        last_label_fmt : str — フォーマット文字列（例: "{:.1f}"）
    """
    x = data["x"]
    theme_lw = getattr(theme, "line_width", 2.5)

    _MARKER_MAP = {
        "circle":   "o",
        "square":   "s",
        "triangle": "^",
        "diamond":  "D",
        "dot":      ".",
        True:       "o",
        False:      None,
        None:       None,
    }
    _LS_MAP = {"solid": "-", "dashed": "--", "dotted": ":"}

    n_series = len(data.get("series", []))
    # 複数シリーズの場合はデフォルト透過率 0.7、単一は 1.0
    default_alpha = 0.7 if n_series > 1 else 1.0

    for i, series in enumerate(data.get("series", [])):
        color = series.get("color") or theme.palette[i % len(theme.palette)]
        lw = float(series.get("linewidth", theme_lw))
        style = series.get("style", "solid")
        ls = _LS_MAP.get(style, "-")
        values = series["values"]
        marker_raw = series.get("marker", None)
        marker = _MARKER_MAP.get(marker_raw, None)
        ms = float(series.get("marker_size", 5))
        alpha = float(series.get("alpha", default_alpha))

        # ── グロー（ハロー）エフェクト ─────────────────────────────────────
        if series.get("glow"):
            for gw, ga in [(lw * 5, 0.04), (lw * 3, 0.08), (lw * 1.8, 0.12)]:
                ax.plot(
                    x, values,
                    color=color,
                    linewidth=gw,
                    alpha=ga,
                    linestyle=ls,
                    zorder=2,
                    solid_capstyle="round",
                )

        # ── メインライン ───────────────────────────────────────────────────
        ax.plot(
            x,
            values,
            label=series.get("label"),
            color=color,
            linestyle=ls,
            linewidth=lw,
            alpha=alpha,
            marker=marker,
            markersize=ms,
            solid_capstyle="round",
            solid_joinstyle="round",
            zorder=3,
        )

        # ── 最終値ラベル ───────────────────────────────────────────────────
        if series.get("last_label") and values:
            last_v = values[-1]
            fmt = series.get("last_label_fmt", "{:.1f}")
            try:
                label_text = fmt.format(last_v)
            except (ValueError, KeyError):
                label_text = str(last_v)
            ax.annotate(
                label_text,
                xy=(x[-1], last_v),
                xytext=(6, -4),
                textcoords="offset points",
                fontsize=theme.tick_size + 1,
                fontweight="bold",
                color=color,
                ha="left",
                va="center",
                zorder=6,
            )

    ax.set_xlabel(data.get("x_label", ""))
    ax.set_ylabel(data.get("y_label", ""))
    _format_axis(ax, data.get("y_format"))
    # 参照ライン（水平）
    _render_reference_lines(ax, data.get("reference_lines"), theme)
    # イベントライン（垂直）
    _render_event_lines(ax, data.get("event_lines"), x, theme)
    if len(data.get("series", [])) > 1:
        ax.legend(
            loc=data.get("legend_loc", "upper left"),
            frameon=getattr(theme, "legend_frameon", False),
            borderaxespad=0.8,
        )
    _apply_annotations(ax, data.get("annotations"), theme, x_labels=list(x))


@register_renderer("area")
def _render_area(ax: object, data: dict, theme: object) -> None:
    """面グラフを描画する."""
    x = data["x"]
    lw = getattr(theme, "line_width", 2.5)
    area_alpha = getattr(theme, "area_alpha", 0.13)
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
            vals = series["values"]
            # グラジェント効果: 2層の fill_between で深みを出す
            ax.fill_between(x, vals, alpha=area_alpha * 1.5, color=color, zorder=2)
            ax.fill_between(x, vals, alpha=area_alpha, color=color, zorder=2)
            ax.plot(
                x,
                vals,
                label=series.get("label"),
                color=color,
                linewidth=lw,
                solid_capstyle="round",
                zorder=3,
            )
    ax.set_xlabel(data.get("x_label", ""))
    ax.set_ylabel(data.get("y_label", ""))
    _format_axis(ax, data.get("y_format"))
    # 参照ライン（水平）
    _render_reference_lines(ax, data.get("reference_lines"), theme)
    # イベントライン（垂直）
    _render_event_lines(ax, data.get("event_lines"), x, theme)
    if len(data.get("series", [])) > 1:
        ax.legend(frameon=getattr(theme, "legend_frameon", False))
    _apply_annotations(ax, data.get("annotations"), theme, x_labels=list(x))


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

    # 水平グリッドのみ（縦グリッド除去）
    if getattr(theme, "grid_y_only", True):
        ax.xaxis.grid(False)
        ax.yaxis.grid(True)

    # スパインカラー調整（jp_analysis は全4辺、note_light は左のみ）
    spine_c = getattr(theme, "spine_color", "") or theme.grid_color
    if getattr(theme, "spine_visible", False):
        for side in ("top", "right", "bottom", "left"):
            ax.spines[side].set_color(spine_c)
            ax.spines[side].set_linewidth(1.0)
    elif getattr(theme, "spine_left_visible", True):
        ax.spines["left"].set_color(spine_c)
        ax.spines["left"].set_linewidth(1.0)

    # x軸ティック間引き + 回転 + 再フォーマット
    # tick_every     : N 本に 1 本だけ表示
    # tick_label_fmt : "%Y" / "%Y/%m" など strftime 形式でラベルを再フォーマット
    tick_every = spec.get("tick_every", 1)
    tick_label_fmt = spec.get("tick_label_fmt")  # e.g. "%Y" or "%Y/%m"
    rotate_x = spec.get("rotate_x_labels", True)

    x_data = data.get("x", [])
    # x_tick_fontsize: x軸ラベルのフォントサイズ個別指定（省略時はテーマのtick_size）
    x_tick_fs = spec.get("x_tick_fontsize", theme.tick_size)

    if tick_every > 1 or tick_label_fmt:
        # ax.set_xticks/set_xticklabels で直接設定（tight_layout に上書きされない）
        from datetime import datetime as _dt

        chosen_pos = [i for i in range(len(x_data)) if i % max(tick_every, 1) == 0]
        chosen_labels = []
        for i in chosen_pos:
            raw = x_data[i] if i < len(x_data) else ""
            if tick_label_fmt:
                for src_fmt in ("%Y/%m/%d", "%Y/%m", "%Y-%m-%d", "%Y-%m"):
                    try:
                        raw = _dt.strptime(raw, src_fmt).strftime(tick_label_fmt)
                        break
                    except ValueError:
                        continue
            chosen_labels.append(raw)

        is_rotate = rotate_x and chart_type in ("line", "area", "combo")
        ax.set_xticks(chosen_pos)
        ax.set_xticklabels(
            chosen_labels,
            rotation=45 if is_rotate else 0,
            ha="right" if is_rotate else "center",
            fontsize=x_tick_fs,
        )
    elif rotate_x and chart_type in ("line", "area", "combo"):
        fig.canvas.draw()
        for label in ax.get_xticklabels():
            label.set_rotation(45)
            label.set_ha("right")
            label.set_fontsize(x_tick_fs)

    # キャプション
    _add_caption(fig, spec.get("caption"), theme)

    # レイアウト調整（右側に参照ラベル用のマージンを確保）
    right_margin = 0.88 if any(
        r.get("label") for r in (spec.get("data", {}).get("reference_lines") or [])
    ) else 1.0
    bottom = 0.05 if spec.get("caption") else 0.12
    fig.tight_layout(rect=[0, bottom, right_margin, 0.95 if subtitle else 1.0])

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
        default=None,
        help=f"テーマ名（デフォルト: spec内のtheme、なければ {DEFAULT_THEME}）",
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
