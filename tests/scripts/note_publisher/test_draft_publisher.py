"""Unit tests for DraftPublisher orchestrator.

This module tests the DraftPublisher class to ensure:
- ``publish()`` returns ``PublishResult`` on success
- ``dry_run()`` returns ``ArticleDraft`` without browser operations
- Error codes E001-E005 are properly handled and returned as
  ``PublishResult(success=False, error_message=...)``
- markdown_parser and browser_client are correctly orchestrated
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from note_publisher.draft_publisher import DraftPublisher
from note_publisher.types import (
    ArticleDraft,
    ContentBlock,
    NotePublisherConfig,
    PublishResult,
)

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config() -> NotePublisherConfig:
    """Create a test NotePublisherConfig with default values."""
    return NotePublisherConfig()


@pytest.fixture
def publisher(config: NotePublisherConfig) -> DraftPublisher:
    """Create a DraftPublisher instance with default config."""
    return DraftPublisher(config=config)


@pytest.fixture
def sample_draft() -> ArticleDraft:
    """Create a sample ArticleDraft for testing.

    Returns
    -------
    ArticleDraft
        A draft with a heading and a paragraph block.
    """
    return ArticleDraft(
        title="テスト記事タイトル",
        body_blocks=[
            ContentBlock(block_type="heading", content="見出し", level=2),
            ContentBlock(block_type="paragraph", content="本文テキストです。"),
        ],
        image_paths=[],
        frontmatter={"title": "テスト記事タイトル", "category": "investment"},
    )


@pytest.fixture
def article_dir(tmp_path: Path) -> Path:
    """Create a temporary article directory with a revised_draft.md file.

    Returns
    -------
    Path
        Path to the article directory with ``02_edit/revised_draft.md`` created.
    """
    edit_dir = tmp_path / "test_article" / "02_edit"
    edit_dir.mkdir(parents=True)
    draft_file = edit_dir / "revised_draft.md"
    draft_file.write_text(
        """\
---
title: テスト記事タイトル
category: investment
---

## 見出し

