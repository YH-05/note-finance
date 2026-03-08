"""Unit tests for DraftPublisher orchestrator.

This module tests the DraftPublisher class to ensure:
- ``publish()`` returns ``PublishResult`` on success
- ``dry_run()`` returns ``ArticleDraft`` without browser operations
- Error codes E001-E005 are properly handled and returned as
  ``PublishResult(success=False, error_message=...)``
- markdown_parser and browser_client are correctly orchestrated
- ``_update_article_meta()`` updates article-meta.json correctly
- ``_copy_to_published()`` copies revised_draft.md to 03_published/
"""

from __future__ import annotations

import json
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

    @pytest.mark.asyncio
    async def test_正常系_publish成功後にupdate_metaが呼ばれる(
        self,
        article_dir: Path,
        sample_draft: ArticleDraft,
    ) -> None:
        """publish should call _update_article_meta and _copy_to_published on success."""
        # Create article-meta.json
        meta = {
            "article_id": "test",
            "status": "ready_for_publish",
            "workflow": {
                "publishing": {"final_review": "pending", "published": "pending"}
            },
        }
        (article_dir / "article-meta.json").write_text(
            json.dumps(meta, ensure_ascii=False),
            encoding="utf-8",
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_instance._restore_session = AsyncMock(return_value=True)
        mock_client_instance.create_new_draft = AsyncMock()
        mock_client_instance.set_title = AsyncMock()
        mock_client_instance.insert_block = AsyncMock()
        mock_client_instance.save_draft = AsyncMock(
            return_value="https://note.com/drafts/12345"
        )

        publisher = DraftPublisher()

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
            result = await publisher.publish(article_dir, update_meta=True)

        assert result.success is True

        # Verify article-meta.json was updated
        updated_meta = json.loads(
            (article_dir / "article-meta.json").read_text(encoding="utf-8")
        )
        assert updated_meta["status"] == "published"
        assert "published_at" in updated_meta
        assert updated_meta["draft_url"] == "https://note.com/drafts/12345"
        assert updated_meta["workflow"]["publishing"]["published"] == "done"

        # Verify 03_published/article.md was created
        published_article = article_dir / "03_published" / "article.md"
        assert published_article.exists()

    @pytest.mark.asyncio
    async def test_正常系_update_meta_falseでメタデータ更新なし(
        self,
        article_dir: Path,
        sample_draft: ArticleDraft,
    ) -> None:
        """publish with update_meta=False should not update article-meta.json."""
        meta = {"article_id": "test", "status": "ready_for_publish"}
        (article_dir / "article-meta.json").write_text(
            json.dumps(meta, ensure_ascii=False),
            encoding="utf-8",
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_instance._restore_session = AsyncMock(return_value=True)
        mock_client_instance.create_new_draft = AsyncMock()
        mock_client_instance.set_title = AsyncMock()
        mock_client_instance.insert_block = AsyncMock()
        mock_client_instance.save_draft = AsyncMock(
            return_value="https://note.com/drafts/12345"
        )

        publisher = DraftPublisher()

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
            result = await publisher.publish(article_dir, update_meta=False)

        assert result.success is True

        # article-meta.json should NOT be updated
        unchanged_meta = json.loads(
            (article_dir / "article-meta.json").read_text(encoding="utf-8")
        )
        assert unchanged_meta["status"] == "ready_for_publish"


# ---------------------------------------------------------------------------
# Tests: _update_article_meta
# ---------------------------------------------------------------------------


class TestUpdateArticleMeta:
    """Tests for DraftPublisher._update_article_meta()."""

    def test_正常系_メタデータが正しく更新される(self, tmp_path: Path) -> None:
        """_update_article_meta should update status, published_at, and draft_url."""
        article_dir = tmp_path / "test_article"
        article_dir.mkdir()
        meta = {
            "article_id": "test-article",
            "status": "ready_for_publish",
            "updated_at": "2026-01-01T00:00:00Z",
            "workflow": {
                "publishing": {"final_review": "pending", "published": "pending"}
            },
        }
        (article_dir / "article-meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=4) + "\n",
            encoding="utf-8",
        )

        DraftPublisher._update_article_meta(
            article_dir, "https://note.com/drafts/99999"
        )

        updated = json.loads(
            (article_dir / "article-meta.json").read_text(encoding="utf-8")
        )
        assert updated["status"] == "published"
        assert "published_at" in updated
        assert updated["draft_url"] == "https://note.com/drafts/99999"
        assert updated["workflow"]["publishing"]["published"] == "done"
        assert updated["workflow"]["publishing"]["final_review"] == "done"

    def test_正常系_article_meta_jsonがない場合スキップ(self, tmp_path: Path) -> None:
        """_update_article_meta should skip gracefully if file doesn't exist."""
        article_dir = tmp_path / "nonexistent_article"
        article_dir.mkdir()

        # Should not raise
        DraftPublisher._update_article_meta(article_dir, "https://note.com/drafts/1")

    def test_正常系_draft_urlがNoneの場合もstatus更新(self, tmp_path: Path) -> None:
        """_update_article_meta should update status even if draft_url is None."""
        article_dir = tmp_path / "test_article"
        article_dir.mkdir()
        meta = {"article_id": "test", "status": "ready_for_publish", "workflow": {}}
        (article_dir / "article-meta.json").write_text(
            json.dumps(meta), encoding="utf-8"
        )

        DraftPublisher._update_article_meta(article_dir, None)

        updated = json.loads(
            (article_dir / "article-meta.json").read_text(encoding="utf-8")
        )
        assert updated["status"] == "published"
        assert "draft_url" not in updated


# ---------------------------------------------------------------------------
# Tests: _copy_to_published
# ---------------------------------------------------------------------------


class TestCopyToPublished:
    """Tests for DraftPublisher._copy_to_published()."""

    def test_正常系_revised_draftが03_publishedにコピーされる(
        self, tmp_path: Path
    ) -> None:
        """_copy_to_published should copy revised_draft.md to 03_published/article.md."""
        article_dir = tmp_path / "test_article"
        edit_dir = article_dir / "02_edit"
        edit_dir.mkdir(parents=True)
        draft_content = "# タイトル\n\n本文です。"
        (edit_dir / "revised_draft.md").write_text(draft_content, encoding="utf-8")

        DraftPublisher._copy_to_published(article_dir)

        published = article_dir / "03_published" / "article.md"
        assert published.exists()
        assert published.read_text(encoding="utf-8") == draft_content

    def test_正常系_03_publishedが既存でも上書きコピー(self, tmp_path: Path) -> None:
        """_copy_to_published should overwrite existing article.md."""
        article_dir = tmp_path / "test_article"
        edit_dir = article_dir / "02_edit"
        edit_dir.mkdir(parents=True)
        pub_dir = article_dir / "03_published"
        pub_dir.mkdir(parents=True)
        (pub_dir / "article.md").write_text("old content", encoding="utf-8")
        (edit_dir / "revised_draft.md").write_text("new content", encoding="utf-8")

        DraftPublisher._copy_to_published(article_dir)

        assert (pub_dir / "article.md").read_text(encoding="utf-8") == "new content"

    def test_正常系_revised_draftがない場合スキップ(self, tmp_path: Path) -> None:
        """_copy_to_published should skip if revised_draft.md doesn't exist."""
        article_dir = tmp_path / "test_article"
        article_dir.mkdir()

        # Should not raise
        DraftPublisher._copy_to_published(article_dir)
