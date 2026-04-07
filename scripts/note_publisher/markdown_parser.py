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

# AIDEV-NOTE: Numbered list pattern matches "1. text", "2. text", etc.
_NUMBERED_LIST_PATTERN = re.compile(r"^\d+\.\s+(.*)")

# AIDEV-NOTE: Inline bold markdown pattern **text**
_BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")

# AIDEV-NOTE: Inline italic markdown pattern *text* (single asterisk)
_ITALIC_PATTERN = re.compile(r"\*(.+?)\*")

# AIDEV-NOTE: Inline link pattern [text](url) — note.com does not render
# markdown links, so these are stripped to plain text during conversion.
_INLINE_LINK_PATTERN = re.compile(r"\[([^\]]*)\]\([^)]+\)")

# AIDEV-NOTE: Bold-only line pattern — entire line is **text** with no other content.
# These are used as sub-headings in markdown but note.com cannot render bold in
# paragraphs, so they are converted to blockquotes for visual distinction.
_BOLD_ONLY_PATTERN = re.compile(r"^\*\*(.+)\*\*$")

# AIDEV-NOTE: Standard disclaimer text injected when no disclaimer is found in source.
# Matches the text defined in .claude/skills/finance-article-writer/references/common-rules.md
_STANDARD_DISCLAIMER = (
    "免責事項: 本記事は一般的な情報提供を目的としており、特定の金融商品の売買を推奨するものではありません。"
    "投資には元本割れリスクがあります。株式、債券、投資信託、ETF等の金融商品は、市場の変動により価値が上下します。"
    "過去の実績は将来の運用成果を保証するものではありません。本記事に含まれる見通しや予測は、"
    "作成時点の情報に基づくものであり、将来の結果を保証するものではありません。"
    "NISA等の税制優遇制度の内容は、税制改正により変更される可能性があります。"
    "投資に関する最終決定は、ご自身の判断と責任において行ってください。"
)


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
    body_text = _remove_references_section(body_text)
    body_blocks, image_paths = _parse_body(body_text, draft_path.parent)
    title = _resolve_title(frontmatter, body_blocks)
    body_blocks = _remove_title_from_body(body_blocks)
    body_blocks = _relocate_disclaimer(body_blocks)
    body_blocks = _insert_paragraph_spacing(body_blocks)

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


# AIDEV-NOTE: References section headings observed in existing drafts.
# When the list grows, update this tuple rather than scattering string
# literals across the codebase.
_REFERENCES_HEADINGS: tuple[str, ...] = (
    "## 参考データソース",
    "## 参考情報",
)


