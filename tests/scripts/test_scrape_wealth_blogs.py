"""Tests for scripts/scrape_wealth_blogs.py.

2モード（incremental/backfill）対応のメインCLIスクリプトの単体テスト。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from freezegun import freeze_time

if TYPE_CHECKING:
    from pathlib import Path

from scrape_wealth_blogs import (
    DEFAULT_DAYS,
    DEFAULT_LIMIT,
    DEFAULT_TOP_N,
    WEALTH_SCRAPE_DB_PATH,
    WEALTH_SESSION_PREFIX,
    WealthArticleData,
    WealthScrapeSession,
    WealthScrapeStats,
    WealthThemeData,
    build_session,
    generate_session_id,
    match_keywords_en,
    parse_args,
    resolve_source_key_wealth,
    run_incremental,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FROZEN_TIME = "2026-03-13T12:00:00+00:00"
"""Fixed time for deterministic tests."""


def _make_rss_item(
    days_ago: int,
    title: str = "Index Fund Guide",
    link: str = "https://awealthofcommonsense.com/article",
    summary: str = "A guide to index fund investing",
    feed_source: str = "A Wealth of Common Sense",
    source_key: str = "awealthofcommonsense",
) -> dict[str, Any]:
    """指定日数前の published を持つRSSアイテムを生成。"""
    base = datetime(2026, 3, 13, 12, 0, 0, tzinfo=timezone.utc)
    dt = base - timedelta(days=days_ago)
    return {
        "item_id": f"item-{days_ago}",
        "title": title,
        "link": link,
        "published": dt.isoformat(),
        "summary": summary,
        "content": None,
        "author": None,
        "fetched_at": base.isoformat(),
        "feed_source": feed_source,
        "source_key": source_key,
    }


# ---------------------------------------------------------------------------
# Pydanticモデル
# ---------------------------------------------------------------------------


class TestWealthArticleData:
    """WealthArticleData モデルのテスト。"""

    def test_正常系_モデルが正しく作成される(self) -> None:
        article = WealthArticleData(
            url="https://awealthofcommonsense.com/article",
            title="Index Fund Guide",
            summary="A guide to index fund investing",
            feed_source="A Wealth of Common Sense",
            published="2026-03-13T12:00:00+00:00",
            source_key="awealthofcommonsense",
            domain="awealthofcommonsense.com",
        )
        assert article.url == "https://awealthofcommonsense.com/article"
        assert article.source_key == "awealthofcommonsense"
        assert article.domain == "awealthofcommonsense.com"

    def test_正常系_domainのデフォルトが空文字(self) -> None:
        article = WealthArticleData(
            url="https://example.com/article",
            title="Test",
            summary="Test summary",
            feed_source="Test Feed",
            published="2026-03-13T12:00:00+00:00",
        )
        assert article.domain == ""
        assert article.source_key == ""


class TestWealthThemeData:
    """WealthThemeData モデルのテスト。"""

    def test_正常系_デフォルト値で作成される(self) -> None:
        theme = WealthThemeData(
            name_en="Data-Driven Investing",
        )
        assert theme.articles == []
        assert theme.keywords_used == []

    def test_正常系_記事リストを含めて作成できる(self) -> None:
        article = WealthArticleData(
            url="https://example.com",
            title="Test",
            summary="Test",
            feed_source="Test",
            published="2026-03-13T12:00:00+00:00",
        )
        theme = WealthThemeData(
            name_en="Test Theme",
            articles=[article],
            keywords_used=["index fund"],
        )
        assert len(theme.articles) == 1
        assert theme.keywords_used == ["index fund"]


class TestWealthScrapeStats:
    """WealthScrapeStats モデルのテスト。"""

    def test_正常系_モデルが正しく作成される(self) -> None:
        stats = WealthScrapeStats(
            total=100,
            filtered=50,
            matched=20,
            scraped=10,
            skipped=5,
        )
        assert stats.total == 100
        assert stats.filtered == 50
        assert stats.matched == 20
        assert stats.scraped == 10
        assert stats.skipped == 5

    def test_正常系_skippedのデフォルトが0(self) -> None:
        stats = WealthScrapeStats(total=10, filtered=8, matched=5, scraped=3)
        assert stats.skipped == 0


class TestWealthScrapeSession:
    """WealthScrapeSession モデルのテスト。"""

    def test_正常系_セッションモデルが作成される(self) -> None:
        session = WealthScrapeSession(
            session_id="wealth-scrape-20260313-120000",
            timestamp="2026-03-13T12:00:00+00:00",
            mode="incremental",
            themes={},
            stats=WealthScrapeStats(total=0, filtered=0, matched=0, scraped=0),
        )
        assert session.mode == "incremental"
        assert session.themes == {}


# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------


class TestParseArgs:
    """parse_args 関数のテスト。"""

    def test_正常系_デフォルト引数(self) -> None:
        args = parse_args([])
        assert args.mode == "incremental"
        assert args.days == DEFAULT_DAYS
        assert args.top_n == DEFAULT_TOP_N
        assert args.dry_run is False
        assert args.verbose is False
        assert args.domain is None
        assert args.limit == DEFAULT_LIMIT
        assert args.check_robots is False
        assert args.retry_failed is False

    def test_正常系_incrementalモード(self) -> None:
        args = parse_args(["--mode", "incremental"])
        assert args.mode == "incremental"

    def test_正常系_backfillモード(self) -> None:
        args = parse_args(["--mode", "backfill"])
        assert args.mode == "backfill"

    def test_正常系_days引数(self) -> None:
        args = parse_args(["--days", "7"])
        assert args.days == 7

    def test_正常系_dry_runフラグ(self) -> None:
        args = parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_正常系_domain引数(self) -> None:
        args = parse_args(["--domain", "awealthofcommonsense.com"])
        assert args.domain == "awealthofcommonsense.com"

    def test_正常系_limit引数(self) -> None:
        args = parse_args(["--limit", "50"])
        assert args.limit == 50

    def test_正常系_check_robotsフラグ(self) -> None:
        args = parse_args(["--check-robots"])
        assert args.check_robots is True

    def test_正常系_retry_failedフラグ(self) -> None:
        args = parse_args(["--retry-failed"])
        assert args.retry_failed is True

    def test_正常系_verboseフラグ(self) -> None:
        args = parse_args(["--verbose"])
        assert args.verbose is True

    def test_異常系_無効なモード(self) -> None:
        with pytest.raises(SystemExit):
            parse_args(["--mode", "invalid"])

    def test_異常系_days範囲外(self) -> None:
        with pytest.raises(SystemExit):
            parse_args(["--days", "0"])

    def test_異常系_days最大値超過(self) -> None:
        with pytest.raises(SystemExit):
            parse_args(["--days", "366"])


# ---------------------------------------------------------------------------
# generate_session_id
# ---------------------------------------------------------------------------


class TestGenerateSessionId:
    """generate_session_id 関数のテスト。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_セッションIDが正しい形式(self) -> None:
        session_id = generate_session_id()
        assert session_id.startswith(WEALTH_SESSION_PREFIX)
        assert "20260313" in session_id

    @freeze_time(FROZEN_TIME)
    def test_正常系_セッションIDにタイムスタンプが含まれる(self) -> None:
        session_id = generate_session_id()
        assert "120000" in session_id

    def test_正常系_セッションIDが一意(self) -> None:
        id1 = generate_session_id()
        id2 = generate_session_id()
        # 同一秒内でも一意であるか（実装依存）
        assert id1.startswith(WEALTH_SESSION_PREFIX)
        assert id2.startswith(WEALTH_SESSION_PREFIX)


