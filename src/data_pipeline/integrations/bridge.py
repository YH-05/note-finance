"""既存パイプラインとRawStoreの統合ブリッジ.

既存の収集パイプライン（news_scraper, report_scraper, pdf_pipeline等）の
出力をRawStoreに保存するワンライナー関数群。

既存コードへの変更は最小限: 収集完了後に bridge 関数を1行呼ぶだけ。

Usage（既存コード側）:
    from data_pipeline.integrations.bridge import save_news_scraper_results
    articles = await collect_financial_news(sources=["cnbc"])
    save_news_scraper_results(articles.to_dict(), source_id="cnbc")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from data_pipeline.collectors.base import CollectedItem
from data_pipeline.storage.adapters import (
    convert_many,
    from_news_scraper_article,
    from_pdf_chunk,
    from_pdf_report,
    from_reddit_post,
    from_rss_mcp_item,
    from_web_research,
)
from data_pipeline.storage.raw_store import RawStore, SaveResult

# AIDEV-NOTE: モジュールレベルのストアインスタンス。
# デフォルトで /Volumes/personal_folder/raw_texts に保存。
_store: RawStore | None = None


def _get_store() -> RawStore:
    """シングルトンの RawStore インスタンスを返す."""
    global _store  # noqa: PLW0603
    if _store is None:
        _store = RawStore()
    return _store


def set_store(store: RawStore) -> None:
    """テスト用: カスタム RawStore を設定する."""
    global _store  # noqa: PLW0603
    _store = store


# ---------------------------------------------------------------------------
# news_scraper パッケージ統合
# ---------------------------------------------------------------------------


def save_news_scraper_results(
    articles: list[dict[str, Any]] | list[Any],
    source_id: str,
) -> SaveResult:
    """news_scraper の収集結果を RawStore に保存する.

    Parameters
    ----------
    articles : list[dict] | list[Article]
        news_scraper.unified.collect_financial_news() の出力。
        NewsDataFrame.to_dict() の結果、または Article リスト。
    source_id : str
        source_registry の source_id (例: "cnbc")。

    Returns
    -------
    SaveResult
        保存結果。

    Examples
    --------
    >>> # 既存コードに1行追加するだけ
    >>> articles = await collect_financial_news(sources=["cnbc"])
    >>> save_news_scraper_results(articles.to_dict(), source_id="cnbc")
    """
    store = _get_store()

    # dict の場合は save_many_texts で直接保存
    if articles and isinstance(articles[0], dict):
        items = []
        for a in articles:
            items.append({
                "url": a.get("url", ""),
                "title": a.get("title", ""),
                "raw_text": a.get("content") or a.get("summary") or "",
                "published_at": a.get("published"),
                "author": a.get("author"),
                "metadata": {
                    "source": a.get("source"),
                    "category": a.get("category"),
                    "tags": a.get("tags", []),
                },
            })
        return store.save_many_texts(
            items, source_id=source_id, collection_method="scraping",
        )

    # Article オブジェクトの場合はアダプター経由
    collected = convert_many(articles, from_news_scraper_article, source_id)
    return _save_collected_items(collected, source_id)


# ---------------------------------------------------------------------------
# report_scraper パッケージ統合
# ---------------------------------------------------------------------------


def save_report_scraper_results(
    reports: list[dict[str, Any]],
    source_id: str = "report-scraper",
) -> SaveResult:
    """report_scraper の収集結果を RawStore に保存する.

    Parameters
    ----------
    reports : list[dict]
        ScrapedReport の辞書化リスト。各dictに:
        - url, title, published（ReportMetadata由来）
        - content.text（ExtractedContent由来）
    source_id : str
        ソースID。
    """
    store = _get_store()
    items = []
    for r in reports:
        metadata = r.get("metadata", r)
        content = r.get("content", {})
        items.append({
            "url": metadata.get("url", ""),
            "title": metadata.get("title", ""),
            "raw_text": content.get("text", "") if isinstance(content, dict) else "",
            "published_at": metadata.get("published"),
            "author": metadata.get("author"),
            "metadata": {
                "source_key": metadata.get("source_key"),
                "tags": list(metadata.get("tags", ())),
                "extraction_method": content.get("method") if isinstance(content, dict) else None,
            },
        })
    return store.save_many_texts(
        items, source_id=source_id, collection_method="scraping",
    )


# ---------------------------------------------------------------------------
# pdf_pipeline パッケージ統合
# ---------------------------------------------------------------------------


def save_pdf_chunks(
    chunks: list[dict[str, Any]],
    source_id: str = "pdf-sellside",
    *,
    pdf_url: str = "",
    pdf_title: str = "",
) -> SaveResult:
    """pdf_pipeline の chunks を RawStore に保存する.

    Parameters
    ----------
    chunks : list[dict]
        MarkdownChunker.chunk() の出力。各dictに:
        - content, section_title, chunk_index
    source_id : str
        ソースID。
    pdf_url : str
        PDFのURL。
    pdf_title : str
        PDFのタイトル。
    """
    collected = convert_many(
        chunks, from_pdf_chunk, source_id,
        pdf_url=pdf_url, pdf_title=pdf_title,
    )
    return _save_collected_items(collected, source_id)


def save_pdf_report(
    report_text: str,
    source_id: str = "pdf-sellside",
    *,
    pdf_url: str = "",
    pdf_title: str = "",
) -> SaveResult:
    """pdf_pipeline の全文テキスト (report.md) を RawStore に保存する."""
    store = _get_store()
    outcome = store.save_text(
        source_id=source_id,
        url=pdf_url,
        title=pdf_title,
        raw_text=report_text,
        collection_method="pdf",
        content_type="report",
    )
    result = SaveResult(source_id=source_id)
    if outcome == "saved":
        result.saved = 1
    elif outcome == "duplicate":
        result.skipped_duplicate = 1
    elif outcome == "empty":
        result.skipped_empty = 1
    return result


# ---------------------------------------------------------------------------
# RSS MCP 統合
# ---------------------------------------------------------------------------


def save_rss_mcp_items(
    items: list[dict[str, Any]],
    source_id: str,
) -> SaveResult:
    """RSS MCP (rss_get_items/rss_search_items) の出力を RawStore に保存する.

    Parameters
    ----------
    items : list[dict]
        rss_get_items の "items" リスト。
    source_id : str
        ソースID。
    """
    collected = convert_many(items, from_rss_mcp_item, source_id)
    return _save_collected_items(collected, source_id)


# ---------------------------------------------------------------------------
# Web検索統合（Tavily / Gemini）
# ---------------------------------------------------------------------------


def save_web_research_results(
    findings: list[dict[str, Any]],
    source_id: str = "tavily",
) -> SaveResult:
    """Web検索（Tavily/Gemini）の結果を RawStore に保存する.

    Parameters
    ----------
    findings : list[dict]
        検索結果。各dictに url, title, content/text/summary。
    source_id : str
        ソースID（"tavily" or "gemini-search"）。
    """
    collected = convert_many(findings, from_web_research, source_id)
    return _save_collected_items(collected, source_id)


# ---------------------------------------------------------------------------
# Reddit 統合
# ---------------------------------------------------------------------------


def save_reddit_posts(
    posts: list[dict[str, Any]],
    source_id: str = "reddit",
) -> SaveResult:
    """Reddit MCP の投稿データを RawStore に保存する.

    Parameters
    ----------
    posts : list[dict]
        Reddit投稿データ。各dictに title, url/permalink, selftext/body。
    source_id : str
        ソースID。
    """
    collected = convert_many(posts, from_reddit_post, source_id)
    return _save_collected_items(collected, source_id)


# ---------------------------------------------------------------------------
# 汎用: 任意のテキストデータ保存
# ---------------------------------------------------------------------------


def save_raw_texts(
    items: list[dict[str, Any]],
    source_id: str,
    collection_method: str,
) -> SaveResult:
    """任意のテキストデータを RawStore に保存する汎用ブリッジ.

    Parameters
    ----------
    items : list[dict]
        各dictに最低限 url, title, raw_text（or text or content）が必要。
    source_id : str
        ソースID。
    collection_method : str
        収集方法。
    """
    store = _get_store()
    return store.save_many_texts(
        items, source_id=source_id, collection_method=collection_method,
    )


# ---------------------------------------------------------------------------
# emit_research_queue.py 入力JSONフック（全コマンド対応）
# ---------------------------------------------------------------------------


# AIDEV-NOTE: コマンドごとに原文テキストの取得先が異なる
_COMMAND_SOURCE_ID_MAP = {
    "finance-news-workflow": "cnbc",
    "ai-research-collect": "ai-research",
    "generate-market-report": "yfinance",
    "asset-management": "wealth-blogs-rss",
    "reddit-finance-topics": "reddit",
    "finance-full": "cnbc",
    "pdf-extraction": "pdf-sellside",
    "wealth-scrape": "wealth-blogs-scrape",
    "topic-discovery": "tavily",
    "web-research": "tavily",
    "academic-fetch": "arxiv",
}

_COMMAND_METHOD_MAP = {
    "finance-news-workflow": "rss",
    "ai-research-collect": "scraping",
    "generate-market-report": "api",
    "asset-management": "rss",
    "reddit-finance-topics": "api",
    "finance-full": "rss",
    "pdf-extraction": "pdf",
    "wealth-scrape": "scraping",
    "topic-discovery": "web_search",
    "web-research": "web_search",
    "academic-fetch": "api",
}


def save_from_emit_input(
    data: dict[str, Any],
    command: str,
    source_id_override: str | None = None,
) -> SaveResult:
    """emit_research_queue.py の入力JSONから原文テキストを抽出して RawStore に保存する.

    全11コマンドに対応。sources[] の URL と facts[]/claims[] の content を
    原文として保存する。

    Parameters
    ----------
    data : dict
        emit_research_queue.py に渡される入力JSON。
    command : str
        emit_research_queue.py の --command 値。
    source_id_override : str | None
        ソースIDの上書き。None の場合はコマンドから推定。

    Returns
    -------
    SaveResult
        保存結果。
    """
    store = _get_store()
    source_id = source_id_override or _COMMAND_SOURCE_ID_MAP.get(command, command)
    method = _COMMAND_METHOD_MAP.get(command, "manual")

    items: list[dict[str, Any]] = []

    # sources[] から URL + title を取得
    source_urls: dict[str, str] = {}
    for src in data.get("sources", []):
        url = src.get("url") or src.get("link", "")
        if url:
            source_urls[url] = src.get("title", "")

    # facts[] から原文テキストを抽出
    for fact in data.get("facts", []):
        content = fact.get("content", "")
        src_url = fact.get("source_url", "")
        if content and src_url:
            items.append({
                "url": src_url,
                "title": source_urls.get(src_url, ""),
                "raw_text": content,
            })

    # claims[] から原文テキストを抽出
    for claim in data.get("claims", []):
        content = claim.get("content", "")
        src_url = claim.get("source_url", "")
        if content and src_url:
            items.append({
                "url": src_url,
                "title": source_urls.get(src_url, ""),
                "raw_text": content,
            })

    # reddit 固有: posts[] からテキスト抽出
    for post in data.get("posts", []):
        url = post.get("url") or post.get("permalink", "")
        text = post.get("selftext") or post.get("body", "")
        if url and text:
            items.append({
                "url": url,
                "title": post.get("title", ""),
                "raw_text": text,
            })

    # articles[] から抽出（finance-news-workflow, wealth-scrape等）
    for article in data.get("articles", []):
        url = article.get("url") or article.get("link", "")
        text = article.get("content") or article.get("summary") or article.get("text", "")
        if url and text:
            items.append({
                "url": url,
                "title": article.get("title", ""),
                "raw_text": text,
                "published_at": article.get("published") or article.get("published_at"),
                "author": article.get("author"),
            })

    if not items:
        return SaveResult(source_id=source_id)

    return store.save_many_texts(
        items, source_id=source_id, collection_method=method,
    )


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _save_collected_items(
    items: list[CollectedItem],
    source_id: str,
) -> SaveResult:
    """CollectedItem リストを RawStore に保存する."""
    store = _get_store()
    from data_pipeline.collectors.base import CollectionResult

    result = CollectionResult(source_id=source_id)
    result.items = items
    return store.save(result)
