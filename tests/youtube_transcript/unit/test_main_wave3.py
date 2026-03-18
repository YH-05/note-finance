"""Unit tests for yt-transcript CLI Wave3 commands.

Tests for Issue #172:
- yt-transcript nlm add <notebook_id> [--channel-id | --video-id]
- yt-transcript kg export [--channel-id | --video-id]
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

if TYPE_CHECKING:
    from pathlib import Path

import pytest
from click.testing import CliRunner

from youtube_transcript.cli.main import cli

# ---------------------------------------------------------------------------
# CLI: nlm add
# ---------------------------------------------------------------------------


class TestNlmAddCommand:
    """yt-transcript nlm add のテスト."""

    def test_正常系_channel_idで全動画を追加できる(self, tmp_path: Path) -> None:
        """nlm add --channel-id でチャンネル全動画が追加される."""
        mock_pipeline = MagicMock()
        mock_pipeline.bulk_add_channel = AsyncMock(
            return_value=[MagicMock(), MagicMock()]
        )

        runner = CliRunner()
        with patch(
            "youtube_transcript.cli.main._build_nlm_pipeline",
            return_value=mock_pipeline,
        ):
            result = runner.invoke(
                cli,
                [
                    "--data-dir",
                    str(tmp_path),
                    "nlm",
                    "add",
                    "nb-abc123",
                    "--channel-id",
                    "UC_test123",
                ],
            )

        assert result.exit_code == 0

    def test_正常系_video_idで単一動画を追加できる(self, tmp_path: Path) -> None:
        """nlm add --video-id で単一動画が追加される."""
        mock_source = MagicMock()
        mock_source.source_id = "src-001"
        mock_pipeline = MagicMock()
        mock_pipeline.add_to_notebook = AsyncMock(return_value=mock_source)

        mock_storage = MagicMock()
        from youtube_transcript.types import (
            Channel,
            TranscriptEntry,
            TranscriptResult,
            TranscriptStatus,
            Video,
        )

        mock_storage.load_channels.return_value = [
            Channel(
                channel_id="UC_test123",
                title="Test",
                uploads_playlist_id="UU_test",
                language_priority=["ja"],
                enabled=True,
                created_at="2026-03-18T00:00:00+00:00",
                last_fetched=None,
                video_count=1,
            )
        ]
        mock_storage.load_videos.return_value = [
            Video(
                video_id="vid001",
                channel_id="UC_test123",
                title="Test Video",
                published="2026-03-18T00:00:00+00:00",
                description="",
                transcript_status=TranscriptStatus.SUCCESS,
                transcript_language="ja",
                fetched_at="2026-03-18T01:00:00+00:00",
            )
        ]
        mock_storage.load_transcript.return_value = TranscriptResult(
            video_id="vid001",
            language="ja",
            entries=[TranscriptEntry(start=0.0, duration=3.0, text="Hello")],
            fetched_at="2026-03-18T01:00:00+00:00",
        )

        runner = CliRunner()
        with (
            patch(
                "youtube_transcript.cli.main._build_nlm_pipeline",
                return_value=mock_pipeline,
            ),
            patch(
                "youtube_transcript.cli.main.JSONStorage",
                return_value=mock_storage,
            ),
        ):
            result = runner.invoke(
                cli,
                [
                    "--data-dir",
                    str(tmp_path),
                    "nlm",
                    "add",
                    "nb-abc123",
                    "--video-id",
                    "vid001",
                ],
            )

        assert result.exit_code == 0

    def test_異常系_channel_idもvideo_idも指定なしでエラー(
        self, tmp_path: Path
    ) -> None:
        """nlm add に --channel-id も --video-id も指定しない場合はエラー."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--data-dir",
                str(tmp_path),
                "nlm",
                "add",
                "nb-abc123",
            ],
        )

        assert result.exit_code != 0

    def test_正常系_json出力モードで動作する(self, tmp_path: Path) -> None:
        """nlm add --json で JSON 出力に切り替わる."""
        mock_pipeline = MagicMock()
        mock_pipeline.bulk_add_channel = AsyncMock(return_value=[])

        runner = CliRunner()
        with patch(
            "youtube_transcript.cli.main._build_nlm_pipeline",
            return_value=mock_pipeline,
        ):
            result = runner.invoke(
                cli,
                [
                    "--data-dir",
                    str(tmp_path),
                    "nlm",
                    "add",
                    "nb-abc123",
                    "--channel-id",
                    "UC_test123",
                    "--json",
                ],
            )

        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# CLI: kg export
# ---------------------------------------------------------------------------


class TestKgExportCommand:
    """yt-transcript kg export のテスト."""

    def test_正常系_channel_idで全動画をエクスポートできる(
        self, tmp_path: Path
    ) -> None:
        """kg export --channel-id でチャンネル全動画がエクスポートされる."""
        mock_exporter = MagicMock()
        mock_path = tmp_path / "gq-test.json"
        mock_path.touch()
        mock_exporter.export_channel.return_value = [mock_path]

        runner = CliRunner()
        with patch(
            "youtube_transcript.cli.main._build_kg_exporter",
            return_value=mock_exporter,
        ):
            result = runner.invoke(
                cli,
                [
                    "--data-dir",
                    str(tmp_path),
                    "kg",
                    "export",
                    "--channel-id",
                    "UC_test123",
                ],
            )

        assert result.exit_code == 0
        mock_exporter.export_channel.assert_called_once_with(
            channel_id="UC_test123",
            video_id=None,
        )

    def test_正常系_video_idで単一動画をエクスポートできる(
        self, tmp_path: Path
    ) -> None:
        """kg export --channel-id --video-id で単一動画がエクスポートされる."""
        mock_exporter = MagicMock()
        mock_path = tmp_path / "gq-test.json"
        mock_path.touch()
        mock_exporter.export_channel.return_value = [mock_path]

        runner = CliRunner()
        with patch(
            "youtube_transcript.cli.main._build_kg_exporter",
            return_value=mock_exporter,
        ):
            result = runner.invoke(
                cli,
                [
                    "--data-dir",
                    str(tmp_path),
                    "kg",
                    "export",
                    "--channel-id",
                    "UC_test123",
                    "--video-id",
                    "vid001",
                ],
            )

        assert result.exit_code == 0
        mock_exporter.export_channel.assert_called_once_with(
            channel_id="UC_test123",
            video_id="vid001",
        )

    def test_異常系_channel_idもvideo_idも指定なしでエラー(
        self, tmp_path: Path
    ) -> None:
        """kg export に --channel-id も指定しない場合はエラー."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--data-dir",
                str(tmp_path),
                "kg",
                "export",
            ],
        )

        assert result.exit_code != 0

    def test_正常系_json出力モードで動作する(self, tmp_path: Path) -> None:
        """kg export --json で JSON 出力に切り替わる."""
        mock_exporter = MagicMock()
        mock_path = tmp_path / "gq-test.json"
        mock_path.touch()
        mock_exporter.export_channel.return_value = [mock_path]

        runner = CliRunner()
        with patch(
            "youtube_transcript.cli.main._build_kg_exporter",
            return_value=mock_exporter,
        ):
            result = runner.invoke(
                cli,
                [
                    "--data-dir",
                    str(tmp_path),
                    "kg",
                    "export",
                    "--channel-id",
                    "UC_test123",
                    "--json",
                ],
            )

        assert result.exit_code == 0
