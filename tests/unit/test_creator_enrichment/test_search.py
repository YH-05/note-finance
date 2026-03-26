"""creator_enrichment.phases.search のテスト.

DirectSearcher による LLM クエリ生成 + Tavily REST API 検索を検証する。
- LLM クエリ生成の正常系・異常系
- Tavily API 呼び出しの正常系・異常系
- URL 重複排除
- 個別クエリ失敗時のスキップ動作
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import httpx
import pytest

from creator_enrichment.llm_client import LLMClient
from creator_enrichment.phases.search import DirectSearcher, TavilyKeyPool
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
def key_pool() -> TavilyKeyPool:
    """テスト用 TavilyKeyPool."""
    return TavilyKeyPool(["tvly-test-key-1", "tvly-test-key-2"])


@pytest.fixture
def searcher(
    mock_llm: MagicMock, genre_config: dict, key_pool: TavilyKeyPool
) -> DirectSearcher:
    """DirectSearcher インスタンス."""
    return DirectSearcher(
        llm_client=mock_llm,
        genre_config=genre_config,
        tavily_key_pool=key_pool,
    )


def _llm_queries_response(n: int = 3) -> str:
    """LLM が返すクエリ生成 JSON を作成する."""
    queries = [
        {"query": f"test query {i}", "type": "gap", "language": "en"} for i in range(n)
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
                "published_date": "2026-03-25T00:00:00+00:00",
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
        assert results[0].get("published_at") == "2026-03-25T00:00:00+00:00"

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
        mock_llm.query.return_value = json.dumps(
            [
                {"query": "", "type": "gap", "language": "en"},
                {"query": "valid query", "type": "gap", "language": "en"},
            ]
        )
        mock_post.return_value = _tavily_api_response()

        searcher.search(queries=["test"], genre="career")

        assert mock_post.call_count == 1  # 空クエリはスキップ

    @patch("creator_enrichment.phases.search.httpx.post")
    def test_正常系_redditクエリにinclude_domainsが設定される(
        self,
        mock_post: MagicMock,
        searcher: DirectSearcher,
        mock_llm: MagicMock,
    ) -> None:
        """'reddit' を含むクエリに include_domains が設定される."""
        mock_llm.query.return_value = json.dumps(
            [
                {
                    "query": "side hustle reddit experience",
                    "type": "explore",
                    "language": "en",
                },
            ]
        )
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
        assert call_json["api_key"].startswith("tvly-test-key")

    @patch("creator_enrichment.phases.search.httpx.post")
    def test_正常系_432エラーで次のキーにローテーションする(
        self,
        mock_post: MagicMock,
        searcher: DirectSearcher,
        mock_llm: MagicMock,
    ) -> None:
        """432 エラーでキーが除外され次のキーでリトライする."""
        mock_llm.query.return_value = _llm_queries_response(1)
        # 1回目: 432、2回目: 成功
        mock_post.side_effect = [
            httpx.Response(
                432,
                json={"detail": {"error": "rate limit"}},
                request=httpx.Request("POST", "https://api.tavily.com/search"),
            ),
            _tavily_api_response(),
        ]

        results = searcher.search(queries=["test"], genre="career")

        assert len(results) == 2
        assert mock_post.call_count == 2
        # 2回目は別のキーが使われる
        first_key = mock_post.call_args_list[0].kwargs["json"]["api_key"]
        second_key = mock_post.call_args_list[1].kwargs["json"]["api_key"]
        assert first_key != second_key


# ---------------------------------------------------------------------------
# TavilyKeyPool
# ---------------------------------------------------------------------------
class TestTavilyKeyPool:
    """TavilyKeyPool のテスト."""

    def test_正常系_キーをローテーションする(self) -> None:
        pool = TavilyKeyPool(["key1", "key2", "key3"])
        keys = [pool.get_key() for _ in range(6)]
        assert keys == ["key1", "key2", "key3", "key1", "key2", "key3"]

    def test_正常系_exhaustedキーがスキップされる(self) -> None:
        pool = TavilyKeyPool(["key1", "key2", "key3"])
        pool.mark_exhausted("key2")
        keys = [pool.get_key() for _ in range(4)]
        assert keys == ["key1", "key3", "key1", "key3"]

    def test_正常系_全キー枯渇でNone(self) -> None:
        pool = TavilyKeyPool(["key1"])
        pool.mark_exhausted("key1")
        assert pool.get_key() is None
        assert not pool.has_keys()

    def test_正常系_空プールでhas_keysFalse(self) -> None:
        pool = TavilyKeyPool([])
        assert not pool.has_keys()

    @patch.dict(
        "os.environ",
        {"TAVILY_API_KEY_1": "k1", "TAVILY_API_KEY_2": "k2", "TAVILY_API_KEY_3": "k3"},
    )
    def test_正常系_from_envで連番キーを読む(self) -> None:
        pool = TavilyKeyPool.from_env()
        assert pool.has_keys()
        keys = [pool.get_key() for _ in range(3)]
        assert keys == ["k1", "k2", "k3"]

    def test_正常系_from_envで単一キーにフォールバック(self) -> None:
        with patch.dict("os.environ", {"TAVILY_API_KEY": "single"}, clear=True):
            pool = TavilyKeyPool.from_env()
            assert pool.get_key() == "single"

    def test_正常系_from_envで連番が途切れたら停止(self) -> None:
        with patch.dict(
            "os.environ", {"TAVILY_API_KEY_1": "a", "TAVILY_API_KEY_3": "c"}, clear=True
        ):
            pool = TavilyKeyPool.from_env()
            # _2 が無いので _1 だけ読まれる
            assert pool.get_key() == "a"
            assert pool.get_key() == "a"


class TestRawStorePersistence:
    """RawStore 永続化時のメタデータ伝播テスト."""

    @patch("data_pipeline.storage.raw_store.RawStore")
    def test_正常系_published_atをRawStoreへ渡す(
        self,
        mock_raw_store_cls: MagicMock,
        searcher: DirectSearcher,
    ) -> None:
        """RawItem.published_at が save_text に渡される."""
        mock_store = mock_raw_store_cls.return_value
        mock_store.save_text.return_value = "saved"

        items = [
            RawItem(
                url="https://example.com/article-1",
                title="Test Article 1",
                content="Content of article 1",
                source="tavily",
                published_at="2026-03-25T00:00:00+00:00",
            )
        ]

        searcher._save_to_rawstore(items, "career")

        mock_store.save_text.assert_called_once()
        kwargs = mock_store.save_text.call_args.kwargs
        assert kwargs["published_at"] == "2026-03-25T00:00:00+00:00"
