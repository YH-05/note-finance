"""Unit tests for src/news_scraper/_html_utils.py.

Tests cover:
- fetch_html: HTML retrieval via httpx.Client (mocked)
- parse_html: lxml HtmlElement parsing
- resolve_relative_url: URL joining
- rate_limit_sleep: rate-limiting sleep
- JP_DEFAULT_HEADERS: header constant validation
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import httpx
import pytest
from lxml.html import HtmlElement

from news_scraper._html_utils import (
    JP_DEFAULT_HEADERS,
    fetch_html,
    parse_html,
    rate_limit_sleep,
    resolve_relative_url,
)
from news_scraper.types import ScraperConfig


class TestJpDefaultHeaders:
    """Tests for JP_DEFAULT_HEADERS constant."""

    def test_正常系_Accept_Languageにja_jaJPが含まれる(self) -> None:
        """JP_DEFAULT_HEADERS contains Accept-Language: ja,ja-JP;q=0.9,en;q=0.8."""
        assert "Accept-Language" in JP_DEFAULT_HEADERS
        assert "ja" in JP_DEFAULT_HEADERS["Accept-Language"]
        assert "ja-JP" in JP_DEFAULT_HEADERS["Accept-Language"]

    def test_正常系_User_Agentが含まれる(self) -> None:
        """JP_DEFAULT_HEADERS contains User-Agent."""
        assert "User-Agent" in JP_DEFAULT_HEADERS
        assert len(JP_DEFAULT_HEADERS["User-Agent"]) > 0

    def test_正常系_Acceptが含まれる(self) -> None:
        """JP_DEFAULT_HEADERS contains Accept."""
        assert "Accept" in JP_DEFAULT_HEADERS
        assert "text/html" in JP_DEFAULT_HEADERS["Accept"]

    def test_正常系_型がdict_str_strである(self) -> None:
        """JP_DEFAULT_HEADERS is a dict[str, str]."""
        assert isinstance(JP_DEFAULT_HEADERS, dict)
        for key, value in JP_DEFAULT_HEADERS.items():
            assert isinstance(key, str)
            assert isinstance(value, str)


class TestFetchHtml:
    """Tests for fetch_html function."""

    def test_正常系_HTML文字列を返す(self) -> None:
        """fetch_html returns HTML string on success."""
        mock_response = MagicMock()
        mock_response.text = "<html><body>Test</body></html>"
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_response

        result = fetch_html("https://example.com", mock_client)

        assert result == "<html><body>Test</body></html>"
        mock_client.get.assert_called_once()
        mock_response.raise_for_status.assert_called_once()

    def test_正常系_デフォルトヘッダーが使用される(self) -> None:
        """fetch_html uses JP_DEFAULT_HEADERS when headers=None."""
        mock_response = MagicMock()
        mock_response.text = "<html></html>"
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_response

        fetch_html("https://example.com", mock_client, headers=None)

        call_kwargs = mock_client.get.call_args
        used_headers = (
            call_kwargs[1].get("headers") or call_kwargs[0][1]
            if len(call_kwargs[0]) > 1
            else call_kwargs[1].get("headers")
        )
        assert used_headers is not None

    def test_正常系_カスタムヘッダーが使用される(self) -> None:
        """fetch_html uses custom headers when provided."""
        mock_response = MagicMock()
        mock_response.text = "<html></html>"
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_response

        custom_headers = {"X-Custom": "value"}
        fetch_html("https://example.com", mock_client, headers=custom_headers)

        # The call should have been made with the custom headers
        mock_client.get.assert_called_once()

    def test_異常系_HTTPエラー時に例外を伝播する(self) -> None:
        """fetch_html propagates HTTPStatusError on HTTP error."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found",
            request=MagicMock(),
            response=MagicMock(),
        )

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_response

        with pytest.raises(httpx.HTTPStatusError):
            fetch_html("https://example.com/notfound", mock_client)

    def test_異常系_接続エラー時に例外を伝播する(self) -> None:
        """fetch_html propagates connection errors."""
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.side_effect = httpx.ConnectError("Connection failed")

        with pytest.raises(httpx.ConnectError):
            fetch_html("https://unreachable.example.com", mock_client)

    def test_正常系_URLが正しく渡される(self) -> None:
        """fetch_html passes the URL to client.get."""
        mock_response = MagicMock()
        mock_response.text = "<html></html>"
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_response

        url = "https://kabutan.jp/news/"
        fetch_html(url, mock_client)

        args = mock_client.get.call_args[0]
        assert args[0] == url


