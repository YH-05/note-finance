"""Tests for scripts/session_utils.py.

汎用関数・Pydanticモデルの単体テスト。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from pathlib import Path

from session_utils import (
    ArticleData,
    BlockedArticle,
    SessionStats,
    filter_by_date,
    get_logger,
    select_top_n,
    write_session_file,
)

# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------


class TestArticleData:
    """ArticleData モデルのテスト。"""

    def test_正常系_全フィールド指定で生成できる(self) -> None:
        article = ArticleData(
            url="https://example.com/article/1",
            title="Test Article",
            summary="A test summary",
            feed_source="Test Feed",
            published="2026-03-01T00:00:00+00:00",
        )
        assert article.url == "https://example.com/article/1"
        assert article.title == "Test Article"
        assert article.summary == "A test summary"
        assert article.feed_source == "Test Feed"
        assert article.published == "2026-03-01T00:00:00+00:00"

    def test_正常系_model_dumpでdict変換できる(self) -> None:
        article = ArticleData(
            url="https://example.com/1",
            title="T",
            summary="S",
            feed_source="F",
            published="2026-03-01T00:00:00+00:00",
        )
        dumped = article.model_dump()
        assert isinstance(dumped, dict)
        assert dumped["url"] == "https://example.com/1"


class TestBlockedArticle:
    """BlockedArticle モデルのテスト。"""

    def test_正常系_全フィールド指定で生成できる(self) -> None:
        blocked = BlockedArticle(
            url="https://example.com/blocked",
            title="Blocked Article",
            summary="Blocked summary",
            reason="paywall detected",
        )
        assert blocked.url == "https://example.com/blocked"
        assert blocked.reason == "paywall detected"


class TestSessionStats:
    """SessionStats モデルのテスト。"""

    def test_正常系_統計データを保持できる(self) -> None:
        stats = SessionStats(total=100, duplicates=20, accessible=80)
        assert stats.total == 100
        assert stats.duplicates == 20
        assert stats.accessible == 80


# ---------------------------------------------------------------------------
# filter_by_date
# ---------------------------------------------------------------------------


class TestFilterByDate:
    """filter_by_date 関数のテスト。"""

    def _make_item(self, days_ago: int) -> dict[str, Any]:
        """指定日数前の published を持つアイテムを生成。"""
        dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
        return {
            "title": f"Article {days_ago} days ago",
            "link": f"https://example.com/{days_ago}",
            "published": dt.isoformat(),
            "summary": "test",
        }

    def test_正常系_期間内の記事のみ返す(self) -> None:
        items = [
            self._make_item(1),  # 1日前 → 含まれる
            self._make_item(3),  # 3日前 → 含まれる
            self._make_item(10),  # 10日前 → 含まれない
        ]
        result = filter_by_date(items, days=7)
        assert len(result) == 2

    def test_正常系_全て期間外なら空リスト(self) -> None:
        items = [self._make_item(30), self._make_item(60)]
        result = filter_by_date(items, days=7)
        assert result == []

    def test_エッジケース_空リストで空結果(self) -> None:
        result = filter_by_date([], days=7)
        assert result == []

    def test_エッジケース_publishedがNoneの記事はスキップ(self) -> None:
        items = [{"title": "No date", "link": "https://example.com/nodate"}]
        result = filter_by_date(items, days=7)
        assert result == []

    def test_エッジケース_不正な日付文字列はスキップ(self) -> None:
        items = [
            {
                "title": "Bad date",
                "link": "https://example.com/bad",
                "published": "not-a-date",
            }
        ]
        result = filter_by_date(items, days=7)
        assert result == []


# ---------------------------------------------------------------------------
# select_top_n
# ---------------------------------------------------------------------------


class TestSelectTopN:
    """select_top_n 関数のテスト。"""

    def test_正常系_上位N件を新しい順に返す(self) -> None:
        items = [
            {"title": "Old", "published": "2026-01-01T00:00:00+00:00"},
            {"title": "New", "published": "2026-03-01T00:00:00+00:00"},
            {"title": "Mid", "published": "2026-02-01T00:00:00+00:00"},
        ]
        result = select_top_n(items, top_n=2)
        assert len(result) == 2
        assert result[0]["title"] == "New"
        assert result[1]["title"] == "Mid"

    def test_正常系_top_nが件数以上なら全件返す(self) -> None:
        items = [
            {"title": "A", "published": "2026-01-01T00:00:00+00:00"},
            {"title": "B", "published": "2026-02-01T00:00:00+00:00"},
        ]
        result = select_top_n(items, top_n=10)
        assert len(result) == 2

    def test_エッジケース_top_nが0以下なら全件返す(self) -> None:
        items = [
            {"title": "A", "published": "2026-01-01T00:00:00+00:00"},
        ]
        result = select_top_n(items, top_n=0)
        assert len(result) == 1

    def test_エッジケース_空リストで空結果(self) -> None:
        result = select_top_n([], top_n=5)
        assert result == []


# ---------------------------------------------------------------------------
# write_session_file
# ---------------------------------------------------------------------------


class TestWriteSessionFile:
    """write_session_file 関数のテスト。"""

    def test_正常系_JSONファイルが作成される(self, tmp_path: Path) -> None:
        # AIDEV-NOTE: NewsSession は prepare_news_session.py に残るため、
        # ここでは write_session_file のインターフェースに合わせたモックを使う
        session = MagicMock()
        session.model_dump.return_value = {
            "session_id": "news-20260306-120000",
            "timestamp": "2026-03-06T12:00:00+00:00",
            "themes": {},
            "stats": {"total": 0, "duplicates": 0, "accessible": 0},
        }

        output_path = tmp_path / "sub" / "test-session.json"
        write_session_file(session, output_path)

        assert output_path.exists()
        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert data["session_id"] == "news-20260306-120000"

    def test_正常系_日本語が正しくエンコードされる(self, tmp_path: Path) -> None:
        session = MagicMock()
        session.model_dump.return_value = {"title": "日本語テスト"}

        output_path = tmp_path / "jp-test.json"
        write_session_file(session, output_path)

        content = output_path.read_text(encoding="utf-8")
        assert "日本語テスト" in content
        # ensure_ascii=False check
        assert "\\u" not in content


# ---------------------------------------------------------------------------
# get_logger
# ---------------------------------------------------------------------------


class TestGetLogger:
    """get_logger 関数のテスト。"""

    def test_正常系_ロガーが返される(self) -> None:
        log = get_logger("test_module")
        assert log is not None
