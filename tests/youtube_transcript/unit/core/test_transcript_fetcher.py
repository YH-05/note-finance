"""Unit tests for TranscriptFetcher."""

import os
from unittest.mock import MagicMock, patch

import pytest

from youtube_transcript.core.transcript_fetcher import TranscriptFetcher
from youtube_transcript.types import TranscriptEntry, TranscriptResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_mock_fetched_transcript(
    video_id: str = "abc1234",
    language: str = "Japanese",
    language_code: str = "ja",
    is_generated: bool = False,
    snippets: list[dict] | None = None,
) -> MagicMock:
    """Return a mock FetchedTranscript matching the 1.0.x API."""
    if snippets is None:
        snippets = [
            {"text": "こんにちは", "start": 0.0, "duration": 2.5},
            {"text": "世界", "start": 2.5, "duration": 1.5},
        ]

    mock_snippets = []
    for s in snippets:
        snippet = MagicMock()
        snippet.text = s["text"]
        snippet.start = s["start"]
        snippet.duration = s["duration"]
        mock_snippets.append(snippet)

    mock_transcript = MagicMock()
    mock_transcript.video_id = video_id
    mock_transcript.language = language
    mock_transcript.language_code = language_code
    mock_transcript.is_generated = is_generated
    mock_transcript.snippets = mock_snippets
    mock_transcript.__iter__ = lambda self: iter(self.snippets)
    mock_transcript.__len__ = lambda self: len(self.snippets)
    return mock_transcript


def make_fetcher_with_mock(
    mock_ft: MagicMock,
    rate_limit_sec: float = 0.0,
) -> tuple[TranscriptFetcher, MagicMock]:
    """Return (fetcher, mock_api) with mock_api.fetch returning mock_ft."""
    mock_api = MagicMock()
    mock_api.fetch.return_value = mock_ft
    fetcher = TranscriptFetcher(rate_limit_sec=rate_limit_sec, _api=mock_api)
    return fetcher, mock_api


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


class TestTranscriptFetcherInit:
    """Tests for TranscriptFetcher initialization."""

    def test_正常系_デフォルト設定で初期化できる(self) -> None:
        fetcher = TranscriptFetcher()
        assert fetcher is not None

    def test_正常系_カスタムレート制限で初期化できる(self) -> None:
        fetcher = TranscriptFetcher(rate_limit_sec=2.0)
        assert fetcher.rate_limit_sec == 2.0

    def test_正常系_環境変数でレート制限を設定できる(self) -> None:
        with patch.dict(os.environ, {"YT_TRANSCRIPT_RATE_LIMIT": "3.0"}):
            fetcher = TranscriptFetcher()
        assert fetcher.rate_limit_sec == 3.0

    def test_正常系_環境変数未設定時はデフォルト1秒(self) -> None:
        env_without_limit = {
            k: v for k, v in os.environ.items() if k != "YT_TRANSCRIPT_RATE_LIMIT"
        }
        with patch.dict(os.environ, env_without_limit, clear=True):
            fetcher = TranscriptFetcher()
        assert fetcher.rate_limit_sec == 1.0

    def test_エッジケース_rate_limit_secが0でも初期化できる(self) -> None:
        fetcher = TranscriptFetcher(rate_limit_sec=0.0)
        assert fetcher.rate_limit_sec == 0.0


# ---------------------------------------------------------------------------
# Successful fetch
# ---------------------------------------------------------------------------


