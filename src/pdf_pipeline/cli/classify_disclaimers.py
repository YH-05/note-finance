"""Disclaimer page classification prompt and utilities.

Provides the system prompt and page text formatting for Haiku-based
disclaimer classification. The actual LLM call is made by the
/convert-pdf skill (Claude Code) which spawns a Haiku subagent.

This module does NOT call any LLM API directly.

Usage (from skill)
------------------
The skill reads page_texts.json, formats with ``format_prompt()``,
and spawns a Haiku subagent via ``Agent(model="haiku")`` to classify.

Usage (CLI — for standalone testing only)
-----------------------------------------
    $ uv run python -m pdf_pipeline.cli.classify_disclaimers page_texts.json
    # Prints formatted prompt for manual inspection (no API call)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pdf_pipeline._logging import get_logger

logger = get_logger(__name__, module="cli.classify_disclaimers")

# ---------------------------------------------------------------------------
# Constants — model is hardcoded in the skill. Do not change.
# ---------------------------------------------------------------------------

MODEL = "claude-haiku-4-5-20251001"
MAX_PREVIEW_CHARS = 2000

SYSTEM_PROMPT = """\
あなたはPDFページの分類器です。
各ページのテキストを読み、ディスクレーマー（免責事項）ページかどうかを判定します。

ディスクレーマーの判定基準:
- 法的免責、投資助言の否定、利益相反の開示
- 格付・レーティングの定義一覧
- 地域別の配布制限・規制情報
- アナリスト認証（Analyst Certification）
- 会社概要・連絡先のみのページ（レポート末尾）

ディスクレーマーではないもの:
- 分析内容・投資見解・データ・考察
- 目次・要約・エグゼクティブサマリー
- 財務データ・業績予想・バリュエーション

ディスクレーマーと判定したページ番号のみをJSON配列で返してください。
ディスクレーマーがなければ空配列 [] を返してください。
出力はJSON配列のみ。説明不要。"""


# ---------------------------------------------------------------------------
# Formatting functions
# ---------------------------------------------------------------------------


def format_prompt(page_texts: dict[str, str]) -> str:
    """Format page texts into a prompt for disclaimer classification.

    Parameters
    ----------
    page_texts : dict[str, str]
        Mapping of page number (str) to page text content.

    Returns
    -------
    str
        Formatted prompt string with page previews.
    """
    previews = []
    for page_num in sorted(page_texts, key=int):
        text = page_texts[page_num].strip()[:MAX_PREVIEW_CHARS]
        previews.append(f"[Page {page_num}]\n{text}")

    return "\n---\n".join(previews)


def parse_response(result_text: str) -> list[int]:
    """Parse the LLM response into a list of disclaimer page numbers.

    Parameters
    ----------
    result_text : str
        Raw LLM response text (expected: JSON array of ints).

    Returns
    -------
    list[int]
        Page numbers identified as disclaimer pages.
        Returns empty list if parsing fails.
    """
    text = result_text.strip()
    try:
        pages = json.loads(text)
    except json.JSONDecodeError:
        logger.warning(
            "Failed to parse response as JSON, returning empty",
            raw=text,
        )
        return []

    if not isinstance(pages, list):
        logger.warning("Response is not a list, returning empty", raw=text)
        return []

    disclaimer_pages = [int(p) for p in pages]
    logger.info("Disclaimer pages identified", pages=disclaimer_pages)
    return disclaimer_pages


# ---------------------------------------------------------------------------
# CLI entry point (prompt preview only — no API call)
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point: prints formatted prompt for inspection."""
    if len(sys.argv) < 2:
        print(
            "Usage: python -m pdf_pipeline.cli.classify_disclaimers <page_texts.json>",
            file=sys.stderr,
        )
        print(
            "  Prints formatted prompt for Haiku disclaimer classification.",
            file=sys.stderr,
        )
        print(
            "  The actual LLM call is made by the /convert-pdf skill.",
            file=sys.stderr,
        )
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"Error: File not found: {path}", file=sys.stderr)
        sys.exit(1)

    page_texts = json.loads(path.read_text(encoding="utf-8"))
    prompt = format_prompt(page_texts)

    print(f"=== SYSTEM PROMPT ===\n{SYSTEM_PROMPT}\n")
    print(f"=== USER PROMPT ({len(prompt)} chars, {len(page_texts)} pages) ===")
    print(prompt)


if __name__ == "__main__":
    main()
