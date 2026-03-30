"""SNS 自動投稿スクリプト — auto_poster.py.

Wave 1: 基本構造の実装
  - AutoPosterConfig: CLI 引数を受け取る dataclass
  - SlotMatcher: 現在時刻とスロット時刻を比較し、±tolerance 分以内のスロットを返す
  - DraftReader: creator/{account}/drafts/ から現在週のディレクトリを検出し meta.json をロード
  - SlotInfo: --dry-run 時に出力するスロット情報
  - main(): Config 生成 → アカウントループ → DraftReader → SlotMatcher → --dry-run 出力

Wave 2: mitsuki Threads 投稿 + StateUpdater
  - AccountPoster: mitsuki の Threads 投稿実行（フロントマター解析・topic_tag 追記）
  - StateUpdater: meta.json / posting_state.json 更新（filelock による排他制御）

Wave 3: career_sister Instagram カルーセル投稿 + エラー分離
  - CareerSisterInstagramPoster: carousel/slide_*.png を R2 にアップロードし Instagram 投稿
  - Threads・Instagram 投稿が独立した try/except で実装
  - StateUpdater.update_meta に instagram_permalink サポート追加

Wave 4: リトライ戦略（tenacity）+ 結果サマリー出力
  - _is_retryable_error(): HTTP 429/500/502/503/504・ConnectError・TimeoutError を判定
  - AccountPoster.post(): tenacity による max 3回リトライ（5s→20s→80s）
  - CareerSisterInstagramPoster.post(): 同上
  - PostingSummary: 投稿成功/スキップ/失敗の集計 dataclass
  - print_summary(): アカウント別サマリー出力
  - main(): 末尾で print_summary() を呼ぶ

使用例::

    uv run python scripts/auto_poster.py --dry-run --account mitsuki
    uv run python scripts/auto_poster.py --account mitsuki --force-slot S1
    uv run python scripts/auto_poster.py --tolerance 30
    uv run python scripts/auto_poster.py --week 2026-03-31

ログファイル: logs/auto_poster.jsonl（JSON Lines、append）
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import re
import subprocess
import sys
import time as time_mod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar
from zoneinfo import ZoneInfo

import filelock
import httpx
import tenacity

from creator.image_hosting import R2ImageHost
from creator.poster import (
    InstagramConfig,
    InstagramPoster,
    PostResult,
    ThreadsConfig,
    ThreadsPoster,
)
from data_paths import get_path, get_project_root
from utils_core.logging.config import get_logger, setup_logging

# ---------------------------------------------------------------------------
# 定数定義
# ---------------------------------------------------------------------------

JST = ZoneInfo("Asia/Tokyo")

SLOT_TIME_MAP_CAREER_SISTER: dict[str, str] = {
    "朝": "07:30",
    "昼": "12:30",
    "夜": "20:30",
}
"""career_sister のスロット名 → 投稿時刻マッピング。"""

SLOT_TIME_MAP_MITSUKI: dict[str, str] = {
    "S1": "07:00",
    "S2": "12:00",
    "S3": "15:00",
    "S4": "19:00",
    "S5": "22:00",
}
"""mitsuki のスロット名 → 投稿時刻マッピング。"""

SLOT_TIME_MAP_KUROTO_AREA: dict[str, str] = {
    "S1": "07:30",
    "S2": "12:00",
    "S3": "18:00",
    "S4": "20:00",
    "S5": "21:30",
}
"""kuroto_area のスロット名 → 投稿時刻マッピング。"""

# AIDEV-NOTE: Backward-compat alias for tests written before account-specific maps were introduced.
SLOT_TIME_MAP: dict[str, str] = SLOT_TIME_MAP_CAREER_SISTER

SLOT_INDEX_MAP_CAREER_SISTER: dict[str, str] = {
    "S1": "朝",
    "S2": "昼",
    "S3": "夜",
}
"""career_sister の --force-slot 引数 → スロット名マッピング。"""

SLOT_INDEX_MAP_MITSUKI: dict[str, str] = {
    "S1": "S1",
    "S2": "S2",
    "S3": "S3",
    "S4": "S4",
    "S5": "S5",
}
"""mitsuki の --force-slot 引数 → スロット名マッピング。"""

SLOT_INDEX_MAP_KUROTO_AREA: dict[str, str] = SLOT_INDEX_MAP_MITSUKI
"""kuroto_area の --force-slot 引数 → スロット名マッピング。"""


def _get_slot_time_map(account: str) -> dict[str, str]:
    """アカウントに応じたスロット時刻マッピングを返す."""
    if account == "mitsuki":
        return SLOT_TIME_MAP_MITSUKI
    if account == "kuroto_area":
        return SLOT_TIME_MAP_KUROTO_AREA
    return SLOT_TIME_MAP_CAREER_SISTER


def _get_slot_index_map(account: str) -> dict[str, str]:
    """アカウントに応じた --force-slot マッピングを返す."""
    if account == "mitsuki":
        return SLOT_INDEX_MAP_MITSUKI
    if account == "kuroto_area":
        return SLOT_INDEX_MAP_KUROTO_AREA
    return SLOT_INDEX_MAP_CAREER_SISTER

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

DAY_DIR_MAP_KUROTO_AREA: dict[str, str] = DAY_DIR_MAP_MITSUKI
"""kuroto_area アカウントの曜日ラベル → ディレクトリ名マッピング（mitsuki と同一）。"""

ACCOUNTS: list[str] = ["career_sister", "mitsuki", "kuroto_area"]
"""対応しているアカウント一覧。"""

# ---------------------------------------------------------------------------
# リトライ定数
# ---------------------------------------------------------------------------

RETRYABLE_STATUS_CODES: frozenset[int] = frozenset([429, 500, 502, 503, 504])
"""リトライ対象の HTTP ステータスコード。"""

RETRY_MAX_ATTEMPTS: int = 3
"""最大リトライ回数（初回含む）。"""

RETRY_WAIT_MULTIPLIER: float = 5.0
"""指数バックオフの乗数（秒）。5s→20s→80s。"""

RETRY_WAIT_MAX: float = 80.0
"""指数バックオフの最大待機時間（秒）。"""

# ---------------------------------------------------------------------------
# マルチマシン対応定数（Wave 5）
# ---------------------------------------------------------------------------

NAS_LOCK_PATH: Path = Path(
    "/Volumes/personal_folder/Projects/note-finance/.auto_poster_lock"
)
"""NAS マウント時のロックファイルパス。"""

LOCAL_FALLBACK_LOCK: Path = Path(f"/tmp/note-finance-auto-poster-{os.getuid()}.lock")
"""NAS 未マウント時のフォールバックロックファイルパス（ユーザー固有）。"""

_NAS_MOUNT_POINT: Path = Path("/Volumes/personal_folder")
"""NAS マウントポイント。"""

_SYNC_NAS_SCRIPT: Path = Path(__file__).parent / "sync_nas.sh"
"""sync_nas.sh スクリプトのパス。"""


def _is_nas_mounted() -> bool:
    """NAS がマウントされているかを判定する."""
    return _NAS_MOUNT_POINT.is_mount()


def _compute_jitter_seconds(max_minutes: int) -> float:
    """正規分布で投稿前ランダム遅延秒数を算出する.

    半正規分布（|N(0, σ)|）を使い、0〜max_minutes の範囲に収める。
    σ = max_minutes / 3 とすることで、99.7% が max_minutes 以内に収まる。

    Parameters
    ----------
    max_minutes : int
        最大遅延（分）。0 の場合は 0.0 を返す。

    Returns
    -------
    float
        遅延秒数（0 以上）。
    """
    if max_minutes <= 0:
        return 0.0
    sigma = max_minutes / 3.0
    delay = abs(random.gauss(0, sigma))
    delay = min(delay, float(max_minutes))
    return delay * 60.0


def _is_retryable_error(exc: BaseException) -> bool:
    """例外がリトライ対象かを判定する.

    Parameters
    ----------
    exc : BaseException
        判定する例外。

    Returns
    -------
    bool
        リトライ対象の場合は True、即座に失敗すべき場合は False。
    """
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS_CODES
    return isinstance(exc, (httpx.ConnectError, httpx.TimeoutException))


def _log_retry(retry_state: tenacity.RetryCallState) -> None:
    """リトライ前のログ出力.

    Parameters
    ----------
    retry_state : tenacity.RetryCallState
        tenacity リトライ状態。
    """
    exc = retry_state.outcome.exception()  # type: ignore[union-attr]
    _retry_logger = get_logger(__name__)
    _retry_logger.warning(
        "api_retry",
        attempt=retry_state.attempt_number,
        exception=str(exc),
    )


# ---------------------------------------------------------------------------
# NasLockManager（Wave 5: マルチマシン対応）
# ---------------------------------------------------------------------------


class NasLockManager:
    """マルチマシン排他制御のためのロックマネージャー.

    NAS がマウントされている場合は NAS 上のロックファイルを使用し、
    複数マシン間での同時投稿を防止する。
    NAS 未マウント時はローカルの /tmp フォールバックを使用するが、
    マルチマシン環境では NAS マウントが必須である旨を警告する。

    Examples
    --------
    >>> manager = NasLockManager()
    >>> lock = manager.get_lock()
    >>> with lock:
    ...     # 排他制御された処理
    ...     pass
    """

    def __init__(self) -> None:
        self._logger = get_logger(__name__)

    def get_lock(self) -> filelock.FileLock:
        """ロックオブジェクトを取得する.

        NAS がマウントされている場合は NAS_LOCK_PATH を使用する。
        NAS 未マウント時は LOCAL_FALLBACK_LOCK を使用し、WARNING を出力する。

        Returns
        -------
        filelock.FileLock
            ロックオブジェクト。
        """
        if _is_nas_mounted():
            self._logger.debug("nas_lock_acquired", lock_path=str(NAS_LOCK_PATH))
            return filelock.FileLock(str(NAS_LOCK_PATH))
        else:
            self._logger.warning(
                "nas_not_mounted_fallback_lock",
                fallback_lock=str(LOCAL_FALLBACK_LOCK),
                message=(
                    "NAS not mounted. Falling back to local lock. "
                    "Multi-machine operation requires NAS mount (マルチマシン運用時は NAS マウント必須)."
                ),
            )
            return filelock.FileLock(str(LOCAL_FALLBACK_LOCK))


# ---------------------------------------------------------------------------
# NasSyncer（Wave 5: drafts 同期）
# ---------------------------------------------------------------------------


class NasSyncer:
    """NAS と drafts ディレクトリを同期するクラス.

    scripts/sync_nas.sh を使用して、NAS との間で設定・データを同期する。
    NAS 未マウント時は pull/push をスキップする。

    Examples
    --------
    >>> syncer = NasSyncer()
    >>> syncer.pull()   # 投稿前: NAS → ローカル
    >>> syncer.push()   # 投稿後: ローカル → NAS
    """

    def __init__(self) -> None:
        self._logger = get_logger(__name__)

    def pull(self) -> None:
        """NAS からローカルへ同期する（投稿前実行）.

        NAS がマウントされていない場合はスキップする。
        """
        if not _is_nas_mounted():
            self._logger.debug("nas_not_mounted_skip_pull")
            return

        self._logger.info("nas_sync_pull_start")
        subprocess.run(
            ["bash", str(_SYNC_NAS_SCRIPT), "--pull"],
            check=True,
            capture_output=True,
            timeout=120,
        )
        self._logger.info("nas_sync_pull_done")

    def push(self) -> None:
        """ローカルから NAS へ同期する（投稿後実行）.

        NAS がマウントされていない場合はスキップする。
        """
        if not _is_nas_mounted():
            self._logger.debug("nas_not_mounted_skip_push")
            return

        self._logger.info("nas_sync_push_start")
        subprocess.run(
            ["bash", str(_SYNC_NAS_SCRIPT), "--push"],
            check=True,
            capture_output=True,
            timeout=120,
        )
        self._logger.info("nas_sync_push_done")


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
    jitter: int = 0


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


@dataclass
class PostingSummary:
    """投稿結果の集計 dataclass.

    Parameters
    ----------
    posted : int
        投稿成功スロット数。
    skipped : int
        投稿スキップスロット数（既投稿・ファイルなし等）。
    failed : int
        投稿失敗スロット数（リトライ上限到達等）。
    """

    posted: int = 0
    skipped: int = 0
    failed: int = 0


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

    def match_force(
        self, now: datetime, force_slot: str, account: str = "career_sister"
    ) -> dict[str, Any] | None:
        """force_slot 指定時は時刻マッチングを無視してスロットを返す.

        Parameters
        ----------
        now : datetime
            現在時刻（参照のみ、マッチングには使用しない）。
        force_slot : str
            強制スロット指定（S1-S5）。
        account : str
            アカウント名（スロット名解決に使用）。

        Returns
        -------
        dict[str, Any] | None
            指定スロット情報、存在しない場合は None。
        """
        slot_index_map = _get_slot_index_map(account)
        slot_name = slot_index_map.get(force_slot)
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
        if self._account == "kuroto_area":
            return DAY_DIR_MAP_KUROTO_AREA
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
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", week):
                raise ValueError(f"week は YYYY-MM-DD 形式で指定してください: {week!r}")
            candidate = self._drafts_root / f"week_{week}"
            # パストラバーサル防止: drafts_root 配下であることを確認
            if not candidate.resolve().is_relative_to(self._drafts_root.resolve()):
                raise ValueError(f"week が drafts_root 外を指しています: {week!r}")
            return candidate if candidate.exists() else None

        # week 未指定: week_start <= 今日 の条件を満たす最新週を返す
        today_str = datetime.now(tz=JST).strftime("%Y-%m-%d")
        candidates = sorted(
            [
                d
                for d in self._drafts_root.iterdir()
                if d.is_dir()
                and re.fullmatch(r"week_\d{4}-\d{2}-\d{2}", d.name)
                and d.name[5:] <= today_str  # week_start <= today
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
        self,
        week_dir_name: str,
        date: str,
        day_label: str,
        slot_name: str,
        meta: dict[str, Any] | None = None,
    ) -> Path | None:
        """スロットの投稿ファイルパスを返す.

        mitsuki / kuroto_area は meta.json の ``file`` フィールドから解決する。
        career_sister はディレクトリ構造ベース（slot_1_morning/threads_post.md）で解決する。

        Parameters
        ----------
        week_dir_name : str
            週ディレクトリ名（例: week_2026-03-24）。
        date : str
            日付（YYYY-MM-DD 形式）。
        day_label : str
            曜日ラベル（月/火/水/木/金/土/日）。
        slot_name : str
            スロット名（朝/昼/夜 or S1-S5）。
        meta : dict[str, Any] | None
            meta.json の内容。file フィールドによるパス解決に使用。

        Returns
        -------
        Path | None
            投稿ファイルへのパス、存在しない場合は None。
        """
        # mitsuki / kuroto_area: meta.json の file フィールドから解決
        if self._account in ("mitsuki", "kuroto_area") and meta:
            for day in meta.get("days", []):
                if day.get("date") == date:
                    for s in day.get("slots", []):
                        if s.get("slot") == slot_name:
                            file_path = s.get("file")
                            if file_path:
                                candidate = self._drafts_root / week_dir_name / file_path
                                return candidate if candidate.exists() else None
            return None

        # career_sister: ディレクトリ構造ベースで解決
        day_dir_map = self._get_day_dir_map()
        day_dir_name = day_dir_map.get(day_label)
        if day_dir_name is None:
            return None

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
# AccountPoster
# ---------------------------------------------------------------------------


class AccountPoster:
    """アカウント別 Threads 投稿クライアント.

    threads_post.md のフロントマターを解析し、topic_tag を本文末尾に追記して投稿する。

    Parameters
    ----------
    account : str
        アカウント名（"mitsuki" または "career_sister"）。

    Examples
    --------
    >>> poster = AccountPoster(account="mitsuki")
    >>> result = poster.post("---\\ntopic_tag: '#資産形成'\\n---\\n本文です。")
    """

    def __init__(self, account: str) -> None:
        self.account = account
        self._logger = get_logger(__name__, account=account)

    def _parse_front_matter(self, content: str) -> tuple[str | None, str]:
        """YAML フロントマターを 1 回でパースし (topic_tag, body) を返す.

        Parameters
        ----------
        content : str
            threads_post.md の全文。

        Returns
        -------
        tuple[str | None, str]
            (topic_tag の値または None, フロントマターを除いた本文)。
        """
        if not content.startswith("---"):
            return None, content

        lines = content.splitlines()
        topic_tag: str | None = None
        end_idx = -1
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                end_idx = i
                break
            if line.startswith("topic_tag:"):
                value = line[len("topic_tag:") :].strip().strip("\"'")
                topic_tag = value if value else None

        if end_idx == -1:
            return None, content

        body = "\n".join(lines[end_idx + 1 :]).strip()
        return topic_tag, body

    def _extract_topic_tag(self, content: str) -> str | None:
        """YAML フロントマターから topic_tag を抽出する.

        Parameters
        ----------
        content : str
            threads_post.md の全文。

        Returns
        -------
        str | None
            topic_tag の値、存在しない場合は None。
        """
        topic_tag, _ = self._parse_front_matter(content)
        return topic_tag

    def _extract_body(self, content: str) -> str:
        """YAML フロントマターを除いた本文を返す.

        Parameters
        ----------
        content : str
            threads_post.md の全文。

        Returns
        -------
        str
            フロントマターを除いた本文テキスト。
        """
        _, body = self._parse_front_matter(content)
        return body

    def post(self, content: str) -> PostResult:
        """Threads に投稿する（リトライ付き）.

        フロントマターから topic_tag を抽出し、本文末尾に追記して投稿する。
        HTTP 429/500/502/503/504 および ConnectError/TimeoutError 時は
        tenacity により max 3回リトライ（5s→20s→80s）。
        HTTP 400/401/403 は即座に失敗。

        Parameters
        ----------
        content : str
            threads_post.md の全文（YAML フロントマターを含む場合もある）。

        Returns
        -------
        PostResult
            投稿結果（media_id、permalink を含む）。
        """
        # フロントマターを 1 回でパース（二重解析を回避）
        topic_tag, body = self._parse_front_matter(content)

        self._logger.info(
            "posting_to_threads",
            account=self.account,
            text_length=len(body),
            has_topic_tag=topic_tag is not None,
            topic_tag=topic_tag,
        )

        @tenacity.retry(
            retry=tenacity.retry_if_exception(_is_retryable_error),
            stop=tenacity.stop_after_attempt(RETRY_MAX_ATTEMPTS),
            wait=tenacity.wait_exponential(
                multiplier=RETRY_WAIT_MULTIPLIER, max=RETRY_WAIT_MAX
            ),
            before_sleep=_log_retry,
            reraise=True,
        )
        def _post_with_retry() -> PostResult:
            config = ThreadsConfig()
            threads_poster = ThreadsPoster(config)
            return threads_poster.post_text(body, topic_tag=topic_tag)

        result = _post_with_retry()

        self._logger.info(
            "threads_post_completed",
            account=self.account,
            media_id=result.media_id,
            permalink=result.permalink,
        )
        return result


# ---------------------------------------------------------------------------
# CareerSisterInstagramPoster
# ---------------------------------------------------------------------------


class CareerSisterInstagramPoster:
    """career_sister 専用 Instagram カルーセル投稿クライアント.

    carousel/slide_*.png を Cloudflare R2 にアップロードし、
    InstagramPoster.post_carousel() でカルーセル投稿を行う。

    キャプションは instagram_caption.md を優先し、存在しない場合は
    threads_post.md をフォールバックとして使用する。

    Examples
    --------
    >>> poster = CareerSisterInstagramPoster()
    >>> result = poster.post(slot_dir)
    """

    def __init__(self) -> None:
        self._logger = get_logger(__name__, account="career_sister")

    def _get_caption(self, slot_dir: Path) -> str:
        """Instagram キャプションを取得する.

        instagram_caption.md が存在する場合はその内容を返す。
        存在しない場合は threads_post.md をフォールバックとして返す。

        Parameters
        ----------
        slot_dir : Path
            スロットディレクトリのパス。

        Returns
        -------
        str
            キャプションテキスト。
        """
        caption_path = slot_dir / "instagram_caption.md"
        if caption_path.exists():
            self._logger.debug("instagram_caption_found", path=str(caption_path))
            return caption_path.read_text(encoding="utf-8")

        fallback_path = slot_dir / "threads_post.md"
        self._logger.warning(
            "instagram_caption_not_found_fallback",
            slot_dir=str(slot_dir),
            fallback=str(fallback_path),
        )
        return fallback_path.read_text(encoding="utf-8")

    def _get_carousel_images(self, slot_dir: Path) -> list[Path]:
        """carousel/slide_*.png をソートされたリストで返す.

        Parameters
        ----------
        slot_dir : Path
            スロットディレクトリのパス。

        Returns
        -------
        list[Path]
            ソートされた carousel 画像パスのリスト。carousel/ が存在しない場合は空リスト。
        """
        carousel_dir = slot_dir / "carousel"
        if not carousel_dir.exists():
            return []

        images = sorted(carousel_dir.glob("slide_*.png"))
        return images

    def post(self, slot_dir: Path) -> PostResult | None:
        """Instagram カルーセル投稿を実行する（リトライ付き）.

        R2 未設定の場合は WARNING を出力して None を返す。
        carousel 画像が存在しない場合も None を返す。
        HTTP 429/500/502/503/504 および ConnectError/TimeoutError 時は
        tenacity により max 3回リトライ（5s→20s→80s）。

        Parameters
        ----------
        slot_dir : Path
            スロットディレクトリのパス。

        Returns
        -------
        PostResult | None
            投稿結果。スキップした場合は None。
        """
        host = R2ImageHost()
        if not host.is_configured:
            self._logger.warning(
                "r2_not_configured_skipping_instagram",
                slot_dir=str(slot_dir),
            )
            return None

        image_paths = self._get_carousel_images(slot_dir)
        if not image_paths:
            self._logger.warning(
                "no_carousel_images_found",
                slot_dir=str(slot_dir),
            )
            return None

        self._logger.info(
            "uploading_carousel_images",
            image_count=len(image_paths),
            slot_dir=str(slot_dir),
        )
        image_urls = host.upload_batch(list(image_paths), prefix="auto_poster")

        caption = self._get_caption(slot_dir)

        self._logger.info(
            "posting_instagram_carousel",
            image_count=len(image_urls),
            caption_length=len(caption),
        )

        @tenacity.retry(
            retry=tenacity.retry_if_exception(_is_retryable_error),
            stop=tenacity.stop_after_attempt(RETRY_MAX_ATTEMPTS),
            wait=tenacity.wait_exponential(
                multiplier=RETRY_WAIT_MULTIPLIER, max=RETRY_WAIT_MAX
            ),
            before_sleep=_log_retry,
            reraise=True,
        )
        def _post_carousel_with_retry() -> PostResult:
            config = InstagramConfig()
            ig_poster = InstagramPoster(config)
            return ig_poster.post_carousel(caption=caption, image_urls=image_urls)

        result = _post_carousel_with_retry()

        self._logger.info(
            "instagram_carousel_completed",
            media_id=result.media_id,
            permalink=result.permalink,
        )
        return result


# ---------------------------------------------------------------------------
# StateUpdater
# ---------------------------------------------------------------------------


class StateUpdater:
    """meta.json / posting_state.json の状態を更新する.

    filelock による排他制御で meta.json を保護し、
    投稿直前に再読み込みして二重投稿を防ぐ。

    Parameters
    ----------
    week_dir : Path
        週ディレクトリのパス（meta.json の親ディレクトリ）。
    posting_state_path : Path
        posting_state.json のパス。

    Examples
    --------
    >>> updater = StateUpdater(week_dir=Path("week_2026-03-24"), posting_state_path=Path("posting_state.json"), account="mitsuki")
    >>> updater.update_meta(date="2026-03-27", slot="朝", posted_at="...", permalink="...")
    """

    def __init__(
        self,
        week_dir: Path,
        posting_state_path: Path,
        account: str = "mitsuki",
    ) -> None:
        self._week_dir = week_dir
        self._meta_path = week_dir / "meta.json"
        self._lock_path = week_dir / "meta.json.lock"
        self._posting_state_path = posting_state_path
        self._account = account
        self._logger = get_logger(__name__, account=account)

    def check_already_posted(self, meta: dict[str, Any], date: str, slot: str) -> bool:
        """指定スロットが既に投稿済みかを確認する.

        アカウントによって投稿済みフラグの判定方法が異なる:
        - mitsuki: ``posted_at`` フィールドが存在するかで判定
        - career_sister: ``status == 'published'`` で判定

        Parameters
        ----------
        meta : dict[str, Any]
            meta.json の内容（最新の再読み込み済みデータを渡すこと）。
        date : str
            対象日付（YYYY-MM-DD 形式）。
        slot : str
            スロット名（朝/昼/夜）。

        Returns
        -------
        bool
            既に投稿済みの場合は True、未投稿の場合は False。
        """
        for day in meta.get("days", []):
            if day.get("date") == date:
                for slot_meta in day.get("slots", []):
                    if slot_meta.get("slot") == slot:
                        if self._account == "career_sister":
                            return slot_meta.get("status") == "published"
                        return slot_meta.get("posted_at") is not None
        return False

    def update_meta(
        self,
        date: str,
        slot: str,
        posted_at: str,
        permalink: str,
        instagram_permalink: str | None = None,
    ) -> None:
        """meta.json の指定スロットに posted_at と permalink を書き戻す.

        filelock で meta.json を排他制御し、投稿直前に再読み込みして
        二重投稿を防ぐ。

        Parameters
        ----------
        date : str
            対象日付（YYYY-MM-DD 形式）。
        slot : str
            スロット名（朝/昼/夜）。
        posted_at : str
            投稿日時（ISO 8601 形式）。
        permalink : str
            Threads 投稿の permalink URL。
        instagram_permalink : str | None
            Instagram 投稿の permalink URL（あれば）。career_sister のみ使用。
        """
        lock = filelock.FileLock(str(self._lock_path))
        with lock:
            # 投稿直前に meta.json を再読み込み（二重投稿防止）
            meta = json.loads(self._meta_path.read_text(encoding="utf-8"))

            # 既に投稿済みなら更新しない
            if self.check_already_posted(meta, date, slot):
                self._logger.warning(
                    "meta_already_posted_skip",
                    date=date,
                    slot=slot,
                )
                return

            # 対象スロットに書き戻す（アカウント別フィールド名）
            updated = False
            for day in meta.get("days", []):
                if day.get("date") == date:
                    for slot_meta in day.get("slots", []):
                        if slot_meta.get("slot") == slot:
                            if self._account == "career_sister":
                                slot_meta["status"] = "published"
                                slot_meta["published_at"] = posted_at
                                slot_meta["threads_permalink"] = permalink
                                if instagram_permalink is not None:
                                    slot_meta["instagram_permalink"] = (
                                        instagram_permalink
                                    )
                            else:
                                slot_meta["posted_at"] = posted_at
                                slot_meta["permalink"] = permalink
                            updated = True
                            break
                    if updated:
                        # career_sister: 全スロット投稿済み時に day.status を更新
                        if self._account == "career_sister":
                            all_published = all(
                                s.get("status") == "published"
                                for s in day.get("slots", [])
                            )
                            if all_published:
                                day["status"] = "published"
                                self._logger.info(
                                    "day_status_published",
                                    date=date,
                                )
                        break

            if not updated:
                self._logger.warning(
                    "meta_slot_not_found",
                    date=date,
                    slot=slot,
                )
                return

            self._meta_path.write_text(
                json.dumps(meta, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._logger.info(
                "meta_updated",
                date=date,
                slot=slot,
                posted_at=posted_at,
            )

    def update_note_meta(
        self,
        date: str,
        published_at: str,
        permalink: str,
    ) -> None:
        """meta.json の指定日の days[].note に published_at と permalink を書き戻す.

        note.com 投稿後に呼び出し、mitsuki の meta.json の ``days[].note``
        フィールドを更新する。filelock で meta.json を排他制御する。

        Parameters
        ----------
        date : str
            対象日付（YYYY-MM-DD 形式）。
        published_at : str
            投稿日時（ISO 8601 形式）。
        permalink : str
            note.com 投稿の下書き URL。
        """
        lock = filelock.FileLock(str(self._lock_path))
        with lock:
            meta = json.loads(self._meta_path.read_text(encoding="utf-8"))

            updated = False
            for day in meta.get("days", []):
                if day.get("date") == date:
                    if "note" not in day:
                        day["note"] = {}
                    day["note"]["published_at"] = published_at
                    day["note"]["permalink"] = permalink
                    updated = True
                    break

            if not updated:
                self._logger.warning(
                    "note_meta_date_not_found",
                    date=date,
                )
                return

            self._meta_path.write_text(
                json.dumps(meta, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._logger.info(
                "note_meta_updated",
                date=date,
                published_at=published_at,
                permalink=permalink,
            )

    def append_post_history(
        self,
        date: str,
        slot: str,
        slot_meta: dict[str, Any],
        posted_at: str,
        threads_permalink: str,
        instagram_permalink: str | None = None,
    ) -> None:
        """posting_state.json の post_history にエントリを追記する.

        Parameters
        ----------
        date : str
            投稿日付（YYYY-MM-DD 形式）。
        slot : str
            スロット名（朝/昼/夜）。
        slot_meta : dict[str, Any]
            meta.json のスロット情報（category, type, theme 等）。
        posted_at : str
            投稿日時（ISO 8601 形式）。
        threads_permalink : str
            Threads 投稿の permalink URL。
        instagram_permalink : str | None
            Instagram 投稿の permalink URL（あれば）。
        """
        # posting_state.json の読み込み（存在しない場合は空の構造を作成）
        if self._posting_state_path.exists():
            state = json.loads(self._posting_state_path.read_text(encoding="utf-8"))
        else:
            state = {"post_history": []}
            self._posting_state_path.parent.mkdir(parents=True, exist_ok=True)

        # post_id を生成（YYYY-MM-DD + ゼロ埋め3桁連番）
        existing_today = [
            e for e in state.get("post_history", []) if e.get("date") == date
        ]
        post_id = f"{date}_{len(existing_today) + 1:03d}"

        entry: dict[str, Any] = {
            "post_id": post_id,
            "date": date,
            "slot": slot,
            "category": slot_meta.get("category"),
            "type": slot_meta.get("type"),
            "theme": slot_meta.get("theme"),
            "material_ids": slot_meta.get("material_ids", []),
            "instagram": slot_meta.get("instagram", False),
            "posted_at": posted_at,
            "threads_permalink": threads_permalink,
            "instagram_permalink": instagram_permalink,
        }

        if "post_history" not in state:
            state["post_history"] = []
        state["post_history"].append(entry)

        self._posting_state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._logger.info(
            "post_history_appended",
            post_id=post_id,
            date=date,
            slot=slot,
            threads_permalink=threads_permalink,
        )


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
# サマリー出力
# ---------------------------------------------------------------------------


def print_summary(summaries: dict[str, PostingSummary]) -> None:
    """投稿結果のサマリーを標準出力に表示する.

    Parameters
    ----------
    summaries : dict[str, PostingSummary]
        アカウント名 → PostingSummary のマッピング。
    """
    print("\n=== Auto Poster Summary ===")
    for account, s in summaries.items():
        print(f"{account}:")
        print(f"  - posted: {s.posted} slots")
        print(f"  - skipped (already posted): {s.skipped} slots")
        print(f"  - failed: {s.failed} slots")
    print()


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
  %(prog)s --jitter 10                     # 投稿前に正規分布で0〜10分遅延
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
    parser.add_argument(
        "--jitter",
        type=int,
        default=10,
        metavar="MINUTES",
        help="投稿前のランダム遅延の最大値（分）。正規分布(σ=max/3)で0〜max分遅延する。0で無効。デフォルト: 10。",
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
    # ログ初期化（LOG_LEVEL / LOG_FORMAT 環境変数で制御可能）
    setup_logging(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format=os.environ.get("LOG_FORMAT", "console"),
    )
    log_path = get_project_root() / "logs" / "auto_poster.jsonl"
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
        jitter=args.jitter,
    )

    logger.info(
        "auto_poster_started",
        account=config.account,
        dry_run=config.dry_run,
        force_slot=config.force_slot,
        tolerance=config.tolerance,
        jitter=config.jitter,
        week=config.week,
    )

    now = datetime.now(tz=JST)

    # 対象アカウントを決定
    target_accounts = [config.account] if config.account else ACCOUNTS

    # Wave 5: マルチマシン対応 — ロック取得 → pull → 投稿ループ → push
    nas_lock_manager = NasLockManager()
    nas_syncer = NasSyncer()
    lock = nas_lock_manager.get_lock()

    summaries: dict[str, PostingSummary] = {}
    with lock:
        nas_syncer.pull()

        for account in target_accounts:
            logger.info("processing_account", account=account)
            slot_time_map = _get_slot_time_map(account)
            matcher = SlotMatcher(slot_time_map=slot_time_map, tolerance=config.tolerance)
            summaries[account] = _process_account(account, config, now, matcher)

        nas_syncer.push()

    logger.info("auto_poster_finished")
    print_summary(summaries)
    return 0


def _get_slot_meta(meta: dict[str, Any], date: str, slot: str) -> dict[str, Any]:
    """meta.json から指定日・スロットのメタ情報を返す.

    Parameters
    ----------
    meta : dict[str, Any]
        meta.json の内容。
    date : str
        対象日付（YYYY-MM-DD 形式）。
    slot : str
        スロット名（朝/昼/夜）。

    Returns
    -------
    dict[str, Any]
        スロットメタ情報。見つからない場合は空の dict。
    """
    for day in meta.get("days", []):
        if day.get("date") == date:
            for s in day.get("slots", []):
                if s.get("slot") == slot:
                    return s
    return {}


def _execute_post(
    account: str,
    slot_name: str,
    today_str: str,
    slot_file: Path,
    updater: StateUpdater,
    fresh_meta: dict[str, Any],
) -> bool:
    """Threads 投稿を実行し、状態を書き戻す.

    Parameters
    ----------
    account : str
        対象アカウント名。
    slot_name : str
        スロット名（朝/昼/夜）。
    today_str : str
        本日の日付文字列（YYYY-MM-DD）。
    slot_file : Path
        投稿ファイルのパス。
    updater : StateUpdater
        StateUpdater インスタンス。
    fresh_meta : dict[str, Any]
        最新の meta.json 内容。

    Returns
    -------
    bool
        Threads 投稿が成功した場合は True、失敗した場合は False。
    """
    slot_meta = _get_slot_meta(fresh_meta, today_str, slot_name)
    content = slot_file.read_text(encoding="utf-8")

    # --- Threads 投稿（独立した try/except）---
    account_poster = AccountPoster(account=account)
    try:
        result = account_poster.post(content)
    except Exception as e:
        logger.error(
            "threads_post_failed",
            account=account,
            date=today_str,
            slot=slot_name,
            error=str(e),
            exc_info=True,
        )
        return False

    logger.info(
        "threads_post_result",
        account=account,
        date=today_str,
        slot=slot_name,
        media_id=result.media_id,
        permalink=result.permalink,
    )

    posted_at = datetime.now(tz=JST).isoformat()

    # --- Instagram 投稿（career_sister のみ、独立した try/except）---
    instagram_permalink: str | None = None
    if account == "career_sister" and slot_meta.get("instagram") is True:
        slot_dir = slot_file.parent
        ig_poster = CareerSisterInstagramPoster()
        try:
            ig_result = ig_poster.post(slot_dir)
            if ig_result is not None:
                instagram_permalink = ig_result.permalink
                logger.info(
                    "instagram_post_result",
                    account=account,
                    date=today_str,
                    slot=slot_name,
                    media_id=ig_result.media_id,
                    permalink=ig_result.permalink,
                )
        except Exception as e:
            logger.error(
                "instagram_post_failed",
                account=account,
                date=today_str,
                slot=slot_name,
                error=str(e),
                exc_info=True,
            )
            # Instagram 失敗時も Threads 投稿済み状態は保持（処理継続）

    updater.update_meta(
        date=today_str,
        slot=slot_name,
        posted_at=posted_at,
        permalink=result.permalink or "",
        instagram_permalink=instagram_permalink,
    )
    updater.append_post_history(
        date=today_str,
        slot=slot_name,
        slot_meta=slot_meta,
        posted_at=posted_at,
        threads_permalink=result.permalink or "",
        instagram_permalink=instagram_permalink,
    )
    return True


def _execute_note_post(day_dir: Path) -> tuple[bool, str | None]:
    """note.com 投稿を subprocess 経由で実行する.

    ``publish_to_note.py --creator-mode`` を呼び出し、
    note.com への下書き投稿を行う。
    標準出力から draft_url を取得する。

    Parameters
    ----------
    day_dir : Path
        creator day ディレクトリのパス
        （例: ``creator/mitsuki/drafts/week_2026-03-31/day_1_月``）。

    Returns
    -------
    tuple[bool, str | None]
        ``(success, draft_url)``。
        成功時は ``(True, draft_url)``、失敗時は ``(False, None)``。
    """
    cmd = [
        "uv",
        "run",
        "python",
        "scripts/publish_to_note.py",
        "--creator-mode",
        str(day_dir),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            env={**__import__("os").environ, "NOTE_HEADLESS": "true"},
        )
    except Exception as exc:
        logger.error(
            "note_post_subprocess_error",
            day_dir=str(day_dir),
            error=str(exc),
            exc_info=True,
        )
        return False, None

    if result.returncode != 0:
        logger.error(
            "note_post_failed",
            day_dir=str(day_dir),
            returncode=result.returncode,
            stderr=result.stderr,
        )
        return False, None

    draft_url = result.stdout.strip() or None
    logger.info(
        "note_post_success",
        day_dir=str(day_dir),
        draft_url=draft_url,
    )
    return True, draft_url


def _process_account(
    account: str,
    config: AutoPosterConfig,
    now: datetime,
    matcher: SlotMatcher,
) -> PostingSummary:
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

    Returns
    -------
    PostingSummary
        このアカウントの投稿結果集計。
    """
    summary = PostingSummary()
    creator_root = get_project_root() / "creator" / account
    drafts_root = creator_root / "drafts"

    reader = DraftReader(drafts_root=drafts_root, account=account)
    meta = reader.load(week=config.week)
    if meta is None:
        logger.warning("no_meta_found", account=account, week=config.week)
        return summary

    today_str = now.strftime("%Y-%m-%d")
    matched = (
        matcher.match_force(now, config.force_slot, account=account)
        if config.force_slot
        else matcher.match(now)
    )

    if config.dry_run:
        _print_dry_run(account, meta, reader, today_str, matched)
        return summary

    if matched is None:
        logger.info("no_slot_matched", account=account, now=now.strftime("%H:%M"))
        return summary

    slot_name = matched["slot"]
    logger.info(
        "slot_to_post",
        account=account,
        slot=slot_name,
        time=matched["time"],
        today=today_str,
    )

    _run_post_slot(
        account, config, reader, creator_root, meta, today_str, slot_name, summary
    )
    return summary


