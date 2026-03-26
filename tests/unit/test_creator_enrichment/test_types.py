"""creator_enrichment.types のテスト.

TypedDict フィールド定義・CycleError 継承・型アノテーションを検証する。
"""

from typing import get_type_hints

from creator_enrichment.types import (
    CycleData,
    CycleError,
    CycleReport,
    GapAnalysisResult,
    IngestResult,
    RawItem,
)


# ---------------------------------------------------------------------------
# RawItem
# ---------------------------------------------------------------------------
class TestRawItem:
    """RawItem TypedDict のテスト."""

    def test_正常系_必須フィールドが定義されている(self) -> None:
        hints = get_type_hints(RawItem)
        assert "url" in hints
        assert "title" in hints
        assert "content" in hints
        assert "source" in hints

    def test_正常系_全フィールドがstr型(self) -> None:
        hints = get_type_hints(RawItem)
        for field in ("url", "title", "content", "source"):
            assert hints[field] is str, f"{field} should be str"

    def test_正常系_任意メタデータフィールドが定義されている(self) -> None:
        hints = get_type_hints(RawItem)
        for field in (
            "published_at",
            "collected_at",
            "source_type",
            "authority_level",
            "language",
        ):
            assert field in hints
            assert hints[field] is str
            assert field in RawItem.__optional_keys__

    def test_正常系_インスタンス生成(self) -> None:
        item: RawItem = {
            "url": "https://example.com",
            "title": "Test Article",
            "content": "Some content",
            "source": "tavily_search",
            "published_at": "2026-03-26T10:00:00+09:00",
        }
        assert item["url"] == "https://example.com"
        assert item["source"] == "tavily_search"
        assert item["published_at"] == "2026-03-26T10:00:00+09:00"


# ---------------------------------------------------------------------------
# GapAnalysisResult
# ---------------------------------------------------------------------------
class TestGapAnalysisResult:
    """GapAnalysisResult TypedDict のテスト."""

    def test_正常系_必須フィールドが定義されている(self) -> None:
        hints = get_type_hints(GapAnalysisResult)
        assert "genre" in hints
        assert "low_coverage_concepts" in hints
        assert "existing_samples" in hints

    def test_正常系_フィールド型が正しい(self) -> None:
        hints = get_type_hints(GapAnalysisResult)
        assert hints["genre"] is str
        assert hints["low_coverage_concepts"] == list[str]
        assert hints["existing_samples"] == list[str]

    def test_正常系_インスタンス生成(self) -> None:
        result: GapAnalysisResult = {
            "genre": "career",
            "low_coverage_concepts": ["転職活動", "副業戦略"],
            "existing_samples": ["sample1", "sample2"],
        }
        assert result["genre"] == "career"
        assert len(result["low_coverage_concepts"]) == 2


# ---------------------------------------------------------------------------
# CycleData
# ---------------------------------------------------------------------------
class TestCycleData:
    """CycleData TypedDict のテスト."""

    def test_正常系_必須フィールドが定義されている(self) -> None:
        hints = get_type_hints(CycleData)
        expected_fields = {
            "genre",
            "cycle_id",
            "sources",
            "facts",
            "tips",
            "stories",
            "entities",
            "concepts",
            "serves_as",
            "concept_relations",
        }
        assert expected_fields.issubset(set(hints.keys()))

    def test_正常系_文字列フィールドの型(self) -> None:
        hints = get_type_hints(CycleData)
        assert hints["genre"] is str
        assert hints["cycle_id"] is str

    def test_正常系_リストフィールドの型(self) -> None:
        hints = get_type_hints(CycleData)
        list_fields = [
            "sources",
            "facts",
            "tips",
            "stories",
            "entities",
            "concepts",
            "serves_as",
            "concept_relations",
        ]
        for field in list_fields:
            origin = getattr(hints[field], "__origin__", None)
            assert origin is list, f"{field} should be list type"

    def test_正常系_インスタンス生成(self) -> None:
        data: CycleData = {
            "genre": "career",
            "cycle_id": "cycle-20260323-140000",
            "sources": [{"url": "https://example.com", "title": "Test"}],
            "facts": [{"text": "fact text", "category": "statistics"}],
            "tips": [],
            "stories": [],
            "entities": [{"name": "Instagram", "entity_type": "platform"}],
            "concepts": [],
            "serves_as": [],
            "concept_relations": [],
        }
        assert data["genre"] == "career"
        assert len(data["sources"]) == 1


