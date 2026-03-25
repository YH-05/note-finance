"""既存パイプラインの出力を CollectedItem に変換するアダプター群.

各既存パイプラインの出力形式を知っているのはこのモジュールだけ。
RawStore は常に CollectedItem を受け取る。

対応する既存モデル:
- news.models.CollectedArticle / ExtractedArticle — news パッケージ
- news_scraper.types.Article — news_scraper パッケージ
- rss MCP の rss_get_items 出力 (dict)
- pdf_pipeline の chunks (dict)
- web-research / reddit-finance-topics の出力 (dict)
"""

from __future__ import annotations

import contextlib
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from data_pipeline.collectors.base import CollectedItem

if TYPE_CHECKING:
    from collections.abc import Callable

# ---------------------------------------------------------------------------
# news パッケージ (src/news/)
# ---------------------------------------------------------------------------


def from_news_collected_article(
    article: Any,
    source_id: str,
) -> CollectedItem:
    """news.models.CollectedArticle → CollectedItem.

    Parameters
    ----------
    article : CollectedArticle
        news パッケージの CollectedArticle インスタンス。
    source_id : str
        source_registry の source_id。
    """
    return CollectedItem(
        source_id=source_id,
        url=str(article.url),
        title=article.title,
        raw_text=article.raw_summary or "",
        published_at=article.published,
        collected_at=article.collected_at,
        collection_method="rss",
        metadata={
            "source_type": article.source.source_type.value
            if hasattr(article.source.source_type, "value")
            else str(article.source.source_type),
            "source_name": article.source.source_name,
            "category": article.source.category,
        },
    )


def from_news_extracted_article(
    article: Any,
    source_id: str,
) -> CollectedItem:
    """news.models.ExtractedArticle → CollectedItem.

    本文抽出済みの記事。body_text があればそちらを raw_text に使う。
    """
    collected = article.collected
    raw_text = article.body_text or collected.raw_summary or ""
    return CollectedItem(
        source_id=source_id,
        url=str(collected.url),
        title=collected.title,
        raw_text=raw_text,
        published_at=collected.published,
        collected_at=collected.collected_at,
        collection_method="rss",
        metadata={
            "source_type": collected.source.source_type.value
            if hasattr(collected.source.source_type, "value")
            else str(collected.source.source_type),
            "source_name": collected.source.source_name,
            "extraction_status": article.extraction_status.value
            if hasattr(article.extraction_status, "value")
            else str(article.extraction_status),
            "extraction_method": article.extraction_method,
        },
    )


# ---------------------------------------------------------------------------
# news_scraper パッケージ (src/news_scraper/)
# ---------------------------------------------------------------------------


def from_news_scraper_article(
    article: Any,
    source_id: str,
) -> CollectedItem:
    """news_scraper.types.Article → CollectedItem.

    Parameters
    ----------
    article : Article
        news_scraper の Article インスタンス。
    source_id : str
        source_registry の source_id。
    """
    raw_text = article.content or article.summary or ""
    return CollectedItem(
        source_id=source_id,
        url=str(article.url),
        title=article.title,
        raw_text=raw_text,
        published_at=article.published,
        author=article.author,
        collected_at=article.fetched_at,
        collection_method="scraping",
        content_type="article",
        metadata={
            "source": article.source,
            "category": article.category,
            "tags": article.tags,
        },
    )


# ---------------------------------------------------------------------------
# RSS MCP 出力 (dict)
# ---------------------------------------------------------------------------


def from_rss_mcp_item(
    item: dict[str, Any],
    source_id: str,
) -> CollectedItem:
    """RSS MCP の rss_get_items / rss_search_items 出力 → CollectedItem.

    RSS MCP は dict 形式で記事を返す:
    {"item_id", "title", "link", "published", "summary", "content", "author", "fetched_at"}
    """
    raw_text = item.get("content") or item.get("summary") or ""
    published_at = None
    if item.get("published"):
        with contextlib.suppress(ValueError, TypeError):
            published_at = datetime.fromisoformat(item["published"])

    return CollectedItem(
        source_id=source_id,
        url=item.get("link", ""),
        title=item.get("title", ""),
        raw_text=raw_text,
        published_at=published_at,
        author=item.get("author"),
        collection_method="rss",
        metadata={
            "item_id": item.get("item_id"),
            "fetched_at": item.get("fetched_at"),
        },
    )


