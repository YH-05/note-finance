"""creator_enrichment テスト共通フィクスチャ.

全 test_creator_enrichment テストで共有するフィクスチャを定義する。
mock クライアント、サンプルデータ、一時ディレクトリなど。
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from creator_enrichment.types import (
    CycleData,
    CycleReport,
    GapAnalysisResult,
    RawItem,
)


# ---------------------------------------------------------------------------
# Mock クライアント
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_neo4j_client() -> MagicMock:
    """Neo4j クライアントのモック.

    Returns
    -------
    MagicMock
        read_cypher / write_cypher メソッドを持つモック
    """
    client = MagicMock()
    client.read_cypher = MagicMock(return_value=[])
    client.write_cypher = MagicMock(return_value=None)
    return client


@pytest.fixture
def mock_anthropic_client() -> MagicMock:
    """Anthropic クライアントのモック.

    Returns
    -------
    MagicMock
        messages.create メソッドを持つモック
    """
    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = MagicMock(return_value=MagicMock())
    return client


# ---------------------------------------------------------------------------
# サンプルデータ
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_gap_result() -> GapAnalysisResult:
    """GapAnalysisResult のサンプルデータ.

    Returns
    -------
    GapAnalysisResult
        career ジャンルのギャップ分析結果サンプル
    """
    return GapAnalysisResult(
        genre="career",
        low_coverage_concepts=[
            "転職活動の始め方",
            "副業の税金対策",
            "リモートワーク戦略",
        ],
        existing_samples=["sample-fact-001", "sample-tip-001"],
    )


@pytest.fixture
def sample_raw_items() -> list[RawItem]:
    """RawItem リストのサンプルデータ.

    Returns
    -------
    list[RawItem]
        3件の検索結果サンプル
    """
    return [
        RawItem(
            url="https://example.com/article-1",
            title="転職市場の最新動向",
            content="2026年の転職市場は活発化しており...",
            source="tavily_search",
        ),
        RawItem(
            url="https://example.com/article-2",
            title="副業で月10万円を達成するまでの道のり",
            content="副業を始めて3ヶ月で...",
            source="webfetch",
        ),
        RawItem(
            url="https://reddit.com/r/japanlife/post-1",
            title="Career change tips in Japan",
            content="I recently changed careers and...",
            source="reddit",
        ),
    ]


@pytest.fixture
def sample_cycle_data() -> CycleData:
    """CycleData のサンプルデータ.

    Returns
    -------
    CycleData
        career ジャンルの抽出結果サンプル
    """
    return CycleData(
        genre="career",
        cycle_id="cycle-20260323-140000",
        sources=[
            {
                "url": "https://example.com/article-1",
                "title": "転職市場の最新動向",
            },
        ],
        facts=[
            {
                "text": "2026年の転職市場は前年比20%増加",
                "category": "statistics",
            },
        ],
        tips=[
            {
                "text": "転職活動では職務経歴書の具体的な数字が重要",
                "category": "strategy",
            },
        ],
        stories=[
            {
                "text": "IT企業から外資コンサルへ転職した事例",
                "outcome": "success",
            },
        ],
        entities=[
            {"name": "LinkedIn", "entity_type": "platform"},
        ],
        concepts=[
            {"name": "転職活動", "category": "Skill"},
        ],
        serves_as=[
            {"entity": "LinkedIn", "concept": "転職活動"},
        ],
        concept_relations=[
            {
                "from_concept": "転職活動",
                "to_concept": "副業戦略",
                "relation": "ENABLES",
            },
        ],
    )


@pytest.fixture
def sample_cycle_report() -> CycleReport:
    """CycleReport のサンプルデータ.

    Returns
    -------
    CycleReport
        成功したサイクルのレポートサンプル
    """
    return CycleReport(
        genre="career",
        search_results=12,
        contents_created={"Fact": 3, "Tip": 5, "Story": 2},
        entities_extracted=18,
        relations_detected=7,
        pipeline_status="success",
        cross_entity_added=4,
    )


# ---------------------------------------------------------------------------
# 一時ディレクトリ
# ---------------------------------------------------------------------------
@pytest.fixture
def tmp_log_dir(tmp_path: Path) -> Path:
    """セッションログ用の一時ディレクトリ.

    Parameters
    ----------
    tmp_path : Path
        pytest 提供の一時ディレクトリ

    Returns
    -------
    Path
        ログ出力用の一時ディレクトリパス
    """
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return log_dir
