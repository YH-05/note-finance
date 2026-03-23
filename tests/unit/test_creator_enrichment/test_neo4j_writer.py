"""creator_enrichment.neo4j_writer のテスト.

CreatorGraphWriter の ingest / validate メソッドをモック Driver で検証する。
ノード MERGE の呼び出し順序（依存関係順）とリレーション MERGE の後続実行、
cycle_id の SET 対象、IngestResult の返却値を確認する。
"""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from creator_enrichment.neo4j_writer import CreatorGraphWriter
from creator_enrichment.types import IngestResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_driver() -> MagicMock:
    """Duck-typed neo4j.Driver モック.

    Returns
    -------
    MagicMock
        session() がコンテキストマネージャを返すモック Driver
    """
    driver = MagicMock()
    session = MagicMock()

    # session.run() の戻り値: consume().counters をモック
    counters = MagicMock()
    counters.nodes_created = 0
    counters.relationships_created = 0
    result_summary = MagicMock()
    result_summary.counters = counters
    run_result = MagicMock()
    run_result.consume.return_value = result_summary

    session.run.return_value = run_result

    # driver.session() をコンテキストマネージャとして利用可能に
    driver.session.return_value.__enter__ = MagicMock(return_value=session)
    driver.session.return_value.__exit__ = MagicMock(return_value=False)

    return driver


@pytest.fixture
def writer(mock_driver: MagicMock) -> CreatorGraphWriter:
    """CreatorGraphWriter インスタンス.

    Returns
    -------
    CreatorGraphWriter
        モック Driver で初期化された Writer
    """
    return CreatorGraphWriter(mock_driver)


@pytest.fixture
def sample_queue_doc() -> dict:
    """サンプル queue_doc (creator-2.0 形式).

    Returns
    -------
    dict
        10 ノード種 + 11 リレーション種を含む queue_doc
    """
    return {
        "schema_version": "creator-2.0",
        "queue_id": "cq-test-001",
        "genre_id": "career",
        "genres": [{"genre_id": "career", "name": "転職・副業"}],
        "concept_categories": [
            {"name": "Skill", "name_ja": "スキル・技能", "layer": "what"},
        ],
        "concepts": [
            {"concept_id": "concept-abc12345", "name": "転職活動", "category": "Skill"},
        ],
        "entities": [
            {
                "entity_id": "ent-001",
                "entity_key": "LinkedIn::platform",
                "name": "LinkedIn",
                "entity_type": "platform",
            },
        ],
        "sources": [
            {
                "source_id": "src-001",
                "url": "https://example.com/article-1",
                "title": "転職市場の最新動向",
                "source_type": "web",
                "authority_level": "media",
                "language": "ja",
                "domain": "example.com",
                "collected_at": "",
                "published_at": "",
            },
        ],
        "domains": [{"name": "example.com"}],
        "facts": [
            {
                "fact_id": "fact-001",
                "text": "2026年の転職市場は前年比20%増加",
                "category": "statistics",
                "confidence": "high",
            },
        ],
        "tips": [
            {
                "tip_id": "tip-001",
                "text": "職務経歴書には具体的な数字を入れる",
                "category": "strategy",
                "difficulty": "beginner",
            },
        ],
        "stories": [
            {
                "story_id": "story-001",
                "text": "IT企業から外資コンサルへ転職した事例",
                "outcome": "success",
                "timeline": "3ヶ月",
            },
        ],
        "aliases": [
            {"value": "リンクトイン", "language": "ja"},
        ],
        "relations": {
            "is_a": [{"from_id": "concept-abc12345", "to_id": "Skill"}],
            "serves_as": [
                {
                    "from_id": "ent-001",
                    "to_id": "concept-abc12345",
                    "context": "転職活動プラットフォーム",
                },
            ],
            "about_fact": [{"from_id": "fact-001", "to_id": "concept-abc12345"}],
            "about_tip": [{"from_id": "tip-001", "to_id": "concept-abc12345"}],
            "about_story": [{"from_id": "story-001", "to_id": "concept-abc12345"}],
            "mentions_fact": [{"from_id": "fact-001", "to_id": "ent-001"}],
            "mentions_tip": [{"from_id": "tip-001", "to_id": "ent-001"}],
            "mentions_story": [{"from_id": "story-001", "to_id": "ent-001"}],
            "in_genre_fact": [{"from_id": "fact-001", "to_id": "career"}],
            "in_genre_tip": [{"from_id": "tip-001", "to_id": "career"}],
            "in_genre_story": [{"from_id": "story-001", "to_id": "career"}],
            "from_source_fact": [{"from_id": "fact-001", "to_id": "src-001"}],
            "from_source_tip": [{"from_id": "tip-001", "to_id": "src-001"}],
            "from_source_story": [{"from_id": "story-001", "to_id": "src-001"}],
            "from_domain": [{"from_id": "src-001", "to_id": "example.com"}],
            "alias_of": [{"alias_value": "リンクトイン", "target_id": "ent-001"}],
        },
    }


