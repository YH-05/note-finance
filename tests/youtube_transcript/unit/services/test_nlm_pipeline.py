"""Tests for NlmPipeline: NotebookLM パイプライン.

NlmPipeline はトランスクリプトを plain text にエクスポートし、
NotebookLM のノートブックにソースとして追加する。
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from youtube_transcript.services.nlm_pipeline import NlmPipeline
from youtube_transcript.types import (
    Channel,
    TranscriptEntry,
    TranscriptResult,
    TranscriptStatus,
    Video,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_channel(channel_id: str = "UC_test123") -> Channel:
    return Channel(
        channel_id=channel_id,
        title="Test Channel",
        uploads_playlist_id="UU_test123",
        language_priority=["ja", "en"],
        enabled=True,
        created_at="2026-03-18T00:00:00+00:00",
        last_fetched=None,
        video_count=0,
    )


def _make_video(
    video_id: str = "vid001",
    channel_id: str = "UC_test123",
    status: TranscriptStatus = TranscriptStatus.SUCCESS,
) -> Video:
    return Video(
        video_id=video_id,
        channel_id=channel_id,
        title="Test Video",
        published="2026-03-18T00:00:00+00:00",
        description="Test description",
        transcript_status=status,
        transcript_language="ja",
        fetched_at="2026-03-18T01:00:00+00:00",
    )


def _make_transcript(video_id: str = "vid001") -> TranscriptResult:
    return TranscriptResult(
        video_id=video_id,
        language="ja",
        entries=[
            TranscriptEntry(start=0.0, duration=3.0, text="こんにちは"),
            TranscriptEntry(start=3.0, duration=2.0, text="世界"),
        ],
        fetched_at="2026-03-18T01:00:00+00:00",
    )


# ---------------------------------------------------------------------------
# NlmPipeline.add_to_notebook
# ---------------------------------------------------------------------------


class TestNlmPipelineAddToNotebook:
    """NlmPipeline.add_to_notebook() のテスト."""

    @pytest.mark.asyncio
    async def test_正常系_単一動画をノートブックに追加できる(
        self, tmp_path: Path
    ) -> None:
        """add_to_notebook が成功したら SourceInfo を返す."""
        transcript = _make_transcript("vid001")
        mock_source_info = MagicMock()
        mock_source_info.source_id = "src-001"
        mock_source_info.title = "Test Video"

        mock_service = AsyncMock()
        mock_service.add_text_source = AsyncMock(return_value=mock_source_info)

        with patch(
            "youtube_transcript.services.nlm_pipeline.NlmPipeline._build_source_service",
            return_value=mock_service,
        ):
            pipeline = NlmPipeline(data_dir=tmp_path)
            result = await pipeline.add_to_notebook(
                notebook_id="nb-abc123",
                transcript=transcript,
                title="Test Video",
            )

        assert result is not None
        assert result.source_id == "src-001"

    @pytest.mark.asyncio
    async def test_正常系_plain_text変換を経由する(self, tmp_path: Path) -> None:
        """add_to_notebook が TranscriptResult.to_plain_text() を使う."""
        transcript = _make_transcript("vid001")
        mock_source_info = MagicMock()
        mock_service = AsyncMock()
        captured_content: list[str] = []

        async def _capture(*args: object, **kwargs: object) -> MagicMock:
            # content が kwargs に含まれることを確認
            content_arg = kwargs.get("content") or (args[1] if len(args) > 1 else "")
            captured_content.append(str(content_arg))
            return mock_source_info

        mock_service.add_text_source = _capture

        with patch(
            "youtube_transcript.services.nlm_pipeline.NlmPipeline._build_source_service",
            return_value=mock_service,
        ):
            pipeline = NlmPipeline(data_dir=tmp_path)
            await pipeline.add_to_notebook(
                notebook_id="nb-abc123",
                transcript=transcript,
                title="Test Video",
            )

        assert len(captured_content) == 1
        assert "こんにちは" in captured_content[0]
        assert "世界" in captured_content[0]

    @pytest.mark.asyncio
    async def test_異常系_空のエントリでも動作する(self, tmp_path: Path) -> None:
        """空のトランスクリプトでも add_to_notebook は呼べる."""
        transcript = TranscriptResult(
            video_id="vid_empty",
            language="ja",
            entries=[],
            fetched_at="2026-03-18T00:00:00+00:00",
        )
        mock_source_info = MagicMock()
        mock_source_info.source_id = "src-empty"
        mock_service = AsyncMock()
        mock_service.add_text_source = AsyncMock(return_value=mock_source_info)

        with patch(
            "youtube_transcript.services.nlm_pipeline.NlmPipeline._build_source_service",
            return_value=mock_service,
        ):
            pipeline = NlmPipeline(data_dir=tmp_path)
            result = await pipeline.add_to_notebook(
                notebook_id="nb-abc123",
                transcript=transcript,
                title="Empty Video",
            )

        assert result is not None


# ---------------------------------------------------------------------------
# NlmPipeline.bulk_add_channel
# ---------------------------------------------------------------------------


class TestNlmPipelineBulkAddChannel:
    """NlmPipeline.bulk_add_channel() のテスト."""

    @pytest.mark.asyncio
    async def test_正常系_チャンネル全動画を一括追加できる(
        self, tmp_path: Path
    ) -> None:
        """bulk_add_channel が SUCCESS 動画のトランスクリプトを全て追加する."""
        videos = [
            _make_video("vid001", "UC_test123", TranscriptStatus.SUCCESS),
            _make_video("vid002", "UC_test123", TranscriptStatus.SUCCESS),
        ]
        transcripts = {
            "vid001": _make_transcript("vid001"),
            "vid002": _make_transcript("vid002"),
        }

        mock_source_info = MagicMock()
        mock_source_info.source_id = "src-001"
        mock_service = AsyncMock()
        mock_service.add_text_source = AsyncMock(return_value=mock_source_info)

        mock_storage = MagicMock()
        mock_storage.load_channels.return_value = [_make_channel("UC_test123")]
        mock_storage.load_videos.return_value = videos
        mock_storage.load_transcript.side_effect = lambda ch_id, vid_id: (
            transcripts.get(vid_id)
        )

        with (
            patch(
                "youtube_transcript.services.nlm_pipeline.JSONStorage",
                return_value=mock_storage,
            ),
            patch(
                "youtube_transcript.services.nlm_pipeline.NlmPipeline._build_source_service",
                return_value=mock_service,
            ),
        ):
            pipeline = NlmPipeline(data_dir=tmp_path)
            results = await pipeline.bulk_add_channel(
                notebook_id="nb-abc123",
                channel_id="UC_test123",
            )

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_正常系_SUCCESSのみ処理しFAILEDはスキップする(
        self, tmp_path: Path
    ) -> None:
        """bulk_add_channel が FAILED / UNAVAILABLE 動画をスキップする."""
        videos = [
            _make_video("vid001", "UC_test123", TranscriptStatus.SUCCESS),
            _make_video("vid002", "UC_test123", TranscriptStatus.FAILED),
            _make_video("vid003", "UC_test123", TranscriptStatus.UNAVAILABLE),
        ]
        transcripts = {
            "vid001": _make_transcript("vid001"),
        }

        mock_source_info = MagicMock()
        mock_source_info.source_id = "src-001"
        mock_service = AsyncMock()
        mock_service.add_text_source = AsyncMock(return_value=mock_source_info)

        mock_storage = MagicMock()
        mock_storage.load_channels.return_value = [_make_channel("UC_test123")]
        mock_storage.load_videos.return_value = videos
        mock_storage.load_transcript.side_effect = lambda ch_id, vid_id: (
            transcripts.get(vid_id)
        )

        with (
            patch(
                "youtube_transcript.services.nlm_pipeline.JSONStorage",
                return_value=mock_storage,
            ),
            patch(
                "youtube_transcript.services.nlm_pipeline.NlmPipeline._build_source_service",
                return_value=mock_service,
            ),
        ):
            pipeline = NlmPipeline(data_dir=tmp_path)
            results = await pipeline.bulk_add_channel(
                notebook_id="nb-abc123",
                channel_id="UC_test123",
            )

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_異常系_チャンネルが存在しない場合エラー(
        self, tmp_path: Path
    ) -> None:
        """bulk_add_channel はチャンネルが存在しない場合に例外を送出する."""
        mock_storage = MagicMock()
        mock_storage.load_channels.return_value = []

        with patch(
            "youtube_transcript.services.nlm_pipeline.JSONStorage",
            return_value=mock_storage,
        ):
            pipeline = NlmPipeline(data_dir=tmp_path)
            from youtube_transcript.exceptions import ChannelNotFoundError

            with pytest.raises(ChannelNotFoundError):
                await pipeline.bulk_add_channel(
                    notebook_id="nb-abc123",
                    channel_id="UC_nonexistent",
                )
