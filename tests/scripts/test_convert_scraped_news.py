"""Unit tests for scripts/convert_scraped_news.py.

Tests cover the public API functions used by the weekly-report pipeline:
``convert``, ``_map_category``, ``_parse_published``, ``_is_in_period``,
``_build_summary``, ``_collect_raw_articles``, ``_build_by_category``,
and ``_build_statistics``.
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

# Make scripts/ importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from convert_scraped_news import (
    VALID_CATEGORIES,
    _build_by_category,
    _build_statistics,
    _build_summary,
    _collect_raw_articles,
    _is_in_period,
    _map_category,
    _parse_published,
    convert,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_article(
    *,
    title: str = "Test Article",
    url: str = "https://example.com/article",
    category: str | None = None,
    summary: str | None = "Default summary",
    content: str | None = None,
    published: str = "2026-03-01T12:00:00+00:00",
    source: str = "CNBC",
) -> dict:
    """Build a minimal scraped article dict."""
    article: dict = {
        "title": title,
        "url": url,
        "source": source,
        "published": published,
    }
    if category is not None:
        article["category"] = category
    if summary is not None:
        article["summary"] = summary
    if content is not None:
        article["content"] = content
    return article


def _make_scraped_file(path: Path, articles: list[dict]) -> Path:
    """Write a scraped JSON file in the expected format."""
    payload = {"news": articles}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Test 1: 正常系_有効なJSONで変換成功
# ---------------------------------------------------------------------------


class TestConvertValidJson:
    """Test that convert() succeeds with valid JSON input."""

    def test_正常系_有効なJSONで変換成功(self, tmp_path: Path) -> None:
        """convert() creates news_from_project.json with correct structure."""
        input_file = tmp_path / "news.json"
        output_dir = tmp_path / "output"
        articles = [
            _make_article(
                title="S&P 500 hits record",
                url="https://cnbc.com/1",
                category="investing",
                summary="S&P 500 reaches all-time high",
                published="2026-02-25T10:00:00+00:00",
            )
        ]
        _make_scraped_file(input_file, articles)

        result_path = convert(
            input_file=input_file,
            input_dir=None,
            output_dir=output_dir,
            start=date(2026, 2, 22),
            end=date(2026, 3, 1),
        )

        assert result_path.exists()
        assert result_path.name == "news_from_project.json"

        data = json.loads(result_path.read_text(encoding="utf-8"))
        assert "news" in data
        assert "by_category" in data
        assert "statistics" in data
        assert "period" in data
        assert data["total_count"] == 1
        assert data["period"]["start"] == "2026-02-22"
        assert data["period"]["end"] == "2026-03-01"

    def test_正常系_変換された記事に必須フィールドが含まれる(
        self, tmp_path: Path
    ) -> None:
        """Each converted article contains all required output fields."""
        input_file = tmp_path / "news.json"
        output_dir = tmp_path / "output"
        articles = [
            _make_article(
                title="Fed raises rates",
                url="https://cnbc.com/fed",
                category="economy",
                published="2026-02-25T08:00:00+00:00",
            )
        ]
        _make_scraped_file(input_file, articles)

        result_path = convert(
            input_file=input_file,
            input_dir=None,
            output_dir=output_dir,
            start=date(2026, 2, 22),
            end=date(2026, 3, 1),
        )

        data = json.loads(result_path.read_text(encoding="utf-8"))
        assert len(data["news"]) == 1
        article = data["news"][0]
        required_fields = {
            "issue_number",
            "title",
            "category",
            "url",
            "original_url",
            "created_at",
            "summary",
            "source",
        }
        assert required_fields.issubset(article.keys())
        assert article["issue_number"] == 1


# ---------------------------------------------------------------------------
# Test 2: 正常系_日付フィルタリングが正しく動作
# ---------------------------------------------------------------------------


class TestDateFiltering:
    """Test that date range filtering works correctly."""

    def test_正常系_日付フィルタリングが正しく動作(self, tmp_path: Path) -> None:
        """convert() only includes articles within the specified date range."""
        input_file = tmp_path / "news.json"
        output_dir = tmp_path / "output"
        articles = [
            _make_article(
                title="In range article",
                url="https://cnbc.com/inrange",
                published="2026-02-25T00:00:00+00:00",
            ),
            _make_article(
                title="Too old article",
                url="https://cnbc.com/old",
                published="2026-02-21T23:59:59+00:00",
            ),
            _make_article(
                title="Too new article",
                url="https://cnbc.com/new",
                published="2026-03-02T00:00:00+00:00",
            ),
        ]
        _make_scraped_file(input_file, articles)

        result_path = convert(
            input_file=input_file,
            input_dir=None,
            output_dir=output_dir,
            start=date(2026, 2, 22),
            end=date(2026, 3, 1),
        )

        data = json.loads(result_path.read_text(encoding="utf-8"))
        assert data["total_count"] == 1
        assert data["news"][0]["title"] == "In range article"

    def test_正常系_境界日付_開始と終了が含まれる(self, tmp_path: Path) -> None:
        """Articles published exactly on start or end date are included."""
        input_file = tmp_path / "news.json"
        output_dir = tmp_path / "output"
        articles = [
            _make_article(
                title="Start day article",
                url="https://cnbc.com/start",
                published="2026-02-22T00:00:00+00:00",
            ),
            _make_article(
                title="End day article",
                url="https://cnbc.com/end",
                published="2026-03-01T23:59:59+00:00",
            ),
        ]
        _make_scraped_file(input_file, articles)

        result_path = convert(
            input_file=input_file,
            input_dir=None,
            output_dir=output_dir,
            start=date(2026, 2, 22),
            end=date(2026, 3, 1),
        )

        data = json.loads(result_path.read_text(encoding="utf-8"))
        assert data["total_count"] == 2


# ---------------------------------------------------------------------------
# Test 3: 正常系_カテゴリマッピングが正しく変換
# ---------------------------------------------------------------------------


class TestCategoryMapping:
    """Test _map_category direct lookup and keyword fallback."""

    def test_正常系_カテゴリマッピングが正しく変換(self) -> None:
        """_map_category converts CATEGORY_MAP entries correctly."""
        assert _map_category("economy", "some title", None) == "macro"
        assert _map_category("finance", "some title", None) == "finance"
        assert _map_category("investing", "some title", None) == "indices"
        assert _map_category("earnings", "some title", None) == "mag7"
        assert _map_category("technology", "some title", None) == "tech"

    def test_正常系_NASDAQカテゴリが正しくマッピングされる(self) -> None:
        """_map_category handles NASDAQ category names."""
        assert _map_category("Markets", "some title", None) == "indices"
        assert _map_category("Economy", "some title", None) == "macro"
        assert _map_category("Technology", "some title", None) == "tech"

    def test_正常系_不明カテゴリはotherを返す(self) -> None:
        """_map_category returns 'other' for unknown categories."""
        assert _map_category("unknown_key", "Random article title", None) == "other"

    def test_正常系_結果はVALID_CATEGORIESに含まれる(self) -> None:
        """All _map_category results are in VALID_CATEGORIES."""
        test_cases = [
            ("economy", "title"),
            ("technology", "title"),
            ("unknown", "title"),
            (None, "title"),
        ]
        for category, title in test_cases:
            result = _map_category(category, title, None)
            assert result in VALID_CATEGORIES, (
                f"Result '{result}' not in VALID_CATEGORIES for category={category!r}"
            )


# ---------------------------------------------------------------------------
# Test 4: 正常系_キーワードフォールバックが動作
# ---------------------------------------------------------------------------


class TestKeywordFallback:
    """Test that keyword-based fallback mapping works when category is absent."""

    def test_正常系_キーワードフォールバックが動作(self) -> None:
        """_map_category falls back to keyword detection when category is None."""
        assert _map_category(None, "S&P 500 reaches new record", None) == "indices"
        assert _map_category(None, "Apple reports record earnings", None) == "mag7"
        assert _map_category(None, "Fed raises interest rate", None) == "macro"
        assert _map_category(None, "AI semiconductor demand surges", None) == "tech"

    def test_正常系_未知カテゴリもキーワードフォールバックが動作(self) -> None:
        """_map_category uses keywords when direct lookup fails."""
        # "unknown_key" is not in CATEGORY_MAP → keyword fallback
        result = _map_category("unknown_key", "NVDA stock price soars", None)
        assert result == "mag7"

    def test_正常系_サマリーもキーワード検索対象(self) -> None:
        """_map_category also searches the summary field."""
        result = _map_category(None, "Market update", "S&P 500 climbs higher")
        assert result == "indices"

    def test_正常系_マッチなしでotherを返す(self) -> None:
        """_map_category returns 'other' when no keyword matches."""
        result = _map_category(None, "Random unrelated title", "Some random text")
        assert result == "other"


# ---------------------------------------------------------------------------
# Test 5: 正常系_by_categoryとstatisticsが正しく生成
# ---------------------------------------------------------------------------


class TestByCategoryAndStatistics:
    """Test _build_by_category and _build_statistics."""

    def test_正常系_by_categoryとstatisticsが正しく生成(self) -> None:
        """_build_by_category groups articles and _build_statistics counts them."""
        news = [
            {"issue_number": 1, "title": "A", "category": "indices"},
            {"issue_number": 2, "title": "B", "category": "macro"},
            {"issue_number": 3, "title": "C", "category": "indices"},
        ]
        by_cat = _build_by_category(news)
        stats = _build_statistics(by_cat)

        assert len(by_cat["indices"]) == 2
        assert len(by_cat["macro"]) == 1
        assert stats["indices"] == 2
        assert stats["macro"] == 1
        assert stats["tech"] == 0

    def test_正常系_全有効カテゴリのキーが存在する(self) -> None:
        """_build_by_category always includes all VALID_CATEGORIES as keys."""
        by_cat = _build_by_category([])
        for cat in VALID_CATEGORIES:
            assert cat in by_cat

    def test_正常系_statisticsはby_categoryと一致する(self) -> None:
        """_build_statistics counts match _build_by_category lists."""
        news = [
            {"category": "finance"},
            {"category": "finance"},
            {"category": "other"},
        ]
        by_cat = _build_by_category(news)
        stats = _build_statistics(by_cat)

        for cat, articles in by_cat.items():
            assert stats[cat] == len(articles), (
                f"Mismatch for category '{cat}': stats={stats[cat]}, len={len(articles)}"
            )

    def test_正常系_不明カテゴリはotherに分類される(self) -> None:
        """_build_by_category moves unknown categories to 'other'."""
        news = [{"category": "completely_unknown_category"}]
        by_cat = _build_by_category(news)
        assert len(by_cat["other"]) == 1

    def test_正常系_convertのby_categoryとstatisticsが一致(
        self, tmp_path: Path
    ) -> None:
        """convert() output's by_category and statistics are consistent."""
        input_file = tmp_path / "news.json"
        output_dir = tmp_path / "output"
        articles = [
            _make_article(
                title="S&P 500 at record",
                url="https://cnbc.com/1",
                category="investing",
                published="2026-02-25T10:00:00+00:00",
            ),
            _make_article(
                title="Fed decision",
                url="https://cnbc.com/2",
                category="economy",
                published="2026-02-26T10:00:00+00:00",
            ),
            _make_article(
                title="Another market story",
                url="https://cnbc.com/3",
                category="investing",
                published="2026-02-27T10:00:00+00:00",
            ),
        ]
        _make_scraped_file(input_file, articles)

        result_path = convert(
            input_file=input_file,
            input_dir=None,
            output_dir=output_dir,
            start=date(2026, 2, 22),
            end=date(2026, 3, 1),
        )

        data = json.loads(result_path.read_text(encoding="utf-8"))
        by_cat = data["by_category"]
        stats = data["statistics"]

        for cat in VALID_CATEGORIES:
            assert cat in by_cat
            assert cat in stats
            assert stats[cat] == len(by_cat[cat])