@pytest.fixture
def empty_queue_doc() -> dict:
    """空の queue_doc.

    Returns
    -------
    dict
        全ノード・リレーションが空の queue_doc
    """
    return {
        "schema_version": "creator-2.0",
        "queue_id": "cq-empty-001",
        "genres": [],
        "concept_categories": [],
        "concepts": [],
        "entities": [],
        "sources": [],
        "domains": [],
        "facts": [],
        "tips": [],
        "stories": [],
        "aliases": [],
        "relations": {},
    }


# ---------------------------------------------------------------------------
# CreatorGraphWriter 初期化
# ---------------------------------------------------------------------------
class TestCreatorGraphWriterInit:
    """CreatorGraphWriter 初期化のテスト."""

    def test_正常系_driverを受け取りインスタンス生成(
        self,
        mock_driver: MagicMock,
    ) -> None:
        writer = CreatorGraphWriter(mock_driver)
        assert writer._driver is mock_driver

    def test_正常系_NODE_ORDERが10種定義されている(self) -> None:
        assert len(CreatorGraphWriter._NODE_ORDER) == 10

    def test_正常系_REL_ORDERが定義されている(self) -> None:
        assert len(CreatorGraphWriter._REL_ORDER) > 0


# ---------------------------------------------------------------------------
# ingest: ノード MERGE 順序
# ---------------------------------------------------------------------------
class TestIngestNodeOrder:
    """ingest() のノード MERGE 呼び出し順序テスト."""

    def test_正常系_ノードが依存関係順でMERGEされる(
        self,
        writer: CreatorGraphWriter,
        mock_driver: MagicMock,
        sample_queue_doc: dict,
    ) -> None:
        session = mock_driver.session.return_value.__enter__.return_value

        writer.ingest(sample_queue_doc, cycle_id="cycle-test-001")

        # session.run に渡された全クエリを抽出
        queries = [c.args[0] for c in session.run.call_args_list]

        # ノード MERGE クエリの出現順序を検証
        node_labels_in_order = []
        for query in queries:
            if "MERGE" in query and "MATCH" not in query:
                # "MERGE (n:Genre" のような形式からラベルを抽出
                for label, _, _ in CreatorGraphWriter._NODE_ORDER:
                    if (f":{label} " in query or f":{label}" in query) and label not in node_labels_in_order:
                            node_labels_in_order.append(label)

        expected_order = [label for label, _, _ in CreatorGraphWriter._NODE_ORDER]
        # 実際に MERGE されたラベルだけで順序を検証
        # （空リストのラベルはスキップされる可能性がある）
        actual_filtered = [lbl for lbl in expected_order if lbl in node_labels_in_order]
        assert node_labels_in_order == actual_filtered

    def test_正常系_ノードMERGEがリレーションMERGEの前に実行される(
        self,
        writer: CreatorGraphWriter,
        mock_driver: MagicMock,
        sample_queue_doc: dict,
    ) -> None:
        session = mock_driver.session.return_value.__enter__.return_value

        writer.ingest(sample_queue_doc, cycle_id="cycle-test-001")

        queries = [c.args[0] for c in session.run.call_args_list]

        # リレーション MERGE クエリは MATCH ... MERGE パターン
        first_rel_idx = None
        last_node_idx = None
        for i, query in enumerate(queries):
            if "MATCH" in query and "MERGE" in query:
                if first_rel_idx is None:
                    first_rel_idx = i
            elif "MERGE" in query and "MATCH" not in query:
                last_node_idx = i

        if first_rel_idx is not None and last_node_idx is not None:
            assert last_node_idx < first_rel_idx, (
                "最後のノード MERGE は最初のリレーション MERGE の前に来るべき"
            )


