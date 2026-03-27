"""Unit tests for scripts/auto_poster.py.

Wave 1: AutoPosterConfig / SlotMatcher / DraftReader / main() 骨格のテスト。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

JST = ZoneInfo("Asia/Tokyo")

# ---------------------------------------------------------------------------
# AutoPosterConfig
# ---------------------------------------------------------------------------


class TestAutoPosterConfig:
    """AutoPosterConfig のテスト。"""

    def test_正常系_デフォルト値が設定される(self) -> None:
        """デフォルト引数で AutoPosterConfig が生成できることを確認。"""
        from scripts.auto_poster import AutoPosterConfig

        config = AutoPosterConfig()
        assert config.account is None
        assert config.dry_run is False
        assert config.include_note is False
        assert config.force_slot is None
        assert config.tolerance == 15
        assert config.week is None

    def test_正常系_全パラメータを設定できる(self) -> None:
        """全パラメータを指定して AutoPosterConfig が生成できることを確認。"""
        from scripts.auto_poster import AutoPosterConfig

        config = AutoPosterConfig(
            account="mitsuki",
            dry_run=True,
            include_note=True,
            force_slot="S1",
            tolerance=30,
            week="2026-03-31",
        )
        assert config.account == "mitsuki"
        assert config.dry_run is True
        assert config.include_note is True
        assert config.force_slot == "S1"
        assert config.tolerance == 30
        assert config.week == "2026-03-31"

    def test_正常系_account指定のみでも生成できる(self) -> None:
        """account のみ指定した場合に正常に生成されることを確認。"""
        from scripts.auto_poster import AutoPosterConfig

        config = AutoPosterConfig(account="career_sister")
        assert config.account == "career_sister"
        assert config.dry_run is False
        assert config.tolerance == 15


# ---------------------------------------------------------------------------
# SlotMatcher
# ---------------------------------------------------------------------------

SLOT_TIME_MAP = {"朝": "07:30", "昼": "12:30", "夜": "20:30"}


class TestSlotMatcher:
    """SlotMatcher のテスト。"""

    def test_正常系_現在時刻がスロット時刻にマッチする(self) -> None:
        """現在時刻が ±tolerance 以内にある場合にスロットが返される。"""
        from scripts.auto_poster import SlotMatcher

        # 朝スロット 07:30 の ±15分以内
        now = datetime(2026, 3, 27, 7, 30, 0, tzinfo=JST)
        matcher = SlotMatcher(slot_time_map=SLOT_TIME_MAP, tolerance=15)
        matched = matcher.match(now)
        assert matched is not None
        assert matched["slot"] == "朝"

    def test_正常系_tolerance範囲内の前後で検出される(self) -> None:
        """tolerance 範囲内（前後14分）でスロットが検出されることを確認。"""
        from scripts.auto_poster import SlotMatcher

        # 07:30 - 14分 = 07:16
        now_before = datetime(2026, 3, 27, 7, 16, 0, tzinfo=JST)
        matcher = SlotMatcher(slot_time_map=SLOT_TIME_MAP, tolerance=15)
        matched = matcher.match(now_before)
        assert matched is not None
        assert matched["slot"] == "朝"

        # 07:30 + 14分 = 07:44
        now_after = datetime(2026, 3, 27, 7, 44, 0, tzinfo=JST)
        matched = matcher.match(now_after)
        assert matched is not None
        assert matched["slot"] == "朝"

    def test_正常系_tolerance範囲外ではNoneが返される(self) -> None:
        """tolerance 範囲外の時刻ではマッチしないことを確認。"""
        from scripts.auto_poster import SlotMatcher

        # 07:30 + 16分 = 07:46（15分超え）
        now = datetime(2026, 3, 27, 7, 46, 0, tzinfo=JST)
        matcher = SlotMatcher(slot_time_map=SLOT_TIME_MAP, tolerance=15)
        matched = matcher.match(now)
        assert matched is None

    def test_正常系_toleranceを30に設定できる(self) -> None:
        """--tolerance 30 の場合に ±30分の範囲でスロットを検出する。"""
        from scripts.auto_poster import SlotMatcher

        # 07:30 + 29分 = 07:59（30分以内）
        now = datetime(2026, 3, 27, 7, 59, 0, tzinfo=JST)
        matcher = SlotMatcher(slot_time_map=SLOT_TIME_MAP, tolerance=30)
        matched = matcher.match(now)
        assert matched is not None
        assert matched["slot"] == "朝"

    def test_正常系_昼スロットにマッチする(self) -> None:
        """昼スロット 12:30 にマッチすることを確認。"""
        from scripts.auto_poster import SlotMatcher

        now = datetime(2026, 3, 27, 12, 30, 0, tzinfo=JST)
        matcher = SlotMatcher(slot_time_map=SLOT_TIME_MAP, tolerance=15)
        matched = matcher.match(now)
        assert matched is not None
        assert matched["slot"] == "昼"

    def test_正常系_夜スロットにマッチする(self) -> None:
        """夜スロット 20:30 にマッチすることを確認。"""
        from scripts.auto_poster import SlotMatcher

        now = datetime(2026, 3, 27, 20, 30, 0, tzinfo=JST)
        matcher = SlotMatcher(slot_time_map=SLOT_TIME_MAP, tolerance=15)
        matched = matcher.match(now)
        assert matched is not None
        assert matched["slot"] == "夜"

    def test_正常系_force_slot指定時は時刻を無視する(self) -> None:
        """force_slot 指定時は時刻マッチングを無視してスロットが返される。"""
        from scripts.auto_poster import SlotMatcher

        # 深夜でも force_slot で朝スロットが返る
        now = datetime(2026, 3, 27, 3, 0, 0, tzinfo=JST)
        matcher = SlotMatcher(slot_time_map=SLOT_TIME_MAP, tolerance=15)
        matched = matcher.match_force(now, "S1")
        assert matched is not None
        assert matched["slot"] == "朝"

    def test_正常系_force_slot_S2で昼スロット(self) -> None:
        """force_slot S2 で昼スロットが返されることを確認。"""
        from scripts.auto_poster import SlotMatcher

        now = datetime(2026, 3, 27, 3, 0, 0, tzinfo=JST)
        matcher = SlotMatcher(slot_time_map=SLOT_TIME_MAP, tolerance=15)
        matched = matcher.match_force(now, "S2")
        assert matched is not None
        assert matched["slot"] == "昼"

    def test_正常系_force_slot_S3で夜スロット(self) -> None:
        """force_slot S3 で夜スロットが返されることを確認。"""
        from scripts.auto_poster import SlotMatcher

        now = datetime(2026, 3, 27, 3, 0, 0, tzinfo=JST)
        matcher = SlotMatcher(slot_time_map=SLOT_TIME_MAP, tolerance=15)
        matched = matcher.match_force(now, "S3")
        assert matched is not None
        assert matched["slot"] == "夜"

    def test_異常系_force_slot_不正な値はNoneを返す(self) -> None:
        """存在しない force_slot 値では None が返されることを確認。"""
        from scripts.auto_poster import SlotMatcher

        now = datetime(2026, 3, 27, 3, 0, 0, tzinfo=JST)
        matcher = SlotMatcher(slot_time_map=SLOT_TIME_MAP, tolerance=15)
        matched = matcher.match_force(now, "S99")
        assert matched is None


# ---------------------------------------------------------------------------
# DraftReader
# ---------------------------------------------------------------------------


class TestDraftReader:
    """DraftReader のテスト。"""

    def test_正常系_career_sisterのmeta_jsonを読み込める(self, tmp_path: Path) -> None:
        """career_sister フォーマットの meta.json を読み込めることを確認。"""
        from scripts.auto_poster import DraftReader

        # career_sister ディレクトリ構造を作成
        week_dir = tmp_path / "drafts" / "week_2026-03-24"
        week_dir.mkdir(parents=True)
        meta = {
            "week_start": "2026-03-24",
            "week_end": "2026-03-30",
            "status": "draft",
            "days": [
                {
                    "date": "2026-03-27",
                    "day_label": "木",
                    "status": "draft",
                    "slots": [
                        {
                            "slot": "朝",
                            "category": "有益",
                            "type": "型3",
                            "theme": "T3",
                        },
                        {
                            "slot": "昼",
                            "category": "有益",
                            "type": "型1",
                            "theme": "T8",
                        },
                        {
                            "slot": "夜",
                            "category": "エンゲージメント",
                            "type": "型1-A",
                            "theme": "T4",
                        },
                    ],
                }
            ],
        }
        (week_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False))

        reader = DraftReader(drafts_root=tmp_path / "drafts", account="career_sister")
        result = reader.load(week="2026-03-24")
        assert result is not None
        assert result["week_start"] == "2026-03-24"
        assert len(result["days"]) == 1

    def test_正常系_week_ディレクトリを自動検出する(self, tmp_path: Path) -> None:
        """--week 未指定時に week_YYYY-MM-DD ディレクトリが自動検出されることを確認。"""
        from scripts.auto_poster import DraftReader

        # 複数の week ディレクトリを作成し最新を検出
        drafts_root = tmp_path / "drafts"
        drafts_root.mkdir(parents=True)

        for week_str in ["week_2026-03-17", "week_2026-03-24"]:
            week_dir = drafts_root / week_str
            week_dir.mkdir(parents=True)
            meta = {
                "week_start": week_str.replace("week_", ""),
                "week_end": "2026-03-30",
                "status": "draft",
                "days": [],
            }
            (week_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False))

        reader = DraftReader(drafts_root=drafts_root, account="career_sister")
        # week 未指定で最新週が検出される
        result = reader.load()
        assert result is not None
        assert result["week_start"] == "2026-03-24"

    def test_正常系_weekオプションで上書き可能(self, tmp_path: Path) -> None:
        """--week オプションで特定の週ディレクトリを指定できることを確認。"""
        from scripts.auto_poster import DraftReader

        drafts_root = tmp_path / "drafts"
        for week_str in ["week_2026-03-17", "week_2026-03-24"]:
            week_dir = drafts_root / week_str
            week_dir.mkdir(parents=True)
            meta = {
                "week_start": week_str.replace("week_", ""),
                "week_end": "2026-03-30",
                "status": "draft",
                "days": [],
            }
            (week_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False))

        reader = DraftReader(drafts_root=drafts_root, account="career_sister")
        result = reader.load(week="2026-03-17")
        assert result is not None
        assert result["week_start"] == "2026-03-17"

    def test_正常系_career_sisterのday_dirフォーマットを検出する(
        self, tmp_path: Path
    ) -> None:
        """career_sister の day_X_mon フォーマットのディレクトリが検出される。"""
        from scripts.auto_poster import DraftReader

        drafts_root = tmp_path / "drafts"
        week_dir = drafts_root / "week_2026-03-24"
        day_dir = week_dir / "day_4_thu"
        slot_dir = day_dir / "slot_1_morning"
        slot_dir.mkdir(parents=True)
        (slot_dir / "threads_post.md").write_text("テスト投稿内容")

        meta = {
            "week_start": "2026-03-24",
            "week_end": "2026-03-30",
            "status": "draft",
            "days": [
                {
                    "date": "2026-03-27",
                    "day_label": "木",
                    "status": "draft",
                    "slots": [
                        {"slot": "朝", "category": "有益", "type": "型3", "theme": "T3"}
                    ],
                }
            ],
        }
        (week_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False))

        reader = DraftReader(drafts_root=drafts_root, account="career_sister")
        result = reader.load(week="2026-03-24")
        assert result is not None

    def test_異常系_week_ディレクトリが存在しない場合はNoneを返す(
        self, tmp_path: Path
    ) -> None:
        """week ディレクトリが存在しない場合は None が返されることを確認。"""
        from scripts.auto_poster import DraftReader

        drafts_root = tmp_path / "drafts"
        drafts_root.mkdir(parents=True)

        reader = DraftReader(drafts_root=drafts_root, account="career_sister")
        result = reader.load()
        assert result is None

    def test_異常系_存在しないweekを指定するとNoneを返す(self, tmp_path: Path) -> None:
        """存在しない --week 指定時に None が返されることを確認。"""
        from scripts.auto_poster import DraftReader

        drafts_root = tmp_path / "drafts"
        drafts_root.mkdir(parents=True)

        reader = DraftReader(drafts_root=drafts_root, account="career_sister")
        result = reader.load(week="2099-01-01")
        assert result is None

    def test_正常系_今日のスロット一覧を取得できる(self, tmp_path: Path) -> None:
        """特定日のスロット一覧を get_day_slots() で取得できることを確認。"""
        from scripts.auto_poster import DraftReader

        drafts_root = tmp_path / "drafts"
        week_dir = drafts_root / "week_2026-03-24"
        week_dir.mkdir(parents=True)
        meta = {
            "week_start": "2026-03-24",
            "week_end": "2026-03-30",
            "status": "draft",
            "days": [
                {
                    "date": "2026-03-27",
                    "day_label": "木",
                    "status": "draft",
                    "slots": [
                        {"slot": "朝", "category": "有益"},
                        {"slot": "昼", "category": "有益"},
                        {"slot": "夜", "category": "エンゲージメント"},
                    ],
                }
            ],
        }
        (week_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False))

        reader = DraftReader(drafts_root=drafts_root, account="career_sister")
        loaded = reader.load(week="2026-03-24")
        assert loaded is not None
        slots = reader.get_day_slots(loaded, date="2026-03-27")
        assert len(slots) == 3
        assert slots[0]["slot"] == "朝"


# ---------------------------------------------------------------------------
# DAY_DIR_MAP constants
# ---------------------------------------------------------------------------


class TestDayDirMaps:
    """DAY_DIR_MAP_CAREER_SISTER と DAY_DIR_MAP_MITSUKI の定数テスト。"""

    def test_正常系_career_sister_mapが7日分定義されている(self) -> None:
        """DAY_DIR_MAP_CAREER_SISTER が7日分の曜日マッピングを持つことを確認。"""
        from scripts.auto_poster import DAY_DIR_MAP_CAREER_SISTER

        assert len(DAY_DIR_MAP_CAREER_SISTER) == 7
        assert DAY_DIR_MAP_CAREER_SISTER["月"] == "day_1_mon"
        assert DAY_DIR_MAP_CAREER_SISTER["日"] == "day_7_sun"

    def test_正常系_mitsuki_mapが7日分定義されている(self) -> None:
        """DAY_DIR_MAP_MITSUKI が7日分の曜日マッピングを持つことを確認。"""
        from scripts.auto_poster import DAY_DIR_MAP_MITSUKI

        assert len(DAY_DIR_MAP_MITSUKI) == 7
        assert DAY_DIR_MAP_MITSUKI["月"] == "day_1_月"
        assert DAY_DIR_MAP_MITSUKI["日"] == "day_7_日"

    def test_正常系_slot_time_mapが3スロット定義されている(self) -> None:
        """SLOT_TIME_MAP が朝・昼・夜の3スロットを持つことを確認。"""
        from scripts.auto_poster import SLOT_TIME_MAP

        assert len(SLOT_TIME_MAP) == 3
        assert SLOT_TIME_MAP["朝"] == "07:30"
        assert SLOT_TIME_MAP["昼"] == "12:30"
        assert SLOT_TIME_MAP["夜"] == "20:30"


# ---------------------------------------------------------------------------
# SlotInfo (dry-run output)
# ---------------------------------------------------------------------------


class TestDryRunOutput:
    """--dry-run 時の出力内容のテスト。"""

    def test_正常系_slotinfoが必須フィールドを持つ(self) -> None:
        """SlotInfo が slot / time / file / posted フィールドを持つことを確認。"""
        from scripts.auto_poster import SlotInfo

        info = SlotInfo(slot="朝", time="07:30", file=None, posted=False)
        assert info.slot == "朝"
        assert info.time == "07:30"
        assert info.file is None
        assert info.posted is False

    def test_正常系_投稿済みスロットのpostedがTrue(self) -> None:
        """投稿済みスロットの posted フラグが True になることを確認。"""
        from scripts.auto_poster import SlotInfo

        info = SlotInfo(
            slot="夜", time="20:30", file=Path("threads_post.md"), posted=True
        )
        assert info.posted is True