# ---------------------------------------------------------------------------
# PDF パイプライン出力 (dict)
# ---------------------------------------------------------------------------


def from_pdf_chunk(
    chunk: dict[str, Any],
    source_id: str,
    *,
    pdf_url: str | None = None,
    pdf_title: str | None = None,
) -> CollectedItem:
    """pdf_pipeline の chunk 出力 → CollectedItem.

    PDF変換は通常 report.md + chunks.json を出力する。
    各 chunk を1つの CollectedItem として保存する。
    """
    # AIDEV-NOTE: chunk_index をURLに付与して一意性を保証（同じPDFの複数チャンク）
    base_url = pdf_url or chunk.get("source_url", "")
    chunk_idx = chunk.get("chunk_index")
    url = f"{base_url}#chunk-{chunk_idx}" if chunk_idx is not None else base_url

    return CollectedItem(
        source_id=source_id,
        url=url,
        title=pdf_title or chunk.get("title", ""),
        raw_text=chunk.get("text", chunk.get("content", "")),
        collection_method="pdf",
        content_type="report",
        metadata={
            "chunk_index": chunk_idx,
            "page_range": chunk.get("page_range"),
            "section": chunk.get("section"),
            "pdf_url": base_url,
        },
    )


def from_pdf_report(
    report_text: str,
    *,
    source_id: str,
    pdf_url: str,
    pdf_title: str,
) -> CollectedItem:
    """PDF変換の全文 (report.md) → 単一 CollectedItem."""
    return CollectedItem(
        source_id=source_id,
        url=pdf_url,
        title=pdf_title,
        raw_text=report_text,
        collection_method="pdf",
        content_type="report",
    )


# ---------------------------------------------------------------------------
# Web検索出力 (dict)
# ---------------------------------------------------------------------------


def from_web_research(
    finding: dict[str, Any],
    source_id: str,
) -> CollectedItem:
    """web-research (Tavily/Gemini) の調査結果 → CollectedItem."""
    return CollectedItem(
        source_id=source_id,
        url=finding.get("url", finding.get("source_url", "")),
        title=finding.get("title", ""),
        raw_text=finding.get(
            "content", finding.get("text", finding.get("summary", ""))
        ),
        collection_method="web_search",
        content_type="article",
        metadata={
            "search_query": finding.get("query"),
            "search_provider": finding.get("provider"),
            "score": finding.get("score"),
        },
    )


# ---------------------------------------------------------------------------
# Reddit 出力 (dict)
# ---------------------------------------------------------------------------


def from_reddit_post(
    post: dict[str, Any],
    source_id: str = "reddit",
) -> CollectedItem:
    """Reddit MCP の投稿データ → CollectedItem."""
    return CollectedItem(
        source_id=source_id,
        url=post.get("url", post.get("permalink", "")),
        title=post.get("title", ""),
        raw_text=post.get("selftext", post.get("body", post.get("content", ""))),
        published_at=post.get("created_utc"),
        author=post.get("author"),
        collection_method="api",
        content_type="post",
        metadata={
            "subreddit": post.get("subreddit"),
            "score": post.get("score"),
            "num_comments": post.get("num_comments"),
        },
    )


# ---------------------------------------------------------------------------
# バッチ変換ヘルパー
# ---------------------------------------------------------------------------


def convert_many(
    items: list[Any],
    converter: Callable[..., CollectedItem],
    source_id: str,
    **kwargs,
) -> list[CollectedItem]:
    """リストの全アイテムを一括変換する.

    変換に失敗したアイテムはスキップする。

    Parameters
    ----------
    items : list
        変換元のアイテムリスト。
    converter : callable
        変換関数（from_* のいずれか）。
    source_id : str
        ソースID。

    Returns
    -------
    list[CollectedItem]
        変換されたアイテム。
    """
    results: list[CollectedItem] = []
    for item in items:
        try:
            results.append(converter(item, source_id, **kwargs))
        except Exception:
            continue
    return results
