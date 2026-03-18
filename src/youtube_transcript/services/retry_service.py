"""RetryService: FAILED ステータスのトランスクリプト再取得サービス.

FAILED ステータスの動画に対して TranscriptFetcher で再取得を試みる。
SUCCESS / UNAVAILABLE の動画は対象外。quota 超過時は残りをスキップする。
"""

from pathlib import Path
from typing import Any

from youtube_transcript._logging import get_logger
from youtube_transcript.exceptions import (
    ChannelNotFoundError,
    QuotaExceededError,
)
from youtube_transcript.storage.json_storage import JSONStorage
from youtube_transcript.types import (
    Channel,
    CollectResult,
    TranscriptStatus,
    Video,
)

logger = get_logger(__name__)


class RetryService:
    """FAILED ステータスのトランスクリプトを再取得するサービス.

    FAILED 動画のみを対象に TranscriptFetcher で再実行する。
    SUCCESS / UNAVAILABLE は再取得しない。
    quota 超過時は残りの動画をスキップする。

    Parameters
    ----------
    data_dir : Path
        youtube_transcript データのルートディレクトリ。
    transcript_fetcher : Any
        :class:`~youtube_transcript.core.transcript_fetcher.TranscriptFetcher`
        互換オブジェクト。``fetch(video_id, languages) -> TranscriptResult | None``
        を実装すること。
    quota_tracker : Any
        :class:`~youtube_transcript.storage.quota_tracker.QuotaTracker`
        互換オブジェクト。``remaining() -> int`` を実装すること。

    Examples
    --------
    >>> from pathlib import Path
    >>> from youtube_transcript.core.transcript_fetcher import TranscriptFetcher
    >>> from youtube_transcript.storage.quota_tracker import QuotaTracker
    >>> data_dir = Path("data/raw/youtube_transcript")
    >>> tracker = QuotaTracker(data_dir)
    >>> service = RetryService(
    ...     data_dir=data_dir,
    ...     transcript_fetcher=TranscriptFetcher(),
    ...     quota_tracker=tracker,
    ... )
    >>> result = service.retry_failed("UCabc123")
    >>> print(result.success)
    """

    def __init__(
        self,
        data_dir: Path,
        transcript_fetcher: Any,
        quota_tracker: Any,
    ) -> None:
        """RetryService を初期化する.

        Parameters
        ----------
        data_dir : Path
            youtube_transcript データのルートディレクトリ。
        transcript_fetcher : Any
            TranscriptFetcher 互換オブジェクト。
        quota_tracker : Any
            QuotaTracker 互換オブジェクト。

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
        self._storage = JSONStorage(data_dir)
        self._transcript_fetcher = transcript_fetcher
        self._quota_tracker = quota_tracker

        logger.debug("RetryService initialized", data_dir=str(data_dir))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def retry_failed(self, channel_id: str) -> CollectResult:
        """指定チャンネルの FAILED 動画のトランスクリプトを再取得する.

        FAILED ステータスの動画のみを対象とし、SUCCESS / UNAVAILABLE は無視する。
        quota 超過時は残りをスキップして返す。

        Parameters
        ----------
        channel_id : str
            YouTube チャンネル ID（例: ``"UCabc123"``）。

        Returns
        -------
        CollectResult
            再取得の集計結果。

        Raises
        ------
        ChannelNotFoundError
            指定した channel_id がストレージに存在しない場合。

        Examples
        --------
        >>> result = service.retry_failed("UCabc123")
        >>> print(f"Success: {result.success}, Failed: {result.failed}")
        """
        logger.info("Starting retry_failed", channel_id=channel_id)

        channel = self._load_channel(channel_id)
        videos = self._storage.load_videos(channel_id)

        # FAILED ステータスの動画のみ抽出
        failed_videos = [
            v for v in videos if v.transcript_status == TranscriptStatus.FAILED
        ]

        logger.info(
            "FAILED videos found",
            channel_id=channel_id,
            failed_count=len(failed_videos),
            total_videos=len(videos),
        )

        if not failed_videos:
            return CollectResult(
                total=0,
                success=0,
                unavailable=0,
                failed=0,
                skipped=0,
            )

        result = self._retry_videos(channel, failed_videos, videos)

        logger.info(
            "retry_failed complete",
            channel_id=channel_id,
            total=result.total,
            success=result.success,
            unavailable=result.unavailable,
            failed=result.failed,
            skipped=result.skipped,
        )

        return result

    def retry_all_failed(self) -> list[CollectResult]:
        """全有効チャンネルの FAILED 動画を再取得する.

        有効（enabled=True）なチャンネルのみを対象に、それぞれの FAILED
        動画を再取得する。

        Returns
        -------
        list[CollectResult]
            有効チャンネルごとの再取得結果。

        Examples
        --------
        >>> results = service.retry_all_failed()
        >>> total_success = sum(r.success for r in results)
        """
        channels = self._storage.load_channels()
        enabled = [ch for ch in channels if ch.enabled]

        logger.info(
            "Starting retry_all_failed",
            total_channels=len(channels),
            enabled_channels=len(enabled),
        )

        results: list[CollectResult] = []

        for channel in enabled:
            logger.info(
                "Processing channel",
                channel_id=channel.channel_id,
                title=channel.title,
            )
            result = self.retry_failed(channel.channel_id)
            results.append(result)

        logger.info(
            "retry_all_failed complete",
            channels_processed=len(results),
        )

        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_channel(self, channel_id: str) -> Channel:
        """ストレージからチャンネルを取得する.

        Parameters
        ----------
        channel_id : str
            YouTube チャンネル ID。

        Returns
        -------
        Channel
            ストレージ内のチャンネル。

        Raises
        ------
        ChannelNotFoundError
            指定した channel_id が存在しない場合。
        """
        channels = self._storage.load_channels()
        for ch in channels:
            if ch.channel_id == channel_id:
                return ch
        raise ChannelNotFoundError(f"Channel '{channel_id}' not found")

    def _retry_videos(
        self,
        channel: Channel,
        failed_videos: list[Video],
        all_videos: list[Video],
    ) -> CollectResult:
        """FAILED 動画のトランスクリプトを再取得して結果を返す.

        Parameters
        ----------
        channel : Channel
            処理対象チャンネル。
        failed_videos : list[Video]
            FAILED ステータスの動画リスト。
        all_videos : list[Video]
            チャンネルの全動画リスト（ストレージ更新に使用）。

        Returns
        -------
        CollectResult
            再取得の集計結果。
        """
        total = len(failed_videos)
        success = 0
        unavailable = 0
        failed = 0
        skipped = 0

        # 全動画の dict を作成（効率的な更新のため）
        video_map: dict[str, Video] = {v.video_id: v for v in all_videos}

        for video in failed_videos:
            try:
                transcript = self._transcript_fetcher.fetch(
                    video.video_id,
                    languages=channel.language_priority,
                )
            except QuotaExceededError:
                logger.warning(
                    "Quota exceeded during retry; skipping remaining videos",
                    channel_id=channel.channel_id,
                    video_id=video.video_id,
                )
                # 残りの動画をすべてスキップとしてカウント
                remaining_count = total - success - unavailable - failed - skipped
                skipped += remaining_count
                break
            except Exception:
                logger.exception(
                    "Unexpected error retrying transcript",
                    channel_id=channel.channel_id,
                    video_id=video.video_id,
                )
                failed += 1
                # FAILED ステータスを維持
                video_map[video.video_id] = video
                continue

            if transcript is not None:
                # トランスクリプトを保存
                self._storage.save_transcript(channel.channel_id, transcript)

                # 動画ステータスを更新
                video.transcript_status = TranscriptStatus.SUCCESS
                video.transcript_language = transcript.language
                video.fetched_at = transcript.fetched_at
                success += 1

                logger.debug(
                    "Transcript saved on retry",
                    channel_id=channel.channel_id,
                    video_id=video.video_id,
                    language=transcript.language,
                )
            else:
                video.transcript_status = TranscriptStatus.UNAVAILABLE
                unavailable += 1

                logger.debug(
                    "Transcript unavailable on retry",
                    channel_id=channel.channel_id,
                    video_id=video.video_id,
                )

            video_map[video.video_id] = video

        # 更新した動画リストをストレージに保存
        self._storage.save_videos(channel.channel_id, list(video_map.values()))

        return CollectResult(
            total=total,
            success=success,
            unavailable=unavailable,
            failed=failed,
            skipped=skipped,
        )
