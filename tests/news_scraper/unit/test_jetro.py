"""Unit tests for src/news_scraper/jetro.py.

Tests cover the internal helper functions and the main collect_news entry point.
HTTP calls are mocked via unittest.mock to avoid real network access.

Wave 1: TestParseJetroDate is fully implemented.
Wave 2: Remaining test classes will be completed.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from news_scraper.jetro import _parse_jetro_date

# ---------------------------------------------------------------------------
# TestParseJetroDate — Wave 1 (fully implemented)
# ---------------------------------------------------------------------------


class TestParseJetroDate:
    """Tests for _parse_jetro_date which handles RFC 2822 and Japanese dates."""

    def test_正常系_RFC2822形式をパースしてUTCに変換(self) -> None:
        """RSS feed の RFC 2822 日付文字列を UTC datetime に変換する。"""
        date_str = "Mon, 18 Mar 2026 09:00:00 +0900"
        result = _parse_jetro_date(date_str)
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 18
        # 09:00 JST (+0900) = 00:00 UTC
        assert result.hour == 0
        assert result.tzinfo == timezone.utc

    def test_正常系_日本語日付形式をパース(self) -> None:
        """HTML ページの「YYYY年MM月DD日」形式をパースする。"""
        date_str = "2026年03月18日"
        result = _parse_jetro_date(date_str)
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 18
        assert result.tzinfo is not None

    def test_正常系_Noneで現在時刻を返す(self) -> None:
        """None を渡すと現在の UTC 時刻を返す。"""
        before = datetime.now(timezone.utc)
        result = _parse_jetro_date(None)
        after = datetime.now(timezone.utc)
        assert before <= result <= after
        assert result.tzinfo is not None


# ---------------------------------------------------------------------------
# TestEntryToArticle — Wave 2 (stub)
# ---------------------------------------------------------------------------


class TestEntryToArticle:
    """Tests for _entry_to_article (JETRO RSS entry -> Article).

    Wave 2 で実装予定。
    """

    @pytest.mark.skip(reason="Wave 2 で実装")
    def test_正常系_有効なエントリからArticleを生成(self) -> None:
        raise NotImplementedError

    @pytest.mark.skip(reason="Wave 2 で実装")
    def test_異常系_title欠落でNoneを返す(self) -> None:
        raise NotImplementedError

    @pytest.mark.skip(reason="Wave 2 で実装")
    def test_異常系_url欠落でNoneを返す(self) -> None:
        raise NotImplementedError

    @pytest.mark.skip(reason="Wave 2 で実装")
    def test_正常系_カテゴリがArticleに設定される(self) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# TestExtractArticleContent — Wave 2 (stub)
# ---------------------------------------------------------------------------


class TestExtractArticleContent:
    """Tests for _extract_article_content (JETRO HTML page -> text).

    Wave 2 で実装予定。
    """

    @pytest.mark.skip(reason="Wave 2 で実装")
    def test_正常系_記事本文を抽出(self) -> None:
        raise NotImplementedError

    @pytest.mark.skip(reason="Wave 2 で実装")
    def test_異常系_接続エラーでNoneを返す(self) -> None:
        raise NotImplementedError

    @pytest.mark.skip(reason="Wave 2 で実装")
    def test_異常系_セレクタ不一致でNoneを返す(self) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# TestCollectNews — Wave 2 (stub)
# ---------------------------------------------------------------------------


class TestCollectNews:
    """Tests for collect_news (main JETRO entry point).

    Wave 2 で実装予定。
    """

    @pytest.mark.skip(reason="Wave 2 で実装")
    def test_正常系_RSSフィードから記事を収集(self) -> None:
        raise NotImplementedError

    @pytest.mark.skip(reason="Wave 2 で実装")
    def test_正常系_max_per_sourceで記事数を制限(self) -> None:
        raise NotImplementedError

    @pytest.mark.skip(reason="Wave 2 で実装")
    def test_異常系_フィード取得失敗で空リストを返す(self) -> None:
        raise NotImplementedError

    @pytest.mark.skip(reason="Wave 2 で実装")
    def test_正常系_カテゴリページから記事を収集(self) -> None:
        raise NotImplementedError
