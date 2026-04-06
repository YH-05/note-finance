#!/usr/bin/env python3
"""SEC EDGAR 8-K プレスリリース取得ヘルパースクリプト.

決算プレビュー記事執筆のために、過去N四半期の決算発表時8-K（EX-99.1プレスリリース）
からキー情報を抽出し、構造化JSONとして出力する。

Processing Flow
---------------
1. ticker → CIK 変換（SEC EDGAR company tickers JSON）
2. submissions API で 8-K の accession_number を特定
3. filing ディレクトリから EX-99.1 URL を特定
4. EX-99.1 HTML を取得し、プレーンテキストに変換
5. ハイライト抽出 → 構造化 JSON 出力

Examples
--------
単一銘柄の直近8四半期:

    $ uv run python scripts/fetch_earnings_8k.py --symbol BLK --quarters 8

出力先指定:

    $ uv run python scripts/fetch_earnings_8k.py --symbol BLK --quarters 8 --output .tmp/blk_8k.json

Notes
-----
- SEC EDGAR REST API を直接使用（MCP ツール不使用）
- レートリミット: 10 requests/sec 以下（0.2秒インターバル）
- User-Agent 必須（SEC EDGAR ポリシー準拠）
- EX-99.1 が存在しない 8-K はスキップ（決算以外の 8-K を除外）
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import httpx

from utils_core.logging.config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SEC_USER_AGENT = "note-finance research@example.com"
"""SEC EDGAR ポリシー準拠の User-Agent."""

SEC_BASE_URL = "https://data.sec.gov"
SEC_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data"

RATE_LIMIT_INTERVAL = 0.2
"""SEC EDGAR レートリミット: 最低 0.2 秒/リクエスト（10 req/sec 以下）."""

EX99_PATTERN = re.compile(r'ex99[_\-]?1.*\.htm', re.IGNORECASE)
"""EX-99.1 ファイル名の正規表現パターン."""

HIGHLIGHTS_START_PATTERN = re.compile(r'Reports?\b', re.IGNORECASE)
"""ハイライト抽出の開始パターン（"Reports" を含む行）."""

HIGHLIGHTS_MAX_CHARS = 5000
"""ハイライトの最大文字数."""

TICKER_LOOKUP_URL = "https://www.sec.gov/files/company_tickers.json"
"""SEC EDGAR の ticker → CIK マッピング JSON."""

EARNINGS_KEYWORDS = re.compile(
    r"(diluted\s+eps|financial\s+results|results\s+of\s+operations|"
    r"quarterly\s+earnings|net\s+income|revenue.*quarter)",
    re.IGNORECASE,
)
"""決算プレスリリースかどうかを判定するキーワードパターン."""


# ---------------------------------------------------------------------------
# HTML → Plain Text Converter
# ---------------------------------------------------------------------------


class _HTMLToTextParser(HTMLParser):
    """HTML からプレーンテキストを抽出するパーサー.

    style/script タグの内容はスキップする。
    """

    def __init__(self) -> None:
        super().__init__()
        self._text_parts: list[str] = []
        self._skip_depth: int = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in ("style", "script"):
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in ("style", "script") and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._text_parts.append(data)

    def get_text(self) -> str:
        """抽出したテキストを返す.

        Returns
        -------
        str
            連続空白・改行を正規化したプレーンテキスト。
        """
        raw = " ".join(self._text_parts)
        # 改行正規化: 連続改行 → 2改行、連続空白 → 1空白
        text = re.sub(r'\n{3,}', '\n\n', raw)
        text = re.sub(r'[ \t]{2,}', ' ', text)
        return text.strip()


def html_to_text(html: str) -> str:
    """HTML をプレーンテキストに変換する.

    Parameters
    ----------
    html : str
        HTML 文字列。

    Returns
    -------
    str
        プレーンテキスト（style/script 除去、空白正規化済み）。
    """
    parser = _HTMLToTextParser()
    parser.feed(html)
    return parser.get_text()


# ---------------------------------------------------------------------------
# SEC EDGAR API Client
# ---------------------------------------------------------------------------


class EdgarClient:
    """SEC EDGAR REST API クライアント.

    Parameters
    ----------
    user_agent : str
        SEC EDGAR ポリシー準拠の User-Agent 文字列。
    rate_limit : float
        リクエスト間の最低インターバル（秒）。
    """

    def __init__(
        self,
        user_agent: str = SEC_USER_AGENT,
        rate_limit: float = RATE_LIMIT_INTERVAL,
    ) -> None:
        self._client = httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=30.0,
            follow_redirects=True,
        )
        self._rate_limit = rate_limit
        self._last_request_time: float = 0.0

    def _throttle(self) -> None:
        """レートリミットを遵守するために必要に応じてスリープする."""
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self._rate_limit:
            time.sleep(self._rate_limit - elapsed)

    def get(self, url: str) -> httpx.Response:
        """レートリミット付き GET リクエスト.

        Parameters
        ----------
        url : str
            リクエスト先 URL。

        Returns
        -------
        httpx.Response
            HTTP レスポンス。

        Raises
        ------
        httpx.HTTPStatusError
            4xx/5xx レスポンス時。
        """
        self._throttle()
        logger.debug("GET %s", url)
        response = self._client.get(url)
        self._last_request_time = time.monotonic()
        response.raise_for_status()
        return response

    def close(self) -> None:
        """HTTP クライアントを閉じる."""
        self._client.close()

    def __enter__(self) -> EdgarClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Core Functions
# ---------------------------------------------------------------------------


def resolve_cik(client: EdgarClient, symbol: str) -> str:
    """ticker シンボルから CIK を解決する.

    Parameters
    ----------
    client : EdgarClient
        EDGAR API クライアント。
    symbol : str
        ティッカーシンボル（例: "BLK"）。

    Returns
    -------
    str
        CIK 文字列（ゼロパディングなし、例: "2012383"）。

    Raises
    ------
    ValueError
        ticker が見つからない場合。
    """
    logger.info("Resolving CIK for ticker: %s", symbol)
    response = client.get(TICKER_LOOKUP_URL)
    tickers_data: dict[str, dict[str, Any]] = response.json()

    symbol_upper = symbol.upper()
    for entry in tickers_data.values():
        if entry.get("ticker", "").upper() == symbol_upper:
            cik = str(entry["cik_str"])
            logger.info("Resolved %s → CIK %s", symbol, cik)
            return cik

    msg = f"Ticker '{symbol}' not found in SEC EDGAR company tickers"
    raise ValueError(msg)


def fetch_8k_filings(
    client: EdgarClient,
    cik: str,
    max_filings: int = 50,
) -> list[dict[str, str]]:
    """CIK から 8-K filing の一覧を取得する.

    Parameters
    ----------
    client : EdgarClient
        EDGAR API クライアント。
    cik : str
        CIK 文字列（ゼロパディングなし）。
    max_filings : int
        取得する最大 filing 数。

    Returns
    -------
    list[dict[str, str]]
        8-K filing のリスト（filingDate 降順）。
        各要素: {"accessionNumber", "filingDate", "primaryDocument"}
    """
    cik_padded = cik.zfill(10)
    url = f"{SEC_BASE_URL}/submissions/CIK{cik_padded}.json"
    logger.info("Fetching submissions for CIK %s", cik_padded)

    response = client.get(url)
    data = response.json()

    filings_data = data.get("filings", {})

    # recent + older filing files を統合
    all_forms: list[str] = []
    all_accessions: list[str] = []
    all_dates: list[str] = []
    all_primary_docs: list[str] = []

    for source in _iter_filing_sources(client, cik_padded, filings_data):
        all_forms.extend(source.get("form", []))
        all_accessions.extend(source.get("accessionNumber", []))
        all_dates.extend(source.get("filingDate", []))
        all_primary_docs.extend(source.get("primaryDocument", []))

    filings: list[dict[str, str]] = []
    for i, form in enumerate(all_forms):
        if form == "8-K" and i < len(all_accessions):
            filings.append({
                "accessionNumber": all_accessions[i],
                "filingDate": all_dates[i],
                "primaryDocument": all_primary_docs[i] if i < len(all_primary_docs) else "",
            })
            if len(filings) >= max_filings:
                break

    # filingDate 降順でソート
    filings.sort(key=lambda x: x["filingDate"], reverse=True)
    logger.info("Found %d 8-K filings", len(filings))
    return filings


def _iter_filing_sources(
    client: EdgarClient,
    cik_padded: str,
    filings_data: dict[str, Any],
) -> list[dict[str, list[str]]]:
    """recent + older filing files からフィリングデータソースを収集する.

    Parameters
    ----------
    client : EdgarClient
        EDGAR API クライアント。
    cik_padded : str
        10桁ゼロパディング済み CIK。
    filings_data : dict
        submissions API の "filings" セクション。

    Returns
    -------
    list[dict[str, list[str]]]
        各ソースのフィリングデータ。
    """
    sources: list[dict[str, list[str]]] = []

    # recent
    recent = filings_data.get("recent", {})
    if recent:
        sources.append(recent)

    # older filing files
    for file_info in filings_data.get("files", []):
        filename = file_info.get("name", "")
        if not filename:
            continue
        url = f"{SEC_BASE_URL}/submissions/{filename}"
        try:
            response = client.get(url)
            older_data = response.json()
            sources.append(older_data)
            logger.debug("Loaded older filings from %s", filename)
        except (httpx.HTTPStatusError, json.JSONDecodeError) as e:
            logger.warning("Failed to load older filings from %s: %s", filename, e)

    return sources


def find_ex99_url(
    client: EdgarClient,
    cik: str,
    accession_number: str,
) -> str | None:
    """filing ディレクトリから EX-99.1 の URL を特定する.

    Parameters
    ----------
    client : EdgarClient
        EDGAR API クライアント。
    cik : str
        CIK 文字列（ゼロパディングなし）。
    accession_number : str
        accession number（例: "0001193125-26-013503"）。

    Returns
    -------
    str | None
        EX-99.1 の完全 URL。見つからない場合は None。
    """
    accession_nodash = accession_number.replace("-", "")
    index_url = f"{SEC_ARCHIVES_URL}/{cik}/{accession_nodash}/"

    logger.debug("Searching EX-99.1 in %s", index_url)

    try:
        response = client.get(index_url)
    except httpx.HTTPStatusError as e:
        logger.warning(
            "Failed to fetch filing directory: %s (status=%d)",
            index_url,
            e.response.status_code,
        )
        return None

    # HTML 内の href からEX-99.1 ファイルを探す
    html_content = response.text
    # href="..." の中からマッチ
    href_pattern = re.compile(r'href="([^"]*)"', re.IGNORECASE)
    for match in href_pattern.finditer(html_content):
        href = match.group(1)
        filename = href.split("/")[-1] if "/" in href else href
        if EX99_PATTERN.search(filename):
            # 絶対 URL を構築
            if href.startswith("http"):
                ex99_url = href
            else:
                ex99_url = f"{SEC_ARCHIVES_URL}/{cik}/{accession_nodash}/{filename}"
            logger.debug("Found EX-99.1: %s", ex99_url)
            return ex99_url

    logger.debug("No EX-99.1 found for accession %s", accession_number)
    return None


def fetch_ex99_text(client: EdgarClient, ex99_url: str) -> str:
    """EX-99.1 HTML を取得してプレーンテキストに変換する.

    Parameters
    ----------
    client : EdgarClient
        EDGAR API クライアント。
    ex99_url : str
        EX-99.1 の完全 URL。

    Returns
    -------
    str
        プレーンテキスト化された内容。
    """
    logger.debug("Fetching EX-99.1: %s", ex99_url)
    response = client.get(ex99_url)
    return html_to_text(response.text)


def extract_highlights(full_text: str) -> str:
    """プレーンテキストからハイライト部分を抽出する.

    "Reports" を含む行から先頭 5000 文字を抽出する。
    パターンが見つからない場合は先頭 5000 文字を返す。

    Parameters
    ----------
    full_text : str
        EX-99.1 のプレーンテキスト。

    Returns
    -------
    str
        ハイライトテキスト（最大 5000 文字）。
    """
    match = HIGHLIGHTS_START_PATTERN.search(full_text)
    if match:
        start_pos = match.start()
        return full_text[start_pos : start_pos + HIGHLIGHTS_MAX_CHARS]
    # フォールバック: 先頭 5000 文字
    logger.debug("'Reports' pattern not found, falling back to first %d chars", HIGHLIGHTS_MAX_CHARS)
    return full_text[:HIGHLIGHTS_MAX_CHARS]


def derive_fiscal_quarter(filing_date: str) -> str:
    """filing_date から推定される fiscal quarter を返す.

    Parameters
    ----------
    filing_date : str
        filing 日付（YYYY-MM-DD 形式）。

    Returns
    -------
    str
        推定 fiscal quarter（例: "2025-Q4"）。

    Notes
    -----
    8-K の filing_date は決算発表日に近い。
    発表月からおよそ1四半期前の fiscal quarter を推定する。

    - 1月〜3月 filing → 前年 Q4
    - 4月〜6月 filing → 当年 Q1
    - 7月〜9月 filing → 当年 Q2
    - 10月〜12月 filing → 当年 Q3
    """
    dt = datetime.strptime(filing_date, "%Y-%m-%d")
    month = dt.month
    year = dt.year

    if month <= 3:
        return f"{year - 1}-Q4"
    elif month <= 6:
        return f"{year}-Q1"
    elif month <= 9:
        return f"{year}-Q2"
    else:
        return f"{year}-Q3"


def fetch_earnings_8k(
    symbol: str,
    quarters: int = 8,
    output_path: str | None = None,
) -> dict[str, Any]:
    """指定銘柄の直近N四半期の8-K EX-99.1 プレスリリースを取得する.

    Parameters
    ----------
    symbol : str
        ティッカーシンボル（例: "BLK"）。
    quarters : int
        取得する四半期数。
    output_path : str | None
        出力JSONファイルパス。None の場合は stdout に出力。

    Returns
    -------
    dict[str, Any]
        構造化された結果 JSON。
    """
    logger.info(
        "Starting 8-K fetch: symbol=%s, quarters=%d",
        symbol,
        quarters,
    )

    with EdgarClient() as client:
        # Step 1: ticker → CIK
        cik = resolve_cik(client, symbol)

        # Step 2: 8-K filing 一覧を取得（十分な数を取得）
        # 8-K は決算以外も含むため、必要数より多めに取得
        filings = fetch_8k_filings(client, cik, max_filings=quarters * 5)

        results: list[dict[str, Any]] = []
        skipped_count = 0

        for filing in filings:
            if len(results) >= quarters:
                break

            accession = filing["accessionNumber"]
            filing_date = filing["filingDate"]

            logger.info(
                "Processing 8-K: accession=%s, filingDate=%s",
                accession,
                filing_date,
            )

            # Step 3: EX-99.1 URL を特定
            ex99_url = find_ex99_url(client, cik, accession)
            if ex99_url is None:
                skipped_count += 1
                logger.warning(
                    "No EX-99.1 found, skipping: accession=%s (non-earnings 8-K)",
                    accession,
                )
                continue

            # Step 4: EX-99.1 テキスト取得
            try:
                full_text = fetch_ex99_text(client, ex99_url)
            except httpx.HTTPStatusError as e:
                skipped_count += 1
                logger.warning(
                    "Failed to fetch EX-99.1: %s (status=%d)",
                    ex99_url,
                    e.response.status_code,
                )
                continue

            # Step 4.5: 決算プレスリリースかどうかを判定
            # EX-99.1 は取締役選任・M&A等のプレスリリースにも使われるため
            preview = full_text[:3000]
            if not EARNINGS_KEYWORDS.search(preview):
                skipped_count += 1
                logger.warning(
                    "EX-99.1 is not an earnings press release, skipping: accession=%s",
                    accession,
                )
                continue

            # Step 5: ハイライト抽出
            highlights = extract_highlights(full_text)
            fiscal_quarter = derive_fiscal_quarter(filing_date)

            results.append({
                "fiscal_quarter": fiscal_quarter,
                "filing_date": filing_date,
                "accession_number": accession,
                "ex99_url": ex99_url,
                "highlights": highlights,
                "full_text_chars": len(full_text),
            })

            logger.info(
                "Extracted: quarter=%s, chars=%d",
                fiscal_quarter,
                len(full_text),
            )

    output = {
        "symbol": symbol.upper(),
        "cik": cik,
        "quarters": results,
        "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    logger.info(
        "Completed: %d quarters fetched, %d skipped",
        len(results),
        skipped_count,
    )

    # 出力
    json_str = json.dumps(output, ensure_ascii=False, indent=2)
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json_str, encoding="utf-8")
        logger.info("Output written to %s", out)
    else:
        print(json_str)

    return output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI エントリーポイント."""
    parser = argparse.ArgumentParser(
        description="SEC EDGAR 8-K プレスリリース（EX-99.1）取得ヘルパー",
    )
    parser.add_argument(
        "--symbol",
        required=True,
        help="ティッカーシンボル（例: BLK, GS, AAPL）",
    )
    parser.add_argument(
        "--quarters",
        type=int,
        default=8,
        help="取得する四半期数（デフォルト: 8）",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="出力 JSON ファイルパス（デフォルト: stdout）",
    )

    args = parser.parse_args()

    if args.quarters < 1:
        parser.error("--quarters は 1 以上を指定してください")

    try:
        fetch_earnings_8k(
            symbol=args.symbol,
            quarters=args.quarters,
            output_path=args.output,
        )
    except ValueError as e:
        logger.error("Error: %s", e)
        sys.exit(1)
    except httpx.HTTPError as e:
        logger.error("HTTP error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
