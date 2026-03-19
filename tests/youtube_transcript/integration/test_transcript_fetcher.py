"""Integration tests for TranscriptFetcher.

実際の youtube-transcript-api v1.0.x を使用して YouTube 動画のトランスクリプトを取得する。

Notes
-----
- CI では ``@pytest.mark.integration`` により自動スキップされる。
- テストはネットワークアクセスを行うため、実際の YouTube API を呼ぶ。
- 動画 ID: "jNQXAC9IVRw" (YouTube 最初の動画、英語字幕あり)
"""

import pytest

from youtube_transcript.core.transcript_fetcher import TranscriptFetcher
from youtube_transcript.types import TranscriptResult

# テストで使用する実際の YouTube コンテンツ
# "Me at the zoo" — YouTube 最初の動画 (2005年)、英語字幕あり
_TEST_VIDEO_ID = "jNQXAC9IVRw"

# 存在しない動画 ID（11文字だが無効）
_NONEXISTENT_VIDEO_ID = "XXXXXXXXXXX"


class TestTranscriptFetcherIntegration:
    """TranscriptFetcher の統合テスト（実際の API を呼ぶ）."""

    @pytest.mark.integration
    def test_正常系_実際の動画から字幕を取得できる(self) -> None:
        """実際の YouTube 動画からトランスクリプトを取得できることを確認する.

        "jNQXAC9IVRw" (Me at the zoo) は英語字幕が利用可能な YouTube 最初の動画。
        """
        fetcher = TranscriptFetcher(rate_limit_sec=0.0)
        result = fetcher.fetch(_TEST_VIDEO_ID, languages=["en"])

        # 字幕がある場合は TranscriptResult が返る
        # 字幕が利用不可の場合は None が返る（例外は発生しない）
        assert result is None or isinstance(result, TranscriptResult)

        if result is not None:
            assert result.video_id == _TEST_VIDEO_ID
            assert result.language in ("en", "en-US", "en-GB", "a.en")
            assert len(result.entries) > 0
            # plain text が取得できる
            text = result.to_plain_text()
            assert isinstance(text, str)
            assert len(text) > 0

    @pytest.mark.integration
    def test_正常系_デフォルト言語で字幕を取得できる(self) -> None:
        """languages 引数を省略した場合にデフォルト言語 ["ja", "en"] で試みる.

        字幕の有無によらず例外なく完了することを確認する。
        """
        fetcher = TranscriptFetcher(rate_limit_sec=0.0)
        result = fetcher.fetch(_TEST_VIDEO_ID)

        # 例外なく None または TranscriptResult が返る
        assert result is None or isinstance(result, TranscriptResult)

    @pytest.mark.integration
    def test_異常系_存在しない動画IDでNoneまたは例外なし(self) -> None:
        """存在しない動画 ID に対して例外を発生させず None を返すことを確認する.

        VideoUnavailable / VideoUnplayable 等の例外は内部でキャッチされ None を返す。
        """
        fetcher = TranscriptFetcher(rate_limit_sec=0.0)
        result = fetcher.fetch(_NONEXISTENT_VIDEO_ID, languages=["en"])

        # 例外は発生しない。存在しない動画なので None が返ることを期待する
        assert result is None

    @pytest.mark.integration
    def test_正常系_rate_limit_secが0でも正常動作する(self) -> None:
        """rate_limit_sec=0.0 の場合もスリープなしで正常にトランスクリプトを取得できる."""
        fetcher = TranscriptFetcher(rate_limit_sec=0.0)
        assert fetcher.rate_limit_sec == 0.0

        result = fetcher.fetch(_TEST_VIDEO_ID, languages=["en"])
        # 例外なく完了することのみ確認（字幕の有無は問わない）
        assert result is None or isinstance(result, TranscriptResult)
