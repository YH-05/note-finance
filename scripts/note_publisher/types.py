"""Pydantic v2 type definitions for the note_publisher package.

Defines the core data models used across all note_publisher modules:

- ``BlockType`` -- Literal type for content block types.
- ``ContentBlock`` -- A single content block (heading, paragraph, etc.).
- ``ArticleDraft`` -- Complete article draft ready for publishing.
- ``PublishResult`` -- Outcome of a publish operation.
- ``NotePublisherConfig`` -- Configuration for the note publisher.

Examples
--------
>>> from note_publisher.types import ContentBlock, ArticleDraft
>>> block = ContentBlock(block_type="heading", content="Title", level=1)
>>> draft = ArticleDraft(title="My Article", body_blocks=[block])
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import structlog
from pydantic import BaseModel, Field

from data_paths import get_path

logger = structlog.get_logger(__name__)

# =============================================================================
# BlockType
# =============================================================================

type BlockType = Literal[
    "heading",
    "paragraph",
    "list_item",
    "blockquote",
    "image",
    "separator",
]
"""Supported content block types for note.com articles.

Values
------
heading
    Section heading (h1-h3).
paragraph
    Regular paragraph text.
list_item
    Bulleted or numbered list item.
blockquote
    Quoted text block.
image
    Image block with optional path.
separator
    Horizontal rule / separator.
"""

# =============================================================================
# ContentBlock
# =============================================================================


class ContentBlock(BaseModel):
    """A single content block within an article.

    Attributes
    ----------
    block_type : BlockType
        Type of the content block.
    content : str
        Text content of the block.
    level : int | None
        Heading level (1-3). Only applicable when ``block_type`` is
        ``"heading"``. Defaults to ``None``.
    image_path : Path | None
        Path to an image file. Only applicable when ``block_type`` is
        ``"image"``. Defaults to ``None``.

    Examples
    --------
    >>> block = ContentBlock(block_type="paragraph", content="Hello world")
    >>> block.block_type
    'paragraph'

    >>> heading = ContentBlock(block_type="heading", content="Title", level=2)
    >>> heading.level
    2
    """

    block_type: BlockType
    content: str
    level: int | None = None
    image_path: Path | None = None


# =============================================================================
# ArticleDraft
# =============================================================================


class ArticleDraft(BaseModel):
    """Complete article draft ready for publishing to note.com.

    Attributes
    ----------
    title : str
        Article title.
    body_blocks : list[ContentBlock]
        Ordered list of content blocks forming the article body.
    image_paths : list[Path]
        List of image file paths referenced in the article.
    frontmatter : dict[str, Any]
        Arbitrary metadata (tags, category, etc.).

    Examples
    --------
    >>> draft = ArticleDraft(
    ...     title="My Article",
    ...     body_blocks=[
    ...         ContentBlock(block_type="heading", content="Intro", level=1),
    ...         ContentBlock(block_type="paragraph", content="Body text."),
    ...     ],
    ... )
    >>> len(draft.body_blocks)
    2
    """

    title: str
    body_blocks: list[ContentBlock] = Field(default_factory=list)
    image_paths: list[Path] = Field(default_factory=list)
    frontmatter: dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# PublishResult
# =============================================================================


class PublishResult(BaseModel):
    """Outcome of a publish operation.

    Attributes
    ----------
    success : bool
        Whether the publish operation succeeded.
    draft_url : str | None
        URL of the created draft on note.com. ``None`` on failure.
    error_message : str | None
        Human-readable error description. ``None`` on success.

    Examples
    --------
    >>> result = PublishResult(
    ...     success=True,
    ...     draft_url="https://note.com/drafts/123",
    ... )
    >>> result.success
    True
    """

    success: bool
    draft_url: str | None = None
    error_message: str | None = None


# =============================================================================
# NotePublisherConfig
# =============================================================================


class NotePublisherConfig(BaseModel):
    """Configuration for the note.com publisher.

    Attributes
    ----------
    headless : bool
        Whether to run the browser in headless mode. Defaults to ``True``.
    storage_state_path : Path
        Path to the Playwright storage state file for authentication.
        Defaults to ``Path("data/config/note-storage-state.json")``.
    timeout_ms : int
        Global timeout in milliseconds for browser operations.
        Must be >= 1000. Defaults to ``30000`` (30 seconds).
    typing_delay_ms : int
        Delay in milliseconds between keystrokes when typing.
        Must be >= 0. Defaults to ``50``.

    Examples
    --------
    >>> config = NotePublisherConfig()
    >>> config.headless
    True
    >>> config.timeout_ms
    30000

    >>> config = NotePublisherConfig(headless=False, timeout_ms=60000)
    >>> config.headless
    False
    """

    headless: bool = True
    storage_state_path: Path = Field(
        default_factory=lambda: get_path("config/note-storage-state.json"),
    )
    timeout_ms: int = Field(default=30000, ge=1000)
    typing_delay_ms: int = Field(default=50, ge=0)
