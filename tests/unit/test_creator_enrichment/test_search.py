"""creator_enrichment.phases.search のテスト.

DirectSearcher による LLM クエリ生成 + Tavily REST API 検索を検証する。
- LLM クエリ生成の正常系・異常系
- Tavily API 呼び出しの正常系・異常系
- URL 重複排除
- 個別クエリ失敗時のスキップ動作
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from creator_enrichment.llm_client import LLMClient
from creator_enrichment.phases.search import DirectSearcher
from creator_enrichment.types import PhaseError, RawItem


# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_llm() -> MagicMock:
    """LLMClient モック."""
    return MagicMock(spec=LLMClient)


@pytest.fixture
def genre_config() -> dict:
    """テスト用 genre_config."""
    return {
        "career": {"name_ja": "転職・副業"},
        "beauty-romance": {"name_ja": "美容・恋愛"},
    }


@pytest.fixture
def searcher(mock_llm: MagicMock, genre_config: dict) -> DirectSearcher:
    """DirectSearcher インスタンス."""
    return DirectSearcher(
        llm_client=mock_llm,
        genre_config=genre_config,
        tavily_api_key="tvly-test-key",
    )


def _llm_queries_response(n: int = 3) -> str:
    """LLM が返すクエリ生成 JSON を作成する."""
    queries = [
        {"query": f"test query {i}", "type": "gap", "language": "en"}
        for i in range(n)
    ]
    return json.dumps(queries, ensure_ascii=False)


def _tavily_api_response(results: list[dict] | None = None) -> httpx.Response:
    """Tavily API レスポンスのモックを作成する."""
    if results is None:
        results = [
            {
                "url": "https://example.com/article-1",
                "title": "Test Article 1",
                "content": "Content of article 1",
            },
            {
                "url": "https://example.com/article-2",
                "title": "Test Article 2",
                "content": "Content of article 2",
            },
        ]
    return httpx.Response(
        200,
        json={"results": results},
        request=httpx.Request("POST", "https://api.tavily.com/search"),
    )


# ---------------------------------------------------------------------------
# LLM クエリ生成
# ---------------------------------------------------------------------------
class TestQueryGeneration:
    """LLM クエリ生成のテスト."""

    def test_正常系_LLMがクエリリストを生成する(
        self, searcher: DirectSearcher, mock_llm: MagicMock
    ) -> None:
        """LLM からクエリリストを正常に生成する."""
        mock_llm.query.return_value = _llm_queries_response(5)

        with patch.object(searcher, "_execute_searches", return_value=[]):
            searcher.search(queries=["FOMO活用"], genre="career")

        mock_llm.query.assert_called_once()
        prompt = mock_llm.query.call_args[0][0]
        assert "career" in prompt
        assert "転職・副業" in prompt
        assert "FOMO活用" in prompt

    def test_異常系_LLM呼び出し失敗でPhaseError(
        self, searcher: DirectSearcher, mock_llm: MagicMock
    ) -> None:
        """LLM 呼び出し失敗で PhaseError が発生する."""
        mock_llm.query.side_effect = RuntimeError("LLM error")

        with pytest.raises(PhaseError, match="Query generation failed"):
            searcher.search(queries=["test"], genre="career")

    def test_異常系_LLMが不正JSONを返すとPhaseError(
        self, searcher: DirectSearcher, mock_llm: MagicMock
    ) -> None:
        """LLM が不正 JSON を返すと PhaseError が発生する."""
        mock_llm.query.return_value = "not valid json"

        with pytest.raises(PhaseError, match="parse failed"):
            searcher.search(queries=["test"], genre="career")

    def test_異常系_LLMがリスト以外を返すとPhaseError(
        self, searcher: DirectSearcher, mock_llm: MagicMock
    ) -> None:
        """LLM がリスト以外を返すと PhaseError が発生する."""
        mock_llm.query.return_value = '{"not": "a list"}'

        with pytest.raises(PhaseError, match="Expected list"):
            searcher.search(queries=["test"], genre="career")


# ---------------------------------------------------------------------------
# Tavily API 検索実行
# ---------------------------------------------------------------------------
class TestTavilyExecution:
    """Tavily API 検索実行のテスト."""

    @patch("creator_enrichment.phases.search.httpx.post")
    def test_正常系_Tavily結果をRawItemに変換する(
        self,
        mock_post: MagicMock,
        searcher: DirectSearcher,
        mock_llm: MagicMock,
    ) -> None:
        """Tavily API 結果を RawItem リストに変換する."""
        mock_llm.query.return_value = _llm_queries_response(1)
        mock_post.return_value = _tavily_api_response()

        results = searcher.search(queries=["test"], genre="career")

        assert len(results) == 2
        assert results[0]["url"] == "https://example.com/article-1"
        assert results[0]["title"] == "Test Article 1"
        assert results[0]["source"] == "tavily"

    @patch("creator_enrichment.phases.search.httpx.post")
    def test_正常系_URL重複が排除される(
        self,
        mock_post: MagicMock,
        searcher: DirectSearcher,
        mock_llm: MagicMock,
    ) -> None:
        """同一 URL の結果が重複排除される."""
        mock_llm.query.return_value = _llm_queries_response(2)
        # 2クエリとも同じ URL を返す
        mock_post.return_value = _tavily_api_response(
            [{"url": "https://dup.com/a", "title": "Dup", "content": "..."}]
        )

        results = searcher.search(queries=["test"], genre="career")

        assert len(results) == 1

    @patch("creator_enrichment.phases.search.httpx.post")
    def test_正常系_個別クエリ失敗はスキップされる(
        self,
        mock_post: MagicMock,
        searcher: DirectSearcher,
        mock_llm: MagicMock,
    ) -> None:
        """個別クエリの Tavily エラーはスキップされ他のクエリは続行する."""
        mock_llm.query.return_value = _llm_queries_response(2)
        mock_post.side_effect = [
            httpx.TimeoutException("timeout"),
            _tavily_api_response(),
        ]

        results = searcher.search(queries=["test"], genre="career")

        assert len(results) == 2  # 2番目のクエリの結果のみ

    @patch("creator_enrichment.phases.search.httpx.post")
    def test_正常系_空クエリ文字列はスキップされる(
        self,
        mock_post: MagicMock,
        searcher: DirectSearcher,
        mock_llm: MagicMock,
    ) -> None:
        """空のクエリ文字列はスキップされる."""
        mock_llm.query.return_value = json.dumps([
            {"query": "", "type": "gap", "language": "en"},
            {"query": "valid query", "type": "gap", "language": "en"},
        ])
        mock_post.return_value = _tavily_api_response()

        results = searcher.search(queries=["test"], genre="career")

        assert mock_post.call_count == 1  # 空クエリはスキップ

    @patch("creator_enrichment.phases.search.httpx.post")
    def test_正常系_redditクエリにinclude_domainsが設定される(
        self,
        mock_post: MagicMock,
        searcher: DirectSearcher,
        mock_llm: MagicMock,
    ) -> None:
        """'reddit' を含むクエリに include_domains が設定される."""
        mock_llm.query.return_value = json.dumps([
            {"query": "side hustle reddit experience", "type": "explore", "language": "en"},
        ])
        mock_post.return_value = _tavily_api_response()

        searcher.search(queries=["test"], genre="career")

        call_json = mock_post.call_args.kwargs["json"]
        assert call_json["include_domains"] == ["reddit.com"]

    @patch("creator_enrichment.phases.search.httpx.post")
    def test_正常系_Tavily_api_keyがbodyに設定される(
        self,
        mock_post: MagicMock,
        searcher: DirectSearcher,
        mock_llm: MagicMock,
    ) -> None:
        """Tavily API 呼び出しに api_key が body に設定される."""
        mock_llm.query.return_value = _llm_queries_response(1)
        mock_post.return_value = _tavily_api_response()

        searcher.search(queries=["test"], genre="career")

        call_json = mock_post.call_args.kwargs["json"]
        assert call_json["api_key"] == "tvly-test-key"
