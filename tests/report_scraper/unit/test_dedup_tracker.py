"""Tests for report_scraper.services.dedup_tracker module."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from report_scraper.services.dedup_tracker import DedupTracker
from report_scraper.storage.json_store import JsonReportStore


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
    now = datetime.now(timezone.utc)
    index = {
        "reports": {
            "https://example.com/report/1": {
                "title": "Report 1",
                "source_key": "source_a",
                "published": "2026-02-01T12:00:00+00:00",
                "collected_at": now.isoformat(),
                "author": "Author A",
                "has_content": True,
            },
            "https://example.com/report/2": {
                "title": "Report 2",
                "source_key": "source_a",
                "published": "2026-02-15T12:00:00+00:00",
                "collected_at": now.isoformat(),
                "author": "Author B",
                "has_content": False,
            },
            "https://example.com/report/3": {
                "title": "Report 3",
                "source_key": "source_b",
                "published": "2026-03-01T12:00:00+00:00",
                "collected_at": now.isoformat(),
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

    def test_正常系_既知URLが検出される(self, populated_tracker: DedupTracker) -> None:
        assert populated_tracker.is_seen("source_a", "https://example.com/report/1")

    def test_正常系_未知URLが新規として扱われる(
        self, populated_tracker: DedupTracker
    ) -> None:
        assert not populated_tracker.is_seen(
            "source_a", "https://example.com/report/new"
        )

    def test_正常系_異なるソースキーの既知URLが検出される(
        self, populated_tracker: DedupTracker
    ) -> None:
        assert populated_tracker.is_seen("source_b", "https://example.com/report/3")

    def test_正常系_ソースキーが異なっても同一URLを検出(
        self, populated_tracker: DedupTracker
    ) -> None:
        # URL "report/1" is registered under source_a, but is_seen checks
        # URL existence regardless of source_key mismatch (URL is the dedup key)
        assert populated_tracker.is_seen("source_b", "https://example.com/report/1")

    def test_正常系_空インデックスで未知扱い(self, tracker: DedupTracker) -> None:
        assert not tracker.is_seen("source_a", "https://example.com/report/1")

    def test_正常系_期間外のURLが新規として扱われる(
        self, store: JsonReportStore
    ) -> None:
        old_date = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
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

    def test_正常系_期間内のURLは既知として検出(self, store: JsonReportStore) -> None:
        recent_date = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
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

    def test_正常系_新規URLをマーク後に既知として検出(
        self, tracker: DedupTracker
    ) -> None:
        url = "https://example.com/new-report"
        assert not tracker.is_seen("source_a", url)
        tracker.mark_seen("source_a", url)
        assert tracker.is_seen("source_a", url)

    def test_正常系_マーク後にインデックスに永続化される(
        self, tracker: DedupTracker, store: JsonReportStore
    ) -> None:
        url = "https://example.com/persisted"
        tracker.mark_seen("source_a", url)
        index = store.load_index()
        assert url in index["reports"]
        assert index["reports"][url]["source_key"] == "source_a"

    def test_正常系_既存URLを再マークしてもエラーにならない(
        self, populated_tracker: DedupTracker
    ) -> None:
        url = "https://example.com/report/1"
        populated_tracker.mark_seen("source_a", url)
        assert populated_tracker.is_seen("source_a", url)


class TestDedupTrackerGetHistory:
    """Tests for DedupTracker.get_history method."""

    def test_正常系_指定日数内のエントリを取得(self, store: JsonReportStore) -> None:
        now = datetime.now(timezone.utc)
        recent = (now - timedelta(days=5)).isoformat()
        old = (now - timedelta(days=60)).isoformat()
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

    def test_正常系_空インデックスで空リスト(self, tracker: DedupTracker) -> None:
        history = tracker.get_history(days=30)
        assert history == []

    def test_正常系_全エントリが期間内の場合すべて返却(
        self, populated_tracker: DedupTracker
    ) -> None:
        history = populated_tracker.get_history(days=90)
        assert len(history) == 3

    def test_正常系_日数パラメータで期間を制御(self, store: JsonReportStore) -> None:
        now = datetime.now(timezone.utc)
        index = {
            "reports": {
                f"https://example.com/report/{i}": {
                    "title": f"Report {i}",
                    "source_key": "source_a",
                    "published": "2026-03-01T00:00:00+00:00",
                    "collected_at": (now - timedelta(days=i * 10)).isoformat(),
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