class TestTranscriptFetcherFetchSuccess:
    """Tests for TranscriptFetcher.fetch() on successful paths."""

    def test_正常系_TranscriptResultを返す(self) -> None:
        mock_ft = make_mock_fetched_transcript()
        fetcher, _ = make_fetcher_with_mock(mock_ft)

        result = fetcher.fetch("abc1234", languages=["ja", "en"])

        assert isinstance(result, TranscriptResult)

    def test_正常系_video_idが正しく設定される(self) -> None:
        mock_ft = make_mock_fetched_transcript(video_id="xyz9999")
        fetcher, _ = make_fetcher_with_mock(mock_ft)

        result = fetcher.fetch("xyz9999", languages=["ja"])

        assert result is not None
        assert result.video_id == "xyz9999"

    def test_正常系_language_codeが正しく設定される(self) -> None:
        mock_ft = make_mock_fetched_transcript(language_code="en")
        fetcher, _ = make_fetcher_with_mock(mock_ft)

        result = fetcher.fetch("abc1234", languages=["en"])

        assert result is not None
        assert result.language == "en"

    def test_正常系_snippetがTranscriptEntryに変換される(self) -> None:
        mock_ft = make_mock_fetched_transcript(
            snippets=[{"text": "Hello", "start": 0.0, "duration": 2.0}]
        )
        fetcher, _ = make_fetcher_with_mock(mock_ft)

        result = fetcher.fetch("abc1234", languages=["en"])

        assert result is not None
        assert len(result.entries) == 1
        entry = result.entries[0]
        assert isinstance(entry, TranscriptEntry)
        assert entry.text == "Hello"
        assert entry.start == 0.0
        assert entry.duration == 2.0

    def test_正常系_複数snippetが全て変換される(self) -> None:
        snippets = [
            {"text": "First", "start": 0.0, "duration": 1.0},
            {"text": "Second", "start": 1.0, "duration": 1.5},
            {"text": "Third", "start": 2.5, "duration": 2.0},
        ]
        mock_ft = make_mock_fetched_transcript(snippets=snippets)
        fetcher, _ = make_fetcher_with_mock(mock_ft)

        result = fetcher.fetch("abc1234", languages=["en"])

        assert result is not None
        assert len(result.entries) == 3
        assert result.entries[0].text == "First"
        assert result.entries[1].text == "Second"
        assert result.entries[2].text == "Third"

    def test_正常系_fetched_atがISO8601形式の文字列になる(self) -> None:
        mock_ft = make_mock_fetched_transcript()
        fetcher, _ = make_fetcher_with_mock(mock_ft)

        result = fetcher.fetch("abc1234", languages=["ja"])

        assert result is not None
        # Should be a non-empty ISO 8601 string like "2026-03-18T12:00:00+00:00"
        assert isinstance(result.fetched_at, str)
        assert len(result.fetched_at) > 0
        assert "T" in result.fetched_at

    def test_正常系_languagesパラメータがAPIに渡される(self) -> None:
        mock_ft = make_mock_fetched_transcript()
        fetcher, mock_api = make_fetcher_with_mock(mock_ft)

        fetcher.fetch("abc1234", languages=["ja", "en"])

        mock_api.fetch.assert_called_once_with("abc1234", languages=["ja", "en"])

    def test_正常系_デフォルトlanguagesはja_en順(self) -> None:
        mock_ft = make_mock_fetched_transcript()
        fetcher, mock_api = make_fetcher_with_mock(mock_ft)

        fetcher.fetch("abc1234")

        call_kwargs = mock_api.fetch.call_args
        languages_used = call_kwargs.kwargs.get(
            "languages",
            call_kwargs.args[1] if len(call_kwargs.args) > 1 else [],
        )
        assert "ja" in languages_used
        assert languages_used.index("ja") < languages_used.index("en")


# ---------------------------------------------------------------------------
# Unavailable transcript → None
# ---------------------------------------------------------------------------