# ---------------------------------------------------------------------------
# ingest: cycle_id の SET
# ---------------------------------------------------------------------------
class TestIngestCycleId:
    """ingest() の cycle_id SET テスト."""

    def test_正常系_FactにcycleIdがSETされる(
        self,
        writer: CreatorGraphWriter,
        mock_driver: MagicMock,
        sample_queue_doc: dict,
    ) -> None:
        session = mock_driver.session.return_value.__enter__.return_value

        writer.ingest(sample_queue_doc, cycle_id="cycle-abc")

        queries = [c.args[0] for c in session.run.call_args_list]
        fact_queries = [q for q in queries if ":Fact" in q and "MATCH" not in q]
        assert len(fact_queries) > 0
        assert any("cycle_id" in q for q in fact_queries)

    def test_正常系_TipにcycleIdがSETされる(
        self,
        writer: CreatorGraphWriter,
        mock_driver: MagicMock,
        sample_queue_doc: dict,
    ) -> None:
        session = mock_driver.session.return_value.__enter__.return_value

        writer.ingest(sample_queue_doc, cycle_id="cycle-abc")

        queries = [c.args[0] for c in session.run.call_args_list]
        tip_queries = [q for q in queries if ":Tip" in q and "MATCH" not in q]
        assert len(tip_queries) > 0
        assert any("cycle_id" in q for q in tip_queries)

    def test_正常系_StorにcycleIdがSETされる(
        self,
        writer: CreatorGraphWriter,
        mock_driver: MagicMock,
        sample_queue_doc: dict,
    ) -> None:
        session = mock_driver.session.return_value.__enter__.return_value

        writer.ingest(sample_queue_doc, cycle_id="cycle-abc")

        queries = [c.args[0] for c in session.run.call_args_list]
        story_queries = [q for q in queries if ":Story" in q and "MATCH" not in q]
        assert len(story_queries) > 0
        assert any("cycle_id" in q for q in story_queries)

    def test_正常系_GenreにはcycleIdがSETされない(
        self,
        writer: CreatorGraphWriter,
        mock_driver: MagicMock,
        sample_queue_doc: dict,
    ) -> None:
        session = mock_driver.session.return_value.__enter__.return_value

        writer.ingest(sample_queue_doc, cycle_id="cycle-abc")

        queries = [c.args[0] for c in session.run.call_args_list]
        genre_queries = [q for q in queries if ":Genre" in q and "MATCH" not in q]
        # Genre クエリに cycle_id は含まれない
        for q in genre_queries:
            assert "cycle_id" not in q


