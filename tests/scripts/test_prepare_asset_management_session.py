"""Tests for scripts/prepare_asset_management_session.py.

資産形成セッション前処理スクリプトの単体テスト。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from freezegun import freeze_time

if TYPE_CHECKING:
    from pathlib import Path

from prepare_asset_management_session import (
    DEFAULT_DAYS,
    PRESET_KEY_TO_PATH,
    RSS_PRESETS_JP_PATH,
    RSS_PRESETS_WEALTH_PATH,
    URL_TO_SOURCE_KEY,
    AssetManagementSession,
    AssetManagementStats,
    AssetManagementThemeData,
    build_session,
    generate_session_id,
    load_rss_presets,
    match_keywords,
    parse_args,
    process_themes,
    resolve_presets_path,
    resolve_source_key,
    run,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FROZEN_TIME = "2026-03-06T12:00:00+00:00"
"""Fixed time for deterministic tests."""


def _make_item(
    days_ago: int,
    title: str = "Test Article",
    link: str = "https://example.com/article",
    summary: str = "A test summary",
    feed_source: str = "Test Feed",
) -> dict[str, Any]:
    """指定日数前の published を持つRSSアイテムを生成。"""
    base = datetime(2026, 3, 6, 12, 0, 0, tzinfo=timezone.utc)
    dt = base - timedelta(days=days_ago)
    return {
        "item_id": f"item-{days_ago}",
        "title": title,
        "link": link,
        "published": dt.isoformat(),
        "summary": summary,
        "content": None,
        "author": None,
        "fetched_at": base.isoformat(),
        "feed_source": feed_source,
    }


# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------


class TestParseArgs:
    """parse_args 関数のテスト。"""

    def test_正常系_デフォルト引数(self) -> None:
        args = parse_args([])
        assert args.days == DEFAULT_DAYS
        assert args.themes == "all"
        assert args.top_n == 10
        assert args.output is None
        assert args.verbose is False

    def test_正常系_全オプション指定(self) -> None:
        args = parse_args(
            ["--days", "30", "--themes", "nisa,ideco", "--top-n", "5", "--verbose"]
        )
        assert args.days == 30
        assert args.themes == "nisa,ideco"
        assert args.top_n == 5
        assert args.verbose is True

    def test_異常系_daysが0でエラー(self) -> None:
        with pytest.raises(SystemExit):
            parse_args(["--days", "0"])

    def test_異常系_daysが負数でエラー(self) -> None:
        with pytest.raises(SystemExit):
            parse_args(["--days", "-1"])

    def test_異常系_daysが上限超過でエラー(self) -> None:
        with pytest.raises(SystemExit):
            parse_args(["--days", "366"])

    def test_異常系_top_nが上限超過でエラー(self) -> None:
        with pytest.raises(SystemExit):
            parse_args(["--top-n", "101"])


# ---------------------------------------------------------------------------
# resolve_source_key
# ---------------------------------------------------------------------------


class TestResolveSourceKey:
    """resolve_source_key 関数のテスト。"""

    def test_正常系_fsaドメインでfsaを返す(self) -> None:
        assert resolve_source_key("https://www.fsa.go.jp/rss.xml") == "fsa"

    def test_正常系_bojドメインでbojを返す(self) -> None:
        assert resolve_source_key("https://www.boj.or.jp/rss/whatsnew.xml") == "boj"

    def test_正常系_未知URLでunknownを返す(self) -> None:
        assert resolve_source_key("https://unknown-site.com/feed") == "unknown"

    def test_正常系_空文字列でunknownを返す(self) -> None:
        assert resolve_source_key("") == "unknown"


# ---------------------------------------------------------------------------
# match_keywords
# ---------------------------------------------------------------------------


class TestMatchKeywords:
    """match_keywords 関数のテスト。"""

    def test_正常系_タイトルにキーワードが含まれる(self) -> None:
        item = _make_item(1, title="NISA制度の最新ニュース")
        keywords = ["NISA", "つみたて", "非課税"]
        assert match_keywords(item, keywords) is True

    def test_正常系_サマリーにキーワードが含まれる(self) -> None:
        item = _make_item(1, title="金融ニュース", summary="つみたてNISAの活用法")
        keywords = ["NISA", "つみたて"]
        assert match_keywords(item, keywords) is True

    def test_正常系_キーワードが含まれない(self) -> None:
        item = _make_item(1, title="天気予報", summary="晴れのち曇り")
        keywords = ["NISA", "つみたて", "非課税"]
        assert match_keywords(item, keywords) is False

    def test_エッジケース_空のキーワードリスト(self) -> None:
        item = _make_item(1, title="何でもマッチ")
        assert match_keywords(item, []) is False

    def test_エッジケース_titleとsummaryがNone(self) -> None:
        item = {"title": None, "summary": None}
        assert match_keywords(item, ["NISA"]) is False


# ---------------------------------------------------------------------------
# process_themes
# ---------------------------------------------------------------------------


class TestProcessThemes:
    """process_themes 関数のテスト。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_日付フィルタで期間内の記事のみ返す(self) -> None:
        items_by_source: dict[str, list[dict[str, Any]]] = {
            "fsa": [
                _make_item(1, title="NISA新制度開始"),
                _make_item(20, title="NISA旧制度"),
            ],
        }
        themes_config = {
            "nisa": {
                "name_ja": "NISA制度",
                "keywords_ja": ["NISA", "つみたて", "非課税", "積立投資"],
                "target_sources": ["fsa"],
            },
        }

        result, date_filtered, keyword_matched = process_themes(
            items_by_source=items_by_source,
            themes_config=themes_config,
            days=14,
            top_n=10,
            selected_themes=None,
        )

        assert "nisa" in result
        assert len(result["nisa"]["articles"]) == 1
        assert result["nisa"]["articles"][0]["title"] == "NISA新制度開始"
        assert date_filtered == 1
        assert keyword_matched == 1

    @freeze_time(FROZEN_TIME)
    def test_正常系_filtered_matchedが異なる値を返す(self) -> None:
        items_by_source: dict[str, list[dict[str, Any]]] = {
            "fsa": [
                _make_item(1, title="NISA制度の改正"),
                _make_item(1, title="天気予報"),
            ],
        }
        themes_config = {
            "nisa": {
                "name_ja": "NISA制度",
                "keywords_ja": ["NISA"],
                "target_sources": ["fsa"],
            },
        }

        _, date_filtered, keyword_matched = process_themes(
            items_by_source=items_by_source,
            themes_config=themes_config,
            days=14,
            top_n=10,
            selected_themes=None,
        )

        # 2 articles pass date filter, but only 1 matches keywords
        assert date_filtered == 2
        assert keyword_matched == 1

    @freeze_time(FROZEN_TIME)
    def test_正常系_キーワードマッチで該当記事のみ返す(self) -> None:
        items_by_source: dict[str, list[dict[str, Any]]] = {
            "fsa": [
                _make_item(1, title="NISA制度の改正"),
                _make_item(1, title="天気予報"),
            ],
        }
        themes_config = {
            "nisa": {
                "name_ja": "NISA制度",
                "keywords_ja": ["NISA", "つみたて"],
                "target_sources": ["fsa"],
            },
        }

        result, _, _ = process_themes(
            items_by_source=items_by_source,
            themes_config=themes_config,
            days=14,
            top_n=10,
            selected_themes=None,
        )

        assert len(result["nisa"]["articles"]) == 1
        assert result["nisa"]["articles"][0]["title"] == "NISA制度の改正"

    @freeze_time(FROZEN_TIME)
    def test_異常系_空フィードで空結果(self) -> None:
        items_by_source: dict[str, list[dict[str, Any]]] = {
            "fsa": [],
        }
        themes_config = {
            "nisa": {
                "name_ja": "NISA制度",
                "keywords_ja": ["NISA"],
                "target_sources": ["fsa"],
            },
        }

        result, _, _ = process_themes(
            items_by_source=items_by_source,
            themes_config=themes_config,
            days=14,
            top_n=10,
            selected_themes=None,
        )

        assert "nisa" in result
        assert len(result["nisa"]["articles"]) == 0

    @freeze_time(FROZEN_TIME)
    def test_エッジケース_全記事期間外で空結果(self) -> None:
        items_by_source: dict[str, list[dict[str, Any]]] = {
            "fsa": [
                _make_item(30, title="NISA制度"),
                _make_item(60, title="NISA改正"),
            ],
        }
        themes_config = {
            "nisa": {
                "name_ja": "NISA制度",
                "keywords_ja": ["NISA"],
                "target_sources": ["fsa"],
            },
        }

        result, _, _ = process_themes(
            items_by_source=items_by_source,
            themes_config=themes_config,
            days=14,
            top_n=10,
            selected_themes=None,
        )

        assert len(result["nisa"]["articles"]) == 0

    @freeze_time(FROZEN_TIME)
    def test_正常系_テーマフィルタで選択テーマのみ処理(self) -> None:
        items_by_source: dict[str, list[dict[str, Any]]] = {
            "fsa": [_make_item(1, title="NISA新制度")],
            "daiwa": [_make_item(1, title="資産配分レポート")],
        }
        themes_config = {
            "nisa": {
                "name_ja": "NISA制度",
                "keywords_ja": ["NISA"],
                "target_sources": ["fsa"],
            },
            "asset_allocation": {
                "name_ja": "資産配分",
                "keywords_ja": ["資産配分"],
                "target_sources": ["daiwa"],
            },
        }

        result, _, _ = process_themes(
            items_by_source=items_by_source,
            themes_config=themes_config,
            days=14,
            top_n=10,
            selected_themes=["nisa"],
        )

        assert "nisa" in result
        assert "asset_allocation" not in result

    def test_エッジケース_存在しないソースキーは空リストで処理(self) -> None:
        items_by_source: dict[str, list[dict[str, Any]]] = {}
        themes_config = {
            "nisa": {
                "name_ja": "NISA制度",
                "keywords_ja": ["NISA"],
                "target_sources": ["nonexistent_source"],
            },
        }

        result, _, _ = process_themes(
            items_by_source=items_by_source,
            themes_config=themes_config,
            days=14,
            top_n=10,
            selected_themes=None,
        )

        assert result["nisa"]["articles"] == []


