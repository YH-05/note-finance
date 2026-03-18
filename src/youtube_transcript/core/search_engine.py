"""SearchEngine: 保存済みトランスクリプトの横断検索.

JSONStorage が管理するデータディレクトリを走査し、
指定キーワードにマッチするトランスクリプトエントリを返す。
"""

import json
from dataclasses import dataclass
from pathlib import Path

from youtube_transcript._logging import get_logger
from youtube_transcript.types import TranscriptEntry, TranscriptResult

logger = get_logger(__name__)


@dataclass
class SearchResult:
    """トランスクリプト検索の1件の結果.

    Attributes
    ----------
    video_id : str
        マッチが見つかった YouTube 動画 ID。
    channel_id : str
        マッチが見つかったチャンネル ID。
    matched_text : str
        マッチしたトランスクリプトエントリのテキスト。
    timestamp : float
        マッチしたエントリの開始タイムスタンプ（秒）。
    """

    video_id: str
    channel_id: str
    matched_text: str
    timestamp: float


class SearchEngine:
    """保存済みトランスクリプトを横断検索するエンジン.

    JSONStorage の 3 階層ディレクトリ構造
    ``{data_dir}/{channel_id}/{video_id}/transcript.json`` を走査し、
    キーワードにマッチするエントリを :class:`SearchResult` として返す。

    Parameters
    ----------
    data_dir : Path
        youtube_transcript のデータルートディレクトリ。

    Examples
    --------
    >>> from pathlib import Path
    >>> engine = SearchEngine(data_dir=Path("data/raw/youtube_transcript"))
    >>> results = engine.search("利上げ")
    >>> for r in results:
    ...     print(r.video_id, r.timestamp, r.matched_text)
    """

    def __init__(self, data_dir: Path) -> None:
        """SearchEngine を初期化する.

        Parameters
        ----------
        data_dir : Path
            youtube_transcript データディレクトリのルートパス。

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

        self._data_dir = data_dir

        logger.debug("SearchEngine initialized", data_dir=str(data_dir))

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        channel_ids: list[str] | None = None,
    ) -> list[SearchResult]:
        """保存済みトランスクリプトを横断検索する.

        Parameters
        ----------
        query : str
            検索キーワード（空文字列の場合は空リストを返す）。
        channel_ids : list[str] | None, optional
            検索対象のチャンネル ID リスト。
            ``None`` または空リストの場合は全チャンネルを対象にする。

        Returns
        -------
        list[SearchResult]
            マッチした :class:`SearchResult` のリスト。
            マッチがない場合は空リスト。

        Examples
        --------
        >>> engine = SearchEngine(data_dir=Path("data/raw/youtube_transcript"))
        >>> results = engine.search("金利")
        >>> print(len(results))
        """
        if not query:
            logger.debug("空クエリのため検索スキップ")
            return []

        query_lower = query.lower()

        logger.debug(
            "SearchEngine: 検索開始",
            query=query,
            channel_ids=channel_ids,
        )

        results: list[SearchResult] = []

        # data_dir 直下のサブディレクトリがチャンネルディレクトリ
        channel_dirs = self._get_channel_dirs(channel_ids)

        for channel_dir in channel_dirs:
            channel_id = channel_dir.name
            channel_results = self._search_channel(channel_dir, channel_id, query_lower)
            results.extend(channel_results)

        logger.info(
            "SearchEngine: 検索完了",
            query=query,
            result_count=len(results),
        )

        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_channel_dirs(self, channel_ids: list[str] | None) -> list[Path]:
        """検索対象のチャンネルディレクトリリストを返す.

        Parameters
        ----------
        channel_ids : list[str] | None
            対象チャンネル ID リスト。None または空リストの場合は全チャンネル。

        Returns
        -------
        list[Path]
            存在するチャンネルディレクトリのリスト。
        """
        if not self._data_dir.exists():
            return []

        if channel_ids:
            # 指定されたチャンネルのみ
            dirs = []
            for cid in channel_ids:
                channel_dir = self._data_dir / cid
                if channel_dir.is_dir():
                    dirs.append(channel_dir)
            return dirs

        # 全チャンネルを列挙（channels.json や quota_usage.json はスキップ）
        return [d for d in self._data_dir.iterdir() if d.is_dir()]

    def _search_channel(
        self,
        channel_dir: Path,
        channel_id: str,
        query_lower: str,
    ) -> list[SearchResult]:
        """1 チャンネル内の全動画トランスクリプトを検索する.

        Parameters
        ----------
        channel_dir : Path
            チャンネルディレクトリ（{data_dir}/{channel_id}/）。
        channel_id : str
            チャンネル ID。
        query_lower : str
            小文字化済みのクエリ文字列。

        Returns
        -------
        list[SearchResult]
            マッチした SearchResult のリスト。
        """
        results: list[SearchResult] = []

        for video_dir in channel_dir.iterdir():
            if not video_dir.is_dir():
                continue

            video_id = video_dir.name
            transcript_file = video_dir / "transcript.json"

            if not transcript_file.exists():
                continue

            try:
                transcript = self._load_transcript(transcript_file)
            except Exception:
                logger.exception(
                    "トランスクリプト読み込みエラー",
                    channel_id=channel_id,
                    video_id=video_id,
                    transcript_file=str(transcript_file),
                )
                continue

            for entry in transcript.entries:
                if query_lower in entry.text.lower():
                    results.append(
                        SearchResult(
                            video_id=video_id,
                            channel_id=channel_id,
                            matched_text=entry.text,
                            timestamp=entry.start,
                        )
                    )

        return results

    @staticmethod
    def _load_transcript(transcript_file: Path) -> TranscriptResult:
        """transcript.json を読み込み TranscriptResult を返す.

        Parameters
        ----------
        transcript_file : Path
            transcript.json のパス。

        Returns
        -------
        TranscriptResult
            読み込んだトランスクリプト。

        Raises
        ------
        Exception
            読み込みまたはパースに失敗した場合。
        """
        content = transcript_file.read_text(encoding="utf-8")
        data = json.loads(content)
        entries = [TranscriptEntry(**e) for e in data.get("entries", [])]
        return TranscriptResult(
            video_id=data["video_id"],
            language=data["language"],
            entries=entries,
            fetched_at=data["fetched_at"],
        )
