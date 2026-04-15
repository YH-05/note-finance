"""企業ロゴをWikidata P154経由で取得しローカルキャッシュするスクリプト.

パイプライン:
1. 企業名/ティッカー → Wikipedia summary API → wikibase_item (QID)
2. QID → Wikidata entity API → P154 (logo image) claim
3. ファイル名 → Commons Special:FilePath?width=800 で PNG取得
4. `assets/company_logos/{ticker}.png` にキャッシュ

Usage
-----
CLI:
    # ティッカーと企業名を明示
    uv run python scripts/fetch_company_logo.py --ticker NFLX --company Netflix

    # meta.yaml から自動解決（category=earnings 前提）
    uv run python scripts/fetch_company_logo.py --meta-yaml articles/earnings/2026-04-15_nflx-q1-2026-earnings-preview/meta.yaml

モジュール:
    from scripts.fetch_company_logo import fetch_company_logo
    path = fetch_company_logo(ticker="NFLX", company_name="Netflix")
"""

# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "requests>=2.31",
#     "pyyaml>=6.0",
# ]
# ///

from __future__ import annotations

import argparse
import logging
import sys
import urllib.parse
from pathlib import Path

import requests
import yaml

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "assets" / "company_logos"
WIKI_USER_AGENT = "note-finance-thumbnail/1.0 (https://github.com/YH-05/note-finance; youxitiancore@gmail.com)"
REQUEST_TIMEOUT = 15
LOGO_WIDTH = 800


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": WIKI_USER_AGENT, "Accept": "application/json"})
    return s


def _wikibase_item(session: requests.Session, title: str) -> str | None:
    """Wikipedia page summary から wikibase_item (Q番号) を取得."""
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title)}"
    resp = session.get(url, timeout=REQUEST_TIMEOUT)
    if resp.status_code != 200:
        logger.warning("Wikipedia summary failed: title=%s status=%s", title, resp.status_code)
        return None
    return resp.json().get("wikibase_item")


def _wikidata_logo_filename(session: requests.Session, qid: str) -> str | None:
    """Wikidata エンティティから P154 (logo image) クレームのファイル名を取得."""
    url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
    resp = session.get(url, timeout=REQUEST_TIMEOUT)
    if resp.status_code != 200:
        logger.warning("Wikidata entity failed: qid=%s status=%s", qid, resp.status_code)
        return None
    entities = resp.json().get("entities", {})
    claims = next(iter(entities.values()), {}).get("claims", {})
    p154 = claims.get("P154", [])
    if not p154:
        return None
    return p154[0]["mainsnak"]["datavalue"]["value"]


def _download_logo(session: requests.Session, filename: str, dest: Path) -> bool:
    """Commons Special:FilePath で指定幅PNGをダウンロードし保存."""
    encoded = urllib.parse.quote(filename)
    url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{encoded}?width={LOGO_WIDTH}"
    resp = session.get(url, timeout=REQUEST_TIMEOUT, stream=True)
    if resp.status_code != 200:
        logger.warning("Commons download failed: filename=%s status=%s", filename, resp.status_code)
        return False
    content_type = resp.headers.get("Content-Type", "")
    if not content_type.startswith("image/"):
        logger.warning("Not an image response: content-type=%s", content_type)
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    logger.info("Saved logo: %s (%d bytes)", dest, dest.stat().st_size)
    return True


def _is_ascii(s: str) -> bool:
    return s.isascii()


def _candidate_titles(company_name: str, ticker: str) -> list[str]:
    """Wikipedia ページタイトル候補を優先順で返す（ASCII優先）."""
    name = company_name.strip()
    ascii_first = _is_ascii(name)
    base = [
        name.replace(" ", "_") if ascii_first else None,
        f"{name.replace(' ', '_')},_Inc." if ascii_first else None,
        f"{name.replace(' ', '_')}_Inc." if ascii_first else None,
        ticker.upper(),
        f"{ticker.upper()}_(company)",
    ]
    # 非ASCII名は検索APIに任せるため末尾
    if not ascii_first and name:
        base.append(name.replace(" ", "_"))
    seen: set[str] = set()
    result = []
    for c in base:
        if c and c not in seen:
            seen.add(c)
            result.append(c)
    return result


def _search_wikipedia_title(session: requests.Session, query: str) -> str | None:
    """Wikipedia検索APIで最上位ヒットのタイトルを返す（候補が全滅した場合のフォールバック）."""
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": 1,
        "format": "json",
    }
    resp = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
    if resp.status_code != 200:
        return None
    results = resp.json().get("query", {}).get("search", [])
    if not results:
        return None
    return results[0]["title"].replace(" ", "_")


_SEC_TICKER_CACHE: dict[str, str] | None = None


