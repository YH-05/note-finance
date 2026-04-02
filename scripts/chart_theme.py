"""note.com 記事用チャートテーマ設定.

チャート画像の統一的なビジュアルスタイルを定義する。
generate-table-image の DEFAULT_THEME_COLOR (#2563eb) と統一。

Usage
-----
    from scripts.chart_theme import NOTE_LIGHT, JP_ANALYSIS, apply_theme

    apply_theme(NOTE_LIGHT)
    apply_theme(JP_ANALYSIS)
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

    # ── 背景色 ──────────────────────────────────────────────────────────────
    background_color: str = "#FFFFFF"    # figure全体の背景
    plot_bg_color: str = ""              # プロットエリアの背景（空 = background_colorと同じ）

    # ── テキスト・グリッド ──────────────────────────────────────────────────
    text_color: str = "#333333"
    grid_color: str = "#E0E0E0"
    grid_alpha: float = 0.7
    grid_y_only: bool = True             # True: 水平グリッドのみ / False: H+V 格子グリッド

    # ── カラーパレット ─────────────────────────────────────────────────────
    palette: list[str] = field(
        default_factory=lambda: [
            "#2166AC",  # 深い信頼感の青 (Primary) — ColorBrewer RdYlBu
            "#D6604D",  # 暖かいコーラルレッド (Negative/Inflation)
            "#1A9641",  # フォレストグリーン (Growth/Positive)
            "#FDAE61",  # 温かいアンバー
            "#762A83",  # 落ち着いたパープル
            "#4393C3",  # スカイブルー
            "#A6DBA0",  # ペールグリーン
            "#C2A5CF",  # ソフトパープル
        ]
    )
    positive_color: str = "#2166AC"
    negative_color: str = "#D6604D"

    # ── スパイン（軸の枠線）─────────────────────────────────────────────────
    spine_visible: bool = False          # 上・右・下スパイン
    spine_left_visible: bool = True      # 左スパイン（データのアンカリング）
    spine_color: str = ""                # スパインの色（空 = grid_colorと同じ）

    # ── 凡例 ─────────────────────────────────────────────────────────────────
    legend_frameon: bool = False
    legend_bg_color: str = "#FFFFFF"     # 凡例の背景色

    # ── 線・面 ───────────────────────────────────────────────────────────────
    line_width: float = 2.5              # デフォルト線幅（シリーズ側で個別上書き可）
    area_alpha: float = 0.13             # エリア塗り alpha


NOTE_LIGHT = ChartTheme(name="note_light")

NOTE_DARK = ChartTheme(
    name="note_dark",
    background_color="#1A1A2E",
    text_color="#E0E0E0",
    grid_color="#333355",
    grid_alpha=0.4,
)

# ── JP_ANALYSIS: 日本のマクロ経済チャート風スタイル ─────────────────────────
# 特徴:
#   - 薄い水色の figure 背景 + 白いプロットエリア
#   - 格子状グリッド (H+V) で読みやすい
#   - 全スパイン（矩形ボーダー）
#   - 大きなタイトル、シンプルな凡例
JP_ANALYSIS = ChartTheme(
    name="jp_analysis",
    title_size=22,
    label_size=12,
    tick_size=12,
    caption_size=11,
    background_color="#E8F4FD",          # 薄い水色の figure 背景
    plot_bg_color="#FFFFFF",             # 白いプロットエリア
    text_color="#1A1A1A",
    grid_color="#C4D4E4",                # 水色がかったグリッド
    grid_alpha=0.85,
    grid_y_only=False,                   # H+V 格子グリッド
    palette=[
        "#1E5FA5",  # 深い青（Primary — 全社員・公式雇用など）
        "#CC1100",  # 鮮やかなレッド（Secondary — 派遣・ADP など）
        "#1A7F37",  # ダークグリーン
        "#E07B00",  # ダークオレンジ
        "#5B2C6F",  # パープル
        "#007B7B",  # ティール
    ],
    positive_color="#1E5FA5",
    negative_color="#CC1100",
    spine_visible=True,                  # 上右下スパイン → 矩形ボーダー
    spine_left_visible=True,
    spine_color="#8CAABB",               # 中明度の青灰色ボーダー
    legend_frameon=True,
    legend_bg_color="#FFFFFFCC",         # 半透明白
    line_width=2.0,
    area_alpha=0.15,
)

_THEMES: dict[str, ChartTheme] = {
    "note_light": NOTE_LIGHT,
    "note_dark": NOTE_DARK,
    "jp_analysis": JP_ANALYSIS,
}


def get_theme(name: str) -> ChartTheme:
    """名前でテーマを取得する.

    Parameters
    ----------
    name : str
        テーマ名（"note_light" | "note_dark" | "jp_analysis"）。

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

    matplotlib.use("Agg")

    _setup_font(theme.font_family)

    plot_bg = theme.plot_bg_color if theme.plot_bg_color else theme.background_color
    spine_c = theme.spine_color if theme.spine_color else theme.grid_color

    plt.rcParams.update(
        {
            "figure.facecolor": theme.background_color,
            "axes.facecolor": plot_bg,
            "axes.edgecolor": spine_c,
            "axes.labelcolor": theme.text_color,
            "axes.labelsize": theme.label_size,
            "axes.titlesize": theme.title_size,
            "axes.grid": True,
            "axes.axisbelow": True,              # グリッドをデータの下に描画
            "axes.spines.top": theme.spine_visible,
            "axes.spines.right": theme.spine_visible,
            "axes.spines.left": theme.spine_left_visible,
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
            "legend.frameon": theme.legend_frameon,
            "legend.facecolor": theme.legend_bg_color,
            "legend.framealpha": 0.0 if not theme.legend_frameon else 0.9,
            "legend.edgecolor": spine_c,
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
