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
        """h2, h3 が body_blocks に含まれ、h1 はタイトルに移動して本文から除去されることを確認。"""
        md = """\
# 大見出し

## 中見出し

### 小見出し
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        # h1 はタイトルとして抽出され、本文からは除去される
        assert result.title == "大見出し"

        headings = [b for b in result.body_blocks if b.block_type == "heading"]
        assert len(headings) == 2

        assert headings[0].content == "中見出し"
        assert headings[0].level == 2

        assert headings[1].content == "小見出し"
        assert headings[1].level == 3


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
        """``![alt](path)`` パターンが image ブロックとしてパースされることを確認。

        実運用では ``02_draft/revised_draft.md`` から ``images/chart.png``
        を参照すると、article root (tmp_path) の ``images/`` にフォールバック
        して解決される。
        """
        md = """\
# タイトル

![グラフ画像](images/chart.png)
"""
        # 実運用の構造を再現: article_root/02_draft/revised_draft.md
        draft_dir = tmp_path / "02_draft"
        draft_dir.mkdir()
        draft_path = draft_dir / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        # 画像は article root の images/ に配置
        images_dir = tmp_path / "images"
        images_dir.mkdir()
        (images_dir / "chart.png").write_bytes(b"fake png")

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
        """Markdown テーブルが ``images/table_0.png`` の画像ブロックに変換されることを確認。"""
        md = """\
# タイトル

テーブルの前の段落。

| 銘柄 | 価格 |
|------|------|
| AAPL | 150  |
| GOOG | 140  |

テーブルの後の段落。
"""
        # 実運用の構造を再現: article_root/02_draft/revised_draft.md
        draft_dir = tmp_path / "02_draft"
        draft_dir.mkdir()
        draft_path = draft_dir / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        # 画像を article root の images/ に作成
        images_dir = tmp_path / "images"
        images_dir.mkdir()
        (images_dir / "table_0.png").write_bytes(b"fake png")

        result = parse_draft(draft_path)

        images = [b for b in result.body_blocks if b.block_type == "image"]
        assert len(images) == 1
        assert images[0].image_path == images_dir / "table_0.png"

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
        # 実運用の構造を再現
        draft_dir = tmp_path / "02_draft"
        draft_dir.mkdir()
        draft_path = draft_dir / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        # 画像を article root の images/ に作成
        images_dir = tmp_path / "images"
        images_dir.mkdir()
        (images_dir / "table_0.png").write_bytes(b"fake png 0")
        (images_dir / "table_1.png").write_bytes(b"fake png 1")

        result = parse_draft(draft_path)

        images = [b for b in result.body_blocks if b.block_type == "image"]
        assert len(images) == 2
        assert images[0].image_path == images_dir / "table_0.png"
        assert images[1].image_path == images_dir / "table_1.png"

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
        # 実運用の構造を再現
        draft_dir = tmp_path / "02_draft"
        draft_dir.mkdir()
        draft_path = draft_dir / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

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
        # 実運用の構造を再現
        draft_dir = tmp_path / "02_draft"
        draft_dir.mkdir()
        draft_path = draft_dir / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        # 画像は article root の images/ に配置
        images_dir = tmp_path / "images"
        images_dir.mkdir()
        (images_dir / "fig1.png").write_bytes(b"fake png")
        (images_dir / "fig2.png").write_bytes(b"fake png")

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
        # 実運用の構造を再現
        draft_dir = tmp_path / "02_draft"
        draft_dir.mkdir()
        draft_path = draft_dir / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        images_dir = tmp_path / "images"
        images_dir.mkdir()
        (images_dir / "table_0.png").write_bytes(b"fake")

        result = parse_draft(draft_path)

        assert images_dir / "table_0.png" in result.image_paths


# =============================================================================
# インラインURL削除
# =============================================================================


class TestInlineLinkStripping:
    """インラインリンク [text](url) の除去テスト。"""

    def test_正常系_段落内のインラインリンクがテキストのみになる(
        self, tmp_path: Path
    ) -> None:
        md = """\