# ---------------------------------------------------------------------------
# generate_session_id
# ---------------------------------------------------------------------------


class TestGenerateSessionId:
    """generate_session_id 関数のテスト。"""

    @freeze_time("2026-03-06T12:30:45+00:00")
    def test_正常系_正しいフォーマットで生成される(self) -> None:
        sid = generate_session_id()
        assert sid == "asset-mgmt-20260306-123045"

    @freeze_time("2026-01-01T00:00:00+00:00")
    def test_正常系_年初でも正しく生成される(self) -> None:
        sid = generate_session_id()
        assert sid.startswith("asset-mgmt-20260101-")


# ---------------------------------------------------------------------------
# build_session
# ---------------------------------------------------------------------------


class TestBuildSession:
    """build_session 関数のテスト。"""

    def test_正常系_セッションを構築できる(self) -> None:
        theme_results = {
            "nisa": {
                "articles": [
                    {
                        "link": "https://example.com/1",
                        "title": "NISA記事",
                        "summary": "要約",
                        "feed_source": "FSA",
                        "published": "2026-03-06T00:00:00+00:00",
                    }
                ],
                "name_ja": "NISA制度",
                "keywords_used": ["NISA"],
            },
        }

        session = build_session(
            session_id="asset-mgmt-20260306-120000",
            theme_results=theme_results,
            total_fetched=10,
            total_filtered=5,
            total_matched=3,
        )

        assert session.session_id == "asset-mgmt-20260306-120000"
        assert session.stats.total == 10
        assert session.stats.filtered == 5
        assert session.stats.matched == 3
        assert "nisa" in session.themes
        assert len(session.themes["nisa"].articles) == 1

    def test_エッジケース_空のtheme_resultsで構築できる(self) -> None:
        session = build_session(
            session_id="asset-mgmt-20260306-120000",
            theme_results={},
            total_fetched=0,
            total_filtered=0,
            total_matched=0,
        )

        assert session.themes == {}
        assert session.stats.total == 0


