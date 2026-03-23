"""creator_enrichment.phases.search のテスト.

ClaudeCodeSearcher によるエージェント検索ロジックを検証する。
- RawItem 変換の正常系
- リトライ動作（2回失敗 -> 3回目成功）
- タイムアウト時の CycleError 変換
- 不正 JSON レスポンスのエラーハンドリング
- 空結果のハンドリング
- ```json コードブロックラッピングのパース
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from creator_enrichment.phases.search import (
    AgentProvider,
    ClaudeCodeSearcher,
)
from creator_enrichment.types import CycleError, RawItem


# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------
@pytest.fixture
def valid_response_json() -> str:
    """正常な JSON レスポンス文字列."""
    data = {
        "items": [
            {
                "url": "https://example.com/article-1",
                "title": "Side Hustle Tips 2026",
                "content": "Here are the best tips for side hustles...",
                "source": "tavily_search",
            },
            {
                "url": "https://example.jp/article-2",
                "title": "副業の始め方ガイド",
                "content": "副業を始めるための具体的なステップ...",
                "source": "tavily_search",
            },
            {
                "url": "https://reddit.com/r/sidehustle/post-1",
                "title": "My side hustle journey",
                "content": "I started a side hustle and...",
                "source": "reddit",
            },
        ],
    }
    return json.dumps(data, ensure_ascii=False)


@pytest.fixture
def valid_response_with_code_block(valid_response_json: str) -> str:
    """```json コードブロックでラップされた JSON レスポンス."""
    return f"```json\n{valid_response_json}\n```"


@pytest.fixture
def mock_provider() -> MagicMock:
    """AgentProvider プロトコルに準拠するモックプロバイダー."""
    provider = MagicMock(spec=AgentProvider)
    return provider


# ---------------------------------------------------------------------------
# RawItem 変換の正常系
# ---------------------------------------------------------------------------
class TestRawItemConversion:
    """JSON レスポンスから RawItem リストへの変換テスト."""

    def test_正常系_JSONレスポンスからRawItemリストを生成(
        self,
        mock_provider: MagicMock,
        valid_response_json: str,
    ) -> None:
        """正常な JSON レスポンスが RawItem リストに変換される."""
        mock_provider.query.return_value = valid_response_json

        searcher = ClaudeCodeSearcher(provider=mock_provider)
        results = searcher.search(
            queries=["side hustle tips"],
            genre="career",
        )

        assert len(results) == 3
        assert results[0]["url"] == "https://example.com/article-1"
        assert results[0]["title"] == "Side Hustle Tips 2026"
        assert results[0]["source"] == "tavily_search"
        assert results[2]["source"] == "reddit"

    def test_正常系_RawItemの全フィールドが存在する(
        self,
        mock_provider: MagicMock,
        valid_response_json: str,
    ) -> None:
        """変換された各 RawItem が url, title, content, source を持つ."""
        mock_provider.query.return_value = valid_response_json

        searcher = ClaudeCodeSearcher(provider=mock_provider)
        results = searcher.search(queries=["test"], genre="career")

        for item in results:
            assert "url" in item
            assert "title" in item
            assert "content" in item
            assert "source" in item

    def test_正常系_コードブロックラップのJSONをパースできる(
        self,
        mock_provider: MagicMock,
        valid_response_with_code_block: str,
    ) -> None:
        """```json ... ``` でラップされたレスポンスを正しくパースする."""
        mock_provider.query.return_value = valid_response_with_code_block

        searcher = ClaudeCodeSearcher(provider=mock_provider)
        results = searcher.search(queries=["test"], genre="career")

        assert len(results) == 3
        assert results[0]["url"] == "https://example.com/article-1"


# ---------------------------------------------------------------------------
# プロバイダー呼び出しの検証
# ---------------------------------------------------------------------------
class TestProviderCalls:
    """プロバイダーへの呼び出しパラメータのテスト."""

    def test_正常系_queryメソッドが正しい引数で呼ばれる(
        self,
        mock_provider: MagicMock,
        valid_response_json: str,
    ) -> None:
        """provider.query がシステムプロンプト・プロンプト・タイムアウトで呼ばれる."""
        mock_provider.query.return_value = valid_response_json

        searcher = ClaudeCodeSearcher(provider=mock_provider)
        searcher.search(queries=["side hustle tips"], genre="career")

        mock_provider.query.assert_called_once()
        call_kwargs = mock_provider.query.call_args
        # keyword arguments で呼ばれることを確認
        assert "system_prompt" in call_kwargs.kwargs
        assert "prompt" in call_kwargs.kwargs
        assert "timeout" in call_kwargs.kwargs
        assert call_kwargs.kwargs["timeout"] == 120

    def test_正常系_システムプロンプトにtavily_searchが含まれる(
        self,
        mock_provider: MagicMock,
        valid_response_json: str,
    ) -> None:
        """システムプロンプトに tavily_search ツール指示が含まれる."""
        mock_provider.query.return_value = valid_response_json

        searcher = ClaudeCodeSearcher(provider=mock_provider)
        searcher.search(queries=["test"], genre="career")

        call_kwargs = mock_provider.query.call_args.kwargs
        assert "tavily_search" in call_kwargs["system_prompt"]

    def test_正常系_システムプロンプトにredditが含まれる(
        self,
        mock_provider: MagicMock,
        valid_response_json: str,
    ) -> None:
        """システムプロンプトに reddit ツール指示が含まれる."""
        mock_provider.query.return_value = valid_response_json

        searcher = ClaudeCodeSearcher(provider=mock_provider)
        searcher.search(queries=["test"], genre="career")

        call_kwargs = mock_provider.query.call_args.kwargs
        assert "reddit" in call_kwargs["system_prompt"]

    def test_正常系_プロンプトにクエリとジャンルが含まれる(
        self,
        mock_provider: MagicMock,
        valid_response_json: str,
    ) -> None:
        """ユーザープロンプトに検索クエリとジャンルが含まれる."""
        mock_provider.query.return_value = valid_response_json

        searcher = ClaudeCodeSearcher(provider=mock_provider)
        searcher.search(
            queries=["side hustle tips", "freelance income"],
            genre="career",
        )

        call_kwargs = mock_provider.query.call_args.kwargs
        prompt = call_kwargs["prompt"]
        assert "side hustle tips" in prompt
        assert "freelance income" in prompt
        assert "career" in prompt


# ---------------------------------------------------------------------------
# リトライ動作
# ---------------------------------------------------------------------------
class TestRetryBehavior:
    """tenacity リトライ動作のテスト."""

    def test_正常系_2回失敗後3回目で成功(
        self,
        mock_provider: MagicMock,
        valid_response_json: str,
    ) -> None:
        """2回 RuntimeError -> 3回目で正常レスポンスを返す."""
        mock_provider.query.side_effect = [
            RuntimeError("Temporary failure 1"),
            RuntimeError("Temporary failure 2"),
            valid_response_json,
        ]

        searcher = ClaudeCodeSearcher(provider=mock_provider)
        results = searcher.search(queries=["test"], genre="career")

        assert len(results) == 3
        assert mock_provider.query.call_count == 3

    def test_異常系_3回連続失敗でCycleError(
        self,
        mock_provider: MagicMock,
    ) -> None:
        """3回連続失敗で CycleError が発生する."""
        mock_provider.query.side_effect = RuntimeError("Persistent failure")

        searcher = ClaudeCodeSearcher(provider=mock_provider)

        with pytest.raises(CycleError) as exc_info:
            searcher.search(queries=["test"], genre="career")

        assert isinstance(exc_info.value.cause, RuntimeError)
        assert mock_provider.query.call_count == 3


# ---------------------------------------------------------------------------
# タイムアウト
# ---------------------------------------------------------------------------
class TestTimeout:
    """タイムアウト時の CycleError 変換テスト."""

    def test_異常系_TimeoutErrorがCycleErrorに変換される(
        self,
        mock_provider: MagicMock,
    ) -> None:
        """TimeoutError が CycleError にラップされる."""
        mock_provider.query.side_effect = TimeoutError("Search timed out after 120s")

        searcher = ClaudeCodeSearcher(provider=mock_provider)

        with pytest.raises(CycleError) as exc_info:
            searcher.search(queries=["test"], genre="career")

        assert isinstance(exc_info.value.cause, TimeoutError)


# ---------------------------------------------------------------------------
# 不正 JSON レスポンス
# ---------------------------------------------------------------------------
class TestInvalidJsonResponse:
    """不正 JSON レスポンスのエラーハンドリングテスト."""

    def test_異常系_不正JSONでCycleError(
        self,
        mock_provider: MagicMock,
    ) -> None:
        """パース不能な JSON が CycleError に変換される."""
        mock_provider.query.return_value = "This is not valid JSON"

        searcher = ClaudeCodeSearcher(provider=mock_provider)

        with pytest.raises(CycleError) as exc_info:
            searcher.search(queries=["test"], genre="career")

        assert isinstance(exc_info.value.cause, (json.JSONDecodeError, ValueError))

    def test_異常系_itemsキーがないJSONでCycleError(
        self,
        mock_provider: MagicMock,
    ) -> None:
        """items キーのない JSON が CycleError に変換される."""
        mock_provider.query.return_value = json.dumps({"data": []})

        searcher = ClaudeCodeSearcher(provider=mock_provider)

        with pytest.raises(CycleError) as exc_info:
            searcher.search(queries=["test"], genre="career")

        assert isinstance(exc_info.value.cause, (KeyError, ValueError))

    def test_異常系_itemsが非リストでCycleError(
        self,
        mock_provider: MagicMock,
    ) -> None:
        """items がリストでない場合 CycleError に変換される."""
        mock_provider.query.return_value = json.dumps({"items": "not a list"})

        searcher = ClaudeCodeSearcher(provider=mock_provider)

        with pytest.raises(CycleError) as exc_info:
            searcher.search(queries=["test"], genre="career")

        assert isinstance(exc_info.value.cause, (TypeError, ValueError))


# ---------------------------------------------------------------------------
# 空結果ハンドリング
# ---------------------------------------------------------------------------
class TestEmptyResults:
    """空結果のハンドリングテスト."""

    def test_正常系_itemsが空リストで空RawItemリスト(
        self,
        mock_provider: MagicMock,
    ) -> None:
        """items が空リストの場合は空リストを返す."""
        mock_provider.query.return_value = json.dumps({"items": []})

        searcher = ClaudeCodeSearcher(provider=mock_provider)
        results = searcher.search(queries=["test"], genre="career")

        assert results == []


# ---------------------------------------------------------------------------
# デフォルトプロバイダーのロード
# ---------------------------------------------------------------------------
class TestDefaultProvider:
    """デフォルトプロバイダーロードのテスト."""

    def test_異常系_claude_agent_sdk未インストールでRuntimeError(self) -> None:
        """provider=None かつ claude_agent_sdk 未インストール時に RuntimeError."""
        with pytest.raises(RuntimeError, match="claude_agent_sdk"):
            ClaudeCodeSearcher(provider=None)


# ---------------------------------------------------------------------------
# AgentProvider プロトコル準拠の検証
# ---------------------------------------------------------------------------
class TestAgentProviderProtocol:
    """AgentProvider プロトコルの検証テスト."""

    def test_正常系_runtime_checkableプロトコルである(self) -> None:
        """AgentProvider が runtime_checkable Protocol である."""

        # query メソッドを持つオブジェクトがプロトコルに準拠していること
        class _MockProvider:
            def query(self, *, system_prompt: str, prompt: str, timeout: int) -> str:
                return "{}"

        assert isinstance(_MockProvider(), AgentProvider)
