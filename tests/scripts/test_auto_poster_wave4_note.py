"""Unit tests for auto_poster.py Wave 4 note.com integration.

Tests cover:
- _execute_note_post: subprocess invocation and return value
- StateUpdater.update_note_meta: days[].note.published_at/permalink update
- _run_post_slot with --include-note for mitsuki account
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_meta(
    week_start: str = "2026-03-31",
    date: str = "2026-03-31",
    note: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a minimal mitsuki meta.json structure."""
    day: dict[str, Any] = {
        "date": date,
        "day_label": "月",
        "status": "draft",
        "slots": [
            {"slot": "朝", "category": "有益", "type": "型1"},
        ],
    }
    if note is not None:
        day["note"] = note
    else:
        day["note"] = {"file": "note_article.md"}
    return {"week_start": week_start, "days": [day]}


# ---------------------------------------------------------------------------
# StateUpdater.update_note_meta
# ---------------------------------------------------------------------------


class TestStateUpdaterUpdateNoteMeta:
    """Tests for StateUpdater.update_note_meta()."""

    def test_正常系_note_フィールドにpublished_atとpermalinkが書き込まれる(
        self, tmp_path: Path
    ) -> None:
        """update_note_meta writes published_at and permalink into days[].note."""
        from scripts.auto_poster import StateUpdater

        week_dir = tmp_path / "week_2026-03-31"
        week_dir.mkdir()
        meta = _make_meta(date="2026-03-31")
        meta_path = week_dir / "meta.json"
        meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        posting_state_path = tmp_path / "posting_state.json"
        updater = StateUpdater(
            week_dir=week_dir,
            posting_state_path=posting_state_path,
            account="mitsuki",
        )
        updater.update_note_meta(
            date="2026-03-31",
            published_at="2026-03-31T07:30:00+09:00",
            permalink="https://note.com/mitsuki/n/abc123",
        )

        updated = json.loads(meta_path.read_text(encoding="utf-8"))
        note_field = updated["days"][0]["note"]
        assert note_field["published_at"] == "2026-03-31T07:30:00+09:00"
        assert note_field["permalink"] == "https://note.com/mitsuki/n/abc123"

    def test_正常系_対象日付が存在しない場合はスキップ(self, tmp_path: Path) -> None:
        """update_note_meta skips silently when date is not found in meta."""
        from scripts.auto_poster import StateUpdater

        week_dir = tmp_path / "week_2026-03-31"
        week_dir.mkdir()
        meta = _make_meta(date="2026-03-31")
        meta_path = week_dir / "meta.json"
        meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        posting_state_path = tmp_path / "posting_state.json"
        updater = StateUpdater(
            week_dir=week_dir,
            posting_state_path=posting_state_path,
            account="mitsuki",
        )
        # 別の日付を指定 → 更新なし
        updater.update_note_meta(
            date="2026-04-01",
            published_at="2026-04-01T07:30:00+09:00",
            permalink="https://note.com/mitsuki/n/xyz999",
        )

        unchanged = json.loads(meta_path.read_text(encoding="utf-8"))
        note_field = unchanged["days"][0]["note"]
        assert "published_at" not in note_field

    def test_正常系_note_フィールドがない日付でもnoteが作成される(
        self, tmp_path: Path
    ) -> None:
        """update_note_meta creates note field when absent."""
        from scripts.auto_poster import StateUpdater

        week_dir = tmp_path / "week_2026-03-31"
        week_dir.mkdir()
        meta = _make_meta(date="2026-03-31", note=None)
        # Remove note field manually
        meta["days"][0].pop("note", None)
        meta_path = week_dir / "meta.json"
        meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        posting_state_path = tmp_path / "posting_state.json"
        updater = StateUpdater(
            week_dir=week_dir,
            posting_state_path=posting_state_path,
            account="mitsuki",
        )
        updater.update_note_meta(
            date="2026-03-31",
            published_at="2026-03-31T07:30:00+09:00",
            permalink="https://note.com/mitsuki/n/abc123",
        )

        updated = json.loads(meta_path.read_text(encoding="utf-8"))
        note_field = updated["days"][0]["note"]
        assert note_field["published_at"] == "2026-03-31T07:30:00+09:00"


# ---------------------------------------------------------------------------
# _execute_note_post
# ---------------------------------------------------------------------------


class TestExecuteNotePost:
    """Tests for _execute_note_post()."""

    def test_正常系_subprocessが成功した場合Trueを返す(self, tmp_path: Path) -> None:
        """_execute_note_post returns (True, draft_url) when subprocess succeeds."""
        from scripts.auto_poster import _execute_note_post

        day_dir = tmp_path / "day_1_月"
        day_dir.mkdir()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "https://note.com/mitsuki/n/abc123\n"

        with patch(
            "scripts.auto_poster.subprocess.run", return_value=mock_result
        ) as mock_run:
            success, _draft_url = _execute_note_post(day_dir)

        assert success is True
        mock_run.assert_called_once()
        # --creator-mode フラグと day_dir が渡されているか確認
        call_args = mock_run.call_args[0][0]
        assert "--creator-mode" in call_args
        assert str(day_dir) in call_args

    def test_異常系_subprocessが失敗した場合Falseを返す(self, tmp_path: Path) -> None:
        """_execute_note_post returns (False, None) when subprocess returns non-zero."""
        from scripts.auto_poster import _execute_note_post

        day_dir = tmp_path / "day_1_月"
        day_dir.mkdir()

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("scripts.auto_poster.subprocess.run", return_value=mock_result):
            success, draft_url = _execute_note_post(day_dir)

        assert success is False
        assert draft_url is None

    def test_異常系_subprocess例外時にFalseを返す(self, tmp_path: Path) -> None:
        """_execute_note_post returns (False, None) when subprocess raises an exception."""
        from scripts.auto_poster import _execute_note_post

        day_dir = tmp_path / "day_1_月"
        day_dir.mkdir()

        with patch(
            "scripts.auto_poster.subprocess.run",
            side_effect=OSError("command not found"),
        ):
            success, draft_url = _execute_note_post(day_dir)

        assert success is False
        assert draft_url is None
