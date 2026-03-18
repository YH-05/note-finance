"""YtDlpFetcher: yt-dlp を使用したトランスクリプト取得フォールバック.

youtube-transcript-api でトランスクリプトが取得できない場合の代替手段として
yt-dlp を subprocess で呼び出し、VTT 形式の字幕を取得・解析する。

yt-dlp 未インストール時は None を返し、例外を発生させない。
"""

import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from youtube_transcript._logging import get_logger
from youtube_transcript.types import TranscriptEntry, TranscriptResult

logger = get_logger(__name__)

_DEFAULT_TIMEOUT_SEC = 60
_DEFAULT_LANGUAGES = ["ja", "en"]

# VTT タイムスタンプ行のパターン: HH:MM:SS.mmm --> HH:MM:SS.mmm
_TIMESTAMP_RE = re.compile(
    r"^(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})\.(\d{3})"
)


def _vtt_time_to_seconds(h: str, m: str, s: str, ms: str) -> float:
    """VTT タイムスタンプ文字列を秒数に変換する."""
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


class YtDlpFetcher:
    """yt-dlp を使用したトランスクリプト取得フォールバック.

    youtube-transcript-api が字幕を取得できない動画に対して
    yt-dlp を subprocess 経由で呼び出し、VTT 字幕ファイルを取得する。

    Parameters
    ----------
    tmp_dir : Path | None, optional
        字幕ファイルを一時的に保存するディレクトリ。
        ``None`` のとき fetch() 内でシステム一時ディレクトリを使用する。
    timeout : int, optional
        yt-dlp の最大待機秒数。デフォルトは 60 秒。

    Examples
    --------
    >>> fetcher = YtDlpFetcher()
    >>> result = fetcher.fetch("dQw4w9WgXcQ", languages=["ja", "en"])
    >>> if result is not None:
    ...     print(result.to_plain_text()[:50])
    """

    def __init__(
        self,
        tmp_dir: Path | None = None,
        timeout: int = _DEFAULT_TIMEOUT_SEC,
    ) -> None:
        """YtDlpFetcher を初期化する.

        Parameters
        ----------
        tmp_dir : Path | None, optional
            字幕一時保存ディレクトリ。省略時はシステム tmp を使用。
        timeout : int, optional
            yt-dlp の実行タイムアウト秒数。
        """
        self._tmp_dir = tmp_dir
        self._timeout = timeout

        logger.debug(
            "YtDlpFetcher initialized",
            tmp_dir=str(tmp_dir) if tmp_dir else "system_tmp",
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def timeout(self) -> int:
        """yt-dlp の実行タイムアウト秒数.

        Returns
        -------
        int
            タイムアウト秒数。
        """
        return self._timeout

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def fetch(
        self,
        video_id: str,
        languages: list[str] | None = None,
    ) -> TranscriptResult | None:
        """yt-dlp を使って指定動画のトランスクリプトを取得する.

        yt-dlp が未インストールの場合や字幕なしの場合は例外を発生させず
        ``None`` を返す。

        Parameters
        ----------
        video_id : str
            YouTube 動画 ID（11 文字の英数字文字列）。
        languages : list[str] | None, optional
            優先順位の高い順に並べた言語コードのリスト。
            ``None`` のとき ``["ja", "en"]`` を使用する。

        Returns
        -------
        TranscriptResult | None
            取得に成功した場合は :class:`~youtube_transcript.types.TranscriptResult`、
            取得不可の場合は ``None``。
        """
        if languages is None:
            languages = _DEFAULT_LANGUAGES

        logger.debug(
            "YtDlpFetcher: fetch 開始",
            video_id=video_id,
            languages=languages,
        )

        if not self._is_ytdlp_available():
            logger.info(
                "yt-dlp 未インストール、フォールバック不可",
                video_id=video_id,
            )
            return None

        vtt_content = self._fetch_vtt_safe(video_id, languages)
        if vtt_content is None:
            return None

        entries = self._parse_vtt(vtt_content)
        if not entries:
            logger.info(
                "yt-dlp: VTT のパース結果が空",
                video_id=video_id,
            )
            return None

        # 言語の判定: VTT ヘッダに "Language: xx" がある場合はそれを使用
        detected_language = self._detect_language(vtt_content, languages)
        fetched_at = datetime.now(tz=timezone.utc).isoformat()

        result = TranscriptResult(
            video_id=video_id,
            language=detected_language,
            entries=entries,
            fetched_at=fetched_at,
        )

        logger.info(
            "YtDlpFetcher: fetch 完了",
            video_id=video_id,
            language=detected_language,
            entry_count=len(entries),
        )

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_vtt_safe(
        self,
        video_id: str,
        languages: list[str],
    ) -> str | None:
        """yt-dlp を呼び出して VTT コンテンツを取得する（例外をすべて捕捉）.

        Parameters
        ----------
        video_id : str
            YouTube 動画 ID。
        languages : list[str]
            試みる言語コードのリスト。

        Returns
        -------
        str | None
            VTT コンテンツ文字列、取得できない場合は ``None``。
        """
        try:
            return self._run_ytdlp(video_id, languages)
        except subprocess.CalledProcessError as exc:
            logger.info(
                "yt-dlp が非ゼロ終了コードで終了",
                video_id=video_id,
                returncode=exc.returncode,
            )
        except subprocess.TimeoutExpired:
            logger.warning(
                "yt-dlp がタイムアウト",
                video_id=video_id,
                timeout=self._timeout,
            )
        except Exception:
            logger.exception(
                "yt-dlp 実行中に予期しないエラー",
                video_id=video_id,
            )
        return None

    def _is_ytdlp_available(self) -> bool:
        """yt-dlp がシステムにインストールされているか確認する.

        Returns
        -------
        bool
            yt-dlp が利用可能な場合は ``True``。
        """
        available = shutil.which("yt-dlp") is not None
        logger.debug("yt-dlp availability check", available=available)
        return available

    def _run_ytdlp(
        self,
        video_id: str,
        languages: list[str] | None = None,
    ) -> str | None:
        """yt-dlp を実行して VTT 字幕コンテンツを返す.

        Parameters
        ----------
        video_id : str
            YouTube 動画 ID。
        languages : list[str] | None, optional
            試みる言語コードのリスト。

        Returns
        -------
        str | None
            VTT 形式の字幕文字列、取得できない場合は ``None``。

        Raises
        ------
        subprocess.CalledProcessError
            yt-dlp が非ゼロ終了コードで終了した場合。
        subprocess.TimeoutExpired
            yt-dlp がタイムアウトした場合。
        """
        if languages is None:
            languages = _DEFAULT_LANGUAGES

        video_url = f"https://www.youtube.com/watch?v={video_id}"

        # 言語を "ja,en" 形式に結合
        langs_str = ",".join(languages)

        use_tmp_dir = self._tmp_dir
        _cleanup_dir: Path | None = None

        if use_tmp_dir is None:
            _cleanup_dir = Path(tempfile.mkdtemp(prefix="yt_dlp_"))
            use_tmp_dir = _cleanup_dir

        try:
            cmd = [
                "yt-dlp",
                "--write-auto-sub",
                "--write-sub",
                f"--sub-lang={langs_str}",
                "--sub-format=vtt",
                "--skip-download",
                "--no-playlist",
                "--output",
                str(use_tmp_dir / "%(id)s.%(ext)s"),
                video_url,
            ]

            logger.debug(
                "yt-dlp コマンド実行",
                video_id=video_id,
                cmd=" ".join(cmd),
            )

            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=True,
            )

            # 生成された VTT ファイルを探す
            vtt_file = self._find_vtt_file(use_tmp_dir, video_id, languages)
            if vtt_file is None:
                return None

            content = vtt_file.read_text(encoding="utf-8")
            logger.debug(
                "yt-dlp: VTT ファイル読み込み完了",
                video_id=video_id,
                vtt_file=str(vtt_file),
                content_length=len(content),
            )
            return content

        finally:
            # 一時ディレクトリを自分で作成した場合のみクリーンアップ
            if _cleanup_dir is not None:
                import shutil as _shutil

                _shutil.rmtree(_cleanup_dir, ignore_errors=True)

    def _find_vtt_file(
        self,
        directory: Path,
        video_id: str,
        languages: list[str],
    ) -> Path | None:
        """指定ディレクトリから VTT ファイルを探す.

        言語優先度に従って最初に見つかった VTT を返す。

        Parameters
        ----------
        directory : Path
            探索するディレクトリ。
        video_id : str
            YouTube 動画 ID。
        languages : list[str]
            優先順位の高い順に並べた言語コードのリスト。

        Returns
        -------
        Path | None
            見つかった VTT ファイルのパス、見つからない場合は ``None``。
        """
        for lang in languages:
            # yt-dlp は "{video_id}.{lang}.vtt" または "{video_id}.{lang}-auto.vtt" を生成する
            candidates = [
                directory / f"{video_id}.{lang}.vtt",
                directory / f"{video_id}.{lang}-orig.vtt",
            ]
            for candidate in candidates:
                if candidate.exists():
                    logger.debug(
                        "VTT ファイル発見",
                        vtt_file=str(candidate),
                        language=lang,
                    )
                    return candidate

        # ワイルドカードでも探す
        vtt_files = list(directory.glob(f"{video_id}*.vtt"))
        if vtt_files:
            logger.debug(
                "VTT ファイル発見（ワイルドカード）",
                vtt_file=str(vtt_files[0]),
            )
            return vtt_files[0]

        logger.debug(
            "VTT ファイルが見つからない",
            video_id=video_id,
            directory=str(directory),
        )
        return None

    def _parse_vtt(self, content: str) -> list[TranscriptEntry]:
        """WebVTT コンテンツをパースして TranscriptEntry リストに変換する.

        連続する重複テキストは除去する（yt-dlp のスライドウィンドウ字幕対策）。

        Parameters
        ----------
        content : str
            WebVTT 形式の字幕文字列。

        Returns
        -------
        list[TranscriptEntry]
            パースされた :class:`~youtube_transcript.types.TranscriptEntry` のリスト。

        Examples
        --------
        >>> fetcher = YtDlpFetcher()
        >>> vtt = "WEBVTT\\n\\n00:00:00.000 --> 00:00:02.000\\nHello\\n"
        >>> entries = fetcher._parse_vtt(vtt)
        >>> entries[0].text
        'Hello'
        """
        entries: list[TranscriptEntry] = []
        lines = content.splitlines()

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            m = _TIMESTAMP_RE.match(line)
            if m:
                start_sec = _vtt_time_to_seconds(
                    m.group(1), m.group(2), m.group(3), m.group(4)
                )
                end_sec = _vtt_time_to_seconds(
                    m.group(5), m.group(6), m.group(7), m.group(8)
                )
                duration = max(0.0, end_sec - start_sec)

                # タイムスタンプ行の次から空行までがテキスト
                text_lines = []
                i += 1
                while i < len(lines) and lines[i].strip():
                    text_line = lines[i].strip()
                    # VTT タグ（<c>, <...>）や空 position 注記を除去
                    text_line = re.sub(r"<[^>]+>", "", text_line)
                    text_line = text_line.strip()
                    if text_line:
                        text_lines.append(text_line)
                    i += 1

                if text_lines:
                    text = " ".join(text_lines)
                    # 連続する重複エントリを除去
                    if not entries or entries[-1].text != text:
                        entries.append(
                            TranscriptEntry(
                                start=start_sec,
                                duration=duration,
                                text=text,
                            )
                        )
                continue
            i += 1

        logger.debug(
            "VTT パース完了",
            entry_count=len(entries),
        )
        return entries

    @staticmethod
    def _detect_language(content: str, languages: list[str]) -> str:
        """VTT コンテンツから言語コードを検出する.

        ヘッダに "Language: xx" がある場合はそれを返す。
        検出できない場合は languages の先頭を返す。

        Parameters
        ----------
        content : str
            WebVTT 形式のコンテンツ。
        languages : list[str]
            優先順位の高い順に並べた言語コードのリスト。

        Returns
        -------
        str
            検出された言語コード。
        """
        for line in content.splitlines()[:10]:
            m = re.match(r"Language:\s*(\w+)", line.strip(), re.IGNORECASE)
            if m:
                return m.group(1).lower()

        return languages[0] if languages else "unknown"
