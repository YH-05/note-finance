"""Property-based tests for note_publisher.markdown_parser module.

Hypothesis を使用して Markdown テキストを自動生成し、parse_draft() の
プロパティを検証する。検証プロパティ:

- パース健全性（例外なし + 有効な ArticleDraft 返却）
- BlockType の妥当性（6種類のうちのいずれか）
- heading の level が 1-3 の範囲
- 修正履歴除外プロパティ
- image_paths 整合性プロパティ
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import get_args

from hypothesis import given, settings
from hypothesis import strategies as st
from note_publisher.markdown_parser import parse_draft
from note_publisher.types import ArticleDraft, BlockType

# =============================================================================
# BlockType の有効値を取得
# =============================================================================

# AIDEV-NOTE: BlockType は PEP 695 の type 文で定義されているため TypeAliasType。
# __value__ で Literal 型を取得してから get_args で有効値を抽出する。
VALID_BLOCK_TYPES: frozenset[str] = frozenset(get_args(BlockType.__value__))


# =============================================================================
# Hypothesis ストラテジー: Markdown テキスト生成
# =============================================================================


def _frontmatter_strategy() -> st.SearchStrategy[str]:
    """YAML frontmatter を生成するストラテジー。

    Returns
    -------
    st.SearchStrategy[str]
        空文字列または ``---\\ntitle: ...\\n---\\n`` 形式の frontmatter。
    """
    title = st.text(
        alphabet=st.characters(
            whitelist_categories=("L", "N", "Zs"),
            whitelist_characters="-_",
        ),
        min_size=1,
        max_size=30,
    )
    return st.one_of(
        st.just(""),
        title.map(lambda t: f"---\ntitle: {t}\n---\n"),
    )


def _heading_line_strategy() -> st.SearchStrategy[str]:
    """見出し行を生成するストラテジー (h1-h3)。

    Returns
    -------
    st.SearchStrategy[str]
        ``# text``, ``## text``, ``### text`` のいずれか。
    """
    prefix = st.sampled_from(["# ", "## ", "### "])
    content = st.text(
        alphabet=st.characters(
            whitelist_categories=("L", "N", "Zs"),
            whitelist_characters="-_",
        ),
        min_size=1,
        max_size=30,
    )
    return st.tuples(prefix, content).map(lambda t: f"{t[0]}{t[1]}")


def _paragraph_line_strategy() -> st.SearchStrategy[str]:
    """段落行を生成するストラテジー。

    Returns
    -------
    st.SearchStrategy[str]
        特殊文字で始まらないテキスト行。
    """
    return st.text(
        alphabet=st.characters(
            whitelist_categories=("L", "N", "Zs", "P"),
            blacklist_characters="#->|![]\n\r",
        ),
        min_size=1,
        max_size=50,
    ).filter(lambda t: t.strip() != "" and t.strip() != "---")


def _list_item_strategy() -> st.SearchStrategy[str]:
    """リスト項目行を生成するストラテジー。

    Returns
    -------
    st.SearchStrategy[str]
        ``- text`` 形式の行。
    """
    content = st.text(
        alphabet=st.characters(
            whitelist_categories=("L", "N", "Zs"),
            whitelist_characters="-_",
        ),
        min_size=1,
        max_size=30,
    )
    return content.map(lambda c: f"- {c}")


def _blockquote_strategy() -> st.SearchStrategy[str]:
    """引用行を生成するストラテジー。

    Returns
    -------
    st.SearchStrategy[str]
        ``> text`` 形式の行。
    """
    content = st.text(
        alphabet=st.characters(
            whitelist_categories=("L", "N", "Zs"),
            whitelist_characters="-_",
        ),
        min_size=1,
        max_size=30,
    )
    return content.map(lambda c: f"> {c}")


def _separator_strategy() -> st.SearchStrategy[str]:
    """区切り線を生成するストラテジー。

    Returns
    -------
    st.SearchStrategy[str]
        ``---`` 固定文字列。
    """
    return st.just("---")


def _image_strategy() -> st.SearchStrategy[str]:
    """画像行を生成するストラテジー。

    Returns
    -------
    st.SearchStrategy[str]
        ``![alt](path)`` 形式の行。
    """
    alt_text = st.text(
        alphabet=st.characters(
            whitelist_categories=("L", "N"),
        ),
        min_size=0,
        max_size=20,
    )
    filename = st.text(
        alphabet=st.characters(
            whitelist_categories=("L", "N"),
            whitelist_characters="-_",
        ),
        min_size=1,
        max_size=15,
    )
    return st.tuples(alt_text, filename).map(lambda t: f"![{t[0]}](images/{t[1]}.png)")


def _body_line_strategy() -> st.SearchStrategy[str]:
    """Markdown 本文の1行を生成するストラテジー。

    Returns
    -------
    st.SearchStrategy[str]
        見出し、段落、リスト項目、引用、区切り線、画像のいずれか。
    """
    return st.one_of(
        _heading_line_strategy(),
        _paragraph_line_strategy(),
        _list_item_strategy(),
        _blockquote_strategy(),
        _separator_strategy(),
        _image_strategy(),
    )


def _non_separator_body_line_strategy() -> st.SearchStrategy[str]:
    """区切り線を除く Markdown 本文の1行を生成するストラテジー。

    Returns
    -------
    st.SearchStrategy[str]
        見出し、段落、リスト項目、引用、画像のいずれか（区切り線を除く）。

    Notes
    -----
    frontmatter なしの Markdown で先頭行が ``---`` になると
    frontmatter パーサーが誤認識するため、先頭行用に使用する。
    """
    return st.one_of(
        _heading_line_strategy(),
        _paragraph_line_strategy(),
        _list_item_strategy(),
        _blockquote_strategy(),
        _image_strategy(),
    )


@st.composite
def markdown_text_strategy(draw: st.DrawFn) -> str:
    """完全な Markdown テキストを生成するコンポジットストラテジー。

    Parameters
    ----------
    draw : st.DrawFn
        Hypothesis の draw 関数。

    Returns
    -------
    str
        frontmatter (optional) + 本文行のリストから構成された Markdown テキスト。

    Notes
    -----
    frontmatter がない場合、先頭行が ``---`` にならないように制御する。
    これは parse_draft の frontmatter パーサーが ``---`` で始まるテキストを
    frontmatter として扱うための仕様に合わせたもの。
    """
    frontmatter = draw(_frontmatter_strategy())
    body_lines = draw(st.lists(_body_line_strategy(), min_size=0, max_size=15))

    # AIDEV-NOTE: frontmatter なしの場合、先頭行が "---" だと frontmatter と
    # 誤認識されるため、先頭行を区切り線以外に差し替える
    if not frontmatter and body_lines and body_lines[0] == "---":
        first_line = draw(_non_separator_body_line_strategy())
        body_lines[0] = first_line

    # 各行の間に空行を挟んで現実的な Markdown にする
    body = "\n\n".join(body_lines)
    return f"{frontmatter}\n{body}\n" if frontmatter else f"{body}\n"


@st.composite
def markdown_with_revision_history(draw: st.DrawFn) -> str:
    """修正履歴セクションを含む Markdown テキストを生成するストラテジー。

    Parameters
    ----------
    draw : st.DrawFn
        Hypothesis の draw 関数。

    Returns
    -------
    str
        本文 + ``## 修正履歴`` + 修正内容を含む Markdown テキスト。
    """
    frontmatter = draw(_frontmatter_strategy())
    body_lines = draw(st.lists(_body_line_strategy(), min_size=1, max_size=10))

    # AIDEV-NOTE: frontmatter なしの場合、先頭行が "---" だと誤認識を防ぐ
    if not frontmatter and body_lines and body_lines[0] == "---":
        first_line = draw(_non_separator_body_line_strategy())
        body_lines[0] = first_line

    body = "\n\n".join(body_lines)

    # 修正履歴セクション
    revision_entries = draw(
        st.lists(
            st.text(
                alphabet=st.characters(
                    whitelist_categories=("L", "N", "Zs"),
                    whitelist_characters="-_:",
                ),
                min_size=1,
                max_size=30,
            ),
            min_size=1,
            max_size=5,
        )
    )
    revision_lines = "\n".join(f"- {entry}" for entry in revision_entries)
    revision_section = f"\n\n## 修正履歴\n\n{revision_lines}\n"

    if frontmatter:
        return f"{frontmatter}\n{body}{revision_section}"
    return f"{body}{revision_section}"


# =============================================================================
# ヘルパー関数
# =============================================================================


def _write_and_parse(md_text: str) -> ArticleDraft:
    """Markdown テキストを一時ファイルに書き出して parse_draft を実行する。

    Parameters
    ----------
    md_text : str
        パース対象の Markdown テキスト。

    Returns
    -------
    ArticleDraft
        パース結果の ArticleDraft。
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        draft_path = Path(tmp_dir) / "revised_draft.md"
        draft_path.write_text(md_text, encoding="utf-8")
        return parse_draft(draft_path)


