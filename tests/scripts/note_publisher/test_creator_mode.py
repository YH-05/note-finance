"""Unit tests for publish_to_note.py --creator-mode feature.

Tests cover:
- parse_note_article_md: title/body parsing from note_article.md
- run_creator_mode_publish: end-to-end creator mode publish
- CLI argument parsing for --creator-mode
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# parse_note_article_md
# ---------------------------------------------------------------------------


class TestParseNoteArticleMd:
    """Tests for parse_note_article_md()."""

    def test_正常系_先頭h1行がタイトルになる(self, tmp_path: "Path") -> None:
        """First `# ` line becomes the title."""
        from scripts.publish_to_note import parse_note_article_md

        note_file = tmp_path / "note_article.md"
        note_file.write_text(
            "# テスト記事タイトル\n\n本文段落です。\n\n## 見出し\n\n続きの本文。\n",
            encoding="utf-8",
        )
        title, body = parse_note_article_md(note_file)
        assert title == "テスト記事タイトル"
        assert "本文段落です。" in body
        assert "## 見出し" in body

    def test_正常系_タイトル行は本文から除外される(self, tmp_path: "Path") -> None:
        """Title line should not appear in the body."""
        from scripts.publish_to_note import parse_note_article_md

        note_file = tmp_path / "note_article.md"
        note_file.write_text(
            "# タイトル\n\n本文です。\n",
            encoding="utf-8",
        )
        title, body = parse_note_article_md(note_file)
        assert "# タイトル" not in body
        assert title == "タイトル"

    def test_正常系_先頭スペース除去(self, tmp_path: "Path") -> None:
        """Title should be stripped of leading `# ` and whitespace."""
        from scripts.publish_to_note import parse_note_article_md

        note_file = tmp_path / "note_article.md"
        note_file.write_text(
            "#   スペース付きタイトル  \n\n本文。\n",
            encoding="utf-8",
        )
        title, _ = parse_note_article_md(note_file)
        assert title == "スペース付きタイトル"

    def test_異常系_note_article_mdが存在しない(self, tmp_path: "Path") -> None:
        """FileNotFoundError raised when note_article.md is missing."""
        from scripts.publish_to_note import parse_note_article_md

        missing = tmp_path / "note_article.md"
        with pytest.raises(FileNotFoundError, match=r"note_article\.md"):
            parse_note_article_md(missing)

    def test_異常系_h1タイトル行がない(self, tmp_path: "Path") -> None:
        """ValueError raised when no `# ` heading is found."""
        from scripts.publish_to_note import parse_note_article_md

        note_file = tmp_path / "note_article.md"
        note_file.write_text("本文のみでタイトルがありません。\n", encoding="utf-8")
        with pytest.raises(ValueError, match="タイトル"):
            parse_note_article_md(note_file)


# ---------------------------------------------------------------------------
# run_creator_mode_publish
# ---------------------------------------------------------------------------


class TestRunCreatorModePublish:
    """Tests for run_creator_mode_publish()."""

    @pytest.mark.asyncio
    async def test_正常系_creator_modeで投稿が成功する(self, tmp_path: "Path") -> None:
        """Creator mode publish returns 0 on success."""
        from scripts.publish_to_note import run_creator_mode_publish

        day_dir = tmp_path / "day_1_月"
        day_dir.mkdir()
        (day_dir / "note_article.md").write_text(
            "# テスト記事タイトル\n\n本文段落です。\n",
            encoding="utf-8",
        )

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client._restore_session = AsyncMock(return_value=True)
        mock_client.create_new_draft = AsyncMock()
        mock_client.set_title = AsyncMock()
        mock_client.insert_block = AsyncMock()
        mock_client.save_draft = AsyncMock(return_value="https://note.com/drafts/99999")

        with patch(
            "note_publisher.draft_publisher.NoteBrowserClient",
            return_value=mock_client,
        ):
            code, draft_url = await run_creator_mode_publish(day_dir)

        assert code == 0
        assert draft_url == "https://note.com/drafts/99999"

    @pytest.mark.asyncio
    async def test_異常系_note_article_mdがない場合エラーコード1(
        self, tmp_path: "Path"
    ) -> None:
        """Creator mode returns (1, None) when note_article.md is missing."""
        from scripts.publish_to_note import run_creator_mode_publish

        day_dir = tmp_path / "day_1_月"
        day_dir.mkdir()

        code, draft_url = await run_creator_mode_publish(day_dir)

        assert code == 1
        assert draft_url is None

    @pytest.mark.asyncio
    async def test_異常系_ブラウザエラー時にエラーコード1(
        self, tmp_path: "Path"
    ) -> None:
        """Creator mode returns (1, None) when browser publish fails."""
        from scripts.publish_to_note import run_creator_mode_publish

        day_dir = tmp_path / "day_1_月"
        day_dir.mkdir()
        (day_dir / "note_article.md").write_text(
            "# 記事タイトル\n\n本文です。\n",
            encoding="utf-8",
        )

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(
            side_effect=ConnectionError("browser failed")
        )
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "note_publisher.draft_publisher.NoteBrowserClient",
            return_value=mock_client,
        ):
            code, draft_url = await run_creator_mode_publish(day_dir)

        assert code == 1
        assert draft_url is None


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------


class TestCliParsing:
    """Tests for parse_args() --creator-mode option."""

    def test_正常系_creator_modeフラグが解析される(self) -> None:
        """--creator-mode flag is parsed correctly."""
        from scripts.publish_to_note import parse_args

        args = parse_args(
            ["--creator-mode", "creator/mitsuki/drafts/week_2026-03-31/day_1_月"]
        )
        assert args.creator_mode is True
        assert (
            str(args.article_dir) == "creator/mitsuki/drafts/week_2026-03-31/day_1_月"
        )

    def test_正常系_creator_modeなしの既存動作(self) -> None:
        """Without --creator-mode the flag is False."""
        from scripts.publish_to_note import parse_args

        args = parse_args(["articles/asset_management/my-article"])
        assert args.creator_mode is False
        assert str(args.article_dir) == "articles/asset_management/my-article"
