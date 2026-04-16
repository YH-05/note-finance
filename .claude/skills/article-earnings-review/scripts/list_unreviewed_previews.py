"""articles/earnings/ 配下から未レビューのプレビュー記事候補を列挙する。

プレビュー記事のうち、以下を全て満たすものをレビュー対象候補として抽出する:

1. ディレクトリ名に ``-preview`` を含む、または ``meta.yaml`` の ``type`` が
   ``earnings_preview``
2. ``earnings_date`` が今日以前（発表済み）
3. note.com に投稿済み（``note_url`` または ``draft_url`` が埋まっている）
4. 対応するレビュー記事が存在しない（同ティッカー・同 fiscal_quarter・同 fiscal_year）

出力は JSON。``--format table`` を指定すると人間可読な整形出力に切り替わる。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

import yaml

EARNINGS_ROOT_DEFAULT = Path("articles/earnings")

QUARTER_END_MONTH_MAP = {
    "jan": "Q4",
    "feb": "Q4",
    "mar": "Q1",
    "apr": "Q1",
    "may": "Q1",
    "jun": "Q2",
    "jul": "Q2",
    "aug": "Q2",
    "sep": "Q3",
    "oct": "Q3",
    "nov": "Q3",
    "dec": "Q4",
}


@dataclass
class PreviewCandidate:
    """未レビューのプレビュー記事候補。"""

    article_dir: str
    ticker: str
    fiscal_quarter: str
    fiscal_year: str
    earnings_date: str
    note_url: str | None
    title: str | None


def _load_meta(meta_path: Path) -> dict | None:
    try:
        with meta_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict):
            return data
    except (OSError, yaml.YAMLError):
        return None
    return None


def _extract_ticker(meta: dict) -> str | None:
    ticker = meta.get("symbol")
    if isinstance(ticker, str) and ticker.strip():
        return ticker.strip().upper()
    symbols = meta.get("symbols")
    if isinstance(symbols, list) and symbols:
        first = symbols[0]
        if isinstance(first, str) and first.strip():
            return first.strip().upper()
    return None


def _extract_fiscal_quarter(meta: dict) -> tuple[str | None, str | None]:
    """``(fiscal_quarter, fiscal_year)`` を抽出する。揺れの多いフィールドを吸収。

    対応する形式:
    - ``fiscal_quarter: Q1`` + ``fiscal_year: 2026``
    - ``fiscal_quarter: "Q1 2026"`` （``fiscal_year`` 省略可）
    - ``fiscal_quarter_ending: Mar/2026`` → ``(Q1, 2026)``
    """

    fq_raw = meta.get("fiscal_quarter")
    fy_raw = meta.get("fiscal_year")

    fq: str | None = None
    fy: str | None = None

    if isinstance(fq_raw, str) and fq_raw.strip():
        # "Q1 2026" / "Q1-2026" / "Q1/2026" のように年度がセットで入っている場合
        m = re.match(r"(Q[1-4])[\s\-/]+(\d{4})", fq_raw.strip().upper())
        if m:
            fq = m.group(1)
            fy = m.group(2)
        else:
            m2 = re.match(r"(Q[1-4])", fq_raw.strip().upper())
            if m2:
                fq = m2.group(1)

    if fy is None and fy_raw:
        fy = str(fy_raw)

    if fq and fy:
        return fq, fy

    ending = meta.get("fiscal_quarter_ending")
    if isinstance(ending, str) and ending.strip():
        # 例: "Mar/2026" → (Q1, 2026)
        m = re.match(r"([A-Za-z]{3,9})[/\-\s]+(\d{4})", ending.strip())
        if m:
            mon = m.group(1).lower()[:3]
            year = m.group(2)
            return QUARTER_END_MONTH_MAP.get(mon), year

    return fq, fy


def _extract_from_dirname(dir_name: str) -> tuple[str | None, str | None, str | None]:
    """ディレクトリ名から (ticker, fiscal_quarter, fiscal_year) を推定する。

    対応する命名パターン:
    - ``2026-04-15_tsla-q1-2026-earnings-preview`` → ``(TSLA, Q1, 2026)``
    - ``2026-04-14_blk-earnings-review-2026q1`` → ``(BLK, Q1, 2026)``
    - ``2026-04-06_blk-earnings-preview`` → ``(BLK, None, None)``
    """

    # パターン A: {ticker}-q{N}-{year}-earnings-{preview|review}
    m = re.match(
        r"\d{4}-\d{2}-\d{2}_(?P<ticker>[a-z0-9\.]+)-q(?P<q>[1-4])-(?P<year>\d{4})-earnings-(?:preview|review)",
        dir_name,
    )
    if m:
        return m.group("ticker").upper(), f"Q{m.group('q')}", m.group("year")

    # パターン B: {ticker}-earnings-{preview|review}-{year}q{N}
    m = re.match(
        r"\d{4}-\d{2}-\d{2}_(?P<ticker>[a-z0-9\.]+)-earnings-(?:preview|review)-(?P<year>\d{4})q(?P<q>[1-4])",
        dir_name,
    )
    if m:
        return m.group("ticker").upper(), f"Q{m.group('q')}", m.group("year")

    # パターン C: {ticker}-earnings-{preview|review} （Q情報なし）
    m = re.match(
        r"\d{4}-\d{2}-\d{2}_(?P<ticker>[a-z0-9\.]+)-earnings-(?:preview|review)", dir_name
    )
    if m:
        return m.group("ticker").upper(), None, None
    return None, None, None


def _extract_note_url(meta: dict) -> str | None:
    for key in ("note_url", "draft_url"):
        val = meta.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _is_published(meta: dict) -> bool:
    workflow = meta.get("workflow", {})
    if not isinstance(workflow, dict):
        return False
    if workflow.get("publish") == "done":
        return True
    publishing = workflow.get("publishing", {})
    if isinstance(publishing, dict) and publishing.get("published") == "done":
        return True
    return False


def _parse_earnings_date(meta: dict) -> date | None:
    raw = meta.get("earnings_date")
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str):
        try:
            return datetime.strptime(raw.strip(), "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def _classify(dir_name: str, meta: dict) -> str:
    """``preview`` / ``review`` / ``other`` のいずれかを返す。"""

    type_field = meta.get("type")
    if type_field == "earnings_preview":
        return "preview"
    if type_field == "earnings_review":
        return "review"
    if "-review" in dir_name:
        return "review"
    if "-preview" in dir_name:
        return "preview"
    return "other"


def scan_earnings_dir(root: Path, today: date) -> list[PreviewCandidate]:
    """``root`` 配下を走査して候補を返す。"""

    if not root.exists():
        return []

    previews: list[tuple[Path, dict]] = []
    reviews_keys: set[tuple[str, str, str]] = set()

    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        meta_path = entry / "meta.yaml"
        if not meta_path.exists():
            continue
        meta = _load_meta(meta_path)
        if meta is None:
            continue
        kind = _classify(entry.name, meta)

        ticker = _extract_ticker(meta)
        fq, fy = _extract_fiscal_quarter(meta)
        if not (ticker and fq and fy):
            dn_ticker, dn_fq, dn_fy = _extract_from_dirname(entry.name)
            ticker = ticker or dn_ticker
            fq = fq or dn_fq
            fy = fy or dn_fy

        if kind == "review" and ticker and fq and fy:
            reviews_keys.add((ticker, fq, fy))
        elif kind == "preview":
            previews.append((entry, meta))

    candidates: list[PreviewCandidate] = []
    for article_dir, meta in previews:
        ticker = _extract_ticker(meta)
        fq, fy = _extract_fiscal_quarter(meta)
        if not (ticker and fq and fy):
            dn_ticker, dn_fq, dn_fy = _extract_from_dirname(article_dir.name)
            ticker = ticker or dn_ticker
            fq = fq or dn_fq
            fy = fy or dn_fy
        if not (ticker and fq and fy):
            # キーが揃わないものはスキップ（ユーザーが後述のログで気付けるよう stderr 出力）
            print(
                f"[warn] fiscal キー不足のためスキップ: {article_dir.name}", file=sys.stderr
            )
            continue

        earnings_date = _parse_earnings_date(meta)
        if earnings_date is None:
            print(
                f"[warn] earnings_date 欠落のためスキップ: {article_dir.name}",
                file=sys.stderr,
            )
            continue
        if earnings_date > today:
            continue  # まだ発表前
        if not _is_published(meta):
            continue  # プレビュー自体が未投稿
        if (ticker, fq, fy) in reviews_keys:
            continue  # 既にレビュー済み

        candidates.append(
            PreviewCandidate(
                article_dir=str(article_dir),
                ticker=ticker,
                fiscal_quarter=fq,
                fiscal_year=fy,
                earnings_date=earnings_date.isoformat(),
                note_url=_extract_note_url(meta),
                title=meta.get("title") if isinstance(meta.get("title"), str) else None,
            )
        )

    candidates.sort(key=lambda c: c.earnings_date)
    return candidates


def _format_table(candidates: list[PreviewCandidate]) -> str:
    if not candidates:
        return "該当候補なし（未レビューのプレビュー記事はありません）"

    lines = [
        "| # | ティッカー | 会計四半期 | 発表日 | プレビュー記事 |",
        "|---|-----------|-----------|--------|---------------|",
    ]
    for idx, c in enumerate(candidates, start=1):
        lines.append(
            f"| {idx} | {c.ticker} | {c.fiscal_quarter} {c.fiscal_year} | "
            f"{c.earnings_date} | {c.article_dir} |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="未レビューのプレビュー記事候補を列挙する"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=EARNINGS_ROOT_DEFAULT,
        help="earnings 記事ルート（デフォルト: articles/earnings）",
    )
    parser.add_argument(
        "--today",
        type=str,
        default=None,
        help="判定基準日（YYYY-MM-DD、省略時は実行日）",
    )
    parser.add_argument(
        "--format",
        choices=("json", "table"),
        default="json",
        help="出力形式",
    )
    args = parser.parse_args()

    today = (
        datetime.strptime(args.today, "%Y-%m-%d").date()
        if args.today
        else date.today()
    )

    candidates = scan_earnings_dir(args.root, today)

    if args.format == "table":
        print(_format_table(candidates))
    else:
        print(
            json.dumps(
                {
                    "today": today.isoformat(),
                    "count": len(candidates),
                    "candidates": [asdict(c) for c in candidates],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
