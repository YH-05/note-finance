"""Unit tests for youtube_transcript DiffDetector."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from youtube_transcript.core.diff_detector import DiffDetector
from youtube_transcript.types import TranscriptStatus, Video


def make_video(video_id: str, channel_id: str = "UC_test") -> Video:
    """Helper to create a minimal Video instance for testing."""
    return Video(
        video_id=video_id,
        channel_id=channel_id,
        title=f"Video {video_id}",
        published="2026-03-18T00:00:00+00:00",
        description="",
        transcript_status=TranscriptStatus.PENDING,
        transcript_language=None,
        fetched_at=None,
    )


class TestDiffDetectorInit:
    """Test DiffDetector initialization."""

    def test_init(self) -> None:
        """Test that DiffDetector can be instantiated."""
        detector = DiffDetector()
        assert detector is not None


class TestDetectNew:
    """Test detect_new method."""

    def test_正常系_existing空で全件が新着になる(self) -> None:
        """All fetched videos are new when existing list is empty."""
        detector = DiffDetector()
        fetched = [make_video("aaa1111"), make_video("bbb2222")]
        result = detector.detect_new(existing=[], fetched=fetched)
        assert len(result) == 2
        assert result == fetched

    def test_正常系_全件既存なら新着なし(self) -> None:
        """No new videos when all fetched videos already exist."""
        detector = DiffDetector()
        existing = [make_video("aaa1111"), make_video("bbb2222")]
        fetched = [make_video("aaa1111"), make_video("bbb2222")]
        result = detector.detect_new(existing=existing, fetched=fetched)
        assert result == []

    def test_正常系_一部既存で新着のみ返す(self) -> None:
        """Only new videos returned when some already exist."""
        detector = DiffDetector()
        existing = [make_video("aaa1111")]
        video_new = make_video("bbb2222")
        fetched = [make_video("aaa1111"), video_new]
        result = detector.detect_new(existing=existing, fetched=fetched)
        assert len(result) == 1
        assert result[0].video_id == "bbb2222"

    def test_正常系_fetched空で新着なし(self) -> None:
        """Empty result when fetched list is empty."""
        detector = DiffDetector()
        existing = [make_video("aaa1111")]
        result = detector.detect_new(existing=existing, fetched=[])
        assert result == []

    def test_正常系_両方空で新着なし(self) -> None:
        """Empty result when both lists are empty."""
        detector = DiffDetector()
        result = detector.detect_new(existing=[], fetched=[])
        assert result == []

    def test_正常系_video_idで重複判定(self) -> None:
        """video_id is used as the deduplication key, not title or other fields."""
        detector = DiffDetector()
        existing = [
            Video(
                video_id="aaa1111",
                channel_id="UC_old",
                title="Old Title",
                published="2026-01-01T00:00:00+00:00",
                description="old",
                transcript_status=TranscriptStatus.SUCCESS,
                transcript_language="ja",
                fetched_at="2026-01-01T01:00:00+00:00",
            )
        ]
        fetched = [
            Video(
                video_id="aaa1111",  # Same video_id
                channel_id="UC_new",
                title="New Title",
                published="2026-03-18T00:00:00+00:00",
                description="new",
                transcript_status=TranscriptStatus.PENDING,
                transcript_language=None,
                fetched_at=None,
            )
        ]
        result = detector.detect_new(existing=existing, fetched=fetched)
        # Should be excluded because video_id matches
        assert result == []

    def test_正常系_返却順序はfetchedの順序を保持(self) -> None:
        """Order of new items matches the order in fetched list."""
        detector = DiffDetector()
        ids = ["vid001", "vid002", "vid003", "vid004", "vid005"]
        fetched = [make_video(vid_id) for vid_id in ids]
        existing = [make_video("vid002"), make_video("vid004")]
        result = detector.detect_new(existing=existing, fetched=fetched)
        assert [v.video_id for v in result] == ["vid001", "vid003", "vid005"]

    def test_正常系_チャンネル違いでも同じvideo_idは重複扱い(self) -> None:
        """Same video_id from different channel is treated as duplicate."""
        detector = DiffDetector()
        existing = [make_video("aaa1111", channel_id="UC_chan1")]
        fetched = [make_video("aaa1111", channel_id="UC_chan2")]
        result = detector.detect_new(existing=existing, fetched=fetched)
        assert result == []


class TestDetectNewLogging:
    """Test that detect_new executes without errors (logging sanity)."""

    def test_detect_new_ログなしでもエラーなし(self) -> None:
        """detect_new executes without errors regardless of logging config."""
        detector = DiffDetector()
        result = detector.detect_new(existing=[], fetched=[make_video("aaa1111")])
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Hypothesis property-based tests
# ---------------------------------------------------------------------------

VIDEO_ID_STRATEGY = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-",
    min_size=1,
    max_size=11,
)


def video_strategy() -> st.SearchStrategy[Video]:
    """Strategy to generate Video instances with unique-ish video_ids."""
    return VIDEO_ID_STRATEGY.map(make_video)


class TestDetectNewProperties:
    """Hypothesis property-based tests for DiffDetector.detect_new."""

    @given(fetched=st.lists(VIDEO_ID_STRATEGY, min_size=0, max_size=20))
    def test_プロパティ_existing空なら全件新着(self, fetched: list[str]) -> None:
        """When existing is empty, all fetched videos are new."""
        detector = DiffDetector()
        fetched_videos = [make_video(vid_id) for vid_id in fetched]
        result = detector.detect_new(existing=[], fetched=fetched_videos)
        assert len(result) == len(fetched_videos)

    @given(
        items=st.lists(
            VIDEO_ID_STRATEGY.filter(lambda x: len(x) >= 1), min_size=0, max_size=20
        )
    )
    def test_プロパティ_same_listを渡すと新着なし(self, items: list[str]) -> None:
        """When existing and fetched are the same list, no new videos."""
        detector = DiffDetector()
        videos = [make_video(vid_id) for vid_id in items]
        result = detector.detect_new(existing=videos, fetched=videos)
        assert result == []

    @given(
        existing_ids=st.lists(VIDEO_ID_STRATEGY, min_size=0, max_size=20),
        new_ids=st.lists(VIDEO_ID_STRATEGY, min_size=0, max_size=20),
    )
    def test_プロパティ_新着数はfetchedのうち既存にないものの数(
        self,
        existing_ids: list[str],
        new_ids: list[str],
    ) -> None:
        """Count of new videos equals fetched videos whose video_id is not in existing."""
        detector = DiffDetector()
        existing = [make_video(vid_id) for vid_id in existing_ids]
        # fetched contains all existing + all new
        all_fetched = existing + [make_video(vid_id) for vid_id in new_ids]
        result = detector.detect_new(existing=existing, fetched=all_fetched)

        existing_id_set = {v.video_id for v in existing}
        truly_new = [v for v in all_fetched if v.video_id not in existing_id_set]
        assert len(result) == len(truly_new)

    @given(
        all_ids=st.lists(
            VIDEO_ID_STRATEGY,
            min_size=0,
            max_size=30,
            unique=True,
        )
    )
    def test_プロパティ_結果の全video_idはexistingに含まれない(
        self, all_ids: list[str]
    ) -> None:
        """All video_ids in result must not be in existing."""
        detector = DiffDetector()
        split = len(all_ids) // 2
        existing_ids = all_ids[:split]
        fetched_ids = all_ids  # fetched includes both existing and new

        existing = [make_video(vid_id) for vid_id in existing_ids]
        fetched = [make_video(vid_id) for vid_id in fetched_ids]
        result = detector.detect_new(existing=existing, fetched=fetched)

        existing_id_set = {v.video_id for v in existing}
        for video in result:
            assert video.video_id not in existing_id_set

    @given(
        fetched_ids=st.lists(VIDEO_ID_STRATEGY, min_size=0, max_size=20),
    )
    def test_プロパティ_fetchedが空でないとき結果はfetchedの部分集合(
        self, fetched_ids: list[str]
    ) -> None:
        """Result is always a subset of fetched (by video_id)."""
        detector = DiffDetector()
        fetched = [make_video(vid_id) for vid_id in fetched_ids]
        result = detector.detect_new(existing=[], fetched=fetched)
        fetched_id_set = {v.video_id for v in fetched}
        for video in result:
            assert video.video_id in fetched_id_set
