"""creator_enrichment セッションログ.

Markdown 形式のセッションログファイルを生成する SessionLogger クラスを提供する。
ログファイルは ``.tmp/creator-enrichment-{session_id}.log.md`` に出力される。

単一プロセス前提のためファイルロックは不要。
セッション ID でファイル名を一意化する。

Usage
-----
::

    from creator_enrichment.session_log import SessionLogger
    from creator_enrichment.types import CycleReport

    logger = SessionLogger("20260323-140000")
    logger.record_cycle(1, report)
    logger.record_error(2, exc)
    logger.finalize(total_cycles=2)
"""

from __future__ import annotations

import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .types import CycleReport

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------
_DEFAULT_LOG_DIR = Path(".tmp")
"""セッションログのデフォルト出力ディレクトリ."""


class SessionLogger:
    """Markdown 形式のセッションログを管理する.

    Parameters
    ----------
    session_id : str
        セッション識別子（ファイル名の一部に使用）
    log_dir : Path | None
        ログ出力ディレクトリ（None の場合はデフォルト ``.tmp/``）

    Attributes
    ----------
    session_id : str
        セッション識別子
    log_path : Path
        ログファイルの絶対パス
    """

    def __init__(
        self,
        session_id: str,
        *,
        log_dir: Path | None = None,
    ) -> None:
        self.session_id = session_id
        self._log_dir = log_dir or _DEFAULT_LOG_DIR
        self.log_path = self._log_dir / f"creator-enrichment-{session_id}.log.md"
        self._start_time = datetime.now(tz=timezone.utc)

        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._write_header()
        # ファイルパーミッションを owner-only に設定（スタックトレース漏洩防止）
        self.log_path.chmod(0o600)
        logger.info(
            "SessionLogger initialized: session_id=%s, log_path=%s",
            session_id,
            self.log_path,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def record_cycle(self, cycle_num: int, report: CycleReport) -> None:
        """サイクル結果をログに追記する.

        Parameters
        ----------
        cycle_num : int
            サイクル番号（1-indexed）
        report : CycleReport
            サイクルレポート
        """
        now = datetime.now(tz=timezone.utc)
        time_str = now.strftime("%H:%M:%S")

        contents_str = ", ".join(
            f"{k}: {v}" for k, v in report["contents_created"].items()
        )

        block = (
            f"\n### Cycle {cycle_num} - {report['genre']}\n"
            f"- time: {time_str}\n"
            f"- genre: {report['genre']}\n"
            f"- search_results: {report['search_results']}\n"
            f"- contents_created: {{{contents_str}}}\n"
            f"- entities_extracted: {report['entities_extracted']}\n"
            f"- relations_detected: {report['relations_detected']}\n"
            f"- pipeline_status: {report['pipeline_status']}\n"
        )
        self._append(block)
        logger.debug(
            "Recorded cycle %d for genre=%s",
            cycle_num,
            report["genre"],
        )

    def record_error(self, cycle_num: int, error: Exception) -> None:
        """エラー情報をログに追記する.

        Parameters
        ----------
        cycle_num : int
            エラーが発生したサイクル番号
        error : Exception
            発生した例外
        """
        tb_str = traceback.format_exception(type(error), error, error.__traceback__)
        tb_text = "".join(tb_str)

        block = (
            f"\n### Cycle {cycle_num} - ERROR\n"
            f"- error: {error}\n"
            f"- traceback:\n"
            f"```\n{tb_text}```\n"
        )
        self._append(block)
        logger.warning(
            "Recorded error for cycle %d: %s",
            cycle_num,
            error,
        )

    def finalize(self, total_cycles: int) -> None:
        """セッション終了サマリーをログに追記する.

        Parameters
        ----------
        total_cycles : int
            実行した総サイクル数
        """
        block = (
            f"\n## Summary\n- total_cycles: {total_cycles}\n- end_reason: completed\n"
        )
        self._append(block)
        logger.info(
            "Session finalized: total_cycles=%d",
            total_cycles,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _write_header(self) -> None:
        """ログファイルのヘッダーを書き込む."""
        start_iso = self._start_time.isoformat()
        header = (
            "# Creator Enrichment Session\n"
            f"- start: {start_iso}\n"
            f"- session_id: {self.session_id}\n"
            "\n## Cycles\n"
        )
        self.log_path.write_text(header, encoding="utf-8")

    def _append(self, text: str) -> None:
        """ログファイルにテキストを追記する."""
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(text)
