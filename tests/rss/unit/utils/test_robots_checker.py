"""Unit tests for RobotsChecker.

Tests cover:
- Allow/deny judgment for robots.txt rules
- crawl_delay retrieval
- Non-standard ai-directive detection (ai-train, GPTBot, CCBot)
- Fallback to allow-all on fetch failure
- Domain-level caching
- Frozen dataclass RobotsCheckResult
"""

from __future__ import annotations

import dataclasses
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rss.utils.robots_checker import RobotsChecker, RobotsCheckResult

# ---------------------------------------------------------------------------
# RobotsCheckResult dataclass tests
# ---------------------------------------------------------------------------


class TestRobotsCheckResult:
    """Test RobotsCheckResult frozen dataclass."""

    def test_正常系_デフォルト値で生成できる(self) -> None:
        result = RobotsCheckResult(url="https://example.com/article")
        assert result.url == "https://example.com/article"
        assert result.allowed is True
        assert result.crawl_delay is None
        assert result.ai_directives == {}
        assert result.error is None

    def test_正常系_全フィールドを指定して生成できる(self) -> None:
        result = RobotsCheckResult(
            url="https://example.com/article",
            allowed=False,
            crawl_delay=30.0,
            ai_directives={"ai-train": "no"},
            error=None,
        )
        assert result.url == "https://example.com/article"
        assert result.allowed is False
        assert result.crawl_delay == 30.0
        assert result.ai_directives == {"ai-train": "no"}

    def test_正常系_frozenなので変更不可(self) -> None:
        result = RobotsCheckResult(url="https://example.com/article")
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            result.allowed = False  # type: ignore[misc]

    def test_正常系_エラー情報を持てる(self) -> None:
        result = RobotsCheckResult(
            url="https://example.com/article",
            allowed=True,
            error="Connection timeout",
        )
        assert result.error == "Connection timeout"


# ---------------------------------------------------------------------------
# RobotsChecker initialization tests
# ---------------------------------------------------------------------------


class TestRobotsCheckerInit:
    """Test RobotsChecker initialization."""

    def test_正常系_デフォルトユーザーエージェントで初期化(self) -> None:
        checker = RobotsChecker()
        assert checker.user_agent == "rss-feed-collector/0.1.0"

    def test_正常系_カスタムユーザーエージェントで初期化(self) -> None:
        checker = RobotsChecker(user_agent="MyBot/1.0")
        assert checker.user_agent == "MyBot/1.0"

    def test_正常系_キャッシュが空で初期化される(self) -> None:
        checker = RobotsChecker()
        assert len(checker._cache) == 0


# ---------------------------------------------------------------------------
# RobotsChecker.check() tests
# ---------------------------------------------------------------------------

ROBOTS_TXT_ALLOW_ALL = """\
User-agent: *
Allow: /
"""

ROBOTS_TXT_DENY_ALL = """\
User-agent: *
Disallow: /
"""

ROBOTS_TXT_WITH_CRAWL_DELAY = """\
User-agent: *
Allow: /
Crawl-delay: 10
"""

ROBOTS_TXT_CLAUDEBOT_BLOCKED = """\
User-agent: ClaudeBot
Disallow: /

User-agent: *
Allow: /
"""

ROBOTS_TXT_AI_TRAIN_NO = """\
User-agent: *
Allow: /
Crawl-delay: 5

# Non-standard directives
ai-train: no
GPTBot: no
CCBot: no
"""

ROBOTS_TXT_MIXED = """\
User-agent: *
Disallow: /private/
Allow: /public/
Crawl-delay: 2

ai-train: yes
GPTBot: no
"""


