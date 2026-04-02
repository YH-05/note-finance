"""Unit tests for scripts/migrate_relations_to_relates_to.py.

Wave 5: ABOUT/MENTIONS → RELATES_TO リレーション統一

テスト対象:
- MigrationCounts: 移行前後カウントデータクラス（total_source プロパティを含む）
- MigrationStats: 移行統計データクラス
- fetch_relation_counts: ABOUT/MENTIONS/RELATES_TO 件数取得
- migrate_about_to_relates_to: ABOUT → RELATES_TO バッチリネーム
- migrate_mentions_to_relates_to: MENTIONS → RELATES_TO バッチリネーム
- verify_migration: 移行後検証
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from scripts.migrate_relations_to_relates_to import (
    MigrationCounts,
    MigrationStats,
    fetch_relation_counts,
    migrate_about_to_relates_to,
    migrate_mentions_to_relates_to,
    verify_migration,
)

# ---------------------------------------------------------------------------
# MigrationCounts
# ---------------------------------------------------------------------------


class TestMigrationCounts:
    """MigrationCounts データクラスのテスト。"""

    def test_正常系_デフォルト値がゼロ(self) -> None:
        counts = MigrationCounts()
        assert counts.about == 0
        assert counts.mentions == 0
        assert counts.relates_to == 0

    def test_正常系_値を設定して取得できる(self) -> None:
        counts = MigrationCounts(about=5343, mentions=925, relates_to=100)
        assert counts.about == 5343
        assert counts.mentions == 925
        assert counts.relates_to == 100

    def test_正常系_total_sourceはABOUTとMENTIONSの合計(self) -> None:
        counts = MigrationCounts(about=5343, mentions=925, relates_to=100)
        assert counts.total_source == 6268

    def test_正常系_total_source_ゼロの場合は0(self) -> None:
        counts = MigrationCounts()
        assert counts.total_source == 0

    def test_正常系_total_sourceはRELATES_TOを含まない(self) -> None:
        """total_source は移行元合計（ABOUT + MENTIONS）のみ。RELATES_TO は含まない。"""
        counts = MigrationCounts(about=10, mentions=5, relates_to=999)
        assert counts.total_source == 15


# ---------------------------------------------------------------------------
# MigrationStats
# ---------------------------------------------------------------------------


class TestMigrationStats:
    """MigrationStats データクラスのテスト。"""

    def test_正常系_デフォルト値がゼロ(self) -> None:
        stats = MigrationStats()
        assert stats.about_migrated == 0
        assert stats.mentions_migrated == 0
        assert stats.verified is False
        assert stats.failed == 0

    def test_正常系_pre_counts初期値がゼロ(self) -> None:
        stats = MigrationStats()
        assert stats.pre.about == 0
        assert stats.pre.mentions == 0
        assert stats.pre.relates_to == 0

    def test_正常系_post_counts初期値がゼロ(self) -> None:
        stats = MigrationStats()
        assert stats.post.about == 0
        assert stats.post.mentions == 0
        assert stats.post.relates_to == 0

    def test_正常系_値を設定して取得できる(self) -> None:
        stats = MigrationStats(
            about_migrated=5343,
            mentions_migrated=925,
            verified=True,
            failed=0,
        )
        assert stats.about_migrated == 5343
        assert stats.mentions_migrated == 925
        assert stats.verified is True
        assert stats.failed == 0


# ---------------------------------------------------------------------------
# fetch_relation_counts
# ---------------------------------------------------------------------------


class TestFetchRelationCounts:
    """fetch_relation_counts のテスト。"""

    def _make_session(self, about: int, mentions: int, relates_to: int) -> MagicMock:
        """指定件数を返すモックセッションを作成する。"""
        mock_session = MagicMock()
        # 3 回 run が呼ばれる順に返却
        mock_r_about = MagicMock()
        mock_r_about.single.return_value = {"cnt": about}
        mock_r_mentions = MagicMock()
        mock_r_mentions.single.return_value = {"cnt": mentions}
        mock_r_relates = MagicMock()
        mock_r_relates.single.return_value = {"cnt": relates_to}
        mock_session.run.side_effect = [mock_r_about, mock_r_mentions, mock_r_relates]
        return mock_session

    def test_正常系_3種のリレーション件数を取得する(self) -> None:
        """ABOUT / MENTIONS / RELATES_TO それぞれの件数を返すことを確認。"""
        mock_session = self._make_session(about=5343, mentions=925, relates_to=100)
        counts = fetch_relation_counts(mock_session)
        assert counts.about == 5343
        assert counts.mentions == 925
        assert counts.relates_to == 100
        assert mock_session.run.call_count == 3

    def test_正常系_全件ゼロの場合は0を返す(self) -> None:
        """リレーションが存在しない場合に 0 を返すことを確認。"""
        mock_session = self._make_session(about=0, mentions=0, relates_to=0)
        counts = fetch_relation_counts(mock_session)
        assert counts.about == 0
        assert counts.mentions == 0
        assert counts.relates_to == 0

    def test_正常系_CypherにABOUTが含まれる(self) -> None:
        """ABOUT カウントクエリに ABOUT が含まれることを確認。"""
        mock_session = self._make_session(about=1, mentions=0, relates_to=0)
        fetch_relation_counts(mock_session)
        first_call = mock_session.run.call_args_list[0]
        cypher = first_call[0][0]
        assert "ABOUT" in cypher

    def test_正常系_CypherにMENTIONSが含まれる(self) -> None:
        """MENTIONS カウントクエリに MENTIONS が含まれることを確認。"""
        mock_session = self._make_session(about=0, mentions=1, relates_to=0)
        fetch_relation_counts(mock_session)
        second_call = mock_session.run.call_args_list[1]
        cypher = second_call[0][0]
        assert "MENTIONS" in cypher

    def test_正常系_CypherにRELATES_TOが含まれる(self) -> None:
        """RELATES_TO カウントクエリに RELATES_TO が含まれることを確認。"""
        mock_session = self._make_session(about=0, mentions=0, relates_to=1)
        fetch_relation_counts(mock_session)
        third_call = mock_session.run.call_args_list[2]
        cypher = third_call[0][0]
        assert "RELATES_TO" in cypher

    def test_正常系_single戻り値がNoneの場合は0(self) -> None:
        """single() が None を返した場合に 0 を返すことを確認。"""
        mock_session = MagicMock()
        mock_r = MagicMock()
        mock_r.single.return_value = None
        mock_session.run.return_value = mock_r
        counts = fetch_relation_counts(mock_session)
        assert counts.about == 0
        assert counts.mentions == 0
        assert counts.relates_to == 0


# ---------------------------------------------------------------------------
# migrate_about_to_relates_to
# ---------------------------------------------------------------------------


class TestMigrateAboutToRelatesTo:
    """migrate_about_to_relates_to のテスト。"""

    def test_正常系_ABOUTをRELATES_TOにリネームする(self) -> None:
        """apoc.refactor.rename.type を呼び出して RELATES_TO にリネームすることを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"total": 5343}
        mock_session.run.return_value = mock_result

        count = migrate_about_to_relates_to(mock_session)
        assert mock_session.run.call_count == 1
        assert count == 5343

    def test_正常系_dry_run時はセッションを呼ばない(self) -> None:
        """dry_run=True の場合に session.run が呼ばれないことを確認。"""
        mock_session = MagicMock()
        count = migrate_about_to_relates_to(mock_session, dry_run=True)
        mock_session.run.assert_not_called()
        assert count == 0

    def test_正常系_0件の場合は0を返す(self) -> None:
        """移行対象が 0 件の場合に 0 を返すことを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"total": 0}
        mock_session.run.return_value = mock_result

        count = migrate_about_to_relates_to(mock_session)
        assert count == 0

    def test_正常系_CypherにapocとABOUTとRELATES_TOが含まれる(self) -> None:
        """実行される Cypher に apoc.refactor.rename.type と ABOUT と RELATES_TO が含まれることを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"total": 100}
        mock_session.run.return_value = mock_result

        migrate_about_to_relates_to(mock_session)
        call_args = mock_session.run.call_args
        cypher = call_args[0][0]
        assert "apoc" in cypher.lower()
        assert "ABOUT" in cypher
        assert "RELATES_TO" in cypher

    def test_正常系_batchSizeが渡される(self) -> None:
        """batch_size パラメータがクエリに渡されることを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"total": 500}
        mock_session.run.return_value = mock_result

        migrate_about_to_relates_to(mock_session, batch_size=500)
        call_args = mock_session.run.call_args
        kwargs = call_args[1] if call_args[1] else {}
        assert kwargs.get("batch_size") == 500

    def test_異常系_セッション例外時は0を返す(self) -> None:
        """session.run が例外を投げた場合に 0 を返すことを確認（処理継続）。"""
        mock_session = MagicMock()
        mock_session.run.side_effect = Exception("Neo4j error")
        count = migrate_about_to_relates_to(mock_session)
        assert count == 0

    def test_正常系_singleがNoneの場合は0を返す(self) -> None:
        """single() が None を返した場合に 0 を返すことを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = None
        mock_session.run.return_value = mock_result

        count = migrate_about_to_relates_to(mock_session)
        assert count == 0


