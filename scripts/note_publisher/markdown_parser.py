"""Markdown parser for converting revised_draft.md to ArticleDraft.

Parses YAML frontmatter, Markdown body blocks (6 types), and converts
Markdown tables to table image references. The ``## 修正履歴`` section
and everything after it is excluded from the output.

Block Types
-----------
- ``heading`` : h1, h2, h3 (level=1,2,3)
- ``paragraph`` : regular text
- ``list_item`` : lines starting with ``- ``
- ``blockquote`` : lines starting with ``> ``
- ``image`` : ``![alt](path)`` pattern
- ``separator`` : ``---`` lines (not frontmatter delimiters)

Examples
--------
>>> from pathlib import Path
>>> draft = parse_draft(Path("articles/example/02_draft/revised_draft.md"))
>>> draft.title
'記事タイトル'
>>> len(draft.body_blocks)
10
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import structlog
import yaml
from note_publisher.types import ArticleDraft, ContentBlock

if TYPE_CHECKING:
    from pathlib import Path

logger = structlog.get_logger(__name__)

# AIDEV-NOTE: Image pattern matches ![alt text](path) syntax
_IMAGE_PATTERN = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)$")


def parse_draft(draft_path: Path) -> ArticleDraft:
    """Parse a revised_draft.md file into an ArticleDraft.

    Parameters
    ----------
    draft_path : Path
        Path to the ``revised_draft.md`` file.

    Returns
    -------
    ArticleDraft
        Parsed article draft with frontmatter, title, body blocks,
        and image paths.
    """
    logger.debug("Parsing draft file", path=str(draft_path))

    text = draft_path.read_text(encoding="utf-8")

    if not text.strip():
        logger.info("Empty draft file", path=str(draft_path))
        return ArticleDraft(title="", body_blocks=[], image_paths=[], frontmatter={})

    frontmatter, body_text = _extract_frontmatter(text)
    body_text = _remove_revision_history(body_text)
    body_blocks, image_paths = _parse_body(body_text, draft_path.parent)
    title = _resolve_title(frontmatter, body_blocks)

    logger.info(
        "Draft parsed successfully",
        path=str(draft_path),
        title=title,
        block_count=len(body_blocks),
        image_count=len(image_paths),
    )

    return ArticleDraft(
        title=title,
        body_blocks=body_blocks,
        image_paths=image_paths,
        frontmatter=frontmatter,
    )


def _extract_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Extract YAML frontmatter from Markdown text.

    Parameters
    ----------
    text : str
        Full Markdown text potentially containing YAML frontmatter
        delimited by ``---``.

    Returns
    -------
    tuple[dict[str, Any], str]
        A tuple of (frontmatter dict, remaining body text).
        If no frontmatter is found, returns an empty dict.
    """
    if not text.startswith("---"):
        logger.debug("No frontmatter detected")
        return {}, text

    # AIDEV-NOTE: Split on the second '---' delimiter to extract frontmatter
    parts = text.split("---", 2)
    if len(parts) < 3:
        logger.debug("Incomplete frontmatter delimiters")
        return {}, text

    yaml_content = parts[1].strip()
    body = parts[2]

    try:
        frontmatter: dict[str, Any] = yaml.safe_load(yaml_content) or {}
    except yaml.YAMLError:
        logger.warning("Failed to parse YAML frontmatter", exc_info=True)
        return {}, text

    logger.debug(
        "Frontmatter extracted",
        keys=list(frontmatter.keys()),
    )
    return frontmatter, body


def _remove_revision_history(body: str) -> str:
    """Remove the ``## 修正履歴`` section and everything after it.

    Parameters
    ----------
    body : str
        Markdown body text.

    Returns
    -------
    str
        Body text with revision history removed.
    """
    marker = "## 修正履歴"
    idx = body.find(marker)
    if idx == -1:
        return body

    logger.debug("Revision history section found, removing")
    return body[:idx]


