"""Tests for report_scraper.services.dedup_tracker module."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from report_scraper.services.dedup_tracker import DedupTracker
from report_scraper.storage.json_store import JsonReportStore

# ---------------------------------------------------------------------------
# Fixed reference time for deterministic tests
# ---------------------------------------------------------------------------

FIXED_NOW = datetime(2026, 3, 6, 12, 0, 0, tzinfo=timezone.utc)
"""Fixed reference time used across all tests."""


@pytest.fixture
def store_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for the store."""
    return tmp_path / "reports"


@pytest.fixture
def store(store_dir: Path) -> JsonReportStore:
    """Create a JsonReportStore instance."""
    return JsonReportStore(store_dir)


@pytest.fixture
def tracker(store: JsonReportStore) -> DedupTracker:
    """Create a DedupTracker with default settings."""
    return DedupTracker(store, dedup_days=30)


@pytest.fixture
def populated_store(store: JsonReportStore) -> JsonReportStore:
    """Create a store with pre-populated index data."""
    index = {
        "reports": {
            "https://example.com/report/1": {
                "title": "Report 1",
                "source_key": "source_a",
                "published": "2026-02-01T12:00:00+00:00",
                "collected_at": FIXED_NOW.isoformat(),
                "author": "Author A",
                "has_content": True,
            },
            "https://example.com/report/2": {
                "title": "Report 2",
                "source_key": "source_a",
                "published": "2026-02-15T12:00:00+00:00",
                "collected_at": FIXED_NOW.isoformat(),
                "author": "Author B",
                "has_content": False,
            },
            "https://example.com/report/3": {
                "title": "Report 3",
                "source_key": "source_b",
                "published": "2026-03-01T12:00:00+00:00",
                "collected_at": FIXED_NOW.isoformat(),
                "author": None,
                "has_content": True,
            },
        },
    }
    store.save_index(index)
    return store


@pytest.fixture
def populated_tracker(populated_store: JsonReportStore) -> DedupTracker:
    """Create a DedupTracker with pre-populated data."""
    return DedupTracker(populated_store, dedup_days=30)


class TestDedupTrackerIsSeen:
    """Tests for DedupTracker.is_seen method."""

    @patch("report_scraper.services.dedup_tracker.datetime")
    def test_正常系_既知URLが検出される(
        self, mock_dt: object, populated_tracker: DedupTracker
    ) -> None:
        mock_dt.now.return_value = FIXED_NOW  # type: ignore[union-attr]
        mock_dt.fromisoformat = datetime.fromisoformat  # type: ignore[union-attr]
        assert populated_tracker.is_seen("source_a", "https://example.com/report/1")

    @patch("report_scraper.services.dedup_tracker.datetime")
    def test_正常系_未知URLが新規として扱われる(
        self, mock_dt: object, populated_tracker: DedupTracker
    ) -> None:
        mock_dt.now.return_value = FIXED_NOW  # type: ignore[union-attr]
        mock_dt.fromisoformat = datetime.fromisoformat  # type: ignore[union-attr]
        assert not populated_tracker.is_seen(
            "source_a", "https://example.com/report/new"
        )

    @patch("report_scraper.services.dedup_tracker.datetime")
    def test_正常系_異なるソースキーの既知URLが検出される(
        self, mock_dt: object, populated_tracker: DedupTracker
    ) -> None:
        mock_dt.now.return_value = FIXED_NOW  # type: ignore[union-attr]
        mock_dt.fromisoformat = datetime.fromisoformat  # type: ignore[union-attr]
        assert populated_tracker.is_seen("source_b", "https://example.com/report/3")

    @patch("report_scraper.services.dedup_tracker.datetime")
    def test_正常系_ソースキーが異なっても同一URLを検出(
        self, mock_dt: object, populated_tracker: DedupTracker
    ) -> None:
        mock_dt.now.return_value = FIXED_NOW  # type: ignore[union-attr]
        mock_dt.fromisoformat = datetime.fromisoformat  # type: ignore[union-attr]
        assert populated_tracker.is_seen("source_b", "https://example.com/report/1")

    @patch("report_scraper.services.dedup_tracker.datetime")
    def test_正常系_空インデックスで未知扱い(
        self, mock_dt: object, tracker: DedupTracker
    ) -> None:
        mock_dt.now.return_value = FIXED_NOW  # type: ignore[union-attr]
        mock_dt.fromisoformat = datetime.fromisoformat  # type: ignore[union-attr]
        assert not tracker.is_seen("source_a", "https://example.com/report/1")

    @patch("report_scraper.services.dedup_tracker.datetime")
    def test_正常系_期間外のURLが新規として扱われる(
        self, mock_dt: object, store: JsonReportStore
    ) -> None:
        mock_dt.now.return_value = FIXED_NOW  # type: ignore[union-attr]
        mock_dt.fromisoformat = datetime.fromisoformat  # type: ignore[union-attr]
        old_date = (FIXED_NOW - timedelta(days=60)).isoformat()
        index = {
            "reports": {
                "https://example.com/old-report": {
                    "title": "Old Report",
                    "source_key": "source_a",
                    "published": "2025-12-01T12:00:00+00:00",
                    "collected_at": old_date,
                    "author": None,
                    "has_content": True,
                },
            },
        }
        store.save_index(index)
        tracker = DedupTracker(store, dedup_days=30)
        assert not tracker.is_seen("source_a", "https://example.com/old-report")

    @patch("report_scraper.services.dedup_tracker.datetime")
    def test_正常系_期間内のURLは既知として検出(
        self, mock_dt: object, store: JsonReportStore
    ) -> None:
        mock_dt.now.return_value = FIXED_NOW  # type: ignore[union-attr]
        mock_dt.fromisoformat = datetime.fromisoformat  # type: ignore[union-attr]
        recent_date = (FIXED_NOW - timedelta(days=10)).isoformat()
        index = {
            "reports": {
                "https://example.com/recent-report": {
                    "title": "Recent Report",
                    "source_key": "source_a",
                    "published": "2026-02-20T12:00:00+00:00",
                    "collected_at": recent_date,
                    "author": None,
                    "has_content": True,
                },
            },
        }
        store.save_index(index)
        tracker = DedupTracker(store, dedup_days=30)
        assert tracker.is_seen("source_a", "https://example.com/recent-report")


