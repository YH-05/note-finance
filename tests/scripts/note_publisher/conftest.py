"""Shared fixtures for note_publisher tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from note_publisher.types import (
    ArticleDraft,
    ContentBlock,
    NotePublisherConfig,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def sample_markdown() -> str:
    """Create a sample Markdown string for testing.

    Returns
    -------
    str
        A Markdown string with frontmatter, headings, paragraphs,
        list items, blockquote, and separator.
    """
    return """\
---
title: テスト記事
category: investment
---

## テスト見出し

テスト段落のテキストです。

- リスト項目1
- リスト項目2

> 引用テキスト

---
"""


@pytest.fixture
def sample_article_draft() -> ArticleDraft:
    """Create a sample ArticleDraft for testing.

    Returns
    -------
    ArticleDraft
        An ArticleDraft with heading and paragraph blocks.
    """
    return ArticleDraft(
        title="テスト記事",
        body_blocks=[
            ContentBlock(block_type="heading", content="テスト見出し", level=2),
            ContentBlock(block_type="paragraph", content="テスト段落のテキストです。"),
        ],
        image_paths=[],
        frontmatter={"title": "テスト記事", "category": "investment"},
    )


@pytest.fixture
def sample_config() -> NotePublisherConfig:
    """Create a sample NotePublisherConfig with default values.

    Returns
    -------
    NotePublisherConfig
        A NotePublisherConfig instance with default settings.
    """
    return NotePublisherConfig()


@pytest.fixture
def tmp_article_dir(tmp_path: Path) -> Path:
    """Create a temporary article directory for testing.

    Parameters
    ----------
    tmp_path : Path
        pytest built-in temporary path fixture.

    Returns
    -------
    Path
        A created temporary directory for article files.
    """
    article_dir = tmp_path / "test_article"
    article_dir.mkdir()
    return article_dir