def _parse_body(
    body: str,
    base_dir: Path,
) -> tuple[list[ContentBlock], list[Path]]:
    """Parse Markdown body into ContentBlock list and collect image paths.

    Parameters
    ----------
    body : str
        Markdown body text (frontmatter and revision history removed).
    base_dir : Path
        Base directory for resolving relative image paths.

    Returns
    -------
    tuple[list[ContentBlock], list[Path]]
        A tuple of (list of content blocks, list of image paths).
    """
    lines = body.split("\n")
    blocks: list[ContentBlock] = []
    image_paths: list[Path] = []
    table_count = 0

    i = 0
    while i < len(lines):
        stripped = lines[i].strip()

        if not stripped:
            i += 1
            continue

        if _is_table_line(stripped):
            i, table_count = _handle_table(
                lines,
                i,
                base_dir,
                table_count,
                blocks,
                image_paths,
            )
            continue

        block, consumed = _parse_line(stripped, base_dir, image_paths)
        if block is not None:
            blocks.append(block)
        i += consumed

    logger.debug(
        "Body parsed",
        block_count=len(blocks),
        image_count=len(image_paths),
        table_count=table_count,
    )
    return blocks, image_paths


def _handle_table(
    lines: list[str],
    i: int,
    base_dir: Path,
    table_count: int,
    blocks: list[ContentBlock],
    image_paths: list[Path],
) -> tuple[int, int]:
    """Process a Markdown table and convert it to an image block."""
    table_lines_end = _consume_table(lines, i)
    image_path = base_dir / "tables" / f"table_{table_count}.png"

    if not image_path.exists():
        logger.warning("Table image not found", expected_path=str(image_path))

    blocks.append(ContentBlock(block_type="image", content="", image_path=image_path))
    image_paths.append(image_path)
    return table_lines_end, table_count + 1


def _parse_line(
    stripped: str,
    base_dir: Path,
    image_paths: list[Path],
) -> tuple[ContentBlock | None, int]:
    """Parse a single non-empty line into a ContentBlock.

    Returns
    -------
    tuple[ContentBlock | None, int]
        The parsed block (or None for unrecognised headings) and the
        number of lines consumed (always 1).
    """
    if stripped.startswith("#"):
        return _parse_heading(stripped), 1

    if stripped == "---":
        return ContentBlock(block_type="separator", content=""), 1

    image_match = _IMAGE_PATTERN.match(stripped)
    if image_match:
        img_path = base_dir / image_match.group(2)
        image_paths.append(img_path)
        return ContentBlock(
            block_type="image",
            content=image_match.group(1),
            image_path=img_path,
        ), 1

    if stripped.startswith("- "):
        return ContentBlock(block_type="list_item", content=stripped[2:]), 1

    if stripped.startswith("> "):
        return ContentBlock(block_type="blockquote", content=stripped[2:]), 1

    return ContentBlock(block_type="paragraph", content=stripped), 1


def _is_table_line(line: str) -> bool:
    """Check if a line is part of a Markdown table.

    Parameters
    ----------
    line : str
        Stripped line text.

    Returns
    -------
    bool
        True if the line starts and ends with ``|`` (table syntax).
    """
    return line.startswith("|") and line.endswith("|")


def _consume_table(lines: list[str], start: int) -> int:
    """Consume consecutive table lines and return the index after the table.

    Parameters
    ----------
    lines : list[str]
        All lines in the body.
    start : int
        Index of the first table line.

    Returns
    -------
    int
        Index of the first non-table line after the table.
    """
    i = start
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped or not _is_table_line(stripped):
            break
        i += 1
    return i


def _parse_heading(line: str) -> ContentBlock | None:
    """Parse a heading line into a ContentBlock.

    Parameters
    ----------
    line : str
        Stripped line starting with ``#``.

    Returns
    -------
    ContentBlock | None
        A heading ContentBlock with appropriate level, or None if
        the heading level exceeds 3.
    """
    if line.startswith("### "):
        return ContentBlock(block_type="heading", content=line[4:].strip(), level=3)
    if line.startswith("## "):
        return ContentBlock(block_type="heading", content=line[3:].strip(), level=2)
    if line.startswith("# "):
        return ContentBlock(block_type="heading", content=line[2:].strip(), level=1)
    return None


def _resolve_title(
    frontmatter: dict[str, Any],
    body_blocks: list[ContentBlock],
) -> str:
    """Resolve the article title from frontmatter or first h1 heading.

    Parameters
    ----------
    frontmatter : dict[str, Any]
        Parsed YAML frontmatter.
    body_blocks : list[ContentBlock]
        Parsed body blocks.

    Returns
    -------
    str
        The resolved title. Frontmatter ``title`` takes priority.
        Falls back to the first h1 heading, then empty string.
    """
    # Priority 1: frontmatter title
    if "title" in frontmatter:
        return str(frontmatter["title"])

    # Priority 2: first h1 heading
    for block in body_blocks:
        if block.block_type == "heading" and block.level == 1:
            return block.content

    return ""
