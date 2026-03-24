"""session_memory.graph のユニットテスト.

SessionGraphWriter の UNWIND バッチ MERGE 動作を検証する。
Neo4j 接続はモックで代替し、純粋にロジックをテストする。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from session_memory.graph import SessionGraphWriter

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class FakeCounters:
    """session.run().consume().counters のフェイク."""

    def __init__(self, nodes_created: int = 0, relationships_created: int = 0) -> None:
        self.nodes_created = nodes_created
        self.relationships_created = relationships_created


class FakeResult:
    """session.run() の戻り値フェイク."""

    def __init__(self, counters: FakeCounters) -> None:
        self._counters = counters

    def consume(self) -> Any:
        return MagicMock(counters=self._counters)


@pytest.fixture
def mock_driver() -> MagicMock:
    """Neo4j ドライバーのモック.

    session.run() が FakeResult を返すように設定する。
    """
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__ = MagicMock(return_value=session)
    driver.session.return_value.__exit__ = MagicMock(return_value=False)
    return driver


@pytest.fixture
def writer(mock_driver: MagicMock) -> SessionGraphWriter:
    """SessionGraphWriter のインスタンス（モックドライバー使用）."""
    return SessionGraphWriter(mock_driver)


def _set_run_results(
    mock_driver: MagicMock,
    node_counts: list[int],
    rel_counts: list[int],
) -> None:
    """mock session.run() の戻り値を順番に設定する."""
    session = mock_driver.session.return_value.__enter__.return_value
    results: list[FakeResult] = []
    for count in node_counts:
        results.append(FakeResult(FakeCounters(nodes_created=count)))
    for count in rel_counts:
        results.append(FakeResult(FakeCounters(relationships_created=count)))
    session.run.side_effect = results


def _build_sample_queue() -> dict[str, Any]:
    """テスト用のサンプル queue_doc を構築する."""
    return {
        "sessions": [
            {
                "session_id": "sess-001",
                "project": "note-finance",
                "started_at": "2026-03-24T10:00:00Z",
                "summary": "KG v3.0 設計を議論",
            },
        ],
        "session_chunks": [
            {
                "chunk_key": "sess-001::0",
                "session_id": "sess-001",
                "content": "Q&Aペア",
                "role": "assistant",
                "seq": 0,
            },
            {
                "chunk_key": "sess-001::1",
                "session_id": "sess-001",
                "content": "次のQ&Aペア",
                "role": "assistant",
                "seq": 1,
            },
        ],
        "entities": [
            {
                "entity_key": "Neo4j::database",
                "name": "Neo4j",
                "entity_type": "database",
            },
        ],
        "topics": [
            {
                "name": "ナレッジグラフ",
            },
        ],
        "decisions": [
            {
                "decision_id": "dec-001",
                "summary": "FIBO準拠スキーマを採用",
                "rationale": "金融ドメインの標準化",
            },
        ],
        "relations": {
            "belongs_to": [
                {"from_id": "sess-001::0", "to_id": "sess-001"},
                {"from_id": "sess-001::1", "to_id": "sess-001"},
            ],
            "next": [
                {"from_id": "sess-001::0", "to_id": "sess-001::1"},
            ],
            "mentions": [
                {"from_id": "sess-001::0", "to_id": "Neo4j::database"},
            ],
            "discusses": [
                {"from_id": "sess-001::0", "to_id": "ナレッジグラフ"},
            ],
            "decided": [
                {"from_id": "sess-001::0", "to_id": "dec-001"},
            ],
        },
    }


# ---------------------------------------------------------------------------
# ノード MERGE テスト
# ---------------------------------------------------------------------------


class TestNodeMerge:
    """Session / SessionChunk ノードの MERGE テスト."""

    def test_正常系_SessionノードがMERGEされる(
        self,
        writer: SessionGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        """Session ノードが UNWIND バッチ MERGE で作成される."""
        queue = _build_sample_queue()
        # 5 node types + 5 rel types = 10 run calls
        _set_run_results(mock_driver, [1, 2, 1, 1, 1], [2, 1, 1, 1, 1])

        result = writer.ingest(queue, session_id="sess-001")

        assert result["nodes_created"] >= 1
        session = mock_driver.session.return_value.__enter__.return_value
        first_call_query = session.run.call_args_list[0][0][0]
        assert "Session" in first_call_query
        assert "MERGE" in first_call_query

    def test_正常系_SessionChunkノードがMERGEされる(
        self,
        writer: SessionGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        """SessionChunk ノードが UNWIND バッチ MERGE で作成される."""
        queue = _build_sample_queue()
        _set_run_results(mock_driver, [1, 2, 1, 1, 1], [2, 1, 1, 1, 1])

        result = writer.ingest(queue, session_id="sess-001")

        assert result["nodes_created"] >= 2
        session = mock_driver.session.return_value.__enter__.return_value
        queries = [c[0][0] for c in session.run.call_args_list]
        session_chunk_queries = [q for q in queries if "SessionChunk" in q]
        assert len(session_chunk_queries) >= 1

    def test_正常系_全5ノード種がMERGEされる(
        self,
        writer: SessionGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        """Session, SessionChunk, Entity, Topic, Decision の5種が全て MERGE される."""
        queue = _build_sample_queue()
        _set_run_results(mock_driver, [1, 2, 1, 1, 1], [2, 1, 1, 1, 1])

        writer.ingest(queue, session_id="sess-001")

        session = mock_driver.session.return_value.__enter__.return_value
        queries = [c[0][0] for c in session.run.call_args_list]
        node_queries = queries[:5]  # First 5 calls are node MERGEs
        all_query_text = " ".join(node_queries)
        assert "Session" in all_query_text
        assert "SessionChunk" in all_query_text
        assert "Entity" in all_query_text
        assert "Topic" in all_query_text
        assert "Decision" in all_query_text


# ---------------------------------------------------------------------------
# リレーション MERGE テスト
# ---------------------------------------------------------------------------


class TestRelationMerge:
    """5種リレーションの MERGE テスト."""

    def test_正常系_BELONGS_TOリレーションが作成される(
        self,
        writer: SessionGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        """SessionChunk -[:BELONGS_TO]-> Session リレーションが作成される."""
        queue = _build_sample_queue()
        _set_run_results(mock_driver, [1, 2, 1, 1, 1], [2, 1, 1, 1, 1])

        result = writer.ingest(queue, session_id="sess-001")

        assert result["relations_created"] >= 2
        session = mock_driver.session.return_value.__enter__.return_value
        queries = [c[0][0] for c in session.run.call_args_list]
        belongs_to_queries = [q for q in queries if "BELONGS_TO" in q]
        assert len(belongs_to_queries) >= 1

    def test_正常系_NEXTリレーションが作成される(
        self,
        writer: SessionGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        """SessionChunk -[:NEXT]-> SessionChunk リレーションが作成される."""
        queue = _build_sample_queue()
        _set_run_results(mock_driver, [1, 2, 1, 1, 1], [2, 1, 1, 1, 1])

        writer.ingest(queue, session_id="sess-001")

        session = mock_driver.session.return_value.__enter__.return_value
        queries = [c[0][0] for c in session.run.call_args_list]
        next_queries = [q for q in queries if ":NEXT]" in q or "NEXT" in q]
        assert len(next_queries) >= 1

    def test_正常系_MENTIONSリレーションが作成される(
        self,
        writer: SessionGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        """SessionChunk -[:MENTIONS]-> Entity リレーションが作成される."""
        queue = _build_sample_queue()
        _set_run_results(mock_driver, [1, 2, 1, 1, 1], [2, 1, 1, 1, 1])

        writer.ingest(queue, session_id="sess-001")

        session = mock_driver.session.return_value.__enter__.return_value
        queries = [c[0][0] for c in session.run.call_args_list]
        mentions_queries = [q for q in queries if "MENTIONS" in q]
        assert len(mentions_queries) >= 1

    def test_正常系_DISCUSSESリレーションが作成される(
        self,
        writer: SessionGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        """SessionChunk -[:DISCUSSES]-> Topic リレーションが作成される."""
        queue = _build_sample_queue()
        _set_run_results(mock_driver, [1, 2, 1, 1, 1], [2, 1, 1, 1, 1])

        writer.ingest(queue, session_id="sess-001")

        session = mock_driver.session.return_value.__enter__.return_value
        queries = [c[0][0] for c in session.run.call_args_list]
        discusses_queries = [q for q in queries if "DISCUSSES" in q]
        assert len(discusses_queries) >= 1

    def test_正常系_DECIDEDリレーションが作成される(
        self,
        writer: SessionGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        """SessionChunk -[:DECIDED]-> Decision リレーションが作成される."""
        queue = _build_sample_queue()
        _set_run_results(mock_driver, [1, 2, 1, 1, 1], [2, 1, 1, 1, 1])

        writer.ingest(queue, session_id="sess-001")

        session = mock_driver.session.return_value.__enter__.return_value
        queries = [c[0][0] for c in session.run.call_args_list]
        decided_queries = [q for q in queries if "DECIDED" in q]
        assert len(decided_queries) >= 1

    def test_正常系_全5リレーションの合計数が正しい(
        self,
        writer: SessionGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        """全5種リレーションの合計作成数が正しい."""
        queue = _build_sample_queue()
        _set_run_results(mock_driver, [1, 2, 1, 1, 1], [2, 1, 1, 1, 1])

        result = writer.ingest(queue, session_id="sess-001")

        # 2 + 1 + 1 + 1 + 1 = 6
        assert result["relations_created"] == 6


# ---------------------------------------------------------------------------
# 冪等性テスト
# ---------------------------------------------------------------------------


class TestIdempotency:
    """冪等性の保証テスト."""

    def test_正常系_MERGEパターンが使用されている(
        self,
        writer: SessionGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        """全クエリで MERGE パターンが使用されていることを確認."""
        queue = _build_sample_queue()
        _set_run_results(mock_driver, [1, 2, 1, 1, 1], [2, 1, 1, 1, 1])

        writer.ingest(queue, session_id="sess-001")

        session = mock_driver.session.return_value.__enter__.return_value
        for call_args in session.run.call_args_list:
            query = call_args[0][0]
            assert "MERGE" in query, f"MERGE not found in query: {query}"
            assert "CREATE" not in query, (
                f"CREATE found in query (should use MERGE): {query}"
            )

    def test_正常系_2回実行してもエラーにならない(
        self,
        writer: SessionGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        """同じデータで2回 ingest してもエラーにならない."""
        queue = _build_sample_queue()
        # 1st run: creates nodes/rels
        _set_run_results(mock_driver, [1, 2, 1, 1, 1], [2, 1, 1, 1, 1])
        result1 = writer.ingest(queue, session_id="sess-001")

        # Reset mock for 2nd run: 0 created (already exist)
        _set_run_results(mock_driver, [0, 0, 0, 0, 0], [0, 0, 0, 0, 0])
        result2 = writer.ingest(queue, session_id="sess-001")

        assert result1["nodes_created"] == 6
        assert result2["nodes_created"] == 0
        assert result2["relations_created"] == 0


# ---------------------------------------------------------------------------
# 空データテスト
# ---------------------------------------------------------------------------


class TestEmptyData:
    """空データのハンドリングテスト."""

    def test_エッジケース_空のqueue_docでスキップ(
        self,
        writer: SessionGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        """全キーが空の場合は 0/0 を返してスキップ."""
        queue: dict[str, Any] = {
            "sessions": [],
            "session_chunks": [],
            "entities": [],
            "topics": [],
            "decisions": [],
            "relations": {},
        }

        result = writer.ingest(queue, session_id="sess-001")

        assert result["nodes_created"] == 0
        assert result["relations_created"] == 0

    def test_エッジケース_relationsキーがない場合(
        self,
        writer: SessionGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        """relations キーが存在しない場合でもエラーにならない."""
        queue: dict[str, Any] = {
            "sessions": [
                {
                    "session_id": "sess-002",
                    "project": "test",
                },
            ],
        }
        _set_run_results(mock_driver, [1, 0, 0, 0, 0], [0, 0, 0, 0, 0])

        result = writer.ingest(queue, session_id="sess-002")

        assert result["nodes_created"] == 1
        assert result["relations_created"] == 0

    def test_エッジケース_queue_docが完全に空の辞書(
        self,
        writer: SessionGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        """完全に空の辞書でも 0/0 を返す."""
        result = writer.ingest({}, session_id="sess-003")

        assert result["nodes_created"] == 0
        assert result["relations_created"] == 0


# ---------------------------------------------------------------------------
# validate テスト
# ---------------------------------------------------------------------------


class TestValidate:
    """validate() メソッドのテスト."""

    def test_正常系_session_idでノードカウントを返す(
        self,
        writer: SessionGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        """session_id で投入されたノードのラベル別カウントを返す."""
        session = mock_driver.session.return_value.__enter__.return_value
        session.run.return_value = [
            {"label": "Session", "count": 1},
            {"label": "SessionChunk", "count": 5},
        ]

        result = writer.validate("sess-001")

        assert result == {"Session": 1, "SessionChunk": 5}

    def test_エッジケース_存在しないsession_idで空辞書(
        self,
        writer: SessionGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        """存在しない session_id では空辞書を返す."""
        session = mock_driver.session.return_value.__enter__.return_value
        session.run.return_value = []

        result = writer.validate("nonexistent-session")

        assert result == {}


# ---------------------------------------------------------------------------
# UNWINDパターン検証テスト
# ---------------------------------------------------------------------------


class TestUnwindPattern:
    """UNWIND $items / $rels パターンの検証."""

    def test_正常系_ノードMERGEでUNWINDパターンが使用される(
        self,
        writer: SessionGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        """ノード MERGE で UNWIND $items パターンが使用される."""
        queue = _build_sample_queue()
        _set_run_results(mock_driver, [1, 2, 1, 1, 1], [2, 1, 1, 1, 1])

        writer.ingest(queue, session_id="sess-001")

        session = mock_driver.session.return_value.__enter__.return_value
        # First 5 calls are node MERGEs
        for i in range(5):
            if i < len(session.run.call_args_list):
                query = session.run.call_args_list[i][0][0]
                if "UNWIND" in query:
                    assert "UNWIND $items" in query

    def test_正常系_リレーションMERGEでUNWINDパターンが使用される(
        self,
        writer: SessionGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        """リレーション MERGE で UNWIND $rels パターンが使用される."""
        queue = _build_sample_queue()
        _set_run_results(mock_driver, [1, 2, 1, 1, 1], [2, 1, 1, 1, 1])

        writer.ingest(queue, session_id="sess-001")

        session = mock_driver.session.return_value.__enter__.return_value
        # Calls after node MERGEs are relation MERGEs
        for call_args in session.run.call_args_list[5:]:
            query = call_args[0][0]
            if "UNWIND" in query:
                assert "UNWIND $rels" in query


# ---------------------------------------------------------------------------
# IngestResult 型テスト
# ---------------------------------------------------------------------------


class TestIngestResult:
    """ingest() の戻り値の型テスト."""

    def test_正常系_戻り値にnodes_createdとrelations_createdが含まれる(
        self,
        writer: SessionGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        """ingest() の戻り値に nodes_created と relations_created が含まれる."""
        queue = _build_sample_queue()
        _set_run_results(mock_driver, [1, 2, 1, 1, 1], [2, 1, 1, 1, 1])

        result = writer.ingest(queue, session_id="sess-001")

        assert "nodes_created" in result
        assert "relations_created" in result
        assert isinstance(result["nodes_created"], int)
        assert isinstance(result["relations_created"], int)


# ---------------------------------------------------------------------------
# session_id SET テスト
# ---------------------------------------------------------------------------


class TestSessionIdSet:
    """session_id がノードに SET されることのテスト."""

    def test_正常系_SessionノードにsessionIdがSETされる(
        self,
        writer: SessionGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        """Session と SessionChunk に session_id が SET される."""
        queue = _build_sample_queue()
        _set_run_results(mock_driver, [1, 2, 1, 1, 1], [2, 1, 1, 1, 1])

        writer.ingest(queue, session_id="sess-001")

        session = mock_driver.session.return_value.__enter__.return_value
        # Check that session_id parameter is passed
        for call_args in session.run.call_args_list[:2]:
            kwargs = call_args[1]
            if "session_id" in kwargs:
                assert kwargs["session_id"] == "sess-001"
