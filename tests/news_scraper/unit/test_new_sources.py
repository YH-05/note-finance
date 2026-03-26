"""Unit tests for Wave2 new source modules.

Tests cover FEEDS constants and the async collect_news entry points for:
- techcrunch
- ars_technica
- the_verge
- hacker_news
- federal_reserve
- zero_hedge

Network calls are mocked via unittest.mock. Each module delegates to
``news_scraper._rss_fetcher.fetch_rss_feeds``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from news_scraper.ars_technica import FEEDS as ARS_FEEDS
from news_scraper.ars_technica import collect_news as ars_collect
from news_scraper.federal_reserve import FEEDS as FED_FEEDS
from news_scraper.federal_reserve import collect_news as fed_collect
from news_scraper.hacker_news import FEEDS as HN_FEEDS
from news_scraper.hacker_news import collect_news as hn_collect
from news_scraper.techcrunch import FEEDS as TC_FEEDS
from news_scraper.techcrunch import collect_news as tc_collect
from news_scraper.the_verge import FEEDS as VERGE_FEEDS
from news_scraper.the_verge import collect_news as verge_collect
from news_scraper.types import ScraperConfig
from news_scraper.zero_hedge import FEEDS as ZH_FEEDS
from news_scraper.zero_hedge import collect_news as zh_collect

# ---------------------------------------------------------------------------
# FEEDS 定数テスト
# ---------------------------------------------------------------------------


class TestFeedsConstants:
    def test_正常系_techcrunch_feedsが1件定義されている(self) -> None:
        assert len(TC_FEEDS) == 1

    def test_正常系_techcrunch_urlがtechcrunchドメイン(self) -> None:
        for url in TC_FEEDS.values():
            assert "techcrunch.com" in url

    def test_正常系_the_verge_feedsが1件定義されている(self) -> None:
        assert len(VERGE_FEEDS) == 1

    def test_正常系_the_verge_urlがthevergeドメイン(self) -> None:
        for url in VERGE_FEEDS.values():
            assert "theverge.com" in url

    def test_正常系_hacker_news_feedsが1件定義されている(self) -> None:
        assert len(HN_FEEDS) == 1

    def test_正常系_hacker_news_urlがhnrssドメイン(self) -> None:
        for url in HN_FEEDS.values():
            assert "hnrss.org" in url

    def test_正常系_federal_reserve_feedsが1件定義されている(self) -> None:
        assert len(FED_FEEDS) == 1

    def test_正常系_federal_reserve_urlがfederalreserveドメイン(self) -> None:
        for url in FED_FEEDS.values():
            assert "federalreserve.gov" in url

    def test_正常系_ars_technica_feedsが1件定義されている(self) -> None:
        assert len(ARS_FEEDS) == 1

    def test_正常系_ars_technica_urlがarstechnicaドメイン(self) -> None:
        for url in ARS_FEEDS.values():
            assert "arstechnica.com" in url

    def test_正常系_zero_hedge_feedsが1件定義されている(self) -> None:
        assert len(ZH_FEEDS) == 1

    def test_正常系_zero_hedge_urlがzerohedgeまたはfeedburnドメイン(self) -> None:
        for url in ZH_FEEDS.values():
            assert "zerohedge" in url or "feedburner" in url


# ---------------------------------------------------------------------------
# collect_news 委譲テスト（共通パターン）
# ---------------------------------------------------------------------------


class TestTechcrunchCollectNews:
    @pytest.mark.asyncio
    async def test_正常系_fetch_rss_feedsに委譲する(self) -> None:
        with patch(
            "news_scraper.techcrunch.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await tc_collect()

        mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_正常系_source_nameがtechcrunch(self) -> None:
        with patch(
            "news_scraper.techcrunch.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await tc_collect()

        assert mock_fetch.call_args.kwargs.get("source_name") == "techcrunch"

    @pytest.mark.asyncio
    async def test_正常系_content_fieldがentry_summary(self) -> None:
        with patch(
            "news_scraper.techcrunch.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await tc_collect()

        assert mock_fetch.call_args.kwargs.get("content_field") == "entry.summary"
        assert mock_fetch.call_args.kwargs.get("content_is_html") is False

    @pytest.mark.asyncio
    async def test_正常系_configNoneでデフォルト設定を使用(self) -> None:
        with patch(
            "news_scraper.techcrunch.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await tc_collect(config=None)

        config_arg = mock_fetch.call_args.args[1]
        assert isinstance(config_arg, ScraperConfig)


class TestTheVergeCollectNews:
    @pytest.mark.asyncio
    async def test_正常系_fetch_rss_feedsに委譲する(self) -> None:
        with patch(
            "news_scraper.the_verge.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await verge_collect()

        mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_正常系_source_nameがthe_verge(self) -> None:
        with patch(
            "news_scraper.the_verge.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await verge_collect()

        assert mock_fetch.call_args.kwargs.get("source_name") == "the_verge"

    @pytest.mark.asyncio
    async def test_正常系_content_fieldがentry_summary(self) -> None:
        with patch(
            "news_scraper.the_verge.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await verge_collect()

        assert mock_fetch.call_args.kwargs.get("content_field") == "entry.summary"
        assert mock_fetch.call_args.kwargs.get("content_is_html") is False

    @pytest.mark.asyncio
    async def test_正常系_configNoneでデフォルト設定を使用(self) -> None:
        with patch(
            "news_scraper.the_verge.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await verge_collect(config=None)

        config_arg = mock_fetch.call_args.args[1]
        assert isinstance(config_arg, ScraperConfig)


class TestHackerNewsCollectNews:
    @pytest.mark.asyncio
    async def test_正常系_fetch_rss_feedsに委譲する(self) -> None:
        with patch(
            "news_scraper.hacker_news.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await hn_collect()

        mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_正常系_source_nameがhacker_news(self) -> None:
        with patch(
            "news_scraper.hacker_news.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await hn_collect()

        assert mock_fetch.call_args.kwargs.get("source_name") == "hacker_news"

    @pytest.mark.asyncio
    async def test_正常系_content_fieldがentry_summary(self) -> None:
        with patch(
            "news_scraper.hacker_news.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await hn_collect()

        assert mock_fetch.call_args.kwargs.get("content_field") == "entry.summary"
        assert mock_fetch.call_args.kwargs.get("content_is_html") is False

    @pytest.mark.asyncio
    async def test_正常系_configNoneでデフォルト設定を使用(self) -> None:
        with patch(
            "news_scraper.hacker_news.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await hn_collect(config=None)

        config_arg = mock_fetch.call_args.args[1]
        assert isinstance(config_arg, ScraperConfig)


class TestFederalReserveCollectNews:
    @pytest.mark.asyncio
    async def test_正常系_fetch_rss_feedsに委譲する(self) -> None:
        with patch(
            "news_scraper.federal_reserve.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await fed_collect()

        mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_正常系_source_nameがfederal_reserve(self) -> None:
        with patch(
            "news_scraper.federal_reserve.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await fed_collect()

        assert mock_fetch.call_args.kwargs.get("source_name") == "federal_reserve"

    @pytest.mark.asyncio
    async def test_正常系_content_fieldがentry_summary(self) -> None:
        with patch(
            "news_scraper.federal_reserve.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await fed_collect()

        assert mock_fetch.call_args.kwargs.get("content_field") == "entry.summary"
        assert mock_fetch.call_args.kwargs.get("content_is_html") is False

    @pytest.mark.asyncio
    async def test_正常系_configNoneでデフォルト設定を使用(self) -> None:
        with patch(
            "news_scraper.federal_reserve.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await fed_collect(config=None)

        config_arg = mock_fetch.call_args.args[1]
        assert isinstance(config_arg, ScraperConfig)


class TestArsTechnicaCollectNews:
    @pytest.mark.asyncio
    async def test_正常系_fetch_rss_feedsに委譲する(self) -> None:
        with patch(
            "news_scraper.ars_technica.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await ars_collect()

        mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_正常系_source_nameがars_technica(self) -> None:
        with patch(
            "news_scraper.ars_technica.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await ars_collect()

        assert mock_fetch.call_args.kwargs.get("source_name") == "ars_technica"

    @pytest.mark.asyncio
    async def test_正常系_content_fieldがentry_content_0_value(self) -> None:
        with patch(
            "news_scraper.ars_technica.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await ars_collect()

        assert (
            mock_fetch.call_args.kwargs.get("content_field") == "entry.content[0].value"
        )

    @pytest.mark.asyncio
    async def test_正常系_content_is_htmlがFalse(self) -> None:
        with patch(
            "news_scraper.ars_technica.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await ars_collect()

        assert mock_fetch.call_args.kwargs.get("content_is_html") is False

    @pytest.mark.asyncio
    async def test_正常系_configNoneでデフォルト設定を使用(self) -> None:
        with patch(
            "news_scraper.ars_technica.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await ars_collect(config=None)

        config_arg = mock_fetch.call_args.args[1]
        assert isinstance(config_arg, ScraperConfig)


class TestZeroHedgeCollectNews:
    @pytest.mark.asyncio
    async def test_正常系_fetch_rss_feedsに委譲する(self) -> None:
        with patch(
            "news_scraper.zero_hedge.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await zh_collect()

        mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_正常系_source_nameがzero_hedge(self) -> None:
        with patch(
            "news_scraper.zero_hedge.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await zh_collect()

        assert mock_fetch.call_args.kwargs.get("source_name") == "zero_hedge"

    @pytest.mark.asyncio
    async def test_正常系_content_is_htmlがTrue(self) -> None:
        """ZeroHedge の summary は HTML なので content_is_html=True を確認する."""
        with patch(
            "news_scraper.zero_hedge.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await zh_collect()

        assert mock_fetch.call_args.kwargs.get("content_is_html") is True

    @pytest.mark.asyncio
    async def test_正常系_content_fieldがentry_summary(self) -> None:
        with patch(
            "news_scraper.zero_hedge.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await zh_collect()

        assert mock_fetch.call_args.kwargs.get("content_field") == "entry.summary"

    @pytest.mark.asyncio
    async def test_正常系_configNoneでデフォルト設定を使用(self) -> None:
        with patch(
            "news_scraper.zero_hedge.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await zh_collect(config=None)

        config_arg = mock_fetch.call_args.args[1]
        assert isinstance(config_arg, ScraperConfig)