# ---------------------------------------------------------------------------
# load_rss_presets
# ---------------------------------------------------------------------------


class TestLoadRssPresets:
    """load_rss_presets 関数のテスト。"""

    def test_正常系_有効なプリセットのみ返す(self, tmp_path: Path) -> None:
        config = {
            "presets": [
                {"title": "Feed A", "url": "https://a.com/rss", "enabled": True},
                {"title": "Feed B", "url": "https://b.com/rss", "enabled": False},
                {"title": "Feed C", "url": "https://c.com/rss"},  # default enabled
            ]
        }
        config_path = tmp_path / "presets.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")

        result = load_rss_presets(config_path)

        assert len(result) == 2
        assert result[0]["title"] == "Feed A"
        assert result[1]["title"] == "Feed C"

    def test_異常系_ファイルが存在しない(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_rss_presets(tmp_path / "nonexistent.json")


# ---------------------------------------------------------------------------
# run (integration)
# ---------------------------------------------------------------------------


class TestRun:
    """run 関数の統合テスト。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_セッションファイルが生成される(self, tmp_path: Path) -> None:
        theme_config = {
            "themes": {
                "nisa": {
                    "name_ja": "NISA制度",
                    "keywords_ja": ["NISA"],
                    "target_sources": ["fsa"],
                },
            }
        }
        presets = [
            {"title": "FSA", "url": "https://www.fsa.go.jp/rss.xml", "enabled": True}
        ]

        output_path = tmp_path / "session.json"

        with (
            patch(
                "prepare_asset_management_session.load_json_config",
                return_value=theme_config,
            ),
            patch(
                "prepare_asset_management_session.load_rss_presets",
                return_value=presets,
            ),
            patch(
                "prepare_asset_management_session.fetch_items_by_source",
                return_value={"fsa": [_make_item(1, title="NISA記事")]},
            ),
        ):
            exit_code = run(
                days=14,
                themes_filter=None,
                output_path=output_path,
                top_n=10,
            )

        assert exit_code == 0
        assert output_path.exists()

        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert data["stats"]["filtered"] == 1
        assert data["stats"]["matched"] == 1


# ---------------------------------------------------------------------------
# AssetManagementSession model
# ---------------------------------------------------------------------------


class TestAssetManagementSession:
    """AssetManagementSession モデルのテスト。"""

    def test_正常系_セッションモデルを生成できる(self) -> None:
        session = AssetManagementSession(
            session_id="asset-mgmt-20260306-120000",
            timestamp="2026-03-06T12:00:00+00:00",
            themes={},
            stats=AssetManagementStats(total=0, filtered=0, matched=0),
        )
        assert session.session_id == "asset-mgmt-20260306-120000"
        assert session.themes == {}

    def test_正常系_model_dumpでdict変換できる(self) -> None:
        session = AssetManagementSession(
            session_id="asset-mgmt-20260306-120000",
            timestamp="2026-03-06T12:00:00+00:00",
            themes={},
            stats=AssetManagementStats(total=0, filtered=0, matched=0),
        )
        dumped = session.model_dump()
        assert isinstance(dumped, dict)
        assert dumped["session_id"] == "asset-mgmt-20260306-120000"
        assert isinstance(dumped["stats"], dict)
        assert set(dumped["stats"].keys()) == {"total", "filtered", "matched"}


# ---------------------------------------------------------------------------
# TestResolvePresetsPath
# ---------------------------------------------------------------------------


class TestResolvePresetsPath:
    """resolve_presets_path のテスト。"""

    def test_正常系_jpキーでJPプリセットパスを返す(self) -> None:
        from pathlib import Path

        result = resolve_presets_path("jp")
        assert result == RSS_PRESETS_JP_PATH
        assert isinstance(result, Path)

    def test_正常系_wealthキーでWealthプリセットパスを返す(self) -> None:
        from pathlib import Path

        result = resolve_presets_path("wealth")
        assert result == RSS_PRESETS_WEALTH_PATH
        assert isinstance(result, Path)

    def test_正常系_カスタムパス文字列をPathに変換して返す(self) -> None:
        from pathlib import Path

        custom = "data/config/my-custom-presets.json"
        result = resolve_presets_path(custom)
        assert result == Path(custom)
        assert isinstance(result, Path)

    def test_エッジケース_未知のキーはPath変換される(self) -> None:
        from pathlib import Path

        result = resolve_presets_path("unknown_key")
        assert result == Path("unknown_key")