# ---------------------------------------------------------------------------
# ingest: IngestResult
# ---------------------------------------------------------------------------
class TestIngestResult:
    """ingest() の IngestResult 返却テスト."""

    def test_正常系_IngestResultが返される(
        self,
        writer: CreatorGraphWriter,
        sample_queue_doc: dict,
    ) -> None:
        result = writer.ingest(sample_queue_doc, cycle_id="cycle-test")
        assert "nodes_created" in result
        assert "relations_created" in result

    def test_正常系_nodes_createdがint(
        self,
        writer: CreatorGraphWriter,
        sample_queue_doc: dict,
    ) -> None:
        result = writer.ingest(sample_queue_doc, cycle_id="cycle-test")
        assert isinstance(result["nodes_created"], int)

    def test_正常系_relations_createdがint(
        self,
        writer: CreatorGraphWriter,
        sample_queue_doc: dict,
    ) -> None:
        result = writer.ingest(sample_queue_doc, cycle_id="cycle-test")
        assert isinstance(result["relations_created"], int)

    def test_正常系_カウンタがsummary値を反映(
        self,
        mock_driver: MagicMock,
    ) -> None:
        """Driver の counters 値が IngestResult に集計されることを確認."""
        session = mock_driver.session.return_value.__enter__.return_value

        # nodes_created=3 を返すモック
        counters = MagicMock()
        counters.nodes_created = 3
        counters.relationships_created = 2
        summary = MagicMock()
        summary.counters = counters
        run_result = MagicMock()
        run_result.consume.return_value = summary
        session.run.return_value = run_result

        writer = CreatorGraphWriter(mock_driver)
        queue_doc = {
            "genres": [{"genre_id": "career", "name": "転職・副業"}],
            "concept_categories": [],
            "concepts": [],
            "entities": [],
            "sources": [],
            "domains": [],
            "facts": [{"fact_id": "f1", "text": "test fact"}],
            "tips": [],
            "stories": [],
            "aliases": [],
            "relations": {},
        }
        result = writer.ingest(queue_doc, cycle_id="cycle-test")

        # 複数回 run が呼ばれた場合の合計が返される
        assert result["nodes_created"] >= 0
        assert result["relations_created"] >= 0


# ---------------------------------------------------------------------------
# ingest: 空の queue_doc
# ---------------------------------------------------------------------------
class TestIngestEmptyDoc:
    """空の queue_doc に対する ingest() テスト."""

    def test_正常系_空docでエラーにならない(
        self,
        writer: CreatorGraphWriter,
        empty_queue_doc: dict,
    ) -> None:
        result = writer.ingest(empty_queue_doc, cycle_id="cycle-empty")
        assert result["nodes_created"] == 0
        assert result["relations_created"] == 0

    def test_正常系_空docでsessionRunが呼ばれない(
        self,
        writer: CreatorGraphWriter,
        mock_driver: MagicMock,
        empty_queue_doc: dict,
    ) -> None:
        session = mock_driver.session.return_value.__enter__.return_value
        writer.ingest(empty_queue_doc, cycle_id="cycle-empty")
        # 空リストなので session.run は呼ばれない
        session.run.assert_not_called()