class TestDedupTrackerMarkSeen:
    """Tests for DedupTracker.mark_seen method."""

    @patch("report_scraper.services.dedup_tracker.datetime")
    def test_正常系_新規URLをマーク後に既知として検出(
        self, mock_dt: object, tracker: DedupTracker
    ) -> None:
        mock_dt.now.return_value = FIXED_NOW  # type: ignore[union-attr]
        mock_dt.fromisoformat = datetime.fromisoformat  # type: ignore[union-attr]
        url = "https://example.com/new-report"
        assert not tracker.is_seen("source_a", url)
        tracker.mark_seen("source_a", url)
        assert tracker.is_seen("source_a", url)

    @patch("report_scraper.services.dedup_tracker.datetime")
    def test_正常系_マーク後にインデックスに永続化される(
        self, mock_dt: object, tracker: DedupTracker, store: JsonReportStore
    ) -> None:
        mock_dt.now.return_value = FIXED_NOW  # type: ignore[union-attr]
        mock_dt.fromisoformat = datetime.fromisoformat  # type: ignore[union-attr]
        url = "https://example.com/persisted"
        tracker.mark_seen("source_a", url)
        # Invalidate cache to force reload
        store._index_cache = None
        index = store.load_index()
        assert url in index["reports"]
        assert index["reports"][url]["source_key"] == "source_a"
        assert index["reports"][url]["collected_at"] == FIXED_NOW.isoformat()

    @patch("report_scraper.services.dedup_tracker.datetime")
    def test_正常系_既存URLを再マークしてもエラーにならない(
        self, mock_dt: object, populated_tracker: DedupTracker
    ) -> None:
        mock_dt.now.return_value = FIXED_NOW  # type: ignore[union-attr]
        mock_dt.fromisoformat = datetime.fromisoformat  # type: ignore[union-attr]
        url = "https://example.com/report/1"
        populated_tracker.mark_seen("source_a", url)
        assert populated_tracker.is_seen("source_a", url)


