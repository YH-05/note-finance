#!/usr/bin/env python3
"""決算プレビュー記事用の株価 + 累積リターンチャート生成スクリプト.

analyze_earnings_reaction.py の出力 JSON から決算発表日を読み取り、
5年間の株価推移（上段）と累積リターン（下段）の2段チャートを生成する。
各決算発表日に赤丸マーカーと矢印アノテーションを配置する。

Examples
--------
reaction JSON を入力に自動生成:

    $ uv run python scripts/generate_earnings_chart.py \\
        --reaction-json .tmp/blk_reaction.json \\
        --output articles/earnings/.../images/chart_price.png

銘柄指定のみ（reaction JSON なし、決算マーカーなし）:

    $ uv run python scripts/generate_earnings_chart.py \\
        --symbol BLK \\
        --output .tmp/blk_chart.png

Notes
-----
- yfinance API から都度 5 年分のデータを取得する
- chart_theme.py を参照するため PYTHONPATH=scripts が必要
- 実行: ``PYTHONPATH=scripts uv run --with yfinance python scripts/generate_earnings_chart.py ...``
  または ``uv run`` で yfinance がプロジェクト依存にあればそのまま実行可能
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

from utils_core.logging.config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MARKER_RADIUS_PT = 9
"""赤丸マーカーの半径（ポイント単位）."""

DEFAULT_PERIOD = "5y"
"""yfinance から取得するデフォルト期間."""


# ---------------------------------------------------------------------------
# Earnings label helpers
# ---------------------------------------------------------------------------


def _fiscal_quarter_to_label(fiscal_quarter: str) -> str:
    """fiscal_quarter 文字列をラベルに変換する.

    Parameters
    ----------
    fiscal_quarter : str
        "2025-Q4" 形式の文字列。

    Returns
    -------
    str
        "4Q25" 形式のラベル。
    """
    # "2025-Q4" -> year=2025, q=4
    parts = fiscal_quarter.split("-Q")
    if len(parts) != 2:
        return fiscal_quarter
    year = parts[0][-2:]  # 下2桁
    quarter = parts[1]
    return f"{quarter}Q{year}"


def _date_to_label(date_str: str) -> str:
    """日付文字列を表示ラベルに変換する（0パディングなし）.

    Parameters
    ----------
    date_str : str
        "2026-01-15" 形式の日付文字列。

    Returns
    -------
    str
        "2026/1/15" 形式のラベル。
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{dt.year}/{dt.month}/{dt.day}"


def build_earnings_dates(reaction_data: dict) -> list[tuple[str, str]]:
    """reaction JSON から決算日ラベルのリストを構築する.

    Parameters
    ----------
    reaction_data : dict
        analyze_earnings_reaction.py の出力 JSON。

    Returns
    -------
    list[tuple[str, str]]
        (date_str, label) のリスト。label は "4Q25\\n2026/1/15" 形式。
    """
    result: list[tuple[str, str]] = []
    for entry in reaction_data.get("earnings_reactions", []):
        reported_date = entry.get("reported_date")
        fiscal_quarter = entry.get("fiscal_quarter")
        if not reported_date or not fiscal_quarter:
            continue
        q_label = _fiscal_quarter_to_label(fiscal_quarter)
        d_label = _date_to_label(reported_date)
        result.append((reported_date, f"{q_label}\n{d_label}"))
    return result


# ---------------------------------------------------------------------------
# Annotation helper
# ---------------------------------------------------------------------------


def _annotate_panel(
    ax: plt.Axes,
    fig: plt.Figure,
    dt: datetime,
    value: float,
    label: str,
    above: bool,
) -> None:
    """パネルに赤丸 + 矢印アノテーションを描画する.

    Parameters
    ----------
    ax : plt.Axes
        描画先の Axes。
    fig : plt.Figure
        親 Figure（DPI 計算用）。
    dt : datetime
        決算発表日。
    value : float
        アンカーポイントの Y 値（株価 or 累積リターン）。
    label : str
        アノテーションテキスト。
    above : bool
        True なら上方向、False なら下方向にアノテーション配置。
    """
    # 赤丸マーカー
    ax.plot(
        dt, value,
        marker="o", markersize=MARKER_RADIUS_PT,
        markerfacecolor="none",
        markeredgecolor="#D6604D",
        markeredgewidth=1.5,
        zorder=5,
    )

    # 丸の縁に矢印先端を合わせる（ピクセル→データ座標変換）
    transform = ax.transData
    inv_transform = transform.inverted()
    anchor_px = transform.transform((mdates.date2num(dt), value))
    marker_radius_px = MARKER_RADIUS_PT * (fig.dpi / 72.0) * 0.5

    if above:
        text_offset_pt = (0, 55)
        arrow_tip_px = (anchor_px[0], anchor_px[1] + marker_radius_px)
    else:
        text_offset_pt = (0, -60)
        arrow_tip_px = (anchor_px[0], anchor_px[1] - marker_radius_px)

    arrow_tip_data = inv_transform.transform(arrow_tip_px)
    arrow_tip_date = mdates.num2date(arrow_tip_data[0])
    arrow_tip_y = arrow_tip_data[1]

    ax.annotate(
        label,
        xy=(arrow_tip_date, arrow_tip_y),
        xytext=text_offset_pt,
        textcoords="offset points",
        fontsize=7, color="#D6604D", fontweight="bold",
        ha="center", va="center",
        arrowprops={
            "arrowstyle": "->",
            "color": "#D6604D",
            "alpha": 0.7,
            "linewidth": 1.2,
        },
    )


