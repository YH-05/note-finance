"""時系列チャートテンプレート.

長期間の日次データを datetime X軸でプロットする汎用テンプレート。
generate_chart_image.py のカテゴリ軸ではなく、matplotlib.dates を直接使用する。

Usage
-----
    # このファイルをコピーしてデータ取得部分をカスタマイズする
    PYTHONPATH=scripts uv run python your_chart.py

カスタマイズポイント
------------------
    1. データ取得部分（FRED / yfinance / CSV 等）
    2. series_config（系列名・カラー）
    3. タイトル・Y軸ラベル
    4. X軸の間隔（YearLocator の引数）
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

import httpx
import matplotlib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from chart_theme import NOTE_LIGHT, apply_theme

# ---------------------------------------------------------------------------
# 1. 設定
# ---------------------------------------------------------------------------
START_DATE = "1999-01-01"
END_DATE = "2026-03-16"
OUTPUT_PATH = ".tmp/timeseries_chart.png"

# 描画する系列の定義
SERIES_IDS = ["DGS3MO", "DGS1", "DGS2", "DGS5", "DGS10", "DGS30"]
SERIES_LABELS = {
    "DGS3MO": "3ヶ月",
    "DGS1": "1年",
    "DGS2": "2年",
    "DGS5": "5年",
    "DGS10": "10年",
    "DGS30": "30年",
}

# ブルー系グラデーション（短期=薄い → 長期=濃い）
BLUE_GRADIENT = [
    "#93C5FD",  # light blue
    "#60A5FA",
    "#3B82F6",
    "#2563EB",
    "#1D4ED8",
    "#1E3A8A",  # dark navy
]


# ---------------------------------------------------------------------------
# 2. データ取得（FRED 公開 CSV）
# ---------------------------------------------------------------------------
def fetch_fred_data(
    series_ids: list[str],
    start: str,
    end: str,
) -> tuple[list[datetime], dict[str, list[float]]]:
    """FRED から複数系列の日次データを取得する."""
    url = (
        f"https://fred.stlouisfed.org/graph/fredgraph.csv"
        f"?cosd={start}&coed={end}"
        f"&id={','.join(series_ids)}"
    )
    resp = httpx.get(url, follow_redirects=True, timeout=30)
    resp.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(resp.text)))

    dates: list[datetime] = []
    series_data: dict[str, list[float]] = {sid: [] for sid in series_ids}

    for row in rows:
        d = row["observation_date"]
        if d < start or d > end:
            continue
        vals: dict[str, float] = {}
        ok = True
        for sid in series_ids:
            v = row.get(sid, "").strip()
            if v and v != ".":
                vals[sid] = float(v)
            else:
                ok = False
                break
        if ok:
            dates.append(datetime.strptime(d, "%Y-%m-%d"))
            for sid in series_ids:
                series_data[sid].append(vals[sid])

    return dates, series_data


# ---------------------------------------------------------------------------
# 3. 日付フォーマット（0パディングなし）
# ---------------------------------------------------------------------------
def fmt_date(dt: datetime) -> str:
    """日本語日付文字列（0パディングなし）."""
    return f"{dt.year}年{dt.month}月{dt.day}日"


# ---------------------------------------------------------------------------
# 4. 描画
# ---------------------------------------------------------------------------
def main() -> None:
    """チャートを生成する."""
    matplotlib.use("Agg")

    dates, series_data = fetch_fred_data(SERIES_IDS, START_DATE, END_DATE)
    print(f"Data points: {len(dates)}")

    theme = NOTE_LIGHT
    apply_theme(theme)

    fig, ax = plt.subplots(figsize=(11, 5.5))

    # 複数ライン: alpha=0.6, linewidth=1.0
    for i, sid in enumerate(SERIES_IDS):
        ax.plot(
            dates,
            series_data[sid],
            label=SERIES_LABELS[sid],
            color=BLUE_GRADIENT[i],
            linewidth=1.0,
            alpha=0.6,
        )

    # タイトル: 1行で完結、日付は0パディングなし
    actual_start = fmt_date(dates[0])
    actual_end = fmt_date(dates[-1])
    ax.set_title(
        f"米国債利回り推移（{actual_start}〜{actual_end}）",
        fontsize=theme.title_size,
        fontweight="bold",
        pad=15,
    )
    ax.set_ylabel("利回り (%)", fontsize=theme.label_size)

    # X軸: 5年間隔
    ax.xaxis.set_major_locator(mdates.YearLocator(5))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_minor_locator(mdates.YearLocator(1))
    ax.set_xlim(dates[0], dates[-1])

    # 凡例: X軸下部に横並び
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.1),
        fontsize=9,
        ncol=len(SERIES_IDS),
        frameon=False,
    )

    fig.tight_layout(rect=[0, 0.05, 1, 1.0])

    fig.savefig(
        OUTPUT_PATH,
        dpi=200,
        bbox_inches="tight",
        facecolor=theme.background_color,
        pad_inches=0.2,
    )
    plt.close(fig)
    print(f"Saved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