本文テキストです。
""",
        encoding="utf-8",
    )
    return tmp_path / "test_article"


@pytest.fixture
def article_dir_no_draft(tmp_path: Path) -> Path:
    """Create a temporary article directory without a revised_draft.md file.

    Returns
    -------
    Path
        Path to the article directory without the draft file.
    """
    article_dir = tmp_path / "test_article_no_draft"
    article_dir.mkdir(parents=True)
    return article_dir


# ---------------------------------------------------------------------------
# Tests: dry_run
# ---------------------------------------------------------------------------


class TestDryRun:
    """Tests for DraftPublisher.dry_run()."""

    def test_正常系_dry_runがArticleDraftを返す(
        self,
        publisher: DraftPublisher,
        article_dir: Path,
        sample_draft: ArticleDraft,
    ) -> None:
        """dry_run should parse the Markdown file and return an ArticleDraft."""
        with patch(
            "note_publisher.draft_publisher.parse_draft",
            return_value=sample_draft,
        ) as mock_parse:
            result = publisher.dry_run(article_dir)

        assert isinstance(result, ArticleDraft)
        assert result.title == "テスト記事タイトル"
        assert len(result.body_blocks) == 2
        mock_parse.assert_called_once_with(article_dir / "02_edit" / "revised_draft.md")

    def test_異常系_E001_revised_draftが見つからない(
        self,
        publisher: DraftPublisher,
        article_dir_no_draft: Path,
    ) -> None:
        """dry_run should raise FileNotFoundError when revised_draft.md is missing."""
        with pytest.raises(FileNotFoundError, match="E001"):
            publisher.dry_run(article_dir_no_draft)

    def test_異常系_E002_Markdownパースエラー(
        self,
        publisher: DraftPublisher,
        article_dir: Path,
    ) -> None:
        """dry_run should raise ValueError when parse_draft fails."""
        with (
            patch(
                "note_publisher.draft_publisher.parse_draft",
                side_effect=Exception("YAML parse error"),
            ),
            pytest.raises(ValueError, match="E002"),
        ):
            publisher.dry_run(article_dir)


# ---------------------------------------------------------------------------
# Tests: publish
# ---------------------------------------------------------------------------


class TestPublish:
    """Tests for DraftPublisher.publish()."""

    @pytest.mark.asyncio
    async def test_正常系_publishがPublishResultを返す(
        self,
        publisher: DraftPublisher,
        article_dir: Path,
        sample_draft: ArticleDraft,
    ) -> None:
        """publish should return PublishResult(success=True) on success."""
        mock_client_instance = AsyncMock()
        mock_client_instance.create_new_draft = AsyncMock()
        mock_client_instance.set_title = AsyncMock()
        mock_client_instance.insert_block = AsyncMock()
        mock_client_instance.upload_image = AsyncMock()
        mock_client_instance.save_draft = AsyncMock(
            return_value="https://note.com/drafts/12345"
        )
        mock_client_instance._restore_session = AsyncMock(return_value=True)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "note_publisher.draft_publisher.parse_draft",
                return_value=sample_draft,
            ),
            patch(
                "note_publisher.draft_publisher.NoteBrowserClient",
                return_value=mock_client_instance,
            ),
        ):
            result = await publisher.publish(article_dir)

        assert isinstance(result, PublishResult)
        assert result.success is True
        assert result.draft_url == "https://note.com/drafts/12345"
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_異常系_E001_publishでrevised_draftが見つからない(
        self,
        publisher: DraftPublisher,
        article_dir_no_draft: Path,
    ) -> None:
        """publish should return PublishResult(success=False) with E001 error."""
        result = await publisher.publish(article_dir_no_draft)

        assert isinstance(result, PublishResult)
        assert result.success is False
        assert result.error_message is not None
        assert "E001" in result.error_message

    @pytest.mark.asyncio
    async def test_異常系_E002_publishでMarkdownパースエラー(
        self,
        publisher: DraftPublisher,
        article_dir: Path,
    ) -> None:
        """publish should return PublishResult(success=False) with E002 error."""
        with patch(
            "note_publisher.draft_publisher.parse_draft",
            side_effect=Exception("YAML parse error"),
        ):
            result = await publisher.publish(article_dir)

        assert isinstance(result, PublishResult)
        assert result.success is False
        assert result.error_message is not None
        assert "E002" in result.error_message

    @pytest.mark.asyncio
    async def test_異常系_E003_ブラウザ起動エラー(
        self,
        publisher: DraftPublisher,
        article_dir: Path,
        sample_draft: ArticleDraft,
    ) -> None:
        """publish should return PublishResult(success=False) with E003 error."""
        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__ = AsyncMock(
            side_effect=ConnectionError("Failed to launch browser")
        )
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "note_publisher.draft_publisher.parse_draft",
                return_value=sample_draft,
            ),
            patch(
                "note_publisher.draft_publisher.NoteBrowserClient",
                return_value=mock_client_instance,
            ),
        ):
            result = await publisher.publish(article_dir)

        assert isinstance(result, PublishResult)
        assert result.success is False
        assert result.error_message is not None
        assert "E003" in result.error_message

    @pytest.mark.asyncio
    async def test_異常系_E004_ログインエラー(
        self,
        publisher: DraftPublisher,
        article_dir: Path,
        sample_draft: ArticleDraft,
    ) -> None:
        """publish should return PublishResult(success=False) with E004 error."""
        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_instance._restore_session = AsyncMock(return_value=False)
        mock_client_instance.wait_for_manual_login = AsyncMock(
            side_effect=TimeoutError("Login timeout")
        )

        with (
            patch(
                "note_publisher.draft_publisher.parse_draft",
                return_value=sample_draft,
            ),
            patch(
                "note_publisher.draft_publisher.NoteBrowserClient",
                return_value=mock_client_instance,
            ),
        ):
            result = await publisher.publish(article_dir)

        assert isinstance(result, PublishResult)
        assert result.success is False
        assert result.error_message is not None
        assert "E004" in result.error_message

    @pytest.mark.asyncio
    async def test_異常系_E005_下書き保存エラー(
        self,
        publisher: DraftPublisher,
        article_dir: Path,
        sample_draft: ArticleDraft,
    ) -> None:
        """publish should return PublishResult(success=False) with E005 error."""
        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_instance._restore_session = AsyncMock(return_value=True)
        mock_client_instance.create_new_draft = AsyncMock()
        mock_client_instance.set_title = AsyncMock()
        mock_client_instance.insert_block = AsyncMock()
        mock_client_instance.upload_image = AsyncMock()
        mock_client_instance.save_draft = AsyncMock(
            side_effect=Exception("Save failed")
        )

        with (
            patch(
                "note_publisher.draft_publisher.parse_draft",
                return_value=sample_draft,
            ),
            patch(
                "note_publisher.draft_publisher.NoteBrowserClient",
                return_value=mock_client_instance,
            ),
        ):
            result = await publisher.publish(article_dir)

        assert isinstance(result, PublishResult)
        assert result.success is False
        assert result.error_message is not None
        assert "E005" in result.error_message

    @pytest.mark.asyncio
    async def test_正常系_publishで画像アップロードが実行される(
        self,
        publisher: DraftPublisher,
        article_dir: Path,
    ) -> None:
        """publish should upload images referenced in the draft."""
        image_path = article_dir / "02_edit" / "image.png"
        draft_with_image = ArticleDraft(
            title="画像付き記事",
            body_blocks=[
                ContentBlock(block_type="paragraph", content="テキスト"),
                ContentBlock(
                    block_type="image",
                    content="グラフ",
                    image_path=image_path,
                ),
            ],
            image_paths=[image_path],
            frontmatter={},
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_instance._restore_session = AsyncMock(return_value=True)
        mock_client_instance.create_new_draft = AsyncMock()
        mock_client_instance.set_title = AsyncMock()
        mock_client_instance.insert_block = AsyncMock()
        mock_client_instance.upload_image = AsyncMock()
        mock_client_instance.save_draft = AsyncMock(
            return_value="https://note.com/drafts/67890"
        )

        with (
            patch(
                "note_publisher.draft_publisher.parse_draft",
                return_value=draft_with_image,
            ),
            patch(
                "note_publisher.draft_publisher.NoteBrowserClient",
                return_value=mock_client_instance,
            ),
        ):
            result = await publisher.publish(article_dir)

        assert result.success is True
        # insert_block is called for each body_block
        assert mock_client_instance.insert_block.call_count == 2

    @pytest.mark.asyncio
    async def test_正常系_configがNoneの場合load_configが呼ばれる(
        self,
        article_dir: Path,
        sample_draft: ArticleDraft,
    ) -> None:
        """DraftPublisher with config=None should call load_config()."""
        mock_config = NotePublisherConfig()

        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_instance._restore_session = AsyncMock(return_value=True)
        mock_client_instance.create_new_draft = AsyncMock()
        mock_client_instance.set_title = AsyncMock()
        mock_client_instance.insert_block = AsyncMock()
        mock_client_instance.save_draft = AsyncMock(
            return_value="https://note.com/drafts/99999"
        )

        with (
            patch(
                "note_publisher.draft_publisher.load_config",
                return_value=mock_config,
            ) as mock_load,
            patch(
                "note_publisher.draft_publisher.parse_draft",
                return_value=sample_draft,
            ),
            patch(
                "note_publisher.draft_publisher.NoteBrowserClient",
                return_value=mock_client_instance,
            ),
        ):
            publisher = DraftPublisher(config=None)
            result = await publisher.publish(article_dir)

        mock_load.assert_called_once()
        assert result.success is True