# ---------------------------------------------------------------------------
# Test 6: 正常系_複数ファイルマージと重複排除
# ---------------------------------------------------------------------------


class TestMultiFileMergeAndDedup:
    """Test merging multiple JSON files and deduplication by URL."""

    def test_正常系_複数ファイルマージと重複排除(self, tmp_path: Path) -> None:
        """convert() merges multiple JSON files and deduplicates by URL."""
        input_dir = tmp_path / "inputs"
        input_dir.mkdir()
        output_dir = tmp_path / "output"

        article_a = _make_article(
            title="Unique article A",
            url="https://cnbc.com/a",
            published="2026-02-25T08:00:00+00:00",
        )
        article_b = _make_article(
            title="Unique article B",
            url="https://cnbc.com/b",
            published="2026-02-25T09:00:00+00:00",
        )
        # Duplicate of article_a in a different file
        article_a_dup = _make_article(
            title="Duplicate of A",
            url="https://cnbc.com/a",  # same URL
            published="2026-02-25T08:00:00+00:00",
        )

        _make_scraped_file(input_dir / "file1.json", [article_a, article_b])
        _make_scraped_file(input_dir / "file2.json", [article_a_dup])

        result_path = convert(
            input_file=None,
            input_dir=input_dir,
            output_dir=output_dir,
            start=date(2026, 2, 22),
            end=date(2026, 3, 1),
        )

        data = json.loads(result_path.read_text(encoding="utf-8"))
        # Only 2 unique URLs; duplicate should be removed
        assert data["total_count"] == 2
        urls = [a["url"] for a in data["news"]]
        assert len(set(urls)) == 2

    def test_正常系_複数ファイルから全記事が収集される(self, tmp_path: Path) -> None:
        """convert() collects articles from all JSON files in input_dir."""
        input_dir = tmp_path / "inputs"
        input_dir.mkdir()
        output_dir = tmp_path / "output"

        for i in range(3):
            article = _make_article(
                title=f"Article {i}",
                url=f"https://cnbc.com/{i}",
                published="2026-02-25T10:00:00+00:00",
            )
            _make_scraped_file(input_dir / f"file{i}.json", [article])

        result_path = convert(
            input_file=None,
            input_dir=input_dir,
            output_dir=output_dir,
            start=date(2026, 2, 22),
            end=date(2026, 3, 1),
        )

        data = json.loads(result_path.read_text(encoding="utf-8"))
        assert data["total_count"] == 3

    def test_正常系_サブディレクトリのJSONファイルも収集される(
        self, tmp_path: Path
    ) -> None:
        """convert() recursively finds JSON files in subdirectories."""
        input_dir = tmp_path / "inputs"
        subdir = input_dir / "subdir"
        subdir.mkdir(parents=True)
        output_dir = tmp_path / "output"

        article = _make_article(
            title="Nested article",
            url="https://cnbc.com/nested",
            published="2026-02-25T10:00:00+00:00",
        )
        _make_scraped_file(subdir / "nested.json", [article])

        result_path = convert(
            input_file=None,
            input_dir=input_dir,
            output_dir=output_dir,
            start=date(2026, 2, 22),
            end=date(2026, 3, 1),
        )

        data = json.loads(result_path.read_text(encoding="utf-8"))
        assert data["total_count"] == 1


