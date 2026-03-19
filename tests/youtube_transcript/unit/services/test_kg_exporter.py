"""Tests for KgExporter: ナレッジグラフエクスポーター.

KgExporter はトランスクリプトデータを save-to-graph スキル向けに整形し、
research-neo4j（port 7688）投入用の graph-queue JSON を生成する。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from youtube_transcript.services.kg_exporter import KgExporter
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
        title="Test Video Title",
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
# KgExporter.export_video
# ---------------------------------------------------------------------------


class TestKgExporterExportVideo:
    """KgExporter.export_video() のテスト."""

    def test_正常系_graph_queue_JSONを生成できる(self, tmp_path: Path) -> None:
        """export_video が有効な graph-queue JSON ファイルを生成する."""
        video = _make_video("vid001")
        transcript = _make_transcript("vid001")

        exporter = KgExporter(data_dir=tmp_path)
        output_path = exporter.export_video(
            video=video,
            transcript=transcript,
        )

        assert output_path.exists()
        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert data["schema_version"] == "2.0"
        assert "sources" in data
        assert len(data["sources"]) >= 1

    def test_正常系_sourceにvideo_idとtitleが含まれる(self, tmp_path: Path) -> None:
        """export_video の sources に video タイトルと URL が含まれる."""
        video = _make_video("vid001")
        transcript = _make_transcript("vid001")

        exporter = KgExporter(data_dir=tmp_path)
        output_path = exporter.export_video(
            video=video,
            transcript=transcript,
        )

        data = json.loads(output_path.read_text(encoding="utf-8"))
        source = data["sources"][0]
        assert source["title"] == video.title
        assert "vid001" in source.get("url", source.get("source_id", ""))

    def test_正常系_chunkが含まれる(self, tmp_path: Path) -> None:
        """export_video が transcript テキストを chunk として含む."""
        video = _make_video("vid001")
        transcript = _make_transcript("vid001")

        exporter = KgExporter(data_dir=tmp_path)
        output_path = exporter.export_video(
            video=video,
            transcript=transcript,
        )

        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert "chunks" in data
        assert len(data["chunks"]) >= 1

    def test_正常系_command_sourceにyoutube_transcriptが含まれる(
        self, tmp_path: Path
    ) -> None:
        """export_video の command_source は youtube_transcript を示す."""
        video = _make_video("vid001")
        transcript = _make_transcript("vid001")

        exporter = KgExporter(data_dir=tmp_path)
        output_path = exporter.export_video(
            video=video,
            transcript=transcript,
        )

        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert "youtube" in data["command_source"].lower()

    def test_正常系_ファイル名がgq_プレフィックスを持つ(self, tmp_path: Path) -> None:
        """export_video の出力ファイル名は gq- で始まる."""
        video = _make_video("vid001")
        transcript = _make_transcript("vid001")

        exporter = KgExporter(data_dir=tmp_path)
        output_path = exporter.export_video(
            video=video,
            transcript=transcript,
        )

        assert output_path.name.startswith("gq-")


# ---------------------------------------------------------------------------
# KgExporter.export_channel
# ---------------------------------------------------------------------------


class TestKgExporterExportChannel:
    """KgExporter.export_channel() のテスト."""

    def test_正常系_チャンネルの全SUCCESS動画を処理する(self, tmp_path: Path) -> None:
        """export_channel が SUCCESS 動画を全て export_video で処理する."""
        videos = [
            _make_video("vid001", "UC_test123", TranscriptStatus.SUCCESS),
            _make_video("vid002", "UC_test123", TranscriptStatus.SUCCESS),
        ]
        transcripts = {
            "vid001": _make_transcript("vid001"),
            "vid002": _make_transcript("vid002"),
        }

        mock_storage = MagicMock()
        mock_storage.load_channels.return_value = [_make_channel("UC_test123")]
        mock_storage.load_videos.return_value = videos
        mock_storage.load_transcript.side_effect = lambda ch_id, vid_id: (
            transcripts.get(vid_id)
        )

        with patch(
            "youtube_transcript.services.kg_exporter.JSONStorage",
            return_value=mock_storage,
        ):
            exporter = KgExporter(data_dir=tmp_path)
            output_paths = exporter.export_channel(channel_id="UC_test123")

        assert len(output_paths) == 2
        for p in output_paths:
            assert p.exists()

    def test_正常系_FAILED動画はスキップされる(self, tmp_path: Path) -> None:
        """export_channel は FAILED / UNAVAILABLE 動画をスキップする."""
        videos = [
            _make_video("vid001", "UC_test123", TranscriptStatus.SUCCESS),
            _make_video("vid002", "UC_test123", TranscriptStatus.FAILED),
        ]
        transcripts = {
            "vid001": _make_transcript("vid001"),
        }

        mock_storage = MagicMock()
        mock_storage.load_channels.return_value = [_make_channel("UC_test123")]
        mock_storage.load_videos.return_value = videos
        mock_storage.load_transcript.side_effect = lambda ch_id, vid_id: (
            transcripts.get(vid_id)
        )

        with patch(
            "youtube_transcript.services.kg_exporter.JSONStorage",
            return_value=mock_storage,
        ):
            exporter = KgExporter(data_dir=tmp_path)
            output_paths = exporter.export_channel(channel_id="UC_test123")

        assert len(output_paths) == 1

    def test_異常系_チャンネルが存在しない場合エラー(self, tmp_path: Path) -> None:
        """export_channel はチャンネルが存在しない場合に例外を送出する."""
        mock_storage = MagicMock()
        mock_storage.load_channels.return_value = []

        with patch(
            "youtube_transcript.services.kg_exporter.JSONStorage",
            return_value=mock_storage,
        ):
            exporter = KgExporter(data_dir=tmp_path)
            from youtube_transcript.exceptions import ChannelNotFoundError

            with pytest.raises(ChannelNotFoundError):
                exporter.export_channel(channel_id="UC_nonexistent")

    def test_正常系_video_id指定でフィルタできる(self, tmp_path: Path) -> None:
        """export_channel に video_id を指定すると1動画のみ処理される."""
        videos = [
            _make_video("vid001", "UC_test123", TranscriptStatus.SUCCESS),
            _make_video("vid002", "UC_test123", TranscriptStatus.SUCCESS),
        ]
        transcripts = {
            "vid001": _make_transcript("vid001"),
            "vid002": _make_transcript("vid002"),
        }

        mock_storage = MagicMock()
        mock_storage.load_channels.return_value = [_make_channel("UC_test123")]
        mock_storage.load_videos.return_value = videos
        mock_storage.load_transcript.side_effect = lambda ch_id, vid_id: (
            transcripts.get(vid_id)
        )

        with patch(
            "youtube_transcript.services.kg_exporter.JSONStorage",
            return_value=mock_storage,
        ):
            exporter = KgExporter(data_dir=tmp_path)
            output_paths = exporter.export_channel(
                channel_id="UC_test123",
                video_id="vid001",
            )

        assert len(output_paths) == 1
