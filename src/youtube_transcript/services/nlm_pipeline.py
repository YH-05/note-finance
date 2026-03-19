"""NlmPipeline: NotebookLM パイプライン.

YouTube トランスクリプトを plain text にエクスポートし、
NotebookLM のノートブックにテキストソースとして投入する。

Architecture
------------
- ``add_to_notebook``: 1動画のトランスクリプトをノートブックに追加
- ``bulk_add_channel``: チャンネル全動画のトランスクリプトを一括追加

Dependencies
------------
- notebooklm.services.source.SourceService (Playwright ブラウザ経由)
- youtube_transcript.storage.json_storage.JSONStorage
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from youtube_transcript._logging import get_logger
from youtube_transcript.exceptions import ChannelNotFoundError
from youtube_transcript.storage.json_storage import JSONStorage
from youtube_transcript.types import (
    TranscriptResult,
    TranscriptStatus,
    Video,
)

logger = get_logger(__name__)


class NlmPipeline:
    """NotebookLM へのトランスクリプト投入パイプライン.

    トランスクリプトを plain text に変換し、NotebookLM の
    テキストソースとしてノートブックに追加する。

    Parameters
    ----------
    data_dir : Path
        youtube_transcript データのルートディレクトリ。
    session_file : str | None
        NotebookLM ブラウザセッションファイルパス。None の場合はデフォルト。
    headless : bool
        Playwright ブラウザをヘッドレスで起動するか（デフォルト: True）。

    Examples
    --------
    >>> from pathlib import Path
    >>> from youtube_transcript.services.nlm_pipeline import NlmPipeline
    >>> pipeline = NlmPipeline(data_dir=Path("data/raw/youtube_transcript"))
    >>> import asyncio
    >>> # result = asyncio.run(pipeline.add_to_notebook(
    >>> #     notebook_id="abc-123",
    >>> #     transcript=transcript,
    >>> #     title="My Video",
    >>> # ))
    """

    def __init__(
        self,
        data_dir: Path,
        session_file: str | None = None,
        headless: bool = True,
    ) -> None:
        """NlmPipeline を初期化する.

        Parameters
        ----------
        data_dir : Path
            youtube_transcript データのルートディレクトリ。
        session_file : str | None
            NotebookLM ブラウザセッションファイルパス。
        headless : bool
            Playwright ブラウザをヘッドレスで起動するか。

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
        self._session_file = session_file
        self._headless = headless
        self._storage = JSONStorage(data_dir)

        logger.debug("NlmPipeline initialized", data_dir=str(data_dir))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def add_to_notebook(
        self,
        notebook_id: str,
        transcript: TranscriptResult,
        title: str,
    ) -> Any:
        """1動画のトランスクリプトを NotebookLM ノートブックに追加する.

        トランスクリプトを ``TranscriptResult.to_plain_text()`` で plain text
        に変換し、NotebookLM のテキストソースとして追加する。

        Parameters
        ----------
        notebook_id : str
            対象の NotebookLM ノートブック ID（UUID）。
        transcript : TranscriptResult
            投入するトランスクリプト。
        title : str
            ソースとして登録するタイトル。

        Returns
        -------
        SourceInfo
            追加されたソースの情報。

        Examples
        --------
        >>> result = await pipeline.add_to_notebook(
        ...     notebook_id="c9354f3f-f55b-4f90-a5c4-219e582945cf",
        ...     transcript=transcript,
        ...     title="NVIDIA 決算説明会",
        ... )
        >>> print(result.source_id)
        """
        plain_text = transcript.to_plain_text()

        logger.info(
            "Adding transcript to notebook",
            notebook_id=notebook_id,
            video_id=transcript.video_id,
            title=title,
            text_length=len(plain_text),
        )

        service = self._build_source_service()
        result = await service.add_text_source(
            notebook_id,
            content=plain_text,
            title=title,
        )

        logger.info(
            "Transcript added to notebook",
            notebook_id=notebook_id,
            video_id=transcript.video_id,
            source_id=getattr(result, "source_id", None),
        )

        return result

    async def bulk_add_channel(
        self,
        notebook_id: str,
        channel_id: str,
    ) -> list[Any]:
        """チャンネルの全 SUCCESS 動画トランスクリプトをノートブックに一括追加する.

        ``TranscriptStatus.SUCCESS`` の動画のみを対象とし、
        FAILED / UNAVAILABLE / PENDING の動画はスキップする。

        Parameters
        ----------
        notebook_id : str
            対象の NotebookLM ノートブック ID（UUID）。
        channel_id : str
            対象の YouTube チャンネル ID。

        Returns
        -------
        list[SourceInfo]
            追加されたソースのリスト。

        Raises
        ------
        ChannelNotFoundError
            指定した channel_id がストレージに存在しない場合。

        Examples
        --------
        >>> results = await pipeline.bulk_add_channel(
        ...     notebook_id="c9354f3f-f55b-4f90-a5c4-219e582945cf",
        ...     channel_id="UCabc123",
        ... )
        >>> print(f"Added {len(results)} sources")
        """
        # チャンネルの存在確認
        channels = self._storage.load_channels()
        channel = next((ch for ch in channels if ch.channel_id == channel_id), None)
        if channel is None:
            logger.error("Channel not found", channel_id=channel_id)
            raise ChannelNotFoundError(f"Channel '{channel_id}' not found")

        # SUCCESS 動画のみ抽出
        all_videos: list[Video] = self._storage.load_videos(channel_id)
        success_videos = [
            v for v in all_videos if v.transcript_status == TranscriptStatus.SUCCESS
        ]

        logger.info(
            "bulk_add_channel started",
            notebook_id=notebook_id,
            channel_id=channel_id,
            total_videos=len(all_videos),
            success_videos=len(success_videos),
        )

        results: list[Any] = []

        for video in success_videos:
            transcript = self._storage.load_transcript(channel_id, video.video_id)
            if transcript is None:
                logger.warning(
                    "Transcript file not found for SUCCESS video; skipping",
                    channel_id=channel_id,
                    video_id=video.video_id,
                )
                continue

            try:
                source_info = await self.add_to_notebook(
                    notebook_id=notebook_id,
                    transcript=transcript,
                    title=video.title,
                )
                results.append(source_info)
            except Exception:
                logger.exception(
                    "Failed to add transcript to notebook; skipping",
                    notebook_id=notebook_id,
                    channel_id=channel_id,
                    video_id=video.video_id,
                )
                continue

        logger.info(
            "bulk_add_channel completed",
            notebook_id=notebook_id,
            channel_id=channel_id,
            added=len(results),
            skipped=len(success_videos) - len(results),
        )

        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_source_service(self) -> Any:
        """NotebookLM SourceService を構築する.

        Returns
        -------
        SourceService
            設定済みの SourceService インスタンス。

        Notes
        -----
        AIDEV-NOTE: ここでのインポートはテスト時のモックを容易にするため。
        """
        # AIDEV-NOTE: Import here to avoid circular imports and allow test mocking.
        from notebooklm.browser.manager import NotebookLMBrowserManager
        from notebooklm.constants import DEFAULT_SESSION_FILE
        from notebooklm.services.source import SourceService

        session_file: str = (
            self._session_file
            if self._session_file is not None
            else DEFAULT_SESSION_FILE
        )
        manager = NotebookLMBrowserManager(
            session_file=session_file,
            headless=self._headless,
        )
        return SourceService(manager)