class TestDedupTrackerGetHistory:
    """Tests for DedupTracker.get_history method."""

    @patch("report_scraper.services.dedup_tracker.datetime")
    def test_正常系_指定日数内のエントリを取得(
        self, mock_dt: object, store: JsonReportStore
    ) -> None:
        mock_dt.now.return_value = FIXED_NOW  # type: ignore[union-attr]
        mock_dt.fromisoformat = datetime.fromisoformat  # type: ignore[union-attr]
        recent = (FIXED_NOW - timedelta(days=5)).isoformat()
        old = (FIXED_NOW - timedelta(days=60)).isoformat()
        index = {
            "reports": {
                "https://example.com/recent": {
                    "title": "Recent",
                    "source_key": "source_a",
                    "published": "2026-03-01T00:00:00+00:00",
                    "collected_at": recent,
                    "author": None,
                    "has_content": True,
                },
                "https://example.com/old": {
                    "title": "Old",
                    "source_key": "source_a",
                    "published": "2025-12-01T00:00:00+00:00",
                    "collected_at": old,
                    "author": None,
                    "has_content": True,
                },
            },
        }
        store.save_index(index)
        tracker = DedupTracker(store, dedup_days=30)
        history = tracker.get_history(days=30)
        urls = [entry["url"] for entry in history]
        assert "https://example.com/recent" in urls
        assert "https://example.com/old" not in urls

    @patch("report_scraper.services.dedup_tracker.datetime")
    def test_正常系_空インデックスで空リスト(
        self, mock_dt: object, tracker: DedupTracker
    ) -> None:
        mock_dt.now.return_value = FIXED_NOW  # type: ignore[union-attr]
        mock_dt.fromisoformat = datetime.fromisoformat  # type: ignore[union-attr]
        history = tracker.get_history(days=30)
        assert history == []

    @patch("report_scraper.services.dedup_tracker.datetime")
    def test_正常系_全エントリが期間内の場合すべて返却(
        self, mock_dt: object, populated_tracker: DedupTracker
    ) -> None:
        mock_dt.now.return_value = FIXED_NOW  # type: ignore[union-attr]
        mock_dt.fromisoformat = datetime.fromisoformat  # type: ignore[union-attr]
        history = populated_tracker.get_history(days=90)
        assert len(history) == 3

    @patch("report_scraper.services.dedup_tracker.datetime")
    def test_正常系_日数パラメータで期間を制御(
        self, mock_dt: object, store: JsonReportStore
    ) -> None:
        mock_dt.now.return_value = FIXED_NOW  # type: ignore[union-attr]
        mock_dt.fromisoformat = datetime.fromisoformat  # type: ignore[union-attr]
        index = {
            "reports": {
                f"https://example.com/report/{i}": {
                    "title": f"Report {i}",
                    "source_key": "source_a",
                    "published": "2026-03-01T00:00:00+00:00",
                    "collected_at": (FIXED_NOW - timedelta(days=i * 10)).isoformat(),
                    "author": None,
                    "has_content": True,
                }
                for i in range(5)
            },
        }
        store.save_index(index)
        tracker = DedupTracker(store, dedup_days=30)

        history_7 = tracker.get_history(days=7)
        history_25 = tracker.get_history(days=25)
        history_45 = tracker.get_history(days=45)

        assert len(history_7) == 1  # only day 0
        assert len(history_25) == 3  # days 0, 10, 20
        assert len(history_45) == 5  # days 0, 10, 20, 30, 40


class TestDedupTrackerInit:
    """Tests for DedupTracker initialization."""

    def test_正常系_デフォルト設定で初期化(self, store: JsonReportStore) -> None:
        tracker = DedupTracker(store)
        assert tracker.dedup_days == 30

    def test_正常系_カスタム日数で初期化(self, store: JsonReportStore) -> None:
        tracker = DedupTracker(store, dedup_days=7)
        assert tracker.dedup_days == 7

    def test_異常系_dedup_daysが0以下でValueError(self, store: JsonReportStore) -> None:
        with pytest.raises(ValueError, match="dedup_days must be positive"):
            DedupTracker(store, dedup_days=0)

    def test_異常系_dedup_daysが負の値でValueError(
        self, store: JsonReportStore
    ) -> None:
        with pytest.raises(ValueError, match="dedup_days must be positive"):
            DedupTracker(store, dedup_days=-1)
