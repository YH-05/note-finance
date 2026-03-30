"""tavily_mcp.server のテスト.

TavilyKeyPool のローテーション動作と
MCP ツール関数の Tavily API 呼び出しを検証する。
"""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from tavily_mcp.server import (
    TavilyKeyPool,
    _post_with_rotation,
    tavily_crawl,
    tavily_extract,
    tavily_map,
    tavily_research,
    tavily_search,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ok_response(body: dict | None = None) -> httpx.Response:
    """200 OK の httpx.Response を作成する."""
    return httpx.Response(
        200,
        json=body or {"results": [{"url": "https://example.com", "title": "Test"}]},
        request=httpx.Request("POST", "https://api.tavily.com/search"),
    )


def _rate_limit_response(status: int = 432) -> httpx.Response:
    """Rate-limit の httpx.Response を作成する."""
    return httpx.Response(
        status,
        json={"detail": "rate limit exceeded"},
        request=httpx.Request("POST", "https://api.tavily.com/search"),
    )


# ---------------------------------------------------------------------------
# TavilyKeyPool
# ---------------------------------------------------------------------------
class TestTavilyKeyPool:
    """TavilyKeyPool の単体テスト."""

    def test_正常系_ラウンドロビンでキーを返す(self) -> None:
        pool = TavilyKeyPool(["k1", "k2", "k3"])
        keys = [pool.get_key() for _ in range(6)]
        assert keys == ["k1", "k2", "k3", "k1", "k2", "k3"]

    def test_正常系_exhaustedキーがスキップされる(self) -> None:
        pool = TavilyKeyPool(["k1", "k2", "k3"])
        pool.mark_exhausted("k2")
        keys = [pool.get_key() for _ in range(4)]
        assert keys == ["k1", "k3", "k1", "k3"]

    def test_正常系_全キー枯渇でNone(self) -> None:
        pool = TavilyKeyPool(["k1"])
        pool.mark_exhausted("k1")
        assert pool.get_key() is None
        assert not pool.has_keys()

    def test_正常系_空プールでhas_keysFalse(self) -> None:
        pool = TavilyKeyPool([])
        assert not pool.has_keys()
        assert pool.get_key() is None

    def test_正常系_statusが正しいカウントを返す(self) -> None:
        pool = TavilyKeyPool(["k1", "k2", "k3"])
        pool.mark_exhausted("k2")
        assert pool.status() == {"total": 3, "available": 2, "exhausted": 1}

    @patch.dict(
        "os.environ",
        {"TAVILY_API_KEY_1": "a", "TAVILY_API_KEY_2": "b", "TAVILY_API_KEY_3": "c"},
    )
    def test_正常系_from_envで連番キーを読む(self) -> None:
        pool = TavilyKeyPool.from_env()
        assert pool.status()["total"] == 3
        assert [pool.get_key() for _ in range(3)] == ["a", "b", "c"]

    def test_正常系_from_envで単一キーにフォールバック(self) -> None:
        with patch.dict("os.environ", {"TAVILY_API_KEY": "single"}, clear=True):
            pool = TavilyKeyPool.from_env()
            assert pool.get_key() == "single"

    def test_正常系_from_envで連番が途切れたら停止(self) -> None:
        with patch.dict(
            "os.environ",
            {"TAVILY_API_KEY_1": "a", "TAVILY_API_KEY_3": "c"},
            clear=True,
        ):
            pool = TavilyKeyPool.from_env()
            # _2 が無いので _1 だけ
            assert pool.status()["total"] == 1

    def test_正常系_envにキーなしで空プール(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            pool = TavilyKeyPool.from_env()
            assert not pool.has_keys()


# ---------------------------------------------------------------------------
# _post_with_rotation
# ---------------------------------------------------------------------------
class TestPostWithRotation:
    """_post_with_rotation の単体テスト."""

    @patch("tavily_mcp.server._get_pool")
    @patch("tavily_mcp.server.httpx.post")
    def test_正常系_成功レスポンスを返す(
        self, mock_post: patch, mock_pool: patch
    ) -> None:
        pool = TavilyKeyPool(["key1"])
        mock_pool.return_value = pool
        mock_post.return_value = _ok_response({"query": "test", "results": []})

        result = _post_with_rotation("search", {"query": "test"})

        assert result == {"query": "test", "results": []}
        call_json = mock_post.call_args.kwargs["json"]
        assert call_json["api_key"] == "key1"

    @patch("tavily_mcp.server._get_pool")
    @patch("tavily_mcp.server.httpx.post")
    def test_正常系_432で次のキーにローテーション(
        self, mock_post: patch, mock_pool: patch
    ) -> None:
        pool = TavilyKeyPool(["key1", "key2"])
        mock_pool.return_value = pool
        mock_post.side_effect = [
            _rate_limit_response(432),
            _ok_response({"results": []}),
        ]

        result = _post_with_rotation("search", {"query": "test"})

        assert "error" not in result
        assert mock_post.call_count == 2
        keys_used = [c.kwargs["json"]["api_key"] for c in mock_post.call_args_list]
        assert keys_used[0] != keys_used[1]

    @patch("tavily_mcp.server._get_pool")
    @patch("tavily_mcp.server.httpx.post")
    def test_正常系_429でもローテーション(
        self, mock_post: patch, mock_pool: patch
    ) -> None:
        pool = TavilyKeyPool(["key1", "key2"])
        mock_pool.return_value = pool
        mock_post.side_effect = [
            _rate_limit_response(429),
            _ok_response(),
        ]

        result = _post_with_rotation("search", {"query": "test"})

        assert "error" not in result

    @patch("tavily_mcp.server._get_pool")
    @patch("tavily_mcp.server.httpx.post")
    def test_異常系_全キー枯渇でエラー(
        self, mock_post: patch, mock_pool: patch
    ) -> None:
        pool = TavilyKeyPool(["key1"])
        mock_pool.return_value = pool
        mock_post.return_value = _rate_limit_response(432)

        result = _post_with_rotation("search", {"query": "test"})

        assert "error" in result
        assert "failed" in result["error"]

    @patch("tavily_mcp.server._get_pool")
    @patch("tavily_mcp.server.httpx.post")
    def test_異常系_タイムアウトでエラー(
        self, mock_post: patch, mock_pool: patch
    ) -> None:
        pool = TavilyKeyPool(["key1"])
        mock_pool.return_value = pool
        mock_post.side_effect = httpx.TimeoutException("timeout")

        result = _post_with_rotation("search", {"query": "test"})

        assert "error" in result
        assert "Timeout" in result["error"]

    @patch("tavily_mcp.server._get_pool")
    def test_異常系_キーなしでエラー(self, mock_pool: patch) -> None:
        pool = TavilyKeyPool([])
        mock_pool.return_value = pool

        result = _post_with_rotation("search", {"query": "test"})

        assert "error" in result
        assert "No Tavily API keys" in result["error"]

    @patch("tavily_mcp.server._get_pool")
    @patch("tavily_mcp.server.httpx.post")
    def test_異常系_HTTP500でエラー(self, mock_post: patch, mock_pool: patch) -> None:
        pool = TavilyKeyPool(["key1"])
        mock_pool.return_value = pool
        mock_post.return_value = httpx.Response(
            500,
            text="Internal Server Error",
            request=httpx.Request("POST", "https://api.tavily.com/search"),
        )

        result = _post_with_rotation("search", {"query": "test"})

        assert "error" in result
        assert "HTTP 500" in result["error"]


# ---------------------------------------------------------------------------
# MCP ツール関数
# ---------------------------------------------------------------------------
class TestTavilySearchTool:
    """tavily_search ツールのテスト."""

    @patch("tavily_mcp.server._post_with_rotation")
    def test_正常系_デフォルトパラメータで検索(self, mock_post: patch) -> None:
        mock_post.return_value = {"results": []}

        tavily_search(query="test query")

        mock_post.assert_called_once()
        args = mock_post.call_args
        assert args[0][0] == "search"
        payload = args[0][1]
        assert payload["query"] == "test query"
        assert payload["max_results"] == 5
        assert payload["search_depth"] == "basic"

    @patch("tavily_mcp.server._post_with_rotation")
    def test_正常系_include_domainsが渡される(self, mock_post: patch) -> None:
        mock_post.return_value = {"results": []}

        tavily_search(query="test", include_domains=["reddit.com"])

        payload = mock_post.call_args[0][1]
        assert payload["include_domains"] == ["reddit.com"]

    @patch("tavily_mcp.server._post_with_rotation")
    def test_正常系_newsトピックでdaysが含まれる(self, mock_post: patch) -> None:
        mock_post.return_value = {"results": []}

        tavily_search(query="test", topic="news", days=7)

        payload = mock_post.call_args[0][1]
        assert payload["days"] == 7

    @patch("tavily_mcp.server._post_with_rotation")
    def test_正常系_max_resultsが20に制限される(self, mock_post: patch) -> None:
        mock_post.return_value = {"results": []}

        tavily_search(query="test", max_results=50)

        payload = mock_post.call_args[0][1]
        assert payload["max_results"] == 20


class TestTavilyResearchTool:
    """tavily_research ツールのテスト."""

    @patch("tavily_mcp.server._post_with_rotation")
    def test_正常系_advancedとinclude_answerが設定される(
        self, mock_post: patch
    ) -> None:
        mock_post.return_value = {"results": [], "answer": "..."}

        tavily_research(query="deep topic")

        args = mock_post.call_args
        payload = args[0][1]
        assert payload["search_depth"] == "advanced"
        assert payload["include_answer"] is True
        assert payload["max_results"] == 10
        assert args[1]["timeout"] == 60


class TestTavilyExtractTool:
    """tavily_extract ツールのテスト."""

    @patch("tavily_mcp.server._post_with_rotation")
    def test_正常系_URLリストが渡される(self, mock_post: patch) -> None:
        mock_post.return_value = {"results": []}

        tavily_extract(urls=["https://example.com/a", "https://example.com/b"])

        args = mock_post.call_args
        assert args[0][0] == "extract"
        assert args[0][1]["urls"] == ["https://example.com/a", "https://example.com/b"]


class TestTavilyCrawlTool:
    """tavily_crawl ツールのテスト."""

    @patch("tavily_mcp.server._post_with_rotation")
    def test_正常系_デフォルトパラメータでクロール(self, mock_post: patch) -> None:
        mock_post.return_value = {"results": []}

        tavily_crawl(url="https://example.com")

        payload = mock_post.call_args[0][1]
        assert payload["url"] == "https://example.com"
        assert payload["max_depth"] == 1
        assert payload["limit"] == 50


class TestTavilyMapTool:
    """tavily_map ツールのテスト."""

    @patch("tavily_mcp.server._post_with_rotation")
    def test_正常系_URLが渡される(self, mock_post: patch) -> None:
        mock_post.return_value = {"urls": []}

        tavily_map(url="https://example.com")

        payload = mock_post.call_args[0][1]
        assert payload["url"] == "https://example.com"
