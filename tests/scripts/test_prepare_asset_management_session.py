"""Tests for scripts/prepare_asset_management_session.py.

資産形成セッション前処理スクリプトの単体テスト。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from prepare_asset_management_session import (
    DEFAULT_DAYS,
    AssetManagementSession,
    AssetManagementStats,
    match_keywords,
    parse_args,
    process_themes,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_item(
    days_ago: int,
    title: str = "Test Article",
    link: str = "https://example.com/article",
    summary: str = "A test summary",
    feed_source: str = "Test Feed",
) -> dict[str, Any]:
    """指定日数前の published を持つRSSアイテムを生成。"""
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {
        "item_id": f"item-{days_ago}",
        "title": title,
        "link": link,
        "published": dt.isoformat(),
        "summary": summary,
        "content": None,
        "author": None,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
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
            [
                "--days",
                "30",
                "--themes",
                "nisa,ideco",
                "--top-n",
                "5",
                "--output",
                "/tmp/test.json",
                "--verbose",
            ]
        )
        assert args.days == 30
        assert args.themes == "nisa,ideco"
        assert args.top_n == 5
        assert args.output == "/tmp/test.json"
        assert args.verbose is True


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


# ---------------------------------------------------------------------------
# process_themes (正常系日付フィルタ)
# ---------------------------------------------------------------------------


class TestProcessThemes:
    """process_themes 関数のテスト。"""

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

        result = process_themes(
            items_by_source=items_by_source,
            themes_config=themes_config,
            days=14,
            top_n=10,
            selected_themes=None,
        )

        assert "nisa" in result
        # 1日前の記事はマッチ（14日以内 & キーワードマッチ）
        # 20日前の記事はフィルタアウト（14日超過）
        assert len(result["nisa"]["articles"]) == 1
        assert result["nisa"]["articles"][0]["title"] == "NISA新制度開始"

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

        result = process_themes(
            items_by_source=items_by_source,
            themes_config=themes_config,
            days=14,
            top_n=10,
            selected_themes=None,
        )

        assert len(result["nisa"]["articles"]) == 1
        assert result["nisa"]["articles"][0]["title"] == "NISA制度の改正"

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

        result = process_themes(
            items_by_source=items_by_source,
            themes_config=themes_config,
            days=14,
            top_n=10,
            selected_themes=None,
        )

        assert "nisa" in result
        assert len(result["nisa"]["articles"]) == 0

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

        result = process_themes(
            items_by_source=items_by_source,
            themes_config=themes_config,
            days=14,
            top_n=10,
            selected_themes=None,
        )

        assert len(result["nisa"]["articles"]) == 0

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

        result = process_themes(
            items_by_source=items_by_source,
            themes_config=themes_config,
            days=14,
            top_n=10,
            selected_themes=["nisa"],
        )

        assert "nisa" in result
        assert "asset_allocation" not in result


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
