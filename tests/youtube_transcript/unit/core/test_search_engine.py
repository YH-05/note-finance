"""Unit tests for SearchEngine (トランスクリプト横断検索)."""

from pathlib import Path

import pytest

from youtube_transcript.core.search_engine import SearchEngine, SearchResult
from youtube_transcript.types import TranscriptEntry, TranscriptResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_transcript(
    video_id: str,
    channel_id: str,
    texts: list[str],
    starts: list[float] | None = None,
    language: str = "ja",
) -> TranscriptResult:
    """Helper: TranscriptResult を作成する."""
    if starts is None:
        starts = [float(i * 2) for i in range(len(texts))]
    entries = [
        TranscriptEntry(start=s, duration=2.0, text=t)
        for s, t in zip(starts, texts, strict=True)
    ]
    return TranscriptResult(
        video_id=video_id,
        language=language,
        entries=entries,
        fetched_at="2026-03-18T00:00:00+00:00",
    )


def setup_storage(
    tmp_path: Path, transcripts: list[tuple[str, TranscriptResult]]
) -> None:
    """チャンネルID + TranscriptResult のペアを storage 形式でディスクに書く."""
    import json
    from dataclasses import asdict

    for channel_id, tr in transcripts:
        video_dir = tmp_path / channel_id / tr.video_id
        video_dir.mkdir(parents=True, exist_ok=True)
        data = asdict(tr)
        (video_dir / "transcript.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


# ---------------------------------------------------------------------------
# SearchResult dataclass
# ---------------------------------------------------------------------------


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_正常系_SearchResultを生成できる(self) -> None:
        sr = SearchResult(
            video_id="abc1234",
            channel_id="UC_test",
            matched_text="テスト",
            timestamp=1.5,
        )
        assert sr.video_id == "abc1234"
        assert sr.channel_id == "UC_test"
        assert sr.matched_text == "テスト"
        assert sr.timestamp == pytest.approx(1.5)


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


class TestSearchEngineInit:
    """Tests for SearchEngine initialization."""

    def test_正常系_data_dirを指定して初期化できる(self, tmp_path: Path) -> None:
        engine = SearchEngine(data_dir=tmp_path)
        assert engine is not None

    def test_異常系_無効なdata_dirでValueError(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            SearchEngine(data_dir="not_a_path")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Search basic
# ---------------------------------------------------------------------------


class TestSearchEngineSearch:
    """Tests for SearchEngine.search() basic functionality."""

    def test_正常系_キーワードにマッチするエントリを返す(self, tmp_path: Path) -> None:
        tr = make_transcript(
            "abc1234",
            "UC_test",
            [
                "日銀が利上げを決定しました",
                "株価が上昇しています",
                "円高が進んでいます",
            ],
        )
        setup_storage(tmp_path, [("UC_test", tr)])

        engine = SearchEngine(data_dir=tmp_path)
        results = engine.search("利上げ")

        assert len(results) >= 1
        assert any("利上げ" in r.matched_text for r in results)

    def test_正常系_マッチしない場合は空リストを返す(self, tmp_path: Path) -> None:
        tr = make_transcript("abc1234", "UC_test", ["日銀が利上げを決定しました"])
        setup_storage(tmp_path, [("UC_test", tr)])

        engine = SearchEngine(data_dir=tmp_path)
        results = engine.search("存在しないキーワードXYZ")

        assert results == []

    def test_正常系_複数動画を横断検索できる(self, tmp_path: Path) -> None:
        tr1 = make_transcript("vid1111", "UC_test", ["利上げの影響"])
        tr2 = make_transcript("vid2222", "UC_test", ["利上げと株価の関係"])
        tr3 = make_transcript("vid3333", "UC_test", ["無関係のコンテンツ"])
        setup_storage(
            tmp_path,
            [("UC_test", tr1), ("UC_test", tr2), ("UC_test", tr3)],
        )

        engine = SearchEngine(data_dir=tmp_path)
        results = engine.search("利上げ")

        video_ids = {r.video_id for r in results}
        assert "vid1111" in video_ids
        assert "vid2222" in video_ids
        assert "vid3333" not in video_ids

    def test_正常系_SearchResultにvideo_idが含まれる(self, tmp_path: Path) -> None:
        tr = make_transcript("xyz9999", "UC_ch1", ["テスト発言"])
        setup_storage(tmp_path, [("UC_ch1", tr)])

        engine = SearchEngine(data_dir=tmp_path)
        results = engine.search("テスト")

        assert len(results) >= 1
        assert results[0].video_id == "xyz9999"

    def test_正常系_SearchResultにchannel_idが含まれる(self, tmp_path: Path) -> None:
        tr = make_transcript("xyz9999", "UC_ch1", ["テスト発言"])
        setup_storage(tmp_path, [("UC_ch1", tr)])

        engine = SearchEngine(data_dir=tmp_path)
        results = engine.search("テスト")

        assert len(results) >= 1
        assert results[0].channel_id == "UC_ch1"

    def test_正常系_SearchResultにtimestampが含まれる(self, tmp_path: Path) -> None:
        tr = make_transcript("xyz9999", "UC_ch1", ["テスト発言"], starts=[5.0])
        setup_storage(tmp_path, [("UC_ch1", tr)])

        engine = SearchEngine(data_dir=tmp_path)
        results = engine.search("テスト")

        assert len(results) >= 1
        assert results[0].timestamp == pytest.approx(5.0)

    def test_正常系_data_dirが空でも空リストを返す(self, tmp_path: Path) -> None:
        engine = SearchEngine(data_dir=tmp_path)
        results = engine.search("キーワード")

        assert results == []


# ---------------------------------------------------------------------------
# channel_ids filter
# ---------------------------------------------------------------------------


class TestSearchEngineChannelFilter:
    """Tests for SearchEngine.search() channel_ids filter."""

    def test_正常系_channel_idsフィルタが機能する(self, tmp_path: Path) -> None:
        tr_a = make_transcript("vid_a", "UC_a", ["利上げ情報"])
        tr_b = make_transcript("vid_b", "UC_b", ["利上げ考察"])
        setup_storage(tmp_path, [("UC_a", tr_a), ("UC_b", tr_b)])

        engine = SearchEngine(data_dir=tmp_path)
        results = engine.search("利上げ", channel_ids=["UC_a"])

        channel_ids_found = {r.channel_id for r in results}
        assert "UC_a" in channel_ids_found
        assert "UC_b" not in channel_ids_found

    def test_正常系_channel_ids空リストは全チャンネルを検索する(
        self, tmp_path: Path
    ) -> None:
        tr_a = make_transcript("vid_a", "UC_a", ["利上げ情報"])
        tr_b = make_transcript("vid_b", "UC_b", ["利上げ考察"])
        setup_storage(tmp_path, [("UC_a", tr_a), ("UC_b", tr_b)])

        engine = SearchEngine(data_dir=tmp_path)
        results = engine.search("利上げ", channel_ids=[])

        channel_ids_found = {r.channel_id for r in results}
        assert "UC_a" in channel_ids_found
        assert "UC_b" in channel_ids_found

    def test_正常系_channel_idsがNoneは全チャンネルを検索する(
        self, tmp_path: Path
    ) -> None:
        tr_a = make_transcript("vid_a", "UC_a", ["利上げ情報"])
        tr_b = make_transcript("vid_b", "UC_b", ["利上げ考察"])
        setup_storage(tmp_path, [("UC_a", tr_a), ("UC_b", tr_b)])

        engine = SearchEngine(data_dir=tmp_path)
        results = engine.search("利上げ", channel_ids=None)

        channel_ids_found = {r.channel_id for r in results}
        assert "UC_a" in channel_ids_found
        assert "UC_b" in channel_ids_found

    def test_正常系_存在しないchannel_idは空リストを返す(self, tmp_path: Path) -> None:
        tr_a = make_transcript("vid_a", "UC_a", ["利上げ情報"])
        setup_storage(tmp_path, [("UC_a", tr_a)])

        engine = SearchEngine(data_dir=tmp_path)
        results = engine.search("利上げ", channel_ids=["UC_nonexistent"])

        assert results == []


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestSearchEngineEdgeCases:
    """Edge case tests for SearchEngine."""

    def test_エッジケース_大文字小文字を区別しない検索(self, tmp_path: Path) -> None:
        tr = make_transcript("vid1", "UC_en", ["The Fed raised interest rates"])
        setup_storage(tmp_path, [("UC_en", tr)])

        engine = SearchEngine(data_dir=tmp_path)
        results_lower = engine.search("fed")
        results_upper = engine.search("FED")

        # 少なくとも一方がマッチすること（大文字小文字非感知実装の場合は両方）
        assert len(results_lower) > 0 or len(results_upper) > 0

    def test_エッジケース_空クエリは空リストを返す(self, tmp_path: Path) -> None:
        tr = make_transcript("vid1", "UC_test", ["日銀利上げ"])
        setup_storage(tmp_path, [("UC_test", tr)])

        engine = SearchEngine(data_dir=tmp_path)
        results = engine.search("")

        assert results == []

    def test_エッジケース_部分一致で検索できる(self, tmp_path: Path) -> None:
        tr = make_transcript("vid1", "UC_test", ["日銀が政策金利を引き上げました"])
        setup_storage(tmp_path, [("UC_test", tr)])

        engine = SearchEngine(data_dir=tmp_path)
        results = engine.search("政策金利")

        assert len(results) >= 1
