"""Unit tests for data_pipeline.structurer.extractor."""

from __future__ import annotations

import json

import pytest

from data_pipeline.collectors.base import CollectedItem
from data_pipeline.structurer.extractor import (
    LlmExtractor,
    _empty_result,
    _parse_response,
)


def _make_item(
    raw_text: str = "S&P 500は2026年3月24日に5,800を突破し過去最高値を更新した。",
    title: str = "S&P 500 過去最高値更新",
    url: str = "https://example.com/article",
    language: str = "ja",
) -> CollectedItem:
    return CollectedItem(
        source_id="test",
        url=url,
        title=title,
        raw_text=raw_text,
        collection_method="rss",
        language=language,
    )


class MockLLM:
    """テスト用モックLLMクライアント."""

    def __init__(self, response: str = "") -> None:
        self.response = response
        self.call_count = 0
        self.last_prompt = ""

    def query(self, prompt: str) -> str:
        self.call_count += 1
        self.last_prompt = prompt
        return self.response


_SAMPLE_RESPONSE = json.dumps({
    "facts": [
        {
            "content": "S&P 500は2026年3月24日に5,800を突破し過去最高値を更新",
            "fact_type": "market_event",
            "confidence": 0.95,
            "about_entities": [
                {"name": "S&P 500", "entity_type": "index"},
            ],
        },
    ],
    "claims": [
        {
            "content": "FRBは2026年中に利下げを開始する可能性が高い",
            "claim_type": "analyst_forecast",
            "sentiment": "positive",
            "about_entities": [
                {"name": "FRB", "entity_type": "organization"},
            ],
        },
    ],
    "topics": [
        {"name": "米国株式市場", "category": "equity"},
    ],
}, ensure_ascii=False)


class TestParseResponse:
    """_parse_response のテスト."""

    def test_正常系_有効なJSONをパース(self) -> None:
        result = _parse_response(_SAMPLE_RESPONSE)
        assert len(result["facts"]) == 1
        assert result["facts"][0]["content"] == "S&P 500は2026年3月24日に5,800を突破し過去最高値を更新"
        assert result["facts"][0]["fact_type"] == "market_event"
        assert result["facts"][0]["about_entities"][0]["name"] == "S&P 500"
        assert len(result["claims"]) == 1
        assert result["claims"][0]["sentiment"] == "positive"
        assert len(result["topics"]) == 1

    def test_正常系_markdownフェンス付きJSON(self) -> None:
        raw = f"```json\n{_SAMPLE_RESPONSE}\n```"
        result = _parse_response(raw)
        assert len(result["facts"]) == 1

    def test_正常系_デフォルト値が補完される(self) -> None:
        raw = json.dumps({
            "facts": [{"content": "Test fact"}],
            "claims": [{"content": "Test claim"}],
            "topics": [],
        })
        result = _parse_response(raw)
        assert result["facts"][0]["confidence"] == 0.8
        assert result["facts"][0]["fact_type"] == "general"
        assert result["facts"][0]["about_entities"] == []
        assert result["claims"][0]["sentiment"] == "neutral"

    def test_異常系_不正JSONで空結果(self) -> None:
        result = _parse_response("not json at all")
        assert result == _empty_result()

    def test_エッジケース_空文字列で空結果(self) -> None:
        result = _parse_response("")
        assert result == _empty_result()


class TestLlmExtractor:
    """LlmExtractor のテスト."""

    def test_正常系_1アイテム抽出(self) -> None:
        mock = MockLLM(response=_SAMPLE_RESPONSE)
        extractor = LlmExtractor(llm_client=mock)
        item = _make_item()

        result = extractor.extract_one(item)

        assert mock.call_count == 1
        assert len(result["facts"]) == 1
        assert len(result["claims"]) == 1
        assert "S&P 500" in mock.last_prompt

    def test_正常系_空テキストは抽出スキップ(self) -> None:
        mock = MockLLM()
        extractor = LlmExtractor(llm_client=mock)
        item = _make_item(raw_text="")

        result = extractor.extract_one(item)

        assert mock.call_count == 0
        assert result == _empty_result()

    def test_正常系_テキスト切り詰め(self) -> None:
        mock = MockLLM(response=json.dumps({"facts": [], "claims": [], "topics": []}))
        extractor = LlmExtractor(llm_client=mock, max_text_length=50)
        item = _make_item(raw_text="A" * 200)

        extractor.extract_one(item)

        # プロンプトに切り詰めたテキストが含まれる
        assert "A" * 50 in mock.last_prompt
        assert "A" * 200 not in mock.last_prompt

    def test_正常系_extract_manyで複数抽出(self) -> None:
        mock = MockLLM(response=_SAMPLE_RESPONSE)
        extractor = LlmExtractor(llm_client=mock, request_delay=0)
        items = [_make_item(), _make_item(title="Article 2")]

        results = extractor.extract_many(items)

        assert len(results) == 2
        assert mock.call_count == 2

    def test_異常系_LLMエラーで空結果(self) -> None:
        class FailingLLM:
            def query(self, prompt: str) -> str:
                raise RuntimeError("LLM error")

        extractor = LlmExtractor(llm_client=FailingLLM())
        result = extractor.extract_one(_make_item())
        assert result == _empty_result()

    def test_正常系_プロンプトにタイトルとURLが含まれる(self) -> None:
        mock = MockLLM(response=json.dumps({"facts": [], "claims": [], "topics": []}))
        extractor = LlmExtractor(llm_client=mock)
        item = _make_item(
            title="金融庁ニュース",
            url="https://www.fsa.go.jp/news",
        )

        extractor.extract_one(item)

        assert "金融庁ニュース" in mock.last_prompt
        assert "https://www.fsa.go.jp/news" in mock.last_prompt


class TestExtractorE2E:
    """LlmExtractor + converter の統合テスト."""

    def test_正常系_抽出結果をStructuredOutputに変換(self) -> None:
        from data_pipeline.structurer.converter import build_from_extracted

        mock = MockLLM(response=_SAMPLE_RESPONSE)
        extractor = LlmExtractor(llm_client=mock, request_delay=0)
        items = [_make_item()]

        extractions = extractor.extract_many(items)
        output = build_from_extracted(items, extractions, authority_level=4)

        assert output.fact_count == 1
        assert output.claim_count == 1
        assert len(output.topics) == 1
        assert "S&P 500" in output.entity_names
        assert "FRB" in output.entity_names
        assert output.sources[0].authority_level == "analyst"
