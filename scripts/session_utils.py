"""Session utility functions and models for finance news workflows.

Provides reusable functions and Pydantic models extracted from
``prepare_news_session.py`` so that other scripts can share the same
building blocks without duplicating logic.

Exported symbols
----------------
Functions
    filter_by_date      — Filter RSS items by publication date.
    select_top_n        — Select top-N items sorted by newest first.
    write_session_file  — Persist a Pydantic session model as JSON.
    get_logger          — Obtain a *structlog* bound logger.

Models
    ArticleData         — Accessible article payload.
    BlockedArticle      — Blocked article payload.
    SessionStats        — Aggregate session statistics.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a *structlog* bound logger.

    Parameters
    ----------
    name : str
        Logger name — typically ``__name__`` of the caller module.

    Returns
    -------
    structlog.stdlib.BoundLogger
        Configured bound logger instance.
    """
    return structlog.get_logger(name)


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------


class ArticleData(BaseModel):
    """Article data for accessible articles.

    Attributes
    ----------
    url : str
        Article URL.
    title : str
        Article title.
    summary : str
        Article summary from RSS feed.
    feed_source : str
        Name of the RSS feed source.
    published : str
        Publication timestamp in ISO 8601 format.
    """

    url: str
    title: str
    summary: str
    feed_source: str
    published: str


class BlockedArticle(BaseModel):
    """Article data for blocked articles.

    Attributes
    ----------
    url : str
        Article URL.
    title : str
        Article title.
    summary : str
        Article summary from RSS feed.
    reason : str
        Reason for blocking (e.g., paywall detected).
    """

    url: str
    title: str
    summary: str
    reason: str


class SessionStats(BaseModel):
    """Session statistics.

    Attributes
    ----------
    total : int
        Total number of articles fetched from RSS.
    duplicates : int
        Number of duplicate articles filtered.
    accessible : int
        Number of accessible articles.
    """

    total: int
    duplicates: int
    accessible: int


# ---------------------------------------------------------------------------
# filter_by_date
# ---------------------------------------------------------------------------

_logger = get_logger(__name__)


def filter_by_date(
    items: list[dict[str, Any]],
    days: int,
) -> list[dict[str, Any]]:
    """Filter items to only those published within the specified number of days.

    Parameters
    ----------
    items : list[dict[str, Any]]
        List of RSS items.  Each item is expected to contain a ``published``
        key with an ISO 8601 timestamp string.
    days : int
        Number of days to look back from *now* (UTC).

    Returns
    -------
    list[dict[str, Any]]
        Filtered list of items whose ``published`` date falls within the
        look-back window.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    filtered: list[dict[str, Any]] = []

    for item in items:
        published_str = item.get("published")
        if not published_str:
            continue

        try:
            published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
            if published >= cutoff:
                filtered.append(item)
        except (ValueError, TypeError) as exc:
            _logger.debug(
                "failed_to_parse_date",
                published_str=published_str,
                error=str(exc),
            )

    _logger.debug(
        "date_filter_applied",
        input_count=len(items),
        output_count=len(filtered),
        days=days,
    )

    return filtered


# ---------------------------------------------------------------------------
# select_top_n
# ---------------------------------------------------------------------------


def select_top_n(
    items: list[dict[str, Any]],
    top_n: int,
) -> list[dict[str, Any]]:
    """Select top *N* articles sorted by published date (newest first).

    Parameters
    ----------
    items : list[dict[str, Any]]
        List of RSS items.
    top_n : int
        Maximum number of articles to return.  If ``<= 0`` the full list is
        returned unchanged.

    Returns
    -------
    list[dict[str, Any]]
        Top *N* articles sorted newest-first.
    """
    if top_n <= 0:
        return items

    sorted_items = sorted(
        items,
        key=lambda x: x.get("published", ""),
        reverse=True,
    )

    selected = sorted_items[:top_n]

    _logger.debug(
        "top_n_selected",
        input_count=len(items),
        output_count=len(selected),
        top_n=top_n,
    )

    return selected


# ---------------------------------------------------------------------------
# write_session_file
# ---------------------------------------------------------------------------


def write_session_file(session: BaseModel, output_path: Path) -> None:
    """Write a Pydantic session model to a JSON file.

    The parent directory is created automatically if it does not exist.

    Parameters
    ----------
    session : BaseModel
        Session data to serialise.  ``model_dump()`` is called internally.
    output_path : Path
        Destination file path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(session.model_dump(), f, ensure_ascii=False, indent=2)

    _logger.info("session_file_written", path=str(output_path))