class TestRobotsCheckerCheck:
    """Test RobotsChecker.check() method."""

    @pytest.fixture
    def checker(self) -> RobotsChecker:
        return RobotsChecker(user_agent="rss-feed-collector/0.1.0")

    @pytest.mark.asyncio
    async def test_正常系_全許可のrobotsTxtでallowedがTrue(
        self, checker: RobotsChecker
    ) -> None:
        """Test that allow-all robots.txt returns allowed=True."""
        with patch.object(
            checker, "_fetch_robots_txt", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = ROBOTS_TXT_ALLOW_ALL
            result = await checker.check("https://example.com/article")

        assert result.allowed is True
        assert result.url == "https://example.com/article"
        assert result.error is None

    @pytest.mark.asyncio
    async def test_正常系_全禁止のrobotsTxtでallowedがFalse(
        self, checker: RobotsChecker
    ) -> None:
        """Test that disallow-all robots.txt returns allowed=False."""
        with patch.object(
            checker, "_fetch_robots_txt", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = ROBOTS_TXT_DENY_ALL
            result = await checker.check("https://example.com/article")

        assert result.allowed is False
        assert result.error is None

    @pytest.mark.asyncio
    async def test_正常系_crawlDelayが正しく取得される(
        self, checker: RobotsChecker
    ) -> None:
        """Test that Crawl-delay is correctly extracted."""
        with patch.object(
            checker, "_fetch_robots_txt", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = ROBOTS_TXT_WITH_CRAWL_DELAY
            result = await checker.check("https://example.com/article")

        assert result.allowed is True
        assert result.crawl_delay == 10.0

    @pytest.mark.asyncio
    async def test_正常系_ClaudeBotがブロックされている場合はFalse(
        self, checker: RobotsChecker
    ) -> None:
        """Test that ClaudeBot-specific block returns allowed=False."""
        checker_claudebot = RobotsChecker(user_agent="ClaudeBot")
        with patch.object(
            checker_claudebot, "_fetch_robots_txt", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = ROBOTS_TXT_CLAUDEBOT_BLOCKED
            result = await checker_claudebot.check("https://example.com/article")

        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_正常系_aiTrainNoディレクティブが検出される(
        self, checker: RobotsChecker
    ) -> None:
        """Test that non-standard ai-train=no directive is detected."""
        with patch.object(
            checker, "_fetch_robots_txt", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = ROBOTS_TXT_AI_TRAIN_NO
            result = await checker.check("https://example.com/article")

        assert result.ai_directives.get("ai-train") == "no"
        assert result.ai_directives.get("GPTBot") == "no"
        assert result.ai_directives.get("CCBot") == "no"

    @pytest.mark.asyncio
    async def test_正常系_取得失敗時はデフォルト許可で動作する(
        self, checker: RobotsChecker
    ) -> None:
        """Test that fetch failure falls back to allow-all with error recorded."""
        with patch.object(
            checker, "_fetch_robots_txt", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.side_effect = Exception("Connection refused")
            result = await checker.check("https://example.com/article")

        assert result.allowed is True
        assert result.error is not None
        assert "Connection refused" in result.error

    @pytest.mark.asyncio
    async def test_正常系_ドメインキャッシュが機能する(
        self, checker: RobotsChecker
    ) -> None:
        """Test that domain-level caching prevents redundant fetches."""
        with patch.object(
            checker, "_fetch_robots_txt", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = ROBOTS_TXT_ALLOW_ALL

            # Call twice with same domain, different paths
            result1 = await checker.check("https://example.com/article1")
            result2 = await checker.check("https://example.com/article2")

        # robots.txt should only be fetched once (cached)
        assert mock_fetch.call_count == 1
        assert result1.allowed is True
        assert result2.allowed is True

    @pytest.mark.asyncio
    async def test_正常系_異なるドメインはそれぞれ取得される(
        self, checker: RobotsChecker
    ) -> None:
        """Test that different domains fetch their own robots.txt."""
        with patch.object(
            checker, "_fetch_robots_txt", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = ROBOTS_TXT_ALLOW_ALL

            await checker.check("https://example.com/article")
            await checker.check("https://other.com/article")

        assert mock_fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_正常系_混合ディレクティブの解析が正しく動作する(
        self, checker: RobotsChecker
    ) -> None:
        """Test correct parsing of mixed standard and non-standard directives."""
        with patch.object(
            checker, "_fetch_robots_txt", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = ROBOTS_TXT_MIXED
            result = await checker.check("https://example.com/public/article")

        assert result.allowed is True
        assert result.crawl_delay == 2.0
        assert result.ai_directives.get("ai-train") == "yes"
        assert result.ai_directives.get("GPTBot") == "no"


# ---------------------------------------------------------------------------
# RobotsChecker.get_crawl_delay() tests
# ---------------------------------------------------------------------------


class TestRobotsCheckerGetCrawlDelay:
    """Test RobotsChecker.get_crawl_delay() method."""

    @pytest.fixture
    def checker(self) -> RobotsChecker:
        return RobotsChecker()

    @pytest.mark.asyncio
    async def test_正常系_キャッシュ済みドメインのcrawlDelayを返す(
        self, checker: RobotsChecker
    ) -> None:
        """Test get_crawl_delay returns cached crawl delay."""
        with patch.object(
            checker, "_fetch_robots_txt", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = ROBOTS_TXT_WITH_CRAWL_DELAY
            await checker.check("https://example.com/article")

        delay = checker.get_crawl_delay("example.com")
        assert delay == 10.0

    def test_正常系_未キャッシュドメインはNoneを返す(
        self, checker: RobotsChecker
    ) -> None:
        """Test get_crawl_delay returns None for unknown domain."""
        delay = checker.get_crawl_delay("unknown.com")
        assert delay is None
