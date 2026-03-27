"""SNS 自動投稿スクリプト — auto_poster.py.

Wave 1: 基本構造の実装
  - AutoPosterConfig: CLI 引数を受け取る dataclass
  - SlotMatcher: 現在時刻とスロット時刻を比較し、±tolerance 分以内のスロットを返す
  - DraftReader: creator/{account}/drafts/ から現在週のディレクトリを検出し meta.json をロード
  - SlotInfo: --dry-run 時に出力するスロット情報
  - main(): Config 生成 → アカウントループ → DraftReader → SlotMatcher → --dry-run 出力

使用例::

    uv run python scripts/auto_poster.py --dry-run --account mitsuki
    uv run python scripts/auto_poster.py --force-slot S1
    uv run python scripts/auto_poster.py --tolerance 30
    uv run python scripts/auto_poster.py --week 2026-03-31

ログファイル: logs/auto_poster.jsonl（JSON Lines、append）
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from pathlib import Path

from data_paths import get_path
from quants.utils.logging_config import get_logger, setup_logging

# ---------------------------------------------------------------------------
# 定数定義
# ---------------------------------------------------------------------------

JST = ZoneInfo("Asia/Tokyo")

SLOT_TIME_MAP: dict[str, str] = {
    "朝": "07:30",
    "昼": "12:30",
    "夜": "20:30",
}
"""スロット名 → 投稿時刻のマッピング。"""

SLOT_INDEX_MAP: dict[str, str] = {
    "S1": "朝",
    "S2": "昼",
    "S3": "夜",
}
"""--force-slot 引数 → スロット名のマッピング。"""

DAY_DIR_MAP_MITSUKI: dict[str, str] = {
    "月": "day_1_月",
    "火": "day_2_火",
    "水": "day_3_水",
    "木": "day_4_木",
    "金": "day_5_金",
    "土": "day_6_土",
    "日": "day_7_日",
}
"""mitsuki アカウントの曜日ラベル → ディレクトリ名マッピング。"""

DAY_DIR_MAP_CAREER_SISTER: dict[str, str] = {
    "月": "day_1_mon",
    "火": "day_2_tue",
    "水": "day_3_wed",
    "木": "day_4_thu",
    "金": "day_5_fri",
    "土": "day_6_sat",
    "日": "day_7_sun",
}
"""career_sister アカウントの曜日ラベル → ディレクトリ名マッピング。"""

ACCOUNTS: list[str] = ["career_sister", "mitsuki"]
"""対応しているアカウント一覧。"""

# ---------------------------------------------------------------------------
# データクラス定義
# ---------------------------------------------------------------------------


@dataclass
class AutoPosterConfig:
    """CLI 引数を受け取る設定 dataclass.

    Parameters
    ----------
    account : str | None
        投稿対象アカウント名。None の場合は全アカウントを対象とする。
    dry_run : bool
        True の場合は実際には投稿せず、対象スロット一覧を出力のみ。
    include_note : bool
        note.com 投稿も含める場合は True。
    force_slot : str | None
        時刻マッチングを無視して強制的に投稿するスロット (S1/S2/S3)。
    tolerance : int
        スロット時刻に対する許容範囲（分）。デフォルト 15。
    week : str | None
        投稿対象週の週開始日（YYYY-MM-DD 形式）。None の場合は現在週を自動検出。
    """

    account: str | None = None
    dry_run: bool = False
    include_note: bool = False
    force_slot: str | None = None
    tolerance: int = 15
    week: str | None = None


@dataclass
class SlotInfo:
    """--dry-run 時に出力するスロット情報.

    Parameters
    ----------
    slot : str
        スロット名（朝/昼/夜）。
    time : str
        スロット投稿時刻（HH:MM 形式）。
    file : Path | None
        投稿ファイルのパス。存在しない場合は None。
    posted : bool
        既に投稿済みの場合 True。
    """

    slot: str
    time: str
    file: Path | None
    posted: bool
    meta: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# SlotMatcher
# ---------------------------------------------------------------------------


class SlotMatcher:
    """現在時刻とスロット時刻を比較し、±tolerance 分以内のスロットを返す.

    Parameters
    ----------
    slot_time_map : dict[str, str]
        スロット名 → 時刻（HH:MM 形式）のマッピング。
    tolerance : int
        許容範囲（分）。デフォルト 15。

    Examples
    --------
    >>> matcher = SlotMatcher(slot_time_map=SLOT_TIME_MAP, tolerance=15)
    >>> now = datetime(2026, 3, 27, 7, 30, tzinfo=JST)
    >>> matched = matcher.match(now)
    >>> matched["slot"]
    '朝'
    """

    # AIDEV-NOTE: スロット順序は S1=朝, S2=昼, S3=夜 の固定マッピング
    _SLOT_ORDER: ClassVar[list[str]] = ["朝", "昼", "夜"]

    def __init__(
        self,
        slot_time_map: dict[str, str] | None = None,
        tolerance: int = 15,
    ) -> None:
        self._slot_time_map = slot_time_map or SLOT_TIME_MAP
        self._tolerance = tolerance
        self._logger = get_logger(__name__)

    def match(self, now: datetime) -> dict[str, Any] | None:
        """現在時刻から ±tolerance 以内のスロットを検索する.

        Parameters
        ----------
        now : datetime
            比較する現在時刻（タイムゾーン付き推奨）。

        Returns
        -------
        dict[str, Any] | None
            マッチしたスロット情報 {"slot": ..., "time": ...}、
            マッチなしの場合は None。
        """
        now_jst = now.astimezone(JST)
        now_minutes = now_jst.hour * 60 + now_jst.minute

        for slot_name, time_str in self._slot_time_map.items():
            h, m = map(int, time_str.split(":"))
            slot_minutes = h * 60 + m
            diff = abs(now_minutes - slot_minutes)
            if diff <= self._tolerance:
                self._logger.debug(
                    "slot_matched",
                    slot=slot_name,
                    time=time_str,
                    diff_minutes=diff,
                )
                return {"slot": slot_name, "time": time_str}

        self._logger.debug(
            "no_slot_matched",
            now=now_jst.strftime("%H:%M"),
            tolerance=self._tolerance,
        )
        return None

    def match_force(self, now: datetime, force_slot: str) -> dict[str, Any] | None:
        """force_slot 指定時は時刻マッチングを無視してスロットを返す.

        Parameters
        ----------
        now : datetime
            現在時刻（参照のみ、マッチングには使用しない）。
        force_slot : str
            強制スロット指定（S1=朝, S2=昼, S3=夜）。

        Returns
        -------
        dict[str, Any] | None
            指定スロット情報、存在しない場合は None。
        """
        slot_name = SLOT_INDEX_MAP.get(force_slot)
        if slot_name is None:
            self._logger.warning("invalid_force_slot", force_slot=force_slot)
            return None

        time_str = self._slot_time_map.get(slot_name)
        if time_str is None:
            return None

        self._logger.debug(
            "force_slot_matched",
            force_slot=force_slot,
            slot=slot_name,
            time=time_str,
        )
        return {"slot": slot_name, "time": time_str}


# ---------------------------------------------------------------------------
# DraftReader
# ---------------------------------------------------------------------------


class DraftReader:
    """creator/{account}/drafts/ から現在週の meta.json をロードする.

    mitsuki と career_sister のフォーマット差異を吸収する。

    Parameters
    ----------
    drafts_root : Path
        drafts/ ディレクトリのルートパス。
    account : str
        アカウント名（"mitsuki" または "career_sister"）。

    Examples
    --------
    >>> reader = DraftReader(drafts_root=Path("creator/career_sister/drafts"), account="career_sister")
    >>> meta = reader.load()
    """

    def __init__(self, drafts_root: Path, account: str) -> None:
        self._drafts_root = drafts_root
        self._account = account
        self._logger = get_logger(__name__, account=account)

    def _get_day_dir_map(self) -> dict[str, str]:
        """アカウントに応じた曜日 → ディレクトリ名マッピングを返す."""
        if self._account == "mitsuki":
            return DAY_DIR_MAP_MITSUKI
        return DAY_DIR_MAP_CAREER_SISTER

    def _detect_week_dir(self, week: str | None) -> Path | None:
        """week ディレクトリを検出する.

        Parameters
        ----------
        week : str | None
            週開始日（YYYY-MM-DD 形式）。None の場合は最新週を自動検出。

        Returns
        -------
        Path | None
            検出された week ディレクトリのパス、存在しない場合は None。
        """
        if not self._drafts_root.exists():
            return None

        if week is not None:
            candidate = self._drafts_root / f"week_{week}"
            return candidate if candidate.exists() else None

        # week 未指定: week_YYYY-MM-DD ディレクトリの中で最新を返す
        candidates = sorted(
            [
                d
                for d in self._drafts_root.iterdir()
                if d.is_dir() and d.name.startswith("week_")
            ],
            key=lambda d: d.name,
            reverse=True,
        )
        if not candidates:
            return None
        return candidates[0]

    def load(self, week: str | None = None) -> dict[str, Any] | None:
        """meta.json をロードして返す.

        Parameters
        ----------
        week : str | None
            週開始日（YYYY-MM-DD 形式）。None の場合は最新週を自動検出。

        Returns
        -------
        dict[str, Any] | None
            meta.json の内容、見つからない場合は None。
        """
        week_dir = self._detect_week_dir(week)
        if week_dir is None:
            self._logger.info(
                "week_dir_not_found", week=week, drafts_root=str(self._drafts_root)
            )
            return None

        meta_path = week_dir / "meta.json"
        if not meta_path.exists():
            self._logger.warning("meta_json_not_found", path=str(meta_path))
            return None

        try:
            data: dict[str, Any] = json.loads(meta_path.read_text(encoding="utf-8"))
            self._logger.info(
                "meta_loaded", week_dir=week_dir.name, week_start=data.get("week_start")
            )
            return data
        except (json.JSONDecodeError, OSError) as e:
            self._logger.error("meta_load_failed", path=str(meta_path), error=str(e))
            return None

    def get_day_slots(self, meta: dict[str, Any], date: str) -> list[dict[str, Any]]:
        """特定日のスロット一覧を返す.

        Parameters
        ----------
        meta : dict[str, Any]
            meta.json の内容。
        date : str
            対象日付（YYYY-MM-DD 形式）。

        Returns
        -------
        list[dict[str, Any]]
            スロット情報のリスト。見つからない場合は空リスト。
        """
        for day in meta.get("days", []):
            if day.get("date") == date:
                return list(day.get("slots", []))
        return []

    def get_slot_file(
        self, week_dir_name: str, date: str, day_label: str, slot_name: str
    ) -> Path | None:
        """スロットの投稿ファイルパスを返す.

        Parameters
        ----------
        week_dir_name : str
            週ディレクトリ名（例: week_2026-03-24）。
        date : str
            日付（YYYY-MM-DD 形式）。
        day_label : str
            曜日ラベル（月/火/水/木/金/土/日）。
        slot_name : str
            スロット名（朝/昼/夜）。

        Returns
        -------
        Path | None
            threads_post.md へのパス、存在しない場合は None。
        """
        day_dir_map = self._get_day_dir_map()
        day_dir_name = day_dir_map.get(day_label)
        if day_dir_name is None:
            return None

        # slot ディレクトリ名マッピング（career_sister / mitsuki 共通）
        slot_dir_map = {
            "朝": "slot_1_morning",
            "昼": "slot_2_noon",
            "夜": "slot_3_evening",
        }
        slot_dir_name = slot_dir_map.get(slot_name)
        if slot_dir_name is None:
            return None

        candidate = (
            self._drafts_root
            / week_dir_name
            / day_dir_name
            / slot_dir_name
            / "threads_post.md"
        )
        return candidate if candidate.exists() else None


# ---------------------------------------------------------------------------
# ログ設定
# ---------------------------------------------------------------------------

logger = get_logger(__name__)


def _setup_file_logger(log_path: Path) -> None:
    """JSON Lines ファイルロガーを設定する.

    Parameters
    ----------
    log_path : Path
        ログファイルのパス（logs/auto_poster.jsonl）。
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    logging.root.addHandler(file_handler)


