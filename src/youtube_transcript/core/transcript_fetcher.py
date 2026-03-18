"""TranscriptFetcher: youtube-transcript-api ラッパー.

youtube-transcript-api 1.0.x 以降の instance-method API を使用して
YouTube 動画のトランスクリプトを取得する。

API の差異メモ（1.0.x 調査結果）:
- 旧 static method `YouTubeTranscriptApi.get_transcript()` は v1.0.x で削除済み
- 新: `YouTubeTranscriptApi().fetch(video_id, languages=["ja", "en"])` を使用する
- 戻り値は `FetchedTranscript` (dataclass): snippets / video_id / language /
  language_code / is_generated
- snippet: text / start (float, 秒) / duration (float, 秒)
- 字幕なし時の例外: NoTranscriptFound / TranscriptsDisabled / VideoUnavailable /
  VideoUnplayable
"""

import os
import time
from datetime import datetime, timezone
from typing import Any

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    VideoUnplayable,
)

from youtube_transcript._logging import get_logger
from youtube_transcript.types import TranscriptEntry, TranscriptResult

logger = get_logger(__name__)

_DEFAULT_RATE_LIMIT_SEC = 1.0
_DEFAULT_LANGUAGES = ["ja", "en"]

# Tuple of exceptions that indicate "no transcript available" (return None)
_UNAVAILABLE_EXCEPTIONS = (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    VideoUnplayable,
)


class TranscriptFetcher:
    """youtube-transcript-api ラッパー.

    YouTube 動画のトランスクリプトを取得し :class:`~youtube_transcript.types.TranscriptResult`
    として返す。字幕が存在しない場合は例外を発生させず ``None`` を返す。

    Parameters
    ----------
    rate_limit_sec : float, optional
        連続した fetch() 呼び出し間の待機秒数。デフォルトは ``YT_TRANSCRIPT_RATE_LIMIT``
        環境変数の値、または 1.0 秒。コンストラクタで直接指定した場合は環境変数より優先する。
    _api : YouTubeTranscriptApi | None, optional
        テスト用の依存性注入。``None`` のとき fetch() 呼び出し時に生成する。

    Examples
    --------
    >>> fetcher = TranscriptFetcher()
    >>> result = fetcher.fetch("dQw4w9WgXcQ", languages=["ja", "en"])
    >>> if result is not None:
    ...     print(result.to_plain_text()[:50])
    """

    def __init__(
        self,
        rate_limit_sec: float | None = None,
        _api: YouTubeTranscriptApi | None = None,
    ) -> None:
        """TranscriptFetcher を初期化する.

        Parameters
        ----------
        rate_limit_sec : float | None, optional
            fetch() 呼び出し間の待機秒数。``None`` のとき ``YT_TRANSCRIPT_RATE_LIMIT``
            環境変数を参照し、未設定なら 1.0 秒をデフォルトとして使用する。
        _api : YouTubeTranscriptApi | None, optional
            テスト用の依存性注入。通常は省略する。
        """
        if rate_limit_sec is not None:
            self._rate_limit_sec = rate_limit_sec
        else:
            env_val = os.environ.get("YT_TRANSCRIPT_RATE_LIMIT")
            if env_val is not None:
                try:
                    self._rate_limit_sec = float(env_val)
                except ValueError:
                    logger.warning(
                        "Invalid YT_TRANSCRIPT_RATE_LIMIT value, using default",
                        env_value=env_val,
                        default_rate_limit=_DEFAULT_RATE_LIMIT_SEC,
                    )
                    self._rate_limit_sec = _DEFAULT_RATE_LIMIT_SEC
            else:
                self._rate_limit_sec = _DEFAULT_RATE_LIMIT_SEC

        self._last_fetch_time: float | None = None
        # _api は None のとき fetch() 内でレイジー生成する
        self._api: YouTubeTranscriptApi | None = _api

        logger.debug(
            "TranscriptFetcher initialized",
            rate_limit_sec=self._rate_limit_sec,
        )

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def rate_limit_sec(self) -> float:
        """fetch() 呼び出し間の待機秒数.

        Returns
        -------
        float
            連続した fetch() 呼び出し間に挿入されるスリープ時間（秒）。
        """
        return self._rate_limit_sec

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def fetch(
        self,
        video_id: str,
        languages: list[str] | None = None,
    ) -> TranscriptResult | None:
        """指定した動画のトランスクリプトを取得する.

        字幕が存在しない場合（``NoTranscriptFound``, ``TranscriptsDisabled``,
        ``VideoUnavailable``, ``VideoUnplayable``）は例外を発生させず ``None`` を返す。

        Parameters
        ----------
        video_id : str
            YouTube 動画 ID（11 文字の英数字文字列）。
        languages : list[str] | None, optional
            優先順位の高い順に並べた言語コードのリスト。``None`` のとき
            ``["ja", "en"]`` をデフォルトとして使用する。

        Returns
        -------
        TranscriptResult | None
            取得に成功した場合は :class:`~youtube_transcript.types.TranscriptResult`、
            字幕なしの場合は ``None``。

        Examples
        --------
        >>> fetcher = TranscriptFetcher(rate_limit_sec=0.0)
        >>> result = fetcher.fetch("dQw4w9WgXcQ")
        >>> result is None or isinstance(result, TranscriptResult)
        True
        """
        if languages is None:
            languages = _DEFAULT_LANGUAGES

        self._apply_rate_limit()

        logger.debug(
            "トランスクリプト取得開始",
            video_id=video_id,
            languages=languages,
        )

        api = self._api if self._api is not None else YouTubeTranscriptApi()

        try:
            fetched = api.fetch(video_id, languages=languages)
        except _UNAVAILABLE_EXCEPTIONS as exc:
            logger.info(
                "トランスクリプト利用不可",
                video_id=video_id,
                reason=type(exc).__name__,
                detail=str(exc),
            )
            return None
        except Exception:
            logger.exception(
                "トランスクリプト取得中に予期しないエラー",
                video_id=video_id,
            )
            raise
        finally:
            self._last_fetch_time = time.monotonic()

        result = self._convert(fetched)
        logger.info(
            "トランスクリプト取得完了",
            video_id=video_id,
            language=result.language,
            entry_count=len(result.entries),
        )
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _apply_rate_limit(self) -> None:
        """前回の fetch() 呼び出しから rate_limit_sec 秒待機する.

        初回呼び出し時はスリープしない。rate_limit_sec が 0 以下の場合も
        スリープしない。
        """
        if self._last_fetch_time is None or self._rate_limit_sec <= 0:
            return

        elapsed = time.monotonic() - self._last_fetch_time
        remaining = self._rate_limit_sec - elapsed
        if remaining > 0:
            logger.debug("レート制限待機", sleep_sec=remaining)
            time.sleep(remaining)

    @staticmethod
    def _convert(fetched: Any) -> TranscriptResult:
        """FetchedTranscript を TranscriptResult に変換する.

        Parameters
        ----------
        fetched : FetchedTranscript
            youtube-transcript-api が返す FetchedTranscript オブジェクト。

        Returns
        -------
        TranscriptResult
            変換された :class:`~youtube_transcript.types.TranscriptResult`。
        """
        entries = [
            TranscriptEntry(
                start=snippet.start,
                duration=snippet.duration,
                text=snippet.text,
            )
            for snippet in fetched
        ]

        fetched_at = datetime.now(tz=timezone.utc).isoformat()

        return TranscriptResult(
            video_id=fetched.video_id,
            language=fetched.language_code,
            entries=entries,
            fetched_at=fetched_at,
        )
