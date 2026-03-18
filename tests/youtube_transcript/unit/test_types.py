"""Unit tests for youtube_transcript.types module."""

from datetime import datetime, timezone

import pytest

from youtube_transcript.types import (
    Channel,
    CollectResult,
    QuotaUsage,
    TranscriptEntry,
    TranscriptResult,
    TranscriptStatus,
    Video,
)


class TestTranscriptStatus:
    def test_正常系_4値が定義されている(self) -> None:
        assert TranscriptStatus.PENDING == "pending"
        assert TranscriptStatus.SUCCESS == "success"
        assert TranscriptStatus.UNAVAILABLE == "unavailable"
        assert TranscriptStatus.FAILED == "failed"

    def test_正常系_文字列として比較できる(self) -> None:
        assert TranscriptStatus.PENDING == "pending"
        assert isinstance(TranscriptStatus.SUCCESS, str)

    def test_正常系_4つの値のみ存在する(self) -> None:
        values = [s.value for s in TranscriptStatus]
        assert len(values) == 4


class TestChannel:
    def test_正常系_全フィールドを持つChannelが作成できる(self) -> None:
        now = datetime.now(tz=timezone.utc).isoformat()
        channel = Channel(
            channel_id="UC_test_123",
            title="Test Channel",
            uploads_playlist_id="UU_test_123",
            language_priority=["ja", "en"],
            enabled=True,
            created_at=now,
            last_fetched=None,
            video_count=0,
        )
        assert channel.channel_id == "UC_test_123"
        assert channel.title == "Test Channel"
        assert channel.uploads_playlist_id == "UU_test_123"
        assert channel.language_priority == ["ja", "en"]
        assert channel.enabled is True
        assert channel.last_fetched is None
        assert channel.video_count == 0

    def test_正常系_last_fetchedにISO文字列を設定できる(self) -> None:
        now = datetime.now(tz=timezone.utc).isoformat()
        channel = Channel(
            channel_id="UC_abc",
            title="Chan",
            uploads_playlist_id="UU_abc",
            language_priority=["en"],
            enabled=True,
            created_at=now,
            last_fetched=now,
            video_count=5,
        )
        assert channel.last_fetched == now


class TestVideo:
    def test_正常系_全フィールドを持つVideoが作成できる(self) -> None:
        now = datetime.now(tz=timezone.utc).isoformat()
        video = Video(
            video_id="abc123",
            channel_id="UC_test",
            title="Test Video",
            published=now,
            description="A test video",
            transcript_status=TranscriptStatus.PENDING,
            transcript_language=None,
            fetched_at=None,
        )
        assert video.video_id == "abc123"
        assert video.channel_id == "UC_test"
        assert video.transcript_status == TranscriptStatus.PENDING
        assert video.transcript_language is None
        assert video.fetched_at is None

    def test_正常系_transcript_statusにSUCCESSを設定できる(self) -> None:
        now = datetime.now(tz=timezone.utc).isoformat()
        video = Video(
            video_id="xyz",
            channel_id="UC_xyz",
            title="Video",
            published=now,
            description="",
            transcript_status=TranscriptStatus.SUCCESS,
            transcript_language="ja",
            fetched_at=now,
        )
        assert video.transcript_status == TranscriptStatus.SUCCESS
        assert video.transcript_language == "ja"


class TestTranscriptEntry:
    def test_正常系_TranscriptEntryが作成できる(self) -> None:
        entry = TranscriptEntry(start=0.0, duration=5.0, text="Hello world")
        assert entry.start == 0.0
        assert entry.duration == 5.0
        assert entry.text == "Hello world"

    def test_エッジケース_start_durationが0の場合(self) -> None:
        entry = TranscriptEntry(start=0.0, duration=0.0, text="")
        assert entry.start == 0.0
        assert entry.duration == 0.0
        assert entry.text == ""


class TestTranscriptResult:
    def _make_entries(self) -> list[TranscriptEntry]:
        return [
            TranscriptEntry(start=0.0, duration=3.0, text="Hello"),
            TranscriptEntry(start=3.0, duration=2.0, text="world"),
            TranscriptEntry(start=5.0, duration=4.0, text="this is a test"),
        ]

    def test_正常系_TranscriptResultが作成できる(self) -> None:
        now = datetime.now(tz=timezone.utc).isoformat()
        entries = self._make_entries()
        result = TranscriptResult(
            video_id="abc123",
            language="ja",
            entries=entries,
            fetched_at=now,
        )
        assert result.video_id == "abc123"
        assert result.language == "ja"
        assert len(result.entries) == 3

    def test_正常系_to_plain_textが全テキストを結合して返す(self) -> None:
        now = datetime.now(tz=timezone.utc).isoformat()
        entries = self._make_entries()
        result = TranscriptResult(
            video_id="abc123",
            language="en",
            entries=entries,
            fetched_at=now,
        )
        plain = result.to_plain_text()
        assert "Hello" in plain
        assert "world" in plain
        assert "this is a test" in plain

    def test_エッジケース_空のentriesのto_plain_textは空文字(self) -> None:
        now = datetime.now(tz=timezone.utc).isoformat()
        result = TranscriptResult(
            video_id="abc",
            language="en",
            entries=[],
            fetched_at=now,
        )
        plain = result.to_plain_text()
        assert plain == ""

    def test_正常系_to_plain_textが改行で区切られる(self) -> None:
        now = datetime.now(tz=timezone.utc).isoformat()
        entries = [
            TranscriptEntry(start=0.0, duration=1.0, text="Line one"),
            TranscriptEntry(start=1.0, duration=1.0, text="Line two"),
        ]
        result = TranscriptResult(
            video_id="v1",
            language="en",
            entries=entries,
            fetched_at=now,
        )
        plain = result.to_plain_text()
        assert "Line one" in plain
        assert "Line two" in plain


class TestCollectResult:
    def test_正常系_CollectResultが作成できる(self) -> None:
        result = CollectResult(
            total=10,
            success=7,
            unavailable=2,
            failed=1,
            skipped=0,
        )
        assert result.total == 10
        assert result.success == 7
        assert result.unavailable == 2
        assert result.failed == 1
        assert result.skipped == 0

    def test_エッジケース_全ゼロのCollectResult(self) -> None:
        result = CollectResult(total=0, success=0, unavailable=0, failed=0, skipped=0)
        assert result.total == 0


class TestQuotaUsage:
    def test_正常系_QuotaUsageが作成できる(self) -> None:
        usage = QuotaUsage(date="2026-03-18", units_used=1000, budget=10000)
        assert usage.date == "2026-03-18"
        assert usage.units_used == 1000
        assert usage.budget == 10000

    def test_エッジケース_units_usedがbudgetを超えている場合も作成できる(self) -> None:
        usage = QuotaUsage(date="2026-03-18", units_used=15000, budget=10000)
        assert usage.units_used > usage.budget