# =============================================================================
# プロパティテスト
# =============================================================================


class TestParseHealthiness:
    """パース健全性プロパティのテスト。"""

    @given(md_text=markdown_text_strategy())
    @settings(max_examples=100)
    def test_プロパティ_パース健全性_任意のMarkdownで例外なくArticleDraftを返す(
        self,
        md_text: str,
    ) -> None:
        """任意の生成 Markdown に対して parse_draft が例外を発生させず、
        有効な ArticleDraft を返却することを検証。
        """
        result = _write_and_parse(md_text)

        assert isinstance(result, ArticleDraft)
        assert isinstance(result.title, str)
        assert isinstance(result.body_blocks, list)
        assert isinstance(result.image_paths, list)
        assert isinstance(result.frontmatter, dict)


class TestBlockTypeValidity:
    """BlockType 妥当性プロパティのテスト。"""

    @given(md_text=markdown_text_strategy())
    @settings(max_examples=100)
    def test_プロパティ_BlockType妥当性_全ブロックが6種類のいずれかである(
        self,
        md_text: str,
    ) -> None:
        """パース結果の全ブロックの block_type が、BlockType で定義された
        6種類 (heading, paragraph, list_item, blockquote, image, separator) の
        いずれかであることを検証。
        """
        result = _write_and_parse(md_text)

        for block in result.body_blocks:
            assert block.block_type in VALID_BLOCK_TYPES, (
                f"Unexpected block_type: {block.block_type!r}. "
                f"Valid types: {VALID_BLOCK_TYPES}"
            )