def _remove_references_section(body: str) -> str:
    """Remove the references section (``## 参考データソース`` / ``## 参考情報``).

    note.com 下書きに参考データソース節を載せない方針のため、
    当該見出しから次の区切り（``免責事項`` 段落または次の ``## `` 見出し、
    それもなければ本文末尾）までを削除する。前後の ``---`` 区切り線は
    触らず、``_relocate_disclaimer`` 側で末尾の余剰 separator を刈る。

    Parameters
    ----------
    body : str
        Markdown body text (after revision history removal).

    Returns
    -------
    str
        Body text with the references section removed.  If no
        references heading is found, returns the input unchanged.
    """
    lines = body.split("\n")

    start_idx = -1
    for i, line in enumerate(lines):
        if line.strip() in _REFERENCES_HEADINGS:
            start_idx = i
            break

    if start_idx == -1:
        return body

    end_idx = len(lines)
    for i in range(start_idx + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("免責事項"):
            end_idx = i
            break
        if (
            stripped.startswith("## ") or stripped.startswith("# ")
        ) and stripped not in _REFERENCES_HEADINGS:
            end_idx = i
            break

    logger.debug(
        "references_section_removed",
        start_line=start_idx,
        end_line=end_idx,
        removed_lines=end_idx - start_idx,
    )
    return "\n".join(lines[:start_idx] + lines[end_idx:])


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
    """Process a Markdown table and convert it to an image block.

    The generated image is saved to ``article_root/images/table_N.png``.
    ``article_root`` is one level up from ``base_dir`` (which is ``02_draft/``).
    """
    table_lines_end = _consume_table(lines, i)

    # article root = base_dir (02_draft/) の親ディレクトリ
    article_root = base_dir.parent
    images_dir = article_root / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    image_path = images_dir / f"table_{table_count}.png"

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
        img_path = _resolve_image_path(base_dir, image_match.group(2))
        image_paths.append(img_path)
        return ContentBlock(
            block_type="image",
            content=image_match.group(1),
            image_path=img_path,
        ), 1

    if stripped.startswith("- "):
        return ContentBlock(
            block_type="list_item",
            content=_strip_inline_markdown(stripped[2:]),
        ), 1

    numbered_match = _NUMBERED_LIST_PATTERN.match(stripped)
    if numbered_match:
        return ContentBlock(
            block_type="numbered_list_item",
            content=_strip_inline_markdown(numbered_match.group(1)),
        ), 1

    if stripped.startswith("> "):
        return ContentBlock(
            block_type="blockquote",
            content=_strip_inline_markdown(stripped[2:]),
        ), 1

    return ContentBlock(
        block_type="paragraph",
        content=_strip_inline_markdown(stripped),
    ), 1


def _resolve_image_path(base_dir: Path, relative_path: str) -> Path:
    """Resolve an image path, trying base_dir first then article root.

    The revised_draft.md lives in ``02_draft/`` but image references like
    ``images/table_competition.png`` are relative to the article root
    (one level up).

    Parameters
    ----------
    base_dir : Path
        Directory containing the draft file (``02_draft/``).
    relative_path : str
        Relative image path from the markdown ``![](path)`` syntax.

    Returns
    -------
    Path
        Resolved image path. Prefers the path that actually exists on disk.
    """
    # Try base_dir first (02_draft/images/...)
    candidate = base_dir / relative_path
    if candidate.exists():
        return candidate

    # Try article root (article_dir/images/...) — one level up from 02_draft/
    article_root_candidate = base_dir.parent / relative_path
    if article_root_candidate.exists():
        logger.debug(
            "image_resolved_via_article_root",
            original=relative_path,
            resolved=str(article_root_candidate),
        )
        return article_root_candidate

    # Neither exists; return article root path as the more likely convention
    logger.warning(
        "image_not_found_at_either_path",
        base_dir_path=str(candidate),
        article_root_path=str(article_root_candidate),
    )
    return article_root_candidate


def _strip_inline_markdown(text: str) -> str:
    """Strip inline Markdown formatting that note.com cannot render.

    Removes ``**bold**`` and ``*italic*`` markers. note.com's editor
    does not interpret inline Markdown, so these would appear as
    literal asterisks.

    Parameters
    ----------
    text : str
        Text potentially containing inline Markdown.

    Returns
    -------
    str
        Text with inline formatting markers removed.
    """
    # Strip inline links first, then bold (**text**), then italic (*text*)
    result = _INLINE_LINK_PATTERN.sub(r"\1", text)
    result = _BOLD_PATTERN.sub(r"\1", result)
    return _ITALIC_PATTERN.sub(r"\1", result)


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
        return ContentBlock(
            block_type="heading",
            content=_strip_inline_markdown(line[4:].strip()),
            level=3,
        )
    if line.startswith("## "):
        return ContentBlock(
            block_type="heading",
            content=_strip_inline_markdown(line[3:].strip()),
            level=2,
        )
    if line.startswith("# "):
        return ContentBlock(
            block_type="heading",
            content=_strip_inline_markdown(line[2:].strip()),
            level=1,
        )
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


def _remove_title_from_body(
    body_blocks: list[ContentBlock],
) -> list[ContentBlock]:
    """Remove h1 heading blocks from the body.

    The article title is set separately in note.com's title field,
    so h1 headings in the body would create a duplicate.

    Parameters
    ----------
    body_blocks : list[ContentBlock]
        Parsed body blocks.

    Returns
    -------
    list[ContentBlock]
        Body blocks with h1 headings removed.
    """
    return [
        block
        for block in body_blocks
        if not (block.block_type == "heading" and block.level == 1)
    ]


def _relocate_disclaimer(
    body_blocks: list[ContentBlock],
) -> list[ContentBlock]:
    """Move disclaimer blocks to the end of the article.

    Detects blocks containing ``免責事項`` and relocates them to the
    end, preceded by exactly one separator. Disclaimer text is
    converted to plain paragraphs (no blockquote or other decoration).

    Any trailing ``separator`` blocks that remain after pulling out the
    disclaimer are stripped before appending the canonical separator.
    This ensures the disclaimer is always preceded by a single ``---``
    even if the source markdown contained multiple adjacent separators
    around the disclaimer or references section.

    Parameters
    ----------
    body_blocks : list[ContentBlock]
        Parsed body blocks.

    Returns
    -------
    list[ContentBlock]
        Body blocks with disclaimer moved to end, preceded by exactly
        one separator.
    """
    disclaimer_blocks: list[ContentBlock] = []
    remaining_blocks: list[ContentBlock] = []

    for block in body_blocks:
        if "免責事項" in block.content:
            disclaimer_blocks.append(
                ContentBlock(block_type="paragraph", content=block.content)
            )
        else:
            remaining_blocks.append(block)

    if not disclaimer_blocks:
        # 免責事項ブロックが存在しない場合、標準文を自動挿入する
        result = list(body_blocks)
        while result and result[-1].block_type == "separator":
            result.pop()
        result.append(ContentBlock(block_type="separator", content=""))
        result.append(ContentBlock(block_type="paragraph", content=_STANDARD_DISCLAIMER))
        logger.debug("disclaimer_auto_injected")
        return result

    # Strip trailing separator blocks so exactly one separator precedes
    # the disclaimer regardless of how many were in the source markdown.
    stripped_separator_count = 0
    while remaining_blocks and remaining_blocks[-1].block_type == "separator":
        remaining_blocks.pop()
        stripped_separator_count += 1

    logger.debug(
        "disclaimer_relocated",
        count=len(disclaimer_blocks),
        stripped_trailing_separators=stripped_separator_count,
    )

    remaining_blocks.append(ContentBlock(block_type="separator", content=""))
    remaining_blocks.extend(disclaimer_blocks)
    return remaining_blocks


def _insert_paragraph_spacing(
    body_blocks: list[ContentBlock],
) -> list[ContentBlock]:
    """Insert empty paragraph blocks between consecutive paragraph blocks.

    note.com のエディタでは連続する段落ブロックが視覚的に詰まって
    表示されるため、Markdown 上の段落区切りを「1行空き」として
    note.com に反映するために、連続 ``paragraph`` ブロックの間に
    空の ``paragraph`` ブロックを1つ挿入する。

    対象は ``paragraph`` → ``paragraph`` の遷移のみ。見出し・リスト・
    画像・引用・separator との境界には挿入しない（それらのブロックは
    note.com 側で独自の視覚的分離を持つため）。

    Parameters
    ----------
    body_blocks : list[ContentBlock]
        Parsed body blocks (after disclaimer relocation).

    Returns
    -------
    list[ContentBlock]
        Body blocks with empty paragraph spacers inserted between
        consecutive paragraph blocks.
    """
    if not body_blocks:
        return body_blocks

    result: list[ContentBlock] = []
    inserted_count = 0
    for i, block in enumerate(body_blocks):
        result.append(block)
        if (
            block.block_type == "paragraph"
            and i + 1 < len(body_blocks)
            and body_blocks[i + 1].block_type == "paragraph"
        ):
            result.append(ContentBlock(block_type="paragraph", content=""))
            inserted_count += 1

    if inserted_count > 0:
        logger.debug(
            "paragraph_spacing_inserted",
            spacer_count=inserted_count,
            total_blocks=len(result),
        )
    return result