# ---------------------------------------------------------------------------
# CLI パーサー
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """CLI 引数パーサーを構築して返す."""
    parser = argparse.ArgumentParser(
        description="SNS 自動投稿スクリプト",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  %(prog)s                                  # 全アカウント、現在時刻基準
  %(prog)s --dry-run                        # 投稿せず対象表示
  %(prog)s --account mitsuki               # 特定アカウントのみ
  %(prog)s --force-slot S1                 # 時刻無視で朝スロット
  %(prog)s --tolerance 30                  # ±30分の許容範囲
  %(prog)s --week 2026-03-31               # 特定週を指定
""",
    )
    parser.add_argument(
        "--account",
        type=str,
        default=None,
        choices=ACCOUNTS,
        help="投稿対象アカウント。未指定の場合は全アカウント。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="実際には投稿せず、対象スロット一覧を出力する。",
    )
    parser.add_argument(
        "--include-note",
        action="store_true",
        default=False,
        help="note.com 投稿も含める。",
    )
    parser.add_argument(
        "--force-slot",
        type=str,
        default=None,
        metavar="SLOT",
        help="時刻マッチングを無視して投稿するスロット (S1=朝, S2=昼, S3=夜)。",
    )
    parser.add_argument(
        "--tolerance",
        type=int,
        default=15,
        metavar="MINUTES",
        help="スロット時刻に対する許容範囲（分）。デフォルト: 15。",
    )
    parser.add_argument(
        "--week",
        type=str,
        default=None,
        metavar="YYYY-MM-DD",
        help="投稿対象週の週開始日（YYYY-MM-DD 形式）。未指定の場合は現在週を自動検出。",
    )
    return parser


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """SNS 自動投稿スクリプトのエントリポイント.

    Parameters
    ----------
    argv : list[str] | None
        CLI 引数リスト。None の場合は sys.argv を使用。

    Returns
    -------
    int
        終了コード（0: 成功, 1: エラー）。
    """
    # ログ初期化
    setup_logging(level="INFO", format="console")
    log_path = get_path("..") / "logs" / "auto_poster.jsonl"
    _setup_file_logger(log_path)

    parser = _build_parser()
    args = parser.parse_args(argv)

    config = AutoPosterConfig(
        account=args.account,
        dry_run=args.dry_run,
        include_note=args.include_note,
        force_slot=args.force_slot,
        tolerance=args.tolerance,
        week=args.week,
    )

    logger.info(
        "auto_poster_started",
        account=config.account,
        dry_run=config.dry_run,
        force_slot=config.force_slot,
        tolerance=config.tolerance,
        week=config.week,
    )

    now = datetime.now(tz=JST)
    matcher = SlotMatcher(slot_time_map=SLOT_TIME_MAP, tolerance=config.tolerance)

    # 対象アカウントを決定
    target_accounts = [config.account] if config.account else ACCOUNTS

    for account in target_accounts:
        logger.info("processing_account", account=account)
        _process_account(account, config, now, matcher)

    logger.info("auto_poster_finished")
    return 0


def _process_account(
    account: str,
    config: AutoPosterConfig,
    now: datetime,
    matcher: SlotMatcher,
) -> None:
    """単一アカウントの投稿処理を実行する.

    Parameters
    ----------
    account : str
        対象アカウント名。
    config : AutoPosterConfig
        CLI 設定。
    now : datetime
        現在時刻（JST）。
    matcher : SlotMatcher
        スロットマッチャー。
    """
    creator_root = get_path("..") / "creator" / account
    drafts_root = creator_root / "drafts"

    reader = DraftReader(drafts_root=drafts_root, account=account)
    meta = reader.load(week=config.week)
    if meta is None:
        logger.warning("no_meta_found", account=account, week=config.week)
        return

    # 本日の日付
    today_str = now.strftime("%Y-%m-%d")

    # 対象スロットを決定
    if config.force_slot:
        matched = matcher.match_force(now, config.force_slot)
    else:
        matched = matcher.match(now)

    # --dry-run: 本日のスロット一覧を出力
    if config.dry_run:
        _print_dry_run(account, meta, reader, today_str, matched)
        return

    if matched is None:
        logger.info("no_slot_matched", account=account, now=now.strftime("%H:%M"))
        return

    logger.info(
        "slot_to_post",
        account=account,
        slot=matched["slot"],
        time=matched["time"],
        today=today_str,
    )


def _print_dry_run(
    account: str,
    meta: dict[str, Any],
    reader: DraftReader,
    today_str: str,
    matched: dict[str, Any] | None,
) -> None:
    """--dry-run 時のスロット一覧を出力する.

    Parameters
    ----------
    account : str
        アカウント名。
    meta : dict[str, Any]
        meta.json の内容。
    reader : DraftReader
        DraftReader インスタンス。
    today_str : str
        本日の日付文字列（YYYY-MM-DD）。
    matched : dict[str, Any] | None
        マッチしたスロット情報、またはNone。
    """
    week_start = meta.get("week_start", "unknown")
    week_dir_name = f"week_{week_start}"

    slots = reader.get_day_slots(meta, date=today_str)

    # 今日の day_label を取得
    day_label = ""
    for day in meta.get("days", []):
        if day.get("date") == today_str:
            day_label = day.get("day_label", "")
            break

    print(f"\n[{account}] Dry-run mode — {today_str}")
    print(f"  週: {week_start}")
    print(f"  マッチしたスロット: {matched['slot'] if matched else 'なし'}")
    print("  ─────────────────────────────────")
    print(f"  {'スロット':<6} {'時刻':<8} {'ファイル':<30} {'投稿状態'}")
    print("  ─────────────────────────────────")

    for slot_meta in slots:
        slot_name = slot_meta.get("slot", "")
        time_str = SLOT_TIME_MAP.get(slot_name, "?:??")
        posted = slot_meta.get("status") == "published"
        file_path = reader.get_slot_file(week_dir_name, today_str, day_label, slot_name)
        file_str = str(file_path) if file_path else "（なし）"

        info = SlotInfo(
            slot=slot_name,
            time=time_str,
            file=file_path,
            posted=posted,
            meta=slot_meta,
        )

        status_str = "投稿済" if info.posted else "未投稿"
        print(f"  {info.slot:<6} {info.time:<8} {file_str:<30} {status_str}")

    print()


if __name__ == "__main__":
    sys.exit(main())