def _run_post_slot(
    account: str,
    config: AutoPosterConfig,
    reader: DraftReader,
    creator_root: Path,
    meta: dict[str, Any],
    today_str: str,
    slot_name: str,
    summary: PostingSummary,
) -> None:
    """スロット投稿の実行と集計を行うヘルパー関数.

    Parameters
    ----------
    account : str
        対象アカウント名。
    config : AutoPosterConfig
        CLI 設定。
    reader : DraftReader
        DraftReader インスタンス。
    creator_root : Path
        creator/{account} ディレクトリのパス。
    meta : dict[str, Any]
        meta.json の内容。
    today_str : str
        本日の日付文字列（YYYY-MM-DD）。
    slot_name : str
        スロット名（朝/昼/夜）。
    summary : PostingSummary
        集計対象の PostingSummary（インプレース更新）。
    """
    # 今日の day_label を取得
    day_label = next(
        (
            day.get("day_label", "")
            for day in meta.get("days", [])
            if day.get("date") == today_str
        ),
        "",
    )

    week_start = meta.get("week_start", "")
    week_dir_name = f"week_{week_start}"

    slot_file = reader.get_slot_file(week_dir_name, today_str, day_label, slot_name, meta=meta)
    if slot_file is None:
        logger.warning(
            "slot_file_not_found",
            account=account,
            date=today_str,
            slot=slot_name,
            day_label=day_label,
        )
        summary.skipped += 1
        return

    week_dir = creator_root / "drafts" / week_dir_name
    posting_state_path = creator_root / "posting_state.json"
    updater = StateUpdater(
        week_dir=week_dir,
        posting_state_path=posting_state_path,
        account=account,
    )

    # 投稿直前に meta.json を再読み込みして二重投稿チェック
    fresh_meta = reader.load(week=week_start)
    if fresh_meta is None:
        logger.error("meta_reload_failed", account=account, week_start=week_start)
        summary.failed += 1
        return

    if updater.check_already_posted(fresh_meta, today_str, slot_name):
        logger.info(
            "already_posted_skip",
            account=account,
            date=today_str,
            slot=slot_name,
        )
        summary.skipped += 1
        return

    # Jitter: 投稿前にランダム遅延（自然な投稿パターンを演出）
    if config.jitter > 0 and not config.dry_run:
        delay_sec = _compute_jitter_seconds(config.jitter)
        if delay_sec > 0:
            logger.info(
                "jitter_sleep",
                account=account,
                slot=slot_name,
                delay_seconds=round(delay_sec, 1),
                delay_minutes=round(delay_sec / 60, 1),
            )
            time_mod.sleep(delay_sec)

    success = _execute_post(
        account, slot_name, today_str, slot_file, updater, fresh_meta
    )
    if success:
        summary.posted += 1
    else:
        summary.failed += 1

    # note.com 投稿（mitsuki + --include-note 時のみ）
    if config.include_note and account == "mitsuki":
        _run_note_post_for_mitsuki(
            config=config,
            creator_root=creator_root,
            updater=updater,
            meta=fresh_meta,
            today_str=today_str,
            day_label=day_label,
            week_dir_name=week_dir_name,
        )


