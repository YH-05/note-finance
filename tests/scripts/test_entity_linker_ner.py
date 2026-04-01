"""Tests for entity_linker._ner_fill_about_entities.

--ner-fallback フラグで about_entities 空の Fact/Claim に
NER 自動補完される機能のユニットテスト。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_data(
    *,
    facts: list[dict[str, Any]] | None = None,
    claims: list[dict[str, Any]] | None = None,
    entities: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build minimal graph-queue data for testing."""
    chunk: dict[str, Any] = {}
    if facts is not None:
        chunk["facts"] = facts
    if claims is not None:
        chunk["claims"] = claims
    return {
        "entities": entities or [],
        "sources": [
            {
                "chunks": [chunk],
            }
        ],
    }


# ---------------------------------------------------------------------------
# _ner_fill_about_entities tests
# ---------------------------------------------------------------------------


class TestNerFillAboutEntities:
    """_ner_fill_about_entities のユニットテスト。"""

    def test_正常系_about_entities空のfactにentityが補完される(self) -> None:
        """about_entities が空の Fact に対して NER 結果が補完されること。"""
        from entity_linker import _ner_fill_about_entities

        data = _make_data(
            facts=[
                {"content": "Apple reported record revenue.", "about_entities": []},
            ],
            entities=[],
        )

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"0": ["Apple"]}')]

        with patch("entity_linker.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = mock_response

            result = _ner_fill_about_entities(data)

        fact = result["sources"][0]["chunks"][0]["facts"][0]
        assert "Apple" in fact["about_entities"]

    def test_正常系_about_entities空のclaimにentityが補完される(self) -> None:
        """about_entities が空の Claim に対して NER 結果が補完されること。"""
        from entity_linker import _ner_fill_about_entities

        data = _make_data(
            claims=[
                {"content": "Microsoft Azure grows 30%.", "about_entities": []},
            ],
            entities=[],
        )

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"0": ["Microsoft", "Azure"]}')]

        with patch("entity_linker.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = mock_response

            result = _ner_fill_about_entities(data)

        claim = result["sources"][0]["chunks"][0]["claims"][0]
        assert "Microsoft" in claim["about_entities"]
        assert "Azure" in claim["about_entities"]

    def test_正常系_data_entitiesに重複なく追加される(self) -> None:
        """抽出した entity 名が data['entities'] に重複なく追加されること。"""
        from entity_linker import _ner_fill_about_entities

        data = _make_data(
            facts=[
                {"content": "Google dominates search.", "about_entities": []},
                {"content": "Google Cloud grows.", "about_entities": []},
            ],
            entities=[],
        )

        mock_response = MagicMock()
        # Both facts contain "Google"
        mock_response.content = [
            MagicMock(text='{"0": ["Google"], "1": ["Google", "Google Cloud"]}')
        ]

        with patch("entity_linker.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = mock_response

            result = _ner_fill_about_entities(data)

        entity_names = [e["name"] for e in result["entities"]]
        # "Google" should appear exactly once despite two facts
        assert entity_names.count("Google") == 1

    def test_正常系_about_entities非空のfactはスキップされる(self) -> None:
        """about_entities が既に設定されている Fact は NER 対象外であること。"""
        from entity_linker import _ner_fill_about_entities

        data = _make_data(
            facts=[
                {
                    "content": "Already annotated fact.",
                    "about_entities": ["ExistingEntity"],
                },
                {"content": "Empty fact.", "about_entities": []},
            ],
            entities=[],
        )

        mock_response = MagicMock()
        # Only index 0 (the empty fact) is sent — mapped as index "0"
        mock_response.content = [MagicMock(text='{"0": ["NewEntity"]}')]

        with patch("entity_linker.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = mock_response

            result = _ner_fill_about_entities(data)

        chunks = result["sources"][0]["chunks"][0]
        # Annotated fact unchanged
        assert chunks["facts"][0]["about_entities"] == ["ExistingEntity"]
        # Empty fact gets NER result
        assert "NewEntity" in chunks["facts"][1]["about_entities"]

    def test_正常系_about_entitiesキーなしのfactはスキップされる(self) -> None:
        """about_entities キー自体がない Fact は NER 対象外であること。"""
        from entity_linker import _ner_fill_about_entities

        data = _make_data(
            facts=[
                {"content": "Fact without about_entities key."},
            ],
            entities=[],
        )

        with patch("entity_linker.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client

            result = _ner_fill_about_entities(data)

        # No API call should be made (no empty about_entities to process)
        mock_client.messages.create.assert_not_called()
        assert (
            result["sources"][0]["chunks"][0]["facts"][0].get("about_entities") is None
        )

    def test_異常系_APIエラー時にサイレントスキップされる(self) -> None:
        """Anthropic API エラー時にも例外を発生させず投入が継続されること。"""
        from entity_linker import _ner_fill_about_entities

        data = _make_data(
            facts=[
                {"content": "Some important fact.", "about_entities": []},
            ],
            entities=[],
        )

        with patch("entity_linker.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.side_effect = Exception("API timeout")

            # Must not raise
            result = _ner_fill_about_entities(data)

        # about_entities remains empty (silently skipped)
        fact = result["sources"][0]["chunks"][0]["facts"][0]
        assert fact["about_entities"] == []

    def test_異常系_NER結果が空の場合は何もしない(self) -> None:
        """NER 結果が空のレスポンスの場合は about_entities を変更しないこと。"""
        from entity_linker import _ner_fill_about_entities

        data = _make_data(
            facts=[
                {"content": "Abstract content with no entities.", "about_entities": []},
            ],
            entities=[],
        )

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"0": []}')]

        with patch("entity_linker.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = mock_response

            result = _ner_fill_about_entities(data)

        fact = result["sources"][0]["chunks"][0]["facts"][0]
        assert fact["about_entities"] == []

    def test_正常系_データが空の場合はAPIを呼ばない(self) -> None:
        """sources/chunks/facts が全てない場合は API 呼び出しが行われないこと。"""
        from entity_linker import _ner_fill_about_entities

        data: dict[str, Any] = {"entities": [], "sources": []}

        with patch("entity_linker.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client

            result = _ner_fill_about_entities(data)

        mock_client.messages.create.assert_not_called()
        assert result["entities"] == []

    def test_正常系_バッチサイズ超過時に複数バッチで処理される(self) -> None:
        """batch_size を超える件数が複数バッチで処理されること。"""
        from entity_linker import _ner_fill_about_entities

        # Create 3 facts with empty about_entities, batch_size=2
        facts = [
            {"content": f"Fact about Company{i}.", "about_entities": []}
            for i in range(3)
        ]
        data = _make_data(facts=facts, entities=[])

        call_count = 0

        def mock_create(**kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            # Return one entity per item in the batch
            texts = kwargs.get("messages", [{}])[0].get("content", "")
            # Count lines that start with digit (0:, 1:)
            items_in_batch = sum(
                1 for line in texts.split("\n") if line and line[0].isdigit()
            )
            payload = {
                str(i): [f"CompanyBatch{call_count}_{i}"] for i in range(items_in_batch)
            }
            import json

            mock_resp.content = [MagicMock(text=json.dumps(payload))]
            return mock_resp

        with patch("entity_linker.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.side_effect = mock_create

            _ner_fill_about_entities(data, batch_size=2)

        # 3 items with batch_size=2 → ceil(3/2) = 2 API calls
        assert call_count == 2

    def test_正常系_既存entitiesに重複しない名前のみ追加される(self) -> None:
        """data['entities'] に既に存在する名前は重複して追加されないこと。"""
        from entity_linker import _ner_fill_about_entities

        data = _make_data(
            facts=[
                {"content": "Apple is a tech company.", "about_entities": []},
            ],
            entities=[{"name": "Apple", "entity_type": "company"}],
        )

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"0": ["Apple", "Google"]}')]

        with patch("entity_linker.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = mock_response

            result = _ner_fill_about_entities(data)

        entity_names = [e["name"] for e in result["entities"]]
        # Apple already existed, should not be duplicated
        assert entity_names.count("Apple") == 1
        # Google is new, should be added
        assert "Google" in entity_names

    def test_異常系_不正なJSONレスポンス時にサイレントスキップされる(self) -> None:
        """API が不正な JSON を返した場合もサイレントスキップされること。"""
        from entity_linker import _ner_fill_about_entities

        data = _make_data(
            facts=[
                {"content": "Some fact.", "about_entities": []},
            ],
            entities=[],
        )

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="not valid json!!!")]

        with patch("entity_linker.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = mock_response

            # Must not raise
            result = _ner_fill_about_entities(data)

        # about_entities should remain untouched
        fact = result["sources"][0]["chunks"][0]["facts"][0]
        assert fact["about_entities"] == []


# ---------------------------------------------------------------------------
# --ner-fallback CLI flag tests
# ---------------------------------------------------------------------------


class TestNerFallbackCliFlag:
    """--ner-fallback CLI フラグのテスト。"""

    def test_正常系_ner_fallbackフラグが解析される(self) -> None:
        """--ner-fallback フラグが argparse で認識されること。"""
        from entity_linker import _build_parser

        parser = _build_parser()
        args = parser.parse_args(
            ["--input", "test.json", "--instance", "research", "--ner-fallback"]
        )
        assert args.ner_fallback is True

    def test_正常系_ner_fallbackデフォルトはFalse(self) -> None:
        """--ner-fallback を指定しない場合はデフォルト False であること。"""
        from entity_linker import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["--input", "test.json", "--instance", "research"])
        assert args.ner_fallback is False
