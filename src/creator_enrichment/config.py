"""creator_enrichment 設定管理.

CLI 引数パース + creator-enrichment-config.json 読み込みを担当する。
OrchestratorConfig / CycleSettings dataclass を定義し、
GENRE_NAMES バリデーションをここで一元管理する。

Usage
-----
::

    from creator_enrichment.config import parse_args, load_config

    args = parse_args()
    config = load_config(args)
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------
GENRE_NAMES: list[str] = ["career", "beauty-romance", "spiritual"]
"""有効なジャンル名のリスト."""

ANTHROPIC_MODEL: str = "claude-haiku-4-5-20251001"
"""Anthropic API で使用するモデル名."""

ANTHROPIC_MAX_TOKENS: int = 2000
"""Anthropic API 呼び出しの max_tokens."""

_DEFAULT_CONFIG_PATH = Path("data/config/creator-enrichment-config.json")


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class CycleSettings:
    """サイクル制御設定.

    Attributes
    ----------
    min_cycle_interval_seconds : int
        サイクル間の最小間隔（秒）
    max_consecutive_empty_cycles : int
        連続空サイクルの最大回数
    empty_cycle_wait_seconds : int
        空サイクル後の待機時間（秒）
    """

    min_cycle_interval_seconds: int
    max_consecutive_empty_cycles: int
    empty_cycle_wait_seconds: int


@dataclass
class OrchestratorConfig:
    """オーケストレーター設定.

    Attributes
    ----------
    until_time : datetime.time
        終了時刻
    genre : str | None
        対象ジャンル（None の場合は全ジャンル）
    dry_run : bool
        ドライラン実行フラグ
    max_cycles : int
        最大サイクル数（0 = 無制限）
    cycle_settings : CycleSettings
        サイクル制御設定
    """

    until_time: datetime.time
    genre: str | None
    dry_run: bool
    max_cycles: int
    cycle_settings: CycleSettings


# ---------------------------------------------------------------------------
# CLI 引数パース
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """CLI 引数をパースする.

    Parameters
    ----------
    argv : list[str] | None
        引数リスト（None の場合は sys.argv を使用）

    Returns
    -------
    argparse.Namespace
        パース結果
    """
    parser = argparse.ArgumentParser(
        description="creator-enrichment オーケストレーター",
    )
    parser.add_argument(
        "--until",
        required=True,
        help="終了時刻 (HH:MM 形式)",
    )
    parser.add_argument(
        "--genre",
        default=None,
        help=f"対象ジャンル ({', '.join(GENRE_NAMES)})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="ドライラン実行（パイプライン投入をスキップ）",
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=0,
        help="最大サイクル数 (0 = 無制限, デフォルト: 0)",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# 設定ファイル読み込み
# ---------------------------------------------------------------------------
def load_config(
    args: argparse.Namespace,
    *,
    config_path: Path | None = None,
) -> OrchestratorConfig:
    """CLI 引数と設定ファイルから OrchestratorConfig を生成する.

    Parameters
    ----------
    args : argparse.Namespace
        parse_args() の返却値
    config_path : Path | None
        設定ファイルパス（None の場合はデフォルトパス）

    Returns
    -------
    OrchestratorConfig
        オーケストレーター設定

    Raises
    ------
    FileNotFoundError
        設定ファイルが存在しない場合
    ValueError
        不正なジャンル名または時刻フォーマットの場合
    """
    path = config_path or _DEFAULT_CONFIG_PATH

    # --- ジャンルバリデーション ---
    if args.genre is not None and args.genre not in GENRE_NAMES:
        msg = f"Invalid genre: {args.genre!r}. Valid genres: {GENRE_NAMES}"
        logger.error(msg)
        raise ValueError(msg)

    # --- 時刻パース ---
    try:
        parts = args.until.split(":")
        if len(parts) != 2:
            raise ValueError
        hour, minute = int(parts[0]), int(parts[1])
        until_time = datetime.time(hour, minute)
    except (ValueError, IndexError):
        msg = f"Invalid until time format: {args.until!r}. Expected HH:MM"
        logger.error(msg)
        raise ValueError(msg) from None

    # --- 設定ファイル読み込み ---
    if not path.exists():
        msg = f"Config file not found: {path}"
        logger.error(msg)
        raise FileNotFoundError(msg)

    raw = json.loads(path.read_text(encoding="utf-8"))
    logger.info("Config loaded from %s (version=%s)", path, raw.get("version"))

    # --- CycleSettings マッピング ---
    cs_raw = raw.get("cycle_settings", {})
    cycle_settings = CycleSettings(
        min_cycle_interval_seconds=cs_raw.get("min_cycle_interval_seconds", 30),
        max_consecutive_empty_cycles=cs_raw.get("max_consecutive_empty_cycles", 3),
        empty_cycle_wait_seconds=cs_raw.get("empty_cycle_wait_seconds", 60),
    )

    config = OrchestratorConfig(
        until_time=until_time,
        genre=args.genre,
        dry_run=args.dry_run,
        max_cycles=args.max_cycles,
        cycle_settings=cycle_settings,
    )
    logger.info(
        "OrchestratorConfig created: genre=%s, until=%s, dry_run=%s, max_cycles=%s",
        config.genre,
        config.until_time,
        config.dry_run,
        config.max_cycles,
    )
    return config