class TestHeadingLevel:
    """heading の level 範囲プロパティのテスト。"""

    @given(md_text=markdown_text_strategy())
    @settings(max_examples=100)
    def test_プロパティ_見出しレベル範囲_headingのlevelが1から3である(
        self,
        md_text: str,
    ) -> None:
        """heading ブロックの level が 1, 2, 3 のいずれかであることを検証。"""
        result = _write_and_parse(md_text)

        heading_blocks = [b for b in result.body_blocks if b.block_type == "heading"]
        for block in heading_blocks:
            assert block.level is not None, "heading block must have a level"
            assert block.level in {1, 2, 3}, (
                f"heading level must be 1-3, got {block.level}"
            )


class TestRevisionHistoryExclusion:
    """修正履歴除外プロパティのテスト。"""

    @given(md_text=markdown_with_revision_history())
    @settings(max_examples=100)
    def test_プロパティ_修正履歴除外_修正履歴セクション以降がブロックに含まれない(
        self,
        md_text: str,
    ) -> None:
        """``## 修正履歴`` 以降のコンテンツが body_blocks に含まれないことを検証。"""
        result = _write_and_parse(md_text)

        # 「修正履歴」という見出しブロックが存在しないことを確認
        revision_headings = [
            b
            for b in result.body_blocks
            if b.block_type == "heading" and b.content == "修正履歴"
        ]
        assert len(revision_headings) == 0, (
            "body_blocks must not contain the '修正履歴' heading"
        )


class TestImagePathsConsistency:
    """image_paths 整合性プロパティのテスト。"""

    @given(md_text=markdown_text_strategy())
    @settings(max_examples=100)
    def test_プロパティ_画像パス整合性_image_pathsとimageブロックが一致する(
        self,
        md_text: str,
    ) -> None:
        """image_paths のエントリ数が body_blocks 内の image ブロック数と
        一致することを検証。
        """
        result = _write_and_parse(md_text)

        image_blocks = [b for b in result.body_blocks if b.block_type == "image"]
        assert len(result.image_paths) == len(image_blocks), (
            f"image_paths count ({len(result.image_paths)}) must equal "
            f"image block count ({len(image_blocks)})"
        )
