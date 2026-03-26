"""creator_enrichment.phases.extract のテスト.

ContentExtractor による LLMClient 呼び出し・抽出ロジックを検証する。
- プロンプトテンプレート適用（genre, title 等の埋め込み）
- JSON コードブロック除去
- CycleData 変換（全4タスク出力の統合）
- 不正 JSON / 空レスポンスのエラーハンドリング
- extract_batch の集約動作
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from creator_enrichment.phases.extract import ContentExtractor
from creator_enrichment.types import CycleData, RawItem
from creator_enrichment.utils import strip_json_codeblock


# ---------------------------------------------------------------------------
# フィクスチャ: サンプル抽出結果 JSON
# ---------------------------------------------------------------------------
def _make_extraction_response(
    content_type: str = "Fact",
    title: str = "テスト記事",
    body: str = "テスト本文の要約",
    source_url: str = "https://example.com/article-1",
) -> dict:
    """LLM が返す抽出結果の辞書を生成する."""
    return {
        "content_type": content_type,
        "title": title,
        "body": body,
        "source_url": source_url,
        "source_type": "web",
        "language": "ja",
        "entities": [
            {"name": "Instagram", "entity_type": "platform"},
            {"name": "Google", "entity_type": "company"},
        ],
        "concepts": [
            {
                "name": "SNS集客",
                "category": "AcquisitionChannel",
                "new_category": False,
            },
            {
                "name": "スキル販売",
                "category": "MonetizationMethod",
                "new_category": False,
            },
        ],
        "serves_as": [
            {
                "entity_name": "Instagram",
                "concept_name": "SNS集客",
                "context": "主要集客チャネルとして",
            },
        ],
        "concept_relations": [
            {
                "from_concept": "SNS集客",
                "to_concept": "スキル販売",
                "rel_type": "ENABLES",
            },
        ],
    }


# ---------------------------------------------------------------------------
# JSON コードブロック除去
# ---------------------------------------------------------------------------
class TestStripJsonCodeblock:
    """strip_json_codeblock のテスト."""

    def test_正常系_jsonコードブロックを除去できる(self) -> None:
        """```json ... ``` コードブロックを正しく除去する."""
        raw = '```json\n{"key": "value"}\n```'
        result = strip_json_codeblock(raw)
        assert result == '{"key": "value"}'

    def test_正常系_言語指定なしコードブロックを除去できる(self) -> None:
        """``` ... ``` コードブロック（言語指定なし）を正しく除去する."""
        raw = '```\n{"key": "value"}\n```'
        result = strip_json_codeblock(raw)
        assert result == '{"key": "value"}'

    def test_正常系_コードブロックなしはそのまま(self) -> None:
        """コードブロックなしの文字列はそのまま返す."""
        raw = '{"key": "value"}'
        result = strip_json_codeblock(raw)
        assert result == '{"key": "value"}'

    def test_正常系_前後の空白を除去する(self) -> None:
        """前後の空白を除去する."""
        raw = '  \n```json\n{"key": "value"}\n```\n  '
        result = strip_json_codeblock(raw)
        assert result == '{"key": "value"}'

    def test_正常系_空文字列(self) -> None:
        """空文字列を渡した場合は空文字列を返す."""
        assert strip_json_codeblock("") == ""

    def test_正常系_コードブロック内の複数行(self) -> None:
        """コードブロック内に複数行の JSON がある場合も正しく処理する."""
        raw = '```json\n{\n  "key": "value",\n  "num": 42\n}\n```'
        result = strip_json_codeblock(raw)
        parsed = json.loads(result)
        assert parsed == {"key": "value", "num": 42}


# ---------------------------------------------------------------------------
# extract_single: プロンプトテンプレート適用
# ---------------------------------------------------------------------------
class TestPromptTemplate:
    """プロンプトテンプレートの適用テスト."""

    def test_正常系_genreがプロンプトに埋め込まれる(
        self,
        mock_llm_client: MagicMock,
    ) -> None:
        """genre 文字列がプロンプトに正しく埋め込まれる."""
        response_data = _make_extraction_response()
        mock_llm_client.query.return_value = json.dumps(
            response_data, ensure_ascii=False
        )

        extractor = ContentExtractor(llm_client=mock_llm_client)
        item = RawItem(
            url="https://example.com/article-1",
            title="テスト記事",
            content="テスト本文",
            source="tavily_search",
        )
        extractor.extract_single(item=item, genre="career")

        prompt = mock_llm_client.query.call_args[0][0]
        assert "career" in prompt

    def test_正常系_titleがプロンプトに埋め込まれる(
        self,
        mock_llm_client: MagicMock,
    ) -> None:
        """title がプロンプトに正しく埋め込まれる."""
        response_data = _make_extraction_response()
        mock_llm_client.query.return_value = json.dumps(
            response_data, ensure_ascii=False
        )

        extractor = ContentExtractor(llm_client=mock_llm_client)
        item = RawItem(
            url="https://example.com/article-1",
            title="副業の始め方ガイド",
            content="副業を始めるには...",
            source="tavily_search",
        )
        extractor.extract_single(item=item, genre="career")

        prompt = mock_llm_client.query.call_args[0][0]
        assert "副業の始め方ガイド" in prompt

    def test_正常系_source_urlがプロンプトに埋め込まれる(
        self,
        mock_llm_client: MagicMock,
    ) -> None:
        """source_url がプロンプトに正しく埋め込まれる."""
        response_data = _make_extraction_response()
        mock_llm_client.query.return_value = json.dumps(
            response_data, ensure_ascii=False
        )

        extractor = ContentExtractor(llm_client=mock_llm_client)
        item = RawItem(
            url="https://example.com/my-article",
            title="テスト記事",
            content="テスト本文",
            source="tavily_search",
        )
        extractor.extract_single(item=item, genre="career")

        prompt = mock_llm_client.query.call_args[0][0]
        assert "https://example.com/my-article" in prompt


# ---------------------------------------------------------------------------
# extract_single: JSON パース
# ---------------------------------------------------------------------------
class TestExtractSingle:
    """extract_single のパースと返り値テスト."""

    def test_正常系_JSONレスポンスをパースして辞書を返す(
        self,
        mock_llm_client: MagicMock,
    ) -> None:
        """正常な JSON レスポンスが辞書としてパースされる."""
        response_data = _make_extraction_response()
        mock_llm_client.query.return_value = json.dumps(
            response_data, ensure_ascii=False
        )

        extractor = ContentExtractor(llm_client=mock_llm_client)
        item = RawItem(
            url="https://example.com/article-1",
            title="テスト記事",
            content="テスト本文",
            source="tavily_search",
        )
        result = extractor.extract_single(item=item, genre="career")

        assert result["content_type"] == "Fact"
        assert result["title"] == "テスト記事"
        assert len(result["entities"]) == 2
        assert len(result["concepts"]) == 2
        assert len(result["serves_as"]) == 1
        assert len(result["concept_relations"]) == 1

    def test_正常系_jsonコードブロック付きレスポンスをパースできる(
        self,
        mock_llm_client: MagicMock,
    ) -> None:
        """```json ... ``` でラップされたレスポンスを正しくパースする."""
        response_data = _make_extraction_response()
        raw_json = json.dumps(response_data, ensure_ascii=False)
        wrapped = f"```json\n{raw_json}\n```"
        mock_llm_client.query.return_value = wrapped

        extractor = ContentExtractor(llm_client=mock_llm_client)
        item = RawItem(
            url="https://example.com/article-1",
            title="テスト記事",
            content="テスト本文",
            source="tavily_search",
        )
        result = extractor.extract_single(item=item, genre="career")

        assert result["content_type"] == "Fact"

    def test_異常系_不正JSONでValueError(
        self,
        mock_llm_client: MagicMock,
    ) -> None:
        """パース不能な JSON で ValueError が発生する."""
        mock_llm_client.query.return_value = "This is not valid JSON at all"

        extractor = ContentExtractor(llm_client=mock_llm_client)
        item = RawItem(
            url="https://example.com/article-1",
            title="テスト記事",
            content="テスト本文",
            source="tavily_search",
        )

        with pytest.raises(ValueError, match="Failed to parse"):
            extractor.extract_single(item=item, genre="career")

    def test_異常系_空レスポンスでValueError(
        self,
        mock_llm_client: MagicMock,
    ) -> None:
        """空レスポンスで ValueError が発生する."""
        mock_llm_client.query.return_value = ""

        extractor = ContentExtractor(llm_client=mock_llm_client)
        item = RawItem(
            url="https://example.com/article-1",
            title="テスト記事",
            content="テスト本文",
            source="tavily_search",
        )

        with pytest.raises(ValueError, match="Empty response"):
            extractor.extract_single(item=item, genre="career")

    def test_正常系_content_typeがTipの場合(
        self,
        mock_llm_client: MagicMock,
    ) -> None:
        """content_type=Tip のレスポンスが正しくパースされる."""
        response_data = _make_extraction_response(content_type="Tip")
        mock_llm_client.query.return_value = json.dumps(
            response_data, ensure_ascii=False
        )

        extractor = ContentExtractor(llm_client=mock_llm_client)
        item = RawItem(
            url="https://example.com/article-1",
            title="テスト記事",
            content="テスト本文",
            source="tavily_search",
        )
        result = extractor.extract_single(item=item, genre="career")

        assert result["content_type"] == "Tip"

    def test_正常系_content_typeがStoryの場合(
        self,
        mock_llm_client: MagicMock,
    ) -> None:
        """content_type=Story のレスポンスが正しくパースされる."""
        response_data = _make_extraction_response(content_type="Story")
        mock_llm_client.query.return_value = json.dumps(
            response_data, ensure_ascii=False
        )

        extractor = ContentExtractor(llm_client=mock_llm_client)
        item = RawItem(
            url="https://example.com/article-1",
            title="テスト記事",
            content="テスト本文",
            source="tavily_search",
        )
        result = extractor.extract_single(item=item, genre="career")

        assert result["content_type"] == "Story"


# ---------------------------------------------------------------------------
# extract_batch: 集約テスト
# ---------------------------------------------------------------------------
class TestExtractBatch:
    """extract_batch の集約動作テスト."""

    def test_正常系_複数アイテムをCycleDataに集約する(
        self,
        mock_llm_client: MagicMock,
    ) -> None:
        """複数アイテムの抽出結果を CycleData に正しく集約する."""
        # Fact, Tip, Story の3タイプ
        responses = [
            _make_extraction_response(
                content_type="Fact",
                title="事実の記事",
                body="事実の要約",
                source_url="https://example.com/fact",
            ),
            _make_extraction_response(
                content_type="Tip",
                title="ノウハウの記事",
                body="ノウハウの要約",
                source_url="https://example.com/tip",
            ),
            _make_extraction_response(
                content_type="Story",
                title="体験談の記事",
                body="体験談の要約",
                source_url="https://example.com/story",
            ),
        ]

        mock_llm_client.query.side_effect = [
            json.dumps(r, ensure_ascii=False) for r in responses
        ]

        extractor = ContentExtractor(llm_client=mock_llm_client)
        items = [
            RawItem(
                url="https://example.com/fact",
                title="事実の記事",
                content="事実の内容",
                source="tavily_search",
            ),
            RawItem(
                url="https://example.com/tip",
                title="ノウハウの記事",
                content="ノウハウの内容",
                source="tavily_search",
            ),
            RawItem(
                url="https://example.com/story",
                title="体験談の記事",
                content="体験談の内容",
                source="reddit",
            ),
        ]

        with patch("creator_enrichment.phases.extract.time.sleep"):
            result = extractor.extract_batch(items=items, genre="career")

        # CycleData の基本構造を検証
        assert result["genre"] == "career"
        assert result["cycle_id"].startswith("cycle-")
        assert len(result["sources"]) == 3
        assert len(result["facts"]) == 1
        assert len(result["tips"]) == 1
        assert len(result["stories"]) == 1
        # entities は各レスポンスから2つずつ = 計6
        assert len(result["entities"]) == 6
        # concepts は各レスポンスから2つずつ = 計6
        assert len(result["concepts"]) == 6
        # serves_as は各レスポンスから1つずつ = 計3
        assert len(result["serves_as"]) == 3
        # concept_relations は各レスポンスから1つずつ = 計3
        assert len(result["concept_relations"]) == 3

    def test_正常系_空リストで空のCycleDataを返す(
        self,
        mock_llm_client: MagicMock,
    ) -> None:
        """空の items リストを渡すと空の CycleData を返す."""
        extractor = ContentExtractor(llm_client=mock_llm_client)

        result = extractor.extract_batch(items=[], genre="career")

        assert result["genre"] == "career"
        assert result["cycle_id"].startswith("cycle-")
        assert result["sources"] == []
        assert result["facts"] == []
        assert result["tips"] == []
        assert result["stories"] == []
        assert result["entities"] == []
        assert result["concepts"] == []
        assert result["serves_as"] == []
        assert result["concept_relations"] == []

    def test_正常系_APIが呼び出し間にsleepを実行する(
        self,
        mock_llm_client: MagicMock,
    ) -> None:
        """複数アイテム処理時に sleep が呼び出し間に実行される."""
        responses = [
            _make_extraction_response(source_url="https://example.com/1"),
            _make_extraction_response(source_url="https://example.com/2"),
        ]
        mock_llm_client.query.side_effect = [
            json.dumps(r, ensure_ascii=False) for r in responses
        ]

        extractor = ContentExtractor(llm_client=mock_llm_client)
        items = [
            RawItem(
                url="https://example.com/1",
                title="記事1",
                content="本文1",
                source="tavily_search",
            ),
            RawItem(
                url="https://example.com/2",
                title="記事2",
                content="本文2",
                source="tavily_search",
            ),
        ]

        with patch("creator_enrichment.phases.extract.time.sleep") as mock_sleep:
            extractor.extract_batch(items=items, genre="career")

        # 2件のアイテム間に1回の sleep が呼ばれる
        assert mock_sleep.call_count == 1

    def test_正常系_cycle_idのフォーマットが正しい(
        self,
        mock_llm_client: MagicMock,
    ) -> None:
        """cycle_id が cycle-YYYYMMDD-HHMMSS 形式である."""
        import re

        extractor = ContentExtractor(llm_client=mock_llm_client)
        result = extractor.extract_batch(items=[], genre="career")

        pattern = r"^cycle-\d{8}-\d{6}$"
        assert re.match(pattern, result["cycle_id"])

    def test_正常系_sourcesにurl_titleが含まれる(
        self,
        mock_llm_client: MagicMock,
    ) -> None:
        """sources の各要素に url と title が含まれる."""
        response_data = _make_extraction_response()
        mock_llm_client.query.return_value = json.dumps(
            response_data, ensure_ascii=False
        )

        extractor = ContentExtractor(llm_client=mock_llm_client)
        items = [
            RawItem(
                url="https://example.com/article-1",
                title="テスト記事",
                content="テスト本文",
                source="tavily_search",
            ),
        ]

        with patch("creator_enrichment.phases.extract.time.sleep"):
            result = extractor.extract_batch(items=items, genre="career")

        assert result["sources"][0]["url"] == "https://example.com/article-1"
        assert result["sources"][0]["title"] == "テスト記事"

    def test_正常系_sourcesにpublished_at等メタデータが含まれる(
        self,
        mock_llm_client: MagicMock,
    ) -> None:
        """RawItem のメタデータが sources に引き継がれる."""
        response_data = _make_extraction_response()
        mock_llm_client.query.return_value = json.dumps(
            response_data, ensure_ascii=False
        )

        extractor = ContentExtractor(llm_client=mock_llm_client)
        items = [
            RawItem(
                url="https://example.com/article-1",
                title="テスト記事",
                content="テスト本文",
                source="tavily_search",
                published_at="2026-03-26T01:23:45+00:00",
                collected_at="2026-03-26T02:34:56+00:00",
                source_type="web",
                authority_level="blog",
                language="ja",
            ),
        ]

        with patch("creator_enrichment.phases.extract.time.sleep"):
            result = extractor.extract_batch(items=items, genre="career")

        source = result["sources"][0]
        assert source["published_at"] == "2026-03-26T01:23:45+00:00"
        assert source["collected_at"] == "2026-03-26T02:34:56+00:00"
        assert source["source_type"] == "web"
        assert source["authority_level"] == "blog"
        assert source["language"] == "ja"

    def test_正常系_factsにbodyとsource_urlが含まれる(
        self,
        mock_llm_client: MagicMock,
    ) -> None:
        """facts の各要素に text, source_url 等が含まれる."""
        response_data = _make_extraction_response(
            content_type="Fact",
            body="統計データの要約",
            source_url="https://example.com/fact-1",
        )
        mock_llm_client.query.return_value = json.dumps(
            response_data, ensure_ascii=False
        )

        extractor = ContentExtractor(llm_client=mock_llm_client)
        items = [
            RawItem(
                url="https://example.com/fact-1",
                title="統計データ記事",
                content="統計データの内容",
                source="tavily_search",
            ),
        ]

        with patch("creator_enrichment.phases.extract.time.sleep"):
            result = extractor.extract_batch(items=items, genre="career")

        assert len(result["facts"]) == 1
        fact = result["facts"][0]
        assert fact["text"] == "統計データの要約"
        assert fact["source_url"] == "https://example.com/fact-1"

    def test_異常系_1件失敗しても他は処理される(
        self,
        mock_llm_client: MagicMock,
    ) -> None:
        """バッチ中の1件が失敗しても他のアイテムは処理される."""
        good_response = _make_extraction_response(
            content_type="Fact",
            source_url="https://example.com/good",
        )

        mock_llm_client.query.side_effect = [
            "invalid json",  # 1件目: 失敗
            json.dumps(good_response, ensure_ascii=False),  # 2件目: 成功
        ]

        extractor = ContentExtractor(llm_client=mock_llm_client)
        items = [
            RawItem(
                url="https://example.com/bad",
                title="失敗記事",
                content="失敗内容",
                source="tavily_search",
            ),
            RawItem(
                url="https://example.com/good",
                title="成功記事",
                content="成功内容",
                source="tavily_search",
            ),
        ]

        with patch("creator_enrichment.phases.extract.time.sleep"):
            result = extractor.extract_batch(items=items, genre="career")

        # 成功した1件分のみ
        assert len(result["sources"]) == 1
        assert len(result["facts"]) == 1
