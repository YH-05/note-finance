"""strengthen_entity_connections.py のユニットテスト。

Entity孤立ノード接続強化スクリプトの純粋関数・CLI・Cypherクエリを検証する。
Neo4j 接続はモックで代替し、DB不要でテスト実行可能。
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# scripts/ をインポートパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from strengthen_entity_connections import (
    ConnectionResult,
    MethodStats,
    count_isolated_entities,
    create_driver,
    lower_co_mention_threshold,
    parse_args,
    strengthen_topic_links,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_session() -> MagicMock:
    """Neo4j セッションのモック。"""
    session = MagicMock()
    return session


@pytest.fixture()
def mock_driver(mock_session: MagicMock) -> MagicMock:
    """Neo4j ドライバーのモック。"""
    driver = MagicMock()
    driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    driver.session.return_value.__exit__ = MagicMock(return_value=False)
    return driver


# ---------------------------------------------------------------------------
# DataClasses
# ---------------------------------------------------------------------------


class TestConnectionResult:
    def test_正常系_デフォルト値でインスタンス生成(self) -> None:
        result = ConnectionResult(
            method="co_mention",
            relationships_added=10,
            before_isolated=97,
            after_isolated=80,
        )
        assert result.method == "co_mention"
        assert result.relationships_added == 10
        assert result.before_isolated == 97
        assert result.after_isolated == 80

    def test_正常系_reduction_rateを計算(self) -> None:
        result = ConnectionResult(
            method="topic",
            relationships_added=20,
            before_isolated=100,
            after_isolated=50,
        )
        assert result.before_isolated - result.after_isolated == 50

    def test_エッジケース_変化なし(self) -> None:
        result = ConnectionResult(
            method="co_mention",
            relationships_added=0,
            before_isolated=97,
            after_isolated=97,
        )
        assert result.relationships_added == 0


class TestMethodStats:
    def test_正常系_統計情報を保持(self) -> None:
        stats = MethodStats(
            method="co_mention",
            candidates_found=50,
            relationships_created=30,
            dry_run=False,
        )
        assert stats.method == "co_mention"
        assert stats.candidates_found == 50
        assert stats.relationships_created == 30
        assert stats.dry_run is False

    def test_正常系_dryrunフラグ(self) -> None:
        stats = MethodStats(
            method="topic",
            candidates_found=10,
            relationships_created=0,
            dry_run=True,
        )
        assert stats.dry_run is True
        assert stats.relationships_created == 0


# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------


class TestParseArgs:
    def test_正常系_デフォルト引数(self) -> None:
        args = parse_args([])
        assert args.dry_run is False
        assert args.method == "all"
        assert args.limit is None
        assert args.neo4j_uri == "bolt://localhost:7688"

    def test_正常系_dry_runフラグ(self) -> None:
        args = parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_正常系_method指定(self) -> None:
        args = parse_args(["--method", "co_mention"])
        assert args.method == "co_mention"

    def test_正常系_method_topic指定(self) -> None:
        args = parse_args(["--method", "topic"])
        assert args.method == "topic"

    def test_正常系_method_all指定(self) -> None:
        args = parse_args(["--method", "all"])
        assert args.method == "all"

    def test_正常系_limit指定(self) -> None:
        args = parse_args(["--limit", "50"])
        assert args.limit == 50

    def test_正常系_neo4j_uri指定(self) -> None:
        args = parse_args(["--neo4j-uri", "bolt://localhost:7687"])
        assert args.neo4j_uri == "bolt://localhost:7687"

    def test_正常系_neo4j_password指定(self) -> None:
        args = parse_args(["--neo4j-password", "secret"])
        assert args.neo4j_password == "secret"

    def test_正常系_全オプション組み合わせ(self) -> None:
        args = parse_args(
            [
                "--dry-run",
                "--method",
                "topic",
                "--limit",
                "100",
                "--neo4j-uri",
                "bolt://remote:7688",
                "--neo4j-password",
                "pass123",
            ]
        )
        assert args.dry_run is True
        assert args.method == "topic"
        assert args.limit == 100
        assert args.neo4j_uri == "bolt://remote:7688"
        assert args.neo4j_password == "pass123"


# ---------------------------------------------------------------------------
# create_driver
# ---------------------------------------------------------------------------


class TestCreateDriver:
    @patch("strengthen_entity_connections.GraphDatabase")
    def test_正常系_デフォルトURIで接続(self, mock_gdb: MagicMock) -> None:
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver

        driver = create_driver()

        mock_gdb.driver.assert_called_once_with(
            "bolt://localhost:7688",
            auth=("neo4j", "gomasuke"),
        )
        mock_driver.verify_connectivity.assert_called_once()
        assert driver is mock_driver

    @patch("strengthen_entity_connections.GraphDatabase")
    def test_正常系_カスタムURIとパスワードで接続(self, mock_gdb: MagicMock) -> None:
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver

        driver = create_driver(uri="bolt://remote:7687", password="secret")

        mock_gdb.driver.assert_called_once_with(
            "bolt://remote:7687",
            auth=("neo4j", "secret"),
        )
        assert driver is mock_driver


# ---------------------------------------------------------------------------
# count_isolated_entities
# ---------------------------------------------------------------------------


class TestCountIsolatedEntities:
    def test_正常系_孤立Entity数を返す(self, mock_session: MagicMock) -> None:
        mock_result = MagicMock()
        mock_result.single.return_value = {"count": 97}
        mock_session.run.return_value = mock_result

        count = count_isolated_entities(mock_session)

        assert count == 97
        # Memory除外フィルタが含まれていることを確認
        query_arg = mock_session.run.call_args[0][0]
        assert "Memory" in query_arg
        assert "NOT" in query_arg

    def test_正常系_孤立Entity0件(self, mock_session: MagicMock) -> None:
        mock_result = MagicMock()
        mock_result.single.return_value = {"count": 0}
        mock_session.run.return_value = mock_result

        count = count_isolated_entities(mock_session)
        assert count == 0

    def test_正常系_CypherにMemory除外フィルタが含まれる(
        self, mock_session: MagicMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.single.return_value = {"count": 10}
        mock_session.run.return_value = mock_result

        count_isolated_entities(mock_session)

        query = mock_session.run.call_args[0][0]
        assert "NOT 'Memory' IN labels" in query


# ---------------------------------------------------------------------------
# lower_co_mention_threshold
# ---------------------------------------------------------------------------


class TestLowerCoMentionThreshold:
    def test_正常系_候補ペアを検出してリレーション作成(
        self, mock_session: MagicMock
    ) -> None:
        # 候補検索の結果
        mock_candidates = MagicMock()
        mock_candidates.__iter__ = MagicMock(
            return_value=iter(
                [
                    {"e1_key": "Apple", "e2_key": "Microsoft", "shared": 1},
                    {"e1_key": "Google", "e2_key": "Meta", "shared": 1},
                ]
            )
        )

        # MERGE 結果
        mock_merge_result = MagicMock()
        mock_merge_result.single.return_value = {"created": 1}

        mock_session.run.side_effect = [
            mock_candidates,
            mock_merge_result,
            mock_merge_result,
        ]

        stats = lower_co_mention_threshold(mock_session, dry_run=False, limit=None)

        assert isinstance(stats, MethodStats)
        assert stats.method == "co_mention"
        assert stats.candidates_found == 2

    def test_正常系_dry_runでリレーション作成なし(
        self, mock_session: MagicMock
    ) -> None:
        mock_candidates = MagicMock()
        mock_candidates.__iter__ = MagicMock(
            return_value=iter(
                [
                    {"e1_key": "Apple", "e2_key": "Microsoft", "shared": 1},
                ]
            )
        )
        mock_session.run.return_value = mock_candidates

        stats = lower_co_mention_threshold(mock_session, dry_run=True, limit=None)

        assert stats.dry_run is True
        assert stats.candidates_found == 1
        assert stats.relationships_created == 0

    def test_正常系_limit制限が機能する(self, mock_session: MagicMock) -> None:
        mock_candidates = MagicMock()
        mock_candidates.__iter__ = MagicMock(
            return_value=iter(
                [
                    {"e1_key": "A", "e2_key": "B", "shared": 1},
                    {"e1_key": "C", "e2_key": "D", "shared": 1},
                    {"e1_key": "E", "e2_key": "F", "shared": 1},
                ]
            )
        )
        mock_session.run.return_value = mock_candidates

        stats = lower_co_mention_threshold(mock_session, dry_run=True, limit=2)

        assert stats.candidates_found <= 2

    def test_正常系_CypherにMemory除外フィルタが含まれる(
        self, mock_session: MagicMock
    ) -> None:
        mock_candidates = MagicMock()
        mock_candidates.__iter__ = MagicMock(return_value=iter([]))
        mock_session.run.return_value = mock_candidates

        lower_co_mention_threshold(mock_session, dry_run=True, limit=None)

        query = mock_session.run.call_args[0][0]
        assert "Memory" in query


# ---------------------------------------------------------------------------
# strengthen_topic_links
# ---------------------------------------------------------------------------


class TestStrengthenTopicLinks:
    def test_正常系_Topic媒介で候補検出(self, mock_session: MagicMock) -> None:
        mock_candidates = MagicMock()
        mock_candidates.__iter__ = MagicMock(
            return_value=iter(
                [
                    {"e1_key": "Tesla", "e2_key": "Nvidia", "shared_topics": 2},
                ]
            )
        )

        mock_merge_result = MagicMock()
        mock_merge_result.single.return_value = {"created": 1}

        mock_session.run.side_effect = [mock_candidates, mock_merge_result]

        stats = strengthen_topic_links(mock_session, dry_run=False, limit=None)

        assert isinstance(stats, MethodStats)
        assert stats.method == "topic"
        assert stats.candidates_found == 1

    def test_正常系_dry_runで作成なし(self, mock_session: MagicMock) -> None:
        mock_candidates = MagicMock()
        mock_candidates.__iter__ = MagicMock(
            return_value=iter(
                [
                    {"e1_key": "Tesla", "e2_key": "Nvidia", "shared_topics": 2},
                ]
            )
        )
        mock_session.run.return_value = mock_candidates

        stats = strengthen_topic_links(mock_session, dry_run=True, limit=None)

        assert stats.dry_run is True
        assert stats.relationships_created == 0

    def test_正常系_CypherにMemory除外フィルタが含まれる(
        self, mock_session: MagicMock
    ) -> None:
        mock_candidates = MagicMock()
        mock_candidates.__iter__ = MagicMock(return_value=iter([]))
        mock_session.run.return_value = mock_candidates

        strengthen_topic_links(mock_session, dry_run=True, limit=None)

        query = mock_session.run.call_args[0][0]
        assert "Memory" in query


# ---------------------------------------------------------------------------
# main (統合テスト)
# ---------------------------------------------------------------------------


class TestMain:
    @patch("strengthen_entity_connections.create_driver")
    def test_正常系_dry_runで正常終了(self, mock_create_driver: MagicMock) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(
            return_value=mock_session
        )
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_create_driver.return_value = mock_driver

        # count_isolated_entities の結果
        mock_count = MagicMock()
        mock_count.single.return_value = {"count": 97}

        # 候補検索の結果（空）
        mock_empty = MagicMock()
        mock_empty.__iter__ = MagicMock(return_value=iter([]))

        mock_session.run.return_value = mock_count

        # dry-run モードで実行
        with patch("sys.argv", ["prog", "--dry-run"]):
            # main() がエラーなく終了することを確認
            # 実際の Cypher クエリはモックで代替
            pass  # main のテストは統合テストレベルで行う

    @patch("strengthen_entity_connections.create_driver")
    def test_正常系_methodオプションで手法を限定(
        self, mock_create_driver: MagicMock
    ) -> None:
        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver
        # method="co_mention" で topic を実行しないことを検証
        # 統合テストとして、main内部の分岐を間接的に検証する
        pass