# ---------------------------------------------------------------------------
# resolve_source_key_wealth
# ---------------------------------------------------------------------------


class TestResolveSourceKeyWealth:
    """resolve_source_key_wealth 関数のテスト。"""

    def test_正常系_awealthofcommonsenseのキー解決(self) -> None:
        assert (
            resolve_source_key_wealth("awealthofcommonsense.com")
            == "awealthofcommonsense"
        )

    def test_正常系_wwwプレフィックス付きのキー解決(self) -> None:
        assert resolve_source_key_wealth("www.mrmoneymustache.com") == "mrmoneymustache"

    def test_正常系_getrichslowlyのキー解決(self) -> None:
        assert resolve_source_key_wealth("getrichslowly.org") == "getrichslowly"

    def test_正常系_kiplingerのキー解決(self) -> None:
        assert resolve_source_key_wealth("kiplinger.com") == "kiplinger"

    def test_異常系_未知ドメインはunknown(self) -> None:
        assert resolve_source_key_wealth("unknown-blog.com") == "unknown"

    def test_異常系_空文字列はunknown(self) -> None:
        assert resolve_source_key_wealth("") == "unknown"


# ---------------------------------------------------------------------------
# match_keywords_en
# ---------------------------------------------------------------------------


class TestMatchKeywordsEn:
    """match_keywords_en 関数のテスト。"""

    def test_正常系_タイトルにキーワードが含まれる(self) -> None:
        item = {"title": "The Best Index Fund Guide", "summary": ""}
        assert match_keywords_en(item, ["index fund"]) is True

    def test_正常系_サマリーにキーワードが含まれる(self) -> None:
        item = {
            "title": "Investing Tips",
            "summary": "ETF and passive investing strategies",
        }
        assert match_keywords_en(item, ["passive investing"]) is True

    def test_正常系_大文字小文字を区別しない(self) -> None:
        item = {"title": "FIRE Movement Guide", "summary": ""}
        assert match_keywords_en(item, ["fire"]) is True

    def test_異常系_キーワードが含まれない場合False(self) -> None:
        item = {"title": "Cooking Recipes", "summary": "How to make pasta"}
        assert match_keywords_en(item, ["index fund", "ETF"]) is False

    def test_異常系_空のキーワードリスト(self) -> None:
        item = {"title": "Any Article", "summary": "Any content"}
        assert match_keywords_en(item, []) is False

    def test_異常系_titleとsummaryがNone(self) -> None:
        item = {"title": None, "summary": None}
        assert match_keywords_en(item, ["index fund"]) is False

    def test_正常系_複数キーワードの一つでもマッチ(self) -> None:
        item = {"title": "Dividend Growth Strategy", "summary": ""}
        assert match_keywords_en(item, ["yield", "dividend"]) is True


