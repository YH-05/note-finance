"""週次レポート・記事向けプリセットチャート定義.

データJSON → チャート仕様 への変換関数を提供する。

Usage
-----
    from scripts.chart_presets import apply_preset

    spec = apply_preset("indices_bar", raw_data)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger(__name__)

_PRESETS: dict[str, object] = {}


def register_preset(name: str):
    """プリセット変換関数を登録するデコレータ."""

    def decorator(func):
        _PRESETS[name] = func
        return func

    return decorator


def apply_preset(name: str, data: dict) -> dict:
    """プリセットを適用してチャート仕様を生成する.

    Parameters
    ----------
    name : str
        プリセット名。
    data : dict
        入力データ。

    Returns
    -------
    dict
        チャート仕様。

    Raises
    ------
    ValueError
        未知のプリセット名が指定された場合。
    """
    if name not in _PRESETS:
        available = ", ".join(sorted(_PRESETS.keys()))
        raise ValueError(f"Unknown preset '{name}'. Available: {available}")
    logger.info("Applying preset", preset=name)
    return _PRESETS[name](data)


def list_presets() -> list[str]:
    """利用可能なプリセット名一覧を返す."""
    return sorted(_PRESETS.keys())


# ---------------------------------------------------------------------------
# Preset definitions
# ---------------------------------------------------------------------------
@register_preset("indices_bar")
def _indices_bar(data: dict) -> dict:
    """指数別リターン棒グラフ.

    入力: {"indices": [{"name": "S&P 500", "return": 1.5}, ...]}
    """
    indices = data.get("indices", [])
    return {
        "chart_type": "bar",
        "title": "主要指数 週間リターン",
        "data": {
            "categories": [idx["name"] for idx in indices],
            "series": [
                {"label": "週間リターン", "values": [idx["return"] for idx in indices]}
            ],
            "y_format": "percent",
            "sort": "descending",
            "color_by_value": True,
        },
    }


@register_preset("sectors_bar")
def _sectors_bar(data: dict) -> dict:
    """セクター別リターン棒グラフ.

    入力: {"sectors": [{"name": "XLK", "return": 3.77}, ...]}
    """
    sectors = data.get("sectors", [])
    return {
        "chart_type": "hbar",
        "title": "セクター別 週間リターン",
        "data": {
            "categories": [s["name"] for s in sectors],
            "series": [
                {"label": "週間リターン", "values": [s["return"] for s in sectors]}
            ],
            "y_format": "percent",
            "sort": "descending",
            "color_by_value": True,
        },
    }


@register_preset("mag7_bar")
def _mag7_bar(data: dict) -> dict:
    """MAG7銘柄リターン棒グラフ.

    入力: {"stocks": [{"ticker": "AAPL", "return": 2.1}, ...]}
    """
    stocks = data.get("stocks", [])
    return {
        "chart_type": "bar",
        "title": "MAG7 週間リターン",
        "data": {
            "categories": [s["ticker"] for s in stocks],
            "series": [
                {"label": "週間リターン", "values": [s["return"] for s in stocks]}
            ],
            "y_format": "percent",
            "sort": "descending",
            "color_by_value": True,
        },
    }


@register_preset("asset_simulation")
def _asset_simulation(data: dict) -> dict:
    """資産シミュレーション面グラフ.

    入力: {"years": [0, 5, 10, ...], "series": [{"label": "積立NISA", "values": [...]}, ...]}
    """
    return {
        "chart_type": "area",
        "title": data.get("title", "資産シミュレーション"),
        "data": {
            "x": data.get("years", []),
            "series": data.get("series", []),
            "x_label": "年数",
            "y_label": "資産額",
            "y_format": "yen",
            "stacked": False,
        },
    }


@register_preset("dot_plot")
def _dot_plot(data: dict) -> dict:
    """FRBドットプロット散布図.

    入力: {"points": [{"x": 2026, "y": 4.25, "size": 30}, ...]}
    """
    return {
        "chart_type": "scatter",
        "title": data.get("title", "FOMC ドットプロット"),
        "data": {
            "points": data.get("points", []),
            "x_label": "年",
            "y_label": "FF金利 (%)",
            "show_median": True,
        },
    }