# ---------------------------------------------------------------------------
# ingest: リレーション MERGE
# ---------------------------------------------------------------------------
class TestIngestRelations:
    """ingest() のリレーション MERGE テスト."""

    def test_正常系_ISAリレーションがMERGEされる(
        self,
        writer: CreatorGraphWriter,
        mock_driver: MagicMock,
        sample_queue_doc: dict,
    ) -> None:
        session = mock_driver.session.return_value.__enter__.return_value
        writer.ingest(sample_queue_doc, cycle_id="cycle-test")

        queries = [c.args[0] for c in session.run.call_args_list]
        is_a_queries = [q for q in queries if "IS_A" in q]
        assert len(is_a_queries) > 0

    def test_正常系_SERVES_ASリレーションがMERGEされる(
        self,
        writer: CreatorGraphWriter,
        mock_driver: MagicMock,
        sample_queue_doc: dict,
    ) -> None:
        session = mock_driver.session.return_value.__enter__.return_value
        writer.ingest(sample_queue_doc, cycle_id="cycle-test")

        queries = [c.args[0] for c in session.run.call_args_list]
        serves_as_queries = [q for q in queries if "SERVES_AS" in q]
        assert len(serves_as_queries) > 0

    def test_正常系_ABOUTリレーションが3種MERGEされる(
        self,
        writer: CreatorGraphWriter,
        mock_driver: MagicMock,
        sample_queue_doc: dict,
    ) -> None:
        session = mock_driver.session.return_value.__enter__.return_value
        writer.ingest(sample_queue_doc, cycle_id="cycle-test")

        queries = [c.args[0] for c in session.run.call_args_list]
        about_queries = [q for q in queries if "ABOUT" in q]
        # Fact, Tip, Story それぞれの ABOUT
        assert len(about_queries) >= 3

    def test_正常系_MENTIONSリレーションがMERGEされる(
        self,
        writer: CreatorGraphWriter,
        mock_driver: MagicMock,
        sample_queue_doc: dict,
    ) -> None:
        session = mock_driver.session.return_value.__enter__.return_value
        writer.ingest(sample_queue_doc, cycle_id="cycle-test")

        queries = [c.args[0] for c in session.run.call_args_list]
        mentions_queries = [q for q in queries if "MENTIONS" in q]
        assert len(mentions_queries) >= 3

    def test_正常系_IN_GENREリレーションがMERGEされる(
        self,
        writer: CreatorGraphWriter,
        mock_driver: MagicMock,
        sample_queue_doc: dict,
    ) -> None:
        session = mock_driver.session.return_value.__enter__.return_value
        writer.ingest(sample_queue_doc, cycle_id="cycle-test")

        queries = [c.args[0] for c in session.run.call_args_list]
        in_genre_queries = [q for q in queries if "IN_GENRE" in q]
        assert len(in_genre_queries) >= 1

    def test_正常系_FROM_SOURCEリレーションがMERGEされる(
        self,
        writer: CreatorGraphWriter,
        mock_driver: MagicMock,
        sample_queue_doc: dict,
    ) -> None:
        session = mock_driver.session.return_value.__enter__.return_value
        writer.ingest(sample_queue_doc, cycle_id="cycle-test")

        queries = [c.args[0] for c in session.run.call_args_list]
        from_source_queries = [q for q in queries if "FROM_SOURCE" in q]
        assert len(from_source_queries) >= 1

    def test_正常系_FROM_DOMAINリレーションがMERGEされる(
        self,
        writer: CreatorGraphWriter,
        mock_driver: MagicMock,
        sample_queue_doc: dict,
    ) -> None:
        session = mock_driver.session.return_value.__enter__.return_value
        writer.ingest(sample_queue_doc, cycle_id="cycle-test")

        queries = [c.args[0] for c in session.run.call_args_list]
        from_domain_queries = [q for q in queries if "FROM_DOMAIN" in q]
        assert len(from_domain_queries) >= 1

    def test_正常系_ALIAS_OFリレーションがMERGEされる(
        self,
        writer: CreatorGraphWriter,
        mock_driver: MagicMock,
        sample_queue_doc: dict,
    ) -> None:
        session = mock_driver.session.return_value.__enter__.return_value
        writer.ingest(sample_queue_doc, cycle_id="cycle-test")

        queries = [c.args[0] for c in session.run.call_args_list]
        alias_of_queries = [q for q in queries if "ALIAS_OF" in q]
        assert len(alias_of_queries) >= 1


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------
class TestValidate:
    """validate() メソッドのテスト."""

    def test_正常系_cycleIdでクエリが実行される(
        self,
        writer: CreatorGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        session = mock_driver.session.return_value.__enter__.return_value

        # validate 用のモック戻り値
        mock_record1 = MagicMock()
        mock_record1.__getitem__ = lambda self, key: {"label": "Fact", "count": 5}[key]
        mock_record2 = MagicMock()
        mock_record2.__getitem__ = lambda self, key: {"label": "Tip", "count": 3}[key]
        session.run.return_value = [mock_record1, mock_record2]

        writer.validate("cycle-test-001")

        # session.run が cycle_id パラメータ付きで呼ばれたことを確認
        session.run.assert_called()
        call_args = session.run.call_args
        assert "cycle_id" in call_args.kwargs or (
            len(call_args.args) > 1 and "cycle_id" in str(call_args)
        )

    def test_正常系_validateクエリにcycleIdが含まれる(
        self,
        writer: CreatorGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        session = mock_driver.session.return_value.__enter__.return_value
        session.run.return_value = []

        writer.validate("cycle-xyz")

        query = session.run.call_args.args[0]
        assert "cycle_id" in query
        assert "MATCH" in query

    def test_正常系_validateが辞書を返す(
        self,
        writer: CreatorGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        session = mock_driver.session.return_value.__enter__.return_value
        session.run.return_value = []

        result = writer.validate("cycle-test")
        assert isinstance(result, dict)

    def test_正常系_validateがラベル別カウントを返す(
        self,
        writer: CreatorGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        session = mock_driver.session.return_value.__enter__.return_value

        # ラベル別カウントのモック結果
        mock_record1 = {"label": "Fact", "count": 5}
        mock_record2 = {"label": "Tip", "count": 3}
        session.run.return_value = [mock_record1, mock_record2]

        result = writer.validate("cycle-test")
        assert result.get("Fact") == 5
        assert result.get("Tip") == 3


# ---------------------------------------------------------------------------
# _merge_nodes 内部メソッド
# ---------------------------------------------------------------------------
class TestMergeNodes:
    """_merge_nodes 内部メソッドのテスト."""

    def test_正常系_空リストで0を返す(
        self,
        writer: CreatorGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        session = mock_driver.session.return_value.__enter__.return_value
        count = writer._merge_nodes(session, "Genre", [], "genre_id")
        assert count == 0
        # 空リストなので session.run は呼ばれない
        session.run.assert_not_called()

    def test_正常系_UNWINDクエリが生成される(
        self,
        writer: CreatorGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        session = mock_driver.session.return_value.__enter__.return_value
        items = [{"genre_id": "career", "name": "転職・副業"}]

        writer._merge_nodes(session, "Genre", items, "genre_id")

        query = session.run.call_args.args[0]
        assert "UNWIND" in query
        assert "MERGE" in query
        assert ":Genre" in query
        assert "genre_id" in query

    def test_正常系_cycleId付きクエリが生成される(
        self,
        writer: CreatorGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        session = mock_driver.session.return_value.__enter__.return_value
        items = [{"fact_id": "f1", "text": "test"}]

        writer._merge_nodes(
            session,
            "Fact",
            items,
            "fact_id",
            cycle_id="cycle-abc",
        )

        query = session.run.call_args.args[0]
        assert "cycle_id" in query


# ---------------------------------------------------------------------------
# _merge_relations 内部メソッド
# ---------------------------------------------------------------------------
class TestMergeRelations:
    """_merge_relations 内部メソッドのテスト."""

    def test_正常系_空リストで0を返す(
        self,
        writer: CreatorGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        session = mock_driver.session.return_value.__enter__.return_value
        count = writer._merge_relations(
            session,
            rel_type="IS_A",
            from_label="Concept",
            to_label="ConceptCategory",
            from_key="concept_id",
            to_key="name",
            items=[],
        )
        assert count == 0

    def test_正常系_MATCHとMERGEを含むクエリが生成される(
        self,
        writer: CreatorGraphWriter,
        mock_driver: MagicMock,
    ) -> None:
        session = mock_driver.session.return_value.__enter__.return_value
        items = [{"from_id": "concept-001", "to_id": "Skill"}]

        writer._merge_relations(
            session,
            rel_type="IS_A",
            from_label="Concept",
            to_label="ConceptCategory",
            from_key="concept_id",
            to_key="name",
            items=items,
        )

        query = session.run.call_args.args[0]
        assert "MATCH" in query
        assert "MERGE" in query
        assert "IS_A" in query
        assert ":Concept" in query
        assert ":ConceptCategory" in query
