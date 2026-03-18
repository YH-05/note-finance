"""migrate_skill_run_schema.py の純粋関数に対するユニットテスト。"""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from scripts.migrate_skill_run_schema import (
    SKILL_RUN_DDL,
    apply_ddl,
    build_ddl_summary,
)

# ---------------------------------------------------------------------------
# SKILL_RUN_DDL
# ---------------------------------------------------------------------------


class TestSkillRunDDL:
    """SKILL_RUN_DDL 定数の構造を検証する。"""

    def test_正常系_DDLリストが空でない(self) -> None:
        """DDL リストに少なくとも1つのステートメントが含まれることを確認。"""
        assert len(SKILL_RUN_DDL) > 0

    def test_正常系_全DDLがIF_NOT_EXISTSを含む(self) -> None:
        """冪等性のため全 DDL に IF NOT EXISTS が含まれることを確認。"""
        for ddl in SKILL_RUN_DDL:
            assert "IF NOT EXISTS" in ddl, f"IF NOT EXISTS missing: {ddl}"

    def test_正常系_制約が含まれる(self) -> None:
        """SkillRun の UNIQUE 制約が DDL に含まれることを確認。"""
        constraint_ddl = [d for d in SKILL_RUN_DDL if "CONSTRAINT" in d.upper()]
        assert len(constraint_ddl) >= 1

    def test_正常系_インデックスが含まれる(self) -> None:
        """SkillRun のインデックスが DDL に含まれることを確認。"""
        index_ddl = [
            d for d in SKILL_RUN_DDL if d.strip().upper().startswith("CREATE INDEX")
        ]
        assert len(index_ddl) >= 4

    def test_正常系_DDL内容が01_constraints_indexesと一致(self) -> None:
        """DDL が 01-constraints-indexes.cypher の Skill Observability セクションと同一であることを確認。"""
        expected_keywords = [
            "skill_run_id_unique",
            "skill_run_skill_name",
            "skill_run_status",
            "skill_run_start_at",
            "skill_run_command_source",
        ]
        all_ddl = "\n".join(SKILL_RUN_DDL)
        for keyword in expected_keywords:
            assert keyword in all_ddl, f"Expected keyword '{keyword}' not found in DDL"


# ---------------------------------------------------------------------------
# build_ddl_summary
# ---------------------------------------------------------------------------


class TestBuildDdlSummary:
    """build_ddl_summary のテスト。"""

    def test_正常系_DDLリストからサマリー文字列を生成(self) -> None:
        """DDL リストからサマリー文字列が生成されることを確認。"""
        result = build_ddl_summary(SKILL_RUN_DDL)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_正常系_全DDLステートメントが含まれる(self) -> None:
        """サマリーに全 DDL ステートメントが含まれることを確認。"""
        result = build_ddl_summary(SKILL_RUN_DDL)
        for ddl in SKILL_RUN_DDL:
            assert ddl in result

    def test_エッジケース_空リストで空文字列(self) -> None:
        """空の DDL リストで空文字列を返すことを確認。"""
        result = build_ddl_summary([])
        assert result == ""


# ---------------------------------------------------------------------------
# apply_ddl
# ---------------------------------------------------------------------------


class TestApplyDdl:
    """apply_ddl のテスト。"""

    def test_正常系_全DDLが実行される(self) -> None:
        """全 DDL ステートメントが session.run で実行されることを確認。"""
        mock_session = MagicMock()
        ddl_list = [
            "CREATE CONSTRAINT test IF NOT EXISTS FOR (n:Test) REQUIRE n.id IS UNIQUE",
            "CREATE INDEX test_idx IF NOT EXISTS FOR (n:Test) ON (n.name)",
        ]

        stats = apply_ddl(mock_session, ddl_list)

        assert mock_session.run.call_count == 2
        mock_session.run.assert_any_call(ddl_list[0])
        mock_session.run.assert_any_call(ddl_list[1])
        assert stats["applied"] == 2
        assert stats["failed"] == 0

    def test_正常系_空DDLリストで何も実行しない(self) -> None:
        """空の DDL リストで session.run が呼ばれないことを確認。"""
        mock_session = MagicMock()

        stats = apply_ddl(mock_session, [])

        mock_session.run.assert_not_called()
        assert stats["applied"] == 0
        assert stats["failed"] == 0

    def test_異常系_DDL実行失敗時にカウントされる(self) -> None:
        """DDL 実行が例外を投げた場合に failed としてカウントされることを確認。"""
        mock_session = MagicMock()
        mock_session.run.side_effect = [None, Exception("Neo4j error"), None]
        ddl_list = [
            "CREATE CONSTRAINT c1 IF NOT EXISTS FOR (n:A) REQUIRE n.id IS UNIQUE",
            "CREATE INDEX i1 IF NOT EXISTS FOR (n:A) ON (n.x)",
            "CREATE INDEX i2 IF NOT EXISTS FOR (n:A) ON (n.y)",
        ]

        stats = apply_ddl(mock_session, ddl_list)

        assert stats["applied"] == 2
        assert stats["failed"] == 1

    def test_正常系_実行順序が保持される(self) -> None:
        """DDL が定義順に実行されることを確認。"""
        mock_session = MagicMock()
        ddl_list = [
            "CREATE CONSTRAINT first IF NOT EXISTS FOR (n:A) REQUIRE n.id IS UNIQUE",
            "CREATE INDEX second IF NOT EXISTS FOR (n:A) ON (n.x)",
        ]

        apply_ddl(mock_session, ddl_list)

        expected_calls = [call(ddl_list[0]), call(ddl_list[1])]
        assert mock_session.run.call_args_list == expected_calls
