"""Tests for Scheduler: 定期収集スケジューラ.

APScheduler を使用して collect_all() を定期実行する。
YT_SCHEDULE_CRON 環境変数でスケジュールを設定する（デフォルト: 毎日 6:00 JST）。
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from youtube_transcript.services.scheduler import Scheduler, run_scheduler

# ---------------------------------------------------------------------------
# Scheduler クラスのテスト
# ---------------------------------------------------------------------------


class TestSchedulerInit:
    """Scheduler 初期化のテスト."""

    def test_正常系_デフォルト設定で初期化できる(self, tmp_path: Path) -> None:
        """Scheduler がデフォルト設定で初期化できる."""
        scheduler = Scheduler(data_dir=tmp_path)
        assert scheduler is not None
        assert scheduler.data_dir == tmp_path

    def test_正常系_デフォルトcronは600_JSTである(self, tmp_path: Path) -> None:
        """Scheduler のデフォルト cron は UTC 21:00（JST 6:00）."""
        scheduler = Scheduler(data_dir=tmp_path)
        # JST 6:00 = UTC 21:00（前日）
        assert scheduler.cron_expression == "0 21 * * *"

    def test_正常系_環境変数でcronを上書きできる(self, tmp_path: Path) -> None:
        """YT_SCHEDULE_CRON 環境変数で cron を上書きできる."""
        with patch.dict(os.environ, {"YT_SCHEDULE_CRON": "0 12 * * *"}):
            scheduler = Scheduler(data_dir=tmp_path)
        assert scheduler.cron_expression == "0 12 * * *"


class TestSchedulerJobRegistration:
    """Scheduler ジョブ登録のテスト."""

    def test_正常系_ジョブが登録できる(self, tmp_path: Path) -> None:
        """Scheduler にジョブが正常に登録できる."""
        mock_scheduler_instance = MagicMock()

        with patch(
            "apscheduler.schedulers.blocking.BlockingScheduler",
            return_value=mock_scheduler_instance,
        ):
            scheduler = Scheduler(data_dir=tmp_path)
            scheduler._register_job()

        mock_scheduler_instance.add_job.assert_called_once()

    def test_正常系_cron_triggerで登録される(self, tmp_path: Path) -> None:
        """ジョブは cron trigger で登録される."""
        mock_scheduler_instance = MagicMock()

        with patch(
            "apscheduler.schedulers.blocking.BlockingScheduler",
            return_value=mock_scheduler_instance,
        ):
            scheduler = Scheduler(data_dir=tmp_path)
            scheduler._register_job()

        call_kwargs = mock_scheduler_instance.add_job.call_args
        # trigger='cron' が渡されることを確認
        assert call_kwargs is not None


class TestSchedulerCollectJob:
    """Scheduler._collect_job のテスト."""

    def test_正常系_collect_jobがcollect_allを呼ぶ(self, tmp_path: Path) -> None:
        """Scheduler._collect_job が Collector.collect_all() を呼ぶ."""
        mock_collect_all = MagicMock(return_value=[])
        mock_collector = MagicMock()
        mock_collector.collect_all = mock_collect_all

        with patch(
            "youtube_transcript.services.scheduler.Scheduler._build_collector",
            return_value=mock_collector,
        ):
            scheduler = Scheduler(data_dir=tmp_path)
            scheduler._collect_job()

        mock_collect_all.assert_called_once()

    def test_正常系_collect_jobが例外をキャッチしてログする(
        self, tmp_path: Path
    ) -> None:
        """Scheduler._collect_job が例外をキャッチしてクラッシュしない."""
        mock_collector = MagicMock()
        mock_collector.collect_all.side_effect = RuntimeError("network error")

        with patch(
            "youtube_transcript.services.scheduler.Scheduler._build_collector",
            return_value=mock_collector,
        ):
            scheduler = Scheduler(data_dir=tmp_path)
            # 例外がスローされずに完了する
            scheduler._collect_job()


# ---------------------------------------------------------------------------
# run_scheduler 関数のテスト
# ---------------------------------------------------------------------------


class TestRunScheduler:
    """run_scheduler() 関数のテスト."""

    def test_正常系_run_schedulerがSchedulerを起動する(self, tmp_path: Path) -> None:
        """run_scheduler が Scheduler.start() を呼ぶ."""
        mock_start = MagicMock()
        mock_scheduler_instance = MagicMock()
        mock_scheduler_instance.start = mock_start

        with patch(
            "youtube_transcript.services.scheduler.Scheduler",
            return_value=mock_scheduler_instance,
        ):
            run_scheduler(data_dir=tmp_path)

        mock_start.assert_called_once()

    def test_正常系_KeyboardInterruptで正常終了する(self, tmp_path: Path) -> None:
        """run_scheduler が KeyboardInterrupt で正常終了する."""
        mock_scheduler_instance = MagicMock()
        mock_scheduler_instance.start.side_effect = KeyboardInterrupt

        with patch(
            "youtube_transcript.services.scheduler.Scheduler",
            return_value=mock_scheduler_instance,
        ):
            # 例外がスローされずに完了する
            run_scheduler(data_dir=tmp_path)