# ---------------------------------------------------------------------------
# Test 7: 異常系_存在しないファイルでエラー
# ---------------------------------------------------------------------------


class TestMissingFile:
    """Test error handling when input file does not exist."""

    def test_異常系_存在しないファイルでエラー(self, tmp_path: Path) -> None:
        """_collect_raw_articles returns empty list for missing file."""
        missing_file = tmp_path / "nonexistent.json"
        # _read_scraped_file logs an error and returns [] without raising
        result = _collect_raw_articles(input_file=missing_file, input_dir=None)
        assert result == []

    def test_異常系_neitherが指定されない場合ValueError(self, tmp_path: Path) -> None:
        """_collect_raw_articles raises ValueError when both inputs are None."""
        with pytest.raises(ValueError, match="Either --input or --input-dir"):
            _collect_raw_articles(input_file=None, input_dir=None)

    def test_異常系_不正なJSONファイルはスキップされる(self, tmp_path: Path) -> None:
        """_collect_raw_articles skips files with invalid JSON."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json", encoding="utf-8")

        result = _collect_raw_articles(input_file=bad_file, input_dir=None)
        assert result == []


# ---------------------------------------------------------------------------
# Test 8: エッジケース_空配列で空の出力
# ---------------------------------------------------------------------------


class TestEmptyInput:
    """Test handling of empty article arrays."""

    def test_エッジケース_空配列で空の出力(self, tmp_path: Path) -> None:
        """convert() produces empty news list when input has no articles."""
        input_file = tmp_path / "empty.json"
        output_dir = tmp_path / "output"
        _make_scraped_file(input_file, [])

        result_path = convert(
            input_file=input_file,
            input_dir=None,
            output_dir=output_dir,
            start=date(2026, 2, 22),
            end=date(2026, 3, 1),
        )

        data = json.loads(result_path.read_text(encoding="utf-8"))
        assert data["total_count"] == 0
        assert data["news"] == []
        # All categories should be present but empty
        for cat in VALID_CATEGORIES:
            assert data["by_category"][cat] == []
            assert data["statistics"][cat] == 0

    def test_エッジケース_全記事が日付範囲外で空の出力(self, tmp_path: Path) -> None:
        """convert() produces empty result when all articles are outside date range."""
        input_file = tmp_path / "news.json"
        output_dir = tmp_path / "output"
        articles = [
            _make_article(
                url="https://cnbc.com/old",
                published="2020-01-01T00:00:00+00:00",
            )
        ]
        _make_scraped_file(input_file, articles)

        result_path = convert(
            input_file=input_file,
            input_dir=None,
            output_dir=output_dir,
            start=date(2026, 2, 22),
            end=date(2026, 3, 1),
        )

        data = json.loads(result_path.read_text(encoding="utf-8"))
        assert data["total_count"] == 0


# ---------------------------------------------------------------------------
# Test 9: エッジケース_summaryが空でcontentフォールバック
# ---------------------------------------------------------------------------


class TestSummaryFallback:
    """Test that _build_summary falls back to content when summary is absent."""

    def test_エッジケース_summaryが空でcontentフォールバック(self) -> None:
        """_build_summary returns first 200 chars of content when summary is empty."""
        long_content = "A" * 300
        article = {"summary": "", "content": long_content}
        result = _build_summary(article)
        assert result == "A" * 200

    def test_エッジケース_summaryがNoneでcontentフォールバック(self) -> None:
        """_build_summary uses content when summary field is None."""
        article = {"content": "Some content text"}
        result = _build_summary(article)
        assert result == "Some content text"

    def test_エッジケース_両方Noneで空文字列を返す(self) -> None:
        """_build_summary returns empty string when both summary and content are absent."""
        result = _build_summary({})
        assert result == ""

    def test_エッジケース_summaryがある場合はsummaryを使う(self) -> None:
        """_build_summary uses summary field when non-empty."""
        article = {"summary": "Short summary", "content": "Longer content here"}
        result = _build_summary(article)
        assert result == "Short summary"

    def test_エッジケース_summaryが空でcontentもNoneの場合は空文字列(self) -> None:
        """_build_summary returns empty string when summary is empty and content is None."""
        article = {"summary": "", "content": None}
        result = _build_summary(article)
        assert result == ""

    def test_エッジケース_convertでsummaryなし記事が処理される(
        self, tmp_path: Path
    ) -> None:
        """convert() processes articles with no summary by using content fallback."""
        input_file = tmp_path / "news.json"
        output_dir = tmp_path / "output"
        articles = [
            {
                "title": "No summary article",
                "url": "https://cnbc.com/nosummary",
                "source": "CNBC",
                "published": "2026-02-25T10:00:00+00:00",
                "content": "Full content text that is used as fallback for the summary",
            }
        ]
        _make_scraped_file(input_file, articles)

        result_path = convert(
            input_file=input_file,
            input_dir=None,
            output_dir=output_dir,
            start=date(2026, 2, 22),
            end=date(2026, 3, 1),
        )

        data = json.loads(result_path.read_text(encoding="utf-8"))
        assert data["total_count"] == 1
        article = data["news"][0]
        # Summary should use content fallback
        assert "Full content text" in article["summary"]


# ---------------------------------------------------------------------------
# Additional: _parse_published and _is_in_period unit tests
# ---------------------------------------------------------------------------


class TestParsePublished:
    """Unit tests for _parse_published."""

    def test_正常系_ISO8601文字列をパースできる(self) -> None:
        """_parse_published parses ISO 8601 strings correctly."""
        result = _parse_published("2026-03-01T12:00:00+00:00")
        assert result == datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_正常系_タイムゾーンなし文字列はUTCとして扱う(self) -> None:
        """_parse_published treats naive datetimes as UTC."""
        result = _parse_published("2026-03-01T12:00:00")
        assert result is not None
        assert result.tzinfo == timezone.utc

    def test_異常系_Noneでは_Noneを返す(self) -> None:
        """_parse_published returns None for None input."""
        assert _parse_published(None) is None

    def test_異常系_不正な文字列ではNoneを返す(self) -> None:
        """_parse_published returns None for unparseable strings."""
        assert _parse_published("not-a-date") is None


class TestIsInPeriod:
    """Unit tests for _is_in_period."""

    def test_正常系_期間内の日付はTrueを返す(self) -> None:
        """_is_in_period returns True for dates within the period."""
        dt = datetime(2026, 2, 25, 12, 0, tzinfo=timezone.utc)
        assert _is_in_period(dt, date(2026, 2, 22), date(2026, 3, 1)) is True

    def test_正常系_境界開始日はTrueを返す(self) -> None:
        """_is_in_period returns True on the start boundary."""
        dt = datetime(2026, 2, 22, 0, 0, tzinfo=timezone.utc)
        assert _is_in_period(dt, date(2026, 2, 22), date(2026, 3, 1)) is True

    def test_正常系_境界終了日はTrueを返す(self) -> None:
        """_is_in_period returns True on the end boundary."""
        dt = datetime(2026, 3, 1, 23, 59, tzinfo=timezone.utc)
        assert _is_in_period(dt, date(2026, 2, 22), date(2026, 3, 1)) is True

    def test_異常系_期間外の日付はFalseを返す(self) -> None:
        """_is_in_period returns False for dates outside the period."""
        dt_before = datetime(2026, 2, 21, tzinfo=timezone.utc)
        dt_after = datetime(2026, 3, 2, tzinfo=timezone.utc)
        assert _is_in_period(dt_before, date(2026, 2, 22), date(2026, 3, 1)) is False
        assert _is_in_period(dt_after, date(2026, 2, 22), date(2026, 3, 1)) is False

    def test_異常系_NoneはFalseを返す(self) -> None:
        """_is_in_period returns False when datetime is None."""
        assert _is_in_period(None, date(2026, 2, 22), date(2026, 3, 1)) is False
