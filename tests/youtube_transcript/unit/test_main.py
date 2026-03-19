"""Unit tests for YouTube Transcript CLI (yt-transcript command).

TDD Red phase: tests covering acceptance criteria from Issue #167.

Acceptance criteria:
- 全コマンドが機能する
- --json フラグで JSON 出力に切り替わる
- stats で quota 使用量が表示される
- `test_main.py` の全テストが通過する
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from youtube_transcript.types import (
    Channel,
    CollectResult,
    QuotaUsage,
    TranscriptEntry,
    TranscriptResult,
    TranscriptStatus,
    Video,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_channel(
    channel_id: str = "UCabc123",
    title: str = "Test Channel",
    uploads_playlist_id: str = "UUabc123",
    language_priority: list[str] | None = None,
    enabled: bool = True,
    last_fetched: str | None = None,
    video_count: int = 0,
) -> Channel:
    """Build a Channel instance for testing."""
    if language_priority is None:
        language_priority = ["ja", "en"]
    return Channel(
        channel_id=channel_id,
        title=title,
        uploads_playlist_id=uploads_playlist_id,
        language_priority=language_priority,
        enabled=enabled,
        created_at="2026-03-18T00:00:00+00:00",
        last_fetched=last_fetched,
        video_count=video_count,
    )


def make_video(
    video_id: str = "vid001",
    channel_id: str = "UCabc123",
    title: str = "Test Video",
    published: str = "2026-03-18T00:00:00+00:00",
    transcript_status: TranscriptStatus = TranscriptStatus.SUCCESS,
    transcript_language: str | None = "ja",
    fetched_at: str | None = "2026-03-18T01:00:00+00:00",
) -> Video:
    """Build a Video instance for testing."""
    return Video(
        video_id=video_id,
        channel_id=channel_id,
        title=title,
        published=published,
        description="",
        transcript_status=transcript_status,
        transcript_language=transcript_language,
        fetched_at=fetched_at,
    )


def make_transcript_result(
    video_id: str = "vid001",
    language: str = "ja",
) -> TranscriptResult:
    """Build a TranscriptResult instance for testing."""
    return TranscriptResult(
        video_id=video_id,
        language=language,
        entries=[
            TranscriptEntry(start=0.0, duration=3.0, text="Hello"),
            TranscriptEntry(start=3.0, duration=2.0, text="World"),
        ],
        fetched_at="2026-03-18T01:00:00+00:00",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner() -> CliRunner:
    """Click test runner."""
    return CliRunner()


@pytest.fixture()
def tmp_data_dir(tmp_path: Path) -> Path:
    """Temporary data directory."""
    return tmp_path / "youtube_transcript"


# ---------------------------------------------------------------------------
# Import CLI
# ---------------------------------------------------------------------------


@pytest.fixture()
def cli():
    """Import and return the CLI entry point."""
    from youtube_transcript.cli.main import cli as _cli

    return _cli


# ---------------------------------------------------------------------------
# channel add
# ---------------------------------------------------------------------------


class TestChannelAdd:
    """Tests for `yt-transcript channel add`."""

    def test_正常系_チャンネル追加成功(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """channel add が正常に動作し、テキスト出力を返す."""
        channel = make_channel()
        with patch(
            "youtube_transcript.cli.channel_cmd.ChannelManager"
        ) as mock_manager_cls:
            mock_manager = mock_manager_cls.return_value
            mock_manager.add.return_value = channel

            result = runner.invoke(
                cli,
                [
                    "--data-dir",
                    str(tmp_data_dir),
                    "channel",
                    "add",
                    "--channel-id",
                    "UCabc123",
                    "--title",
                    "Test Channel",
                ],
            )

        assert result.exit_code == 0
        assert "UCabc123" in result.output or "Test Channel" in result.output

    def test_正常系_チャンネル追加_json出力(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """channel add --json がJSON形式で出力する."""
        channel = make_channel()
        with patch(
            "youtube_transcript.cli.channel_cmd.ChannelManager"
        ) as mock_manager_cls:
            mock_manager = mock_manager_cls.return_value
            mock_manager.add.return_value = channel

            result = runner.invoke(
                cli,
                [
                    "--data-dir",
                    str(tmp_data_dir),
                    "channel",
                    "add",
                    "--channel-id",
                    "UCabc123",
                    "--title",
                    "Test Channel",
                    "--json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["channel_id"] == "UCabc123"
        assert data["title"] == "Test Channel"

    def test_異常系_既存チャンネルでエラー(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """channel add で既存チャンネルの場合はエラーになる."""
        from youtube_transcript.exceptions import ChannelAlreadyExistsError

        with patch(
            "youtube_transcript.cli.channel_cmd.ChannelManager"
        ) as mock_manager_cls:
            mock_manager = mock_manager_cls.return_value
            mock_manager.add.side_effect = ChannelAlreadyExistsError(
                "Channel 'UCabc123' already exists"
            )

            result = runner.invoke(
                cli,
                [
                    "--data-dir",
                    str(tmp_data_dir),
                    "channel",
                    "add",
                    "--channel-id",
                    "UCabc123",
                    "--title",
                    "Test Channel",
                ],
            )

        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# channel list
# ---------------------------------------------------------------------------


class TestChannelList:
    """Tests for `yt-transcript channel list`."""

    def test_正常系_チャンネル一覧表示(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """channel list がテキスト形式で一覧表示する."""
        channels = [make_channel(), make_channel(channel_id="UCdef456", title="Chan2")]
        with patch(
            "youtube_transcript.cli.channel_cmd.ChannelManager"
        ) as mock_manager_cls:
            mock_manager = mock_manager_cls.return_value
            mock_manager.list.return_value = channels

            result = runner.invoke(
                cli,
                ["--data-dir", str(tmp_data_dir), "channel", "list"],
            )

        assert result.exit_code == 0
        assert "UCabc123" in result.output or "Test Channel" in result.output

    def test_正常系_チャンネル一覧_json出力(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """channel list --json がJSON配列を出力する."""
        channels = [make_channel()]
        with patch(
            "youtube_transcript.cli.channel_cmd.ChannelManager"
        ) as mock_manager_cls:
            mock_manager = mock_manager_cls.return_value
            mock_manager.list.return_value = channels

            result = runner.invoke(
                cli,
                ["--data-dir", str(tmp_data_dir), "channel", "list", "--json"],
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["channel_id"] == "UCabc123"

    def test_正常系_チャンネルなし(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """channel list でチャンネルが0件の場合に適切なメッセージを表示する."""
        with patch(
            "youtube_transcript.cli.channel_cmd.ChannelManager"
        ) as mock_manager_cls:
            mock_manager = mock_manager_cls.return_value
            mock_manager.list.return_value = []

            result = runner.invoke(
                cli,
                ["--data-dir", str(tmp_data_dir), "channel", "list"],
            )

        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# channel remove
# ---------------------------------------------------------------------------


class TestChannelRemove:
    """Tests for `yt-transcript channel remove`."""

    def test_正常系_チャンネル削除成功(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """channel remove が正常に動作する."""
        with patch(
            "youtube_transcript.cli.channel_cmd.ChannelManager"
        ) as mock_manager_cls:
            mock_manager = mock_manager_cls.return_value
            mock_manager.remove.return_value = None

            result = runner.invoke(
                cli,
                [
                    "--data-dir",
                    str(tmp_data_dir),
                    "channel",
                    "remove",
                    "UCabc123",
                ],
            )

        assert result.exit_code == 0
        mock_manager.remove.assert_called_once_with("UCabc123")

    def test_正常系_チャンネル削除_json出力(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """channel remove --json がJSON出力する."""
        with patch(
            "youtube_transcript.cli.channel_cmd.ChannelManager"
        ) as mock_manager_cls:
            mock_manager = mock_manager_cls.return_value
            mock_manager.remove.return_value = None

            result = runner.invoke(
                cli,
                [
                    "--data-dir",
                    str(tmp_data_dir),
                    "channel",
                    "remove",
                    "UCabc123",
                    "--json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["channel_id"] == "UCabc123"

    def test_異常系_存在しないチャンネル削除(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """channel remove で存在しないチャンネルはエラーになる."""
        from youtube_transcript.exceptions import ChannelNotFoundError

        with patch(
            "youtube_transcript.cli.channel_cmd.ChannelManager"
        ) as mock_manager_cls:
            mock_manager = mock_manager_cls.return_value
            mock_manager.remove.side_effect = ChannelNotFoundError(
                "Channel 'UCxxx' not found"
            )

            result = runner.invoke(
                cli,
                [
                    "--data-dir",
                    str(tmp_data_dir),
                    "channel",
                    "remove",
                    "UCxxx",
                ],
            )

        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# collect
# ---------------------------------------------------------------------------


class TestCollect:
    """Tests for `yt-transcript collect`."""

    def test_正常系_単一チャンネル収集(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """collect --channel-id で単一チャンネルの収集が動作する."""
        collect_result = CollectResult(
            total=5, success=4, unavailable=1, failed=0, skipped=0
        )
        with patch("youtube_transcript.cli.collect_cmd._build_collector") as mock_build:
            mock_collector = MagicMock()
            mock_build.return_value = mock_collector
            mock_collector.collect.return_value = collect_result

            result = runner.invoke(
                cli,
                [
                    "--data-dir",
                    str(tmp_data_dir),
                    "collect",
                    "--channel-id",
                    "UCabc123",
                ],
            )

        assert result.exit_code == 0

    def test_正常系_全チャンネル収集(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """collect --all で全チャンネルの収集が動作する."""
        collect_results = [
            CollectResult(total=3, success=2, unavailable=1, failed=0, skipped=0)
        ]
        with patch("youtube_transcript.cli.collect_cmd._build_collector") as mock_build:
            mock_collector = MagicMock()
            mock_build.return_value = mock_collector
            mock_collector.collect_all.return_value = collect_results

            result = runner.invoke(
                cli,
                ["--data-dir", str(tmp_data_dir), "collect", "--all"],
            )

        assert result.exit_code == 0

    def test_正常系_収集結果_json出力(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """collect --channel-id --json がJSON出力する."""
        collect_result = CollectResult(
            total=5, success=4, unavailable=1, failed=0, skipped=0
        )
        with patch("youtube_transcript.cli.collect_cmd._build_collector") as mock_build:
            mock_collector = MagicMock()
            mock_build.return_value = mock_collector
            mock_collector.collect.return_value = collect_result

            result = runner.invoke(
                cli,
                [
                    "--data-dir",
                    str(tmp_data_dir),
                    "collect",
                    "--channel-id",
                    "UCabc123",
                    "--json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total"] == 5
        assert data["success"] == 4

    def test_異常系_channel_idもallも指定なし(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """collect で --channel-id も --all も指定しない場合はエラーになる."""
        result = runner.invoke(
            cli,
            ["--data-dir", str(tmp_data_dir), "collect"],
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# videos
# ---------------------------------------------------------------------------


class TestVideos:
    """Tests for `yt-transcript videos <channel_id>`."""

    def test_正常系_動画一覧表示(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """videos <channel_id> が動画一覧をテキスト表示する."""
        videos = [make_video(), make_video(video_id="vid002", title="Video 2")]
        with patch("youtube_transcript.cli.media_cmd.JSONStorage") as mock_storage_cls:
            mock_storage = mock_storage_cls.return_value
            mock_storage.load_videos.return_value = videos

            result = runner.invoke(
                cli,
                ["--data-dir", str(tmp_data_dir), "videos", "UCabc123"],
            )

        assert result.exit_code == 0
        assert "vid001" in result.output or "Test Video" in result.output

    def test_正常系_動画一覧_json出力(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """videos <channel_id> --json がJSON配列を出力する."""
        videos = [make_video()]
        with patch("youtube_transcript.cli.media_cmd.JSONStorage") as mock_storage_cls:
            mock_storage = mock_storage_cls.return_value
            mock_storage.load_videos.return_value = videos

            result = runner.invoke(
                cli,
                [
                    "--data-dir",
                    str(tmp_data_dir),
                    "videos",
                    "UCabc123",
                    "--json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["video_id"] == "vid001"

    def test_正常系_動画なし(self, runner: CliRunner, tmp_data_dir: Path, cli) -> None:
        """videos で動画が0件の場合に適切なメッセージを表示する."""
        with patch("youtube_transcript.cli.media_cmd.JSONStorage") as mock_storage_cls:
            mock_storage = mock_storage_cls.return_value
            mock_storage.load_videos.return_value = []

            result = runner.invoke(
                cli,
                ["--data-dir", str(tmp_data_dir), "videos", "UCabc123"],
            )

        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# transcript
# ---------------------------------------------------------------------------


class TestTranscript:
    """Tests for `yt-transcript transcript <video_id>`."""

    def _setup_transcript_mock(
        self,
        mock_storage: MagicMock,
        transcript: TranscriptResult,
    ) -> None:
        """Set up storage mock for transcript lookup flow.

        The CLI looks up channel_id by iterating channels then videos,
        so we must set up load_channels and load_videos as well.
        """
        channel = make_channel()
        video = make_video()
        mock_storage.load_channels.return_value = [channel]
        mock_storage.load_videos.return_value = [video]
        mock_storage.load_transcript.return_value = transcript

    def test_正常系_トランスクリプト_plain出力(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """transcript <video_id> --plain がプレーンテキストで出力する."""
        transcript = make_transcript_result()
        with patch("youtube_transcript.cli.media_cmd.JSONStorage") as mock_storage_cls:
            mock_storage = mock_storage_cls.return_value
            self._setup_transcript_mock(mock_storage, transcript)

            result = runner.invoke(
                cli,
                [
                    "--data-dir",
                    str(tmp_data_dir),
                    "transcript",
                    "vid001",
                    "--plain",
                ],
            )

        assert result.exit_code == 0
        assert "Hello" in result.output
        assert "World" in result.output

    def test_正常系_トランスクリプト_json出力(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """transcript <video_id> --json がJSON形式で出力する."""
        transcript = make_transcript_result()
        with patch("youtube_transcript.cli.media_cmd.JSONStorage") as mock_storage_cls:
            mock_storage = mock_storage_cls.return_value
            self._setup_transcript_mock(mock_storage, transcript)

            result = runner.invoke(
                cli,
                [
                    "--data-dir",
                    str(tmp_data_dir),
                    "transcript",
                    "vid001",
                    "--json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["video_id"] == "vid001"
        assert data["language"] == "ja"
        assert len(data["entries"]) == 2

    def test_正常系_トランスクリプト_デフォルト出力(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """transcript <video_id> デフォルトでテキスト出力する."""
        transcript = make_transcript_result()
        with patch("youtube_transcript.cli.media_cmd.JSONStorage") as mock_storage_cls:
            mock_storage = mock_storage_cls.return_value
            self._setup_transcript_mock(mock_storage, transcript)

            result = runner.invoke(
                cli,
                ["--data-dir", str(tmp_data_dir), "transcript", "vid001"],
            )

        assert result.exit_code == 0

    def test_異常系_トランスクリプト不在(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """transcript で対象動画がない場合はエラーになる."""
        with patch("youtube_transcript.cli.media_cmd.JSONStorage") as mock_storage_cls:
            mock_storage = mock_storage_cls.return_value
            # No matching channel/video, so load_channels returns empty list
            mock_storage.load_channels.return_value = []
            mock_storage.load_transcript.return_value = None

            result = runner.invoke(
                cli,
                ["--data-dir", str(tmp_data_dir), "transcript", "vid_missing"],
            )

        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------


class TestStats:
    """Tests for `yt-transcript stats`."""

    def test_正常系_stats_quota使用量表示(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """stats でquota使用量が表示される（受け入れ条件）."""
        channels = [
            make_channel(channel_id="UCabc123", title="Chan1", video_count=10),
            make_channel(channel_id="UCdef456", title="Chan2", enabled=False),
        ]
        quota = QuotaUsage(date="2026-03-18", units_used=1500, budget=9000)

        with (
            patch(
                "youtube_transcript.cli.media_cmd.ChannelManager"
            ) as mock_manager_cls,
            patch("youtube_transcript.cli.media_cmd.QuotaTracker") as mock_tracker_cls,
        ):
            mock_manager = mock_manager_cls.return_value
            mock_manager.list.return_value = channels
            mock_tracker = mock_tracker_cls.return_value
            mock_tracker.today_usage.return_value = quota.units_used
            mock_tracker.budget = quota.budget
            mock_tracker.remaining.return_value = quota.budget - quota.units_used

            result = runner.invoke(
                cli,
                ["--data-dir", str(tmp_data_dir), "stats"],
            )

        assert result.exit_code == 0
        # quota使用量が表示されること
        assert (
            "1500" in result.output
            or "quota" in result.output.lower()
            or "Quota" in result.output
        )

    def test_正常系_stats_json出力(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """stats --json がquota情報を含むJSONを出力する."""
        channels = [make_channel()]
        with (
            patch(
                "youtube_transcript.cli.media_cmd.ChannelManager"
            ) as mock_manager_cls,
            patch("youtube_transcript.cli.media_cmd.QuotaTracker") as mock_tracker_cls,
        ):
            mock_manager = mock_manager_cls.return_value
            mock_manager.list.return_value = channels
            mock_tracker = mock_tracker_cls.return_value
            mock_tracker.today_usage.return_value = 500
            mock_tracker.budget = 9000
            mock_tracker.remaining.return_value = 8500

            result = runner.invoke(
                cli,
                ["--data-dir", str(tmp_data_dir), "stats", "--json"],
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "quota" in data
        assert data["quota"]["units_used"] == 500
        assert data["quota"]["budget"] == 9000
        assert data["total_channels"] == 1

    def test_正常系_stats_チャンネルなし(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """stats でチャンネルが0件でも動作する."""
        with (
            patch(
                "youtube_transcript.cli.media_cmd.ChannelManager"
            ) as mock_manager_cls,
            patch("youtube_transcript.cli.media_cmd.QuotaTracker") as mock_tracker_cls,
        ):
            mock_manager = mock_manager_cls.return_value
            mock_manager.list.return_value = []
            mock_tracker = mock_tracker_cls.return_value
            mock_tracker.today_usage.return_value = 0
            mock_tracker.budget = 9000
            mock_tracker.remaining.return_value = 9000

            result = runner.invoke(
                cli,
                ["--data-dir", str(tmp_data_dir), "stats"],
            )

        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


class TestSearch:
    """Tests for `yt-transcript search <query>`."""

    def test_正常系_検索結果をテキスト表示する(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """search <query> が検索結果をテキスト表示する."""
        from youtube_transcript.core.search_engine import SearchResult

        search_results = [
            SearchResult(
                video_id="vid001",
                channel_id="UCabc123",
                matched_text="利上げについて説明します",
                timestamp=5.0,
            )
        ]
        with patch("youtube_transcript.cli.media_cmd.SearchEngine") as mock_engine_cls:
            mock_engine = mock_engine_cls.return_value
            mock_engine.search.return_value = search_results

            result = runner.invoke(
                cli,
                ["--data-dir", str(tmp_data_dir), "search", "利上げ"],
            )

        assert result.exit_code == 0
        assert "vid001" in result.output or "利上げ" in result.output

    def test_正常系_検索結果をJSON出力する(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """search <query> --json がJSON配列を出力する."""
        from youtube_transcript.core.search_engine import SearchResult

        search_results = [
            SearchResult(
                video_id="vid001",
                channel_id="UCabc123",
                matched_text="利上げについて",
                timestamp=5.0,
            )
        ]
        with patch("youtube_transcript.cli.media_cmd.SearchEngine") as mock_engine_cls:
            mock_engine = mock_engine_cls.return_value
            mock_engine.search.return_value = search_results

            result = runner.invoke(
                cli,
                ["--data-dir", str(tmp_data_dir), "search", "利上げ", "--json"],
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["video_id"] == "vid001"
        assert data[0]["channel_id"] == "UCabc123"
        assert data[0]["matched_text"] == "利上げについて"
        assert data[0]["timestamp"] == 5.0

    def test_正常系_channel_idフィルタを渡す(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """search <query> --channel-id でチャンネルを絞り込む."""
        from youtube_transcript.core.search_engine import SearchResult

        search_results = [
            SearchResult(
                video_id="vid001",
                channel_id="UCabc123",
                matched_text="テスト",
                timestamp=0.0,
            )
        ]
        with patch("youtube_transcript.cli.media_cmd.SearchEngine") as mock_engine_cls:
            mock_engine = mock_engine_cls.return_value
            mock_engine.search.return_value = search_results

            result = runner.invoke(
                cli,
                [
                    "--data-dir",
                    str(tmp_data_dir),
                    "search",
                    "テスト",
                    "--channel-id",
                    "UCabc123",
                ],
            )

        assert result.exit_code == 0
        mock_engine.search.assert_called_once_with("テスト", channel_ids=["UCabc123"])

    def test_正常系_検索結果なしで適切なメッセージ(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """search <query> で結果なしの場合に適切に動作する."""
        with patch("youtube_transcript.cli.media_cmd.SearchEngine") as mock_engine_cls:
            mock_engine = mock_engine_cls.return_value
            mock_engine.search.return_value = []

            result = runner.invoke(
                cli,
                ["--data-dir", str(tmp_data_dir), "search", "存在しないキーワード"],
            )

        assert result.exit_code == 0

    def test_正常系_channel_idなしで全チャンネル検索(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """search <query> で --channel-id 未指定の場合は channel_ids=None で呼ばれる."""
        with patch("youtube_transcript.cli.media_cmd.SearchEngine") as mock_engine_cls:
            mock_engine = mock_engine_cls.return_value
            mock_engine.search.return_value = []

            result = runner.invoke(
                cli,
                ["--data-dir", str(tmp_data_dir), "search", "テスト"],
            )

        assert result.exit_code == 0
        mock_engine.search.assert_called_once_with("テスト", channel_ids=None)


# ---------------------------------------------------------------------------
# collect --retry-failed
# ---------------------------------------------------------------------------


class TestCollectRetryFailed:
    """Tests for `yt-transcript collect --retry-failed`."""

    def test_正常系_retry_failed単一チャンネル(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """collect --retry-failed --channel-id でチャンネルの FAILED を再取得する."""
        collect_result = CollectResult(
            total=2, success=1, unavailable=0, failed=0, skipped=1
        )
        with patch(
            "youtube_transcript.cli.collect_cmd._build_retry_service"
        ) as mock_build:
            mock_service = MagicMock()
            mock_build.return_value = mock_service
            mock_service.retry_failed.return_value = collect_result

            result = runner.invoke(
                cli,
                [
                    "--data-dir",
                    str(tmp_data_dir),
                    "collect",
                    "--retry-failed",
                    "--channel-id",
                    "UCabc123",
                ],
            )

        assert result.exit_code == 0
        mock_service.retry_failed.assert_called_once_with("UCabc123")

    def test_正常系_retry_failed全チャンネル(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """collect --retry-failed --all で全チャンネルの FAILED を再取得する."""
        collect_results = [
            CollectResult(total=1, success=1, unavailable=0, failed=0, skipped=0)
        ]
        with patch(
            "youtube_transcript.cli.collect_cmd._build_retry_service"
        ) as mock_build:
            mock_service = MagicMock()
            mock_build.return_value = mock_service
            mock_service.retry_all_failed.return_value = collect_results

            result = runner.invoke(
                cli,
                [
                    "--data-dir",
                    str(tmp_data_dir),
                    "collect",
                    "--retry-failed",
                    "--all",
                ],
            )

        assert result.exit_code == 0
        mock_service.retry_all_failed.assert_called_once()

    def test_正常系_retry_failed結果をJSON出力する(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """collect --retry-failed --channel-id --json がJSON出力する."""
        collect_result = CollectResult(
            total=3, success=2, unavailable=0, failed=1, skipped=0
        )
        with patch(
            "youtube_transcript.cli.collect_cmd._build_retry_service"
        ) as mock_build:
            mock_service = MagicMock()
            mock_build.return_value = mock_service
            mock_service.retry_failed.return_value = collect_result

            result = runner.invoke(
                cli,
                [
                    "--data-dir",
                    str(tmp_data_dir),
                    "collect",
                    "--retry-failed",
                    "--channel-id",
                    "UCabc123",
                    "--json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total"] == 3
        assert data["success"] == 2
        assert data["failed"] == 1

    def test_異常系_retry_failed_channel_idもallも指定なし(
        self, runner: CliRunner, tmp_data_dir: Path, cli
    ) -> None:
        """collect --retry-failed で --channel-id も --all も未指定はエラーになる."""
        result = runner.invoke(
            cli,
            ["--data-dir", str(tmp_data_dir), "collect", "--retry-failed"],
        )
        assert result.exit_code != 0