# ---------------------------------------------------------------------------
# Main chart generation
# ---------------------------------------------------------------------------


def generate_earnings_chart(
    symbol: str,
    output_path: str,
    earnings_dates: list[tuple[str, str]] | None = None,
    period: str = DEFAULT_PERIOD,
) -> None:
    """決算プレビュー用の2段チャートを生成する.

    Parameters
    ----------
    symbol : str
        ティッカーシンボル。
    output_path : str
        出力 PNG ファイルパス。
    earnings_dates : list[tuple[str, str]] | None
        決算発表日とラベルのリスト。None の場合はマーカーなし。
    period : str
        yfinance の取得期間（デフォルト: "5y"）。
    """
    import yfinance as yf
    from chart_theme import NOTE_LIGHT, apply_theme

    matplotlib.use("Agg")

    logger.info("Fetching %s price data (period=%s)", symbol, period)
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=period)

    if hist.empty:
        logger.error("No price data returned for %s", symbol)
        sys.exit(1)

    hist.index = hist.index.tz_localize(None)

    dates = hist.index.to_list()
    closes = np.array(hist["Close"].to_list())
    cumulative_return = (closes / closes[0] - 1) * 100

    logger.info(
        "Data points: %d, range: %s ~ %s",
        len(dates), dates[0].date(), dates[-1].date(),
    )

    theme = NOTE_LIGHT
    apply_theme(theme)

    fig, (ax_price, ax_ret) = plt.subplots(
        2, 1, figsize=(12, 9), sharex=True,
        gridspec_kw={"height_ratios": [1, 1], "hspace": 0.08},
    )
    fig.subplots_adjust(top=0.93)

    # 上段: 株価
    ax_price.plot(dates, closes, color="#2166AC", linewidth=1.8, alpha=1.0)
    ax_price.fill_between(dates, closes, alpha=0.08, color="#2166AC")
    ax_price.set_ylabel("株価 (USD)", fontsize=theme.label_size)
    ax_price.set_title(
        f"{symbol} 株価推移と累積リターン（直近{period.replace('y', '年')}）",
        fontsize=theme.title_size, fontweight="bold", pad=15,
        loc="left",
    )
    ax_price.tick_params(axis="x", which="both", bottom=False, labelbottom=False)

    # 下段: 累積リターン
    ax_ret.plot(dates, cumulative_return, color="#1A9641", linewidth=1.8, alpha=1.0)
    ax_ret.fill_between(dates, cumulative_return, alpha=0.08, color="#1A9641")
    ax_ret.axhline(y=0, color="#888888", linewidth=0.8, linestyle="-", alpha=0.5)
    ax_ret.set_ylabel("累積リターン (%)", fontsize=theme.label_size)

    # 決算発表日アノテーション
    if earnings_dates:
        fig.canvas.draw()  # レンダラー確定

        for i, (date_str, label) in enumerate(earnings_dates):
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            if dates[0] <= dt <= dates[-1]:
                nearest_idx = min(
                    range(len(dates)), key=lambda j: abs(dates[j] - dt),
                )
                above = i % 2 == 0
                _annotate_panel(ax_price, fig, dt, closes[nearest_idx], label, above)
                _annotate_panel(
                    ax_ret, fig, dt, cumulative_return[nearest_idx], label, above,
                )

        logger.info("Annotated %d earnings dates", len(earnings_dates))

    # X軸
    ax_ret.xaxis.set_major_locator(mdates.YearLocator())
    ax_ret.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax_ret.xaxis.set_minor_locator(mdates.MonthLocator(interval=3))
    ax_ret.set_xlim(dates[0], dates[-1])

    # 保存
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    fig.savefig(
        output_path, dpi=200, bbox_inches="tight",
        facecolor=theme.background_color, pad_inches=0.2,
    )
    plt.close(fig)
    logger.info("Saved: %s", output_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI エントリーポイント."""
    parser = argparse.ArgumentParser(
        description="決算プレビュー用 株価 + 累積リターン チャート生成",
    )
    parser.add_argument(
        "--symbol",
        default=None,
        help="ティッカーシンボル（--reaction-json 未指定時は必須）",
    )
    parser.add_argument(
        "--reaction-json",
        default=None,
        help="analyze_earnings_reaction.py の出力 JSON パス",
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="出力 PNG ファイルパス",
    )
    parser.add_argument(
        "--period",
        default=DEFAULT_PERIOD,
        help="yfinance 取得期間（デフォルト: 5y）",
    )

    args = parser.parse_args()

    # reaction JSON があればシンボルと決算日を取得
    earnings_dates: list[tuple[str, str]] | None = None
    symbol = args.symbol

    if args.reaction_json:
        reaction_path = Path(args.reaction_json)
        if not reaction_path.exists():
            logger.error("Reaction JSON not found: %s", reaction_path)
            sys.exit(1)

        with reaction_path.open() as f:
            reaction_data = json.load(f)

        if not symbol:
            symbol = reaction_data.get("symbol")
        earnings_dates = build_earnings_dates(reaction_data)
        logger.info(
            "Loaded %d earnings dates from %s",
            len(earnings_dates), reaction_path,
        )

    if not symbol:
        parser.error("--symbol または --reaction-json のいずれかを指定してください")

    generate_earnings_chart(
        symbol=symbol,
        output_path=args.output,
        earnings_dates=earnings_dates,
        period=args.period,
    )


if __name__ == "__main__":
    main()