def _run_note_post_for_mitsuki(
    config: AutoPosterConfig,
    creator_root: Path,
    updater: StateUpdater,
    meta: dict[str, Any],
    today_str: str,
    day_label: str,
    week_dir_name: str,
) -> None:
    """mitsuki アカウントの note.com 投稿を実行する.

    ``days[].note.file`` が存在し、かつ ``days[].note.published_at`` が
    未設定の場合に note.com へ投稿する。
    投稿成功後に ``days[].note.published_at`` と ``days[].note.permalink`` を更新する。

    Parameters
    ----------
    config : AutoPosterConfig
        CLI 設定。
    creator_root : Path
        creator/mitsuki ディレクトリのパス。
    updater : StateUpdater
        StateUpdater インスタンス。
    meta : dict[str, Any]
        最新の meta.json 内容。
    today_str : str
        本日の日付文字列（YYYY-MM-DD）。
    day_label : str
        曜日ラベル（月/火/水/木/金/土/日）。
    week_dir_name : str
        週ディレクトリ名（例: week_2026-03-31）。
    """
    # 今日のエントリから note フィールドを取得
    day_data: dict[str, Any] = {}
    for day in meta.get("days", []):
        if day.get("date") == today_str:
            day_data = day
            break

    note_day = day_data.get("note", {})

    # note_article.md が存在しない場合はスキップ
    if not note_day.get("file"):
        logger.debug(
            "note_post_no_file",
            date=today_str,
            day_label=day_label,
        )
        return

    # 既に投稿済みの場合はスキップ
    if note_day.get("published_at") is not None:
        logger.info(
            "note_already_posted_skip",
            date=today_str,
            day_label=day_label,
        )
        return

    # day ディレクトリを特定
    day_dir_map_mitsuki: dict[str, str] = {
        "月": "day_1_月",
        "火": "day_2_火",
        "水": "day_3_水",
        "木": "day_4_木",
        "金": "day_5_金",
        "土": "day_6_土",
        "日": "day_7_日",
    }
    day_dir_name = day_dir_map_mitsuki.get(day_label)
    if day_dir_name is None:
        logger.warning(
            "note_post_unknown_day_label",
            day_label=day_label,
            date=today_str,
        )
        return

    day_dir = creator_root / "drafts" / week_dir_name / day_dir_name

    logger.info(
        "note_post_started",
        date=today_str,
        day_label=day_label,
        day_dir=str(day_dir),
    )

    note_success, draft_url = _execute_note_post(day_dir)

    if note_success:
        published_at = datetime.now(tz=JST).isoformat()
        updater.update_note_meta(
            date=today_str,
            published_at=published_at,
            permalink=draft_url or "",
        )
        logger.info(
            "note_post_completed",
            date=today_str,
            draft_url=draft_url,
        )
    else:
        logger.error(
            "note_post_failed_skip",
            date=today_str,
            day_label=day_label,
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

    slot_time_map = _get_slot_time_map(account)
    for slot_meta in slots:
        slot_name = slot_meta.get("slot", "")
        time_str = slot_time_map.get(slot_name, "?:??")
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
