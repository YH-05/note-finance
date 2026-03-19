"""fix_legacy_relationships.py のユニットテスト。

Neo4j 接続はモックで代替し、DB不要でテスト実行可能。
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from fix_legacy_relationships import (
    BATCH_SIZE,
    LEGACY_MAPPING,
    LegacyRelInfo,
    find_legacy_relationships,
    fix_legacy_relationships,
    parse_args,
)


# ---------------------------------------------------------------------------
# LEGACY_MAPPING
# ---------------------------------------------------------------------------


class TestLegacyMapping:
    def test_正常系_3種のマッピングが定義されている(self) -> None:
        assert len(LEGACY_MAPPING) == 3
        assert LEGACY_MAPPING["RELATED_TO"] == "RELATES_TO"
        assert LEGACY_MAPPING["HAS_FACT"] == "STATES_FACT"
        assert LEGACY_MAPPING["TAGGED_WITH"] == "TAGGED"


# ---------------------------------------------------------------------------
# find_legacy_relationships
# ---------------------------------------------------------------------------


class TestFindLegacyRelationships:
    def test_正常系_レガシーリレーションを検出する(self) -> None:
        mock_session = MagicMock()

        def side_effect(query, **kwargs):
            mock_result = MagicMock()
            if "RELATED_TO" in query:
                mock_result.single.return_value = {"cnt": 50}
            elif "HAS_FACT" in query:
                mock_result.single.return_value = {"cnt": 30}
            elif "TAGGED_WITH" in query:
                mock_result.single.return_value = {"cnt": 20}
            else:
                mock_result.single.return_value = {"cnt": 0}
            return mock_result

        mock_session.run.side_effect = side_effect

        result = find_legacy_relationships(mock_session)

        assert len(result) == 3
        assert result[0].old_type == "RELATED_TO"
        assert result[0].new_type == "RELATES_TO"
        assert result[0].count == 50

    def test_正常系_レガシーが0件のタイプは除外される(self) -> None:
        mock_session = MagicMock()

        def side_effect(query, **kwargs):
            mock_result = MagicMock()
            if "RELATED_TO" in query:
                mock_result.single.return_value = {"cnt": 10}
            else:
                mock_result.single.return_value = {"cnt": 0}
            return mock_result

        mock_session.run.side_effect = side_effect

        result = find_legacy_relationships(mock_session)

        assert len(result) == 1
        assert result[0].old_type == "RELATED_TO"

    def test_エッジケース_全て0件で空リスト(self) -> None:
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"cnt": 0}
        mock_session.run.return_value = mock_result

        result = find_legacy_relationships(mock_session)

        assert result == []


# ---------------------------------------------------------------------------
# fix_legacy_relationships
# ---------------------------------------------------------------------------


class TestFixLegacyRelationships:
    def test_正常系_dry_runでは書き込みしない(self) -> None:
        mock_session = MagicMock()
        rels = [LegacyRelInfo(old_type="RELATED_TO", new_type="RELATES_TO", count=10)]

        result = fix_legacy_relationships(mock_session, rels, dry_run=True)

        assert result == 0
        mock_session.run.assert_not_called()

    def test_正常系_executeでリレーション移行する(self) -> None:
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"migrated": 10}
        mock_session.run.return_value = mock_result

        rels = [LegacyRelInfo(old_type="RELATED_TO", new_type="RELATES_TO", count=10)]

        result = fix_legacy_relationships(mock_session, rels, dry_run=False)

        assert result == 10

    def test_正常系_バッチ処理で段階的に移行する(self) -> None:
        mock_session = MagicMock()

        call_count = [0]

        def side_effect(query, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                mock_result.single.return_value = {"migrated": 100}
            elif call_count[0] == 2:
                mock_result.single.return_value = {"migrated": 50}
            else:
                mock_result.single.return_value = {"migrated": 0}
            return mock_result

        mock_session.run.side_effect = side_effect

        rels = [LegacyRelInfo(old_type="RELATED_TO", new_type="RELATES_TO", count=150)]

        result = fix_legacy_relationships(
            mock_session, rels, dry_run=False, batch_size=100
        )

        assert result == 150

    def test_エッジケース_空リストで0件(self) -> None:
        mock_session = MagicMock()
        result = fix_legacy_relationships(mock_session, [], dry_run=False)
        assert result == 0

    def test_正常系_複数タイプを順次処理する(self) -> None:
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"migrated": 5}
        mock_session.run.return_value = mock_result

        rels = [
            LegacyRelInfo(old_type="RELATED_TO", new_type="RELATES_TO", count=5),
            LegacyRelInfo(old_type="HAS_FACT", new_type="STATES_FACT", count=5),
        ]

        result = fix_legacy_relationships(mock_session, rels, dry_run=False)

        assert result == 10


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

    def test_正常系_batch_sizeのデフォルト値(self) -> None:
        args = parse_args([])
        assert args.batch_size == BATCH_SIZE

    def test_正常系_batch_sizeをカスタム指定(self) -> None:
        args = parse_args(["--batch-size", "50"])
        assert args.batch_size == 50
