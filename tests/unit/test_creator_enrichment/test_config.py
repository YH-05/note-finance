"""creator_enrichment.config のテスト.

CLI 引数パース・設定ファイル読み込み・バリデーションを検証する。
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path

import pytest

from creator_enrichment.config import (
    GENRE_NAMES,
    CycleSettings,
    OrchestratorConfig,
    load_config,
    parse_args,
)


# ---------------------------------------------------------------------------
# CycleSettings
# ---------------------------------------------------------------------------
class TestCycleSettings:
    """CycleSettings dataclass のテスト."""

    def test_正常系_デフォルト値なしで全フィールド指定(self) -> None:
        settings = CycleSettings(
            min_cycle_interval_seconds=30,
            max_consecutive_empty_cycles=3,
            empty_cycle_wait_seconds=60,
        )
        assert settings.min_cycle_interval_seconds == 30
        assert settings.max_consecutive_empty_cycles == 3
        assert settings.empty_cycle_wait_seconds == 60

    def test_正常系_異なる値で生成(self) -> None:
        settings = CycleSettings(
            min_cycle_interval_seconds=10,
            max_consecutive_empty_cycles=5,
            empty_cycle_wait_seconds=120,
        )
        assert settings.min_cycle_interval_seconds == 10
        assert settings.max_consecutive_empty_cycles == 5
        assert settings.empty_cycle_wait_seconds == 120


# ---------------------------------------------------------------------------
# OrchestratorConfig
# ---------------------------------------------------------------------------
class TestOrchestratorConfig:
    """OrchestratorConfig dataclass のテスト."""

    def test_正常系_全フィールド指定(self) -> None:
        cycle = CycleSettings(
            min_cycle_interval_seconds=30,
            max_consecutive_empty_cycles=3,
            empty_cycle_wait_seconds=60,
        )
        config = OrchestratorConfig(
            until_time=datetime.time(23, 30),
            genre="career",
            dry_run=False,
            max_cycles=0,
            cycle_settings=cycle,
        )
        assert config.until_time == datetime.time(23, 30)
        assert config.genre == "career"
        assert config.dry_run is False
        assert config.max_cycles == 0
        assert config.cycle_settings is cycle

    def test_正常系_genre_Noneで生成(self) -> None:
        cycle = CycleSettings(
            min_cycle_interval_seconds=30,
            max_consecutive_empty_cycles=3,
            empty_cycle_wait_seconds=60,
        )
        config = OrchestratorConfig(
            until_time=datetime.time(12, 0),
            genre=None,
            dry_run=True,
            max_cycles=5,
            cycle_settings=cycle,
        )
        assert config.genre is None
        assert config.dry_run is True
        assert config.max_cycles == 5


# ---------------------------------------------------------------------------
# GENRE_NAMES
# ---------------------------------------------------------------------------
class TestGenreNames:
    """GENRE_NAMES 定数のテスト."""

    def test_正常系_3ジャンルが定義されている(self) -> None:
        assert len(GENRE_NAMES) == 3

    def test_正常系_careerが含まれる(self) -> None:
        assert "career" in GENRE_NAMES

    def test_正常系_beauty_romanceが含まれる(self) -> None:
        assert "beauty-romance" in GENRE_NAMES

    def test_正常系_spiritualが含まれる(self) -> None:
        assert "spiritual" in GENRE_NAMES

    def test_正常系_リスト型である(self) -> None:
        assert isinstance(GENRE_NAMES, list)


# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------
class TestParseArgs:
    """parse_args() のテスト."""

    def test_正常系_until_23_30がパースされる(self) -> None:
        args = parse_args(["--until", "23:30"])
        assert args.until == "23:30"

    def test_正常系_genre_careerがパースされる(self) -> None:
        args = parse_args(["--until", "23:30", "--genre", "career"])
        assert args.genre == "career"

    def test_正常系_dry_runフラグがTrueになる(self) -> None:
        args = parse_args(["--until", "23:30", "--dry-run"])
        assert args.dry_run is True

    def test_正常系_dry_runフラグなしでFalse(self) -> None:
        args = parse_args(["--until", "23:30"])
        assert args.dry_run is False

    def test_正常系_max_cyclesのデフォルトは0(self) -> None:
        args = parse_args(["--until", "23:30"])
        assert args.max_cycles == 0

    def test_正常系_max_cyclesを指定(self) -> None:
        args = parse_args(["--until", "23:30", "--max-cycles", "10"])
        assert args.max_cycles == 10

    def test_正常系_genreのデフォルトはNone(self) -> None:
        args = parse_args(["--until", "23:30"])
        assert args.genre is None


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------
def _make_config_json(tmp_path: Path) -> Path:
    """テスト用の config JSON ファイルを作成する."""
    config_data = {
        "version": "1.1",
        "cycle_settings": {
            "min_cycle_interval_seconds": 30,
            "max_consecutive_empty_cycles": 3,
            "empty_cycle_wait_seconds": 60,
        },
        "genres": {
            "career": {"name_ja": "転職・副業"},
            "beauty-romance": {"name_ja": "美容・恋愛"},
            "spiritual": {"name_ja": "占い・スピリチュアル"},
        },
    }
    config_path = tmp_path / "creator-enrichment-config.json"
    config_path.write_text(
        json.dumps(config_data, ensure_ascii=False), encoding="utf-8"
    )
    return config_path


class TestLoadConfig:
    """load_config() のテスト."""

    def test_正常系_until_23_30がdatetime_timeにパースされる(
        self, tmp_path: Path
    ) -> None:
        config_path = _make_config_json(tmp_path)
        args = argparse.Namespace(
            until="23:30",
            genre=None,
            dry_run=False,
            max_cycles=0,
        )
        config = load_config(args, config_path=config_path)
        assert config.until_time == datetime.time(23, 30)

    def test_正常系_genre_careerで正常ロード(self, tmp_path: Path) -> None:
        config_path = _make_config_json(tmp_path)
        args = argparse.Namespace(
            until="23:30",
            genre="career",
            dry_run=False,
            max_cycles=0,
        )
        config = load_config(args, config_path=config_path)
        assert config.genre == "career"

    def test_異常系_不正ジャンルでValueError(self, tmp_path: Path) -> None:
        config_path = _make_config_json(tmp_path)
        args = argparse.Namespace(
            until="23:30",
            genre="invalid-genre",
            dry_run=False,
            max_cycles=0,
        )
        with pytest.raises(ValueError, match="invalid-genre"):
            load_config(args, config_path=config_path)

    def test_正常系_CycleSettingsが正しくマッピングされる(self, tmp_path: Path) -> None:
        config_path = _make_config_json(tmp_path)
        args = argparse.Namespace(
            until="23:30",
            genre=None,
            dry_run=False,
            max_cycles=0,
        )
        config = load_config(args, config_path=config_path)
        assert config.cycle_settings.min_cycle_interval_seconds == 30
        assert config.cycle_settings.max_consecutive_empty_cycles == 3
        assert config.cycle_settings.empty_cycle_wait_seconds == 60

    def test_正常系_dry_runフラグが反映される(self, tmp_path: Path) -> None:
        config_path = _make_config_json(tmp_path)
        args = argparse.Namespace(
            until="23:30",
            genre=None,
            dry_run=True,
            max_cycles=0,
        )
        config = load_config(args, config_path=config_path)
        assert config.dry_run is True

    def test_正常系_max_cyclesのデフォルトは0(self, tmp_path: Path) -> None:
        config_path = _make_config_json(tmp_path)
        args = argparse.Namespace(
            until="23:30",
            genre=None,
            dry_run=False,
            max_cycles=0,
        )
        config = load_config(args, config_path=config_path)
        assert config.max_cycles == 0

    def test_正常系_max_cyclesが指定値で反映される(self, tmp_path: Path) -> None:
        config_path = _make_config_json(tmp_path)
        args = argparse.Namespace(
            until="12:00",
            genre="spiritual",
            dry_run=False,
            max_cycles=10,
        )
        config = load_config(args, config_path=config_path)
        assert config.max_cycles == 10
        assert config.genre == "spiritual"

    def test_異常系_不正な時刻フォーマットでValueError(self, tmp_path: Path) -> None:
        config_path = _make_config_json(tmp_path)
        args = argparse.Namespace(
            until="invalid",
            genre=None,
            dry_run=False,
            max_cycles=0,
        )
        with pytest.raises(ValueError, match="until"):
            load_config(args, config_path=config_path)

    def test_異常系_設定ファイルが存在しないでFileNotFoundError(self) -> None:
        args = argparse.Namespace(
            until="23:30",
            genre=None,
            dry_run=False,
            max_cycles=0,
        )
        with pytest.raises(FileNotFoundError):
            load_config(args, config_path=Path("/nonexistent/config.json"))