def _sec_ticker_to_name(_session: requests.Session, ticker: str) -> str | None:
    """SEC EDGAR の company_tickers.json からティッカー → 公式企業名を解決.

    SEC EDGAR は独自UA要件があるため、Wikipedia/Commons用セッションとは別に
    直接 requests.get を呼ぶ.
    """
    global _SEC_TICKER_CACHE
    if _SEC_TICKER_CACHE is None:
        try:
            resp = requests.get(
                "https://www.sec.gov/files/company_tickers.json",
                headers={
                    "User-Agent": "YH-05 note-finance youxitiancore@gmail.com",
                    "Accept": "application/json",
                },
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code == 200:
                _SEC_TICKER_CACHE = {
                    row["ticker"].upper(): row["title"]
                    for row in resp.json().values()
                }
                logger.debug("SEC EDGAR cache loaded: %d tickers", len(_SEC_TICKER_CACHE))
            else:
                logger.warning("SEC EDGAR returned status=%s", resp.status_code)
                _SEC_TICKER_CACHE = {}
        except Exception as e:
            logger.warning("SEC EDGAR fetch failed: %s", e)
            _SEC_TICKER_CACHE = {}
    return _SEC_TICKER_CACHE.get(ticker.upper())


def _normalize_sec_name(sec_name: str) -> str:
    """SEC公式名 (例: 'UNITEDHEALTH GROUP INC') を Wikipedia 検索向けに整形."""
    import re

    name = sec_name
    # 末尾サフィックス除去
    name = re.sub(r"\b(INC|CORP|CO|LTD|PLC|SA|AG|NV|LLC|LP|HLDGS|HOLDINGS|GROUP)\.?$", "", name, flags=re.IGNORECASE).strip()
    # タイトルケース化
    return " ".join(w.capitalize() for w in name.split())


def fetch_company_logo(
    ticker: str,
    company_name: str,
    output_path: Path | None = None,
    force_refresh: bool = False,
) -> Path | None:
    """企業ロゴをWikidata P154経由で取得しローカルキャッシュに保存.

    Parameters
    ----------
    ticker : str
        ティッカーシンボル（キャッシュファイル名に使用）
    company_name : str
        Wikipedia検索用の企業名
    output_path : Path | None
        出力先。省略時は `assets/company_logos/{ticker}.png`
    force_refresh : bool
        True の場合キャッシュを無視して再取得

    Returns
    -------
    Path | None
        保存されたロゴPNGパス。取得失敗時は None
    """
    ticker_norm = ticker.upper()
    dest = output_path if output_path else CACHE_DIR / f"{ticker_norm}.png"

    if dest.exists() and not force_refresh:
        logger.info("Using cached logo: %s", dest)
        return dest

    session = _session()

    # SEC EDGAR公式名を解決（曖昧ティッカー対策として候補の先頭に配置）
    sec_candidates: list[str] = []
    sec_name = _sec_ticker_to_name(session, ticker_norm)
    if sec_name:
        normalized = _normalize_sec_name(sec_name)
        logger.info("SEC EDGAR resolved: %s → %s (normalized: %s)", ticker_norm, sec_name, normalized)
        sec_candidates.append(normalized.replace(" ", "_"))
        sec_candidates.append(f"{normalized.replace(' ', '_')}_Group")
        # SEC名での検索APIヒット
        hit = _search_wikipedia_title(session, normalized)
        if hit:
            sec_candidates.append(hit)

    # ユーザー指定 company_name の候補
    user_candidates = _candidate_titles(company_name, ticker_norm)

    # 元の company_name での検索フォールバック
    search_query = f"{company_name} {ticker_norm}".strip()
    search_hit = _search_wikipedia_title(session, search_query)

    # 結合（SEC優先 → ユーザー指定 → 検索ヒット）
    seen: set[str] = set()
    titles: list[str] = []
    for c in (*sec_candidates, *user_candidates, search_hit):
        if c and c not in seen:
            seen.add(c)
            titles.append(c)

    for title in titles:
        logger.debug("Trying Wikipedia title: %s", title)
        qid = _wikibase_item(session, title)
        if not qid:
            continue
        logger.info("Resolved QID: %s → %s", title, qid)

        filename = _wikidata_logo_filename(session, qid)
        if not filename:
            logger.warning("No P154 logo for QID=%s", qid)
            continue
        logger.info("Found logo filename: %s", filename)

        if _download_logo(session, filename, dest):
            return dest

    logger.error("Failed to fetch logo: ticker=%s company=%s", ticker_norm, company_name)
    return None


def _resolve_from_meta(meta_path: Path) -> tuple[str, str, str] | None:
    """meta.yaml から (ticker, company_name, earnings_date) を抽出."""
    data = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    symbols = data.get("symbols") or []
    tags = data.get("tags") or []
    if not symbols:
        logger.error("meta.yaml has no symbols: %s", meta_path)
        return None
    ticker = symbols[0]
    # tags から ticker 以外の最初の要素を企業名と仮定
    company = next(
        (t for t in tags if t != ticker and t not in ("決算", "Q1", "Q2", "Q3", "Q4")),
        ticker,
    )
    earnings_date = str(data.get("earnings_date", ""))
    return ticker, company, earnings_date


def main() -> int:
    parser = argparse.ArgumentParser(description="企業ロゴをWikidata P154経由で取得")
    parser.add_argument("--ticker", help="ティッカーシンボル (例: NFLX)")
    parser.add_argument("--company", help="Wikipedia検索用の企業名 (例: Netflix)")
    parser.add_argument("--meta-yaml", type=Path, help="meta.yamlから ticker/company を自動解決")
    parser.add_argument("--output", type=Path, help="出力先PNGパス")
    parser.add_argument("--force-refresh", action="store_true", help="キャッシュを無視して再取得")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(level=args.log_level, format="%(levelname)s: %(message)s")

    if args.meta_yaml:
        resolved = _resolve_from_meta(args.meta_yaml)
        if not resolved:
            return 1
        ticker, company, _ = resolved
    else:
        if not args.ticker or not args.company:
            parser.error("--ticker と --company を指定するか --meta-yaml を指定してください")
        ticker, company = args.ticker, args.company

    path = fetch_company_logo(
        ticker=ticker,
        company_name=company,
        output_path=args.output,
        force_refresh=args.force_refresh,
    )
    if not path:
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
