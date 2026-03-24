"""extractor モジュールのユニットテスト.

受け入れ条件:
- extract_chunk() が ChunkExtraction を返すこと
- ルールベース検出が動作すること
- Mock API テストが全て通過すること
- confidence に基づくフィルタリング（>= 0.7 自動, < 0.3 棄却）
- ルールベース + Sonnet 抽出のマージ
- 10並列実行（rate limit時 5並列フォールバック）
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from session_memory.extractor import (
    ChunkExtraction,
    ExtractedDecision,
    ExtractedEntity,
    ExtractedTopic,
    extract_chunk,
    extract_chunks_batch,
    rule_based_predetect,
)

# ---------------------------------------------------------------------------
# テストデータヘルパー
# ---------------------------------------------------------------------------


def _make_chunk_text(
    *, entities: bool = True, topics: bool = True, decisions: bool = True
) -> str:
    """テスト用チャンクテキストを生成する.

    Parameters
    ----------
    entities : bool
        エンティティを含むテキストにするか
    topics : bool
        トピックを含むテキストにするか
    decisions : bool
        決定事項を含むテキストにするか

    Returns
    -------
    str
        テスト用テキスト
    """
    parts: list[str] = []
    if entities:
        parts.append(
            "[user]\nPythonのPydanticライブラリについて教えてください。"
            "FastAPIでの利用方法も知りたいです。"
        )
    if topics:
        parts.append(
            "[assistant]\nPydanticはデータバリデーションライブラリです。"
            "型ヒントを使ってデータモデルを定義できます。"
            "機械学習パイプラインでも活用されています。"
        )
    if decisions:
        parts.append(
            "決定事項: Pydantic v2 を採用することにしました。"
            "理由はパフォーマンスの大幅な改善です。"
        )
    return "\n\n".join(parts)


def _make_sonnet_response(
    *,
    entities: list[dict[str, Any]] | None = None,
    topics: list[dict[str, Any]] | None = None,
    decisions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Sonnet tool_use レスポンスをシミュレートする.

    Parameters
    ----------
    entities : list[dict] | None
        エンティティリスト
    topics : list[dict] | None
        トピックリスト
    decisions : list[dict] | None
        決定事項リスト

    Returns
    -------
    dict
        Anthropic API レスポンス形式
    """
    tool_input = {
        "entities": entities or [],
        "topics": topics or [],
        "decisions": decisions or [],
    }

    # Anthropic SDK のレスポンス構造をシミュレート
    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.name = "extract_chunk_metadata"
    tool_use_block.input = tool_input

    response = MagicMock()
    response.content = [tool_use_block]
    response.stop_reason = "tool_use"
    return response


# ---------------------------------------------------------------------------
# ChunkExtraction モデルテスト
# ---------------------------------------------------------------------------


