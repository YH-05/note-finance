"""creator_enrichment 共通ユーティリティ."""

from __future__ import annotations


def strip_json_codeblock(text: str) -> str:
    """LLM レスポンスから JSON コードブロックマーカーを除去する.

    ``````json ... `````` または ````` ... ````` ラッピングに対応する。

    Parameters
    ----------
    text : str
        LLM のテキストレスポンス

    Returns
    -------
    str
        コードブロックマーカーを除去した文字列
    """
    text = text.strip()
    if text.startswith("```json"):
        text = text[len("```json") :]
    elif text.startswith("```"):
        text = text[len("```") :]
    if text.endswith("```"):
        text = text[: -len("```")]
    return text.strip()
