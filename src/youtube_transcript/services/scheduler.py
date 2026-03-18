"""Scheduler: APScheduler を使った定期収集スケジューラ.

``YT_SCHEDULE_CRON`` 環境変数で定期実行スケジュールを設定できる。
デフォルトは毎日 6:00 JST（UTC 21:00）。

Architecture
------------
- ``Scheduler``: スケジューラクラス（APScheduler の BlockingScheduler をラップ）
- ``run_scheduler``: エントリーポイント関数

Usage
-----
環境変数で制御:
    YT_SCHEDULE_CRON: cron 式（デフォルト: "0 21 * * *" = JST 6:00）

Examples
--------
>>> from pathlib import Path
>>> from youtube_transcript.services.scheduler import run_scheduler
>>> run_scheduler(data_dir=Path("data/raw/youtube_transcript"))

CLI からは別途 yt-transcript scheduler start コマンドで起動する。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from youtube_transcript._logging import get_logger

logger = get_logger(__name__)

# デフォルト cron: JST 6:00 = UTC 21:00（前日）
# AIDEV-NOTE: APScheduler は UTC で動作するため、JST 6:00 を UTC 21:00 に変換
_DEFAULT_CRON = "0 21 * * *"

# 環境変数名
_ENV_CRON = "YT_SCHEDULE_CRON"


class Scheduler:
    """YouTube トランスクリプト定期収集スケジューラ.

    APScheduler の BlockingScheduler を使用して、定期的に
    ``Collector.collect_all()`` を実行する。

    Parameters
    ----------
    data_dir : Path
        youtube_transcript データのルートディレクトリ。
    cron_expression : str | None
        cron 式（None の場合は環境変数 YT_SCHEDULE_CRON、
        それも未設定の場合はデフォルト "0 21 * * *" を使用）。

    Examples
    --------
    >>> from pathlib import Path
    >>> scheduler = Scheduler(data_dir=Path("data/raw/youtube_transcript"))
    >>> scheduler.start()
    """

    def __init__(
        self,
        data_dir: Path,
        cron_expression: str | None = None,
    ) -> None:
        """Scheduler を初期化する.

        Parameters
        ----------
        data_dir : Path
            youtube_transcript データのルートディレクトリ。
        cron_expression : str | None
            cron 式。None の場合は環境変数または デフォルト値を使用。

        Raises
        ------
        ValueError
            data_dir が Path オブジェクトでない場合。
        """
        if not isinstance(data_dir, Path):  # type: ignore[reportUnnecessaryIsInstance]
            logger.error(
                "Invalid data_dir type",
                data_dir=str(data_dir),
                expected_type="Path",
                actual_type=type(data_dir).__name__,
            )
            raise ValueError(f"data_dir must be a Path object, got {type(data_dir)}")

        self.data_dir = data_dir

        # cron 式の解決: 引数 > 環境変数 > デフォルト
        if cron_expression is not None:
            self.cron_expression = cron_expression
        else:
            self.cron_expression = os.environ.get(_ENV_CRON, _DEFAULT_CRON)

        logger.debug(
            "Scheduler initialized",
            data_dir=str(data_dir),
            cron_expression=self.cron_expression,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """スケジューラを起動する（ブロッキング呼び出し）.

        APScheduler の BlockingScheduler を使用し、
        cron トリガーでジョブを登録して開始する。
        KeyboardInterrupt が発生した場合は正常終了する。

        Raises
        ------
        ImportError
            apscheduler がインストールされていない場合。
        """
        logger.info(
            "Starting scheduler",
            cron_expression=self.cron_expression,
        )

        # AIDEV-NOTE: Import here to avoid ImportError when apscheduler is not installed
        from apscheduler.schedulers.blocking import (
            BlockingScheduler,  # type: ignore[import-not-found]
        )

        _apscheduler = BlockingScheduler()
        self._apscheduler = _apscheduler

        self._register_job()

        logger.info("Scheduler started, waiting for jobs...")

        try:
            _apscheduler.start()
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by KeyboardInterrupt")
            _apscheduler.shutdown(wait=False)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _register_job(self) -> None:
        """cron トリガーでジョブを APScheduler に登録する.

        Notes
        -----
        AIDEV-NOTE: テストから直接呼び出せるように分離している。
        """
        # AIDEV-NOTE: Import here for testability
        from apscheduler.schedulers.blocking import (
            BlockingScheduler,  # type: ignore[import-not-found]
        )

        # _apscheduler がまだない場合（_register_job を直接テストするとき）
        if not hasattr(self, "_apscheduler"):
            self._apscheduler = BlockingScheduler()

        # cron 式を分解して APScheduler に渡す
        cron_parts = self.cron_expression.split()
        if len(cron_parts) != 5:
            logger.error(
                "Invalid cron expression",
                cron_expression=self.cron_expression,
            )
            raise ValueError(
                f"Invalid cron expression (must have 5 parts): {self.cron_expression}"
            )

        minute, hour, day, month, day_of_week = cron_parts

        self._apscheduler.add_job(
            self._collect_job,
            trigger="cron",
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
            id="collect_all",
            replace_existing=True,
        )

        logger.info(
            "Job registered",
            cron_expression=self.cron_expression,
        )

    def _collect_job(self) -> None:
        """定期実行されるジョブ: 全チャンネルのトランスクリプトを収集する.

        例外が発生してもスケジューラをクラッシュさせないよう、
        全ての例外をキャッチしてログする。
        """
        logger.info("Scheduled collect_all started")

        try:
            collector = self._build_collector()
            results = collector.collect_all()

            total_success = sum(r.success for r in results)
            logger.info(
                "Scheduled collect_all completed",
                channels_processed=len(results),
                total_success=total_success,
            )
        except Exception:
            logger.exception("Scheduled collect_all failed with unexpected error")

    def _build_collector(self) -> Any:
        """Collector インスタンスを構築する.

        Returns
        -------
        Collector
            設定済みの Collector インスタンス。

        Notes
        -----
        AIDEV-NOTE: テストでのモックを容易にするため分離している。
        """
        import os as _os

        from youtube_transcript.core.channel_fetcher import ChannelFetcher
        from youtube_transcript.core.transcript_fetcher import TranscriptFetcher
        from youtube_transcript.services.collector import Collector
        from youtube_transcript.storage.quota_tracker import QuotaTracker

        api_key = _os.environ.get("YOUTUBE_API_KEY", "")
        quota_tracker = QuotaTracker(self.data_dir)
        channel_fetcher = ChannelFetcher(api_key=api_key, quota_tracker=quota_tracker)
        transcript_fetcher = TranscriptFetcher()

        return Collector(
            data_dir=self.data_dir,
            channel_fetcher=channel_fetcher,
            transcript_fetcher=transcript_fetcher,
            quota_tracker=quota_tracker,
        )


def run_scheduler(data_dir: Path) -> None:
    """スケジューラのエントリーポイント関数.

    ``Scheduler`` インスタンスを生成して起動する。

    Parameters
    ----------
    data_dir : Path
        youtube_transcript データのルートディレクトリ。

    Examples
    --------
    >>> from pathlib import Path
    >>> from youtube_transcript.services.scheduler import run_scheduler
    >>> run_scheduler(data_dir=Path("data/raw/youtube_transcript"))
    """
    logger.info("run_scheduler called", data_dir=str(data_dir))
    scheduler = Scheduler(data_dir=data_dir)
    scheduler.start()