# ---------------------------------------------------------------------------
# migrate_mentions_to_relates_to
# ---------------------------------------------------------------------------


class TestMigrateMentionsToRelatesTo:
    """migrate_mentions_to_relates_to のテスト。"""

    def test_正常系_MENTIONSをRELATES_TOにリネームする(self) -> None:
        """apoc.refactor.rename.type を呼び出して RELATES_TO にリネームすることを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"total": 925}
        mock_session.run.return_value = mock_result

        count = migrate_mentions_to_relates_to(mock_session)
        assert mock_session.run.call_count == 1
        assert count == 925

    def test_正常系_dry_run時はセッションを呼ばない(self) -> None:
        """dry_run=True の場合に session.run が呼ばれないことを確認。"""
        mock_session = MagicMock()
        count = migrate_mentions_to_relates_to(mock_session, dry_run=True)
        mock_session.run.assert_not_called()
        assert count == 0

    def test_正常系_0件の場合は0を返す(self) -> None:
        """移行対象が 0 件の場合に 0 を返すことを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"total": 0}
        mock_session.run.return_value = mock_result

        count = migrate_mentions_to_relates_to(mock_session)
        assert count == 0

    def test_正常系_CypherにapocとMENTIONSとRELATES_TOが含まれる(self) -> None:
        """実行される Cypher に apoc.refactor.rename.type と MENTIONS と RELATES_TO が含まれることを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"total": 100}
        mock_session.run.return_value = mock_result

        migrate_mentions_to_relates_to(mock_session)
        call_args = mock_session.run.call_args
        cypher = call_args[0][0]
        assert "apoc" in cypher.lower()
        assert "MENTIONS" in cypher
        assert "RELATES_TO" in cypher

    def test_正常系_batchSizeが渡される(self) -> None:
        """batch_size パラメータがクエリに渡されることを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"total": 300}
        mock_session.run.return_value = mock_result

        migrate_mentions_to_relates_to(mock_session, batch_size=300)
        call_args = mock_session.run.call_args
        kwargs = call_args[1] if call_args[1] else {}
        assert kwargs.get("batch_size") == 300

    def test_異常系_セッション例外時は0を返す(self) -> None:
        """session.run が例外を投げた場合に 0 を返すことを確認（処理継続）。"""
        mock_session = MagicMock()
        mock_session.run.side_effect = Exception("Neo4j error")
        count = migrate_mentions_to_relates_to(mock_session)
        assert count == 0

    def test_正常系_singleがNoneの場合は0を返す(self) -> None:
        """single() が None を返した場合に 0 を返すことを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = None
        mock_session.run.return_value = mock_result

        count = migrate_mentions_to_relates_to(mock_session)
        assert count == 0


# ---------------------------------------------------------------------------
# verify_migration
# ---------------------------------------------------------------------------


class TestVerifyMigration:
    """verify_migration のテスト。"""

    def _make_post_session(
        self, about: int, mentions: int, relates_to: int
    ) -> MagicMock:
        """移行後の件数を返すモックセッションを作成する。"""
        mock_session = MagicMock()
        mock_r_about = MagicMock()
        mock_r_about.single.return_value = {"cnt": about}
        mock_r_mentions = MagicMock()
        mock_r_mentions.single.return_value = {"cnt": mentions}
        mock_r_relates = MagicMock()
        mock_r_relates.single.return_value = {"cnt": relates_to}
        mock_session.run.side_effect = [mock_r_about, mock_r_mentions, mock_r_relates]
        return mock_session

    def test_正常系_全条件を満たす場合はTrueを返す(self) -> None:
        """ABOUT=0, MENTIONS=0, RELATES_TO 件数が一致する場合に True を返すことを確認。"""
        pre = MigrationCounts(about=5343, mentions=925, relates_to=100)
        expected_relates_to = 5343 + 925 + 100  # = 6368
        mock_session = self._make_post_session(
            about=0, mentions=0, relates_to=expected_relates_to
        )
        result = verify_migration(mock_session, pre)
        assert result is True

    def test_異常系_ABOUT件数が残っている場合はFalseを返す(self) -> None:
        """移行後に ABOUT が残っている場合に False を返すことを確認。"""
        pre = MigrationCounts(about=5343, mentions=925, relates_to=100)
        mock_session = self._make_post_session(
            about=100,  # 残存
            mentions=0,
            relates_to=5343 + 925 + 100 - 100,  # 不一致
        )
        result = verify_migration(mock_session, pre)
        assert result is False

    def test_異常系_MENTIONS件数が残っている場合はFalseを返す(self) -> None:
        """移行後に MENTIONS が残っている場合に False を返すことを確認。"""
        pre = MigrationCounts(about=5343, mentions=925, relates_to=100)
        mock_session = self._make_post_session(
            about=0,
            mentions=50,  # 残存
            relates_to=5343 + 925 + 100 - 50,  # 不一致
        )
        result = verify_migration(mock_session, pre)
        assert result is False

    def test_異常系_RELATES_TO件数が一致しない場合はFalseを返す(self) -> None:
        """移行後の RELATES_TO が期待値と異なる場合に False を返すことを確認。"""
        pre = MigrationCounts(about=5343, mentions=925, relates_to=100)
        mock_session = self._make_post_session(
            about=0,
            mentions=0,
            relates_to=9999,  # 期待値と不一致
        )
        result = verify_migration(mock_session, pre)
        assert result is False

    def test_正常系_移行前にABOUTとMENTIONSが0の場合はTrueを返す(self) -> None:
        """移行前から ABOUT/MENTIONS が 0 件の場合（冪等実行）に True を返すことを確認。"""
        pre = MigrationCounts(about=0, mentions=0, relates_to=200)
        mock_session = self._make_post_session(about=0, mentions=0, relates_to=200)
        result = verify_migration(mock_session, pre)
        assert result is True

    def test_正常系_全て0件の場合もTrueを返す(self) -> None:
        """全件ゼロ（空グラフ）の場合に True を返すことを確認。"""
        pre = MigrationCounts(about=0, mentions=0, relates_to=0)
        mock_session = self._make_post_session(about=0, mentions=0, relates_to=0)
        result = verify_migration(mock_session, pre)
        assert result is True
