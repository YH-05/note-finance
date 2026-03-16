"""note.com 記事用チャートテーマ設定.

チャート画像の統一的なビジュアルスタイルを定義する。
generate-table-image の DEFAULT_THEME_COLOR (#2563eb) と統一。

Usage
-----
    from scripts.chart_theme import NOTE_LIGHT, apply_theme

    apply_theme(NOTE_LIGHT)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ChartTheme:
    """チャートのビジュアルテーマ定義."""

    name: str
    font_family: str = "Noto Sans JP"
    title_size: int = 16
    label_size: int = 12
    tick_size: int = 10
    caption_size: int = 9
    background_color: str = "#FFFFFF"
    text_color: str = "#333333"
    grid_color: str = "#E8E8E8"
    grid_alpha: float = 0.5
    palette: list[str] = field(
        default_factory=lambda: [
            "#2563EB",  # blue (Primary / Positive)
            "#DC2626",  # red (Negative)
            "#059669",  # green
            "#D97706",  # amber
            "#7C3AED",  # purple
            "#DB2777",  # pink
            "#0891B2",  # cyan
            "#65A30D",  # lime
        ]
    )
    positive_color: str = "#2563EB"
    negative_color: str = "#DC2626"
    spine_visible: bool = False


NOTE_LIGHT = ChartTheme(name="note_light")

NOTE_DARK = ChartTheme(
    name="note_dark",
    background_color="#1A1A2E",
    text_color="#E0E0E0",
    grid_color="#333355",
    grid_alpha=0.4,
)

_THEMES: dict[str, ChartTheme] = {
    "note_light": NOTE_LIGHT,
    "note_dark": NOTE_DARK,
}


def get_theme(name: str) -> ChartTheme:
    """名前でテーマを取得する.

    Parameters
    ----------
    name : str
        テーマ名（"note_light" | "note_dark"）。

    Returns
    -------
    ChartTheme
        テーマ設定。

    Raises
    ------
    ValueError
        未知のテーマ名が指定された場合。
    """
    if name not in _THEMES:
        available = ", ".join(sorted(_THEMES.keys()))
        raise ValueError(f"Unknown theme '{name}'. Available: {available}")
    return _THEMES[name]


def apply_theme(theme: ChartTheme) -> None:
    """matplotlib の rcParams にテーマを適用する.

    Parameters
    ----------
    theme : ChartTheme
        適用するテーマ。
    """
    import matplotlib
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    matplotlib.use("Agg")

    _setup_font(theme.font_family)

    plt.rcParams.update(
        {
            "figure.facecolor": theme.background_color,
            "axes.facecolor": theme.background_color,
            "axes.edgecolor": theme.grid_color,
            "axes.labelcolor": theme.text_color,
            "axes.labelsize": theme.label_size,
            "axes.titlesize": theme.title_size,
            "axes.grid": True,
            "axes.spines.top": theme.spine_visible,
            "axes.spines.right": theme.spine_visible,
            "axes.spines.left": theme.spine_visible,
            "axes.spines.bottom": theme.spine_visible,
            "grid.color": theme.grid_color,
            "grid.alpha": theme.grid_alpha,
            "xtick.color": theme.text_color,
            "xtick.labelsize": theme.tick_size,
            "ytick.color": theme.text_color,
            "ytick.labelsize": theme.tick_size,
            "text.color": theme.text_color,
            "figure.titlesize": theme.title_size,
            "legend.fontsize": theme.tick_size,
            "legend.framealpha": 0.8,
        }
    )

    logger.debug("Theme applied", theme=theme.name)


def _setup_font(font_family: str) -> None:
    """日本語フォントを検出して設定する."""
    import os

    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    # 環境変数で明示的に指定
    env_path = os.environ.get("CHART_FONT_PATH")
    if env_path and Path(env_path).is_file():
        font_manager.fontManager.addfont(env_path)
        plt.rcParams["font.family"] = font_family
        logger.debug("Font loaded from env", path=env_path)
        return

    # システムフォントから検索
    jp_fonts = [
        "Noto Sans JP",
        "Noto Sans CJK JP",
        "Hiragino Sans",
        "Hiragino Kaku Gothic Pro",
        "Yu Gothic",
        "Meiryo",
    ]
    available_fonts = {f.name for f in font_manager.fontManager.ttflist}

    for name in jp_fonts:
        if name in available_fonts:
            plt.rcParams["font.family"] = name
            logger.debug("Japanese font found", font=name)
            return

    logger.warning(
        "Japanese font not found, using default. "
        "Install Noto Sans JP or set CHART_FONT_PATH env var."
    )
