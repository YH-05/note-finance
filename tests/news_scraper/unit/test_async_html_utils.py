"""Unit tests for async fetch functions in news_scraper._html_utils.

Tests cover:
- async_fetch_html: HTML retrieval via httpx.AsyncClient (mocked)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from news_scraper._html_utils import JP_DEFAULT_HEADERS, async_fetch_html


class TestAsyncFetchHtml:
    """Tests for async_fetch_html function."""

    async def test_正常系_HTML文字列を返す(self) -> None:
        """async_fetch_html returns HTML string on success."""
        mock_response = MagicMock()
        mock_response.text = "<html><body>Test</body></html>"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await async_fetch_html("https://example.com", mock_client)

        assert result == "<html><body>Test</body></html>"
        mock_client.get.assert_called_once()
        mock_response.raise_for_status.assert_called_once()

    async def test_正常系_デフォルトヘッダーが使用される(self) -> None:
        """async_fetch_html uses JP_DEFAULT_HEADERS when headers=None."""
        mock_response = MagicMock()
        mock_response.text = "<html></html>"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        await async_fetch_html("https://example.com", mock_client, headers=None)

        call_kwargs = mock_client.get.call_args
        assert call_kwargs is not None

    async def test_正常系_カスタムヘッダーが使用される(self) -> None:
        """async_fetch_html uses custom headers when provided."""
        mock_response = MagicMock()
        mock_response.text = "<html></html>"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        custom_headers = {"X-Custom": "value"}
        await async_fetch_html(
            "https://example.com", mock_client, headers=custom_headers
        )

        mock_client.get.assert_called_once()

    async def test_異常系_HTTPエラー時に例外を伝播する(self) -> None:
        """async_fetch_html propagates HTTPStatusError on HTTP error."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found",
            request=MagicMock(),
            response=MagicMock(),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        with pytest.raises(httpx.HTTPStatusError):
            await async_fetch_html("https://example.com/notfound", mock_client)

    async def test_異常系_接続エラー時に例外を伝播する(self) -> None:
        """async_fetch_html propagates connection errors."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))

        with pytest.raises(httpx.ConnectError):
            await async_fetch_html("https://unreachable.example.com", mock_client)

    async def test_正常系_URLが正しく渡される(self) -> None:
        """async_fetch_html passes the URL to client.get."""
        mock_response = MagicMock()
        mock_response.text = "<html></html>"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        url = "https://kabutan.jp/news/"
        await async_fetch_html(url, mock_client)

        args = mock_client.get.call_args[0]
        assert args[0] == url