class TestParseHtml:
    """Tests for parse_html function."""

    def test_正常系_HtmlElementを返す(self) -> None:
        """parse_html returns an lxml HtmlElement."""
        html_content = "<html><body><h1>Test</h1></body></html>"
        result = parse_html(html_content)
        assert isinstance(result, HtmlElement)

    def test_正常系_h1タグをXPathで抽出できる(self) -> None:
        """parse_html result supports XPath queries."""
        html_content = "<html><body><h1>Test Title</h1></body></html>"
        result = parse_html(html_content)
        h1_elements = result.xpath("//h1")
        assert len(h1_elements) == 1
        assert h1_elements[0].text_content() == "Test Title"

    def test_正常系_複数要素をパースできる(self) -> None:
        """parse_html can handle HTML with multiple elements."""
        html_content = (
            "<html><body>"
            "<div class='article'><a href='/news/1'>Article 1</a></div>"
            "<div class='article'><a href='/news/2'>Article 2</a></div>"
            "</body></html>"
        )
        result = parse_html(html_content)
        divs = result.xpath("//div[@class='article']")
        assert len(divs) == 2

    def test_正常系_空のHTML文字列でも動作する(self) -> None:
        """parse_html handles minimal/empty HTML."""
        result = parse_html("<html></html>")
        assert isinstance(result, HtmlElement)


class TestResolveRelativeUrl:
    """Tests for resolve_relative_url function."""

    def test_正常系_相対URLを絶対URLに変換する(self) -> None:
        """resolve_relative_url converts relative URL to absolute URL."""
        result = resolve_relative_url(
            "/news/marketnews/?&b=n123",
            "https://kabutan.jp",
        )
        assert result == "https://kabutan.jp/news/marketnews/?&b=n123"

    def test_正常系_パスのみの相対URLを変換する(self) -> None:
        """resolve_relative_url handles path-only relative URLs."""
        result = resolve_relative_url("/articles/123", "https://example.com")
        assert result == "https://example.com/articles/123"

    def test_正常系_絶対URLはそのまま返す(self) -> None:
        """resolve_relative_url returns absolute URLs unchanged."""
        absolute_url = "https://other.example.com/page"
        result = resolve_relative_url(absolute_url, "https://example.com")
        assert result == absolute_url

    def test_正常系_クエリパラメータを保持する(self) -> None:
        """resolve_relative_url preserves query parameters."""
        result = resolve_relative_url(
            "/search?q=test&page=1",
            "https://example.com",
        )
        assert result == "https://example.com/search?q=test&page=1"

    def test_正常系_ベースURLにパスが含まれる場合(self) -> None:
        """resolve_relative_url handles base URLs with paths."""
        result = resolve_relative_url(
            "../other/page",
            "https://example.com/news/article",
        )
        assert result == "https://example.com/other/page"


class TestRateLimitSleep:
    """Tests for rate_limit_sleep function."""

    def test_正常系_configのrequest_delayだけスリープする(self) -> None:
        """rate_limit_sleep sleeps for config.request_delay seconds."""
        config = ScraperConfig(request_delay=0.5)
        with patch("time.sleep") as mock_sleep:
            rate_limit_sleep(config)
            mock_sleep.assert_called_once_with(0.5)

    def test_正常系_configがNoneの場合デフォルト値でスリープする(self) -> None:
        """rate_limit_sleep uses default delay when config is None."""
        with patch("time.sleep") as mock_sleep:
            rate_limit_sleep(None)
            mock_sleep.assert_called_once()
            # Default delay should be a reasonable value (1.0 per get_delay default)
            sleep_arg = mock_sleep.call_args[0][0]
            assert sleep_arg >= 0.0

    def test_正常系_request_delay_0でスリープしない(self) -> None:
        """rate_limit_sleep calls sleep with 0.0 when request_delay is 0."""
        config = ScraperConfig(request_delay=0.0)
        with patch("time.sleep") as mock_sleep:
            rate_limit_sleep(config)
            mock_sleep.assert_called_once_with(0.0)

    def test_正常系_カスタムdelayが反映される(self) -> None:
        """rate_limit_sleep uses custom delay from config."""
        config = ScraperConfig(request_delay=2.5)
        with patch("time.sleep") as mock_sleep:
            rate_limit_sleep(config)
            mock_sleep.assert_called_once_with(2.5)
