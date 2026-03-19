"""fix_entity_id_null.py のユニットテスト。

Neo4j 接続はモックで代替し、DB不要でテスト実行可能。
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from fix_entity_id_null import (
    NullEntityRecord,
    find_null_entity_ids,
    fix_entity_ids,
    generate_entity_id,
    parse_args,
)


# ---------------------------------------------------------------------------
# generate_entity_id
# ---------------------------------------------------------------------------


class TestGenerateEntityId:
    def test_正常系_同じ入力で同じIDが生成される(self) -> None:
        id1 = generate_entity_id("Apple", "company")
        id2 = generate_entity_id("Apple", "company")
        assert id1 == id2

    def test_正常系_異なる入力で異なるIDが生成される(self) -> None:
        id1 = generate_entity_id("Apple", "company")
        id2 = generate_entity_id("Google", "company")
        assert id1 != id2

    def test_正常系_typeが異なると異なるIDになる(self) -> None:
        id1 = generate_entity_id("Apple", "company")
        id2 = generate_entity_id("Apple", "technology")
        assert id1 != id2

    def test_正常系_UUID形式の文字列を返す(self) -> None:
        result = generate_entity_id("test", "company")
        assert len(result) == 36
        assert result.count("-") == 4


# ---------------------------------------------------------------------------
# find_null_entity_ids
# ---------------------------------------------------------------------------


class TestFindNullEntityIds:
    def test_正常系_NULLエンティティを検出する(self) -> None:
        mock_session = MagicMock()
        mock_session.run.return_value.data.return_value = [
            {"eid": "elem:1", "name": "Apple", "entity_type": "company"},
            {"eid": "elem:2", "name": "Google", "entity_type": None},
        ]

        result = find_null_entity_ids(mock_session)

        assert len(result) == 2
        assert result[0].name == "Apple"
        assert result[0].entity_type == "company"
        assert result[1].entity_type is None

    def test_エッジケース_該当なしで空リスト(self) -> None:
        mock_session = MagicMock()
        mock_session.run.return_value.data.return_value = []

        result = find_null_entity_ids(mock_session)

        assert result == []


# ---------------------------------------------------------------------------
# fix_entity_ids
# ---------------------------------------------------------------------------


class TestFixEntityIds:
    def test_正常系_dry_runでは書き込みしない(self) -> None:
        mock_session = MagicMock()
        entities = [
            NullEntityRecord(element_id="elem:1", name="Apple", entity_type="company"),
        ]

        result = fix_entity_ids(mock_session, entities, dry_run=True)

        assert result == 0
        mock_session.run.assert_not_called()

    def test_正常系_executeで書き込みする(self) -> None:
        mock_session = MagicMock()
        entities = [
            NullEntityRecord(element_id="elem:1", name="Apple", entity_type="company"),
            NullEntityRecord(element_id="elem:2", name="Google", entity_type=None),
        ]

        result = fix_entity_ids(mock_session, entities, dry_run=False)

        assert result == 2
        assert mock_session.run.call_count == 2

    def test_正常系_entity_typeがNoneの場合unknownにフォールバック(self) -> None:
        mock_session = MagicMock()
        entities = [
            NullEntityRecord(element_id="elem:1", name="Test", entity_type=None),
        ]

        fix_entity_ids(mock_session, entities, dry_run=False)

        call_kwargs = mock_session.run.call_args
        assert call_kwargs.kwargs["entity_key"] == "Test::unknown"

    def test_エッジケース_空リストで0件(self) -> None:
        mock_session = MagicMock()
        result = fix_entity_ids(mock_session, [], dry_run=False)
        assert result == 0

    def test_正常系_entity_keyが正しく設定される(self) -> None:
        mock_session = MagicMock()
        entities = [
            NullEntityRecord(element_id="elem:1", name="Apple", entity_type="company"),
        ]

        fix_entity_ids(mock_session, entities, dry_run=False)

        call_kwargs = mock_session.run.call_args
        assert call_kwargs.kwargs["entity_key"] == "Apple::company"
        expected_id = generate_entity_id("Apple", "company")
        assert call_kwargs.kwargs["entity_id"] == expected_id


# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------


class TestParseArgs:
    def test_正常系_デフォルトはdry_run(self) -> None:
        args = parse_args([])
        assert args.dry_run is True

    def test_正常系_executeでdry_runがFalse(self) -> None:
        args = parse_args(["--execute"])
        assert args.dry_run is False

    def test_正常系_neo4j_uriのデフォルト値(self) -> None:
        args = parse_args([])
        assert args.neo4j_uri == "bolt://localhost:7688"
