"""Unit tests for note_publisher.markdown_parser module.

revised_draft.md を ArticleDraft に変換する parse_draft() 関数のテスト。
YAML frontmatter 抽出、修正履歴除外、6種類のブロックパース、テーブル→画像変換を検証する。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from note_publisher.markdown_parser import parse_draft
from note_publisher.types import ArticleDraft
from structlog.testing import capture_logs

if TYPE_CHECKING:
    from pathlib import Path

# =============================================================================
# Frontmatter
# =============================================================================


class TestFrontmatter:
    """YAML frontmatter の抽出テスト。"""

    def test_正常系_frontmatterを正しく抽出できる(self, tmp_path: Path) -> None:
        """YAML frontmatter が ArticleDraft.frontmatter に正しく格納されることを確認。"""
        md = """\
---
title: テスト記事タイトル
category: investment
tags:
  - 投資
  - 資産形成
---

# テスト記事タイトル

本文テキスト。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        assert isinstance(result, ArticleDraft)
        assert result.frontmatter["title"] == "テスト記事タイトル"
        assert result.frontmatter["category"] == "investment"
        assert result.frontmatter["tags"] == ["投資", "資産形成"]
        assert result.title == "テスト記事タイトル"

    def test_エッジケース_frontmatterがない場合(self, tmp_path: Path) -> None:
        """frontmatter がない Markdown でも正常にパースできることを確認。"""
        md = """\
# タイトルのみ

本文テキスト。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        assert result.frontmatter == {}
        assert result.title == "タイトルのみ"


# =============================================================================
# 修正履歴の除外
# =============================================================================


class TestRevisionHistory:
    """修正履歴セクションの除外テスト。"""

    def test_正常系_修正履歴を除外できる(self, tmp_path: Path) -> None:
        """``## 修正履歴`` セクション以降が body_blocks に含まれないことを確認。"""
        md = """\
---
title: 修正履歴テスト
---

# 修正履歴テスト

本文テキスト。

## 修正履歴

- 2024-01-01: 初版作成
- 2024-01-02: 誤字修正
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        # 修正履歴セクションの内容がブロックに含まれないことを確認
        all_content = " ".join(b.content for b in result.body_blocks)
        assert "初版作成" not in all_content
        assert "誤字修正" not in all_content

        # 「## 修正履歴」という見出しブロック自体もないことを確認
        revision_headings = [
            b
            for b in result.body_blocks
            if b.block_type == "heading" and b.content == "修正履歴"
        ]
        assert len(revision_headings) == 0

        # 本文テキストは含まれる
        assert any(b.content == "本文テキスト。" for b in result.body_blocks)


# =============================================================================
# ブロックパース（6種類）
# =============================================================================


class TestHeadingBlock:
    """見出しブロックのテスト。"""

    def test_正常系_見出しブロックを正しくパースできる(self, tmp_path: Path) -> None:
        """h1, h2, h3 がそれぞれ正しい level の heading ブロックになることを確認。"""
        md = """\
# 大見出し

## 中見出し

### 小見出し
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        headings = [b for b in result.body_blocks if b.block_type == "heading"]
        assert len(headings) == 3

        assert headings[0].content == "大見出し"
        assert headings[0].level == 1

        assert headings[1].content == "中見出し"
        assert headings[1].level == 2

        assert headings[2].content == "小見出し"
        assert headings[2].level == 3


class TestParagraphBlock:
    """段落ブロックのテスト。"""

    def test_正常系_段落ブロックを正しくパースできる(self, tmp_path: Path) -> None:
        """通常テキスト行が paragraph ブロックとしてパースされることを確認。"""
        md = """\
# タイトル

最初の段落です。

二番目の段落です。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        paragraphs = [b for b in result.body_blocks if b.block_type == "paragraph"]
        assert len(paragraphs) == 2
        assert paragraphs[0].content == "最初の段落です。"
        assert paragraphs[1].content == "二番目の段落です。"


class TestListItemBlock:
    """リスト項目ブロックのテスト。"""

    def test_正常系_リスト項目を正しくパースできる(self, tmp_path: Path) -> None:
        """``- `` で始まる行が list_item ブロックとしてパースされることを確認。"""
        md = """\
# タイトル

- 項目1
- 項目2
- 項目3
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        list_items = [b for b in result.body_blocks if b.block_type == "list_item"]
        assert len(list_items) == 3
        assert list_items[0].content == "項目1"
        assert list_items[1].content == "項目2"
        assert list_items[2].content == "項目3"


class TestBlockquoteBlock:
    """引用ブロックのテスト。"""

    def test_正常系_引用ブロックを正しくパースできる(self, tmp_path: Path) -> None:
        """``> `` で始まる行が blockquote ブロックとしてパースされることを確認。"""
        md = """\
# タイトル

> これは引用テキストです。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        quotes = [b for b in result.body_blocks if b.block_type == "blockquote"]
        assert len(quotes) == 1
        assert quotes[0].content == "これは引用テキストです。"


class TestSeparatorBlock:
    """区切り線ブロックのテスト。"""

    def test_正常系_区切り線を正しくパースできる(self, tmp_path: Path) -> None:
        """``---`` 行が separator ブロックとしてパースされることを確認。"""
        md = """\
# タイトル

本文1

---

本文2
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        separators = [b for b in result.body_blocks if b.block_type == "separator"]
        assert len(separators) == 1
        assert separators[0].content == ""