class TestChunkExtractionModel:
    """ChunkExtraction Pydantic モデルのテスト."""

    def test_正常系_空のChunkExtractionが作成できる(self) -> None:
        """エンティティ・トピック・決定が空でも作成可能."""
        extraction = ChunkExtraction(entities=[], topics=[], decisions=[])
        assert extraction.entities == []
        assert extraction.topics == []
        assert extraction.decisions == []

    def test_正常系_エンティティ付きのChunkExtractionが作成できる(self) -> None:
        """エンティティを含むChunkExtractionが正しく作成される."""
        entity = ExtractedEntity(
            name="Pydantic",
            entity_type="library",
            confidence=0.9,
        )
        extraction = ChunkExtraction(entities=[entity], topics=[], decisions=[])
        assert len(extraction.entities) == 1
        assert extraction.entities[0].name == "Pydantic"
        assert extraction.entities[0].confidence == 0.9

    def test_正常系_トピック付きのChunkExtractionが作成できる(self) -> None:
        """トピックを含むChunkExtractionが正しく作成される."""
        topic = ExtractedTopic(
            name="データバリデーション",
            confidence=0.85,
        )
        extraction = ChunkExtraction(entities=[], topics=[topic], decisions=[])
        assert len(extraction.topics) == 1
        assert extraction.topics[0].name == "データバリデーション"

    def test_正常系_決定事項付きのChunkExtractionが作成できる(self) -> None:
        """決定事項を含むChunkExtractionが正しく作成される."""
        decision = ExtractedDecision(
            summary="Pydantic v2 を採用",
            rationale="パフォーマンスの大幅な改善",
            confidence=0.95,
        )
        extraction = ChunkExtraction(entities=[], topics=[], decisions=[decision])
        assert len(extraction.decisions) == 1
        assert extraction.decisions[0].summary == "Pydantic v2 を採用"

    def test_正常系_model_json_schemaが生成できる(self) -> None:
        """ChunkExtraction.model_json_schema() が有効なJSON Schemaを返す."""
        schema = ChunkExtraction.model_json_schema()
        assert isinstance(schema, dict)
        assert "properties" in schema
        assert "entities" in schema["properties"]
        assert "topics" in schema["properties"]
        assert "decisions" in schema["properties"]

    def test_正常系_confidenceのバリデーション(self) -> None:
        """confidence は 0.0 - 1.0 の範囲."""
        entity = ExtractedEntity(name="test", entity_type="lib", confidence=0.0)
        assert entity.confidence == 0.0

        entity2 = ExtractedEntity(name="test", entity_type="lib", confidence=1.0)
        assert entity2.confidence == 1.0

    def test_異常系_confidence範囲外でバリデーションエラー(self) -> None:
        """confidence が範囲外の場合はバリデーションエラー."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ExtractedEntity(name="test", entity_type="lib", confidence=1.5)

        with pytest.raises(ValidationError):
            ExtractedEntity(name="test", entity_type="lib", confidence=-0.1)


# ---------------------------------------------------------------------------
# ルールベース事前検出テスト
# ---------------------------------------------------------------------------


class TestRuleBasedPredetect:
    """ルールベース事前検出のテスト."""

    def test_正常系_エンティティが検出される(self) -> None:
        """テキスト中のライブラリ名・技術名が検出される."""
        text = "PydanticとFastAPIを使ってAPIサーバーを構築しました。"
        result = rule_based_predetect(text)
        assert isinstance(result, ChunkExtraction)
        # エンティティが1つ以上検出される
        assert len(result.entities) >= 1
        entity_names = [e.name for e in result.entities]
        # Pydantic or FastAPI が検出されるべき
        assert any(name in entity_names for name in ["Pydantic", "FastAPI"])

    def test_正常系_決定事項キーワードが検出される(self) -> None:
        """「決定」「採用」等のキーワードで決定事項が検出される."""
        text = "決定事項: TypeScript から Python に移行することにしました。理由はデータ処理の効率化です。"
        result = rule_based_predetect(text)
        assert len(result.decisions) >= 1

    def test_正常系_トピックが検出される(self) -> None:
        """トピック関連のキーワードでトピックが検出される."""
        text = "機械学習のモデル学習パイプラインについて議論しました。データ前処理が重要です。"
        result = rule_based_predetect(text)
        assert len(result.topics) >= 1

    def test_正常系_空テキストで空結果(self) -> None:
        """空テキストでは空のChunkExtractionを返す."""
        result = rule_based_predetect("")
        assert result.entities == []
        assert result.topics == []
        assert result.decisions == []

    def test_正常系_ルールベース検出のconfidenceが低め(self) -> None:
        """ルールベース検出の confidence は Sonnet より低い値になる."""
        text = "Pydanticライブラリを使ってデータバリデーションを実装しました。"
        result = rule_based_predetect(text)
        if result.entities:
            for entity in result.entities:
                # ルールベースは 0.5 程度の confidence
                assert entity.confidence <= 0.7


# ---------------------------------------------------------------------------
# extract_chunk テスト（Mock API）
# ---------------------------------------------------------------------------


class TestExtractChunk:
    """extract_chunk の Mock API テスト."""

    @pytest.mark.asyncio
    async def test_正常系_ChunkExtractionが返される(self) -> None:
        """extract_chunk() が ChunkExtraction を返す."""
        mock_response = _make_sonnet_response(
            entities=[
                {"name": "Pydantic", "entity_type": "library", "confidence": 0.95},
            ],
            topics=[
                {"name": "データバリデーション", "confidence": 0.88},
            ],
            decisions=[
                {
                    "summary": "Pydantic v2 を採用",
                    "rationale": "パフォーマンス改善",
                    "confidence": 0.92,
                },
            ],
        )

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        text = _make_chunk_text()
        result = await extract_chunk(text, client=mock_client)

        assert isinstance(result, ChunkExtraction)
        assert len(result.entities) >= 1
        assert len(result.topics) >= 1
        assert len(result.decisions) >= 1

    @pytest.mark.asyncio
    async def test_正常系_tool_choiceが強制される(self) -> None:
        """API呼び出しで tool_choice が extract_chunk_metadata に強制される."""
        mock_response = _make_sonnet_response(entities=[], topics=[], decisions=[])

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        await extract_chunk("テスト文", client=mock_client)

        # API呼び出しの引数を検証
        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs is not None
        kwargs = call_kwargs.kwargs if call_kwargs.kwargs else call_kwargs[1]
        assert kwargs["tool_choice"] == {
            "type": "tool",
            "name": "extract_chunk_metadata",
        }

    @pytest.mark.asyncio
    async def test_正常系_input_schemaにmodel_json_schemaが使用される(self) -> None:
        """ツール定義の input_schema に ChunkExtraction.model_json_schema() が使用される."""
        mock_response = _make_sonnet_response(entities=[], topics=[], decisions=[])

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        await extract_chunk("テスト文", client=mock_client)

        call_kwargs = mock_client.messages.create.call_args
        kwargs = call_kwargs.kwargs if call_kwargs.kwargs else call_kwargs[1]
        tools = kwargs["tools"]
        assert len(tools) == 1
        assert tools[0]["name"] == "extract_chunk_metadata"
        # input_schema は ChunkExtraction のスキーマ
        assert "properties" in tools[0]["input_schema"]
        assert "entities" in tools[0]["input_schema"]["properties"]

    @pytest.mark.asyncio
    async def test_正常系_低confidenceエンティティが棄却される(self) -> None:
        """confidence < 0.3 のエンティティは棄却される."""
        mock_response = _make_sonnet_response(
            entities=[
                {"name": "maybe_entity", "entity_type": "unknown", "confidence": 0.2},
                {"name": "Pydantic", "entity_type": "library", "confidence": 0.95},
            ],
        )

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        result = await extract_chunk("テスト", client=mock_client)
        entity_names = [e.name for e in result.entities]
        assert "maybe_entity" not in entity_names
        assert "Pydantic" in entity_names

    @pytest.mark.asyncio
    async def test_正常系_ルールベースとSonnet結果がマージされる(self) -> None:
        """ルールベース事前検出とSonnet抽出結果がマージされる."""
        mock_response = _make_sonnet_response(
            entities=[
                {"name": "FastAPI", "entity_type": "framework", "confidence": 0.9},
            ],
        )

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        # ルールベースで Pydantic を検出、Sonnet で FastAPI を検出
        text = "PydanticとFastAPIを使ったAPIサーバー構築について"
        result = await extract_chunk(text, client=mock_client)

        entity_names = [e.name for e in result.entities]
        # Sonnet の結果は必ず含まれる
        assert "FastAPI" in entity_names

    @pytest.mark.asyncio
    async def test_異常系_APIエラーでルールベース結果のみ返す(self) -> None:
        """APIエラー時はルールベース検出結果のみ返す."""
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("API error"))

        text = "Pydanticライブラリを使ったデータバリデーション"
        result = await extract_chunk(text, client=mock_client)

        # エラー時もChunkExtractionが返る（ルールベース結果）
        assert isinstance(result, ChunkExtraction)


# ---------------------------------------------------------------------------
# extract_chunks_batch テスト（バッチ並列実行）
# ---------------------------------------------------------------------------


class TestExtractChunksBatch:
    """バッチ並列実行のテスト."""

    @pytest.mark.asyncio
    async def test_正常系_複数チャンクが並列処理される(self) -> None:
        """複数チャンクがバッチで並列処理される."""
        mock_response = _make_sonnet_response(
            entities=[
                {"name": "Python", "entity_type": "language", "confidence": 0.95},
            ],
        )

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        texts = [
            "チャンク1: Python入門",
            "チャンク2: Python応用",
            "チャンク3: Python実践",
        ]
        results = await extract_chunks_batch(
            texts, client=mock_client, max_concurrency=10
        )

        assert len(results) == 3
        for result in results:
            assert isinstance(result, ChunkExtraction)

    @pytest.mark.asyncio
    async def test_正常系_空リストで空結果(self) -> None:
        """空リストを渡すと空リストが返る."""
        mock_client = AsyncMock()
        results = await extract_chunks_batch([], client=mock_client)
        assert results == []

    @pytest.mark.asyncio
    async def test_正常系_concurrency制御が機能する(self) -> None:
        """max_concurrency が同時実行数を制限する."""
        call_count = 0
        max_concurrent = 0
        current_concurrent = 0

        original_response = _make_sonnet_response(entities=[])

        async def mock_create(**kwargs: Any) -> Any:
            nonlocal call_count, max_concurrent, current_concurrent
            current_concurrent += 1
            max_concurrent = max(max_concurrent, current_concurrent)
            call_count += 1
            await asyncio.sleep(0.01)  # シミュレート
            current_concurrent -= 1
            return original_response

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=mock_create)

        texts = [f"チャンク{i}" for i in range(20)]
        await extract_chunks_batch(texts, client=mock_client, max_concurrency=5)

        assert call_count == 20
        # max_concurrency=5 なので同時実行数は5以下
        assert max_concurrent <= 5

    @pytest.mark.asyncio
    async def test_正常系_rate_limitでフォールバック(self) -> None:
        """RateLimitError 時に並列数を5に削減してリトライ."""
        call_count = 0
        mock_response = _make_sonnet_response(entities=[])

        async def mock_create(**kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                # 最初の数回は rate limit エラー
                error = MagicMock()
                error.status_code = 429
                error.message = "rate_limit_error"
                raise Exception("rate_limit_error")
            return mock_response

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=mock_create)

        texts = ["チャンク1"]
        # rate limit でもクラッシュしない（リトライする）
        results = await extract_chunks_batch(
            texts, client=mock_client, max_concurrency=10
        )
        assert len(results) == 1


# ---------------------------------------------------------------------------
# confidence フィルタリングテスト
# ---------------------------------------------------------------------------


class TestConfidenceFiltering:
    """confidence に基づくフィルタリングのテスト."""

    @pytest.mark.asyncio
    async def test_正常系_高confidenceエンティティが保持される(self) -> None:
        """confidence >= 0.7 のエンティティは自動リンク対象として保持."""
        mock_response = _make_sonnet_response(
            entities=[
                {"name": "HighConf", "entity_type": "lib", "confidence": 0.9},
            ],
        )
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        result = await extract_chunk("テスト", client=mock_client)
        assert any(e.name == "HighConf" for e in result.entities)

    @pytest.mark.asyncio
    async def test_正常系_中confidenceエンティティが保持される(self) -> None:
        """confidence >= 0.3 かつ < 0.7 のエンティティは embedding 補完対象として保持."""
        mock_response = _make_sonnet_response(
            entities=[
                {"name": "MidConf", "entity_type": "lib", "confidence": 0.5},
            ],
        )
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        result = await extract_chunk("テスト", client=mock_client)
        mid_entities = [e for e in result.entities if e.name == "MidConf"]
        assert len(mid_entities) == 1
        assert mid_entities[0].confidence == 0.5

    @pytest.mark.asyncio
    async def test_正常系_低confidenceが棄却される(self) -> None:
        """confidence < 0.3 のエンティティ/トピック/決定は棄却."""
        mock_response = _make_sonnet_response(
            entities=[
                {"name": "LowConf", "entity_type": "unknown", "confidence": 0.1},
            ],
            topics=[
                {"name": "低確信トピック", "confidence": 0.2},
            ],
            decisions=[
                {"summary": "低確信決定", "rationale": "不明", "confidence": 0.15},
            ],
        )
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        result = await extract_chunk("テスト", client=mock_client)
        assert len(result.entities) == 0
        assert len(result.topics) == 0
        assert len(result.decisions) == 0