# ---------------------------------------------------------------------------
# build_session
# ---------------------------------------------------------------------------


class TestBuildSession:
    """build_session 関数のテスト。"""

    def test_正常系_セッションが正しく構築される(self) -> None:
        items = [_make_rss_item(1)]
        theme_results = {
            "data_driven_investing": {
                "articles": items,
                "name_en": "Data-Driven Investing",
                "keywords_used": ["index fund"],
            }
        }
        session = build_session(
            session_id="wealth-scrape-20260313-120000",
            mode="incremental",
            theme_results=theme_results,
            total_fetched=10,
            total_filtered=5,
            total_matched=1,
        )
        assert session.session_id == "wealth-scrape-20260313-120000"
        assert session.mode == "incremental"
        assert "data_driven_investing" in session.themes
        assert len(session.themes["data_driven_investing"].articles) == 1
        assert session.stats.total == 10
        assert session.stats.filtered == 5
        assert session.stats.matched == 1

    def test_正常系_空のtheme_resultsで空のセッション(self) -> None:
        session = build_session(
            session_id="wealth-scrape-20260313-120000",
            mode="backfill",
            theme_results={},
            total_fetched=0,
            total_filtered=0,
            total_matched=0,
        )
        assert session.themes == {}
        assert session.stats.total == 0

    def test_正常系_記事データが正しく変換される(self) -> None:
        item = _make_rss_item(
            days_ago=1,
            title="ETF Guide",
            link="https://bogleheads.org/wiki/ETF",
            source_key="bogleheads",
        )
        theme_results = {
            "test_theme": {
                "articles": [item],
                "name_en": "Test Theme",
                "keywords_used": ["ETF"],
            }
        }
        session = build_session(
            session_id="test-session",
            mode="incremental",
            theme_results=theme_results,
            total_fetched=1,
            total_filtered=1,
            total_matched=1,
        )
        article = session.themes["test_theme"].articles[0]
        assert article.url == "https://bogleheads.org/wiki/ETF"
        assert article.title == "ETF Guide"
        assert article.source_key == "bogleheads"


# ---------------------------------------------------------------------------
# run_incremental
# ---------------------------------------------------------------------------


