"""Google Spreadsheet をCLIから読み込むスクリプト。

Usage:
    # スプレッドシート全体（最初のシート）
    uv run python scripts/read_gsheet.py <spreadsheet_url_or_key>

    # シート名を指定
    uv run python scripts/read_gsheet.py <spreadsheet_url_or_key> --sheet "Sheet2"

    # CSV形式で出力
    uv run python scripts/read_gsheet.py <spreadsheet_url_or_key> --format csv

    # JSON形式で出力
    uv run python scripts/read_gsheet.py <spreadsheet_url_or_key> --format json

    # ファイルに保存
    uv run python scripts/read_gsheet.py <spreadsheet_url_or_key> --output data.csv

事前準備:
    1. Google Cloud Console でサービスアカウントを作成
    2. Google Sheets API と Google Drive API を有効化
    3. JSON鍵を ~/.config/gspread/service_account.json に配置
    4. スプレッドシートをサービスアカウントのメールに共有
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path

import gspread
import structlog

logger = structlog.get_logger(__name__)

CREDENTIALS_PATH = Path.home() / ".config" / "gspread" / "service_account.json"


def extract_spreadsheet_key(url_or_key: str) -> str:
    """URLまたはスプレッドシートキーからキーを抽出する。

    Parameters
    ----------
    url_or_key : str
        スプレッドシートのURLまたはキー

    Returns
    -------
    str
        スプレッドシートキー
    """
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url_or_key)
    if match:
        return match.group(1)
    return url_or_key


def get_client() -> gspread.Client:
    """gspread クライアントを取得する。"""
    if not CREDENTIALS_PATH.exists():
        logger.error(
            "credentials_not_found",
            path=str(CREDENTIALS_PATH),
            hint="サービスアカウントのJSON鍵を配置してください",
        )
        msg = (
            f"認証ファイルが見つかりません: {CREDENTIALS_PATH}\n"
            "手順:\n"
            "  1. Google Cloud Console でサービスアカウントを作成\n"
            "  2. JSON鍵をダウンロード\n"
            "  3. ~/.config/gspread/service_account.json に配置"
        )
        raise FileNotFoundError(msg)

    return gspread.service_account(filename=str(CREDENTIALS_PATH))


def read_spreadsheet(
    url_or_key: str,
    sheet_name: str | None = None,
) -> list[dict[str, str]]:
    """スプレッドシートを読み込んでレコードのリストを返す。

    Parameters
    ----------
    url_or_key : str
        スプレッドシートのURLまたはキー
    sheet_name : str | None
        シート名（Noneなら最初のシート）

    Returns
    -------
    list[dict[str, str]]
        行データのリスト（ヘッダーをキーとした辞書）
    """
    client = get_client()
    key = extract_spreadsheet_key(url_or_key)

    logger.info("opening_spreadsheet", key=key)
    spreadsheet = client.open_by_key(key)

    if sheet_name:
        logger.info("selecting_sheet", name=sheet_name)
        worksheet = spreadsheet.worksheet(sheet_name)
    else:
        worksheet = spreadsheet.sheet1
        logger.info("using_first_sheet", title=worksheet.title)

    records = worksheet.get_all_records()
    logger.info("read_complete", rows=len(records))
    return records


def format_as_csv(records: list[dict[str, str]]) -> str:
    """レコードをCSV文字列に変換する。"""
    if not records:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=records[0].keys())
    writer.writeheader()
    writer.writerows(records)
    return output.getvalue()


def format_as_json(records: list[dict[str, str]]) -> str:
    """レコードをJSON文字列に変換する。"""
    return json.dumps(records, ensure_ascii=False, indent=2)


def format_as_table(records: list[dict[str, str]]) -> str:
    """レコードをテーブル形式の文字列に変換する。"""
    if not records:
        return "(empty)"
    headers = list(records[0].keys())
    col_widths = {h: len(str(h)) for h in headers}
    for row in records:
        for h in headers:
            col_widths[h] = max(col_widths[h], len(str(row.get(h, ""))))

    header_line = " | ".join(str(h).ljust(col_widths[h]) for h in headers)
    separator = "-+-".join("-" * col_widths[h] for h in headers)
    rows = []
    for row in records:
        rows.append(
            " | ".join(str(row.get(h, "")).ljust(col_widths[h]) for h in headers)
        )

    return "\n".join([header_line, separator, *rows])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Google Spreadsheetを読み込む",
    )
    parser.add_argument(
        "spreadsheet",
        help="スプレッドシートのURLまたはキー",
    )
    parser.add_argument(
        "--sheet",
        default=None,
        help="シート名（デフォルト: 最初のシート）",
    )
    parser.add_argument(
        "--format",
        choices=["table", "csv", "json"],
        default="table",
        help="出力形式（デフォルト: table）",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="出力ファイルパス（デフォルト: stdout）",
    )
    args = parser.parse_args()

    try:
        records = read_spreadsheet(args.spreadsheet, args.sheet)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except gspread.exceptions.SpreadsheetNotFound:
        print(
            "スプレッドシートが見つかりません。"
            "URLを確認し、サービスアカウントに共有してください。",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.format == "csv":
        output = format_as_csv(records)
    elif args.format == "json":
        output = format_as_json(records)
    else:
        output = format_as_table(records)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        logger.info("saved_to_file", path=args.output, rows=len(records))
    else:
        print(output)


if __name__ == "__main__":
    main()
