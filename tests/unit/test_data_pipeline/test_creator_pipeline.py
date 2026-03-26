"""data_pipeline.pipeline の creator 向け変換テスト."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from data_pipeline.collectors.base import CollectedItem
from data_pipeline.pipeline import PipelineResult, _run_creator_layers


class TestCreatorPipeline:
    """creator target の RawItem 変換を検証する."""

    @patch("data_pipeline.pipeline._ingest_neo4j")
    @patch("scripts.emit_creator_queue_v2.map_creator_enrichment_v2")
    @patch("creator_enrichment.phases.extract.ContentExtractor")
    @patch("creator_enrichment.llm_client.SdkLLMClient")
    def test_正常系_CollectedItemのpublished_at等をRawItemへ引き継ぐ(
        self,
        _mock_sdk_llm_cls: MagicMock,
        mock_extractor_cls: MagicMock,
        mock_map_fn: MagicMock,
        mock_ingest_neo4j: MagicMock,
    ) -> None:
        """CollectedItem メタデータが creator RawItem に保持される."""
        published_at = datetime(2026, 3, 26, 1, 23, 45, tzinfo=timezone.utc)
        collected_at = datetime(2026, 3, 26, 2, 34, 56, tzinfo=timezone.utc)
        item = CollectedItem(
            source_id="note-com-test",
            url="https://example.com/article-1",
            title="Test Article",
            raw_text="Body text",
            published_at=published_at,
            collected_at=collected_at,
            collection_method="scraping",
            language="ja",
            metadata={"source_type": "web", "authority_level": "official"},
        )
        result = PipelineResult(target="creator")

        mock_extractor = mock_extractor_cls.return_value
        mock_extractor.extract_batch.return_value = {
            "genre": "career",
            "cycle_id": "cycle-test-001",
            "sources": [
                {
                    "url": item.url,
                    "title": item.title,
                    "published_at": published_at.isoformat(),
                }
            ],
            "facts": [],
            "tips": [],
            "stories": [],
            "entities": [],
            "concepts": [],
            "serves_as": [],
            "concept_relations": [],
        }
        mock_map_fn.return_value = {
            "queue_id": "cq-test-001",
            "sources": [],
            "facts": [],
            "tips": [],
            "stories": [],
            "entities": [],
            "concepts": [],
            "concept_categories": [],
            "domains": [],
            "genres": [],
            "aliases": [],
            "relations": {},
        }

        _run_creator_layers(
            [item],
            result,
            genre="career",
            link_entities=False,
            ingest_neo4j=False,
            dry_run=True,
        )

        mock_extractor.extract_batch.assert_called_once()
        raw_items = mock_extractor.extract_batch.call_args.kwargs["items"]
        assert len(raw_items) == 1
        raw_item = raw_items[0]
        assert raw_item["published_at"] == published_at.isoformat()
        assert raw_item["collected_at"] == collected_at.isoformat()
        assert raw_item["source_type"] == "web"
        assert raw_item["authority_level"] == "official"
        assert raw_item["language"] == "ja"
        assert raw_item["source"] == "scraping"
        mock_ingest_neo4j.assert_called_once()