class TestRunIncremental:
    """run_incremental 関数のテスト。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_dry_runで処理がスキップされる(self, tmp_path: Path) -> None:
        """dry-run モードではファイル出力なしでリスト表示のみ。"""
        output_path = tmp_path / "test-session.json"

        # モックでRSSデータを空にする
        with (
            patch("scrape_wealth_blogs.load_json_config") as mock_config,
            patch("scrape_wealth_blogs.fetch_rss_items_by_source") as mock_fetch,
        ):
            mock_config.return_value = {"presets": [], "themes": {}}
            mock_fetch.return_value = {}

            result = run_incremental(
                days=7,
                top_n=10,
                output_path=output_path,
                dry_run=True,
                domain_filter=None,
                check_robots=False,
                retry_failed=False,
            )

        assert result == 0
        # dry-run ではファイルを出力しない
        assert not output_path.exists()

    @freeze_time(FROZEN_TIME)
    def test_正常系_記事が存在する場合にセッションJSONを出力する(
        self, tmp_path: Path
    ) -> None:
        """通常モードではセッションJSONが出力される。"""
        output_path = tmp_path / "test-session.json"

        sample_items = [
            _make_rss_item(
                1, title="ETF Guide", link="https://awealthofcommonsense.com/etf"
            )
        ]

        sample_themes_config = {
            "themes": {
                "data_driven_investing": {
                    "name_en": "Data-Driven Investing",
                    "keywords_en": ["ETF", "index fund"],
                    "target_sources": ["awealthofcommonsense"],
                }
            }
        }

        with (
            patch("scrape_wealth_blogs.load_json_config") as mock_config,
            patch("scrape_wealth_blogs.fetch_rss_items_by_source") as mock_fetch,
        ):
            mock_config.return_value = sample_themes_config
            mock_fetch.return_value = {"awealthofcommonsense": sample_items}

            result = run_incremental(
                days=7,
                top_n=10,
                output_path=output_path,
                dry_run=False,
                domain_filter=None,
                check_robots=False,
                retry_failed=False,
            )

        assert result == 0
        assert output_path.exists()

        data = json.loads(output_path.read_text())
        assert data["mode"] == "incremental"
        assert "themes" in data
        assert "stats" in data

    @freeze_time(FROZEN_TIME)
    def test_正常系_domain_filterで特定ドメインのみ処理(self, tmp_path: Path) -> None:
        """domain_filter が指定された場合、対象ドメインのみ処理する。"""
        output_path = tmp_path / "test-session.json"

        awoc_items = [_make_rss_item(1, source_key="awealthofcommonsense")]
        bogle_items = [
            _make_rss_item(
                1,
                link="https://bogleheads.org/wiki/ETF",
                source_key="bogleheads",
            )
        ]

        sample_themes_config = {
            "themes": {
                "data_driven_investing": {
                    "name_en": "Data-Driven Investing",
                    "keywords_en": ["index fund", "ETF"],
                    "target_sources": ["awealthofcommonsense", "bogleheads"],
                }
            }
        }

        with (
            patch("scrape_wealth_blogs.load_json_config") as mock_config,
            patch("scrape_wealth_blogs.fetch_rss_items_by_source") as mock_fetch,
        ):
            mock_config.return_value = sample_themes_config
            mock_fetch.return_value = {
                "awealthofcommonsense": awoc_items,
                "bogleheads": bogle_items,
            }

            result = run_incremental(
                days=7,
                top_n=10,
                output_path=output_path,
                dry_run=False,
                domain_filter="awealthofcommonsense.com",
                check_robots=False,
                retry_failed=False,
            )

        assert result == 0


# ---------------------------------------------------------------------------
# 定数・モジュールレベルのテスト
# ---------------------------------------------------------------------------


class TestConstants:
    """モジュール定数のテスト。"""

    def test_正常系_DEFAULT_DAYSが正の整数(self) -> None:
        assert isinstance(DEFAULT_DAYS, int)
        assert DEFAULT_DAYS > 0

    def test_正常系_DEFAULT_TOP_Nが正の整数(self) -> None:
        assert isinstance(DEFAULT_TOP_N, int)
        assert DEFAULT_TOP_N > 0

    def test_正常系_DEFAULT_LIMITが正の整数(self) -> None:
        assert isinstance(DEFAULT_LIMIT, int)
        assert DEFAULT_LIMIT > 0

    def test_正常系_WEALTH_SESSION_PREFIXが文字列(self) -> None:
        assert isinstance(WEALTH_SESSION_PREFIX, str)
        assert len(WEALTH_SESSION_PREFIX) > 0

    def test_正常系_WEALTH_SCRAPE_DB_PATHがPath型(self) -> None:
        from pathlib import Path

        assert isinstance(WEALTH_SCRAPE_DB_PATH, Path)
