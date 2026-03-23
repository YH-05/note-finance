"""creator_enrichment.phases.cross_entity のテスト.

CrossEntityEnricher による Entity ペア抽出・LLM 判定・リレーション MERGE を検証する。
- 共起クエリが 0 件の場合に 0 を返す
- 25 ペア超時のトランケーション
- SKIP フィルタリング（SKIP 以外のみ MERGE）
- LLM 呼び出しプロンプトの正しさ
- 両クエリとも空の場合に LLM を呼ばない
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, call

import pytest

from creator_enrichment.phases.cross_entity import CrossEntityEnricher


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

    # デフォルト: 空結果を返す
    session.run.return_value = iter([])

    # driver.session() をコンテキストマネージャとして利用可能に
    driver.session.return_value.__enter__ = MagicMock(return_value=session)
    driver.session.return_value.__exit__ = MagicMock(return_value=False)

    return driver


def _make_mock_response(text: str) -> MagicMock:
    """Anthropic API レスポンスのモックを生成する."""
    mock_content = MagicMock()
    mock_content.text = text
    mock_response = MagicMock()
    mock_response.content = [mock_content]
    return mock_response


def _make_co_occurrence_record(
    from_name: str,
    from_type: str,
    from_id: str,
    to_name: str,
    to_type: str,
    to_id: str,
    co_occurrence: int = 3,
) -> dict:
    """共起クエリの結果レコードを生成する."""
    return {
        "from_name": from_name,
        "from_type": from_type,
        "from_id": from_id,
        "to_name": to_name,
        "to_type": to_type,
        "to_id": to_id,
        "co_occurrence": co_occurrence,
    }


def _make_same_type_record(
    from_name: str,
    from_type: str,
    from_id: str,
    to_name: str,
    to_type: str,
    to_id: str,
    from_context: str | None = None,
    to_context: str | None = None,
) -> dict:
    """同一タイプクエリの結果レコードを生成する."""
    return {
        "from_name": from_name,
        "from_type": from_type,
        "from_id": from_id,
        "to_name": to_name,
        "to_type": to_type,
        "to_id": to_id,
        "from_context": from_context,
        "to_context": to_context,
    }


# ---------------------------------------------------------------------------
# 初期化
# ---------------------------------------------------------------------------
class TestCrossEntityEnricherInit:
    """CrossEntityEnricher 初期化のテスト."""

    def test_正常系_driverとclientを受け取りインスタンス生成(
        self,
        mock_driver: MagicMock,
        mock_anthropic_client: MagicMock,
    ) -> None:
        """driver と client を渡してインスタンスが生成できる."""
        enricher = CrossEntityEnricher(mock_driver, mock_anthropic_client)
        assert enricher._driver is mock_driver
        assert enricher._client is mock_anthropic_client


# ---------------------------------------------------------------------------
# run: 候補なしで 0 を返す
# ---------------------------------------------------------------------------
class TestRunNoCandidates:
    """候補なしの場合のテスト."""

    def test_正常系_共起クエリ0件で0を返す(
        self,
        mock_driver: MagicMock,
        mock_anthropic_client: MagicMock,
    ) -> None:
        """共起クエリが 0 件を返す場合、run() は 0 を返す."""
        session = mock_driver.session.return_value.__enter__.return_value
        # 両クエリとも空
        session.run.return_value = iter([])

        enricher = CrossEntityEnricher(mock_driver, mock_anthropic_client)
        result = enricher.run(cycle_count=3)

        assert result == 0

    def test_正常系_両クエリ空でLLMが呼ばれない(
        self,
        mock_driver: MagicMock,
        mock_anthropic_client: MagicMock,
    ) -> None:
        """両クエリとも空の場合、LLM は呼び出されない."""
        session = mock_driver.session.return_value.__enter__.return_value
        session.run.return_value = iter([])

        enricher = CrossEntityEnricher(mock_driver, mock_anthropic_client)
        enricher.run(cycle_count=3)

        mock_anthropic_client.messages.create.assert_not_called()


# ---------------------------------------------------------------------------
# run: 25 ペアトランケーション
# ---------------------------------------------------------------------------
class TestRunTruncation:
    """25 ペア上限のトランケーションテスト."""

    def test_正常系_25ペア超がトランケーションされる(
        self,
        mock_driver: MagicMock,
        mock_anthropic_client: MagicMock,
    ) -> None:
        """30 件の共起候補が 25 ペアに制限される."""
        session = mock_driver.session.return_value.__enter__.return_value

        # 30 件の共起候補を生成
        co_occurrence_records = [
            _make_co_occurrence_record(
                from_name=f"Entity-A{i}",
                from_type="platform",
                from_id=f"ent-a{i}",
                to_name=f"Entity-B{i}",
                to_type="company",
                to_id=f"ent-b{i}",
                co_occurrence=30 - i,
            )
            for i in range(30)
        ]

        # 1回目の run (共起クエリ): 30 件、2回目 (同一タイプ): 0 件
        session.run.side_effect = [
            iter(co_occurrence_records),
            iter([]),
            iter([]),  # MERGE クエリ用
        ]

        # LLM レスポンス: 25 件全て RELATES_TO
        llm_response = [
            {"from_id": f"ent-a{i}", "to_id": f"ent-b{i}", "rel_detail": "RELATED"}
            for i in range(25)
        ]
        mock_anthropic_client.messages.create.return_value = _make_mock_response(
            json.dumps(llm_response, ensure_ascii=False)
        )

        enricher = CrossEntityEnricher(mock_driver, mock_anthropic_client)
        enricher.run(cycle_count=3)

        # LLM に送られるペア数を検証
        call_args = mock_anthropic_client.messages.create.call_args
        prompt = call_args.kwargs["messages"][0]["content"]
        # プロンプト内の from_id 数で 25 ペアを確認
        # ent-a25 以降は含まれないことを確認
        assert "ent-a24" in prompt
        assert "ent-a25" not in prompt


# ---------------------------------------------------------------------------
# run: SKIP フィルタリング
# ---------------------------------------------------------------------------
class TestRunSkipFiltering:
    """SKIP リレーションのフィルタリングテスト."""

    def test_正常系_SKIPリレーションがMERGEされない(
        self,
        mock_driver: MagicMock,
        mock_anthropic_client: MagicMock,
    ) -> None:
        """LLM が SKIP と判定したペアは MERGE されない."""
        session = mock_driver.session.return_value.__enter__.return_value

        co_occurrence_records = [
            _make_co_occurrence_record(
                from_name="LinkedIn",
                from_type="platform",
                from_id="ent-linkedin",
                to_name="Indeed",
                to_type="platform",
                to_id="ent-indeed",
            ),
            _make_co_occurrence_record(
                from_name="Google",
                from_type="company",
                from_id="ent-google",
                to_name="Amazon",
                to_type="company",
                to_id="ent-amazon",
            ),
            _make_co_occurrence_record(
                from_name="YouTube",
                from_type="platform",
                from_id="ent-youtube",
                to_name="TikTok",
                to_type="platform",
                to_id="ent-tiktok",
            ),
        ]

        session.run.side_effect = [
            iter(co_occurrence_records),
            iter([]),
            iter([]),  # MERGE 用
        ]

        # 1件は COMPETES_WITH、1件は SKIP、1件は RELATED
        llm_response = [
            {
                "from_id": "ent-linkedin",
                "to_id": "ent-indeed",
                "rel_detail": "COMPETES_WITH",
            },
            {"from_id": "ent-google", "to_id": "ent-amazon", "rel_detail": "SKIP"},
            {"from_id": "ent-youtube", "to_id": "ent-tiktok", "rel_detail": "RELATED"},
        ]
        mock_anthropic_client.messages.create.return_value = _make_mock_response(
            json.dumps(llm_response, ensure_ascii=False)
        )

        enricher = CrossEntityEnricher(mock_driver, mock_anthropic_client)
        enricher.run(cycle_count=3)

        # MERGE クエリに渡される rels を検証
        # 3回目の session.run (MERGE) に渡されるパラメータを確認
        merge_call = session.run.call_args_list[-1]
        merge_query = merge_call.args[0]
        assert "MERGE" in merge_query
        assert "RELATES_TO" in merge_query

        # MERGE に渡された rels パラメータ
        merge_kwargs = merge_call.kwargs
        rels = merge_kwargs.get("rels", [])
        # SKIP は除外されて 2 件のみ
        assert len(rels) == 2
        rel_details = [r["rel_detail"] for r in rels]
        assert "SKIP" not in rel_details
        assert "COMPETES_WITH" in rel_details
        assert "RELATED" in rel_details

    def test_正常系_全SKIPの場合MERGEされずrun結果0(
        self,
        mock_driver: MagicMock,
        mock_anthropic_client: MagicMock,
    ) -> None:
        """全ペアが SKIP の場合、MERGE は実行されず 0 を返す."""
        session = mock_driver.session.return_value.__enter__.return_value

        co_occurrence_records = [
            _make_co_occurrence_record(
                from_name="A",
                from_type="platform",
                from_id="ent-a",
                to_name="B",
                to_type="company",
                to_id="ent-b",
            ),
        ]

        session.run.side_effect = [
            iter(co_occurrence_records),
            iter([]),
        ]

        llm_response = [
            {"from_id": "ent-a", "to_id": "ent-b", "rel_detail": "SKIP"},
        ]
        mock_anthropic_client.messages.create.return_value = _make_mock_response(
            json.dumps(llm_response, ensure_ascii=False)
        )

        enricher = CrossEntityEnricher(mock_driver, mock_anthropic_client)
        result = enricher.run(cycle_count=3)

        assert result == 0


# ---------------------------------------------------------------------------
# run: LLM 呼び出しプロンプトの検証
# ---------------------------------------------------------------------------
class TestRunLLMPrompt:
    """LLM 呼び出しプロンプトの正しさテスト."""

    def test_正常系_LLMに正しいプロンプトが送られる(
        self,
        mock_driver: MagicMock,
        mock_anthropic_client: MagicMock,
    ) -> None:
        """LLM プロンプトに Entity ペア情報と判定基準が含まれる."""
        session = mock_driver.session.return_value.__enter__.return_value

        co_occurrence_records = [
            _make_co_occurrence_record(
                from_name="LinkedIn",
                from_type="platform",
                from_id="ent-linkedin",
                to_name="Indeed",
                to_type="platform",
                to_id="ent-indeed",
                co_occurrence=5,
            ),
        ]

        session.run.side_effect = [
            iter(co_occurrence_records),
            iter([]),
            iter([]),
        ]

        llm_response = [
            {
                "from_id": "ent-linkedin",
                "to_id": "ent-indeed",
                "rel_detail": "COMPETES_WITH",
            },
        ]
        mock_anthropic_client.messages.create.return_value = _make_mock_response(
            json.dumps(llm_response, ensure_ascii=False)
        )

        enricher = CrossEntityEnricher(mock_driver, mock_anthropic_client)
        enricher.run(cycle_count=3)

        call_args = mock_anthropic_client.messages.create.call_args
        prompt = call_args.kwargs["messages"][0]["content"]

        # プロンプトに Entity 名が含まれる
        assert "LinkedIn" in prompt
        assert "Indeed" in prompt

        # プロンプトに判定基準のキーワードが含まれる
        assert "ENABLES" in prompt
        assert "USES" in prompt
        assert "COMPETES_WITH" in prompt
        assert "SKIP" in prompt

        # モデル名が正しい
        assert call_args.kwargs["model"] == "claude-haiku-4-5-20251001"

    def test_正常系_同一タイプ候補もプロンプトに含まれる(
        self,
        mock_driver: MagicMock,
        mock_anthropic_client: MagicMock,
    ) -> None:
        """同一タイプクエリの結果も LLM プロンプトに含まれる."""
        session = mock_driver.session.return_value.__enter__.return_value

        same_type_records = [
            _make_same_type_record(
                from_name="Notion",
                from_type="platform",
                from_id="ent-notion",
                to_name="Obsidian",
                to_type="platform",
                to_id="ent-obsidian",
                from_context="ナレッジ管理ツール",
                to_context="PKM ツール",
            ),
        ]

        session.run.side_effect = [
            iter([]),  # 共起クエリ: 0 件
            iter(same_type_records),  # 同一タイプクエリ: 1 件
            iter([]),  # MERGE 用
        ]

        llm_response = [
            {
                "from_id": "ent-notion",
                "to_id": "ent-obsidian",
                "rel_detail": "COMPETES_WITH",
            },
        ]
        mock_anthropic_client.messages.create.return_value = _make_mock_response(
            json.dumps(llm_response, ensure_ascii=False)
        )

        enricher = CrossEntityEnricher(mock_driver, mock_anthropic_client)
        enricher.run(cycle_count=3)

        call_args = mock_anthropic_client.messages.create.call_args
        prompt = call_args.kwargs["messages"][0]["content"]
        assert "Notion" in prompt
        assert "Obsidian" in prompt

    def test_正常系_JSONコードブロック付きレスポンスを処理できる(
        self,
        mock_driver: MagicMock,
        mock_anthropic_client: MagicMock,
    ) -> None:
        """```json ... ``` でラップされた LLM レスポンスを処理できる."""
        session = mock_driver.session.return_value.__enter__.return_value

        co_occurrence_records = [
            _make_co_occurrence_record(
                from_name="A",
                from_type="platform",
                from_id="ent-a",
                to_name="B",
                to_type="company",
                to_id="ent-b",
            ),
        ]

        session.run.side_effect = [
            iter(co_occurrence_records),
            iter([]),
            iter([]),
        ]

        # JSON コードブロック付きレスポンス
        llm_response = [
            {"from_id": "ent-a", "to_id": "ent-b", "rel_detail": "ENABLES"},
        ]
        wrapped = f"```json\n{json.dumps(llm_response, ensure_ascii=False)}\n```"
        mock_anthropic_client.messages.create.return_value = _make_mock_response(
            wrapped
        )

        enricher = CrossEntityEnricher(mock_driver, mock_anthropic_client)
        result = enricher.run(cycle_count=3)

        # コードブロックが正しくパースされ、1件の MERGE が実行される
        assert result == 1


# ---------------------------------------------------------------------------
# run: MERGE クエリの検証
# ---------------------------------------------------------------------------
class TestRunMergeQuery:
    """MERGE クエリの正しさテスト."""

    def test_正常系_MERGEクエリにrel_detailとsourceとcreated_atが含まれる(
        self,
        mock_driver: MagicMock,
        mock_anthropic_client: MagicMock,
    ) -> None:
        """MERGE クエリに rel_detail, source, created_at が SET される."""
        session = mock_driver.session.return_value.__enter__.return_value

        co_occurrence_records = [
            _make_co_occurrence_record(
                from_name="A",
                from_type="platform",
                from_id="ent-a",
                to_name="B",
                to_type="company",
                to_id="ent-b",
            ),
        ]

        session.run.side_effect = [
            iter(co_occurrence_records),
            iter([]),
            iter([]),
        ]

        llm_response = [
            {"from_id": "ent-a", "to_id": "ent-b", "rel_detail": "ENABLES"},
        ]
        mock_anthropic_client.messages.create.return_value = _make_mock_response(
            json.dumps(llm_response, ensure_ascii=False)
        )

        enricher = CrossEntityEnricher(mock_driver, mock_anthropic_client)
        enricher.run(cycle_count=3)

        # MERGE クエリの内容を検証
        merge_call = session.run.call_args_list[-1]
        merge_query = merge_call.args[0]
        assert "RELATES_TO" in merge_query
        assert "rel_detail" in merge_query
        assert "source" in merge_query
        assert "cross-entity-enrichment" in merge_query
        assert "created_at" in merge_query
        assert "datetime()" in merge_query

    def test_正常系_返り値がMERGEされたリレーション数(
        self,
        mock_driver: MagicMock,
        mock_anthropic_client: MagicMock,
    ) -> None:
        """run() の返り値が MERGE された非 SKIP リレーション数."""
        session = mock_driver.session.return_value.__enter__.return_value

        co_occurrence_records = [
            _make_co_occurrence_record(
                from_name="A",
                from_type="platform",
                from_id="ent-a",
                to_name="B",
                to_type="company",
                to_id="ent-b",
            ),
            _make_co_occurrence_record(
                from_name="C",
                from_type="platform",
                from_id="ent-c",
                to_name="D",
                to_type="company",
                to_id="ent-d",
            ),
        ]

        session.run.side_effect = [
            iter(co_occurrence_records),
            iter([]),
            iter([]),
        ]

        llm_response = [
            {"from_id": "ent-a", "to_id": "ent-b", "rel_detail": "ENABLES"},
            {"from_id": "ent-c", "to_id": "ent-d", "rel_detail": "SKIP"},
        ]
        mock_anthropic_client.messages.create.return_value = _make_mock_response(
            json.dumps(llm_response, ensure_ascii=False)
        )

        enricher = CrossEntityEnricher(mock_driver, mock_anthropic_client)
        result = enricher.run(cycle_count=3)

        # SKIP を除いた 1 件
        assert result == 1
