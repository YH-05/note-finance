"""Unit tests for QuotaTracker."""

from pathlib import Path
from unittest.mock import patch

import pytest

from youtube_transcript.exceptions import QuotaExceededError
from youtube_transcript.storage.quota_tracker import QuotaTracker

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tracker(tmp_path: Path) -> QuotaTracker:
    """Return a QuotaTracker backed by a temp directory with 9000 unit budget."""
    return QuotaTracker(tmp_path)


@pytest.fixture()
def small_budget_tracker(tmp_path: Path) -> QuotaTracker:
    """Return a QuotaTracker with a small budget for overflow testing."""
    return QuotaTracker(tmp_path, budget=100)


# ---------------------------------------------------------------------------
# Phase 1: TDD Red Tests
# ---------------------------------------------------------------------------


class TestQuotaTrackerInit:
    """Tests for QuotaTracker initialization."""

    def test_正常系_デフォルト予算で初期化できる(self, tmp_path: Path) -> None:
        tracker = QuotaTracker(tmp_path)
        assert tracker.budget == 9000

    def test_正常系_カスタム予算で初期化できる(self, tmp_path: Path) -> None:
        tracker = QuotaTracker(tmp_path, budget=5000)
        assert tracker.budget == 5000

    def test_正常系_環境変数YT_QUOTA_BUDGETで予算を上書きできる(
        self, tmp_path: Path
    ) -> None:
        with patch.dict("os.environ", {"YT_QUOTA_BUDGET": "7500"}):
            tracker = QuotaTracker(tmp_path)
        assert tracker.budget == 7500

    def test_エッジケース_新規ストレージで残りquotaはbudget全量(
        self, tracker: QuotaTracker
    ) -> None:
        assert tracker.remaining() == 9000

    def test_エッジケース_新規ストレージで今日の使用量は0(
        self, tracker: QuotaTracker
    ) -> None:
        assert tracker.today_usage() == 0


class TestQuotaTrackerConsume:
    """Tests for QuotaTracker.consume()."""

    def test_正常系_consume後に使用量が増加する(self, tracker: QuotaTracker) -> None:
        tracker.consume(100)
        assert tracker.today_usage() == 100

    def test_正常系_複数回consumeで累積される(self, tracker: QuotaTracker) -> None:
        tracker.consume(100)
        tracker.consume(200)
        assert tracker.today_usage() == 300

    def test_正常系_consume後にremainingが減少する(self, tracker: QuotaTracker) -> None:
        tracker.consume(500)
        assert tracker.remaining() == 8500

    def test_正常系_ちょうどbudget消費時はエラーなし(
        self, small_budget_tracker: QuotaTracker
    ) -> None:
        small_budget_tracker.consume(100)
        assert small_budget_tracker.today_usage() == 100
        assert small_budget_tracker.remaining() == 0

    def test_異常系_超過時にQuotaExceededErrorを発生させる(
        self, small_budget_tracker: QuotaTracker
    ) -> None:
        with pytest.raises(QuotaExceededError):
            small_budget_tracker.consume(101)

    def test_異常系_超過時にquotaが変更されない(
        self, small_budget_tracker: QuotaTracker
    ) -> None:
        """consume() が QuotaExceededError を発生させた場合、使用量は変わらない."""
        small_budget_tracker.consume(50)
        with pytest.raises(QuotaExceededError):
            small_budget_tracker.consume(60)
        assert small_budget_tracker.today_usage() == 50

    def test_異常系_累積消費が超過する場合にQuotaExceededError(
        self, small_budget_tracker: QuotaTracker
    ) -> None:
        small_budget_tracker.consume(80)
        with pytest.raises(QuotaExceededError):
            small_budget_tracker.consume(30)

    def test_エッジケース_0単位のconsumeは正常終了(self, tracker: QuotaTracker) -> None:
        tracker.consume(0)
        assert tracker.today_usage() == 0

    def test_異常系_負の単位でValueError(self, tracker: QuotaTracker) -> None:
        with pytest.raises(ValueError, match="units must be non-negative"):
            tracker.consume(-1)


class TestQuotaTrackerRemaining:
    """Tests for QuotaTracker.remaining()."""

    def test_正常系_初期状態でbudget全量が残る(self, tracker: QuotaTracker) -> None:
        assert tracker.remaining() == 9000

    def test_正常系_消費後に正確な残量を返す(self, tracker: QuotaTracker) -> None:
        tracker.consume(1000)
        tracker.consume(2000)
        assert tracker.remaining() == 6000

    def test_エッジケース_使い切った場合に0を返す(
        self, small_budget_tracker: QuotaTracker
    ) -> None:
        small_budget_tracker.consume(100)
        assert small_budget_tracker.remaining() == 0


class TestQuotaTrackerPersistence:
    """Tests for QuotaTracker data persistence across instances."""

    def test_正常系_消費量がファイルに永続化される(self, tmp_path: Path) -> None:
        tracker1 = QuotaTracker(tmp_path)
        tracker1.consume(300)

        tracker2 = QuotaTracker(tmp_path)
        assert tracker2.today_usage() == 300

    def test_正常系_別インスタンスでも正確なremainingを返す(
        self, tmp_path: Path
    ) -> None:
        tracker1 = QuotaTracker(tmp_path)
        tracker1.consume(1000)

        tracker2 = QuotaTracker(tmp_path)
        assert tracker2.remaining() == 8000


class TestQuotaTrackerResetIfNewDay:
    """Tests for QuotaTracker.reset_if_new_day()."""

    def test_正常系_同日はリセットされない(self, tracker: QuotaTracker) -> None:
        tracker.consume(500)
        tracker.reset_if_new_day()
        assert tracker.today_usage() == 500

    def test_正常系_日付変わりで自動リセットされる(self, tmp_path: Path) -> None:
        tracker = QuotaTracker(tmp_path)
        tracker.consume(500)
        assert tracker.today_usage() == 500

        # Simulate next day by patching the date in the stored quota
        import json

        quota_file = tmp_path / "quota_usage.json"
        data = json.loads(quota_file.read_text())
        data["date"] = "2000-01-01"  # old date
        quota_file.write_text(json.dumps(data))

        tracker2 = QuotaTracker(tmp_path)
        tracker2.reset_if_new_day()
        assert tracker2.today_usage() == 0

    def test_正常系_リセット後にconsumeできる(self, tmp_path: Path) -> None:
        import json

        tracker = QuotaTracker(tmp_path)
        tracker.consume(500)

        quota_file = tmp_path / "quota_usage.json"
        data = json.loads(quota_file.read_text())
        data["date"] = "2000-01-01"
        quota_file.write_text(json.dumps(data))

        tracker2 = QuotaTracker(tmp_path)
        tracker2.reset_if_new_day()
        tracker2.consume(100)
        assert tracker2.today_usage() == 100

    def test_正常系_ファイル未作成の場合もreset_if_new_dayは正常終了(
        self, tracker: QuotaTracker
    ) -> None:
        # No consume called; quota_usage.json may not exist
        tracker.reset_if_new_day()
        assert tracker.today_usage() == 0