class TestImageBlock:
    """画像ブロックのテスト。"""

    def test_正常系_画像ブロックを正しくパースできる(self, tmp_path: Path) -> None:
        """``![alt](path)`` パターンが image ブロックとしてパースされることを確認。"""
        md = """\
# タイトル

![グラフ画像](images/chart.png)
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        images = [b for b in result.body_blocks if b.block_type == "image"]
        assert len(images) == 1
        assert images[0].content == "グラフ画像"
        assert images[0].image_path == tmp_path / "images" / "chart.png"


# =============================================================================
# テーブル→画像変換
# =============================================================================


class TestTableToImage:
    """テーブル→画像変換のテスト。"""

    def test_正常系_テーブルを画像ブロックに変換できる(self, tmp_path: Path) -> None:
        """Markdown テーブルが ``tables/table_0.png`` の画像ブロックに変換されることを確認。"""
        md = """\
# タイトル

テーブルの前の段落。

| 銘柄 | 価格 |
|------|------|
| AAPL | 150  |
| GOOG | 140  |

テーブルの後の段落。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        # tables ディレクトリと画像を作成
        tables_dir = tmp_path / "tables"
        tables_dir.mkdir()
        (tables_dir / "table_0.png").write_bytes(b"fake png")

        result = parse_draft(draft_path)

        images = [b for b in result.body_blocks if b.block_type == "image"]
        assert len(images) == 1
        assert images[0].image_path == tables_dir / "table_0.png"

        # テーブルの生テキストがブロックに残っていないことを確認
        all_content = " ".join(b.content for b in result.body_blocks)
        assert "| 銘柄" not in all_content
        assert "|------" not in all_content

    def test_正常系_複数テーブルの連番が正しい(self, tmp_path: Path) -> None:
        """複数のテーブルが出現順に ``table_0.png``, ``table_1.png`` と変換されることを確認。"""
        md = """\
# タイトル

| A | B |
|---|---|
| 1 | 2 |

中間テキスト。

| C | D |
|---|---|
| 3 | 4 |
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        # tables ディレクトリと画像を作成
        tables_dir = tmp_path / "tables"
        tables_dir.mkdir()
        (tables_dir / "table_0.png").write_bytes(b"fake png 0")
        (tables_dir / "table_1.png").write_bytes(b"fake png 1")

        result = parse_draft(draft_path)

        images = [b for b in result.body_blocks if b.block_type == "image"]
        assert len(images) == 2
        assert images[0].image_path == tables_dir / "table_0.png"
        assert images[1].image_path == tables_dir / "table_1.png"

    def test_エッジケース_テーブルPNGが存在しない場合(
        self,
        tmp_path: Path,
    ) -> None:
        """テーブル PNG が存在しない場合に警告ログが出力されることを確認。"""
        md = """\
# タイトル

| X | Y |
|---|---|
| 1 | 2 |
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        # tables ディレクトリを作成するがPNGは配置しない
        (tmp_path / "tables").mkdir()

        with capture_logs() as cap_logs:
            result = parse_draft(draft_path)

        # 画像ブロックは生成されるがファイルが見つからない警告が出る
        images = [b for b in result.body_blocks if b.block_type == "image"]
        assert len(images) == 1

        # structlog.testing.capture_logs で警告ログをキャプチャ
        warning_logs = [log for log in cap_logs if log.get("log_level") == "warning"]
        assert len(warning_logs) >= 1
        assert "table_0.png" in str(warning_logs[0].get("expected_path", ""))


# =============================================================================
# エッジケース
# =============================================================================


class TestEdgeCases:
    """エッジケースのテスト。"""

    def test_エッジケース_空のファイル(self, tmp_path: Path) -> None:
        """空のファイルでもエラーなくパースできることを確認。"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text("", encoding="utf-8")

        result = parse_draft(draft_path)

        assert isinstance(result, ArticleDraft)
        assert result.title == ""
        assert result.body_blocks == []
        assert result.frontmatter == {}

    def test_正常系_image_pathsに画像パスが収集される(self, tmp_path: Path) -> None:
        """body_blocks 内の image ブロックのパスが image_paths にも収集されることを確認。"""
        md = """\
# タイトル

![画像1](images/fig1.png)

テキスト段落。

![画像2](images/fig2.png)
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        assert len(result.image_paths) == 2
        assert tmp_path / "images" / "fig1.png" in result.image_paths
        assert tmp_path / "images" / "fig2.png" in result.image_paths

    def test_正常系_titleはfrontmatterのtitleを優先する(self, tmp_path: Path) -> None:
        """frontmatter に title がある場合はそちらを優先することを確認。"""
        md = """\
---
title: frontmatterのタイトル
---

# Markdownのタイトル

本文。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        assert result.title == "frontmatterのタイトル"

    def test_正常系_titleはh1見出しから取得される(self, tmp_path: Path) -> None:
        """frontmatter に title がない場合は最初の h1 見出しをタイトルに使うことを確認。"""
        md = """\
---
category: investment
---

# これがタイトル

本文テキスト。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        assert result.title == "これがタイトル"

    def test_正常系_テーブル画像がimage_pathsに含まれる(self, tmp_path: Path) -> None:
        """テーブルから変換された画像パスも image_paths に含まれることを確認。"""
        md = """\
# タイトル

| A | B |
|---|---|
| 1 | 2 |
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        tables_dir = tmp_path / "tables"
        tables_dir.mkdir()
        (tables_dir / "table_0.png").write_bytes(b"fake")

        result = parse_draft(draft_path)

        assert tables_dir / "table_0.png" in result.image_paths