# タイトル

純資産総額が[10兆円に到達](https://example.com/source)しました。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        paragraphs = [b for b in result.body_blocks if b.block_type == "paragraph"]
        assert len(paragraphs) == 1
        assert paragraphs[0].content == "純資産総額が10兆円に到達しました。"

    def test_正常系_出典リンクがテキストのみになる(self, tmp_path: Path) -> None:
        md = """\
# タイトル

重要なデータです（出典：[金融庁](https://www.fsa.go.jp/)）。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        paragraphs = [b for b in result.body_blocks if b.block_type == "paragraph"]
        assert paragraphs[0].content == "重要なデータです（出典：金融庁）。"

    def test_正常系_見出し内のリンクも除去される(self, tmp_path: Path) -> None:
        md = """\
# タイトル

## [公式レポート](https://example.com)の要約
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        headings = [b for b in result.body_blocks if b.block_type == "heading"]
        assert headings[0].content == "公式レポートの要約"

    def test_正常系_リスト項目内のリンクも除去される(self, tmp_path: Path) -> None:
        md = """\
# タイトル

- [三菱UFJ銀行](https://www.bk.mufg.jp/)の報告
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        items = [b for b in result.body_blocks if b.block_type == "list_item"]
        assert items[0].content == "三菱UFJ銀行の報告"


# =============================================================================
# ディスクレーマー末尾移動
# =============================================================================


class TestDisclaimerRelocation:
    """免責事項ブロックの末尾移動テスト。"""

    def test_正常系_太字ディスクレーマーが末尾に移動する(self, tmp_path: Path) -> None:
        md = """\
# タイトル

**免責事項**: 本記事は情報提供を目的としており、投資勧誘ではありません。

## 第1章

本文テキスト。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        # 末尾が separator → disclaimer の順
        assert result.body_blocks[-2].block_type == "separator"
        assert result.body_blocks[-1].block_type == "paragraph"
        assert "免責事項" in result.body_blocks[-1].content

        # disclaimer が本文の途中にないことを確認
        non_tail = result.body_blocks[:-2]
        assert all("免責事項" not in b.content for b in non_tail)

    def test_正常系_引用ブロックのディスクレーマーが段落に変換される(
        self, tmp_path: Path
    ) -> None:
        md = """\
# タイトル

## 本文

テキスト。

> **免責事項**: 投資判断は自己責任で行ってください。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        # blockquote ではなく paragraph に変換される
        assert result.body_blocks[-1].block_type == "paragraph"
        assert result.body_blocks[-2].block_type == "separator"

    def test_エッジケース_ディスクレーマーがない場合は変更なし(
        self, tmp_path: Path
    ) -> None:
        md = """\
# タイトル

## セクション

本文のみ。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        # separator が追加されていないことを確認
        assert result.body_blocks[-1].block_type == "paragraph"
        assert result.body_blocks[-1].content == "本文のみ。"


# =============================================================================
# タイトル本文除去
# =============================================================================


class TestTitleRemovalFromBody:
    """h1 見出しが本文から除去されるテスト。"""

    def test_正常系_h1がbody_blocksに含まれない(self, tmp_path: Path) -> None:
        md = """\
# 記事タイトル

## セクション1

本文。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        assert result.title == "記事タイトル"

        h1_blocks = [
            b for b in result.body_blocks if b.block_type == "heading" and b.level == 1
        ]
        assert len(h1_blocks) == 0

    def test_正常系_frontmatterタイトル時もh1は除去される(self, tmp_path: Path) -> None:
        md = """\
---
title: FMタイトル
---

# Markdownタイトル

本文。
"""
        draft_path = tmp_path / "revised_draft.md"
        draft_path.write_text(md, encoding="utf-8")

        result = parse_draft(draft_path)

        assert result.title == "FMタイトル"

        h1_blocks = [
            b for b in result.body_blocks if b.block_type == "heading" and b.level == 1
        ]
        assert len(h1_blocks) == 0