class TestTranscriptFetcherFetchUnavailable:
    """Tests for TranscriptFetcher.fetch() on unavailable transcript paths."""

    def test_正常系_NoTranscriptFoundでNoneを返す(self) -> None:
        from youtube_transcript_api._errors import NoTranscriptFound

        mock_api = MagicMock()
        mock_api.fetch.side_effect = NoTranscriptFound(
            "abc1234", ["ja", "en"], MagicMock()
        )
        fetcher = TranscriptFetcher(rate_limit_sec=0.0, _api=mock_api)

        result = fetcher.fetch("abc1234", languages=["ja", "en"])

        assert result is None

    def test_正常系_TranscriptsDisabledでNoneを返す(self) -> None:
        from youtube_transcript_api._errors import TranscriptsDisabled

        mock_api = MagicMock()
        mock_api.fetch.side_effect = TranscriptsDisabled("abc1234")
        fetcher = TranscriptFetcher(rate_limit_sec=0.0, _api=mock_api)

        result = fetcher.fetch("abc1234", languages=["ja"])

        assert result is None

    def test_正常系_VideoUnavailableでNoneを返す(self) -> None:
        from youtube_transcript_api._errors import VideoUnavailable

        mock_api = MagicMock()
        mock_api.fetch.side_effect = VideoUnavailable("abc1234")
        fetcher = TranscriptFetcher(rate_limit_sec=0.0, _api=mock_api)

        result = fetcher.fetch("abc1234", languages=["ja"])

        assert result is None

    def test_正常系_VideoUnplayableでNoneを返す(self) -> None:
        from youtube_transcript_api._errors import VideoUnplayable

        mock_api = MagicMock()
        mock_api.fetch.side_effect = VideoUnplayable(
            "abc1234", reason="restricted", sub_reasons=[]
        )
        fetcher = TranscriptFetcher(rate_limit_sec=0.0, _api=mock_api)

        result = fetcher.fetch("abc1234", languages=["ja"])

        assert result is None


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


class TestTranscriptFetcherRateLimit:
    """Tests for TranscriptFetcher rate limiting behaviour."""

    def test_正常系_レート制限が機能する(self) -> None:
        """Fetcher sleeps for approximately rate_limit_sec between calls."""
        mock_ft = make_mock_fetched_transcript()
        mock_api = MagicMock()
        mock_api.fetch.return_value = mock_ft
        fetcher = TranscriptFetcher(rate_limit_sec=0.05, _api=mock_api)

        with patch("time.sleep") as mock_sleep:
            fetcher.fetch("abc1234", languages=["ja"])
            fetcher.fetch("bbb5678", languages=["ja"])

        # sleep should be called at least once between requests
        assert mock_sleep.called

    def test_正常系_レート制限0秒ではsleepしない(self) -> None:
        """No sleep when rate_limit_sec is 0."""
        mock_ft = make_mock_fetched_transcript()
        fetcher, _ = make_fetcher_with_mock(mock_ft, rate_limit_sec=0.0)

        with patch("time.sleep") as mock_sleep:
            fetcher.fetch("abc1234", languages=["ja"])

        mock_sleep.assert_not_called()

    def test_正常系_初回fetchはsleepしない(self) -> None:
        """First fetch never sleeps (no previous call to delay after)."""
        mock_ft = make_mock_fetched_transcript()
        fetcher, _ = make_fetcher_with_mock(mock_ft, rate_limit_sec=1.0)

        with patch("time.sleep") as mock_sleep:
            fetcher.fetch("abc1234", languages=["ja"])

        mock_sleep.assert_not_called()

    def test_正常系_2回目fetchでsleepが呼ばれる(self) -> None:
        """Second fetch triggers a sleep."""
        mock_ft = make_mock_fetched_transcript()
        fetcher, _ = make_fetcher_with_mock(mock_ft, rate_limit_sec=1.0)

        with patch("time.sleep") as mock_sleep:
            fetcher.fetch("abc1234", languages=["ja"])
            fetcher.fetch("bbb5678", languages=["ja"])

        assert mock_sleep.call_count >= 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestTranscriptFetcherEdgeCases:
    """Edge case tests for TranscriptFetcher.fetch()."""

    def test_エッジケース_空のsnippetリストでemptyentriesを返す(self) -> None:
        mock_ft = make_mock_fetched_transcript(snippets=[])
        fetcher, _ = make_fetcher_with_mock(mock_ft)

        result = fetcher.fetch("abc1234", languages=["ja"])

        assert result is not None
        assert result.entries == []

    def test_エッジケース_自動生成字幕も正常に取得できる(self) -> None:
        mock_ft = make_mock_fetched_transcript(is_generated=True)
        fetcher, _ = make_fetcher_with_mock(mock_ft)

        result = fetcher.fetch("abc1234", languages=["ja"])

        assert result is not None
        assert isinstance(result, TranscriptResult)