# ---------------------------------------------------------------------------
# IngestResult
# ---------------------------------------------------------------------------
class TestIngestResult:
    """IngestResult TypedDict のテスト."""

    def test_正常系_必須フィールドが定義されている(self) -> None:
        hints = get_type_hints(IngestResult)
        assert "nodes_created" in hints
        assert "relations_created" in hints

    def test_正常系_フィールド型がint(self) -> None:
        hints = get_type_hints(IngestResult)
        assert hints["nodes_created"] is int
        assert hints["relations_created"] is int

    def test_正常系_インスタンス生成(self) -> None:
        result: IngestResult = {
            "nodes_created": 15,
            "relations_created": 8,
        }
        assert result["nodes_created"] == 15
        assert result["relations_created"] == 8


# ---------------------------------------------------------------------------
# CycleReport
# ---------------------------------------------------------------------------
class TestCycleReport:
    """CycleReport TypedDict のテスト."""

    def test_正常系_必須フィールドが定義されている(self) -> None:
        hints = get_type_hints(CycleReport)
        expected_fields = {
            "genre",
            "search_results",
            "contents_created",
            "entities_extracted",
            "relations_detected",
            "pipeline_status",
            "cross_entity_added",
        }
        assert expected_fields.issubset(set(hints.keys()))

    def test_正常系_フィールド型が正しい(self) -> None:
        hints = get_type_hints(CycleReport)
        assert hints["genre"] is str
        assert hints["search_results"] is int
        assert hints["contents_created"] == dict[str, int]
        assert hints["entities_extracted"] is int
        assert hints["relations_detected"] is int
        assert hints["cross_entity_added"] is int

    def test_正常系_インスタンス生成(self) -> None:
        report: CycleReport = {
            "genre": "beauty-romance",
            "search_results": 12,
            "contents_created": {"Fact": 3, "Tip": 5, "Story": 2},
            "entities_extracted": 18,
            "relations_detected": 7,
            "pipeline_status": "success",
            "cross_entity_added": 4,
        }
        assert report["pipeline_status"] == "success"
        assert report["contents_created"]["Fact"] == 3


# ---------------------------------------------------------------------------
# CycleError
# ---------------------------------------------------------------------------
class TestCycleError:
    """CycleError 例外クラスのテスト."""

    def test_正常系_CycleErrorはExceptionを継承(self) -> None:
        err = CycleError(cycle_num=1, cause=ValueError("test"))
        assert isinstance(err, Exception)

    def test_正常系_cycle_numを保持(self) -> None:
        err = CycleError(cycle_num=3, cause=RuntimeError("timeout"))
        assert err.cycle_num == 3

    def test_正常系_causeを保持(self) -> None:
        original = ValueError("invalid data")
        err = CycleError(cycle_num=2, cause=original)
        assert err.cause is original

    def test_正常系_メッセージにcycle_numとcauseが含まれる(self) -> None:
        err = CycleError(cycle_num=5, cause=IOError("connection refused"))
        assert "5" in str(err)
        assert "connection refused" in str(err)

    def test_正常系_raiseとcatchが可能(self) -> None:
        try:
            raise CycleError(cycle_num=1, cause=ValueError("test"))
        except CycleError as e:
            assert e.cycle_num == 1
        except Exception as exc:
            raise AssertionError("CycleError should be caught as CycleError") from exc

    def test_正常系_Exceptionとしてもcatch可能(self) -> None:
        try:
            raise CycleError(cycle_num=1, cause=ValueError("test"))
        except Exception as e:
            assert isinstance(e, CycleError)


# ---------------------------------------------------------------------------
# パッケージインポート
# ---------------------------------------------------------------------------
class TestPackageImport:
    """パッケージレベルのインポートテスト."""

    def test_正常系_パッケージからバージョンをインポート(self) -> None:
        from creator_enrichment import __version__

        assert __version__ == "0.1.0"

    def test_正常系_パッケージから型をインポート(self) -> None:
        from creator_enrichment import (
            CycleData,
            CycleError,
            CycleReport,
            GapAnalysisResult,
            IngestResult,
            RawItem,
        )

        # All types are importable (no assertion needed beyond successful import)
        assert CycleData is not None
        assert CycleError is not None
        assert CycleReport is not None
        assert GapAnalysisResult is not None
        assert IngestResult is not None
        assert RawItem is not None
