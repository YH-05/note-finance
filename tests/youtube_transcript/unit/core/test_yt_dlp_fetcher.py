"""Unit tests for YtDlpFetcher (yt-dlp フォールバック)."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from youtube_transcript.core.yt_dlp_fetcher import YtDlpFetcher
from youtube_transcript.types import TranscriptEntry, TranscriptResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_vtt_content() -> str:
    """Return minimal WebVTT subtitle content."""
    return """\
WEBVTT
Kind: captions
Language: ja

00:00:00.000 --> 00:00:02.500
こんにちは

00:00:02.500 --> 00:00:04.000
世界
"""


def make_srv3_content() -> str:
    """Return minimal SRV3/ttml subtitle content."""
    return """<?xml version="1.0" encoding="utf-8"?>
<timedtext format="3">
<head>
<ws id="0"/>
<wp id="1" ah="20" av="100" justify="0" style=""/>
</head>
<body>
<p t="0" d="2500" ws="0" wp="1">こんにちは</p>
<p t="2500" d="1500" ws="0" wp="1">世界</p>
</body>
</timedtext>
"""


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


class TestYtDlpFetcherInit:
    """Tests for YtDlpFetcher initialization."""

    def test_正常系_デフォルト設定で初期化できる(self) -> None:
        fetcher = YtDlpFetcher()
        assert fetcher is not None

    def test_正常系_tmpdir指定で初期化できる(self, tmp_path: Path) -> None:
        fetcher = YtDlpFetcher(tmp_dir=tmp_path)
        assert fetcher is not None

    def test_正常系_timeout指定で初期化できる(self) -> None:
        fetcher = YtDlpFetcher(timeout=60)
        assert fetcher.timeout == 60


# ---------------------------------------------------------------------------
# yt-dlp 未インストール時の動作
# ---------------------------------------------------------------------------


class TestYtDlpFetcherNotInstalled:
    """Tests for YtDlpFetcher when yt-dlp is not installed."""

    def test_正常系_ytdlp未インストール時にNoneを返す(self, tmp_path: Path) -> None:
        """yt-dlp が存在しない場合は例外にならず None を返す."""
        fetcher = YtDlpFetcher(tmp_dir=tmp_path)
        with patch.object(
            fetcher,
            "_is_ytdlp_available",
            return_value=False,
        ):
            result = fetcher.fetch("abc1234", languages=["ja", "en"])
        assert result is None

    def test_正常系_ytdlp未インストール時に例外にならない(self, tmp_path: Path) -> None:
        """yt-dlp がない環境でも例外を raise しない."""
        fetcher = YtDlpFetcher(tmp_dir=tmp_path)
        with patch.object(
            fetcher,
            "_is_ytdlp_available",
            return_value=False,
        ):
            result = fetcher.fetch("abc1234")
        assert result is None  # 例外なし、None が返る


# ---------------------------------------------------------------------------
# Successful fetch
# ---------------------------------------------------------------------------


class TestYtDlpFetcherFetchSuccess:
    """Tests for YtDlpFetcher.fetch() on successful paths."""

    def test_正常系_TranscriptResultを返す(self, tmp_path: Path) -> None:
        fetcher = YtDlpFetcher(tmp_dir=tmp_path)

        vtt_content = make_vtt_content()

        with (
            patch.object(fetcher, "_is_ytdlp_available", return_value=True),
            patch.object(
                fetcher,
                "_run_ytdlp",
                return_value=vtt_content,
            ),
        ):
            result = fetcher.fetch("abc1234", languages=["ja", "en"])

        assert isinstance(result, TranscriptResult)

    def test_正常系_video_idが正しく設定される(self, tmp_path: Path) -> None:
        fetcher = YtDlpFetcher(tmp_dir=tmp_path)
        vtt_content = make_vtt_content()

        with (
            patch.object(fetcher, "_is_ytdlp_available", return_value=True),
            patch.object(fetcher, "_run_ytdlp", return_value=vtt_content),
        ):
            result = fetcher.fetch("abc1234", languages=["ja"])

        assert result is not None
        assert result.video_id == "abc1234"

    def test_正常系_entriesが変換される(self, tmp_path: Path) -> None:
        fetcher = YtDlpFetcher(tmp_dir=tmp_path)
        vtt_content = make_vtt_content()

        with (
            patch.object(fetcher, "_is_ytdlp_available", return_value=True),
            patch.object(fetcher, "_run_ytdlp", return_value=vtt_content),
        ):
            result = fetcher.fetch("abc1234", languages=["ja"])

        assert result is not None
        assert len(result.entries) >= 1
        assert all(isinstance(e, TranscriptEntry) for e in result.entries)

    def test_正常系_テキストが抽出される(self, tmp_path: Path) -> None:
        fetcher = YtDlpFetcher(tmp_dir=tmp_path)
        vtt_content = make_vtt_content()

        with (
            patch.object(fetcher, "_is_ytdlp_available", return_value=True),
            patch.object(fetcher, "_run_ytdlp", return_value=vtt_content),
        ):
            result = fetcher.fetch("abc1234", languages=["ja"])

        assert result is not None
        texts = [e.text for e in result.entries]
        assert "こんにちは" in texts

    def test_正常系_fetched_atがISO8601形式の文字列になる(self, tmp_path: Path) -> None:
        fetcher = YtDlpFetcher(tmp_dir=tmp_path)
        vtt_content = make_vtt_content()

        with (
            patch.object(fetcher, "_is_ytdlp_available", return_value=True),
            patch.object(fetcher, "_run_ytdlp", return_value=vtt_content),
        ):
            result = fetcher.fetch("abc1234", languages=["ja"])

        assert result is not None
        assert isinstance(result.fetched_at, str)
        assert "T" in result.fetched_at

    def test_正常系_languageが設定される(self, tmp_path: Path) -> None:
        fetcher = YtDlpFetcher(tmp_dir=tmp_path)
        vtt_content = make_vtt_content()

        with (
            patch.object(fetcher, "_is_ytdlp_available", return_value=True),
            patch.object(fetcher, "_run_ytdlp", return_value=vtt_content),
        ):
            result = fetcher.fetch("abc1234", languages=["ja"])

        assert result is not None
        assert result.language != ""


# ---------------------------------------------------------------------------
# Failure cases → None
# ---------------------------------------------------------------------------


class TestYtDlpFetcherFetchFailure:
    """Tests for YtDlpFetcher.fetch() on failure paths."""

    def test_正常系_字幕なし時にNoneを返す(self, tmp_path: Path) -> None:
        """yt-dlp が字幕なしで終了した場合は None を返す."""
        fetcher = YtDlpFetcher(tmp_dir=tmp_path)

        with (
            patch.object(fetcher, "_is_ytdlp_available", return_value=True),
            patch.object(fetcher, "_run_ytdlp", return_value=None),
        ):
            result = fetcher.fetch("abc1234", languages=["ja"])

        assert result is None

    def test_正常系_subprocess失敗時にNoneを返す(self, tmp_path: Path) -> None:
        """yt-dlp が非ゼロ終了コードで終了した場合は None を返す."""
        fetcher = YtDlpFetcher(tmp_dir=tmp_path)

        with (
            patch.object(fetcher, "_is_ytdlp_available", return_value=True),
            patch.object(
                fetcher,
                "_run_ytdlp",
                side_effect=subprocess.CalledProcessError(1, "yt-dlp"),
            ),
        ):
            result = fetcher.fetch("abc1234", languages=["ja"])

        assert result is None

    def test_正常系_タイムアウト時にNoneを返す(self, tmp_path: Path) -> None:
        """yt-dlp がタイムアウトした場合は None を返す."""
        fetcher = YtDlpFetcher(tmp_dir=tmp_path)

        with (
            patch.object(fetcher, "_is_ytdlp_available", return_value=True),
            patch.object(
                fetcher,
                "_run_ytdlp",
                side_effect=subprocess.TimeoutExpired("yt-dlp", 30),
            ),
        ):
            result = fetcher.fetch("abc1234", languages=["ja"])

        assert result is None


# ---------------------------------------------------------------------------
# VTT parsing
# ---------------------------------------------------------------------------


class TestYtDlpFetcherVttParsing:
    """Tests for WebVTT parsing logic."""

    def test_正常系_VTTを正しくパースできる(self, tmp_path: Path) -> None:
        fetcher = YtDlpFetcher(tmp_dir=tmp_path)
        vtt_content = make_vtt_content()

        entries = fetcher._parse_vtt(vtt_content)

        assert len(entries) == 2
        assert entries[0].text == "こんにちは"
        assert entries[0].start == 0.0
        assert entries[1].text == "世界"
        assert entries[1].start == pytest.approx(2.5, abs=0.01)

    def test_正常系_空VTTで空リストを返す(self, tmp_path: Path) -> None:
        fetcher = YtDlpFetcher(tmp_dir=tmp_path)

        entries = fetcher._parse_vtt("WEBVTT\n\n")

        assert entries == []

    def test_正常系_重複行を除去する(self, tmp_path: Path) -> None:
        """VTT に同一テキストの連続エントリがある場合、重複を除去する."""
        fetcher = YtDlpFetcher(tmp_dir=tmp_path)
        vtt_duplicated = """\
WEBVTT

00:00:00.000 --> 00:00:02.000
テキスト

00:00:01.000 --> 00:00:03.000
テキスト

00:00:03.000 --> 00:00:05.000
別テキスト
"""
        entries = fetcher._parse_vtt(vtt_duplicated)
        texts = [e.text for e in entries]
        # 連続する重複 "テキスト" はひとつにまとまる
        assert texts.count("テキスト") == 1
        assert "別テキスト" in texts
