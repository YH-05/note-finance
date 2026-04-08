#!/usr/bin/env python3
"""Collect US Macro Weekly Article Data.

米国マクロ経済 weekly シリーズ記事用のデータを収集する。
以下の3つのコレクターを統合:

1. CFTC COT コレクター  — Fed Funds 先物の建玉（CFTC 公式 ZIP → CSV パース）
2. Fed Funds 先物コレクター — 市場が織り込む FF 金利パス（yfinance ZQK26=F 等）
3. FRED カレンダーコレクター — 翌週の経済指標発表スケジュール（FRED API）

Examples
--------
基本的な使い方（カレントディレクトリに data/ を作成）:

    $ uv run python scripts/collect_us_macro_data.py

記事フォルダを指定:

    $ uv run python scripts/collect_us_macro_data.py \\
        --output articles/macro_economy/2026-04-13_us-macro-weekly-vol01/data

特定のコレクターのみ実行:

    $ uv run python scripts/collect_us_macro_data.py --only cot
    $ uv run python scripts/collect_us_macro_data.py --only fed_futures
    $ uv run python scripts/collect_us_macro_data.py --only fred_calendar

出力ファイル:
- cot_fed_funds.json   : CFTC COT 建玉データ（直近52週）
- fed_futures.json     : FF 金利の市場織込みパス（近月〜8ヶ月先）
- fred_calendar.json   : 翌週の経済指標発表カレンダー

Notes
-----
- FRED_API_KEY 環境変数（.env）が必要（#5 FRED カレンダーのみ）
- yfinance は dev 依存: uv run --extra dev python ... または uv run python ...
  （pyproject.toml に dev extra が含まれる環境で実行のこと）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import csv
import io
import zipfile

import requests

# ---------------------------------------------------------------------------
# Logger セットアップ（structlog を直接使用）
# ---------------------------------------------------------------------------
import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

# CFTC 公式 ZIP ダウンロード URL (Traders in Financial Futures, TXT 版)
# XLS 版 (fut_fin_xls_YYYY.zip) は .xls バイナリで xlrd が必要なので TXT 版を使用
_CFTC_ZIP_URL_TEMPLATE = (
    "https://www.cftc.gov/sites/default/files/files/dea/history/fut_fin_txt_{year}.zip"
)
_CFTC_FF_MARKET = "FED FUNDS"   # TXT ファイルでの実際の表記

# FRED API
_FRED_RELEASE_DATES_URL = "https://api.stlouisfed.org/fred/release/dates"  # 単数形

# 主要リリース（ID固定）
# ID は /fred/releases API で確認済み（2026-04-08 時点）
_MAJOR_RELEASES: dict[int, dict[str, str]] = {
    10:  {"name": "Consumer Price Index",                           "freq": "monthly"},
    46:  {"name": "Producer Price Index",                           "freq": "monthly"},
    50:  {"name": "Employment Situation",                           "freq": "monthly"},   # NFP
    54:  {"name": "Personal Income and Outlays",                    "freq": "monthly"},   # PCE
    53:  {"name": "Gross Domestic Product",                         "freq": "quarterly"},
    9:   {"name": "Advance Monthly Sales for Retail",               "freq": "monthly"},
    13:  {"name": "Industrial Production and Capacity Utilization", "freq": "monthly"},
    27:  {"name": "New Residential Construction",                   "freq": "monthly"},
    180: {"name": "Unemployment Insurance Weekly Claims",           "freq": "weekly"},
    101: {"name": "FOMC Press Release",                             "freq": "varies"},
    91:  {"name": "Surveys of Consumers (Univ. of Michigan)",      "freq": "monthly"},
    # CB Consumer Confidence は FRED 非掲載（有償データ）のため除外
}

# CME 30日物 Fed Funds 先物 月コード
# F=Jan, G=Feb, H=Mar, J=Apr, K=May, M=Jun, N=Jul, Q=Aug, U=Sep, V=Oct, X=Nov, Z=Dec
_MONTH_CODES: dict[int, str] = {
    1: "F", 2: "G", 3: "H", 4: "J", 5: "K", 6: "M",
    7: "N", 8: "Q", 9: "U", 10: "V", 11: "X", 12: "Z",
}


def _gen_zq_symbols(n: int = 9) -> list[str]:
    """今月〜n ヶ月先の ZQ 先物シンボルを生成する。

    Parameters
    ----------
    n : int
        生成するシンボル数（デフォルト9）

    Returns
    -------
    list[str]
        例: ["ZQJ26=F", "ZQK26=F", "ZQM26=F", ...]
    """
    today = date.today()
    symbols: list[str] = []
    for i in range(n):
        total_months = today.month - 1 + i
        month = total_months % 12 + 1
        year = today.year + total_months // 12
        code = _MONTH_CODES[month]
        symbols.append(f"ZQ{code}{str(year)[2:]}=F")
    return symbols


# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------

def _load_env() -> None:
    """プロジェクトルートの .env を読み込む。"""
    env_path = Path(__file__).parents[1] / ".env"
    if not env_path.exists():
        return
    with env_path.open() as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key not in os.environ:  # 既に設定されている場合は上書きしない
                os.environ[key] = val


def _save_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info("saved", path=str(path))


# ---------------------------------------------------------------------------
# #3 CFTC COT コレクター
# ---------------------------------------------------------------------------

# TFF CSV の列名（CFTC 公式 ZIP に含まれる FinFutTxt_YYYY.txt のヘッダー）
_COT_KEY_COLS = [
    "Market_and_Exchange_Names",
    "As_of_Date_In_Form_YYMMDD",
    "Open_Interest_All",
    "Dealer_Positions_Long_All",  "Dealer_Positions_Short_All",
    "Asset_Mgr_Positions_Long_All", "Asset_Mgr_Positions_Short_All",
    "Lev_Money_Positions_Long_All", "Lev_Money_Positions_Short_All",
    "Other_Rept_Positions_Long_All", "Other_Rept_Positions_Short_All",
    "NonRept_Positions_Long_All",   "NonRept_Positions_Short_All",
    "Change_in_Open_Interest_All",
    "Change_in_Dealer_Long_All",  "Change_in_Dealer_Short_All",
    "Change_in_Asset_Mgr_Long_All", "Change_in_Asset_Mgr_Short_All",
    "Change_in_Lev_Money_Long_All", "Change_in_Lev_Money_Short_All",
]


def collect_cot(output_dir: Path, weeks: int = 52) -> dict[str, Any]:
    """CFTC 公式 ZIP から Traders in Financial Futures (TFF) の Fed Funds 建玉を取得する。

    CFTC の Socrata API の代わりに公式配布 ZIP を直接ダウンロードしてパースする。
    URL 形式: https://www.cftc.gov/sites/default/files/files/dea/history/fut_fin_xls_{year}.zip

    Parameters
    ----------
    output_dir : Path
        出力ディレクトリ
    weeks : int
        直近何週分を保持するか（デフォルト52週 = 1年）

    Returns
    -------
    dict
        取得結果サマリー
    """
    current_year = date.today().year
    url = _CFTC_ZIP_URL_TEMPLATE.format(year=current_year)
    logger.info("collect_cot: start", url=url, market=_CFTC_FF_MARKET)

    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error("collect_cot: download failed", url=url, error=str(e))
        raise

    # ZIP を展開して TXT（タブ区切り CSV）を読む
    records: list[dict[str, Any]] = []
    try:
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            # ZIP 内の .txt ファイルを探す（例: FinFutTxt_2026.txt）
            txt_names = [n for n in zf.namelist() if n.endswith(".txt")]
            if not txt_names:
                raise ValueError(f"ZIP に .txt ファイルが見つかりません: {zf.namelist()}")
            txt_name = txt_names[0]
            logger.debug("collect_cot: reading", file=txt_name)

            with zf.open(txt_name) as f:
                content = f.read().decode("latin-1")  # CFTC ファイルは latin-1

            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                market = row.get("Market_and_Exchange_Names", "")
                if _CFTC_FF_MARKET.upper() not in market.upper():
                    continue
                # 必要列のみ抽出
                trimmed = {
                    col: row.get(col, "").strip()
                    for col in _COT_KEY_COLS
                    if col in row
                }
                records.append(trimmed)

    except (zipfile.BadZipFile, KeyError, ValueError, UnicodeDecodeError) as e:
        logger.error("collect_cot: parse failed", error=str(e))
        raise

    # 日付降順でソートして直近 weeks 件に絞る
    records.sort(key=lambda r: r.get("As_of_Date_In_Form_YYMMDD", ""), reverse=True)
    records = records[:weeks]

    if not records:
        logger.warning("collect_cot: no records for market", market=_CFTC_FF_MARKET)

    result: dict[str, Any] = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": f"CFTC TFF CSV ({txt_name if records else 'unknown'})",
        "download_url": url,
        "market_filter": _CFTC_FF_MARKET,
        "record_count": len(records),
        "latest_report_date": records[0].get("As_of_Date_In_Form_YYMMDD") if records else None,
        "records": records,
    }

    _save_json(result, output_dir / "cot_fed_funds.json")
    logger.info("collect_cot: done", records=len(records))
    return result


# ---------------------------------------------------------------------------
# #4 Fed Funds 先物コレクター
# ---------------------------------------------------------------------------

def collect_fed_futures(output_dir: Path) -> dict[str, Any]:
    """yfinance から CME ZQ 先物で FF 金利の市場織込みを取得する。

    30日物 Fed Funds 先物の価格 P から:
        implied_rate = 100 - P

    Notes
    -----
    Yahoo Finance が提供するのは最前月（ZQ=F）のみ。
    月別シンボル（ZQK26=F 等）は Yahoo Finance では提供されていない。
    複数限月のパスが必要な場合は CME DataMine 等の有償データを検討すること。

    Parameters
    ----------
    output_dir : Path
        出力ディレクトリ

    Returns
    -------
    dict
        取得結果サマリー
    """
    # ZQ=F（最前月）を主として、月別シンボルも試みる（将来的な追加対応の余地）
    symbols = ["ZQ=F"] + _gen_zq_symbols(9)
    logger.info("collect_fed_futures: start", symbols=symbols)

    try:
        import yfinance as yf
    except ImportError:
        logger.error("collect_fed_futures: yfinance not installed. Run with --extra dev")
        raise

    contracts: list[dict[str, Any]] = []
    failed: list[str] = []

    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info

            last_price = getattr(info, "last_price", None)
            if last_price is None or last_price == 0:
                logger.debug("collect_fed_futures: no price", symbol=symbol)
                failed.append(symbol)
                continue

            implied_rate = round(100.0 - float(last_price), 4)

            contracts.append({
                "symbol": symbol,
                "last_price": round(float(last_price), 4),
                "implied_ff_rate_pct": implied_rate,
                # 利用可能であれば追加情報
                "currency": getattr(info, "currency", None),
                "exchange": getattr(info, "exchange", None),
            })
            logger.debug("collect_fed_futures: fetched", symbol=symbol, implied_rate=implied_rate)

        except Exception as e:
            logger.warning("collect_fed_futures: symbol failed", symbol=symbol, error=str(e))
            failed.append(symbol)

    result: dict[str, Any] = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "yfinance (CME 30-Day Federal Funds Futures, ZQ monthly symbols)",
        "description": (
            "implied_ff_rate_pct = 100 - futures_price. "
            "Represents market-implied FF rate at contract expiry."
        ),
        "symbols_tried": symbols,
        "contract_count": len(contracts),
        "failed_symbols": failed,
        "contracts": contracts,
    }

    _save_json(result, output_dir / "fed_futures.json")
    logger.info("collect_fed_futures: done", contracts=len(contracts), failed=len(failed))
    return result


# ---------------------------------------------------------------------------
# #5 FRED releases/dates コレクター
# ---------------------------------------------------------------------------

def _estimate_next_date(past_dates: list[str], freq: str) -> str | None:
    """過去の発表日パターンから「今日以降の最初の」推定発表日を返す。

    Parameters
    ----------
    past_dates : list[str]
        YYYY-MM-DD 形式の発表日リスト
    freq : str
        "weekly" | "monthly" | "quarterly" | "varies"

    Returns
    -------
    str | None
        今日以降の推定次回発表日（YYYY-MM-DD）
    """
    if not past_dates:
        return None

    try:
        latest = date.fromisoformat(max(past_dates))
    except ValueError:
        return None

    if freq == "weekly":
        delta = timedelta(weeks=1)
    elif freq == "monthly":
        delta = timedelta(days=30)
    elif freq == "quarterly":
        delta = timedelta(days=91)
    else:
        return None  # varies（FOMC等）はパターン推定不可

    # 今日以降になるまでステップを進める
    today = date.today()
    next_d = latest
    while next_d < today:
        next_d += delta

    return next_d.isoformat()


def collect_fred_calendar(
    output_dir: Path,
    api_key: str,
    days_ahead: int = 14,
) -> dict[str, Any]:
    """主要経済指標の発表日履歴を取得し、翌週の発表予定を推定する。

    Notes
    -----
    FRED の /release/dates API は将来の発表予定日を事前登録しない。
    そのため過去3ヶ月の実績日から発表頻度（月次/週次等）を使い次回日を推定する。
    FOMC 日程など「varies」頻度のリリースはパターン推定を行わない。

    Parameters
    ----------
    output_dir : Path
        出力ディレクトリ
    api_key : str
        FRED API キー
    days_ahead : int
        参考情報として何日先までの推定日を含めるか（デフォルト14日）

    Returns
    -------
    dict
        取得結果サマリー
    """
    today = date.today()
    today_str = today.isoformat()
    horizon_str = (today + timedelta(days=days_ahead)).isoformat()

    logger.info(
        "collect_fred_calendar: start",
        releases=len(_MAJOR_RELEASES),
        horizon=horizon_str,
    )

    entries: list[dict[str, Any]] = []
    errors: list[str] = []

    for release_id, meta in _MAJOR_RELEASES.items():
        name = meta["name"]
        freq = meta["freq"]
        try:
            resp = requests.get(
                _FRED_RELEASE_DATES_URL,
                params={
                    "release_id": release_id,
                    "api_key": api_key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "include_release_dates_with_no_data": "false",
                    "limit": 20,   # 直近20回分
                },
                timeout=20,
            )
            resp.raise_for_status()
            dates_raw: list[dict[str, Any]] = resp.json().get("release_dates", [])
        except requests.RequestException as e:
            logger.warning("collect_fred_calendar: release fetch failed",
                           release_id=release_id, name=name, error=str(e))
            errors.append(f"{name}: {e}")
            continue

        past_dates = [d["date"] for d in dates_raw if d["date"] <= today_str]
        latest_date = past_dates[0] if past_dates else None

        estimated_next = _estimate_next_date(past_dates, freq)
        in_window = (
            estimated_next is not None
            and today_str <= estimated_next <= horizon_str
        )

        entries.append({
            "release_id": release_id,
            "release_name": name,
            "frequency": freq,
            "latest_past_date": latest_date,
            "estimated_next_date": estimated_next,
            "estimated_next_in_window": in_window,
            "window": {"start": today_str, "end": horizon_str},
        })

        logger.debug(
            "collect_fred_calendar: fetched",
            name=name,
            latest=latest_date,
            estimated_next=estimated_next,
            in_window=in_window,
        )

    in_window_count = sum(1 for e in entries if e["estimated_next_in_window"])

    result: dict[str, Any] = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "FRED /release/dates API (estimated schedule from past dates)",
        "note": (
            "FRED does not pre-register future release dates. "
            "estimated_next_date is approximated from historical patterns."
        ),
        "window": {"start": today_str, "end": horizon_str},
        "release_count": len(entries),
        "in_window_count": in_window_count,
        "fetch_errors": errors,
        "releases": entries,
    }

    _save_json(result, output_dir / "fred_calendar.json")
    logger.info(
        "collect_fred_calendar: done",
        releases=len(entries),
        in_window=in_window_count,
    )
    return result


# ---------------------------------------------------------------------------
# CLI エントリポイント
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="米国マクロ weekly 記事用データを収集する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--output",
        default="data/us_macro",
        help="出力ディレクトリ (default: data/us_macro)",
    )
    parser.add_argument(
        "--only",
        choices=["cot", "fed_futures", "fred_calendar"],
        help="特定のコレクターのみ実行",
    )
    parser.add_argument(
        "--weeks",
        type=int,
        default=52,
        help="COT 取得週数 (default: 52)",
    )
    parser.add_argument(
        "--days-ahead",
        type=int,
        default=14,
        help="FRED カレンダー取得日数 (default: 14)",
    )
    args = parser.parse_args()

    _load_env()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    run_all = args.only is None
    errors: list[str] = []

    # --- #3 CFTC COT ---
    if run_all or args.only == "cot":
        try:
            collect_cot(output_dir, weeks=args.weeks)
        except Exception as e:
            logger.error("COT コレクター失敗", error=str(e))
            errors.append(f"cot: {e}")

    # --- #4 Fed Funds 先物 ---
    if run_all or args.only == "fed_futures":
        try:
            collect_fed_futures(output_dir)
        except Exception as e:
            logger.error("Fed Funds 先物コレクター失敗", error=str(e))
            errors.append(f"fed_futures: {e}")

    # --- #5 FRED カレンダー ---
    if run_all or args.only == "fred_calendar":
        api_key = os.environ.get("FRED_API_KEY", "")
        if not api_key:
            msg = "FRED_API_KEY が設定されていません。.env を確認してください。"
            logger.error(msg)
            errors.append(f"fred_calendar: {msg}")
        else:
            try:
                collect_fred_calendar(output_dir, api_key=api_key, days_ahead=args.days_ahead)
            except Exception as e:
                logger.error("FRED カレンダーコレクター失敗", error=str(e))
                errors.append(f"fred_calendar: {e}")

    if errors:
        print(f"\n⚠ {len(errors)} 件のエラーが発生しました:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(f"\n✓ 完了。出力先: {output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
