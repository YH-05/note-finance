#!/usr/bin/env python3
"""Analyze Earnings Reaction Script.

決算発表前後の株価反応を分析し、EPSサプライズと株価方向の乖離パターンを特定する。
決算プレビュー記事の「過去の決算実績」セクション向けデータを構造化JSONで出力する。

Processing Flow
---------------
1. yfinance API で6年分の日次株価を取得
2. alphavantage.db (SQLite) から直近N四半期の決算データを取得
3. 各四半期の決算前後リターン（1日・1週間）を算出
4. サプライズ方向と株価方向の乖離を判定
5. リターン一覧（1M, 3M, 6M, 1Y, 3Y, 5Y）を算出
6. 構造化JSON出力

Examples
--------
Basic usage:

    $ uv run python scripts/analyze_earnings_reaction.py --symbol BLK --quarters 8

Specify output file:

    $ uv run python scripts/analyze_earnings_reaction.py --symbol BLK --quarters 8 --output .tmp/blk_reaction.json

Notes
-----
- yfinance の history() はタイムゾーン付き datetime を返す → tz_localize(None) で除去
- av_earnings の reported_date は YYYY-MM-DD 文字列
- DBパス: /Volumes/personal_folder/Projects/quants/data/sqlite/alphavantage.db
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yfinance as yf

from utils_core.logging.config import get_logger

logger = get_logger(__name__)

DB_PATH = Path("/Volumes/personal_folder/Projects/quants/data/sqlite/alphavantage.db")

# --- 乖離判定閾値 ---
SURPRISE_THRESHOLD_PCT = 1.0  # サプライズ ±1% 以内は inline
PRICE_THRESHOLD_PCT = 0.5  # 株価 ±0.5% 以内は flat


def fetch_stock_history(symbol: str) -> Any:
    """yfinance から6年分の日次株価を取得する。

    Parameters
    ----------
    symbol : str
        ティッカーシンボル（例: "BLK"）

    Returns
    -------
    pd.DataFrame
        日次株価データ（タイムゾーン除去済み）

    Raises
    ------
    SystemExit
        株価データが取得できなかった場合
    """
    logger.info("Fetching stock history", symbol=symbol, period="6y")
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="6y")

    if hist.empty:
        logger.error("Failed to fetch stock history", symbol=symbol)
        print(f"ERROR: yfinance で {symbol} の株価データを取得できませんでした。", file=sys.stderr)
        sys.exit(1)

    # タイムゾーン除去（yfinance は tz-aware、SQLite は naive）
    hist.index = hist.index.tz_localize(None)
    logger.info(
        "Stock history fetched",
        symbol=symbol,
        rows=len(hist),
        date_range=f"{hist.index[0].date()} ~ {hist.index[-1].date()}",
    )
    return hist


def fetch_earnings_data(symbol: str, quarters: int) -> list[dict[str, Any]]:
    """alphavantage.db から直近N四半期の決算データを取得する。

    Parameters
    ----------
    symbol : str
        ティッカーシンボル
    quarters : int
        取得する四半期数

    Returns
    -------
    list[dict[str, Any]]
        決算データのリスト（新しい順）

    Raises
    ------
    SystemExit
        DBが存在しない場合
    """
    if not DB_PATH.exists():
        logger.error("alphavantage.db not found", path=str(DB_PATH))
        print(f"ERROR: alphavantage.db が見つかりません: {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    logger.info("Fetching earnings data", symbol=symbol, quarters=quarters)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            """
            SELECT
                symbol,
                fiscal_date_ending,
                reported_date,
                reported_eps,
                estimated_eps,
                surprise,
                surprise_percentage
            FROM av_earnings
            WHERE symbol = ? AND period_type = 'quarterly'
              AND reported_date IS NOT NULL
            ORDER BY fiscal_date_ending DESC
            LIMIT ?
            """,
            (symbol.upper(), quarters),
        )
        rows = [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

    if not rows:
        logger.warning("No earnings data found", symbol=symbol)
        print(
            f"WARNING: {symbol} の決算データが av_earnings テーブルにありません。"
            " earnings_reactions は空リストで出力します。",
            file=sys.stderr,
        )

    logger.info("Earnings data fetched", symbol=symbol, count=len(rows))
    return rows


def derive_fiscal_quarter(fiscal_date_ending: str) -> str:
    """fiscal_date_ending から fiscal_quarter を算出する。

    Parameters
    ----------
    fiscal_date_ending : str
        会計期末日（"YYYY-MM-DD"）

    Returns
    -------
    str
        四半期表記（例: "2025-Q4"）
    """
    dt = datetime.strptime(fiscal_date_ending, "%Y-%m-%d")
    quarter = (dt.month - 1) // 3 + 1
    return f"{dt.year}-Q{quarter}"


def calc_return(hist: Any, months: float) -> float | None:
    """指定月数前からのリターンを算出する。

    Parameters
    ----------
    hist : pd.DataFrame
        日次株価データ
    months : float
        何ヶ月前からのリターンを算出するか

    Returns
    -------
    float | None
        リターン（%）。算出不可の場合は None
    """
    if hist.empty:
        return None

    latest = hist["Close"].iloc[-1]
    target_date = hist.index[-1] - timedelta(days=int(months * 30.44))

    # 株価データの範囲外の場合は None
    if target_date < hist.index[0]:
        return None

    nearest_idx = hist.index.get_indexer([target_date], method="nearest")[0]
    past_price = hist["Close"].iloc[nearest_idx]

    if past_price == 0:
        return None

    return round((latest / past_price - 1) * 100, 1)


def calc_returns_summary(hist: Any) -> dict[str, float | None]:
    """リターン一覧（1M, 3M, 6M, 1Y, 3Y, 5Y）を算出する。

    Parameters
    ----------
    hist : pd.DataFrame
        日次株価データ

    Returns
    -------
    dict[str, float | None]
        期間別リターン（%）
    """
    periods = {"1M": 1, "3M": 3, "6M": 6, "1Y": 12, "3Y": 36, "5Y": 60}
    returns = {}
    for label, months in periods.items():
        ret = calc_return(hist, months)
        returns[label] = ret
        logger.debug("Return calculated", period=label, return_pct=ret)
    return returns


def determine_surprise_direction(surprise_pct: float | None) -> str:
    """サプライズ方向を判定する。

    Parameters
    ----------
    surprise_pct : float | None
        サプライズ率（%）

    Returns
    -------
    str
        "beat", "miss", or "inline"
    """
    if surprise_pct is None:
        return "inline"
    if surprise_pct > SURPRISE_THRESHOLD_PCT:
        return "beat"
    if surprise_pct < -SURPRISE_THRESHOLD_PCT:
        return "miss"
    return "inline"


def determine_price_direction(day_return_pct: float) -> str:
    """株価方向を判定する。

    Parameters
    ----------
    day_return_pct : float
        1日リターン（%）

    Returns
    -------
    str
        "up", "down", or "flat"
    """
    if day_return_pct > PRICE_THRESHOLD_PCT:
        return "up"
    if day_return_pct < -PRICE_THRESHOLD_PCT:
        return "down"
    return "flat"


def is_divergence(surprise_direction: str, price_direction: str) -> bool:
    """サプライズ方向と株価方向の乖離を判定する。

    Parameters
    ----------
    surprise_direction : str
        "beat", "miss", or "inline"
    price_direction : str
        "up", "down", or "flat"

    Returns
    -------
    bool
        乖離している場合 True
    """
    return (surprise_direction == "beat" and price_direction == "down") or (
        surprise_direction == "miss" and price_direction == "up"
    )


def calc_earnings_reaction(
    hist: Any, earnings_row: dict[str, Any]
) -> dict[str, Any] | None:
    """単一四半期の決算前後株価反応を算出する。

    Parameters
    ----------
    hist : pd.DataFrame
        日次株価データ（タイムゾーン除去済み）
    earnings_row : dict[str, Any]
        av_earnings テーブルの1行

    Returns
    -------
    dict[str, Any] | None
        決算反応データ。算出不可の場合は None
    """
    reported_date_str = earnings_row["reported_date"]
    if not reported_date_str:
        logger.warning("reported_date is None, skipping", row=earnings_row)
        return None

    reported_date = datetime.strptime(reported_date_str, "%Y-%m-%d")
    fiscal_date_ending = earnings_row["fiscal_date_ending"]
    fiscal_quarter = derive_fiscal_quarter(fiscal_date_ending)

    # --- 前日（発表日より前の最新営業日） ---
    pre_dates = hist.index[hist.index < reported_date]
    if len(pre_dates) == 0:
        logger.warning(
            "No trading day before reported_date, skipping",
            reported_date=reported_date_str,
            fiscal_quarter=fiscal_quarter,
        )
        return None

    pre_day_close = hist["Close"].loc[pre_dates[-1]]

    # --- 翌営業日（発表日より後の最初の営業日） ---
    post_dates = hist.index[hist.index > reported_date]
    if len(post_dates) == 0:
        logger.warning(
            "No trading day after reported_date, skipping",
            reported_date=reported_date_str,
            fiscal_quarter=fiscal_quarter,
        )
        return None

    post_day_close = hist["Close"].loc[post_dates[0]]

    # --- 1日リターン ---
    day_return = round((post_day_close / pre_day_close - 1) * 100, 1) if pre_day_close != 0 else 0.0

    # --- 前5営業日→後5営業日リターン ---
    pre_day_idx = hist.index.get_loc(pre_dates[-1])
    post_day_idx = hist.index.get_loc(post_dates[0])

    # 前5営業日のClose（前日から4営業日遡った日）
    pre5_idx = max(pre_day_idx - 4, 0)
    pre5_close = hist["Close"].iloc[pre5_idx]

    # 後5営業日のClose（翌営業日から4営業日先）
    post5_idx = min(post_day_idx + 4, len(hist) - 1)
    post5_close = hist["Close"].iloc[post5_idx]

    week_return = round((post5_close / pre5_close - 1) * 100, 1) if pre5_close != 0 else 0.0

    # --- サプライズ・方向判定 ---
    surprise_pct = earnings_row.get("surprise_percentage")
    if surprise_pct is not None:
        surprise_pct = round(surprise_pct, 2)
    surprise_dir = determine_surprise_direction(surprise_pct)
    price_dir = determine_price_direction(day_return)
    divergence = is_divergence(surprise_dir, price_dir)

    result = {
        "fiscal_quarter": fiscal_quarter,
        "fiscal_date_ending": fiscal_date_ending,
        "reported_date": reported_date_str,
        "reported_eps": earnings_row.get("reported_eps"),
        "estimated_eps": earnings_row.get("estimated_eps"),
        "surprise_pct": surprise_pct,
        "surprise_direction": surprise_dir,
        "day_return_pct": day_return,
        "week_return_pct": week_return,
        "price_direction": price_dir,
        "divergence": divergence,
    }

    logger.debug(
        "Earnings reaction calculated",
        fiscal_quarter=fiscal_quarter,
        surprise_dir=surprise_dir,
        day_return=day_return,
        divergence=divergence,
    )
    return result


def build_summary(reactions: list[dict[str, Any]]) -> dict[str, Any]:
    """決算反応の集計サマリーを生成する。

    Parameters
    ----------
    reactions : list[dict[str, Any]]
        決算反応データのリスト

    Returns
    -------
    dict[str, Any]
        集計サマリー
    """
    if not reactions:
        return {
            "total_quarters": 0,
            "beats": 0,
            "misses": 0,
            "avg_day_return_pct": 0.0,
            "median_day_return_pct": 0.0,
            "up_probability_pct": 0.0,
            "divergence_count": 0,
            "divergence_quarters": [],
        }

    beats = sum(1 for r in reactions if r["surprise_direction"] == "beat")
    misses = sum(1 for r in reactions if r["surprise_direction"] == "miss")

    day_returns = [r["day_return_pct"] for r in reactions]
    avg_day_return = round(sum(day_returns) / len(day_returns), 1)

    sorted_returns = sorted(day_returns)
    n = len(sorted_returns)
    if n % 2 == 0:
        median_day_return = round(
            (sorted_returns[n // 2 - 1] + sorted_returns[n // 2]) / 2, 1
        )
    else:
        median_day_return = round(sorted_returns[n // 2], 1)

    up_count = sum(1 for r in reactions if r["price_direction"] == "up")
    up_probability = round(up_count / len(reactions) * 100, 1)

    divergence_quarters = [
        r["fiscal_quarter"] for r in reactions if r["divergence"]
    ]

    return {
        "total_quarters": len(reactions),
        "beats": beats,
        "misses": misses,
        "avg_day_return_pct": avg_day_return,
        "median_day_return_pct": median_day_return,
        "up_probability_pct": up_probability,
        "divergence_count": len(divergence_quarters),
        "divergence_quarters": divergence_quarters,
    }


def analyze_earnings_reaction(
    symbol: str, quarters: int
) -> dict[str, Any]:
    """決算前後株価反応の分析を実行する。

    Parameters
    ----------
    symbol : str
        ティッカーシンボル（例: "BLK"）
    quarters : int
        分析する四半期数

    Returns
    -------
    dict[str, Any]
        分析結果の構造化データ
    """
    logger.info("Starting earnings reaction analysis", symbol=symbol, quarters=quarters)

    # Step 1: 株価取得
    hist = fetch_stock_history(symbol)
    current_price = round(float(hist["Close"].iloc[-1]), 2)

    # Step 2: 決算データ取得
    earnings_data = fetch_earnings_data(symbol, quarters)

    # Step 3: 各四半期の決算反応算出
    reactions: list[dict[str, Any]] = []
    for row in earnings_data:
        reaction = calc_earnings_reaction(hist, row)
        if reaction is not None:
            reactions.append(reaction)
        else:
            logger.warning(
                "Skipped quarter due to insufficient data",
                fiscal_date_ending=row.get("fiscal_date_ending"),
                reported_date=row.get("reported_date"),
            )

    # Step 4: リターン一覧算出
    returns = calc_returns_summary(hist)

    # Step 5: サマリー生成
    summary = build_summary(reactions)

    result = {
        "symbol": symbol.upper(),
        "as_of_date": datetime.now().strftime("%Y-%m-%d"),
        "current_price": current_price,
        "returns": returns,
        "earnings_reactions": reactions,
        "summary": summary,
        "fetched_at": datetime.now().isoformat(),
    }

    logger.info(
        "Analysis completed",
        symbol=symbol,
        total_reactions=len(reactions),
        divergence_count=summary["divergence_count"],
    )
    return result


def main() -> None:
    """CLI エントリーポイント。"""
    parser = argparse.ArgumentParser(
        description="決算前後の株価反応を分析し、構造化JSONを出力する",
    )
    parser.add_argument(
        "--symbol",
        required=True,
        help="ティッカーシンボル（例: BLK, AAPL）",
    )
    parser.add_argument(
        "--quarters",
        type=int,
        default=8,
        help="分析する四半期数（デフォルト: 8）",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="出力先JSONファイルパス（省略時は stdout に出力）",
    )
    args = parser.parse_args()

    result = analyze_earnings_reaction(args.symbol, args.quarters)

    json_output = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_output, encoding="utf-8")
        logger.info("Output written", path=str(output_path))
        print(f"Output written to: {output_path}")
    else:
        print(json_output)


if __name__ == "__main__":
    main()
